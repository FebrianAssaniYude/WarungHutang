import customtkinter as ctk

from utils.theme import COLORS, LAYOUT, RADIUS, SPACING, get_font


def _card_kwargs() -> dict:
    return {
        "corner_radius": RADIUS["card"],
        "fg_color": COLORS["surface"],
        "border_width": 1,
        "border_color": COLORS["border"],
    }


class Card(ctk.CTkFrame):
    """Kartu kosong standar (latar surface, border 1px, radius 12)."""

    def __init__(self, master):
        super().__init__(master, **_card_kwargs())


class StatCard(ctk.CTkFrame):
    """
    Card ringkasan: judul kecil + nilai + subjudul opsional.

        card = StatCard(parent, "Sisa Hutang")
        card.set_value("Rp 1.000.000")
        card.set_value("3", color=COLORS["warning"])

        StatCard(parent, "Saldo Saat Ini", subtitle="Seluruh pelanggan")
    """

    def __init__(self, master, title: str, subtitle: str = ""):
        super().__init__(master, **_card_kwargs())

        ctk.CTkLabel(
            self,
            text=title,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", padx=SPACING["lg"], pady=(SPACING["lg"], SPACING["xs"]))

        self.value_label = ctk.CTkLabel(
            self,
            text="-",
            font=get_font("stat_value"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.value_label.pack(
            anchor="w",
            padx=SPACING["lg"],
            pady=(0, SPACING["xs"] if subtitle else SPACING["lg"]),
        )

        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=get_font("small"),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(
                anchor="w",
                padx=SPACING["lg"],
                pady=(0, SPACING["lg"]),
            )

    def set_value(self, text: str, color=None):
        self.value_label.configure(
            text=text,
            text_color=color or COLORS["text"],
        )


class StatRow(ctk.CTkFrame):
    """
    Satu baris StatCard dengan lebar sama dan jarak standar.

        row = StatRow(parent, ["Total", "Masih Berhutang", "Lunas"])
        row.pack(fill="x", padx=..., pady=...)
        row.set(0, "12")
        row.set(1, "Rp 50.000", color=COLORS["danger"])

    Kartu tersedia di `row.cards`.
    """

    def __init__(self, master, titles: list):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        half_gap = LAYOUT["card_gap"] // 2
        self.cards = []

        for column, title in enumerate(titles):
            self.grid_columnconfigure(column, weight=1, uniform="stat")

            card = StatCard(self, title)
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else half_gap,
                    0 if column == len(titles) - 1 else half_gap,
                ),
            )
            self.cards.append(card)

    def set(self, index: int, text: str, color=None):
        self.cards[index].set_value(text, color)


class SectionCard(ctk.CTkFrame):
    """
    Card berisi satu bagian halaman, dengan judul opsional.
    Isi card ditaruh di `card.body`.
    """

    def __init__(self, master, title: str = ""):
        super().__init__(master, **_card_kwargs())

        if title:
            ctk.CTkLabel(
                self,
                text=title,
                font=get_font("heading"),
                text_color=COLORS["text"],
                anchor="w",
            ).pack(
                anchor="w",
                padx=SPACING["lg"],
                pady=(SPACING["lg"], SPACING["md"]),
            )

        self.body = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.body.pack(
            fill="both",
            expand=True,
            padx=SPACING["lg"],
            pady=(0 if title else SPACING["lg"], SPACING["lg"]),
        )


class TransactionFooter(Card):
    """
    Bar bawah halaman transaksi: total di kiri, tombol aksi di kanan.

        footer = TransactionFooter(self, "Total Pembelian")
        footer.grid(...)
        footer.set_total("Rp 10.000")
        ctk.CTkButton(footer.actions, ...).pack(side="right")

    Tombol dipasang dengan pack(side="right"); pasang tombol utama lebih dulu.
    Bagian kiri tambahan (mis. kolom catatan) bisa dipasang di `footer.left`.
    """

    def __init__(self, master, total_title: str = "Total Transaksi"):
        super().__init__(master)

        self.grid_columnconfigure(0, weight=1)

        self.left = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.left.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=SPACING["lg"],
            pady=SPACING["md"],
        )

        total_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        total_frame.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"],
        )

        ctk.CTkLabel(
            total_frame,
            text=total_title,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="e")

        self.total_label = ctk.CTkLabel(
            total_frame,
            text="Rp 0",
            font=get_font("stat_value"),
            text_color=COLORS["text"],
        )
        self.total_label.pack(anchor="e", pady=(SPACING["xs"], 0))

        self.actions = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.actions.grid(
            row=0,
            column=2,
            sticky="e",
            padx=(0, SPACING["lg"]),
            pady=SPACING["md"],
        )

    def set_total(self, text: str):
        self.total_label.configure(text=text)