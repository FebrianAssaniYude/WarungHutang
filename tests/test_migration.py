import os
import shutil
import sqlite3
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import (
    Database,
    LEGACY_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION,
)


SOURCE_DB = os.path.join(
    PROJECT_ROOT,
    "data",
    "warung.db",
)


def check(condition, message):
    if condition:
        print(f"[PASS] {message}")
        return True

    print(f"[FAIL] {message}")
    return False


def table_exists(conn, table_name):
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?;
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_table_count(conn, table_name):
    row = conn.execute(
        f"SELECT COUNT(*) AS total FROM {table_name};"
    ).fetchone()

    return row["total"]


def get_columns(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name});"
    ).fetchall()

    return {row["name"] for row in rows}


def get_financial_snapshot(conn):
    debt = conn.execute(
        """
        SELECT COALESCE(SUM(total_amount), 0) AS total
        FROM debt_transactions;
        """
    ).fetchone()["total"]

    payment = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM payments;
        """
    ).fetchone()["total"]

    return {
        "debt": debt,
        "payment": payment,
        "balance": debt - payment,
    }


def create_legacy_v1_database(db_path):
    """
    Membuat database sementara yang benar-benar menyerupai
    schema lama v1.
    """

    conn = sqlite3.connect(db_path)

    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                price INTEGER NOT NULL
                    CHECK (price >= 0),
                unit TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE debt_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                transaction_date TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                total_amount INTEGER NOT NULL
                    CHECK (total_amount >= 0),
                notes TEXT,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            );

            CREATE TABLE debt_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL
                    CHECK (quantity > 0),
                price INTEGER NOT NULL
                    CHECK (price >= 0),
                subtotal INTEGER NOT NULL
                    CHECK (subtotal >= 0),

                FOREIGN KEY (transaction_id)
                    REFERENCES debt_transactions(id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON UPDATE CASCADE
                    ON DELETE SET NULL
            );

            CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                amount INTEGER NOT NULL
                    CHECK (amount > 0),
                notes TEXT,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            );

            CREATE TABLE settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT
            );

            CREATE INDEX idx_customers_name
                ON customers(name);

            CREATE INDEX idx_products_name
                ON products(name);

            CREATE INDEX idx_products_barcode
                ON products(barcode);

            CREATE INDEX idx_debt_tx_customer
                ON debt_transactions(customer_id);

            CREATE INDEX idx_debt_tx_date
                ON debt_transactions(transaction_date);

            CREATE INDEX idx_debt_details_tx
                ON debt_details(transaction_id);

            CREATE INDEX idx_debt_details_product
                ON debt_details(product_id);

            CREATE INDEX idx_payments_customer
                ON payments(customer_id);

            CREATE INDEX idx_payments_date
                ON payments(payment_date);
            """
        )

        # -----------------------------------------------------
        # Data contoh
        # -----------------------------------------------------

        conn.execute(
            """
            INSERT INTO users (
                username,
                password_hash
            )
            VALUES (?, ?);
            """,
            ("admin", "dummy_hash_for_migration_test"),
        )

        conn.execute(
            """
            INSERT INTO customers (
                name,
                phone,
                notes
            )
            VALUES (?, ?, ?);
            """,
            ("Budi", "08123456789", "Customer test"),
        )

        conn.execute(
            """
            INSERT INTO customers (
                name,
                phone,
                notes
            )
            VALUES (?, ?, ?);
            """,
            ("Siti", None, None),
        )

        conn.execute(
            """
            INSERT INTO products (
                barcode,
                name,
                price,
                unit
            )
            VALUES (?, ?, ?, ?);
            """,
            ("8991234567890", "Indomie Goreng", 3500, "pcs"),
        )

        conn.execute(
            """
            INSERT INTO products (
                barcode,
                name,
                price,
                unit
            )
            VALUES (?, ?, ?, ?);
            """,
            (None, "Teh Botol", 4000, "botol"),
        )

        conn.execute(
            """
            INSERT INTO debt_transactions (
                customer_id,
                total_amount,
                notes
            )
            VALUES (?, ?, ?);
            """,
            (1, 7000, "Hutang test"),
        )

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
                1,
                1,
                "Indomie Goreng",
                2,
                3500,
                7000,
            ),
        )

        conn.execute(
            """
            INSERT INTO debt_transactions (
                customer_id,
                total_amount,
                notes
            )
            VALUES (?, ?, ?);
            """,
            (2, 5000, "Hutang kedua"),
        )

        # Manual item lama sengaja dibuat untuk memastikan
        # migration tidak menghapus histori lama.
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
                2,
                None,
                "Barang Manual Lama",
                1,
                5000,
                5000,
            ),
        )

        conn.execute(
            """
            INSERT INTO payments (
                customer_id,
                amount,
                notes
            )
            VALUES (?, ?, ?);
            """,
            (1, 4000, "Pembayaran test"),
        )

        conn.execute(
            """
            INSERT INTO settings (
                key,
                value
            )
            VALUES (?, ?);
            """,
            ("nama_warung", "Warung Test"),
        )

        conn.commit()

    finally:
        conn.close()


