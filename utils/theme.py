"""
Design system terpusat untuk aplikasi Warung Hutang.

Semua warna, font, ukuran, dan style komponen utama didefinisikan di sini.
Halaman TIDAK boleh menulis warna/ukuran sendiri; ambil dari modul ini
agar seluruh menu terlihat berasal dari satu aplikasi yang sama.
"""

import customtkinter as ctk


# ============================================================
# APP
# ============================================================

APP_NAME_FALLBACK = "Warung Hutang"


# ============================================================
# COLORS  (light, dark)
# ============================================================

COLORS = {
    # Background
    "background": ("#F5F7FA", "#111827"),
    "surface": ("#FFFFFF", "#1F2937"),
    "surface_hover": ("#F1F5F9", "#273449"),

    # Sidebar
    "sidebar": ("#FFFFFF", "#111827"),
    "sidebar_border": ("#E5E7EB", "#374151"),

    # Primary
    "primary": ("#2563EB", "#3B82F6"),
    "primary_hover": ("#1D4ED8", "#2563EB"),
    "primary_light": ("#EFF6FF", "#1E3A8A"),

    # Secondary
    "secondary": ("#64748B", "#94A3B8"),
    "secondary_hover": ("#475569", "#CBD5E1"),

    # Text
    "text": ("#111827", "#F9FAFB"),
    "text_secondary": ("#64748B", "#94A3B8"),
    "text_muted": ("#94A3B8", "#64748B"),
    "text_on_primary": ("#FFFFFF", "#FFFFFF"),

    # Border
    "border": ("#E2E8F0", "#374151"),

    # Status
    "success": ("#16A34A", "#22C55E"),
    "success_light": ("#F0FDF4", "#14532D"),

    "warning": ("#D97706", "#F59E0B"),
    "warning_light": ("#FFFBEB", "#78350F"),

    "danger": ("#DC2626", "#EF4444"),
    "danger_hover": ("#B91C1C", "#DC2626"),
    "danger_light": ("#FEF2F2", "#7F1D1D"),

    "info": ("#0284C7", "#38BDF8"),
    "info_light": ("#F0F9FF", "#0C4A6E"),

    # Netral (badge) - cukup gelap agar tetap terlihat di baris zebra.
    "neutral_light": ("#E2E8F0", "#374151"),

    # Table
    "table_header": ("#F1F5F9", "#273449"),
    "table_row": ("#FFFFFF", "#1F2937"),
    "table_row_alt": ("#F8FAFC", "#243041"),
    "table_hover": ("#EFF6FF", "#263B5C"),
    "table_selected": ("#DBEAFE", "#1E3A8A"),
}


# ============================================================
# RADIUS
# ============================================================

RADIUS = {
    "small": 6,
    "medium": 8,
    "large": 12,
    "card": 12,
    "button": 8,
    "input": 8,
    "badge": 11,
}


# ============================================================
# SPACING
# ============================================================

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}


# ============================================================
# LAYOUT
# ============================================================

LAYOUT = {
    "sidebar_width": 220,
    "sidebar_padding": 12,          # jarak kiri/kanan tombol menu
    "sidebar_header_padding": 20,   # jarak kiri nama warung / user
    "sidebar_item_height": 40,
    "sidebar_item_gap": 2,          # jarak atas/bawah tiap tombol menu
    "sidebar_title_pady": (24, 2),  # nama warung di sidebar
    "sidebar_user_pady": (0, 20),   # label "Masuk sebagai"
    "page_padding": 24,             # padding kiri/atas/bawah area halaman
    "page_padding_right": 16,       # padding kanan bila ada scrollbar
    "header_pady": (24, 16),        # jarak atas/bawah header halaman
    "card_gap": 12,                 # jarak antar kartu dalam satu baris
    "section_gap": 16,              # jarak vertikal antar bagian halaman
}


# ============================================================
# COMPONENT SIZES
# ============================================================

BUTTON_HEIGHT = {
    "normal": 36,
    "small": 28,   # tombol aksi di dalam tabel
}

BUTTON_WIDTH = {
    "header": 170,   # tombol aksi di header halaman
    "dialog": 96,    # tombol footer dialog
    "confirm": 110,  # tombol konfirmasi di dialog
    "filter": 100,   # tombol Terapkan / Tampilkan
}

# Lebar tombol aksi di dalam tabel (Detail, Edit, Nonaktifkan, Hapus).
TABLE_ACTION_WIDTH = {
    "detail": 64,
    "edit": 56,
    "danger": 96,
    "delete": 64,
}

INPUT_HEIGHT = 36

TABLE = {
    "header_height": 40,
    "row_height": 40,
    "row_height_image": 56,       # baris yang memuat gambar
    "action_button_height": 28,
    "cell_padx": 12,
    "scrollbar_gutter": 22,       # jarak kanan header agar sejajar dengan baris
    "first_batch": 20,            # baris yang dibuat langsung
    "batch": 15,                  # baris per tahap sisanya
}

SIZES = {
    "thumb": 42,          # gambar produk di tabel
    "thumb_preview": 54,  # pratinjau gambar di dialog
}

DIALOG_WIDTH = {
    "confirm": 420,
    "form": 480,
    "picker": 600,
    "detail": 720,
}

