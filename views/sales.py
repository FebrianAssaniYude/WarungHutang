import customtkinter as ctk

from components.cards import SectionCard
from components.dialogs import (
    BaseDialog,
    show_error,
    show_success,
    show_warning,
)
from components.forms import FormField, entry_style
from components.page_header import PageHeader
from components.tables import SimpleTable, text_cell
from utils.printer import Printer, PrinterError
from utils.formatter import format_rupiah
from utils.theme import (
    COLORS,
    DIALOG_WIDTH,
    LAYOUT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)


CART_COLUMNS = [
    {"title": "Barang", "weight": 5, "align": "left"},
    {"title": "Harga", "weight": 3, "align": "right"},
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


class SalePage(ctk.CTkFrame):
    def __init__(self, parent, product_model, sale_model):
        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.product_model = product_model
        self.sale_model = sale_model

        self.items = []

        self.search_results = []
        self.search_selected_index = -1
        self.search_after_id = None
        self.search_popup = None
        self.popup_listbox = None

        # Teks pencarian yang menghasilkan search_results saat ini. Dipakai
        # untuk memastikan Enter tidak memakai hasil dari teks yang sudah lama.
        self._results_query = ""

        self.payment_popup = None
        self.payment_entry = None
        self.change_value = None
        self.print_checkbox = None

        self.total_value = None

        self._build_ui()
        self._bind_events()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # =====================================================
        # HEADER
        # =====================================================

        PageHeader(self, "Penjualan").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=LAYOUT["header_pady"]
        )

        # =====================================================
        # SEARCH CARD
        # =====================================================

        search_card = _card(self)
        search_card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, SPACING["md"])
        )

        search_card.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_card,
            placeholder_text="Cari barcode atau nama produk...",
            **entry_style()
        )
        self.search_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(SPACING["lg"], SPACING["sm"]),
            pady=SPACING["md"]
        )

        self.qty_entry = ctk.CTkEntry(
            search_card,
            width=90,
            placeholder_text="Qty",
            **entry_style()
        )
        self.qty_entry.grid(
            row=0,
            column=1,
            padx=(0, SPACING["sm"]),
            pady=SPACING["md"]
        )

        self.qty_entry.insert(0, "1")

        ctk.CTkButton(
            search_card,
            text="Tambah",
            width=100,
            command=self._add_from_search,
            **button_style("primary")
        ).grid(
            row=0,
            column=2,
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"]
        )

        # =====================================================
        # CART CARD
        # =====================================================

        cart_card = SectionCard(self)
        cart_card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=page_padding,
            pady=(0, SPACING["md"])
        )

        self.cart_table = SimpleTable(
            cart_card.body,
            CART_COLUMNS,
            empty_title="Belum ada barang",
            empty_text="Cari produk di bagian atas untuk menambahkannya.",
            scrollable=True
        )
        self.cart_table.pack(
            fill="both",
            expand=True
        )

        # =====================================================
        # BOTTOM PAYMENT SUMMARY
        # =====================================================

        bottom_bar = _card(self)
        bottom_bar.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, page_padding)
        )

        bottom_bar.grid_columnconfigure(0, weight=1)

        total_frame = ctk.CTkFrame(
            bottom_bar,
            fg_color="transparent"
        )
        total_frame.grid(
            row=0,
            column=0,
            sticky="w",
            padx=SPACING["lg"],
            pady=SPACING["md"]
        )

        ctk.CTkLabel(
            total_frame,
            text="Total Transaksi",
            text_color=COLORS["text_secondary"],
            font=get_font("small")
        ).pack(anchor="w")

        self.total_value = ctk.CTkLabel(
            total_frame,
            text="Rp 0",
            text_color=COLORS["text"],
            font=get_font("title")
        )
        self.total_value.pack(
            anchor="w",
            pady=(SPACING["xs"], 0)
        )

        ctk.CTkButton(
            bottom_bar,
            text="Bersihkan",
            width=110,
            command=self._reset_form,
            **button_style("secondary")
        ).grid(
            row=0,
            column=1,
            padx=(SPACING["sm"], SPACING["sm"]),
            pady=SPACING["md"]
        )

        ctk.CTkButton(
            bottom_bar,
            text="Pembayaran",
            width=150,
            command=self._open_payment_popup,
            **button_style("primary")
        ).grid(
            row=0,
            column=2,
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"]
        )

        # =====================================================
        # INITIAL STATE
        # =====================================================

        self._render_items()
        self._update_total()

    # =========================================================
    # PAYMENT POPUP
    # =========================================================

    def _open_payment_popup(self):
        if not self.items:
            show_warning(
                self,
                "Pembayaran",
                "Belum ada barang di keranjang."
            )
            return

        if self.payment_popup:
            try:
                self.payment_popup.lift()
                self.payment_popup.focus_force()
            except Exception:
                self.payment_popup = None

            if self.payment_popup:
                return

        popup = PaymentDialog(
            self,
            total_text=format_rupiah(
                self._calculate_total()
            ),
            on_process=self._save_transaction,
            on_close=self._close_payment_popup,
            on_change=self._on_payment_changed
        )

        self.payment_popup = popup
        self.payment_entry = popup.payment_entry
        self.change_value = popup.change_value
        self.print_checkbox = popup.print_checkbox

    def _close_payment_popup(self):
        if self.payment_popup:
            try:
                self.payment_popup.grab_release()
            except Exception:
                pass

            try:
                self.payment_popup.destroy()
            except Exception:
                pass

        self.payment_popup = None
        self.payment_entry = None
        self.change_value = None
        self.print_checkbox = None

    def _message_parent(self):
        """Pesan muncul di atas dialog pembayaran bila sedang terbuka."""
        return self.payment_popup or self

    # =========================================================
    # EVENTS
    # =========================================================

    def _bind_events(self):
        self.search_entry.bind("<KeyRelease>", self._on_search_key_release)
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Escape>", self._close_search_popup)
        self.search_entry.bind("<Down>", self._on_key_down)
        self.search_entry.bind("<Up>", self._on_key_up)

        self.qty_entry.bind(
            "<Return>",
            lambda event: self._add_from_search()
        )

    # =========================================================
    # PRODUCT LOOKUP
    # =========================================================

    def _find_by_barcode(self, search):
        try:
            return self.product_model.get_by_barcode(search)
        except Exception:
            return None

    def _query_products(self, search):
        try:
            products = self.product_model.list_products(
                search=search
            )
        except TypeError:
            products = self.product_model.list_products()

            products = [
                p
                for p in products
                if search.lower()
                in str(p.get("name", "")).lower()
            ]

        except Exception:
            products = []

        return products or []

    # =========================================================
    # SEARCH
    # =========================================================

    def _cancel_pending_search(self):
        """Batalkan pencarian terjadwal (jeda 120 ms setelah mengetik)."""
        if self.search_after_id:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass

            self.search_after_id = None

    def _on_search_key_release(self, event=None):
        if event and event.keysym in (
            "Up",
            "Down",
            "Return",
            "Escape"
        ):
            return

        search = self.search_entry.get().strip()

        self._cancel_pending_search()

        if not search:
            self.search_results = []
            self.search_selected_index = -1
            self._results_query = ""
            self._close_search_popup()
            return

        self.search_after_id = self.after(
            120,
            lambda: self._perform_search(search)
        )

    def _perform_search(self, search):
        self.search_after_id = None

        search = search.strip()

        if not search:
            self.search_results = []
            self.search_selected_index = -1
            self._results_query = ""
            self._close_search_popup()
            return

        # Teks sudah berubah atau barang sudah ditambahkan: hasil ini basi.
        if search != self.search_entry.get().strip():
            return

        results = []

        product = self._find_by_barcode(search)

        if product:
            results = [product]

        if not results:
            results = self._query_products(search)

        self.search_results = [
            product
            for product in results
            if isinstance(product, dict)
        ]
        self._results_query = search

        if len(self.search_results) == 1:
            self.search_selected_index = 0
        else:
            self.search_selected_index = -1

        self._show_search_popup()

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

        self.search_popup = popup

        popup.overrideredirect(True)
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())

        width = max(
            self.search_entry.winfo_width(),
            420
        )

        height = min(
            8 * 48 + 10,
            394
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
            border_color=COLORS["border"]
        )
        container.pack(
            fill="both",
            expand=True
        )

        self.popup_listbox = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent"
        )
        self.popup_listbox.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        for index, product in enumerate(self.search_results):
            self._create_search_result(
                self.popup_listbox,
                product,
                index
            )

        self._highlight_search_result()

        self.search_entry.focus_set()

    def _create_search_result(
        self,
        parent,
        product,
        index
    ):
        name = product.get("name", "Produk")
        barcode = product.get("barcode")
        stock = product.get("stock", 0)
        selling_price = product.get("selling_price", 0)

        barcode_text = (
            str(barcode)
            if barcode
            else "-"
        )

        row = ctk.CTkFrame(
            parent,
            height=44,
            corner_radius=RADIUS["small"],
            fg_color="transparent"
        )

        row.pack(
            fill="x",
            padx=2,
            pady=2
        )

        row.pack_propagate(False)

        name_label = ctk.CTkLabel(
            row,
            text=name,
            anchor="w",
            text_color=COLORS["text"],
            font=get_font("button")
        )
        name_label.pack(
            side="left",
            padx=(10, 5)
        )

        info_label = ctk.CTkLabel(
            row,
            text=(
                f"Barcode: {barcode_text}  •  "
                f"Stok: {stock}  •  "
                f"{format_rupiah(selling_price)}"
            ),
            anchor="e",
            text_color=COLORS["text_secondary"],
            font=get_font("small")
        )
        info_label.pack(
            side="right",
            padx=10
        )

        for widget in (row, name_label, info_label):
            widget.bind(
                "<Button-1>",
                lambda event, i=index:
                self._select_search_result(i)
            )

    def _highlight_search_result(self):
        if not self.search_popup:
            return

        if not self.search_results:
            return

        if not self.popup_listbox:
            return

        children = self.popup_listbox.winfo_children()

        for index, child in enumerate(children):
            if index == self.search_selected_index:
                child.configure(
                    fg_color=COLORS["table_selected"]
                )
            else:
                child.configure(
                    fg_color="transparent"
                )

    def _select_search_result(self, index):
        if not self.search_results:
            return "break"

        if (
            index < 0
            or index >= len(self.search_results)
        ):
            return "break"

        product = self.search_results[index]

        quantity = self._get_quantity()

        if quantity is None:
            return "break"

        self._add_and_reset(product, quantity)

        return "break"

    # =========================================================
    # KEYBOARD SEARCH
    # =========================================================

    def _move_search_selection(self, direction):
        if not self.search_results:
            return "break"

        if self.search_selected_index < 0:
            self.search_selected_index = 0
        else:
            self.search_selected_index += direction

            if (
                self.search_selected_index
                >= len(self.search_results)
            ):
                self.search_selected_index = 0

            elif self.search_selected_index < 0:
                self.search_selected_index = (
                    len(self.search_results) - 1
                )

        self._highlight_search_result()

        return "break"

    def _on_key_down(self, event=None):
        if not self.search_results:
            return "break"

        self._move_search_selection(1)

        return "break"

    def _on_key_up(self, event=None):
        if not self.search_results:
            return "break"

        self._move_search_selection(-1)

        return "break"

    def _on_search_enter(self, event=None):
        """
        Enter di kolom pencarian. Urutan:

        1. Teks cocok persis dengan barcode -> langsung masuk keranjang.
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
            quantity = self._get_quantity()

            if quantity is not None:
                self._add_and_reset(product, quantity)

            return "break"

        # 2. Hasil popup yang masih sesuai dengan teks sekarang
        if self.search_results and self._results_query == search:
            if self.search_selected_index < 0:
                self.search_selected_index = 0
                self._highlight_search_result()
                return "break"

            self._select_search_result(self.search_selected_index)

            return "break"

        # 3. Cari sekarang
        self._perform_search(search)

        if not self.search_results:
            show_warning(
                self,
                "Produk Tidak Ditemukan",
                "Produk tidak ditemukan."
            )
            return "break"

        if len(self.search_results) == 1:
            self._select_search_result(0)
        else:
            self.search_selected_index = 0
            self._highlight_search_result()

        return "break"

    def _close_search_popup(self, event=None):
        if self.search_popup:
            try:
                self.search_popup.destroy()
            except Exception:
                pass

        self.search_popup = None
        self.popup_listbox = None

        if event is not None:
            return "break"

        return None

    # =========================================================
    # ADD TO CART
    # =========================================================

    def _add_and_reset(self, product, quantity):
        """
        Tambahkan barang, lalu kosongkan input agar siap untuk scan/ketik
        berikutnya. Input dikosongkan walau penambahan gagal (mis. stok
        habis), supaya scan berikutnya tidak menempel pada kode lama.
        """
        self._cancel_pending_search()

        # Tutup popup lebih dulu agar dialog pesan tidak tertutup popup.
        self._close_search_popup()

        self._add_product_to_cart(
            product,
            quantity
        )

        self.search_results = []
        self.search_selected_index = -1
        self._results_query = ""

        self.search_entry.delete(0, "end")

        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, "1")

        self.search_entry.focus_set()

    def _add_from_search(self):
        """Tombol Tambah (dan Enter di kolom Qty)."""
        search = self.search_entry.get().strip()

        if not search:
            return

        quantity = self._get_quantity()

        if quantity is None:
            return

        self._cancel_pending_search()

        product = self._find_by_barcode(search)

        if product:
            self._add_and_reset(product, quantity)
            return

        products = self._query_products(search)

        if not products:
            show_warning(
                self,
                "Produk Tidak Ditemukan",
                "Produk tidak ditemukan."
            )
            return

        if len(products) > 1:
            self.search_results = products
            self.search_selected_index = -1
            self._results_query = search

            self._show_search_popup()

            return

        self._add_and_reset(products[0], quantity)

    # =========================================================
    # QUANTITY
    # =========================================================

    def _get_quantity(self):
        value = self.qty_entry.get().strip()

        if not value:
            show_warning(
                self,
                "Qty",
                "Jumlah barang harus diisi."
            )
            return None

        try:
            quantity = int(value)
        except ValueError:
            show_warning(
                self,
                "Qty",
                "Jumlah barang harus berupa angka."
            )
            return None

        if quantity <= 0:
            show_warning(
                self,
                "Qty",
                "Jumlah barang harus lebih dari 0."
            )
            return None

        return quantity

    # =========================================================
    # CART
    # =========================================================

    def _add_product_to_cart(
        self,
        product,
        quantity
    ):
        product_id = product.get("id")

        if not product_id:
            show_error(
                self,
                "Error",
                "ID produk tidak ditemukan."
            )
            return False

        stock = int(
            product.get("stock", 0) or 0
        )

        if stock <= 0:
            show_warning(
                self,
                "Stok Habis",
                f"Stok {product.get('name', 'produk')} "
                "sudah habis."
            )
            return False

        existing_item = None

        for item in self.items:
            if item["product_id"] == product_id:
                existing_item = item
                break

        if existing_item:
            new_quantity = (
                existing_item["quantity"]
                + quantity
            )

            if new_quantity > stock:
                show_warning(
                    self,
                    "Stok Tidak Cukup",
                    f"Stok tersedia hanya {stock}."
                )
                return False

            existing_item["quantity"] = new_quantity

            existing_item["subtotal"] = (
                new_quantity
                * existing_item["selling_price"]
            )

            self.items.insert(
                0,
                self.items.pop(self.items.index(existing_item)),
            )

        else:
            if quantity > stock:
                show_warning(
                    self,
                    "Stok Tidak Cukup",
                    f"Stok tersedia hanya {stock}."
                )
                return False

            selling_price = int(
                product.get("selling_price", 0) or 0
            )

            self.items.insert(
                0,
                {
                    "product_id": product_id,
                    "name": product.get("name", "Produk"),
                    "selling_price": selling_price,
                    "quantity": quantity,
                    "subtotal": selling_price * quantity,
                    "stock": stock,
                },
            )

        self._render_items()
        self._update_total()

        return True

    def _render_items(self):
        self.cart_table.set_rows(
            [
                self._cart_row(index, item)
                for index, item in enumerate(self.items)
            ]
        )

    def _cart_row(self, index, item):
        return [
            text_cell(
                item["name"],
                bold=True
            ),
            text_cell(
                format_rupiah(item["selling_price"])
            ),
            lambda parent, i=index, q=item["quantity"]: (
                self._build_qty_entry(parent, i, q)
            ),
            text_cell(
                format_rupiah(item["subtotal"]),
                bold=True
            ),
            lambda parent, i=index: ctk.CTkButton(
                parent,
                text="Hapus",
                width=64,
                command=lambda: self._remove_cart_item(i),
                **button_style("danger", "small")
            ),
        ]

    def _build_qty_entry(
        self,
        parent,
        index,
        quantity
    ):
        style = entry_style()
        style["height"] = 30

        entry = ctk.CTkEntry(
            parent,
            width=70,
            justify="center",
            **style
        )

        entry.insert(0, str(quantity))

        entry.bind(
            "<Return>",
            lambda event, i=index, e=entry:
            self._update_cart_quantity(i, e)
        )

        return entry

    def _update_cart_quantity(
        self,
        index,
        entry
    ):
        if (
            index < 0
            or index >= len(self.items)
        ):
            return

        try:
            quantity = int(
                entry.get().strip()
            )
        except ValueError:
            show_warning(
                self,
                "Qty",
                "Jumlah harus berupa angka."
            )

            self._render_items()

            return

        if quantity <= 0:
            show_warning(
                self,
                "Qty",
                "Jumlah harus lebih dari 0."
            )

            self._render_items()

            return

        item = self.items[index]

        stock = int(
            item.get("stock", 0) or 0
        )

        if quantity > stock:
            show_warning(
                self,
                "Stok Tidak Cukup",
                f"Stok tersedia hanya {stock}."
            )

            self._render_items()

            return

        item["quantity"] = quantity

        item["subtotal"] = (
            item["selling_price"]
            * quantity
        )

        self._render_items()
        self._update_total()

    def _remove_cart_item(self, index):
        if (
            index < 0
            or index >= len(self.items)
        ):
            return

        del self.items[index]

        self._render_items()
        self._update_total()

    # =========================================================
    # TOTAL / PAYMENT
    # =========================================================

    def _calculate_total(self):
        return sum(
            int(item["subtotal"])
            for item in self.items
        )

    def _update_total(self):
        total = self._calculate_total()

        if self.total_value:
            self.total_value.configure(
                text=format_rupiah(total)
            )

        self._on_payment_changed()

    def _on_payment_changed(self, event=None):
        if not self.payment_entry:
            return

        if not self.change_value:
            return

        total = self._calculate_total()

        value = self.payment_entry.get().strip()

        if not value:
            self.change_value.configure(text="Rp 0")
            return

        try:
            paid = int(value)
        except ValueError:
            self.change_value.configure(text="Rp 0")
            return

        change = paid - total

        if change < 0:
            change = 0

        self.change_value.configure(
            text=format_rupiah(change)
        )

    # =========================================================
    # SAVE
    # =========================================================

    def _save_transaction(self):
        if not self.items:
            show_warning(
                self._message_parent(),
                "Penjualan",
                "Belum ada barang di keranjang."
            )
            return

        if not self.payment_entry:
            return

        total = self._calculate_total()

        paid_text = self.payment_entry.get().strip()

        if not paid_text:
            show_warning(
                self._message_parent(),
                "Pembayaran",
                "Nominal pembayaran harus diisi."
            )
            self.payment_entry.focus_set()
            return

        try:
            paid_amount = int(paid_text)
        except ValueError:
            show_warning(
                self._message_parent(),
                "Pembayaran",
                "Nominal pembayaran harus berupa angka."
            )
            self.payment_entry.focus_set()
            return

        if paid_amount < total:
            show_warning(
                self._message_parent(),
                "Pembayaran",
                "Nominal pembayaran kurang dari total."
            )
            self.payment_entry.focus_set()
            return

        # -----------------------------------------------------
        # UI STOCK RECHECK
        # -----------------------------------------------------

        for item in self.items:
            try:
                product = self.product_model.get_by_id(
                    item["product_id"]
                )
            except Exception:
                product = None

            if not product:
                show_error(
                    self._message_parent(),
                    "Produk",
                    f"Produk {item['name']} tidak ditemukan."
                )
                return

            stock = int(
                product.get("stock", 0) or 0
            )

            if item["quantity"] > stock:
                show_warning(
                    self._message_parent(),
                    "Stok Tidak Cukup",
                    f"Stok {item['name']} "
                    f"tersisa {stock}."
                )
                return

        # -----------------------------------------------------
        # PREPARE ITEMS
        # -----------------------------------------------------

        transaction_items = []

        for item in self.items:
            transaction_items.append(
                {
                    "product_id": item["product_id"],
                    "quantity": item["quantity"]
                }
            )

        # -----------------------------------------------------
        # PRINT OPTION
        # -----------------------------------------------------

        print_after = bool(
            self.print_checkbox.get()
        ) if self.print_checkbox else False

        # -----------------------------------------------------
        # SAVE MODEL
        # -----------------------------------------------------

        try:
            success, message, sale_id = (
                self.sale_model.create_transaction(
                    transaction_items,
                    paid_amount,
                    ""
                )
            )

        except Exception:
            show_error(
                self._message_parent(),
                "Penjualan",
                "Gagal menyimpan transaksi. "
                "Silakan coba lagi."
            )
            return

        if not success:
            show_error(
                self._message_parent(),
                "Penjualan",
                message
            )
            return

        # -----------------------------------------------------
        # PREPARE PDF
        # -----------------------------------------------------

        pdf_path = None
        printer = None

        if print_after:
            try:
                sale_detail = (
                    self.sale_model.get_transaction_detail(
                        sale_id
                    )
                )

                printer = Printer()

                pdf_path = printer.create_pdf(
                    "sale",
                    sale_detail
                )

            except PrinterError as exc:
                show_warning(
                    self._message_parent(),
                    "Transaksi Berhasil",
                    "Penjualan berhasil disimpan, "
                    f"tetapi struk tidak dapat dibuat.\n\n{exc}"
                )

            except Exception:
                show_warning(
                    self._message_parent(),
                    "Transaksi Berhasil",
                    "Penjualan berhasil disimpan, "
                    "tetapi struk tidak dapat dibuat."
                )

        # -----------------------------------------------------
        # CLOSE PAYMENT
        # -----------------------------------------------------

        self._close_payment_popup()

        # -----------------------------------------------------
        # RESET FORM
        # -----------------------------------------------------

        self._reset_form()

        # -----------------------------------------------------
        # OPEN PDF DIRECTLY
        # -----------------------------------------------------

        if print_after and pdf_path:
            try:
                printer.open_pdf(pdf_path)

                show_success(
                    self,
                    "Penjualan",
                    "Transaksi berhasil diproses dan "
                    "struk PDF telah dibuat."
                )

            except Exception:
                show_success(
                    self,
                    "Penjualan",
                    "Transaksi berhasil diproses.\n\n"
                    f"Struk PDF tersimpan di:\n{pdf_path}"
                )

        else:
            show_success(
                self,
                "Penjualan",
                message
            )

    # =========================================================
    # RESET
    # =========================================================

    def _reset_form(self):
        self.items = []

        self.search_results = []
        self.search_selected_index = -1
        self._results_query = ""

        self._cancel_pending_search()
        self._close_search_popup()

        self.search_entry.delete(0, "end")

        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, "1")

        self._render_items()
        self._update_total()

        self.search_entry.focus_set()


class PaymentDialog(BaseDialog):
    """Dialog pembayaran: total, nominal bayar, kembalian, opsi cetak struk."""

    def __init__(
        self,
        master,
        total_text: str,
        on_process,
        on_close,
        on_change
    ):
        super().__init__(master, "Pembayaran", DIALOG_WIDTH["form"])

        # Tutup lewat tombol X atau Esc harus membersihkan state halaman.
        self.protocol("WM_DELETE_WINDOW", on_close)
        self.bind("<Escape>", lambda _event: on_close())

        total_box = ctk.CTkFrame(
            self.body,
            fg_color=COLORS["surface_hover"],
            corner_radius=RADIUS["card"]
        )
        total_box.pack(
            fill="x",
            pady=(0, SPACING["md"])
        )

        ctk.CTkLabel(
            total_box,
            text="Total",
            text_color=COLORS["text_secondary"],
            font=get_font("small"),
            anchor="w"
        ).pack(
            anchor="w",
            padx=SPACING["lg"],
            pady=(SPACING["md"], 0)
        )

        ctk.CTkLabel(
            total_box,
            text=total_text,
            text_color=COLORS["text"],
            font=get_font("title"),
            anchor="w"
        ).pack(
            anchor="w",
            padx=SPACING["lg"],
            pady=(0, SPACING["md"])
        )

        self.payment_field = FormField(
            self.body,
            "Nominal Bayar",
            "Masukkan nominal pembayaran"
        )
        self.payment_field.pack(
            fill="x",
            pady=(0, SPACING["md"])
        )

        self.payment_entry = self.payment_field.entry
        self.payment_entry.bind(
            "<KeyRelease>",
            on_change
        )

        change_row = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0
        )
        change_row.pack(
            fill="x",
            pady=(0, SPACING["md"])
        )

        change_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            change_row,
            text="Kembalian",
            text_color=COLORS["text_secondary"],
            font=get_font("body"),
            anchor="w"
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.change_value = ctk.CTkLabel(
            change_row,
            text="Rp 0",
            text_color=COLORS["text"],
            font=get_font("heading"),
            anchor="e"
        )
        self.change_value.grid(
            row=0,
            column=1,
            sticky="e"
        )

        self.print_checkbox = ctk.CTkCheckBox(
            self.body,
            text="Cetak struk setelah transaksi",
            font=get_font("body"),
            text_color=COLORS["text"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            corner_radius=RADIUS["small"]
        )
        self.print_checkbox.pack(anchor="w")

        self.set_buttons(
            "Proses",
            on_process,
            secondary_text="Batal",
            secondary_command=on_close
        )
        self.finish()

        self.after(
            100,
            self.payment_entry.focus_set
        )