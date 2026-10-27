"""
Dialog detail transaksi yang dipakai bersama oleh halaman Pelanggan
dan Riwayat: Hutang, Pembayaran, Pembelian, Penjualan.

Semua dialog turunan BaseDialog, jadi lebar, padding, judul, dan footer
mengikuti standar aplikasi. Tombol Cetak langsung membuat dan membuka PDF.

Warna nominal utama: Hutang merah, Pembayaran hijau, lainnya warna teks biasa.
"""

import customtkinter as ctk

from components.dialogs import BaseDialog, show_error
from components.forms import InfoRow
from components.tables import SimpleTable
from utils.formatter import format_date_indonesia, format_rupiah
from utils.printer import Printer, PrinterError
from utils.theme import (
    COLORS,
    DIALOG_HEIGHT,
    DIALOG_WIDTH,
    SPACING,
    get_font,
)

# Lebar teks nilai pada baris info (dialog lebar vs dialog sempit).
INFO_WRAP_WIDE = 460
INFO_WRAP_NARROW = 260


def _open_pdf(dialog, document_type: str, payload: dict, fail_text: str):
    """Buat PDF lalu buka dengan aplikasi bawaan. Error tampil sebagai dialog."""
    try:
        printer = Printer()
        pdf_path = printer.create_pdf(document_type, payload)
        printer.open_pdf(pdf_path)

    except PrinterError as exc:
        show_error(dialog, "Cetak Gagal", str(exc))

    except Exception:
        show_error(dialog, "Cetak Gagal", fail_text)


def _add_info_rows(parent, rows: list, wraplength: int = INFO_WRAP_WIDE):
    """
    rows: list of (label, nilai, tebal) atau (label, nilai, tebal, warna).
    """
    for index, row in enumerate(rows):
        label, value, bold = row[0], row[1], row[2]
        color = row[3] if len(row) > 3 else None

        InfoRow(
            parent,
            label,
            value,
            bold,
            wraplength=wraplength,
            color=color,
        ).pack(
            fill="x",
            pady=(0 if index == 0 else SPACING["sm"], 0),
        )


def _item_columns(price_title: str) -> list:
    return [
        {"title": "Barang", "weight": 4, "align": "left"},
        {"title": "Qty", "weight": 1, "align": "right"},
        {"title": price_title, "weight": 2, "align": "right"},
        {"title": "Subtotal", "weight": 2, "align": "right"},
    ]


def _item_rows(items: list) -> list:
    return [
        [
            item.get("product_name") or "-",
            str(item.get("quantity", 0)),
            format_rupiah(item.get("price", 0)),
            format_rupiah(item.get("subtotal", 0)),
        ]
        for item in items
    ]


# ======================================================================
# DIALOG DASAR TRANSAKSI BERBARANG
# ======================================================================

