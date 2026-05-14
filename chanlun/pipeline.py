"""缠论分析流水线 — K线到全部分析结果的完整处理"""

from chanlun.algorithms import (
    compute_auto_segments,
    compute_auto_zhongshu,
    compute_segment_zhongshu,
    compute_higher_segments,
    compute_buy_sell_points,
    build_strokes,
)
from chanlun.binance_service import (
    detect_fractals_from_klines,
    fractals_to_turning_points,
)
from chanlun.indicators import compute_macd, detect_divergences


def analyze_klines(klines, min_kline_gap=4, min_segment_ratio=0.05):
    """完整分析流水线：K线 → 分型 → 转折点 → 笔 → 段 → 中枢 → 买卖点。

    参数：
        klines: K 线列表 [{"openTime", "open", "high", "low", "close", "volume", "closeTime"}, ...]
        min_kline_gap: 相邻分型间最少 K 线间隔（默认 4，即 5 根 K 线）
        min_segment_ratio: 段检测的最小价格幅度比

    返回：
        dict: {fractals, turningPoints, strokes, segments, zhongshu,
               segmentZhongshu, higherSegments, buySellPoints}
    """
    fractals = detect_fractals_from_klines(klines)
    turning_points, filtered_fractals = fractals_to_turning_points(fractals, min_kline_gap)

    # MACD 计算（基于收盘价）
    closes = [k["close"] for k in klines]
    macd = compute_macd(closes)

    if len(turning_points) < 4:
        return {
            "fractals": filtered_fractals,
            "turningPoints": [round(p, 2) for p in turning_points],
            "strokes": build_strokes(turning_points),
            "segments": [],
            "zhongshu": [],
            "segmentZhongshu": [],
            "higherSegments": [],
            "buySellPoints": [],
            "macd": macd,
            "divergences": [],
            "warning": f"仅检测到 {len(turning_points)} 个转折点，不足以自动画段",
        }

    segments = compute_auto_segments(turning_points, min_segment_ratio)
    zhongshu = compute_auto_zhongshu(turning_points, segments)
    higher_segments = compute_higher_segments(turning_points, segments, min_segment_ratio)
    seg_zhongshu = compute_segment_zhongshu(turning_points, segments, higher_segments)
    buy_sell_points = compute_buy_sell_points(turning_points, zhongshu)

    # 背驰检测
    divergences = detect_divergences(klines, turning_points, filtered_fractals, buy_sell_points)

    # 给买卖点添加 hasDivergence 标记
    div_by_idx = {d["idx"]: d for d in divergences}
    for bsp in buy_sell_points:
        bsp["hasDivergence"] = bsp["idx"] in div_by_idx

    return {
        "fractals": filtered_fractals,
        "turningPoints": [round(p, 2) for p in turning_points],
        "strokes": build_strokes(turning_points),
        "segments": segments,
        "zhongshu": zhongshu,
        "segmentZhongshu": seg_zhongshu,
        "higherSegments": higher_segments,
        "buySellPoints": buy_sell_points,
        "macd": macd,
        "divergences": divergences,
    }


def recompute_from_turning_points(turning_points, min_segment_ratio=0.05):
    """从转折点开始重新计算（不涉及 K 线和分型，因此无法计算 MACD/背驰）。

    参数：
        turning_points: 转折点价格列表
        min_segment_ratio: 段检测的最小价格幅度比

    返回：
        dict: {segments, zhongshu, segmentZhongshu, higherSegments, buySellPoints, divergences}
    """
    segments = compute_auto_segments(turning_points, min_segment_ratio)
    zhongshu = compute_auto_zhongshu(turning_points, segments)
    higher_segments = compute_higher_segments(turning_points, segments, min_segment_ratio)
    seg_zhongshu = compute_segment_zhongshu(turning_points, segments, higher_segments)
    buy_sell_points = compute_buy_sell_points(turning_points, zhongshu)

    return {
        "segments": segments,
        "zhongshu": zhongshu,
        "segmentZhongshu": seg_zhongshu,
        "higherSegments": higher_segments,
        "buySellPoints": buy_sell_points,
        "divergences": [],
    }
