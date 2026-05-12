"""Binance K线获取 + 顶底分型检测"""

import requests

BINANCE_BASE = "https://api.binance.com/api/v3/klines"
VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}


def fetch_klines(symbol, interval, limit=500, start_time=None, end_time=None):
    """从 Binance 公共 API 获取 K 线数据，无需 API key。
    返回 [{"openTime", "open", "high", "low", "close", "volume", "closeTime"}, ...]
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Invalid interval. Must be one of: {', '.join(sorted(VALID_INTERVALS))}")

    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": min(limit, 1000),
    }
    if start_time is not None:
        params["startTime"] = int(start_time)
    if end_time is not None:
        params["endTime"] = int(end_time)

    resp = requests.get(BINANCE_BASE, params=params, timeout=10)
    if resp.status_code == 400:
        data = resp.json()
        raise ValueError(data.get("msg", "Bad request"))
    resp.raise_for_status()

    raw = resp.json()
    klines = []
    for item in raw:
        klines.append({
            "openTime": item[0],
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "closeTime": item[6],
        })
    return klines


def detect_fractals_from_klines(klines):
    """从 K 线 OHLC 数据检测顶分型和底分型。
    顶分型: klines[i].high > klines[i-1].high AND klines[i].high > klines[i+1].high
    底分型: klines[i].low < klines[i-1].low AND klines[i].low < klines[i+1].low
    返回 [{"klineIdx", "type", "price", "time"}, ...]
    """
    if len(klines) < 3:
        return []

    fractals = []
    for i in range(1, len(klines) - 1):
        is_top = (klines[i]["high"] > klines[i - 1]["high"] and
                  klines[i]["high"] > klines[i + 1]["high"])
        is_bottom = (klines[i]["low"] < klines[i - 1]["low"] and
                     klines[i]["low"] < klines[i + 1]["low"])

        if is_top and is_bottom:
            # 两边都是，看哪个差距更大
            top_gap = klines[i]["high"] - max(klines[i - 1]["high"], klines[i + 1]["high"])
            bottom_gap = min(klines[i - 1]["low"], klines[i + 1]["low"]) - klines[i]["low"]
            if top_gap >= bottom_gap:
                is_bottom = False
            else:
                is_top = False

        if is_top:
            fractals.append({
                "klineIdx": i,
                "type": "top",
                "price": klines[i]["high"],
                "time": klines[i]["openTime"],
            })
        elif is_bottom:
            fractals.append({
                "klineIdx": i,
                "type": "bottom",
                "price": klines[i]["low"],
                "time": klines[i]["openTime"],
            })

    return fractals


def fractals_to_turning_points(fractals):
    """将分型列表转为转折点价格序列，确保严格交替。
    连续顶分型取最高，连续底分型取最低。
    返回 (turning_points, filtered_fractals)
    """
    if not fractals:
        return [], []

    # 合并连续同类型分型
    filtered = [fractals[0]]
    for f in fractals[1:]:
        prev = filtered[-1]
        if f["type"] == prev["type"]:
            # 同类型，保留更极端的
            if f["type"] == "top" and f["price"] > prev["price"]:
                filtered[-1] = f
            elif f["type"] == "bottom" and f["price"] < prev["price"]:
                filtered[-1] = f
        else:
            filtered.append(f)

    turning_points = [f["price"] for f in filtered]
    return turning_points, filtered
