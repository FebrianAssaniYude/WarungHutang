from tkinter import filedialog

import customtkinter as ctk

from components.cards import SectionCard
from components.dialogs import ConfirmDialog, show_error, show_success
from components.forms import ErrorText, FormField
from components.page_header import PageHeader
from database.integrity import DatabaseValidationError, inspect_database
from models.settings import SettingsModel, DEFAULT_NAMA_WARUNG
from models.user import UserModel
from utils.backup import (
    BackupError,
    RestoreError,
    backup_database,
    restore_database,
    validate_backup_file,
)
from utils.theme import COLORS, LAYOUT, SPACING, button_style, get_font

APP_VERSION = "1.0.0"

SAVE_BUTTON_WIDTH = 96
PASSWORD_BUTTON_WIDTH = 190
ACTION_BUTTON_WIDTH = 170
TEXT_WRAPLENGTH = 560


class SettingsPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        user: dict,
        settings_model: SettingsModel,
        user_model: UserModel,
        db_path_getter,
        on_username_changed=None,
        on_restore_complete=None,
    ):
        super().__init__(master, fg_color="transparent")

        self.user = user
        self.settings_model = settings_model
        self.user_model = user_model
        self.db_path_getter = db_path_getter
        self.on_username_changed = on_username_changed
        self.on_restore_complete = on_restore_complete

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        PageHeader(self, "Pengaturan").pack(
            fill="x",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.scroll.pack(
            fill="both",
            expand=True,
            padx=(page_padding, SPACING["lg"]),
            pady=(0, page_padding),
        )

        self._build_nama_warung_section()
        self._build_username_section()
        self._build_password_section()
        self._build_backup_section()
        self._build_info_section()

    def _safe_get_nama_warung(self) -> str:
        # Dipanggil saat konstruksi halaman (MainWindow membangun semua
        # halaman sekaligus setelah login). Kegagalan di sini tidak boleh
        # menjatuhkan main window, jadi jatuh ke nilai default.
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
    # Helper
    # ------------------------------------------------------------------
    def _make_card(self, title: str) -> SectionCard:
        card = SectionCard(self.scroll, title)
        card.pack(fill="x", pady=(0, SPACING["lg"]))
        return card

    def _build_save_row(self, card, label: str, initial: str, command):
        """Satu field dengan tombol Simpan di sampingnya + teks error di bawah."""
        row = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)

        field = FormField(row, label, initial=initial)
        field.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, SPACING["sm"]),
        )
        field.entry.bind("<Return>", lambda _event: command())

        ctk.CTkButton(
            row,
            text="Simpan",
            width=SAVE_BUTTON_WIDTH,
            command=command,
            **button_style("primary"),
        ).grid(row=0, column=1, sticky="s")

        error = ErrorText(card.body)
        error.pack(fill="x", pady=(SPACING["sm"], 0))

        return field, error

    @staticmethod
    def _body_text(parent, text: str, **pack_options):
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=TEXT_WRAPLENGTH,
        )
        label.pack(fill="x", **pack_options)
        return label

    # ------------------------------------------------------------------
    # Nama Warung
    # ------------------------------------------------------------------
    def _build_nama_warung_section(self):
        card = self._make_card("Nama Warung")

        field, self.nama_warung_error = self._build_save_row(
            card,
            "Nama Warung",
            self._safe_get_nama_warung(),
            self._handle_save_nama_warung,
        )
        self.nama_warung_entry = field.entry

    def _handle_save_nama_warung(self):
        self.nama_warung_error.clear()

        value = self.nama_warung_entry.get().strip()

        try:
            saved = self.settings_model.set_nama_warung(value)
        except Exception:
            self.nama_warung_error.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        self.nama_warung_entry.delete(0, "end")
        self.nama_warung_entry.insert(0, saved)

        show_success(self, "Nama Warung", f"Nama warung disimpan: {saved}")

    # ------------------------------------------------------------------
    # Ganti Username
    # ------------------------------------------------------------------
    def _build_username_section(self):
        card = self._make_card("Ganti Username")

        field, self.username_error = self._build_save_row(
            card,
            "Username",
            self.user.get("username", ""),
            self._handle_change_username,
        )
        self.username_entry = field.entry

    def _handle_change_username(self):
        self.username_error.clear()

        new_username = self.username_entry.get().strip()

        try:
            ok, message = self.user_model.change_username(
                self.user["id"],
                new_username,
            )
        except Exception:
            self.username_error.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not ok:
            self.username_error.show(message)
            return

        self.user["username"] = new_username

        if self.on_username_changed:
            self.on_username_changed(new_username)

        show_success(self, "Username", message)

    # ------------------------------------------------------------------
    # Ganti Password
    # ------------------------------------------------------------------
    def _build_password_section(self):
        card = self._make_card("Ganti Password")
        body = card.body

        self.old_password_field = FormField(body, "Password Lama")
        self.old_password_field.pack(fill="x")

        self.new_password_field = FormField(body, "Password Baru")
        self.new_password_field.pack(fill="x", pady=(SPACING["md"], 0))

        self.confirm_password_field = FormField(
            body,
            "Konfirmasi Password Baru",
        )
        self.confirm_password_field.pack(fill="x", pady=(SPACING["md"], 0))

        self.old_password_entry = self.old_password_field.entry
        self.new_password_entry = self.new_password_field.entry
        self.confirm_password_entry = self.confirm_password_field.entry

        for entry in (
            self.old_password_entry,
            self.new_password_entry,
            self.confirm_password_entry,
        ):
            entry.configure(show="*")

        self.confirm_password_entry.bind(
            "<Return>",
            lambda _event: self._handle_change_password(),
        )

        self.password_error = ErrorText(body)
        self.password_error.pack(fill="x", pady=(SPACING["sm"], 0))

        footer = ctk.CTkFrame(
            body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        footer.pack(fill="x", pady=(SPACING["md"], 0))

        ctk.CTkButton(
            footer,
            text="Simpan Password Baru",
            width=PASSWORD_BUTTON_WIDTH,
            command=self._handle_change_password,
            **button_style("primary"),
        ).pack(side="right")

    def _handle_change_password(self):
        self.password_error.clear()

        old = self.old_password_entry.get()
        new = self.new_password_entry.get()
        confirm = self.confirm_password_entry.get()

        if new != confirm:
            self.password_error.show(
                "Konfirmasi password baru tidak cocok."
            )
            return

        try:
            ok, message = self.user_model.change_password(
                self.user["id"],
                old,
                new,
            )
        except Exception:
            self.password_error.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not ok:
            self.password_error.show(message)
            return

        self.old_password_entry.delete(0, "end")
        self.new_password_entry.delete(0, "end")
        self.confirm_password_entry.delete(0, "end")

        show_success(self, "Password", message)

    # ------------------------------------------------------------------
    # Backup & Restore
    # ------------------------------------------------------------------
    def _build_backup_section(self):
        card = self._make_card("Backup & Restore Database")
        body = card.body

        # --- Backup (aman) -------------------------------------------
        ctk.CTkLabel(
            body,
            text="Backup",
            font=get_font("subheading"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        self._body_text(
            body,
            "Backup menyimpan salinan database dengan nama bertanggal.",
            pady=(SPACING["xs"], SPACING["md"]),
        )

        ctk.CTkButton(
            body,
            text="Backup Database",
            width=ACTION_BUTTON_WIDTH,
            command=self._handle_backup,
            **button_style("primary"),
        ).pack(anchor="w")

        # --- Pemisah -------------------------------------------------
        ctk.CTkFrame(
            body,
            height=1,
            corner_radius=0,
            fg_color=COLORS["border"],
        ).pack(fill="x", pady=SPACING["lg"])

        # --- Restore (destruktif) ------------------------------------
        ctk.CTkLabel(
            body,
            text="Restore",
            font=get_font("subheading"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        self._body_text(
            body,
            "Restore akan mengganti seluruh data saat ini dengan isi file "
            "backup yang dipilih. Tindakan ini tidak dapat dibatalkan.",
            pady=(SPACING["xs"], SPACING["md"]),
        )

        ctk.CTkButton(
            body,
            text="Restore Database",
            width=ACTION_BUTTON_WIDTH,
            command=self._handle_restore,
            **button_style("danger"),
        ).pack(anchor="w")

    def _handle_backup(self):
        try:
            backup_path = backup_database(self.db_path_getter())
        except BackupError as exc:
            show_error(
                self,
                "Backup Gagal",
                "Backup database tidak dibuat.\n\n"
                f"{exc}\n\n"
                "Backup lama tidak dihapus.",
            )
            return
        except Exception as exc:
            show_error(
                self,
                "Backup Gagal",
                "Terjadi kesalahan saat membuat backup.\n\n"
                f"Detail: {exc}\n\n"
                "Backup lama tidak dihapus.",
            )
            return

        try:
            info = inspect_database(backup_path)
            summary = (
                f"Versi schema: v{info.schema_version}\n"
                f"Pelanggan: {info.counts.get('customers', 0)}\n"
                f"Produk: {info.counts.get('products', 0)}\n"
                f"Transaksi hutang: "
                f"{info.counts.get('debt_transactions', 0)}\n"
                f"Pembayaran: {info.counts.get('payments', 0)}\n"
                f"Pembelian: {info.counts.get('purchases', 0)}\n"
                f"Penjualan: {info.counts.get('sales', 0)}"
            )
        except Exception:
            summary = "Backup sudah lolos validasi."

        show_success(
            self,
            "Backup Berhasil",
            "Database berhasil dibackup dan diverifikasi ke:\n"
            f"{backup_path}\n\n"
            f"{summary}\n\n"
            "Backup lama tidak dihapus.",
        )

    def _handle_restore(self):
        chosen_path = filedialog.askopenfilename(
            title="Pilih File Backup",
            filetypes=[
                ("Database SQLite", "*.db"),
                ("Semua file", "*.*"),
            ],
        )

        if not chosen_path:
            return  # dibatalkan

        try:
            info = validate_backup_file(chosen_path)
        except DatabaseValidationError as exc:
            show_error(
                self,
                "Backup Tidak Valid",
                "File backup tidak bisa dipakai. Database saat ini "
                "tidak diubah.\n\n"
                f"{exc}",
            )
            return
        except Exception as exc:
            show_error(
                self,
                "Backup Tidak Valid",
                "File backup tidak bisa diperiksa. Database saat ini "
                "tidak diubah.\n\n"
                f"Detail: {exc}",
            )
            return

        summary_lines = [
            f"Versi schema: v{info.schema_version}",
            f"Pelanggan: {info.counts.get('customers', 0)}",
            f"Produk: {info.counts.get('products', 0)}",
            "Transaksi hutang: "
            f"{info.counts.get('debt_transactions', 0)}",
            f"Pembayaran: {info.counts.get('payments', 0)}",
            f"Pembelian: {info.counts.get('purchases', 0)}",
            f"Penjualan: {info.counts.get('sales', 0)}",
        ]

        message = (
            "Restore akan mengganti seluruh data saat ini dengan isi "
            "file backup yang dipilih.\n\n"
            "Ringkasan backup:\n"
            + "\n".join(summary_lines)
        )

        if info.warnings:
            message += "\n\nCatatan:\n" + "\n".join(
                f"- {warning}" for warning in info.warnings[:5]
            )

        message += (
            "\n\nDatabase saat ini akan diamankan otomatis terlebih "
            "dahulu. Lanjutkan restore?"
        )

        ConfirmDialog(
            self,
            title="Konfirmasi Restore",
            message=message,
            on_confirm=lambda: self._do_restore(chosen_path),
            confirm_text="Restore",
        )

    def _do_restore(self, chosen_path: str):
        try:
            safety_path = restore_database(
                chosen_path,
                self.db_path_getter(),
            )
        except RestoreError as exc:
            message = (
                "Restore gagal atau dibatalkan. Database produksi "
                "dipertahankan/dikembalikan.\n\n"
                f"{exc}"
            )
            if exc.safety_path and exc.safety_path not in str(exc):
                message += (
                    "\n\nSafety backup:\n"
                    f"{exc.safety_path}"
                )
            show_error(self, "Restore Gagal", message)
            return
        except Exception as exc:
            show_error(
                self,
                "Restore Gagal",
                "Terjadi kesalahan saat melakukan restore.\n\n"
                f"Detail: {exc}",
            )
            return

        try:
            info = inspect_database(self.db_path_getter())
            summary = (
                f"Versi schema: v{info.schema_version}\n"
                f"Pelanggan: {info.counts.get('customers', 0)}\n"
                f"Produk: {info.counts.get('products', 0)}\n"
                f"Transaksi hutang: "
                f"{info.counts.get('debt_transactions', 0)}\n"
                f"Pembayaran: {info.counts.get('payments', 0)}\n"
                f"Pembelian: {info.counts.get('purchases', 0)}\n"
                f"Penjualan: {info.counts.get('sales', 0)}"
            )
        except Exception:
            summary = "Database sudah diverifikasi setelah restore."

        message = (
            "Database berhasil dipulihkan dan diverifikasi.\n\n"
            f"{summary}"
        )

        if safety_path:
            message += (
                "\n\nSafety backup data sebelumnya:\n"
                f"{safety_path}"
            )

        message += (
            "\n\nAnda akan diarahkan ke halaman login agar semua data "
            "dimuat ulang."
        )

        show_success(
            self,
            "Restore Berhasil",
            message,
            on_close=self.on_restore_complete,
        )

    # ------------------------------------------------------------------
    # Informasi Aplikasi
    # ------------------------------------------------------------------
    def _build_info_section(self):
        card = self._make_card("Informasi Aplikasi")

        ctk.CTkLabel(
            card.body,
            text=f"Warung Hutang v{APP_VERSION}",
            font=get_font("body"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        self._body_text(
            card.body,
            "Aplikasi pencatatan hutang warung - 100% offline, "
            "database lokal (SQLite).",
            pady=(SPACING["xs"], 0),
        )
        self._body_text(
            card.body,
            "Dibangun dengan Python, CustomTkinter, dan SQLite.",
            pady=(SPACING["xs"], 0),
        )