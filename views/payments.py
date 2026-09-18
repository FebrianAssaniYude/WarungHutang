"""
views/payments.py

Halaman Pembayaran: pilih pelanggan -> lihat total hutang (sisa saat
ini) -> masukkan jumlah pembayaran -> lihat preview sisa setelah
pembayaran -> Simpan Pembayaran.

Pembayaran hanya dikaitkan ke pelanggan, tidak ke transaksi hutang
tertentu, sesuai spesifikasi. Menggunakan ulang CustomerPickerDialog
dari views.debts supaya tidak duplikasi kode.
"""

import customtkinter as ctk

from models.customer import CustomerModel
from models.payment import PaymentModel
from utils.formatter import format_rupiah
from views.debts import CustomerPickerDialog


class PaymentsPage(ctk.CTkFrame):
    def __init__(self, master, customer_model: CustomerModel, payment_model: PaymentModel):
        super().__init__(master, fg_color="transparent")

        self.customer_model = customer_model
        self.payment_model = payment_model
        self.selected_customer = None
        self.current_sisa = 0

        self._build_header()
        self._build_customer_row()
        self._build_summary_card()
        self._build_form()

    def refresh(self):
        # Dipanggil setiap kali halaman dibuka dari sidebar. Sengaja tidak
        # mengosongkan form yang sedang diisi. Tapi jika pelanggan sudah
        # dipilih, muat ulang saldonya - siapa tahu berubah dari halaman lain.
        if self.selected_customer:
            self._refresh_summary()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self):
        ctk.CTkLabel(
            self, text="Pembayaran", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=32, pady=(28, 4))

        self.status_label = ctk.CTkLabel(self, text="", text_color="#2E7D32")
        self.status_label.pack(anchor="w", padx=32)

    # ------------------------------------------------------------------
    # Pilih pelanggan
    # ------------------------------------------------------------------
    def _build_customer_row(self):
        row = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        row.pack(fill="x", padx=32, pady=(12, 12))

        ctk.CTkLabel(row, text="Pelanggan:", font=ctk.CTkFont(size=13, weight="bold")).pack(
            side="left", padx=(16, 8), pady=12
        )

        self.customer_button = ctk.CTkButton(
            row, text="[ Cari/Pilih Pelanggan ]", anchor="w",
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            command=self._open_customer_picker,
        )
        self.customer_button.pack(side="left", fill="x", expand=True, padx=(0, 16), pady=12)

    def _open_customer_picker(self):
        CustomerPickerDialog(self, self.customer_model, on_select=self._handle_customer_selected)

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self.customer_button.configure(text=f"{customer['name']}  (ganti)")
        self._refresh_summary()

    # ------------------------------------------------------------------
    # Kartu ringkasan (Total Hutang saat ini)
    # ------------------------------------------------------------------
    def _build_summary_card(self):
        self.summary_frame = ctk.CTkFrame(self, fg_color=("white", "gray17"))
        self.summary_frame.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(
            self.summary_frame, text="Total Hutang", font=ctk.CTkFont(size=12), text_color="gray50"
        ).pack(anchor="w", padx=16, pady=(16, 0))

        self.total_debt_label = ctk.CTkLabel(
            self.summary_frame, text="-", font=ctk.CTkFont(size=22, weight="bold")
        )
        self.total_debt_label.pack(anchor="w", padx=16, pady=(0, 16))

    def _refresh_summary(self):
        if not self.selected_customer:
            self.current_sisa = 0
            self.total_debt_label.configure(text="-")
            return

        try:
            _, _, sisa = self.payment_model.get_balance(self.selected_customer["id"])
        except Exception:
            self.total_debt_label.configure(text="-")
            self.error_label.configure(text="Gagal memuat saldo pelanggan. Coba lagi.")
            return

        self.current_sisa = sisa
        self.total_debt_label.configure(text=format_rupiah(sisa))
        self._update_preview()

    # ------------------------------------------------------------------
    # Form pembayaran
    # ------------------------------------------------------------------
    def _build_form(self):
        form = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        form.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(
            form, text="Jumlah Pembayaran", anchor="w", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=16, pady=(16, 4))

        self.amount_entry = ctk.CTkEntry(form, height=40, placeholder_text="contoh: 50000")
        self.amount_entry.pack(fill="x", padx=16, pady=(0, 8))
        self.amount_entry.bind("<KeyRelease>", lambda e: self._update_preview())

        ctk.CTkLabel(
            form, text="Sisa Setelah Pembayaran", anchor="w", font=ctk.CTkFont(size=12), text_color="gray50"
        ).pack(anchor="w", padx=16, pady=(4, 0))

        self.preview_label = ctk.CTkLabel(
            form, text="-", font=ctk.CTkFont(size=16, weight="bold")
        )
        self.preview_label.pack(anchor="w", padx=16, pady=(0, 8))

        self.error_label = ctk.CTkLabel(form, text="", text_color="#D64545")
        self.error_label.pack(anchor="w", padx=16, pady=(0, 4))

        ctk.CTkButton(
            form, text="Simpan Pembayaran", height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_save,
        ).pack(fill="x", padx=16, pady=(8, 16))

    def _update_preview(self):
        if not self.selected_customer:
            self.preview_label.configure(text="-")
            return

        amount_text = self.amount_entry.get().strip()
        if not amount_text:
            self.preview_label.configure(text=format_rupiah(self.current_sisa))
            return

        try:
            amount = int(round(float(amount_text)))
        except ValueError:
            self.preview_label.configure(text="-")
            return

        remaining = self.current_sisa - amount
        color = "#B93A3A" if remaining < 0 else None
        self.preview_label.configure(
            text=format_rupiah(remaining),
            text_color=color if color else ("gray10", "gray90"),
        )

    def _handle_save(self):
        self.status_label.configure(text="")
        self.error_label.configure(text="")

        if not self.selected_customer:
            self.error_label.configure(text="Pelanggan harus dipilih terlebih dahulu.")
            return

        amount_text = self.amount_entry.get().strip()

        try:
            success, message, _ = self.payment_model.create_payment(
                self.selected_customer["id"], amount_text
            )
        except Exception:
            self.error_label.configure(text="Terjadi kesalahan pada database. Coba lagi.")
            return

        if not success:
            self.error_label.configure(text=message)
            return

        # Sukses: pesan singkat, reset form untuk pembayaran berikutnya.
        self.status_label.configure(text=f"✓ {message}")
        self.selected_customer = None
        self.current_sisa = 0
        self.customer_button.configure(text="[ Cari/Pilih Pelanggan ]")
        self.amount_entry.delete(0, "end")
        self.total_debt_label.configure(text="-")
        self.preview_label.configure(text="-")
