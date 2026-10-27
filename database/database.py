import os
import sys
import sqlite3
from contextlib import contextmanager
from datetime import datetime

# utils/security.py ada satu level di atas folder database/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import hash_password  # noqa: E402


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

CURRENT_SCHEMA_VERSION = 4
LEGACY_SCHEMA_VERSION = 1

# Definisi tabel kelompok pelanggan. Harus sama dengan database/schema.sql
# (dijaga oleh tests/test_customer_group.py).
CREATE_CUSTOMER_GROUPS_SQL = """
CREATE TABLE IF NOT EXISTS customer_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def get_app_base_dir() -> str:
    """
    Menentukan folder dasar aplikasi.

    - Saat frozen/PyInstaller: folder tempat EXE berada.
    - Saat development: root project.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_database_path() -> str:
    """Mengembalikan path database dan memastikan folder data tersedia."""
    base_dir = get_app_base_dir()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    return os.path.join(data_dir, "warung.db")


def get_schema_path() -> str:
    """
    Mengembalikan path schema.sql.

    Saat frozen, schema.sql diambil dari _MEIPASS karena
    file tersebut dibundel oleh PyInstaller.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(
            sys._MEIPASS,
            "database",
            "schema.sql",
        )

    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "schema.sql",
    )


class Database:
    """
    Wrapper SQLite dengan:

    - foreign key aktif
    - busy timeout
    - transaction helper
    - schema version
    - migration berantai v1 -> v2 -> v3 -> v4
    - satu backup sebelum rangkaian migration
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_database_path()

    def connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite baru."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")

        conn.row_factory = sqlite3.Row

        return conn

    @contextmanager
    def transaction(self):
        """
        Transaction aman:
        commit jika berhasil, rollback jika gagal.
        """
        conn = self.connect()

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def initialize(self) -> None:
        """
        Inisialisasi database.

        Kemungkinan:
        1. Database belum ada -> buat schema terbaru dari schema.sql.
        2. Database lama -> satu backup, lalu migration berantai
           sampai versi terbaru.
        3. Database sudah terbaru -> validasi saja.
        4. Versi tidak dikenal -> hentikan aplikasi.
        """

        if not os.path.exists(self.db_path):
            self._create_fresh_database()
            self._ensure_default_admin()
            self._ensure_image_directory()
            return

        version = self._detect_schema_version()

        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Versi database tidak didukung: {version}. "
                f"Versi aplikasi yang didukung: {CURRENT_SCHEMA_VERSION}."
            )

        if version < CURRENT_SCHEMA_VERSION:
            # Satu backup untuk seluruh rangkaian migration, diambil dari
            # kondisi database asli sebelum ada yang diubah.
            backup_path = self._create_migration_backup(version)

            if version == LEGACY_SCHEMA_VERSION:
                self._migrate_v1_to_v2(backup_path)
                version = 2

            if version == 2:
                self._migrate_v2_to_v3(backup_path)
                version = 3

            if version == 3:
                self._migrate_v3_to_v4(backup_path)
                version = 4

        if version != CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Versi database tidak didukung: {version}. "
                f"Versi aplikasi yang didukung: {CURRENT_SCHEMA_VERSION}."
            )

        self._validate_schema_v4()

        self._ensure_default_admin()
        self._ensure_image_directory()

    # =====================================================
    # SCHEMA DETECTION
    # =====================================================

    def _detect_schema_version(self) -> int:
        """
        Menentukan versi database.

        Database lama belum mempunyai schema_version,
        sehingga dianggap sebagai v1.
        """
        conn = self.connect()

        try:
            if not self._table_exists(conn, "schema_version"):
                if self._is_legacy_database(conn):
                    return LEGACY_SCHEMA_VERSION

                raise RuntimeError(
                    "Database tidak memiliki schema_version "
                    "dan bukan struktur database lama yang dikenali."
                )

            rows = conn.execute(
                """
                SELECT version
                FROM schema_version
                ORDER BY updated_at DESC
                LIMIT 1;
                """
            ).fetchone()

            if rows is None:
                raise RuntimeError(
                    "Tabel schema_version ditemukan tetapi kosong."
                )

            return int(rows["version"])

        finally:
            conn.close()

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
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

    def _is_legacy_database(self, conn: sqlite3.Connection) -> bool:
        """
        Memastikan database benar-benar merupakan database lama
        yang dikenali aplikasi.
        """
        required_tables = {
            "users",
            "customers",
            "products",
            "debt_transactions",
            "debt_details",
            "payments",
            "settings",
        }

        existing_tables = {
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table';
                """
            ).fetchall()
        }

        return required_tables.issubset(existing_tables)

    # =====================================================
    # FRESH DATABASE
    # =====================================================

    def _create_fresh_database(self) -> None:
        """Membuat database baru menggunakan schema.sql."""
        schema_path = get_schema_path()

        if not os.path.exists(schema_path):
            raise FileNotFoundError(
                f"File schema tidak ditemukan: {schema_path}"
            )

        with open(schema_path, "r", encoding="utf-8") as file:
            schema_sql = file.read()

        with self.transaction() as conn:
            conn.executescript(schema_sql)

    # =====================================================
    # MIGRATION
    # =====================================================

    def _set_schema_version(
        self,
        conn: sqlite3.Connection,
        version: int,
    ) -> None:
        conn.execute("DELETE FROM schema_version;")
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?);",
            (version,),
        )

    def _migrate_v1_to_v2(self, backup_path: str = "") -> None:
        """
        Migration database lama -> schema v2.

        Prinsip:
        - tidak menghapus data lama
        - ID produk tetap
        - harga lama -> purchase_price + selling_price
        - stok lama dimulai dari 0
        - supplier lama NULL
        - image_path lama NULL
        - transaksi hutang/payment lama tetap

        Backup dibuat oleh initialize() sebelum rangkaian migration.
        """

        try:
            with self.transaction() as conn:
                self._create_schema_version_table(conn)

                # -------------------------------------------------
                # Supplier
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS suppliers (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        name            TEXT NOT NULL UNIQUE,
                        notes           TEXT,
                        created_at      TEXT NOT NULL
                                        DEFAULT (datetime('now', 'localtime')),
                        updated_at      TEXT NOT NULL
                                        DEFAULT (datetime('now', 'localtime'))
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_suppliers_name
                    ON suppliers(name);
                    """
                )

                # -------------------------------------------------
                # Products - kolom baru
                # -------------------------------------------------
                product_columns = self._get_columns(
                    conn,
                    "products",
                )

                if "purchase_price" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN purchase_price
                        INTEGER NOT NULL DEFAULT 0;
                        """
                    )

                if "selling_price" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN selling_price
                        INTEGER NOT NULL DEFAULT 0;
                        """
                    )

                if "stock" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN stock
                        INTEGER NOT NULL DEFAULT 0;
                        """
                    )

                if "opening_stock" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN opening_stock
                        INTEGER NOT NULL DEFAULT 0;
                        """
                    )

                if "supplier_id" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN supplier_id
                        INTEGER;
                        """
                    )

                if "image_path" not in product_columns:
                    conn.execute(
                        """
                        ALTER TABLE products
                        ADD COLUMN image_path
                        TEXT;
                        """
                    )

                # -------------------------------------------------
                # Migrasi harga lama
                # -------------------------------------------------
                conn.execute(
                    """
                    UPDATE products
                    SET purchase_price = price,
                        selling_price = price
                    WHERE purchase_price = 0
                      AND selling_price = 0;
                    """
                )

                # -------------------------------------------------
                # Index baru products
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_products_supplier
                    ON products(supplier_id);
                    """
                )

                # -------------------------------------------------
                # Nomor transaksi hutang
                # -------------------------------------------------
                debt_columns = self._get_columns(
                    conn,
                    "debt_transactions",
                )

                if "transaction_number" not in debt_columns:
                    conn.execute(
                        """
                        ALTER TABLE debt_transactions
                        ADD COLUMN transaction_number TEXT;
                        """
                    )

                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_debt_tx_number_unique
                    ON debt_transactions(transaction_number)
                    WHERE transaction_number IS NOT NULL;
                    """
                )

                # -------------------------------------------------
                # Purchases
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS purchases (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_number  TEXT NOT NULL UNIQUE,
                        transaction_date    TEXT NOT NULL
                                            DEFAULT (datetime('now', 'localtime')),
                        supplier_id         INTEGER,
                        total_amount        INTEGER NOT NULL
                                            CHECK (total_amount >= 0),
                        notes               TEXT,
                        created_at          TEXT NOT NULL
                                            DEFAULT (datetime('now', 'localtime')),
                        FOREIGN KEY (supplier_id)
                            REFERENCES suppliers(id)
                            ON UPDATE CASCADE
                            ON DELETE SET NULL
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_purchases_number
                    ON purchases(transaction_number);
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_purchases_date
                    ON purchases(transaction_date);
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_purchases_supplier
                    ON purchases(supplier_id);
                    """
                )

                # -------------------------------------------------
                # Purchase details
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS purchase_details (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        purchase_id     INTEGER NOT NULL,
                        product_id      INTEGER NOT NULL,
                        product_name    TEXT NOT NULL,
                        quantity        INTEGER NOT NULL
                                        CHECK (quantity > 0),
                        price           INTEGER NOT NULL
                                        CHECK (price >= 0),
                        subtotal        INTEGER NOT NULL
                                        CHECK (subtotal >= 0),

                        FOREIGN KEY (purchase_id)
                            REFERENCES purchases(id)
                            ON UPDATE CASCADE
                            ON DELETE CASCADE,

                        FOREIGN KEY (product_id)
                            REFERENCES products(id)
                            ON UPDATE CASCADE
                            ON DELETE RESTRICT
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_purchase_details_purchase
                    ON purchase_details(purchase_id);
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_purchase_details_product
                    ON purchase_details(product_id);
                    """
                )

                # -------------------------------------------------
                # Sales
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sales (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_number  TEXT NOT NULL UNIQUE,
                        transaction_date    TEXT NOT NULL
                                            DEFAULT (datetime('now', 'localtime')),
                        total_amount        INTEGER NOT NULL
                                            CHECK (total_amount >= 0),
                        paid_amount         INTEGER NOT NULL
                                            CHECK (paid_amount >= 0),
                        change_amount       INTEGER NOT NULL
                                            CHECK (change_amount >= 0),
                        notes               TEXT,
                        created_at          TEXT NOT NULL
                                            DEFAULT (datetime('now', 'localtime')),

                        CHECK (paid_amount >= total_amount),
                        CHECK (
                            change_amount =
                            paid_amount - total_amount
                        )
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sales_number
                    ON sales(transaction_number);
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sales_date
                    ON sales(transaction_date);
                    """
                )

                # -------------------------------------------------
                # Sale details
                # -------------------------------------------------
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sale_details (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        sale_id         INTEGER NOT NULL,
                        product_id      INTEGER NOT NULL,
                        product_name    TEXT NOT NULL,
                        quantity        INTEGER NOT NULL
                                        CHECK (quantity > 0),
                        price           INTEGER NOT NULL
                                        CHECK (price >= 0),
                        subtotal        INTEGER NOT NULL
                                        CHECK (subtotal >= 0),

                        FOREIGN KEY (sale_id)
                            REFERENCES sales(id)
                            ON UPDATE CASCADE
                            ON DELETE CASCADE,

                        FOREIGN KEY (product_id)
                            REFERENCES products(id)
                            ON UPDATE CASCADE
                            ON DELETE RESTRICT
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sale_details_sale
                    ON sale_details(sale_id);
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sale_details_product
                    ON sale_details(product_id);
                    """
                )

                # -------------------------------------------------
                # Set version 2
                # -------------------------------------------------
                self._set_schema_version(conn, 2)

                # -------------------------------------------------
                # Validasi dalam transaction
                # -------------------------------------------------
                self._validate_schema_v2(conn)

        except Exception as exc:
            raise RuntimeError(
                "Migration database v1 -> v2 gagal. "
                f"Backup tersedia di: {backup_path}. "
                f"Detail: {exc}"
            ) from exc

    def _migrate_v2_to_v3(self, backup_path: str = "") -> None:
        """
        Migration database v2 -> schema v3.

        Menambahkan snapshot kondisi hutang saat pembayaran dibuat:
        - total_debt_at_payment
        - remaining_debt_at_payment

        Data pembayaran lama tetap dipertahankan.
        Snapshot pembayaran lama dibiarkan NULL karena kondisi
        historisnya tidak dapat diketahui secara akurat.
        """

        try:
            with self.transaction() as conn:
                payment_columns = self._get_columns(
                    conn,
                    "payments",
                )

                if "total_debt_at_payment" not in payment_columns:
                    conn.execute(
                        """
                        ALTER TABLE payments
                        ADD COLUMN total_debt_at_payment INTEGER;
                        """
                    )

                if "remaining_debt_at_payment" not in payment_columns:
                    conn.execute(
                        """
                        ALTER TABLE payments
                        ADD COLUMN remaining_debt_at_payment INTEGER;
                        """
                    )

                self._set_schema_version(conn, 3)

                self._validate_schema_v3(conn)

        except Exception as exc:
            raise RuntimeError(
                "Migration database v2 -> v3 gagal. "
                f"Backup tersedia di: {backup_path}. "
                f"Detail: {exc}"
            ) from exc

    def _migrate_v3_to_v4(self, backup_path: str = "") -> None:
        """
        Migration database v3 -> schema v4.

        Menambahkan kelompok pelanggan:
        - tabel customer_groups
        - kolom customers.group_id (boleh NULL)

        Pelanggan lama tidak berubah; group_id = NULL berarti
        "Tanpa kelompok". Bila kelompok dihapus, pelanggannya tetap
        ada dan group_id kembali NULL (ON DELETE SET NULL).
        """

        try:
            with self.transaction() as conn:
                conn.execute(CREATE_CUSTOMER_GROUPS_SQL)

                customer_columns = self._get_columns(
                    conn,
                    "customers",
                )

                if "group_id" not in customer_columns:
                    conn.execute(
                        """
                        ALTER TABLE customers
                        ADD COLUMN group_id INTEGER
                        REFERENCES customer_groups(id)
                        ON UPDATE CASCADE
                        ON DELETE SET NULL;
                        """
                    )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_customers_group
                    ON customers(group_id);
                    """
                )

                self._set_schema_version(conn, 4)

                self._validate_schema_v4(conn)

        except Exception as exc:
            raise RuntimeError(
                "Migration database v3 -> v4 gagal. "
                f"Backup tersedia di: {backup_path}. "
                f"Detail: {exc}"
            ) from exc

    # =====================================================
    # MIGRATION HELPERS
    # =====================================================

    def _create_schema_version_table(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """Membuat tabel version jika belum ada."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER NOT NULL,
                updated_at  TEXT NOT NULL
                            DEFAULT (datetime('now', 'localtime'))
            );
            """
        )

    @staticmethod
    def _get_columns(
        conn: sqlite3.Connection,
        table_name: str,
    ) -> set:
        """Mengambil nama kolom sebuah tabel."""
        rows = conn.execute(
            f"PRAGMA table_info({table_name});"
        ).fetchall()

        return {row["name"] for row in rows}

    # =====================================================
    # BACKUP
    # =====================================================

    def _create_migration_backup(self, from_version: int) -> str:
        """
        Membuat backup sebelum migration.

        Backup disimpan di folder `backup` di samping file database
        (untuk aplikasi: data/backup). Menggunakan SQLite backup API
        agar backup merupakan snapshot database yang valid.
        """
        backup_dir = os.path.join(
            os.path.dirname(os.path.abspath(self.db_path)),
            "backup",
        )

        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        backup_path = os.path.join(
            backup_dir,
            f"pre_migration_from_v{from_version}_{timestamp}.db",
        )

        source = sqlite3.connect(self.db_path)
        destination = sqlite3.connect(backup_path)

        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        return backup_path

    # =====================================================
    # VALIDATION
    # =====================================================

    def _validate_schema_v2(
        self,
        conn: sqlite3.Connection = None,
    ) -> None:
        """
        Memastikan tabel/kolom penting schema v2 tersedia.

        Jika conn tidak diberikan, validation membuka koneksi sendiri.
        """
        owns_connection = conn is None

        if owns_connection:
            conn = self.connect()

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

            existing_tables = {
                row["name"]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table';
                    """
                ).fetchall()
            }

            missing_tables = required_tables - existing_tables

            if missing_tables:
                raise RuntimeError(
                    "Tabel schema v2 tidak lengkap: "
                    + ", ".join(sorted(missing_tables))
                )

            required_product_columns = {
                "id",
                "barcode",
                "name",
                "price",
                "purchase_price",
                "selling_price",
                "stock",
                "opening_stock",
                "supplier_id",
                "image_path",
                "unit",
                "is_active",
                "created_at",
                "updated_at",
            }

            product_columns = self._get_columns(
                conn,
                "products",
            )

            missing_product_columns = (
                required_product_columns - product_columns
            )

            if missing_product_columns:
                raise RuntimeError(
                    "Kolom products tidak lengkap: "
                    + ", ".join(
                        sorted(missing_product_columns)
                    )
                )

            version = conn.execute(
                """
                SELECT version
                FROM schema_version
                ORDER BY updated_at DESC
                LIMIT 1;
                """
            ).fetchone()

            if version is None:
                raise RuntimeError(
                    "schema_version tidak memiliki data."
                )

            if int(version["version"]) not in (2, 3, 4):
                raise RuntimeError(
                    "Schema version tidak sesuai untuk validasi schema v2. "
                    f"Ditemukan {version['version']}."
                )

            # Pastikan foreign key aktif.
            foreign_keys = conn.execute(
                "PRAGMA foreign_keys;"
            ).fetchone()[0]

            if foreign_keys != 1:
                raise RuntimeError(
                    "SQLite foreign_keys tidak aktif."
                )

        finally:
            if owns_connection:
                conn.close()

    def _validate_schema_v3(
        self,
        conn: sqlite3.Connection = None,
    ) -> None:
        """
        Memastikan schema v3 lengkap.
        """

        owns_connection = conn is None

        if owns_connection:
            conn = self.connect()

        try:
            self._validate_schema_v2(conn)

            payment_columns = self._get_columns(
                conn,
                "payments",
            )

            required_payment_columns = {
                "id",
                "customer_id",
                "payment_date",
                "amount",
                "notes",
                "created_at",
                "total_debt_at_payment",
                "remaining_debt_at_payment",
            }

            missing_payment_columns = (
                required_payment_columns - payment_columns
            )

            if missing_payment_columns:
                raise RuntimeError(
                    "Kolom payments tidak lengkap: "
                    + ", ".join(
                        sorted(missing_payment_columns)
                    )
                )

        finally:
            if owns_connection:
                conn.close()

    def _validate_schema_v4(
        self,
        conn: sqlite3.Connection = None,
    ) -> None:
        """
        Memastikan schema v4 lengkap (termasuk kelompok pelanggan).
        """

        owns_connection = conn is None

        if owns_connection:
            conn = self.connect()

        try:
            self._validate_schema_v3(conn)

            if not self._table_exists(conn, "customer_groups"):
                raise RuntimeError(
                    "Tabel customer_groups tidak ditemukan."
                )

            group_columns = self._get_columns(
                conn,
                "customer_groups",
            )

            missing_group_columns = (
                {"id", "name", "created_at"} - group_columns
            )

            if missing_group_columns:
                raise RuntimeError(
                    "Kolom customer_groups tidak lengkap: "
                    + ", ".join(sorted(missing_group_columns))
                )

            if "group_id" not in self._get_columns(conn, "customers"):
                raise RuntimeError(
                    "Kolom customers.group_id tidak ditemukan."
                )

            version = conn.execute(
                """
                SELECT version
                FROM schema_version
                ORDER BY updated_at DESC
                LIMIT 1;
                """
            ).fetchone()

            if int(version["version"]) != 4:
                raise RuntimeError(
                    "Schema version tidak sesuai untuk validasi schema v4. "
                    f"Ditemukan {version['version']}."
                )

        finally:
            if owns_connection:
                conn.close()

    # =====================================================
    # ADMIN
    # =====================================================

    def _ensure_default_admin(self) -> None:
        """Membuat admin default jika belum ada user."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM users;
                """
            )

            total_users = cursor.fetchone()["total"]

            if total_users == 0:
                password_hash = hash_password(
                    DEFAULT_ADMIN_PASSWORD
                )

                conn.execute(
                    """
                    INSERT INTO users (
                        username,
                        password_hash
                    )
                    VALUES (?, ?);
                    """,
                    (
                        DEFAULT_ADMIN_USERNAME,
                        password_hash,
                    ),
                )

    # =====================================================
    # IMAGE DIRECTORY
    # =====================================================

    def _ensure_image_directory(self) -> None:
        """Memastikan folder gambar produk tersedia."""
        image_dir = os.path.join(
            get_app_base_dir(),
            "data",
            "images",
        )

        os.makedirs(image_dir, exist_ok=True)