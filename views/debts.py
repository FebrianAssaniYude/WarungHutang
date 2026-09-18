"""
views/debts.py

Halaman Transaksi Hutang - fitur TERPENTING aplikasi ini. Alur:
    1. Pilih pelanggan
    2. Scan barcode ATAU cari nama barang (satu kolom input yang sama)
    3. Barang masuk ke keranjang (tabel)
    4. Atur quantity dengan tombol +/-
    5. Tambahkan barang lain (ulangi langkah 2), atau "+ Barang Manual"
       untuk barang yang tidak ada di database
    6. Simpan hutang

Setelah scan berhasil, fokus kembali otomatis ke kolom scan/cari supaya
alur "Scan -> Scan -> Scan -> Scan -> Simpan" bisa dilakukan tanpa mouse.
"""

import uuid

import customtkinter as ctk

from models.customer import CustomerModel
from models.debt import DebtModel
from models.product import ProductModel
from utils.formatter import format_rupiah

MAX_SEARCH_RESULTS = 6


class TransaksiHutangPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        customer_model: CustomerModel,
        product_model: ProductModel,
        debt_model: DebtModel,
    ):
        super().__init__(master, fg_color="transparent")

        self.customer_model = customer_model
        self.product_model = product_model
        self.debt_model = debt_model

        self.selected_customer = None
        self.cart = []  # list of dict: row_id, product_id, product_name, quantity, price
        self._current_results = []

        self._build_header()
        self._build_customer_row()
        self._build_search_row()
        self._build_cart_area()
        self._build_footer()

        self._render_cart()

    def refresh(self):
        # Dipanggil setiap kali halaman ini dibuka dari sidebar. Sengaja
        # TIDAK mengosongkan keranjang yang sedang diisi (page ini tidak
        # dibuat ulang, hanya diangkat ke depan - jadi state tetap aman
        # kalau pengguna sempat melihat halaman lain di tengah transaksi).
        pass

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self):
        ctk.CTkLabel(
            self, text="Transaksi Hutang", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=32, pady=(28, 4))

        self.status_label = ctk.CTkLabel(self, text="", text_color="#2E7D32")
        self.status_label.pack(anchor="w", padx=32)

    # ------------------------------------------------------------------
    # Baris pilih pelanggan
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
        CustomerPickerDialog(
            self, self.customer_model, on_select=self._handle_customer_selected
        )

    def _handle_customer_selected(self, customer: dict):
        self.selected_customer = customer
        self.customer_button.configure(text=f"{customer['name']}  (ganti)")

    # ------------------------------------------------------------------
    # Baris scan/cari barang
    # ------------------------------------------------------------------
    def _build_search_row(self):
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="x", padx=32)

        search_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        search_row.pack(fill="x")

        self.search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Scan barcode atau cari nama barang...",
            height=40,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Return>", self._on_search_enter)

        ctk.CTkButton(
            search_row, text="+ Barang Manual", height=40, width=150,
            fg_color="gray70", hover_color="gray60",
            command=self._open_manual_item_dialog,
        ).pack(side="left")

        self.results_frame = ctk.CTkFrame(wrapper, fg_color=("white", "gray17"))
        # results_frame di-pack hanya saat ada hasil (lihat _render_results)

        self.search_entry.focus()

    def _on_search_change(self, event=None):
        query = self.search_entry.get().strip()
        if not query:
            self._current_results = []
            self._hide_results()
            return

        try:
            self._current_results = self.product_model.list_products(search=query)[:MAX_SEARCH_RESULTS]
        except Exception:
            # Gagal cari terjadi di tiap ketikan - jangan ganggu dengan popup,
            # cukup kosongkan hasil dan beri tahu lewat status di bawah judul.
            self._current_results = []
            self._hide_results()
            self._show_error("Gagal mencari barang. Periksa koneksi ke database.")
            return

        self._render_results()

    def _render_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not self._current_results:
            self._hide_results()
            return

        self.results_frame.pack(fill="x", pady=(0, 8))
        for product in self._current_results:
            label = f"{product['name']}  ·  {format_rupiah(product['price'])}"
            if product["barcode"]:
                label += f"  ·  {product['barcode']}"

            btn = ctk.CTkButton(
                self.results_frame, text=label, anchor="w",
                fg_color="transparent", hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                command=lambda p=product: self._select_search_result(p),
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _hide_results(self):
        self.results_frame.pack_forget()

    def _select_search_result(self, product: dict):
        self._add_product_to_cart(product)
        self._clear_search()

    def _on_search_enter(self, event=None):
        query = self.search_entry.get().strip()
        if not query:
            return

        # 1. Cocokkan barcode persis dulu (ini yang terjadi saat scan sungguhan).
        try:
            product = self.product_model.get_by_barcode(query)
        except Exception:
            self._show_error("Gagal memeriksa barcode. Periksa koneksi ke database.")
            return
        if product:
            self._add_product_to_cart(product)
            self._clear_search()
            return

        # 2. Jika hasil pencarian nama tinggal satu, anggap itu yang dimaksud.
        if len(self._current_results) == 1:
            self._add_product_to_cart(self._current_results[0])
            self._clear_search()
            return

        # 3. Tidak ditemukan sama sekali -> tawarkan pilihan (sesuai alur barcode scanner).
        if not self._current_results:
            BarcodeNotFoundDialog(
                self,
                code=query,
                on_add_as_product=lambda: self._open_manual_item_dialog(prefill_barcode=query),
                on_add_manual_only=lambda: self._open_manual_item_dialog(
                    prefill_barcode="", prefill_name="", one_off=True
                ),
            )
        # Jika hasil > 1, biarkan pengguna klik salah satu dari daftar hasil.

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self._current_results = []
        self._hide_results()
        self.search_entry.focus()

    # ------------------------------------------------------------------
    # Keranjang (cart)
    # ------------------------------------------------------------------
    def _build_cart_area(self):
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", padx=32, pady=(4, 0))
        columns = [("Barang", 3), ("Qty", 2), ("Harga", 2), ("Subtotal", 2), ("Aksi", 1)]
        for col, (_, weight) in enumerate(columns):
            header_row.grid_columnconfigure(col, weight=weight)
        for col, (text, _) in enumerate(columns):
            ctk.CTkLabel(
                header_row, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=(8, 4))

        self.cart_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"), height=220)
        self.cart_frame.pack(fill="both", expand=True, padx=32, pady=(0, 8))
        for col, weight in [(0, 3), (1, 2), (2, 2), (3, 2), (4, 1)]:
            self.cart_frame.grid_columnconfigure(col, weight=weight)

    def _add_product_to_cart(self, product: dict, quantity: int = 1):
        self._add_item_to_cart(
            product_id=product["id"],
            product_name=product["name"],
            price=product["price"],
            quantity=quantity,
        )

    def _add_item_to_cart(self, product_id, product_name: str, price: int, quantity: int = 1):
        # Gabungkan dengan baris yang sudah ada jika barang & harga sama,
        # supaya scan berulang cukup menambah qty (bukan bikin baris baru).
        for row in self.cart:
            if row["product_id"] == product_id and row["product_name"] == product_name and row["price"] == price:
                row["quantity"] += quantity
                self._render_cart()
                return

        self.cart.append({
            "row_id": str(uuid.uuid4()),
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity,
            "price": price,
        })
        self._render_cart()

    def _change_quantity(self, row_id: str, delta: int):
        for row in self.cart:
            if row["row_id"] == row_id:
                row["quantity"] = max(1, row["quantity"] + delta)
                break
        self._render_cart()

    def _remove_from_cart(self, row_id: str):
        self.cart = [row for row in self.cart if row["row_id"] != row_id]
        self._render_cart()

    def _open_price_edit_dialog(self, row_id: str):
        row = next((r for r in self.cart if r["row_id"] == row_id), None)
        if not row:
            return

        def on_save(new_price: int):
            row["price"] = new_price
            self._render_cart()

        PriceEditDialog(self, product_name=row["product_name"], current_price=row["price"], on_save=on_save)

    def _render_cart(self):
        for widget in self.cart_frame.winfo_children():
            widget.destroy()

        if not self.cart:
            ctk.CTkLabel(
                self.cart_frame,
                text="Keranjang masih kosong. Scan barcode atau cari barang di atas.",
                text_color="gray50",
            ).grid(row=0, column=0, columnspan=5, sticky="w", padx=8, pady=16)
            self._update_total()
            return

        for i, row in enumerate(self.cart):
            self._build_cart_row(i, row)

        self._update_total()

    def _build_cart_row(self, row_index: int, row: dict):
        subtotal = row["quantity"] * row["price"]

        ctk.CTkLabel(self.cart_frame, text=row["product_name"], anchor="w").grid(
            row=row_index, column=0, sticky="ew", padx=8, pady=6
        )

        qty_frame = ctk.CTkFrame(self.cart_frame, fg_color="transparent")
        qty_frame.grid(row=row_index, column=1, sticky="w", padx=8, pady=4)
        ctk.CTkButton(
            qty_frame, text="-", width=28, height=28,
            command=lambda rid=row["row_id"]: self._change_quantity(rid, -1),
        ).pack(side="left")
        ctk.CTkLabel(qty_frame, text=str(row["quantity"]), width=32).pack(side="left")
        ctk.CTkButton(
            qty_frame, text="+", width=28, height=28,
            command=lambda rid=row["row_id"]: self._change_quantity(rid, 1),
        ).pack(side="left")

        price_frame = ctk.CTkFrame(self.cart_frame, fg_color="transparent")
        price_frame.grid(row=row_index, column=2, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(price_frame, text=format_rupiah(row["price"])).pack(side="left")
        # Tombol edit harga sengaja dibuat kecil & tidak mencolok (fitur pelengkap).
        ctk.CTkButton(
            price_frame, text="ubah", width=40, height=20,
            font=ctk.CTkFont(size=10),
            fg_color="transparent", text_color="gray50", hover_color=("gray85", "gray25"),
            command=lambda rid=row["row_id"]: self._open_price_edit_dialog(rid),
        ).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(self.cart_frame, text=format_rupiah(subtotal), anchor="w").grid(
            row=row_index, column=3, sticky="ew", padx=8, pady=6
        )

        ctk.CTkButton(
            self.cart_frame, text="Hapus", width=64, height=28,
            fg_color="#D64545", hover_color="#B93A3A",
            command=lambda rid=row["row_id"]: self._remove_from_cart(rid),
        ).grid(row=row_index, column=4, sticky="w", padx=8, pady=4)

    # ------------------------------------------------------------------
    # Footer: total + simpan
    # ------------------------------------------------------------------
    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=32, pady=(0, 24))
        footer.grid_columnconfigure(0, weight=1)

        self.total_label = ctk.CTkLabel(
            footer, text="Total: Rp 0", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.total_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer, text="Simpan Hutang", height=44, width=180,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_save,
        ).grid(row=0, column=1, sticky="e")

    def _update_total(self):
        total = sum(row["quantity"] * row["price"] for row in self.cart)
        self.total_label.configure(text=f"Total: {format_rupiah(total)}")

    def _handle_save(self):
        self.status_label.configure(text="")

        if not self.selected_customer:
            self._show_error("Pelanggan harus dipilih terlebih dahulu.")
            return
        if not self.cart:
            self._show_error("Tambahkan minimal satu barang sebelum menyimpan.")
            return

        items = [
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"],
                "price": row["price"],
            }
            for row in self.cart
        ]

        try:
            success, message, _ = self.debt_model.create_transaction(
                customer_id=self.selected_customer["id"], items=items
            )
        except Exception:
            self._show_error("Terjadi kesalahan pada database. Transaksi tidak disimpan.")
            return

        if not success:
            self._show_error(message)
            return

        # Sukses: tampilkan pesan singkat, reset form untuk transaksi berikutnya.
        self.cart = []
        self.selected_customer = None
        self.customer_button.configure(text="[ Cari/Pilih Pelanggan ]")
        self._render_cart()
        self.status_label.configure(text=f"✓ {message}")
        self._clear_search()

    def _show_error(self, message: str):
        self.status_label.configure(text=message, text_color="#D64545")

    # ------------------------------------------------------------------
    # Dialog barang manual
    # ------------------------------------------------------------------
    def _open_manual_item_dialog(self, prefill_barcode: str = "", prefill_name: str = "", one_off: bool = False):
        ManualItemDialog(
            self,
            product_model=self.product_model,
            prefill_barcode=prefill_barcode,
            prefill_name=prefill_name,
            one_off=one_off,
            on_add=self._add_item_to_cart,
        )


