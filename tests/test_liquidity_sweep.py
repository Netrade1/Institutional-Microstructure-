"""Synthetic causal and evidence-boundary tests; no market performance claims."""
from copy import deepcopy
from decimal import Decimal
import json
import unittest

from integrations.liquidity_sweep import (
    ClosedBar, DetectionRejected, DetectorConfig, LiquiditySweepDetector,
)


TF = 60_000_000_000


def bar(index, low, high, close=None, open_=None, **overrides):
    close = close if close is not None else (Decimal(str(low)) + Decimal(str(high))) / 2
    result = {
        "symbol": "SYNTH", "timeframe_ns": TF, "source": "SYNTHETIC_TEST",
        "session_id": "TEST_SESSION_A", "open_time_ns": index * TF,
        "close_time_ns": (index + 1) * TF, "received_ns": (index + 1) * TF + 1,
        "open": str(open_ if open_ is not None else close),
        "high": str(high), "low": str(low), "close": str(close), "is_closed": True,
    }
    result.update(overrides)
    return result


def detector(**config):
    return LiquiditySweepDetector("SYNTH", TF, "SYNTHETIC_TEST", DetectorConfig(swing_length=2, **config))


def ingest(engine, candle, **kwargs):
    return engine.ingest(candle, asof_ns=kwargs.get("asof_ns", candle["received_ns"]))


def seed_low(engine):
    # Center bar 2 is a unique low; highs deliberately do not form a unique pivot.
    candles = [bar(i, low, 14) for i, low in enumerate([12, 11, 10, 11, 12])]
    return [ingest(engine, item) for item in candles]


def seed_both(engine):
    # One unique outside pivot supplies high=14 and low=10.
    pairs = [(12, 13), (11, 13), (10, 14), (11, 13), (12, 13)]
    return [ingest(engine, bar(i, lo, hi)) for i, (lo, hi) in enumerate(pairs)]


class TestCausalPivots(unittest.TestCase):
    def test_pivot_unavailable_until_right_bars_close(self):
        e = detector()
        events = seed_low(e)
        for event in events[:4]:
            self.assertIsNone(event["levels"]["low"])
            self.assertIsNone(event["candidate_side"])
        level = events[4]["levels"]["low"]
        self.assertEqual(level["price"], "10")
        self.assertEqual(level["pivot_close_time_ns"], 3 * TF)
        self.assertEqual(level["confirmed_close_time_ns"], 5 * TF)
        self.assertEqual(level["confirmed_asof_ns"], 5 * TF + 1)
        self.assertEqual(level["age_bars"], 0)

    def test_default_requires_five_right_bars(self):
        e = LiquiditySweepDetector("SYNTH", TF, "SYNTHETIC_TEST")
        values = [15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15]
        events = [ingest(e, bar(i, lo, 20)) for i, lo in enumerate(values)]
        self.assertTrue(all(item["levels"]["low"] is None for item in events[:-1]))
        self.assertEqual(events[-1]["levels"]["low"]["pivot_close_time_ns"], 6 * TF)

    def test_future_suffix_does_not_change_prefix(self):
        prefix = [bar(i, low, 14) for i, low in enumerate([12, 11, 10, 11, 12])]
        suffix = [bar(5, 9, 13, close=11), bar(6, 8, 15, close=10)]
        a, b = detector(), detector()
        prefix_only = [ingest(a, item) for item in prefix]
        extended = [ingest(b, item) for item in prefix + suffix]
        self.assertEqual(prefix_only, extended[:len(prefix)])

    def test_equal_extrema_do_not_confirm_a_pivot(self):
        e = detector()
        events = [ingest(e, bar(i, lo, 14)) for i, lo in enumerate([12, 10, 10, 11, 12])]
        self.assertIsNone(events[-1]["levels"]["low"])
        self.assertEqual(events[-1]["policy"]["pivot_tie_policy"], "REJECT_TIED_EXTREMES")

    def test_new_pivot_replaces_old_level_before_sweep(self):
        e = detector(one_per_level=False)
        seed_low(e)  # old low 10
        for item in [bar(5, 11, 14), bar(6, 8, 14), bar(7, 9, 14)]:
            ingest(e, item)
        event = ingest(e, bar(8, 9, 14, close=11))
        self.assertEqual(event["levels"]["low"]["price"], "8")
        self.assertFalse(event["raw_buy"])  # would have swept the old low 10

    def test_same_bar_cannot_breach_the_pivot_it_confirms(self):
        e = detector()
        event = seed_both(e)[-1]
        self.assertFalse(event["raw_buy"])
        self.assertFalse(event["raw_sell"])


