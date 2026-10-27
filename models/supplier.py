import sqlite3

from database.database import Database


class SupplierModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Daftar & pencarian
    # ------------------------------------------------------------------
    def list_suppliers(self, search: str = ""):
        """
        Mengembalikan daftar supplier berdasarkan nama.
        """
        search = (search or "").strip()

        query = """
            SELECT
                id,
                name,
                notes,
                created_at,
                updated_at
            FROM suppliers
        """
        params = []

        if search:
            query += " WHERE name LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY name COLLATE NOCASE ASC;"

        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------
    def get_by_id(self, supplier_id: int):
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    name,
                    notes,
                    created_at,
                    updated_at
                FROM suppliers
                WHERE id = ?;
                """,
                (supplier_id,),
            ).fetchone()

        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Tambah
    # ------------------------------------------------------------------
    def add_supplier(self, name: str, notes: str = ""):
        """
        Returns:
            (success: bool, message: str, supplier_id: int | None)
        """
        name = (name or "").strip()
        notes = (notes or "").strip() or None

        if not name:
            return False, "Nama supplier wajib diisi.", None

        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO suppliers (name, notes)
                    VALUES (?, ?);
                    """,
                    (name, notes),
                )
                supplier_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            return False, "Nama supplier tersebut sudah digunakan.", None

        return True, "Supplier berhasil ditambahkan.", supplier_id

    # ------------------------------------------------------------------
    # Edit
    # ------------------------------------------------------------------
    def update_supplier(
        self,
        supplier_id: int,
        name: str,
        notes: str = "",
    ):
        """
        Returns:
            (success: bool, message: str)
        """
        name = (name or "").strip()
        notes = (notes or "").strip() or None

        if not name:
            return False, "Nama supplier wajib diisi."

        try:
            with self.db.transaction() as conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM suppliers
                    WHERE id = ?;
                    """,
                    (supplier_id,),
                ).fetchone()

                if not existing:
                    return False, "Supplier tidak ditemukan."

                conn.execute(
                    """
                    UPDATE suppliers
                    SET
                        name = ?,
                        notes = ?,
                        updated_at = datetime('now', 'localtime')
                    WHERE id = ?;
                    """,
                    (name, notes, supplier_id),
                )

        except sqlite3.IntegrityError:
            return False, "Nama supplier tersebut sudah digunakan."

        return True, "Data supplier berhasil diperbarui."

    # ------------------------------------------------------------------
    # Hapus
    # ------------------------------------------------------------------
    def delete_supplier(self, supplier_id: int):
        """
        Supplier hanya boleh dihapus jika belum digunakan
        oleh produk atau transaksi pembelian.
        """
        try:
            with self.db.transaction() as conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM suppliers
                    WHERE id = ?;
                    """,
                    (supplier_id,),
                ).fetchone()

                if not existing:
                    return False, "Supplier tidak ditemukan."

                product_usage = conn.execute(
                    """
                    SELECT 1
                    FROM products
                    WHERE supplier_id = ?
                    LIMIT 1;
                    """,
                    (supplier_id,),
                ).fetchone()

                if product_usage:
                    return (
                        False,
                        "Supplier tidak dapat dihapus karena masih digunakan oleh barang.",
                    )

                purchase_usage = conn.execute(
                    """
                    SELECT 1
                    FROM purchases
                    WHERE supplier_id = ?
                    LIMIT 1;
                    """,
                    (supplier_id,),
                ).fetchone()

                if purchase_usage:
                    return (
                        False,
                        "Supplier tidak dapat dihapus karena sudah digunakan dalam transaksi pembelian.",
                    )

                conn.execute(
                    """
                    DELETE FROM suppliers
                    WHERE id = ?;
                    """,
                    (supplier_id,),
                )

        except sqlite3.IntegrityError:
            return (
                False,
                "Supplier tidak dapat dihapus karena masih digunakan.",
            )

        return True, "Supplier berhasil dihapus."