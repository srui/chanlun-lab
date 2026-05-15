"""K 线 SQLite 缓存 — 减少 Binance API 调用"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "klines.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS klines_v2 (
            symbol TEXT,
            interval TEXT,
            market_type TEXT NOT NULL DEFAULT 'spot',
            open_time INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, interval, market_type, open_time)
        )"""
    )
    # 迁移：如果旧表 klines 存在但没有 market_type 列，迁移数据
    _migrate_v1(conn)
    return conn


def _migrate_v1(conn):
    """将旧表数据迁移到新表 v2。"""
    try:
        # 检查旧表是否存在
        old = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='klines'").fetchone()
        if not old:
            return
        # 检查是否已迁移过（新表有数据）
        new_count = conn.execute("SELECT COUNT(*) FROM klines_v2").fetchone()[0]
        old_count = conn.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
        if old_count > 0 and new_count == 0:
            conn.execute(
                "INSERT OR IGNORE INTO klines_v2 (symbol, interval, market_type, open_time, open, high, low, close, volume) "
                "SELECT symbol, interval, 'spot', open_time, open, high, low, close, volume FROM klines"
            )
            conn.commit()
            print(f"[cache] 迁移 {old_count} 条旧缓存数据到 klines_v2")
    except Exception:
        pass  # 迁移失败不影响运行


def save_klines(symbol, interval, klines, market_type="spot"):
    """批量写入 K 线缓存。跳过最后一根（可能未收盘）。"""
    if not klines:
        return
    conn = _get_conn()
    try:
        rows = klines[:-1]
        conn.executemany(
            "INSERT OR REPLACE INTO klines_v2 VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (symbol, interval, market_type, k["openTime"], k["open"], k["high"],
                 k["low"], k["close"], k["volume"])
                for k in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_klines(symbol, interval, start_ms=None, end_ms=None, market_type="spot"):
    """查询缓存，返回 list[dict]，按 openTime 升序。"""
    conn = _get_conn()
    try:
        sql = "SELECT open_time, open, high, low, close, volume FROM klines_v2 WHERE symbol=? AND interval=? AND market_type=?"
        params = [symbol, interval, market_type]
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


def get_latest_cached_time(symbol, interval, market_type="spot"):
    """返回最新缓存时间戳，无缓存返回 None。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(open_time) FROM klines_v2 WHERE symbol=? AND interval=? AND market_type=?",
            (symbol, interval, market_type),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] else None
