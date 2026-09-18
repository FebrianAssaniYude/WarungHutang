"""
test_phase12_integration.py

PHASE 12 - Testing Keseluruhan.

Mensimulasikan operasional warung dari nol sampai akhir, memakai SEMUA
model sekaligus persis seperti alur nyata (bukan unit test terisolasi
per model seperti phase-phase sebelumnya). Tujuannya membuktikan bahwa
seluruh bagian aplikasi bekerja BENAR ketika digabung, bukan cuma benar
sendiri-sendiri.

Skrip ini TIDAK menyentuh GUI (tidak ada tkinter di lingkungan pengujian
ini) - jadi ini adalah pengujian menyeluruh terhadap seluruh lapisan
model/database/business-logic, yang merupakan bagian tersulit untuk
diuji manual. Klik-per-klik GUI tetap perlu diuji manual oleh pengguna.
"""

import os
import sys
import shutil

# File ini ada di dalam tests/, jadi root project adalah satu level di atas.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import Database
from models.customer import CustomerModel
from models.product import ProductModel
from models.debt import DebtModel
from models.payment import PaymentModel
from models.history import HistoryModel
from models.report import ReportModel
from models.settings import SettingsModel
from models.user import UserModel
from utils.backup import backup_database, restore_database
from utils.formatter import format_rupiah

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
# Persiapan lingkungan bersih
# ----------------------------------------------------------------------
TEST_DIR = "/tmp/warung_phase12_test"
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.makedirs(TEST_DIR)
DB_PATH = os.path.join(TEST_DIR, "warung.db")

db = Database(db_path=DB_PATH)
db.initialize()

cm = CustomerModel(db)
pm = ProductModel(db)
dm = DebtModel(db)
pym = PaymentModel(db)
hm = HistoryModel(db)
rm = ReportModel(db)
sm = SettingsModel(db)
um = UserModel(db)

# ----------------------------------------------------------------------
section("1. LOGIN & AKUN (Phase 2)")
# ----------------------------------------------------------------------
user = um.authenticate("admin", "admin")
check("Login dengan akun default admin/admin berhasil", user is not None)

ok, msg = um.change_username(user["id"], "pemilik_warung")
check("Ganti username berhasil", ok)
user["username"] = "pemilik_warung"

ok, msg = um.change_password(user["id"], "admin", "rahasia123")
check("Ganti password berhasil", ok)

relogin = um.authenticate("pemilik_warung", "rahasia123")
check("Login ulang dengan username & password baru berhasil", relogin is not None)

relogin_gagal = um.authenticate("pemilik_warung", "admin")
check("Login dengan password LAMA setelah diganti gagal (benar)", relogin_gagal is None)

# ----------------------------------------------------------------------
section("2. PENGATURAN - Nama Warung (Phase 10)")
# ----------------------------------------------------------------------
saved_name = sm.set_nama_warung("Warung Bu Ani")
check("Nama warung tersimpan", sm.get_nama_warung() == "Warung Bu Ani")

# ----------------------------------------------------------------------
section("3. DATA MASTER - Pelanggan & Barang (Phase 4 & 5)")
# ----------------------------------------------------------------------
_, _, budi_id = cm.add_customer("Budi", "081234567890", "Pelanggan lama")
_, _, siti_id = cm.add_customer("Siti", "", "")
_, _, tono_id = cm.add_customer("Tono", "", "")
check("3 pelanggan berhasil dibuat", all([budi_id, siti_id, tono_id]))

_, _, indomie_id = pm.add_product(name="Indomie Goreng", price=3000, barcode="8991002101012", unit="pcs")
_, _, kopi_id = pm.add_product(name="Kopi ABC", price=5000, barcode="8991002101013", unit="sachet")
_, _, gula_id = pm.add_product(name="Gula Pasir", price=15000, barcode="", unit="kg")
_, _, telur_id = pm.add_product(name="Telur Ayam", price=2000, barcode="", unit="butir")
check("4 barang berhasil dibuat (2 dengan barcode, 2 tanpa)", all([indomie_id, kopi_id, gula_id, telur_id]))

dup_ok, dup_msg, _ = pm.add_product(name="Indomie Palsu", price=3000, barcode="8991002101012")
check("Barcode duplikat ditolak", not dup_ok)

scan_result = pm.get_by_barcode("8991002101012")
check("Scan barcode Indomie ditemukan", scan_result and scan_result["name"] == "Indomie Goreng")

# ----------------------------------------------------------------------
section("4. TRANSAKSI HUTANG - Beberapa Pelanggan (Phase 6)")
# ----------------------------------------------------------------------
ok, msg, tx1 = dm.create_transaction(budi_id, [
    {"product_id": indomie_id, "product_name": "Indomie Goreng", "quantity": 2, "price": 3000},
    {"product_id": kopi_id, "product_name": "Kopi ABC", "quantity": 1, "price": 5000},
])
check("Transaksi Budi #1 (Rp 11.000) tersimpan", ok and dm.get_transaction_detail(tx1)["total_amount"] == 11000)

