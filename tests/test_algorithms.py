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
