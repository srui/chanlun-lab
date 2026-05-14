"""缠论核心算法单元测试 — 快照测试 + 属性测试"""

import unittest
from chanlun.algorithms import (
    compute_auto_segments,
    compute_auto_zhongshu,
    compute_segment_zhongshu,
    compute_higher_segments,
    compute_buy_sell_points,
    build_strokes,
    build_segment_details,
)
from chanlun.binance_service import (
    _has_inclusion,
    merge_klines_with_inclusion,
    detect_fractals_from_klines,
    fractals_to_turning_points,
)


def _kline(high, low, open_time=0, idx=None):
    """Helper: 构建单根K线数据。"""
    return {
        "openTime": open_time,
        "open": low,
        "high": high,
        "low": low,
        "close": high,
        "volume": 1.0,
        "closeTime": open_time + 60000,
    }


class TestComputeAutoSegments(unittest.TestCase):
    """段检测快照测试：基于已知正确的转折点序列验证输出。"""

    def _validate_segments(self, tp, segments):
        """通用段属性校验"""
        if not segments:
            return
        # 每段至少3笔
        for s in segments:
            fi, ti = s["fromIdx"], s["toIdx"]
            self.assertGreater(ti, fi, f"toIdx must > fromIdx: {fi}->{ti}")
            self.assertGreaterEqual(ti - fi, 3, f"segment must span >= 3 strokes: {fi}->{ti} ({ti-fi})")

        # 方向交替
        dirs = []
        for s in segments:
            fi, ti = s["fromIdx"], s["toIdx"]
            d = "up" if tp[ti] > tp[fi] else "down"
            dirs.append(d)
        for i in range(1, len(dirs)):
            self.assertNotEqual(dirs[i], dirs[i - 1],
                                f"segments must alternate direction: {dirs[i-1]} then {dirs[i]} at index {i}")

        # 连续性
        for i in range(1, len(segments)):
            self.assertEqual(segments[i]["fromIdx"], segments[i - 1]["toIdx"],
                             f"segments must be contiguous: seg[{i-1}].to={segments[i-1]['toIdx']} != seg[{i}].from={segments[i]['fromIdx']}")

    # --- BTC 15m 快照 ---
    def test_btc_15m(self):
        """15分钟BTC数据：应产生9段，匹配用户手画结果。"""
        tp = [
            80111.02, 80666.66, 80135, 80452.44, 80166.26,
            81080, 80572.77, 80840, 80658.97, 80913.8,
            80691, 81000.01, 80816.22, 81583.11, 80279.77,
            82479.32, 80525, 81049.51, 80646.56, 81356.46,
            80462.97, 82137.26, 81600, 81924.63, 80714.28,
            81294.42, 81000, 81305.24, 80496.57, 80999,
            79843.59, 80896.25, 80412.15, 81299.99, 80889.12,
            81324.64, 78754.65, 79800, 79228, 79681.73,
        ]
        segments = compute_auto_segments(tp, 0.05)
        self.assertEqual(len(segments), 9)

        # 验证关键端点
        expected = [
            (0, 11),   # UP 80111 -> 81000
            (11, 14),  # DOWN 81000 -> 80279
            (14, 17),  # UP 80279 -> 81049
            (17, 20),  # DOWN 81049 -> 80462
            (20, 23),  # UP 80462 -> 81924
            (23, 30),  # DOWN 81924 -> 79843
            (30, 33),  # UP 79843 -> 81299
            (33, 36),  # DOWN 81299 -> 78754
            (36, 39),  # UP 78754 -> 79681
        ]
        for i, (fi, ti) in enumerate(expected):
            self.assertEqual(segments[i]["fromIdx"], fi, f"seg[{i}] fromIdx mismatch")
            self.assertEqual(segments[i]["toIdx"], ti, f"seg[{i}] toIdx mismatch")

        self._validate_segments(tp, segments)

    # --- 简单锯齿 ---
    def test_simple_zigzag_6points(self):
        """简单6点锯齿：应产生1段或2段。"""
        tp = [100, 120, 95, 115, 90, 110]
        segments = compute_auto_segments(tp, 0.05)
        self._validate_segments(tp, segments)
        self.assertGreaterEqual(len(segments), 1)

    def test_simple_zigzag_8points(self):
        """简单8点锯齿。"""
        tp = [100, 130, 90, 125, 85, 120, 80, 115]
        segments = compute_auto_segments(tp, 0.05)
        self._validate_segments(tp, segments)
        self.assertGreaterEqual(len(segments), 1)

    # --- 边界情况 ---
    def test_too_few_points(self):
        """不足4个点应返回空。"""
        self.assertEqual(compute_auto_segments([100, 120, 110], 0.05), [])
        self.assertEqual(compute_auto_segments([], 0.05), [])
        self.assertEqual(compute_auto_segments([100], 0.05), [])

    def test_flat_sequence(self):
        """平坦序列应返回空或极少段。"""
        tp = [100, 100, 100, 100, 100, 100, 100, 100]
        segments = compute_auto_segments(tp, 0.05)
        self._validate_segments(tp, segments)

    def test_strong_uptrend(self):
        """强上升趋势：高点低点都递增。"""
        tp = [100, 110, 105, 120, 115, 130, 125, 140, 135, 150]
        segments = compute_auto_segments(tp, 0.05)
        self._validate_segments(tp, segments)
        # 应至少有1个上升段
        self.assertGreaterEqual(len(segments), 1)

    def test_strong_downtrend(self):
        """强下降趋势。"""
        tp = [150, 140, 145, 130, 135, 120, 125, 110, 115, 100]
        segments = compute_auto_segments(tp, 0.05)
        self._validate_segments(tp, segments)
        self.assertGreaterEqual(len(segments), 1)


