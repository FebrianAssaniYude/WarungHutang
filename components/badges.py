import customtkinter as ctk

from utils.theme import COLORS, RADIUS, SPACING, get_font

# variant -> (warna latar, warna teks)
_STYLES = {
    "success": (COLORS["success_light"], COLORS["success"]),
    "warning": (COLORS["warning_light"], COLORS["warning"]),
    "danger": (COLORS["danger_light"], COLORS["danger"]),
    "info": (COLORS["info_light"], COLORS["info"]),
    "neutral": (COLORS["neutral_light"], COLORS["text_secondary"]),
}

BADGE_VARIANTS = tuple(_STYLES.keys())

# Jenis transaksi (kunci huruf kecil) -> varian badge.
# Satu-satunya sumber warna jenis transaksi di seluruh aplikasi.
TRANSACTION_VARIANTS = {
    "hutang": "danger",
    "pembayaran": "success",
    "penjualan": "success",
    "pembelian": "neutral",
}

# Status pelanggan (kunci huruf kecil) -> varian badge.
CUSTOMER_STATUS_VARIANTS = {
    "lunas": "success",
    "belum lunas": "warning",
    "aktif": "success",
    "nonaktif": "danger",
}

# Jenis transaksi (kunci huruf kecil) -> (tanda, warna nominal).
# Warna None berarti warna teks biasa.
# Satu-satunya sumber tanda dan warna nominal di seluruh aplikasi.
AMOUNT_STYLES = {
    "hutang": ("+", COLORS["danger"]),
    "pembayaran": ("-", COLORS["success"]),
    "penjualan": ("+", COLORS["success"]),
    "pembelian": ("-", None),
}


class Badge(ctk.CTkFrame):
    """
    Badge status berbentuk pil. Teks otomatis menjadi huruf besar.

    Contoh:
        Badge(parent, "Lunas", "success")
        Badge(parent, "Belum Lunas", "warning")
        Badge(parent, "Nonaktif", "danger")
        Badge(parent, "-", "neutral")
    """

    def __init__(self, master, text: str, variant: str = "neutral"):
        background, foreground = _STYLES.get(variant, _STYLES["neutral"])

        super().__init__(
            master,
            corner_radius=RADIUS["badge"],
            fg_color=background,
        )

        ctk.CTkLabel(
            self,
            text=str(text).upper(),
            font=get_font("badge"),
            text_color=foreground,
        ).pack(
            padx=SPACING["md"],
            pady=SPACING["xs"] // 2,
        )


def _key(value) -> str:
    return str(value or "").strip().lower()


def transaction_variant(transaction_type) -> str:
    """Varian badge untuk jenis transaksi (Hutang, Pembayaran, dst.)."""
    return TRANSACTION_VARIANTS.get(_key(transaction_type), "neutral")


def transaction_badge(master, transaction_type) -> Badge:
    """Badge jenis transaksi dengan warna standar."""
    return Badge(
        master,
        str(transaction_type or "-"),
        transaction_variant(transaction_type),
    )


def customer_status_variant(status) -> str:
    """Varian badge untuk status pelanggan. Status tak dikenal tampil kuning."""
    return CUSTOMER_STATUS_VARIANTS.get(_key(status), "warning")


def customer_status_badge(master, status) -> Badge:
    """Badge status pelanggan dengan warna standar."""
    return Badge(
        master,
        str(status or "-"),
        customer_status_variant(status),
    )


def amount_style(transaction_type):
    """Tanda dan warna nominal untuk jenis transaksi: (tanda, warna_atau_None)."""
    return AMOUNT_STYLES.get(_key(transaction_type), ("", None))