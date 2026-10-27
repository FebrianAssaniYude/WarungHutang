import uuid

import customtkinter as ctk

from components.cards import SectionCard
from components.customer_picker import CustomerPickerDialog, CustomerSelector
from components.dialogs import (
    show_error,
    show_success,
    show_warning,
)
from components.forms import FormField, SearchBar
from components.page_header import PageHeader
from components.tables import SimpleTable, text_cell
from models.customer import CustomerModel
from models.debt import DebtModel
from models.product import ProductModel
from utils.formatter import format_rupiah
from utils.printer import Printer, PrinterError
from utils.theme import (
    COLORS,
    LAYOUT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)


MAX_SEARCH_RESULTS = 8

# Popup hasil pencarian barang (dua baris: nama + info).
SEARCH_ROW_HEIGHT = 58
SEARCH_POPUP_MIN_WIDTH = 460
SEARCH_POPUP_MAX_HEIGHT = MAX_SEARCH_RESULTS * SEARCH_ROW_HEIGHT + 8

CART_COLUMNS = [
    {"title": "Barang", "weight": 5, "align": "left"},
    {"title": "Harga", "weight": 3, "align": "right"},
    {"title": "Qty", "weight": 3, "align": "center"},
    {"title": "Subtotal", "weight": 3, "align": "right"},
    {"title": "Aksi", "weight": 2, "align": "center"},
]

def _checkbox_kwargs() -> dict:
    return {
        "font": get_font("body"),
        "text_color": COLORS["text"],
        "fg_color": COLORS["primary"],
        "hover_color": COLORS["primary_hover"],
        "border_color": COLORS["border"],
        "corner_radius": RADIUS["small"],
    }


class TransaksiHutangPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        customer_model: CustomerModel,
        product_model: ProductModel,
        debt_model: DebtModel,
    ):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.customer_model = customer_model
        self.product_model = product_model
        self.debt_model = debt_model

        self.selected_customer = None
        self.cart = []

        self._current_results = []
        self._selected_result_index = -1
        self._search_popup = None
        self._search_after_id = None

        self.search_var = ctk.StringVar()

        self._build_ui()

        self._set_customer_button(None)
        self._render_cart()

    def refresh(self):
        # Jangan mengosongkan transaksi yang sedang dibuat.
        pass

    # ==================================================================
    # UI
    # ==================================================================

    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        PageHeader(self, "Transaksi Hutang").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        self._build_input_card(page_padding)
        self._build_cart_card(page_padding)
        self._build_bottom_card(page_padding)

    # ------------------------------------------------------------------
    # Kartu input: pelanggan + cari barang
    # ------------------------------------------------------------------
    def _build_input_card(self, page_padding):
        card = SectionCard(self)
        card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, SPACING["md"]),
        )

        body = card.body
        body.grid_columnconfigure(1, weight=1)

        label_padx = (0, SPACING["lg"])

        ctk.CTkLabel(
            body,
            text="Pelanggan",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=label_padx)

        self.customer_button = CustomerSelector(
            body,
            command=self._open_customer_picker,
        )
        self.customer_button.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        ctk.CTkLabel(
            body,
            text="Tambah Barang",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=label_padx,
            pady=(SPACING["md"], 0),
        )

        self.search_entry = SearchBar(
            body,
            self.search_var,
            "Scan barcode atau cari nama barang...",
        )
        self.search_entry.grid(
            row=1,
            column=1,
            sticky="ew",
            pady=(SPACING["md"], 0),
        )

        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Escape>", self._on_search_escape)
        self.search_entry.bind("<Down>", self._on_search_down)
        self.search_entry.bind("<Up>", self._on_search_up)

    # ------------------------------------------------------------------
    # Kartu keranjang
    # ------------------------------------------------------------------
    def _build_cart_card(self, page_padding):
        card = SectionCard(self)
        card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=page_padding,
            pady=(0, SPACING["md"]),
        )

        title_row = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
        )
        title_row.pack(fill="x", pady=(0, SPACING["md"]))

        ctk.CTkLabel(
            title_row,
            text="Daftar Barang",
            font=get_font("subheading"),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.cart_count_label = ctk.CTkLabel(
            title_row,
            text="0 barang",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        )
        self.cart_count_label.pack(side="left", padx=(SPACING["sm"], 0))

        self.cart_table = SimpleTable(
            card.body,
            CART_COLUMNS,
            empty_title="Belum ada barang",
            empty_text="Scan barcode atau cari barang untuk menambahkannya.",
            scrollable=True,
        )
        self.cart_table.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Kartu bawah: catatan + total + aksi
    # ------------------------------------------------------------------
    def _build_bottom_card(self, page_padding):
        card = SectionCard(self)
        card.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=page_padding,
            pady=(0, page_padding),
        )

        self.notes_field = FormField(
            card.body,
            "Catatan",
            "Contoh: Bayar akhir bulan",
        )
        self.notes_field.pack(fill="x")
        self.notes_entry = self.notes_field.entry

        footer = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
        )
        footer.pack(fill="x", pady=(SPACING["lg"], 0))
        footer.grid_columnconfigure(0, weight=1)

        total_frame = ctk.CTkFrame(footer, fg_color="transparent")
        total_frame.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            total_frame,
            text="Total Transaksi",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w")

        self.total_label = ctk.CTkLabel(
            total_frame,
            text=format_rupiah(0),
            font=get_font("title"),
            text_color=COLORS["text"],
        )
        self.total_label.pack(anchor="w", pady=(SPACING["xs"], 0))

        self.print_var = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(
            footer,
            text="Cetak nota setelah transaksi",
            variable=self.print_var,
            **_checkbox_kwargs(),
        ).grid(row=0, column=1, padx=(SPACING["xl"], SPACING["lg"]))

        ctk.CTkButton(
            footer,
            text="Bersihkan",
            width=110,
            command=self._clear_transaction,
            **button_style("secondary"),
        ).grid(row=0, column=2, padx=(0, SPACING["sm"]))

        ctk.CTkButton(
            footer,
            text="Proses",
            width=150,
            command=self._handle_save,
            **button_style("primary"),
        ).grid(row=0, column=3)

    # ==================================================================
    # PELANGGAN
    # ==================================================================

    def _set_customer_button(self, customer):
        self.customer_button.set_customer(customer)

    def _open_customer_picker(self):
        self._hide_search_popup()

        CustomerPickerDialog(
            self,
            self.customer_model,
            on_select=self._handle_customer_selected,
        )

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self._set_customer_button(customer)

    # ==================================================================
    # SEARCH LOGIC
    # ==================================================================

    def _on_search_change(self, event=None):
        if event and event.keysym in (
            "Up",
            "Down",
            "Return",
            "Escape",
        ):
            return

        query = self.search_entry.get().strip()

        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass

            self._search_after_id = None

        if not query:
            self._current_results = []
            self._selected_result_index = -1
            self._hide_search_popup()
            return

        self._search_after_id = self.after(
            120,
            lambda q=query: self._perform_search(q),
        )

    def _perform_search(self, query: str):
        self._search_after_id = None

        if query != self.search_entry.get().strip():
            return

        try:
            barcode_product = self.product_model.get_by_barcode(query)

            if barcode_product:
                self._current_results = [barcode_product]
            else:
                self._current_results = (
                    self.product_model.list_products(search=query)
                    [:MAX_SEARCH_RESULTS]
                )

        except Exception:
            self._current_results = []
            self._selected_result_index = -1
            self._hide_search_popup()

            show_error(
                self,
                "Pencarian Gagal",
                "Gagal mencari barang. Periksa database lalu coba lagi.",
            )
            return

        self._selected_result_index = (
            0 if self._current_results else -1
        )

        self._render_search_popup()

    # ==================================================================
    # POPUP HASIL BARANG
    # ==================================================================

    def _render_search_popup(self):
        self._hide_search_popup()

        if not self._current_results:
            return

        self._search_popup = ctk.CTkToplevel(self)

        self._search_popup.overrideredirect(True)
        self._search_popup.transient(self.winfo_toplevel())

        self.update_idletasks()

        x = self.search_entry.winfo_rootx()
        y = (
            self.search_entry.winfo_rooty()
            + self.search_entry.winfo_height()
            + SPACING["xs"]
        )

        width = max(
            self.search_entry.winfo_width(),
            SEARCH_POPUP_MIN_WIDTH,
        )

        height = min(
            len(self._current_results) * SEARCH_ROW_HEIGHT + SPACING["sm"],
            SEARCH_POPUP_MAX_HEIGHT,
        )

        self._search_popup.geometry(f"{width}x{height}+{x}+{y}")
        self._search_popup.configure(fg_color=COLORS["surface"])

        container = ctk.CTkFrame(
            self._search_popup,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RADIUS["medium"],
        )
        container.pack(fill="both", expand=True)

        for index, product in enumerate(self._current_results):
            self._build_search_result(container, index, product)

        self._update_search_selection()

    def _build_search_result(
        self,
        parent,
        index: int,
        product: dict,
    ):
        row = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            corner_radius=RADIUS["small"],
        )
        row.pack(fill="x", padx=SPACING["xs"], pady=2)
        row.grid_columnconfigure(0, weight=1)

        name_label = ctk.CTkLabel(
            row,
            text=product["name"],
            anchor="w",
            font=get_font("button"),
            text_color=COLORS["text"],
        )
        name_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(SPACING["md"], SPACING["sm"]),
            pady=(SPACING["sm"] - 2, 0),
        )

        stock_text = f"Stok: {product.get('stock', 0)}"

        if product.get("barcode"):
            stock_text += f"   ·   Barcode: {product['barcode']}"

        detail_label = ctk.CTkLabel(
            row,
            text=(
                f"{format_rupiah(product['selling_price'])}"
                f"   ·   {stock_text}"
            ),
            anchor="w",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        )
        detail_label.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(SPACING["md"], SPACING["sm"]),
            pady=(0, SPACING["sm"] - 2),
        )

        for widget in (row, name_label, detail_label):
            widget.bind(
                "<Button-1>",
                lambda event, i=index: self._select_search_result(i),
            )

        row.bind(
            "<Enter>",
            lambda event, i=index: self._set_search_selection(i),
        )

    def _set_search_selection(self, index: int):
        if not self._current_results:
            return

        if index < 0 or index >= len(self._current_results):
            return

        self._selected_result_index = index
        self._update_search_selection()

    def _update_search_selection(self):
        if not self._search_popup:
            return

        children = self._search_popup.winfo_children()

        if not children:
            return

        for index, row in enumerate(children[0].winfo_children()):
            if index == self._selected_result_index:
                row.configure(fg_color=COLORS["table_selected"])
            else:
                row.configure(fg_color="transparent")

    def _select_search_result(self, index: int):
        if not self._current_results:
            return

        if index < 0 or index >= len(self._current_results):
            return

        product = self._current_results[index]

        # Tutup popup lebih dulu agar dialog pesan tidak tertutup popup.
        self._hide_search_popup()

        self._add_product_to_cart(product)
        self._clear_search()

    def _on_search_down(self, event=None):
        if not self._current_results:
            return "break"

        if self._selected_result_index < len(self._current_results) - 1:
            self._selected_result_index += 1
        else:
            self._selected_result_index = 0

        self._update_search_selection()

        return "break"

    def _on_search_up(self, event=None):
        if not self._current_results:
            return "break"

        if self._selected_result_index > 0:
            self._selected_result_index -= 1
        else:
            self._selected_result_index = len(self._current_results) - 1

        self._update_search_selection()

        return "break"

    def _on_search_enter(self, event=None):
        query = self.search_entry.get().strip()

        if not query:
            return "break"

        try:
            product = self.product_model.get_by_barcode(query)

        except Exception:
            show_error(
                self,
                "Pencarian Gagal",
                "Gagal memeriksa barcode. Periksa database lalu coba lagi.",
            )
            return "break"

        if product:
            self._hide_search_popup()
            self._add_product_to_cart(product)
            self._clear_search()
            return "break"

        if self._current_results:
            index = self._selected_result_index

            if index < 0:
                index = 0

            self._select_search_result(index)
            return "break"

        show_warning(
            self,
            "Barang Tidak Ditemukan",
            "Barang tidak ditemukan di master produk.",
        )

        return "break"

    def _on_search_escape(self, event=None):
        self._current_results = []
        self._selected_result_index = -1
        self._hide_search_popup()

        return "break"

    def _hide_search_popup(self):
        if self._search_popup is not None:
            try:
                if self._search_popup.winfo_exists():
                    self._search_popup.destroy()
            except Exception:
                pass

        self._search_popup = None

    def _clear_search(self):
        self._current_results = []
        self._selected_result_index = -1

        self._hide_search_popup()

        self.search_entry.delete(0, "end")
        self.search_entry.focus()

    # ==================================================================
    # KERANJANG
    # ==================================================================

    def _add_product_to_cart(
        self,
        product: dict,
        quantity: int = 1,
    ):
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            quantity = 1

        if quantity <= 0:
            quantity = 1

        product_id = product["id"]
        product_name = product["name"]
        price = int(product["selling_price"])
        stock = int(product.get("stock") or 0)

        if stock <= 0:
            show_warning(
                self,
                "Stok Habis",
                f"Stok {product_name} habis.",
            )
            return

        if quantity > stock:
            show_warning(
                self,
                "Stok Tidak Cukup",
                f"Stok {product_name} hanya {stock}. "
                "Qty tidak dapat melebihi stok.",
            )
            return

        for row in self.cart:
            if row["product_id"] == product_id:
                new_quantity = row["quantity"] + quantity

                if new_quantity > stock:
                    show_warning(
                        self,
                        "Stok Tidak Cukup",
                        f"Stok {product_name} hanya {stock}. "
                        "Qty tidak dapat melebihi stok.",
                    )
                    return

                row["quantity"] = new_quantity
                self.cart.remove(row)
                self.cart.insert(0, row)

                self._render_cart()
                return

        self.cart.insert(
            0,
            {
                "row_id": str(uuid.uuid4()),
                "product_id": product_id,
                "product_name": product_name,
                "quantity": quantity,
                "price": price,
            },
        )

        self._render_cart()

    def _change_quantity(
        self,
        row_id: str,
        delta: int,
    ):
        for row in self.cart:
            if row["row_id"] != row_id:
                continue

            new_quantity = row["quantity"] + delta

            if new_quantity < 1:
                new_quantity = 1

            if delta > 0:
                try:
                    product = self.product_model.get_by_id(
                        row["product_id"]
                    )

                except Exception:
                    show_error(
                        self,
                        "Terjadi Kesalahan",
                        "Gagal memeriksa stok barang. Coba lagi.",
                    )
                    return

                if not product:
                    show_warning(
                        self,
                        "Barang Tidak Ditemukan",
                        "Barang tidak ditemukan di master produk.",
                    )
                    return

                stock = int(product.get("stock") or 0)

                if new_quantity > stock:
                    show_warning(
                        self,
                        "Stok Tidak Cukup",
                        f"Stok {row['product_name']} hanya {stock}. "
                        "Qty tidak dapat melebihi stok.",
                    )
                    return

            row["quantity"] = new_quantity
            break

        self._render_cart()

    def _remove_from_cart(self, row_id: str):
        self.cart = [
            row
            for row in self.cart
            if row["row_id"] != row_id
        ]

        self._render_cart()

    def _render_cart(self):
        self.cart_table.set_rows(
            [self._cart_row(row) for row in self.cart]
        )

        self.cart_count_label.configure(
            text=f"{len(self.cart)} barang"
        )

        self._update_total()

    def _cart_row(self, row: dict) -> list:
        subtotal = row["quantity"] * row["price"]

        return [
            text_cell(row["product_name"], bold=True),
            text_cell(format_rupiah(row["price"])),
            lambda parent, r=row: self._build_qty_cell(parent, r),
            text_cell(format_rupiah(subtotal), bold=True),
            lambda parent, rid=row["row_id"]: ctk.CTkButton(
                parent,
                text="Hapus",
                width=64,
                command=lambda: self._remove_from_cart(rid),
                **button_style("danger", "small"),
            ),
        ]

    
    def _build_qty_cell(self, parent, row: dict):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )

        row_id = row["row_id"]

        ctk.CTkButton(
            frame,
            text="−",
            width=28,
            command=lambda: self._change_quantity(row_id, -1),
            **button_style("secondary", "small"),
        ).pack(side="left")

        qty_var = ctk.StringVar(value=str(row["quantity"]))

        qty_entry = ctk.CTkEntry(
            frame,
            width=52,
            height=30,
            textvariable=qty_var,
            justify="center",
            font=get_font("button"),
        )
        qty_entry.pack(side="left", padx=SPACING["xs"])

        def apply_quantity(event=None):
            value = qty_var.get().strip()

            try:
                quantity = int(value)
            except (TypeError, ValueError):
                show_warning(
                    self,
                    "Qty Tidak Valid",
                    "Qty harus berupa bilangan bulat positif.",
                )
                qty_var.set(str(row["quantity"]))
                qty_entry.selection_clear()
                return "break"

            if quantity < 1:
                show_warning(
                    self,
                    "Qty Tidak Valid",
                    "Qty minimal adalah 1.",
                )
                qty_var.set(str(row["quantity"]))
                return "break"

            try:
                product = self.product_model.get_by_id(
                    row["product_id"]
                )
            except Exception:
                show_error(
                    self,
                    "Terjadi Kesalahan",
                    "Gagal memeriksa stok barang. Coba lagi.",
                )
                qty_var.set(str(row["quantity"]))
                return "break"

            if not product:
                show_warning(
                    self,
                    "Barang Tidak Ditemukan",
                    "Barang tidak ditemukan di master produk.",
                )
                qty_var.set(str(row["quantity"]))
                return "break"

            stock = int(product.get("stock") or 0)

            if quantity > stock:
                show_warning(
                    self,
                    "Stok Tidak Cukup",
                    f"Stok {row['product_name']} hanya {stock}.",
                )
                qty_var.set(str(row["quantity"]))
                return "break"

            row["quantity"] = quantity
            self._render_cart()
            return "break"

        qty_entry.bind("<Return>", apply_quantity)
        qty_entry.bind("<KP_Enter>", apply_quantity)
        qty_entry.bind(
            "<FocusOut>",
            lambda event: qty_var.set(str(row["quantity"])),
        )

        ctk.CTkButton(
            frame,
            text="+",
            width=28,
            command=lambda: self._change_quantity(row_id, 1),
            **button_style("secondary", "small"),
        ).pack(side="left")

        return frame

    def _update_total(self):
        total = sum(
            row["quantity"] * row["price"]
            for row in self.cart
        )

        self.total_label.configure(text=format_rupiah(total))

    # ==================================================================
    # PROSES TRANSAKSI
    # ==================================================================

    def _handle_save(self):
        if not self.selected_customer:
            show_warning(
                self,
                "Pelanggan Belum Dipilih",
                "Pelanggan harus dipilih terlebih dahulu.",
            )
            return

        if not self.cart:
            show_warning(
                self,
                "Keranjang Kosong",
                "Tambahkan minimal satu barang sebelum memproses transaksi.",
            )
            return

        items = [
            {
                "product_id": row["product_id"],
                "quantity": row["quantity"],
            }
            for row in self.cart
        ]

        notes = self.notes_entry.get().strip()
        should_print = self.print_var.get()

        try:
            success, message, transaction_id = (
                self.debt_model.create_transaction(
                    customer_id=self.selected_customer["id"],
                    items=items,
                    notes=notes,
                )
            )

        except Exception:
            show_error(
                self,
                "Terjadi Kesalahan",
                "Terjadi kesalahan pada database. "
                "Transaksi tidak disimpan.",
            )
            return

        if not success:
            show_error(self, "Transaksi Gagal", message)
            return

        # Cetak langsung ke PDF jika checkbox dicentang.
        print_error = None

        if should_print:
            try:
                transaction_detail = (
                    self.debt_model.get_transaction_detail(
                        transaction_id
                    )
                )

                if not transaction_detail:
                    raise PrinterError(
                        "Detail transaksi hutang tidak ditemukan."
                    )

                printer = Printer()

                pdf_path = printer.create_pdf(
                    document_type="debt",
                    data=transaction_detail,
                )

                printer.open_pdf(pdf_path)

            except Exception as exc:
                print_error = str(exc)

        self._reset_form()

        if print_error:
            show_warning(
                self,
                "Transaksi Berhasil",
                f"{message}\n\nNamun nota gagal dibuat:\n{print_error}",
            )
        elif should_print:
            show_success(
                self,
                "Transaksi Hutang",
                f"{message}\n\nNota PDF berhasil dibuat.",
            )
        else:
            show_success(self, "Transaksi Hutang", message)

    # ==================================================================
    # RESET
    # ==================================================================

    def _reset_form(self):
        self.cart = []
        self.selected_customer = None

        self._set_customer_button(None)

        self.notes_entry.delete(0, "end")
        self.print_var.set(False)

        self._clear_search()
        self._render_cart()

    def _clear_transaction(self):
        self._reset_form()