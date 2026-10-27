import customtkinter as ctk

from components.badges import amount_style
from components.cards import SectionCard, StatRow
from components.detail_dialogs import DebtDetailDialog, PaymentDetailDialog
from components.dialogs import (
    BaseDialog,
    ConfirmDialog,
    show_error,
    show_warning,
)
from components.forms import (
    ErrorText,
    FormField,
    FormLabel,
    SearchBar,
    option_menu_style,
)
from components.page_header import PageHeader
from components.tables import DataTable, SimpleTable, text_cell
from models.customer import NO_GROUP, CustomerModel
from models.debt import DebtModel
from models.payment import PaymentModel
from utils.formatter import format_rupiah, format_date_indonesia
from utils.printer import Printer, PrinterError
from utils.theme import (
    BUTTON_WIDTH,
    COLORS,
    DIALOG_HEIGHT,
    DIALOG_WIDTH,
    LAYOUT,
    SPACING,
    action_button_style,
    button_style,
    get_font,
)


# Tidak ada kolom Aksi: klik dua kali baris membuka dialog Detail,
# dan Edit / Nonaktifkan ada di dalam dialog itu.
CUSTOMER_COLUMNS = [
    {"title": "Pelanggan", "weight": 5, "align": "left"},
    {"title": "Kelompok", "weight": 3, "align": "left"},
    {"title": "Sisa Hutang", "weight": 3, "align": "right"},
    {"title": "Status", "weight": 2, "align": "left"},
]

# Riwayat di dialog Detail: klik dua kali baris membuka detail transaksinya.
TIMELINE_COLUMNS = [
    {"title": "Tanggal", "weight": 2, "align": "left"},
    {"title": "Jenis", "weight": 2, "align": "left"},
    {"title": "Referensi", "weight": 3, "align": "left"},
    {"title": "Jumlah", "weight": 2, "align": "right"},
]

# Warna titik di kolom kiri tabel per jenis transaksi.
# Samakan dengan TYPE_VARIANTS di views/history.py dan views/dashboard.py.
TYPE_VARIANTS = {
    "Hutang": "warning",
    "Pembayaran": "success",
    "Pembelian": "neutral",
    "Penjualan": "info",
}

ACTIVATE_HINT = "Klik dua kali pelanggan untuk melihat detail."
TIMELINE_HINT = "Klik dua kali transaksi untuk melihat detail."

# Pilihan khusus pada filter dan form kelompok.
ALL_GROUPS = "Semua Kelompok"
NO_GROUP_LABEL = "Tanpa Kelompok"
RESERVED_GROUP_NAMES = {ALL_GROUPS.lower(), NO_GROUP_LABEL.lower()}

GROUP_FILTER_WIDTH = 190

# Jeda (ms) setelah berhenti mengetik sebelum daftar dicari ulang.
SEARCH_DELAY = 250


def _reserved_name_error(name: str):
    """Nama kelompok tidak boleh sama dengan pilihan khusus filter."""
    if " ".join((name or "").split()).lower() in RESERVED_GROUP_NAMES:
        return "Nama kelompok ini dipakai oleh sistem. Gunakan nama lain."

    return None


