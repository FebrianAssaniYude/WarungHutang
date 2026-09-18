"""
models/customer.py

Logika data pelanggan: daftar, tambah, edit, nonaktifkan (soft delete),
dan detail (ringkasan + riwayat hutang/pembayaran).

PENTING: saldo hutang TIDAK PERNAH disimpan sebagai angka yang diedit
manual. Selalu dihitung ulang dari:
    total seluruh debt_transactions  -  total seluruh payments
"""

from database.database import Database


class CustomerModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Helper internal
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_balance(conn, customer_id: int):
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

    # ------------------------------------------------------------------
    # Daftar & pencarian
    # ------------------------------------------------------------------
    def list_customers(self, search: str = "", include_inactive: bool = False):
        """
        Mengembalikan list of dict pelanggan lengkap dengan saldo & status,
        diurutkan berdasarkan nama.
        """
        query = "SELECT id, name, phone, notes, is_active FROM customers"
        conditions = []
        params = []

        if not include_inactive:
            conditions.append("is_active = 1")
        if search:
            conditions.append("name LIKE ?")
            params.append(f"%{search.strip()}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY name COLLATE NOCASE ASC;"

        results = []
        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            for row in rows:
                total_debt, total_paid, sisa = self._compute_balance(conn, row["id"])
                results.append({
                    "id": row["id"],
                    "name": row["name"],
                    "phone": row["phone"],
                    "notes": row["notes"],
                    "is_active": row["is_active"],
                    "total_debt": total_debt,
                    "total_paid": total_paid,
                    "sisa": sisa,
                    "status": "Lunas" if sisa <= 0 else "Masih Berhutang",
                })
        return results

    # ------------------------------------------------------------------
    # Tambah / edit / nonaktifkan
    # ------------------------------------------------------------------
    def add_customer(self, name: str, phone: str = "", notes: str = ""):
        """Returns (sukses: bool, pesan: str, customer_id: int|None)."""
        name = (name or "").strip()
        if not name:
            return False, "Nama pelanggan wajib diisi.", None

        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO customers (name, phone, notes) VALUES (?, ?, ?);",
                (name, (phone or "").strip() or None, (notes or "").strip() or None),
            )
            new_id = cursor.lastrowid

        return True, "Pelanggan berhasil ditambahkan.", new_id

    def update_customer(self, customer_id: int, name: str, phone: str = "", notes: str = ""):
        """Returns (sukses: bool, pesan: str)."""
        name = (name or "").strip()
        if not name:
            return False, "Nama pelanggan wajib diisi."

        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE id = ?;", (customer_id,)
            ).fetchone()
            if not existing:
                return False, "Pelanggan tidak ditemukan."

            conn.execute(
                "UPDATE customers SET name = ?, phone = ?, notes = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?;",
                (name, (phone or "").strip() or None, (notes or "").strip() or None, customer_id),
            )

        return True, "Data pelanggan berhasil diperbarui."

    def deactivate_customer(self, customer_id: int):
        """Soft delete - data & histori tetap tersimpan. Returns (sukses, pesan)."""
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE id = ?;", (customer_id,)
            ).fetchone()
            if not existing:
                return False, "Pelanggan tidak ditemukan."

            conn.execute(
                "UPDATE customers SET is_active = 0, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?;",
                (customer_id,),
            )

        return True, "Pelanggan berhasil dinonaktifkan."

    # ------------------------------------------------------------------
    # Detail pelanggan (ringkasan + timeline)
    # ------------------------------------------------------------------
    def get_detail(self, customer_id: int):
        """
        Returns dict berisi data pelanggan, ringkasan saldo, dan timeline
        riwayat hutang + pembayaran (urut dari terbaru), atau None jika
        pelanggan tidak ditemukan.
        """
        with self.db.transaction() as conn:
            customer = conn.execute(
                "SELECT id, name, phone, notes, is_active, created_at "
                "FROM customers WHERE id = ?;",
                (customer_id,),
            ).fetchone()
            if not customer:
                return None

            total_debt, total_paid, sisa = self._compute_balance(conn, customer_id)

            debts = conn.execute(
                "SELECT id, transaction_date, total_amount, notes "
                "FROM debt_transactions WHERE customer_id = ? "
                "ORDER BY transaction_date DESC, id DESC;",
                (customer_id,),
            ).fetchall()

            payments = conn.execute(
                "SELECT id, payment_date, amount, notes "
                "FROM payments WHERE customer_id = ? "
                "ORDER BY payment_date DESC, id DESC;",
                (customer_id,),
            ).fetchall()

        timeline = []
        for d in debts:
            timeline.append({
                "date": d["transaction_date"],
                "type": "Hutang",
                "amount": d["total_amount"],
                "notes": d["notes"],
            })
        for p in payments:
            timeline.append({
                "date": p["payment_date"],
                "type": "Pembayaran",
                "amount": p["amount"],
                "notes": p["notes"],
            })
        # Urutkan gabungan berdasarkan tanggal terbaru dulu.
        timeline.sort(key=lambda item: item["date"], reverse=True)

        return {
            "id": customer["id"],
            "name": customer["name"],
            "phone": customer["phone"],
            "notes": customer["notes"],
            "is_active": customer["is_active"],
            "created_at": customer["created_at"],
            "total_debt": total_debt,
            "total_paid": total_paid,
            "sisa": sisa,
            "status": "Lunas" if sisa <= 0 else "Masih Berhutang",
            "timeline": timeline,
        }
