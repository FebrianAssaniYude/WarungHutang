import os
import tempfile
import unittest

from database.database import Database
from models.product import ProductModel
from models.supplier import SupplierModel


class TestProductModel(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp_dir.name,
            "test_product.db",
        )

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.product_model = ProductModel(self.db)
        self.supplier_model = SupplierModel(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def create_supplier(self, name="Supplier Test"):
        success, message, supplier_id = self.supplier_model.add_supplier(
            name
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(supplier_id)

        return supplier_id

    def create_product(
        self,
        name="Produk Test",
        barcode="899000000001",
        supplier_id=None,
        stock=10,
    ):
        success, message, product_id = self.product_model.add_product(
            name=name,
            purchase_price=2000,
            selling_price=3000,
            opening_stock=stock,
            barcode=barcode,
            supplier_id=supplier_id,
            image_path="data/images/product_test.jpg",
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(product_id)

        return product_id

    # ------------------------------------------------------------------
    # Tambah
    # ------------------------------------------------------------------
    def test_add_product(self):
        supplier_id = self.create_supplier()

        product_id = self.create_product(
            supplier_id=supplier_id
        )

        product = self.product_model.get_by_id(product_id)

        self.assertIsNotNone(product)

        self.assertEqual(product["name"], "Produk Test")
        self.assertEqual(product["barcode"], "899000000001")

        self.assertEqual(product["purchase_price"], 2000)
        self.assertEqual(product["selling_price"], 3000)

        self.assertEqual(product["opening_stock"], 10)
        self.assertEqual(product["stock"], 10)

        self.assertEqual(product["supplier_id"], supplier_id)
        self.assertEqual(
            product["supplier_name"],
            "Supplier Test",
        )

        self.assertEqual(
            product["image_path"],
            "data/images/product_test.jpg",
        )

    def test_add_product_without_barcode(self):
        success, message, product_id = self.product_model.add_product(
            name="Produk Tanpa Barcode",
            purchase_price=1000,
            selling_price=1500,
            opening_stock=5,
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(product_id)

        product = self.product_model.get_by_id(product_id)

        self.assertIsNone(product["barcode"])

    def test_add_product_without_supplier(self):
        product_id = self.create_product(
            name="Produk Tanpa Supplier",
            barcode="899000000002",
            supplier_id=None,
        )

        product = self.product_model.get_by_id(product_id)

        self.assertIsNone(product["supplier_id"])
        self.assertIsNone(product["supplier_name"])

    def test_add_product_invalid_supplier(self):
        success, message, product_id = self.product_model.add_product(
            name="Produk Supplier Invalid",
            purchase_price=1000,
            selling_price=1500,
            opening_stock=5,
            supplier_id=999999,
        )

        self.assertFalse(success)
        self.assertEqual(message, "Supplier tidak ditemukan.")
        self.assertIsNone(product_id)

    def test_add_product_invalid_price(self):
        success, message, product_id = self.product_model.add_product(
            name="Produk Harga Invalid",
            purchase_price=-100,
            selling_price=1500,
            opening_stock=5,
        )

        self.assertFalse(success)
        self.assertIn("Harga beli", message)
        self.assertIsNone(product_id)

    def test_add_product_invalid_stock(self):
        success, message, product_id = self.product_model.add_product(
            name="Produk Stok Invalid",
            purchase_price=1000,
            selling_price=1500,
            opening_stock=-1,
        )

        self.assertFalse(success)
        self.assertIn("Stok awal", message)
        self.assertIsNone(product_id)

    def test_duplicate_barcode(self):
        self.create_product()

        success, message, product_id = self.product_model.add_product(
            name="Produk Kedua",
            purchase_price=2500,
            selling_price=3500,
            opening_stock=5,
            barcode="899000000001",
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Barcode tersebut sudah digunakan oleh barang lain.",
        )
        self.assertIsNone(product_id)

    # ------------------------------------------------------------------
    # Pencarian
    # ------------------------------------------------------------------
    def test_get_by_barcode(self):
        product_id = self.create_product()

        product = self.product_model.get_by_barcode(
            "899000000001"
        )

        self.assertIsNotNone(product)
        self.assertEqual(product["id"], product_id)

    def test_get_by_barcode_empty(self):
        product = self.product_model.get_by_barcode("")

        self.assertIsNone(product)

    def test_list_products_search(self):
        self.create_product(
            name="Indomie Goreng",
            barcode="899111111111",
        )

        success, message, _ = self.product_model.add_product(
            name="Aqua 600ml",
            purchase_price=2500,
            selling_price=4000,
            opening_stock=20,
            barcode="899222222222",
        )

        self.assertTrue(success, message)

        results = self.product_model.list_products(
            search="Indomie"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["name"],
            "Indomie Goreng",
        )

        results = self.product_model.list_products(
            search="899222"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["name"],
            "Aqua 600ml",
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def test_update_product(self):
        supplier_id = self.create_supplier()

        product_id = self.create_product(
            supplier_id=supplier_id,
            stock=20,
        )

        success, message = self.product_model.update_product(
            product_id=product_id,
            name="Produk Updated",
            purchase_price=2500,
            selling_price=3500,
            barcode="899999999999",
            supplier_id=supplier_id,
            image_path="data/images/updated.jpg",
        )

        self.assertTrue(success, message)

        product = self.product_model.get_by_id(product_id)

        self.assertEqual(
            product["name"],
            "Produk Updated",
        )
        self.assertEqual(
            product["purchase_price"],
            2500,
        )
        self.assertEqual(
            product["selling_price"],
            3500,
        )
        self.assertEqual(
            product["barcode"],
            "899999999999",
        )
        self.assertEqual(
            product["image_path"],
            "data/images/updated.jpg",
        )

        # Stok tidak boleh berubah saat edit master produk.
        self.assertEqual(product["stock"], 20)
        self.assertEqual(product["opening_stock"], 20)

    def test_update_product_remove_supplier(self):
        supplier_id = self.create_supplier()

        product_id = self.create_product(
            supplier_id=supplier_id
        )

        success, message = self.product_model.update_product(
            product_id=product_id,
            name="Produk Tanpa Supplier",
            purchase_price=2000,
            selling_price=3000,
            supplier_id=None,
        )

        self.assertTrue(success, message)

        product = self.product_model.get_by_id(product_id)

        self.assertIsNone(product["supplier_id"])

    def test_update_nonexistent_product(self):
        success, message = self.product_model.update_product(
            product_id=999999,
            name="Tidak Ada",
            purchase_price=1000,
            selling_price=1500,
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Barang tidak ditemukan.",
        )

    # ------------------------------------------------------------------
    # Nonaktif / aktif
    # ------------------------------------------------------------------
    def test_deactivate_product(self):
        product_id = self.create_product()

        success, message = self.product_model.deactivate_product(
            product_id
        )

        self.assertTrue(success)
        self.assertEqual(
            message,
            "Barang berhasil dinonaktifkan.",
        )

        # Tidak muncul pada daftar aktif.
        products = self.product_model.list_products()

        self.assertEqual(len(products), 0)

        # Tetap bisa ditemukan jika include_inactive=True.
        products = self.product_model.list_products(
            include_inactive=True
        )

        self.assertEqual(len(products), 1)
        self.assertEqual(
            products[0]["is_active"],
            0,
        )

    def test_activate_product(self):
        product_id = self.create_product()

        self.product_model.deactivate_product(product_id)

        success, message = self.product_model.activate_product(
            product_id
        )

        self.assertTrue(success)
        self.assertEqual(
            message,
            "Barang berhasil diaktifkan.",
        )

        products = self.product_model.list_products()

        self.assertEqual(len(products), 1)

    # ------------------------------------------------------------------
    # Stok
    # ------------------------------------------------------------------
    def test_increase_stock(self):
        product_id = self.create_product(stock=10)

        success, message = self.product_model.increase_stock(
            product_id,
            5,
        )

        self.assertTrue(success, message)

        product = self.product_model.get_by_id(product_id)

        self.assertEqual(product["stock"], 15)
        self.assertEqual(product["opening_stock"], 10)

    def test_decrease_stock(self):
        product_id = self.create_product(stock=10)

        success, message = self.product_model.decrease_stock(
            product_id,
            4,
        )

        self.assertTrue(success, message)

        product = self.product_model.get_by_id(product_id)

        self.assertEqual(product["stock"], 6)
        self.assertEqual(product["opening_stock"], 10)

    def test_decrease_stock_cannot_go_negative(self):
        product_id = self.create_product(stock=5)

        success, message = self.product_model.decrease_stock(
            product_id,
            6,
        )

        self.assertFalse(success)
        self.assertIn("Stok tidak mencukupi", message)

        product = self.product_model.get_by_id(product_id)

        self.assertEqual(product["stock"], 5)

    def test_stock_quantity_must_be_positive(self):
        product_id = self.create_product(stock=10)

        success, message = self.product_model.decrease_stock(
            product_id,
            0,
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Jumlah harus lebih dari 0.",
        )

        product = self.product_model.get_by_id(product_id)

        self.assertEqual(product["stock"], 10)

    def test_increase_stock_nonexistent_product(self):
        success, message = self.product_model.increase_stock(
            999999,
            5,
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Barang tidak ditemukan.",
        )


if __name__ == "__main__":
    unittest.main()