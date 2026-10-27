"""
Tes kelompok pelanggan dan rantai migrasi sampai schema v4.

Jalankan:  python -m pytest tests/test_customer_group.py -q
Semua tes memakai database sementara; database asli tidak disentuh.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import CURRENT_SCHEMA_VERSION, Database  # noqa: E402
from models.customer import (  # noqa: E402
    KEEP_GROUP,
    NO_GROUP,
    CustomerModel,
)


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------

def columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table});").fetchall()
    }


def table_exists(conn, table):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;",
            (table,),
        ).fetchone()
        is not None
    )


def create_v1_database(path):
    """Database v1 minimal (tanpa schema_version) dengan data contoh."""
    conn = sqlite3.connect(path)

    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                unit TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE debt_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                transaction_date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                total_amount INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE TABLE debt_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                subtotal INTEGER NOT NULL,
                FOREIGN KEY (transaction_id) REFERENCES debt_transactions(id)
            );
            CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                amount INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE TABLE settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT
            );

            INSERT INTO users (username, password_hash) VALUES ('admin', 'x');
            INSERT INTO customers (name) VALUES ('Budi'), ('Siti');
            INSERT INTO products (name, price) VALUES ('Indomie', 3500);
            INSERT INTO debt_transactions (customer_id, total_amount)
                VALUES (1, 7000), (2, 5000);
            INSERT INTO payments (customer_id, amount) VALUES (1, 4000);
            INSERT INTO settings (key, value) VALUES ('nama_warung', 'Warung Test');
            """
        )
        conn.commit()
    finally:
        conn.close()


def balance_snapshot(db):
    with db.transaction() as conn:
        debt = conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) AS t FROM debt_transactions;"
        ).fetchone()["t"]
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM payments;"
        ).fetchone()["t"]

    return debt, paid


@pytest.fixture
def fresh_db(tmp_path):
    db = Database(str(tmp_path / "fresh.db"))
    db.initialize()
    return db


@pytest.fixture
def model(fresh_db):
    return CustomerModel(fresh_db)


def add_debt(db, customer_id, amount):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO debt_transactions (customer_id, total_amount) "
            "VALUES (?, ?);",
            (customer_id, amount),
        )


# ----------------------------------------------------------------------
# Migrasi dan schema
# ----------------------------------------------------------------------

def test_current_version_is_4():
    assert CURRENT_SCHEMA_VERSION == 4


def test_fresh_database_is_v4_and_complete(fresh_db):
    conn = fresh_db.connect()

    try:
        version = conn.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()["version"]

        assert version == 4
        assert table_exists(conn, "customer_groups")
        assert "group_id" in columns(conn, "customers")
        assert {
            "total_debt_at_payment",
            "remaining_debt_at_payment",
        } <= columns(conn, "payments")
    finally:
        conn.close()

    # initialize() kedua pada DB baru tidak mengubah apa pun.
    fresh_db.initialize()


def test_v1_migrates_to_v4_with_single_true_backup(tmp_path):
    path = str(tmp_path / "legacy.db")
    create_v1_database(path)

    db = Database(path)
    before = balance_snapshot(db)

    db.initialize()

    # Versi akhir, data utuh.
    conn = db.connect()

    try:
        assert (
            conn.execute("SELECT version FROM schema_version;").fetchone()[0]
            == 4
        )
        assert table_exists(conn, "customer_groups")
        assert "group_id" in columns(conn, "customers")
        assert {
            "total_debt_at_payment",
            "remaining_debt_at_payment",
        } <= columns(conn, "payments")
        assert conn.execute(
            "SELECT COUNT(*) FROM customers;"
        ).fetchone()[0] == 2
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM customers WHERE group_id IS NULL;"
            ).fetchone()[0]
            == 2
        )
        assert conn.execute("PRAGMA integrity_check;").fetchone()[0] == "ok"
    finally:
        conn.close()

    assert balance_snapshot(db) == before

    # Tepat satu backup, dan isinya kondisi v1 ASLI (bukan hasil migrasi).
    backup_dir = tmp_path / "backup"
    backups = sorted(backup_dir.glob("pre_migration_*.db"))

    assert len(backups) == 1

    backup = sqlite3.connect(str(backups[0]))
    backup.row_factory = sqlite3.Row

    try:
        assert not table_exists(backup, "schema_version")
        assert "group_id" not in columns(backup, "customers")
        assert backup.execute(
            "SELECT COUNT(*) FROM customers;"
        ).fetchone()[0] == 2
    finally:
        backup.close()

    # initialize() kedua: tidak ada migrasi dan tidak ada backup baru.
    db.initialize()
    assert len(list(backup_dir.glob("pre_migration_*.db"))) == 1


