import os
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.history import HistoryModel


class TestHistoryModel(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp_dir.name,
            "test_history.db",
        )

        self.db = Database(self.db_path)

        with self.db.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                );

                CREATE TABLE debt_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_number TEXT UNIQUE,
                    customer_id INTEGER NOT NULL,
                    transaction_date TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    notes TEXT
                );

                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    payment_date TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    notes TEXT
                );

                CREATE TABLE purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_number TEXT NOT NULL UNIQUE,
                    transaction_date TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    notes TEXT
                );

                CREATE TABLE sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_number TEXT NOT NULL UNIQUE,
                    transaction_date TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    paid_amount INTEGER NOT NULL,
                    change_amount INTEGER NOT NULL,
                    notes TEXT
                );
                """
            )

            conn.execute(
                "INSERT INTO customers (name) VALUES (?)",
                ("Rian",),
            )

            conn.execute(
                "INSERT INTO customers (name) VALUES (?)",
                ("Baron",),
            )

            # Hutang Rian
            conn.execute(
                """
                INSERT INTO debt_transactions (
                    transaction_number,
                    customer_id,
                    transaction_date,
                    total_amount
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "HT-20260927-0001",
                    1,
                    "2026-09-27 08:00:00",
                    10000,
                ),
            )

            # Hutang Baron
            conn.execute(
                """
                INSERT INTO debt_transactions (
                    transaction_number,
                    customer_id,
                    transaction_date,
                    total_amount
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "HT-20260927-0002",
                    2,
                    "2026-09-27 09:00:00",
                    20000,
                ),
            )

            # Pembayaran Rian
            conn.execute(
                """
                INSERT INTO payments (
                    customer_id,
                    payment_date,
                    amount
                )
                VALUES (?, ?, ?)
                """,
                (
                    1,
                    "2026-09-27 10:00:00",
                    3000,
                ),
            )

            # Pembayaran Baron
            conn.execute(
                """
                INSERT INTO payments (
                    customer_id,
                    payment_date,
                    amount
                )
                VALUES (?, ?, ?)
                """,
                (
                    2,
                    "2026-09-27 11:00:00",
                    5000,
                ),
            )

            # Pembelian
            conn.execute(
                """
                INSERT INTO purchases (
                    transaction_number,
                    transaction_date,
                    total_amount
                )
                VALUES (?, ?, ?)
                """,
                (
                    "PB-20260927-0001",
                    "2026-09-27 12:00:00",
                    50000,
                ),
            )

            # Penjualan
            conn.execute(
                """
                INSERT INTO sales (
                    transaction_number,
                    transaction_date,
                    total_amount,
                    paid_amount,
                    change_amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "JL-20260927-0001",
                    "2026-09-27 13:00:00",
                    25000,
                    30000,
                    5000,
                ),
            )

        self.model = HistoryModel(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    # =========================================================
    # SEMUA
    # =========================================================

    def test_list_all_history(self):
        entries = self.model.list_history("semua")

        self.assertEqual(len(entries), 6)

        types = [entry["type"] for entry in entries]

        self.assertIn("Hutang", types)
        self.assertIn("Pembayaran", types)
        self.assertIn("Pembelian", types)
        self.assertIn("Penjualan", types)

    # =========================================================
    # HUTANG
    # =========================================================

    def test_list_hutang(self):
        entries = self.model.list_history("hutang")

        self.assertEqual(len(entries), 2)

        self.assertEqual(
            entries[0]["type"],
            "Hutang",
        )

        self.assertEqual(
            entries[0]["amount"],
            20000,
        )

    # =========================================================
    # PEMBAYARAN
    # =========================================================

    def test_list_pembayaran(self):
        entries = self.model.list_history("pembayaran")

        self.assertEqual(len(entries), 2)

        self.assertEqual(
            entries[0]["type"],
            "Pembayaran",
        )

        self.assertEqual(
            entries[0]["amount"],
            5000,
        )

    # =========================================================
    # PEMBELIAN
    # =========================================================

    def test_list_pembelian(self):
        entries = self.model.list_history("pembelian")

        self.assertEqual(len(entries), 1)

        entry = entries[0]

        self.assertEqual(
            entry["type"],
            "Pembelian",
        )

        self.assertEqual(
            entry["amount"],
            50000,
        )

        self.assertEqual(
            entry["customer_id"],
            None,
        )

        self.assertEqual(
            entry["customer_name"],
            "-",
        )

        self.assertEqual(
            entry["transaction_number"],
            "PB-20260927-0001",
        )

    # =========================================================
    # PENJUALAN
    # =========================================================

    def test_list_penjualan(self):
        entries = self.model.list_history("penjualan")

        self.assertEqual(len(entries), 1)

        entry = entries[0]

        self.assertEqual(
            entry["type"],
            "Penjualan",
        )

        self.assertEqual(
            entry["amount"],
            25000,
        )

        self.assertEqual(
            entry["customer_id"],
            None,
        )

        self.assertEqual(
            entry["customer_name"],
            "-",
        )

        self.assertEqual(
            entry["transaction_number"],
            "JL-20260927-0001",
        )

    # =========================================================
    # FILTER CUSTOMER
    # =========================================================

    def test_customer_filter(self):
        entries = self.model.list_history(
            type_filter="semua",
            customer_id=1,
        )

        self.assertEqual(len(entries), 2)

        for entry in entries:
            self.assertEqual(
                entry["customer_id"],
                1,
            )

        types = [entry["type"] for entry in entries]

        self.assertIn("Hutang", types)
        self.assertIn("Pembayaran", types)

    # =========================================================
    # FILTER CUSTOMER BARON
    # =========================================================

    def test_customer_filter_baron(self):
        entries = self.model.list_history(
            type_filter="semua",
            customer_id=2,
        )

        self.assertEqual(len(entries), 2)

        for entry in entries:
            self.assertEqual(
                entry["customer_id"],
                2,
            )

    # =========================================================
    # FILTER DATE FROM
    # =========================================================

    def test_date_from_filter(self):
        entries = self.model.list_history(
            type_filter="semua",
            date_from="2026-09-27",
        )

        self.assertEqual(len(entries), 6)

    # =========================================================
    # FILTER DATE TO
    # =========================================================

    def test_date_to_filter(self):
        entries = self.model.list_history(
            type_filter="semua",
            date_to="2026-09-26",
        )

        self.assertEqual(len(entries), 0)

    # =========================================================
    # RANGE DATE
    # =========================================================

    def test_date_range_filter(self):
        entries = self.model.list_history(
            type_filter="semua",
            date_from="2026-09-27",
            date_to="2026-09-27",
        )

        self.assertEqual(len(entries), 6)

    # =========================================================
    # INVALID TYPE FILTER
    # =========================================================

    def test_invalid_type_filter_defaults_to_all(self):
        entries = self.model.list_history(
            type_filter="tidak-valid",
        )

        self.assertEqual(len(entries), 6)

    # =========================================================
    # ORDER
    # =========================================================

    def test_history_sorted_newest_first(self):
        entries = self.model.list_history("semua")

        dates = [
            entry["date"]
            for entry in entries
        ]

        self.assertEqual(
            dates,
            sorted(
                dates,
                reverse=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()