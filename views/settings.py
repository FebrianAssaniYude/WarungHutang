"""
views/settings.py

Halaman Pengaturan:
- Nama Warung (dipakai sebagai header di laporan PDF)
- Ganti Username
- Ganti Password (wajib memasukkan password lama)
- Backup Database
- Restore Database (WAJIB konfirmasi - tindakan berisiko)
- Informasi Aplikasi
"""

from tkinter import filedialog, messagebox

import customtkinter as ctk

from models.settings import SettingsModel, DEFAULT_NAMA_WARUNG
from models.user import UserModel
from utils.backup import backup_database, restore_database

APP_VERSION = "1.0.0"


class SettingsPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        user: dict,
        settings_model: SettingsModel,
        user_model: UserModel,
        db_path_getter,
        on_username_changed=None,
    ):
        super().__init__(master, fg_color="transparent")

        self.user = user
        self.settings_model = settings_model
        self.user_model = user_model
        self.db_path_getter = db_path_getter
        self.on_username_changed = on_username_changed

        ctk.CTkLabel(
            self, text="Pengaturan", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=32, pady=(28, 12))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._build_nama_warung_section()
        self._build_username_section()
        self._build_password_section()
        self._build_backup_section()
        self._build_info_section()

    def _safe_get_nama_warung(self) -> str:
        # Dipanggil saat konstruksi halaman (termasuk saat MainWindow
        # membangun semua halaman sekaligus setelah login) - kegagalan di
        # sini TIDAK BOLEH menjatuhkan seluruh main window, jadi jatuh ke
        # nilai default jika database bermasalah.
        try:
            return self.settings_model.get_nama_warung()
        except Exception:
            return DEFAULT_NAMA_WARUNG

    def refresh(self):
        # Muat ulang nilai terkini setiap kali halaman dibuka.
        self.nama_warung_entry.delete(0, "end")
        self.nama_warung_entry.insert(0, self._safe_get_nama_warung())

        self.username_entry.delete(0, "end")
        self.username_entry.insert(0, self.user.get("username", ""))

    # ------------------------------------------------------------------
    # Helper kartu section
    # ------------------------------------------------------------------
    def _make_card(self, title: str):
        card = ctk.CTkFrame(self.scroll, fg_color=("white", "gray17"))
        card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(18, 12))
        return card

    @staticmethod
    def _show_status(label: ctk.CTkLabel, message: str, error: bool = False):
        label.configure(text=message, text_color="#D64545" if error else "#2E7D32")

    # ------------------------------------------------------------------
    # Nama Warung
    # ------------------------------------------------------------------
    def _build_nama_warung_section(self):
        card = self._make_card("Nama Warung")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 8))

        self.nama_warung_entry = ctk.CTkEntry(row, height=36)
        self.nama_warung_entry.insert(0, self._safe_get_nama_warung())
        self.nama_warung_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row, text="Simpan", width=90, command=self._handle_save_nama_warung).pack(
            side="left"
        )

        self.nama_warung_status = ctk.CTkLabel(card, text="")
        self.nama_warung_status.pack(anchor="w", padx=20, pady=(0, 16))

    def _handle_save_nama_warung(self):
        value = self.nama_warung_entry.get().strip()
        try:
            saved = self.settings_model.set_nama_warung(value)
        except Exception:
            self._show_status(
                self.nama_warung_status, "Terjadi kesalahan pada database. Coba lagi.", error=True
            )
            return
        self.nama_warung_entry.delete(0, "end")
        self.nama_warung_entry.insert(0, saved)
        self._show_status(self.nama_warung_status, f"Nama warung disimpan: {saved}")

    # ------------------------------------------------------------------
    # Ganti Username
    # ------------------------------------------------------------------
    def _build_username_section(self):
        card = self._make_card("Ganti Username")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 8))

        self.username_entry = ctk.CTkEntry(row, height=36)
        self.username_entry.insert(0, self.user.get("username", ""))
        self.username_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row, text="Simpan", width=90, command=self._handle_change_username).pack(
            side="left"
        )

        self.username_status = ctk.CTkLabel(card, text="")
        self.username_status.pack(anchor="w", padx=20, pady=(0, 16))

    def _handle_change_username(self):
        new_username = self.username_entry.get().strip()
        try:
            ok, message = self.user_model.change_username(self.user["id"], new_username)
        except Exception:
            self._show_status(
                self.username_status, "Terjadi kesalahan pada database. Coba lagi.", error=True
            )
            return

        if not ok:
            self._show_status(self.username_status, message, error=True)
            return

        self.user["username"] = new_username
        if self.on_username_changed:
            self.on_username_changed(new_username)
        self._show_status(self.username_status, message)

    # ------------------------------------------------------------------
    # Ganti Password
    # ------------------------------------------------------------------
    def _build_password_section(self):
        card = self._make_card("Ganti Password")

        ctk.CTkLabel(card, text="Password Lama", anchor="w").pack(fill="x", padx=20)
        self.old_password_entry = ctk.CTkEntry(card, height=36, show="*")
        self.old_password_entry.pack(fill="x", padx=20, pady=(2, 10))

        ctk.CTkLabel(card, text="Password Baru", anchor="w").pack(fill="x", padx=20)
        self.new_password_entry = ctk.CTkEntry(card, height=36, show="*")
        self.new_password_entry.pack(fill="x", padx=20, pady=(2, 10))

        ctk.CTkLabel(card, text="Konfirmasi Password Baru", anchor="w").pack(fill="x", padx=20)
        self.confirm_password_entry = ctk.CTkEntry(card, height=36, show="*")
        self.confirm_password_entry.pack(fill="x", padx=20, pady=(2, 10))

        ctk.CTkButton(card, text="Simpan Password Baru", command=self._handle_change_password).pack(
            fill="x", padx=20, pady=(0, 8)
        )

        self.password_status = ctk.CTkLabel(card, text="")
        self.password_status.pack(anchor="w", padx=20, pady=(0, 16))

    def _handle_change_password(self):
        old = self.old_password_entry.get()
        new = self.new_password_entry.get()
        confirm = self.confirm_password_entry.get()

        if new != confirm:
            self._show_status(self.password_status, "Konfirmasi password baru tidak cocok.", error=True)
            return

        try:
            ok, message = self.user_model.change_password(self.user["id"], old, new)
        except Exception:
            self._show_status(
                self.password_status, "Terjadi kesalahan pada database. Coba lagi.", error=True
            )
            return

        if not ok:
            self._show_status(self.password_status, message, error=True)
            return

        self.old_password_entry.delete(0, "end")
        self.new_password_entry.delete(0, "end")
        self.confirm_password_entry.delete(0, "end")
        self._show_status(self.password_status, message)

    # ------------------------------------------------------------------
    # Backup & Restore
    # ------------------------------------------------------------------
    def _build_backup_section(self):
        card = self._make_card("Backup & Restore Database")

        ctk.CTkLabel(
            card,
            text="Backup menyimpan salinan database dengan nama bertanggal. "
                 "Restore akan MENGGANTI seluruh data saat ini dengan isi file backup yang dipilih.",
            anchor="w", justify="left", wraplength=500, text_color="gray50", font=ctk.CTkFont(size=12),
        ).pack(fill="x", padx=20, pady=(0, 12))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkButton(btn_row, text="Backup Database", command=self._handle_backup).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(
            btn_row, text="Restore Database", fg_color="#D64545", hover_color="#B93A3A",
            command=self._handle_restore,
        ).pack(side="left")

        self.backup_status = ctk.CTkLabel(card, text="")
        self.backup_status.pack(anchor="w", padx=20, pady=(0, 16))

    def _handle_backup(self):
        try:
            backup_path = backup_database(self.db_path_getter())
        except Exception:
            messagebox.showerror(
                "Backup Gagal", "Terjadi kesalahan saat membuat backup. Coba lagi."
            )
            return

        self._show_status(self.backup_status, f"Backup berhasil: {backup_path}")
        messagebox.showinfo("Backup Berhasil", f"Database berhasil dibackup ke:\n{backup_path}")

    def _handle_restore(self):
        chosen_path = filedialog.askopenfilename(
            title="Pilih File Backup",
            filetypes=[("Database SQLite", "*.db")],
        )
        if not chosen_path:
            return  # dibatalkan

        confirmed = messagebox.askyesno(
            "Konfirmasi Restore",
            "PERHATIAN: Restore akan MENGGANTI seluruh data saat ini dengan isi "
            "file backup yang dipilih.\n\n"
            "Data saat ini akan otomatis diamankan terlebih dahulu, tapi sebaiknya "
            "lanjutkan hanya jika Anda yakin.\n\nLanjutkan restore?",
            icon="warning",
        )
        if not confirmed:
            return

        try:
            safety_path = restore_database(chosen_path, self.db_path_getter())
        except Exception:
            messagebox.showerror(
                "Restore Gagal", "Terjadi kesalahan saat melakukan restore. Coba lagi."
            )
            return

        self._show_status(self.backup_status, "Restore berhasil.")
        note = f"\n\n(Data sebelumnya diamankan ke:\n{safety_path})" if safety_path else ""
        messagebox.showinfo(
            "Restore Berhasil",
            "Database berhasil dipulihkan dari file backup." + note +
            "\n\nDisarankan logout lalu login kembali untuk memastikan tampilan sinkron.",
        )

    # ------------------------------------------------------------------
    # Informasi Aplikasi
    # ------------------------------------------------------------------
    def _build_info_section(self):
        card = self._make_card("Informasi Aplikasi")

        info_lines = [
            f"Warung Hutang v{APP_VERSION}",
            "Aplikasi pencatatan hutang warung - 100% offline, database lokal (SQLite).",
            "Dibangun dengan Python, CustomTkinter, dan SQLite.",
        ]
        for line in info_lines:
            ctk.CTkLabel(card, text=line, anchor="w", text_color="gray50", font=ctk.CTkFont(size=12)).pack(
                fill="x", padx=20, pady=(0, 4)
            )

        ctk.CTkLabel(card, text="", height=8).pack()  # spacer bawah
