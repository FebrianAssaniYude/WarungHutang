import customtkinter as ctk

from components.cards import SectionCard, StatCard
from components.dialogs import (
    BaseDialog,
    ConfirmDialog,
    show_error,
    show_warning,
)
from components.forms import ErrorText, FormField, SearchBar, entry_style
from components.page_header import PageHeader
from components.tables import DataTable
from models.product import ProductModel
from utils.barcode import BarcodeScanEntry
from utils.formatter import format_rupiah
from utils.theme import (
    BUTTON_WIDTH,
    COLORS,
    DIALOG_WIDTH,
    LAYOUT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)


# Stok sama dengan atau di bawah angka ini dianggap menipis.
LOW_STOCK_LIMIT = 5

ACTIVATE_HINT = "Klik dua kali barang untuk melihat atau mengubah."

# Tidak ada kolom Aksi: Edit dan Nonaktifkan ada di dialog Edit Barang.
# Titik berwarna di kiri baris menunjukkan kondisi stok.
PRODUCT_COLUMNS = [
    {"title": "Barcode", "weight": 3, "align": "left"},
    {"title": "Nama Barang", "weight": 6, "align": "left"},
    {"title": "Harga Beli", "weight": 3, "align": "right"},
    {"title": "Harga Jual", "weight": 3, "align": "right"},
    {"title": "Stok", "weight": 2, "align": "right"},
]


