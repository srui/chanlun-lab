"""K 线缓存模块测试"""

import os
import tempfile
import unittest

# 使用临时数据库，避免污染正式数据
_test_db_dir = tempfile.mkdtemp()

import chanlun.kline_cache as kc

# 替换数据库路径为临时目录
kc.DB_PATH = os.path.join(_test_db_dir, "test_klines.db")


def _kline(open_time, high, low, close=None, volume=1.0):
    return {
        "openTime": open_time,
        "open": low,
        "high": high,
        "low": low,
        "close": close if close is not None else high,
        "volume": volume,
        "closeTime": open_time + 59999,
    }


class TestKlineCache(unittest.TestCase):

    def test_save_and_get(self):
        """写入后应能读取相同数据。"""
        klines = [_kline(1000, 110, 100), _kline(2000, 120, 105), _kline(3000, 115, 103)]
        kc.save_klines("BTC", "1h", klines)
        result = kc.get_cached_klines("BTC", "1h")
        # 最后一根不缓存（未收盘），只缓存前两根
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["openTime"], 1000)
        self.assertEqual(result[1]["openTime"], 2000)

    def test_skip_last_kline(self):
        """最后一根 K 线不应被缓存。"""
        klines = [_kline(1000, 110, 100)]
        kc.save_klines("ETH", "1h", klines)
        result = kc.get_cached_klines("ETH", "1h")
        # 单根 K 线是"最后一根"，不缓存
        self.assertEqual(len(result), 0)

    def test_overwrite_on_duplicate(self):
        """重复写入同一时间戳应覆盖。"""
        # 写 3 根，缓存前 2 根（最后一根不缓存）
        kc.save_klines("SOL", "1h", [_kline(1000, 110, 100), _kline(2000, 120, 105), _kline(3000, 130, 110)])
        # 再写 3 根（前两根时间戳相同），缓存前 2 根覆盖
        kc.save_klines("SOL", "1h", [_kline(1000, 115, 95), _kline(2000, 125, 100), _kline(3000, 135, 105)])
        result = kc.get_cached_klines("SOL", "1h")
        self.assertEqual(len(result), 2)
        # 两根都被覆盖
        self.assertEqual(result[0]["high"], 115)
        self.assertEqual(result[1]["high"], 125)

    def test_time_range_filter(self):
        """应支持时间范围过滤。"""
        kc.save_klines("DOGE", "1h", [
            _kline(1000, 110, 100), _kline(2000, 120, 105),
            _kline(3000, 115, 103), _kline(4000, 118, 107),
        ])
        result = kc.get_cached_klines("DOGE", "1h", start_ms=2000, end_ms=3000)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["openTime"], 2000)
        self.assertEqual(result[1]["openTime"], 3000)

    def test_latest_cached_time(self):
        """应返回最新缓存时间戳。"""
        kc.save_klines("XRP", "1h", [
            _kline(1000, 110, 100), _kline(5000, 120, 105), _kline(9000, 115, 103),
        ])
        # 最后一根不缓存，最新应该是 5000
        latest = kc.get_latest_cached_time("XRP", "1h")
        self.assertEqual(latest, 5000)

    def test_latest_cached_time_empty(self):
        """无缓存时应返回 None。"""
        latest = kc.get_latest_cached_time("NONEXIST", "1h")
        self.assertIsNone(latest)

    def test_incremental_save(self):
        """增量写入后数据应完整。"""
        kc.save_klines("ADA", "1h", [
            _kline(1000, 110, 100), _kline(2000, 120, 105),
        ])
        kc.save_klines("ADA", "1h", [
            _kline(3000, 115, 103), _kline(4000, 118, 107),
        ])
        result = kc.get_cached_klines("ADA", "1h")
        # 第一次缓存 1 根（1000），第二次缓存 1 根（3000），共 2 根
        # 但第二次还有 4000 不缓存
        # 实际：第一次写入 1 根（1000），第二次写入 1 根（3000）
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["openTime"], 1000)
        self.assertEqual(result[1]["openTime"], 3000)

    def test_empty_save(self):
        """空列表写入不应报错。"""
        kc.save_klines("EMPTY", "1h", [])
        result = kc.get_cached_klines("EMPTY", "1h")
        self.assertEqual(result, [])


