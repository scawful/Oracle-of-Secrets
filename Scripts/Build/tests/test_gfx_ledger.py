#!/usr/bin/env python3
"""Tests for gfx_ledger.py bank-overlap and sheet classification (no ROM needed)."""
import contextlib
import io
import json
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


def find_rom(name="oos168x.sfc"):
    """Roms/ is untracked; in a worktree it lives in the main checkout."""
    roots = [g.REPO_ROOT]
    proc = subprocess.run(["git", "-C", str(g.REPO_ROOT), "rev-parse", "--git-common-dir"],
                          capture_output=True, text=True)
    if proc.returncode == 0:
        common = Path(proc.stdout.strip())
        roots.append((common if common.is_absolute() else g.REPO_ROOT / common).resolve().parent)
    for root in roots:
        if (root / "Roms" / name).is_file():
            return root / "Roms" / name
    return None


JUNGLE = [0xA6, 0xA7, 0xAE, 0xAF]
# Live ROM updated $A3/$A4/$AC to share jungle sheets $6C/$6D alongside $A6/$A7/$AE/$AF.
LIVE_JUNGLE = [0xA3, 0xA4, 0xA6, 0xA7, 0xAC, 0xAE, 0xAF]


class TailMaps(unittest.TestCase):
    def inv(self, tail):
        return {"overworld_areas": {}, "main_blocksets": {}, "room_blocksets": {},
                "spritesets": {"5": [1, 2, 3, 4]}, "tail_areas": tail,
                "sheets": [{"hex": "0x6C", "usage": {"ow_areas_static": []}}]}

    def test_tail_area_rows_count_as_users(self):
        row = {"static_graphics": [0x69, 0x3B, 0x3C, 0x6C, 0x6D, 0x6E, 0x96, 0x5B],
               "sprite_graphics": [5, 5, 0]}
        inv = self.inv({str(a): row for a in JUNGLE})
        L = g.build_loaders(inv)
        self.assertEqual(L[0x6C]["area"], {3: JUNGLE})
        self.assertEqual(L[0x6D]["area"], {4: JUNGLE})
        self.assertEqual(L[0x74]["area_spriteset"][0], [a for a in JUNGLE for _ in range(2)])
        # z3ed does not list tail maps, so they are not a cross-check mismatch.
        self.assertEqual(g.check_inventory_usage(inv, L), [])
        # An empty stub with tail users is no longer reported as a free id.
        n = sum(len(v) for kinds in L[0x6C].values() for v in kinds.values())
        self.assertEqual(g.classify(0x6C, {}, None, n)[0], "CHECK")

    def test_inventory_without_tail_areas_still_builds(self):
        inv = self.inv({})
        del inv["tail_areas"]
        L = g.build_loaders(inv)
        self.assertFalse(any({"area", "area_spriteset"} & set(kinds) for kinds in L.values()))

    def test_real_rom_jungle_maps_load_6c_6d(self):
        rom = find_rom()
        if rom is None:
            self.skipTest("Roms/oos168x.sfc not present")
        before = g.sha256(rom)
        tail = g.read_tail_areas(rom.read_bytes())  # read-only
        self.assertEqual(sorted(tail), list(range(0xA0, 0xC0)))
        L = g.build_loaders(self.inv({str(a): v for a, v in tail.items()}))
        for sheet in (0x6C, 0x6D):
            users = sorted({a for ids in L[sheet]["area"].values() for a in ids})
            self.assertEqual(users, LIVE_JUNGLE, f"sheet ${sheet:02X}")
        self.assertEqual(g.sha256(rom), before)


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


class AsmAndJsonLoaders(unittest.TestCase):
    def test_scan_asm_catches_lastsprset_aa3_and_kits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Sprites").mkdir()
            (root / "Sprites" / "maple.asm").write_text(
                "LDA.b #$55 : STA.l LASTSPRSET3\nLDA.b #$42 : STA.l LASTSPRSET1\n"
            )
            (root / "Sprites" / "owl.asm").write_text(
                "LDA.w $0AA3 : CMP.b #$05 : BEQ .ok\n"
            )
            (root / "Dungeons").mkdir()
            (root / "Dungeons" / "kits.asm").write_text(
                "org $00DDF7\n  db $FD, read1($00DDC4), read1($00DDC5), $F4\npullpc\n"
            )
            (root / "Data" / "graphics").mkdir(parents=True)
            (root / "Data" / "graphics" / "d4_zora_sprite_sheets.json").write_text(json.dumps({
                "sheets": [
                    {"sprite_sheet": "0x64", "source": "spr64.png"},
                    {"global_sheet": "0xE7", "source": "refuge.txt", "flag": "ENABLE_D4_ZORA_REDESIGN"},
                ]
            }))
            inv = {
                "overworld_areas": {},
                "main_blocksets": {},
                "room_blocksets": {},
                "spritesets": {"5": [1, 2, 3, 4]},
                "sheets": [{"hex": "0x5E", "kind": "3bpp", "pc": "0x000000", "unreferenced": True, "usage": {}}],
            }
            L = g.build_loaders(inv, repo_root=root, include_code_refs=True)
            # LASTSPRSET3 #$55 -> 0x55 + 0x73 = 0xC8; LASTSPRSET1 #$42 -> 0xB5
            self.assertIn(3, L[0xC8]["asm_code"])
            self.assertIn(1, L[0xB5]["asm_code"])
            # $0AA3 == #$05 -> spriteset [1,2,3,4] -> 0x74..0x77
            self.assertIn(0, L[0x74]["asm_code"])
            # Kit blockset -> $FD, $F4
            self.assertIn(0, L[0xFD]["asm_code"])
            self.assertIn(3, L[0xF4]["asm_code"])
            # JSON specs -> 0x64+0x73 = 0xD7 (Impa follower), 0xE7 (refuge)
            self.assertIn(0, L[0xD7]["json_spec"])
            self.assertIn(0, L[0xE7]["json_spec"])
            # Fixed follower loader -> 0xCB, 0xD7, 0xD9
            self.assertIn(0, L[0xCB]["asm_code"])
            self.assertIn(0, L[0xD9]["asm_code"])
            rows = g.build_rows(inv, {}, repo_root=root)
            by_sid = {r["sheet"]: r for r in rows}
            self.assertEqual(by_sid[0xE7]["status"], "IN-USE")
            self.assertEqual(by_sid[0xFD]["status"], "IN-USE")


if __name__ == "__main__":
    unittest.main()