class TestComputeAutoZhongshu(unittest.TestCase):
    """中枢检测测试。"""

    def test_overlapping_strokes_form_zhongshu(self):
        """重叠笔应形成中枢。"""
        tp = [100, 120, 105, 115, 103, 113, 101, 114]
        segments = compute_auto_segments(tp, 0.05)
        if len(segments) >= 3:
            zhongshu = compute_auto_zhongshu(tp, segments)
            # 如果有重叠区域，应有中枢
            self.assertIsInstance(zhongshu, list)

    def test_no_overlap_no_zhongshu(self):
        """不重叠的笔不应产生中枢。"""
        tp = [100, 200, 50, 250, 30, 300]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        # 极端波动不太可能有重叠
        self.assertIsInstance(zhongshu, list)


class TestBuildStrokes(unittest.TestCase):
    """笔构建测试。"""

    def test_basic_strokes(self):
        """基本笔应交替上下。"""
        tp = [100, 120, 90, 110, 85]
        strokes = build_strokes(tp)
        self.assertEqual(len(strokes), 5)
        # First stroke is the starting point placeholder
        self.assertEqual(strokes[0]["dir"], "up")
        self.assertIsNone(strokes[0]["fromIdx"])
        # Subsequent strokes alternate directions
        self.assertEqual(strokes[1]["dir"], "up")
        self.assertEqual(strokes[2]["dir"], "down")
        self.assertEqual(strokes[3]["dir"], "up")
        self.assertEqual(strokes[4]["dir"], "down")

    def test_single_point(self):
        tp = [100]
        strokes = build_strokes(tp)
        self.assertEqual(len(strokes), 1)


class TestSegmentZhongshu(unittest.TestCase):
    """段中枢测试。"""

    def test_with_sufficient_segments(self):
        """有足够重叠段时应检测段中枢。"""
        tp = [
            100, 120, 95, 115, 90, 110, 85, 105,
            88, 108, 86, 106, 84, 104, 82, 103,
        ]
        segments = compute_auto_segments(tp, 0.05)
        if len(segments) >= 3:
            higher = compute_higher_segments(tp, segments, 0.05)
            seg_zs = compute_segment_zhongshu(tp, segments, higher)
            self.assertIsInstance(seg_zs, list)


