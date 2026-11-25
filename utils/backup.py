"""
Backup & restore database SQLite yang aman.

Prinsip utama modul ini:

- Backup memakai SQLite Backup API, bukan penyalinan file biasa.
- Backup baru dipublikasikan setelah lolos integritas, foreign key,
  schema, dan perbandingan isi dengan sumber.
- Restore memakai staging: kandidat divalidasi dan dimigrasi di salinan
  kerja, bukan langsung di database produksi.
- Safety backup dibuat dan diverifikasi sebelum database produksi
  diganti.
- Jika penggantian atau verifikasi gagal, database produksi dikembalikan
  dari salinan sebelumnya/safety backup.
- Safety backup tidak dihapus otomatis.
- Marker ``.restore_state.json`` dipakai untuk memulihkan kondisi jika
  aplikasi terhenti di tengah proses restore.

Gambar produk tidak termasuk dalam backup/restore. Data gambar lama
tidak dihapus oleh modul ini.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from database.database import CURRENT_SCHEMA_VERSION, Database
from database.integrity import (
    DatabaseValidationError,
    business_fingerprint,
    compare_business_fingerprints,
    content_digest,
    inspect_database,
    sqlite_backup,
    validate_database,
)


RESTORE_MARKER_NAME = ".restore_state.json"
RESTORE_WORK_DIR_NAME = ".restore_work"
BACKUP_DIR_NAME = "backup"
BACKUP_PREFIX = "backup_"
SAFETY_PREFIX = "before_restore_"

ProgressCallback = Callable[[str, str], None]


class BackupError(Exception):
    """Backup gagal. Pesan siap ditampilkan ke pengguna."""

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


class RestoreError(Exception):
    """Restore gagal atau dibatalkan."""

    def __init__(
        self,
        message: str,
        *,
        safety_path: str | None = None,
        details: Iterable[str] | None = None,
        phase: str | None = None,
        critical: bool = False,
    ):
        self.safety_path = safety_path
        self.details = list(details or [])
        self.phase = phase
        self.critical = critical

        full_message = message
        if self.details:
            full_message += "\n\n" + "\n".join(
                f"- {item}" for item in self.details
            )
        if safety_path:
            full_message += (
                "\n\nSafety backup database sebelumnya:\n"
                f"{safety_path}"
            )
        super().__init__(full_message)


class RestoreRecoveryError(Exception):
    """Pemulihan otomatis setelah restore terputus tidak bisa dilakukan."""

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


# ----------------------------------------------------------------------
# Helper umum
# ----------------------------------------------------------------------


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path

    base, extension = os.path.splitext(path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{extension}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _backup_dir(target_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(target_path)),
        BACKUP_DIR_NAME,
    )


def _marker_path(target_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(target_path)),
        RESTORE_MARKER_NAME,
    )


def _work_root(target_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(target_path)),
        RESTORE_WORK_DIR_NAME,
    )


def _sidecar_paths(path: str) -> tuple[str, ...]:
    return (
        path + "-journal",
        path + "-wal",
        path + "-shm",
    )


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: str) -> None:
    try:
        with open(path, "rb") as file:
            os.fsync(file.fileno())
    except OSError:
        # fsync bukan jaminan yang bisa dipaksakan di semua filesystem.
        pass


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temp_path = f"{path}.tmp.{uuid.uuid4().hex}"

    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _write_marker(path: str, data: dict[str, Any]) -> None:
    payload = dict(data)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(path, payload)


def _read_marker(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _clear_marker(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _cleanup_work_dir(work_dir: str | None) -> None:
    if not work_dir:
        return
    try:
        if os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
    except OSError:
        pass


def _check_disk_space(directory: str, required_bytes: int) -> None:
    try:
        free = shutil.disk_usage(directory).free
    except OSError as exc:
        raise RestoreError(
            "Ruang disk tidak bisa diperiksa.",
            details=[str(exc)],
        ) from exc

    if free < required_bytes:
        raise RestoreError(
            "Ruang disk tidak mencukupi untuk restore.",
            details=[
                f"Butuh minimal {required_bytes // (1024 * 1024)} MB, "
                f"tersedia {free // (1024 * 1024)} MB."
            ],
        )


def _ensure_no_sidecars(target_path: str) -> None:
    existing = [
        path
        for path in _sidecar_paths(target_path)
        if os.path.exists(path)
    ]
    if existing:
        raise RestoreError(
            "Database target masih memiliki file jurnal/WAL. "
            "Tutup aplikasi, jalankan ulang sekali agar SQLite "
            "menyelesaikan pemulihan, lalu coba restore lagi.",
            details=existing,
        )


def _check_target_readable(target_path: str) -> None:
    """Memastikan target tidak sedang dikunci proses lain."""
    if not os.path.exists(target_path):
        return

    uri = Path(target_path).resolve().as_uri() + "?mode=ro"
    conn = None

    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("PRAGMA busy_timeout = 1000;")
        conn.execute("SELECT COUNT(*) FROM sqlite_master;").fetchone()
    except sqlite3.OperationalError as exc:
        raise RestoreError(
            "Database sedang digunakan oleh proses lain. "
            "Tutup aplikasi lain lalu coba lagi.",
            details=[str(exc)],
        ) from exc
    except sqlite3.DatabaseError:
        # Database rusak akan dilaporkan oleh inspect_database.
        pass
    finally:
        if conn is not None:
            conn.close()


def _check_exclusive_access(target_path: str) -> None:
    """Memastikan tidak ada koneksi lain yang memegang database."""
    if not os.path.exists(target_path):
        return

    conn = sqlite3.connect(target_path)

    try:
        conn.execute("PRAGMA busy_timeout = 1000;")
        conn.execute("BEGIN EXCLUSIVE;")
        conn.rollback()
    except sqlite3.OperationalError as exc:
        raise RestoreError(
            "Database sedang digunakan oleh proses lain. "
            "Tutup aplikasi lain lalu coba lagi.",
            details=[str(exc)],
        ) from exc
    finally:
        conn.close()


def _stage_candidate(
    candidate_path: str,
    staging_path: str,
    work_dir: str,
) -> None:
    """
    Menyalin kandidat ke staging memakai Backup API.

    Jika kandidat memiliki sidecar WAL/journal, sidecar tersebut ikut
    disalin ke salinan sementara agar SQLite bisa membaca kondisi
    terakhir tanpa menyentuh file kandidat asli.
    """
    sidecars = [
        suffix
        for suffix in ("-wal", "-journal", "-shm")
        if os.path.exists(candidate_path + suffix)
    ]

    if not sidecars:
        sqlite_backup(candidate_path, staging_path, readonly=True)
        return

    copy_path = os.path.join(work_dir, "candidate_copy.db")
    copied_sidecars: list[str] = []

    try:
        shutil.copy2(candidate_path, copy_path)
        for suffix in sidecars:
            destination = copy_path + suffix
            shutil.copy2(candidate_path + suffix, destination)
            copied_sidecars.append(destination)

        sqlite_backup(copy_path, staging_path)
    finally:
        for path in [copy_path] + copied_sidecars:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


# ----------------------------------------------------------------------
# Backup
# ----------------------------------------------------------------------


def backup_database(
    source_db_path: str,
    backup_dir: str | None = None,
) -> str:
    """
    Membuat backup database yang sudah diverifikasi.

    Returns:
        Path lengkap file backup yang baru dibuat.

    Raises:
        BackupError: jika backup atau validasinya gagal.
    """
    source_path = os.path.abspath(source_db_path)

    if not os.path.isfile(source_path):
        raise BackupError("File database tidak ditemukan.")

    source_info = inspect_database(
        source_path,
        max_version=CURRENT_SCHEMA_VERSION,
    )

    if source_info.errors:
        raise BackupError(
            "Database sumber tidak valid sehingga backup dibatalkan.",
            details=source_info.errors,
        )

    destination_dir = os.path.abspath(
        backup_dir or _backup_dir(source_path)
    )
    os.makedirs(destination_dir, exist_ok=True)

    final_path = _unique_path(
        os.path.join(
            destination_dir,
            f"{BACKUP_PREFIX}{_stamp()}.db",
        )
    )
    temp_path = os.path.join(
        destination_dir,
        f".tmp_backup_{uuid.uuid4().hex}.db",
    )

    last_error = ""

    try:
        for _attempt in range(2):
            try:
                sqlite_backup(source_path, temp_path)

                validate_database(
                    temp_path,
                    max_version=CURRENT_SCHEMA_VERSION,
                    require_users=False,
                )

                source_digest = content_digest(source_path)
                backup_digest = content_digest(temp_path)

                if source_digest == backup_digest:
                    _fsync_file(temp_path)
                    os.replace(temp_path, final_path)
                    return final_path

                last_error = (
                    "Isi backup berbeda dengan database sumber. "
                    "Kemungkinan ada perubahan data saat backup berjalan."
                )
            except (
                DatabaseValidationError,
                sqlite3.DatabaseError,
                OSError,
            ) as exc:
                last_error = str(exc)
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

        raise BackupError(
            "Backup gagal diverifikasi. File backup tidak dibuat.",
            details=[last_error] if last_error else None,
        )
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(
            "Terjadi kesalahan saat membuat backup.",
            details=[str(exc)],
        ) from exc


def validate_backup_file(
    backup_path: str,
    *,
    require_users: bool = True,
):
    """Memvalidasi file backup sebelum dipakai untuk restore."""
    path = os.path.abspath(backup_path)

    if not os.path.isfile(path):
        raise DatabaseValidationError("File backup tidak ditemukan.")

    return validate_database(
        path,
        max_version=CURRENT_SCHEMA_VERSION,
        require_users=require_users,
    )


# ----------------------------------------------------------------------
# Restore
# ----------------------------------------------------------------------


def _verify_restored_target(
    target_path: str,
    *,
    expected_digest: str | None,
    expected_file_hash: str | None,
    target_info,
) -> bool:
    try:
        if target_info is not None and target_info.valid:
            inspection = inspect_database(
                target_path,
                max_version=CURRENT_SCHEMA_VERSION,
            )
            if inspection.errors:
                return False
            if expected_digest is not None:
                return content_digest(target_path) == expected_digest
            return True

        if expected_file_hash is not None:
            return _sha256_file(target_path) == expected_file_hash
    except Exception:
        return False

    return False


def _rollback_restore(
    *,
    target_path: str,
    previous_path: str | None,
    safety_path: str | None,
    work_dir: str | None,
    target_existed: bool,
    target_digest: str | None,
    target_file_hash: str | None,
    target_info,
) -> bool:
    """Mengembalikan database produksi. True jika terverifikasi."""
    try:
        if not target_existed:
            if os.path.exists(target_path):
                failed_path = os.path.join(
                    work_dir or os.path.dirname(target_path),
                    f"failed_target_{uuid.uuid4().hex}.db",
                )
                os.replace(target_path, failed_path)
            return not os.path.exists(target_path)

        # Utamakan salinan previous (byte-for-byte sebelum swap).
        if previous_path and os.path.exists(previous_path):
            if os.path.exists(target_path):
                failed_path = os.path.join(
                    work_dir or os.path.dirname(target_path),
                    f"failed_target_{uuid.uuid4().hex}.db",
                )
                os.replace(target_path, failed_path)

            os.replace(previous_path, target_path)

            if _verify_restored_target(
                target_path,
                expected_digest=target_digest,
                expected_file_hash=target_file_hash,
                target_info=target_info,
            ):
                return True

        # Fallback: pulihkan dari safety backup.
        if safety_path and os.path.exists(safety_path):
            recovery_path = os.path.join(
                work_dir or os.path.dirname(target_path),
                f"rollback_{uuid.uuid4().hex}.db",
            )
            sqlite_backup(safety_path, recovery_path)

            if target_info is not None and target_info.valid:
                validate_database(
                    recovery_path,
                    expected_version=target_info.schema_version,
                    require_users=False,
                )

            os.replace(recovery_path, target_path)

            if _verify_restored_target(
                target_path,
                expected_digest=target_digest,
                expected_file_hash=target_file_hash,
                target_info=target_info,
            ):
                return True

        return False
    except Exception:
        return False


def restore_database(
    backup_path: str,
    target_db_path: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> str | None:
    """
    Mengembalikan database dari file backup dengan proses staging.

    Returns:
        Path safety backup yang dibuat sebelum restore (atau None jika
        database target belum ada).

    Raises:
        RestoreError: jika restore gagal/dibatalkan. Atribut
        ``safety_path`` berisi lokasi safety backup bila sudah dibuat.
    """
    candidate_path = os.path.abspath(backup_path)
    target_path = os.path.abspath(target_db_path)
    progress = on_progress or (lambda _phase, _message: None)

    if candidate_path == target_path:
        raise RestoreError(
            "File backup yang dipilih adalah database aktif. "
            "Pilih file backup lain."
        )

    if not os.path.isfile(candidate_path):
        raise RestoreError("File backup tidak ditemukan.")

    if os.path.getsize(candidate_path) <= 0:
        raise RestoreError("File backup kosong (0 byte).")

    target_dir = os.path.dirname(target_path)
    os.makedirs(target_dir, exist_ok=True)

    target_existed = os.path.exists(target_path)
    target_size = os.path.getsize(target_path) if target_existed else 0
    required_space = (
        os.path.getsize(candidate_path) * 3
        + target_size
        + 64 * 1024 * 1024
    )
    _check_disk_space(target_dir, required_space)

    target_info = None
    target_digest = None
    target_file_hash = None

    if target_existed:
        _check_target_readable(target_path)

        try:
            target_info = inspect_database(
                target_path,
                max_version=CURRENT_SCHEMA_VERSION,
            )
            target_file_hash = _sha256_file(target_path)
            if target_info.valid:
                target_digest = content_digest(target_path)
        except sqlite3.OperationalError as exc:
            raise RestoreError(
                "Database target tidak bisa dibaca karena sedang "
                "digunakan. Tutup aplikasi lain lalu coba lagi.",
                details=[str(exc)],
                phase="preflight",
            ) from exc

    progress("validating", "Memeriksa file backup...")
    try:
        validate_backup_file(candidate_path, require_users=True)
    except DatabaseValidationError as exc:
        raise RestoreError(
            "File backup tidak valid. Database produksi tidak diubah.",
            details=exc.details or [str(exc)],
            phase="validating",
        ) from exc

    work_dir: str | None = None
    staging_path: str | None = None
    previous_path: str | None = None
    safety_path: str | None = None
    marker_path = _marker_path(target_path)
    marker_written = False
    target_moved = False
    swapped = False
    staging_digest: str | None = None
    expected_fingerprint: dict[str, Any] | None = None

    try:
        work_root = _work_root(target_path)
        os.makedirs(work_root, exist_ok=True)
        work_dir = os.path.join(work_root, uuid.uuid4().hex)
        os.makedirs(work_dir, exist_ok=False)

        staging_path = os.path.join(work_dir, "staging.db")

        progress("staging", "Membuat salinan kerja...")
        _stage_candidate(candidate_path, staging_path, work_dir)

        staged_info = validate_database(
            staging_path,
            max_version=CURRENT_SCHEMA_VERSION,
            require_users=True,
        )
        before_fingerprint = business_fingerprint(staging_path)

        if staged_info.schema_version < CURRENT_SCHEMA_VERSION:
            progress("migrating", "Menyiapkan migrasi database...")
            staging_db = Database(db_path=staging_path)
            staging_db.initialize(run_bootstrap=False)

            staged_info = validate_database(
                staging_path,
                expected_version=CURRENT_SCHEMA_VERSION,
                require_users=True,
            )
            after_fingerprint = business_fingerprint(staging_path)
            differences = compare_business_fingerprints(
                before_fingerprint,
                after_fingerprint,
            )
            if differences:
                raise RestoreError(
                    "Migrasi backup mengubah data. Restore dibatalkan.",
                    details=differences,
                    phase="migrating",
                )
        else:
            after_fingerprint = before_fingerprint

        expected_fingerprint = after_fingerprint
        staging_digest = content_digest(staging_path)
        _fsync_file(staging_path)

        if target_existed:
            safety_path = _unique_path(
                os.path.join(
                    _backup_dir(target_path),
                    f"{SAFETY_PREFIX}{_stamp()}.db",
                )
            )
            os.makedirs(os.path.dirname(safety_path), exist_ok=True)

            progress("safety", "Membuat safety backup...")

            if target_info is not None and target_info.valid:
                sqlite_backup(target_path, safety_path)
                validate_database(
                    safety_path,
                    max_version=CURRENT_SCHEMA_VERSION,
                    require_users=False,
                )
                if target_digest != content_digest(safety_path):
                    raise RestoreError(
                        "Safety backup tidak sama dengan database "
                        "produksi. Restore dibatalkan.",
                        safety_path=safety_path,
                        phase="safety",
                    )
            else:
                # Database target sudah rusak. Simpan byte-for-byte agar
                # bukti/isi lama tetap bisa diselamatkan secara manual.
                shutil.copy2(target_path, safety_path)
                if target_file_hash != _sha256_file(safety_path):
                    raise RestoreError(
                        "Salinan pengaman database lama gagal diverifikasi.",
                        safety_path=safety_path,
                        phase="safety",
                    )

            _fsync_file(safety_path)

        marker_data: dict[str, Any] = {
            "phase": "prepared",
            "app_version": "1.0.0",
            "candidate_path": candidate_path,
            "candidate_sha256": _sha256_file(candidate_path),
            "staging_path": staging_path,
            "staging_digest": staging_digest,
            "safety_path": safety_path,
            "target_path": target_path,
            "work_dir": work_dir,
            "previous_path": os.path.join(work_dir, "previous.db"),
            "target_existed": target_existed,
            "target_digest": target_digest,
            "target_file_hash": target_file_hash,
            "pid": os.getpid(),
        }
        _write_marker(marker_path, marker_data)
        marker_written = True

        progress("locking", "Memastikan database tidak sedang digunakan...")
        _ensure_no_sidecars(target_path)
        if target_info is None or target_info.valid:
            _check_exclusive_access(target_path)

        previous_path = marker_data["previous_path"]

        if target_existed:
            os.replace(target_path, previous_path)
            target_moved = True
            marker_data["phase"] = "swapped_out"
            _write_marker(marker_path, marker_data)

        os.replace(staging_path, target_path)
        swapped = True
        marker_data["phase"] = "swapped_in"
        _write_marker(marker_path, marker_data)

        progress("verifying", "Memeriksa hasil restore...")
        validate_database(
            target_path,
            expected_version=CURRENT_SCHEMA_VERSION,
            require_users=True,
        )

        if content_digest(target_path) != staging_digest:
            raise RestoreError(
                "Isi database hasil restore berbeda dengan staging.",
                phase="verifying",
            )

        post_fingerprint = business_fingerprint(target_path)
        differences = compare_business_fingerprints(
            expected_fingerprint,
            post_fingerprint,
        )
        if differences:
            raise RestoreError(
                "Data hasil restore tidak konsisten.",
                details=differences,
                phase="verifying",
            )

        marker_data["phase"] = "done"
        _write_marker(marker_path, marker_data)
        _clear_marker(marker_path)
        _cleanup_work_dir(work_dir)

        progress("done", "Restore selesai.")
        return safety_path

    except Exception as exc:
        if isinstance(exc, RestoreError):
            error = exc
        else:
            error = RestoreError(
                "Restore gagal.",
                details=[str(exc)],
            )

        if target_moved or swapped:
            progress("rollback", "Mengembalikan database produksi...")
            rolled_back = _rollback_restore(
                target_path=target_path,
                previous_path=previous_path,
                safety_path=safety_path,
                work_dir=work_dir,
                target_existed=target_existed,
                target_digest=target_digest,
                target_file_hash=target_file_hash,
                target_info=target_info,
            )

            if rolled_back:
                if marker_written:
                    _clear_marker(marker_path)
                _cleanup_work_dir(work_dir)
                raise RestoreError(
                    "Restore gagal; database produksi sudah dikembalikan "
                    "ke kondisi sebelumnya.",
                    safety_path=safety_path,
                    details=error.details or [str(error)],
                    phase=error.phase,
                ) from exc

            raise RestoreError(
                "Restore gagal dan rollback otomatis juga gagal. "
                "Jangan menutup aplikasi. Gunakan safety backup di atas "
                "untuk memulihkan data secara manual.",
                safety_path=safety_path,
                details=(error.details or [str(error)])
                + ["Rollback otomatis gagal."],
                phase=error.phase,
                critical=True,
            ) from exc

        if marker_written:
            _clear_marker(marker_path)
        _cleanup_work_dir(work_dir)
        raise RestoreError(
            "Restore dibatalkan; database produksi tidak diubah.",
            safety_path=safety_path,
            details=error.details or [str(error)],
            phase=error.phase,
        ) from exc


# ----------------------------------------------------------------------
# Pemulihan setelah restore terputus
# ----------------------------------------------------------------------


def _target_matches_recovery(
    target_path: str,
    marker_data: dict[str, Any],
) -> bool:
    try:
        inspection = inspect_database(
            target_path,
            max_version=CURRENT_SCHEMA_VERSION,
        )
        if inspection.errors:
            return False

        expected_digest = marker_data.get("target_digest")
        if expected_digest:
            return content_digest(target_path) == expected_digest

        expected_hash = marker_data.get("target_file_hash")
        if expected_hash:
            return _sha256_file(target_path) == expected_hash

        return True
    except Exception:
        return False


def recover_interrupted_restore(
    target_db_path: str,
) -> dict[str, Any]:
    """
    Dipanggil saat startup, sebelum ``Database.initialize()``.

    Jika marker restore ditemukan, fungsi ini memastikan database target
    valid. Bila tidak, database dikembalikan dari ``previous.db`` atau
    safety backup. Fungsi ini tidak pernah membuat database baru.

    Returns:
        dict berisi ``action`` dan ``message``.
    """
    target_path = os.path.abspath(target_db_path)
    marker_path = _marker_path(target_path)

    marker_data = _read_marker(marker_path)
    if marker_data is None:
        return {"action": "none", "message": ""}

    safety_path = marker_data.get("safety_path")
    previous_path = marker_data.get("previous_path")
    work_dir = marker_data.get("work_dir")
    phase = marker_data.get("phase")

    target_info = inspect_database(
        target_path,
        max_version=CURRENT_SCHEMA_VERSION,
    )
    target_valid = target_info.valid and target_info.schema_version is not None

    if target_valid and phase in ("swapped_in", "verifying", "done"):
        expected_digest = marker_data.get("staging_digest")
        if expected_digest:
            try:
                target_valid = (
                    content_digest(target_path) == expected_digest
                )
            except Exception:
                target_valid = False

    if target_valid:
        _clear_marker(marker_path)
        _cleanup_work_dir(work_dir)
        return {
            "action": "kept_target",
            "message": (
                "Restore sebelumnya terputus, tetapi database utama "
                "sudah dalam kondisi valid. Safety backup tetap disimpan."
            ),
            "safety_path": safety_path,
        }

    recovery_dir = work_dir
    if not recovery_dir or not os.path.isdir(recovery_dir):
        recovery_dir = os.path.join(
            _work_root(target_path),
            uuid.uuid4().hex,
        )
        os.makedirs(recovery_dir, exist_ok=True)

    # Coba previous.db lebih dulu (kondisi persis sebelum swap).
    if previous_path and os.path.exists(previous_path):
        try:
            if os.path.exists(target_path):
                failed_path = os.path.join(
                    recovery_dir,
                    f"failed_target_{uuid.uuid4().hex}.db",
                )
                os.replace(target_path, failed_path)

            os.replace(previous_path, target_path)

            if _target_matches_recovery(target_path, marker_data):
                _clear_marker(marker_path)
                _cleanup_work_dir(recovery_dir)
                return {
                    "action": "rolled_back_previous",
                    "message": (
                        "Restore sebelumnya terputus. Database utama "
                        "dikembalikan ke kondisi sebelum restore."
                    ),
                    "safety_path": safety_path,
                }
        except Exception:
            pass

    # Fallback: safety backup.
    if safety_path and os.path.exists(safety_path):
        try:
            recovery_path = os.path.join(
                recovery_dir,
                f"recovery_{uuid.uuid4().hex}.db",
            )
            sqlite_backup(safety_path, recovery_path)
            validate_database(
                recovery_path,
                max_version=CURRENT_SCHEMA_VERSION,
                require_users=False,
            )
            os.replace(recovery_path, target_path)

            if _target_matches_recovery(target_path, marker_data):
                _clear_marker(marker_path)
                _cleanup_work_dir(recovery_dir)
                return {
                    "action": "rolled_back_safety",
                    "message": (
                        "Restore sebelumnya terputus. Database utama "
                        "dipulihkan dari safety backup."
                    ),
                    "safety_path": safety_path,
                }
        except Exception:
            pass

    raise RestoreRecoveryError(
        "Aplikasi menemukan proses restore yang terputus dan tidak bisa "
        "memulihkan database secara otomatis. Jangan membuat database "
        "baru. Hubungi pengembang dengan menyertakan lokasi file berikut.",
        details=[
            f"Database: {target_path}",
            f"Marker: {marker_path}",
            f"Safety backup: {safety_path}",
            f"Previous: {previous_path}",
            f"Work dir: {work_dir}",
        ],
    )
