"""
models/history.py

Riwayat gabungan seluruh aktivitas (hutang + pembayaran), dengan filter
jenis, pelanggan, dan rentang tanggal. Histori lama tidak pernah diubah
oleh apa pun di sini - modul ini murni membaca data.
"""

from database.database import Database


class HistoryModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def list_history(
        self,
        type_filter: str = "semua",
        customer_id: int = None,
        date_from: str = None,
        date_to: str = None,
    ):
        """
        Args:
            type_filter: "semua" | "hutang" | "pembayaran"
            customer_id: filter pelanggan tertentu (opsional)
            date_from, date_to: "YYYY-MM-DD" (opsional, inklusif)

        Returns:
            List of dict {date, customer_id, customer_name, type, amount},
            diurutkan dari yang terbaru.
        """
        type_filter = (type_filter or "semua").strip().lower()
        entries = []

        with self.db.transaction() as conn:
            if type_filter in ("semua", "hutang"):
                query = (
                    "SELECT dt.transaction_date AS date, dt.customer_id AS customer_id, "
                    "c.name AS customer_name, dt.total_amount AS amount "
                    "FROM debt_transactions dt "
                    "JOIN customers c ON c.id = dt.customer_id"
                )
                conditions, params = self._build_conditions("dt", customer_id, date_from, date_to)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                for row in conn.execute(query, params).fetchall():
                    entries.append({
                        "date": row["date"],
                        "customer_id": row["customer_id"],
                        "customer_name": row["customer_name"],
                        "type": "Hutang",
                        "amount": row["amount"],
                    })

            if type_filter in ("semua", "pembayaran"):
                query = (
                    "SELECT p.payment_date AS date, p.customer_id AS customer_id, "
                    "c.name AS customer_name, p.amount AS amount "
                    "FROM payments p "
                    "JOIN customers c ON c.id = p.customer_id"
                )
                conditions, params = self._build_conditions(
                    "p", customer_id, date_from, date_to, date_column="payment_date"
                )
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                for row in conn.execute(query, params).fetchall():
                    entries.append({
                        "date": row["date"],
                        "customer_id": row["customer_id"],
                        "customer_name": row["customer_name"],
                        "type": "Pembayaran",
                        "amount": row["amount"],
                    })

        entries.sort(key=lambda e: e["date"], reverse=True)
        return entries

    @staticmethod
    def _build_conditions(alias, customer_id, date_from, date_to, date_column="transaction_date"):
        conditions = []
        params = []

        if customer_id:
            conditions.append(f"{alias}.customer_id = ?")
            params.append(customer_id)
        if date_from:
            conditions.append(f"date({alias}.{date_column}) >= date(?)")
            params.append(date_from)
        if date_to:
            conditions.append(f"date({alias}.{date_column}) <= date(?)")
            params.append(date_to)

        return conditions, params
