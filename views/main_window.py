import customtkinter as ctk
import os
from datetime import date

from database.database import Database, get_database_path
from models.customer import CustomerModel
from models.debt import DebtModel
from models.supplier import SupplierModel
from models.history import HistoryModel
from models.payment import PaymentModel
from models.product import ProductModel
from models.purchase import PurchaseModel
from models.sale import SaleModel
from models.report import ReportModel
from models.settings import SettingsModel
from models.user import UserModel
from utils.error_handler import install_global_error_handler
from utils.theme import (
    COLORS,
    LAYOUT,
    RADIUS,
    SPACING,
    get_font,
    logout_button_style,
    nav_button_style,
)
from views.dashboard import DashboardPage
from views.customers import CustomersPage
from views.debts import TransaksiHutangPage
from views.history import HistoryPage
from views.payments import PaymentsPage
from views.products import ProductsPage
from views.purchases import PurchasePage
from views.sales import SalePage
from views.reports import LaporanPage
from views.settings import SettingsPage


SIDEBAR_WIDTH = LAYOUT["sidebar_width"]
WINDOW_SIZE = "1280x720"
MIN_WINDOW_SIZE = (1024, 600)

# Menu aplikasi.
MENU_ITEMS = [
    {"key": "dashboard", "label": "Dashboard"},
    {"key": "pelanggan", "label": "Pelanggan"},
    {"key": "barang", "label": "Barang"},
    {"key": "pembelian", "label": "Pembelian"},
    {"key": "penjualan", "label": "Penjualan"},
    {"key": "transaksi_hutang", "label": "Transaksi Hutang"},
    {"key": "pembayaran", "label": "Pembayaran"},
    {"key": "riwayat", "label": "Riwayat"},
    {"key": "laporan", "label": "Laporan"},
    {"key": "pengaturan", "label": "Pengaturan"},
]

# Halaman bertabel besar. Hanya dimuat ulang bila datanya memang berubah
# (lihat DATA_DEPENDENTS), bukan setiap kali menu diklik.
HEAVY_PAGES = {"dashboard", "pelanggan", "barang", "riwayat", "laporan"}

# Halaman yang bisa mengubah data -> halaman berat yang ikut terpengaruh.
# Dipakai saat pengguna meninggalkan halaman tersebut.
DATA_DEPENDENTS = {
    "pelanggan": {"dashboard", "riwayat", "laporan"},
    "barang": {"dashboard"},
    "pembelian": {"dashboard", "barang", "riwayat"},
    "penjualan": {"dashboard", "barang", "riwayat"},
    "transaksi_hutang": {
        "dashboard", "pelanggan", "barang", "riwayat", "laporan",
    },
    "pembayaran": {"dashboard", "pelanggan", "riwayat", "laporan"},
    "pengaturan": HEAVY_PAGES,  # Restore database mengubah semuanya
}


