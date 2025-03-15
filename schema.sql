-- schema.sql
DROP TABLE IF EXISTS contributions;
DROP TABLE IF EXISTS order_numbers;  -- Added table

CREATE TABLE contributions (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_id TEXT,
    status TEXT NOT NULL,
    ordernum TEXT,
    token TEXT,
    check_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_numbers (
    datestamp TEXT PRIMARY KEY,
    last_number INTEGER NOT NULL
);

-- archived sql
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS contributions;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,  -- SERIAL for auto-incrementing integer
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contributions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,  -- Use DECIMAL for currency values
    transaction_id TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);