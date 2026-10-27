import customtkinter as ctk

from components.badges import customer_status_variant
from components.dialogs import BaseDialog
from components.forms import SearchBar, entry_style, option_menu_style
from components.tables import DataTable
from models.customer import NO_GROUP
from utils.theme import (
    COLORS,
    DIALOG_HEIGHT,
    DIALOG_WIDTH,
    SPACING,
)

CUSTOMER_PLACEHOLDER = "Cari / Pilih Pelanggan..."

# Pilihan khusus pada filter kelompok (sama dengan halaman Pelanggan).
ALL_GROUPS = "Semua Kelompok"
NO_GROUP_LABEL = "Tanpa Kelompok"

PICKER_WIDTH = DIALOG_WIDTH.get("picker", 600)
GROUP_FILTER_WIDTH = 190

# Jeda (ms) setelah berhenti mengetik sebelum daftar dicari ulang.
SEARCH_DELAY = 150

PICKER_COLUMNS = [
    {"title": "Pelanggan", "weight": 5, "align": "left"},
    {"title": "Kelompok", "weight": 3, "align": "left"},
    {"title": "Status", "weight": 3, "align": "left"},
]


def customer_selector_style() -> dict:
    """Tombol yang tampil seperti input (untuk pemilih pelanggan)."""
    base = entry_style()

    return {
        "height": base["height"],
        "corner_radius": base["corner_radius"],
        "border_width": base["border_width"],
        "border_color": base["border_color"],
        "fg_color": base["fg_color"],
        "hover_color": COLORS["surface_hover"],
        "font": base["font"],
    }


class CustomerSelector(ctk.CTkButton):
    """
    Tombol pemilih pelanggan standar.

        selector = CustomerSelector(parent, command=self._open_picker)
        selector.set_customer(customer)   # dict dengan key "name"
        selector.set_customer(None)       # kembali ke placeholder
    """

    def __init__(self, master, command, placeholder: str = CUSTOMER_PLACEHOLDER):
        self.placeholder = placeholder

        super().__init__(
            master,
            text=placeholder,
            anchor="w",
            command=command,
            **customer_selector_style(),
        )
        self.set_customer(None)

    def set_customer(self, customer):
        if customer:
            self.configure(
                text=customer["name"],
                text_color=COLORS["text"],
            )
        else:
            self.configure(
                text=self.placeholder,
                text_color=COLORS["text_muted"],
            )


