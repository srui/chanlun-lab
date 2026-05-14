"""缠论核心算法 — 缠论规则线段检测 + PoP回退"""

import random

# ====== 中枢参数 ======
ZS_MAX_EXTEND = 30  # 最大延伸笔数（安全上限，防止异常数据）

# ====== 段参数 ======
MIN_STROKES = 3
MAX_SEGMENT_STROKES = 15  # 超过此笔数的段尝试拆分
VALLEY_EXTEND_TOLERANCE = 0.015  # 谷值延伸容差（1.5% of 全局数据范围）


def _extract_local_extremes(tp):
    """从转折点序列中提取局部极值索引。
    返回 (peak_indices, valley_indices)
    """
    n = len(tp)
    peaks = []
    valleys = []
    for i in range(n):
        if i == 0:
            if n > 1:
                (peaks if tp[0] > tp[1] else valleys).append(0)
        elif i == n - 1:
            if n > 1:
                (peaks if tp[i] > tp[i - 1] else valleys).append(i)
        else:
            if tp[i] > tp[i - 1] and tp[i] > tp[i + 1]:
                peaks.append(i)
            elif tp[i] < tp[i - 1] and tp[i] < tp[i + 1]:
                valleys.append(i)
    return peaks, valleys


def _find_pops(tp, peak_indices):
    """峰之峰：在峰子序列中找局部极大值。"""
    if len(peak_indices) < 3:
        return peak_indices[:]
    vals = [tp[i] for i in peak_indices]
    return [peak_indices[i] for i in range(1, len(vals) - 1)
            if vals[i] > vals[i - 1] and vals[i] > vals[i + 1]]


def _find_vovs(tp, valley_indices):
    """谷之谷：在谷子序列中找局部极小值。"""
    if len(valley_indices) < 3:
        return valley_indices[:]
    vals = [tp[i] for i in valley_indices]
    return [valley_indices[i] for i in range(1, len(vals) - 1)
            if vals[i] < vals[i - 1] and vals[i] < vals[i + 1]]


def _find_valid_valley(tp, valley_indices, pop_a, pop_b):
    """在两个 PoP 之间找满足 MIN_STROKES 约束的最佳谷。
    策略：先找最低有效谷，再延伸到最后一个容差范围内的谷。
    容差基于全局数据范围（尺度无关），而非段范围。
    """
    cands = [v for v in valley_indices if pop_a < v < pop_b]
    valid = [v for v in cands
             if v - pop_a >= MIN_STROKES and pop_b - v >= MIN_STROKES]
    if not valid:
        return None

    lowest = min(valid, key=lambda v: tp[v])
    lowest_val = tp[lowest]
    data_range = max(tp) - min(tp)
    tolerance = data_range * VALLEY_EXTEND_TOLERANCE

    best = lowest
    for v in valid:
        if v > lowest and tp[v] - lowest_val <= tolerance:
            best = v
    return best


def _merge_close_pops(tp, valleys, pops):
    """合并距离过近的 PoP（间距 < 2*MIN_STROKES+1）。
    当两个 PoP 太近无法形成有效谷时，保留更显著的那个。
    显著性 = 该 PoP 与前一个谷的幅度差。
    """
    min_gap = 2 * MIN_STROKES
    merged = pops[:]

    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(merged) - 1:
            gap = merged[i + 1] - merged[i]
            if gap < min_gap:
                # 计算两个 PoP 的显著性
                # 用各自前面最近的谷来衡量
                v_before_a = [v for v in valleys if v < merged[i]]
                nearest_valley_a = max(v_before_a) if v_before_a else 0
                v_before_b = [v for v in valleys if v < merged[i + 1]]
                nearest_valley_b = max(v_before_b) if v_before_b else 0

                sig_a = abs(tp[merged[i]] - tp[nearest_valley_a])
                sig_b = abs(tp[merged[i + 1]] - tp[nearest_valley_b])

                # 保留更显著的
                if sig_a >= sig_b:
                    del merged[i + 1]
                else:
                    del merged[i]
                changed = True
            else:
                i += 1

    return merged