ok, msg, tx2 = dm.create_transaction(budi_id, [
    {"product_id": gula_id, "product_name": "Gula Pasir", "quantity": 1, "price": 15000},
    {"product_id": None, "product_name": "Minyak Goreng Curah", "quantity": 1, "price": 8000},
])
check("Transaksi Budi #2 (dengan barang manual) tersimpan", ok)

ok, msg, tx3 = dm.create_transaction(siti_id, [
    {"product_id": telur_id, "product_name": "Telur Ayam", "quantity": 10, "price": 2000},
])
check("Transaksi Siti (Rp 20.000) tersimpan", ok)

ok, msg, tx4 = dm.create_transaction(tono_id, [
    {"product_id": indomie_id, "product_name": "Indomie Goreng", "quantity": 1, "price": 3000},
])
check("Transaksi Tono (Rp 3.000) tersimpan", ok)

rej1, _, _ = dm.create_transaction(budi_id, [])
rej2, _, _ = dm.create_transaction(None, [{"product_id": None, "product_name": "X", "quantity": 1, "price": 1000}])
rej3, _, _ = dm.create_transaction(budi_id, [{"product_id": None, "product_name": "Y", "quantity": -1, "price": 1000}])
check("Transaksi tanpa barang / tanpa pelanggan / qty negatif semuanya ditolak", not any([rej1, rej2, rej3]))

# ----------------------------------------------------------------------
section("5. PERUBAHAN HARGA MASTER TIDAK MENGUBAH HISTORI (Phase 6/15)")
# ----------------------------------------------------------------------
pm.update_product(indomie_id, name="Indomie Goreng", price=3500, barcode="8991002101012", unit="pcs")
detail_tx1 = dm.get_transaction_detail(tx1)
indomie_line = next(i for i in detail_tx1["items"] if i["product_name"] == "Indomie Goreng")
check("Harga Indomie di histori TETAP Rp 3.000 walau harga master naik jadi Rp 3.500",
      indomie_line["price"] == 3000)

# ----------------------------------------------------------------------
section("6. PEMBAYARAN - Sebagian, Pas, dan Ditolak (Phase 7)")
# ----------------------------------------------------------------------
total_debt, total_paid, sisa_budi = pym.get_balance(budi_id)
check("Sisa hutang Budi sebelum bayar = 11000+23000 = 34000", sisa_budi == 34000)

ok, msg, _ = pym.create_payment(budi_id, 34000 + 1000)
check("Pembayaran Budi MELEBIHI sisa DITOLAK", not ok)

ok, msg, _ = pym.create_payment(budi_id, 20000)
check("Pembayaran sebagian Budi (Rp 20.000) berhasil", ok)

_, _, sisa_budi_setelah = pym.get_balance(budi_id)
check("Sisa hutang Budi setelah bayar sebagian = 14000", sisa_budi_setelah == 14000)

ok, msg, _ = pym.create_payment(budi_id, 14000)
check("Pelunasan sisa Budi (Rp 14.000, pas) berhasil", ok)

detail_budi = cm.get_detail(budi_id)
check("Status Budi setelah lunas = 'Lunas'", detail_budi["status"] == "Lunas" and detail_budi["sisa"] == 0)

pym.create_payment(siti_id, 5000)
detail_siti = cm.get_detail(siti_id)
check("Siti masih berhutang Rp 15.000 setelah bayar sebagian",
      detail_siti["sisa"] == 15000 and detail_siti["status"] == "Masih Berhutang")

# ----------------------------------------------------------------------
section("7. SOFT DELETE - Pelanggan & Barang (Phase 4/5)")
# ----------------------------------------------------------------------
cm.deactivate_customer(tono_id)
active_customers = [c["name"] for c in cm.list_customers()]
all_customers = [c["name"] for c in cm.list_customers(include_inactive=True)]
check("Tono hilang dari daftar aktif tapi tetap ada di database",
      "Tono" not in active_customers and "Tono" in all_customers)

pm.deactivate_product(telur_id)
active_products = [p["name"] for p in pm.list_products()]
check("Telur Ayam nonaktif tidak muncul di daftar aktif", "Telur Ayam" not in active_products)

history_tono = hm.list_history(customer_id=tono_id)
check("Histori transaksi Tono tetap utuh walau Tono sudah dinonaktifkan", len(history_tono) == 1)

# ----------------------------------------------------------------------
section("8. RIWAYAT - Filter Gabungan (Phase 8)")
# ----------------------------------------------------------------------
all_history = hm.list_history()
check("Total baris riwayat = 4 transaksi hutang + 3 pembayaran = 7", len(all_history) == 7)

