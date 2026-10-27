import customtkinter as ctk

from components.cards import SectionCard
from components.dialogs import (
    BaseDialog,
    show_error,
    show_success,
    show_warning,
)
from components.forms import entry_style
from components.page_header import PageHeader
from components.tables import SimpleTable, text_cell
from utils.formatter import format_rupiah
from utils.printer import Printer, PrinterError
from utils.theme import (
    COLORS,
    DIALOG_PADDING,
    DIALOG_WIDTH,
    LAYOUT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)


ITEM_COLUMNS = [
    {"title": "Barang", "weight": 5, "align": "left"},
    {"title": "Harga Beli", "weight": 3, "align": "right"},
    {"title": "Qty", "weight": 2, "align": "center"},
    {"title": "Subtotal", "weight": 3, "align": "right"},
    {"title": "Aksi", "weight": 2, "align": "center"},
]


def _card(parent):
    """Card standar (latar surface, border 1px, radius 12)."""
    return ctk.CTkFrame(
        parent,
        corner_radius=RADIUS["card"],
        fg_color=COLORS["surface"],
        border_width=1,
        border_color=COLORS["border"],
    )


class PurchasePage(ctk.CTkFrame):
    """
    Halaman transaksi Pembelian.

    Pola halaman sama dengan Penjualan: cari barang, daftar barang,
    ringkasan di bawah. Cetak nota memakai Printer standar aplikasi
    (Printer.create_pdf lalu Printer.open_pdf).
    """

    def __init__(self, master, product_model, purchase_model):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.product_model = product_model
        self.purchase_model = purchase_model

        self.items = []
        self.search_results = []
        self.selected_result_index = -1

        # Teks pencarian yang menghasilkan search_results saat ini. Dipakai
        # untuk memastikan Enter tidak memakai hasil dari teks yang sudah lama.
        self._results_query = ""

        self._search_after_id = None
        self._search_popup = None
        self._popup_listbox = None

        self._build_ui()
        self._render_items()
        self._update_total()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # =====================================================
        # HEADER
        # =====================================================

        PageHeader(self, "Pembelian").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        # =====================================================
        # CARD PENCARIAN
        # =====================================================

        input_card = _card(self)
        input_card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, SPACING["md"]),
        )

        input_card.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            input_card,
            placeholder_text="Scan barcode atau cari nama barang...",
            **entry_style(),
        )
        self.search_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(SPACING["lg"], SPACING["sm"]),
            pady=SPACING["md"],
        )

        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Up>", self._select_previous_result)
        self.search_entry.bind("<Down>", self._select_next_result)
        self.search_entry.bind("<Escape>", self._close_search_popup)

        self.quantity_entry = ctk.CTkEntry(
            input_card,
            width=90,
            justify="center",
            placeholder_text="Qty",
            **entry_style(),
        )
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(
            row=0,
            column=1,
            padx=(0, SPACING["sm"]),
            pady=SPACING["md"],
        )

        self.quantity_entry.bind("<Return>", self._on_quantity_enter)

        self.add_button = ctk.CTkButton(
            input_card,
            text="+  Tambah",
            width=105,
            command=self._add_selected_product,
            **button_style("primary"),
        )
        self.add_button.grid(
            row=0,
            column=2,
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"],
        )

        # =====================================================
        # CARD DAFTAR BARANG
        # =====================================================

        transaction_card = SectionCard(self)
        transaction_card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=page_padding,
            pady=(0, SPACING["md"]),
        )

        self.items_table = SimpleTable(
            transaction_card.body,
            ITEM_COLUMNS,
            empty_title="Belum ada barang",
            empty_text=(
                "Scan barcode atau cari nama barang "
                "untuk memulai transaksi."
            ),
            scrollable=True,
        )
        self.items_table.pack(
            fill="both",
            expand=True,
        )

        # =====================================================
        # BAR BAWAH: CATATAN, TOTAL, PROSES
        # =====================================================

        footer = _card(self)
        footer.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, page_padding),
        )

        footer.grid_columnconfigure(0, weight=1)

        self.notes_entry = ctk.CTkEntry(
            footer,
            placeholder_text="Catatan pembelian (opsional)...",
            **entry_style(),
        )
        self.notes_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(SPACING["lg"], SPACING["lg"]),
            pady=SPACING["md"],
        )

        total_frame = ctk.CTkFrame(
            footer,
            fg_color="transparent",
        )
        total_frame.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"],
        )

        ctk.CTkLabel(
            total_frame,
            text="Total Pembelian",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="e")

        self.total_label = ctk.CTkLabel(
            total_frame,
            text="Rp 0",
            font=get_font("title"),
            text_color=COLORS["text"],
        )
        self.total_label.pack(
            anchor="e",
            pady=(SPACING["xs"], 0),
        )

        self.save_button = ctk.CTkButton(
            footer,
            text="Proses",
            width=125,
            command=self._save_transaction,
            **button_style("primary"),
        )
        self.save_button.grid(
            row=0,
            column=2,
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"],
        )

    # =========================================================
    # SEARCH
    # =========================================================

    def _cancel_pending_search(self):
        """Batalkan pencarian terjadwal (jeda 120 ms setelah mengetik)."""
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass

            self._search_after_id = None

    def _find_by_barcode(self, search):
        try:
            return self.product_model.get_by_barcode(
                search,
                active_only=True,
            )
        except Exception:
            return None

    def _on_search_changed(self, event=None):
        if event and event.keysym in (
            "Up",
            "Down",
            "Return",
            "Escape",
        ):
            return

        search = self.search_entry.get().strip()

        self._cancel_pending_search()

        if not search:
            self.search_results = []
            self.selected_result_index = -1
            self._results_query = ""
            self._close_search_popup()
            return

        self._search_after_id = self.after(
            120,
            lambda: self._search_products(search),
        )

    def _search_products(self, search):
        """
        Isi search_results untuk teks `search` dan tampilkan popup.

        Returns False bila pencarian gagal karena error (dialog error
        sudah ditampilkan), True selain itu.
        """
        self._search_after_id = None

        search = (search or "").strip()

        if not search:
            self.search_results = []
            self.selected_result_index = -1
            self._results_query = ""
            self._close_search_popup()
            return True

        # Teks sudah berubah atau barang sudah ditambahkan: hasil ini basi.
        if search != self.search_entry.get().strip():
            return True

        barcode_product = self._find_by_barcode(search)

        if barcode_product:
            self.search_results = [barcode_product]
            self._results_query = search
            self.selected_result_index = 0
            self._show_search_popup()
            return True

        try:
            products = (
                self.product_model.list_products(
                    search=search,
                    include_inactive=False,
                )
            )
        except Exception as e:
            show_error(
                self,
                "Gagal Mencari Barang",
                f"Data barang tidak dapat dicari.\n\n{e}",
            )
            self._close_search_popup()
            return False

        self.search_results = products[:8]
        self._results_query = search

        self.selected_result_index = (
            0
            if len(self.search_results) == 1
            else -1
        )

        if self.search_results:
            self._show_search_popup()
        else:
            self._close_search_popup()

        return True

    # =========================================================
    # SEARCH POPUP
    # =========================================================

    def _show_search_popup(self):
        self._close_search_popup()

        if not self.search_results:
            return

        self.update_idletasks()

        popup = ctk.CTkToplevel(
            self.winfo_toplevel()
        )

        self._search_popup = popup

        popup.overrideredirect(True)
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())

        width = max(
            self.search_entry.winfo_width(),
            420,
        )

        height = min(
            len(self.search_results) * 54 + 10,
            394,
        )

        x = self.search_entry.winfo_rootx()

        y = (
            self.search_entry.winfo_rooty()
            + self.search_entry.winfo_height()
            + 4
        )

        popup.geometry(f"{width}x{height}+{x}+{y}")

        container = ctk.CTkFrame(
            popup,
            corner_radius=RADIUS["medium"],
            border_width=1,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
        )
        container.pack(
            fill="both",
            expand=True,
        )

        self._popup_listbox = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
        )
        self._popup_listbox.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5,
        )

        for index, product in enumerate(self.search_results):
            self._create_popup_result(
                index,
                product,
            )

        self._highlight_popup_result()

    def _create_popup_result(
        self,
        index,
        product,
    ):
        barcode = product.get("barcode") or "-"
        name = product.get("name") or "-"
        price = int(
            product.get("purchase_price") or 0
        )
        stock = int(
            product.get("stock") or 0
        )

        row = ctk.CTkFrame(
            self._popup_listbox,
            corner_radius=RADIUS["small"],
            fg_color="transparent",
        )
        row.pack(
            fill="x",
            pady=1,
        )

        row.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            row,
            text=(
                f"{name}\n"
                f"Barcode: {barcode}   •   "
                f"Harga beli: {format_rupiah(price)}   •   "
                f"Stok: {stock}"
            ),
            anchor="w",
            justify="left",
            height=48,
            font=get_font("body"),
            text_color=COLORS["text"],
        )
        label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=10,
            pady=2,
        )

        for widget in (row, label):
            widget.bind(
                "<Button-1>",
                lambda event, i=index:
                self._popup_click(i),
            )

            widget.bind(
                "<Double-Button-1>",
                lambda event, i=index:
                self._popup_double_click(i),
            )

    def _popup_click(self, index):
        self.selected_result_index = index
        self._highlight_popup_result()

    def _popup_double_click(self, index):
        self.selected_result_index = index
        self._add_selected_product()

    def _highlight_popup_result(self):
        if not self._popup_listbox:
            return

        children = self._popup_listbox.winfo_children()

        for index, widget in enumerate(children):
            if index == self.selected_result_index:
                widget.configure(
                    fg_color=COLORS["table_selected"]
                )
            else:
                widget.configure(
                    fg_color="transparent"
                )

    def _close_search_popup(self, event=None):
        if self._search_popup:
            try:
                self._search_popup.destroy()
            except Exception:
                pass

        self._search_popup = None
        self._popup_listbox = None

        return "break" if event else None

    # =========================================================
    # KEYBOARD NAVIGATION
    # =========================================================

    def _select_next_result(self, event=None):
        if not self.search_results:
            return "break"

        if self.selected_result_index < 0:
            self.selected_result_index = 0

        elif (
            self.selected_result_index
            >= len(self.search_results) - 1
        ):
            self.selected_result_index = 0

        else:
            self.selected_result_index += 1

        self._highlight_popup_result()

        return "break"

    def _select_previous_result(self, event=None):
        if not self.search_results:
            return "break"

        if self.selected_result_index <= 0:
            self.selected_result_index = (
                len(self.search_results) - 1
            )
        else:
            self.selected_result_index -= 1

        self._highlight_popup_result()

        return "break"

    def _on_search_enter(self, event=None):
        """
        Enter di kolom pencarian. Urutan:

        1. Teks cocok persis dengan barcode -> langsung masuk daftar.
           Ini alur scanner: scanner mengirim Enter beberapa milidetik
           setelah karakter terakhir, jauh sebelum pencarian 120 ms selesai.
        2. Ada hasil popup untuk teks yang sama -> pakai baris terpilih
           (Enter pertama hanya menyorot baris pertama).
        3. Selain itu -> cari sekarang tanpa menunggu jeda.
        """
        search = self.search_entry.get().strip()

        if not search:
            return "break"

        self._cancel_pending_search()

        # 1. Barcode persis
        product = self._find_by_barcode(search)

        if product:
            self.search_results = [product]
            self._results_query = search
            self.selected_result_index = 0
            self._add_selected_product()
            return "break"

        # 2. Hasil popup yang masih sesuai dengan teks sekarang
        if self.search_results and self._results_query == search:
            if len(self.search_results) == 1:
                self.selected_result_index = 0
                self._add_selected_product()

            elif self.selected_result_index < 0:
                self.selected_result_index = 0
                self._highlight_popup_result()

            else:
                self._add_selected_product()

            return "break"

        # 3. Cari sekarang
        if not self._search_products(search):
            return "break"

        if not self.search_results:
            show_warning(
                self,
                "Barang Tidak Ditemukan",
                "Barang yang dicari tidak ditemukan.",
            )
            return "break"

        if len(self.search_results) == 1:
            self.selected_result_index = 0
            self._add_selected_product()
        else:
            self.selected_result_index = 0
            self._highlight_popup_result()

        return "break"

    def _on_quantity_enter(self, event=None):
        self._add_selected_product()
        return "break"

    # =========================================================
    # ADD PRODUCT
    # =========================================================

    def _add_selected_product(self):
        if not self.search_results:
            show_warning(
                self,
                "Barang Tidak Ditemukan",
                "Barang yang dicari tidak ditemukan.",
            )
            self.search_entry.focus_set()
            return

        index = self.selected_result_index

        if index < 0:
            if len(self.search_results) == 1:
                index = 0
            else:
                show_warning(
                    self,
                    "Pilih Barang",
                    "Pilih barang dari hasil pencarian terlebih dahulu.",
                )
                return

        if index >= len(self.search_results):
            return

        product = self.search_results[index]

        try:
            quantity = int(
                self.quantity_entry.get().strip()
            )
        except (
            TypeError,
            ValueError,
        ):
            show_warning(
                self,
                "Qty Tidak Valid",
                "Qty harus berupa angka bulat.",
            )
            self.quantity_entry.focus_set()
            self.quantity_entry.select_range(0, "end")
            return

        if quantity <= 0:
            show_warning(
                self,
                "Qty Tidak Valid",
                "Qty harus lebih besar dari 0.",
            )
            self.quantity_entry.focus_set()
            self.quantity_entry.select_range(0, "end")
            return

        product_id = product["id"]
        price = int(product.get("purchase_price") or 0)

        for index, item in enumerate(self.items):
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                self.items.insert(0, self.items.pop(index))
                break
        else:
            self.items.insert(
                0,
                {
                    "product_id": product_id,
                    "product_name": product["name"],
                    "quantity": quantity,
                    "price": price,
                },
            )

        self._render_items()
        self._update_total()

        self.quantity_entry.delete(0, "end")
        self.quantity_entry.insert(0, "1")

        self.search_entry.delete(0, "end")

        self._cancel_pending_search()

        self.search_results = []
        self.selected_result_index = -1
        self._results_query = ""

        self._close_search_popup()

        self.search_entry.focus_set()

    # =========================================================
    # TRANSACTION TABLE
    # =========================================================

    def _render_items(self):
        self.items_table.set_rows(
            [
                self._item_row(row_index, item)
                for row_index, item in enumerate(self.items)
            ]
        )

    def _item_row(self, row_index, item):
        subtotal = item["quantity"] * item["price"]

        return [
            text_cell(
                item["product_name"],
                bold=True,
            ),
            text_cell(format_rupiah(item["price"])),
            lambda parent, i=row_index, q=item["quantity"]: (
                self._build_qty_entry(parent, i, q)
            ),
            text_cell(
                format_rupiah(subtotal),
                bold=True,
            ),
            lambda parent, i=row_index: ctk.CTkButton(
                parent,
                text="Hapus",
                width=64,
                command=lambda: self._remove_item(i),
                **button_style("danger", "small"),
            ),
        ]


    def _build_qty_entry(self, parent, index, quantity):
        style = entry_style()
        style["height"] = 30

        entry = ctk.CTkEntry(
            parent,
            width=70,
            justify="center",
            **style,
        )
        entry.insert(0, str(quantity))
        entry.bind(
            "<Return>",
            lambda event, i=index, e=entry: (
                self._update_item_quantity(i, e)
            ),
        )

        return entry


    def _update_item_quantity(self, index, entry):
        if index < 0 or index >= len(self.items):
            return

        try:
            quantity = int(entry.get().strip())
        except ValueError:
            show_warning(
                self,
                "Qty Tidak Valid",
                "Jumlah harus berupa angka bulat.",
            )
            self._render_items()
            return

        if quantity <= 0:
            show_warning(
                self,
                "Qty Tidak Valid",
                "Jumlah harus lebih besar dari 0.",
            )
            self._render_items()
            return

        self.items[index]["quantity"] = quantity

        self._render_items()
        self._update_total()

    def _remove_item(self, index):
        if index < 0 or index >= len(self.items):
            return

        del self.items[index]

        self._render_items()
        self._update_total()

        self.search_entry.focus_set()

    # =========================================================
    # TOTAL
    # =========================================================

    def _update_total(self):
        total = sum(
            item["quantity"] * item["price"]
            for item in self.items
        )

        self.total_label.configure(
            text=format_rupiah(total)
        )

    # =========================================================
    # SAVE
    # =========================================================

    def _save_transaction(self):
        """Langkah 1: validasi, lalu minta konfirmasi."""
        if not self.items:
            show_warning(
                self,
                "Transaksi Kosong",
                "Tambahkan minimal satu barang.",
            )
            self.search_entry.focus_set()
            return

        total = sum(
            item["quantity"] * item["price"]
            for item in self.items
        )

        PurchaseConfirmDialog(
            self,
            total_text=format_rupiah(total),
            on_confirm=self._process_transaction,
        )

    def _process_transaction(self, print_after: bool = False):
        """Langkah 2: simpan transaksi (dipanggil setelah konfirmasi)."""
        total = sum(
            item["quantity"] * item["price"]
            for item in self.items
        )

        model_items = [
            {
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "price": item["price"],
            }
            for item in self.items
        ]

        self.save_button.configure(state="disabled")

        try:
            (
                success,
                message,
                transaction_id,
            ) = self.purchase_model.create_transaction(
                items=model_items,
                notes=self.notes_entry.get().strip(),
            )
        except Exception as e:
            success = False
            message = f"Terjadi kesalahan: {e}"
            transaction_id = None

        self.save_button.configure(state="normal")

        if not success:
            show_error(
                self,
                "Gagal Memproses",
                message,
            )
            return

        detail = (
            self.purchase_model.get_transaction_detail(
                transaction_id,
            )
        )

        transaction_number = (
            detail["transaction_number"]
            if detail
            else "-"
        )

        # -----------------------------------------------------
        # NOTA PDF (Printer standar aplikasi)
        # -----------------------------------------------------

        pdf_path = None
        printer = None

        if print_after:
            try:
                if not detail:
                    raise PrinterError(
                        "Detail transaksi pembelian tidak ditemukan."
                    )

                printer = Printer()

                pdf_path = printer.create_pdf(
                    "purchase",
                    detail,
                )

            except PrinterError as exc:
                show_warning(
                    self,
                    "Pembelian Berhasil",
                    "Pembelian berhasil disimpan, "
                    f"tetapi nota tidak dapat dibuat.\n\n{exc}",
                )

            except Exception:
                show_warning(
                    self,
                    "Pembelian Berhasil",
                    "Pembelian berhasil disimpan, "
                    "tetapi nota tidak dapat dibuat.",
                )

        self._reset_form()

        result_text = (
            "Transaksi pembelian berhasil diproses.\n\n"
            f"Nomor Transaksi: {transaction_number}\n"
            f"Total: {format_rupiah(total)}"
        )

        if print_after and pdf_path:
            try:
                printer.open_pdf(pdf_path)

                result_text += "\n\nNota PDF telah dibuat."

            except Exception:
                result_text += (
                    "\n\nNota PDF tersimpan di:\n"
                    f"{pdf_path}"
                )

        show_success(
            self,
            "Pembelian Berhasil",
            result_text,
        )

    # =========================================================
    # RESET
    # =========================================================

    def _reset_form(self):
        self.items.clear()

        self.notes_entry.delete(0, "end")

        self.quantity_entry.delete(0, "end")
        self.quantity_entry.insert(0, "1")

        self.search_entry.delete(0, "end")

        self._cancel_pending_search()

        self.search_results = []
        self.selected_result_index = -1
        self._results_query = ""

        self._close_search_popup()
        self._render_items()
        self._update_total()

        self.search_entry.focus_set()

    # =========================================================
    # REFRESH
    # =========================================================

    def refresh(self):
        self._cancel_pending_search()
        self._close_search_popup()

        self.search_results = []
        self.selected_result_index = -1
        self._results_query = ""

        self._render_items()
        self._update_total()

        self.search_entry.focus_set()


