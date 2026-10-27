import os
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.debt import DebtModel


class DebtModelTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp_dir.name,
            "test.db",
        )

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.debt_model = DebtModel(self.db)

        self._create_customer(
            1,
            "Budi",
        )

        self._create_customer(
            2,
            "Siti",
        )

        self._create_product(
            1,
            "Barang A",
            purchase_price=10000,
            selling_price=15000,
            stock=10,
        )

        self._create_product(
            2,
            "Barang B",
            purchase_price=20000,
            selling_price=30000,
            stock=5,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def _create_customer(self, customer_id, name):
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO customers (
                    id,
                    name
                )
                VALUES (?, ?);
                """,
                (
                    customer_id,
                    name,
                ),
            )

    def _create_product(
        self,
        product_id,
        name,
        purchase_price,
        selling_price,
        stock,
        is_active=1,
    ):
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO products (
                    id,
                    barcode,
                    name,
                    price,
                    purchase_price,
                    selling_price,
                    stock,
                    opening_stock,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    product_id,
                    f"TEST-{product_id}",
                    name,
                    selling_price,
                    purchase_price,
                    selling_price,
                    stock,
                    stock,
                    is_active,
                ),
            )

    def _get_product(self, product_id):
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    id,
                    name,
                    selling_price,
                    stock
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

    def _get_transaction(self, transaction_id):
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    customer_id,
                    total_amount,
                    notes
                FROM debt_transactions
                WHERE id = ?;
                """,
                (transaction_id,),
            ).fetchone()

    def _get_debt_counts(self):
        with self.db.transaction() as conn:
            transaction_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM debt_transactions;
                """
            ).fetchone()["total"]

            detail_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM debt_details;
                """
            ).fetchone()["total"]

        return transaction_count, detail_count

    # ------------------------------------------------------------------
    # Tambah transaksi hutang
    # ------------------------------------------------------------------
    def test_create_debt_transaction(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                    }
                ],
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(transaction_id)

        transaction = self._get_transaction(
            transaction_id
        )

        self.assertIsNotNone(transaction)
        self.assertEqual(
            transaction["customer_id"],
            1,
        )
        self.assertEqual(
            transaction["total_amount"],
            2 * 15000,
        )

    def test_debt_uses_master_selling_price(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                        "price": 999,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertEqual(
            detail["items"][0]["price"],
            15000,
        )

        self.assertEqual(
            detail["total_amount"],
            30000,
        )

    def test_debt_detail_uses_master_product_name(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "product_name": "NAMA PALSU",
                        "quantity": 2,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertEqual(
            detail["items"][0]["product_name"],
            "Barang A",
        )

    def test_debt_transaction_can_contain_multiple_products(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                    },
                    {
                        "product_id": 2,
                        "quantity": 3,
                    },
                ],
            )
        )

        self.assertTrue(success, message)

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)
        self.assertEqual(
            len(detail["items"]),
            2,
        )

        expected_total = (
            (2 * 15000)
            + (3 * 30000)
        )

        self.assertEqual(
            detail["total_amount"],
            expected_total,
        )

    # ------------------------------------------------------------------
    # Transaction number
    # ------------------------------------------------------------------
    def test_transaction_number_is_generated(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertRegex(
            detail["transaction_number"],
            r"^HT-\d{8}-\d{4}$",
        )

    def test_transaction_numbers_are_unique(self):
        success, message, first_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        success, message, second_id = (
            self.debt_model.create_transaction(
                customer_id=2,
                items=[
                    {
                        "product_id": 2,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        first = self.debt_model.get_transaction_detail(
            first_id
        )

        second = self.debt_model.get_transaction_detail(
            second_id
        )

        self.assertNotEqual(
            first["transaction_number"],
            second["transaction_number"],
        )

    # ------------------------------------------------------------------
    # Stok
    # ------------------------------------------------------------------
    def test_debt_decreases_stock(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 4,
                    }
                ],
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            6,
        )

    def test_debt_decreases_stock_for_multiple_products(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 3,
                    },
                    {
                        "product_id": 2,
                        "quantity": 2,
                    },
                ],
            )
        )

        self.assertTrue(success, message)

        product_a = self._get_product(1)
        product_b = self._get_product(2)

        self.assertEqual(
            product_a["stock"],
            7,
        )

        self.assertEqual(
            product_b["stock"],
            3,
        )

    def test_debt_cannot_make_stock_negative(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 11,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            10,
        )

    def test_debt_rejects_insufficient_stock_for_second_product(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 3,
                    },
                    {
                        "product_id": 2,
                        "quantity": 6,
                    },
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product_a = self._get_product(1)
        product_b = self._get_product(2)

        self.assertEqual(
            product_a["stock"],
            10,
        )

        self.assertEqual(
            product_b["stock"],
            5,
        )

    # ------------------------------------------------------------------
    # Validasi customer
    # ------------------------------------------------------------------
    def test_unknown_customer_is_rejected(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=9999,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    # ------------------------------------------------------------------
    # Validasi product
    # ------------------------------------------------------------------
    def test_unknown_product_is_rejected(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 9999,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    def test_inactive_product_is_rejected(self):
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE products
                SET is_active = 0
                WHERE id = 1;
                """
            )

        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 1,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            10,
        )

    def test_manual_product_id_is_rejected(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": None,
                        "product_name": "Barang Manual",
                        "quantity": 1,
                        "price": 5000,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    # ------------------------------------------------------------------
    # Validasi quantity
    # ------------------------------------------------------------------
    def test_quantity_must_be_positive(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 0,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            10,
        )

    def test_negative_quantity_is_rejected(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": -2,
                    }
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            10,
        )

    def test_empty_items_are_rejected(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------
    def test_notes_are_saved(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                    }
                ],
                notes="Hutang untuk kebutuhan warung.",
            )
        )

        self.assertTrue(success, message)

        transaction = self._get_transaction(
            transaction_id
        )

        self.assertEqual(
            transaction["notes"],
            "Hutang untuk kebutuhan warung.",
        )

    # ------------------------------------------------------------------
    # Snapshot detail
    # ------------------------------------------------------------------
    def test_debt_detail_is_snapshot(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                    }
                ],
            )
        )

        self.assertTrue(success, message)

        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE products
                SET
                    name = ?,
                    selling_price = ?
                WHERE id = 1;
                """,
                (
                    "Barang A Updated",
                    20000,
                ),
            )

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertEqual(
            detail["items"][0]["product_name"],
            "Barang A",
        )

        self.assertEqual(
            detail["items"][0]["price"],
            15000,
        )

        self.assertEqual(
            detail["items"][0]["quantity"],
            2,
        )

        self.assertEqual(
            detail["items"][0]["subtotal"],
            30000,
        )

    # ------------------------------------------------------------------
    # Atomic transaction / rollback
    # ------------------------------------------------------------------
    def test_transaction_is_atomic_when_one_item_fails(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 3,
                    },
                    {
                        "product_id": 9999,
                        "quantity": 2,
                    },
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product = self._get_product(1)

        self.assertEqual(
            product["stock"],
            10,
        )

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    def test_transaction_rolls_back_when_stock_is_insufficient(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 3,
                    },
                    {
                        "product_id": 2,
                        "quantity": 6,
                    },
                ],
            )
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        product_a = self._get_product(1)
        product_b = self._get_product(2)

        self.assertEqual(
            product_a["stock"],
            10,
        )

        self.assertEqual(
            product_b["stock"],
            5,
        )

        transaction_count, detail_count = (
            self._get_debt_counts()
        )

        self.assertEqual(
            transaction_count,
            0,
        )

        self.assertEqual(
            detail_count,
            0,
        )

    # ------------------------------------------------------------------
    # Detail transaction
    # ------------------------------------------------------------------
    def test_get_transaction_detail(self):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=1,
                items=[
                    {
                        "product_id": 1,
                        "quantity": 2,
                    }
                ],
                notes="Test detail",
            )
        )

        self.assertTrue(success, message)

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertEqual(
            detail["id"],
            transaction_id,
        )

        self.assertIsNotNone(
            detail["transaction_number"]
        )

        self.assertEqual(
            detail["customer_id"],
            1,
        )

        self.assertEqual(
            detail["total_amount"],
            30000,
        )

        self.assertEqual(
            detail["notes"],
            "Test detail",
        )

        self.assertEqual(
            len(detail["items"]),
            1,
        )

        item = detail["items"][0]

        self.assertEqual(
            item["product_id"],
            1,
        )

        self.assertEqual(
            item["product_name"],
            "Barang A",
        )

        self.assertEqual(
            item["quantity"],
            2,
        )

        self.assertEqual(
            item["price"],
            15000,
        )

        self.assertEqual(
            item["subtotal"],
            30000,
        )

    def test_get_nonexistent_transaction_detail(self):
        detail = self.debt_model.get_transaction_detail(
            999999
        )

        self.assertIsNone(detail)

    # ------------------------------------------------------------------
    # Legacy debt compatibility
    # ------------------------------------------------------------------
    def test_legacy_debt_detail_with_null_product_id_is_readable(self):
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO debt_transactions (
                    transaction_number,
                    customer_id,
                    total_amount,
                    notes
                )
                VALUES (?, ?, ?, ?);
                """,
                (
                    None,
                    1,
                    5000,
                    "Legacy debt",
                ),
            )

            transaction_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO debt_details (
                    transaction_id,
                    product_id,
                    product_name,
                    quantity,
                    price,
                    subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    transaction_id,
                    None,
                    "Barang Manual Lama",
                    1,
                    5000,
                    5000,
                ),
            )

        detail = self.debt_model.get_transaction_detail(
            transaction_id
        )

        self.assertIsNotNone(detail)

        self.assertIsNone(
            detail["transaction_number"]
        )

        self.assertEqual(
            detail["total_amount"],
            5000,
        )

        self.assertEqual(
            len(detail["items"]),
            1,
        )

        item = detail["items"][0]

        self.assertIsNone(
            item["product_id"]
        )

        self.assertEqual(
            item["product_name"],
            "Barang Manual Lama",
        )

        self.assertEqual(
            item["quantity"],
            1,
        )

        self.assertEqual(
            item["price"],
            5000,
        )

        self.assertEqual(
            item["subtotal"],
            5000,
        )


if __name__ == "__main__":
    unittest.main()