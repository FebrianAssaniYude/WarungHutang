import customtkinter as ctk

from components.cards import SectionCard, StatCard
from components.customer_picker import CustomerPickerDialog, CustomerSelector
from components.dialogs import show_error, show_success
from components.forms import ErrorText, FormField
from components.page_header import PageHeader
from models.customer import CustomerModel
from models.payment import PaymentModel
from utils.error_handler import log_error
from utils.formatter import format_rupiah
from utils.theme import (
    COLORS,
    INPUT_HEIGHT,
    LAYOUT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)


class PaymentsPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        customer_model: CustomerModel,
        payment_model: PaymentModel,
    ):
        super().__init__(master, fg_color="transparent")

        self.customer_model = customer_model
        self.payment_model = payment_model

        self.selected_customer = None
        self.current_sisa = 0
        self._saving_payment = False

        self._build_ui()

    def refresh(self):
        """
        Dipanggil setiap kali halaman dibuka dari sidebar.

        Form yang sedang diisi tidak dikosongkan.
        Jika pelanggan sudah dipilih, saldo dimuat ulang.
        """
        if self.selected_customer:
            self._refresh_summary()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        page_padding = LAYOUT["page_padding"]

        PageHeader(self, "Pembayaran").pack(
            fill="x",
            padx=page_padding,
            pady=LAYOUT["header_pady"],
        )

        self._build_customer_card(page_padding)
        self._build_summary_card(page_padding)
        self._build_form_card(page_padding)

    # ------------------------------------------------------------------
    # Pilih pelanggan
    # ------------------------------------------------------------------

    def _build_customer_card(self, page_padding):
        card = SectionCard(self)
        card.pack(
            fill="x",
            padx=page_padding,
            pady=(0, SPACING["lg"]),
        )

        ctk.CTkLabel(
            card.body,
            text="Pelanggan",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        self.customer_button = CustomerSelector(
            card.body,
            command=self._open_customer_picker,
        )
        self.customer_button.pack(fill="x", pady=(SPACING["xs"], 0))

    def _open_customer_picker(self):
        CustomerPickerDialog(
            self,
            self.customer_model,
            on_select=self._handle_customer_selected,
        )

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self.customer_button.set_customer(customer)

        self.error_label.clear()

        self._refresh_summary()

    # ------------------------------------------------------------------
    # Kartu ringkasan
    # ------------------------------------------------------------------

    def _build_summary_card(self, page_padding):
        self.summary_card = StatCard(self, "Sisa Hutang")
        self.summary_card.pack(
            fill="x",
            padx=page_padding,
            pady=(0, SPACING["lg"]),
        )

    def _set_summary(self, sisa=None):
        if sisa is None:
            self.summary_card.set_value("-")
            return

        self.summary_card.set_value(
            format_rupiah(sisa),
            color=COLORS["danger"] if sisa > 0 else COLORS["success"],
        )

    def _refresh_summary(self):
        if not self.selected_customer:
            self.current_sisa = 0
            self._set_summary(None)
            return

        try:
            _, _, sisa = self.payment_model.get_balance(
                self.selected_customer["id"]
            )
        except Exception as exc:
            log_error(
                "Gagal memuat saldo pelanggan.\n"
                f"customer_id={self.selected_customer['id']}\n"
                f"{type(exc).__name__}: {exc}"
            )
            self._set_summary(None)
            self.error_label.show(
                "Gagal memuat saldo pelanggan. Coba lagi."
            )
            return

        self.current_sisa = sisa

        self._set_summary(sisa)
        self._update_preview()

    # ------------------------------------------------------------------
    # Form pembayaran
    # ------------------------------------------------------------------

    def _build_form_card(self, page_padding):
        card = SectionCard(self)
        card.pack(
            fill="x",
            padx=page_padding,
            pady=(0, page_padding),
        )

        body = card.body

        # Jumlah pembayaran (kiri) + sisa setelah pembayaran (kanan)
        row = ctk.CTkFrame(
            body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1), weight=1, uniform="pay")

        self.amount_field = FormField(
            row,
            "Jumlah Pembayaran",
            "Contoh: 50000",
            required=True,
        )
        self.amount_field.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, SPACING["sm"]),
        )
        self.amount_entry = self.amount_field.entry
        self.amount_entry.bind(
            "<KeyRelease>",
            lambda _event: self._update_preview(),
        )

        preview = ctk.CTkFrame(
            row,
            fg_color="transparent",
            width=0,
            height=0,
        )
        preview.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(SPACING["sm"], 0),
        )

        ctk.CTkLabel(
            preview,
            text="Sisa Setelah Pembayaran",
            font=get_font("button_small"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        box = ctk.CTkFrame(
            preview,
            height=INPUT_HEIGHT,
            fg_color=COLORS["surface_hover"],
            corner_radius=RADIUS["input"],
        )
        box.pack(fill="x", pady=(SPACING["xs"], 0))
        box.pack_propagate(False)

        self.preview_label = ctk.CTkLabel(
            box,
            text="-",
            font=get_font("button"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.preview_label.pack(
            fill="both",
            expand=True,
            padx=SPACING["md"],
        )

        # Catatan
        self.notes_field = FormField(
            body,
            "Catatan",
            "Catatan pembayaran (opsional)",
        )
        self.notes_field.pack(fill="x", pady=(SPACING["md"], 0))
        self.notes_entry = self.notes_field.entry

        # Error validasi
        self.error_label = ErrorText(body)
        self.error_label.pack(fill="x", pady=(SPACING["sm"], 0))

        # Tombol simpan
        footer = ctk.CTkFrame(
            body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        footer.pack(fill="x", pady=(SPACING["md"], 0))

        ctk.CTkButton(
            footer,
            text="Simpan Pembayaran",
            width=170,
            command=self._handle_save,
            **button_style("primary"),
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self):
        if not self.selected_customer:
            self.preview_label.configure(
                text="-",
                text_color=COLORS["text"],
            )
            return

        amount_text = self.amount_entry.get().strip()

        if not amount_text:
            self.preview_label.configure(
                text=format_rupiah(self.current_sisa),
                text_color=COLORS["text"],
            )
            return

        try:
            amount = int(round(float(amount_text)))
        except ValueError:
            self.preview_label.configure(
                text="-",
                text_color=COLORS["text"],
            )
            return

        remaining = self.current_sisa - amount

        self.preview_label.configure(
            text=format_rupiah(remaining),
            text_color=(
                COLORS["danger"] if remaining < 0 else COLORS["text"]
            ),
        )

    # ------------------------------------------------------------------
    # Simpan pembayaran
    # ------------------------------------------------------------------

    def _handle_save(self):
        if self._saving_payment:
            return

        self._saving_payment = True

        try:
            self.error_label.clear()

            if not self.selected_customer:
                self.error_label.show(
                    "Pelanggan harus dipilih terlebih dahulu."
                )
                return

            amount_text = self.amount_entry.get().strip()
            notes = self.notes_entry.get().strip()

            try:
                success, message, _ = self.payment_model.create_payment(
                    self.selected_customer["id"],
                    amount_text,
                    notes=notes,
                )
            except Exception as exc:
                log_error(
                    "Gagal menyimpan pembayaran.\n"
                    f"customer_id={self.selected_customer['id']}\n"
                    f"{type(exc).__name__}: {exc}"
                )
                show_error(
                    self,
                    "Terjadi Kesalahan",
                    "Terjadi kesalahan pada database. Coba lagi.",
                )
                return

            if not success:
                self.error_label.show(message)
                return

            self._reset_form()

            show_success(self, "Pembayaran", message)

        finally:
            self._saving_payment = False

    def _reset_form(self):
        self.selected_customer = None
        self.current_sisa = 0

        self.customer_button.set_customer(None)

        self.amount_entry.delete(0, "end")
        self.notes_entry.delete(0, "end")

        self._set_summary(None)
        self._update_preview()