"""技术指标计算 — MACD、背驰检测"""


def compute_macd(closes, fast=12, slow=26, signal=9):
    """计算 MACD 指标。

    参数：
        closes: 收盘价列表
        fast: 快线周期（默认 12）
        slow: 慢线周期（默认 26）
        signal: 信号线周期（默认 9）

    返回：
        dict: { dif: [...], dea: [...], histogram: [...] }
    """
    if not closes:
        return {"dif": [], "dea": [], "histogram": []}

    def ema(data, period):
        k = 2.0 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i] * k + result[i - 1] * (1 - k))
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = ema(dif, signal)
    histogram = [(d - e) * 2 for d, e in zip(dif, dea)]

    return {"dif": dif, "dea": dea, "histogram": histogram}


def compute_macd_area(histogram, from_idx, to_idx):
    """计算 MACD 柱状图在 [from_idx, to_idx] 区间内的面积（绝对值之和）。

    参数：
        histogram: MACD 柱状图数据
        from_idx: 起始索引（含）
        to_idx: 结束索引（含）

    返回：
        float: 区间内柱状图的绝对值之和
    """
    start = min(from_idx, to_idx)
    end = max(from_idx, to_idx)
    return sum(abs(histogram[i]) for i in range(start, end + 1))


def detect_divergences(klines, turning_points, fractals, buy_sell_points):
    """检测背驰（缠论笔级别）。

    逻辑与前端 detectDivergences() 一致：
    - 在买卖点位置，向前寻找同方向的前一个极值点
    - 比较 MACD 面积：当前段面积 < 前一段面积 → 背驰

    参数：
        klines: K 线数据列表
        turning_points: 转折点价格列表
        fractals: 分型列表（含 klineIdx 字段）
        buy_sell_points: 买卖点列表（含 idx, type 字段）

    返回：
        list[dict]: [{ type, idx, compareIdx, klineIdx, compareKlineIdx }]
    """
    if not klines or not fractals or not buy_sell_points:
        return []

    closes = [k["close"] for k in klines]
    macd = compute_macd(closes)
    histogram = macd["histogram"]
    tp_kline_idx = [f["klineIdx"] for f in fractals]

    # 分离峰和谷
    peaks = []
    valleys = []
    for i in range(1, len(turning_points) - 1):
        if turning_points[i] > turning_points[i - 1] and turning_points[i] > turning_points[i + 1]:
            peaks.append(i)
        if turning_points[i] < turning_points[i - 1] and turning_points[i] < turning_points[i + 1]:
            valleys.append(i)

    def prev_peak_before(idx):
        for i in range(len(peaks) - 1, -1, -1):
            if peaks[i] < idx:
                return peaks[i]
        return None

    def prev_valley_before(idx):
        for i in range(len(valleys) - 1, -1, -1):
            if valleys[i] < idx:
                return valleys[i]
        return None

    results = []

    for point in buy_sell_points:
        i = point["idx"]
        if i >= len(tp_kline_idx) or tp_kline_idx[i] is None:
            continue

        if point["type"] == "buy":
            # 底背驰：找前一个谷 j，要求 price[j] > price[i]
            for vi in range(len(valleys) - 1, -1, -1):
                j = valleys[vi]
                if j >= i:
                    continue
                if turning_points[j] <= turning_points[i]:
                    continue
                if j >= len(tp_kline_idx) or tp_kline_idx[j] is None:
                    continue
                peak_before_i = prev_peak_before(i)
                peak_before_j = prev_peak_before(j)
                kl_start_i = tp_kline_idx[peak_before_i] if peak_before_i is not None else 0
                kl_start_j = tp_kline_idx[peak_before_j] if peak_before_j is not None else 0
                area_i = compute_macd_area(histogram, kl_start_i, tp_kline_idx[i])
                area_j = compute_macd_area(histogram, kl_start_j, tp_kline_idx[j])
                if area_i < area_j:
                    results.append({
                        "type": "bottom",
                        "idx": i,
                        "compareIdx": j,
                        "klineIdx": tp_kline_idx[i],
                        "compareKlineIdx": tp_kline_idx[j],
                    })
                break
        else:
            # 顶背驰：找前一个峰 j，要求 price[j] < price[i]
            for pi in range(len(peaks) - 1, -1, -1):
                j = peaks[pi]
                if j >= i:
                    continue
                if turning_points[j] >= turning_points[i]:
                    continue
                if j >= len(tp_kline_idx) or tp_kline_idx[j] is None:
                    continue
                valley_before_i = prev_valley_before(i)
                valley_before_j = prev_valley_before(j)
                kl_start_i = tp_kline_idx[valley_before_i] if valley_before_i is not None else 0
                kl_start_j = tp_kline_idx[valley_before_j] if valley_before_j is not None else 0
                area_i = compute_macd_area(histogram, kl_start_i, tp_kline_idx[i])
                area_j = compute_macd_area(histogram, kl_start_j, tp_kline_idx[j])
                if area_i < area_j:
                    results.append({
                        "type": "top",
                        "idx": i,
                        "compareIdx": j,
                        "klineIdx": tp_kline_idx[i],
                        "compareKlineIdx": tp_kline_idx[j],
                    })
                break

    return results
