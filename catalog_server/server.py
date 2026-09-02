"""
Database — MCP server for the product catalog.

Exposes four tools over Streamable HTTP:
  - query_products(max_price, category=None)
  - get_product(product_id)
  - get_catalog_summary()
  - compare_products(product_ids)

Run:
    python seed_db.py        # once, to create catalog.db
    python server.py         # starts on http://127.0.0.1:8100/mcp
"""
import sqlite3
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "catalog.db"

mcp = FastMCP("database", host="127.0.0.1", port=8100)


def _connect():
    if not DB_PATH.exists():
        raise RuntimeError("catalog.db not found — run seed_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def query_products(max_price: float, category: Optional[str] = None) -> list[dict]:
    """Search the catalog for products at or below a given price,
    optionally filtered by category (electronics, stationery, home)."""
    conn = _connect()
    try:
        if category:
            rows = conn.execute(
                "SELECT id, name, price, category FROM products "
                "WHERE price <= ? AND category = ? ORDER BY price",
                (max_price, category),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, price, category FROM products "
                "WHERE price <= ? ORDER BY price",
                (max_price,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def get_product(product_id: int) -> dict:
    """Look up a single product by its id."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, name, price, category FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            return {"error": f"no product with id {product_id}"}
        return dict(row)
    finally:
        conn.close()


@mcp.tool()
def get_catalog_summary() -> dict:
    """Return aggregate statistics about the product catalog: available
    categories, number of products per category, and the price range
    (min and max) for each category and overall."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT
                category,
                COUNT(*)   AS count,
                MIN(price) AS min_price,
                MAX(price) AS max_price
            FROM products
            GROUP BY category
            ORDER BY category
            """
        ).fetchall()
        overall = conn.execute(
            "SELECT COUNT(*), MIN(price), MAX(price) FROM products"
        ).fetchone()
        return {
            "total_products": overall[0],
            "overall_price_range": {"min": overall[1], "max": overall[2]},
            "by_category": [
                {
                    "category": r["category"],
                    "count": r["count"],
                    "price_range": {"min": r["min_price"], "max": r["max_price"]},
                }
                for r in rows
            ],
        }
    finally:
        conn.close()


@mcp.tool()
def compare_products(product_ids: list[int]) -> list[dict]:
    """Fetch and return multiple products by their ids for side-by-side
    comparison. Products not found are included as error entries so the
    caller always receives one entry per requested id."""
    conn = _connect()
    try:
        placeholders = ", ".join("?" * len(product_ids))
        rows = conn.execute(
            f"SELECT id, name, price, category FROM products WHERE id IN ({placeholders})",
            product_ids,
        ).fetchall()
        found = {r["id"]: dict(r) for r in rows}
        return [
            found.get(pid, {"error": f"no product with id {pid}", "id": pid})
            for pid in product_ids
        ]
    finally:
        conn.close()


if __name__ == "__main__":
    # Streamable HTTP transport: reachable at http://127.0.0.1:8100/mcp
    mcp.run(transport="streamable-http")
