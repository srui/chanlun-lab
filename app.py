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
    fetch_klines_cached,
    detect_fractals_from_klines,
    fractals_to_turning_points,
)
from chanlun.pipeline import analyze_klines, recompute_from_turning_points
from chanlun.config import get_context_interval, get_poll_interval
from chanlun.annotation_store import save_annotation, load_annotation, clear_annotation
from chanlun.signal import compute_signal

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


@app.route("/api/compute/recompute", methods=["POST"])
def api_recompute():
    """一次性重算段、中枢、段中枢、高级段、买卖点"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    return jsonify(recompute_from_turning_points(tp, min_segment_ratio))


@app.route("/api/compute/zhongshu", methods=["POST"])
def api_zhongshu():
    """从转折点自动画中枢（段内检测）"""
    data = request.get_json() or {}
    tp = data.get("turningPoints", [])
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    if len(tp) < 4:
        return jsonify({"error": "至少需要4个转折点"}), 400

    segments = data.get("segments") or compute_auto_segments(tp, min_segment_ratio)
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

    segments = data.get("segments") or compute_auto_segments(tp, min_segment_ratio)
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

    segments = data.get("segments") or compute_auto_segments(tp, min_segment_ratio)
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

    result = analyze_klines(klines, min_kline_gap, min_segment_ratio)
    result["symbol"] = symbol
    result["interval"] = interval
    result["klines"] = klines
    return jsonify(result)


@app.route("/api/compute/dual", methods=["POST"])
def api_compute_dual():
    """双周期分析：主周期 + 上下文周期，返回两组分析结果。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    primary_interval = data.get("interval", "15m")
    limit = data.get("limit", 300)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)
    min_kline_gap = data.get("minKlineGap", 4)

    context_interval = data.get("contextInterval") or get_context_interval(primary_interval)

    try:
        primary_klines = fetch_klines_cached(symbol, primary_interval, limit)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"获取主周期数据失败: {str(e)}"}), 502

    if len(primary_klines) < 3:
        return jsonify({"error": "主周期K线数据不足（至少需要3条）"}), 400

    primary = analyze_klines(primary_klines, min_kline_gap, min_segment_ratio)
    primary["symbol"] = symbol
    primary["interval"] = primary_interval
    primary["klines"] = primary_klines

    context = None
    if context_interval:
        ctx_limit = max(50, limit // 4)
        try:
            ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit)
        except Exception:
            ctx_klines = []

        if len(ctx_klines) >= 3:
            context = analyze_klines(ctx_klines, min_kline_gap, min_segment_ratio)
            context["symbol"] = symbol
            context["interval"] = context_interval
            context["klines"] = ctx_klines

    return jsonify({"primary": primary, "context": context})


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


@app.route("/api/annotation/save", methods=["POST"])
def api_annotation_save():
    """保存标注数据"""
    data = request.get_json() or {}
    symbol = data.get("symbol")
    interval = data.get("interval")
    if not symbol or not interval:
        return jsonify({"error": "symbol and interval required"}), 400
    save_annotation(symbol, interval, data)
    return jsonify({"ok": True})


@app.route("/api/annotation/load", methods=["GET"])
def api_annotation_load():
    """加载标注数据"""
    symbol = request.args.get("symbol")
    interval = request.args.get("interval")
    if not symbol or not interval:
        return jsonify({"error": "symbol and interval required"}), 400
    data = load_annotation(symbol, interval)
    if data is None:
        return jsonify({"annotation": None})
    return jsonify({"annotation": data})


@app.route("/api/annotation/clear", methods=["DELETE"])
def api_annotation_clear():
    """清除标注数据"""
    symbol = request.args.get("symbol")
    interval = request.args.get("interval")
    if not symbol or not interval:
        return jsonify({"error": "symbol and interval required"}), 400
    clear_annotation(symbol, interval)
    return jsonify({"ok": True})


@app.route("/api/signal", methods=["POST"])
def api_signal():
    """计算区间套信号状态。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    interval = data.get("interval", "4h")
    limit = data.get("limit", 300)
    min_kline_gap = data.get("minKlineGap", 4)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    try:
        primary_klines = fetch_klines_cached(symbol, interval, limit)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"获取主周期数据失败: {str(e)}"}), 502

    if len(primary_klines) < 3:
        return jsonify({"error": "主周期K线数据不足"}), 400

    primary = analyze_klines(primary_klines, min_kline_gap, min_segment_ratio)
    primary["symbol"] = symbol
    primary["interval"] = interval
    primary["klines"] = primary_klines

    # 获取上下文周期
    context_interval = data.get("contextInterval") or get_context_interval(interval)
    context = None
    if context_interval:
        ctx_limit = max(50, limit // 4)
        try:
            ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit)
        except Exception:
            ctx_klines = []

        if len(ctx_klines) >= 3:
            context = analyze_klines(ctx_klines, min_kline_gap, min_segment_ratio)
            context["interval"] = context_interval

    signal = compute_signal(primary, context)
    return jsonify({"signal": signal})


@app.route("/api/config/poll-interval", methods=["GET"])
def api_poll_interval():
    """返回指定周期的推荐轮询间隔（秒）。"""
    interval = request.args.get("interval", "4h")
    return jsonify({"interval": interval, "pollSeconds": get_poll_interval(interval)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
