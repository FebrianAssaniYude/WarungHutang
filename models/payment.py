from database.database import Database
from utils.formatter import format_rupiah


class PaymentModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def get_balance(self, customer_id: int):
        """Returns (total_debt, total_paid, sisa) untuk satu pelanggan."""
        with self.db.transaction() as conn:
            total_debt = conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS total "
                "FROM debt_transactions WHERE customer_id = ?;",
                (customer_id,),
            ).fetchone()["total"]

            total_paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total "
                "FROM payments WHERE customer_id = ?;",
                (customer_id,),
            ).fetchone()["total"]

        return total_debt, total_paid, total_debt - total_paid

    def create_payment(self, customer_id: int, amount, notes: str = ""):
        """
        Mencatat pembayaran baru untuk seorang pelanggan.

        Snapshot yang disimpan:
        - total_debt_at_payment:
            Total seluruh hutang pelanggan sebelum pembayaran ini.
        - remaining_debt_at_payment:
            Sisa hutang setelah pembayaran ini.

        Aturan:
        - lebih kecil dari sisa -> sisa berkurang
        - sama dengan sisa -> status Lunas
        - lebih besar dari sisa -> DITOLAK

        Returns:
            (sukses: bool, pesan: str, payment_id: int|None)
        """

        if not customer_id:
            return False, "Pelanggan harus dipilih.", None

        try:
            amount_value = int(round(float(amount)))
        except (TypeError, ValueError):
            return False, "Jumlah pembayaran harus berupa angka.", None

        if amount_value <= 0:
            return False, "Jumlah pembayaran harus lebih dari 0.", None

        try:
            with self.db.transaction() as conn:
                customer = conn.execute(
                    """
                    SELECT id
                    FROM customers
                    WHERE id = ?;
                    """,
                    (customer_id,),
                ).fetchone()

                if not customer:
                    raise LookupError(
                        "Pelanggan tidak ditemukan."
                    )

                total_debt = conn.execute(
                    """
                    SELECT COALESCE(SUM(total_amount), 0) AS total
                    FROM debt_transactions
                    WHERE customer_id = ?;
                    """,
                    (customer_id,),
                ).fetchone()["total"]

                total_paid = conn.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) AS total
                    FROM payments
                    WHERE customer_id = ?;
                    """,
                    (customer_id,),
                ).fetchone()["total"]

                sisa = total_debt - total_paid

                if amount_value > sisa:
                    raise ValueError(
                        "Pembayaran melebihi sisa hutang. "
                        f"Sisa saat ini: {format_rupiah(sisa)}."
                    )

                total_debt_at_payment = sisa
                remaining_debt = sisa - amount_value

                cursor = conn.execute(
                    """
                    INSERT INTO payments (
                        customer_id,
                        amount,
                        notes,
                        total_debt_at_payment,
                        remaining_debt_at_payment
                    )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        customer_id,
                        amount_value,
                        (notes or "").strip() or None,
                        total_debt_at_payment,
                        remaining_debt,
                    ),
                )

                payment_id = cursor.lastrowid

        except LookupError as e:
            return False, str(e), None

        except ValueError as e:
            return False, str(e), None

        except Exception:
            return (
                False,
                "Terjadi kesalahan saat menyimpan pembayaran ke database.",
                None,
            )

        return True, "Pembayaran berhasil disimpan.", payment_id

    def get_payment_detail(self, payment_id: int):
        """
        Mengambil detail satu pembayaran berdasarkan ID.

        Returns:
            dict atau None jika pembayaran tidak ditemukan.
        """

        if not payment_id:
            return None

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id,
                    p.customer_id,
                    c.name AS customer_name,
                    p.payment_date,
                    p.amount,
                    p.notes,
                    p.total_debt_at_payment,
                    p.remaining_debt_at_payment
                FROM payments p
                JOIN customers c
                    ON c.id = p.customer_id
                WHERE p.id = ?;
                """,
                (payment_id,),
            ).fetchone()

        return dict(row) if row else None