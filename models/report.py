
from models.settings import SettingsModel
from database.database import Database


class ReportModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Data laporan
    # ------------------------------------------------------------------
    def get_monthly_report(self, year: int, month: int):
        """
        Returns dict:
            year, month,
            total_debt_month, total_payment_month,
            count_debt_transactions, count_payment_transactions,
            total_purchase_month, count_purchase_month,
            total_purchase_items_month,
            current_outstanding_balance,   # saldo saat ini, SEMUA waktu
            details: list of {transaction_id, transaction_number, date,
                     customer_name, type, amount, notes, items}
                     (hanya aktivitas BULAN INI, urut tanggal naik)
            purchases: list of {id, transaction_id, transaction_number,
                     date, supplier_name, total_amount, amount, notes,
                     items} (hanya pembelian BULAN INI)
        """
        month_str = f"{int(year):04d}-{int(month):02d}"

        with self.db.transaction() as conn:
            debt_summary = conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS total, COUNT(*) AS cnt "
                "FROM debt_transactions WHERE strftime('%Y-%m', transaction_date) = ?;",
                (month_str,),
            ).fetchone()

            payment_summary = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
                "FROM payments WHERE strftime('%Y-%m', payment_date) = ?;",
                (month_str,),
            ).fetchone()

            purchase_summary = conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS total, COUNT(*) AS cnt "
                "FROM purchases WHERE strftime('%Y-%m', transaction_date) = ?;",
                (month_str,),
            ).fetchone()

            debt_rows = conn.execute(
                "SELECT dt.id AS transaction_id, dt.transaction_number, "
                "dt.transaction_date AS date, c.name AS customer_name, "
                "dt.total_amount AS amount, dt.notes "
                "FROM debt_transactions dt JOIN customers c ON c.id = dt.customer_id "
                "WHERE strftime('%Y-%m', dt.transaction_date) = ? "
                "ORDER BY dt.transaction_date ASC, dt.id ASC;",
                (month_str,),
            ).fetchall()

            debt_item_rows = conn.execute(
                "SELECT dd.transaction_id, dd.product_id, dd.product_name, "
                "dd.quantity, dd.price, dd.subtotal "
                "FROM debt_details dd "
                "JOIN debt_transactions dt ON dt.id = dd.transaction_id "
                "WHERE strftime('%Y-%m', dt.transaction_date) = ? "
                "ORDER BY dd.transaction_id ASC, dd.id ASC;",
                (month_str,),
            ).fetchall()

            payment_rows = conn.execute(
                "SELECT p.id AS transaction_id, NULL AS transaction_number, "
                "p.payment_date AS date, c.name AS customer_name, "
                "p.amount AS amount, p.notes "
                "FROM payments p JOIN customers c ON c.id = p.customer_id "
                "WHERE strftime('%Y-%m', p.payment_date) = ? "
                "ORDER BY p.payment_date ASC, p.id ASC;",
                (month_str,),
            ).fetchall()

            purchase_rows = conn.execute(
                "SELECT p.id, p.transaction_number, p.transaction_date AS date, "
                "s.name AS supplier_name, p.total_amount, p.notes "
                "FROM purchases p "
                "LEFT JOIN suppliers s ON s.id = p.supplier_id "
                "WHERE strftime('%Y-%m', p.transaction_date) = ? "
                "ORDER BY p.transaction_date ASC, p.id ASC;",
                (month_str,),
            ).fetchall()

            purchase_item_rows = conn.execute(
                "SELECT pd.purchase_id, pd.product_id, pd.product_name, "
                "pd.quantity, pd.price, pd.subtotal "
                "FROM purchase_details pd "
                "JOIN purchases p ON p.id = pd.purchase_id "
                "WHERE strftime('%Y-%m', p.transaction_date) = ? "
                "ORDER BY pd.purchase_id ASC, pd.id ASC;",
                (month_str,),
            ).fetchall()

            # Saldo saat ini: SEMUA transaksi sepanjang waktu, TIDAK dibatasi
            # bulan yang sedang dilihat - ini metrik yang berbeda dan sengaja
            # tidak dicampur dengan angka aktivitas bulan di atas.
            global_debt = conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS total FROM debt_transactions;"
            ).fetchone()["total"]
            global_paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments;"
            ).fetchone()["total"]

        def group_items(rows, key):
            grouped = {}

            for row in rows:
                grouped.setdefault(row[key], []).append(
                    {
                        "product_id": row["product_id"],
                        "product_name": row["product_name"],
                        "quantity": row["quantity"],
                        "price": row["price"],
                        "subtotal": row["subtotal"],
                    }
                )

            return grouped

        debt_items = group_items(debt_item_rows, "transaction_id")
        purchase_items = group_items(purchase_item_rows, "purchase_id")

        details = []
        for row in debt_rows:
            details.append({
                "transaction_id": row["transaction_id"],
                "transaction_number": row["transaction_number"],
                "date": row["date"], "customer_name": row["customer_name"],
                "type": "Hutang", "amount": row["amount"], "notes": row["notes"],
                "items": debt_items.get(row["transaction_id"], []),
            })
        for row in payment_rows:
            details.append({
                "transaction_id": row["transaction_id"],
                "transaction_number": row["transaction_number"],
                "date": row["date"], "customer_name": row["customer_name"],
                "type": "Pembayaran", "amount": row["amount"], "notes": row["notes"],
                "items": [],
            })
        details.sort(key=lambda item: item["date"])

        purchases = []
        for row in purchase_rows:
            purchases.append({
                "id": row["id"],
                "transaction_id": row["id"],
                "transaction_number": row["transaction_number"],
                "date": row["date"],
                "supplier_name": row["supplier_name"],
                "total_amount": row["total_amount"],
                "amount": row["total_amount"],
                "notes": row["notes"],
                "items": purchase_items.get(row["id"], []),
            })

        total_purchase_items = sum(
            item["quantity"]
            for purchase in purchases
            for item in purchase["items"]
        )

        return {
            "year": int(year),
            "month": int(month),
            "total_debt_month": debt_summary["total"],
            "total_payment_month": payment_summary["total"],
            "count_debt_transactions": debt_summary["cnt"],
            "count_payment_transactions": payment_summary["cnt"],
            "total_purchase_month": purchase_summary["total"],
            "count_purchase_month": purchase_summary["cnt"],
            "total_purchase_items_month": total_purchase_items,
            "current_outstanding_balance": global_debt - global_paid,
            "details": details,
            "purchases": purchases,
        }
    # ------------------------------------------------------------------
    # Data dashboard
    # ------------------------------------------------------------------
    def get_dashboard_summary(self, low_stock_threshold: int = 5):
        """
        Mengambil ringkasan data untuk Dashboard.
        """
        with self.db.transaction() as conn:
            customer_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM customers
                WHERE is_active = 1;
                """
            ).fetchone()["total"]

            product_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM products
                WHERE is_active = 1;
                """
            ).fetchone()["total"]

            low_stock_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM products
                WHERE is_active = 1
                  AND stock <= ?;
                """,
                (int(low_stock_threshold),),
            ).fetchone()["total"]

            total_debt = conn.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM debt_transactions;
                """
            ).fetchone()["total"]

            total_payment = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM payments;
                """
            ).fetchone()["total"]

            today_sales = conn.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM sales
                WHERE date(transaction_date) = date('now', 'localtime');
                """
            ).fetchone()["total"]

            today_purchases = conn.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM purchases
                WHERE date(transaction_date) = date('now', 'localtime');
                """
            ).fetchone()["total"]

            today_debt = conn.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM debt_transactions
                WHERE date(transaction_date) = date('now', 'localtime');
                """
            ).fetchone()["total"]

            today_payments = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) = date('now', 'localtime');
                """
            ).fetchone()["total"]

            recent_sales = conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    transaction_date AS date,
                    'Penjualan' AS type,
                    total_amount AS amount
                FROM sales
                ORDER BY transaction_date DESC, id DESC
                LIMIT 10;
                """
            ).fetchall()

            recent_purchases = conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    transaction_date AS date,
                    'Pembelian' AS type,
                    total_amount AS amount
                FROM purchases
                ORDER BY transaction_date DESC, id DESC
                LIMIT 10;
                """
            ).fetchall()

            recent_debts = conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    transaction_date AS date,
                    'Hutang' AS type,
                    total_amount AS amount
                FROM debt_transactions
                ORDER BY transaction_date DESC, id DESC
                LIMIT 10;
                """
            ).fetchall()

            recent_payments = conn.execute(
                """
                SELECT
                    id,
                    NULL AS transaction_number,
                    payment_date AS date,
                    'Pembayaran' AS type,
                    amount
                FROM payments
                ORDER BY payment_date DESC, id DESC
                LIMIT 10;
                """
            ).fetchall()

        recent_transactions = [
            dict(row)
            for row in (
                list(recent_sales)
                + list(recent_purchases)
                + list(recent_debts)
                + list(recent_payments)
            )
        ]

        recent_transactions.sort(
            key=lambda item: (
                item.get("date") or "",
                item.get("id") or 0,
            ),
            reverse=True,
        )

        return {
            "total_outstanding": total_debt - total_payment,
            "total_customers": customer_count,
            "total_products": product_count,
            "low_stock_products": low_stock_count,
            "today_sales": today_sales,
            "today_purchases": today_purchases,
            "today_debt": today_debt,
            "today_payments": today_payments,
            "recent_transactions": recent_transactions[:10],
        }
    # ------------------------------------------------------------------
    # Export PDF
    # ------------------------------------------------------------------
    def export_to_pdf(
        self,
        report: dict,
        output_path: str,
        store_name: str = None,
    ):
        """
        Cetak laporan bulanan.

        Didelegasikan ke `Printer` agar tampilan konsisten dengan
        dokumen lain (riwayat pelanggan, nota). `store_name` tetap
        diselesaikan dari database milik model ini agar pengujian
        dengan database temp tidak membaca settings produksi.
        """
        if not store_name:
            try:
                store_name = SettingsModel(self.db).get_nama_warung()
            except Exception:
                store_name = "Warung Hutang"

        from utils.printer import Printer

        return Printer(store_name=store_name).create_pdf(
            "monthly_report",
            report,
            output_path=output_path,
        )
