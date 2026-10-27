import os
import tempfile
from datetime import datetime

import customtkinter as ctk

from components.cards import SectionCard, StatCard
from components.dialogs import show_error, show_warning
from components.forms import ErrorText, FormField, option_menu_style
from components.page_header import PageHeader
from components.tables import DataTable
from models.report import ReportModel
from utils.formatter import BULAN_INDONESIA, format_date_indonesia, format_rupiah
from utils.printer import Printer, PrinterError
from utils.theme import COLORS, LAYOUT, SPACING, button_style, get_font

DETAIL_COLUMNS = [
    {"title": "Tanggal", "weight": 2, "align": "left"},
    {"title": "Pelanggan", "weight": 4, "align": "left"},
    {"title": "Jenis", "weight": 2, "align": "left"},
    {"title": "Nominal", "weight": 3, "align": "right"},
]

# Warna titik di kolom kiri tabel per jenis transaksi.
# Samakan dengan TYPE_VARIANTS di views/history.py dan views/dashboard.py.
TYPE_VARIANTS = {
    "Hutang": "warning",
    "Pembayaran": "success",
}

# (kunci laporan, judul kartu)
MONTH_CARDS = [
    ("total_debt_month", "Total Hutang Bulan Ini"),
    ("total_payment_month", "Total Pembayaran Bulan Ini"),
    ("count_debt_transactions", "Jumlah Transaksi Hutang"),
    ("count_payment_transactions", "Jumlah Transaksi Pembayaran"),
]

# Treeview ringan, jadi satu halaman bisa memuat lebih banyak baris.
PAGE_SIZE = 500

