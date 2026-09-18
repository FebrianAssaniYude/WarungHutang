"""
database/database.py

Mengelola koneksi ke database SQLite lokal:
- Menentukan lokasi file database (aman untuk mode development maupun .exe)
- Membuat skema tabel jika belum ada
- Membuat akun admin default pada first run
- Menyediakan helper context manager untuk transaksi yang aman
"""

import os
import sys
import sqlite3
from contextlib import contextmanager

# utils/security.py ada satu level di atas folder database/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import hash_password  # noqa: E402

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def get_app_base_dir() -> str:
    """
    Menentukan folder dasar aplikasi.

    - Saat dijalankan sebagai .exe hasil PyInstaller (frozen), folder dasar
      adalah folder tempat file .exe berada, agar database ikut terbawa
      dan tetap writable di sebelah executable.
    - Saat dijalankan sebagai script Python biasa, folder dasar adalah
      root project (dua tingkat di atas file ini: database/ -> root).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_database_path() -> str:
    """Mengembalikan path lengkap ke file database, memastikan folder ada."""
    base_dir = get_app_base_dir()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "warung.db")


def get_schema_path() -> str:
    """
    Mengembalikan path ke file schema.sql.

    - Saat dijalankan sebagai .exe hasil PyInstaller, file data (seperti
      schema.sql) diekstrak PyInstaller ke folder sementara sys._MEIPASS
      saat aplikasi berjalan - BUKAN di sebelah database.py yang sudah
      di-compile ke dalam file .exe. Karena itu path-nya harus diambil
      dari sys._MEIPASS, bukan dari os.path.dirname(__file__) module ini.
    - Saat dijalankan sebagai script Python biasa, schema.sql memang ada
      tepat di folder yang sama dengan file ini.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "database", "schema.sql")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


class Database:
    """
    Wrapper sederhana untuk koneksi SQLite.

    Contoh pemakaian:
        db = Database()
        db.initialize()  # buat tabel + admin default jika perlu

        with db.transaction() as conn:
            conn.execute("INSERT INTO customers (name) VALUES (?)", ("Budi",))
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_database_path()

    def connect(self) -> sqlite3.Connection:
        """
        Membuka koneksi baru ke database dengan foreign key aktif dan
        row_factory berbasis nama kolom (memudahkan akses data seperti dict).
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        # Jika file database sedang dikunci sesaat oleh proses lain (mis.
        # antivirus atau software backup yang sedang membaca file), tunggu
        # hingga 5 detik alih-alih langsung gagal dengan "database is locked".
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transaction(self):
        """
        Context manager transaksi aman: commit otomatis jika sukses,
        rollback otomatis jika terjadi exception (mencegah data
        setengah jadi tersimpan).
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

    def initialize(self) -> None:
        """
        Menjalankan schema.sql (idempotent, aman dipanggil berkali-kali
        karena semua statement memakai "IF NOT EXISTS"), lalu memastikan
        akun admin default tersedia pada first run.
        """
        schema_path = get_schema_path()
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with self.transaction() as conn:
            conn.executescript(schema_sql)

        self._ensure_default_admin()

    def _ensure_default_admin(self) -> None:
        """Membuat akun admin/admin jika tabel users masih kosong."""
        with self.transaction() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS total FROM users;")
            total_users = cursor.fetchone()["total"]

            if total_users == 0:
                password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?);",
                    (DEFAULT_ADMIN_USERNAME, password_hash),
                )
