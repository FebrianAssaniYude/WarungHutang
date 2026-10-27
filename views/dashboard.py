import customtkinter as ctk

from components.cards import SectionCard, StatCard
from components.page_header import PageHeader
from components.tables import DataTable
from utils.formatter import format_rupiah, format_date_indonesia
from utils.theme import COLORS, LAYOUT, SPACING, get_font


# Warna titik per jenis transaksi (kunci huruf kecil).
# Jenis yang tidak terdaftar di sini otomatis tampil netral.
# Samakan dengan TYPE_VARIANTS di views/history.py dan components/badges.py.
TYPE_VARIANTS = {
    "hutang": "warning",
    "pembayaran": "success",
    "pembelian": "neutral",
    "penjualan": "info",
}

RECENT_COLUMNS = [
    {"title": "Tanggal", "weight": 2, "align": "left"},
    {"title": "Nomor Transaksi", "weight": 4, "align": "left"},
    {"title": "Jenis", "weight": 2, "align": "left"},
    {"title": "Nominal", "weight": 3, "align": "right"},
]


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, report_model):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.report_model = report_model

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        PageHeader(
            self,
            "Dashboard",
        ).pack(
            fill="x",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        # Bukan CTkScrollableFrame: tabel transaksi terbaru (Treeview)
        # sudah punya scrollbar sendiri dan mengisi sisa tinggi halaman,
        # sehingga halaman tidak perlu digulir.
        self.content = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.content.pack(
            fill="both",
            expand=True,
            padx=page_padding,
            pady=(0, page_padding),
        )

        self._build_summary_cards()
        self._build_today_section()
        self._build_recent_section()

    def _build_summary_cards(self):
        frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        frame.pack(
            fill="x",
            pady=(0, SPACING["lg"]),
        )

        titles = ["Sisa Hutang", "Pelanggan", "Barang", "Stok Menipis"]
        cards = []
        half_gap = LAYOUT["card_gap"] // 2

        for column, title in enumerate(titles):
            frame.grid_columnconfigure(column, weight=1, uniform="stat")

            card = StatCard(frame, title)
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else half_gap,
                    0 if column == len(titles) - 1 else half_gap,
                ),
            )
            cards.append(card)

        self.stat_low_stock = cards[3]

        self.card_outstanding = cards[0].value_label
        self.card_customers = cards[1].value_label
        self.card_products = cards[2].value_label
        self.card_low_stock = cards[3].value_label

    def _build_today_section(self):
        section = SectionCard(self.content, "Aktivitas Hari Ini")
        section.pack(
            fill="x",
            pady=(0, SPACING["lg"]),
        )

        grid = section.body
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1, uniform="today")

        self.today_sales_label = self._create_today_item(grid, 0, "Penjualan")
        self.today_purchase_label = self._create_today_item(grid, 1, "Pembelian")
        self.today_debt_label = self._create_today_item(grid, 2, "Hutang")
        self.today_payment_label = self._create_today_item(grid, 3, "Pembayaran")

    def _create_today_item(self, parent, column, title):
        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.grid(row=0, column=column, sticky="w")

        ctk.CTkLabel(
            item,
            text=title,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            item,
            text="-",
            font=get_font("heading"),
            text_color=COLORS["text"],
            anchor="w",
        )
        value_label.pack(anchor="w", pady=(SPACING["xs"], 0))

        return value_label

    def _build_recent_section(self):
        self.recent_section = SectionCard(self.content, "Transaksi Terbaru")
        self.recent_section.pack(fill="both", expand=True)

        self.recent_table = DataTable(
            self.recent_section.body,
            RECENT_COLUMNS,
            empty_title="Belum ada transaksi",
            empty_text="Transaksi terbaru akan muncul di sini.",
            show_dot=True,
        )
        self.recent_table.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self):
        try:
            import time

            started = time.perf_counter()
            summary = self.report_model.get_dashboard_summary()
            print(f"[dashboard] query={time.perf_counter() - started:.3f}s")
        except Exception as exc:
            self.recent_table.set_error(
                "Gagal memuat data dashboard.",
                str(exc),
            )
            return

        self.card_outstanding.configure(
            text=format_rupiah(
                summary["total_outstanding"]
            )
        )

        self.card_customers.configure(
            text=str(summary["total_customers"])
        )

        self.card_products.configure(
            text=str(summary["total_products"])
        )

        low_stock = summary["low_stock_products"]
        try:
            has_low_stock = int(low_stock or 0) > 0
        except (TypeError, ValueError):
            has_low_stock = False

        self.stat_low_stock.set_value(
            str(low_stock),
            color=COLORS["warning"] if has_low_stock else None,
        )

        self.today_sales_label.configure(
            text=format_rupiah(
                summary["today_sales"]
            )
        )

        self.today_purchase_label.configure(
            text=format_rupiah(
                summary["today_purchases"]
            )
        )

        self.today_debt_label.configure(
            text=format_rupiah(
                summary["today_debt"]
            )
        )

        self.today_payment_label.configure(
            text=format_rupiah(
                summary["today_payments"]
            )
        )

        self._refresh_recent_transactions(
            summary["recent_transactions"]
        )

    def _refresh_recent_transactions(self, transactions):
        rows = []
        variants = []

        for transaction in transactions or []:
            transaction_type = transaction.get("type") or "-"

            rows.append(
                [
                    format_date_indonesia(
                        transaction.get("date")
                    ),
                    transaction.get("transaction_number") or "-",
                    transaction_type,
                    format_rupiah(
                        transaction.get("amount", 0)
                    ),
                ]
            )
            variants.append(
                TYPE_VARIANTS.get(
                    str(transaction_type).strip().lower(),
                    "neutral",
                )
            )

        self.recent_table.set_rows(rows, variants=variants)