def _merge_small_segments(tp, segments, min_range):
    """合并价格幅度低于 min_range 的段。"""
    if not segments or min_range <= 0:
        return segments

    result = [s.copy() for s in segments]

    changed = True
    while changed and len(result) > 1:
        changed = False
        # 找幅度最小的段（低于阈值）
        worst_idx = -1
        worst_range = min_range
        for i, seg in enumerate(result):
            r = abs(tp[seg["toIdx"]] - tp[seg["fromIdx"]])
            if r < worst_range:
                worst_range = r
                worst_idx = i

        if worst_idx < 0:
            break

        # 与相邻段合并
        if worst_idx < len(result) - 1:
            result[worst_idx]["toIdx"] = result[worst_idx + 1]["toIdx"]
            del result[worst_idx + 1]
        else:
            result[worst_idx - 1]["toIdx"] = result[worst_idx]["toIdx"]
            del result[worst_idx]

        changed = True

        # 合并同方向相邻段
        i = 0
        while i < len(result) - 1:
            d1 = "up" if tp[result[i]["toIdx"]] > tp[result[i]["fromIdx"]] else "down"
            d2 = "up" if tp[result[i + 1]["toIdx"]] > tp[result[i + 1]["fromIdx"]] else "down"
            if d1 == d2:
                result[i]["toIdx"] = result[i + 1]["toIdx"]
                del result[i + 1]
            else:
                i += 1

    return result


def _stroke_dir(tp, i):
    """第 i 笔的方向（从 tp[i] 到 tp[i+1]）。"""
    return "up" if tp[i + 1] > tp[i] else "down"


def _strokes_overlap(tp, start, end):
    """检测 tp[start..end] 范围内是否有连续3笔重叠。
    start, end 是 tp 索引，笔从 start 到 end-1。
    """
    for i in range(start, end - 2):
        r1_lo = min(tp[i], tp[i + 1])
        r1_hi = max(tp[i], tp[i + 1])
        r2_lo = min(tp[i + 1], tp[i + 2])
        r2_hi = max(tp[i + 1], tp[i + 2])
        r3_lo = min(tp[i + 2], tp[i + 3])
        r3_hi = max(tp[i + 2], tp[i + 3])
        overlap_hi = min(r1_hi, r2_hi, r3_hi)
        overlap_lo = max(r1_lo, r2_lo, r3_lo)
        if overlap_hi > overlap_lo:
            return True
    return False


def _higher_high_higher_low(tp, start, end):
    """向上段趋势条件：所有谷值严格递增（更高的低点 = 支撑位上移）。
    向上段中谷在偶数索引(start, start+2, ...)。
    严格要求：不允许任何谷值下降。
    """
    valleys = [tp[i] for i in range(start, end, 2)]
    return all(valleys[i + 1] > valleys[i] for i in range(len(valleys) - 1))


def _lower_high_lower_low(tp, start, end):
    """向下段趋势条件：谷值整体下移，允许最多1对相邻谷小幅反弹。
    向下段中谷在奇数索引(start+1, start+3, ...)。
    3笔段（2个谷）必须严格递减；5笔以上允许1次例外。
    """
    valleys = [tp[i] for i in range(start + 1, end + 1, 2)]
    n = len(valleys)
    if n < 2:
        return False
    max_exceptions = 0 if n <= 2 else 1
    exceptions = 0
    for i in range(n - 1):
        if valleys[i + 1] >= valleys[i]:
            exceptions += 1
    return exceptions <= max_exceptions


def _is_segment_formed(tp, start, end, direction):
    """判断从 tp[start] 到 tp[end] 是否满足段的条件。
    direction='up': 所有谷值递增（更高的低点 = 支撑位上移）
    direction='down': 所有谷值递减（更低的低点 = 支撑位下移）
    """
    if end - start < 3:
        return False
    if direction == "up":
        return _higher_high_higher_low(tp, start, end)
    else:
        return _lower_high_lower_low(tp, start, end)


def compute_auto_segments(turning_points, min_segment_ratio=0.05):
    """自动画段 — 缠论线段检测算法
    使用缠论规则作为主算法，仅在完全失败时才尝试 PoP 回退。
    """
    tp = turning_points
    n = len(tp)
    if n < 4:
        return []

    # 主算法：缠论规则线段检测
    segments = _extremum_tracking(tp)

    # 主算法失败时 PoP 回退
    if not segments:
        segments = _pop_segment_fallback(tp, min_segment_ratio)

    return segments


def _can_form_opposite_segment(tp, start, n, direction):
    """检查从 start 开始能否形成 direction 方向的趋势段。
    只用趋势条件（更高高点+更高低点 或 更低高点+更低低点）。
    """
    for end_idx in range(start + 3, n):
        sc = end_idx - start
        if sc % 2 == 0:
            continue
        if _stroke_dir(tp, end_idx - 1) != direction:
            continue
        if _is_segment_formed(tp, start, end_idx, direction):
            return True
    return False


def _last_pair_ok(tp, start, end, direction):
    """检查段的最后一对峰谷是否满足趋势条件。"""
    if direction == "up":
        peaks = [tp[j] for j in range(start + 1, end + 1, 2)]
        valleys = [tp[j] for j in range(start, end + 1, 2)]
    else:
        peaks = [tp[j] for j in range(start, end + 1, 2)]
        valleys = [tp[j] for j in range(start + 1, end + 1, 2)]
    if len(peaks) < 2 or len(valleys) < 2:
        return False
    if direction == "up":
        return peaks[-1] > peaks[-2] and valleys[-1] > valleys[-2]
    else:
        return peaks[-1] < peaks[-2] and valleys[-1] < valleys[-2]


