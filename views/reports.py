"""
views/reports.py

Halaman Laporan Bulanan: pilih bulan & tahun -> tampilkan ringkasan
(total hutang/pembayaran bulan itu + jumlah transaksi) dan detail
transaksinya, terpisah dari "Saldo Saat Ini" (total sisa hutang
seluruh pelanggan per hari ini, tidak dibatasi bulan yang dipilih).

Export ke PDF memakai dialog simpan file bawaan (tkinter.filedialog),
tanpa dependency tambahan di luar reportlab yang sudah dipakai model.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from models.report import ReportModel
from utils.formatter import format_rupiah, format_date_indonesia, BULAN_INDONESIA


class LaporanPage(ctk.CTkFrame):
    def __init__(self, master, report_model: ReportModel):
        super().__init__(master, fg_color="transparent")

        self.report_model = report_model
        now = datetime.now()
        self.selected_year = now.year
        self.selected_month = now.month
        self.current_report = None

        self._build_header()
        self._build_filter_row()
        self._build_summary_cards()
        self._build_detail_header()
        self._build_detail_body()

        self.refresh()

    def refresh(self):
        self._load_report()

    # ------------------------------------------------------------------
    # Header & filter bulan/tahun
    # ------------------------------------------------------------------
    def _build_header(self):
        ctk.CTkLabel(
            self, text="Laporan Bulanan", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=32, pady=(28, 12))

    def _build_filter_row(self):
        row = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        row.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(row, text="Bulan:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(16, 6), pady=12
        )
        self.month_var = ctk.StringVar(value=BULAN_INDONESIA[self.selected_month - 1])
        ctk.CTkOptionMenu(
            row, values=BULAN_INDONESIA, variable=self.month_var, width=140,
            command=lambda _: self._load_report(),
        ).pack(side="left", padx=(0, 16), pady=12)

        ctk.CTkLabel(row, text="Tahun:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(0, 6), pady=12
        )
        self.year_entry = ctk.CTkEntry(row, width=90)
        self.year_entry.insert(0, str(self.selected_year))
        self.year_entry.pack(side="left", padx=(0, 12), pady=12)
        self.year_entry.bind("<Return>", lambda e: self._load_report())

        ctk.CTkButton(row, text="Tampilkan", height=32, command=self._load_report).pack(
            side="left", padx=(0, 12), pady=12
        )

        ctk.CTkButton(
            row, text="Export ke PDF", height=32,
            fg_color="gray70", hover_color="gray60",
            command=self._handle_export,
        ).pack(side="left", padx=(0, 16), pady=12)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#D64545")
        self.error_label.pack(anchor="w", padx=32)

    # ------------------------------------------------------------------
    # Kartu ringkasan
    # ------------------------------------------------------------------
    def _build_summary_cards(self):
        self.summary_frame = ctk.CTkFrame(self, fg_color=("white", "gray17"))
        self.summary_frame.pack(fill="x", padx=32, pady=(0, 12))
        self.summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_labels = {}
        cards = [
            ("total_debt_month", "Total Hutang Bulan Ini"),
            ("total_payment_month", "Total Pembayaran Bulan Ini"),
            ("count_debt_transactions", "Jumlah Transaksi Hutang"),
            ("count_payment_transactions", "Jumlah Transaksi Pembayaran"),
        ]
        for col, (key, label) in enumerate(cards):
            cell = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=12, pady=12)
            ctk.CTkLabel(cell, text=label, font=ctk.CTkFont(size=11), text_color="gray50").pack(anchor="w")
            value_label = ctk.CTkLabel(cell, text="-", font=ctk.CTkFont(size=16, weight="bold"))
            value_label.pack(anchor="w")
            self.card_labels[key] = value_label

        # Saldo saat ini - dipisah jelas secara visual dari ringkasan bulan,
        # supaya tidak disalahartikan sebagai aktivitas bulan tersebut.
        balance_row = ctk.CTkFrame(self, fg_color=("gray90", "gray25"))
        balance_row.pack(fill="x", padx=32, pady=(0, 12))
        ctk.CTkLabel(
            balance_row, text="Saldo Saat Ini (Seluruh Pelanggan, tidak dibatasi bulan)",
            font=ctk.CTkFont(size=11), text_color="gray50",
        ).pack(anchor="w", padx=16, pady=(10, 0))
        self.balance_label = ctk.CTkLabel(balance_row, text="-", font=ctk.CTkFont(size=18, weight="bold"))
        self.balance_label.pack(anchor="w", padx=16, pady=(0, 10))

    # ------------------------------------------------------------------
    # Detail transaksi
    # ------------------------------------------------------------------
    def _build_detail_header(self):
        ctk.CTkLabel(
            self, text="Detail Transaksi Bulan Ini", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=32, pady=(4, 6))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=32)
        columns = [("Tanggal", 2), ("Pelanggan", 2), ("Jenis", 1), ("Nominal", 1)]
        for col, (_, weight) in enumerate(columns):
            row.grid_columnconfigure(col, weight=weight)
        for col, (text, _) in enumerate(columns):
            ctk.CTkLabel(
                row, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=(0, 6))

    def _build_detail_body(self):
        self.detail_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        self.detail_frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        for col, weight in [(0, 2), (1, 2), (2, 1), (3, 1)]:
            self.detail_frame.grid_columnconfigure(col, weight=weight)

    # ------------------------------------------------------------------
    # Muat & render laporan
    # ------------------------------------------------------------------
    def _load_report(self):
        self.error_label.configure(text="")

        try:
            month = BULAN_INDONESIA.index(self.month_var.get()) + 1
        except ValueError:
            month = self.selected_month

        year_text = self.year_entry.get().strip()
        try:
            year = int(year_text)
            if year < 2000 or year > 2100:
                raise ValueError
        except ValueError:
            self.error_label.configure(text="Tahun tidak valid. Masukkan angka tahun, contoh: 2026.")
            return

        self.selected_month = month
        self.selected_year = year

        try:
            self.current_report = self.report_model.get_monthly_report(year, month)
        except Exception:
            self.error_label.configure(text="Terjadi kesalahan saat memuat laporan. Coba lagi.")
            self.current_report = None
            return

        self._render_summary(self.current_report)
        self._render_details(self.current_report)

    def _render_summary(self, report: dict):
        self.card_labels["total_debt_month"].configure(text=format_rupiah(report["total_debt_month"]))
        self.card_labels["total_payment_month"].configure(text=format_rupiah(report["total_payment_month"]))
        self.card_labels["count_debt_transactions"].configure(text=str(report["count_debt_transactions"]))
        self.card_labels["count_payment_transactions"].configure(text=str(report["count_payment_transactions"]))
        self.balance_label.configure(text=format_rupiah(report["current_outstanding_balance"]))

    def _render_details(self, report: dict):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

        details = report["details"]
        if not details:
            ctk.CTkLabel(
                self.detail_frame, text="Tidak ada transaksi pada bulan ini.", text_color="gray50",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
            return

        for i, item in enumerate(details):
            color = "#B93A3A" if item["type"] == "Hutang" else "#2E7D32"
            sign = "+" if item["type"] == "Hutang" else "-"

            ctk.CTkLabel(
                self.detail_frame, text=format_date_indonesia(item["date"]), anchor="w"
            ).grid(row=i, column=0, sticky="ew", padx=8, pady=6)
            ctk.CTkLabel(self.detail_frame, text=item["customer_name"], anchor="w").grid(
                row=i, column=1, sticky="ew", padx=8, pady=6
            )
            ctk.CTkLabel(self.detail_frame, text=item["type"], anchor="w", text_color=color).grid(
                row=i, column=2, sticky="ew", padx=8, pady=6
            )
            ctk.CTkLabel(
                self.detail_frame, text=f"{sign} {format_rupiah(item['amount'])}", anchor="w", text_color=color,
            ).grid(row=i, column=3, sticky="ew", padx=8, pady=6)

    # ------------------------------------------------------------------
    # Export PDF
    # ------------------------------------------------------------------
    def _handle_export(self):
        if not self.current_report:
            self.error_label.configure(text="Tampilkan laporan terlebih dahulu sebelum export.")
            return

        default_name = f"laporan_{self.selected_year}-{self.selected_month:02d}.pdf"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("File PDF", "*.pdf")],
            title="Simpan Laporan Sebagai",
        )
        if not path:
            return  # pengguna membatalkan dialog

        try:
            self.report_model.export_to_pdf(self.current_report, path)
        except Exception:
            messagebox.showerror(
                "Export Gagal", "Terjadi kesalahan saat membuat file PDF. Coba lagi."
            )
            return

        messagebox.showinfo("Export Berhasil", f"Laporan berhasil disimpan ke:\n{path}")
