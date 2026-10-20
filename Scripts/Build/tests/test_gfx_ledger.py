#!/usr/bin/env python3
"""Tests for gfx_ledger.py bank-overlap and sheet classification (no ROM needed)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gfx_ledger as g  # noqa: E402


class BankChecks(unittest.TestCase):
    def test_default_claims_do_not_overlap(self):
        self.assertEqual(g.overlap_conflicts(g.BANK_CLAIMS), [])

    def test_two_owners_on_one_bank_fail(self):
        claims = g.BANK_CLAIMS + [{"owner": "x", "lo": 0x23, "hi": 0x24, "sources": []}]
        self.assertEqual(len(g.overlap_conflicts(claims)), 1)

    def test_foreign_org_fails(self):
        out = g.source_conflicts(g.BANK_CLAIMS, [("Sprites/foo.asm", 3, 0x2A)])
        self.assertEqual(len(out), 1)
        self.assertEqual(g.source_conflicts(g.BANK_CLAIMS, [("Sprites/Bosses/ganondorf.asm", 3, 0x2A)]), [])


class Classify(unittest.TestCase):
    def test_off_limits_beats_owner(self):
        self.assertEqual(g.classify(0x7B, {}, "someone", 0)[0], "OFF-LIMITS")
        self.assertEqual(g.classify(0xD9, {}, None, 0)[0], "OFF-LIMITS")
        self.assertEqual(g.classify(0xDA, {}, None, 0)[0], "OFF-LIMITS")

    def test_free_and_check(self):
        self.assertEqual(g.classify(0x5E, {}, None, 0)[0], "FREE-ID")
        self.assertEqual(g.classify(0x5E, {}, None, 3)[0], "CHECK")
        self.assertEqual(g.classify(0x63, {}, "PR", 9)[0], "CLAIMED")


if __name__ == "__main__":
    unittest.main()
