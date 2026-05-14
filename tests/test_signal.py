"""信号引擎测试 — 区间套状态机"""

import unittest

from chanlun.signal import compute_signal, IDLE, WATCHING, CONFIRMING, READY, LONG, SHORT, NEUTRAL


def _make_result(turning_points, segments=None, zhongshu=None, buy_sell_points=None):
    """Helper: create a minimal result dict matching pipeline output structure."""
    return {
        "turningPoints": turning_points,
        "segments": segments or [],
        "zhongshu": zhongshu or [],
        "buySellPoints": buy_sell_points or [],
    }


class TestContextDirection(unittest.TestCase):

    def test_no_segments_returns_neutral(self):
        result = _make_result([100, 110, 95, 105])
        signal = compute_signal(result)
        self.assertEqual(signal["contextDirection"], NEUTRAL)

    def test_uptrend_last_segment_long(self):
        context = _make_result(
            [100, 120, 95, 130],
            segments=[{"fromIdx": 0, "toIdx": 1}, {"fromIdx": 1, "toIdx": 3}]
        )
        primary = _make_result([50, 55, 48, 52])
        signal = compute_signal(primary, context)
        self.assertEqual(signal["contextDirection"], LONG)

    def test_downtrend_last_segment_short(self):
        context = _make_result(
            [130, 100, 120, 90],
            segments=[{"fromIdx": 0, "toIdx": 1}, {"fromIdx": 1, "toIdx": 3}]
        )
        primary = _make_result([50, 55, 48, 52])
        signal = compute_signal(primary, context)
        self.assertEqual(signal["contextDirection"], SHORT)


class TestStateTransitions(unittest.TestCase):

    def test_no_context_returns_idle(self):
        primary = _make_result([100, 110, 95, 105])
        signal = compute_signal(primary)
        self.assertEqual(signal["state"], IDLE)
        self.assertEqual(signal["direction"], NEUTRAL)

    def test_context_neutral_returns_idle(self):
        context = _make_result([100, 110, 95, 105])  # no segments → neutral
        primary = _make_result([100, 110, 95, 105])
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], IDLE)

    def test_watching_when_context_clear_no_primary_zhongshu(self):
        """Context has direction, primary has no zhongshu → WATCHING."""
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result([50, 55, 48, 52])
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], WATCHING)
        self.assertEqual(signal["direction"], LONG)

    def test_watching_when_zhongshu_but_no_buy_sell(self):
        """Context direction + primary zhongshu but no matching buy/sell → WATCHING."""
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], WATCHING)

    def test_confirming_when_buy_point_no_divergence(self):
        """Buy point appears but no divergence → CONFIRMING."""
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": False}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], CONFIRMING)
        self.assertEqual(signal["direction"], LONG)
        self.assertIsNotNone(signal["activeSetup"])
        self.assertEqual(signal["activeSetup"]["hasDivergence"], False)

    def test_ready_when_buy_point_with_divergence(self):
        """Buy point with divergence → READY."""
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], READY)
        self.assertEqual(signal["activeSetup"]["hasDivergence"], True)
        self.assertEqual(signal["activeSetup"]["price"], 48)

    def test_short_direction_matching_sell_point(self):
        """Short direction + sell point with divergence → READY."""
        context = _make_result(
            [140, 100, 120, 90],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [52, 48, 55, 50],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "sell", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["state"], READY)
        self.assertEqual(signal["direction"], SHORT)


