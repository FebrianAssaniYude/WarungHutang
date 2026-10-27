import customtkinter as ctk

from utils.theme import COLORS, SPACING, get_font

# Lebar teks penjelas untuk empty dan error state (sama untuk keduanya).
STATE_WRAPLENGTH = 480


class EmptyState(ctk.CTkFrame):
    """Tampilan standar saat tabel/daftar kosong."""

    def __init__(self, master, title: str = "Belum ada data", description: str = ""):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(
            self,
            text=title,
            font=get_font("subheading"),
            text_color=COLORS["text"],
        ).pack(pady=(SPACING["sm"], 0))

        if description:
            ctk.CTkLabel(
                self,
                text=description,
                font=get_font("small"),
                text_color=COLORS["text_secondary"],
                wraplength=STATE_WRAPLENGTH,
                justify="center",
            ).pack(pady=(SPACING["xs"], SPACING["sm"]))


class ErrorState(ctk.CTkFrame):
    """Tampilan standar saat data gagal dimuat."""

    def __init__(self, master, title: str = "Terjadi kesalahan", message: str = ""):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(
            self,
            text=title,
            font=get_font("subheading"),
            text_color=COLORS["danger"],
        ).pack(pady=(SPACING["sm"], 0))

        if message:
            ctk.CTkLabel(
                self,
                text=message,
                font=get_font("small"),
                text_color=COLORS["text_secondary"],
                wraplength=STATE_WRAPLENGTH,
                justify="center",
            ).pack(pady=(SPACING["xs"], SPACING["sm"]))