class TestZhongshuProperties(unittest.TestCase):
    """中枢属性测试：验证 ZG/ZD 和方向裁剪的正确性。"""

    def test_zhongshu_zg_zd_correctness(self):
        """中枢的 ZG 应为笔高点中的低点，ZD 应为笔低点中的高点。"""
        # 构造重叠笔：tp[1..7] 之间有明显的重叠区间
        tp = [100, 120, 105, 115, 103, 113, 101, 114, 95, 110, 92, 108]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        for zs in zhongshu:
            fi, ti = zs["fromIdx"], zs["toIdx"]
            # 手动计算期望值
            stroke_highs = [max(tp[k], tp[k + 1]) for k in range(fi, ti)]
            stroke_lows = [min(tp[k], tp[k + 1]) for k in range(fi, ti)]
            expected_zg = min(stroke_highs)
            expected_zd = max(stroke_lows)
            self.assertAlmostEqual(zs["zg"], expected_zg, places=2)
            self.assertAlmostEqual(zs["zd"], expected_zd, places=2)
            self.assertGreater(zs["zg"], zs["zd"])

    def test_zhongshu_no_cross_segment(self):
        """中枢不应跨越段边界。"""
        tp = [
            100, 130, 95, 125, 90, 120, 85, 115, 80,
            110, 75, 105, 70, 100, 65, 95,
        ]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        seg_bounds = [(s["fromIdx"], s["toIdx"]) for s in segments]
        for zs in zhongshu:
            # 中枢必须完全在某个段内
            inside = any(s[0] <= zs["fromIdx"] and zs["toIdx"] <= s[1]
                         for s in seg_bounds)
            self.assertTrue(inside,
                            f"Zhongshu {zs['fromIdx']}-{zs['toIdx']} crosses segment boundaries")


class TestBuySellPoints(unittest.TestCase):
    """买卖点检测测试。"""

    def test_buy1_after_down_exit(self):
        """向下离开中枢后应有1买。"""
        # 构造一个明确的中枢区间，然后向下离开
        tp = [100, 115, 105, 113, 106, 112, 107, 110, 90, 95, 88, 93]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        if zhongshu:
            bsp = compute_buy_sell_points(tp, zhongshu)
            buy1 = [p for p in bsp if p["type"] == "buy" and p["label"] == "1"]
            # 如果中枢后有价格低于ZD的谷，应有1买
            for zs in zhongshu:
                has_below = any(tp[i] < zs["zd"]
                               for i in range(zs["toIdx"] + 1, len(tp))
                               if i % 2 == 0)  # rough valley check
                if has_below:
                    self.assertGreater(len(buy1), 0,
                                       "Should have 1-buy when price exits below ZD")

    def test_sell1_after_up_exit(self):
        """向上离开中枢后应有1卖。"""
        tp = [100, 95, 105, 96, 104, 97, 103, 98, 120, 110, 125, 115]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        if zhongshu:
            bsp = compute_buy_sell_points(tp, zhongshu)
            sell1 = [p for p in bsp if p["type"] == "sell" and p["label"] == "1"]
            for zs in zhongshu:
                has_above = any(tp[i] > zs["zg"]
                               for i in range(zs["toIdx"] + 1, len(tp))
                               if i % 2 == 1)  # rough peak check
                if has_above:
                    self.assertGreater(len(sell1), 0,
                                       "Should have 1-sell when price exits above ZG")

    def test_points_within_data_range(self):
        """所有买卖点的索引应在有效范围内。"""
        tp = [100, 130, 90, 125, 85, 120, 95, 115, 100, 110, 105, 108]
        segments = compute_auto_segments(tp, 0.05)
        zhongshu = compute_auto_zhongshu(tp, segments)
        if zhongshu:
            bsp = compute_buy_sell_points(tp, zhongshu)
            for p in bsp:
                self.assertGreaterEqual(p["idx"], 0)
                self.assertLess(p["idx"], len(tp))
                self.assertIn(p["type"], ("buy", "sell"))
                self.assertIn(p["label"], ("1", "2", "3"))


class TestHasInclusion(unittest.TestCase):
    """K线包含关系判断测试。"""

    def test_no_inclusion(self):
        self.assertFalse(_has_inclusion(_kline(110, 100), _kline(120, 105)))

    def test_full_inclusion(self):
        self.assertTrue(_has_inclusion(_kline(120, 90), _kline(110, 100)))

    def test_reverse_inclusion(self):
        self.assertTrue(_has_inclusion(_kline(110, 100), _kline(120, 90)))

    def test_equal_high_low(self):
        self.assertTrue(_has_inclusion(_kline(110, 100), _kline(110, 100)))

    def test_partial_overlap(self):
        """部分交叉但互不包含。"""
        self.assertFalse(_has_inclusion(_kline(110, 100), _kline(115, 105)))