class BalanceBlock(ctk.CTkFrame):
    """Saldo saat ini, ringkas, untuk diletakkan di kartu filter."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        ctk.CTkLabel(
            self,
            text="Saldo Saat Ini (seluruh pelanggan, semua bulan)",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="e",
        ).pack(anchor="e")

        self.value_label = ctk.CTkLabel(
            self,
            text="-",
            font=get_font("heading"),
            text_color=COLORS["text"],
            anchor="e",
        )
        self.value_label.pack(anchor="e", pady=(SPACING["xs"], 0))

    def set_value(self, text: str, color=None):
        self.value_label.configure(
            text=text,
            text_color=color or COLORS["text"],
        )


class LaporanPage(ctk.CTkFrame):
    def __init__(self, master, report_model: ReportModel):
        super().__init__(master, fg_color="transparent")

        self.report_model = report_model

        now = datetime.now()
        self.selected_year = now.year
        self.selected_month = now.month
        self.current_report = None
        self._details = []
        self._shown = PAGE_SIZE
        self._build_ui()

        # Tidak memanggil refresh() di sini: halaman dimuat saat pertama
        # kali dibuka (lihat _stale_pages di MainWindow).

    def refresh(self):
        self._load_report()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        header = PageHeader(self, "Laporan Bulanan")
        header.pack(
            fill="x",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        ctk.CTkButton(
            header.actions,
            text="Cetak Laporan",
            width=150,
            command=self._handle_print,
            **button_style("primary"),
        ).pack()

        self._build_filter_card(page_padding)
        self._build_summary_cards(page_padding)
        self._build_detail_card(page_padding)

    # ------------------------------------------------------------------
    # Filter bulan / tahun
    # ------------------------------------------------------------------
    def _build_filter_card(self, page_padding):
        card = SectionCard(self)
        card.pack(
            fill="x",
            padx=page_padding,
            pady=(0, SPACING["lg"]),
        )

        bar = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        bar.pack(fill="x")

        gap = SPACING["md"]

        # Bulan
        month_cell = ctk.CTkFrame(
            bar,
            fg_color="transparent",
            width=0,
            height=0,
        )
        month_cell.grid(row=0, column=0, sticky="sw", padx=(0, gap))

        ctk.CTkLabel(
            month_cell,
            text="Bulan",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        self.month_var = ctk.StringVar(
            value=BULAN_INDONESIA[self.selected_month - 1]
        )

        ctk.CTkOptionMenu(
            month_cell,
            values=BULAN_INDONESIA,
            variable=self.month_var,
            width=160,
            command=lambda _value: self._load_report(),
            **option_menu_style(),
        ).pack(fill="x", pady=(SPACING["xs"], 0))

        # Tahun
        self.year_field = FormField(
            bar,
            "Tahun",
            "Contoh: 2026",
            initial=str(self.selected_year),
        )
        self.year_field.grid(row=0, column=1, sticky="sw", padx=(0, gap))
        self.year_entry = self.year_field.entry
        self.year_entry.bind("<Return>", lambda _e: self._load_report())

        ctk.CTkButton(
            bar,
            text="Tampilkan",
            width=110,
            command=self._load_report,
            **button_style("secondary"),
        ).grid(row=0, column=2, sticky="s")

        # Pesan error sebaris dengan filter (tidak menambah tinggi kartu).
        bar.grid_columnconfigure(3, weight=1)

        self.error_label = ErrorText(bar, wraplength=300)
        self.error_label.grid(
            row=0,
            column=3,
            sticky="sw",
            padx=(gap, gap),
        )

        # Saldo saat ini di kanan kartu filter.
        self.balance_card = BalanceBlock(bar)
        self.balance_card.grid(row=0, column=4, sticky="se")

    # ------------------------------------------------------------------
    # Kartu ringkasan
    # ------------------------------------------------------------------
    def _build_summary_cards(self, page_padding):
        frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        frame.pack(
            fill="x",
            padx=page_padding,
            pady=(0, SPACING["lg"]),
        )

        half_gap = SPACING["md"] // 2

        self.month_cards = {}

        for column, (key, title) in enumerate(MONTH_CARDS):
            frame.grid_columnconfigure(column, weight=1, uniform="stat")

            card = StatCard(frame, title)
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else half_gap,
                    0 if column == len(MONTH_CARDS) - 1 else half_gap,
                ),
            )
            self.month_cards[key] = card

    # ------------------------------------------------------------------
    # Detail transaksi
    # ------------------------------------------------------------------
    def _build_detail_card(self, page_padding):
        card = SectionCard(self, "Detail Transaksi")
        card.pack(
            fill="both",
            expand=True,
            padx=page_padding,
            pady=(0, page_padding),
        )

        # Footer dipasang sebelum tabel agar selalu terlihat di bawah.
        footer = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        footer.pack(side="bottom", fill="x", pady=(SPACING["md"], 0))

        self.count_label = ctk.CTkLabel(
            footer,
            text="",
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.count_label.pack(side="left")

        self.more_button = ctk.CTkButton(
            footer,
            text="Tampilkan Lebih Banyak",
            width=180,
            command=self._show_more,
            **button_style("secondary", "small"),
        )

        self.detail_table = DataTable(
            card.body,
            DETAIL_COLUMNS,
            empty_title="Tidak ada transaksi",
            empty_text="Tidak ada transaksi pada bulan ini.",
            show_dot=True,
        )
        self.detail_table.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Muat & render laporan
    # ------------------------------------------------------------------
    def _load_report(self):
        self.error_label.clear()

        try:
            month = BULAN_INDONESIA.index(self.month_var.get()) + 1
        except ValueError:
            month = self.selected_month

        try:
            year = int(self.year_entry.get().strip())
            if year < 2000 or year > 2100:
                raise ValueError
        except ValueError:
            self.error_label.show(
                "Tahun tidak valid. Masukkan angka tahun, contoh: 2026."
            )
            return

        self.selected_month = month
        self.selected_year = year

        try:
            self.current_report = self.report_model.get_monthly_report(
                year,
                month,
            )
        except Exception:
            self.current_report = None
            self._clear_summary()
            self._details = []
            self._update_footer()
            self.detail_table.set_error(
                "Gagal memuat laporan",
                "Terjadi kesalahan saat memuat laporan. Coba lagi.",
            )
            return

        self._render_summary(self.current_report)
        self._render_details(self.current_report)

    def _clear_summary(self):
        for card in self.month_cards.values():
            card.set_value("-")

        self.balance_card.set_value("-")

    def _render_summary(self, report: dict):
        self.month_cards["total_debt_month"].set_value(
            format_rupiah(report["total_debt_month"]),
            color=COLORS["danger"],
        )
        self.month_cards["total_payment_month"].set_value(
            format_rupiah(report["total_payment_month"]),
            color=COLORS["success"],
        )
        self.month_cards["count_debt_transactions"].set_value(
            str(report["count_debt_transactions"])
        )
        self.month_cards["count_payment_transactions"].set_value(
            str(report["count_payment_transactions"])
        )

        balance = report["current_outstanding_balance"]

        self.balance_card.set_value(
            format_rupiah(balance),
            color=COLORS["danger"] if balance > 0 else COLORS["success"],
        )

    def _render_details(self, report: dict):
        self._details = list(report["details"])
        self._shown = PAGE_SIZE
        self._render_rows()

    def _render_rows(self):
        visible = self._details[: self._shown]

        self.detail_table.set_rows(
            [self._detail_values(item) for item in visible],
            variants=[
                TYPE_VARIANTS.get(item["type"], "neutral")
                for item in visible
            ],
        )
        self._update_footer()

    def _update_footer(self):
        total = len(self._details)
        shown = min(self._shown, total)

        self.count_label.configure(
            text=f"Menampilkan {shown} dari {total} transaksi" if total else ""
        )

        if total > shown:
            self.more_button.pack(side="right")
        else:
            self.more_button.pack_forget()

    def _show_more(self):
        self._shown += PAGE_SIZE
        self._render_rows()

    @staticmethod
    def _detail_values(item: dict) -> list:
        sign = "+" if item["type"] == "Hutang" else "-"

        return [
            format_date_indonesia(item["date"]),
            item.get("customer_name") or "-",
            item["type"],
            f"{sign} {format_rupiah(item['amount'])}",
        ]

    # ------------------------------------------------------------------
    # Cetak PDF
    # ------------------------------------------------------------------
    def _handle_print(self):
        if not self.current_report:
            show_warning(
                self,
                "Laporan Belum Ditampilkan",
                "Tampilkan laporan terlebih dahulu sebelum mencetak.",
            )
            return

        filename = (
            f"laporan_{self.selected_year}-{self.selected_month:02d}"
            f"_{datetime.now().strftime('%H%M%S')}.pdf"
        )
        output_path = os.path.join(tempfile.gettempdir(), filename)

        try:
            self.report_model.export_to_pdf(
                self.current_report,
                output_path,
            )
            Printer().open_pdf(output_path)

        except PrinterError as exc:
            show_error(self, "Cetak Gagal", str(exc))

        except Exception:
            show_error(
                self,
                "Cetak Gagal",
                "Terjadi kesalahan saat membuat file PDF laporan. "
                "Coba lagi.",
            )