import sqlite3

from database.database import Database

# Nilai khusus untuk filter kelompok pada list_customers():
#   group_id=None      -> semua pelanggan
#   group_id=NO_GROUP  -> hanya pelanggan tanpa kelompok
#   group_id=<id>      -> hanya pelanggan di kelompok itu
NO_GROUP = -1

# Nilai khusus untuk update_customer(): jangan ubah kelompok pelanggan.
# (group_id=None berarti "kosongkan kelompok".)
KEEP_GROUP = object()

MAX_GROUP_NAME_LENGTH = 40


class CustomerModel:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Helper internal
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_balance(conn, customer_id: int):
        total_debt = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS total "
            "FROM debt_transactions WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()["total"]

        total_paid = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total "
            "FROM payments WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()["total"]

        return total_debt, total_paid, total_debt - total_paid

    @staticmethod
    def _group_exists(conn, group_id) -> bool:
        row = conn.execute(
            "SELECT 1 FROM customer_groups WHERE id = ?;",
            (group_id,),
        ).fetchone()

        return row is not None

    # ------------------------------------------------------------------
    # Daftar & pencarian
    # ------------------------------------------------------------------
    def list_customers(
        self,
        search: str = "",
        include_inactive: bool = False,
        group_id=None,
    ):
        """
        Mengembalikan list of dict pelanggan lengkap dengan saldo, status,
        dan kelompok, diurutkan berdasarkan nama.

        group_id: None (semua) | NO_GROUP (tanpa kelompok) | id kelompok.
        """
        query = (
            "SELECT c.id, c.name, c.phone, c.notes, c.is_active, "
            "c.group_id, g.name AS group_name "
            "FROM customers c "
            "LEFT JOIN customer_groups g ON g.id = c.group_id"
        )
        conditions = []
        params = []

        if not include_inactive:
            conditions.append("c.is_active = 1")

        if search:
            conditions.append("c.name LIKE ?")
            params.append(f"%{search.strip()}%")

        if group_id == NO_GROUP:
            conditions.append("c.group_id IS NULL")
        elif group_id is not None:
            conditions.append("c.group_id = ?")
            params.append(int(group_id))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.name COLLATE NOCASE ASC;"

        results = []

        with self.db.transaction() as conn:
            rows = conn.execute(query, params).fetchall()

            for row in rows:
                total_debt, total_paid, sisa = self._compute_balance(
                    conn, row["id"]
                )

                results.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "phone": row["phone"],
                        "notes": row["notes"],
                        "is_active": row["is_active"],
                        "group_id": row["group_id"],
                        "group_name": row["group_name"],
                        "total_debt": total_debt,
                        "total_paid": total_paid,
                        "sisa": sisa,
                        "status": "Lunas" if sisa <= 0 else "Masih Berhutang",
                    }
                )

        return results

    # ------------------------------------------------------------------
    # Tambah / edit / nonaktifkan
    # ------------------------------------------------------------------
    def add_customer(
        self,
        name: str,
        phone: str = "",
        notes: str = "",
        group_id=None,
    ):
        """Returns (sukses: bool, pesan: str, customer_id: int|None)."""
        name = (name or "").strip()

        if not name:
            return False, "Nama pelanggan wajib diisi.", None

        with self.db.transaction() as conn:
            if group_id is not None and not self._group_exists(conn, group_id):
                return False, "Kelompok tidak ditemukan.", None

            cursor = conn.execute(
                """
                INSERT INTO customers (name, phone, notes, group_id)
                VALUES (?, ?, ?, ?);
                """,
                (
                    name,
                    (phone or "").strip() or None,
                    (notes or "").strip() or None,
                    group_id,
                ),
            )

            new_id = cursor.lastrowid

        return True, "Pelanggan berhasil ditambahkan.", new_id

    def update_customer(
        self,
        customer_id: int,
        name: str,
        phone: str = "",
        notes: str = "",
        group_id=KEEP_GROUP,
    ):
        """
        Returns (sukses: bool, pesan: str).

        group_id: KEEP_GROUP (default, kelompok tidak diubah) |
                  None (kosongkan kelompok) | id kelompok.
        """
        name = (name or "").strip()

        if not name:
            return False, "Nama pelanggan wajib diisi."

        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE id = ?;",
                (customer_id,),
            ).fetchone()

            if not existing:
                return False, "Pelanggan tidak ditemukan."

            values = [
                name,
                (phone or "").strip() or None,
                (notes or "").strip() or None,
            ]
            group_sql = ""

            if group_id is not KEEP_GROUP:
                if group_id is not None and not self._group_exists(
                    conn, group_id
                ):
                    return False, "Kelompok tidak ditemukan."

                group_sql = ", group_id = ?"
                values.append(group_id)

            values.append(customer_id)

            conn.execute(
                f"""
                UPDATE customers
                SET
                    name = ?,
                    phone = ?,
                    notes = ?{group_sql},
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                values,
            )

        return True, "Data pelanggan berhasil diperbarui."

    def deactivate_customer(self, customer_id: int):
        """
        Soft delete - data & histori tetap tersimpan.
        Returns (sukses, pesan).
        """
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE id = ?;",
                (customer_id,),
            ).fetchone()

            if not existing:
                return False, "Pelanggan tidak ditemukan."

            conn.execute(
                """
                UPDATE customers
                SET
                    is_active = 0,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?;
                """,
                (customer_id,),
            )

        return True, "Pelanggan berhasil dinonaktifkan."

    # ------------------------------------------------------------------
    # Kelompok pelanggan
    # ------------------------------------------------------------------
    def list_groups(self):
        """
        Mengembalikan list of dict {id, name, member_count}, urut nama.
        member_count = jumlah pelanggan AKTIF di kelompok itu.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT
                    g.id,
                    g.name,
                    COUNT(c.id) AS member_count
                FROM customer_groups g
                LEFT JOIN customers c
                    ON c.group_id = g.id
                   AND c.is_active = 1
                GROUP BY g.id, g.name
                ORDER BY g.name COLLATE NOCASE ASC;
                """
            ).fetchall()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "member_count": row["member_count"],
            }
            for row in rows
        ]

    @staticmethod
    def _validate_group_name(name: str):
        """Returns (nama_bersih, pesan_error_atau_None)."""
        name = " ".join((name or "").split())

        if not name:
            return name, "Nama kelompok wajib diisi."

        if len(name) > MAX_GROUP_NAME_LENGTH:
            return name, (
                f"Nama kelompok maksimal {MAX_GROUP_NAME_LENGTH} karakter."
            )

        return name, None

    def add_group(self, name: str):
        """Returns (sukses: bool, pesan: str, group_id: int|None)."""
        name, error = self._validate_group_name(name)

        if error:
            return False, error, None

        try:
            with self.db.transaction() as conn:
                duplicate = conn.execute(
                    "SELECT 1 FROM customer_groups WHERE name = ?;",
                    (name,),
                ).fetchone()

                if duplicate:
                    return False, "Kelompok dengan nama tersebut sudah ada.", None

                cursor = conn.execute(
                    "INSERT INTO customer_groups (name) VALUES (?);",
                    (name,),
                )

                new_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            return False, "Kelompok dengan nama tersebut sudah ada.", None

        return True, "Kelompok berhasil ditambahkan.", new_id

    def rename_group(self, group_id: int, name: str):
        """Returns (sukses: bool, pesan: str)."""
        name, error = self._validate_group_name(name)

        if error:
            return False, error

        try:
            with self.db.transaction() as conn:
                if not self._group_exists(conn, group_id):
                    return False, "Kelompok tidak ditemukan."

                duplicate = conn.execute(
                    "SELECT 1 FROM customer_groups "
                    "WHERE name = ? AND id != ?;",
                    (name, group_id),
                ).fetchone()

                if duplicate:
                    return False, "Kelompok dengan nama tersebut sudah ada."

                conn.execute(
                    "UPDATE customer_groups SET name = ? WHERE id = ?;",
                    (name, group_id),
                )

        except sqlite3.IntegrityError:
            return False, "Kelompok dengan nama tersebut sudah ada."

        return True, "Nama kelompok berhasil diubah."

    def delete_group(self, group_id: int):
        """
        Menghapus kelompok. Pelanggannya TIDAK dihapus; mereka kembali
        menjadi "Tanpa kelompok".

        Returns (sukses: bool, pesan: str, jumlah_pelanggan_terdampak: int).
        """
        with self.db.transaction() as conn:
            if not self._group_exists(conn, group_id):
                return False, "Kelompok tidak ditemukan.", 0

            affected = conn.execute(
                "SELECT COUNT(*) AS total FROM customers "
                "WHERE group_id = ? AND is_active = 1;",
                (group_id,),
            ).fetchone()["total"]

            # Eksplisit (selain ON DELETE SET NULL) agar tidak bergantung
            # pada pengaturan foreign key koneksi.
            conn.execute(
                "UPDATE customers SET group_id = NULL WHERE group_id = ?;",
                (group_id,),
            )

            conn.execute(
                "DELETE FROM customer_groups WHERE id = ?;",
                (group_id,),
            )

        return True, "Kelompok berhasil dihapus.", affected

    # ------------------------------------------------------------------
    # Detail pelanggan (ringkasan + timeline)
    # ------------------------------------------------------------------
    def get_detail(self, customer_id: int):
        """
        Returns dict berisi data pelanggan, ringkasan saldo, dan timeline
        riwayat hutang + pembayaran (urut dari terbaru).

        Setiap entry timeline sekarang memiliki:
        - id
        - transaction_number untuk Hutang
        - date
        - type
        - amount
        - notes

        transaction_number pembayaran tetap None karena tabel payments
        tidak memiliki nomor transaksi.
        """
        with self.db.transaction() as conn:

            # ==========================================================
            # DATA PELANGGAN
            # ==========================================================

            customer = conn.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.phone,
                    c.notes,
                    c.is_active,
                    c.created_at,
                    c.group_id,
                    g.name AS group_name
                FROM customers c
                LEFT JOIN customer_groups g ON g.id = c.group_id
                WHERE c.id = ?;
                """,
                (customer_id,),
            ).fetchone()

            if not customer:
                return None

            # ==========================================================
            # SALDO
            # ==========================================================

            total_debt, total_paid, sisa = self._compute_balance(
                conn, customer_id
            )

            # ==========================================================
            # RIWAYAT HUTANG
            #
            # transaction_number dibawa supaya UI dapat menampilkan
            # nomor transaksi dan membuka detail transaksi hutang.
            # ==========================================================

            debts = conn.execute(
                """
                SELECT
                    id,
                    transaction_number,
                    transaction_date,
                    total_amount,
                    notes
                FROM debt_transactions
                WHERE customer_id = ?
                ORDER BY transaction_date DESC, id DESC;
                """,
                (customer_id,),
            ).fetchall()

            # ==========================================================
            # RIWAYAT PEMBAYARAN
            #
            # payments memang tidak mempunyai transaction_number.
            # ID payment tetap dibawa agar detail pembayaran dapat
            # dibuka berdasarkan ID tersebut.
            # ==========================================================

            payments = conn.execute(
                """
                SELECT
                    id,
                    payment_date,
                    amount,
                    notes
                FROM payments
                WHERE customer_id = ?
                ORDER BY payment_date DESC, id DESC;
                """,
                (customer_id,),
            ).fetchall()

        # ==============================================================
        # GABUNGKAN MENJADI TIMELINE
        # ==============================================================

        timeline = []

        for debt in debts:
            timeline.append(
                {
                    "id": debt["id"],
                    "transaction_number": debt["transaction_number"],
                    "date": debt["transaction_date"],
                    "type": "Hutang",
                    "amount": debt["total_amount"],
                    "notes": debt["notes"],
                }
            )

        for payment in payments:
            timeline.append(
                {
                    "id": payment["id"],
                    "transaction_number": None,
                    "date": payment["payment_date"],
                    "type": "Pembayaran",
                    "amount": payment["amount"],
                    "notes": payment["notes"],
                }
            )

        # Urutkan gabungan berdasarkan tanggal terbaru dulu.
        timeline.sort(
            key=lambda item: (
                item["date"] or "",
                item["id"] or 0,
            ),
            reverse=True,
        )

        # ==============================================================
        # HASIL
        # ==============================================================

        return {
            "id": customer["id"],
            "name": customer["name"],
            "phone": customer["phone"],
            "notes": customer["notes"],
            "is_active": customer["is_active"],
            "created_at": customer["created_at"],
            "group_id": customer["group_id"],
            "group_name": customer["group_name"],
            "total_debt": total_debt,
            "total_paid": total_paid,
            "sisa": sisa,
            "status": "Lunas" if sisa <= 0 else "Masih Berhutang",
            "timeline": timeline,
        }