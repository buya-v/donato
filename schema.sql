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