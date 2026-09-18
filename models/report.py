"""
models/report.py

Laporan bulanan: ringkasan aktivitas BULAN TERSEBUT saja (hutang &
pembayaran yang dibuat/dilakukan pada bulan itu) - TIDAK dicampur
dengan saldo pelanggan yang masih berjalan dari bulan-bulan sebelumnya.

"Saldo saat ini" ditampilkan terpisah sebagai info tambahan (total
sisa hutang seluruh pelanggan per hari ini), sesuai spesifikasi:
    Aktivitas bulan tersebut   != Saldo saat ini

Export PDF memakai reportlab (satu-satunya dependency tambahan untuk
fitur ini) dengan layout teks sederhana - sengaja tidak memakai
komponen berat (grafik, gambar, dsb) supaya tetap ringan.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from database.database import Database
from utils.formatter import format_rupiah, format_date_indonesia, BULAN_INDONESIA


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
            current_outstanding_balance,   # saldo saat ini, SEMUA waktu
            details: list of {date, customer_name, type, amount, notes}
                     (hanya aktivitas BULAN INI, urut tanggal naik)
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

            debt_rows = conn.execute(
                "SELECT dt.transaction_date AS date, c.name AS customer_name, "
                "dt.total_amount AS amount, dt.notes "
                "FROM debt_transactions dt JOIN customers c ON c.id = dt.customer_id "
                "WHERE strftime('%Y-%m', dt.transaction_date) = ? "
                "ORDER BY dt.transaction_date ASC;",
                (month_str,),
            ).fetchall()

            payment_rows = conn.execute(
                "SELECT p.payment_date AS date, c.name AS customer_name, "
                "p.amount AS amount, p.notes "
                "FROM payments p JOIN customers c ON c.id = p.customer_id "
                "WHERE strftime('%Y-%m', p.payment_date) = ? "
                "ORDER BY p.payment_date ASC;",
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

        details = []
        for row in debt_rows:
            details.append({
                "date": row["date"], "customer_name": row["customer_name"],
                "type": "Hutang", "amount": row["amount"], "notes": row["notes"],
            })
        for row in payment_rows:
            details.append({
                "date": row["date"], "customer_name": row["customer_name"],
                "type": "Pembayaran", "amount": row["amount"], "notes": row["notes"],
            })
        details.sort(key=lambda item: item["date"])

        return {
            "year": int(year),
            "month": int(month),
            "total_debt_month": debt_summary["total"],
            "total_payment_month": payment_summary["total"],
            "count_debt_transactions": debt_summary["cnt"],
            "count_payment_transactions": payment_summary["cnt"],
            "current_outstanding_balance": global_debt - global_paid,
            "details": details,
        }

    # ------------------------------------------------------------------
    # Export PDF (ringan - teks biasa, tanpa grafik/gambar)
    # ------------------------------------------------------------------
    def export_to_pdf(self, report: dict, output_path: str, store_name: str = "Warung Hutang"):
        page_width, page_height = A4
        margin_left = 2 * cm
        margin_top = page_height - 2 * cm
        bottom_limit = 2 * cm

        c = canvas.Canvas(output_path, pagesize=A4)
        y = [margin_top]  # list agar bisa diubah dari nested function (workaround nonlocal-like)

        def draw_page_header():
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin_left, y[0], store_name)
            y[0] -= 0.8 * cm
            c.setFont("Helvetica", 11)
            period_text = f"Laporan Bulanan - {BULAN_INDONESIA[report['month'] - 1]} {report['year']}"
            c.drawString(margin_left, y[0], period_text)
            y[0] -= 1.0 * cm

        def draw_summary():
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin_left, y[0], "Ringkasan Bulan Ini")
            y[0] -= 0.7 * cm
            c.setFont("Helvetica", 10.5)

            lines = [
                f"Total Hutang Bulan Ini      : {format_rupiah(report['total_debt_month'])}",
                f"Total Pembayaran Bulan Ini  : {format_rupiah(report['total_payment_month'])}",
                f"Jumlah Transaksi Hutang     : {report['count_debt_transactions']}",
                f"Jumlah Transaksi Pembayaran : {report['count_payment_transactions']}",
            ]
            for line in lines:
                c.drawString(margin_left, y[0], line)
                y[0] -= 0.55 * cm

            y[0] -= 0.2 * cm
            c.setFont("Helvetica-Oblique", 9.5)
            c.drawString(
                margin_left, y[0],
                "Catatan: angka di atas hanya aktivitas bulan ini, bukan sisa hutang berjalan.",
            )
            y[0] -= 0.5 * cm
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(
                margin_left, y[0],
                f"Saldo Saat Ini (Seluruh Pelanggan): {format_rupiah(report['current_outstanding_balance'])}",
            )
            y[0] -= 1.0 * cm

        def draw_table_header():
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin_left, y[0], "Tanggal")
            c.drawString(margin_left + 3.5 * cm, y[0], "Pelanggan")
            c.drawString(margin_left + 9.5 * cm, y[0], "Jenis")
            c.drawString(margin_left + 12.5 * cm, y[0], "Nominal")
            y[0] -= 0.15 * cm
            c.line(margin_left, y[0], page_width - margin_left, y[0])
            y[0] -= 0.45 * cm
            c.setFont("Helvetica", 9.5)

        def ensure_space(min_space=0.6 * cm):
            if y[0] < bottom_limit + min_space:
                c.showPage()
                y[0] = margin_top
                draw_table_header()

        draw_page_header()
        draw_summary()

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_left, y[0], "Detail Transaksi Bulan Ini")
        y[0] -= 0.7 * cm

        draw_table_header()

        if not report["details"]:
            c.drawString(margin_left, y[0], "Tidak ada transaksi pada bulan ini.")
            y[0] -= 0.5 * cm
        else:
            for item in report["details"]:
                ensure_space()
                c.drawString(margin_left, y[0], format_date_indonesia(item["date"]))
                c.drawString(margin_left + 3.5 * cm, y[0], (item["customer_name"] or "-")[:22])
                c.drawString(margin_left + 9.5 * cm, y[0], item["type"])
                c.drawString(margin_left + 12.5 * cm, y[0], format_rupiah(item["amount"]))
                y[0] -= 0.5 * cm

        c.save()
        return output_path