def test_v1_to_v2(temp_dir):
    print()
    print("=" * 70)
    print("TEST 1 — MIGRATION v1 -> v2")
    print("=" * 70)
    print()

    legacy_db = os.path.join(
        temp_dir,
        "legacy_v1.db",
    )

    create_legacy_v1_database(
        legacy_db
    )

    conn = sqlite3.connect(legacy_db)
    conn.row_factory = sqlite3.Row

    try:
        old_counts = {
            "users": get_table_count(conn, "users"),
            "customers": get_table_count(conn, "customers"),
            "products": get_table_count(conn, "products"),
            "debt_transactions": get_table_count(
                conn,
                "debt_transactions",
            ),
            "debt_details": get_table_count(
                conn,
                "debt_details",
            ),
            "payments": get_table_count(
                conn,
                "payments",
            ),
            "settings": get_table_count(
                conn,
                "settings",
            ),
        }

        old_products = conn.execute(
            """
            SELECT id, name, price
            FROM products
            ORDER BY id;
            """
        ).fetchall()

        old_financial = get_financial_snapshot(
            conn
        )

        old_debt_details = conn.execute(
            """
            SELECT
                transaction_id,
                product_id,
                product_name,
                quantity,
                price,
                subtotal
            FROM debt_details
            ORDER BY id;
            """
        ).fetchall()

        check(
            not table_exists(
                conn,
                "schema_version",
            ),
            "Database test benar-benar schema v1",
        )

        check(
            "purchase_price"
            not in get_columns(conn, "products"),
            "products belum memiliki purchase_price",
        )

    finally:
        conn.close()

    # ---------------------------------------------------------
    # Jalankan migration
    # ---------------------------------------------------------

    db = Database(
        db_path=legacy_db
    )

    try:
        db.initialize()

        check(
            db._detect_schema_version()
            == CURRENT_SCHEMA_VERSION,
            "Migration menghasilkan schema v2",
        )

    except Exception as exc:
        print()
        print("[FAIL] Migration v1 -> v2 gagal:")
        print(exc)
        return False

    # ---------------------------------------------------------
    # Validasi hasil migration
    # ---------------------------------------------------------

    conn = db.connect()

    try:
        required_tables = {
            "schema_version",
            "users",
            "customers",
            "suppliers",
            "products",
            "debt_transactions",
            "debt_details",
            "payments",
            "purchases",
            "purchase_details",
            "sales",
            "sale_details",
            "settings",
        }

        current_tables = {
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table';
                """
            ).fetchall()
        }

        for table in sorted(required_tables):
            check(
                table in current_tables,
                f"Tabel '{table}' tersedia",
            )

        # -----------------------------------------------------
        # Jumlah data lama
        # -----------------------------------------------------

        new_counts = {
            table: get_table_count(
                conn,
                table,
            )
            for table in old_counts
        }

        for table, old_count in old_counts.items():
            check(
                new_counts[table] == old_count,
                (
                    f"Jumlah {table} tetap "
                    f"({old_count})"
                ),
            )

        # -----------------------------------------------------
        # Product migration
        # -----------------------------------------------------

        new_products = conn.execute(
            """
            SELECT
                id,
                name,
                price,
                purchase_price,
                selling_price,
                stock,
                opening_stock,
                supplier_id,
                image_path
            FROM products
            ORDER BY id;
            """
        ).fetchall()

        product_ok = True

        for old, new in zip(
            old_products,
            new_products,
        ):
            if new["id"] != old["id"]:
                product_ok = False

            if new["name"] != old["name"]:
                product_ok = False

            if new["price"] != old["price"]:
                product_ok = False

            if new["purchase_price"] != old["price"]:
                product_ok = False

            if new["selling_price"] != old["price"]:
                product_ok = False

            if new["stock"] != 0:
                product_ok = False

            if new["opening_stock"] != 0:
                product_ok = False

            if new["supplier_id"] is not None:
                product_ok = False

            if new["image_path"] is not None:
                product_ok = False

        check(
            product_ok,
            (
                "Produk lama tetap dan "
                "price -> purchase_price + selling_price"
            ),
        )

        # -----------------------------------------------------
        # Financial data
        # -----------------------------------------------------

        new_financial = get_financial_snapshot(
            conn
        )

        check(
            new_financial["debt"]
            == old_financial["debt"],
            "Total hutang tetap",
        )

        check(
            new_financial["payment"]
            == old_financial["payment"],
            "Total pembayaran tetap",
        )

        check(
            new_financial["balance"]
            == old_financial["balance"],
            "Saldo hutang tetap",
        )

        # -----------------------------------------------------
        # Debt detail lama
        # -----------------------------------------------------

        new_debt_details = conn.execute(
            """
            SELECT
                transaction_id,
                product_id,
                product_name,
                quantity,
                price,
                subtotal
            FROM debt_details
            ORDER BY id;
            """
        ).fetchall()

        debt_details_ok = True

        for old, new in zip(
            old_debt_details,
            new_debt_details,
        ):
            for field in [
                "transaction_id",
                "product_id",
                "product_name",
                "quantity",
                "price",
                "subtotal",
            ]:
                if new[field] != old[field]:
                    debt_details_ok = False

        check(
            debt_details_ok,
            "Detail hutang lama tetap termasuk manual item lama",
        )

        # -----------------------------------------------------
        # Schema version
        # -----------------------------------------------------

        version = conn.execute(
            """
            SELECT version
            FROM schema_version
            LIMIT 1;
            """
        ).fetchone()["version"]

        check(
            version == CURRENT_SCHEMA_VERSION,
            f"schema_version = {CURRENT_SCHEMA_VERSION}",
        )

        # -----------------------------------------------------
        # Foreign keys
        # -----------------------------------------------------

        foreign_keys = conn.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()[0]

        check(
            foreign_keys == 1,
            "Foreign key SQLite aktif",
        )

        # -----------------------------------------------------
        # Integrity
        # -----------------------------------------------------

        integrity = conn.execute(
            "PRAGMA integrity_check;"
        ).fetchone()[0]

        check(
            integrity == "ok",
            "SQLite integrity_check = ok",
        )

        # -----------------------------------------------------
        # Idempotency
        # -----------------------------------------------------

        counts_before_second_init = {
            table: get_table_count(
                conn,
                table,
            )
            for table in old_counts
        }

    finally:
        conn.close()

    try:
        db.initialize()
    except Exception as exc:
        print(
            "[FAIL] initialize() kedua gagal:",
            exc,
        )
        return False

    conn = db.connect()

    try:
        counts_after_second_init = {
            table: get_table_count(
                conn,
                table,
            )
            for table in old_counts
        }

        check(
            counts_before_second_init
            == counts_after_second_init,
            "initialize() kedua tidak mengubah data",
        )

        version_after_second_init = conn.execute(
            """
            SELECT version
            FROM schema_version
            LIMIT 1;
            """
        ).fetchone()["version"]

        check(
            version_after_second_init
            == CURRENT_SCHEMA_VERSION,
            "Schema tetap v2 setelah initialize() kedua",
        )

    finally:
        conn.close()

    # ---------------------------------------------------------
    # Backup migration
    # ---------------------------------------------------------

    backup_dir = os.path.join(
        temp_dir,
        "backup",
    )

    backup_files = []

    if os.path.exists(backup_dir):
        backup_files = [
            filename
            for filename in os.listdir(backup_dir)
            if filename.startswith(
                "pre_migration_"
            )
            and filename.endswith(".db")
        ]

    check(
        len(backup_files) >= 1,
        "Backup migration berhasil dibuat",
    )

    return True


def test_existing_v2_database():
    print()
    print("=" * 70)
    print("TEST 2 — SALINAN DATABASE ASLI")
    print("=" * 70)
    print()

    if not os.path.exists(SOURCE_DB):
        print("[FAIL] Database asli tidak ditemukan:")
        print(SOURCE_DB)
        return False

    with tempfile.TemporaryDirectory(prefix="warung_real_copy_") as temp_dir:
        copy_path = os.path.join(temp_dir, "warung_copy.db")

        source = sqlite3.connect(SOURCE_DB)
        destination = sqlite3.connect(copy_path)

        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        conn = sqlite3.connect(copy_path)
        conn.row_factory = sqlite3.Row

        try:
            financial_before = get_financial_snapshot(conn)
        finally:
            conn.close()

        db = Database(db_path=copy_path)

        try:
            db.initialize()
        except Exception as exc:
            print("[FAIL] initialize() pada salinan database asli gagal:")
            print(exc)
            return False

        conn = db.connect()

        try:
            check(
                db._detect_schema_version() == CURRENT_SCHEMA_VERSION,
                f"Salinan database asli berada pada schema v{CURRENT_SCHEMA_VERSION}",
            )

            for table, column in (
                ("products", "purchase_price"),
                ("products", "selling_price"),
                ("products", "stock"),
                ("customers", "group_id"),
            ):
                check(
                    column in get_columns(conn, table),
                    f"Salinan memiliki {table}.{column}",
                )

            check(
                get_financial_snapshot(conn) == financial_before,
                "Saldo salinan database asli tidak berubah",
            )

            check(
                conn.execute("PRAGMA integrity_check;").fetchone()[0] == "ok",
                "Salinan database asli integrity_check = ok",
            )

        finally:
            conn.close()

    return True

def main():
    print("=" * 70)
    print("WARUNG HUTANG — MIGRATION TEST SUITE")
    print("=" * 70)

    with tempfile.TemporaryDirectory(
        prefix="warung_migration_test_"
    ) as temp_dir:

        migration_result = test_v1_to_v2(
            temp_dir
        )

    existing_result = test_existing_v2_database()

    print()
    print("=" * 70)
    print("HASIL AKHIR")
    print("=" * 70)

    if migration_result and existing_result:
        print("[PASS] SEMUA TEST MIGRATION BERHASIL.")
        print()
        print(
            "Database asli tidak digunakan sebagai "
            "target migration v1 -> v2."
        )
        print(
            "Database asli hanya diuji sebagai database v2."
        )
        return 0

    print("[FAIL] MASIH ADA TEST YANG GAGAL.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())