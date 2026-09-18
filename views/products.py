"""
views/products.py

Halaman Barang: daftar barang (barcode, nama, harga, satuan, status),
pencarian berdasarkan nama ATAU barcode, tambah/edit lewat dialog,
nonaktifkan (soft delete) dengan konfirmasi, dan kotak scan barcode
cepat untuk mencari atau langsung menambah barang baru.
"""

import customtkinter as ctk

from models.product import ProductModel
from utils.barcode import BarcodeScanEntry
from utils.formatter import format_rupiah


class ProductsPage(ctk.CTkFrame):
    def __init__(self, master, product_model: ProductModel):
        super().__init__(master, fg_color="transparent")

        self.product_model = product_model
        self.search_var = ctk.StringVar()

        self._build_header()
        self._build_scan_bar()
        self._build_table_header()
        self._build_table_body()

        self.refresh()

    # ------------------------------------------------------------------
    # Header: judul, pencarian, tombol tambah manual
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Barang", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        search_entry = ctk.CTkEntry(
            actions,
            textvariable=self.search_var,
            placeholder_text="Cari nama atau barcode...",
            width=220,
            height=36,
        )
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        ctk.CTkButton(
            actions, text="+ Tambah Barang", height=36, command=self._open_add_dialog
        ).pack(side="left")

    def _build_scan_bar(self):
        """Kotak scan barcode cepat: scan -> jika ada, buka edit; jika tidak, tawarkan tambah baru."""
        bar = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        bar.pack(fill="x", padx=32, pady=(0, 16))

        ctk.CTkLabel(
            bar, text="Scan Barcode:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(16, 8), pady=12)

        self.scan_entry = BarcodeScanEntry(
            bar,
            on_scan=self._handle_barcode_scan,
            placeholder_text="Arahkan scanner ke sini lalu scan...",
            height=34,
        )
        self.scan_entry.pack(side="left", fill="x", expand=True, padx=(0, 16), pady=12)

    def _handle_barcode_scan(self, code: str):
        try:
            product = self.product_model.get_by_barcode(code, active_only=False)
        except Exception:
            from tkinter import messagebox
            messagebox.showerror(
                "Terjadi Kesalahan", "Gagal memeriksa barcode. Coba lagi."
            )
            return
        if product:
            self._open_edit_dialog(product)
        else:
            self._open_add_dialog(prefill_barcode=code)

    # ------------------------------------------------------------------
    # Tabel
    # ------------------------------------------------------------------
    def _build_table_header(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=32)

        columns = [("Barcode", 2), ("Nama", 3), ("Harga", 1), ("Satuan", 1), ("Status", 1), ("Aksi", 2)]
        for col, (_, weight) in enumerate(columns):
            row.grid_columnconfigure(col, weight=weight)

        for col, (text, _) in enumerate(columns):
            ctk.CTkLabel(
                row, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=(0, 6))

    def _build_table_body(self):
        self.table_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        self.table_frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        for col, weight in [(0, 2), (1, 3), (2, 1), (3, 1), (4, 1), (5, 2)]:
            self.table_frame.grid_columnconfigure(col, weight=weight)

    def refresh(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        try:
            products = self.product_model.list_products(search=self.search_var.get())
        except Exception:
            ctk.CTkLabel(
                self.table_frame,
                text="Gagal memuat daftar barang. Coba lagi.",
                text_color="#D64545",
            ).grid(row=0, column=0, columnspan=6, sticky="w", padx=8, pady=16)
            return

        if not products:
            ctk.CTkLabel(
                self.table_frame,
                text="Belum ada barang. Klik \"+ Tambah Barang\" atau scan barcode untuk menambahkan.",
                text_color="gray50",
            ).grid(row=0, column=0, columnspan=6, sticky="w", padx=8, pady=16)
            return

        for i, product in enumerate(products):
            self._build_row(i, product)

    def _build_row(self, row_index: int, product: dict):
        barcode_text = product["barcode"] or "-"
        ctk.CTkLabel(self.table_frame, text=barcode_text, anchor="w", text_color="gray50").grid(
            row=row_index, column=0, sticky="ew", padx=8, pady=6
        )
        ctk.CTkLabel(self.table_frame, text=product["name"], anchor="w").grid(
            row=row_index, column=1, sticky="ew", padx=8, pady=6
        )
        ctk.CTkLabel(self.table_frame, text=format_rupiah(product["price"]), anchor="w").grid(
            row=row_index, column=2, sticky="ew", padx=8, pady=6
        )
        ctk.CTkLabel(self.table_frame, text=product["unit"] or "-", anchor="w").grid(
            row=row_index, column=3, sticky="ew", padx=8, pady=6
        )

        status_text = "Aktif" if product["is_active"] else "Nonaktif"
        status_color = "#2E7D32" if product["is_active"] else "gray50"
        ctk.CTkLabel(self.table_frame, text=status_text, anchor="w", text_color=status_color).grid(
            row=row_index, column=4, sticky="ew", padx=8, pady=6
        )

        actions = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        actions.grid(row=row_index, column=5, sticky="w", padx=8, pady=4)

        ctk.CTkButton(
            actions, text="Edit", width=56, height=28,
            fg_color="gray70", hover_color="gray60",
            command=lambda p=product: self._open_edit_dialog(p),
        ).pack(side="left", padx=(0, 6))

        if product["is_active"]:
            ctk.CTkButton(
                actions, text="Nonaktifkan", width=96, height=28,
                fg_color="#D64545", hover_color="#B93A3A",
                command=lambda p=product: self._confirm_deactivate(p),
            ).pack(side="left")

    # ------------------------------------------------------------------
    # Dialog: tambah / edit
    # ------------------------------------------------------------------
    def _open_add_dialog(self, prefill_barcode: str = ""):
        ProductFormDialog(
            self,
            title="Tambah Barang",
            on_submit=self._handle_add,
            initial={"barcode": prefill_barcode},
        )

    def _open_edit_dialog(self, product: dict):
        ProductFormDialog(
            self,
            title="Edit Barang",
            initial={
                "barcode": product["barcode"] or "",
                "name": product["name"],
                "price": str(product["price"]),
                "unit": product["unit"] or "",
            },
            on_submit=lambda data: self._handle_edit(product["id"], data),
        )

    def _handle_add(self, data: dict):
        success, message, _ = self.product_model.add_product(
            name=data["name"], price=data["price"], barcode=data["barcode"], unit=data["unit"]
        )
        return success, message

    def _handle_edit(self, product_id: int, data: dict):
        return self.product_model.update_product(
            product_id, name=data["name"], price=data["price"], barcode=data["barcode"], unit=data["unit"]
        )

    # ------------------------------------------------------------------
    # Nonaktifkan (perlu konfirmasi)
    # ------------------------------------------------------------------
    def _confirm_deactivate(self, product: dict):
        ProductConfirmDialog(
            self,
            title="Nonaktifkan Barang",
            message=(
                f"Nonaktifkan \"{product['name']}\"?\n\n"
                "Barang tidak akan muncul lagi pada transaksi baru, "
                "tapi histori transaksi lama tetap aman."
            ),
            on_confirm=lambda: self._handle_deactivate(product["id"]),
        )

    def _handle_deactivate(self, product_id: int):
        try:
            self.product_model.deactivate_product(product_id)
        except Exception:
            from tkinter import messagebox
            messagebox.showerror(
                "Terjadi Kesalahan", "Gagal menonaktifkan barang. Coba lagi."
            )
            return
        self.refresh()


class ProductFormDialog(ctk.CTkToplevel):
    """Dialog tambah/edit barang. on_submit(data) harus mengembalikan (sukses, pesan)."""

    def __init__(self, master: ProductsPage, title: str, on_submit, initial: dict = None):
        super().__init__(master)
        self.master_page = master
        self.on_submit = on_submit
        initial = initial or {}

        self.title(title)
        self.geometry("380x460")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=18, weight="bold")).pack(
            pady=(20, 16)
        )

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24)

        ctk.CTkLabel(form, text="Barcode (opsional)", anchor="w").pack(fill="x")
        self.barcode_entry = ctk.CTkEntry(form, height=36)
        self.barcode_entry.pack(fill="x", pady=(2, 12))
        self.barcode_entry.insert(0, initial.get("barcode", ""))

        ctk.CTkLabel(form, text="Nama Barang *", anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(form, height=36)
        self.name_entry.pack(fill="x", pady=(2, 12))
        self.name_entry.insert(0, initial.get("name", ""))

        ctk.CTkLabel(form, text="Harga *", anchor="w").pack(fill="x")
        self.price_entry = ctk.CTkEntry(form, height=36, placeholder_text="contoh: 3000")
        self.price_entry.pack(fill="x", pady=(2, 12))
        self.price_entry.insert(0, initial.get("price", ""))

        ctk.CTkLabel(form, text="Satuan (opsional)", anchor="w").pack(fill="x")
        self.unit_entry = ctk.CTkEntry(form, height=36, placeholder_text="contoh: pcs, kg, sachet")
        self.unit_entry.pack(fill="x", pady=(2, 8))
        self.unit_entry.insert(0, initial.get("unit", ""))

        self.error_label = ctk.CTkLabel(form, text="", text_color="#D64545")
        self.error_label.pack(fill="x", pady=(0, 4))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(8, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Batal", fg_color="gray70", hover_color="gray60",
            command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Simpan", command=self._submit,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Fokus ke nama jika barcode sudah terisi otomatis dari hasil scan,
        # kalau tidak fokus ke barcode agar bisa langsung scan.
        if initial.get("barcode"):
            self.name_entry.focus()
        else:
            self.barcode_entry.focus()

    def _submit(self):
        data = {
            "barcode": self.barcode_entry.get().strip(),
            "name": self.name_entry.get().strip(),
            "price": self.price_entry.get().strip(),
            "unit": self.unit_entry.get().strip(),
        }
        try:
            success, message = self.on_submit(data)
        except Exception:
            self.error_label.configure(text="Terjadi kesalahan pada database. Coba lagi.")
            return

        if not success:
            self.error_label.configure(text=message)
            return

        self.master_page.refresh()
        self.destroy()


class ProductConfirmDialog(ctk.CTkToplevel):
    """Dialog konfirmasi nonaktifkan barang."""

    def __init__(self, master, title: str, message: str, on_confirm):
        super().__init__(master)
        self.on_confirm = on_confirm

        self.title(title)
        self.geometry("360x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self, text=message, wraplength=300, justify="left"
        ).pack(padx=24, pady=(28, 16), fill="both", expand=True)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Batal", fg_color="gray70", hover_color="gray60",
            command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Nonaktifkan", fg_color="#D64545", hover_color="#B93A3A",
            command=self._confirm,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _confirm(self):
        self.on_confirm()
        self.destroy()
