import os
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.purchase import PurchaseModel


class PurchaseModelTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.purchase_model = PurchaseModel(self.db)

        self._create_supplier(1, "Supplier A")
        self._create_supplier(2, "Supplier B")

        self._create_product(
            1,
            "Barang A",
            purchase_price=10000,
            selling_price=15000,
            stock=10,
            supplier_id=1,
        )

        self._create_product(
            2,
            "Barang B",
            purchase_price=20000,
            selling_price=30000,
            stock=5,
            supplier_id=2,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_supplier(self, supplier_id, name):
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO suppliers (id, name)
                VALUES (?, ?);
                """,
                (supplier_id, name),
            )

    def _create_product(
        self,
        product_id,
        name,
        purchase_price,
        selling_price,
        stock,
        supplier_id,
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
                    supplier_id
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
                    supplier_id,
                ),
            )

    def test_purchase_increases_stock(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 5,
                    "price": 11000,
                }
            ]
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(transaction_id)

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT stock
                FROM products
                WHERE id = 1;
                """
            ).fetchone()

        self.assertEqual(row["stock"], 15)

    def test_purchase_price_becomes_latest_purchase_price(self):
        success, message, _ = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 2,
                    "price": 12500,
                }
            ]
        )

        self.assertTrue(success, message)

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT purchase_price, selling_price
                FROM products
                WHERE id = 1;
                """
            ).fetchone()

        self.assertEqual(row["purchase_price"], 12500)
        self.assertEqual(row["selling_price"], 15000)

    def test_purchase_can_contain_multiple_suppliers(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 3,
                    "price": 11000,
                },
                {
                    "product_id": 2,
                    "quantity": 4,
                    "price": 22000,
                },
            ]
        )

        self.assertTrue(success, message)

        detail = self.purchase_model.get_transaction_detail(transaction_id)

        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["items"]), 2)
        self.assertEqual(detail["total_amount"], (3 * 11000) + (4 * 22000))

    def test_purchase_preserves_selling_price(self):
        success, message, _ = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 1,
                    "price": 13000,
                }
            ]
        )

        self.assertTrue(success, message)

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT selling_price
                FROM products
                WHERE id = 1;
                """
            ).fetchone()

        self.assertEqual(row["selling_price"], 15000)

    def test_purchase_detail_uses_master_product_name(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "product_name": "NAMA PALSU",
                    "quantity": 2,
                    "price": 11000,
                }
            ]
        )

        self.assertTrue(success, message)

        detail = self.purchase_model.get_transaction_detail(transaction_id)

        self.assertEqual(detail["items"][0]["product_name"], "Barang A")

    def test_quantity_must_be_positive(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 0,
                    "price": 10000,
                }
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

    def test_negative_quantity_is_rejected(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": -2,
                    "price": 10000,
                }
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

    def test_negative_price_is_rejected(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 2,
                    "price": -1000,
                }
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

    def test_unknown_product_is_rejected(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 9999,
                    "quantity": 2,
                    "price": 10000,
                }
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

    def test_inactive_product_is_rejected(self):
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE products
                SET is_active = 0
                WHERE id = 1;
                """
            )

        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 2,
                    "price": 10000,
                }
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

    def test_transaction_is_atomic_when_one_item_fails(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 5,
                    "price": 11000,
                },
                {
                    "product_id": 9999,
                    "quantity": 5,
                    "price": 20000,
                },
            ]
        )

        self.assertFalse(success)
        self.assertIsNone(transaction_id)

        with self.db.transaction() as conn:
            product = conn.execute(
                """
                SELECT stock, purchase_price
                FROM products
                WHERE id = 1;
                """
            ).fetchone()

            purchase_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM purchases;
                """
            ).fetchone()["total"]

            detail_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM purchase_details;
                """
            ).fetchone()["total"]

        self.assertEqual(product["stock"], 10)
        self.assertEqual(product["purchase_price"], 10000)
        self.assertEqual(purchase_count, 0)
        self.assertEqual(detail_count, 0)

    def test_transaction_number_is_generated(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 1,
                    "price": 10500,
                }
            ]
        )

        self.assertTrue(success, message)

        detail = self.purchase_model.get_transaction_detail(transaction_id)

        self.assertRegex(
            detail["transaction_number"],
            r"^PB-\d{8}-\d{4}$",
        )

    def test_purchase_list_transactions(self):
        success, message, transaction_id = self.purchase_model.create_transaction(
            items=[
                {
                    "product_id": 1,
                    "quantity": 2,
                    "price": 11000,
                }
            ]
        )

        self.assertTrue(success, message)

        rows = self.purchase_model.list_transactions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], transaction_id)


if __name__ == "__main__":
    unittest.main()