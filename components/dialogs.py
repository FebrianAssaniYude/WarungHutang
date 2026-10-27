import customtkinter as ctk

from utils.theme import (
    BUTTON_WIDTH,
    COLORS,
    DIALOG_PADDING,
    DIALOG_WIDTH,
    SPACING,
    button_style,
    get_font,
)


class BaseDialog(ctk.CTkToplevel):
    """
    Dialog dasar semua popup aplikasi.

    Susunan: judul (atas) / body (isi) / garis / footer tombol (bawah, rata kanan).
    Cara pakai di subclass:

        super().__init__(master, "Tambah Pelanggan", DIALOG_WIDTH["form"])
        ... isi widget ke self.body ...
        self.set_buttons("Simpan", self._submit)   # [Batal] [Simpan]
        self.finish()                              # wajib, di akhir __init__

    Dialog tanpa aksi utama (hanya menutup):
        self.set_close_button("Tutup")

    Enter menjalankan tombol utama, kecuali tombol berwarna merah (danger).
    Esc menutup dialog.

    height=None  -> tinggi mengikuti isi
    height=angka -> tinggi tetap (untuk dialog berisi tabel/scroll)
    """

    def __init__(
        self,
        master,
        title: str,
        width: int,
        height: int = None,
        heading: str = None,
    ):
        super().__init__(master, fg_color=COLORS["surface"])

        self.dialog_width = width
        self.dialog_height = height
        self._primary_button = None

        self.title(title)
        self.resizable(False, False)

        try:
            self.transient(master.winfo_toplevel())
        except Exception:
            pass

        self.bind("<Escape>", lambda _event: self.destroy())

        self.heading_label = ctk.CTkLabel(
            self,
            text=heading if heading is not None else title,
            font=get_font("heading"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.heading_label.pack(
            fill="x",
            padx=DIALOG_PADDING,
            pady=(DIALOG_PADDING, SPACING["md"]),
        )

        # Footer dan garis dipasang sebelum body agar selalu terlihat di bawah.
        self.footer = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.footer.pack(
            side="bottom",
            fill="x",
            padx=DIALOG_PADDING,
            pady=(SPACING["md"], DIALOG_PADDING),
        )

        self.divider = ctk.CTkFrame(
            self,
            height=1,
            corner_radius=0,
            fg_color=COLORS["border"],
        )
        self.divider.pack(side="bottom", fill="x")

        self.body = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.body.pack(
            fill="both",
            expand=True,
            padx=DIALOG_PADDING,
            pady=(0, SPACING["md"]),
        )

    @property
    def text_width(self) -> int:
        """Lebar area isi dialog; dipakai sebagai wraplength teks."""
        return self.dialog_width - (DIALOG_PADDING * 2)

    # ------------------------------------------------------------------
    def set_buttons(
        self,
        primary_text: str,
        primary_command,
        secondary_text: str = "Batal",
        secondary_command=None,
        primary_variant: str = "primary",
        primary_width: int = BUTTON_WIDTH["dialog"],
    ):
        """Footer standar rata kanan: [secondary] [primary]."""
        primary = ctk.CTkButton(
            self.footer,
            text=primary_text,
            command=primary_command,
            width=primary_width,
            **button_style(primary_variant),
        )
        primary.pack(side="right")

        self._primary_button = primary

        # Aksi destruktif tidak boleh terpicu tanpa sengaja oleh Enter.
        if primary_variant != "danger":
            self.bind("<Return>", lambda _event: primary.invoke())

        if secondary_text:
            ctk.CTkButton(
                self.footer,
                text=secondary_text,
                command=secondary_command or self.destroy,
                width=BUTTON_WIDTH["dialog"],
                **button_style("secondary"),
            ).pack(side="right", padx=(0, SPACING["sm"]))

        return primary

    def set_close_button(self, text: str = "Tutup", command=None):
        """Footer untuk dialog yang hanya punya satu tombol tutup."""
        button = ctk.CTkButton(
            self.footer,
            text=text,
            command=command or self.destroy,
            width=BUTTON_WIDTH["dialog"],
            **button_style("secondary"),
        )
        button.pack(side="right")

        return button

    def finish(self):
        """Hitung ukuran, tengahkan terhadap jendela induk, lalu aktifkan dialog."""
        self.update_idletasks()

        width = self.dialog_width
        height = self.dialog_height or self.winfo_reqheight()

        try:
            parent = self.master.winfo_toplevel()
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        except Exception:
            x, y = 200, 100

        x = max(x, 0)
        y = max(y, 0)

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.after(30, self._take_focus)

    def _take_focus(self):
        try:
            self._previous_grab = self.grab_current()
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def destroy(self):
        # Kembalikan modal ke dialog sebelumnya (mis. pesan peringatan yang
        # muncul di atas dialog pembayaran), agar dialog induk tetap modal.
        previous = getattr(self, "_previous_grab", None)
        super().destroy()

        if previous is not None:
            try:
                previous.grab_set()
            except Exception:
                pass


class ConfirmDialog(BaseDialog):
    """Dialog konfirmasi: [Batal] [aksi]. Aksi berwarna merah bila danger=True."""

    def __init__(
        self,
        master,
        title: str,
        message: str,
        on_confirm,
        confirm_text: str = "Ya",
        danger: bool = True,
    ):
        super().__init__(master, title, DIALOG_WIDTH["confirm"])

        self.on_confirm = on_confirm

        ctk.CTkLabel(
            self.body,
            text=message,
            font=get_font("body"),
            text_color=COLORS["text"],
            wraplength=self.text_width,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        self.set_buttons(
            confirm_text,
            self._confirm,
            "Batal",
            primary_variant="danger" if danger else "primary",
            primary_width=BUTTON_WIDTH["confirm"],
        )
        self.finish()

    def _confirm(self):
        self.destroy()
        self.on_confirm()


_KIND_COLORS = {
    "info": COLORS["info"],
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "error": COLORS["danger"],
}


class MessageDialog(BaseDialog):
    """Dialog pesan satu tombol (pengganti messagebox): info, success, warning, error."""

    def __init__(self, master, title: str, message: str, kind: str = "info"):
        super().__init__(master, title, DIALOG_WIDTH["confirm"])

        self.heading_label.configure(
            text_color=_KIND_COLORS.get(kind, COLORS["text"])
        )

        ctk.CTkLabel(
            self.body,
            text=message,
            font=get_font("body"),
            text_color=COLORS["text"],
            wraplength=self.text_width,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        self.set_buttons("OK", self.destroy, secondary_text=None)
        self.finish()


def show_info(master, title: str, message: str):
    MessageDialog(master, title, message, "info")


def show_success(master, title: str, message: str):
    MessageDialog(master, title, message, "success")


def show_warning(master, title: str, message: str):
    MessageDialog(master, title, message, "warning")


def show_error(master, title: str, message: str):
    MessageDialog(master, title, message, "error")