class MainWindow(ctk.CTk):
    def __init__(self, user: dict, db=None, on_logout=None):
        super().__init__()

        self.user = user
        self.db = db or Database()
        self.on_logout = on_logout
        self.settings_model = SettingsModel(self.db)
        self.pages = {}
        self.nav_buttons = {}
        self.active_key = None
        self.logged_out = False

        # Halaman lain sudah memuat datanya sendiri saat dibuat;
        # hanya Dashboard yang belum.
        self._stale_pages = {"dashboard", "barang"}
        self._data_date = date.today()

        self.store_name = self.settings_model.get_nama_warung()
        self.title(self.store_name)
        self._set_icon()
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_WINDOW_SIZE)
        self.after(10, self._maximize)

        # Kolom 0 = sidebar, kolom 1 = garis pemisah, kolom 2 = konten.
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self._build_pages()

        install_global_error_handler(self)

        self.show_page("dashboard")

    def _set_icon(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "..", "assets", "icon.ico")

        try:
            self.iconbitmap(icon_path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLORS["sidebar"],
        )
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(len(MENU_ITEMS) + 2, weight=1)

        # Garis pemisah vertikal antara sidebar dan konten
        ctk.CTkFrame(
            self,
            width=1,
            corner_radius=0,
            fg_color=COLORS["sidebar_border"],
        ).grid(row=0, column=1, sticky="ns")

        header_pad = LAYOUT["sidebar_header_padding"]
        nav_pad = LAYOUT["sidebar_padding"]

        # Header / nama aplikasi + nama pengguna yang sedang login
        ctk.CTkLabel(
            sidebar,
            text=self.store_name,
            font=get_font("heading"),
            text_color=COLORS["text"],
            anchor="w",
            justify="left",
            wraplength=SIDEBAR_WIDTH - (header_pad * 2),
        ).grid(
            row=0,
            column=0,
            padx=header_pad,
            pady=LAYOUT["sidebar_title_pady"],
            sticky="w",
        )

        self.user_label = ctk.CTkLabel(
            sidebar,
            text=f"Masuk sebagai: {self.user.get('username', '-')}",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=SIDEBAR_WIDTH - (header_pad * 2),
        )
        self.user_label.grid(
            row=1,
            column=0,
            padx=header_pad,
            pady=LAYOUT["sidebar_user_pady"],
            sticky="w",
        )

        # Tombol menu
        row = 2

        for item in MENU_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=item["label"],
                anchor="w",
                height=LAYOUT["sidebar_item_height"],
                corner_radius=RADIUS["button"],
                border_width=0,
                command=lambda key=item["key"]: self.show_page(key),
            )
            self._style_nav_button(btn, active=False)
            btn.grid(
                row=row,
                column=0,
                padx=nav_pad,
                pady=LAYOUT["sidebar_item_gap"],
                sticky="ew",
            )
            self.nav_buttons[item["key"]] = btn
            row += 1

        # Garis tipis di atas tombol keluar
        ctk.CTkFrame(
            sidebar,
            height=1,
            corner_radius=0,
            fg_color=COLORS["sidebar_border"],
        ).grid(
            row=len(MENU_ITEMS) + 3,
            column=0,
            padx=nav_pad,
            pady=(0, SPACING["sm"]),
            sticky="ew",
        )

        # Tombol keluar - selalu di bagian bawah sidebar
        logout_btn = ctk.CTkButton(
            sidebar,
            text="Keluar",
            anchor="w",
            height=LAYOUT["sidebar_item_height"],
            corner_radius=RADIUS["button"],
            border_width=0,
            command=self._handle_logout,
            **logout_button_style(),
        )
        logout_btn.grid(
            row=len(MENU_ITEMS) + 4,
            column=0,
            padx=nav_pad,
            pady=(0, LAYOUT["section_gap"]),
            sticky="ew",
        )

    def _style_nav_button(self, btn, active: bool):
        btn.configure(**nav_button_style(active))

    def _handle_logout(self):
        # Keluar langsung dilakukan karena tidak ada konfirmasi
        # untuk data transaksi yang belum tersimpan.
        self.logged_out = True

        if self.on_logout:
            self.on_logout()

        self.destroy()

    def _maximize(self):
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                self.update_idletasks()
                w = self.winfo_screenwidth()
                h = self.winfo_screenheight()
                self.geometry(f"{w}x{h}+0+0")

    # ------------------------------------------------------------------
    # Area konten
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["background"],
        )
        self.content_area.grid(
            row=0,
            column=2,
            sticky="nsew",
        )
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

    def _build_pages(self):
        self.customer_model = CustomerModel(self.db)
        self.product_model = ProductModel(self.db)
        self.purchase_model = PurchaseModel(self.db)
        self.sale_model = SaleModel(self.db)
        self.debt_model = DebtModel(self.db)
        self.payment_model = PaymentModel(self.db)
        self.history_model = HistoryModel(self.db)
        self.report_model = ReportModel(self.db)
        self.user_model = UserModel(self.db)
        self.supplier_model = SupplierModel(self.db)

        for item in MENU_ITEMS:
            if item["key"] == "dashboard":
                page = DashboardPage(
                    self.content_area,
                    report_model=self.report_model,
                )

            elif item["key"] == "pelanggan":
                page = CustomersPage(
                    self.content_area,
                    customer_model=self.customer_model,
                )

            elif item["key"] == "barang":
                page = ProductsPage(
                    self.content_area,
                    product_model=self.product_model,
                    supplier_model=self.supplier_model,
                )

            elif item["key"] == "pembelian":
                page = PurchasePage(
                    self.content_area,
                    product_model=self.product_model,
                    purchase_model=self.purchase_model,
                )

            elif item["key"] == "penjualan":
                page = SalePage(
                    self.content_area,
                    product_model=self.product_model,
                    sale_model=self.sale_model,
                )

            elif item["key"] == "transaksi_hutang":
                page = TransaksiHutangPage(
                    self.content_area,
                    customer_model=self.customer_model,
                    product_model=self.product_model,
                    debt_model=self.debt_model,
                )

            elif item["key"] == "pembayaran":
                page = PaymentsPage(
                    self.content_area,
                    customer_model=self.customer_model,
                    payment_model=self.payment_model,
                )

            elif item["key"] == "riwayat":
                page = HistoryPage(
                    self.content_area,
                    history_model=self.history_model,
                    customer_model=self.customer_model,
                )

            elif item["key"] == "laporan":
                page = LaporanPage(
                    self.content_area,
                    report_model=self.report_model,
                )

            elif item["key"] == "pengaturan":
                page = SettingsPage(
                    self.content_area,
                    user=self.user,
                    settings_model=self.settings_model,
                    user_model=self.user_model,
                    db_path_getter=get_database_path,
                    on_username_changed=self._handle_username_changed,
                )

            page.grid(
                row=0,
                column=0,
                sticky="nsew",
            )
            self.pages[item["key"]] = page

    def _handle_username_changed(self, new_username: str):
        self.user["username"] = new_username
        self.user_label.configure(
            text=f"Masuk sebagai: {new_username}"
        )

    # ------------------------------------------------------------------
    # Navigasi
    # ------------------------------------------------------------------
    def invalidate(self, *keys):
        """Tandai halaman agar dimuat ulang saat dibuka berikutnya."""
        self._stale_pages.update(keys)

    def show_page(self, key: str):
        if key not in self.pages:
            return

        previous = self.active_key

        # Halaman yang baru ditinggalkan mungkin mengubah data.
        if previous and previous != key:
            self._stale_pages |= DATA_DEPENDENTS.get(previous, set())

        # Lewat tengah malam, "hari ini" di Dashboard berganti.
        today = date.today()

        if today != self._data_date:
            self._data_date = today
            self._stale_pages |= HEAVY_PAGES

        page = self.pages[key]

        # Halaman ringan selalu dimuat ulang. Halaman berat hanya bila
        # datanya berubah, atau saat menunya diklik ulang (muat ulang manual).
        needs_refresh = (
            key not in HEAVY_PAGES
            or key in self._stale_pages
            or key == previous
        )

        if needs_refresh and hasattr(page, "refresh"):
            page.refresh()

        self._stale_pages.discard(key)

        page.tkraise()
        self.active_key = key

        # Highlight tombol menu yang sedang aktif
        for btn_key, btn in self.nav_buttons.items():
            self._style_nav_button(btn, active=(btn_key == key))


if __name__ == "__main__":
    # Uji manual berdiri sendiri (tanpa lewat login), memakai user palsu.
    fake_user = {"id": 1, "username": "admin"}

    app = MainWindow(
        user=fake_user,
        on_logout=lambda: print("[TEST] Keluar dipanggil"),
    )
    app.mainloop()