"""区间套信号引擎 — 纯函数，无状态"""

# 状态常量
IDLE = "IDLE"            # 无信号
WATCHING = "WATCHING"    # 发现潜在机会
CONFIRMING = "CONFIRMING"  # 等待入场确认
READY = "READY"          # 可以入场

# 方向常量
LONG = "long"
SHORT = "short"
NEUTRAL = "neutral"


def _get_context_direction(context_result):
    """从上下文周期结果推导大周期方向。

    规则：最新一段的方向决定当前方向。
    无段或无法判断时返回 neutral。
    """
    segments = context_result.get("segments", [])
    if not segments:
        return NEUTRAL

    tp = context_result.get("turningPoints", [])
    if not tp:
        return NEUTRAL

    last_seg = segments[-1]
    from_idx = last_seg["fromIdx"]
    to_idx = last_seg["toIdx"]

    if from_idx >= len(tp) or to_idx >= len(tp):
        return NEUTRAL

    if tp[to_idx] > tp[from_idx]:
        return LONG
    elif tp[to_idx] < tp[from_idx]:
        return SHORT
    return NEUTRAL


def _get_primary_buy_sell(primary_result, direction):
    """获取主周期中与方向匹配的买卖点。

    做多方向找买点，做空方向找卖点。
    """
    buy_sell = primary_result.get("buySellPoints", [])
    if direction == LONG:
        return [p for p in buy_sell if p["type"] == "buy"]
    elif direction == SHORT:
        return [p for p in buy_sell if p["type"] == "sell"]
    return []


def _check_context_invalidated(context_result, direction):
    """检查上下文方向是否已反转（导致信号失效）。

    如果最新段方向与当前跟踪方向相反，则失效。
    """
    current_dir = _get_context_direction(context_result)
    if current_dir == NEUTRAL:
        return False
    return current_dir != direction


def compute_signal(primary_result, context_result=None):
    """计算当前区间套信号状态。

    纯函数，每次调用从数据完整推导当前状态，不依赖历史状态。

    参数：
        primary_result: 主周期分析结果（来自 pipeline.analyze_klines）
        context_result: 上下文周期分析结果（可选，无则为单周期模式）

    返回：
        dict: {
            direction: "long" | "short" | "neutral",
            state: "IDLE" | "WATCHING" | "CONFIRMING" | "READY",
            activeSetup: { ... } | null,
            contextDirection: "long" | "short" | "neutral",
            contextSegments: int,
            primaryZhongshu: int,
            primaryBuySell: int,
        }
    """
    # 基础信息
    if context_result is None:
        context_result = {}

    context_dir = _get_context_direction(context_result)
    context_segments = len(context_result.get("segments", []))
    primary_zhongshu = primary_result.get("zhongshu", [])
    primary_buy_sell = primary_result.get("buySellPoints", [])
    tp = primary_result.get("turningPoints", [])

    result = {
        "direction": NEUTRAL,
        "state": IDLE,
        "activeSetup": None,
        "contextDirection": context_dir,
        "contextSegments": context_segments,
        "primaryZhongshu": len(primary_zhongshu),
        "primaryBuySell": len(primary_buy_sell),
    }

    # 无上下文或上下文方向不明确 → IDLE
    if context_dir == NEUTRAL:
        return result

    direction = context_dir
    result["direction"] = direction

    # 检查失效：上下文段方向反转
    if _check_context_invalidated(context_result, direction):
        result["direction"] = NEUTRAL
        result["state"] = IDLE
        return result

    # 检查失效：价格突破上下文中枢 ZG/ZD
    context_zhongshu = context_result.get("zhongshu", [])
    context_tp = context_result.get("turningPoints", [])
    if context_zhongshu and context_tp:
        last_zs = context_zhongshu[-1]
        last_price = context_tp[-1] if context_tp else None
        if last_price is not None:
            if direction == LONG and last_price < last_zs.get("zd", 0):
                result["direction"] = NEUTRAL
                result["state"] = IDLE
                return result
            elif direction == SHORT and last_price > last_zs.get("zg", float("inf")):
                result["direction"] = NEUTRAL
                result["state"] = IDLE
                return result

    # WATCHING: 上下文方向明确 + 主周期有中枢
    if not primary_zhongshu:
        result["state"] = WATCHING
        return result

    # 获取与方向匹配的买卖点
    matching_points = _get_primary_buy_sell(primary_result, direction)

    # 无匹配买卖点 → WATCHING
    if not matching_points:
        result["state"] = WATCHING
        return result

    # 找最新的有效买卖点
    best_point = matching_points[-1]

    # 检查是否 READY（有背驰确认）
    if best_point.get("hasDivergence", False):
        result["state"] = READY
        result["activeSetup"] = {
            "type": best_point["type"],
            "idx": best_point["idx"],
            "label": best_point.get("label", ""),
            "hasDivergence": True,
            "price": tp[best_point["idx"]] if best_point["idx"] < len(tp) else None,
        }
        return result

    # CONFIRMING: 买卖点已出现但无背驰确认
    result["state"] = CONFIRMING
    result["activeSetup"] = {
        "type": best_point["type"],
        "idx": best_point["idx"],
        "label": best_point.get("label", ""),
        "hasDivergence": False,
        "price": tp[best_point["idx"]] if best_point["idx"] < len(tp) else None,
    }
    return result
