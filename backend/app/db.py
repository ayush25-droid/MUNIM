"""Schema + connection. Six tables, money in integer paise (see IMPLEMENTATION.md).

Every function opens and closes its own connection unless a `conn` is passed in, in
which case the caller owns the transaction (commit/rollback/close). That's how
inventory.apply_scan keeps a whole bill's writes inside one transaction while still
reusing these same helpers.

Function names here (`create_scan`, `get_scan`, `set_scan_status`, `get_connection`,
plus the sku/alias/ledger helpers) aren't pinned by docs/api-contract.md the way the
API shapes are -- only the table columns were frozen in IMPLEMENTATION.md. Treat this
file's function names as the de facto contract going forward.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time

DB_PATH = os.getenv("DB_PATH", "munim.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL REFERENCES shops(id),
    name TEXT NOT NULL,
    canonical_unit TEXT NOT NULL,
    current_qty REAL NOT NULL DEFAULT 0,
    cost_per_unit INTEGER,
    sell_price INTEGER,
    -- Per-SKU unit->canonical ratios as a JSON object, e.g. {"box": 24, "dozen": 12}.
    -- Not in the IMPLEMENTATION.md column list (which only named "columns that
    -- matter") but required for units.convert()'s per-SKU packaging rule -- a box of
    -- Coke is 24, a box of something else isn't, and nothing else in the schema
    -- records that ratio.
    unit_conversions TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL REFERENCES shops(id),
    text TEXT NOT NULL,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    UNIQUE(shop_id, text)
);

CREATE TABLE IF NOT EXISTS stock_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    direction TEXT NOT NULL,
    qty REAL NOT NULL,
    unit_as_said TEXT,
    price_paise INTEGER,
    ts REAL NOT NULL,
    scan_id INTEGER REFERENCES scans(id)
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL REFERENCES shops(id),
    raw_text TEXT,
    items_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    direction TEXT NOT NULL DEFAULT 'stock_in',
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    direction TEXT,
    body TEXT,
    ts REAL NOT NULL
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _with_conn(conn: sqlite3.Connection | None):
    """Returns (conn, owns_conn). Callers close only the connections they opened."""
    if conn is not None:
        return conn, False
    return get_connection(), True


# --- shops -------------------------------------------------------------------------

def create_shop(name: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO shops (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_shop(shop_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        return _row(row)
    finally:
        conn.close()


# --- skus ----------------------------------------------------------------------------

def create_sku(shop_id: int, name: str, canonical_unit: str, current_qty: float = 0,
               cost_per_unit: int | None = None, sell_price: int | None = None,
               unit_conversions: dict | None = None, conn: sqlite3.Connection | None = None) -> int:
    conn, owns_conn = _with_conn(conn)
    try:
        cur = conn.execute(
            """INSERT INTO skus (shop_id, name, canonical_unit, current_qty,
                                  cost_per_unit, sell_price, unit_conversions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (shop_id, name, canonical_unit, current_qty, cost_per_unit, sell_price,
             json.dumps(unit_conversions or {})),
        )
        if owns_conn:
            conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def get_sku(sku_id: int, conn: sqlite3.Connection | None = None) -> dict | None:
    conn, owns_conn = _with_conn(conn)
    try:
        row = conn.execute("SELECT * FROM skus WHERE id = ?", (sku_id,)).fetchone()
        return _row(row)
    finally:
        if owns_conn:
            conn.close()