def _extremum_tracking_core(turning_points):
    """缠论线段检测核心扫描。
    策略：
    1. 尝试从 TP[0] 开始扫描，失败则从 TP[1] 开始
    2. 贪心扫描：选反向段最少笔数的端点闭合，同分时选更极端的端点
    3. 后处理拆分：对超长段在段内用同样策略递归拆分
    """
    tp = turning_points
    n = len(tp)
    if n < 4:
        return []

    # 尝试从 TP[0] 开始，失败则从 TP[1] 开始
    for start_offset in [0, 1]:
        if start_offset >= n - 3:
            continue
        segments = _scan_segments(tp, start_offset)
        if segments:
            return segments

    return []


def _scan_segments(tp, start_offset):
    """从指定起始位置贪心扫描段。"""
    n = len(tp)
    segments = []
    seg_start = start_offset
    seg_dir = _stroke_dir(tp, seg_start)

    for _ in range(200):
        if seg_start >= n - 3:
            break

        valid_ends = []
        for end_idx in range(seg_start + 3, n):
            sc = end_idx - seg_start
            if sc % 2 == 0:
                continue
            if _stroke_dir(tp, end_idx - 1) != seg_dir:
                continue
            if _is_segment_formed(tp, seg_start, end_idx, seg_dir):
                valid_ends.append(end_idx)

        if not valid_ends:
            break

        opp_dir = "up" if seg_dir == "down" else "down"
        best_end = None
        best_min_opp = None

        for end_idx in valid_ends:
            for opp_end in range(end_idx + 3, n):
                sc = opp_end - end_idx
                if sc % 2 == 0:
                    continue
                if _stroke_dir(tp, opp_end - 1) != opp_dir:
                    continue
                if _is_segment_formed(tp, end_idx, opp_end, opp_dir):
                    if best_min_opp is None or sc < best_min_opp:
                        best_min_opp = sc
                        best_end = end_idx
                    elif sc == best_min_opp:
                        # 同分时选更极端的端点（上升选更高峰，下降选更低谷）
                        if seg_dir == "up" and tp[end_idx] > tp[best_end]:
                            best_end = end_idx
                        elif seg_dir == "down" and tp[end_idx] < tp[best_end]:
                            best_end = end_idx
                    break

        if best_end is None:
            best_end = valid_ends[-1]

        segments.append({"fromIdx": seg_start, "toIdx": best_end})
        seg_start = best_end
        seg_dir = opp_dir

    # 剩余部分：仅当主循环产生了段时才处理尾部
    if segments and seg_start < n - 1 and n - 1 - seg_start >= MIN_STROKES:
        segments.append({"fromIdx": seg_start, "toIdx": n - 1})

    # 主循环没产生任何段，返回空（让上层尝试下一个起始点）
    if not segments:
        return []

    # 拆分超长段
    segments = _split_long_segments_v3(tp, segments)

    return _merge_same_direction(tp, segments)



def _split_long_segments_v3(tp, segments):
    """拆分超长段：对 > MAX_SEGMENT_STROKES 笔的段，用最早闭合策略在段内拆分。"""
    if not segments:
        return segments
    result = []
    for seg in segments:
        fi, ti = seg["fromIdx"], seg["toIdx"]
        strokes = ti - fi
        if strokes <= MAX_SEGMENT_STROKES:
            result.append(seg)
            continue
        # 在段内用贪心拆分
        sub = _greedy_split_inside(tp, fi, ti)
        if sub and len(sub) > 1:
            result.extend(sub)
        else:
            result.append(seg)
    return result



def _greedy_split_inside(tp, start, end):
    """在段内贪心拆分：用第一笔方向开始，找交替方向子段。
    如果第一笔方向和段整体方向不一致，先完成一个反转段再继续。
    """
    n = end + 1
    segs = []
    cur = start
    cur_dir = _stroke_dir(tp, cur)

    for _ in range(30):
        if cur >= end:
            break
        remaining = end - cur
        if remaining < MIN_STROKES:
            if segs: segs[-1]["toIdx"] = end
            break

        found = False
        for ei in range(cur + MIN_STROKES, min(cur + MAX_SEGMENT_STROKES + 1, n)):
            sc = ei - cur
            if sc % 2 == 0: continue
            if _stroke_dir(tp, ei - 1) != cur_dir: continue
            if _is_segment_formed(tp, cur, ei, cur_dir):
                segs.append({"fromIdx": cur, "toIdx": ei})
                cur = ei
                cur_dir = "up" if cur_dir == "down" else "down"
                found = True
                break
        if not found:
            if end - cur >= MIN_STROKES:
                segs.append({"fromIdx": cur, "toIdx": end})
            elif segs:
                segs[-1]["toIdx"] = end
            break
    return segs


