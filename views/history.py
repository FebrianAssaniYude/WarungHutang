import re
import time

import customtkinter as ctk

from components.cards import SectionCard
from components.customer_picker import CustomerPickerDialog, CustomerSelector
from components.detail_dialogs import (
    DebtDetailDialog,
    PaymentDetailDialog,
    PurchaseDetailDialog,
    SaleDetailDialog,
)
from components.dialogs import show_error, show_warning
from components.forms import FormField, option_menu_style
from components.page_header import PageHeader
from components.tables import DataTable
from models.customer import CustomerModel
from models.debt import DebtModel
from models.history import HistoryModel
from models.payment import PaymentModel
from models.purchase import PurchaseModel
from models.sale import SaleModel
from utils.formatter import format_date_indonesia, format_rupiah
from utils.theme import COLORS, LAYOUT, SPACING, button_style, get_font

TYPE_OPTIONS = [
    "Semua",
    "Hutang",
    "Pembayaran",
    "Pembelian",
    "Penjualan",
]

ALL_CUSTOMERS = "Semua Pelanggan"

# Treeview ringan, jadi satu halaman bisa memuat lebih banyak baris.
PAGE_SIZE = 500

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Tidak ada kolom Aksi: baris dibuka dengan klik dua kali atau Enter.
HISTORY_COLUMNS = [
    {"title": "Tanggal", "weight": 2, "align": "left"},
    {"title": "Pelanggan", "weight": 4, "align": "left"},
    {"title": "Jenis", "weight": 2, "align": "left"},
    {"title": "Nominal", "weight": 3, "align": "right"},
]

# Tanda nominal per jenis transaksi.
SIGN_MAP = {
    "Hutang": "+",
    "Pembayaran": "-",
    "Pembelian": "-",
    "Penjualan": "+",
}

# Warna titik di kolom kiri tabel per jenis transaksi.
# Sesuaikan dengan warna badge jenis transaksi di components/badges.py.
TYPE_VARIANTS = {
    "Hutang": "warning",
    "Pembayaran": "success",
    "Pembelian": "neutral",
    "Penjualan": "info",
}

ACTIVATE_HINT = "Klik dua kali baris untuk melihat detail."


class HistoryPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        history_model: HistoryModel,
        customer_model: CustomerModel,
    ):
        super().__init__(master, fg_color="transparent")

        self.history_model = history_model
        self.customer_model = customer_model
        self.debt_model = DebtModel(customer_model.db)
        self.payment_model = PaymentModel(customer_model.db)
        self.purchase_model = PurchaseModel(customer_model.db)
        self.sale_model = SaleModel(customer_model.db)
        self.selected_customer = None
        self._entries = []
        self._shown = PAGE_SIZE

        # jenis -> (pemuat detail, kelas dialog, nama, pesan tidak ditemukan)
        self._detail_sources = {
            "Hutang": (
                self.debt_model.get_transaction_detail,
                DebtDetailDialog,
                "hutang",
                "Transaksi hutang tidak ditemukan.",
            ),
            "Pembayaran": (
                self.payment_model.get_payment_detail,
                PaymentDetailDialog,
                "pembayaran",
                "Data pembayaran tidak ditemukan.",
            ),
            "Pembelian": (
                self.purchase_model.get_transaction_detail,
                PurchaseDetailDialog,
                "pembelian",
                "Transaksi pembelian tidak ditemukan.",
            ),
            "Penjualan": (
                self.sale_model.get_transaction_detail,
                SaleDetailDialog,
                "penjualan",
                "Transaksi penjualan tidak ditemukan.",
            ),
        }

        self._build_ui()

        # Tidak memanggil refresh() di sini: MainWindow.show_page() sudah
        # memanggil refresh() setiap halaman dibuka, jadi memuat seluruh
        # riwayat saat aplikasi start hanya memperlambat startup.

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        PageHeader(self, "Riwayat").pack(
            fill="x",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        card = SectionCard(self)
        card.pack(
            fill="both",
            expand=True,
            padx=page_padding,
            pady=(0, page_padding),
        )

        self._build_filters(card.body)

        # Footer dipasang sebelum tabel agar selalu terlihat di bawah.
        self._build_footer(card.body)

        self.table = DataTable(
            card.body,
            HISTORY_COLUMNS,
            empty_title="Tidak ada riwayat",
            empty_text="Tidak ada riwayat yang cocok dengan filter ini.",
            on_activate=self._on_activate,
            show_dot=True,
        )
        self.table.pack(fill="both", expand=True)

    def _build_footer(self, parent):
        self.footer = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.footer.pack(side="bottom", fill="x", pady=(SPACING["md"], 0))

        self.count_label = ctk.CTkLabel(
            self.footer,
            text="",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.count_label.pack(side="left")

        self.more_button = ctk.CTkButton(
            self.footer,
            text="Tampilkan Lebih Banyak",
            width=180,
            command=self._show_more,
            **button_style("secondary", "small"),
        )

    def _update_footer(self):
        total = len(self._entries)
        shown = min(self._shown, total)

        self.count_label.configure(
            text=(
                f"Menampilkan {shown} dari {total} transaksi"
                f"  •  {ACTIVATE_HINT}"
                if total
                else ""
            )
        )

        if total > shown:
            self.more_button.pack(side="right")
        else:
            self.more_button.pack_forget()

    def _render(self):
        started = time.perf_counter()

        visible = self._entries[: self._shown]

        self.table.set_rows(
            [self._row_values(entry) for entry in visible],
            variants=[
                TYPE_VARIANTS.get(entry["type"], "neutral")
                for entry in visible
            ],
        )
        self._update_footer()

        print(
            f"[riwayat] render={time.perf_counter() - started:.3f}s "
            f"baris={len(visible)}"
        )

    def _show_more(self):
        self._shown += PAGE_SIZE
        self._render()

    @staticmethod
    def _labeled_cell(parent, label: str):
        cell = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )

        ctk.CTkLabel(
            cell,
            text=label,
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        return cell

    def _build_filters(self, parent):
        bar = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )
        bar.pack(fill="x", pady=(0, SPACING["md"]))
        bar.grid_columnconfigure(1, weight=1)

        gap = SPACING["md"]

        # Jenis
        type_cell = self._labeled_cell(bar, "Jenis")
        type_cell.grid(row=0, column=0, sticky="sw", padx=(0, gap))

        self.type_var = ctk.StringVar(value="Semua")

        ctk.CTkOptionMenu(
            type_cell,
            values=TYPE_OPTIONS,
            variable=self.type_var,
            width=140,
            command=lambda _value: self.refresh(),
            **option_menu_style(),
        ).pack(fill="x", pady=(SPACING["xs"], 0))

        # Pelanggan
        customer_cell = self._labeled_cell(bar, "Pelanggan")
        customer_cell.grid(row=0, column=1, sticky="sew", padx=(0, gap))

        customer_row = ctk.CTkFrame(
            customer_cell,
            fg_color="transparent",
            width=0,
            height=0,
        )
        customer_row.pack(fill="x", pady=(SPACING["xs"], 0))

        self.customer_button = CustomerSelector(
            customer_row,
            command=self._open_customer_picker,
            placeholder=ALL_CUSTOMERS,
        )
        self.customer_button.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            customer_row,
            text="Reset",
            width=72,
            command=self._reset_customer_filter,
            **button_style("secondary"),
        ).pack(side="left", padx=(SPACING["sm"], 0))

        # Tanggal
        self.date_from_field = FormField(bar, "Dari", "YYYY-MM-DD")
        self.date_from_field.grid(
            row=0, column=2, sticky="sew", padx=(0, gap)
        )
        self.date_from_entry = self.date_from_field.entry
        self.date_from_entry.bind("<Return>", lambda _e: self.refresh())

        self.date_to_field = FormField(bar, "Sampai", "YYYY-MM-DD")
        self.date_to_field.grid(
            row=0, column=3, sticky="sew", padx=(0, gap)
        )
        self.date_to_entry = self.date_to_field.entry
        self.date_to_entry.bind("<Return>", lambda _e: self.refresh())

        ctk.CTkButton(
            bar,
            text="Terapkan",
            width=100,
            command=self.refresh,
            **button_style("primary"),
        ).grid(row=0, column=4, sticky="s")

    # ------------------------------------------------------------------
    # Filter pelanggan
    # ------------------------------------------------------------------
    def _open_customer_picker(self):
        CustomerPickerDialog(
            self,
            self.customer_model,
            on_select=self._handle_customer_selected,
        )

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self.customer_button.set_customer(customer)
        self.refresh()

    def _reset_customer_filter(self):
        self.selected_customer = None
        self.customer_button.set_customer(None)
        self.refresh()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self):
        type_filter = self.type_var.get().strip().lower()

        customer_id = (
            self.selected_customer["id"]
            if self.selected_customer
            else None
        )

        date_from = self.date_from_entry.get().strip() or None
        date_to = self.date_to_entry.get().strip() or None

        for label, value in (
            ("Dari", date_from),
            ("Sampai", date_to),
        ):
            if value and not _DATE_PATTERN.match(value):
                self._entries = []
                self._update_footer()
                self.table.set_error(
                    "Format tanggal tidak valid",
                    f'Format tanggal "{label}" tidak valid. '
                    "Gunakan format YYYY-MM-DD, contoh: 2026-09-11.",
                )
                return

        try:
            started = time.perf_counter()
            entries = self.history_model.list_history(
                type_filter=type_filter,
                customer_id=customer_id,
                date_from=date_from,
                date_to=date_to,
            )
            print(
                f"[riwayat] query={time.perf_counter() - started:.3f}s "
                f"baris={len(entries)}"
            )
        except Exception:
            self._entries = []
            self._update_footer()
            self.table.set_error(
                "Gagal memuat riwayat",
                "Terjadi kesalahan saat memuat riwayat. Coba lagi.",
            )
            return

        self._entries = list(entries)
        self._shown = PAGE_SIZE
        self._render()

    # ------------------------------------------------------------------
    # Row
    # ------------------------------------------------------------------
    @staticmethod
    def _row_values(entry: dict) -> list:
        sign = SIGN_MAP.get(entry["type"], "")
        amount_text = f"{sign} {format_rupiah(entry['amount'])}".strip()

        return [
            format_date_indonesia(entry["date"]),
            entry.get("customer_name") or "-",
            entry["type"],
            amount_text,
        ]

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------
    def _on_activate(self, index: int):
        if 0 <= index < len(self._entries):
            self._open_detail(self._entries[index])

    def _open_detail(self, entry: dict):
        source = self._detail_sources.get(entry["type"])

        if not source:
            return

        loader, dialog_class, name, not_found_text = source

        try:
            detail = loader(entry["transaction_id"])
        except Exception:
            show_error(
                self,
                "Terjadi Kesalahan",
                f"Gagal memuat detail {name}. Coba lagi.",
            )
            return

        if not detail:
            show_warning(self, "Data Tidak Ditemukan", not_found_text)
            return

        dialog_class(self, detail)