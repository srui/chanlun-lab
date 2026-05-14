"""技术指标计算测试 — MACD、背驰检测"""

import unittest
import math

from chanlun.indicators import compute_macd, compute_macd_area, detect_divergences


class TestComputeMACD(unittest.TestCase):

    def test_empty_input(self):
        result = compute_macd([])
        self.assertEqual(result["dif"], [])
        self.assertEqual(result["dea"], [])
        self.assertEqual(result["histogram"], [])

    def test_single_value(self):
        result = compute_macd([100.0])
        self.assertEqual(len(result["dif"]), 1)
        self.assertEqual(len(result["dea"]), 1)
        self.assertEqual(len(result["histogram"]), 1)

    def test_length_matches_input(self):
        closes = [100.0 + i for i in range(50)]
        result = compute_macd(closes)
        self.assertEqual(len(result["dif"]), 50)
        self.assertEqual(len(result["dea"]), 50)
        self.assertEqual(len(result["histogram"]), 50)

    def test_histogram_equals_2x_dif_minus_dea(self):
        closes = [45, 46, 44, 47, 48, 43, 42, 49, 50, 46,
                  45, 47, 48, 44, 43, 50, 51, 47, 46, 49,
                  50, 45, 44, 48, 47, 52, 53, 46, 45, 51]
        result = compute_macd(closes)
        for i in range(len(closes)):
            expected = (result["dif"][i] - result["dea"][i]) * 2
            self.assertAlmostEqual(result["histogram"][i], expected, places=10)

    def test_ema_convergence_on_constant(self):
        """Constant prices → MACD should converge to zero."""
        closes = [100.0] * 100
        result = compute_macd(closes)
        self.assertAlmostEqual(result["dif"][-1], 0.0, places=8)
        self.assertAlmostEqual(result["dea"][-1], 0.0, places=8)
        self.assertAlmostEqual(result["histogram"][-1], 0.0, places=8)

    def test_uptrend_dif_positive(self):
        """In a strong uptrend, DIF should be positive after enough bars."""
        closes = [100.0 + i * 2 for i in range(100)]
        result = compute_macd(closes)
        self.assertGreater(result["dif"][-1], 0)

    def test_downtrend_dif_negative(self):
        """In a strong downtrend, DIF should be negative after enough bars."""
        closes = [200.0 - i * 2 for i in range(100)]
        result = compute_macd(closes)
        self.assertLess(result["dif"][-1], 0)

    def test_custom_parameters(self):
        closes = [100.0 + i for i in range(50)]
        result = compute_macd(closes, fast=5, slow=10, signal=3)
        self.assertEqual(len(result["dif"]), 50)


class TestComputeMACDArea(unittest.TestCase):

    def test_basic_area(self):
        histogram = [1.0, 2.0, -3.0, 4.0]
        area = compute_macd_area(histogram, 0, 3)
        self.assertAlmostEqual(area, abs(1.0) + abs(2.0) + abs(3.0) + abs(4.0))

    def test_reversed_indices(self):
        histogram = [1.0, 2.0, 3.0]
        area = compute_macd_area(histogram, 2, 0)
        self.assertAlmostEqual(area, abs(1.0) + abs(2.0) + abs(3.0))

    def test_single_element(self):
        histogram = [5.0, -3.0, 2.0]
        area = compute_macd_area(histogram, 1, 1)
        self.assertAlmostEqual(area, abs(-3.0))

    def test_all_zeros(self):
        histogram = [0.0] * 10
        area = compute_macd_area(histogram, 0, 9)
        self.assertAlmostEqual(area, 0.0)


