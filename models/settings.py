"""
models/settings.py

Pengaturan aplikasi disimpan sebagai key-value di tabel settings.
Saat ini dipakai untuk "nama_warung", tapi dibuat generik supaya mudah
menambah pengaturan lain di masa depan tanpa migrasi skema.
"""

from database.database import Database

KEY_NAMA_WARUNG = "nama_warung"
DEFAULT_NAMA_WARUNG = "Warung Hutang"


class SettingsModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def get(self, key: str, default: str = None):
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?;", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str):
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
                (key, value),
            )

    # ------------------------------------------------------------------
    # Helper khusus nama warung (dipakai di header Laporan PDF, dsb)
    # ------------------------------------------------------------------
    def get_nama_warung(self) -> str:
        return self.get(KEY_NAMA_WARUNG, DEFAULT_NAMA_WARUNG)

    def set_nama_warung(self, name: str):
        name = (name or "").strip() or DEFAULT_NAMA_WARUNG
        self.set(KEY_NAMA_WARUNG, name)
        return name
