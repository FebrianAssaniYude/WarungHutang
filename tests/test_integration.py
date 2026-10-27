import os
import shutil
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    ),
)

from database.database import Database
from models.customer import CustomerModel
from models.product import ProductModel
from models.supplier import SupplierModel
from models.purchase import PurchaseModel
from models.sale import SaleModel
from models.debt import DebtModel
from models.payment import PaymentModel
from models.history import HistoryModel
from models.report import ReportModel
from models.settings import SettingsModel
from models.user import UserModel
from utils.backup import backup_database, restore_database
from utils.printer import Printer


PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL

    if condition:
        PASS += 1
        print(f"  [OK]   {label}")
    else:
        FAIL += 1
        print(f"  [GAGAL] {label}")


def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ----------------------------------------------------------------------
# SETUP
# ----------------------------------------------------------------------

TEST_DIR = tempfile.mkdtemp(prefix="warung_phase12_")
DB_PATH = os.path.join(TEST_DIR, "warung.db")
BACKUP_DIR = os.path.join(TEST_DIR, "backup")
PDF_DIR = os.path.join(TEST_DIR, "pdf")

os.makedirs(PDF_DIR, exist_ok=True)

try:
    db = Database(db_path=DB_PATH)
    db.initialize()

    cm = CustomerModel(db)
    pm = ProductModel(db)
    sm_supplier = SupplierModel(db)
    purchase_model = PurchaseModel(db)
    sale_model = SaleModel(db)
    dm = DebtModel(db)
    pym = PaymentModel(db)
    hm = HistoryModel(db)
    rm = ReportModel(db)
    settings = SettingsModel(db)
    um = UserModel(db)

    # ------------------------------------------------------------------
    # 1. LOGIN
    # ------------------------------------------------------------------

    section("1. LOGIN")

    user = um.authenticate("admin", "admin")
    check(
        "Login default admin/admin berhasil",
        user is not None,
    )

    if user is not None:
        ok, msg = um.change_username(
            user["id"],
            "pemilik_warung",
        )
        check(
            "Ganti username berhasil",
            ok,
        )

        ok, msg = um.change_password(
            user["id"],
            "admin",
            "rahasia123",
        )
        check(
            "Ganti password berhasil",
            ok,
        )

        relogin = um.authenticate(
            "pemilik_warung",
            "rahasia123",
        )
        check(
            "Login ulang dengan password baru berhasil",
            relogin is not None,
        )

        old_password_login = um.authenticate(
            "pemilik_warung",
            "admin",
        )
        check(
            "Login dengan password lama gagal",
            old_password_login is None,
        )

    # ------------------------------------------------------------------
    # 2. SETTINGS
    # ------------------------------------------------------------------

    section("2. SETTINGS")

    saved_name = settings.set_nama_warung(
        "Warung Bu Ani"
    )

    check(
        "Nama warung berhasil disimpan",
        saved_name == "Warung Bu Ani",
    )

    check(
        "Nama warung dapat dibaca kembali",
        settings.get_nama_warung() == "Warung Bu Ani",
    )

    # ------------------------------------------------------------------
    # 3. MASTER CUSTOMER
    # ------------------------------------------------------------------

    section("3. MASTER CUSTOMER")

    ok, msg, budi_id = cm.add_customer(
        "Budi",
        "081234567890",
        "Pelanggan lama",
    )
    check(
        "Customer Budi berhasil dibuat",
        ok and budi_id is not None,
    )

    ok, msg, siti_id = cm.add_customer(
        "Siti",
        "",
        "",
    )
    check(
        "Customer Siti berhasil dibuat",
        ok and siti_id is not None,
    )

    ok, msg, tono_id = cm.add_customer(
        "Tono",
        "",
        "",
    )
    check(
        "Customer Tono berhasil dibuat",
        ok and tono_id is not None,
    )

    # ------------------------------------------------------------------
    # 4. MASTER SUPPLIER
    # ------------------------------------------------------------------

    section("4. MASTER SUPPLIER")

    ok, msg, supplier_id = sm_supplier.add_supplier(
        "Supplier Utama",
        "Supplier integration test",
    )

    check(
        "Supplier berhasil dibuat",
        ok and supplier_id is not None,
    )

    supplier = sm_supplier.get_by_id(supplier_id)
    check(
        "Supplier dapat dibaca",
        supplier is not None
        and supplier["name"] == "Supplier Utama",
    )

    ok, msg = sm_supplier.update_supplier(
        supplier_id,
        "Supplier Utama Update",
        "Updated",
    )

    check(
        "Supplier berhasil diubah",
        ok,
    )

    supplier_list = sm_supplier.list_suppliers(
        "Supplier Utama Update"
    )

    check(
        "Pencarian supplier berhasil",
        len(supplier_list) == 1,
    )

    # ------------------------------------------------------------------
    # 5. MASTER PRODUCT
    # ------------------------------------------------------------------

    section("5. MASTER PRODUCT")

    ok, msg, indomie_id = pm.add_product(
        name="Indomie Goreng",
        purchase_price=2500,
        selling_price=3000,
        barcode="8991002101012",
    )

    check(
        "Produk Indomie berhasil dibuat",
        ok and indomie_id is not None,
    )

    ok, msg, kopi_id = pm.add_product(
        name="Kopi Sachet",
        purchase_price=1800,
        selling_price=2500,
        barcode="8991002101013",
    )

    check(
        "Produk Kopi berhasil dibuat",
        ok and kopi_id is not None,
    )

    ok, msg, gula_id = pm.add_product(
        name="Gula 1 Kg",
        purchase_price=14000,
        selling_price=16000,
        barcode="8991002101014",
    )

    check(
        "Produk Gula berhasil dibuat",
        ok and gula_id is not None,
    )

    duplicate_ok, duplicate_msg, duplicate_id = pm.add_product(
        name="Indomie Duplicate",
        purchase_price=2500,
        selling_price=3000,
        barcode="8991002101012",
    )

    check(
        "Barcode duplikat ditolak",
        not duplicate_ok and duplicate_id is None,
    )

    scanned_product = pm.get_by_barcode(
        "8991002101012"
    )

    check(
        "Pencarian produk berdasarkan barcode berhasil",
        scanned_product is not None
        and scanned_product["id"] == indomie_id,
    )

    # ------------------------------------------------------------------
    # 6. PURCHASE
    # ------------------------------------------------------------------

    section("6. PEMBELIAN + STOK")

    ok, msg, purchase_id = purchase_model.create_transaction(
        [
            {
                "product_id": indomie_id,
                "quantity": 20,
                "price": 2500,
            },
            {
                "product_id": kopi_id,
                "quantity": 10,
                "price": 1800,
            },
            {
                "product_id": gula_id,
                "quantity": 5,
                "price": 14000,
            },
        ],
        notes="Pembelian integration test",
    )

    check(
        "Transaksi pembelian berhasil",
        ok and purchase_id is not None,
    )

    indomie = pm.get_by_id(indomie_id)
    kopi = pm.get_by_id(kopi_id)
    gula = pm.get_by_id(gula_id)

    check(
        "Stok Indomie bertambah menjadi 20",
        indomie is not None
        and indomie["stock"] == 20,
    )

    check(
        "Stok Kopi bertambah menjadi 10",
        kopi is not None
        and kopi["stock"] == 10,
    )

    check(
        "Stok Gula bertambah menjadi 5",
        gula is not None
        and gula["stock"] == 5,
    )

    check(
        "Purchase price Indomie menjadi 2500",
        indomie is not None
        and indomie["purchase_price"] == 2500,
    )

    purchase_detail = purchase_model.get_transaction_detail(
        purchase_id
    )

    check(
        "Detail pembelian dapat dibaca",
        purchase_detail is not None
        and len(purchase_detail["items"]) == 3,
    )

    check(
        "Total pembelian benar",
        purchase_detail is not None
        and purchase_detail["total_amount"] == (
            20 * 2500
            + 10 * 1800
            + 5 * 14000
        ),
    )

    purchases = purchase_model.list_transactions()

    check(
        "Daftar transaksi pembelian berisi transaksi",
        any(
            row["id"] == purchase_id
            for row in purchases
        ),
    )

    # ------------------------------------------------------------------
    # 7. SALE
    # ------------------------------------------------------------------

    section("7. PENJUALAN + STOK")

    ok, msg, sale_id = sale_model.create_transaction(
        [
            {
                "product_id": indomie_id,
                "quantity": 3,
            },
            {
                "product_id": kopi_id,
                "quantity": 2,
            },
        ],
        paid_amount=20000,
        notes="Penjualan integration test",
    )

    check(
        "Transaksi penjualan berhasil",
        ok and sale_id is not None,
    )

    indomie = pm.get_by_id(indomie_id)
    kopi = pm.get_by_id(kopi_id)

    check(
        "Stok Indomie berkurang menjadi 17",
        indomie is not None
        and indomie["stock"] == 17,
    )

    check(
        "Stok Kopi berkurang menjadi 8",
        kopi is not None
        and kopi["stock"] == 8,
    )

    sale_detail = sale_model.get_transaction_detail(
        sale_id
    )

    check(
        "Detail penjualan dapat dibaca",
        sale_detail is not None
        and len(sale_detail["details"]) == 2,
    )

    sale_total = (
        3 * 3000
        + 2 * 2500
    )

    check(
        "Total penjualan benar",
        sale_detail is not None
        and sale_detail["sale"]["total_amount"] == sale_total,
    )

    check(
        "Pembayaran penjualan benar",
        sale_detail is not None
        and sale_detail["sale"]["paid_amount"] == 20000,
    )

    check(
        "Kembalian penjualan benar",
        sale_detail is not None
        and sale_detail["sale"]["change_amount"]
        == 20000 - sale_total,
    )

    # ------------------------------------------------------------------
    # 8. DEBT
    # ------------------------------------------------------------------

    section("8. HUTANG + STOK")

    # Siti membeli 2 Indomie dan 1 Gula.
    ok, msg, debt_id = dm.create_transaction(
        siti_id,
        [
            {
                "product_id": indomie_id,
                "quantity": 2,
            },
            {
                "product_id": gula_id,
                "quantity": 1,
            },
        ],
        notes="Hutang integration test",
    )

    check(
        "Transaksi hutang berhasil",
        ok and debt_id is not None,
    )

    indomie = pm.get_by_id(indomie_id)
    gula = pm.get_by_id(gula_id)

    check(
        "Stok Indomie setelah hutang menjadi 15",
        indomie is not None
        and indomie["stock"] == 15,
    )

    check(
        "Stok Gula setelah hutang menjadi 4",
        gula is not None
        and gula["stock"] == 4,
    )

    debt_detail = dm.get_transaction_detail(
        debt_id
    )

    check(
        "Detail hutang dapat dibaca",
        debt_detail is not None
        and len(debt_detail["items"]) == 2,
    )

    debt_total = (
        2 * 3000
        + 1 * 16000
    )

    check(
        "Total hutang benar",
        debt_detail is not None
        and debt_detail["total_amount"] == debt_total,
    )

    # ------------------------------------------------------------------
    # 9. PAYMENT
    # ------------------------------------------------------------------

    section("9. PEMBAYARAN HUTANG")

    before_payment = cm.get_detail(siti_id)

    check(
        "Detail customer Siti tersedia sebelum pembayaran",
        before_payment is not None,
    )

    ok, msg, payment_id = pym.create_payment(
        siti_id,
        5000,
        notes="Pembayaran sebagian",
    )

    check(
        "Pembayaran hutang berhasil",
        ok and payment_id is not None,
    )

    payment_detail = pym.get_payment_detail(
        payment_id
    )

    check(
        "Detail pembayaran dapat dibaca",
        payment_detail is not None
        and payment_detail["amount"] == 5000,
    )

    # ------------------------------------------------------------------
    # 10. CUSTOMER DETAIL
    # ------------------------------------------------------------------

    section("10. CUSTOMER DETAIL + TIMELINE")

    siti_detail = cm.get_detail(siti_id)

    check(
        "Detail customer Siti dapat dibaca",
        siti_detail is not None,
    )

    timeline = siti_detail.get(
        "timeline",
        []
    ) if siti_detail else []

    check(
        "Timeline customer memiliki transaksi",
        len(timeline) >= 2,
    )

    timeline_types = [
        row.get("type")
        for row in timeline
    ]

    check(
        "Timeline memuat Hutang",
        "Hutang" in timeline_types,
    )

    check(
        "Timeline memuat Pembayaran",
        "Pembayaran" in timeline_types,
    )

    # ------------------------------------------------------------------
    # 11. HISTORY
    # ------------------------------------------------------------------

    section("11. HISTORY")

    history = hm.list_history()

    check(
        "History tidak kosong",
        len(history) > 0,
    )

    history_types = [
        row.get("type")
        for row in history
    ]

    check(
        "History memuat Penjualan",
        "Penjualan" in history_types,
    )

    check(
        "History memuat Pembelian",
        "Pembelian" in history_types,
    )

    check(
        "History memuat Hutang",
        "Hutang" in history_types,
    )

    check(
        "History memuat Pembayaran",
        "Pembayaran" in history_types,
    )

    # ------------------------------------------------------------------
    # 12. DASHBOARD
    # ------------------------------------------------------------------

    section("12. DASHBOARD")

    dashboard = rm.get_dashboard_summary()

    check(
        "Dashboard summary berhasil dibuat",
        dashboard is not None,
    )

    check(
        "Dashboard memiliki total customer",
        dashboard is not None
        and dashboard["total_customers"] >= 3,
    )

    check(
        "Dashboard memiliki total produk",
        dashboard is not None
        and dashboard["total_products"] >= 3,
    )

    check(
        "Dashboard memiliki transaksi terbaru",
        dashboard is not None
        and len(dashboard["recent_transactions"]) > 0,
    )

    check(
        "Dashboard menghitung outstanding",
        dashboard is not None
        and "total_outstanding" in dashboard,
    )

    # ------------------------------------------------------------------
    # 13. MONTHLY REPORT
    # ------------------------------------------------------------------

    section("13. MONTHLY REPORT")

    from datetime import datetime

    now = datetime.now()

    report = rm.get_monthly_report(
        now.year,
        now.month,
    )

    check(
        "Monthly report berhasil dibuat",
        report is not None,
    )

    report_pdf = os.path.join(
        PDF_DIR,
        "laporan_integration.pdf",
    )

    try:
        rm.export_to_pdf(
            report,
            report_pdf,
            store_name=settings.get_nama_warung(),
        )

        check(
            "PDF laporan berhasil dibuat",
            os.path.exists(report_pdf)
            and os.path.getsize(report_pdf) > 0,
        )

    except Exception:
        check(
            "PDF laporan berhasil dibuat",
            False,
        )

    # ------------------------------------------------------------------
    # 14. PRINTER
    # ------------------------------------------------------------------

    section("14. PRINTER / PDF TRANSAKSI")

    printer = Printer(
        store_name=settings.get_nama_warung()
    )

    # Sale
    sale_pdf = os.path.join(
        PDF_DIR,
        "penjualan.pdf",
    )

    try:
        printer.create_pdf(
            "sale",
            {
                "sale_id": sale_id,
                "transaction_number": sale_detail["sale"][
                    "transaction_number"
                ],
                "transaction_date": sale_detail["sale"][
                    "transaction_date"
                ],
                "total_amount": sale_detail["sale"][
                    "total_amount"
                ],
                "paid_amount": sale_detail["sale"][
                    "paid_amount"
                ],
                "change_amount": sale_detail["sale"][
                    "change_amount"
                ],
                "notes": sale_detail["sale"]["notes"],
                "details": sale_detail["details"],
            },
            output_path=sale_pdf,
        )

        check(
            "PDF penjualan berhasil dibuat",
            os.path.exists(sale_pdf)
            and os.path.getsize(sale_pdf) > 0,
        )

    except Exception:
        check(
            "PDF penjualan berhasil dibuat",
            False,
        )

    # Purchase
    purchase_pdf = os.path.join(
        PDF_DIR,
        "pembelian.pdf",
    )

    try:
        printer.create_pdf(
            "purchase",
            purchase_detail,
            output_path=purchase_pdf,
        )

        check(
            "PDF pembelian berhasil dibuat",
            os.path.exists(purchase_pdf)
            and os.path.getsize(purchase_pdf) > 0,
        )

    except Exception:
        check(
            "PDF pembelian berhasil dibuat",
            False,
        )

    # Debt
    debt_pdf = os.path.join(
        PDF_DIR,
        "hutang.pdf",
    )

    try:
        printer.create_pdf(
            "debt",
            {
                "transaction_number": debt_detail[
                    "transaction_number"
                ],
                "transaction_date": debt_detail[
                    "transaction_date"
                ],
                "customer_name": debt_detail[
                    "customer_name"
                ],
                "total_amount": debt_detail[
                    "total_amount"
                ],
                "notes": debt_detail["notes"],
                "details": debt_detail["items"],
            },
            output_path=debt_pdf,
        )

        check(
            "PDF hutang berhasil dibuat",
            os.path.exists(debt_pdf)
            and os.path.getsize(debt_pdf) > 0,
        )

    except Exception:
        check(
            "PDF hutang berhasil dibuat",
            False,
        )

    # Payment
    payment_pdf = os.path.join(
        PDF_DIR,
        "pembayaran.pdf",
    )

    try:
        printer.create_pdf(
            "payment",
            {
                "payment_id": payment_detail["id"],
                "customer_name": payment_detail[
                    "customer_name"
                ],
                "payment_date": payment_detail[
                    "payment_date"
                ],
                "amount": payment_detail["amount"],
                "notes": payment_detail["notes"],
            },
            output_path=payment_pdf,
        )

        check(
            "PDF pembayaran berhasil dibuat",
            os.path.exists(payment_pdf)
            and os.path.getsize(payment_pdf) > 0,
        )

    except Exception:
        check(
            "PDF pembayaran berhasil dibuat",
            False,
        )

    # ------------------------------------------------------------------
    # 15. INVALID STOCK / ATOMIC VALIDATION
    # ------------------------------------------------------------------

    section("15. ATOMIC VALIDATION")

    before_debt_count = len(
        dm.get_transaction_detail(999999)
        or {}
    )

    ok, msg, transaction_id = dm.create_transaction(
        customer_id=siti_id,
        items=[
            {
                "product_id": 999999,
                "quantity": 1,
            }
        ],
    )

    check(
        not ok and transaction_id is None,
        "Debt invalid product ditolak",
    )

    after_debt_detail = dm.get_transaction_detail(999999)

    check(
        before_debt_count == len(after_debt_detail or {}),
        "Debt invalid tidak membuat transaksi",
    )

    # ------------------------------------------------------------------
    # 16. BACKUP
    # ------------------------------------------------------------------

    section("16. BACKUP")

    backup_path = backup_database(
        DB_PATH,
        BACKUP_DIR,
    )

    check(
        "Backup database berhasil dibuat",
        os.path.exists(backup_path),
    )

    backup_db = Database(
        db_path=backup_path
    )

    backup_db.initialize()

    backup_settings = SettingsModel(
        backup_db
    )

    check(
        "Data settings ikut tersimpan dalam backup",
        backup_settings.get_nama_warung()
        == "Warung Bu Ani",
    )

    # ------------------------------------------------------------------
    # 17. RESTORE
    # ------------------------------------------------------------------

    section("17. RESTORE")

    # Tambahkan perubahan setelah backup.
    ok, msg, extra_customer_id = cm.add_customer(
        "Customer Setelah Backup",
        "",
        "",
    )

    check(
        "Data tambahan setelah backup berhasil dibuat",
        ok and extra_customer_id is not None,
    )

    customer_before_restore = cm.get_detail(
        extra_customer_id
    )

    check(
        customer_before_restore is not None,
        "Data tambahan setelah backup berhasil dibuat",
    )

    safety_backup = restore_database(
        backup_path,
        DB_PATH,
    )

    check(
        "Restore database berhasil",
        os.path.exists(DB_PATH),
    )

    check(
        "Safety backup sebelum restore dibuat",
        safety_backup is not None
        and os.path.exists(safety_backup),
    )

    restored_db = Database(
        db_path=DB_PATH
    )

    restored_customer_model = CustomerModel(
        restored_db
    )

    restored_extra_customer = (
        restored_customer_model.get_detail(
            extra_customer_id
        )
    )

    check(
        "Data setelah backup hilang setelah restore",
        restored_extra_customer is None,
    )

    restored_settings = SettingsModel(
        restored_db
    )

    check(
        "Data settings dari backup berhasil dipulihkan",
        restored_settings.get_nama_warung()
        == "Warung Bu Ani",
    )

    # ------------------------------------------------------------------
    # 18. FINAL DATABASE INTEGRITY
    # ------------------------------------------------------------------

    section("18. FINAL DATABASE INTEGRITY")

    with restored_db.transaction() as conn:
        integrity = conn.execute(
            "PRAGMA integrity_check;"
        ).fetchone()[0]

        foreign_keys = conn.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()[0]

    check(
        "SQLite integrity_check = ok",
        integrity == "ok",
    )

    check(
        "Foreign key aktif",
        foreign_keys == 1,
    )

finally:
    # Jangan menghapus TEST_DIR agar PDF/database hasil test
    # bisa diperiksa jika ada kegagalan.
    pass


# ----------------------------------------------------------------------
# RESULT
# ----------------------------------------------------------------------

print()
print("=" * 70)
print("HASIL INTEGRATION TEST")
print("=" * 70)

print(f"PASS : {PASS}")
print(f"FAIL : {FAIL}")
print(f"TEST DIR : {TEST_DIR}")

if FAIL == 0:
    print()
    print("SEMUA INTEGRATION TEST BERHASIL.")
    sys.exit(0)

print()
print("MASIH ADA TEST YANG GAGAL.")
sys.exit(1)