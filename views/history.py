"""
views/history.py

Halaman Riwayat: menampilkan seluruh aktivitas (hutang + pembayaran)
dalam satu tabel, dengan filter jenis (Semua/Hutang/Pembayaran),
pelanggan (opsional), dan rentang tanggal (opsional).
"""

import re

import customtkinter as ctk

from models.customer import CustomerModel
from models.history import HistoryModel
from utils.formatter import format_rupiah, format_date_indonesia
from views.debts import CustomerPickerDialog

TYPE_OPTIONS = ["Semua", "Hutang", "Pembayaran"]
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HistoryPage(ctk.CTkFrame):
    def __init__(self, master, history_model: HistoryModel, customer_model: CustomerModel):
        super().__init__(master, fg_color="transparent")

        self.history_model = history_model
        self.customer_model = customer_model
        self.selected_customer = None  # None = semua pelanggan

        self._build_header()
        self._build_filter_row()
        self._build_table_header()
        self._build_table_body()

        self.refresh()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self):
        ctk.CTkLabel(
            self, text="Riwayat", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=32, pady=(28, 12))

    # ------------------------------------------------------------------
    # Filter: jenis, pelanggan, rentang tanggal
    # ------------------------------------------------------------------
    def _build_filter_row(self):
        row = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        row.pack(fill="x", padx=32, pady=(0, 12))

        # Jenis
        ctk.CTkLabel(row, text="Jenis:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(16, 6), pady=12
        )
        self.type_var = ctk.StringVar(value="Semua")
        type_menu = ctk.CTkOptionMenu(
            row, values=TYPE_OPTIONS, variable=self.type_var,
            width=130, command=lambda _: self.refresh(),
        )
        type_menu.pack(side="left", padx=(0, 16), pady=12)

        # Pelanggan
        ctk.CTkLabel(row, text="Pelanggan:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(0, 6), pady=12
        )
        self.customer_button = ctk.CTkButton(
            row, text="Semua Pelanggan", width=160, height=28,
            fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
            command=self._open_customer_picker,
        )
        self.customer_button.pack(side="left", padx=(0, 6), pady=12)

        ctk.CTkButton(
            row, text="Reset", width=56, height=28,
            fg_color="gray70", hover_color="gray60",
            command=self._reset_customer_filter,
        ).pack(side="left", padx=(0, 16), pady=12)

        # Rentang tanggal
        ctk.CTkLabel(row, text="Dari:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(0, 6), pady=12
        )
        self.date_from_entry = ctk.CTkEntry(row, width=110, placeholder_text="YYYY-MM-DD")
        self.date_from_entry.pack(side="left", padx=(0, 12), pady=12)
        self.date_from_entry.bind("<Return>", lambda e: self.refresh())

        ctk.CTkLabel(row, text="Sampai:", font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(0, 6), pady=12
        )
        self.date_to_entry = ctk.CTkEntry(row, width=110, placeholder_text="YYYY-MM-DD")
        self.date_to_entry.pack(side="left", padx=(0, 12), pady=12)
        self.date_to_entry.bind("<Return>", lambda e: self.refresh())

        ctk.CTkButton(row, text="Terapkan", height=28, command=self.refresh).pack(
            side="left", padx=(0, 16), pady=12
        )

    def _open_customer_picker(self):
        CustomerPickerDialog(self, self.customer_model, on_select=self._handle_customer_selected)

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self.customer_button.configure(text=f"{customer['name']}")
        self.refresh()

    def _reset_customer_filter(self):
        self.selected_customer = None
        self.customer_button.configure(text="Semua Pelanggan")
        self.refresh()

    # ------------------------------------------------------------------
    # Tabel
    # ------------------------------------------------------------------
    def _build_table_header(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=32)

        columns = [("Tanggal", 2), ("Pelanggan", 2), ("Jenis", 1), ("Nominal", 1)]
        for col, (_, weight) in enumerate(columns):
            row.grid_columnconfigure(col, weight=weight)
        for col, (text, _) in enumerate(columns):
            ctk.CTkLabel(
                row, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=(0, 6))

    def _build_table_body(self):
        self.table_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        self.table_frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        for col, weight in [(0, 2), (1, 2), (2, 1), (3, 1)]:
            self.table_frame.grid_columnconfigure(col, weight=weight)

    def refresh(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        type_filter_map = {"Semua": "semua", "Hutang": "hutang", "Pembayaran": "pembayaran"}
        type_filter = type_filter_map.get(self.type_var.get(), "semua")

        customer_id = self.selected_customer["id"] if self.selected_customer else None
        date_from = self.date_from_entry.get().strip() or None
        date_to = self.date_to_entry.get().strip() or None

        for label, value in (("Dari", date_from), ("Sampai", date_to)):
            if value and not _DATE_PATTERN.match(value):
                ctk.CTkLabel(
                    self.table_frame,
                    text=f"Format tanggal \"{label}\" tidak valid. Gunakan format YYYY-MM-DD, contoh: 2026-09-11.",
                    text_color="#D64545",
                ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
                return

        try:
            entries = self.history_model.list_history(
                type_filter=type_filter,
                customer_id=customer_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception:
            ctk.CTkLabel(
                self.table_frame,
                text="Terjadi kesalahan saat memuat riwayat. Coba lagi.",
                text_color="#D64545",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
            return

        if not entries:
            ctk.CTkLabel(
                self.table_frame, text="Tidak ada riwayat yang cocok dengan filter ini.",
                text_color="gray50",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
            return

        for i, entry in enumerate(entries):
            self._build_row(i, entry)

    def _build_row(self, row_index: int, entry: dict):
        ctk.CTkLabel(
            self.table_frame, text=format_date_indonesia(entry["date"]), anchor="w"
        ).grid(row=row_index, column=0, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(self.table_frame, text=entry["customer_name"], anchor="w").grid(
            row=row_index, column=1, sticky="ew", padx=8, pady=6
        )

        color = "#B93A3A" if entry["type"] == "Hutang" else "#2E7D32"
        ctk.CTkLabel(self.table_frame, text=entry["type"], anchor="w", text_color=color).grid(
            row=row_index, column=2, sticky="ew", padx=8, pady=6
        )

        sign = "+" if entry["type"] == "Hutang" else "-"
        ctk.CTkLabel(
            self.table_frame, text=f"{sign} {format_rupiah(entry['amount'])}", anchor="w", text_color=color,
        ).grid(row=row_index, column=3, sticky="ew", padx=8, pady=6)
