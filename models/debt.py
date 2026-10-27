import sqlite3
from datetime import datetime

from database.database import Database


class DebtModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    @staticmethod
    def _generate_transaction_number(conn):
        """
        Membuat nomor transaksi hutang dengan format:

            HT-YYYYMMDD-0001

        Nomor dibuat berdasarkan transaksi pada tanggal yang sama.
        """
        prefix = datetime.now().strftime("HT-%Y%m%d-")

        row = conn.execute(
            """
            SELECT transaction_number
            FROM debt_transactions
            WHERE transaction_number LIKE ?
            ORDER BY transaction_number DESC
            LIMIT 1;
            """,
            (f"{prefix}%",),
        ).fetchone()

        if not row or not row["transaction_number"]:
            next_number = 1
        else:
            last_number = row["transaction_number"][-4:]

            try:
                next_number = int(last_number) + 1
            except ValueError:
                next_number = 1

        return f"{prefix}{next_number:04d}"

    def create_transaction(
        self,
        customer_id: int,
        items: list,
        notes: str = "",
    ):
        """
        Membuat transaksi hutang baru.

        Barang untuk transaksi baru WAJIB berasal dari master products.

        Format items:
            [
                {
                    "product_id": 1,
                    "quantity": 2
                },
                ...
            ]

        product_name dan price dari UI tidak dipercaya.
        Nama dan harga selalu diambil ulang dari database.

        Returns:
            (sukses: bool, pesan: str, transaction_id: int | None)
        """

        # ==========================================================
        # VALIDASI DASAR
        # ==========================================================

        if not customer_id:
            return False, "Pelanggan harus dipilih.", None

        if not items:
            return False, "Minimal harus ada satu barang.", None

        # ==========================================================
        # SIMPAN DALAM SATU TRANSAKSI DATABASE
        # ==========================================================

        try:
            with self.db.transaction() as conn:

                # --------------------------------------------------
                # Validasi pelanggan
                # --------------------------------------------------

                customer = conn.execute(
                    """
                    SELECT id, name
                    FROM customers
                    WHERE id = ?;
                    """,
                    (customer_id,),
                ).fetchone()

                if not customer:
                    raise LookupError("Pelanggan tidak ditemukan.")

                # --------------------------------------------------
                # Nomor transaksi
                # --------------------------------------------------

                transaction_number = self._generate_transaction_number(
                    conn
                )

                # --------------------------------------------------
                # Validasi dan hitung ulang semua item
                #
                # Tidak mempercayai:
                # - product_name dari UI
                # - price dari UI
                # - subtotal dari UI
                #
                # Semua diambil ulang dari database.
                # --------------------------------------------------

                computed_items = []
                total = 0

                for item in items:

                    # ----------------------------------------------
                    # product_id wajib ada
                    # ----------------------------------------------

                    product_id = item.get("product_id")

                    try:
                        product_id = int(product_id)
                    except (TypeError, ValueError):
                        raise ValueError(
                            "Barang tidak valid. "
                            "Silakan pilih barang dari master produk."
                        )

                    if product_id <= 0:
                        raise ValueError(
                            "Barang tidak valid. "
                            "Silakan pilih barang dari master produk."
                        )

                    # ----------------------------------------------
                    # quantity
                    # ----------------------------------------------

                    try:
                        quantity = int(item.get("quantity"))
                    except (TypeError, ValueError):
                        raise ValueError(
                            "Qty barang tidak valid."
                        )

                    if quantity <= 0:
                        raise ValueError(
                            "Qty barang harus lebih besar dari 0."
                        )

                    # ----------------------------------------------
                    # Ambil produk dari database
                    #
                    # Hanya produk aktif yang boleh digunakan
                    # untuk transaksi hutang baru.
                    # ----------------------------------------------

                    product = conn.execute(
                        """
                        SELECT
                            id,
                            name,
                            selling_price,
                            stock,
                            is_active
                        FROM products
                        WHERE id = ?;
                        """,
                        (product_id,),
                    ).fetchone()

                    if not product:
                        raise LookupError(
                            "Barang tidak ditemukan."
                        )

                    if not product["is_active"]:
                        raise ValueError(
                            f'Barang "{product["name"]}" '
                            "sudah tidak aktif."
                        )

                    # ----------------------------------------------
                    # Harga selalu dari master produk
                    # ----------------------------------------------

                    price = int(product["selling_price"])

                    if price < 0:
                        raise ValueError(
                            f'Harga jual barang "{product["name"]}" '
                            "tidak valid."
                        )

                    # ----------------------------------------------
                    # Validasi stok
                    # ----------------------------------------------

                    current_stock = int(product["stock"])

                    if current_stock < quantity:
                        raise ValueError(
                            f'Stok barang "{product["name"]}" '
                            f"tidak mencukupi. "
                            f"Stok tersedia: {current_stock}."
                        )

                    # ----------------------------------------------
                    # Hitung subtotal dari data database
                    # ----------------------------------------------

                    subtotal = quantity * price

                    total += subtotal

                    # ----------------------------------------------
                    # Snapshot data transaksi
                    # ----------------------------------------------

                    computed_items.append(
                        {
                            "product_id": product["id"],
                            "product_name": product["name"],
                            "quantity": quantity,
                            "price": price,
                            "subtotal": subtotal,
                        }
                    )

                # ==================================================
                # VALIDASI TOTAL
                # ==================================================

                if total <= 0:
                    return (
                        False,
                        "Total transaksi tidak valid.",
                        None,
                    )

                # ==================================================
                # INSERT HEADER
                # ==================================================

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
                        transaction_number,
                        customer_id,
                        total,
                        (notes or "").strip() or None,
                    ),
                )

                transaction_id = cursor.lastrowid

                # ==================================================
                # INSERT DETAIL + KURANGI STOK
                # ==================================================

                for item in computed_items:

                    # ----------------------------------------------
                    # Simpan detail
                    # ----------------------------------------------

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
                            item["product_id"],
                            item["product_name"],
                            item["quantity"],
                            item["price"],
                            item["subtotal"],
                        ),
                    )

                    # ----------------------------------------------
                    # Kurangi stok secara atomic.
                    #
                    # Kondisi stock >= quantity tetap diperiksa
                    # pada UPDATE agar stok tidak pernah negatif.
                    # ----------------------------------------------

                    cursor_stock = conn.execute(
                        """
                        UPDATE products
                        SET
                            stock = stock - ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                          AND is_active = 1
                          AND stock >= ?;
                        """,
                        (
                            item["quantity"],
                            item["product_id"],
                            item["quantity"],
                        ),
                    )

                    if cursor_stock.rowcount != 1:
                        raise ValueError(
                            f'Stok barang "{item["product_name"]}" '
                            "berubah atau tidak mencukupi. "
                            "Silakan periksa stok lalu coba lagi."
                        )

        # ==========================================================
        # ERROR TERKONTROL
        # ==========================================================

        except (LookupError, ValueError) as e:
            return False, str(e), None

        # ==========================================================
        # ERROR DATABASE
        # ==========================================================

        except sqlite3.IntegrityError:
            return (
                False,
                "Gagal menyimpan transaksi karena data tidak valid.",
                None,
            )

        except Exception:
            # Database.transaction() menangani rollback.
            return (
                False,
                "Gagal menyimpan transaksi. "
                "Data tidak disimpan, silakan coba lagi.",
                None,
            )

        return True, "Hutang berhasil dicatat.", transaction_id

    def get_transaction_detail(self, transaction_id: int):
        """
        Mengembalikan header + rincian barang satu transaksi.

        Data transaksi lama tetap dapat dibaca, termasuk detail
        legacy yang product_id-nya NULL.
        """

        with self.db.transaction() as conn:

            # ======================================================
            # HEADER
            # ======================================================

            header = conn.execute(
                """
                SELECT
                    dt.id,
                    dt.transaction_number,
                    dt.customer_id,
                    dt.transaction_date,
                    dt.total_amount,
                    dt.notes,
                    c.name AS customer_name
                FROM debt_transactions dt
                JOIN customers c
                    ON c.id = dt.customer_id
                WHERE dt.id = ?;
                """,
                (transaction_id,),
            ).fetchone()

            if not header:
                return None

            # ======================================================
            # DETAIL
            # ======================================================

            details = conn.execute(
                """
                SELECT
                    product_id,
                    product_name,
                    quantity,
                    price,
                    subtotal
                FROM debt_details
                WHERE transaction_id = ?
                ORDER BY id ASC;
                """,
                (transaction_id,),
            ).fetchall()

        # ==========================================================
        # HASIL
        # ==========================================================

        return {
            "id": header["id"],
            "transaction_number": header["transaction_number"],
            "customer_id": header["customer_id"],
            "customer_name": header["customer_name"],
            "transaction_date": header["transaction_date"],
            "total_amount": header["total_amount"],
            "notes": header["notes"],
            "items": [dict(row) for row in details],
        }