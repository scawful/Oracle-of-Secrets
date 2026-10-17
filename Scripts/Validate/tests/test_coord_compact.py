"""Tests for Scripts/Agents/coord_compact.py (AFS coordination-file compaction).

Planning tests are pure (text in, plan out). Apply tests use a temporary
directory as the scratchpad root; nothing touches the real AFS files.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "Agents" / "coord_compact.py"
spec = importlib.util.spec_from_file_location("coord_compact", SCRIPT)
cc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cc  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(cc)

NOW_ISO = "2026-10-17T20:00:00Z"
NOW = cc.parse_now(NOW_ISO)
GOAL = "Current goal: Christmas 2026 1.0 (handoffs/christmas_delivery_2026-10-15/DELIVERY_PLAN.md)"


def owner_section(name: str, stamp: str, result: str = "done", handoff: str = "handoffs/x/WORK.md",
                  extra: tuple[str, ...] = ()) -> str:
    return "\n".join([f"## {name} — {stamp}", f"Result: {result}", "Ran: tests PASS", "Next: review",
                      "Holds: none", f"Handoff: {handoff}", *extra])


LEGACY_INBOX = "\n".join([
    "## Current: Yaze INSTALLED — October 17, 20:30 UTC",
    "Status paragraph one, RELEASED.",
    "",
    "Status paragraph two.",
    "",
    "## Historical updates below — current status is above",
    "- Codex → Claude, October 16: old bullet status",
    "",
    GOAL,
    "",
    "# Inbox",
    "One line per ask: `YYYY-MM-DD from -> to: ask (handoff path)`.",
    "",
    "2026-10-15 codex -> cursor: confirm runner readiness (handoffs/ci/README.md)",
    "DONE 2026-10-16 claude -> codex: review PR 170 (handoffs/pr170.md)",
    "2026-10-01 claude -> codex: old ask nobody answered (handoffs/old.md)",
    "2026-10-17 19:44 UTC codex -> claude,cursor: heavy lock claimed (handoffs/lock.md)",
    "stray prose line",
]) + "\n"

LEGACY_BOARD = "\n".join([
    "## Current: Combined Yaze INSTALLED — October 17",
    "Long prepended status block.",
    "",
    "# Agent board (Oracle of Secrets + yaze + Mesen2-OOS)",
    "Intro text.",
    "",
    "## Rules (scawful, 2026-09-26: fans)",
    "1. Heavy lock. `mkdir /tmp/oos-heavy.lock` before a C++ build.",
    "2. Throttle with `taskpolicy -b nice -n 10`.",
    "",
    "## Sessions (updated 2026-09-26)",
    "| Session | Lane | Current task |",
    "|---|---|---|",
    "| Codex | yaze | DONE |",
    "",
    owner_section("Codex", "2026-10-17 18:00Z", result="older", handoff="handoffs/codex/OLD.md"),
    "",
    owner_section("Codex", "2026-10-17 19:30Z", result="newer", handoff="handoffs/codex/NEW.md"),
    "",
    owner_section("Claude", "2026-10-12 10:00Z", result="stale"),
    "",
]) + "\n"

LEGACY_HANDOFF = "\n".join([
    "## Current: Combined Yaze INSTALLED — October 17",
    "Same status as the board.",
    "",
    "# Current handoff — 2026-10-10",
    "Old handoff prose.",
    "",
    "## Next Tasks (Priority Order)",
    "1. something",
]) + "\n"

TEXTS = {cc.BOARD: LEGACY_BOARD, cc.HANDOFF: LEGACY_HANDOFF, cc.INBOX: LEGACY_INBOX}


def plan_for(texts=None, **kwargs):
    return cc.build_plan(dict(texts or TEXTS), NOW, **kwargs)


def reasons(file_plan):
    return {m.block.first: (m.dest, m.reason) for m in file_plan.moves}


class SplitTests(unittest.TestCase):
    def test_section_split_round_trips(self):
        for text in (LEGACY_BOARD, LEGACY_HANDOFF):
            blocks = cc.split_sections(text)
            rebuilt = [ln for b in blocks for ln in b.lines if ln.strip()]
            self.assertEqual(rebuilt, cc.nonblank(cc.split_lines(text)))
        firsts = [b.first for b in cc.split_sections(LEGACY_BOARD)]
        self.assertIn("## Rules (scawful, 2026-09-26: fans)", firsts)
        self.assertEqual(firsts.count("## Codex — 2026-10-17 19:30Z"), 1)

    def test_heading_inside_code_fence_does_not_split(self):
        text = "## A\n```bash\n# comment\n```\nafter\n## B\nx\n"
        self.assertEqual([b.first for b in cc.split_sections(text)], ["## A", "## B"])

    def test_inbox_status_block_is_one_block_and_messages_are_lines(self):
        blocks = cc.split_inbox(LEGACY_INBOX)
        self.assertEqual(blocks[0].lines[-1], "Status paragraph two.")
        self.assertIn("Status paragraph one, RELEASED.", blocks[0].lines)
        rebuilt = [ln for b in blocks for ln in b.lines if ln.strip()]
        self.assertEqual(rebuilt, cc.nonblank(cc.split_lines(LEGACY_INBOX)))
        singles = [b.first for b in blocks if len(b.lines) == 1]
        self.assertIn(GOAL, singles)
        self.assertIn("2026-10-01 claude -> codex: old ask nobody answered (handoffs/old.md)", singles)


class InboxTests(unittest.TestCase):
    def test_done_and_expired_lines_move_open_lines_stay_in_order(self):
        plan = plan_for()
        got = reasons(plan.files[cc.INBOX])
        self.assertEqual(got["DONE 2026-10-16 claude -> codex: review PR 170 (handoffs/pr170.md)"],
                         ("archive", "done"))
        self.assertEqual(got["2026-10-01 claude -> codex: old ask nobody answered (handoffs/old.md)"],
                         ("archive", "expired"))
        self.assertEqual(got["stray prose line"], ("archive", "not-an-ask"))
        self.assertEqual(got["## Historical updates below — current status is above"],
                         ("archive", "not-an-ask"))
        after = plan.files[cc.INBOX].after.splitlines()
        self.assertEqual(after[2:], [
            "2026-10-15 codex -> cursor: confirm runner readiness (handoffs/ci/README.md)",
            "2026-10-17 19:44 UTC codex -> claude,cursor: heavy lock claimed (handoffs/lock.md)",
        ])

    def test_goal_is_pinned_to_line_1_and_format_to_line_2(self):
        after = plan_for().files[cc.INBOX].after.splitlines()
        self.assertEqual(after[0], GOAL)
        self.assertEqual(after[1], cc.INBOX_FORMAT)

    def test_max_age_is_configurable(self):
        plan = plan_for(inbox_max_age_days=1)
        got = reasons(plan.files[cc.INBOX])
        self.assertEqual(got["2026-10-15 codex -> cursor: confirm runner readiness (handoffs/ci/README.md)"],
                         ("archive", "expired"))

    def test_missing_goal_refuses_without_writing(self):
        texts = dict(TEXTS, **{cc.INBOX: LEGACY_INBOX.replace(GOAL, "goal moved elsewhere")})
        plan = plan_for(texts)
        self.assertTrue(any("Current goal" in e for e in plan.errors))
        self.assertIsNone(plan.files[cc.INBOX].after)
        with self.assertRaises(cc.Refused):
            cc.apply_plan(plan, Path("/nonexistent-root"), {})

    def test_long_open_line_is_flagged_not_truncated(self):
        long_line = "2026-10-17 claude -> codex: " + "x" * 300 + " (handoffs/y.md)"
        texts = dict(TEXTS, **{cc.INBOX: f"{GOAL}\n{long_line}\n"})
        plan = plan_for(texts)
        self.assertIn(long_line, plan.files[cc.INBOX].after.splitlines())
        self.assertTrue(any("over 240 chars" in f for f in plan.files[cc.INBOX].flags))


class BoardTests(unittest.TestCase):
    def test_duplicate_owner_sections_keep_the_newest(self):
        plan = plan_for()
        got = reasons(plan.files[cc.BOARD])
        self.assertEqual(got["## Codex — 2026-10-17 19:30Z"], ("keep", "owner"))
        self.assertEqual(got["## Codex — 2026-10-17 18:00Z"], ("archive", "superseded"))
        self.assertIn("Result: newer", plan.files[cc.BOARD].after)
        self.assertNotIn("Result: older", plan.files[cc.BOARD].after)

    def test_stale_owner_section_is_archived_and_replaced_by_idle_stub(self):
        plan = plan_for()
        self.assertEqual(reasons(plan.files[cc.BOARD])["## Claude — 2026-10-12 10:00Z"],
                         ("archive", "stale-owner"))
        after = plan.files[cc.BOARD].after
        self.assertIn(cc.idle_stub("Claude"), after)
        self.assertIn(cc.idle_stub("Cursor"), after)

    def test_board_header_has_title_lock_and_goal(self):
        after = plan_for().files[cc.BOARD].after.splitlines()
        self.assertEqual(after[:3], [cc.BOARD_TITLE, cc.LOCK_SEED, GOAL])

    def test_existing_lock_line_is_kept(self):
        board = "\n".join([cc.BOARD_TITLE, "Heavy lock: codex since 2026-10-17 19:50Z", "old goal", ""])
        plan = plan_for(dict(TEXTS, **{cc.BOARD: board}))
        after = plan.files[cc.BOARD].after.splitlines()
        self.assertEqual(after[1], "Heavy lock: codex since 2026-10-17 19:50Z")
        self.assertEqual(after[2], GOAL)
        # The old header block (with its stale goal copy) goes to the archive, not away.
        self.assertEqual([m.reason for m in plan.files[cc.BOARD].archived], ["header-refresh"])

    def test_rules_move_to_board_rules_once(self):
        plan = plan_for()
        self.assertEqual(reasons(plan.files[cc.BOARD])["## Rules (scawful, 2026-09-26: fans)"],
                         ("rules", "rules"))
        self.assertIn("2. Throttle with `taskpolicy -b nice -n 10`.", plan.rules_new)
        again = plan_for(rules_exists=True)
        self.assertIsNone(again.rules_new)
        self.assertEqual(reasons(again.files[cc.BOARD])["## Rules (scawful, 2026-09-26: fans)"],
                         ("archive", "rules-copy"))

    def test_oversize_owner_section_is_reported_not_truncated(self):
        extra = tuple(f"note {i}" for i in range(4)) + ("y" * 200,)
        section = owner_section("Cursor", "2026-10-17 19:00Z", extra=extra)
        plan = plan_for(dict(TEXTS, **{cc.BOARD: LEGACY_BOARD + "\n" + section + "\n"}))
        self.assertIn(section, plan.files[cc.BOARD].after)
        flags = " | ".join(plan.files[cc.BOARD].flags)
        self.assertIn("Cursor section", flags)
        self.assertIn("body lines, over 5", flags)
        self.assertIn("over 160 chars", flags)

    def test_handoff_becomes_index_with_owner_handoff_paths(self):
        plan = plan_for()
        after = plan.files[cc.HANDOFF].after.splitlines()
        self.assertEqual(after[0], cc.HANDOFF_TITLE)
        self.assertIn("Codex: handoffs/codex/NEW.md", after)
        self.assertIn("Claude: -", after)
        self.assertTrue(all(m.dest == "archive" for m in plan.files[cc.HANDOFF].moves))


class PartitionTests(unittest.TestCase):
    def test_every_block_has_exactly_one_destination(self):
        plan = plan_for()
        self.assertEqual(plan.errors, [])
        for fp in plan.files.values():
            self.assertEqual(cc.check_partition(fp), [])
            self.assertEqual(len(fp.moves), len(fp.blocks))

    def test_partition_check_catches_a_dropped_block(self):
        fp = plan_for().files[cc.BOARD]
        broken = cc.FilePlan(fp.name, fp.before, fp.blocks, fp.moves[1:], fp.after)
        self.assertTrue(cc.check_partition(broken))


def tree_state(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        for name, text in TEXTS.items():
            (self.root / name).write_text(text, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cc.main(["--root", str(self.root), "--now", NOW_ISO, *args])
        return code, out.getvalue()

    def plan_from_disk(self):
        texts, stamps = cc.read_targets(self.root)
        return cc.build_plan(texts, NOW, rules_exists=stamps[cc.RULES].exists), stamps

    def test_dry_run_writes_nothing(self):
        before = tree_state(self.root)
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertEqual(tree_state(self.root), before)

    def test_apply_archives_verbatim_then_rewrites(self):
        plan, _ = self.plan_from_disk()
        code, _ = self.run_cli("--apply")
        self.assertEqual(code, 0)
        archive = self.root / "archive" / "coordination" / "2026-10-17"
        for name in cc.TARGETS:
            self.assertEqual((self.root / name).read_text(encoding="utf-8"), plan.files[name].after)
            archived_text = (archive / name).read_text(encoding="utf-8")
            for move in plan.files[name].archived:
                self.assertIn(move.block.text, archived_text)
        self.assertEqual((self.root / cc.RULES).read_text(encoding="utf-8"), plan.rules_new)
        receipt = json.loads((archive / cc.RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual(receipt["runs"][-1]["status"], "applied")
        self.assertEqual(len(receipt["runs"][-1]["archived"][cc.INBOX]), len(plan.files[cc.INBOX].archived))
        self.assertFalse((self.root / cc.LOCK_DIR).exists())

    def test_second_run_makes_no_change(self):
        self.assertEqual(self.run_cli("--apply")[0], 0)
        first = tree_state(self.root)
        code, out = self.run_cli("--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: no-change", out)
        self.assertEqual(tree_state(self.root), first)

    def test_target_changed_after_read_aborts_before_any_write(self):
        plan, stamps = self.plan_from_disk()
        with open(self.root / cc.INBOX, "a", encoding="utf-8") as handle:
            handle.write("2026-10-17 claude -> codex: written during the run (handoffs/z.md)\n")
        before = tree_state(self.root)
        with self.assertRaises(cc.Refused):
            cc.apply_plan(plan, self.root, stamps)
        self.assertEqual(tree_state(self.root), before)
        self.assertFalse((self.root / "archive").exists())

    def test_change_after_archiving_keeps_the_new_text_and_rerun_does_not_rearchive(self):
        plan, stamps = self.plan_from_disk()
        original_append = cc.append_verified
        concurrent = "2026-10-17 codex -> claude: written mid-run (handoffs/w.md)\n"

        def append_then_concurrent_write(path, chunk, blocks):
            original_append(path, chunk, blocks)
            if path.name == cc.INBOX:
                with open(self.root / cc.INBOX, "a", encoding="utf-8") as handle:
                    handle.write(concurrent)

        cc.append_verified = append_then_concurrent_write
        try:
            with self.assertRaises(cc.Refused):
                cc.apply_plan(plan, self.root, stamps)
        finally:
            cc.append_verified = original_append
        self.assertTrue((self.root / cc.INBOX).read_text(encoding="utf-8").endswith(concurrent))
        archive = self.root / "archive" / "coordination" / "2026-10-17" / cc.INBOX
        archived_once = archive.read_text(encoding="utf-8")
        self.assertEqual(self.run_cli("--apply")[0], 0)
        self.assertEqual(archive.read_text(encoding="utf-8"), archived_once)
        self.assertIn(concurrent.strip(), (self.root / cc.INBOX).read_text(encoding="utf-8"))

    def test_held_lock_refuses(self):
        (self.root / cc.LOCK_DIR).mkdir()
        plan, stamps = self.plan_from_disk()
        with self.assertRaises(cc.Refused):
            cc.apply_plan(plan, self.root, stamps)
        self.assertFalse((self.root / "archive").exists())

    def test_archive_symlink_outside_root_refuses(self):
        with tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, self.root / "archive")
            plan, stamps = self.plan_from_disk()
            with self.assertRaises(cc.Refused):
                cc.apply_plan(plan, self.root, stamps)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_symlinked_target_refuses(self):
        real = self.root / "real_inbox.md"
        (self.root / cc.INBOX).rename(real)
        os.symlink(real, self.root / cc.INBOX)
        code, _ = self.run_cli()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