class TestPatternRules(unittest.TestCase):
    def test_buy_with_red_candle(self):
        e = detector()
        seed_low(e)
        event = ingest(e, bar(5, 9, 13, close=11, open_=12))
        self.assertTrue(event["raw_buy"])
        self.assertEqual(event["candidate_side"], "BUY")
        self.assertEqual(event["decision"], "NO_TRADE")

    def test_sell_with_green_candle(self):
        e = detector()
        seed_both(e)
        event = ingest(e, bar(5, 11, 15, close=13, open_=12))
        self.assertTrue(event["raw_sell"])
        self.assertEqual(event["candidate_side"], "SELL")

    def test_strict_buy_equalities_and_failed_reclaim(self):
        for low, close in [(10, 11), (9, 10), (9, "9.5")]:
            with self.subTest(low=low, close=close):
                e = detector()
                seed_low(e)
                event = ingest(e, bar(5, low, 13, close=close))
                self.assertFalse(event["raw_buy"])

    def test_strict_sell_equalities_and_failed_rejection(self):
        for high, close in [(14, 13), (15, 14), (15, "14.5")]:
            with self.subTest(high=high, close=close):
                e = detector()
                seed_both(e)
                event = ingest(e, bar(5, 11, high, close=close))
                self.assertFalse(event["raw_sell"])

    def test_both_signals_suppressed_without_consuming_levels(self):
        e = detector()
        seed_both(e)
        event = ingest(e, bar(5, 9, 15, close=12))
        self.assertTrue(event["raw_buy"] and event["raw_sell"])
        self.assertIsNone(event["candidate_side"])
        self.assertIn("AMBIGUOUS_DUAL_SWEEP", event["reasons"])
        self.assertFalse(event["levels"]["low"]["used"])
        self.assertFalse(event["levels"]["high"]["used"])
        self.assertEqual(ingest(e, bar(6, 9, 13, close=11))["candidate_side"], "BUY")

    def test_repeat_suppression_preserves_raw_pattern(self):
        e = detector()
        seed_low(e)
        first = ingest(e, bar(5, 9, 13, close=11))
        second = ingest(e, bar(6, 9, 13, close=11))
        self.assertEqual(first["candidate_side"], "BUY")
        self.assertTrue(second["raw_buy"])
        self.assertIsNone(second["candidate_side"])
        self.assertIn("LEVEL_ALREADY_USED", second["reasons"])

    def test_repeat_policy_can_be_disabled(self):
        e = detector(one_per_level=False)
        seed_low(e)
        self.assertEqual(ingest(e, bar(5, 9, 13, close=11))["candidate_side"], "BUY")
        self.assertEqual(ingest(e, bar(6, 9, 13, close=11))["candidate_side"], "BUY")

    def test_expiry_is_measured_after_confirmation(self):
        e = detector(max_age_bars=1)
        seed_low(e)
        ingest(e, bar(5, 11, 14))
        event = ingest(e, bar(6, 9, 13, close=11))
        self.assertTrue(event["raw_buy"])
        self.assertIsNone(event["candidate_side"])
        self.assertEqual(event["levels"]["low"]["age_bars"], 2)
        self.assertIn("LEVEL_EXPIRED", event["reasons"])

    def test_original_rule_allows_reclaim_from_below(self):
        e = detector()
        seed_low(e)
        ingest(e, bar(5, 9, 13, close="9.5"))
        event = ingest(e, bar(6, "9.2", 13, close=11, open_="9.5"))
        self.assertEqual(event["candidate_side"], "BUY")