class TestInvalidation(unittest.TestCase):

    def test_direction_reversal_invalidates(self):
        """If context latest segment reverses, direction becomes neutral."""
        # Context: first segment up, second segment down → last is down
        context = _make_result(
            [100, 130, 95, 80],
            segments=[{"fromIdx": 0, "toIdx": 1}, {"fromIdx": 1, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        # Direction should be SHORT (last segment is down), not LONG
        # Buy points don't match SHORT direction → WATCHING or IDLE
        self.assertNotEqual(signal["direction"], LONG)

    def test_price_breaks_context_zhongshu_zd_for_long(self):
        """Long direction, but context last price below context zhongshu ZD → IDLE."""
        # Context: 5 turning points, last segment is up (idx 2→4), but last tp drops below ZD
        # tp = [100, 150, 120, 160, 80] — segments: up, down, up (last: 120→160, up)
        # Wait, last segment fromIdx:2(120) toIdx:4(80) is actually down...
        # Need: last segment UP but very last tp below ZD.
        # Use 6 points: segments[0→1, 1→3, 3→5], last seg 3→5 = 100→200 (up)
        # But tp[-1] = 200, not below ZD...
        # The key insight: "last price" is context_tp[-1]. For a long context,
        # the last tp should be the HIGH of the up segment, so it can't be below ZD naturally.
        # Invalidation here tests an edge case where context price drops below ZD at the very end,
        # which would mean the direction has actually reversed.
        # Let's use a scenario with more points where the last tp dips below ZD
        # even though the last segment direction is still "up":
        # tp = [90, 140, 110, 160, 80] — last segment 2→4: tp[2]=110 → tp[4]=80 (down!)
        # That's short, not long. The reality is: if last tp < ZD, direction must be short or neutral.
        # This test is actually testing an impossible state. Let me instead test a valid scenario:
        # Context with zhongshu, direction long, but the VERY LAST turning point (not segment endpoint)
        # drops below ZD after the last segment ended.
        # Since _get_context_direction uses last segment direction, I can have:
        # tp = [90, 140, 100, 160, 95, 130] — segments up to index 4+...
        # Actually, simplest: context direction is long, but context_tp[-1] is below ZD.
        # This means we need a segment ending in an up direction, but the last TP is below ZD.
        # That requires the last TP to be a valley after the last segment's endpoint...
        # which means it's outside the segment. But the segment covers up to the last index.
        #
        # Simplest valid test: context_tp[-1] < ZD, but last segment goes up
        # e.g. tp = [80, 150, 120] — segment [0→2]: 80→120 (up), but tp[-1]=120 > ZD
        # Need tp[-1] < ZD: tp = [150, 100, 80] — segment [0→2]: 150→80 (down!) = short
        # So for long: tp[-1] must be > tp[fromIdx], but also < ZD
        # e.g. tp = [60, 150, 90] — segment [0→2]: 60→90 (up), ZD=100, tp[-1]=90 < ZD ✓
        context = _make_result(
            [60, 150, 90],
            segments=[{"fromIdx": 0, "toIdx": 2}],
            zhongshu=[{"fromIdx": 0, "toIdx": 1, "zg": 140, "zd": 100}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        # Context last tp 90 < ZD 100 → invalidated
        self.assertEqual(signal["state"], IDLE)

    def test_price_breaks_context_zhongshu_zg_for_short(self):
        """Short direction, but context last price above context zhongshu ZG → IDLE."""
        # tp = [150, 80, 160] — segment [0→2]: 150→160 (up!) that's long, not short
        # Need short: tp = [150, 80, 140] — segment [0→2]: 150→140 (down ✓)
        # ZG = 130, tp[-1] = 140 > ZG ✓
        context = _make_result(
            [150, 80, 140],
            segments=[{"fromIdx": 0, "toIdx": 2}],
            zhongshu=[{"fromIdx": 0, "toIdx": 1, "zg": 130, "zd": 90}]
        )
        primary = _make_result(
            [90, 85, 95, 88],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 92, "zd": 86}],
            buy_sell_points=[{"idx": 1, "type": "sell", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        # Context last tp 140 > ZG 130 → invalidated
        self.assertEqual(signal["state"], IDLE)


class TestSymmetry(unittest.TestCase):

    def test_long_and_short_symmetric_structure(self):
        """Both directions should have same state machine structure."""
        # Long
        ctx_long = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary_long = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": False}]
        )
        sig_long = compute_signal(primary_long, ctx_long)

        # Short (mirror: swap directions)
        ctx_short = _make_result(
            [140, 100, 120, 90],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary_short = _make_result(
            [52, 48, 55, 50],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "sell", "label": "1", "hasDivergence": False}]
        )
        sig_short = compute_signal(primary_short, ctx_short)

        # Both should be CONFIRMING (buy/sell point without divergence)
        self.assertEqual(sig_long["state"], CONFIRMING)
        self.assertEqual(sig_short["state"], CONFIRMING)
        self.assertEqual(sig_long["direction"], LONG)
        self.assertEqual(sig_short["direction"], SHORT)

    def test_no_matching_points_for_opposite_direction(self):
        """Long direction + only sell points → WATCHING (not CONFIRMING)."""
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "sell", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["direction"], LONG)
        self.assertEqual(signal["state"], WATCHING)  # No buy points → watching


class TestResultFields(unittest.TestCase):

    def test_result_has_all_fields(self):
        primary = _make_result([100, 110, 95, 105])
        signal = compute_signal(primary)
        for field in ["direction", "state", "activeSetup", "contextDirection",
                       "contextSegments", "primaryZhongshu", "primaryBuySell"]:
            self.assertIn(field, signal)

    def test_counts_accurate(self):
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 1}, {"fromIdx": 1, "toIdx": 3}],
            zhongshu=[{"fromIdx": 0, "toIdx": 2, "zg": 125, "zd": 100}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[
                {"idx": 2, "type": "buy", "label": "1", "hasDivergence": True}
            ]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["contextSegments"], 2)
        self.assertEqual(signal["primaryZhongshu"], 1)
        self.assertEqual(signal["primaryBuySell"], 1)

    def test_setup_price_from_turning_points(self):
        context = _make_result(
            [100, 130, 95, 140],
            segments=[{"fromIdx": 0, "toIdx": 3}]
        )
        primary = _make_result(
            [50, 55, 48, 52],
            zhongshu=[{"fromIdx": 0, "toIdx": 3, "zg": 53, "zd": 49}],
            buy_sell_points=[{"idx": 2, "type": "buy", "label": "1", "hasDivergence": True}]
        )
        signal = compute_signal(primary, context)
        self.assertEqual(signal["activeSetup"]["price"], 48)


if __name__ == "__main__":
    unittest.main()
