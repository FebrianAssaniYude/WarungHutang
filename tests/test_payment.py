import os
import tempfile
import unittest

from database.database import Database
from models.debt import DebtModel
from models.payment import PaymentModel


class PaymentModelTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp_dir.name,
            "test.db",
        )

        self.db = Database(db_path=self.db_path)
        self.db.initialize()

        self.debt_model = DebtModel(self.db)
        self.payment_model = PaymentModel(self.db)

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

    def _create_debt(self, customer_id=1, quantity=2):
        success, message, transaction_id = (
            self.debt_model.create_transaction(
                customer_id=customer_id,
                items=[
                    {
                        "product_id": 1,
                        "quantity": quantity,
                    }
                ],
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(transaction_id)

        return transaction_id

    def _get_payment(self, payment_id):
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT
                    id,
                    customer_id,
                    amount,
                    notes
                FROM payments
                WHERE id = ?;
                """,
                (payment_id,),
            ).fetchone()

    def _get_payment_count(self):
        with self.db.transaction() as conn:
            return conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM payments;
                """
            ).fetchone()["total"]

    # ------------------------------------------------------------------
    # Saldo awal
    # ------------------------------------------------------------------
    def test_initial_balance_is_zero(self):
        total_debt, total_paid, balance = (
            self.payment_model.get_balance(1)
        )

        self.assertEqual(
            total_debt,
            0,
        )

        self.assertEqual(
            total_paid,
            0,
        )

        self.assertEqual(
            balance,
            0,
        )

    # ------------------------------------------------------------------
    # Pembayaran
    # ------------------------------------------------------------------
    def test_create_payment_successfully(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=10000,
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(payment_id)

        payment = self._get_payment(
            payment_id
        )

        self.assertIsNotNone(payment)

        self.assertEqual(
            payment["customer_id"],
            1,
        )

        self.assertEqual(
            payment["amount"],
            10000,
        )

    def test_partial_payment_reduces_balance(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        # Total hutang = 2 x 15.000 = 30.000
        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=10000,
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(payment_id)

        total_debt, total_paid, balance = (
            self.payment_model.get_balance(1)
        )

        self.assertEqual(
            total_debt,
            30000,
        )

        self.assertEqual(
            total_paid,
            10000,
        )

        self.assertEqual(
            balance,
            20000,
        )

    def test_full_payment_makes_balance_zero(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=30000,
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(payment_id)

        total_debt, total_paid, balance = (
            self.payment_model.get_balance(1)
        )

        self.assertEqual(
            total_debt,
            30000,
        )

        self.assertEqual(
            total_paid,
            30000,
        )

        self.assertEqual(
            balance,
            0,
        )

    def test_multiple_payments_reduce_balance_correctly(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, first_payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=10000,
            )
        )

        self.assertTrue(
            success,
            message,
        )

        self.assertIsNotNone(
            first_payment_id,
        )

        success, message, second_payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=5000,
            )
        )

        self.assertTrue(
            success,
            message,
        )

        self.assertIsNotNone(
            second_payment_id,
        )

        total_debt, total_paid, balance = (
            self.payment_model.get_balance(1)
        )

        self.assertEqual(
            total_debt,
            30000,
        )

        self.assertEqual(
            total_paid,
            15000,
        )

        self.assertEqual(
            balance,
            15000,
        )

    # ------------------------------------------------------------------
    # Validasi jumlah pembayaran
    # ------------------------------------------------------------------
    def test_payment_exceeding_balance_is_rejected(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=30001,
            )
        )

        self.assertFalse(success)
        self.assertIsNone(payment_id)

        self.assertEqual(
            self._get_payment_count(),
            0,
        )

        total_debt, total_paid, balance = (
            self.payment_model.get_balance(1)
        )

        self.assertEqual(
            total_debt,
            30000,
        )

        self.assertEqual(
            total_paid,
            0,
        )

        self.assertEqual(
            balance,
            30000,
        )

    def test_zero_payment_is_rejected(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=0,
            )
        )

        self.assertFalse(success)
        self.assertIsNone(payment_id)

        self.assertEqual(
            self._get_payment_count(),
            0,
        )

    def test_negative_payment_is_rejected(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=-5000,
            )
        )

        self.assertFalse(success)
        self.assertIsNone(payment_id)

        self.assertEqual(
            self._get_payment_count(),
            0,
        )

    def test_invalid_payment_amount_is_rejected(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount="abc",
            )
        )

        self.assertFalse(success)
        self.assertIsNone(payment_id)

        self.assertEqual(
            self._get_payment_count(),
            0,
        )

    # ------------------------------------------------------------------
    # Validasi customer
    # ------------------------------------------------------------------
    def test_unknown_customer_is_rejected(self):
        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=9999,
                amount=5000,
            )
        )

        self.assertFalse(success)
        self.assertIsNone(payment_id)

        self.assertEqual(
            self._get_payment_count(),
            0,
        )

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------
    def test_payment_notes_are_saved(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=10000,
                notes="Pembayaran pertama",
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(payment_id)

        payment = self._get_payment(
            payment_id
        )

        self.assertIsNotNone(payment)

        self.assertEqual(
            payment["notes"],
            "Pembayaran pertama",
        )

    # ------------------------------------------------------------------
    # Pembayaran pelanggan lain tidak memengaruhi saldo
    # ------------------------------------------------------------------
    def test_payment_for_one_customer_does_not_affect_another(self):
        self._create_debt(
            customer_id=1,
            quantity=2,
        )

        success, message, payment_id = (
            self.payment_model.create_payment(
                customer_id=1,
                amount=10000,
            )
        )

        self.assertTrue(success, message)
        self.assertIsNotNone(payment_id)

        customer_1_balance = (
            self.payment_model.get_balance(1)
        )

        customer_2_balance = (
            self.payment_model.get_balance(2)
        )

        self.assertEqual(
            customer_1_balance[0],
            30000,
        )

        self.assertEqual(
            customer_1_balance[1],
            10000,
        )

        self.assertEqual(
            customer_1_balance[2],
            20000,
        )

        self.assertEqual(
            customer_2_balance[0],
            0,
        )

        self.assertEqual(
            customer_2_balance[1],
            0,
        )

        self.assertEqual(
            customer_2_balance[2],
            0,
        )


if __name__ == "__main__":
    unittest.main()