def _merge_same_direction(tp, segments):
    """合并同方向段。"""
    if len(segments) <= 1:
        return segments
    merged = [segments[0].copy()]
    for seg in segments[1:]:
        prev = merged[-1]
        d_prev = "up" if tp[prev["toIdx"]] > tp[prev["fromIdx"]] else "down"
        d_cur = "up" if tp[seg["toIdx"]] > tp[seg["fromIdx"]] else "down"
        if d_prev == d_cur:
            merged[-1] = {"fromIdx": prev["fromIdx"], "toIdx": seg["toIdx"]}
        else:
            merged.append(seg.copy())
    return merged


def _extremum_tracking(turning_points):
    """缠论线段检测算法。"""
    return _extremum_tracking_core(turning_points)


def _remove_degenerate_segments(tp, segments, min_range):
    """移除价格幅度过小的退化段，修复链路保持交替方向。
    策略：将退化段与前一方向相同的邻居合并（扩展前一段的终点），
    而不是简单删除后让两边合并成超长段。
    """
    if not segments:
        return segments

    result = [segments[0].copy()]
    for seg in segments[1:]:
        rng = abs(tp[seg["toIdx"]] - tp[seg["fromIdx"]])
        if rng < min_range:
            # 退化段：扩展前一段的终点到当前段的终点
            # 这相当于把退化段合并进前一段
            result[-1]["toIdx"] = seg["toIdx"]
        else:
            result.append(seg.copy())

    # 修复链路：确保每段 fromIdx == 前一段 toIdx
    for i in range(1, len(result)):
        if result[i]["fromIdx"] != result[i - 1]["toIdx"]:
            result[i]["fromIdx"] = result[i - 1]["toIdx"]

    # 合并相邻同方向段
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(result) - 1:
            d1 = "up" if tp[result[i]["toIdx"]] > tp[result[i]["fromIdx"]] else "down"
            d2 = "up" if tp[result[i + 1]["toIdx"]] > tp[result[i + 1]["fromIdx"]] else "down"
            if d1 == d2:
                result[i] = {"fromIdx": result[i]["fromIdx"], "toIdx": result[i + 1]["toIdx"]}
                del result[i + 1]
                changed = True
            else:
                i += 1

    return result


def _pop_segment_fallback(turning_points, min_segment_ratio=0.05):
    """PoP 峰之峰回退算法 — 仅在主算法完全失败时使用。"""
    tp = turning_points
    n = len(tp)
    if n < 4:
        return []

    peaks, valleys = _extract_local_extremes(tp)
    pops = _find_pops(tp, peaks)
    if len(pops) < 1:
        return []

    pops = _merge_close_pops(tp, valleys, pops)
    if len(pops) < 1:
        return []

    endpoints = []
    first_pop = pops[0]
    pre_v = [v for v in valleys if v < first_pop and first_pop - v >= MIN_STROKES]
    if pre_v:
        endpoints.append(min(pre_v, key=lambda v: tp[v]))
    else:
        pre_v_relaxed = [v for v in valleys if v < first_pop]
        if pre_v_relaxed:
            endpoints.append(min(pre_v_relaxed, key=lambda v: tp[v]))
        else:
            endpoints.append(0)

    for i in range(len(pops) - 1):
        endpoints.append(pops[i])
        valley = _find_valid_valley(tp, valleys, pops[i], pops[i + 1])
        if valley is not None:
            endpoints.append(valley)
        else:
            best = pops[i] + 1
            for j in range(pops[i] + 1, pops[i + 1]):
                if tp[j] < tp[best]:
                    best = j
            endpoints.append(best)

    endpoints.append(pops[-1])
    last_pop = pops[-1]
    post_v = [v for v in valleys if v > last_pop and v - last_pop >= MIN_STROKES]
    if post_v:
        endpoints.append(min(post_v, key=lambda v: tp[v]))

    segments = []
    for i in range(len(endpoints) - 1):
        fi, ti = endpoints[i], endpoints[i + 1]
        if ti > fi:
            segments.append({"fromIdx": fi, "toIdx": ti})

    if any(s["toIdx"] - s["fromIdx"] < MIN_STROKES for s in segments):
        return []

    # 合并同方向
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(segments) - 1:
            d1 = "up" if tp[segments[i]["toIdx"]] > tp[segments[i]["fromIdx"]] else "down"
            d2 = "up" if tp[segments[i+1]["toIdx"]] > tp[segments[i+1]["fromIdx"]] else "down"
            if d1 == d2:
                segments[i] = {"fromIdx": segments[i]["fromIdx"], "toIdx": segments[i+1]["toIdx"]}
                del segments[i+1]
                changed = True
            else:
                i += 1

    if min_segment_ratio > 0 and segments:
        data_range = max(tp) - min(tp)
        if data_range > 0:
            segments = _merge_small_segments(tp, segments, data_range * min_segment_ratio)

    return segments


