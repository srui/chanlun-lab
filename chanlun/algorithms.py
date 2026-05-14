"""缠论核心算法 — 缠论规则线段检测 + PoP回退"""

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
    segments = _extremum_tracking_core(tp)

    # 主算法失败时 PoP 回退
    if not segments:
        segments = _pop_segment_fallback(tp, min_segment_ratio)

    return segments


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

    segments = _merge_same_direction(tp, segments)

    if min_segment_ratio > 0 and segments:
        data_range = max(tp) - min(tp)
        if data_range > 0:
            segments = _merge_small_segments(tp, segments, data_range * min_segment_ratio)

    return segments


def _detect_zhongshu_in_units(units_high, units_low, start, end):
    """在 units[start..end] 范围内检测中枢（通用版本）。

    units_high[i]: 第 i 个单元的高点
    units_low[i]:  第 i 个单元的低点
    start, end: 单元索引范围

    缠论规则：至少三个连续单元有重叠部分。
    ZG = 高点中的低点，ZD = 低点中的高点。
    重叠单元可延伸，直到新单元与已有中枢不再重叠。
    """
    n = len(units_high)
    if end - start < 2 or end >= n:
        return []

    raw = []
    i = start
    while i <= end - 2:
        h0, l0 = units_high[i], units_low[i]
        h1, l1 = units_high[i + 1], units_low[i + 1]
        h2, l2 = units_high[i + 2], units_low[i + 2]

        zg = min(h0, h1, h2)
        zd = max(l0, l1, l2)

        if zg > zd:
            cur_zg, cur_zd = zg, zd
            to_idx = i + 2
            ext = 0

            for j in range(i + 3, end + 1):
                if ext >= ZS_MAX_EXTEND:
                    break
                new_zg = min(cur_zg, units_high[j])
                new_zd = max(cur_zd, units_low[j])
                if new_zg <= new_zd:
                    break
                to_idx = j
                cur_zg, cur_zd = new_zg, new_zd
                ext += 1

            raw.append({
                "first": i,
                "last": to_idx,
                "zg": cur_zg,
                "zd": cur_zd,
            })
            i = to_idx + 1
        else:
            i += 1

    return raw


def _trim_and_merge_zhongshu(zs_list, unit_dir, container_dir):
    """对中枢列表做方向裁剪和重叠合并（通用版本）。

    unit_dir(i): 第 i 个单元的方向 ("up" / "down")
    container_dir: 容器方向 ("up" / "down")
    """
    for zs in zs_list:
        fi, li = zs["first"], zs["last"]

        # 检查第一个单元方向
        if (container_dir == "up" and unit_dir(fi) == "up") or \
           (container_dir == "down" and unit_dir(fi) == "down"):
            fi += 1
        # 检查最后一个单元方向
        if (container_dir == "up" and unit_dir(li) == "up") or \
           (container_dir == "down" and unit_dir(li) == "down"):
            li -= 1

        if li - fi >= 2:
            zs["first"] = fi
            zs["last"] = li
        else:
            zs["first"] = -1  # 标记无效

    zs_list = [z for z in zs_list if z["first"] >= 0]

    # 合并重叠
    if len(zs_list) <= 1:
        return zs_list

    merged = [zs_list[0].copy()]
    for zs in zs_list[1:]:
        prev = merged[-1]
        if zs["zd"] < prev["zg"] and zs["zg"] > prev["zd"]:
            new_first = min(prev["first"], zs["first"])
            new_last = max(prev["last"], zs["last"])
            # 重新计算合并后的 ZG/ZD（由调用者负责，这里先合并范围）
            merged[-1] = {
                "first": new_first,
                "last": new_last,
                "zg": min(prev["zg"], zs["zg"]),
                "zd": max(prev["zd"], zs["zd"]),
            }
        else:
            merged.append(zs.copy())

    return merged


