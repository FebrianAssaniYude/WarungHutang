"""
Pemeriksaan database SQLite secara read-only.

Modul ini sengaja tidak mengubah database. Semua fungsi membuka file
dengan mode read-only dan hanya menjalankan PRAGMA/SELECT. Modul ini
dipakai oleh proses backup, restore, dan pemulihan setelah restore
terputus.

Catatan penting:
- ``PRAGMA integrity_check`` dan ``PRAGMA foreign_key_check`` dijalankan
  eksplisit. Membuka file dengan sqlite3 saja tidak membuktikan bahwa
  isinya sehat.
- Versi schema dibaca dari tabel ``schema_version``. Database lama yang
  belum punya tabel tersebut dikenali sebagai schema v1.
- Perbedaan bentuk DDL (mis. foreign key yang hilang pada database hasil
  migrasi lama) tidak dianggap fatal. Validasi memakai daftar tabel/kolom
  yang dibutuhkan dan ``foreign_key_check``.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


SQLITE_HEADER = b"SQLite format 3\x00"

# Versi schema yang dikenal aplikasi. Harus sama dengan
# database.database.CURRENT_SCHEMA_VERSION.
SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3, 4)
CURRENT_SCHEMA_VERSION = 4

# Tabel inti yang sudah ada sejak schema v1.
BASE_TABLES = frozenset(
    {
        "users",
        "customers",
        "products",
        "debt_transactions",
        "debt_details",
        "payments",
        "settings",
    }
)

# Tabel/kolom tambahan untuk v2.
V2_TABLES = frozenset(
    {
        "schema_version",
        "suppliers",
        "purchases",
        "purchase_details",
        "sales",
        "sale_details",
    }
)

# Kolom yang wajib ada pada tiap versi.
BASE_COLUMNS: dict[str, frozenset[str]] = {
    "users": frozenset(
        {"id", "username", "password_hash", "created_at"}
    ),
    "customers": frozenset(
        {
            "id",
            "name",
            "phone",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "products": frozenset(
        {
            "id",
            "barcode",
            "name",
            "price",
            "unit",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "debt_transactions": frozenset(
        {
            "id",
            "customer_id",
            "transaction_date",
            "total_amount",
            "notes",
            "created_at",
        }
    ),
    "debt_details": frozenset(
        {
            "id",
            "transaction_id",
            "product_id",
            "product_name",
            "quantity",
            "price",
            "subtotal",
        }
    ),
    "payments": frozenset(
        {
            "id",
            "customer_id",
            "payment_date",
            "amount",
            "notes",
            "created_at",
        }
    ),
    "settings": frozenset({"id", "key", "value"}),
}

V2_COLUMNS: dict[str, frozenset[str]] = {
    "schema_version": frozenset({"version", "updated_at"}),
    "suppliers": frozenset(
        {"id", "name", "notes", "created_at", "updated_at"}
    ),
    "products": frozenset(
        {
            "purchase_price",
            "selling_price",
            "stock",
            "opening_stock",
            "supplier_id",
            "image_path",
        }
    ),
    "debt_transactions": frozenset({"transaction_number"}),
    "purchases": frozenset(
        {
            "id",
            "transaction_number",
            "transaction_date",
            "supplier_id",
            "total_amount",
            "notes",
            "created_at",
        }
    ),
    "purchase_details": frozenset(
        {
            "id",
            "purchase_id",
            "product_id",
            "product_name",
            "quantity",
            "price",
            "subtotal",
        }
    ),
    "sales": frozenset(
        {
            "id",
            "transaction_number",
            "transaction_date",
            "total_amount",
            "paid_amount",
            "change_amount",
            "notes",
            "created_at",
        }
    ),
    "sale_details": frozenset(
        {
            "id",
            "sale_id",
            "product_id",
            "product_name",
            "quantity",
            "price",
            "subtotal",
        }
    ),
}

V3_COLUMNS: dict[str, frozenset[str]] = {
    "payments": frozenset(
        {
            "total_debt_at_payment",
            "remaining_debt_at_payment",
        }
    ),
}

V4_TABLES = frozenset({"customer_groups"})
V4_COLUMNS: dict[str, frozenset[str]] = {
    "customer_groups": frozenset({"id", "name", "created_at"}),
    "customers": frozenset({"group_id"}),
}

# Kolom angka yang ikut dibandingkan saat backup/migrasi.
SUM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("products", "price"),
    ("debt_transactions", "total_amount"),
    ("debt_details", "subtotal"),
    ("payments", "amount"),
    ("purchases", "total_amount"),
    ("purchase_details", "subtotal"),
    ("sales", "total_amount"),
    ("sales", "paid_amount"),
    ("sales", "change_amount"),
    ("sale_details", "subtotal"),
)

# Tabel yang isinya tidak boleh berubah karena migrasi.
BASE_DATA_TABLES = (
    "users",
    "customers",
    "products",
    "debt_transactions",
    "debt_details",
    "payments",
    "settings",
)

# Tabel yang boleh bertambah (tetapi harus kosong) saat migrasi v1.
OPTIONAL_DATA_TABLES = (
    "suppliers",
    "purchases",
    "purchase_details",
    "sales",
    "sale_details",
    "customer_groups",
)


class DatabaseValidationError(Exception):
    """Database tidak lolos validasi. Pesan siap ditampilkan ke pengguna."""

    def __init__(
        self,
        message: str,
        *,
        details: Iterable[str] | None = None,
    ):
        self.details = list(details or [])
        full_message = message
        if self.details:
            full_message += "\n\n" + "\n".join(
                f"- {item}" for item in self.details
            )
        super().__init__(full_message)


@dataclass
class DatabaseInspection:
    """Hasil pemeriksaan satu file database."""

    path: str
    exists: bool = False
    size: int = 0
    header_ok: bool = False
    integrity_ok: bool = False
    integrity_messages: list[str] = field(default_factory=list)
    foreign_key_violations: list[tuple] = field(default_factory=list)
    tables: set[str] = field(default_factory=set)
    columns: dict[str, set[str]] = field(default_factory=dict)
    schema_version: int | None = None
    is_legacy: bool = False
    version_rows: list[dict[str, Any]] = field(default_factory=list)
    users_count: int = 0
    settings_count: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    sums: dict[str, int] = field(default_factory=dict)
    duplicate_transaction_numbers: dict[str, list[str]] = field(
        default_factory=dict
    )
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def is_current(self) -> bool:
        return self.schema_version == CURRENT_SCHEMA_VERSION


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _read_header(path: str) -> bytes:
    try:
        with open(path, "rb") as file:
            return file.read(len(SQLITE_HEADER))
    except OSError:
        return b""


def _connect_readonly(path: str) -> sqlite3.Connection:
    """Membuka database tanpa izin tulis."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table';
            """
        ).fetchall()
    }


def _columns(
    conn: sqlite3.Connection,
    table: str,
) -> set[str]:
    try:
        rows = conn.execute(
            f"PRAGMA table_info({_quote_identifier(table)});"
        ).fetchall()
    except sqlite3.DatabaseError:
        return set()

    return {row["name"] for row in rows}


def _count(conn: sqlite3.Connection, table: str) -> int:
    try:
        row = conn.execute(
            f"SELECT COUNT(*) AS total "
            f"FROM {_quote_identifier(table)};"
        ).fetchone()
    except sqlite3.DatabaseError:
        return 0

    return int(row["total"]) if row else 0


def _sum(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> int:
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM({_quote_identifier(column)}), 0) AS total "
            f"FROM {_quote_identifier(table)};"
        ).fetchone()
    except sqlite3.DatabaseError:
        return 0

    return int(row["total"]) if row else 0


def _requirements(
    version: int,
) -> tuple[set[str], dict[str, set[str]]]:
    """Tabel dan kolom wajib untuk satu versi schema."""
    tables = set(BASE_TABLES)
    columns = {
        table: set(required)
        for table, required in BASE_COLUMNS.items()
    }

    if version >= 2:
        tables |= set(V2_TABLES)
        for table, required in V2_COLUMNS.items():
            columns.setdefault(table, set()).update(required)

    if version >= 3:
        for table, required in V3_COLUMNS.items():
            columns.setdefault(table, set()).update(required)

    if version >= 4:
        tables |= set(V4_TABLES)
        for table, required in V4_COLUMNS.items():
            columns.setdefault(table, set()).update(required)

    return tables, columns


def _detect_version(
    conn: sqlite3.Connection,
    tables: set[str],
    inspection: DatabaseInspection,
) -> None:
    if "schema_version" in tables:
        try:
            rows = conn.execute(
                """
                SELECT version, updated_at
                FROM schema_version
                ORDER BY updated_at DESC, rowid DESC;
                """
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            inspection.errors.append(
                f"Tabel schema_version tidak bisa dibaca: {exc}"
            )
            return

        if not rows:
            inspection.errors.append(
                "Tabel schema_version ditemukan tetapi kosong."
            )
            return

        inspection.version_rows = [dict(row) for row in rows]

        try:
            versions = {int(row["version"]) for row in rows}
        except (TypeError, ValueError):
            inspection.errors.append(
                "Nilai schema_version bukan angka yang valid."
            )
            return

        if len(versions) > 1:
            inspection.errors.append(
                "schema_version berisi beberapa versi berbeda: "
                + ", ".join(str(item) for item in sorted(versions))
                + "."
            )
            return

        inspection.schema_version = versions.pop()
        inspection.is_legacy = False
        return

    # Database lama belum punya schema_version.
    if BASE_TABLES.issubset(tables):
        inspection.schema_version = 1
        inspection.is_legacy = True
        return

    inspection.errors.append(
        "Database tidak memiliki schema_version dan bukan struktur "
        "database lama (v1) yang dikenali."
    )


def _check_required_schema(
    inspection: DatabaseInspection,
) -> None:
    if inspection.schema_version is None:
        return

    required_tables, required_columns = _requirements(
        inspection.schema_version
    )

    missing_tables = required_tables - inspection.tables
    if missing_tables:
        inspection.errors.append(
            "Tabel wajib tidak ditemukan: "
            + ", ".join(sorted(missing_tables))
            + "."
        )

    for table, required in sorted(required_columns.items()):
        if table not in inspection.tables:
            continue

        available = inspection.columns.get(table, set())
        missing = required - available
        if missing:
            inspection.errors.append(
                f"Kolom wajib pada tabel {table} tidak ditemukan: "
                + ", ".join(sorted(missing))
                + "."
            )


def _check_transaction_numbers(
    conn: sqlite3.Connection,
    inspection: DatabaseInspection,
) -> None:
    for table in ("debt_transactions", "purchases", "sales"):
        columns = inspection.columns.get(table, set())
        if "transaction_number" not in columns:
            continue

        try:
            rows = conn.execute(
                f"""
                SELECT transaction_number, COUNT(*) AS total
                FROM {_quote_identifier(table)}
                WHERE transaction_number IS NOT NULL
                GROUP BY transaction_number
                HAVING COUNT(*) > 1;
                """
            ).fetchall()
        except sqlite3.DatabaseError:
            continue

        if rows:
            inspection.duplicate_transaction_numbers[table] = [
                str(row["transaction_number"]) for row in rows
            ]


def inspect_database(
    path: str,
    *,
    check_integrity: bool = True,
    check_foreign_keys: bool = True,
    max_version: int | None = None,
) -> DatabaseInspection:
    """
    Memeriksa file database tanpa mengubahnya.

    Fungsi ini tidak melempar exception untuk file yang rusak; hasilnya
    berisi daftar ``errors``. Gunakan ``validate_database`` jika ingin
    exception dengan pesan siap tampil.
    """
    inspection = DatabaseInspection(path=os.path.abspath(path))

    if not os.path.exists(path):
        inspection.errors.append("File database tidak ditemukan.")
        return inspection

    if not os.path.isfile(path):
        inspection.errors.append("Path database bukan sebuah file.")
        return inspection

    inspection.exists = True

    try:
        inspection.size = os.path.getsize(path)
    except OSError as exc:
        inspection.errors.append(f"File tidak bisa dibaca: {exc}")
        return inspection

    if inspection.size <= 0:
        inspection.errors.append("File database kosong (0 byte).")
        return inspection

    header = _read_header(path)
    inspection.header_ok = header == SQLITE_HEADER
    if not inspection.header_ok:
        inspection.errors.append(
            "File bukan database SQLite yang valid (header tidak cocok)."
        )
        return inspection

    try:
        conn = _connect_readonly(path)
    except sqlite3.DatabaseError as exc:
        inspection.errors.append(f"Database tidak bisa dibuka: {exc}")
        return inspection

    try:
        try:
            inspection.tables = _table_names(conn)
        except sqlite3.DatabaseError as exc:
            inspection.errors.append(
                f"Daftar tabel database tidak bisa dibaca: {exc}"
            )
            return inspection

        inspection.columns = {
            table: _columns(conn, table)
            for table in inspection.tables
        }

        if check_integrity:
            try:
                rows = conn.execute(
                    "PRAGMA integrity_check;"
                ).fetchall()
                inspection.integrity_messages = [
                    str(row[0]) for row in rows
                ]
                inspection.integrity_ok = (
                    inspection.integrity_messages == ["ok"]
                )
            except sqlite3.DatabaseError as exc:
                inspection.integrity_messages = [str(exc)]
                inspection.integrity_ok = False

            if not inspection.integrity_ok:
                messages = inspection.integrity_messages[:5]
                inspection.errors.append(
                    "PRAGMA integrity_check gagal: "
                    + "; ".join(messages)
                )

        if check_foreign_keys:
            try:
                violations = conn.execute(
                    "PRAGMA foreign_key_check;"
                ).fetchall()
                inspection.foreign_key_violations = [
                    tuple(row) for row in violations
                ]
            except sqlite3.DatabaseError as exc:
                inspection.errors.append(
                    f"PRAGMA foreign_key_check gagal: {exc}"
                )

            if inspection.foreign_key_violations:
                inspection.errors.append(
                    "PRAGMA foreign_key_check menemukan "
                    f"{len(inspection.foreign_key_violations)} pelanggaran."
                )

        _detect_version(conn, inspection.tables, inspection)

        if inspection.schema_version is not None:
            if inspection.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
                inspection.errors.append(
                    "Versi schema tidak dikenal: "
                    f"{inspection.schema_version}."
                )
            elif (
                max_version is not None
                and inspection.schema_version > max_version
            ):
                inspection.errors.append(
                    "Database berasal dari versi aplikasi yang lebih baru "
                    f"(schema v{inspection.schema_version}, aplikasi ini "
                    f"mendukung sampai v{max_version})."
                )

            _check_required_schema(inspection)

        inspection.users_count = (
            _count(conn, "users") if "users" in inspection.tables else 0
        )
        inspection.settings_count = (
            _count(conn, "settings")
            if "settings" in inspection.tables
            else 0
        )

        excluded_tables = {
            "sqlite_sequence",
        }
        for table in sorted(inspection.tables - excluded_tables):
            if table.startswith("sqlite_stat"):
                continue
            inspection.counts[table] = _count(conn, table)

        for table, column in SUM_COLUMNS:
            if table not in inspection.tables:
                continue
            if column not in inspection.columns.get(table, set()):
                continue
            inspection.sums[f"{table}.{column}"] = _sum(
                conn,
                table,
                column,
            )

        _check_transaction_numbers(conn, inspection)

        if inspection.users_count == 0:
            inspection.warnings.append(
                "Database tidak memiliki akun pengguna (users kosong)."
            )

        if inspection.settings_count == 0:
            inspection.warnings.append(
                "Tabel settings kosong; nama warung akan memakai nilai "
                "default."
            )

        if "payments" in inspection.tables:
            columns = inspection.columns.get("payments", set())
            if "total_debt_at_payment" in columns:
                try:
                    row = conn.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM payments
                        WHERE total_debt_at_payment IS NULL;
                        """
                    ).fetchone()
                    if row and row["total"]:
                        inspection.warnings.append(
                            f"{row['total']} pembayaran lama belum memiliki "
                            "snapshot kondisi hutang (NULL)."
                        )
                except sqlite3.DatabaseError:
                    pass

        if "debt_transactions" in inspection.tables:
            columns = inspection.columns.get(
                "debt_transactions",
                set(),
            )
            if "transaction_number" in columns:
                try:
                    row = conn.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM debt_transactions
                        WHERE transaction_number IS NULL;
                        """
                    ).fetchone()
                    if row and row["total"]:
                        inspection.warnings.append(
                            f"{row['total']} transaksi hutang lama belum "
                            "memiliki nomor transaksi (NULL)."
                        )
                except sqlite3.DatabaseError:
                    pass

        if "products" in inspection.tables:
            columns = inspection.columns.get("products", set())
            if "image_path" in columns:
                try:
                    row = conn.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM products
                        WHERE image_path IS NOT NULL
                          AND TRIM(image_path) <> '';
                        """
                    ).fetchone()
                    if row and row["total"]:
                        inspection.warnings.append(
                            f"{row['total']} produk masih menyimpan path "
                            "gambar lama. Gambar tidak termasuk dalam "
                            "backup/restore."
                        )
                except sqlite3.DatabaseError:
                    pass

    finally:
        conn.close()

    return inspection