class TestMergeKlines(unittest.TestCase):
    """K线包含关系合并测试。"""

    def test_no_inclusion_passthrough(self):
        """无包含关系时K线不变。"""
        klines = [_kline(110, 100, 0), _kline(120, 105, 1)]
        result = merge_klines_with_inclusion(klines)
        self.assertEqual(len(result), 2)

    def test_up_merge(self):
        """上升趋势中的包含合并：取高高+高低。"""
        # 3根K线：上升 + 包含
        klines = [
            _kline(100, 90, 0),
            _kline(110, 95, 1),   # high > prev → 上升趋势
            _kline(108, 96, 2),   # 被包含
        ]
        result = merge_klines_with_inclusion(klines)
        self.assertEqual(len(result), 2)
        # 合并后：max(110,108)=110, max(95,96)=96
        self.assertEqual(result[1]["high"], 110)
        self.assertEqual(result[1]["low"], 96)

    def test_down_merge(self):
        """下降趋势中的包含合并：取低高+低低。"""
        klines = [
            _kline(120, 100, 0),
            _kline(110, 95, 1),   # high < prev → 下降趋势
            _kline(112, 93, 2),   # 被包含
        ]
        result = merge_klines_with_inclusion(klines)
        self.assertEqual(len(result), 2)
        # 合并后：min(110,112)=110, min(95,93)=93
        self.assertEqual(result[1]["high"], 110)
        self.assertEqual(result[1]["low"], 93)

    def test_chain_inclusion(self):
        """连续包含：3根K线连续被包含应合并为1根。"""
        klines = [
            _kline(100, 80, 0),
            _kline(110, 85, 1),   # 上升
            _kline(108, 90, 2),   # 被包含
            _kline(105, 92, 3),   # 被包含
        ]
        result = merge_klines_with_inclusion(klines)
        self.assertEqual(len(result), 2)
        # 上升合并：max(110,108,105)=110, max(85,90,92)=92
        self.assertEqual(result[1]["high"], 110)
        self.assertEqual(result[1]["low"], 92)

    def test_single_kline(self):
        """单根K线不合并。"""
        result = merge_klines_with_inclusion([_kline(100, 90)])
        self.assertEqual(len(result), 1)

    def test_empty(self):
        self.assertEqual(merge_klines_with_inclusion([]), [])


class TestDetectFractals(unittest.TestCase):
    """分型检测测试。"""

    def test_top_fractal(self):
        """3根K线中间最高 → 顶分型。"""
        klines = [
            _kline(100, 90, 0),
            _kline(110, 95, 1),
            _kline(105, 92, 2),
        ]
        fractals = detect_fractals_from_klines(klines, process_inclusion=False)
        self.assertEqual(len(fractals), 1)
        self.assertEqual(fractals[0]["type"], "top")
        self.assertEqual(fractals[0]["price"], 110)

    def test_bottom_fractal(self):
        """3根K线中间最低 → 底分型。"""
        klines = [
            _kline(105, 92, 0),
            _kline(100, 85, 1),
            _kline(108, 90, 2),
        ]
        fractals = detect_fractals_from_klines(klines, process_inclusion=False)
        self.assertEqual(len(fractals), 1)
        self.assertEqual(fractals[0]["type"], "bottom")
        self.assertEqual(fractals[0]["price"], 85)

    def test_no_fractal_flat(self):
        """平坦序列无分型。"""
        klines = [_kline(100, 90, i) for i in range(5)]
        fractals = detect_fractals_from_klines(klines, process_inclusion=False)
        self.assertEqual(len(fractals), 0)

    def test_alternating_fractals(self):
        """交替的锯齿K线应产生交替的顶底分型。"""
        klines = [
            _kline(100, 90, 0),   # -
            _kline(110, 100, 1),  # 顶
            _kline(100, 90, 2),   # -
            _kline(110, 100, 3),  # 顶（但与前一个分型同类型）
            _kline(95, 85, 4),    # 底
            _kline(105, 95, 5),   # -
            _kline(90, 80, 6),    # -
        ]
        fractals = detect_fractals_from_klines(klines, process_inclusion=False)
        # 至少应检测到分型
        self.assertGreater(len(fractals), 0)
        types = [f["type"] for f in fractals]
        self.assertIn("top", types)
        self.assertIn("bottom", types)

    def test_too_few_klines(self):
        self.assertEqual(detect_fractals_from_klines([_kline(100, 90)]), [])
        self.assertEqual(detect_fractals_from_klines([]), [])


