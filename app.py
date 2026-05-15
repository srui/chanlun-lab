"""缠论标注工具 Flask 后端"""

import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    fetch_klines_range,
    detect_fractals_from_klines,
    fractals_to_turning_points,
)
from chanlun.pipeline import analyze_klines, recompute_from_turning_points
from chanlun.config import get_context_interval, get_poll_interval, PREFETCH_INTERVALS, PREFETCH_DAYS
from chanlun.annotation_store import save_annotation, load_annotation, clear_annotation
from chanlun.signal import compute_signal
from chanlun.analysis_cache import get_cached_analysis, save_analysis, get_cache_status
from chanlun.background_updater import start_updater, get_updater_status
from chanlun.watchlist_store import get_watchlist as wl_get, add_symbol as wl_add, remove_symbol as wl_remove

app = Flask(__name__)

# 预热状态
_prefetch_status = {"symbols": {}, "complete": False}

MARKET_TYPES = ["spot", "futures"]


def prefetch_symbol(symbol):
    """后台线程：拉取 60 天 × 所有周期 × 现货+合约 的 K 线数据，然后跑分析缓存。"""
    sym_status = {}
    for iv in PREFETCH_INTERVALS:
        sym_status[iv] = "pending"
    _prefetch_status["symbols"][symbol] = sym_status

    def _fetch_one(iv, mt):
        key = f"{iv}:{mt}"
        sym_status[key] = "pending"
        try:
            klines, ok = fetch_klines_range(symbol, iv, days=PREFETCH_DAYS, market_type=mt)
            sym_status[key] = "done" if ok else "failed"
            return (iv, mt, klines if ok else [])
        except Exception as e:
            print(f"[prefetch] {symbol} {iv} {mt} 异常: {e}")
            sym_status[key] = "failed"
            return (iv, mt, [])

    # 并发拉取所有 周期×市场 组合
    tasks = [(iv, mt) for iv in PREFETCH_INTERVALS for mt in MARKET_TYPES]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_fetch_one, iv, mt) for iv, mt in tasks]
        results = [f.result() for f in as_completed(futures)]

    # 拉完后用已有 klines 跑分析管线并缓存（不重复拉取）
    for iv, mt, klines in results:
        if len(klines) >= 3:
            try:
                primary = analyze_klines(klines)
                primary["symbol"] = symbol
                primary["interval"] = iv
                primary["klines"] = klines

                context_interval = get_context_interval(iv)
                context = None
                if context_interval:
                    ctx_limit = 75
                    try:
                        ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit, market_type=mt)
                    except Exception:
                        ctx_klines = []
                    if len(ctx_klines) >= 3:
                        context = analyze_klines(ctx_klines)
                        context["symbol"] = symbol
                        context["interval"] = context_interval
                        context["klines"] = ctx_klines

                signal = compute_signal(primary, context)
                save_analysis(symbol, iv, {"primary": primary, "context": context, "signal": signal}, market_type=mt)
            except Exception as e:
                print(f"[prefetch] {symbol} {iv} {mt} 分析失败: {e}")

    print(f"[prefetch] {symbol} 完成")


@app.route("/api/prefetch/status", methods=["GET"])
def api_prefetch_status():
    """返回预热进度。"""
    return jsonify(_prefetch_status)


@app.route("/api/watchlist", methods=["GET"])
def api_watchlist_get():
    """返回当前自选币种列表。"""
    return jsonify({"symbols": wl_get()})


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    """添加币种到自选，并异步拉取 60 天全量数据。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol 不能为空"}), 400

    added = wl_add(symbol)
    if not added:
        return jsonify({"ok": True, "message": "币种已存在", "symbols": wl_get()})

    # 异步拉取全量数据
    t = threading.Thread(target=prefetch_symbol, args=(symbol,), daemon=True)
    t.start()
    print(f"[watchlist] 新增 {symbol}，后台拉取已启动")

    return jsonify({"ok": True, "message": "已添加，正在后台拉取数据", "symbols": wl_get()})


@app.route("/api/watchlist/remove", methods=["POST"])
def api_watchlist_remove():
    """从自选移除币种。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol 不能为空"}), 400

    removed = wl_remove(symbol)
    return jsonify({"ok": removed, "symbols": wl_get()})


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/chart")
def chart():
    return render_template("chart.html")


@app.route("/watchlist")
def watchlist():
    return render_template("watchlist.html")


@app.route("/signals")
def signals():
    return render_template("signals.html")