def validate_database(
    path: str,
    *,
    expected_version: int | None = None,
    max_version: int = CURRENT_SCHEMA_VERSION,
    require_users: bool = True,
    allow_legacy: bool = True,
) -> DatabaseInspection:
    """
    Memeriksa database dan melempar DatabaseValidationError jika tidak
    memenuhi syarat.
    """
    inspection = inspect_database(path, max_version=max_version)

    if inspection.errors:
        raise DatabaseValidationError(
            "File database tidak lolos validasi.",
            details=inspection.errors,
        )

    if inspection.schema_version is None:
        raise DatabaseValidationError(
            "Versi schema database tidak dapat ditentukan."
        )

    if not allow_legacy and inspection.is_legacy:
        raise DatabaseValidationError(
            "Database legacy (v1) tidak diizinkan untuk operasi ini."
        )

    if (
        expected_version is not None
        and inspection.schema_version != expected_version
    ):
        raise DatabaseValidationError(
            "Versi schema tidak sesuai. "
            f"Ditemukan v{inspection.schema_version}, "
            f"dibutuhkan v{expected_version}."
        )

    if require_users and inspection.users_count < 1:
        raise DatabaseValidationError(
            "Database tidak memiliki akun pengguna. "
            "Restore dibatalkan agar aplikasi tidak membuat akun default "
            "secara diam-diam.",
            details=inspection.warnings,
        )

    if inspection.duplicate_transaction_numbers:
        details = [
            f"{table}: {', '.join(numbers[:5])}"
            for table, numbers in inspection.duplicate_transaction_numbers.items()
        ]
        raise DatabaseValidationError(
            "Ditemukan nomor transaksi ganda. "
            "Perbaiki backup terlebih dahulu.",
            details=details,
        )

    return inspection


