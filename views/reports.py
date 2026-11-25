import os
import tempfile
from datetime import datetime

import customtkinter as ctk

from components.cards import SectionCard, StatCard
from components.detail_dialogs import PurchaseDetailDialog
from components.dialogs import show_error, show_warning
from components.forms import ErrorText, FormField, option_menu_style
from components.page_header import PageHeader
from components.tables import DataTable
from models.purchase import PurchaseModel
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

PURCHASE_COLUMNS = [
    {"title": "Tanggal", "weight": 2, "align": "left"},
    {"title": "No. Transaksi", "weight": 4, "align": "left"},
    {"title": "Supplier", "weight": 3, "align": "left"},
    {"title": "Total", "weight": 3, "align": "right"},
]

MODE_HUTANG = "Hutang & Pembayaran"
MODE_PEMBELIAN = "Pembelian"

# Warna titik di kolom kiri tabel per jenis transaksi.
# Samakan dengan TYPE_VARIANTS di views/history.py dan views/dashboard.py.
TYPE_VARIANTS = {
    "Hutang": "warning",
    "Pembayaran": "success",
}

# Empat kartu ringkasan dipakai ulang; judul dan nilainya berganti
# mengikuti mode laporan (hutang/pembayaran atau pembelian).
MONTH_CARD_KEYS = ["card_0", "card_1", "card_2", "card_3"]

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
        self.purchase_model = PurchaseModel(report_model.db)

        now = datetime.now()
        self.selected_year = now.year
        self.selected_month = now.month
        self.current_report = None
        self._details = []
        self._purchases = []
        self._shown = PAGE_SIZE
        self.mode_var = ctk.StringVar(value=MODE_HUTANG)
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

        self._build_mode_switch(page_padding)
        self._build_filter_card(page_padding)
        self._build_summary_cards(page_padding)
        self._build_detail_card(page_padding)

    def _build_mode_switch(self, page_padding):
        bar = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        bar.pack(
            fill="x",
            padx=page_padding,
            pady=(0, SPACING["md"]),
        )

        self.mode_switch = ctk.CTkSegmentedButton(
            bar,
            values=[MODE_HUTANG, MODE_PEMBELIAN],
            variable=self.mode_var,
            command=self._switch_mode,
            font=get_font("button_small"),
            height=32,
            corner_radius=8,
            fg_color=COLORS["background"],
            selected_color=COLORS["primary"],
            selected_hover_color=COLORS["primary_hover"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            text_color_disabled=COLORS["text_muted"],
        )
        self.mode_switch.pack(side="left")

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

        for column, key in enumerate(MONTH_CARD_KEYS):
            frame.grid_columnconfigure(column, weight=1, uniform="stat")

            card = StatCard(frame, "")
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else half_gap,
                    0 if column == len(MONTH_CARD_KEYS) - 1 else half_gap,
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

        self.table_holder = ctk.CTkFrame(
            card.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.table_holder.pack(fill="both", expand=True)

        self.detail_table = DataTable(
            self.table_holder,
            DETAIL_COLUMNS,
            empty_title="Tidak ada transaksi",
            empty_text="Tidak ada transaksi pada bulan ini.",
            show_dot=True,
        )

        self.purchase_table = DataTable(
            self.table_holder,
            PURCHASE_COLUMNS,
            empty_title="Tidak ada pembelian",
            empty_text="Tidak ada pembelian pada bulan ini.",
            on_activate=self._open_purchase_detail,
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
            self._purchases = []
            self._update_footer()
            error_title = "Gagal memuat laporan"
            error_text = "Terjadi kesalahan saat memuat laporan. Coba lagi."
            self.detail_table.set_error(error_title, error_text)
            self.purchase_table.set_error(error_title, error_text)
            return

        self._render_summary(self.current_report)
        self._render_details(self.current_report)

    def _clear_summary(self):
        for card in self.month_cards.values():
            card.set_value("-")

        self.balance_card.set_value("-")

    def _render_summary(self, report: dict):
        cards = [self.month_cards[key] for key in MONTH_CARD_KEYS]

        if self._is_purchase_mode():
            total = report.get("total_purchase_month", 0)
            count = report.get("count_purchase_month", 0)
            item_count = report.get("total_purchase_items_month", 0)
            average = int(round(total / count)) if count else 0

            cards[0].set_title("Total Pembelian Bulan Ini")
            cards[0].set_value(
                format_rupiah(total),
                color=COLORS["text"],
            )
            cards[1].set_title("Jumlah Transaksi Pembelian")
            cards[1].set_value(str(count))
            cards[2].set_title("Jumlah Barang Dibeli")
            cards[2].set_value(str(item_count))
            cards[3].set_title("Rata-rata per Transaksi")
            cards[3].set_value(format_rupiah(average))
        else:
            cards[0].set_title("Total Hutang Bulan Ini")
            cards[0].set_value(
                format_rupiah(report["total_debt_month"]),
                color=COLORS["danger"],
            )
            cards[1].set_title("Total Pembayaran Bulan Ini")
            cards[1].set_value(
                format_rupiah(report["total_payment_month"]),
                color=COLORS["success"],
            )
            cards[2].set_title("Jumlah Transaksi Hutang")
            cards[2].set_value(str(report["count_debt_transactions"]))
            cards[3].set_title("Jumlah Transaksi Pembayaran")
            cards[3].set_value(str(report["count_payment_transactions"]))

        balance = report["current_outstanding_balance"]

        self.balance_card.set_value(
            format_rupiah(balance),
            color=COLORS["danger"] if balance > 0 else COLORS["success"],
        )

    def _render_details(self, report: dict):
        self._details = list(report.get("details") or [])
        self._purchases = list(report.get("purchases") or [])
        self._shown = PAGE_SIZE
        self._render_rows()

    def _render_rows(self):
        if self._is_purchase_mode():
            self.detail_table.pack_forget()
            self.purchase_table.pack(fill="both", expand=True)

            visible = self._purchases[: self._shown]

            self.purchase_table.set_rows(
                [self._purchase_values(item) for item in visible],
                variants=["neutral"] * len(visible),
            )
        else:
            self.purchase_table.pack_forget()
            self.detail_table.pack(fill="both", expand=True)

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
        purchase_mode = self._is_purchase_mode()
        active = self._purchases if purchase_mode else self._details
        total = len(active)
        shown = min(self._shown, total)
        noun = "pembelian" if purchase_mode else "transaksi"

        self.count_label.configure(
            text=f"Menampilkan {shown} dari {total} {noun}" if total else ""
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

    @staticmethod
    def _purchase_values(item: dict) -> list:
        return [
            format_date_indonesia(item["date"]),
            item.get("transaction_number") or "Transaksi Lama",
            item.get("supplier_name") or "Tidak ada supplier",
            format_rupiah(item.get("total_amount", 0)),
        ]

    def _is_purchase_mode(self) -> bool:
        return self.mode_var.get() == MODE_PEMBELIAN

    def _switch_mode(self, _value=None):
        self._shown = PAGE_SIZE

        if self.current_report:
            self._render_summary(self.current_report)

        self._render_rows()

    def _open_purchase_detail(self, index: int):
        if not (0 <= index < len(self._purchases)):
            return

        entry = self._purchases[index]

        try:
            detail = self.purchase_model.get_transaction_detail(entry["id"])
        except Exception:
            show_error(
                self,
                "Terjadi Kesalahan",
                "Gagal memuat detail pembelian. Coba lagi.",
            )
            return

        if not detail:
            show_warning(
                self,
                "Data Tidak Ditemukan",
                "Transaksi pembelian tidak ditemukan.",
            )
            return

        PurchaseDetailDialog(self, detail)

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