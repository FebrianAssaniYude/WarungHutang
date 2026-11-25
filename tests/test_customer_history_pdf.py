"""
Tes data dan PDF riwayat pelanggan.

Semua tes memakai database sementara dan tidak menyentuh
`data/warung.db`. PDF dibuat di folder sementara pytest.
"""

import os

from database.database import Database
from models.customer import CustomerModel
from utils.printer import Printer


# ----------------------------------------------------------------------
# Helper database
# ----------------------------------------------------------------------


def _create_database(tmp_path) -> Database:
    db = Database(db_path=str(tmp_path / "warung.db"))
    db.initialize()
    return db


def _seed_customer_with_debt(db: Database):
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name) VALUES (?);",
            ("Pelanggan Uji",),
        )
        customer_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO products (
                name, price, purchase_price, selling_price, stock
            ) VALUES (?, ?, ?, ?, ?);
            """,
            ("Indomie", 3000, 2500, 3000, 10),
        )
        indomie_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO products (
                name, price, purchase_price, selling_price, stock
            ) VALUES (?, ?, ?, ?, ?);
            """,
            ("Kopi", 3000, 2000, 3000, 10),
        )
        kopi_id = cursor.lastrowid

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
                12000,
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
            (debt_id, indomie_id, "Indomie", 2, 3000, 6000),
        )
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
            (debt_id, kopi_id, "Kopi", 2, 3000, 6000),
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
                5000,
                "Pembayaran uji",
                12000,
                7000,
            ),
        )

    return customer_id


def _history_payload():
    return {
        "customer_id": 1,
        "customer_name": "Pelanggan Uji",
        "total_debt": 12000,
        "total_paid": 5000,
        "sisa": 7000,
        "timeline": [
            {
                "id": 2,
                "transaction_number": None,
                "date": "2026-11-02 09:00:00",
                "type": "Pembayaran",
                "amount": 5000,
                "notes": "Pembayaran uji",
                "items": [],
            },
            {
                "id": 1,
                "transaction_number": "HUT-UJI-001",
                "date": "2026-11-01 10:00:00",
                "type": "Hutang",
                "amount": 12000,
                "notes": "Hutang uji",
                "items": [
                    {
                        "product_id": 1,
                        "product_name": "Indomie",
                        "quantity": 2,
                        "price": 3000,
                        "subtotal": 6000,
                    },
                    {
                        "product_id": 2,
                        "product_name": "Kopi",
                        "quantity": 2,
                        "price": 3000,
                        "subtotal": 6000,
                    },
                ],
            },
        ],
    }


def _collect_text(flowable) -> str:
    """Mengumpulkan teks dari Paragraph/Table reportlab tanpa parsing PDF."""
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


def test_get_detail_includes_debt_items(tmp_path):
    db = _create_database(tmp_path)
    customer_id = _seed_customer_with_debt(db)

    detail = CustomerModel(db).get_detail(customer_id)

    assert detail is not None
    assert detail["timeline"]

    debt = next(
        entry
        for entry in detail["timeline"]
        if entry["type"] == "Hutang"
    )
    payment = next(
        entry
        for entry in detail["timeline"]
        if entry["type"] == "Pembayaran"
    )

    assert debt["transaction_number"] == "HUT-UJI-001"
    assert [item["product_name"] for item in debt["items"]] == [
        "Indomie",
        "Kopi",
    ]
    assert debt["items"][0]["quantity"] == 2
    assert debt["items"][0]["price"] == 3000
    assert debt["items"][0]["subtotal"] == 6000
    assert payment["items"] == []


def test_get_detail_legacy_debt_without_items(tmp_path):
    db = _create_database(tmp_path)

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
            (customer_id, "2026-10-01 08:00:00", 1000, None),
        )

    detail = CustomerModel(db).get_detail(customer_id)
    debt = detail["timeline"][0]

    assert debt["type"] == "Hutang"
    assert debt["items"] == []


def test_get_detail_legacy_detail_with_null_product_id(tmp_path):
    db = _create_database(tmp_path)

    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name) VALUES (?);",
            ("Pelanggan Legacy",),
        )
        customer_id = cursor.lastrowid
        cursor = conn.execute(
            """
            INSERT INTO debt_transactions (
                customer_id, transaction_date, total_amount, notes
            ) VALUES (?, ?, ?, ?);
            """,
            (customer_id, "2026-10-01 08:00:00", 1000, None),
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
            (debt_id, None, "Barang Lama", 1, 1000, 1000),
        )

    detail = CustomerModel(db).get_detail(customer_id)
    items = detail["timeline"][0]["items"]

    assert len(items) == 1
    assert items[0]["product_id"] is None
    assert items[0]["product_name"] == "Barang Lama"


# ----------------------------------------------------------------------
# Printer
# ----------------------------------------------------------------------


def test_customer_history_pdf_contains_item_details(tmp_path):
    printer = Printer(store_name="Warung Uji")
    payload = _history_payload()

    flowables = printer._build_customer_history_document(
        payload,
        printer._build_styles(),
    )
    text = _document_text(flowables)

    assert "Rincian Barang per Transaksi" in text
    assert "HUT-UJI-001" in text
    assert "Indomie" in text
    assert "Kopi" in text
    assert "Rp 6.000" in text
    assert "Total transaksi: Rp 12.000" in text

    output_path = str(tmp_path / "riwayat_pelanggan.pdf")
    printer.create_pdf(
        "customer_history",
        payload,
        output_path=output_path,
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_customer_history_pdf_notes_legacy_without_items(tmp_path):
    printer = Printer(store_name="Warung Uji")
    payload = _history_payload()
    payload["timeline"] = [
        {
            "id": 1,
            "transaction_number": None,
            "date": "2026-10-01 08:00:00",
            "type": "Hutang",
            "amount": 1000,
            "notes": None,
            "items": [],
        }
    ]

    flowables = printer._build_customer_history_document(
        payload,
        printer._build_styles(),
    )
    text = _document_text(flowables)

    assert "Rincian Barang per Transaksi" in text
    assert "Tidak ada rincian barang tersimpan" in text

    output_path = str(tmp_path / "riwayat_legacy.pdf")
    printer.create_pdf(
        "customer_history",
        payload,
        output_path=output_path,
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_customer_history_without_debt_has_no_item_section(tmp_path):
    printer = Printer(store_name="Warung Uji")
    payload = _history_payload()
    payload["timeline"] = [
        entry
        for entry in payload["timeline"]
        if entry["type"] != "Hutang"
    ]

    flowables = printer._build_customer_history_document(
        payload,
        printer._build_styles(),
    )
    text = _document_text(flowables)

    assert "Rincian Barang per Transaksi" not in text