def content_digest(
    path: str,
    *,
    exclude_tables: Iterable[str] | None = None,
) -> str:
    """
    Menghitung SHA-256 isi seluruh tabel (urutan baris berdasarkan rowid).

    Dipakai untuk memastikan backup benar-benar berisi data yang sama
    dengan sumber. Tabel internal SQLite tidak ikut dihitung.
    """
    excluded = {
        "sqlite_sequence",
    }
    if exclude_tables:
        excluded |= set(exclude_tables)

    conn = _connect_readonly(path)
    digest = hashlib.sha256()

    try:
        tables = sorted(_table_names(conn) - excluded)
        for table in tables:
            if table.startswith("sqlite_stat"):
                continue

            digest.update(b"\x00T")
            digest.update(table.encode("utf-8"))

            try:
                rows = conn.execute(
                    f"SELECT * FROM {_quote_identifier(table)} "
                    "ORDER BY rowid;"
                )
            except sqlite3.DatabaseError:
                rows = conn.execute(
                    f"SELECT * FROM {_quote_identifier(table)};"
                )

            for row in rows:
                digest.update(b"\x00R")
                digest.update(
                    repr(tuple(row)).encode(
                        "utf-8",
                        errors="backslashreplace",
                    )
                )
    finally:
        conn.close()

    return digest.hexdigest()


