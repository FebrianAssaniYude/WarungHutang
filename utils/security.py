"""
utils/security.py

Fungsi-fungsi terkait keamanan: hashing & verifikasi password.
Menggunakan bcrypt agar password tidak pernah disimpan sebagai plaintext.
"""

import bcrypt


def hash_password(plain_password: str) -> str:
    """
    Membuat hash bcrypt dari password plaintext.

    Args:
        plain_password: password asli yang diketik pengguna.

    Returns:
        String hash bcrypt (aman untuk disimpan di database).
    """
    if not plain_password:
        raise ValueError("Password tidak boleh kosong.")

    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Mengecek apakah password plaintext cocok dengan hash yang tersimpan.

    Args:
        plain_password: password yang diketik saat login.
        password_hash: hash bcrypt yang tersimpan di database.

    Returns:
        True jika cocok, False jika tidak.
    """
    if not plain_password or not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # Hash rusak/format tidak valid -> anggap tidak cocok, jangan crash.
        return False