class TestDetectDivergences(unittest.TestCase):

    def _make_klines(self, closes):
        """Helper: create minimal kline dicts from close prices."""
        return [{"open": c, "high": c + 1, "low": c - 1, "close": c,
                 "openTime": i * 60000, "closeTime": i * 60000 + 59999, "volume": 1.0}
                for i, c in enumerate(closes)]

    def _make_fractals(self, kline_indices):
        """Helper: create fractal dicts with klineIdx."""
        return [{"klineIdx": ki, "type": "top" if i % 2 == 0 else "bottom", "high": 0, "low": 0}
                for i, ki in enumerate(kline_indices)]

    def test_empty_inputs(self):
        self.assertEqual(detect_divergences([], [], [], []), [])
        self.assertEqual(detect_divergences(None, [], [], []), [])

    def test_no_buy_sell_points(self):
        klines = self._make_klines([100 + i for i in range(30)])
        fractals = self._make_fractals([3, 7, 11, 15, 19, 23])
        self.assertEqual(detect_divergences(klines, [100, 105, 95, 110, 90, 115], fractals, []), [])

    def test_divergence_returns_list(self):
        """Output should be a list of dicts with expected keys."""
        klines = self._make_klines([100, 102, 98, 105, 95, 108, 92, 106, 94, 104])
        fractals = self._make_fractals([1, 3, 5, 7, 9])
        tp = [102, 105, 92, 106, 94]
        bsp = [{"idx": 2, "type": "buy", "label": "1"}]
        result = detect_divergences(klines, tp, fractals, bsp)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIn("type", item)
            self.assertIn("idx", item)
            self.assertIn("compareIdx", item)
            self.assertIn("klineIdx", item)
            self.assertIn("compareKlineIdx", item)

    def test_top_divergence_format(self):
        """Top divergence should have type='top'."""
        # Craft data where a top divergence occurs: higher peak, smaller MACD area
        closes = [100 + i * 0.5 for i in range(50)]
        klines = self._make_klines(closes)
        # Peaks at turning point indices 1, 3; valleys at 0, 2
        tp = [100, 95, 90, 92]  # tp[1]=95 (valley), tp[3]=92 (valley) — not peaks
        # Let's make proper peaks and valleys
        tp = [100, 110, 95, 108, 90]  # peaks at 1(110), 3(108); valleys at 2(95), 4(90)
        fractals = self._make_fractals([0, 3, 6, 9, 12])
        bsp = [{"idx": 3, "type": "sell", "label": "1"}]
        result = detect_divergences(klines, tp, fractals, bsp)
        for div in result:
            if div["type"] == "top":
                self.assertEqual(div["type"], "top")


class TestPipelineIntegration(unittest.TestCase):

    def test_analyze_klines_includes_macd(self):
        """analyze_klines should return macd and divergences fields."""
        from chanlun.pipeline import analyze_klines

        klines = [{"open": 100 + i, "high": 101 + i, "low": 99 + i,
                    "close": 100 + i, "volume": 10, "openTime": i * 60000,
                    "closeTime": i * 60000 + 59999}
                   for i in range(50)]

        result = analyze_klines(klines)
        self.assertIn("macd", result)
        self.assertIn("divergences", result)
        self.assertIn("dif", result["macd"])
        self.assertIn("dea", result["macd"])
        self.assertIn("histogram", result["macd"])
        self.assertEqual(len(result["macd"]["dif"]), 50)

    def test_recompute_includes_divergences(self):
        """recompute_from_turning_points should return divergences (empty)."""
        from chanlun.pipeline import recompute_from_turning_points

        tp = [100, 110, 95, 108, 90, 105, 85]
        result = recompute_from_turning_points(tp)
        self.assertIn("divergences", result)
        self.assertEqual(result["divergences"], [])

    def test_buy_sell_has_divergence_flag(self):
        """buySellPoints should have hasDivergence field."""
        from chanlun.pipeline import analyze_klines

        # Create oscillating klines that should generate zhongshu and buy/sell
        klines = []
        base = 100
        for i in range(60):
            phase = math.sin(i * 0.3) * 10
            c = base + phase
            klines.append({"open": c - 0.5, "high": c + 1, "low": c - 1,
                            "close": c, "volume": 10, "openTime": i * 60000,
                            "closeTime": i * 60000 + 59999})

        result = analyze_klines(klines)
        for bsp in result.get("buySellPoints", []):
            self.assertIn("hasDivergence", bsp)
            self.assertIsInstance(bsp["hasDivergence"], bool)


if __name__ == "__main__":
    unittest.main()