def _detect_zhongshu_in_range(tp, start, end):
    """在 tp[start..end] 范围内检测中枢。
    缠论规则：至少三个连续笔有重叠部分。
    ZG = 高点中的低点，ZD = 低点中的高点。
    重叠笔可延伸，直到新笔与已有中枢不再重叠。
    """
    if end - start < 3:
        return []

    raw = []
    i = start
    while i <= end - 3:
        r1_low = min(tp[i], tp[i + 1])
        r1_high = max(tp[i], tp[i + 1])
        r2_low = min(tp[i + 1], tp[i + 2])
        r2_high = max(tp[i + 1], tp[i + 2])
        r3_low = min(tp[i + 2], tp[i + 3])
        r3_high = max(tp[i + 2], tp[i + 3])

        zg = min(r1_high, r2_high, r3_high)
        zd = max(r1_low, r2_low, r3_low)

        if zg > zd:
            # 3笔重叠，中枢成立
            from_idx = i
            to_idx = i + 3
            cur_zg = zg
            cur_zd = zd
            ext = 0

            # 延伸：后续笔如果与中枢重叠，则扩展中枢
            for j in range(i + 3, end):
                if ext >= ZS_MAX_EXTEND:
                    break
                r_low = min(tp[j], tp[j + 1])
                r_high = max(tp[j], tp[j + 1])
                new_zg = min(cur_zg, r_high)
                new_zd = max(cur_zd, r_low)
                if new_zg <= new_zd:
                    break
                to_idx = j + 1
                cur_zg = new_zg
                cur_zd = new_zd
                ext += 1

            raw.append({
                "fromIdx": from_idx,
                "toIdx": to_idx,
                "zg": cur_zg,
                "zd": cur_zd,
            })
            i = to_idx
        else:
            i += 1

    return raw


def compute_auto_zhongshu(turning_points, segments=None, min_segment_ratio=0.05):
    """自动画笔中枢 — 段内检测，中枢不跨越段边界。
    segments: 段列表 [{"fromIdx", "toIdx"}, ...]
    如果不传 segments，内部自动计算。
    """
    tp = turning_points
    if len(tp) < 4:
        return []

    if segments is None:
        segments = compute_auto_segments(tp, min_segment_ratio)

    if not segments:
        return []

    all_zhongshu = []

    for seg in segments:
        seg_start = seg["fromIdx"]
        seg_end = seg["toIdx"]

        # 跳过首尾笔：中枢不包含段的第一笔和最后一笔
        # UP段：DOWN开始DOWN结束 → fromIdx >= seg_start+1, toIdx <= seg_end-1
        # DN段：UP开始UP结束 → 同上
        inner_start = seg_start + 1
        inner_end = seg_end - 1

        if inner_end - inner_start < 2:
            # 内部笔不足3笔，无法形成中枢
            continue

        # 段方向
        seg_dir = "up" if tp[seg_end] > tp[seg_start] else "down"

        # 段内检测中枢
        zs_list = _detect_zhongshu_in_range(tp, inner_start, inner_end)

        # 方向约束裁剪：UP段→首尾笔须为DN，DN段→首尾笔须为UP
        for zs in zs_list:
            # 检查第一笔方向
            first_up = tp[zs["fromIdx"] + 1] > tp[zs["fromIdx"]]
            if (seg_dir == "up" and first_up) or (seg_dir == "down" and not first_up):
                zs["fromIdx"] += 1
            # 检查最后一笔方向
            last_up = tp[zs["toIdx"]] > tp[zs["toIdx"] - 1]
            if (seg_dir == "up" and last_up) or (seg_dir == "down" and not last_up):
                zs["toIdx"] -= 1
            # 裁剪后重新计算 ZG/ZD
            if zs["toIdx"] - zs["fromIdx"] >= 2:
                min_high = float("inf")
                max_low = float("-inf")
                for k in range(zs["fromIdx"], zs["toIdx"]):
                    min_high = min(min_high, max(tp[k], tp[k + 1]))
                    max_low = max(max_low, min(tp[k], tp[k + 1]))
                if min_high > max_low:
                    zs["zg"] = min_high
                    zs["zd"] = max_low
                else:
                    zs["fromIdx"] = -1  # 标记为无效
            else:
                zs["fromIdx"] = -1  # 标记为无效

        # 过滤无效的中枢
        zs_list = [z for z in zs_list if z["fromIdx"] >= 0]

        # 段内合并相邻/重叠的中枢
        if len(zs_list) <= 1:
            all_zhongshu.extend(zs_list)
            continue

        merged = [zs_list[0].copy()]
        for zs in zs_list[1:]:
            prev = merged[-1]
            if zs["zd"] < prev["zg"] and zs["zg"] > prev["zd"]:
                new_from = min(prev["fromIdx"], zs["fromIdx"])
                new_to = max(prev["toIdx"], zs["toIdx"])
                min_high = float("inf")
                max_low = float("-inf")
                for k in range(new_from, new_to):
                    min_high = min(min_high, max(tp[k], tp[k + 1]))
                    max_low = max(max_low, min(tp[k], tp[k + 1]))
                if min_high > max_low:
                    merged[-1] = {
                        "fromIdx": new_from,
                        "toIdx": new_to,
                        "zg": min_high,
                        "zd": max_low,
                    }
                else:
                    merged.append(zs.copy())
            else:
                merged.append(zs.copy())

        all_zhongshu.extend(merged)

    return all_zhongshu