class CustomerPickerDialog(ctk.CTkToplevel):
    """Dialog cari & pilih pelanggan (hanya pelanggan aktif)."""

    def __init__(self, master, customer_model: CustomerModel, on_select):
        super().__init__(master)
        self.customer_model = customer_model
        self.on_select = on_select

        self.title("Pilih Pelanggan")
        self.geometry("400x480")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="Pilih Pelanggan", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=20, pady=(20, 8), anchor="w"
        )

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Cari nama pelanggan...", height=36)
        self.search_entry.pack(fill="x", padx=20, pady=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda e: self._render_list())

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.search_entry.focus()
        self._render_list()

    def _render_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        try:
            customers = self.customer_model.list_customers(search=self.search_entry.get())
        except Exception:
            ctk.CTkLabel(
                self.list_frame, text="Gagal memuat daftar pelanggan. Coba lagi.",
                text_color="#D64545",
            ).pack(anchor="w", padx=8, pady=12)
            return

        if not customers:
            ctk.CTkLabel(self.list_frame, text="Pelanggan tidak ditemukan.", text_color="gray50").pack(
                anchor="w", padx=8, pady=12
            )
            return

        for customer in customers:
            btn = ctk.CTkButton(
                self.list_frame,
                text=f"{customer['name']}   ·   {customer['status']}",
                anchor="w",
                fg_color="transparent", hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                command=lambda c=customer: self._select(c),
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _select(self, customer: dict):
        self.on_select(customer)
        self.destroy()


class ManualItemDialog(ctk.CTkToplevel):
    """
    Dialog "+ Barang Manual": untuk barang tanpa barcode, belum ada di
    database, atau ingin dicatat langsung tanpa disimpan sebagai barang
    master (one_off=True).
    """

    def __init__(self, master, product_model: ProductModel, on_add, prefill_barcode="", prefill_name="", one_off=False):
        super().__init__(master)
        self.product_model = product_model
        self.on_add = on_add
        self.one_off = one_off

        self.title("Barang Manual")
        self.geometry("360x420")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="+ Barang Manual", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=20, pady=(20, 4), anchor="w"
        )
        ctk.CTkLabel(
            self,
            text="Untuk barang tanpa barcode atau belum ada di database.",
            text_color="gray50",
        ).pack(padx=20, anchor="w", pady=(0, 12))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        ctk.CTkLabel(form, text="Nama Barang *", anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(form, height=36)
        self.name_entry.pack(fill="x", pady=(2, 12))
        self.name_entry.insert(0, prefill_name)

        ctk.CTkLabel(form, text="Harga *", anchor="w").pack(fill="x")
        self.price_entry = ctk.CTkEntry(form, height=36, placeholder_text="contoh: 3000")
        self.price_entry.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(form, text="Qty *", anchor="w").pack(fill="x")
        self.qty_entry = ctk.CTkEntry(form, height=36)
        self.qty_entry.pack(fill="x", pady=(2, 12))
        self.qty_entry.insert(0, "1")

        self._barcode_for_new_product = prefill_barcode
        if not one_off:
            self.save_as_product_var = ctk.BooleanVar(value=True)
            self.save_as_product_check = ctk.CTkCheckBox(
                form, text="Simpan juga sebagai barang baru di database",
                variable=self.save_as_product_var,
            )
            self.save_as_product_check.pack(anchor="w", pady=(0, 8))
        else:
            self.save_as_product_var = ctk.BooleanVar(value=False)

        self.error_label = ctk.CTkLabel(form, text="", text_color="#D64545")
        self.error_label.pack(fill="x", pady=(0, 4))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Batal", fg_color="gray70", hover_color="gray60", command=self.destroy
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Tambahkan", command=self._submit).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        self.name_entry.focus()

    def _submit(self):
        name = self.name_entry.get().strip()
        if not name:
            self.error_label.configure(text="Nama barang wajib diisi.")
            return

        try:
            price = int(round(float(self.price_entry.get().strip())))
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.error_label.configure(text="Harga harus berupa angka dan tidak boleh negatif.")
            return

        try:
            qty = int(self.qty_entry.get().strip())
            if qty <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.error_label.configure(text="Qty harus berupa angka bulat lebih besar dari 0.")
            return

        product_id = None
        if self.save_as_product_var.get():
            try:
                ok, msg, new_id = self.product_model.add_product(
                    name=name, price=price, barcode=self._barcode_for_new_product, unit=""
                )
            except Exception:
                ok, new_id = False, None
            if ok:
                product_id = new_id
            # Jika gagal simpan sebagai produk (mis. barcode duplikat, atau
            # kesalahan database tak terduga), tetap lanjutkan sebagai
            # barang manual pada transaksi ini saja - jangan sampai batal
            # menambahkan barang hanya karena gagal menyimpan ke master.

        self.on_add(product_id=product_id, product_name=name, price=price, quantity=qty)
        self.destroy()


class PriceEditDialog(ctk.CTkToplevel):
    """Dialog kecil untuk mengubah harga khusus baris transaksi ini saja."""

    def __init__(self, master, product_name: str, current_price: int, on_save):
        super().__init__(master)
        self.on_save = on_save

        self.title("Ubah Harga")
        self.geometry("320x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Ubah harga: {product_name}", font=ctk.CTkFont(size=14, weight="bold")).pack(
            padx=20, pady=(20, 4), anchor="w"
        )
        ctk.CTkLabel(
            self, text="Perubahan ini hanya berlaku untuk transaksi ini saja.", text_color="gray50", wraplength=280,
        ).pack(padx=20, anchor="w", pady=(0, 12))

        self.price_entry = ctk.CTkEntry(self, height=36)
        self.price_entry.pack(fill="x", padx=20)
        self.price_entry.insert(0, str(current_price))
        self.price_entry.focus()

        self.error_label = ctk.CTkLabel(self, text="", text_color="#D64545")
        self.error_label.pack(fill="x", padx=20, pady=(6, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(16, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Batal", fg_color="gray70", hover_color="gray60", command=self.destroy
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Simpan", command=self._submit).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def _submit(self):
        try:
            price = int(round(float(self.price_entry.get().strip())))
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.error_label.configure(text="Harga harus berupa angka dan tidak boleh negatif.")
            return

        self.on_save(price)
        self.destroy()


class BarcodeNotFoundDialog(ctk.CTkToplevel):
    """
    Muncul ketika kode yang di-scan/diketik tidak cocok dengan barang
    manapun. Menawarkan pilihan lanjutan sesuai alur barcode di spesifikasi.
    """

    def __init__(self, master, code: str, on_add_as_product, on_add_manual_only):
        super().__init__(master)

        self.title("Barang Tidak Ditemukan")
        self.geometry("360x260")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self, text="Barang Tidak Ditemukan", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(padx=20, pady=(20, 4), anchor="w")
        ctk.CTkLabel(
            self, text=f"Kode \"{code}\" tidak cocok dengan barang manapun.", text_color="gray50", wraplength=300,
        ).pack(padx=20, anchor="w", pady=(0, 16))

        ctk.CTkButton(
            self, text="Tambah sebagai Barang Baru", height=38,
            command=lambda: self._choose(on_add_as_product),
        ).pack(fill="x", padx=20, pady=4)

        ctk.CTkButton(
            self, text="Input Manual (hanya transaksi ini)", height=38,
            fg_color="gray70", hover_color="gray60",
            command=lambda: self._choose(on_add_manual_only),
        ).pack(fill="x", padx=20, pady=4)

        ctk.CTkButton(
            self, text="Batal", height=38,
            fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
            command=self.destroy,
        ).pack(fill="x", padx=20, pady=(4, 20))

    def _choose(self, action):
        self.destroy()
        action()