def test_v3_migrates_to_v4(tmp_path):
    path = str(tmp_path / "v3.db")
    create_v1_database(path)

    db = Database(path)
    db._migrate_v1_to_v2()
    db._migrate_v2_to_v3()

    conn = db.connect()
    try:
        assert (
            conn.execute("SELECT version FROM schema_version;").fetchone()[0]
            == 3
        )
        assert not table_exists(conn, "customer_groups")
    finally:
        conn.close()

    before = balance_snapshot(db)

    db.initialize()

    conn = db.connect()
    try:
        assert (
            conn.execute("SELECT version FROM schema_version;").fetchone()[0]
            == 4
        )
        assert table_exists(conn, "customer_groups")
        assert "group_id" in columns(conn, "customers")
    finally:
        conn.close()

    assert balance_snapshot(db) == before
    assert len(list((tmp_path / "backup").glob("pre_migration_*.db"))) == 1


def test_unknown_future_version_is_rejected(fresh_db):
    with fresh_db.transaction() as conn:
        conn.execute("UPDATE schema_version SET version = 99;")

    with pytest.raises(RuntimeError):
        fresh_db.initialize()


def test_fresh_and_migrated_schema_match(tmp_path, fresh_db):
    path = str(tmp_path / "legacy.db")
    create_v1_database(path)

    migrated = Database(path)
    migrated.initialize()

    fresh_conn = fresh_db.connect()
    migrated_conn = migrated.connect()

    try:
        for table in ("customer_groups", "customers", "payments"):
            assert columns(fresh_conn, table) == columns(migrated_conn, table)
    finally:
        fresh_conn.close()
        migrated_conn.close()


# ----------------------------------------------------------------------
# Kelompok
# ----------------------------------------------------------------------

def test_add_group_validation(model):
    assert model.add_group("")[0] is False
    assert model.add_group("   ")[0] is False
    assert model.add_group("x" * 41)[0] is False

    ok, _, group_id = model.add_group("  Tetangga  ")
    assert ok and group_id

    # Nama dirapikan dan unik tanpa membedakan huruf besar/kecil.
    assert model.list_groups()[0]["name"] == "Tetangga"
    assert model.add_group("tetangga")[0] is False
    assert model.add_group("TETANGGA ")[0] is False


def test_rename_group(model):
    _, _, a = model.add_group("Tetangga")
    _, _, b = model.add_group("Pegawai")

    assert model.rename_group(a, "Tetangga Dekat")[0] is True
    assert model.rename_group(a, "pegawai")[0] is False   # bentrok dengan b
    assert model.rename_group(a, "tetangga dekat")[0] is True  # huruf saja
    assert model.rename_group(a, "")[0] is False
    assert model.rename_group(9999, "Baru")[0] is False


def test_customer_with_group_and_filters(model):
    _, _, tetangga = model.add_group("Tetangga")
    _, _, pegawai = model.add_group("Pegawai")

    model.add_customer("Budi", group_id=tetangga)
    model.add_customer("Siti", group_id=pegawai)
    model.add_customer("Andi")

    everyone = model.list_customers()
    assert [c["name"] for c in everyone] == ["Andi", "Budi", "Siti"]

    by_name = {c["name"]: c for c in everyone}
    assert by_name["Budi"]["group_name"] == "Tetangga"
    assert by_name["Siti"]["group_id"] == pegawai
    assert by_name["Andi"]["group_id"] is None
    assert by_name["Andi"]["group_name"] is None

    assert [c["name"] for c in model.list_customers(group_id=tetangga)] == [
        "Budi"
    ]
    assert [c["name"] for c in model.list_customers(group_id=NO_GROUP)] == [
        "Andi"
    ]

    # Filter kelompok bekerja bersama pencarian nama.
    assert model.list_customers(search="bu", group_id=pegawai) == []
    assert [
        c["name"] for c in model.list_customers(search="bu", group_id=tetangga)
    ] == ["Budi"]


