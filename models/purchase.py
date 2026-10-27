import sqlite3

from database.database import Database


class PurchaseModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def create_transaction(self, items: list, notes: str = ""):
        """
        Membuat satu transaksi pembelian.

        Args:
            items: list of dict:
                - product_id: int (wajib)
                - quantity: int (> 0)
                - price: int/float (>= 0)
            notes: catatan opsional.

        Returns:
            (sukses: bool, pesan: str, transaction_id: int|None)
        """
        if not items:
            return False, "Minimal harus ada satu barang.", None

        computed_items = []
        total = 0

        # ---------------------------------------------------------
        # Validasi input dasar dan hitung ulang subtotal
        # ---------------------------------------------------------
        for item in items:
            product_id = item.get("product_id")

            try:
                product_id = int(product_id)
            except (TypeError, ValueError):
                return False, "Barang tidak valid.", None

            if product_id <= 0:
                return False, "Barang tidak valid.", None

            try:
                quantity = int(item.get("quantity"))
            except (TypeError, ValueError):
                return False, "Qty barang tidak valid.", None

            if quantity <= 0:
                return False, "Qty barang harus lebih besar dari 0.", None

            try:
                price = int(round(float(item.get("price"))))
            except (TypeError, ValueError):
                return False, "Harga beli tidak valid.", None

            if price < 0:
                return False, "Harga beli tidak boleh negatif.", None

            computed_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "price": price,
                    "subtotal": quantity * price,
                }
            )

            total += quantity * price

        if total <= 0:
            return False, "Total transaksi tidak valid.", None

        # ---------------------------------------------------------
        # Atomic transaction:
        # header + detail + stock + purchase_price
        # ---------------------------------------------------------
        try:
            with self.db.transaction() as conn:
                # Nomor transaksi dibuat di dalam transaction.
                transaction_number = self._generate_transaction_number(conn)

                cursor = conn.execute(
                    """
                    INSERT INTO purchases (
                        transaction_number,
                        supplier_id,
                        total_amount,
                        notes
                    )
                    VALUES (?, NULL, ?, ?);
                    """,
                    (
                        transaction_number,
                        total,
                        (notes or "").strip() or None,
                    ),
                )

                transaction_id = cursor.lastrowid

                for item in computed_items:
                    product = conn.execute(
                        """
                        SELECT
                            id,
                            name,
                            purchase_price,
                            selling_price,
                            stock,
                            supplier_id
                        FROM products
                        WHERE id = ?
                          AND is_active = 1;
                        """,
                        (item["product_id"],),
                    ).fetchone()

                    if not product:
                        raise LookupError(
                            f"Barang dengan ID {item['product_id']} "
                            "tidak ditemukan atau tidak aktif."
                        )

                    new_stock = product["stock"] + item["quantity"]

                    # Proteksi tambahan terhadap kondisi stok tidak valid.
                    if new_stock < 0:
                        raise ValueError(
                            f"Stok barang \"{product['name']}\" tidak valid."
                        )

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
                            transaction_id,
                            product["id"],
                            product["name"],
                            item["quantity"],
                            item["price"],
                            item["subtotal"],
                        ),
                    )

                    conn.execute(
                        """
                        UPDATE products
                        SET
                            stock = ?,
                            purchase_price = ?,
                            price = selling_price,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?;
                        """,
                        (
                            new_stock,
                            item["price"],
                            product["id"],
                        ),
                    )

        except LookupError as e:
            return False, str(e), None

        except ValueError as e:
            return False, str(e), None

        except sqlite3.IntegrityError:
            return (
                False,
                "Gagal menyimpan transaksi pembelian karena data tidak valid.",
                None,
            )

        except Exception:
            return (
                False,
                "Gagal menyimpan transaksi pembelian. "
                "Data tidak disimpan, silakan coba lagi.",
                None,
            )

        return True, "Pembelian berhasil disimpan.", transaction_id

    def get_transaction_detail(self, transaction_id: int):
        """
        Mengembalikan header + detail satu transaksi pembelian.
        """
        with self.db.transaction() as conn:
            header = conn.execute(
                """
                SELECT
                    p.id,
                    p.transaction_number,
                    p.transaction_date,
                    p.supplier_id,
                    s.name AS supplier_name,
                    p.total_amount,
                    p.notes
                FROM purchases p
                LEFT JOIN suppliers s
                    ON s.id = p.supplier_id
                WHERE p.id = ?;
                """,
                (transaction_id,),
            ).fetchone()

            if not header:
                return None

            details = conn.execute(
                """
                SELECT
                    pd.product_id,
                    pd.product_name,
                    pd.quantity,
                    pd.price,
                    pd.subtotal,
                    pr.supplier_id
                FROM purchase_details pd
                JOIN products pr
                    ON pr.id = pd.product_id
                WHERE pd.purchase_id = ?
                ORDER BY pd.id ASC;
                """,
                (transaction_id,),
            ).fetchall()

        return {
            "id": header["id"],
            "transaction_number": header["transaction_number"],
            "transaction_date": header["transaction_date"],
            "supplier_id": header["supplier_id"],
            "supplier_name": header["supplier_name"],
            "total_amount": header["total_amount"],
            "notes": header["notes"],
            "items": [dict(row) for row in details],
        }

    def list_transactions(
        self,
        date_from: str = None,
        date_to: str = None,
    ):
        """
        Mengambil daftar transaksi pembelian.
        """
        query = """
            SELECT
                id,
                transaction_number,
                transaction_date,
                total_amount,
                notes
            FROM purchases
        """

        conditions = []
        params = []

        if date_from:
            conditions.append("date(transaction_date) >= date(?)")
            params.append(date_from)

        if date_to:
            conditions.append("date(transaction_date) <= date(?)")
            params.append(date_to)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY transaction_date DESC, id DESC;
        """

        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _generate_transaction_number(conn):
        """
        Format:
            PB-YYYYMMDD-XXXX

        Contoh:
            PB-20260926-0001
        """
        date_value = conn.execute(
            """
            SELECT strftime('%Y%m%d', 'now', 'localtime') AS date_value;
            """
        ).fetchone()["date_value"]

        prefix = f"PB-{date_value}-"

        row = conn.execute(
            """
            SELECT transaction_number
            FROM purchases
            WHERE transaction_number LIKE ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (f"{prefix}%",),
        ).fetchone()

        if not row:
            sequence = 1
        else:
            last_number = row["transaction_number"]
            try:
                sequence = int(last_number.rsplit("-", 1)[1]) + 1
            except (ValueError, IndexError):
                sequence = 1

        return f"{prefix}{sequence:04d}"