def _detect_zhongshu_in_range(tp, start, end):
    """在 tp[start..end] 范围内检测笔中枢（兼容旧接口）。"""
    if end - start < 3 or end >= len(tp):
        return []

    # 构建笔级别的高点/低点数组
    units_high = []
    units_low = []
    for i in range(start, end + 1):
        units_high.append(max(tp[i], tp[i + 1]) if i + 1 <= end else tp[i])
        units_low.append(min(tp[i], tp[i + 1]) if i + 1 <= end else tp[i])

    raw = _detect_zhongshu_in_units(units_high, units_low, 0, len(units_high) - 1)

    # 转换回 tp 索引
    result = []
    for zs in raw:
        result.append({
            "fromIdx": start + zs["first"],
            "toIdx": start + zs["last"] + 1,
            "zg": zs["zg"],
            "zd": zs["zd"],
        })
    return result


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

        inner_start = seg_start + 1
        inner_end = seg_end - 1

        if inner_end - inner_start < 2:
            continue

        seg_dir = "up" if tp[seg_end] > tp[seg_start] else "down"

        # 构建笔级别的高点/低点数组
        n_units = inner_end - inner_start
        units_high = [max(tp[inner_start + i], tp[inner_start + i + 1]) for i in range(n_units)]
        units_low = [min(tp[inner_start + i], tp[inner_start + i + 1]) for i in range(n_units)]

        zs_list = _detect_zhongshu_in_units(units_high, units_low, 0, n_units - 1)

        # 方向函数：第 i 个笔单元的方向
        def stroke_dir(i):
            return "up" if tp[inner_start + i + 1] > tp[inner_start + i] else "down"

        zs_list = _trim_and_merge_zhongshu(zs_list, stroke_dir, seg_dir)

        # 转换回 tp 索引并重新计算裁剪后的 ZG/ZD
        for zs in zs_list:
            fi = inner_start + zs["first"]
            ti = inner_start + zs["last"] + 1
            min_high = min(max(tp[k], tp[k + 1]) for k in range(fi, ti))
            max_low = max(min(tp[k], tp[k + 1]) for k in range(fi, ti))
            if min_high > max_low:
                zs["fromIdx"] = fi
                zs["toIdx"] = ti
                zs["zg"] = min_high
                zs["zd"] = max_low
                del zs["first"]
                del zs["last"]
            else:
                zs["fromIdx"] = -1

        all_zhongshu.extend(z for z in zs_list if z.get("fromIdx", -1) >= 0)

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
    """段中枢：对每个高级别段内部的段做中枢检测。
    排除首尾段，方向裁剪，延伸限制和重叠合并。
    使用通用的 _detect_zhongshu_in_units + _trim_and_merge_zhongshu。
    """
    tp = turning_points
    if len(segments) < 3:
        return []

    if higher_segments is None:
        higher_segments = compute_higher_segments(tp, segments)

    if not higher_segments:
        return []

    # 构建段级别的高点/低点数组
    seg_highs = [max(tp[s["fromIdx"]], tp[s["toIdx"]]) for s in segments]
    seg_lows = [min(tp[s["fromIdx"]], tp[s["toIdx"]]) for s in segments]

    def seg_unit_dir(si):
        return "up" if tp[segments[si]["toIdx"]] > tp[segments[si]["fromIdx"]] else "down"

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

        hseg_dir = "up" if tp[h_end] > tp[h_start] else "down"

        zs_list = _detect_zhongshu_in_units(seg_highs, seg_lows, inner_start, inner_end)
        zs_list = _trim_and_merge_zhongshu(zs_list, seg_unit_dir, hseg_dir)

        # 转换为 tp 索引并重新计算 ZG/ZD
        for zs in zs_list:
            fi_si = zs["first"]
            li_si = zs["last"]
            min_h = min(seg_highs[s] for s in range(fi_si, li_si + 1))
            max_l = max(seg_lows[s] for s in range(fi_si, li_si + 1))
            if min_h > max_l:
                zs["fromIdx"] = segments[fi_si]["fromIdx"]
                zs["toIdx"] = segments[li_si]["toIdx"]
                zs["zg"] = min_h
                zs["zd"] = max_l
                del zs["first"]
                del zs["last"]
            else:
                zs["fromIdx"] = -1

        all_zhongshu.extend(z for z in zs_list if z.get("fromIdx", -1) >= 0)

    return all_zhongshu


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
    - 2买: 1买后回调不破1买低点的第一个谷（更高低点），且之后继续向上
    - 2卖: 1卖后反弹不破1卖高点的第一个峰（更低高点），且之后继续向下
    - 3买: 1卖后回踩不低于ZG的第一个谷，且之后继续向上
    - 3卖: 1买后反弹不高于ZD的第一个峰，且之后继续向下

    搜索范围：到数据末尾（不截断到下一个中枢）。
    """
    if not zhongshu_list or len(turning_points) < 3:
        return []

    n = len(turning_points)
    tp = turning_points

    # 转折点序列本身是交替的峰谷，直接按奇偶索引区分
    if tp[0] > tp[1]:
        peak_set = set(range(0, n, 2))
    else:
        peak_set = set(range(1, n, 2))

    def is_peak(i):
        return i in peak_set

    def is_valley(i):
        return i not in peak_set

    def has_continuation(idx, direction):
        """确认 idx 之后有继续朝着 direction 方向运动的笔。
        direction='up': idx 之后有一个更高的峰
        direction='down': idx 之后有一个更低的谷
        """
        if direction == "up":
            # 如果 idx 是谷，看下一个峰是否更高
            if is_valley(idx):
                return idx + 1 < n and tp[idx + 1] > tp[idx]
            # 如果 idx 是峰，看后面的谷+峰是否创新高
            return idx + 2 < n and tp[idx + 2] > tp[idx]
        else:
            if is_peak(idx):
                return idx + 1 < n and tp[idx + 1] < tp[idx]
            return idx + 2 < n and tp[idx + 2] < tp[idx]

    results = []

    for zsi, zs in enumerate(zhongshu_list):
        zg = zs['zg']
        zd = zs['zd']
        start = zs['toIdx'] + 1

        if start >= n:
            continue

        # 阶段1：确定离开方向
        # 找第一笔穿越 ZG 或 ZD 的笔（看笔的终点，即转折点）
        exit_up_idx = None   # 第一个峰 > ZG（向上离开）
        exit_down_idx = None # 第一个谷 < ZD（向下离开）

        for i in range(start, n):
            if exit_up_idx is None and is_peak(i) and tp[i] > zg:
                exit_up_idx = i
            if exit_down_idx is None and is_valley(i) and tp[i] < zd:
                exit_down_idx = i
            if exit_up_idx is not None and exit_down_idx is not None:
                break

        if exit_up_idx is not None and (exit_down_idx is None or exit_up_idx < exit_down_idx):
            # 向上离开 → 1卖
            results.append({"idx": exit_up_idx, "type": "sell", "label": "1"})

            # 3买：1卖后回踩到 ZG 附近但不破 ZG 的谷，且之后继续向上
            for i in range(exit_up_idx + 1, n):
                if is_valley(i) and tp[i] >= zg:
                    if has_continuation(i, "up"):
                        results.append({"idx": i, "type": "buy", "label": "3"})
                    break  # 只看第一个谷

            # 2卖：1卖后第一个更低高点（峰 <= 1卖价格），且之后继续向下
            for i in range(exit_up_idx + 1, n):
                if is_peak(i) and tp[i] <= tp[exit_up_idx]:
                    if has_continuation(i, "down"):
                        results.append({"idx": i, "type": "sell", "label": "2"})
                    break

        elif exit_down_idx is not None and (exit_up_idx is None or exit_down_idx < exit_up_idx):
            # 向下离开 → 1买
            results.append({"idx": exit_down_idx, "type": "buy", "label": "1"})

            # 3卖：1买后反弹到 ZD 附近但不破 ZD 的峰，且之后继续向下
            for i in range(exit_down_idx + 1, n):
                if is_peak(i) and tp[i] <= zd:
                    if has_continuation(i, "down"):
                        results.append({"idx": i, "type": "sell", "label": "3"})
                    break  # 只看第一个峰

            # 2买：1买后第一个更高低点（谷 >= 1买价格），且之后继续向上
            for i in range(exit_down_idx + 1, n):
                if is_valley(i) and tp[i] >= tp[exit_down_idx]:
                    if has_continuation(i, "up"):
                        results.append({"idx": i, "type": "buy", "label": "2"})
                    break

    results.sort(key=lambda x: x['idx'])
    return results
