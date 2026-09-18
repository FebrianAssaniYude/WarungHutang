-- =========================================================
-- Warung Hutang - Database Schema (SQLite)
-- =========================================================
-- Catatan penting:
-- - Semua nominal uang disimpan sebagai INTEGER (satuan rupiah penuh,
--   tanpa desimal). Format "Rp" hanya dilakukan di lapisan tampilan.
-- - Foreign key harus diaktifkan secara eksplisit oleh koneksi SQLite
--   (dilakukan di database/database.py via "PRAGMA foreign_keys = ON").
-- - Soft delete memakai kolom is_active pada customers & products.
-- =========================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------
-- users: akun login aplikasi (hanya 1 pengguna, tapi tabel
-- dibuat generik agar mudah dikembangkan/di-reset)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------------------------------------------------------
-- customers: pelanggan warung
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
CREATE INDEX IF NOT EXISTS idx_customers_is_active ON customers(is_active);

-- ---------------------------------------------------------
-- products: barang yang dijual/dicatat sebagai hutang
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode         TEXT UNIQUE,             -- boleh NULL, tidak semua barang punya barcode
    name            TEXT NOT NULL,
    price           INTEGER NOT NULL CHECK (price >= 0),
    unit            TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active);

-- ---------------------------------------------------------
-- debt_transactions: header transaksi hutang (per kunjungan)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS debt_transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id         INTEGER NOT NULL,
    transaction_date    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_amount        INTEGER NOT NULL CHECK (total_amount >= 0),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_debt_tx_customer ON debt_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_debt_tx_date ON debt_transactions(transaction_date);

-- ---------------------------------------------------------
-- debt_details: rincian barang per transaksi hutang
-- product_name & price disimpan terpisah dari products agar
-- histori tidak berubah walau data master berubah di kemudian hari.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS debt_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL,
    product_id      INTEGER,                 -- boleh NULL untuk barang manual
    product_name    TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    price           INTEGER NOT NULL CHECK (price >= 0),
    subtotal        INTEGER NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (transaction_id) REFERENCES debt_transactions(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_debt_details_tx ON debt_details(transaction_id);
CREATE INDEX IF NOT EXISTS idx_debt_details_product ON debt_details(product_id);

-- ---------------------------------------------------------
-- payments: pembayaran, dikaitkan ke pelanggan saja (bukan
-- ke transaksi hutang tertentu)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL,
    payment_date    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    amount          INTEGER NOT NULL CHECK (amount > 0),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);

-- ---------------------------------------------------------
-- settings: key-value untuk pengaturan aplikasi
-- (nama warung, dll)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    key     TEXT NOT NULL UNIQUE,
    value   TEXT
);
