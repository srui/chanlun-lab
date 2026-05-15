"""币种自选列表 — SQLite 持久化，支持动态增删。"""

import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "klines.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            added_at REAL NOT NULL
        )"""
    )
    conn.commit()
    return conn


def get_watchlist():
    """返回所有自选币种列表（按 added_at 排序）。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol FROM watchlist ORDER BY added_at"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def add_symbol(symbol):
    """添加币种，返回 True 表示新增、False 表示已存在。"""
    symbol = symbol.upper().strip()
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO watchlist VALUES (?, ?)",
            (symbol, time.time()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def remove_symbol(symbol):
    """移除币种，返回是否成功。"""
    symbol = symbol.upper().strip()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
