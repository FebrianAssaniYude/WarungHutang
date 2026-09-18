"""
utils/backup.py

Backup & restore database SQLite lewat penyalinan file biasa (aplikasi
ini tidak memakai koneksi database yang dibiarkan terbuka lama -
Database.transaction() selalu membuka lalu menutup koneksi per operasi -
jadi menyalin file .db secara langsung aman dilakukan).
"""

import os
import shutil
from datetime import datetime


def backup_database(source_db_path: str, backup_dir: str = None) -> str:
    """
    Menyalin database ke folder backup dengan nama menyertakan tanggal
    & jam, mis. "backup_2026-09-11_1700.db".

    Returns:
        Path lengkap file backup yang baru dibuat.
    """
    if not os.path.exists(source_db_path):
        raise FileNotFoundError("File database tidak ditemukan.")

    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(source_db_path), "backup")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"backup_{timestamp}.db"
    dest_path = os.path.join(backup_dir, filename)

    # Hindari menimpa backup yang kebetulan dibuat pada menit yang sama.
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(backup_dir, f"backup_{timestamp}_{counter}.db")
        counter += 1

    shutil.copy2(source_db_path, dest_path)
    return dest_path


def restore_database(backup_path: str, target_db_path: str) -> str:
    """
    Mengembalikan database dari file backup. Sebelum menimpa, database
    yang sedang aktif SELALU disalin dulu ke folder backup (dengan nama
    "before_restore_...") sebagai jaring pengaman tambahan - supaya
    proses restore itu sendiri tidak pernah menyebabkan kehilangan data
    secara permanen jika ternyata file backup yang dipilih salah.

    Returns:
        Path file safety-backup yang dibuat sebelum restore (bisa None
        jika belum ada database aktif sebelumnya).
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError("File backup tidak ditemukan.")

    safety_backup_path = None
    if os.path.exists(target_db_path):
        backup_dir = os.path.join(os.path.dirname(target_db_path), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safety_backup_path = os.path.join(backup_dir, f"before_restore_{timestamp}.db")
        shutil.copy2(target_db_path, safety_backup_path)

    shutil.copy2(backup_path, target_db_path)
    return safety_backup_path
