"""
Creates catalog.db with a small product table.
Run once: python seed_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "catalog.db"

PRODUCTS = [
    ("Wireless Mouse", 14.99, "electronics"),
    ("USB-C Cable 1m", 6.50, "electronics"),
    ("Notebook A5", 3.20, "stationery"),
    ("Ceramic Mug", 8.90, "home"),
    ("Bluetooth Speaker", 24.00, "electronics"),
    ("Desk Lamp", 19.99, "home"),
    ("Ballpoint Pen Set", 4.50, "stationery"),
    ("Phone Stand", 9.99, "electronics"),
    ("Water Bottle", 11.00, "home"),
    ("Sticky Notes Pack", 2.75, "stationery"),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO products (name, price, category) VALUES (?, ?, ?)",
        PRODUCTS,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with {len(PRODUCTS)} products.")


if __name__ == "__main__":
    main()
