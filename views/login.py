"""
views/login.py

Halaman/jendela login aplikasi Warung Hutang.

Catatan desain:
- Jendela ini dibuat sebagai CTk (root) yang berdiri sendiri untuk PHASE 2,
  supaya bisa langsung dites. Mulai PHASE 3, alur ini akan disatukan
  dengan main window (sidebar) - biasanya login window tampil dulu,
  lalu ditutup dan digantikan main window setelah sukses.
- on_login_success(user) dipanggil setelah login berhasil, membawa data
  user (tanpa password_hash) agar main window tahu siapa yang sedang login.
"""

import customtkinter as ctk
import os

from database.database import Database
from models.user import UserModel
from utils.error_handler import install_global_error_handler

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

WINDOW_WIDTH = 380
WINDOW_HEIGHT = 440


class LoginWindow(ctk.CTk):
    def __init__(self, on_login_success=None, db: Database = None):
        super().__init__()

        self.on_login_success = on_login_success
        self.db = db or Database()
        self.user_model = UserModel(self.db)
        self._password_visible = False

        self.title("Warung Hutang - Login")
        self.resizable(False, False)
        self._center_on_screen(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._set_icon()

        self._build_ui()
        install_global_error_handler(self)

    def _center_on_screen(self, width: int, height: int):
        """Menempatkan jendela tepat di tengah layar, dihitung dari ukuran
        layar pengguna saat ini - bukan posisi hardcode - supaya tetap
        di tengah pada resolusi layar berapa pun."""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_icon(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "..", "assets", "icon.ico")
        try:
            self.iconbitmap(icon_path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        container = ctk.CTkFrame(self, corner_radius=16)
        container.pack(expand=True, fill="both", padx=24, pady=24)

        ctk.CTkLabel(
            container,
            text="Warung Hutang",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(32, 4))

        ctk.CTkLabel(
            container,
            text="Silakan login untuk melanjutkan",
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        ).pack(pady=(0, 24))

        # Username
        ctk.CTkLabel(container, text="Username", anchor="w").pack(
            fill="x", padx=32
        )
        self.username_entry = ctk.CTkEntry(
            container, placeholder_text="Masukkan username", height=38
        )
        self.username_entry.pack(fill="x", padx=32, pady=(4, 16))

        # Password
        ctk.CTkLabel(container, text="Password", anchor="w").pack(
            fill="x", padx=32
        )
        password_row = ctk.CTkFrame(container, fg_color="transparent")
        password_row.pack(fill="x", padx=32, pady=(4, 4))
        password_row.grid_columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(
            password_row, placeholder_text="Masukkan password", show="*", height=38
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")

        self.toggle_btn = ctk.CTkButton(
            password_row,
            text="Lihat",
            width=56,
            height=38,
            fg_color="gray80",
            text_color="black",
            hover_color="gray70",
            command=self._toggle_password_visibility,
        )
        self.toggle_btn.grid(row=0, column=1, padx=(8, 0))

        # Label error (kosong secara default, muncul saat ada masalah)
        self.error_label = ctk.CTkLabel(
            container, text="", text_color="#D64545", font=ctk.CTkFont(size=12)
        )
        self.error_label.pack(fill="x", padx=32, pady=(8, 0))

        # Tombol masuk
        self.login_button = ctk.CTkButton(
            container, text="Masuk", height=40, command=self._handle_login
        )
        self.login_button.pack(fill="x", padx=32, pady=(16, 32))

        # Enter menekan tombol masuk dari field manapun
        self.bind("<Return>", lambda event: self._handle_login())
        self.username_entry.focus()

    # ------------------------------------------------------------------
    # Aksi
    # ------------------------------------------------------------------
    def _toggle_password_visibility(self):
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.password_entry.configure(show="")
            self.toggle_btn.configure(text="Sembunyi")
        else:
            self.password_entry.configure(show="*")
            self.toggle_btn.configure(text="Lihat")

    def _handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self._show_error("Username dan password wajib diisi.")
            return

        self.login_button.configure(state="disabled", text="Memproses...")
        self.update_idletasks()

        try:
            user = self.user_model.authenticate(username, password)
        except Exception:
            # Jangan pernah menampilkan traceback ke pengguna awam.
            self._show_error("Terjadi kesalahan pada database. Coba lagi.")
            self.login_button.configure(state="normal", text="Masuk")
            return

        self.login_button.configure(state="normal", text="Masuk")

        if user is None:
            self._show_error("Username atau password salah.")
            self.password_entry.delete(0, "end")
            return

        self._show_error("")

        if self.on_login_success:
            self.on_login_success(user)
        else:
            # Fallback jika dijalankan berdiri sendiri tanpa callback.
            self._show_error("")
            self.destroy()

    def _show_error(self, message: str):
        self.error_label.configure(text=message)


if __name__ == "__main__":
    # Menjalankan halaman login secara berdiri sendiri untuk keperluan testing manual.
    def _on_success(user):
        print(f"[TEST] Login berhasil sebagai: {user['username']} (id={user['id']})")

    db = Database()
    db.initialize()
    app = LoginWindow(on_login_success=_on_success, db=db)
    app.mainloop()