class ProductsPage(ctk.CTkFrame):
    """
    Halaman Barang.

    Header, ringkasan, dan tabel mengikuti pola CustomersPage.
    Scanner barcode ada di toolbar kartu tabel.
    Gambar produk dan supplier tidak digunakan pada UI.
    """

    def __init__(
        self,
        master,
        product_model: ProductModel,
        supplier_model=None,
    ):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.product_model = product_model

        self.search_var = ctk.StringVar()

        self._products = []

        self._build_header()
        self._build_summary()
        self._build_content()

        # Tidak memanggil refresh() di sini: halaman dimuat saat pertama
        # kali dibuka (lihat _stale_pages di MainWindow).

    # ==================================================================
    # HEADER
    # ==================================================================

    def _build_header(self):
        header = PageHeader(self, "Barang")
        header.pack(
            fill="x",
            padx=LAYOUT["page_padding"],
            pady=LAYOUT["header_pady"],
        )

        ctk.CTkButton(
            header.actions,
            text="+  Tambah Barang",
            width=150,
            command=self._open_add_dialog,
            **button_style("primary"),
        ).pack()

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def _build_summary(self):
        frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        frame.pack(
            fill="x",
            padx=LAYOUT["page_padding"],
            pady=(0, SPACING["lg"]),
        )

        titles = ["Total Barang", "Stok Tersedia", "Stok Menipis"]
        cards = []

        for column, title in enumerate(titles):
            frame.grid_columnconfigure(column, weight=1, uniform="stat")

            card = StatCard(frame, title)
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else 6,
                    0 if column == len(titles) - 1 else 6,
                ),
            )
            cards.append(card)

        self.total_card = cards[0]
        self.stock_card = cards[1]
        self.low_stock_card = cards[2]

    # ==================================================================
    # CONTENT (toolbar + tabel)
    # ==================================================================

    def _build_content(self):
        section = SectionCard(self)
        section.pack(
            fill="both",
            expand=True,
            padx=LAYOUT["page_padding"],
            pady=(0, LAYOUT["page_padding"]),
        )

        toolbar = ctk.CTkFrame(
            section.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        toolbar.pack(
            fill="x",
            pady=(0, SPACING["md"]),
        )

        self.search_entry = SearchBar(
            toolbar,
            self.search_var,
            "Cari nama atau barcode...",
            
        )
        self.search_entry.pack(side="left")

        self.search_entry.bind(
            "<KeyRelease>",
            lambda _event: self.refresh(),
        )

        ctk.CTkLabel(
            toolbar,
            text=ACTIVATE_HINT,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(SPACING["lg"], 0))

        self.scan_entry = BarcodeScanEntry(
            toolbar,
            on_scan=self._handle_barcode_scan,
            placeholder_text="Gunakan scanner untuk tambah barang",
            width=300,
            **entry_style(),
        )
        self.scan_entry.pack(side="right")

        self.table = DataTable(
            section.body,
            PRODUCT_COLUMNS,
            empty_title="Belum ada barang",
            empty_text=(
                "Tambahkan barang baru atau scan barcode "
                "untuk mulai mengelola stok."
            ),
            search_empty_title="Barang tidak ditemukan",
            search_empty_text="Coba gunakan nama atau barcode yang berbeda.",
            on_activate=self._on_activate,
            show_dot=True,
        )
        self.table.pack(fill="both", expand=True)

    # ==================================================================
    # BARCODE SCANNER
    # ==================================================================

    def _handle_barcode_scan(
        self,
        code: str,
    ):
        code = code.strip()

        if not code:
            return

        try:
            product = self.product_model.get_by_barcode(
                code,
                active_only=False,
            )
        except Exception:
            show_error(
                self,
                "Terjadi Kesalahan",
                "Gagal memeriksa barcode. Coba lagi.",
            )
            return

        if product:
            if not product["is_active"]:
                show_warning(
                    self,
                    "Barang Nonaktif",
                    f'Barang "{product["name"]}" sedang nonaktif.',
                )
                return

            self._open_edit_dialog(product)
        else:
            self._open_add_dialog(
                prefill_barcode=code,
            )

    # ==================================================================
    # REFRESH
    # ==================================================================

    def refresh(self):
        search = self.search_var.get().strip()

        try:
            products = self.product_model.list_products(
                search=search,
            )
        except Exception:
            self._products = []
            self.table.set_error(
                "Gagal memuat daftar barang",
                "Terjadi kesalahan saat membaca data barang.",
            )
            return

        self._products = list(products)

        self._update_summary(self._products)

        rows = []
        variants = []

        for product in self._products:
            stock = int(
                product.get("stock") or 0
            )

            rows.append(
                [
                    product.get("barcode") or "-",
                    product.get("name") or "-",
                    format_rupiah(product.get("purchase_price", 0)),
                    format_rupiah(product.get("selling_price", 0)),
                    str(stock),
                ]
            )

            if stock == 0:
                variants.append("danger")
            elif stock <= LOW_STOCK_LIMIT:
                variants.append("warning")
            else:
                variants.append("success")

        self.table.set_rows(
            rows,
            variants=variants,
            searching=bool(search),
        )

    def _on_activate(self, index: int):
        if 0 <= index < len(self._products):
            self._open_edit_dialog(self._products[index])

    # ==================================================================
    # SUMMARY UPDATE
    # ==================================================================

    def _update_summary(
        self,
        products,
    ):
        total_products = len(products)

        total_stock = 0
        low_stock = 0

        for product in products:
            stock = int(
                product.get("stock") or 0
            )

            total_stock += stock

            if stock <= LOW_STOCK_LIMIT:
                low_stock += 1

        self.total_card.set_value(str(total_products))
        self.stock_card.set_value(str(total_stock))
        self.low_stock_card.set_value(
            str(low_stock),
            color=COLORS["warning"] if low_stock > 0 else None,
        )

    # ==================================================================
    # ADD
    # ==================================================================

    def _open_add_dialog(
        self,
        prefill_barcode: str = "",
    ):
        ProductFormDialog(
            self,
            title="Tambah Barang",
            on_submit=self._handle_add,
            initial={
                "barcode": prefill_barcode,
            },
            is_edit=False,
        )

    def _handle_add(
        self,
        data: dict,
    ):
        try:
            result = self.product_model.add_product(
                name=data["name"],
                purchase_price=data["purchase_price"],
                selling_price=data["selling_price"],
                opening_stock=data["opening_stock"],
                barcode=data["barcode"],
                supplier_id=None,
                image_path="",
            )

            if (
                not isinstance(result, tuple)
                or len(result) < 2
            ):
                return (
                    False,
                    "Gagal menyimpan barang.",
                )

            success = result[0]
            message = result[1]

            if not success:
                return False, message

            return True, message

        except Exception:
            return (
                False,
                "Gagal menyimpan barang. Silakan coba lagi.",
            )

    # ==================================================================
    # EDIT
    # ==================================================================

    def _open_edit_dialog(
        self,
        product: dict,
    ):
        ProductFormDialog(
            self,
            title="Edit Barang",
            on_submit=lambda data: (
                self._handle_edit(
                    product["id"],
                    product,
                    data,
                )
            ),
            initial={
                "barcode": product.get(
                    "barcode"
                ) or "",
                "name": product.get(
                    "name"
                ) or "",
                "purchase_price": str(
                    product.get(
                        "purchase_price",
                        "",
                    )
                ),
                "selling_price": str(
                    product.get(
                        "selling_price",
                        "",
                    )
                ),
                "stock": str(
                    product.get(
                        "stock",
                        0,
                    )
                ),
            },
            is_edit=True,
            on_deactivate=(
                (lambda on_done: self._confirm_deactivate(
                    product,
                    on_done,
                ))
                if product.get("is_active")
                else None
            ),
        )

    def _handle_edit(
        self,
        product_id: int,
        old_product: dict,
        data: dict,
    ):
        try:
            result = self.product_model.update_product(
                product_id=product_id,
                name=data["name"],
                purchase_price=data["purchase_price"],
                selling_price=data["selling_price"],
                barcode=data["barcode"],
                supplier_id=None,
                # Gambar tidak lagi diubah dari UI; data lama dibiarkan utuh.
                image_path=old_product.get("image_path") or "",
            )

            if isinstance(result, tuple):
                if len(result) >= 2:
                    success = result[0]
                    message = result[1]
                else:
                    success = False
                    message = str(
                        result[0]
                    )
            else:
                success = False
                message = str(result)

            if not success:
                return False, message

            return True, message

        except Exception:
            return (
                False,
                "Gagal memperbarui barang. Silakan coba lagi.",
            )

    # ==================================================================
    # DEACTIVATE
    # ==================================================================

    def _confirm_deactivate(
        self,
        product: dict,
        on_done=None,
    ):
        ProductConfirmDialog(
            self,
            title="Nonaktifkan Barang",
            message=(
                f'Nonaktifkan "{product["name"]}"?\n\n'
                "Barang tidak akan muncul pada transaksi baru, "
                "tetapi histori transaksi lama tetap aman."
            ),
            on_confirm=lambda: (
                self._handle_deactivate(
                    product["id"],
                    on_done,
                )
            ),
        )

    def _handle_deactivate(
        self,
        product_id: int,
        on_done=None,
    ):
        try:
            success, message = (
                self.product_model.deactivate_product(
                    product_id
                )
            )

            if not success:
                show_error(
                    self,
                    "Gagal",
                    message,
                )
                return

        except Exception:
            show_error(
                self,
                "Terjadi Kesalahan",
                "Gagal menonaktifkan barang. Coba lagi.",
            )
            return

        self.refresh()

        # Tutup dialog Edit yang memicu penonaktifan.
        if on_done:
            on_done()


# ======================================================================
# PRODUCT FORM DIALOG
# ======================================================================

class ProductFormDialog(BaseDialog):
    """
    Dialog Tambah/Edit Barang.

    Tambah:
        - Barcode opsional
        - Nama
        - Harga beli dan harga jual
        - Stok awal

    Edit:
        - Sama, tetapi stok saat ini hanya ditampilkan (read-only)
        - Tombol Nonaktifkan di footer kiri (barang aktif saja)

    Gambar produk dan supplier tidak ditampilkan.
    """

    def __init__(
        self,
        master: ProductsPage,
        title: str,
        on_submit,
        initial: dict = None,
        is_edit: bool = False,
        on_deactivate=None,
    ):
        super().__init__(master, title, DIALOG_WIDTH["form"])

        self.on_deactivate = on_deactivate
        self.master_page = master
        self.on_submit = on_submit
        self.initial = initial or {}
        self.is_edit = is_edit

        self._build_form()

        self.set_buttons("Simpan", self._submit)
        self._add_deactivate_button()
        self.finish()

        if self.initial.get("barcode"):
            self.after(100, self.name_field.focus)
        else:
            self.after(100, self.barcode_field.focus)

    # ==================================================================
    # UI
    # ==================================================================

    def _add_deactivate_button(self):
        """Nonaktifkan: footer kiri, merah, hanya saat edit barang aktif."""
        if not (self.is_edit and self.on_deactivate):
            return

        ctk.CTkButton(
            self.footer,
            text="Nonaktifkan",
            command=lambda: self.on_deactivate(self.destroy),
            width=BUTTON_WIDTH["confirm"],
            **button_style("danger"),
        ).pack(side="left")

    def _build_form(self):
        body = self.body

        self.barcode_field = FormField(
            body,
            "Barcode (opsional)",
            "Masukkan barcode",
            initial=self.initial.get("barcode", ""),
        )
        self.barcode_field.pack(
            fill="x",
            pady=(0, SPACING["md"]),
        )

        self.name_field = FormField(
            body,
            "Nama Barang",
            "Masukkan nama barang",
            initial=self.initial.get("name", ""),
            required=True,
        )
        self.name_field.pack(
            fill="x",
            pady=(0, SPACING["md"]),
        )

        # Harga beli dan harga jual berdampingan.
        prices = ctk.CTkFrame(
            body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        prices.pack(
            fill="x",
            pady=(0, SPACING["md"]),
        )
        prices.grid_columnconfigure((0, 1), weight=1, uniform="price")

        self.purchase_price_field = FormField(
            prices,
            "Harga Beli",
            "Contoh: 2500",
            initial=self.initial.get("purchase_price", ""),
            required=True,
        )
        self.purchase_price_field.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, SPACING["sm"]),
        )

        self.selling_price_field = FormField(
            prices,
            "Harga Jual",
            "Contoh: 3000",
            initial=self.initial.get("selling_price", ""),
            required=True,
        )
        self.selling_price_field.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(SPACING["sm"], 0),
        )

        # Stok
        if self.is_edit:
            self._build_readonly_stock()
        else:
            self.opening_stock_field = FormField(
                body,
                "Stok Awal",
                "Contoh: 10",
                initial="0",
                required=True,
            )
            self.opening_stock_field.pack(fill="x")

        # Nama atribut lama dipertahankan.
        self.barcode_entry = self.barcode_field.entry
        self.name_entry = self.name_field.entry
        self.purchase_price_entry = self.purchase_price_field.entry
        self.selling_price_entry = self.selling_price_field.entry

        if not self.is_edit:
            self.opening_stock_entry = self.opening_stock_field.entry

        self.error_label = ErrorText(body)
        self.error_label.pack(
            fill="x",
            pady=(SPACING["sm"], 0),
        )

    def _build_readonly_stock(self):
        ctk.CTkLabel(
            self.body,
            text="Stok Saat Ini",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        box = ctk.CTkFrame(
            self.body,
            fg_color=COLORS["surface_hover"],
            corner_radius=RADIUS["input"],
        )
        box.pack(
            fill="x",
            pady=(SPACING["xs"], 0),
        )

        self.stock_label = ctk.CTkLabel(
            box,
            text=str(self.initial.get("stock", 0)),
            font=get_font("button"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.stock_label.pack(
            fill="x",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        )

        ctk.CTkLabel(
            self.body,
            text=(
                "Stok tidak diubah dari menu Barang. "
                "Gunakan transaksi pembelian atau penjualan."
            ),
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            wraplength=DIALOG_WIDTH["form"] - 48,
            justify="left",
            anchor="w",
        ).pack(
            fill="x",
            pady=(SPACING["xs"], 0),
        )

    # ==================================================================
    # SUBMIT
    # ==================================================================

    def _submit(self):
        data = {
            "barcode": self.barcode_entry.get().strip(),
            "name": self.name_entry.get().strip(),
            "purchase_price": self.purchase_price_entry.get().strip(),
            "selling_price": self.selling_price_entry.get().strip(),
        }

        if self.is_edit:
            data["opening_stock"] = 0
        else:
            data["opening_stock"] = (
                self.opening_stock_entry.get().strip()
            )

        # --------------------------------------------------------------
        # Validasi
        # --------------------------------------------------------------

        if not data["name"]:
            self._show_error(
                "Nama barang wajib diisi."
            )
            self.name_entry.focus()
            return

        if not data["purchase_price"]:
            self._show_error(
                "Harga beli wajib diisi."
            )
            self.purchase_price_entry.focus()
            return

        if not data["selling_price"]:
            self._show_error(
                "Harga jual wajib diisi."
            )
            self.selling_price_entry.focus()
            return

        if not self.is_edit:
            if not data["opening_stock"]:
                self._show_error(
                    "Stok awal wajib diisi."
                )
                self.opening_stock_entry.focus()
                return

            try:
                opening_stock = int(
                    data["opening_stock"]
                )

                if opening_stock < 0:
                    raise ValueError

            except (TypeError, ValueError):
                self._show_error(
                    "Stok awal harus berupa angka 0 atau lebih."
                )
                self.opening_stock_entry.focus()
                return
            
        try:
            result = self.on_submit(
                data
            )

            if not isinstance(result, tuple):
                self._show_error(
                    "Terjadi kesalahan saat menyimpan data."
                )
                return

            if len(result) < 2:
                self._show_error(
                    "Terjadi kesalahan saat menyimpan data."
                )
                return

            success = result[0]
            message = result[1]

        except Exception:
            self._show_error(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not success:
            self._show_error(
                message
            )
            return

        self.master_page.refresh()
        self.destroy()

    def _show_error(
        self,
        message,
    ):
        self.error_label.show(
            message or "Terjadi kesalahan."
        )


# ======================================================================
# CONFIRMATION DIALOG
# ======================================================================

class ProductConfirmDialog(ConfirmDialog):
    """Dialog konfirmasi nonaktifkan barang (memakai dialog standar)."""

    def __init__(
        self,
        master,
        title: str,
        message: str,
        on_confirm,
    ):
        super().__init__(
            master,
            title,
            message,
            on_confirm,
            confirm_text="Nonaktifkan",
        )