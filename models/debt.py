"""
models/debt.py

Logika transaksi hutang: membuat transaksi baru (header debt_transactions
+ rincian debt_details) dalam satu operasi database yang aman - jika ada
kegagalan di tengah jalan, TIDAK ADA data yang tersimpan setengah jadi
(rollback otomatis lewat Database.transaction()).
"""

from database.database import Database


class DebtModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def create_transaction(self, customer_id: int, items: list, notes: str = ""):
        """
        Membuat satu transaksi hutang baru.

        Args:
            customer_id: id pelanggan (wajib).
            items: list of dict, masing-masing berisi:
                - product_id: int|None (None untuk barang manual)
                - product_name: str
                - quantity: int (> 0)
                - price: int/float (>= 0)
            notes: catatan opsional untuk transaksi.

        Returns:
            (sukses: bool, pesan: str, transaction_id: int|None)
        """
        if not customer_id:
            return False, "Pelanggan harus dipilih.", None

        if not items:
            return False, "Minimal harus ada satu barang.", None

        # --- Validasi & hitung ulang setiap baris (jangan percaya angka dari UI) ---
        computed_items = []
        total = 0
        for item in items:
            name = (item.get("product_name") or "").strip()
            if not name:
                return False, "Nama barang tidak boleh kosong.", None

            try:
                qty = int(item.get("quantity"))
            except (TypeError, ValueError):
                return False, f"Qty untuk \"{name}\" tidak valid.", None
            if qty <= 0:
                return False, f"Qty untuk \"{name}\" harus lebih besar dari 0.", None

            try:
                price = int(round(float(item.get("price"))))
            except (TypeError, ValueError):
                return False, f"Harga untuk \"{name}\" tidak valid.", None
            if price < 0:
                return False, f"Harga untuk \"{name}\" tidak boleh negatif.", None

            subtotal = qty * price
            total += subtotal
            computed_items.append({
                "product_id": item.get("product_id"),
                "product_name": name,
                "quantity": qty,
                "price": price,
                "subtotal": subtotal,
            })

        if total <= 0:
            return False, "Total transaksi tidak valid.", None

        # --- Simpan header + detail dalam satu transaksi database ---
        try:
            with self.db.transaction() as conn:
                customer = conn.execute(
                    "SELECT id FROM customers WHERE id = ?;", (customer_id,)
                ).fetchone()
                if not customer:
                    raise LookupError("Pelanggan tidak ditemukan.")

                cursor = conn.execute(
                    "INSERT INTO debt_transactions (customer_id, total_amount, notes) "
                    "VALUES (?, ?, ?);",
                    (customer_id, total, (notes or "").strip() or None),
                )
                transaction_id = cursor.lastrowid

                for item in computed_items:
                    conn.execute(
                        "INSERT INTO debt_details "
                        "(transaction_id, product_id, product_name, quantity, price, subtotal) "
                        "VALUES (?, ?, ?, ?, ?, ?);",
                        (
                            transaction_id,
                            item["product_id"],
                            item["product_name"],
                            item["quantity"],
                            item["price"],
                            item["subtotal"],
                        ),
                    )
        except LookupError as e:
            return False, str(e), None
        except Exception:
            # Rollback sudah otomatis dilakukan oleh Database.transaction().
            return False, "Gagal menyimpan transaksi. Data tidak disimpan, silakan coba lagi.", None

        return True, "Hutang berhasil dicatat.", transaction_id

    def get_transaction_detail(self, transaction_id: int):
        """Mengembalikan header + rincian barang satu transaksi, atau None jika tidak ada."""
        with self.db.transaction() as conn:
            header = conn.execute(
                "SELECT dt.id, dt.customer_id, dt.transaction_date, dt.total_amount, "
                "dt.notes, c.name AS customer_name "
                "FROM debt_transactions dt "
                "JOIN customers c ON c.id = dt.customer_id "
                "WHERE dt.id = ?;",
                (transaction_id,),
            ).fetchone()
            if not header:
                return None

            details = conn.execute(
                "SELECT product_id, product_name, quantity, price, subtotal "
                "FROM debt_details WHERE transaction_id = ?;",
                (transaction_id,),
            ).fetchall()

        return {
            "id": header["id"],
            "customer_id": header["customer_id"],
            "customer_name": header["customer_name"],
            "transaction_date": header["transaction_date"],
            "total_amount": header["total_amount"],
            "notes": header["notes"],
            "items": [dict(row) for row in details],
        }
