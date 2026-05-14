"""缠论标注工具 Flask 后端"""

import sys
import os

# 确保能找到 chanlun 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, render_template
from chanlun.algorithms import (
    compute_auto_segments,
    compute_auto_zhongshu,
    compute_manual_zhongshu,
    compute_segment_zhongshu,
    compute_higher_segments,
    compute_buy_sell_points,
    build_strokes,
    build_segment_details,
)
from chanlun.binance_service import (
    fetch_klines,
    detect_fractals_from_klines,
    fractals_to_turning_points,
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/compute/strokes", methods=["POST"])
def api_strokes():
    """从 K 线数据自动检测分型 → 笔（转折点）。支持传入已有 klines 或重新 fetch。"""
    data = request.get_json() or {}

    # 优先使用传入的 klines
    klines = data.get("klines")
    if not klines:
        symbol = data.get("symbol", "BTCUSDT").upper()
        interval = data.get("interval", "4h")
        limit = data.get("limit", 200)
        try:
            klines = fetch_klines(symbol, interval, limit, data.get("startTime"), data.get("endTime"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"获取 Binance 数据失败: {str(e)}"}), 502

    if len(klines) < 3:
        return jsonify({"error": "K线数据不足（至少需要3条）"}), 400

    min_kline_gap = data.get("minKlineGap", 4)

    fractals = detect_fractals_from_klines(klines)
    turning_points, filtered_fractals = fractals_to_turning_points(fractals, min_kline_gap)
    strokes = build_strokes(turning_points)

    return jsonify({
        "fractals": filtered_fractals,
        "turningPoints": [round(p, 2) for p in turning_points],
        "strokes": strokes,
    })


@app.route("/api/compute/segments", methods=["POST"])
def api_segments():
    """从转折点自动画段"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    segments = compute_auto_segments(tp, min_segment_ratio)
    return jsonify({"segments": segments})


@app.route("/api/compute/zhongshu", methods=["POST"])
def api_zhongshu():
    """从转折点自动画中枢（段内检测）"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    segments = compute_auto_segments(tp, min_segment_ratio)
    zhongshu = compute_auto_zhongshu(tp, segments)
    return jsonify({"zhongshu": zhongshu})


@app.route("/api/compute/segment-level", methods=["POST"])
def api_segment_level():
    """计算段中枢和段的段"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    segments = compute_auto_segments(tp, min_segment_ratio)
    higher_segments = compute_higher_segments(tp, segments, min_segment_ratio)
    seg_zhongshu = compute_segment_zhongshu(tp, segments, higher_segments)

    return jsonify({
        "segmentZhongshu": seg_zhongshu,
        "higherSegments": higher_segments,
    })


@app.route("/api/compute/manual-zhongshu", methods=["POST"])
def api_manual_zhongshu():
    """手动画中枢时计算 ZG/ZD"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    from_idx = data.get("fromIdx")
    to_idx = data.get("toIdx")

    if not tp or from_idx is None or to_idx is None:
        return jsonify({"error": "turningPoints, fromIdx, toIdx required"}), 400

    result = compute_manual_zhongshu(tp, from_idx, to_idx)
    if result is None:
        return jsonify({"zhongshu": None, "message": "选择的笔之间没有重叠区域"})

    return jsonify({"zhongshu": result})


@app.route("/api/compute/buy-sell", methods=["POST"])
def api_buy_sell():
    """从转折点自动检测笔级别买卖点"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    segments = compute_auto_segments(tp, min_segment_ratio)
    zhongshu = compute_auto_zhongshu(tp, segments)
    buy_sell_points = compute_buy_sell_points(tp, zhongshu)
    return jsonify({"buySellPoints": buy_sell_points})


@app.route("/api/compute/all", methods=["POST"])
def api_compute_all():
    """Binance K线 → 分型 → 笔 → 段 → 中枢（一次性）"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    interval = data.get("interval", "4h")
    limit = data.get("limit", 200)
    start_time = data.get("startTime")
    end_time = data.get("endTime")
    min_segment_ratio = data.get("minSegmentRatio", 0.05)
    min_kline_gap = data.get("minKlineGap", 4)

    try:
        klines = fetch_klines(symbol, interval, limit, start_time, end_time)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"获取 Binance 数据失败: {str(e)}"}), 502

    if len(klines) < 3:
        return jsonify({"error": "K线数据不足（至少需要3条）"}), 400

    fractals = detect_fractals_from_klines(klines)
    turning_points, filtered_fractals = fractals_to_turning_points(fractals, min_kline_gap)

    if len(turning_points) < 4:
        # 分型太少，无法画段/中枢
        return jsonify({
            "symbol": symbol,
            "interval": interval,
            "klines": klines,
            "fractals": filtered_fractals,
            "turningPoints": turning_points,
            "strokes": build_strokes(turning_points),
            "segments": [],
            "zhongshu": [],
            "warning": f"仅检测到 {len(turning_points)} 个转折点，不足以自动画段",
        })

    segments = compute_auto_segments(turning_points, min_segment_ratio)
    zhongshu = compute_auto_zhongshu(turning_points, segments)
    higher_segments = compute_higher_segments(turning_points, segments, min_segment_ratio)
    seg_zhongshu = compute_segment_zhongshu(turning_points, segments, higher_segments)
    buy_sell_points = compute_buy_sell_points(turning_points, zhongshu)
    strokes = build_strokes(turning_points)

    return jsonify({
        "symbol": symbol,
        "interval": interval,
        "klines": klines,
        "fractals": filtered_fractals,
        "turningPoints": [round(p, 2) for p in turning_points],
        "strokes": strokes,
        "segments": segments,
        "zhongshu": zhongshu,
        "segmentZhongshu": seg_zhongshu,
        "higherSegments": higher_segments,
        "buySellPoints": buy_sell_points,
    })


@app.route("/api/compute/export", methods=["POST"])
def api_export():
    """构建导出 JSON"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    user_segments = data.get("segments", [])
    user_zhongshu = data.get("zhongshu", [])
    klines = data.get("klines")
    symbol = data.get("symbol")
    interval = data.get("interval")

    strokes = build_strokes(tp)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)
    seg_indices = compute_auto_segments(tp, min_segment_ratio)
    auto_segments = build_segment_details(tp, seg_indices)
    auto_zhongshu = compute_auto_zhongshu(tp, seg_indices)

    # Build user segments with details
    user_seg_details = []
    for seg in user_segments:
        fi = seg.get("fromIdx", 0)
        ti = seg.get("toIdx", 0)
        if fi < len(tp) and ti < len(tp):
            user_seg_details.append({
                "from": tp[fi],
                "to": tp[ti],
                "dir": "up" if tp[ti] > tp[fi] else "down",
                "fromIdx": fi,
                "toIdx": ti,
            })

    result = {
        "source": "binance" if klines else "random",
        "turningPoints": tp,
        "strokes": strokes,
        "autoSegments": auto_segments,
        "segments": user_seg_details,
        "autoZhongshu": auto_zhongshu,
        "zhongshu": user_zhongshu,
    }

    if klines:
        result["symbol"] = symbol
        result["interval"] = interval
        result["klines"] = klines

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
