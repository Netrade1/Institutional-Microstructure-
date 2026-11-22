"""Isolated checks for the read-only L2 integration boundary."""
import unittest
from integrations.smart_l2_readonly import ReadOnlyBook, FeedRejected

def snap(seq=1, ts=100, rx=101):
    return {"type":"snapshot","symbol":"SPCX","seq":seq,"ts_ns":ts,"received_ns":rx,
            "bids":[["100","10"]],"asks":[["101","5"]]}

class TestReadOnlyL2(unittest.TestCase):
    def test_snapshot_and_metrics(self):
        b=ReadOnlyBook("SPCX")
        m=b.ingest(snap())
        self.assertEqual(m["status"],"RESEARCH_ONLY")
        self.assertEqual(m["obi"],str((10-5)/(10+5)) if False else "0.3333333333333333333333333333")
        self.assertTrue(m["paper_only"])

    def test_sequence_gap_fails_closed(self):
        b=ReadOnlyBook("SPCX")
        b.ingest(snap())
        with self.assertRaises(FeedRejected):
            b.ingest({"type":"delta","symbol":"SPCX","seq":3,"ts_ns":102,"received_ns":103})
        self.assertEqual(b.metrics(104)["status"],"NO_DATA")

    def test_trade_classification(self):
        b=ReadOnlyBook("SPCX")
        b.ingest(snap())
        m=b.ingest({"type":"trade","symbol":"SPCX","trade_id":"t1","price":"101","size":"4","ts_ns":102,"received_ns":103})
        self.assertEqual(m["cvd"],"4")
        self.assertEqual(m["vwap"],"101")

    def test_inside_spread_rejected(self):
        b=ReadOnlyBook("SPCX")
        b.ingest(snap())
        with self.assertRaises(FeedRejected):
            b.ingest({"type":"trade","symbol":"SPCX","trade_id":"t1","price":"100.5","size":"1","ts_ns":102,"received_ns":103})
        self.assertEqual(b.metrics(104)["status"],"NO_DATA")

    def test_receive_before_event_rejected(self):
        b=ReadOnlyBook("SPCX")
        with self.assertRaises(FeedRejected):
            b.ingest(snap(rx=99))

if __name__ == "__main__":
    unittest.main()
