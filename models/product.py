"""
models/product.py

Logika data barang: daftar, tambah, edit, nonaktifkan (soft delete),
dan pencarian (berdasarkan nama maupun barcode).

Barcode boleh NULL/kosong karena tidak semua barang memiliki barcode.
Kolom "barcode" di schema.sql memakai UNIQUE, tapi SQLite mengizinkan
banyak baris NULL pada kolom UNIQUE (NULL tidak dianggap sama dengan
NULL lain), jadi banyak barang tanpa barcode tetap bisa disimpan.
"""

import sqlite3

from database.database import Database


class ProductModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Daftar & pencarian
    # ------------------------------------------------------------------
    def list_products(self, search: str = "", include_inactive: bool = False):
        """
        Daftar barang, opsional difilter oleh 'search' yang mencocokkan
        nama ATAU barcode (LIKE), diurutkan berdasarkan nama.
        """
        query = "SELECT id, barcode, name, price, unit, is_active FROM products"
        conditions = []
        params = []

        if not include_inactive:
            conditions.append("is_active = 1")
        if search:
            conditions.append("(name LIKE ? OR barcode LIKE ?)")
            like_term = f"%{search.strip()}%"
            params.extend([like_term, like_term])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY name COLLATE NOCASE ASC;"

        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, product_id: int):
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id, barcode, name, price, unit, is_active FROM products WHERE id = ?;",
                (product_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_barcode(self, barcode: str, active_only: bool = True):
        """
        Mencari satu barang berdasarkan barcode persis.
        Dipakai saat scan barcode scanner USB.
        """
        barcode = (barcode or "").strip()
        if not barcode:
            return None

        query = "SELECT id, barcode, name, price, unit, is_active FROM products WHERE barcode = ?"
        params = [barcode]
        if active_only:
            query += " AND is_active = 1"
        query += ";"

        with self.db.transaction() as conn:
            row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Tambah / edit / nonaktifkan
    # ------------------------------------------------------------------
    def add_product(self, name: str, price, barcode: str = "", unit: str = ""):
        """Returns (sukses: bool, pesan: str, product_id: int|None)."""
        name = (name or "").strip()
        if not name:
            return False, "Nama barang wajib diisi.", None

        valid, price_value, price_error = self._validate_price(price)
        if not valid:
            return False, price_error, None

        barcode = (barcode or "").strip() or None
        unit = (unit or "").strip() or None

        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO products (barcode, name, price, unit) VALUES (?, ?, ?, ?);",
                    (barcode, name, price_value, unit),
                )
                new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            return False, "Barcode tersebut sudah digunakan oleh barang lain.", None

        return True, "Barang berhasil ditambahkan.", new_id

    def update_product(self, product_id: int, name: str, price, barcode: str = "", unit: str = ""):
        """Returns (sukses: bool, pesan: str)."""
        name = (name or "").strip()
        if not name:
            return False, "Nama barang wajib diisi."

        valid, price_value, price_error = self._validate_price(price)
        if not valid:
            return False, price_error

        barcode = (barcode or "").strip() or None
        unit = (unit or "").strip() or None

        try:
            with self.db.transaction() as conn:
                existing = conn.execute(
                    "SELECT id FROM products WHERE id = ?;", (product_id,)
                ).fetchone()
                if not existing:
                    return False, "Barang tidak ditemukan."

                conn.execute(
                    "UPDATE products SET barcode = ?, name = ?, price = ?, unit = ?, "
                    "updated_at = datetime('now', 'localtime') WHERE id = ?;",
                    (barcode, name, price_value, unit, product_id),
                )
        except sqlite3.IntegrityError:
            return False, "Barcode tersebut sudah digunakan oleh barang lain."

        return True, "Data barang berhasil diperbarui."

    def deactivate_product(self, product_id: int):
        """Soft delete - histori transaksi lama tetap aman. Returns (sukses, pesan)."""
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM products WHERE id = ?;", (product_id,)
            ).fetchone()
            if not existing:
                return False, "Barang tidak ditemukan."

            conn.execute(
                "UPDATE products SET is_active = 0, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?;",
                (product_id,),
            )

        return True, "Barang berhasil dinonaktifkan."

    # ------------------------------------------------------------------
    # Helper internal
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_price(price):
        """Returns (valid: bool, price_as_int: int|None, error_message: str|None)."""
        try:
            price_value = int(round(float(price)))
        except (TypeError, ValueError):
            return False, None, "Harga harus berupa angka."

        if price_value < 0:
            return False, None, "Harga tidak boleh negatif."

        return True, price_value, None