class TransactionDetailDialog(BaseDialog):
    """
    Dialog detail transaksi yang memuat daftar barang.

    info_rows    : list of (label, nilai, tebal)
    summary_rows : list of (label, nilai_teks, warna_atau_None, tebal)
    """

    def __init__(
        self,
        master,
        title: str,
        heading: str,
        info_rows: list,
        price_title: str,
        items: list,
        summary_rows: list,
        document_type: str,
        payload: dict,
        print_error_text: str,
    ):
        super().__init__(
            master,
            title,
            DIALOG_WIDTH["detail"],
            height=DIALOG_HEIGHT["detail"],
            heading=heading,
        )

        self.document_type = document_type
        self.payload = payload
        self.print_error_text = print_error_text

        info = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        info.pack(fill="x")
        _add_info_rows(info, info_rows)

        ctk.CTkLabel(
            self.body,
            text="Barang",
            font=get_font("subheading"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(
            fill="x",
            pady=(SPACING["lg"], SPACING["sm"]),
        )

        # Ringkasan dipasang lebih dulu di bawah agar tidak terpotong tabel.
        summary = ctk.CTkFrame(
            self.body,
            fg_color="transparent",
            width=0,
            height=0,
        )
        summary.pack(
            side="bottom",
            fill="x",
            pady=(SPACING["md"], 0),
        )

        for index, (label, value, color, bold) in enumerate(summary_rows):
            self._summary_row(summary, index, label, value, color, bold)

        table = SimpleTable(
            self.body,
            _item_columns(price_title),
            empty_title="Tidak ada detail barang",
            scrollable=True,
        )
        table.pack(fill="both", expand=True)
        table.set_rows(_item_rows(items))

        self.set_buttons("Cetak", self._print, "Tutup")
        self.finish()

    @staticmethod
    def _summary_row(parent, index, label, value, color, bold):
        row = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=0,
            height=0,
        )
        row.pack(
            fill="x",
            pady=(0 if index == 0 else SPACING["xs"], 0),
        )

        ctk.CTkLabel(
            row,
            text=label,
            font=get_font("subheading" if bold else "body"),
            text_color=COLORS["text" if bold else "text_secondary"],
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=value,
            font=get_font("summary_value" if bold else "body"),
            text_color=color or COLORS["text"],
        ).pack(side="right")

    def _print(self):
        _open_pdf(
            self,
            self.document_type,
            self.payload,
            self.print_error_text,
        )


# ======================================================================
# HUTANG
# ======================================================================

class DebtDetailDialog(TransactionDetailDialog):
    """Detail lengkap satu transaksi hutang."""

    def __init__(self, master, detail: dict):
        number = detail.get("transaction_number") or "Transaksi Lama"

        info = [
            ("Nomor Transaksi", number, True),
            (
                "Tanggal",
                format_date_indonesia(detail.get("transaction_date")),
                False,
            ),
            ("Pelanggan", detail.get("customer_name") or "-", False),
        ]

        if detail.get("notes"):
            info.append(("Catatan", detail["notes"], False))

        super().__init__(
            master,
            title=f"Detail Hutang - {number}",
            heading="Detail Transaksi Hutang",
            info_rows=info,
            price_title="Harga",
            items=detail.get("items") or [],
            summary_rows=[
                (
                    "Total",
                    format_rupiah(detail.get("total_amount", 0)),
                    COLORS["danger"],
                    True,
                ),
            ],
            document_type="debt",
            payload={
                "transaction_number": (
                    detail.get("transaction_number") or "Transaksi-Lama"
                ),
                "transaction_date": detail.get("transaction_date"),
                "customer_name": detail.get("customer_name"),
                "total_amount": detail.get("total_amount", 0),
                "notes": detail.get("notes"),
                "details": detail.get("items") or [],
            },
            print_error_text="Gagal membuat atau membuka dokumen PDF hutang.",
        )


# ======================================================================
# PEMBELIAN
# ======================================================================

class PurchaseDetailDialog(TransactionDetailDialog):
    """Detail lengkap satu transaksi pembelian."""

    def __init__(self, master, detail: dict):
        number = detail.get("transaction_number") or "Transaksi Lama"

        info = [
            ("Nomor Transaksi", number, True),
            (
                "Tanggal",
                format_date_indonesia(detail.get("transaction_date")),
                False,
            ),
            (
                "Supplier",
                detail.get("supplier_name") or "Tidak ada supplier",
                False,
            ),
        ]

        if detail.get("notes"):
            info.append(("Catatan", detail["notes"], False))

        super().__init__(
            master,
            title=f"Detail Pembelian - {number}",
            heading="Detail Transaksi Pembelian",
            info_rows=info,
            price_title="Harga Beli",
            items=detail.get("items") or [],
            summary_rows=[
                (
                    "Total",
                    format_rupiah(detail.get("total_amount", 0)),
                    None,
                    True,
                ),
            ],
            document_type="purchase",
            payload={
                "transaction_number": (
                    detail.get("transaction_number") or "Transaksi-Lama"
                ),
                "transaction_date": detail.get("transaction_date"),
                "supplier_name": detail.get("supplier_name"),
                "total_amount": detail.get("total_amount", 0),
                "notes": detail.get("notes"),
                "details": detail.get("items") or [],
            },
            print_error_text="Gagal membuat atau membuka dokumen PDF pembelian.",
        )


# ======================================================================
# PENJUALAN
# ======================================================================

class SaleDetailDialog(TransactionDetailDialog):
    """Detail lengkap satu transaksi penjualan."""

    def __init__(self, master, detail: dict):
        sale = detail.get("sale") or {}
        number = sale.get("transaction_number") or "Transaksi Lama"

        info = [
            ("Nomor Transaksi", number, True),
            (
                "Tanggal",
                format_date_indonesia(sale.get("transaction_date")),
                False,
            ),
        ]

        if sale.get("notes"):
            info.append(("Catatan", sale["notes"], False))

        super().__init__(
            master,
            title=f"Detail Penjualan - {number}",
            heading="Detail Transaksi Penjualan",
            info_rows=info,
            price_title="Harga Jual",
            items=detail.get("details") or [],
            summary_rows=[
                (
                    "Total",
                    format_rupiah(sale.get("total_amount", 0)),
                    None,
                    True,
                ),
                (
                    "Dibayar",
                    format_rupiah(sale.get("paid_amount", 0)),
                    None,
                    False,
                ),
                (
                    "Kembalian",
                    format_rupiah(sale.get("change_amount", 0)),
                    None,
                    False,
                ),
            ],
            document_type="sale",
            # Printer membaca "sale" dan "details" dari hasil model apa adanya.
            payload=detail,
            print_error_text="Gagal membuat atau membuka dokumen PDF penjualan.",
        )


# ======================================================================
# PEMBAYARAN
# ======================================================================

class PaymentDetailDialog(BaseDialog):
    """Detail lengkap satu pembayaran hutang."""

    def __init__(self, master, detail: dict):
        super().__init__(
            master,
            "Detail Pembayaran",
            DIALOG_WIDTH["form"],
        )

        self.detail = detail

        rows = [
            ("Pelanggan", detail.get("customer_name") or "-", False),
            (
                "Tanggal",
                format_date_indonesia(detail.get("payment_date")),
                False,
            ),
            (
                "Jumlah Pembayaran",
                format_rupiah(detail.get("amount", 0)),
                True,
                COLORS["success"],
            ),
        ]

        # Snapshot kondisi hutang saat pembayaran
        total_debt = detail.get("total_debt_at_payment")
        remaining_debt = detail.get("remaining_debt_at_payment")

        if total_debt is not None:
            rows.append(
                ("Total Hutang Saat Itu", format_rupiah(total_debt), False)
            )

        if remaining_debt is not None:
            rows.append(
                ("Sisa Hutang Saat Itu", format_rupiah(remaining_debt), True)
            )

        if detail.get("notes"):
            rows.append(("Catatan", detail["notes"], False))

        _add_info_rows(self.body, rows, wraplength=INFO_WRAP_NARROW)

        self.set_buttons("Cetak", self._print, "Tutup")
        self.finish()

    def _print(self):
        detail = self.detail

        _open_pdf(
            self,
            "payment",
            {
                "payment_id": detail.get("id"),
                "customer_name": detail.get("customer_name"),
                "payment_date": detail.get("payment_date"),
                "amount": detail.get("amount", 0),
                "total_debt_at_payment": detail.get(
                    "total_debt_at_payment", 0
                ),
                "remaining_debt_at_payment": detail.get(
                    "remaining_debt_at_payment", 0
                ),
                "notes": detail.get("notes"),
            },
            "Gagal membuat atau membuka dokumen PDF pembayaran.",
        )