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
        Mengambil seluruh riwayat transaksi.

        type_filter:
            "semua"
            "hutang"
            "pembayaran"
            "pembelian"
            "penjualan"

        customer_id:
            Filter pelanggan.
            Jika dipilih, hanya Hutang dan Pembayaran
            yang ditampilkan karena Pembelian dan Penjualan
            tidak memiliki customer_id.

        date_from/date_to:
            Format YYYY-MM-DD, inklusif.

        Returns:
            List of dict:
            {
                "date": ...,
                "customer_id": ...,
                "customer_name": ...,
                "type": ...,
                "amount": ...,
                "transaction_id": ...,
                "transaction_number": ...
            }
        """

        type_filter = (type_filter or "semua").strip().lower()

        valid_filters = {
            "semua",
            "hutang",
            "pembayaran",
            "pembelian",
            "penjualan",
        }

        if type_filter not in valid_filters:
            type_filter = "semua"

        entries = []

        with self.db.transaction() as conn:

            # =====================================================
            # HUTANG
            # =====================================================

            if type_filter in ("semua", "hutang"):

                query = """
                    SELECT
                        dt.id AS transaction_id,
                        dt.transaction_number,
                        dt.transaction_date AS date,
                        dt.customer_id,
                        c.name AS customer_name,
                        dt.total_amount AS amount
                    FROM debt_transactions dt
                    JOIN customers c
                        ON c.id = dt.customer_id
                """

                conditions, params = self._build_conditions(
                    alias="dt",
                    customer_id=customer_id,
                    date_from=date_from,
                    date_to=date_to,
                    date_column="transaction_date",
                )

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += """
                    ORDER BY dt.transaction_date DESC,
                             dt.id DESC
                """

                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    entries.append(
                        {
                            "date": row["date"],
                            "customer_id": row["customer_id"],
                            "customer_name": row["customer_name"],
                            "type": "Hutang",
                            "amount": row["amount"],
                            "transaction_id": row["transaction_id"],
                            "transaction_number": row["transaction_number"],
                        }
                    )

            # =====================================================
            # PEMBAYARAN
            # =====================================================

            if type_filter in ("semua", "pembayaran"):

                query = """
                    SELECT
                        p.id AS transaction_id,
                        NULL AS transaction_number,
                        p.payment_date AS date,
                        p.customer_id,
                        c.name AS customer_name,
                        p.amount AS amount
                    FROM payments p
                    JOIN customers c
                        ON c.id = p.customer_id
                """

                conditions, params = self._build_conditions(
                    alias="p",
                    customer_id=customer_id,
                    date_from=date_from,
                    date_to=date_to,
                    date_column="payment_date",
                )

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += """
                    ORDER BY p.payment_date DESC,
                             p.id DESC
                """

                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    entries.append(
                        {
                            "date": row["date"],
                            "customer_id": row["customer_id"],
                            "customer_name": row["customer_name"],
                            "type": "Pembayaran",
                            "amount": row["amount"],
                            "transaction_id": row["transaction_id"],
                            "transaction_number": row["transaction_number"],
                        }
                    )

            # =====================================================
            # PEMBELIAN
            #
            # Hanya ditampilkan jika tidak sedang memfilter
            # berdasarkan pelanggan.
            # =====================================================

            if (
                type_filter in ("semua", "pembelian")
                and customer_id is None
            ):

                query = """
                    SELECT
                        p.id AS transaction_id,
                        p.transaction_number,
                        p.transaction_date AS date,
                        p.total_amount AS amount
                    FROM purchases p
                """

                conditions, params = self._build_conditions(
                    alias="p",
                    customer_id=None,
                    date_from=date_from,
                    date_to=date_to,
                    date_column="transaction_date",
                )

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += """
                    ORDER BY p.transaction_date DESC,
                             p.id DESC
                """

                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    entries.append(
                        {
                            "date": row["date"],
                            "customer_id": None,
                            "customer_name": "-",
                            "type": "Pembelian",
                            "amount": row["amount"],
                            "transaction_id": row["transaction_id"],
                            "transaction_number": row["transaction_number"],
                        }
                    )

            # =====================================================
            # PENJUALAN
            #
            # Hanya ditampilkan jika tidak sedang memfilter
            # berdasarkan pelanggan.
            # =====================================================

            if (
                type_filter in ("semua", "penjualan")
                and customer_id is None
            ):

                query = """
                    SELECT
                        s.id AS transaction_id,
                        s.transaction_number,
                        s.transaction_date AS date,
                        s.total_amount AS amount
                    FROM sales s
                """

                conditions, params = self._build_conditions(
                    alias="s",
                    customer_id=None,
                    date_from=date_from,
                    date_to=date_to,
                    date_column="transaction_date",
                )

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += """
                    ORDER BY s.transaction_date DESC,
                             s.id DESC
                """

                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    entries.append(
                        {
                            "date": row["date"],
                            "customer_id": None,
                            "customer_name": "-",
                            "type": "Penjualan",
                            "amount": row["amount"],
                            "transaction_id": row["transaction_id"],
                            "transaction_number": row["transaction_number"],
                        }
                    )

        # =========================================================
        # SORT GABUNGAN
        # =========================================================

        entries.sort(
            key=lambda entry: (
                entry["date"] or "",
                entry["transaction_id"] or 0,
            ),
            reverse=True,
        )

        return entries

    @staticmethod
    def _build_conditions(
        alias,
        customer_id,
        date_from,
        date_to,
        date_column="transaction_date",
    ):
        conditions = []
        params = []

        if customer_id:
            conditions.append(
                f"{alias}.customer_id = ?"
            )
            params.append(customer_id)

        if date_from:
            conditions.append(
                f"date({alias}.{date_column}) >= date(?)"
            )
            params.append(date_from)

        if date_to:
            conditions.append(
                f"date({alias}.{date_column}) <= date(?)"
            )
            params.append(date_to)

        return conditions, params