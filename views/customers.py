"""
views/customers.py

Halaman Pelanggan: menampilkan daftar pelanggan (nama, sisa hutang,
status), pencarian, tambah/edit lewat dialog, nonaktifkan (soft delete)
dengan konfirmasi, dan detail pelanggan (ringkasan + riwayat).

CustomTkinter tidak punya widget tabel bawaan, jadi tabel dibuat manual
memakai CTkScrollableFrame + baris-baris CTkFrame.
"""

import customtkinter as ctk

from models.customer import CustomerModel
from utils.formatter import format_rupiah, format_date_indonesia


class CustomersPage(ctk.CTkFrame):
    def __init__(self, master, customer_model: CustomerModel):
        super().__init__(master, fg_color="transparent")

        self.customer_model = customer_model
        self.search_var = ctk.StringVar()

        self._build_header()
        self._build_table_header()
        self._build_table_body()

        self.refresh()

    # ------------------------------------------------------------------
    # Header: judul, pencarian, tombol tambah
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Pelanggan", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        search_entry = ctk.CTkEntry(
            actions,
            textvariable=self.search_var,
            placeholder_text="Cari nama pelanggan...",
            width=220,
            height=36,
        )
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        ctk.CTkButton(
            actions, text="+ Tambah Pelanggan", height=36, command=self._open_add_dialog
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Tabel
    # ------------------------------------------------------------------
    def _build_table_header(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=32)

        widths = [(0, 3), (1, 1), (2, 1), (3, 2)]
        labels = ["Nama", "Sisa Hutang", "Status", "Aksi"]
        for col, weight in widths:
            row.grid_columnconfigure(col, weight=weight)

        for col, text in enumerate(labels):
            ctk.CTkLabel(
                row, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=(0, 6))

    def _build_table_body(self):
        self.table_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        self.table_frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        for col, weight in [(0, 3), (1, 1), (2, 1), (3, 2)]:
            self.table_frame.grid_columnconfigure(col, weight=weight)

    def refresh(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        try:
            customers = self.customer_model.list_customers(search=self.search_var.get())
        except Exception:
            ctk.CTkLabel(
                self.table_frame,
                text="Gagal memuat daftar pelanggan. Coba lagi.",
                text_color="#D64545",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
            return

        if not customers:
            ctk.CTkLabel(
                self.table_frame,
                text="Belum ada pelanggan. Klik \"+ Tambah Pelanggan\" untuk menambahkan.",
                text_color="gray50",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=16)
            return

        for i, customer in enumerate(customers):
            self._build_row(i, customer)

    def _build_row(self, row_index: int, customer: dict):
        row_color = ("gray95", "gray20") if row_index % 2 == 0 else ("white", "gray17")

        name_label = ctk.CTkLabel(
            self.table_frame, text=customer["name"], anchor="w"
        )
        name_label.grid(row=row_index, column=0, sticky="ew", padx=8, pady=6)

        sisa_label = ctk.CTkLabel(
            self.table_frame, text=format_rupiah(customer["sisa"]), anchor="w"
        )
        sisa_label.grid(row=row_index, column=1, sticky="ew", padx=8, pady=6)

        status_color = "#2E7D32" if customer["status"] == "Lunas" else "#B93A3A"
        status_label = ctk.CTkLabel(
            self.table_frame, text=customer["status"], anchor="w", text_color=status_color
        )
        status_label.grid(row=row_index, column=2, sticky="ew", padx=8, pady=6)

        actions = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        actions.grid(row=row_index, column=3, sticky="w", padx=8, pady=4)

        ctk.CTkButton(
            actions, text="Detail", width=64, height=28,
            command=lambda c=customer: self._open_detail_dialog(c["id"]),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="Edit", width=56, height=28,
            fg_color="gray70", hover_color="gray60",
            command=lambda c=customer: self._open_edit_dialog(c),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="Nonaktifkan", width=96, height=28,
            fg_color="#D64545", hover_color="#B93A3A",
            command=lambda c=customer: self._confirm_deactivate(c),
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Dialog: tambah / edit
    # ------------------------------------------------------------------
    def _open_add_dialog(self):
        CustomerFormDialog(
            self, title="Tambah Pelanggan", on_submit=self._handle_add
        )

    def _open_edit_dialog(self, customer: dict):
        CustomerFormDialog(
            self,
            title="Edit Pelanggan",
            initial={
                "name": customer["name"],
                "phone": customer["phone"] or "",
                "notes": customer["notes"] or "",
            },
            on_submit=lambda data: self._handle_edit(customer["id"], data),
        )

    def _handle_add(self, data: dict):
        return self.customer_model.add_customer(
            name=data["name"], phone=data["phone"], notes=data["notes"]
        )[:2]  # (sukses, pesan) - dialog tidak butuh id baru

    def _handle_edit(self, customer_id: int, data: dict):
        return self.customer_model.update_customer(
            customer_id, name=data["name"], phone=data["phone"], notes=data["notes"]
        )

    # ------------------------------------------------------------------
    # Dialog: nonaktifkan (perlu konfirmasi)
    # ------------------------------------------------------------------
    def _confirm_deactivate(self, customer: dict):
        ConfirmDialog(
            self,
            title="Nonaktifkan Pelanggan",
            message=(
                f"Nonaktifkan \"{customer['name']}\"?\n\n"
                "Pelanggan tidak akan muncul lagi pada transaksi baru, "
                "tapi seluruh riwayatnya tetap tersimpan aman."
            ),
            confirm_text="Nonaktifkan",
            on_confirm=lambda: self._handle_deactivate(customer["id"]),
        )

    def _handle_deactivate(self, customer_id: int):
        try:
            self.customer_model.deactivate_customer(customer_id)
        except Exception:
            from tkinter import messagebox
            messagebox.showerror(
                "Terjadi Kesalahan", "Gagal menonaktifkan pelanggan. Coba lagi."
            )
            return
        self.refresh()

    # ------------------------------------------------------------------
    # Dialog: detail
    # ------------------------------------------------------------------
    def _open_detail_dialog(self, customer_id: int):
        try:
            detail = self.customer_model.get_detail(customer_id)
        except Exception:
            from tkinter import messagebox
            messagebox.showerror(
                "Terjadi Kesalahan", "Gagal memuat detail pelanggan. Coba lagi."
            )
            return
        if detail:
            CustomerDetailDialog(self, detail)


class CustomerFormDialog(ctk.CTkToplevel):
    """Dialog tambah/edit pelanggan. on_submit(data) harus mengembalikan (sukses, pesan)."""

    def __init__(self, master: CustomersPage, title: str, on_submit, initial: dict = None):
        super().__init__(master)
        self.master_page = master
        self.on_submit = on_submit
        initial = initial or {}

        self.title(title)
        self.geometry("380x380")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=18, weight="bold")).pack(
            pady=(20, 16)
        )

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24)

        ctk.CTkLabel(form, text="Nama *", anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(form, height=36)
        self.name_entry.pack(fill="x", pady=(2, 12))
        self.name_entry.insert(0, initial.get("name", ""))

        ctk.CTkLabel(form, text="Nomor HP (opsional)", anchor="w").pack(fill="x")
        self.phone_entry = ctk.CTkEntry(form, height=36)
        self.phone_entry.pack(fill="x", pady=(2, 12))
        self.phone_entry.insert(0, initial.get("phone", ""))

        ctk.CTkLabel(form, text="Catatan (opsional)", anchor="w").pack(fill="x")
        self.notes_entry = ctk.CTkEntry(form, height=36)
        self.notes_entry.pack(fill="x", pady=(2, 8))
        self.notes_entry.insert(0, initial.get("notes", ""))

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

        self.name_entry.focus()

    def _submit(self):
        data = {
            "name": self.name_entry.get().strip(),
            "phone": self.phone_entry.get().strip(),
            "notes": self.notes_entry.get().strip(),
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


class ConfirmDialog(ctk.CTkToplevel):
    """Dialog konfirmasi generik untuk tindakan penting (nonaktifkan, dsb)."""

    def __init__(self, master, title: str, message: str, on_confirm, confirm_text: str = "Ya"):
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
            btn_row, text=confirm_text, fg_color="#D64545", hover_color="#B93A3A",
            command=self._confirm,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _confirm(self):
        self.on_confirm()
        self.destroy()


class CustomerDetailDialog(ctk.CTkToplevel):
    """Menampilkan ringkasan saldo + timeline riwayat hutang/pembayaran."""

    def __init__(self, master, detail: dict):
        super().__init__(master)

        self.title(f"Detail - {detail['name']}")
        self.geometry("520x600")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self, text=detail["name"], font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=24, pady=(20, 2))

        subtitle = detail["phone"] or "Tanpa nomor HP"
        ctk.CTkLabel(self, text=subtitle, text_color="gray50").pack(
            anchor="w", padx=24, pady=(0, 16)
        )

        self._build_summary(detail)

        ctk.CTkLabel(
            self, text="Riwayat", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=24, pady=(16, 6))

        self._build_timeline(detail["timeline"])

        ctk.CTkButton(self, text="Tutup", command=self.destroy).pack(
            pady=16, padx=24, fill="x"
        )

    def _build_summary(self, detail: dict):
        summary = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        summary.pack(fill="x", padx=24)
        summary.grid_columnconfigure((0, 1, 2), weight=1)

        cards = [
            ("Total Hutang", detail["total_debt"]),
            ("Total Pembayaran", detail["total_paid"]),
            ("Sisa Hutang", detail["sisa"]),
        ]
        for col, (label, value) in enumerate(cards):
            cell = ctk.CTkFrame(summary, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=12, pady=12)
            ctk.CTkLabel(cell, text=label, font=ctk.CTkFont(size=11), text_color="gray50").pack(
                anchor="w"
            )
            ctk.CTkLabel(
                cell, text=format_rupiah(value), font=ctk.CTkFont(size=15, weight="bold")
            ).pack(anchor="w")

    def _build_timeline(self, timeline: list):
        scroll = ctk.CTkScrollableFrame(self, fg_color=("white", "gray17"))
        scroll.pack(fill="both", expand=True, padx=24)

        if not timeline:
            ctk.CTkLabel(
                scroll, text="Belum ada riwayat transaksi.", text_color="gray50"
            ).pack(anchor="w", padx=8, pady=12)
            return

        for entry in timeline:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=4)
            row.grid_columnconfigure(0, weight=1)

            color = "#B93A3A" if entry["type"] == "Hutang" else "#2E7D32"
            sign = "+" if entry["type"] == "Hutang" else "-"

            ctk.CTkLabel(
                row,
                text=f"{format_date_indonesia(entry['date'])} · {entry['type']}",
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                row, text=f"{sign} {format_rupiah(entry['amount'])}", text_color=color,
            ).grid(row=0, column=1, sticky="e")
