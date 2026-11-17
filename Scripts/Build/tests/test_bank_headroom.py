"""Unit checks for Scripts/Build/bank_headroom.py thresholds and parsing."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bank_headroom as bh  # noqa: E402

L13 = "Bank07 Free Space: 07FDEB\nBank30 Free Space: 24 bytes\nBank31 Free Space: 83 bytes\nBank32 Free Space: 322 bytes\n"


class BankHeadroomTest(unittest.TestCase):
    def test_l13_numbers_fail_on_bank30(self):
        code, summary = bh.evaluate(bh.parse(L13))
        self.assertEqual(code, 1)
        self.assertIn("$30 24 B FAIL", summary)
        self.assertIn("$31 83 B WARN", summary)
        self.assertIn("$32 322 B WARN", summary)

    def test_thresholds_are_exclusive(self):
        free = {"30": 64, "31": 512, "32": 511}
        code, summary = bh.evaluate(free)
        self.assertEqual(code, 0)
        self.assertIn("$30 64 B WARN", summary)
        self.assertIn("$31 512 B,", summary)
        self.assertIn("$32 511 B WARN", summary)

    def test_missing_bank_fails(self):
        code, summary = bh.evaluate(bh.parse("Bank30 Free Space: 900 bytes\n"))
        self.assertEqual(code, 1)
        self.assertIn("$31 MISSING", summary)

    def test_last_line_wins_after_reassembly(self):
        text = L13 + "Bank30 Free Space: 700 bytes\nBank31 Free Space: 700 bytes\nBank32 Free Space: 700 bytes\n"
        self.assertEqual(bh.evaluate(bh.parse(text))[0], 0)

    def test_negative_free_space_fails(self):
        self.assertEqual(bh.evaluate({"30": -5, "31": 900, "32": 900})[0], 1)


if __name__ == "__main__":
    unittest.main()
