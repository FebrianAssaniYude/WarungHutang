"""
Tes laporan bulanan: agregasi rincian barang dan isi PDF.

Semua tes memakai database sementara dan tidak menyentuh
`data/warung.db`.
"""

import os

from database.database import Database
from models.report import ReportModel
from utils.printer import Printer


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------

def _create_database(tmp_path) -> Database:
    db = Database(db_path=str(tmp_path / "warung.db"))
    db.initialize()
    return db


def _seed_report_data(db: Database):
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name) VALUES (?);",
            ("Budi",),
        )
        customer_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO products (
                name, price, purchase_price, selling_price, stock
            ) VALUES (?, ?, ?, ?, ?);
            """,
            ("Indomie", 3500, 2500, 3500, 20),
        )
        indomie_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO products (
                name, price, purchase_price, selling_price, stock
            ) VALUES (?, ?, ?, ?, ?);
            """,
            ("Kopi", 2000, 1500, 2000, 20),
        )
        kopi_id = cursor.lastrowid

        cursor = conn.execute(
            "INSERT INTO suppliers (name) VALUES (?);",
            ("Supplier Uji",),
        )
        supplier_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO debt_transactions (
                customer_id,
                transaction_date,
                total_amount,
                notes,
                transaction_number
            ) VALUES (?, ?, ?, ?, ?);
            """,
            (
                customer_id,
                "2026-11-01 10:00:00",
                7000,
                "Hutang uji",
                "HUT-UJI-001",
            ),
        )
        debt_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO debt_details (
                transaction_id,
                product_id,
                product_name,
                quantity,
                price,
                subtotal
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (debt_id, indomie_id, "Indomie", 2, 3500, 7000),
        )

        conn.execute(
            """
            INSERT INTO payments (
                customer_id,
                payment_date,
                amount,
                notes,
                total_debt_at_payment,
                remaining_debt_at_payment
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                customer_id,
                "2026-11-02 09:00:00",
                3000,
                "Bayar sebagian",
                7000,
                4000,
            ),
        )

        cursor = conn.execute(
            """
            INSERT INTO purchases (
                transaction_number,
                transaction_date,
                supplier_id,
                total_amount,
                notes
            ) VALUES (?, ?, ?, ?, ?);
            """,
            (
                "PB-UJI-001",
                "2026-11-03 11:00:00",
                supplier_id,
                8000,
                "Beli stok",
            ),
        )
        purchase_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO purchase_details (
                purchase_id,
                product_id,
                product_name,
                quantity,
                price,
                subtotal
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (purchase_id, indomie_id, "Indomie", 2, 2500, 5000),
        )
        conn.execute(
            """
            INSERT INTO purchase_details (
                purchase_id,
                product_id,
                product_name,
                quantity,
                price,
                subtotal
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (purchase_id, kopi_id, "Kopi", 2, 1500, 3000),
        )

    return {
        "customer_id": customer_id,
        "purchase_id": purchase_id,
    }


def _seed_legacy_debt(db: Database):
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name) VALUES (?);",
            ("Pelanggan Legacy",),
        )
        customer_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO debt_transactions (
                customer_id, transaction_date, total_amount, notes
            ) VALUES (?, ?, ?, ?);
            """,
            (customer_id, "2026-11-05 08:00:00", 1000, None),
        )

    return customer_id


def _collect_text(flowable) -> str:
    """Kumpulkan teks dari Paragraph/Table reportlab tanpa parsing PDF."""
    parts = []

    text = getattr(flowable, "text", None)
    if isinstance(text, str):
        parts.append(text)

    cells = getattr(flowable, "_cellvalues", None)
    if cells:
        for row in cells:
            for cell in row:
                parts.append(_collect_text(cell))

    return " ".join(parts)


def _document_text(flowables) -> str:
    return " ".join(_collect_text(item) for item in flowables)


# ----------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------

