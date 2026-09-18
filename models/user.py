"""
models/user.py

Logika terkait akun pengguna: autentikasi login, ganti username,
ganti password. Aplikasi ini hanya punya satu pengguna aktif, tapi
tabel/model dibuat generik agar tetap rapi dan mudah dites.
"""

from database.database import Database
from utils.security import hash_password, verify_password


class UserModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def get_by_username(self, username: str):
        """Mengembalikan baris user (dict-like) berdasarkan username, atau None."""
        if not username:
            return None
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at "
                "FROM users WHERE username = ?;",
                (username,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_id(self, user_id: int):
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at "
                "FROM users WHERE id = ?;",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def authenticate(self, username: str, password: str):
        """
        Mengecek kombinasi username & password.

        Returns:
            dict berisi data user (tanpa password_hash) jika berhasil,
            None jika username tidak ditemukan atau password salah.
        """
        username = (username or "").strip()
        if not username or not password:
            return None

        user = self.get_by_username(username)
        if user is None:
            return None

        if not verify_password(password, user["password_hash"]):
            return None

        # Jangan pernah mengembalikan password_hash ke pemanggil/UI.
        return {
            "id": user["id"],
            "username": user["username"],
            "created_at": user["created_at"],
        }

    def change_username(self, user_id: int, new_username: str) -> tuple[bool, str]:
        """
        Mengganti username. Mengembalikan (sukses, pesan).
        """
        new_username = (new_username or "").strip()
        if not new_username:
            return False, "Username baru tidak boleh kosong."

        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?;",
                (new_username, user_id),
            ).fetchone()
            if existing:
                return False, "Username tersebut sudah digunakan."

            conn.execute(
                "UPDATE users SET username = ? WHERE id = ?;",
                (new_username, user_id),
            )
        return True, "Username berhasil diubah."

    def change_password(self, user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
        """
        Mengganti password. Mewajibkan password lama yang benar sebagai
        verifikasi keamanan. Mengembalikan (sukses, pesan).
        """
        if not new_password or len(new_password) < 4:
            return False, "Password baru minimal 4 karakter."

        user = self.get_by_id(user_id)
        if user is None:
            return False, "Akun tidak ditemukan."

        if not verify_password(old_password, user["password_hash"]):
            return False, "Password lama tidak sesuai."

        new_hash = hash_password(new_password)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?;",
                (new_hash, user_id),
            )
        return True, "Password berhasil diubah."