def table_digest(path: str, table: str) -> str | None:
    """SHA-256 isi satu tabel, atau None jika tabel tidak ada."""
    conn = _connect_readonly(path)

    try:
        if table not in _table_names(conn):
            return None

        digest = hashlib.sha256()
        try:
            rows = conn.execute(
                f"SELECT * FROM {_quote_identifier(table)} ORDER BY rowid;"
            )
        except sqlite3.DatabaseError:
            rows = conn.execute(
                f"SELECT * FROM {_quote_identifier(table)};"
            )

        for row in rows:
            digest.update(b"\x00R")
            digest.update(
                repr(tuple(row)).encode(
                    "utf-8",
                    errors="backslashreplace",
                )
            )

        return digest.hexdigest()
    finally:
        conn.close()


def business_fingerprint(path: str) -> dict[str, Any]:
    """
    Ringkasan data bisnis untuk membandingkan kondisi sebelum/sesudah
    migrasi. Tidak memakai digest seluruh tabel karena migrasi v1 -> v2
    memang mengubah kolom harga produk.
    """
    inspection = inspect_database(path)

    return {
        "counts": dict(inspection.counts),
        "sums": dict(inspection.sums),
        "users_digest": table_digest(path, "users"),
        "settings_digest": table_digest(path, "settings"),
    }


