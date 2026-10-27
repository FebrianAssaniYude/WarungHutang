import sqlite3
from datetime import datetime

from database.database import Database


class SaleModel:
    """Model untuk transaksi penjualan normal."""

    def __init__(self, db=None):
        self.db = db or Database()

    def _generate_transaction_number(self, conn):
        """Generate nomor transaksi JL-YYYYMMDD-XXXX."""
        date_part = datetime.now().strftime("%Y%m%d")
        prefix = f"JL-{date_part}-"

        row = conn.execute(
            """
            SELECT transaction_number
            FROM sales
            WHERE transaction_number LIKE ?
            ORDER BY transaction_number DESC
            LIMIT 1
            """,
            (f"{prefix}%",),
        ).fetchone()

        if row:
            try:
                last_number = int(row["transaction_number"][-4:])
                next_number = last_number + 1
            except (ValueError, TypeError):
                next_number = 1
        else:
            next_number = 1

        return f"{prefix}{next_number:04d}"

    def create_transaction(self, items, paid_amount, notes=""):
        """
        Membuat transaksi penjualan.

        items:
            [
                {
                    "product_id": 1,
                    "quantity": 2
                }
            ]

        Returns:
            (success, message, transaction_id)
        """
        if not items:
            return False, "Tidak ada barang dalam transaksi.", None

        try:
            paid_amount = int(paid_amount)
        except (TypeError, ValueError):
            return False, "Jumlah pembayaran tidak valid.", None

        if paid_amount < 0:
            return False, "Jumlah pembayaran tidak boleh negatif.", None

        conn = self.db.connect()

        try:
            conn.execute("BEGIN")

            transaction_number = self._generate_transaction_number(conn)

            prepared_items = []
            total_amount = 0

            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Format item transaksi tidak valid.")

                product_id = item.get("product_id")
                quantity = item.get("quantity")

                try:
                    product_id = int(product_id)
                    quantity = int(quantity)
                except (TypeError, ValueError):
                    raise ValueError("Produk atau quantity tidak valid.")

                if product_id <= 0:
                    raise ValueError("Product ID tidak valid.")

                if quantity <= 0:
                    raise ValueError("Quantity harus lebih dari 0.")

                product = conn.execute(
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

                if not product:
                    raise ValueError(
                        f"Produk dengan ID {product_id} tidak ditemukan."
                    )

                if not product["is_active"]:
                    raise ValueError(
                        f"Produk '{product['name']}' sudah tidak aktif."
                    )

                current_stock = int(product["stock"])

                if current_stock < quantity:
                    raise ValueError(
                        f"Stok produk '{product['name']}' tidak mencukupi. "
                        f"Stok tersedia: {current_stock}."
                    )

                price = int(product["selling_price"])
                subtotal = price * quantity

                if subtotal < 0:
                    raise ValueError(
                        f"Subtotal produk '{product['name']}' tidak valid."
                    )

                prepared_items.append(
                    {
                        "product_id": product_id,
                        "product_name": product["name"],
                        "quantity": quantity,
                        "price": price,
                        "subtotal": subtotal,
                    }
                )

                total_amount += subtotal

            if total_amount <= 0:
                raise ValueError(
                    "Total transaksi harus lebih dari 0."
                )

            if paid_amount < total_amount:
                raise ValueError(
                    f"Pembayaran kurang. Total transaksi: {total_amount}."
                )

            change_amount = paid_amount - total_amount

            cursor = conn.execute(
                """
                INSERT INTO sales (
                    transaction_number,
                    transaction_date,
                    total_amount,
                    paid_amount,
                    change_amount,
                    notes
                )
                VALUES (
                    ?,
                    datetime('now', 'localtime'),
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    transaction_number,
                    total_amount,
                    paid_amount,
                    change_amount,
                    notes.strip() if notes else None,
                ),
            )

            sale_id = cursor.lastrowid

            for item in prepared_items:
                # Validasi stok dilakukan kembali di database.
                stock_cursor = conn.execute(
                    """
                    UPDATE products
                    SET stock = stock - ?
                    WHERE id = ?
                      AND stock >= ?
                      AND is_active = 1
                    """,
                    (
                        item["quantity"],
                        item["product_id"],
                        item["quantity"],
                    ),
                )

                if stock_cursor.rowcount != 1:
                    raise ValueError(
                        f"Stok produk '{item['product_name']}' "
                        "tidak mencukupi atau produk sudah tidak aktif."
                    )

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
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        item["product_id"],
                        item["product_name"],
                        item["quantity"],
                        item["price"],
                        item["subtotal"],
                    ),
                )

            conn.commit()

            return (
                True,
                f"Transaksi {transaction_number} berhasil disimpan.",
                sale_id,
            )

        except ValueError as e:
            conn.rollback()
            return False, str(e), None

        except sqlite3.IntegrityError as e:
            conn.rollback()

            if "FOREIGN KEY" in str(e).upper():
                return False, "Data produk tidak valid.", None

            if "UNIQUE" in str(e).upper():
                return False, "Nomor transaksi sudah digunakan.", None

            return False, "Transaksi gagal disimpan.", None

        except sqlite3.Error:
            conn.rollback()
            return False, "Terjadi kesalahan database.", None

        except Exception:
            conn.rollback()
            return False, "Terjadi kesalahan saat menyimpan transaksi.", None

        finally:
            conn.close()

    def get_transaction_detail(self, sale_id):
        """Mengambil header dan detail satu transaksi penjualan."""
        conn = self.db.connect()

        try:
            sale = conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    transaction_date,
                    total_amount,
                    paid_amount,
                    change_amount,
                    notes,
                    created_at
                FROM sales
                WHERE id = ?
                """,
                (sale_id,),
            ).fetchone()

            if not sale:
                return None

            details = conn.execute(
                """
                SELECT
                    id,
                    sale_id,
                    product_id,
                    product_name,
                    quantity,
                    price,
                    subtotal
                FROM sale_details
                WHERE sale_id = ?
                ORDER BY id ASC
                """,
                (sale_id,),
            ).fetchall()

            return {
                "sale": dict(sale),
                "details": [dict(detail) for detail in details],
            }

        finally:
            conn.close()

    def list_transactions(self, search="", limit=100):
        """Mengambil daftar transaksi penjualan."""
        conn = self.db.connect()

        try:
            search = (search or "").strip()

            if search:
                like = f"%{search}%"

                rows = conn.execute(
                    """
                    SELECT
                        id,
                        transaction_number,
                        transaction_date,
                        total_amount,
                        paid_amount,
                        change_amount,
                        notes,
                        created_at
                    FROM sales
                    WHERE transaction_number LIKE ?
                       OR notes LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (like, like, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        transaction_number,
                        transaction_date,
                        total_amount,
                        paid_amount,
                        change_amount,
                        notes,
                        created_at
                    FROM sales
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()