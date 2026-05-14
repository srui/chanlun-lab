"""K 线 SQLite 缓存 — 减少 Binance API 调用"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "klines.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS klines (
            symbol TEXT,
            interval TEXT,
            open_time INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, interval, open_time)
        )"""
    )
    return conn


def save_klines(symbol, interval, klines):
    """批量写入 K 线缓存。跳过最后一根（可能未收盘）。"""
    if not klines:
        return
    conn = _get_conn()
    try:
        rows = klines[:-1]  # 最后一根可能未收盘，不缓存
        conn.executemany(
            "INSERT OR REPLACE INTO klines VALUES (?,?,?,?,?,?,?,?)",
            [
                (symbol, interval, k["openTime"], k["open"], k["high"],
                 k["low"], k["close"], k["volume"])
                for k in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_klines(symbol, interval, start_ms=None, end_ms=None):
    """查询缓存，返回 list[dict]，按 openTime 升序。"""
    conn = _get_conn()
    try:
        sql = "SELECT open_time, open, high, low, close, volume FROM klines WHERE symbol=? AND interval=?"
        params = [symbol, interval]
        if start_ms is not None:
            sql += " AND open_time >= ?"
            params.append(start_ms)
        if end_ms is not None:
            sql += " AND open_time <= ?"
            params.append(end_ms)
        sql += " ORDER BY open_time"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [
        {
            "openTime": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
            "closeTime": r[0] + 59999,
        }
        for r in rows
    ]


def get_latest_cached_time(symbol, interval):
    """返回最新缓存时间戳，无缓存返回 None。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
            (symbol, interval),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] else None
