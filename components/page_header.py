import customtkinter as ctk

from utils.theme import BUTTON_WIDTH, COLORS, SPACING, button_style, get_font


class PageHeader(ctk.CTkFrame):
    """
    Header standar halaman:

        Judul                              [ aksi ]
        Subjudul (opsional)

    Tombol aksi: header.add_button("Tambah Pelanggan", command, plus=True)
    Tombol memakai lebar standar; beberapa tombol tersusun dari kanan ke kiri
    (tambahkan tombol utama lebih dulu).

    Widget lain bisa ditaruh di `header.actions`.
    """

    def __init__(self, master, title: str, subtitle: str = ""):
        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=get_font("title"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="nw")

        self.subtitle_label = None

        if subtitle:
            self.subtitle_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=get_font("body"),
                text_color=COLORS["text_secondary"],
                anchor="w",
            )
            self.subtitle_label.grid(
                row=1,
                column=0,
                sticky="nw",
                pady=(SPACING["xs"], 0),
            )

        self.actions = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.actions.grid(row=0, column=1, rowspan=2, sticky="ne")

    def add_button(
        self,
        text: str,
        command,
        variant: str = "primary",
        plus: bool = False,
    ):
        """Tambah tombol aksi standar. plus=True menambahkan ikon '+' di depan teks."""
        button = ctk.CTkButton(
            self.actions,
            text=f"+  {text}" if plus else text,
            width=BUTTON_WIDTH["header"],
            command=command,
            **button_style(variant),
        )
        button.pack(side="right", padx=(SPACING["sm"], 0))

        return button