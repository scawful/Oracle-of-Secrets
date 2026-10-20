#!/usr/bin/env python3
"""Tests for gfx_ledger.py bank-overlap and sheet classification (no ROM needed)."""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class GitScan(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        patcher = mock.patch.object(g, "REPO_ROOT", self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def track_asm(self, text):
        path = self.repo / "Sprites" / "foreign.asm"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        subprocess.run(["git", "-C", str(self.repo), "add", str(path)], check=True)

    def test_foreign_writers_in_collision_and_overworld_banks_fail(self):
        self.track_asm("org $258000\ndb $01\norg $288000\ndb $02\n")
        self.assertEqual(g.scan_orgs(None), [
            ("Sprites/foreign.asm", 1, 0x25),
            ("Sprites/foreign.asm", 3, 0x28),
        ])
        self.assertEqual(len(g.check_banks(g.BANK_CLAIMS, None)), 2)

    def test_invalid_ref_exits_nonzero_without_pass(self):
        self.track_asm("org $238000\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [
            "gfx_ledger.py", "--check-banks-only", "--ref", "nonexistent-ref",
        ]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(g.main(), 2)
        self.assertNotIn("PASS", stdout.getvalue())
        self.assertIn("git grep failed", stderr.getvalue())

    def test_successful_search_without_matches_passes(self):
        self.track_asm("org $018000\n")
        self.assertEqual(g.check_banks(g.BANK_CLAIMS, None), [])


if __name__ == "__main__":
    unittest.main()
