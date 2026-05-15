"""分析结果缓存 — 避免每次请求重新跑完整分析管线。"""

import json
import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "klines.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS analysis_cache (
            symbol TEXT,
            interval TEXT,
            market_type TEXT NOT NULL DEFAULT 'spot',
            result_json TEXT NOT NULL,
            computed_at REAL NOT NULL,
            PRIMARY KEY (symbol, interval, market_type)
        )"""
    )
    # 迁移：旧表没有 market_type 列
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(analysis_cache)").fetchall()]
        if "market_type" not in cols:
            conn.execute("ALTER TABLE analysis_cache ADD COLUMN market_type TEXT NOT NULL DEFAULT 'spot'")
            conn.commit()
    except Exception:
        pass
    return conn


def save_analysis(symbol, interval, result, market_type="spot"):
    """存储分析结果，附带当前时间戳。"""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO analysis_cache VALUES (?, ?, ?, ?, ?)",
            (symbol, interval, market_type, json.dumps(result, ensure_ascii=False), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_analysis(symbol, interval, ttl_seconds, market_type="spot"):
    """返回缓存的分析结果（未过期），过期或不存在返回 None。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT result_json, computed_at FROM analysis_cache WHERE symbol=? AND interval=? AND market_type=?",
            (symbol, interval, market_type),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    result_json, computed_at = row
    if time.time() - computed_at > ttl_seconds:
        return None

    return json.loads(result_json)


def get_cache_status():
    """返回所有缓存条目及 age 信息，用于状态接口。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, interval, market_type, computed_at FROM analysis_cache ORDER BY symbol, interval"
        ).fetchall()
    finally:
        conn.close()

    now = time.time()
    return [
        {"symbol": r[0], "interval": r[1], "marketType": r[2], "computedAt": r[3], "age": round(now - r[3], 1)}
        for r in rows
    ]