class CustomersPage(ctk.CTkFrame):
    def __init__(self, master, customer_model: CustomerModel):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.customer_model = customer_model
        self.debt_model = DebtModel(customer_model.db)
        self.payment_model = PaymentModel(customer_model.db)

        self.search_var = ctk.StringVar()
        self.group_var = ctk.StringVar(value=ALL_GROUPS)

        self._groups = []
        self._group_ids = {}
        self._customers = []
        self._search_job = None

        self._build_header()
        self._build_summary()
        self._build_customer_section()

        self.refresh()

    def destroy(self):
        self._cancel_search()
        super().destroy()

    # =========================================================
    # HEADER
    # =========================================================

    def _build_header(self):
        header = PageHeader(self, "Pelanggan")
        header.pack(
            fill="x",
            padx=LAYOUT["page_padding"],
            pady=LAYOUT["header_pady"],
        )

        # Tombol utama dipasang lebih dulu (paling kanan).
        header.add_button(
            "Tambah Pelanggan",
            self._open_add_dialog,
            plus=True,
        )
        header.add_button(
            "Kelola Kelompok",
            self._open_group_manager,
            variant="secondary",
        )

    # =========================================================
    # SUMMARY
    # =========================================================

    def _build_summary(self):
        self.summary_row = StatRow(
            self,
            ["Total Pelanggan", "Masih Berhutang", "Lunas"],
        )
        self.summary_row.pack(
            fill="x",
            padx=LAYOUT["page_padding"],
            pady=(0, LAYOUT["section_gap"]),
        )

    # =========================================================
    # CUSTOMER SECTION
    # =========================================================

    def _build_customer_section(self):
        section = SectionCard(self)
        section.pack(
            fill="both",
            expand=True,
            padx=LAYOUT["page_padding"],
            pady=(0, LAYOUT["page_padding"]),
        )

        toolbar = ctk.CTkFrame(
            section.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        toolbar.pack(
            fill="x",
            pady=(0, SPACING["md"]),
        )

        self.search_entry = SearchBar(
            toolbar,
            self.search_var,
            "Cari pelanggan...",
        )
        self.search_entry.pack(side="left")

        self.search_var.trace_add(
            "write",
            lambda *_: self._schedule_refresh(),
        )

        self.group_menu = ctk.CTkOptionMenu(
            toolbar,
            values=[ALL_GROUPS, NO_GROUP_LABEL],
            variable=self.group_var,
            width=GROUP_FILTER_WIDTH,
            command=lambda _value: self.refresh(),
            **option_menu_style(),
        )
        self.group_menu.pack(side="left", padx=(SPACING["sm"], 0))

        ctk.CTkLabel(
            toolbar,
            text=ACTIVATE_HINT,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(side="right")

        self.table = DataTable(
            section.body,
            CUSTOMER_COLUMNS,
            empty_title="Belum ada pelanggan",
            empty_text=(
                "Tambahkan pelanggan untuk mulai mencatat "
                "transaksi hutang."
            ),
            search_empty_title="Pelanggan tidak ditemukan",
            search_empty_text=(
                "Tidak ada pelanggan yang cocok dengan pencarian "
                "atau kelompok ini."
            ),
            on_activate=self._on_activate,
            show_dot=True,
        )
        self.table.pack(fill="both", expand=True)

    # =========================================================
    # KELOMPOK
    # =========================================================

    def _reload_groups(self):
        """Muat ulang daftar kelompok ke pilihan filter."""
        try:
            self._groups = self.customer_model.list_groups()
        except Exception:
            self._groups = []

        self._group_ids = {
            group["name"]: group["id"] for group in self._groups
        }

        values = [ALL_GROUPS, NO_GROUP_LABEL] + [
            group["name"] for group in self._groups
        ]

        self.group_menu.configure(values=values)

        # Kelompok yang dipilih mungkin baru saja dihapus.
        if self.group_var.get() not in values:
            self.group_var.set(ALL_GROUPS)

    def _selected_group_filter(self):
        """None (semua) | NO_GROUP | id kelompok."""
        label = self.group_var.get()

        if label == ALL_GROUPS:
            return None

        if label == NO_GROUP_LABEL:
            return NO_GROUP

        return self._group_ids.get(label)

    def _default_group_id(self):
        """Saat memfilter satu kelompok, pelanggan baru ikut kelompok itu."""
        selected = self._selected_group_filter()

        if isinstance(selected, int) and selected > 0:
            return selected

        return None

    def _open_group_manager(self):
        GroupManagerDialog(
            self,
            self.customer_model,
            on_change=self.refresh,
        )

    # =========================================================
    # REFRESH
    # =========================================================

    def _cancel_search(self):
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass

            self._search_job = None

    def _schedule_refresh(self):
        self._cancel_search()
        self._search_job = self.after(SEARCH_DELAY, self.refresh)

    def refresh(self):
        self._search_job = None

        self._reload_groups()

        search = self.search_var.get()
        group_filter = self._selected_group_filter()

        try:
            customers = self.customer_model.list_customers(
                search=search,
                group_id=group_filter,
            )
        except Exception as exc:
            self._customers = []
            self.table.set_error(
                "Gagal memuat data pelanggan",
                str(exc),
            )
            return

        self._customers = list(customers)

        self._update_summary(self._customers)

        self.table.set_rows(
            [self._row_values(customer) for customer in self._customers],
            variants=[
                "success" if customer["status"] == "Lunas" else "warning"
                for customer in self._customers
            ],
            searching=bool(search.strip()) or group_filter is not None,
        )

    def _update_summary(self, customers):
        total = len(customers)

        debt_count = sum(
            1
            for customer in customers
            if customer["sisa"] > 0
        )

        paid_count = total - debt_count

        self.summary_row.set(0, str(total))
        self.summary_row.set(1, str(debt_count))
        self.summary_row.set(2, str(paid_count))

    # =========================================================
    # TABLE ROW
    # =========================================================

    @staticmethod
    def _row_values(customer: dict) -> list:
        name = customer["name"].strip()
        notes = customer["notes"] or ""

        if len(notes) > 42:
            notes = notes[:42] + "..."

        display_name = (
            f"{name} ({notes})"
            if notes
            else name
        )

        return [
            display_name,
            customer.get("group_name") or "-",
            format_rupiah(customer["sisa"]),
            customer["status"],
        ]

    def _on_activate(self, index: int):
        if 0 <= index < len(self._customers):
            customer = self._customers[index]
            self._open_detail_dialog(customer["id"], customer)

    # =========================================================
    # ADD / EDIT CUSTOMER
    # =========================================================

    def _open_add_dialog(self):
        CustomerFormDialog(
            self,
            title="Tambah Pelanggan",
            on_submit=self._handle_add,
            groups=self._groups,
            initial={"group_id": self._default_group_id()},
        )

    def _open_edit_dialog(self, customer: dict):
        CustomerFormDialog(
            self,
            title="Edit Pelanggan",
            initial={
                "name": customer["name"],
                "notes": customer["notes"] or "",
                "group_id": customer.get("group_id"),
            },
            groups=self._groups,
            on_submit=lambda data: self._handle_edit(
                customer["id"],
                data,
            ),
        )

    def _handle_add(self, data: dict):
        return self.customer_model.add_customer(
            name=data["name"],
            phone="",
            notes=data["notes"],
            group_id=data["group_id"],
        )[:2]

    def _handle_edit(self, customer_id: int, data: dict):
        return self.customer_model.update_customer(
            customer_id,
            name=data["name"],
            phone="",
            notes=data["notes"],
            group_id=data["group_id"],
        )

    # =========================================================
    # DEACTIVATE
    # =========================================================

    def _confirm_deactivate(self, customer: dict, on_done=None):
        ConfirmDialog(
            self,
            title="Nonaktifkan Pelanggan",
            message=(
                f'Apakah Anda yakin ingin menonaktifkan '
                f'pelanggan "{customer["name"]}"?\n\n'
                "Pelanggan tidak akan muncul pada transaksi baru, "
                "tetapi seluruh riwayat hutang tetap tersimpan."
            ),
            confirm_text="Nonaktifkan",
            on_confirm=lambda: self._handle_deactivate(
                customer["id"],
                on_done,
            ),
        )

    def _handle_deactivate(self, customer_id: int, on_done=None):
        try:
            result = self.customer_model.deactivate_customer(
                customer_id
            )

            if not result:
                show_error(
                    self,
                    "Gagal",
                    "Pelanggan tidak dapat dinonaktifkan.",
                )
                return

            self.refresh()

            # Tutup dialog Detail yang memicu penonaktifan.
            if on_done:
                on_done()

        except Exception as exc:
            show_error(
                self,
                "Gagal",
                f"Gagal menonaktifkan pelanggan:\n{exc}",
            )

    # =========================================================
    # DETAIL
    # =========================================================

    def _open_detail_dialog(self, customer_id: int, customer: dict = None):
        try:
            detail = self.customer_model.get_detail(
                customer_id
            )

            if not detail:
                show_warning(
                    self,
                    "Data Tidak Ditemukan",
                    "Data pelanggan tidak ditemukan.",
                )
                return

            CustomerDetailDialog(
                self,
                detail=detail,
                on_open_debt=self._open_debt_detail,
                on_open_payment=self._open_payment_detail,
                on_edit=(
                    (lambda: self._open_edit_dialog(customer))
                    if customer
                    else None
                ),
                on_deactivate=(
                    (lambda on_done: self._confirm_deactivate(
                        customer,
                        on_done,
                    ))
                    if customer
                    else None
                ),
            )

        except Exception as exc:
            show_error(
                self,
                "Gagal",
                f"Gagal membuka detail pelanggan:\n{exc}",
            )

    def _open_debt_detail(self, transaction_id: int):
        try:
            detail = self.debt_model.get_transaction_detail(
                transaction_id
            )

            if not detail:
                show_warning(
                    self,
                    "Data Tidak Ditemukan",
                    "Detail transaksi hutang tidak ditemukan.",
                )
                return

            DebtDetailDialog(
                self,
                detail=detail,
            )

        except Exception as exc:
            show_error(
                self,
                "Gagal",
                f"Gagal membuka detail hutang:\n{exc}",
            )

    def _open_payment_detail(self, payment_id: int):
        try:
            detail = self.payment_model.get_payment_detail(
                payment_id
            )

            if not detail:
                show_warning(
                    self,
                    "Data Tidak Ditemukan",
                    "Detail pembayaran tidak ditemukan.",
                )
                return

            PaymentDetailDialog(
                self,
                detail=detail,
            )

        except Exception as exc:
            show_error(
                self,
                "Gagal",
                f"Gagal membuka detail pembayaran:\n{exc}",
            )


# =============================================================
# DIALOG TAMBAH / EDIT
# =============================================================

class CustomerFormDialog(BaseDialog):
    """Dialog tambah/edit pelanggan (nama, kelompok, catatan)."""

    def __init__(
        self,
        master: CustomersPage,
        title: str,
        on_submit,
        groups: list = None,
        initial: dict = None,
    ):
        super().__init__(master, title, DIALOG_WIDTH["form"])

        self.master_page = master
        self.on_submit = on_submit
        initial = initial or {}

        self.name_field = FormField(
            self.body,
            "Nama Pelanggan",
            "Masukkan nama pelanggan",
            initial.get("name", ""),
            required=True,
        )
        self.name_field.pack(fill="x")

        # Kelompok
        self._group_ids = {
            group["name"]: group["id"] for group in (groups or [])
        }
        values = [NO_GROUP_LABEL] + list(self._group_ids)

        initial_group = NO_GROUP_LABEL

        for name, group_id in self._group_ids.items():
            if group_id == initial.get("group_id"):
                initial_group = name

        self.group_var = ctk.StringVar(value=initial_group)

        group_block = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        group_block.pack(fill="x", pady=(SPACING["md"], 0))

        FormLabel(group_block, "Kelompok").pack(fill="x")

        self.group_menu = ctk.CTkOptionMenu(
            group_block,
            values=values,
            variable=self.group_var,
            **option_menu_style(),
        )
        self.group_menu.pack(fill="x", pady=(SPACING["xs"], 0))

        self.notes_field = FormField(
            self.body,
            "Catatan",
            "Contoh: pelanggan tetap",
            initial.get("notes", ""),
        )
        self.notes_field.pack(
            fill="x",
            pady=(SPACING["md"], 0),
        )

        self.name_entry = self.name_field.entry
        self.notes_entry = self.notes_field.entry

        self.error_label = ErrorText(self.body)
        self.error_label.pack(
            fill="x",
            pady=(SPACING["sm"], 0),
        )

        self.set_buttons("Simpan", self._submit)
        self.finish()

        self.after(100, self.name_entry.focus)

    def _submit(self):
        data = {
            "name": self.name_entry.get().strip(),
            "notes": self.notes_entry.get().strip(),
            "group_id": self._group_ids.get(self.group_var.get()),
        }

        try:
            success, message = self.on_submit(data)

        except Exception:
            self.error_label.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not success:
            self.error_label.show(message)
            return

        self.master_page.refresh()
        self.destroy()


# =============================================================
# DIALOG KELOLA KELOMPOK
# =============================================================

class GroupNameDialog(BaseDialog):
    """Dialog kecil untuk mengubah nama kelompok."""

    def __init__(self, master, title: str, initial: str, on_submit):
        super().__init__(master, title, DIALOG_WIDTH["form"])

        self.on_submit = on_submit

        self.name_field = FormField(
            self.body,
            "Nama Kelompok",
            "Contoh: Tetangga",
            initial,
            required=True,
        )
        self.name_field.pack(fill="x")

        self.error_label = ErrorText(self.body)
        self.error_label.pack(
            fill="x",
            pady=(SPACING["sm"], 0),
        )

        self.set_buttons("Simpan", self._submit)
        self.finish()

        self.after(100, self.name_field.focus)

    def _submit(self):
        try:
            success, message = self.on_submit(self.name_field.get())

        except Exception:
            self.error_label.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not success:
            self.error_label.show(message)
            return

        self.destroy()


class GroupManagerDialog(BaseDialog):
    """Tambah, ubah nama, dan hapus kelompok pelanggan."""

    COLUMNS = [
        {"title": "Kelompok", "weight": 4, "align": "left"},
        {"title": "Anggota", "weight": 2, "align": "right"},
        {"title": "Aksi", "weight": 4, "align": "center"},
    ]

    def __init__(self, master, customer_model, on_change):
        super().__init__(
            master,
            "Kelola Kelompok",
            DIALOG_WIDTH["form"],
            height=DIALOG_HEIGHT["picker"],
        )

        self.customer_model = customer_model
        self.on_change = on_change

        add_row = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        add_row.pack(fill="x")
        add_row.grid_columnconfigure(0, weight=1)

        self.name_field = FormField(
            add_row,
            "Kelompok Baru",
            "Contoh: Tetangga",
        )
        self.name_field.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, SPACING["sm"]),
        )
        self.name_field.entry.bind(
            "<Return>",
            lambda _event: self._add(),
        )

        ctk.CTkButton(
            add_row,
            text="Tambah",
            width=BUTTON_WIDTH["dialog"],
            command=self._add,
            **button_style("primary"),
        ).grid(row=0, column=1, sticky="s")

        self.error_label = ErrorText(self.body)
        self.error_label.pack(
            fill="x",
            pady=(SPACING["sm"], SPACING["md"]),
        )

        self.table = SimpleTable(
            self.body,
            self.COLUMNS,
            empty_title="Belum ada kelompok",
            empty_text=(
                "Tambahkan kelompok pertama di atas, "
                "misalnya Tetangga atau Pegawai."
            ),
            scrollable=True,
        )
        self.table.pack(fill="both", expand=True)

        self.set_close_button("Tutup")
        self.finish()

        self._render()
        self.after(100, self.name_field.focus)

    # ------------------------------------------------------------------
    def _render(self):
        try:
            groups = self.customer_model.list_groups()
        except Exception:
            self.table.set_error(
                "Gagal memuat kelompok",
                "Terjadi kesalahan saat membaca data kelompok.",
            )
            return

        self.table.set_rows(
            [
                [
                    text_cell(group["name"], bold=True),
                    text_cell(str(group["member_count"])),
                    lambda parent, g=group: self._build_actions(parent, g),
                ]
                for group in groups
            ]
        )

    def _build_actions(self, parent, group: dict):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )

        ctk.CTkButton(
            frame,
            text="Ubah",
            command=lambda: self._open_rename(group),
            **action_button_style("edit"),
        ).pack(side="left", padx=(0, SPACING["xs"]))

        ctk.CTkButton(
            frame,
            text="Hapus",
            command=lambda: self._confirm_delete(group),
            **action_button_style("delete"),
        ).pack(side="left", padx=(SPACING["xs"], 0))

        return frame

    def _changed(self):
        self._render()
        self.on_change()

    # ------------------------------------------------------------------
    # Tambah
    # ------------------------------------------------------------------
    def _add(self):
        self.error_label.clear()

        name = self.name_field.get()

        error = _reserved_name_error(name)

        if error:
            self.error_label.show(error)
            return

        try:
            success, message, _ = self.customer_model.add_group(name)

        except Exception:
            self.error_label.show(
                "Terjadi kesalahan pada database. Coba lagi."
            )
            return

        if not success:
            self.error_label.show(message)
            return

        self.name_field.set("")
        self._changed()

    # ------------------------------------------------------------------
    # Ubah nama
    # ------------------------------------------------------------------
    def _open_rename(self, group: dict):
        GroupNameDialog(
            self,
            "Ubah Nama Kelompok",
            group["name"],
            on_submit=lambda name: self._do_rename(group["id"], name),
        )

    def _do_rename(self, group_id: int, name: str):
        error = _reserved_name_error(name)

        if error:
            return False, error

        success, message = self.customer_model.rename_group(group_id, name)

        if success:
            self._changed()

        return success, message

    # ------------------------------------------------------------------
    # Hapus
    # ------------------------------------------------------------------
    def _confirm_delete(self, group: dict):
        count = group["member_count"]

        if count:
            note = (
                f"{count} pelanggan di kelompok ini tidak ikut terhapus; "
                'mereka akan menjadi "Tanpa Kelompok".'
            )
        else:
            note = "Kelompok ini tidak memiliki anggota."

        ConfirmDialog(
            self,
            title="Hapus Kelompok",
            message=f'Hapus kelompok "{group["name"]}"?\n\n{note}',
            confirm_text="Hapus",
            on_confirm=lambda: self._do_delete(group["id"]),
        )

    def _do_delete(self, group_id: int):
        try:
            success, message, _ = self.customer_model.delete_group(group_id)

        except Exception:
            show_error(
                self,
                "Gagal",
                "Terjadi kesalahan pada database. Coba lagi.",
            )
            return

        if not success:
            show_error(self, "Gagal", message)
            return

        self._changed()


