PRAGMA foreign_keys = ON;

-- =========================================================
-- schema_version
-- =========================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- =========================================================
-- users
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- =========================================================
-- customer_groups (kelompok pelanggan)
-- Nama unik tanpa membedakan huruf besar/kecil.
-- =========================================================
CREATE TABLE IF NOT EXISTS customer_groups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- =========================================================
-- customers
-- group_id boleh NULL (= "Tanpa kelompok").
-- Bila kelompok dihapus, pelanggannya tetap ada dan group_id menjadi NULL.
-- =========================================================
CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    group_id        INTEGER
                    REFERENCES customer_groups(id)
                    ON UPDATE CASCADE
                    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_name
    ON customers(name);

CREATE INDEX IF NOT EXISTS idx_customers_is_active
    ON customers(is_active);

CREATE INDEX IF NOT EXISTS idx_customers_group
    ON customers(group_id);

-- =========================================================
-- suppliers
-- =========================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_suppliers_name
    ON suppliers(name);

-- =========================================================
-- products
-- =========================================================
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode         TEXT UNIQUE,
    name            TEXT NOT NULL,

    -- Legacy column dari schema lama.
    -- Dipertahankan untuk kompatibilitas database lama.
    price           INTEGER NOT NULL DEFAULT 0 CHECK (price >= 0),

    purchase_price  INTEGER NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    selling_price   INTEGER NOT NULL DEFAULT 0 CHECK (selling_price >= 0),

    stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    opening_stock   INTEGER NOT NULL DEFAULT 0 CHECK (opening_stock >= 0),

    supplier_id     INTEGER,
    image_path      TEXT,

    -- Dipertahankan untuk kompatibilitas.
    -- Tidak perlu ditampilkan pada UI baru.
    unit            TEXT,

    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),

    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_products_name
    ON products(name);

CREATE INDEX IF NOT EXISTS idx_products_barcode
    ON products(barcode);

CREATE INDEX IF NOT EXISTS idx_products_is_active
    ON products(is_active);

CREATE INDEX IF NOT EXISTS idx_products_supplier
    ON products(supplier_id);

-- =========================================================
-- debt_transactions
-- =========================================================
CREATE TABLE IF NOT EXISTS debt_transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_number  TEXT UNIQUE,
    customer_id         INTEGER NOT NULL,
    transaction_date    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_amount        INTEGER NOT NULL CHECK (total_amount >= 0),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_debt_tx_customer
    ON debt_transactions(customer_id);

CREATE INDEX IF NOT EXISTS idx_debt_tx_date
    ON debt_transactions(transaction_date);

CREATE INDEX IF NOT EXISTS idx_debt_tx_number
    ON debt_transactions(transaction_number);

-- =========================================================
-- debt_details
-- =========================================================
CREATE TABLE IF NOT EXISTS debt_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL,
    product_id      INTEGER,
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

CREATE INDEX IF NOT EXISTS idx_debt_details_tx
    ON debt_details(transaction_id);

CREATE INDEX IF NOT EXISTS idx_debt_details_product
    ON debt_details(product_id);

-- =========================================================
-- payments
-- total_debt_at_payment / remaining_debt_at_payment adalah snapshot
-- kondisi hutang saat pembayaran dibuat (NULL untuk pembayaran lama).
-- =========================================================
CREATE TABLE IF NOT EXISTS payments (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id                 INTEGER NOT NULL,
    payment_date                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    amount                      INTEGER NOT NULL CHECK (amount > 0),
    notes                       TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_debt_at_payment       INTEGER,
    remaining_debt_at_payment   INTEGER,

    FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_payments_customer
    ON payments(customer_id);

CREATE INDEX IF NOT EXISTS idx_payments_date
    ON payments(payment_date);

-- =========================================================
-- purchases
-- =========================================================
CREATE TABLE IF NOT EXISTS purchases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_number  TEXT NOT NULL UNIQUE,
    transaction_date    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    supplier_id         INTEGER,
    total_amount        INTEGER NOT NULL CHECK (total_amount >= 0),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_purchases_number
    ON purchases(transaction_number);

CREATE INDEX IF NOT EXISTS idx_purchases_date
    ON purchases(transaction_date);

CREATE INDEX IF NOT EXISTS idx_purchases_supplier
    ON purchases(supplier_id);

-- =========================================================
-- purchase_details
-- =========================================================
CREATE TABLE IF NOT EXISTS purchase_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id     INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    product_name    TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    price           INTEGER NOT NULL CHECK (price >= 0),
    subtotal        INTEGER NOT NULL CHECK (subtotal >= 0),

    FOREIGN KEY (purchase_id) REFERENCES purchases(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (product_id) REFERENCES products(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_purchase_details_purchase
    ON purchase_details(purchase_id);

CREATE INDEX IF NOT EXISTS idx_purchase_details_product
    ON purchase_details(product_id);

-- =========================================================
-- sales
-- =========================================================
CREATE TABLE IF NOT EXISTS sales (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_number  TEXT NOT NULL UNIQUE,
    transaction_date    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_amount        INTEGER NOT NULL CHECK (total_amount >= 0),
    paid_amount         INTEGER NOT NULL CHECK (paid_amount >= 0),
    change_amount       INTEGER NOT NULL CHECK (change_amount >= 0),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    CHECK (paid_amount >= total_amount),
    CHECK (change_amount = paid_amount - total_amount)
);

CREATE INDEX IF NOT EXISTS idx_sales_number
    ON sales(transaction_number);

CREATE INDEX IF NOT EXISTS idx_sales_date
    ON sales(transaction_date);

-- =========================================================
-- sale_details
-- =========================================================
CREATE TABLE IF NOT EXISTS sale_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id         INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    product_name    TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    price           INTEGER NOT NULL CHECK (price >= 0),
    subtotal        INTEGER NOT NULL CHECK (subtotal >= 0),

    FOREIGN KEY (sale_id) REFERENCES sales(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (product_id) REFERENCES products(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sale_details_sale
    ON sale_details(sale_id);

CREATE INDEX IF NOT EXISTS idx_sale_details_product
    ON sale_details(product_id);

-- =========================================================
-- settings
-- =========================================================
CREATE TABLE IF NOT EXISTS settings (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    key     TEXT NOT NULL UNIQUE,
    value   TEXT
);

-- =========================================================
-- Fresh database = schema version 4
-- =========================================================
INSERT INTO schema_version (version)
SELECT 4
WHERE NOT EXISTS (SELECT 1 FROM schema_version);