DIALOG_HEIGHT = {
    "detail": 620,
    "picker": 540,
}

DIALOG_PADDING = 24


# ============================================================
# FONT
# ============================================================

FONT_FAMILY = "Segoe UI"

FONT = {
    "title": {"size": 24, "weight": "bold"},
    "heading": {"size": 18, "weight": "bold"},
    "subheading": {"size": 14, "weight": "bold"},
    "body": {"size": 13, "weight": "normal"},
    "small": {"size": 11, "weight": "normal"},
    "button": {"size": 13, "weight": "bold"},
    "button_small": {"size": 12, "weight": "bold"},

    # Token khusus komponen (jangan meminjam token tombol)
    "label": {"size": 12, "weight": "bold"},
    "table_header": {"size": 12, "weight": "bold"},
    "table_cell": {"size": 13, "weight": "normal"},
    "table_cell_bold": {"size": 13, "weight": "bold"},
    "badge": {"size": 11, "weight": "bold"},
    "stat_value": {"size": 20, "weight": "bold"},
    "summary_value": {"size": 18, "weight": "bold"},
}


# ============================================================
# GLOBAL THEME
# ============================================================

def apply_theme():
    """
    Mengaktifkan tampilan global aplikasi.
    Dipanggil sekali saat aplikasi dimulai.
    """
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def get_color(name: str):
    """
    Mengambil warna (light, dark) berdasarkan nama.
    Nama yang salah menimbulkan KeyError agar salah ketik cepat ketahuan.
    """
    return COLORS[name]


def resolve_color(color):
    """
    Mengubah warna (light, dark) menjadi satu string hex sesuai mode
    tampilan saat ini. Dipakai untuk widget non-CustomTkinter (ttk).
    """
    if isinstance(color, (tuple, list)):
        index = 0 if ctk.get_appearance_mode() == "Light" else 1
        return color[index]

    return color


def get_font(name: str):
    """
    Mengambil CTkFont berdasarkan nama.
    Harus dipanggil setelah window utama (CTk) dibuat.
    """
    config = FONT.get(name, FONT["body"])

    return ctk.CTkFont(
        family=FONT_FAMILY,
        size=config["size"],
        weight=config["weight"],
    )


# ============================================================
# BUTTON STYLE
# ============================================================

BUTTON_VARIANTS = ("primary", "secondary", "danger", "ghost", "link")


def button_style(variant: str = "primary", size: str = "normal") -> dict:
    """
    Mengembalikan kwargs standar untuk ctk.CTkButton.

    Pemakaian:
        ctk.CTkButton(parent, text="Simpan", command=..., **button_style("primary"))

    variant : primary | secondary | danger | ghost | link
    size    : normal (36) | small (28, untuk tabel)
    """
    if variant not in BUTTON_VARIANTS:
        variant = "primary"

    small = size == "small"

    style = {
        "height": BUTTON_HEIGHT["small" if small else "normal"],
        "corner_radius": RADIUS["button"],
        "font": get_font("button_small" if small else "button"),
        "border_width": 0,
    }

    if variant == "primary":
        style.update(
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_on_primary"],
        )
    elif variant == "secondary":
        style.update(
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
        )
    elif variant == "danger":
        style.update(
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            text_color=COLORS["text_on_primary"],
        )
    elif variant == "link":
        style.update(
            fg_color="transparent",
            hover_color=COLORS["primary_light"],
            text_color=COLORS["primary"],
        )
    else:  # ghost
        style.update(
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
        )

    return style


def action_button_style(kind: str = "detail") -> dict:
    """
    Style tombol aksi di dalam tabel, lengkap dengan lebar standar.

    kind : detail | edit (secondary)  |  danger | delete (merah)
    """
    variant = "danger" if kind in ("danger", "delete") else "secondary"

    style = button_style(variant, "small")
    style["width"] = TABLE_ACTION_WIDTH.get(kind, TABLE_ACTION_WIDTH["detail"])

    return style


# ============================================================
# SIDEBAR STYLE
# ============================================================

def nav_button_style(active: bool) -> dict:
    """Style tombol menu sidebar (aktif: latar biru muda, teks tebal)."""
    if active:
        return {
            "fg_color": COLORS["primary_light"],
            "hover_color": COLORS["primary_light"],
            "text_color": COLORS["primary"],
            "font": get_font("button"),
        }

    return {
        "fg_color": "transparent",
        "hover_color": COLORS["surface_hover"],
        "text_color": COLORS["text"],
        "font": get_font("body"),
    }


def logout_button_style() -> dict:
    """Style tombol keluar di bagian bawah sidebar."""
    return {
        "fg_color": "transparent",
        "hover_color": COLORS["danger_light"],
        "text_color": COLORS["danger"],
        "font": get_font("body"),
    }


# ============================================================
# CHECKBOX STYLE
# ============================================================

def checkbox_style() -> dict:
    """Kwargs standar untuk ctk.CTkCheckBox."""
    return {
        "font": get_font("body"),
        "text_color": COLORS["text"],
        "fg_color": COLORS["primary"],
        "hover_color": COLORS["primary_hover"],
        "border_color": COLORS["border"],
        "corner_radius": RADIUS["small"],
    }