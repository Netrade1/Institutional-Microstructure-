"""Cross-component temporal, authority, and replay publication boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from integrations.liquidity_sweep import DetectorConfig
from integrations.smart_l2_readonly import FeedRejected, ReadOnlyBook
from integrations.sweep_research import SweepResearchPipeline, replay_file


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic_sweep_bars.jsonl"


def rows():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines()]


def pipeline(book=None):
    return SweepResearchPipeline("SYNTH", 60_000_000_000, "synthetic-fixture",
                                 book=book, market_source="synthetic-book" if book else None)


def snapshot(row, **changes):
    asof = row["asof_ns"]
    value = {"type": "snapshot", "symbol": "SYNTH", "seq": 1,
             "ts_ns": asof - 2, "received_ns": asof - 1,
             "source": "synthetic-book", "session_id": row["bar"]["session_id"],
             "bids": [["10.05", "100"]], "asks": [["10.07", "90"]]}
    value.update(changes)
    return value


class SweepResearchTests(unittest.TestCase):
    def test_actual_buy_and_sell_remain_no_trade_without_book(self):
        p = pipeline()
        result = [p.ingest_bar(x["bar"], asof_ns=x["asof_ns"]) for x in rows()]
        directions = [x["price_pattern"]["candidate_side"] for x in result]
        self.assertEqual(directions.count("BUY"), 1)
        self.assertEqual(directions.count("SELL"), 1)
        for observation in result:
            self.assertEqual(observation["decision"], "NO_TRADE")
            self.assertEqual(observation["authority"], "EVIDENCE_ONLY")
            self.assertEqual(observation["evidence_kind"], "OHLC_PRICE_PATTERN")
            self.assertIn("VERIFIED_TRUE_DELTA", observation["required_external_checks"])
            self.assertIn("SIGNED_HUMAN_APPROVAL", observation["required_external_checks"])
            self.assertFalse(observation["governance"]["live_execution_enabled"])
        self.assertTrue(result[-1]["price_pattern"]["raw_buy"])
        self.assertTrue(result[-1]["price_pattern"]["raw_sell"])
        self.assertIsNone(result[-1]["price_pattern"]["candidate_side"])

    def test_book_diagnostics_never_become_authenticated_flow(self):
        data = rows()
        p = pipeline(ReadOnlyBook("SYNTH"))
        for row in data[:11]:
            p.ingest_bar(row["bar"], asof_ns=row["asof_ns"])
        row = data[11]
        p.ingest_market_event(snapshot(row), asof_ns=row["asof_ns"])
        result = p.ingest_bar(row["bar"], asof_ns=row["asof_ns"])
        self.assertEqual(result["price_pattern"]["candidate_side"], "BUY")
        diag = result["market_diagnostics"]
        self.assertEqual(diag["values"]["status"], "RESEARCH_ONLY")
        self.assertFalse(diag["provider_authenticated"])
        self.assertEqual(diag["true_delta_verification"], "UNVERIFIED")
        self.assertEqual(diag["session_vwap_verification"], "UNVERIFIED")
        self.assertEqual(result["decision"], "NO_TRADE")

    def test_future_market_state_is_not_joined_to_earlier_bar(self):
        data = rows()
        p = pipeline(ReadOnlyBook("SYNTH"))
        p.ingest_market_event(snapshot(data[1]), asof_ns=data[1]["asof_ns"])
        result = p.ingest_bar(data[0]["bar"], asof_ns=data[0]["asof_ns"])
        self.assertEqual(result["market_diagnostics"]["reason"], "MARKET_STATE_NOT_YET_AVAILABLE")

    def test_mismatched_market_session_is_not_joined(self):
        row = rows()[0]
        p = pipeline(ReadOnlyBook("SYNTH"))
        p.ingest_market_event(snapshot(row, session_id="different"), asof_ns=row["asof_ns"])
        result = p.ingest_bar(row["bar"], asof_ns=row["asof_ns"])
        self.assertEqual(result["market_diagnostics"]["reason"], "MARKET_SESSION_MISMATCH")

    def test_market_receive_future_and_bad_scope_fail_closed(self):
        row = rows()[0]
        for change in ({"received_ns": row["asof_ns"] + 1}, {"source": "wrong"},
                       {"symbol": "WRONG"}, {"session_id": ""}, {"received_ns": True}):
            with self.subTest(change=change):
                book = ReadOnlyBook("SYNTH")
                p = pipeline(book)
                with self.assertRaises(FeedRejected):
                    p.ingest_market_event(snapshot(row, **change), asof_ns=row["asof_ns"])
                self.assertFalse(book.healthy)

    def test_new_session_cannot_continue_old_book_or_cvd(self):
        row = rows()[0]
        book = ReadOnlyBook("SYNTH")
        p = pipeline(book)
        p.ingest_market_event(snapshot(row), asof_ns=row["asof_ns"])
        book.cvd += 10
        later = deepcopy(row)
        later["asof_ns"] += 10
        p.ingest_market_event(snapshot(later, session_id="next"), asof_ns=later["asof_ns"])
        self.assertEqual(book.cvd, 0)

    def test_cli_replays_are_byte_deterministic_and_keep_full_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.jsonl", Path(directory) / "b.jsonl"
            first = replay_file(FIXTURE, a, symbol="SYNTH", timeframe_ns=60_000_000_000,
                                source="synthetic-fixture", config=DetectorConfig())
            second = replay_file(FIXTURE, b, symbol="SYNTH", timeframe_ns=60_000_000_000,
                                 source="synthetic-fixture", config=DetectorConfig())
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(first["input_sha256"], second["input_sha256"])
            self.assertEqual(first["observations"], 16)
            self.assertEqual(first["buy_setups"], 1)
            self.assertEqual(first["sell_setups"], 1)
            self.assertFalse(first["performance_tested"])

    def test_bad_input_does_not_publish_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "bad.jsonl", Path(directory) / "out.jsonl"
            source.write_text(FIXTURE.read_text().splitlines()[0] + "\n{bad json}\n")
            with self.assertRaisesRegex(ValueError, "line 2"):
                replay_file(source, output, symbol="SYNTH", timeframe_ns=60_000_000_000,
                            source="synthetic-fixture", config=DetectorConfig())
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).glob(".sweep-*.tmp")), [])

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.jsonl"
            output.write_text("retain me")
            with self.assertRaises(FileExistsError):
                replay_file(FIXTURE, output, symbol="SYNTH", timeframe_ns=60_000_000_000,
                            source="synthetic-fixture", config=DetectorConfig())
            self.assertEqual(output.read_text(), "retain me")

    def test_replay_counts_unconfirmed_and_duplicate_without_extra_candidate(self):
        data = rows()
        partial = deepcopy(data[0])
        partial["bar"]["is_closed"] = False
        stream = [partial, *data[:12], data[11], *data[12:]]
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.jsonl", Path(directory) / "output.jsonl"
            source.write_text("\n".join(json.dumps(row) for row in stream) + "\n")
            result = replay_file(source, output, symbol="SYNTH", timeframe_ns=60_000_000_000,
                                 source="synthetic-fixture", config=DetectorConfig())
            self.assertEqual(result["ignored_unconfirmed"], 1)
            self.assertEqual(result["duplicates"], 1)
            self.assertEqual(result["buy_setups"], 1)
            self.assertEqual(result["sell_setups"], 1)

    def test_unconfirmed_wrapper_still_requires_a_valid_decision_boundary(self):
        p = pipeline()
        for invalid in (True, -1, "123"):
            with self.subTest(invalid=invalid), self.assertRaises(FeedRejected):
                p.ingest_bar({"is_closed": False}, asof_ns=invalid)

    def test_duplicate_json_keys_and_nonfinite_json_are_rejected(self):
        for text in ('{"bar":{},"bar":{},"asof_ns":1}', '{"bar":{},"asof_ns":NaN}'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory) / "bad.jsonl", Path(directory) / "out.jsonl"
                source.write_text(text)
                with self.assertRaises(ValueError):
                    replay_file(source, output, symbol="SYNTH", timeframe_ns=60_000_000_000,
                                source="synthetic-fixture", config=DetectorConfig())
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
