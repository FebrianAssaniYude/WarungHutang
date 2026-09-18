"""
views/main_window.py

Jendela utama aplikasi setelah login berhasil: sidebar navigasi kiri +
area konten kanan yang berganti-ganti sesuai menu yang dipilih.

PHASE 3 ini baru menyediakan KERANGKA navigasinya saja. Setiap halaman
(Pelanggan, Barang, Transaksi Hutang, dst) masih berupa placeholder
kosong dan akan diisi satu per satu pada phase-phase berikutnya, sesuai
urutan yang sudah disepakati - supaya tidak membangun semua sekaligus.
"""

import customtkinter as ctk
import os

from database.database import Database, get_database_path
from models.customer import CustomerModel
from models.debt import DebtModel
from models.history import HistoryModel
from models.payment import PaymentModel
from models.product import ProductModel
from models.report import ReportModel
from models.settings import SettingsModel
from models.user import UserModel
from utils.error_handler import install_global_error_handler
from views.customers import CustomersPage
from views.debts import TransaksiHutangPage
from views.history import HistoryPage
from views.payments import PaymentsPage
from views.products import ProductsPage
from views.reports import LaporanPage
from views.settings import SettingsPage

SIDEBAR_WIDTH = 220
WINDOW_SIZE = "1280x720"
MIN_WINDOW_SIZE = (1024, 600)

# Urutan menu sesuai spesifikasi. "key" dipakai secara internal,
# "label" yang tampil ke pengguna.
MENU_ITEMS = [
    {"key": "dashboard", "label": "Dashboard"},
    {"key": "pelanggan", "label": "Pelanggan"},
    {"key": "barang", "label": "Barang"},
    {"key": "transaksi_hutang", "label": "Transaksi Hutang"},
    {"key": "pembayaran", "label": "Pembayaran"},
    {"key": "riwayat", "label": "Riwayat"},
    {"key": "laporan", "label": "Laporan"},
    {"key": "pengaturan", "label": "Pengaturan"},
]


class PlaceholderPage(ctk.CTkFrame):
    """
    Halaman sementara untuk menu yang belum dibangun fiturnya.
    Akan digantikan oleh halaman sungguhan pada phase terkait
    (mis. Pelanggan -> PHASE 4, Barang -> PHASE 5, dst).
    """

    def __init__(self, master, title: str):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=32, pady=(28, 4))

        ctk.CTkLabel(
            self,
            text="Halaman ini akan dibangun pada tahap pengembangan berikutnya.",
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        ).pack(anchor="w", padx=32)


class MainWindow(ctk.CTk):
    def __init__(self, user: dict, db=None, on_logout=None):
        super().__init__()

        self.user = user
        self.db = db or Database()
        self.on_logout = on_logout
        self.pages = {}
        self.nav_buttons = {}
        self.active_key = None
        self.logged_out = False
        
        self.title("Warung Hutang")
        self._set_icon()
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_WINDOW_SIZE)
        self.after(10, self._maximize)

        self.grid_columnconfigure(1, weight=1)
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
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(len(MENU_ITEMS) + 2, weight=1)  # dorong logout ke bawah

        # Header / nama aplikasi + nama pengguna yang sedang login
        ctk.CTkLabel(
            sidebar,
            text="Warung Hutang",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(24, 2), sticky="w")

        self.user_label = ctk.CTkLabel(
            sidebar,
            text=f"Masuk sebagai: {self.user.get('username', '-')}",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.user_label.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Tombol menu
        row = 2
        for item in MENU_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=item["label"],
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
                command=lambda key=item["key"]: self.show_page(key),
            )
            btn.grid(row=row, column=0, padx=12, pady=2, sticky="ew")
            self.nav_buttons[item["key"]] = btn
            row += 1

        sidebar.grid_columnconfigure(0, weight=1)

        # Tombol logout - selalu di bagian bawah sidebar
        logout_btn = ctk.CTkButton(
            sidebar,
            text="Logout",
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color="#D64545",
            hover_color="#B93A3A",
            command=self._handle_logout,
        )
        logout_btn.grid(row=len(MENU_ITEMS) + 3, column=0, padx=12, pady=(4, 16), sticky="ew")

    def _handle_logout(self):
        # Catatan: sesuai spesifikasi, konfirmasi logout hanya diperlukan
        # jika ada data yang belum tersimpan. Karena belum ada halaman
        # dengan form yang menyimpan state (baru dibangun di phase
        # berikutnya), logout saat ini langsung dieksekusi tanpa popup.
        self.logged_out = True
        if self.on_logout:
            self.on_logout()
        self.destroy()

    def _maximize(self):
        try:
            self.state("zoomed")  # Windows
        except Exception:
            try:
                self.attributes("-zoomed", True)  # Linux
            except Exception:
                self.update_idletasks()
                w = self.winfo_screenwidth()
                h = self.winfo_screenheight()
                self.geometry(f"{w}x{h}+0+0")

    # ------------------------------------------------------------------
    # Area konten
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray95", "gray12"))
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

    def _build_pages(self):
        self.customer_model = CustomerModel(self.db)
        self.product_model = ProductModel(self.db)
        self.debt_model = DebtModel(self.db)
        self.payment_model = PaymentModel(self.db)
        self.history_model = HistoryModel(self.db)
        self.report_model = ReportModel(self.db)
        self.user_model = UserModel(self.db)
        self.settings_model = SettingsModel(self.db)

        for item in MENU_ITEMS:
            if item["key"] == "pelanggan":
                page = CustomersPage(self.content_area, customer_model=self.customer_model)
            elif item["key"] == "barang":
                page = ProductsPage(self.content_area, product_model=self.product_model)
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
                page = LaporanPage(self.content_area, report_model=self.report_model)
            elif item["key"] == "pengaturan":
                page = SettingsPage(
                    self.content_area,
                    user=self.user,
                    settings_model=self.settings_model,
                    user_model=self.user_model,
                    db_path_getter=get_database_path,
                    on_username_changed=self._handle_username_changed,
                )
            else:
                page = PlaceholderPage(self.content_area, title=item["label"])
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[item["key"]] = page

    def _handle_username_changed(self, new_username: str):
        self.user["username"] = new_username
        self.user_label.configure(text=f"Masuk sebagai: {new_username}")

    def show_page(self, key: str):
        if key not in self.pages:
            return

        page = self.pages[key]
        # Muat ulang data setiap kali halaman dibuka, supaya perubahan dari
        # halaman lain (mis. transaksi hutang di phase berikutnya) selalu
        # tercermin di sini.
        if hasattr(page, "refresh"):
            page.refresh()

        page.tkraise()
        self.active_key = key

        # Highlight tombol menu yang sedang aktif
        for btn_key, btn in self.nav_buttons.items():
            if btn_key == key:
                btn.configure(fg_color=("gray80", "gray25"))
            else:
                btn.configure(fg_color="transparent")



if __name__ == "__main__":
    # Uji manual berdiri sendiri (tanpa lewat login), memakai user palsu.
    fake_user = {"id": 1, "username": "admin"}
    app = MainWindow(user=fake_user, on_logout=lambda: print("[TEST] Logout dipanggil"))
    app.mainloop()