class TestIntervalConfig(unittest.TestCase):

    def test_known_pairs(self):
        """已知配对应正确返回。"""
        from chanlun.config import get_context_interval, INTERVAL_PAIRS
        self.assertEqual(get_context_interval("15m"), "1h")
        self.assertEqual(get_context_interval("1h"), "4h")
        self.assertEqual(get_context_interval("4h"), "1d")
        self.assertEqual(get_context_interval("1d"), "1w")

    def test_unknown_returns_none(self):
        """未知周期应返回 None。"""
        from chanlun.config import get_context_interval
        self.assertIsNone(get_context_interval("2m"))
        self.assertIsNone(get_context_interval("1M"))

    def test_all_pairs_have_valid_intervals(self):
        """所有配对的上下文周期应为合法 Binance 周期。"""
        from chanlun.config import INTERVAL_PAIRS
        from chanlun.binance_service import VALID_INTERVALS
        for primary, context in INTERVAL_PAIRS.items():
            self.assertIn(primary, VALID_INTERVALS, f"Primary {primary} not valid")
            self.assertIn(context, VALID_INTERVALS, f"Context {context} not valid")


class TestPollInterval(unittest.TestCase):

    def test_known_intervals(self):
        """已知周期应返回正确的轮询间隔。"""
        from chanlun.config import get_poll_interval
        self.assertEqual(get_poll_interval("5m"), 30)
        self.assertEqual(get_poll_interval("15m"), 30)
        self.assertEqual(get_poll_interval("1h"), 60)
        self.assertEqual(get_poll_interval("4h"), 300)
        self.assertEqual(get_poll_interval("1d"), 300)

    def test_unknown_returns_default(self):
        """未知周期应返回默认 60 秒。"""
        from chanlun.config import get_poll_interval
        self.assertEqual(get_poll_interval("unknown"), 60)

    def test_all_valid_intervals_covered(self):
        """所有 Binance 合法周期都应有轮询配置。"""
        from chanlun.config import POLL_INTERVALS
        from chanlun.binance_service import VALID_INTERVALS
        for interval in VALID_INTERVALS:
            self.assertIn(interval, POLL_INTERVALS, f"Missing poll interval for {interval}")

    def test_intervals_are_reasonable(self):
        """轮询间隔应在合理范围内（10-600秒）。"""
        from chanlun.config import POLL_INTERVALS
        for interval, seconds in POLL_INTERVALS.items():
            self.assertGreaterEqual(seconds, 10, f"{interval} poll too fast: {seconds}s")
            self.assertLessEqual(seconds, 600, f"{interval} poll too slow: {seconds}s")


class TestPipeline(unittest.TestCase):

    def test_analyze_klines_structure(self):
        """analyze_klines 应返回完整结构。"""
        from chanlun.pipeline import analyze_klines

        klines = [
            _kline(1000, 110, 100), _kline(2000, 105, 90),
            _kline(3000, 120, 100), _kline(4000, 100, 85),
            _kline(5000, 130, 100), _kline(6000, 105, 90),
            _kline(7000, 125, 100), _kline(8000, 100, 82),
            _kline(9000, 135, 100), _kline(10000, 108, 92),
            _kline(11000, 140, 100), _kline(12000, 105, 88),
        ]
        result = analyze_klines(klines)

        for key in ["fractals", "turningPoints", "strokes", "segments",
                     "zhongshu", "segmentZhongshu", "higherSegments", "buySellPoints"]:
            self.assertIn(key, result, f"Missing key: {key}")

        self.assertIsInstance(result["fractals"], list)
        self.assertIsInstance(result["turningPoints"], list)
        self.assertIsInstance(result["strokes"], list)
        self.assertIsInstance(result["segments"], list)

    def test_analyze_klines_too_few(self):
        """转折点不足时应返回 warning。"""
        from chanlun.pipeline import analyze_klines

        # 只有 2 根 K 线，无法检测分型
        klines = [_kline(1000, 110, 100), _kline(2000, 105, 95)]
        result = analyze_klines(klines)
        self.assertIn("warning", result)
        self.assertEqual(result["segments"], [])

    def test_recompute_consistency(self):
        """recompute_from_turning_points 结果应与 analyze_klines 的段/中枢一致。"""
        from chanlun.pipeline import analyze_klines, recompute_from_turning_points

        klines = [
            _kline(1000, 110, 100), _kline(2000, 105, 90),
            _kline(3000, 120, 100), _kline(4000, 100, 85),
            _kline(5000, 130, 100), _kline(6000, 105, 90),
            _kline(7000, 125, 100), _kline(8000, 100, 82),
            _kline(9000, 135, 100), _kline(10000, 108, 92),
            _kline(11000, 140, 100), _kline(12000, 105, 88),
        ]
        full = analyze_klines(klines)
        tp = full["turningPoints"]

        if len(tp) >= 4:
            recomputed = recompute_from_turning_points(tp)
            self.assertEqual(full["segments"], recomputed["segments"])
            self.assertEqual(full["zhongshu"], recomputed["zhongshu"])
            self.assertEqual(full["buySellPoints"], recomputed["buySellPoints"])


if __name__ == "__main__":
    unittest.main()