def test_add_customer_rejects_unknown_group(model):
    ok, _, new_id = model.add_customer("Budi", group_id=9999)

    assert ok is False and new_id is None
    assert model.list_customers() == []


def test_update_customer_group_semantics(model):
    _, _, group_id = model.add_group("Tetangga")
    _, _, customer_id = model.add_customer("Budi", group_id=group_id)

    # Pemanggil lama (tanpa group_id) tidak boleh menghapus kelompok.
    assert model.update_customer(customer_id, "Budi S", "", "") == (
        True,
        "Data pelanggan berhasil diperbarui.",
    )
    customer = model.list_customers()[0]
    assert customer["name"] == "Budi S"
    assert customer["group_id"] == group_id

    # KEEP_GROUP eksplisit sama dengan default.
    model.update_customer(customer_id, "Budi S", group_id=KEEP_GROUP)
    assert model.list_customers()[0]["group_id"] == group_id

    # group_id=None mengosongkan kelompok.
    model.update_customer(customer_id, "Budi S", group_id=None)
    assert model.list_customers()[0]["group_id"] is None

    # Pindah kelompok, dan kelompok tak dikenal ditolak.
    model.update_customer(customer_id, "Budi S", group_id=group_id)
    assert model.list_customers()[0]["group_id"] == group_id
    assert model.update_customer(customer_id, "Budi S", group_id=9999)[0] is False
    assert model.list_customers()[0]["group_id"] == group_id


def test_delete_group_keeps_customers_and_balances(fresh_db, model):
    _, _, group_id = model.add_group("Tetangga")
    ids = [
        model.add_customer(name, group_id=group_id)[2]
        for name in ("Budi", "Siti", "Andi")
    ]

    for customer_id in ids:
        add_debt(fresh_db, customer_id, 10000)

    before = {
        c["name"]: (c["sisa"], c["total_debt"])
        for c in model.list_customers()
    }

    groups = model.list_groups()
    assert groups[0]["member_count"] == 3

    ok, _, affected = model.delete_group(group_id)

    assert ok is True
    assert affected == 3
    assert model.list_groups() == []

    after = model.list_customers()

    # Ketiga pelanggan masih ada, saldo sama, kini tanpa kelompok.
    assert len(after) == 3
    assert {c["name"]: (c["sisa"], c["total_debt"]) for c in after} == before
    assert all(c["group_id"] is None for c in after)
    assert len(model.list_customers(group_id=NO_GROUP)) == 3

    assert model.delete_group(group_id)[0] is False


def test_delete_group_also_works_when_foreign_keys_are_off(fresh_db, model):
    """Penghapusan tidak boleh bergantung pada PRAGMA foreign_keys."""
    _, _, group_id = model.add_group("Tetangga")
    model.add_customer("Budi", group_id=group_id)

    original_connect = fresh_db.connect

    def connect_without_foreign_keys():
        conn = original_connect()
        conn.execute("PRAGMA foreign_keys = OFF;")
        return conn

    fresh_db.connect = connect_without_foreign_keys

    assert model.delete_group(group_id)[0] is True
    assert model.list_customers()[0]["group_id"] is None


def test_member_count_ignores_inactive_customers(model):
    _, _, group_id = model.add_group("Tetangga")
    _, _, a = model.add_customer("Budi", group_id=group_id)
    model.add_customer("Siti", group_id=group_id)

    model.deactivate_customer(a)

    assert model.list_groups()[0]["member_count"] == 1


def test_get_detail_includes_group(model):
    _, _, group_id = model.add_group("Tetangga")
    _, _, with_group = model.add_customer("Budi", group_id=group_id)
    _, _, without_group = model.add_customer("Siti")

    detail = model.get_detail(with_group)
    assert detail["group_id"] == group_id
    assert detail["group_name"] == "Tetangga"

    detail = model.get_detail(without_group)
    assert detail["group_id"] is None
    assert detail["group_name"] is None