# =============================================================
# DIALOG DETAIL PELANGGAN
# =============================================================

class CustomerDetailDialog(BaseDialog):
    """
    Ringkasan saldo + riwayat pelanggan.

    Footer:  [Nonaktifkan]                [Edit] [Tutup] [Cetak Riwayat]
    Edit dan Nonaktifkan hanya tampil bila callback-nya diberikan.
    Riwayat: klik dua kali baris membuka detail hutang / pembayaran.
    """

    def __init__(
        self,
        master,
        detail: dict,
        on_open_debt=None,
        on_open_payment=None,
        on_edit=None,
        on_deactivate=None,
    ):
        super().__init__(
            master,
            f"Detail - {detail['name']}",
            DIALOG_WIDTH["detail"],
            height=DIALOG_HEIGHT["detail"],
            heading=detail["name"],
        )

        self.detail = detail
        self.on_open_debt = on_open_debt
        self.on_open_payment = on_open_payment
        self.on_edit = on_edit
        self.on_deactivate = on_deactivate
        self._timeline = []

        if detail.get("group_name"):
            ctk.CTkLabel(
                self.body,
                text=f"Kelompok: {detail['group_name']}",
                font=get_font("body"),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(fill="x", pady=(0, SPACING["md"]))

        self._build_summary(detail)

        title_row = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        title_row.pack(
            fill="x",
            pady=(SPACING["lg"], SPACING["sm"]),
        )

        ctk.CTkLabel(
            title_row,
            text="Riwayat",
            font=get_font("subheading"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text=TIMELINE_HINT,
            font=get_font("small"),
            text_color=COLORS["text_secondary"],
        ).pack(side="right")

        self._build_timeline(detail["timeline"])

        self.set_buttons(
            "Cetak Riwayat",
            self._print_history,
            "Tutup",
            primary_width=BUTTON_WIDTH["header"] - 40,
        )
        self._add_manage_buttons()
        self.finish()

    # ------------------------------------------------------------------
    # Edit / Nonaktifkan
    # ------------------------------------------------------------------
    def _add_manage_buttons(self):
        if self.on_edit:
            ctk.CTkButton(
                self.footer,
                text="Edit",
                command=self._edit,
                width=BUTTON_WIDTH["dialog"],
                **button_style("secondary"),
            ).pack(side="right", padx=(0, SPACING["sm"]))

        if self.on_deactivate:
            ctk.CTkButton(
                self.footer,
                text="Nonaktifkan",
                command=lambda: self.on_deactivate(self.destroy),
                width=BUTTON_WIDTH["confirm"],
                **button_style("danger"),
            ).pack(side="left")

    def _edit(self):
        # Tutup dulu: data di dialog ini akan usang setelah diedit.
        self.destroy()
        self.on_edit()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _build_summary(self, detail: dict):
        row = StatRow(
            self.body,
            ["Total Hutang", "Total Pembayaran", "Sisa Hutang"],
        )
        row.pack(fill="x")

        row.set(0, format_rupiah(detail["total_debt"]))
        row.set(1, format_rupiah(detail["total_paid"]))
        row.set(2, format_rupiah(detail["sisa"]))

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------
    def _build_timeline(self, timeline: list):
        self._timeline = list(timeline or [])

        table = DataTable(
            self.body,
            TIMELINE_COLUMNS,
            empty_title="Belum ada riwayat",
            empty_text="Belum ada riwayat transaksi.",
            on_activate=self._on_timeline_activate,
            show_dot=True,
        )
        table.pack(fill="both", expand=True)

        table.set_rows(
            [self._timeline_values(entry) for entry in self._timeline],
            variants=[
                TYPE_VARIANTS.get(entry["type"], "neutral")
                for entry in self._timeline
            ],
        )

    @staticmethod
    def _timeline_values(entry: dict) -> list:
        entry_type = entry["type"]
        sign, _color = amount_style(entry_type)

        if entry_type == "Hutang":
            reference = entry.get("transaction_number") or "Transaksi lama"
        elif entry_type == "Pembayaran":
            reference = "Pembayaran"
        else:
            reference = "-"

        return [
            format_date_indonesia(entry["date"]),
            entry_type,
            reference,
            f"{sign} {format_rupiah(entry['amount'])}".strip(),
        ]

    def _on_timeline_activate(self, index: int):
        if not (0 <= index < len(self._timeline)):
            return

        entry = self._timeline[index]

        if entry["type"] == "Hutang":
            self._open_debt(entry["id"])

        elif entry["type"] == "Pembayaran":
            self._open_payment(entry["id"])

    # ------------------------------------------------------------------
    # Cetak Riwayat
    # ------------------------------------------------------------------
    def _print_history(self):
        try:
            printer = Printer()

            customer_name = (
                self.detail.get("name")
                or "Pelanggan"
            )

            customer_id = self.detail.get("id")

            pdf_path = printer.create_pdf(
                "customer_history",
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "total_debt": self.detail.get(
                        "total_debt",
                        0,
                    ),
                    "total_paid": self.detail.get(
                        "total_paid",
                        0,
                    ),
                    "sisa": self.detail.get(
                        "sisa",
                        0,
                    ),
                    "timeline": self.detail.get(
                        "timeline"
                    ) or [],
                },
            )

            printer.open_pdf(pdf_path)

        except PrinterError as exc:
            show_error(self, "Cetak Gagal", str(exc))

        except Exception as exc:
            show_error(
                self,
                "Cetak Gagal",
                f"Gagal membuka dokumen riwayat pelanggan:\n{exc}",
            )

    # ------------------------------------------------------------------
    # Open Detail
    # ------------------------------------------------------------------
    def _open_debt(self, transaction_id: int):
        if self.on_open_debt:
            self.on_open_debt(transaction_id)

    def _open_payment(self, payment_id: int):
        if self.on_open_payment:
            self.on_open_payment(payment_id)