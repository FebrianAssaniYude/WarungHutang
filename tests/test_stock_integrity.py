import os
import sqlite3
import tempfile
import unittest

from database.database import Database


class TestStockIntegrity(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp_dir.name,
            "test_stock_integrity.db",
        )

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def create_product(self, stock=10, opening_stock=10):
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO products (
                    name,
                    price,
                    purchase_price,
                    selling_price,
                    stock,
                    opening_stock
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    "Produk Test",
                    2000,
                    2000,
                    3000,
                    stock,
                    opening_stock,
                ),
            )

            return cursor.lastrowid

    # ------------------------------------------------------------------
    # Product stock constraints
    # ------------------------------------------------------------------
    def test_product_stock_cannot_be_negative(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_product(
                stock=-1,
                opening_stock=0,
            )

    def test_product_opening_stock_cannot_be_negative(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_product(
                stock=0,
                opening_stock=-1,
            )

    def test_product_zero_stock_is_allowed(self):
        product_id = self.create_product(
            stock=0,
            opening_stock=0,
        )

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT stock, opening_stock
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

        self.assertEqual(row["stock"], 0)
        self.assertEqual(row["opening_stock"], 0)

    # ------------------------------------------------------------------
    # Debt detail quantity
    # ------------------------------------------------------------------
    def test_debt_detail_quantity_cannot_be_zero(self):
        with self.db.transaction() as conn:
            customer = conn.execute(
                """
                INSERT INTO customers (name)
                VALUES (?);
                """,
                ("Customer Test",),
            )

            customer_id = customer.lastrowid

            debt = conn.execute(
                """
                INSERT INTO debt_transactions (
                    customer_id,
                    total_amount
                )
                VALUES (?, ?);
                """,
                (customer_id, 0),
            )

            debt_id = debt.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO debt_details (
                        transaction_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        debt_id,
                        "Produk Test",
                        0,
                        3000,
                        0,
                    ),
                )

    def test_debt_detail_quantity_cannot_be_negative(self):
        with self.db.transaction() as conn:
            customer = conn.execute(
                """
                INSERT INTO customers (name)
                VALUES (?);
                """,
                ("Customer Test",),
            )

            customer_id = customer.lastrowid

            debt = conn.execute(
                """
                INSERT INTO debt_transactions (
                    customer_id,
                    total_amount
                )
                VALUES (?, ?);
                """,
                (customer_id, 0),
            )

            debt_id = debt.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO debt_details (
                        transaction_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        debt_id,
                        "Produk Test",
                        -1,
                        3000,
                        -3000,
                    ),
                )

    # ------------------------------------------------------------------
    # Purchase detail quantity
    # ------------------------------------------------------------------
    def test_purchase_detail_quantity_cannot_be_zero(self):
        product_id = self.create_product()

        with self.db.transaction() as conn:
            purchase = conn.execute(
                """
                INSERT INTO purchases (
                    transaction_number,
                    total_amount
                )
                VALUES (?, ?);
                """,
                ("TEST-PURCHASE-001", 0),
            )

            purchase_id = purchase.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO purchase_details (
                        purchase_id,
                        product_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        purchase_id,
                        product_id,
                        "Produk Test",
                        0,
                        2000,
                        0,
                    ),
                )

    def test_purchase_detail_quantity_cannot_be_negative(self):
        product_id = self.create_product()

        with self.db.transaction() as conn:
            purchase = conn.execute(
                """
                INSERT INTO purchases (
                    transaction_number,
                    total_amount
                )
                VALUES (?, ?);
                """,
                ("TEST-PURCHASE-002", 0),
            )

            purchase_id = purchase.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO purchase_details (
                        purchase_id,
                        product_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        purchase_id,
                        product_id,
                        "Produk Test",
                        -1,
                        2000,
                        -2000,
                    ),
                )

    # ------------------------------------------------------------------
    # Sale detail quantity
    # ------------------------------------------------------------------
    def test_sale_detail_quantity_cannot_be_zero(self):
        product_id = self.create_product()

        with self.db.transaction() as conn:
            sale = conn.execute(
                """
                INSERT INTO sales (
                    transaction_number,
                    total_amount,
                    paid_amount,
                    change_amount
                )
                VALUES (?, ?, ?, ?);
                """,
                ("TEST-SALE-001", 0, 0, 0),
            )

            sale_id = sale.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO sale_details (
                        sale_id,
                        product_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        sale_id,
                        product_id,
                        "Produk Test",
                        0,
                        3000,
                        0,
                    ),
                )

    def test_sale_detail_quantity_cannot_be_negative(self):
        product_id = self.create_product()

        with self.db.transaction() as conn:
            sale = conn.execute(
                """
                INSERT INTO sales (
                    transaction_number,
                    total_amount,
                    paid_amount,
                    change_amount
                )
                VALUES (?, ?, ?, ?);
                """,
                ("TEST-SALE-002", 0, 0, 0),
            )

            sale_id = sale.lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO sale_details (
                        sale_id,
                        product_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        sale_id,
                        product_id,
                        "Produk Test",
                        -1,
                        3000,
                        -3000,
                    ),
                )


if __name__ == "__main__":
    unittest.main()