@app.route("/multi-tf")
def multi_tf():
    return render_template("multi-tf.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


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
            klines = fetch_klines(symbol, interval, limit, data.get("startTime"), data.get("endTime"), market_type=data.get("marketType", "spot"))
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


@app.route("/api/compute/analyze", methods=["POST"])
def api_analyze():
    """接收 K 线数组，运行完整分析流水线，返回全部分析结果。"""
    data = request.get_json() or {}
    klines = data.get("klines")

    if not klines or len(klines) < 3:
        return jsonify({"error": "K线数据不足（至少需要3条）"}), 400

    min_kline_gap = data.get("minKlineGap", 4)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)

    result = analyze_klines(klines, min_kline_gap, min_segment_ratio)
    return jsonify(result)


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
        klines = fetch_klines(symbol, interval, limit, start_time, end_time, market_type=data.get("marketType", "spot"))
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
    """双周期分析：主周期 + 上下文周期。优先返回缓存。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    primary_interval = data.get("interval", "15m")
    limit = data.get("limit", 300)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)
    min_kline_gap = data.get("minKlineGap", 4)
    market_type = data.get("marketType", "spot")

    # 尝试缓存
    ttl = get_poll_interval(primary_interval)
    cached = get_cached_analysis(symbol, primary_interval, ttl, market_type=market_type)
    if cached is not None:
        return jsonify({"primary": cached["primary"], "context": cached.get("context")})

    # 缓存未命中 — 跑管线
    context_interval = data.get("contextInterval") or get_context_interval(primary_interval)

    try:
        primary_klines = fetch_klines_cached(symbol, primary_interval, limit, market_type=market_type)
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
            ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit, market_type=market_type)
        except Exception:
            ctx_klines = []

        if len(ctx_klines) >= 3:
            context = analyze_klines(ctx_klines, min_kline_gap, min_segment_ratio)
            context["symbol"] = symbol
            context["interval"] = context_interval
            context["klines"] = ctx_klines

    # 存缓存
    save_analysis(symbol, primary_interval, {
        "primary": primary,
        "context": context,
        "signal": compute_signal(primary, context),
    }, market_type=market_type)

    return jsonify({"primary": primary, "context": context})


@app.route("/api/klines/older", methods=["GET"])
def api_klines_older():
    """从缓存加载更早的 K 线数据，用于前端增量加载。

    参数：
        symbol: 交易对
        interval: 周期
        beforeTime: 加载此时间戳之前的 K 线
        count: 请求数量（默认 500）
    """
    from chanlun.kline_cache import get_cached_klines

    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "4h")
    before_time = request.args.get("beforeTime", type=int)
    count = request.args.get("count", 500, type=int)
    market_type = request.args.get("marketType", "spot")

    if before_time is None:
        return jsonify({"error": "beforeTime required"}), 400

    klines = get_cached_klines(symbol, interval, end_ms=before_time - 1, market_type=market_type)
    # 取最后 count 根（最接近 beforeTime 的）
    if len(klines) > count:
        klines = klines[-count:]

    return jsonify({"klines": klines, "count": len(klines)})


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
    """计算区间套信号状态。优先返回缓存。"""
    data = request.get_json() or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    interval = data.get("interval", "4h")
    limit = data.get("limit", 300)
    min_kline_gap = data.get("minKlineGap", 4)
    min_segment_ratio = data.get("minSegmentRatio", 0.05)
    market_type = data.get("marketType", "spot")

    # 尝试缓存
    ttl = get_poll_interval(interval)
    cached = get_cached_analysis(symbol, interval, ttl, market_type=market_type)
    if cached is not None:
        return jsonify({"signal": cached["signal"]})

    # 缓存未命中 — 跑管线
    try:
        primary_klines = fetch_klines_cached(symbol, interval, limit, market_type=market_type)
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
            ctx_klines = fetch_klines_cached(symbol, context_interval, ctx_limit, market_type=market_type)
        except Exception:
            ctx_klines = []

        if len(ctx_klines) >= 3:
            context = analyze_klines(ctx_klines, min_kline_gap, min_segment_ratio)
            context["symbol"] = symbol
            context["interval"] = context_interval

    signal = compute_signal(primary, context)

    # 存缓存
    save_analysis(symbol, interval, {
        "primary": primary,
        "context": context,
        "signal": signal,
    }, market_type=market_type)

    return jsonify({"signal": signal})


@app.route("/api/price", methods=["GET"])
def api_price():
    """返回最新K线价格（轻量接口，不跑分析管线）。"""
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "4h")
    market_type = request.args.get("marketType", "spot")

    try:
        klines = fetch_klines_cached(symbol, interval, 2, market_type=market_type)
    except Exception as e:
        return jsonify({"error": f"获取价格失败: {str(e)}"}), 502

    if not klines:
        return jsonify({"error": "无数据"}), 404

    last = klines[-1]
    prev = klines[-2] if len(klines) > 1 else last
    change_pct = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0

    return jsonify({
        "symbol": symbol,
        "interval": interval,
        "price": last["close"],
        "high": last["high"],
        "low": last["low"],
        "volume": last["volume"],
        "openTime": last["openTime"],
        "change": round(change_pct, 4),
    })


@app.route("/api/config/poll-interval", methods=["GET"])
def api_poll_interval():
    """返回指定周期的推荐轮询间隔（秒）。"""
    interval = request.args.get("interval", "4h")
    return jsonify({"interval": interval, "pollSeconds": get_poll_interval(interval)})


@app.route("/api/cache/status", methods=["GET"])
def api_cache_status():
    """返回分析缓存状态和后台更新器信息。"""
    return jsonify({
        "cache": get_cache_status(),
        "updater": get_updater_status(),
    })


if __name__ == "__main__":
    import os as _os
    if _os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        start_updater()
        print("[updater] 后台分析缓存更新已启动（仅更新自选币种）...")

    app.run(debug=True, port=5000)