class CustomerPickerDialog(BaseDialog):
    """
    Dialog untuk mencari dan memilih pelanggan.

    Daftar berupa tabel (Treeview) sehingga tetap cepat walau pelanggan
    banyak. Bisa dicari berdasarkan nama dan difilter berdasarkan kelompok.

    Cara memilih:
      - klik dua kali baris, atau
      - pilih baris lalu tekan Enter / tombol Pilih, atau
      - ketik pencarian lalu Enter (memilih baris yang tersorot, awalnya
        baris pertama). Panah bawah di kolom cari memindahkan fokus ke daftar.
    """

    def __init__(
        self,
        master,
        customer_model,
        on_select,
    ):
        super().__init__(
            master,
            "Pilih Pelanggan",
            PICKER_WIDTH,
            height=DIALOG_HEIGHT["picker"],
        )

        self.customer_model = customer_model
        self.on_select = on_select
        self._customers = []
        self._group_ids = {}
        self._search_job = None

        self.search_var = ctk.StringVar()
        self.group_var = ctk.StringVar(value=ALL_GROUPS)

        # --------------------------------------------------------------
        # Baris pencarian + filter kelompok
        # --------------------------------------------------------------
        toolbar = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        toolbar.pack(fill="x", pady=(0, SPACING["md"]))
        toolbar.grid_columnconfigure(0, weight=1)

        self.search_entry = SearchBar(
            toolbar,
            self.search_var,
            "Cari nama pelanggan...",
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")

        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Down>", self._focus_list)

        self.group_menu = ctk.CTkOptionMenu(
            toolbar,
            values=[ALL_GROUPS, NO_GROUP_LABEL],
            variable=self.group_var,
            width=GROUP_FILTER_WIDTH,
            command=lambda _value: self._render_now(),
            **option_menu_style(),
        )
        self.group_menu.grid(
            row=0,
            column=1,
            padx=(SPACING["sm"], 0),
        )

        # --------------------------------------------------------------
        # Daftar pelanggan
        # --------------------------------------------------------------
        self.table = DataTable(
            self.body,
            PICKER_COLUMNS,
            empty_title="Belum ada pelanggan",
            empty_text="Tambahkan pelanggan terlebih dahulu di menu Pelanggan.",
            search_empty_title="Pelanggan tidak ditemukan",
            search_empty_text="Coba nama atau kelompok yang berbeda.",
            on_activate=self._select_index,
            show_dot=True,
        )
        self.table.pack(fill="both", expand=True)

        self.search_var.trace_add(
            "write",
            lambda *_: self._schedule_render(),
        )

        self.set_buttons("Pilih", self._select_current, "Batal")
        self.finish()

        self._load_groups()
        self._render_list()
        self.after(100, self.search_entry.focus)

    # ------------------------------------------------------------------
    # Kelompok
    # ------------------------------------------------------------------
    def _load_groups(self):
        try:
            groups = self.customer_model.list_groups()
        except Exception:
            groups = []

        self._group_ids = {group["name"]: group["id"] for group in groups}

        self.group_menu.configure(
            values=[ALL_GROUPS, NO_GROUP_LABEL] + list(self._group_ids)
        )

    def _selected_group_filter(self):
        """None (semua) | NO_GROUP | id kelompok."""
        label = self.group_var.get()

        if label == ALL_GROUPS:
            return None

        if label == NO_GROUP_LABEL:
            return NO_GROUP

        return self._group_ids.get(label)

    # ------------------------------------------------------------------
    # Pencarian
    # ------------------------------------------------------------------
    def _schedule_render(self):
        self._cancel_pending()
        self._search_job = self.after(SEARCH_DELAY, self._render_list)

    def _cancel_pending(self):
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass

            self._search_job = None

    def _render_now(self):
        self._cancel_pending()
        self._render_list()

    def destroy(self):
        self._cancel_pending()
        super().destroy()

    def _render_list(self):
        self._search_job = None

        search = self.search_entry.get().strip()
        group_filter = self._selected_group_filter()

        try:
            self._customers = self.customer_model.list_customers(
                search=search,
                group_id=group_filter,
            )

        except Exception:
            self._customers = []
            self.table.set_error(
                "Gagal memuat daftar pelanggan",
                "Terjadi kesalahan saat membaca data pelanggan.",
            )
            return

        self.table.set_rows(
            [self._row_values(customer) for customer in self._customers],
            variants=[
                customer_status_variant(customer.get("status"))
                for customer in self._customers
            ],
            searching=bool(search) or group_filter is not None,
        )

        self._highlight_row(0)

    @staticmethod
    def _row_values(customer: dict) -> list:
        return [
            customer["name"],
            customer.get("group_name") or "-",
            customer.get("status") or "-",
        ]

    # ------------------------------------------------------------------
    # Pemilihan
    # ------------------------------------------------------------------
    def _highlight_row(self, index: int):
        """Sorot satu baris agar jelas mana yang dipilih Enter / Pilih."""
        if not self._customers:
            return

        tree = self.table.tree

        try:
            tree.selection_set(str(index))
            tree.focus(str(index))
            tree.see(str(index))
        except Exception:
            pass

    def _focus_list(self, event=None):
        if not self._customers:
            return "break"

        index = self.table.selected_index()

        self.table.tree.focus_set()
        self._highlight_row(index if index is not None else 0)

        return "break"

    def _on_search_enter(self, event=None):
        self._select_current()
        return "break"

    def _select_current(self):
        # Bila pencarian masih menunggu, jalankan sekarang agar yang dipilih
        # adalah hasil terbaru.
        if self._search_job is not None:
            self._render_now()

        if not self._customers:
            return

        index = self.table.selected_index()

        self._select_index(index if index is not None else 0)

    def _select_index(self, index: int):
        if index is None or not 0 <= index < len(self._customers):
            return

        self._select(self._customers[index])

    def _select(self, customer: dict):
        self.on_select(customer)
        self.destroy()