def list_skus(shop_id: int, conn: sqlite3.Connection | None = None) -> list[dict]:
    conn, owns_conn = _with_conn(conn)
    try:
        rows = conn.execute(
            "SELECT * FROM skus WHERE shop_id = ? ORDER BY name", (shop_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def update_sku(sku_id: int, conn: sqlite3.Connection | None = None, **fields) -> None:
    if not fields:
        return
    conn, owns_conn = _with_conn(conn)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE skus SET {set_clause} WHERE id = ?", (*fields.values(), sku_id))
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


# --- aliases -------------------------------------------------------------------------

def get_alias(shop_id: int, text: str, conn: sqlite3.Connection | None = None) -> dict | None:
    conn, owns_conn = _with_conn(conn)
    try:
        row = conn.execute(
            "SELECT * FROM aliases WHERE shop_id = ? AND text = ?", (shop_id, text)
        ).fetchone()
        return _row(row)
    finally:
        if owns_conn:
            conn.close()


def list_aliases(shop_id: int, conn: sqlite3.Connection | None = None) -> list[dict]:
    conn, owns_conn = _with_conn(conn)
    try:
        rows = conn.execute("SELECT * FROM aliases WHERE shop_id = ?", (shop_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def upsert_alias(shop_id: int, text: str, sku_id: int, conn: sqlite3.Connection | None = None) -> int:
    """The shopkeeper's latest pick for a given bill-text wins over whatever (if
    anything) was learned before -- temporarily wrong is fine, permanently wrong from
    a stale alias is not.
    """
    conn, owns_conn = _with_conn(conn)
    try:
        conn.execute(
            """INSERT INTO aliases (shop_id, text, sku_id) VALUES (?, ?, ?)
               ON CONFLICT(shop_id, text) DO UPDATE SET sku_id = excluded.sku_id""",
            (shop_id, text, sku_id),
        )
        if owns_conn:
            conn.commit()
        row = conn.execute(
            "SELECT id FROM aliases WHERE shop_id = ? AND text = ?", (shop_id, text)
        ).fetchone()
        return row["id"]
    finally:
        if owns_conn:
            conn.close()


# --- stock_ledger ----------------------------------------------------------------------

def insert_ledger(sku_id: int, direction: str, qty: float, unit_as_said: str | None = None,
                   price_paise: int | None = None, scan_id: int | None = None,
                   ts: float | None = None, conn: sqlite3.Connection | None = None) -> int:
    conn, owns_conn = _with_conn(conn)
    try:
        cur = conn.execute(
            """INSERT INTO stock_ledger (sku_id, direction, qty, unit_as_said,
                                          price_paise, ts, scan_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sku_id, direction, qty, unit_as_said, price_paise, ts or time.time(), scan_id),
        )
        if owns_conn:
            conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def sum_stock_out(sku_id: int, since_ts: float, conn: sqlite3.Connection | None = None) -> float:
    conn, owns_conn = _with_conn(conn)
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(qty), 0) AS total FROM stock_ledger
               WHERE sku_id = ? AND direction = 'stock_out' AND ts >= ?""",
            (sku_id, since_ts),
        ).fetchone()
        return float(row["total"])
    finally:
        if owns_conn:
            conn.close()


def insert_ledger_batch(rows: list[dict], conn: sqlite3.Connection | None = None) -> None:
    """Bulk-load historical ledger rows with an explicit `ts`, for seed.py's 14 days
    of sales history. Thin wrapper over insert_ledger so seed.py doesn't poke at SQL.
    """
    conn, owns_conn = _with_conn(conn)
    try:
        for row in rows:
            insert_ledger(conn=conn, **row)
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


# --- scans ---------------------------------------------------------------------------

def create_scan(shop_id: int, raw_text: str, items_json: str, status: str = "pending",
                 direction: str = "stock_in", conn: sqlite3.Connection | None = None) -> int:
    conn, owns_conn = _with_conn(conn)
    try:
        cur = conn.execute(
            "INSERT INTO scans (shop_id, raw_text, items_json, status, direction, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (shop_id, raw_text, items_json, status, direction, time.time()),
        )
        if owns_conn:
            conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def get_scan(scan_id: int, conn: sqlite3.Connection | None = None) -> dict | None:
    conn, owns_conn = _with_conn(conn)
    try:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return _row(row)
    finally:
        if owns_conn:
            conn.close()


def set_scan_status(scan_id: int, status: str, conn: sqlite3.Connection | None = None) -> None:
    conn, owns_conn = _with_conn(conn)
    try:
        conn.execute("UPDATE scans SET status = ? WHERE id = ?", (status, scan_id))
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


# --- messages ------------------------------------------------------------------------

def create_message(sender: str, direction: str, body: str,
                    conn: sqlite3.Connection | None = None) -> int:
    conn, owns_conn = _with_conn(conn)
    try:
        cur = conn.execute(
            "INSERT INTO messages (sender, direction, body, ts) VALUES (?, ?, ?, ?)",
            (sender, direction, body, time.time()),
        )
        if owns_conn:
            conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()
