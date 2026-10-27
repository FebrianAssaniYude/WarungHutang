import customtkinter as ctk
import os

from components.forms import ErrorText, FormField
from database.database import Database
from models.user import UserModel
from models.settings import SettingsModel
from utils.error_handler import install_global_error_handler
from utils.theme import COLORS, RADIUS, SPACING, button_style, get_font


WINDOW_WIDTH = 400
WINDOW_HEIGHT = 480

# Lebar isi kartu = lebar jendela - jarak luar kartu - jarak dalam kartu.
OUTER_PADDING = SPACING["xl"]
INNER_PADDING = SPACING["xl"]
CONTENT_WIDTH = WINDOW_WIDTH - (OUTER_PADDING * 2) - (INNER_PADDING * 2)

TOGGLE_BUTTON_WIDTH = 88


class LoginWindow(ctk.CTk):
    def __init__(self, on_login_success=None, db: Database = None):
        super().__init__()

        self.on_login_success = on_login_success
        self.db = db or Database()
        self.user_model = UserModel(self.db)
        self.settings_model = SettingsModel(self.db)
        self.store_name = self.settings_model.get_nama_warung()
        self._password_visible = False

        self.title(f"{self.store_name} - Login")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["background"])
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
        container = ctk.CTkFrame(
            self,
            corner_radius=RADIUS["card"],
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
        )
        container.pack(
            expand=True,
            fill="both",
            padx=OUTER_PADDING,
            pady=OUTER_PADDING,
        )

        ctk.CTkLabel(
            container,
            text=self.store_name,
            font=get_font("title"),
            text_color=COLORS["text"],
            wraplength=CONTENT_WIDTH,
            justify="center",
        ).pack(
            padx=INNER_PADDING,
            pady=(SPACING["xxl"], SPACING["xs"]),
        )

        ctk.CTkLabel(
            container,
            text="Silakan login untuk melanjutkan",
            font=get_font("body"),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, SPACING["xl"]))

        # Username
        self.username_field = FormField(
            container,
            "Username",
            "Masukkan username",
        )
        self.username_field.pack(fill="x", padx=INNER_PADDING)
        self.username_entry = self.username_field.entry

        # Password + tombol lihat/sembunyi
        password_row = ctk.CTkFrame(
            container,
            fg_color="transparent",
            width=0,
            height=0,
        )
        password_row.pack(
            fill="x",
            padx=INNER_PADDING,
            pady=(SPACING["lg"], 0),
        )
        password_row.grid_columnconfigure(0, weight=1)

        self.password_field = FormField(
            password_row,
            "Password",
            "Masukkan password",
        )
        self.password_field.grid(row=0, column=0, sticky="ew")
        self.password_entry = self.password_field.entry
        self.password_entry.configure(show="*")

        self.toggle_btn = ctk.CTkButton(
            password_row,
            text="Lihat",
            width=TOGGLE_BUTTON_WIDTH,
            command=self._toggle_password_visibility,
            **button_style("secondary"),
        )
        self.toggle_btn.grid(
            row=0,
            column=1,
            sticky="s",
            padx=(SPACING["sm"], 0),
        )

        # Label error (kosong secara default, muncul saat ada masalah)
        self.error_label = ErrorText(container)
        self.error_label.configure(wraplength=CONTENT_WIDTH)
        self.error_label.pack(
            fill="x",
            padx=INNER_PADDING,
            pady=(SPACING["sm"], 0),
        )

        # Tombol masuk
        self.login_button = ctk.CTkButton(
            container,
            text="Masuk",
            command=self._handle_login,
            **button_style("primary"),
        )
        self.login_button.pack(
            fill="x",
            padx=INNER_PADDING,
            pady=(SPACING["lg"], SPACING["xxl"]),
        )

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
        self.error_label.show(message)


if __name__ == "__main__":
    # Menjalankan halaman login secara berdiri sendiri untuk keperluan testing manual.
    def _on_success(user):
        print(f"[TEST] Login berhasil sebagai: {user['username']} (id={user['id']})")

    db = Database()
    db.initialize()
    app = LoginWindow(on_login_success=_on_success, db=db)
    app.mainloop()