class TestStateAndValidation(unittest.TestCase):
    def test_unconfirmed_bar_does_not_advance_or_consume(self):
        e = detector()
        seed_low(e)
        candidate = bar(5, 9, 13, close=11)
        result = ingest(e, {**candidate, "is_closed": False})
        self.assertEqual(result["status"], "IGNORED")
        self.assertEqual(ingest(e, candidate)["candidate_side"], "BUY")

    def test_exact_duplicate_is_idempotent(self):
        e = detector()
        seed_low(e)
        candidate = bar(5, 9, 13, close=11)
        first = ingest(e, candidate)
        duplicate = ingest(e, candidate, asof_ns=candidate["received_ns"] + 10)
        self.assertEqual(duplicate["event_id"], first["event_id"])
        self.assertEqual(duplicate["status"], "DUPLICATE")
        self.assertIsNone(duplicate["candidate_side"])
        self.assertTrue(e.healthy)

    def test_correction_latches_without_mutating_accepted_state(self):
        e = detector()
        seed_low(e)
        old = e._last_result.copy()
        with self.assertRaises(DetectionRejected):
            ingest(e, bar(4, 12, 14, close="12.5"))
        self.assertFalse(e.healthy)
        self.assertEqual(e._last_result, old)
        with self.assertRaises(DetectionRejected):
            ingest(e, bar(5, 9, 13, close=11))
        e.reset()
        self.assertEqual(seed_low(e)[-1]["levels"]["low"]["price"], "10")

    def test_out_of_order_and_overlapping_bars_rejected(self):
        for item in [bar(2, 11, 14), bar(4, 11, 14, open_time_ns=4 * TF + TF // 2,
                                                  close_time_ns=5 * TF + TF // 2,
                                                  received_ns=5 * TF + TF // 2 + 1)]:
            with self.subTest(item=item):
                e = detector()
                seed_low(e)
                with self.assertRaises(DetectionRejected):
                    ingest(e, item, asof_ns=10 * TF)

    def test_session_change_resets_levels_and_warmup(self):
        e = detector()
        seed_low(e)
        event = ingest(e, bar(5, 9, 13, close=11, session_id="TEST_SESSION_B"))
        self.assertFalse(event["raw_buy"])
        self.assertIsNone(event["levels"]["low"])
        self.assertIn("SESSION_RESET", event["reasons"])

    def test_session_reset_can_be_disabled_explicitly(self):
        e = detector(reset_on_session=False)
        seed_low(e)
        event = ingest(e, bar(5, 9, 13, close=11, session_id="TEST_SESSION_B"))
        self.assertEqual(event["candidate_side"], "BUY")

    def test_missing_bar_resets_even_with_session_reset_disabled(self):
        e = detector(reset_on_session=False)
        seed_low(e)
        event = ingest(e, bar(6, 9, 13, close=11))
        self.assertIn("GAP_RESET", event["reasons"])
        self.assertEqual(event["status"], "WARMUP")
        self.assertIsNone(event["levels"]["low"])

    def test_future_availability_rejected(self):
        item = bar(0, 10, 12)
        with self.assertRaises(DetectionRejected):
            ingest(detector(), item, asof_ns=item["received_ns"] - 1)

    def test_receive_before_close_rejected(self):
        with self.assertRaises(DetectionRejected):
            ingest(detector(), bar(0, 10, 12, received_ns=TF - 1))

    def test_receive_and_asof_regressions_rejected(self):
        for kind in ("receive", "asof"):
            with self.subTest(kind=kind):
                e = detector()
                ingest(e, bar(0, 10, 12, received_ns=5 * TF), asof_ns=6 * TF)
                item = bar(1, 10, 12, received_ns=4 * TF if kind == "receive" else 5 * TF + 1)
                with self.assertRaises(DetectionRejected):
                    ingest(e, item, asof_ns=6 * TF + 1 if kind == "receive" else 5 * TF + 1)

    def test_invalid_inputs_fail_closed(self):
        cases = [
            {"high": "NaN"}, {"low": "Infinity"}, {"open": True}, {"close": "0"},
            {"low": "13"}, {"high": "9"}, {"received_ns": True},
            {"is_closed": 1}, {"is_closed": "true"}, {"symbol": "OTHER"},
            {"source": "OTHER"}, {"timeframe_ns": TF // 2}, {"session_id": ""},
            {"open_time_ns": -1}, {"close": "1e999999999"}, {"received_ns": 2**64},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                e = detector()
                item = bar(0, 10, 12)
                item.update(changes)
                with self.assertRaises(DetectionRejected):
                    ingest(e, item)
                self.assertFalse(e.healthy)

    def test_missing_field_and_bad_configuration(self):
        item = bar(0, 10, 12)
        del item["source"]
        with self.assertRaises(DetectionRejected):
            ingest(detector(), item)
        for changes in [{"swing_length": 1}, {"swing_length": True}, {"one_per_level": 1},
                        {"reset_on_session": "true"}, {"max_age_bars": -1}]:
            with self.subTest(changes=changes), self.assertRaises(DetectionRejected):
                DetectorConfig(**changes)

    def test_direct_dataclass_is_revalidated(self):
        item = ClosedBar.from_mapping(bar(0, 10, 12))
        self.assertEqual(ingest(detector(), item.to_mapping())["status"], "WARMUP")
        bad = deepcopy(item)
        object.__setattr__(bad, "is_closed", 1)
        with self.assertRaises(DetectionRejected):
            detector().ingest(bad, asof_ns=item.received_ns)
        bad_price = deepcopy(item)
        object.__setattr__(bad_price, "close", True)
        with self.assertRaises(DetectionRejected):
            detector().ingest(bad_price, asof_ns=item.received_ns)

    def test_output_mutation_does_not_corrupt_duplicate_or_levels(self):
        e = detector()
        seed_low(e)
        item = bar(5, 9, 13, close=11)
        event = ingest(e, item)
        event["levels"]["low"]["price"] = "999"
        event["governance"]["execution_authorized"] = True
        duplicate = ingest(e, item)
        self.assertEqual(duplicate["levels"]["low"]["price"], "10")
        self.assertFalse(duplicate["governance"]["execution_authorized"])

    def test_policy_affects_identity_and_all_events_are_evidence_only(self):
        a, b = detector(), detector(one_per_level=False)
        left, right = seed_low(a)[-1], seed_low(b)[-1]
        self.assertNotEqual(left["event_id"], right["event_id"])
        for event in [left, right, ingest(a, bar(5, 9, 13, close=11))]:
            self.assertEqual(event["decision"], "NO_TRADE")
            self.assertEqual(event["evidence_type"], "OHLC_PRICE_PATTERN")
            self.assertEqual(event["provenance"]["source_authentication"], "UNVERIFIED")
            self.assertEqual(event["provenance"]["tape_sweep_confirmation"], "NOT_PROVIDED")
            self.assertFalse(event["governance"]["execution_authorized"])
            json.dumps(event, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
