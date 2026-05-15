"""后台守护线程 — 定时更新所有币种/周期/市场的分析缓存。"""

import time
import threading
from chanlun.binance_service import fetch_klines_cached
from chanlun.pipeline import analyze_klines
from chanlun.signal import compute_signal
from chanlun.config import get_poll_interval, get_context_interval, DEFAULT_SYMBOLS, CACHE_INTERVALS
from chanlun.analysis_cache import save_analysis

MARKET_TYPES = ["spot", "futures"]

_updater_status = {
    "running": False,
    "symbols": [],
    "intervals": [],
    "marketTypes": MARKET_TYPES,
    "lastRun": None,
    "lastError": None,
    "stats": {},
}


def _update_one(symbol, interval, market_type="spot", limit=300):
    """拉取 K 线、跑管线、存缓存。"""
    klines = fetch_klines_cached(symbol, interval, limit, market_type=market_type)
    if len(klines) < 3:
        return None

    primary = analyze_klines(klines)
    primary["symbol"] = symbol
    primary["interval"] = interval
    primary["klines"] = klines

    context_interval = get_context_interval(interval)
    context = None
    if context_interval:
        ctx_limit = max(50, limit // 4)
        try:
            ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit, market_type=market_type)
        except Exception:
            ctx_klines = []
        if len(ctx_klines) >= 3:
            context = analyze_klines(ctx_klines)
            context["symbol"] = symbol
            context["interval"] = context_interval
            context["klines"] = ctx_klines

    signal = compute_signal(primary, context)

    cache_entry = {"primary": primary, "context": context, "signal": signal}
    save_analysis(symbol, interval, cache_entry, market_type=market_type)
    return cache_entry


def _updater_loop(symbols=None, intervals=None):
    if symbols is None:
        symbols = DEFAULT_SYMBOLS
    if intervals is None:
        intervals = CACHE_INTERVALS

    _updater_status["running"] = True
    _updater_status["symbols"] = symbols
    _updater_status["intervals"] = intervals

    last_update = {}
    min_sleep = 10
    total = len(symbols) * len(intervals) * len(MARKET_TYPES)

    print(f"[updater] 启动 — {len(symbols)} 币种 × {len(intervals)} 周期 × {len(MARKET_TYPES)} 市场 = {total} 个缓存对")

    while True:
        now = time.time()
        _updater_status["lastRun"] = now

        for symbol in symbols:
            for interval in intervals:
                for market_type in MARKET_TYPES:
                    ttl = get_poll_interval(interval)
                    key_tuple = (symbol, interval, market_type)
                    last = last_update.get(key_tuple, 0)
                    if now - last < ttl:
                        continue

                    try:
                        _update_one(symbol, interval, market_type=market_type)
                        last_update[key_tuple] = time.time()
                        key = f"{symbol}:{interval}:{market_type}"
                        _updater_status["stats"][key] = {
                            "lastRun": last_update[key_tuple],
                            "error": None,
                        }
                    except Exception as e:
                        key = f"{symbol}:{interval}:{market_type}"
                        _updater_status["stats"][key] = {
                            "lastRun": last_update.get(key_tuple, 0),
                            "error": str(e),
                        }
                        _updater_status["lastError"] = f"{symbol} {interval} {market_type}: {e}"
                        print(f"[updater] {symbol} {interval} {market_type} error: {e}")

        shortest_ttl = min(get_poll_interval(iv) for iv in intervals)
        time.sleep(max(min_sleep, shortest_ttl // 2))


def start_updater(symbols=None, intervals=None):
    """启动后台更新线程（daemon），立即返回。"""
    t = threading.Thread(target=_updater_loop, args=(symbols, intervals), daemon=True)
    t.start()
    return t


def get_updater_status():
    return dict(_updater_status)