hutang_only = hm.list_history(type_filter="hutang")
check("Filter jenis Hutang = 4 baris", len(hutang_only) == 4)

bayar_only = hm.list_history(type_filter="pembayaran")
check("Filter jenis Pembayaran = 3 baris", len(bayar_only) == 3)

budi_history = hm.list_history(customer_id=budi_id)
check("Filter per pelanggan Budi = 4 baris (2 hutang + 2 bayar)", len(budi_history) == 4)

# ----------------------------------------------------------------------
section("9. LAPORAN BULANAN (Phase 9)")
# ----------------------------------------------------------------------
import datetime
now = datetime.datetime.now()
report = rm.get_monthly_report(now.year, now.month)

expected_total_debt_month = 11000 + 23000 + 20000 + 3000
check(f"Total hutang bulan ini = {format_rupiah(expected_total_debt_month)}",
      report["total_debt_month"] == expected_total_debt_month)

expected_total_payment_month = 20000 + 14000 + 5000
check(f"Total pembayaran bulan ini = {format_rupiah(expected_total_payment_month)}",
      report["total_payment_month"] == expected_total_payment_month)

check("Jumlah transaksi hutang bulan ini = 4", report["count_debt_transactions"] == 4)
check("Jumlah transaksi pembayaran bulan ini = 3", report["count_payment_transactions"] == 3)

expected_outstanding = expected_total_debt_month - expected_total_payment_month
check(f"Saldo saat ini (semua pelanggan) = {format_rupiah(expected_outstanding)}",
      report["current_outstanding_balance"] == expected_outstanding)

pdf_path = os.path.join(TEST_DIR, "laporan_test.pdf")
rm.export_to_pdf(report, pdf_path, store_name=sm.get_nama_warung())
check("File PDF laporan berhasil dibuat", os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500)

# ----------------------------------------------------------------------
section("10. BACKUP & RESTORE (Phase 10)")
# ----------------------------------------------------------------------
backup_path = backup_database(DB_PATH)
check("Backup database berhasil dibuat", os.path.exists(backup_path))

dm.create_transaction(siti_id, [{"product_id": None, "product_name": "Barang Setelah Backup", "quantity": 1, "price": 99000}])
_, _, sisa_siti_setelah_tambahan = pym.get_balance(siti_id)
check("Sisa hutang Siti bertambah setelah transaksi baru", sisa_siti_setelah_tambahan == 15000 + 99000)

safety_path = restore_database(backup_path, DB_PATH)
check("Safety-backup otomatis dibuat sebelum restore", safety_path and os.path.exists(safety_path))

db2 = Database(db_path=DB_PATH)
pym2 = PaymentModel(db2)
_, _, sisa_siti_setelah_restore = pym2.get_balance(siti_id)
check("Setelah restore, transaksi ekstra HILANG dari database aktif (kembali ke Rp 15.000)",
      sisa_siti_setelah_restore == 15000)

db_safety = Database(db_path=safety_path)
pym_safety = PaymentModel(db_safety)
_, _, sisa_siti_di_safety = pym_safety.get_balance(siti_id)
check("Data yang 'hilang' tadi TETAP AMAN tersimpan di safety-backup",
      sisa_siti_di_safety == 15000 + 99000)

# ----------------------------------------------------------------------
section("11. INTEGRITAS ATOMIK (Phase 6/11)")
# ----------------------------------------------------------------------
with db2.transaction() as conn:
    tx_count_before = conn.execute("SELECT COUNT(*) AS c FROM debt_transactions").fetchone()["c"]

dm2 = DebtModel(db2)
ok, msg, _ = dm2.create_transaction(budi_id, [
    {"product_id": 999999, "product_name": "Barang Hantu", "quantity": 1, "price": 1000}
])
with db2.transaction() as conn:
    tx_count_after = conn.execute("SELECT COUNT(*) AS c FROM debt_transactions").fetchone()["c"]

check("Transaksi dengan referensi barang tidak valid ditolak & TIDAK menambah baris (atomik)",
      not ok and tx_count_before == tx_count_after)

# ----------------------------------------------------------------------
section("HASIL AKHIR")
# ----------------------------------------------------------------------
print()
print(f"Total pemeriksaan : {PASS + FAIL}")
print(f"Lolos             : {PASS}")
print(f"Gagal             : {FAIL}")
print()
if FAIL == 0:
    print(">>> SEMUA SKENARIO END-TO-END LOLOS <<<")
else:
    print(f">>> ADA {FAIL} SKENARIO YANG GAGAL - PERLU DIPERIKSA <<<")

shutil.rmtree(TEST_DIR, ignore_errors=True)

sys.exit(0 if FAIL == 0 else 1)