def compute_manual_zhongshu(turning_points, from_idx, to_idx):
    """手动画中枢时计算 ZG/ZD"""
    tp = turning_points
    min_high = float("inf")
    max_low = float("-inf")
    for i in range(from_idx, to_idx):
        min_high = min(min_high, max(tp[i], tp[i + 1]))
        max_low = max(max_low, min(tp[i], tp[i + 1]))
    if min_high > max_low:
        return {"fromIdx": from_idx, "toIdx": to_idx, "zg": min_high, "zd": max_low}
    return None


def compute_segment_zhongshu(turning_points, segments, higher_segments=None):
    """段中枢：完全沿用 compute_auto_zhongshu 的递归逻辑。
    对每个段的段（higher_segment）内部检测，排除首尾段，
    方向裁剪（UP higher→首尾段须为DN，DN higher→首尾段须为UP），
    紧密度检查、延伸限制和重叠合并。
    """
    tp = turning_points
    if len(segments) < 3:
        return []

    if higher_segments is None:
        higher_segments = compute_higher_segments(tp, segments)

    if not higher_segments:
        return []

    def seg_high(si):
        s = segments[si]
        return max(tp[s["fromIdx"]], tp[s["toIdx"]])

    def seg_low(si):
        s = segments[si]
        return min(tp[s["fromIdx"]], tp[s["toIdx"]])

    all_zhongshu = []

    for hseg in higher_segments:
        h_start = hseg["fromIdx"]
        h_end = hseg["toIdx"]

        # 找到属于此 higher_segment 的段索引
        seg_range = []
        for si, seg in enumerate(segments):
            if seg["fromIdx"] >= h_start and seg["toIdx"] <= h_end:
                seg_range.append(si)

        # 排除首尾段（与笔中枢排除首尾笔完全相同）
        if len(seg_range) < 5:
            continue

        inner_start = seg_range[1]
        inner_end = seg_range[-2]

        # higher_segment 方向
        hseg_dir = "up" if tp[h_end] > tp[h_start] else "down"

        # 段内检测中枢
        zs_list = _detect_seg_zhongshu_range(tp, segments, inner_start, inner_end)

        # 方向约束裁剪：与笔中枢完全相同的逻辑
        # UP higher→中枢首尾段须为DN，DN higher→中枢首尾段须为UP
        for zs in zs_list:
            fsi = zs["_fsi"]
            lsi = zs["_lsi"]

            # 检查第一段方向
            first_up = tp[segments[fsi]["toIdx"]] > tp[segments[fsi]["fromIdx"]]
            if (hseg_dir == "up" and first_up) or (hseg_dir == "down" and not first_up):
                fsi += 1

            # 检查最后一段方向
            last_up = tp[segments[lsi]["toIdx"]] > tp[segments[lsi]["fromIdx"]]
            if (hseg_dir == "up" and last_up) or (hseg_dir == "down" and not last_up):
                lsi -= 1

            # 裁剪后重新计算 ZG/ZD
            if lsi - fsi >= 2:
                min_h = float("inf")
                max_l = float("-inf")
                for si in range(fsi, lsi + 1):
                    min_h = min(min_h, seg_high(si))
                    max_l = max(max_l, seg_low(si))
                if min_h > max_l:
                    zs["fromIdx"] = segments[fsi]["fromIdx"]
                    zs["toIdx"] = segments[lsi]["toIdx"]
                    zs["zg"] = min_h
                    zs["zd"] = max_l
                else:
                    zs["fromIdx"] = -1
            else:
                zs["fromIdx"] = -1

        # 过滤无效的中枢
        zs_list = [z for z in zs_list if z["fromIdx"] >= 0]

        # 段内合并相邻/重叠的中枢（与笔中枢完全相同）
        if len(zs_list) <= 1:
            all_zhongshu.extend(_clean_seg_zhongshu_list(zs_list))
            continue

        merged = [zs_list[0].copy()]
        for zs in zs_list[1:]:
            prev = merged[-1]
            if zs["zd"] < prev["zg"] and zs["zg"] > prev["zd"]:
                new_from = min(prev["fromIdx"], zs["fromIdx"])
                new_to = max(prev["toIdx"], zs["toIdx"])
                min_h = float("inf")
                max_l = float("-inf")
                for si in range(len(segments)):
                    s = segments[si]
                    if s["fromIdx"] >= new_from and s["toIdx"] <= new_to:
                        min_h = min(min_h, seg_high(si))
                        max_l = max(max_l, seg_low(si))
                if min_h > max_l:
                    merged[-1] = {
                        "fromIdx": new_from,
                        "toIdx": new_to,
                        "zg": min_h,
                        "zd": max_l,
                    }
                else:
                    merged.append(zs.copy())
            else:
                merged.append(zs.copy())

        all_zhongshu.extend(_clean_seg_zhongshu_list(merged))

    return all_zhongshu