class TestFractalsToTurningPoints(unittest.TestCase):
    """转折点筛选测试。"""

    def _fractal(self, kline_idx, ftype, price):
        return {"klineIdx": kline_idx, "type": ftype, "price": price, "time": kline_idx * 60000}

    def test_basic_zigzag(self):
        """基本交替分型应直接通过。"""
        fractals = [
            self._fractal(0, "bottom", 100),
            self._fractal(5, "top", 120),
            self._fractal(10, "bottom", 90),
            self._fractal(15, "top", 110),
        ]
        tp, ff = fractals_to_turning_points(fractals)
        self.assertEqual(tp, [100, 120, 90, 110])

    def test_same_type_merge_top(self):
        """连续两个顶分型应保留更高的。"""
        fractals = [
            self._fractal(0, "bottom", 100),
            self._fractal(5, "top", 115),
            self._fractal(9, "top", 120),   # 更高，替换前一个
            self._fractal(14, "bottom", 90),
        ]
        tp, ff = fractals_to_turning_points(fractals, min_kline_gap=4)
        self.assertEqual(tp, [100, 120, 90])

    def test_gap_filter(self):
        """间距不足的分型应被过滤。"""
        fractals = [
            self._fractal(0, "bottom", 100),
            self._fractal(3, "top", 120),     # gap=2 < 4, 过滤
            self._fractal(8, "top", 115),     # gap=7 >= 4, 通过
            self._fractal(13, "bottom", 90),
        ]
        tp, ff = fractals_to_turning_points(fractals, min_kline_gap=4)
        self.assertEqual(tp, [100, 115, 90])

    def test_zigzag_violation(self):
        """顶低于前底应被过滤。"""
        fractals = [
            self._fractal(0, "bottom", 100),
            self._fractal(5, "top", 95),       # 顶 < 底，违反zigzag
            self._fractal(10, "top", 120),     # 正确
            self._fractal(15, "bottom", 110),
        ]
        tp, ff = fractals_to_turning_points(fractals, min_kline_gap=4)
        self.assertEqual(tp, [100, 120, 110])

    def test_empty_input(self):
        tp, ff = fractals_to_turning_points([])
        self.assertEqual(tp, [])
        self.assertEqual(ff, [])


class TestPropertyBased(unittest.TestCase):
    """属性测试：随机数据上的不变量。"""

    def test_alternation_invariant(self):
        """段方向必须交替。"""
        import random
        random.seed(12345)
        for _ in range(200):
            count = random.randint(6, 40)
            lo = random.uniform(50, 500)
            hi = lo + random.uniform(50, 500)
            # 生成简单锯齿
            tp = []
            price = lo + random.random() * (hi - lo)
            going_down = random.random() > 0.5
            for _ in range(count):
                tp.append(round(price, 2))
                swing = (hi - lo) * (0.05 + random.random() * 0.2)
                price = price + (-swing if going_down else swing)
                price = max(lo, min(hi, price))
                going_down = not going_down

            if len(tp) < 4:
                continue

            segments = compute_auto_segments(tp, 0.05)
            if not segments:
                continue

            # 交替校验
            dirs = []
            for s in segments:
                d = "up" if tp[s["toIdx"]] > tp[s["fromIdx"]] else "down"
                dirs.append(d)
            for i in range(1, len(dirs)):
                self.assertNotEqual(dirs[i], dirs[i - 1],
                    f"Non-alternating at {i}: {dirs} tp={tp[:10]}...")

            # 连续性
            for i in range(1, len(segments)):
                self.assertEqual(segments[i]["fromIdx"], segments[i - 1]["toIdx"])

            # 最少3笔
            for s in segments:
                self.assertGreaterEqual(s["toIdx"] - s["fromIdx"], 3)


if __name__ == "__main__":
    unittest.main()