def test_get_monthly_report_includes_items_and_purchases(tmp_path):
    db = _create_database(tmp_path)
    _seed_report_data(db)

    report = ReportModel(db).get_monthly_report(2026, 11)

    assert report["total_debt_month"] == 7000
    assert report["count_debt_transactions"] == 1
    assert report["total_purchase_month"] == 8000
    assert report["count_purchase_month"] == 1
    assert report["total_purchase_items_month"] == 4

    debt = next(
        item
        for item in report["details"]
        if item["type"] == "Hutang"
    )
    payment = next(
        item
        for item in report["details"]
        if item["type"] == "Pembayaran"
    )

    assert debt["transaction_number"] == "HUT-UJI-001"
    assert [item["product_name"] for item in debt["items"]] == [
        "Indomie",
    ]
    assert debt["items"][0]["quantity"] == 2
    assert debt["items"][0]["subtotal"] == 7000
    assert payment["items"] == []

    assert len(report["purchases"]) == 1

    purchase = report["purchases"][0]
    assert purchase["transaction_number"] == "PB-UJI-001"
    assert purchase["supplier_name"] == "Supplier Uji"
    assert purchase["total_amount"] == 8000
    assert [item["product_name"] for item in purchase["items"]] == [
        "Indomie",
        "Kopi",
    ]


def test_get_monthly_report_legacy_debt_without_items(tmp_path):
    db = _create_database(tmp_path)
    _seed_legacy_debt(db)

    report = ReportModel(db).get_monthly_report(2026, 11)

    debt = next(
        item
        for item in report["details"]
        if item["type"] == "Hutang"
    )

    assert debt["items"] == []
    assert report["purchases"] == []
    assert report["total_purchase_month"] == 0
    assert report["count_purchase_month"] == 0


# ----------------------------------------------------------------------
# Printer
# ----------------------------------------------------------------------

def test_monthly_report_pdf_contains_items_and_purchases(tmp_path):
    db = _create_database(tmp_path)
    _seed_report_data(db)
    report = ReportModel(db).get_monthly_report(2026, 11)

    printer = Printer(store_name="Warung Uji")
    flowables = printer._build_monthly_report_document(
        report,
        printer._build_styles(),
    )
    text = _document_text(flowables)

    assert "Rincian Barang Hutang per Transaksi" in text
    assert "HUT-UJI-001" in text
    assert "Indomie" in text

    assert "Riwayat Pembelian Bulan Ini" in text
    assert "PB-UJI-001" in text
    assert "Supplier Uji" in text
    assert "Rincian Barang Pembelian per Transaksi" in text
    assert "Kopi" in text

    output_path = str(tmp_path / "laporan_bulanan.pdf")
    printer.create_pdf(
        "monthly_report",
        report,
        output_path=output_path,
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_monthly_report_pdf_without_purchases(tmp_path):
    db = _create_database(tmp_path)
    _seed_legacy_debt(db)
    report = ReportModel(db).get_monthly_report(2026, 11)

    printer = Printer(store_name="Warung Uji")
    flowables = printer._build_monthly_report_document(
        report,
        printer._build_styles(),
    )
    text = _document_text(flowables)

    assert "Riwayat Pembelian Bulan Ini" in text
    assert "Tidak ada pembelian pada bulan ini." in text
    assert "Rincian Barang Pembelian per Transaksi" not in text
    assert "Tidak ada rincian barang tersimpan" in text

    output_path = str(tmp_path / "laporan_tanpa_pembelian.pdf")
    printer.create_pdf(
        "monthly_report",
        report,
        output_path=output_path,
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_export_to_pdf_uses_printer_engine(tmp_path):
    db = _create_database(tmp_path)
    _seed_report_data(db)
    report = ReportModel(db).get_monthly_report(2026, 11)

    output_path = str(tmp_path / "laporan_export.pdf")

    result = ReportModel(db).export_to_pdf(
        report,
        output_path,
        store_name="Warung Uji",
    )

    assert result == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