def _detect_seg_zhongshu_range(tp, segments, si_start, si_end):
    """在 segments[si_start..si_end] 范围内检测段中枢。
    与笔中枢完全相同的规则：至少3个连续段有重叠，延伸到不重叠为止。
    ZG = 高点中的低点，ZD = 低点中的高点。
    """
    if si_end - si_start < 2:
        return []

    def sh(si):
        s = segments[si]
        return max(tp[s["fromIdx"]], tp[s["toIdx"]])

    def sl(si):
        s = segments[si]
        return min(tp[s["fromIdx"]], tp[s["toIdx"]])

    raw = []
    i = si_start
    while i <= si_end - 2:
        h0, l0 = sh(i), sl(i)
        h1, l1 = sh(i + 1), sl(i + 1)
        h2, l2 = sh(i + 2), sl(i + 2)

        zg = min(h0, h1, h2)
        zd = max(l0, l1, l2)

        if zg > zd:
            # 3段重叠，中枢成立
            cur_zg, cur_zd = zg, zd
            to_si = i + 2
            ext = 0

            for j in range(i + 3, si_end + 1):
                if ext >= ZS_MAX_EXTEND:
                    break
                new_zg = min(cur_zg, sh(j))
                new_zd = max(cur_zd, sl(j))
                if new_zg <= new_zd:
                    break
                to_si = j
                cur_zg, cur_zd = new_zg, new_zd
                ext += 1

            raw.append({
                "fromIdx": segments[i]["fromIdx"],
                "toIdx": segments[to_si]["toIdx"],
                "zg": cur_zg, "zd": cur_zd,
                "_fsi": i, "_lsi": to_si,
            })
            i = to_si + 1
        else:
            i += 1

    return raw


def _clean_seg_zhongshu_list(zs_list):
    """Remove internal _fsi/_lsi keys from zhongshu list."""
    for zs in zs_list:
        zs.pop("_fsi", None)
        zs.pop("_lsi", None)
    return zs_list


def compute_higher_segments(turning_points, segments, min_segment_ratio=0.05):
    """段的段：将段的端点作为新的转折点序列，用同一套 compute_auto_segments 画段。"""
    tp = turning_points
    if len(segments) < 4:
        return []

    # 构建段端点序列
    endpoints = [segments[0]["fromIdx"]]
    for seg in segments:
        endpoints.append(seg["toIdx"])

    prices = [tp[i] for i in endpoints]

    # 与笔的段完全相同的算法
    higher = compute_auto_segments(prices, min_segment_ratio)

    # 映射回原始转折点索引
    return [{"fromIdx": endpoints[s["fromIdx"]], "toIdx": endpoints[s["toIdx"]]}
            for s in higher]


def generate_random_zigzag(count, price_min, price_max):
    """随机生成转折点"""
    if count < 3 or price_min >= price_max:
        return []

    points = []
    price = price_min + random.random() * (price_max - price_min)
    points.append(round(price))

    going_down = random.random() > 0.5
    for _ in range(1, count):
        r = price_max - price_min
        swing = r * 0.05 + random.random() * r * 0.2
        if going_down:
            price = price - swing
            if price < price_min:
                price = price_min + random.random() * r * 0.05
        else:
            price = price + swing
            if price > price_max:
                price = price_max - random.random() * r * 0.05
        rounded = round(price)
        if rounded != points[-1]:
            points.append(rounded)
        going_down = not going_down

    return points


