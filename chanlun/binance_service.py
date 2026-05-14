"""Binance K线获取 + 包含关系处理 + 顶底分型检测"""

import requests

BINANCE_BASE = "https://api.binance.com/api/v3/klines"
VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}


def _has_inclusion(k1, k2):
    """判断两根K线是否存在包含关系。
    包含 = 一根K线的高低点完全包含另一根的高低点。
    """
    return (k1["high"] >= k2["high"] and k1["low"] <= k2["low"]) or \
           (k2["high"] >= k1["high"] and k2["low"] <= k1["low"])


def merge_klines_with_inclusion(klines):
    """处理K线包含关系，返回合并后的K线序列。

    规则：
    - 上升趋势中（前一根 high > 更前一根 high），合并取高高+高低（向上合并）
    - 下降趋势中（前一根 low < 更前一根 low），合并取低低+低高（向下合并）
    - 第一根无法判断趋势时，默认向下合并

    合并后的K线保留原始K线的索引信息：
    - highIdx: high 价格对应的原始K线索引（用于顶分型定位）
    - lowIdx: low 价格对应的原始K线索引（用于底分型定位）
    """
    if len(klines) < 2:
        return list(klines)

    merged = [dict(klines[0], originalIdx=0, highIdx=0, lowIdx=0)]

    for i in range(1, len(klines)):
        cur = klines[i]
        prev = merged[-1]

        if not _has_inclusion(prev, cur):
            # 无包含关系，直接追加
            merged.append(dict(cur, originalIdx=i, highIdx=i, lowIdx=i))
            continue

        # 存在包含关系，需要合并
        # 判断趋势方向：看 merged 中最后两根
        if len(merged) >= 2:
            prev2 = merged[-2]
            # 上升趋势：前一根 high > 更前一根 high
            if prev["high"] > prev2["high"]:
                # 向上合并：取更高的 high 和更高的 low
                new_high = max(prev["high"], cur["high"])
                new_low = max(prev["low"], cur["low"])
            else:
                # 向下合并：取更低的 low 和更低的 high
                new_high = min(prev["high"], cur["high"])
                new_low = min(prev["low"], cur["low"])
        else:
            # 只有一根，默认向下合并
            new_high = min(prev["high"], cur["high"])
            new_low = min(prev["low"], cur["low"])

        # 跟踪 high/low 分别来自哪根原始K线
        # 根据合并方向判断：new_high/new_low 是 max 还是 min 决定用哪个比较
        prev_high_idx = prev.get("highIdx", prev.get("originalIdx", i - 1))
        prev_low_idx = prev.get("lowIdx", prev.get("originalIdx", i - 1))
        # high 来源：new_high == cur.high 则来自 cur，否则来自 prev
        high_idx = i if new_high == cur["high"] else prev_high_idx
        # low 来源：new_low == cur.low 则来自 cur，否则来自 prev
        low_idx = i if new_low == cur["low"] else prev_low_idx

        # 使用实际产生 extreme price 的K线的时间
        high_time = klines[high_idx]["openTime"]
        low_time = klines[low_idx]["openTime"]

        merged[-1] = {
            "openTime": prev["openTime"],
            "open": prev["open"],
            "high": new_high,
            "low": new_low,
            "close": cur["close"],
            "volume": prev["volume"] + cur["volume"],
            "closeTime": cur["closeTime"],
            "originalIdx": prev.get("originalIdx", i - 1),
            "highIdx": high_idx,
            "lowIdx": low_idx,
            "highTime": high_time,
            "lowTime": low_time,
        }

    return merged


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


def detect_fractals_from_klines(klines, process_inclusion=True):
    """从 K 线 OHLC 数据检测顶分型和底分型。

    流程：
    1. 可选：先处理K线包含关系（合并后的K线用于分型检测）
    2. 在合并后的K线上检测分型
    3. 验证笔的合法性（相邻分型间至少间隔5根K线，不含分型所在K线）

    顶分型: klines[i].high > klines[i-1].high AND klines[i].high > klines[i+1].high
    底分型: klines[i].low < klines[i-1].low AND klines[i].low < klines[i+1].low
    返回 [{"klineIdx", "type", "price", "time"}, ...]
    """
    if len(klines) < 3:
        return []

    # Step 1: 包含关系处理
    if process_inclusion:
        processed = merge_klines_with_inclusion(klines)
    else:
        processed = klines

    # Step 2: 在处理后的K线上检测分型
    fractals = []
    for i in range(1, len(processed) - 1):
        is_top = (processed[i]["high"] > processed[i - 1]["high"] and
                  processed[i]["high"] > processed[i + 1]["high"])
        is_bottom = (processed[i]["low"] < processed[i - 1]["low"] and
                     processed[i]["low"] < processed[i + 1]["low"])

        if is_top and is_bottom:
            top_gap = processed[i]["high"] - max(processed[i - 1]["high"], processed[i + 1]["high"])
            bottom_gap = min(processed[i - 1]["low"], processed[i + 1]["low"]) - processed[i]["low"]
            if top_gap >= bottom_gap:
                is_bottom = False
            else:
                is_top = False

        if is_top:
            # 使用实际产生 high 价格的K线索引和时间
            kidx = processed[i].get("highIdx", processed[i].get("originalIdx", i))
            ftime = processed[i].get("highTime", processed[i]["openTime"])
            fractals.append({
                "klineIdx": kidx,
                "type": "top",
                "price": processed[i]["high"],
                "time": ftime,
            })
        elif is_bottom:
            # 使用实际产生 low 价格的K线索引和时间
            kidx = processed[i].get("lowIdx", processed[i].get("originalIdx", i))
            ftime = processed[i].get("lowTime", processed[i]["openTime"])
            fractals.append({
                "klineIdx": kidx,
                "type": "bottom",
                "price": processed[i]["low"],
                "time": ftime,
            })

    return fractals


def fractals_to_turning_points(fractals, min_kline_gap=4):
    """将分型列表转为转折点价格序列，使用贪心zigzag算法。

    算法：逐个处理分型，同时处理同类型合并、间距约束和zigzag约束。
    1. 同类型分型：更新为更极端的值（顶取最高，底取最低）
    2. 不同类型分型：检查间距 >= min_kline_gap 且满足zigzag（顶>底，底<顶）

    返回 (turning_points, filtered_fractals)
    """
    if not fractals:
        return [], []

    if min_kline_gap <= 0 or len(fractals) <= 1:
        turning_points = [f["price"] for f in fractals]
        return turning_points, list(fractals)

    result = [fractals[0]]

    for f in fractals[1:]:
        prev = result[-1]

        if f["type"] == prev["type"]:
            # 同类型分型：保留更极端的
            if f["type"] == "top" and f["price"] > prev["price"]:
                result[-1] = f
            elif f["type"] == "bottom" and f["price"] < prev["price"]:
                result[-1] = f
        else:
            # 不同类型分型：检查间距
            gap = abs(f["klineIdx"] - prev["klineIdx"]) - 1
            if gap < min_kline_gap:
                continue
            # 检查zigzag约束
            if prev["type"] == "bottom" and f["price"] <= prev["price"]:
                continue
            if prev["type"] == "top" and f["price"] >= prev["price"]:
                continue
            # 有效转折点
            result.append(f)

    turning_points = [f["price"] for f in result]
    return turning_points, result