class PurchaseConfirmDialog(BaseDialog):
    """Konfirmasi pembelian, dengan opsi cetak nota setelah transaksi."""

    def __init__(
        self,
        master,
        total_text: str,
        on_confirm,
    ):
        super().__init__(
            master,
            "Konfirmasi Pembelian",
            DIALOG_WIDTH["confirm"],
        )

        self.on_confirm = on_confirm

        ctk.CTkLabel(
            self.body,
            text=(
                "Proses transaksi pembelian ini?\n\n"
                f"Total: {total_text}"
            ),
            font=get_font("body"),
            text_color=COLORS["text"],
            wraplength=DIALOG_WIDTH["confirm"] - (DIALOG_PADDING * 2),
            justify="left",
            anchor="w",
        ).pack(fill="x")

        self.print_checkbox = ctk.CTkCheckBox(
            self.body,
            text="Cetak nota setelah transaksi",
            font=get_font("body"),
            text_color=COLORS["text"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            corner_radius=RADIUS["small"],
        )
        self.print_checkbox.pack(
            anchor="w",
            pady=(SPACING["md"], 0),
        )

        self.set_buttons(
            "Proses",
            self._confirm,
            secondary_text="Batal",
        )
        self.finish()

    def _confirm(self):
        print_after = bool(self.print_checkbox.get())

        self.destroy()
        self.on_confirm(print_after)