def build_strokes(turning_points):
    """从转折点构建笔列表。

    注意：前端将 strokes[i] 与 turningPoints[i] 一一对应（用于编辑/删除）。
    这里保持 N 个条目的格式（每条记录代表以该转折点为终点的笔），
    同时附加 from/to 信息供算法使用。
    """
    if not turning_points:
        return []
    strokes = []
    for i, p in enumerate(turning_points):
        if i == 0:
            d = "down" if (len(turning_points) > 1 and turning_points[1] < turning_points[0]) else "up"
        else:
            d = "up" if p > turning_points[i - 1] else "down"
        strokes.append({
            "dir": d,
            "val": p,
            "from": turning_points[i - 1] if i > 0 else None,
            "to": p,
            "fromIdx": i - 1 if i > 0 else None,
            "toIdx": i,
        })
    return strokes


def build_segment_details(turning_points, segment_indices):
    """将段索引列表转换为包含价格和方向的详细信息"""
    result = []
    for seg in segment_indices:
        from_val = turning_points[seg["fromIdx"]]
        to_val = turning_points[seg["toIdx"]]
        result.append({
            "from": from_val,
            "to": to_val,
            "dir": "up" if to_val > from_val else "down",
            "fromIdx": seg["fromIdx"],
            "toIdx": seg["toIdx"]
        })
    return result


def compute_buy_sell_points(turning_points, zhongshu_list):
    """计算笔级别买卖点。

    对每个笔中枢，检测其后的买卖点：
    - 1买: 价格向下离开中枢（低于ZD）的第一个谷
    - 1卖: 价格向上离开中枢（高于ZG）的第一个峰
    - 2买: 1买后回调不破1买低点的第一个谷（更高低点）
    - 2卖: 1卖后反弹不破1卖高点的第一个峰（更低高点）
    - 3买: 1卖后回踩不低于ZG的第一个谷（突破后回踩确认）
    - 3卖: 1买后反弹不高于ZD的第一个峰（跌破后反弹确认）

    搜索范围限制在当前中枢到下一个中枢之间。
    """
    if not zhongshu_list or len(turning_points) < 3:
        return []

    n = len(turning_points)
    peak_indices, valley_indices = _extract_local_extremes(turning_points)
    peak_set = set(peak_indices)

    results = []
    zs_count = len(zhongshu_list)

    for zsi, zs in enumerate(zhongshu_list):
        zg = zs['zg']
        zd = zs['zd']
        start = zs['toIdx'] + 1

        # 搜索范围：到下一个中枢的 fromIdx 或数据末尾
        limit = n
        if zsi + 1 < zs_count:
            limit = zhongshu_list[zsi + 1]['fromIdx']

        if start >= limit:
            continue

        # 阶段1：确定离开方向
        exit_up_idx = None   # 第一个峰 > ZG
        exit_down_idx = None # 第一个谷 < ZD

        for i in range(start, limit):
            if exit_up_idx is None and i in peak_set and turning_points[i] > zg:
                exit_up_idx = i
            if exit_down_idx is None and i not in peak_set and turning_points[i] < zd:
                exit_down_idx = i
            if exit_up_idx is not None and exit_down_idx is not None:
                break

        if exit_up_idx is not None and (exit_down_idx is None or exit_up_idx < exit_down_idx):
            # 向上离开 → 1卖
            results.append({"idx": exit_up_idx, "type": "sell", "label": "1"})

            # 3买：1卖后第一个谷 >= ZG
            for i in range(exit_up_idx + 1, limit):
                if i not in peak_set:
                    if turning_points[i] >= zg:
                        results.append({"idx": i, "type": "buy", "label": "3"})
                    break  # 只看第一个谷

            # 2卖：1卖后第一个峰 <= 1卖价格
            for i in range(exit_up_idx + 1, limit):
                if i in peak_set and turning_points[i] <= turning_points[exit_up_idx]:
                    results.append({"idx": i, "type": "sell", "label": "2"})
                    break

        elif exit_down_idx is not None and (exit_up_idx is None or exit_down_idx < exit_up_idx):
            # 向下离开 → 1买
            results.append({"idx": exit_down_idx, "type": "buy", "label": "1"})

            # 3卖：1买后第一个峰 <= ZD
            for i in range(exit_down_idx + 1, limit):
                if i in peak_set:
                    if turning_points[i] <= zd:
                        results.append({"idx": i, "type": "sell", "label": "3"})
                    break  # 只看第一个峰

            # 2买：1买后第一个谷 >= 1买价格
            for i in range(exit_down_idx + 1, limit):
                if i not in peak_set and turning_points[i] >= turning_points[exit_down_idx]:
                    results.append({"idx": i, "type": "buy", "label": "2"})
                    break

    results.sort(key=lambda x: x['idx'])
    return results
