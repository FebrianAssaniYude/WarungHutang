import hashlib
import json
import os
import sqlite3
from unittest.mock import patch

import pytest

from database.database import Database
from database.integrity import (
    content_digest,
    inspect_database,
    sqlite_backup,
)
from models.customer import CustomerModel
from models.settings import SettingsModel
from utils.backup import (
    BackupError,
    RestoreError,
    backup_database,
    recover_interrupted_restore,
    restore_database,
    validate_backup_file,
)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_v4(path: str, customer_name: str = "Pelanggan A") -> str:
    db = Database(db_path=path)
    db.initialize()

    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO customers (name) VALUES (?);",
            (customer_name,),
        )
        conn.execute(
            """
            INSERT INTO products (
                name, price, purchase_price, selling_price, stock
            ) VALUES (?, ?, ?, ?, ?);
            """,
            ("Produk A", 1000, 800, 1200, 5),
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?);",
            ("nama_warung", "Warung Uji"),
        )

    return path


def make_v1(path: str) -> str:
    conn = sqlite3.connect(path)

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
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                unit TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
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
                total_amount INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
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
                FOREIGN KEY (transaction_id)
                    REFERENCES debt_transactions(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                amount INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT
            );

            INSERT INTO users (username, password_hash)
            VALUES ('admin', 'dummy_hash');

            INSERT INTO customers (name) VALUES ('Pelanggan Lama');

            INSERT INTO products (name, price, unit)
            VALUES ('Produk Lama', 1000, 'pcs');

            INSERT INTO debt_transactions (customer_id, total_amount)
            VALUES (1, 1000);

            INSERT INTO debt_details (
                transaction_id, product_id, product_name,
                quantity, price, subtotal
            ) VALUES (1, 1, 'Produk Lama', 1, 1000, 1000);

            INSERT INTO payments (customer_id, amount)
            VALUES (1, 200);

            INSERT INTO settings (key, value)
            VALUES ('nama_warung', 'Warung Lama');
            """
        )
    finally:
        conn.close()

    return path


def make_v2(path: str) -> str:
    make_v1(path)
    db = Database(db_path=path)
    db._migrate_v1_to_v2()
    return path


def make_v3(path: str) -> str:
    make_v2(path)
    db = Database(db_path=path)
    db._migrate_v2_to_v3()
    return path


def make_invalid_candidate(tmp_path, kind: str) -> str:
    path = str(tmp_path / f"invalid_{kind}.db")

    if kind == "non_sqlite":
        with open(path, "wb") as file:
            file.write(b"ini bukan database sqlite" * 100)
        return path

    if kind == "empty":
        with open(path, "wb") as file:
            file.write(b"")
        return path

    make_v4(path)

    if kind == "truncated":
        with open(path, "rb") as file:
            data = file.read()
        with open(path, "wb") as file:
            file.write(data[:120])
        return path

    conn = sqlite3.connect(path)
    try:
        if kind == "missing_table":
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute("DROP TABLE customer_groups;")
        elif kind == "zero_users":
            conn.execute("DELETE FROM users;")
        elif kind == "newer_version":
            conn.execute("UPDATE schema_version SET version = 5;")
        elif kind == "fk_violation":
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute(
                """
                INSERT INTO debt_transactions (customer_id, total_amount)
                VALUES (999999, 100);
                """
            )
        conn.commit()
    finally:
        conn.close()

    return path


# ----------------------------------------------------------------------
# Backup
# ----------------------------------------------------------------------


def test_backup_creates_valid_file_and_keeps_old_backups(tmp_path):
    source = make_v4(str(tmp_path / "source.db"))
    backup_dir = str(tmp_path / "backup")

    first = backup_database(source, backup_dir)
    second = backup_database(source, backup_dir)

    assert os.path.exists(first)
    assert os.path.exists(second)
    assert first != second

    info = validate_backup_file(first)
    assert info.schema_version == 4
    assert info.integrity_ok
    assert not info.foreign_key_violations
    assert info.counts["customers"] == 1

    assert content_digest(source) == content_digest(first)


def test_backup_rejects_corrupt_source(tmp_path):
    source = str(tmp_path / "corrupt.db")
    with open(source, "wb") as file:
        file.write(b"bukan sqlite" * 100)

    with pytest.raises(BackupError):
        backup_database(source, str(tmp_path / "backup"))

    backup_dir = tmp_path / "backup"
    assert not backup_dir.exists() or not any(backup_dir.iterdir())


def test_backup_does_not_overwrite_existing_backup(tmp_path):
    source = make_v4(str(tmp_path / "source.db"))
    backup_dir = str(tmp_path / "backup")

    first = backup_database(source, backup_dir)
    first_hash = sha256_file(first)

    second = backup_database(source, backup_dir)

    assert os.path.exists(first)
    assert sha256_file(first) == first_hash
    assert second != first


# ----------------------------------------------------------------------
# Restore valid
# ----------------------------------------------------------------------


def test_restore_v4_replaces_target_and_creates_verified_safety(tmp_path):
    target = make_v4(str(tmp_path / "target.db"), "Pelanggan Target")
    candidate = make_v4(str(tmp_path / "candidate.db"), "Pelanggan Baru")
    backup = backup_database(candidate, str(tmp_path / "backup"))

    safety = restore_database(backup, target)

    assert safety is not None
    assert os.path.exists(safety)

    safety_info = inspect_database(safety)
    assert safety_info.integrity_ok
    assert safety_info.counts["customers"] == 1

    restored = inspect_database(target)
    assert restored.schema_version == 4
    assert restored.integrity_ok
    assert not restored.foreign_key_violations

    with Database(db_path=target).transaction() as conn:
        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM customers ORDER BY id;"
            ).fetchall()
        ]

    assert names == ["Pelanggan Baru"]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_restore_old_version_migrates_only_staging(tmp_path, version):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    candidate = str(tmp_path / f"candidate_v{version}.db")

    if version == 1:
        make_v1(candidate)
    elif version == 2:
        make_v2(candidate)
    else:
        make_v3(candidate)

    candidate_hash_before = sha256_file(candidate)
    candidate_info_before = validate_backup_file(candidate)
    assert candidate_info_before.schema_version == version

    safety = restore_database(candidate, target)

    assert safety is not None
    assert os.path.exists(safety)
    assert sha256_file(candidate) == candidate_hash_before

    restored = inspect_database(target)
    assert restored.schema_version == 4
    assert restored.integrity_ok
    assert not restored.foreign_key_violations
    assert restored.counts["customers"] == 1
    assert restored.counts["products"] == 1
    assert restored.counts["debt_transactions"] == 1
    assert restored.counts["payments"] == 1


def test_restore_then_new_transaction_works(tmp_path):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    candidate = make_v4(str(tmp_path / "candidate.db"), "Hasil Restore")
    backup = backup_database(candidate, str(tmp_path / "backup"))

    restore_database(backup, target)

    db = Database(db_path=target)
    customer_model = CustomerModel(db)
    settings_model = SettingsModel(db)

    assert settings_model.get_nama_warung() == "Warung Uji"

    ok, message, customer_id = customer_model.add_customer(
        "Pelanggan Setelah Restore",
        "0812",
        "",
    )

    assert ok, message
    assert customer_id is not None
    assert customer_model.get_detail(customer_id)["name"] == (
        "Pelanggan Setelah Restore"
    )


# ----------------------------------------------------------------------
# Restore invalid / gagal
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        "non_sqlite",
        "empty",
        "truncated",
        "missing_table",
        "zero_users",
        "newer_version",
        "fk_violation",
    ],
)
def test_restore_rejects_invalid_candidate_without_touching_target(
    tmp_path,
    kind,
):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    candidate = make_invalid_candidate(tmp_path, kind)
    target_hash_before = sha256_file(target)

    with pytest.raises(RestoreError):
        restore_database(candidate, target)

    assert sha256_file(target) == target_hash_before
    assert inspect_database(target).integrity_ok


def test_restore_rejects_candidate_equal_to_target(tmp_path):
    target = make_v4(str(tmp_path / "target.db"))
    target_hash_before = sha256_file(target)

    with pytest.raises(RestoreError):
        restore_database(target, target)

    assert sha256_file(target) == target_hash_before


def test_restore_aborts_when_target_is_in_use(tmp_path):
    target = make_v4(str(tmp_path / "target.db"))
    candidate = make_v4(str(tmp_path / "candidate.db"), "Baru")
    target_hash_before = sha256_file(target)

    connection = sqlite3.connect(target)
    connection.execute("BEGIN EXCLUSIVE;")

    try:
        with pytest.raises(RestoreError):
            restore_database(candidate, target)
    finally:
        connection.rollback()
        connection.close()

    assert sha256_file(target) == target_hash_before


def test_restore_rolls_back_when_swap_fails(tmp_path):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    candidate = make_v4(str(tmp_path / "candidate.db"), "Baru")
    backup = backup_database(candidate, str(tmp_path / "backup"))
    target_hash_before = sha256_file(target)

    real_replace = os.replace

    def failing_replace(source, destination):
        if (
            os.path.abspath(source).endswith("staging.db")
            and os.path.abspath(destination) == os.path.abspath(target)
        ):
            raise OSError("simulasi kegagalan swap")
        return real_replace(source, destination)

    with patch("utils.backup.os.replace", side_effect=failing_replace):
        with pytest.raises(RestoreError) as error:
            restore_database(backup, target)

    assert not error.value.critical
    assert sha256_file(target) == target_hash_before
    assert not os.path.exists(
        os.path.join(os.path.dirname(target), ".restore_state.json")
    )


def test_restore_aborts_when_disk_is_full(tmp_path):
    target = make_v4(str(tmp_path / "target.db"))
    candidate = make_v4(str(tmp_path / "candidate.db"), "Baru")
    backup = backup_database(candidate, str(tmp_path / "backup"))
    target_hash_before = sha256_file(target)

    class Usage:
        free = 0

    with patch(
        "utils.backup.shutil.disk_usage",
        return_value=Usage(),
    ):
        with pytest.raises(RestoreError):
            restore_database(backup, target)

    assert sha256_file(target) == target_hash_before


def test_restore_aborts_when_staging_fails(tmp_path):
    target = make_v4(str(tmp_path / "target.db"))
    candidate = make_v4(str(tmp_path / "candidate.db"), "Baru")
    backup = backup_database(candidate, str(tmp_path / "backup"))
    target_hash_before = sha256_file(target)

    with patch(
        "utils.backup._stage_candidate",
        side_effect=OSError("simulasi staging gagal"),
    ):
        with pytest.raises(RestoreError):
            restore_database(backup, target)

    assert sha256_file(target) == target_hash_before


# ----------------------------------------------------------------------
# Pemulihan setelah restore terputus
# ----------------------------------------------------------------------


def test_recover_interrupted_restore_after_swap_out(tmp_path):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    target_digest = content_digest(target)

    work_dir = str(tmp_path / ".restore_work" / "crash1")
    os.makedirs(work_dir)
    previous = os.path.join(work_dir, "previous.db")
    os.replace(target, previous)

    safety = str(tmp_path / "safety.db")
    sqlite_backup(previous, safety)

    marker = os.path.join(str(tmp_path), ".restore_state.json")
    with open(marker, "w", encoding="utf-8") as file:
        json.dump(
            {
                "phase": "swapped_out",
                "target_path": target,
                "previous_path": previous,
                "safety_path": safety,
                "work_dir": work_dir,
                "target_existed": True,
                "target_digest": target_digest,
                "target_file_hash": None,
                "staging_digest": None,
            },
            file,
        )

    result = recover_interrupted_restore(target)

    assert result["action"] == "rolled_back_previous"
    assert content_digest(target) == target_digest
    assert not os.path.exists(marker)


def test_recover_interrupted_restore_keeps_valid_target(tmp_path):
    target = make_v4(str(tmp_path / "target.db"), "Target")
    candidate = make_v4(str(tmp_path / "candidate.db"), "Kandidat")
    candidate_digest = content_digest(candidate)

    os.replace(candidate, target)

    work_dir = str(tmp_path / ".restore_work" / "crash2")
    os.makedirs(work_dir)
    safety = str(tmp_path / "safety.db")
    sqlite_backup(target, safety)

    marker = os.path.join(str(tmp_path), ".restore_state.json")
    with open(marker, "w", encoding="utf-8") as file:
        json.dump(
            {
                "phase": "swapped_in",
                "target_path": target,
                "previous_path": os.path.join(work_dir, "previous.db"),
                "safety_path": safety,
                "work_dir": work_dir,
                "target_existed": True,
                "target_digest": None,
                "target_file_hash": None,
                "staging_digest": candidate_digest,
            },
            file,
        )

    result = recover_interrupted_restore(target)

    assert result["action"] == "kept_target"
    assert content_digest(target) == candidate_digest
    assert not os.path.exists(marker)
