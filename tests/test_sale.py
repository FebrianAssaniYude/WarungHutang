import os
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.sale import SaleModel


class SaleModelTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.sale_model = SaleModel(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_product(
        self,
        name="Indomie Goreng",
        selling_price=3500,
        stock=10,
        is_active=1,
    ):
        conn = self.db.connect()

        try:
            cursor = conn.execute(
                """
                INSERT INTO products (
                    barcode,
                    name,
                    price,
                    purchase_price,
                    selling_price,
                    stock,
                    opening_stock,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    name,
                    selling_price,
                    selling_price,
                    selling_price,
                    stock,
                    stock,
                    is_active,
                ),
            )

            conn.commit()
            return cursor.lastrowid

        finally:
            conn.close()

    def _get_product(self, product_id):
        conn = self.db.connect()

        try:
            return conn.execute(
                """
                SELECT
                    id,
                    name,
                    selling_price,
                    stock,
                    is_active
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()

        finally:
            conn.close()

    def test_create_sale_transaction(self):
        product_id = self._create_product()

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=10000,
        )

        self.assertTrue(success)
        self.assertIn("berhasil", message.lower())
        self.assertIsNotNone(sale_id)

    def test_sale_generates_transaction_number(self):
        product_id = self._create_product()

        success, message, sale_id = self.sale_model.create_transaction(
            items=[{"product_id": product_id, "quantity": 1}],
            paid_amount=5000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertIsNotNone(detail)
        self.assertRegex(
            detail["sale"]["transaction_number"],
            r"^JL-\d{8}-\d{4}$",
        )

    def test_sale_transaction_numbers_are_unique(self):
        product1 = self._create_product(
            name="Produk A",
            selling_price=2000,
            stock=10,
        )

        product2 = self._create_product(
            name="Produk B",
            selling_price=3000,
            stock=10,
        )

        success1, _, sale_id1 = self.sale_model.create_transaction(
            items=[{"product_id": product1, "quantity": 1}],
            paid_amount=2000,
        )

        success2, _, sale_id2 = self.sale_model.create_transaction(
            items=[{"product_id": product2, "quantity": 1}],
            paid_amount=3000,
        )

        self.assertTrue(success1)
        self.assertTrue(success2)

        detail1 = self.sale_model.get_transaction_detail(sale_id1)
        detail2 = self.sale_model.get_transaction_detail(sale_id2)

        self.assertNotEqual(
            detail1["sale"]["transaction_number"],
            detail2["sale"]["transaction_number"],
        )

    def test_sale_uses_master_selling_price(self):
        product_id = self._create_product(
            name="Teh Botol",
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=10000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["details"][0]["price"],
            5000,
        )

        self.assertEqual(
            detail["details"][0]["subtotal"],
            10000,
        )

    def test_sale_uses_master_product_name(self):
        product_id = self._create_product(
            name="Aqua 600ml",
            selling_price=4000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=4000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["details"][0]["product_name"],
            "Aqua 600ml",
        )

    def test_sale_decreases_stock(self):
        product_id = self._create_product(
            selling_price=3000,
            stock=10,
        )

        success, _, _ = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 3,
                }
            ],
            paid_amount=10000,
        )

        self.assertTrue(success)

        product = self._get_product(product_id)

        self.assertEqual(product["stock"], 7)

    def test_sale_multiple_products_decreases_stock(self):
        product1 = self._create_product(
            name="Produk A",
            selling_price=2000,
            stock=10,
        )

        product2 = self._create_product(
            name="Produk B",
            selling_price=3000,
            stock=20,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product1,
                    "quantity": 2,
                },
                {
                    "product_id": product2,
                    "quantity": 4,
                },
            ],
            paid_amount=20000,
        )

        self.assertTrue(success)

        self.assertEqual(
            self._get_product(product1)["stock"],
            8,
        )

        self.assertEqual(
            self._get_product(product2)["stock"],
            16,
        )

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(len(detail["details"]), 2)

    def test_sale_rejects_insufficient_stock(self):
        product_id = self._create_product(
            selling_price=3000,
            stock=2,
        )

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 3,
                }
            ],
            paid_amount=10000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("stok", message.lower())

        self.assertEqual(
            self._get_product(product_id)["stock"],
            2,
        )

    def test_sale_rejects_zero_quantity(self):
        product_id = self._create_product()

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 0,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("quantity", message.lower())

    def test_sale_rejects_negative_quantity(self):
        product_id = self._create_product()

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": -1,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("quantity", message.lower())

    def test_sale_rejects_unknown_product(self):
        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": 999999,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("tidak ditemukan", message.lower())

    def test_sale_rejects_inactive_product(self):
        product_id = self._create_product(
            name="Produk Nonaktif",
            selling_price=5000,
            stock=10,
            is_active=0,
        )

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("tidak aktif", message.lower())

    def test_sale_rejects_manual_item(self):
        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": None,
                    "quantity": 1,
                    "product_name": "Barang Manual",
                    "price": 5000,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)

    def test_sale_rejects_empty_items(self):
        success, message, sale_id = self.sale_model.create_transaction(
            items=[],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("tidak ada", message.lower())

    def test_sale_rejects_insufficient_payment(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=5000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)
        self.assertIn("kurang", message.lower())

        self.assertEqual(
            self._get_product(product_id)["stock"],
            10,
        )

    def test_sale_accepts_exact_payment(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=10000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["sale"]["paid_amount"],
            10000,
        )

        self.assertEqual(
            detail["sale"]["change_amount"],
            0,
        )

    def test_sale_calculates_change(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=15000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["sale"]["total_amount"],
            10000,
        )

        self.assertEqual(
            detail["sale"]["paid_amount"],
            15000,
        )

        self.assertEqual(
            detail["sale"]["change_amount"],
            5000,
        )

    def test_sale_saves_notes(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
            notes="Pelanggan bayar tunai",
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["sale"]["notes"],
            "Pelanggan bayar tunai",
        )

    def test_sale_snapshot_remains_after_product_change(self):
        product_id = self._create_product(
            name="Produk Lama",
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
            paid_amount=10000,
        )

        self.assertTrue(success)

        conn = self.db.connect()

        try:
            conn.execute(
                """
                UPDATE products
                SET name = ?, selling_price = ?
                WHERE id = ?
                """,
                (
                    "Produk Baru",
                    7000,
                    product_id,
                ),
            )
            conn.commit()

        finally:
            conn.close()

        detail = self.sale_model.get_transaction_detail(sale_id)

        self.assertEqual(
            detail["details"][0]["product_name"],
            "Produk Lama",
        )

        self.assertEqual(
            detail["details"][0]["price"],
            5000,
        )

        self.assertEqual(
            detail["details"][0]["subtotal"],
            10000,
        )

    def test_sale_is_atomic_when_second_product_fails(self):
        product1 = self._create_product(
            name="Produk Aman",
            selling_price=2000,
            stock=10,
        )

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product1,
                    "quantity": 2,
                },
                {
                    "product_id": 999999,
                    "quantity": 1,
                },
            ],
            paid_amount=10000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)

        self.assertEqual(
            self._get_product(product1)["stock"],
            10,
        )

        conn = self.db.connect()

        try:
            count = conn.execute(
                "SELECT COUNT(*) AS total FROM sales"
            ).fetchone()["total"]

            self.assertEqual(count, 0)

        finally:
            conn.close()

    def test_sale_is_atomic_when_second_product_has_insufficient_stock(self):
        product1 = self._create_product(
            name="Produk Aman",
            selling_price=2000,
            stock=10,
        )

        product2 = self._create_product(
            name="Produk Stok Sedikit",
            selling_price=3000,
            stock=1,
        )

        success, message, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product1,
                    "quantity": 2,
                },
                {
                    "product_id": product2,
                    "quantity": 2,
                },
            ],
            paid_amount=10000,
        )

        self.assertFalse(success)
        self.assertIsNone(sale_id)

        self.assertEqual(
            self._get_product(product1)["stock"],
            10,
        )

        self.assertEqual(
            self._get_product(product2)["stock"],
            1,
        )

        conn = self.db.connect()

        try:
            count = conn.execute(
                "SELECT COUNT(*) AS total FROM sales"
            ).fetchone()["total"]

            self.assertEqual(count, 0)

        finally:
            conn.close()

    def test_get_transaction_detail_nonexistent(self):
        result = self.sale_model.get_transaction_detail(999999)

        self.assertIsNone(result)

    def test_list_transactions(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, _ = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
            notes="Tes penjualan",
        )

        self.assertTrue(success)

        rows = self.sale_model.list_transactions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_amount"], 5000)

    def test_list_transactions_searches_transaction_number(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, sale_id = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
        )

        self.assertTrue(success)

        detail = self.sale_model.get_transaction_detail(sale_id)
        transaction_number = detail["sale"]["transaction_number"]

        rows = self.sale_model.list_transactions(
            search=transaction_number
        )

        self.assertEqual(len(rows), 1)

    def test_list_transactions_searches_notes(self):
        product_id = self._create_product(
            selling_price=5000,
            stock=10,
        )

        success, _, _ = self.sale_model.create_transaction(
            items=[
                {
                    "product_id": product_id,
                    "quantity": 1,
                }
            ],
            paid_amount=5000,
            notes="Pelanggan tetap",
        )

        self.assertTrue(success)

        rows = self.sale_model.list_transactions(
            search="Pelanggan tetap"
        )

        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()