def compare_business_fingerprints(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    """Mengembalikan daftar perbedaan yang tidak boleh terjadi."""
    differences: list[str] = []

    before_counts = before.get("counts", {})
    after_counts = after.get("counts", {})

    for table in BASE_DATA_TABLES:
        old = before_counts.get(table)
        new = after_counts.get(table)
        if old is not None and old != new:
            differences.append(
                f"Jumlah baris {table} berubah: {old} -> {new}."
            )

    for table, old in before_counts.items():
        if table in BASE_DATA_TABLES:
            continue
        new = after_counts.get(table)
        if new is not None and old != new:
            differences.append(
                f"Jumlah baris {table} berubah: {old} -> {new}."
            )

    for table in OPTIONAL_DATA_TABLES:
        if table in before_counts:
            continue
        new = after_counts.get(table)
        if new:
            differences.append(
                f"Tabel baru {table} seharusnya kosong, ditemukan {new} baris."
            )

    before_sums = before.get("sums", {})
    after_sums = after.get("sums", {})

    for key, old in before_sums.items():
        new = after_sums.get(key)
        if new is not None and old != new:
            differences.append(
                f"Nilai total {key} berubah: {old} -> {new}."
            )

    for key in ("users_digest", "settings_digest"):
        old = before.get(key)
        new = after.get(key)
        if old is not None and new is not None and old != new:
            differences.append(
                f"Isi {key.replace('_digest', '')} berubah."
            )

    return differences


def sqlite_backup(
    source_path: str,
    destination_path: str,
    *,
    readonly: bool = False,
) -> None:
    """
    Menyalin database memakai SQLite Backup API.

    ``readonly=True`` dipakai untuk kandidat backup yang tidak boleh
    diubah. Untuk database produksi, gunakan mode biasa agar SQLite bisa
    melakukan pemulihan journal bila perlu.
    """
    destination_dir = os.path.dirname(os.path.abspath(destination_path))
    os.makedirs(destination_dir, exist_ok=True)

    if os.path.exists(destination_path):
        os.remove(destination_path)

    source_target: Any
    if readonly:
        source_target = (
            Path(source_path).resolve().as_uri() + "?mode=ro"
        )
    else:
        source_target = source_path

    source = sqlite3.connect(
        source_target,
        uri=readonly,
    )
    destination = sqlite3.connect(destination_path)

    try:
        source.execute("PRAGMA busy_timeout = 5000;")
        destination.execute("PRAGMA busy_timeout = 5000;")
        source.backup(destination)
    finally:
        destination.close()
        source.close()
