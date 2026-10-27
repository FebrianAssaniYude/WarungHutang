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
        Mengembalikan daftar produk.

        Search mencocokkan nama atau barcode.
        Barcode bersifat opsional.
        """
        query = """
            SELECT
                p.id,
                p.barcode,
                p.name,
                p.purchase_price,
                p.selling_price,
                p.stock,
                p.opening_stock,
                p.supplier_id,
                s.name AS supplier_name,
                p.image_path,
                p.unit,
                p.is_active,
                p.created_at,
                p.updated_at
            FROM products p
            LEFT JOIN suppliers s
                ON s.id = p.supplier_id
        """

        conditions = []
        params = []

        if not include_inactive:
            conditions.append("p.is_active = 1")

        search = (search or "").strip()

        if search:
            conditions.append(
                "(p.name LIKE ? OR p.barcode LIKE ?)"
            )
            like_term = f"%{search}%"
            params.extend([like_term, like_term])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY p.name COLLATE NOCASE ASC;"

        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------
    def get_by_id(self, product_id: int):
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id,
                    p.barcode,
                    p.name,
                    p.purchase_price,
                    p.selling_price,
                    p.stock,
                    p.opening_stock,
                    p.supplier_id,
                    s.name AS supplier_name,
                    p.image_path,
                    p.unit,
                    p.is_active,
                    p.created_at,
                    p.updated_at
                FROM products p
                LEFT JOIN suppliers s
                    ON s.id = p.supplier_id
                WHERE p.id = ?;
                """,
                (product_id,),
            ).fetchone()

        return dict(row) if row else None

    def get_by_barcode(self, barcode: str, active_only: bool = True):
        """
        Mencari produk berdasarkan barcode persis.

        Barcode kosong dianggap tidak valid untuk pencarian.
        """
        barcode = (barcode or "").strip()

        if not barcode:
            return None

        query = """
            SELECT
                p.id,
                p.barcode,
                p.name,
                p.purchase_price,
                p.selling_price,
                p.stock,
                p.opening_stock,
                p.supplier_id,
                s.name AS supplier_name,
                p.image_path,
                p.unit,
                p.is_active,
                p.created_at,
                p.updated_at
            FROM products p
            LEFT JOIN suppliers s
                ON s.id = p.supplier_id
            WHERE p.barcode = ?
        """

        params = [barcode]

        if active_only:
            query += " AND p.is_active = 1"

        query += ";"

        with self.db.transaction() as conn:
            row = conn.execute(query, params).fetchone()

        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Tambah produk
    # ------------------------------------------------------------------
    def add_product(
        self,
        name: str,
        purchase_price,
        selling_price,
        opening_stock=0,
        barcode: str = "",
        supplier_id=None,
        image_path: str = "",
    ):
        """
        Returns:
            (success: bool, message: str, product_id: int | None)

        Saat produk baru dibuat:
            opening_stock = stok awal
            stock         = stok awal

        Field `price` legacy disamakan dengan selling_price
        untuk menjaga kompatibilitas dengan kode lama.
        """
        name = (name or "").strip()

        if not name:
            return False, "Nama barang wajib diisi.", None

        valid, purchase_value, error = self._validate_price(purchase_price)
        if not valid:
            return False, f"Harga beli: {error}", None

        valid, selling_value, error = self._validate_price(selling_price)
        if not valid:
            return False, f"Harga jual: {error}", None

        valid, stock_value, error = self._validate_stock(opening_stock)
        if not valid:
            return False, f"Stok awal: {error}", None

        barcode = (barcode or "").strip() or None
        image_path = (image_path or "").strip() or None

        try:
            with self.db.transaction() as conn:
                if supplier_id is not None:
                    if not self._supplier_exists(conn, supplier_id):
                        return False, "Supplier tidak ditemukan.", None

                cursor = conn.execute(
                    """
                    INSERT INTO products (
                        barcode,
                        name,
                        price,
                        purchase_price,
                        selling_price,
                        stock,
                        opening_stock,
                        supplier_id,
                        image_path
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        barcode,
                        name,
                        selling_value,
                        purchase_value,
                        selling_value,
                        stock_value,
                        stock_value,
                        supplier_id,
                        image_path,
                    ),
                )

                product_id = cursor.lastrowid

        except sqlite3.IntegrityError as exc:
            if "barcode" in str(exc).lower():
                return (
                    False,
                    "Barcode tersebut sudah digunakan oleh barang lain.",
                    None,
                )

            return False, "Data barang tidak dapat disimpan.", None

        return True, "Barang berhasil ditambahkan.", product_id

    # ------------------------------------------------------------------
    # Edit produk
    # ------------------------------------------------------------------
    def update_product(
        self,
        product_id: int,
        name: str,
        purchase_price,
        selling_price,
        barcode: str = "",
        supplier_id=None,
        image_path: str = "",
    ):
        """
        Mengedit data master produk.

        Stok dan opening_stock TIDAK diubah melalui method ini.
        """
        name = (name or "").strip()

        if not name:
            return False, "Nama barang wajib diisi."

        valid, purchase_value, error = self._validate_price(purchase_price)
        if not valid:
            return False, f"Harga beli: {error}"

        valid, selling_value, error = self._validate_price(selling_price)
        if not valid:
            return False, f"Harga jual: {error}"

        barcode = (barcode or "").strip() or None
        image_path = (image_path or "").strip() or None

        try:
            with self.db.transaction() as conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM products
                    WHERE id = ?;
                    """,
                    (product_id,),
                ).fetchone()

                if not existing:
                    return False, "Barang tidak ditemukan."

                if supplier_id is not None:
                    if not self._supplier_exists(conn, supplier_id):
                        return False, "Supplier tidak ditemukan."

                conn.execute(
                    """
                    UPDATE products
                    SET
                        barcode = ?,
                        name = ?,
                        price = ?,
                        purchase_price = ?,
                        selling_price = ?,
                        supplier_id = ?,
                        image_path = ?,
                        updated_at = datetime('now', 'localtime')
                    WHERE id = ?;
                    """,
                    (
                        barcode,
                        name,
                        selling_value,
                        purchase_value,
                        selling_value,
                        supplier_id,
                        image_path,
                        product_id,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            if "barcode" in str(exc).lower():
                return "Data barang tidak dapat diperbarui karena barcode sudah digunakan."

            return "Data barang tidak dapat diperbarui."

        return True, "Data barang berhasil diperbarui."

    # ------------------------------------------------------------------
    # Nonaktifkan
    # ------------------------------------------------------------------
    def deactivate_product(self, product_id: int):
        """
        Soft delete.

        Histori transaksi lama tetap aman.
        """
        with self.db.transaction() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

            if not existing:
                return False, "Barang tidak ditemukan."

            conn.execute(
                """
                UPDATE products
                SET
                    is_active = 0,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                (product_id,),
            )

        return True, "Barang berhasil dinonaktifkan."

    # ------------------------------------------------------------------
    # Aktivasi kembali
    # ------------------------------------------------------------------
    def activate_product(self, product_id: int):
        with self.db.transaction() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

            if not existing:
                return False, "Barang tidak ditemukan."

            conn.execute(
                """
                UPDATE products
                SET
                    is_active = 1,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                (product_id,),
            )

        return True, "Barang berhasil diaktifkan."

    # ------------------------------------------------------------------
    # Stok
    # ------------------------------------------------------------------
    def increase_stock(self, product_id: int, quantity: int):
        """
        Menambah stok secara atomik.

        Dipakai nantinya oleh transaksi pembelian.
        """
        valid, quantity_value, error = self._validate_quantity(quantity)

        if not valid:
            return False, error

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT id, stock
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

            if not row:
                return False, "Barang tidak ditemukan."

            conn.execute(
                """
                UPDATE products
                SET
                    stock = stock + ?,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                (quantity_value, product_id),
            )

        return True, "Stok berhasil ditambahkan."

    def decrease_stock(self, product_id: int, quantity: int):
        """
        Mengurangi stok secara atomik.

        Jika stok tidak mencukupi, transaksi ditolak.
        """
        valid, quantity_value, error = self._validate_quantity(quantity)

        if not valid:
            return False, error

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT id, stock
                FROM products
                WHERE id = ?;
                """,
                (product_id,),
            ).fetchone()

            if not row:
                return False, "Barang tidak ditemukan."

            if row["stock"] < quantity_value:
                return (
                    False,
                    f"Stok tidak mencukupi. Stok tersedia: {row['stock']}.",
                )

            conn.execute(
                """
                UPDATE products
                SET
                    stock = stock - ?,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                (quantity_value, product_id),
            )

        return True, "Stok berhasil dikurangi."

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    @staticmethod
    def _supplier_exists(conn, supplier_id):
        row = conn.execute(
            """
            SELECT id
            FROM suppliers
            WHERE id = ?;
            """,
            (supplier_id,),
        ).fetchone()

        return row is not None

    @staticmethod
    def _validate_price(value):
        try:
            value = int(round(float(value)))
        except (TypeError, ValueError):
            return False, None, "Harga harus berupa angka."

        if value < 0:
            return False, None, "Harga tidak boleh negatif."

        return True, value, None

    @staticmethod
    def _validate_stock(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return False, None, "Stok harus berupa angka bulat."

        if value < 0:
            return False, None, "Stok tidak boleh negatif."

        return True, value, None

    @staticmethod
    def _validate_quantity(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return False, None, "Jumlah harus berupa angka bulat."

        if value <= 0:
            return False, None, "Jumlah harus lebih dari 0."

        return True, value, None