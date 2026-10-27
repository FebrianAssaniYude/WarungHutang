import os
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.supplier import SupplierModel


class TestSupplierModel(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_supplier.db")

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.model = SupplierModel(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_supplier(self):
        success, message, supplier_id = self.model.add_supplier(
            "PT Supplier A",
            "Supplier utama",
        )

        self.assertTrue(success)
        self.assertEqual(message, "Supplier berhasil ditambahkan.")
        self.assertIsNotNone(supplier_id)

        supplier = self.model.get_by_id(supplier_id)

        self.assertIsNotNone(supplier)
        self.assertEqual(supplier["name"], "PT Supplier A")
        self.assertEqual(supplier["notes"], "Supplier utama")

    def test_add_supplier_without_name(self):
        success, message, supplier_id = self.model.add_supplier("")

        self.assertFalse(success)
        self.assertEqual(message, "Nama supplier wajib diisi.")
        self.assertIsNone(supplier_id)

    def test_duplicate_supplier(self):
        self.model.add_supplier("Supplier Sama")

        success, message, supplier_id = self.model.add_supplier(
            "Supplier Sama"
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Nama supplier tersebut sudah digunakan.",
        )
        self.assertIsNone(supplier_id)

    def test_list_and_search_supplier(self):
        self.model.add_supplier("PT ABC")
        self.model.add_supplier("CV Maju Jaya")
        self.model.add_supplier("Toko Sumber Rezeki")

        suppliers = self.model.list_suppliers()

        self.assertEqual(len(suppliers), 3)

        results = self.model.list_suppliers("maju")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "CV Maju Jaya")

    def test_update_supplier(self):
        success, _, supplier_id = self.model.add_supplier(
            "Supplier Lama"
        )

        self.assertTrue(success)

        success, message = self.model.update_supplier(
            supplier_id,
            "Supplier Baru",
            "Catatan baru",
        )

        self.assertTrue(success)
        self.assertEqual(
            message,
            "Data supplier berhasil diperbarui.",
        )

        supplier = self.model.get_by_id(supplier_id)

        self.assertEqual(supplier["name"], "Supplier Baru")
        self.assertEqual(supplier["notes"], "Catatan baru")

    def test_update_nonexistent_supplier(self):
        success, message = self.model.update_supplier(
            999999,
            "Supplier Baru",
        )

        self.assertFalse(success)
        self.assertEqual(message, "Supplier tidak ditemukan.")

    def test_delete_unused_supplier(self):
        success, _, supplier_id = self.model.add_supplier(
            "Supplier Hapus"
        )

        self.assertTrue(success)

        success, message = self.model.delete_supplier(supplier_id)

        self.assertTrue(success)
        self.assertEqual(
            message,
            "Supplier berhasil dihapus.",
        )

        self.assertIsNone(
            self.model.get_by_id(supplier_id)
        )

    def test_delete_supplier_used_by_product(self):
        success, _, supplier_id = self.model.add_supplier(
            "Supplier Produk"
        )

        self.assertTrue(success)

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO products (
                    name,
                    price,
                    purchase_price,
                    selling_price,
                    stock,
                    opening_stock,
                    supplier_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "Produk Test",
                    1000,
                    1000,
                    1500,
                    10,
                    10,
                    supplier_id,
                ),
            )

        success, message = self.model.delete_supplier(supplier_id)

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Supplier tidak dapat dihapus karena masih digunakan oleh barang.",
        )

        self.assertIsNotNone(
            self.model.get_by_id(supplier_id)
        )

    def test_delete_supplier_used_by_purchase(self):
        success, _, supplier_id = self.model.add_supplier(
            "Supplier Pembelian"
        )

        self.assertTrue(success)

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO purchases (
                    transaction_number,
                    supplier_id,
                    total_amount
                )
                VALUES (?, ?, ?);
                """,
                (
                    "TEST-PURCHASE-001",
                    supplier_id,
                    10000,
                ),
            )

        success, message = self.model.delete_supplier(supplier_id)

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Supplier tidak dapat dihapus karena sudah digunakan dalam transaksi pembelian.",
        )

        self.assertIsNotNone(
            self.model.get_by_id(supplier_id)
        )


if __name__ == "__main__":
    unittest.main()