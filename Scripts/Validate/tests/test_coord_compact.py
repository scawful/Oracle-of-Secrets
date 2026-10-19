"""Tests for Scripts/Agents/coord_compact.py (AFS coordination-file compaction).

Planning tests are pure (text in, plan out). Apply tests use a temporary
directory as the scratchpad root; nothing touches the real AFS files.
"""
from __future__ import annotations

import contextlib
import errno
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "Scripts" / "Agents" / "coord_compact.py"
spec = importlib.util.spec_from_file_location("coord_compact", SCRIPT)
cc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cc  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(cc)

NOW_ISO = "2026-10-17T20:00:00Z"
NOW = cc.parse_now(NOW_ISO)
GOAL = "Current goal: Christmas 2026 1.0 (handoffs/christmas_delivery_2026-10-15/DELIVERY_PLAN.md)"
STRICT_ASK = "2026-10-17 19:50Z claude -> codex: review PR 178 (handoffs/pr178/REVIEW.md)"


def owner_section(name: str, stamp: str, result: str = "done", handoff: str = "handoffs/x/WORK.md",
                  extra: tuple[str, ...] = ()) -> str:
    return "\n".join([f"## {name} — {stamp}", f"Result: {result}", "Ran: tests PASS", "Next: review",
                      "Holds: none", f"Handoff: {handoff}", *extra])


LEGACY_INBOX = "\n".join([
    GOAL,
    "## Current: Yaze INSTALLED — October 17, 20:30 UTC",
    "Status paragraph one, RELEASED.",
    "",
    "Status paragraph two.",
    "",
    "## Historical updates below — current status is above",
    "- Codex → Claude, October 16: old bullet status",
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

# Heading lines copied verbatim from the live AFS agent_board.md (read-only, 2026-10-17T21:15Z).
CODEX_REAL_HEADINGS = [
    "## Active: Lyra normal workflow — 2026-10-17 21:02:40 UTC",
    "## Current: Combined Yaze INSTALLED — October 17, 20:30 UTC",
    "## Current: Claude editor-survey accuracy review COMPLETE — October 17, 19:33 UTC",
    "## Historical updates below — current status is above",
    "## Codex review fixes delivered — October 17, 12:32 UTC",
    "## Codex RC/Yaze delivery — October 17",
    "## Codex Portal off-camera persistence — COMPLETE, PR164 READY, 2026-10-16",
    "## Codex fixed room view — 2026-10-10 15:57 EDT",
]
REAL_NOW = cc.parse_now("2026-10-17T21:15:31Z")
REAL_BOARD = "\n\n".join(f"{h}\nbody of section {i}." for i, h in enumerate(CODEX_REAL_HEADINGS)) + "\n"


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
        self.assertEqual(blocks[0].lines, [GOAL])
        self.assertEqual(blocks[1].lines[-1], "Status paragraph two.")
        self.assertIn("Status paragraph one, RELEASED.", blocks[1].lines)
        rebuilt = [ln for b in blocks for ln in b.lines if ln.strip()]
        self.assertEqual(rebuilt, cc.nonblank(cc.split_lines(LEGACY_INBOX)))
        singles = [b.first for b in blocks if len(b.lines) == 1]
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

    def test_goal_looking_line_elsewhere_is_archived_and_flagged(self):
        inbox = LEGACY_INBOX + "Current goal: an older goal pasted lower down\n"
        plan = plan_for(dict(TEXTS, **{cc.INBOX: inbox}))
        self.assertEqual(plan.errors, [])
        self.assertEqual(plan.files[cc.INBOX].after.splitlines()[0], GOAL)
        self.assertEqual(reasons(plan.files[cc.INBOX])["Current goal: an older goal pasted lower down"],
                         ("archive", "extra-goal"))
        self.assertTrue(any("goal-looking" in f for f in plan.files[cc.INBOX].flags))

    def test_goal_not_on_line_1_refuses_and_names_the_line(self):
        lines = LEGACY_INBOX.splitlines()
        moved = "\n".join(lines[1:6] + [GOAL] + lines[6:]) + "\n"
        plan = plan_for(dict(TEXTS, **{cc.INBOX: moved}))
        self.assertTrue(any("line 1 is not a 'Current goal:' line" in e and "line 6" in e for e in plan.errors))
        self.assertIsNone(plan.files[cc.INBOX].after)

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

    def test_default_report_lists_malformed_archived_inbox_lines(self):
        report = cc.render_markdown(cc.report_dict(plan_for(), Path("/r")), list_moved=False)
        section = report.split("Archived inbox lines that are not open asks", 1)[1]
        self.assertIn("stray prose line", section)
        self.assertIn("(not-an-ask", section)
        self.assertIn("## Current: Yaze INSTALLED", section)


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

    def test_board_title_points_to_board_rules(self):
        self.assertIn(f"Load rules: {cc.RULES_POINTER}", cc.BOARD_TITLE)
        self.assertEqual(cc.RULES_POINTER, f"scratchpad/{cc.RULES}")

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


class LegacyHeadingTests(unittest.TestCase):
    """Codex's real heading style: '## Current: ... — October 17, 20:30 UTC', '## Codex ... — 2026-10-16'."""

    def plan(self, migrate=False):
        texts = {cc.BOARD: REAL_BOARD, cc.HANDOFF: "", cc.INBOX: GOAL + "\n"}
        return cc.build_plan(texts, REAL_NOW, migrate=migrate)

    def test_heading_time_reads_codex_date_styles(self):
        def at(heading):
            return cc.heading_time(heading, REAL_NOW)
        self.assertEqual(at(CODEX_REAL_HEADINGS[1]), (cc.parse_now("2026-10-17T20:30:00Z"), True))
        self.assertEqual(at(CODEX_REAL_HEADINGS[0]), (cc.parse_now("2026-10-17T21:02:00Z"), True))
        self.assertEqual(at(CODEX_REAL_HEADINGS[7]), (cc.parse_now("2026-10-10T19:57:00Z"), True))
        self.assertEqual(at(CODEX_REAL_HEADINGS[5]), (cc.parse_now("2026-10-17T00:00:00Z"), False))
        self.assertEqual(at("## Catalog full build ACTIVE — PR168 merged, October16"),
                         (cc.parse_now("2026-10-16T00:00:00Z"), False))
        self.assertEqual(at(CODEX_REAL_HEADINGS[3]), (None, False))

    def test_owner_named_first_is_that_owners_section(self):
        plan = self.plan()
        got = reasons(plan.files[cc.BOARD])
        self.assertEqual(got["## Codex review fixes delivered — October 17, 12:32 UTC"], ("keep", "owner"))
        self.assertEqual(got["## Codex RC/Yaze delivery — October 17"], ("archive", "superseded"))
        self.assertEqual(got[CODEX_REAL_HEADINGS[6]], ("archive", "superseded"))
        self.assertEqual(got["## Codex fixed room view — 2026-10-10 15:57 EDT"], ("archive", "stale-owner"))
        flags = " | ".join(plan.files[cc.BOARD].flags)
        self.assertIn("Codex section (source line", flags)
        self.assertIn("legacy heading", flags)

    def test_unattributed_recent_sections_stay_on_the_board_and_are_flagged(self):
        plan = self.plan()
        self.assertEqual(plan.errors, [])
        got = reasons(plan.files[cc.BOARD])
        after = plan.files[cc.BOARD].after
        for heading in CODEX_REAL_HEADINGS[:3]:
            self.assertEqual(got[heading], ("keep", "unattributed"), heading)
            self.assertIn(heading, after)
        # 'Current: Claude editor-survey ...' was written by Codex; it is not taken as Claude's section.
        self.assertIn(cc.idle_stub("Claude"), after)
        flags = " | ".join(plan.files[cc.BOARD].flags)
        self.assertEqual(flags.count("unattributed recent section kept"), 3)
        self.assertEqual(got[CODEX_REAL_HEADINGS[3]], ("archive", "history"))
        self.assertIn("no owner and no date archived", flags)

    def test_migrate_does_not_carry_legacy_sections_but_flags_them(self):
        plan = self.plan(migrate=True)
        board = plan.files[cc.BOARD]
        self.assertTrue(board.archive_whole)
        for owner in cc.DEFAULT_OWNERS:
            self.assertIn(cc.idle_stub(owner), board.after)
        self.assertNotIn("Combined Yaze", board.after)
        self.assertTrue(any("not carried forward" in f for f in board.flags))


class SubOwnerTests(unittest.TestCase):
    """'## Claude-Kydrog — ...' is a side session's own section, not an older Claude section
    (live board 2026-10-18: the default run archived it as superseded by '## Claude')."""

    def texts(self, kydrog_stamp="2026-10-17 18:59Z", claude_stamp="2026-10-17 19:32Z", kydrog=None):
        kydrog = kydrog or owner_section("Claude-Kydrog", kydrog_stamp, result="kydrog art",
                                         handoff="handoffs/kydrog/WORK.md")
        board = "\n\n".join([
            "\n".join([cc.BOARD_TITLE, cc.LOCK_SEED, GOAL]),
            owner_section("Codex", "2026-10-17 19:00Z", handoff="handoffs/codex/WORK.md"),
            owner_section("Claude", claude_stamp, result="leader", handoff="handoffs/leader/HANDOFF.md"),
            cc.idle_stub("Cursor"),
            kydrog,
        ]) + "\n"
        return {cc.BOARD: board, cc.HANDOFF: "", cc.INBOX: GOAL + "\n"}

    def test_sub_owner_section_is_kept_as_its_own_owner_and_indexed(self):
        for claude_stamp in ("2026-10-17 19:32Z", "2026-10-17 18:00Z"):  # Claude newer, then older
            with self.subTest(claude_stamp=claude_stamp):
                texts = self.texts(claude_stamp=claude_stamp)
                plan = plan_for(texts)
                self.assertEqual(plan.errors, [])
                got = reasons(plan.files[cc.BOARD])
                self.assertEqual(got[f"## Claude — {claude_stamp}"], ("keep", "owner"))
                self.assertEqual(got["## Claude-Kydrog — 2026-10-17 18:59Z"], ("keep", "owner"))
                # Every block stays and the board is already in form: nothing to rewrite.
                self.assertEqual(plan.files[cc.BOARD].after, texts[cc.BOARD])
                index = plan.files[cc.HANDOFF].after.splitlines()
                self.assertIn("Claude: handoffs/leader/HANDOFF.md", index)
                self.assertIn("Claude-Kydrog: handoffs/kydrog/WORK.md", index)
                self.assertEqual(index.index("Claude-Kydrog: handoffs/kydrog/WORK.md"),
                                 index.index("Cursor: -") + 1)
                self.assertTrue(any("Claude-Kydrog" in n for n in plan.notes))
                again = cc.build_plan({n: plan.files[n].after for n in cc.TARGETS}, NOW)
                self.assertFalse(again.changes)

    def test_stale_sub_owner_is_archived_with_no_idle_stub(self):
        plan = plan_for(self.texts(kydrog_stamp="2026-10-12 10:00Z"))
        self.assertEqual(reasons(plan.files[cc.BOARD])["## Claude-Kydrog — 2026-10-12 10:00Z"],
                         ("archive", "stale-owner"))
        self.assertNotIn("Claude-Kydrog", plan.files[cc.BOARD].after)
        self.assertNotIn("Claude-Kydrog", plan.files[cc.HANDOFF].after)
        self.assertIn("Claude: handoffs/leader/HANDOFF.md", plan.files[cc.HANDOFF].after)

    def test_idle_sub_owner_stub_is_archived(self):
        plan = plan_for(self.texts(kydrog=cc.idle_stub("Claude-Kydrog")))
        self.assertEqual(reasons(plan.files[cc.BOARD])["## Claude-Kydrog — idle"],
                         ("archive", "sub-owner-idle"))
        self.assertNotIn("Claude-Kydrog", plan.files[cc.BOARD].after)

    def test_sub_owner_named_in_owners_keeps_an_idle_stub(self):
        owners = cc.DEFAULT_OWNERS + ("Claude-Kydrog",)
        plan = plan_for(self.texts(kydrog_stamp="2026-10-12 10:00Z"), owners=owners)
        self.assertIn(cc.idle_stub("Claude-Kydrog"), plan.files[cc.BOARD].after)
        self.assertIn("Claude-Kydrog: -", plan.files[cc.HANDOFF].after.splitlines())

    def test_first_word_match_does_not_take_a_hyphenated_name(self):
        first_word = cc.owner_first_word_re(cc.DEFAULT_OWNERS)
        self.assertIsNone(first_word.match("## Claude-Kydrog — 2026-10-17 18:59Z"))
        self.assertEqual(first_word.match("## Claude review notes — October 17")["owner"], "Claude")
        self.assertEqual(first_word.match("## Claude: notes — October 17")["owner"], "Claude")


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


class AgentsDocTests(unittest.TestCase):
    def test_every_load_rules_pointer_in_agents_md_names_board_rules(self):
        lines = (REPO / "AGENTS.md").read_text(encoding="utf-8").splitlines()
        pointers = [ln for ln in lines if re.search(r"load rules", ln, re.IGNORECASE)]
        self.assertGreaterEqual(len(pointers), 3)
        for line in pointers:
            self.assertIn(cc.RULES, line, line)


def tree_state(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.archive = self.root / "archive" / "coordination" / "2026-10-17"
        for name, text in TEXTS.items():
            (self.root / name).write_text(text, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cc.main(["--root", str(self.root), "--now", NOW_ISO, *args])
        return code, out.getvalue()

    def plan_from_disk(self, migrate=False):
        texts, stamps = cc.read_targets(self.root)
        return cc.build_plan(texts, NOW, rules_exists=stamps[cc.RULES].exists, migrate=migrate), stamps

    def receipt(self) -> dict:
        return json.loads((self.archive / cc.RECEIPT).read_text(encoding="utf-8"))

    def test_dry_run_writes_nothing(self):
        before = tree_state(self.root)
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertEqual(self.run_cli("--dry-run")[0], 0)
        self.assertEqual(tree_state(self.root), before)

    def test_apply_archives_verbatim_then_rewrites(self):
        plan, _ = self.plan_from_disk()
        code, _ = self.run_cli("--apply")
        self.assertEqual(code, 0)
        for name in cc.TARGETS:
            self.assertEqual((self.root / name).read_text(encoding="utf-8"), plan.files[name].after)
            archived_text = (self.archive / name).read_text(encoding="utf-8")
            for move in plan.files[name].archived:
                self.assertIn(move.block.text, archived_text)
        self.assertEqual((self.root / cc.RULES).read_text(encoding="utf-8"), plan.rules_new)
        run = self.receipt()["runs"][-1]
        self.assertEqual(run["status"], "applied")
        self.assertEqual(sorted(run["replaced"]), sorted(cc.TARGETS))
        self.assertEqual(len(run["archived"][cc.INBOX]), len(plan.files[cc.INBOX].archived))
        self.assertFalse((self.root / cc.LOCK_DIR).exists())

    def test_second_run_makes_no_change(self):
        self.assertEqual(self.run_cli("--apply")[0], 0)
        first = tree_state(self.root)
        code, out = self.run_cli("--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: no-change", out)
        self.assertEqual(tree_state(self.root), first)

    def test_blank_lines_and_trailing_spaces_in_header_and_index_do_not_wedge(self):
        self.assertEqual(self.run_cli("--apply")[0], 0)
        board = self.root / cc.BOARD
        board.write_text(board.read_text(encoding="utf-8").replace(
            cc.BOARD_TITLE + "\n", cc.BOARD_TITLE + "  \n\n", 1), encoding="utf-8")
        handoff = self.root / cc.HANDOFF
        lines = handoff.read_text(encoding="utf-8").splitlines()
        handoff.write_text("\n".join(lines[:2] + ["", lines[2] + " "] + lines[3:]) + "\n", encoding="utf-8")
        plan, _ = self.plan_from_disk()
        self.assertEqual(plan.errors, [])
        self.assertFalse(plan.changes)
        edited = tree_state(self.root)
        for _ in range(2):
            code, out = self.run_cli("--apply")
            self.assertEqual(code, 0, out)
            self.assertIn("Applied: no-change", out)
        self.assertEqual(tree_state(self.root), edited)

    def test_target_changed_after_read_aborts_before_any_write(self):
        plan, stamps = self.plan_from_disk()
        with open(self.root / cc.INBOX, "a", encoding="utf-8") as handle:
            handle.write("2026-10-17 claude -> codex: written during the run (handoffs/z.md)\n")
        before = tree_state(self.root)
        with self.assertRaises(cc.Refused):
            cc.apply_plan(plan, self.root, stamps)
        self.assertEqual(tree_state(self.root), before)
        self.assertFalse((self.root / "archive").exists())

    def test_change_after_temp_write_leaves_that_file_alone_and_rerun_does_not_rearchive(self):
        plan, stamps = self.plan_from_disk()
        original_write_temp = cc.write_temp
        concurrent = "2026-10-17 codex -> claude: written mid-run (handoffs/w.md)\n"

        def write_temp_then_concurrent_write(path, data, mode=None):
            tmp = original_write_temp(path, data, mode)
            if path.name == cc.INBOX:
                with open(self.root / cc.INBOX, "a", encoding="utf-8") as handle:
                    handle.write(concurrent)
            return tmp

        cc.write_temp = write_temp_then_concurrent_write
        try:
            run = cc.apply_plan(plan, self.root, stamps)
        finally:
            cc.write_temp = original_write_temp
        self.assertEqual(run["status"], "partial")
        self.assertIn(cc.INBOX, run["skipped"])
        self.assertNotIn(cc.INBOX, run["replaced"])
        self.assertEqual((self.root / cc.INBOX).read_text(encoding="utf-8"), LEGACY_INBOX + concurrent)
        self.assertEqual((self.root / cc.BOARD).read_text(encoding="utf-8"), plan.files[cc.BOARD].after)
        self.assertEqual(self.receipt()["runs"][-1]["archived"][cc.INBOX],
                         [m.block.sha for m in plan.files[cc.INBOX].archived])
        self.assertEqual(list(self.root.glob(".*.tmp")), [])
        archived_once = (self.archive / cc.INBOX).read_text(encoding="utf-8")
        self.assertEqual(self.run_cli("--apply")[0], 0)
        self.assertEqual((self.archive / cc.INBOX).read_text(encoding="utf-8"), archived_once)
        self.assertIn(concurrent.strip(), (self.root / cc.INBOX).read_text(encoding="utf-8"))

    def test_write_into_the_displaced_file_during_the_swap_is_saved_and_reported(self):
        plan, _ = self.plan_from_disk()
        original_exchange = cc._exchange
        late = "2026-10-17 codex -> claude: landed during the swap (handoffs/s.md)\n"

        def exchange_with_late_writer(src, dst):
            if Path(dst).name == cc.INBOX:
                with open(dst, "a", encoding="utf-8") as writer:  # opened before the swap
                    original_exchange(src, dst)
                    writer.write(late)
            else:
                original_exchange(src, dst)

        with mock.patch.object(cc, "_exchange", side_effect=exchange_with_late_writer):
            code, out = self.run_cli("--apply")
        self.assertEqual(code, 1, out)  # a hand merge is still needed
        run = self.receipt()["runs"][-1]
        self.assertEqual(run["status"], "rescued")
        self.assertIn(cc.INBOX, run["replaced"])
        self.assertNotIn(cc.INBOX, run["skipped"])
        self.assertIn("saved to", run["rescued"][cc.INBOX])
        self.assertEqual((self.root / cc.INBOX).read_text(encoding="utf-8"), plan.files[cc.INBOX].after)
        recovery = Path(run["recovery"][cc.INBOX])
        self.assertEqual(recovery.parent, self.archive)
        for name in ("planned", "displaced"):
            self.assertEqual((recovery / name).read_text(encoding="utf-8"), LEGACY_INBOX + late)
        self.assertIn("Applied: rescued", out)
        self.assertIn(f"REWRITTEN; CONCURRENT WRITE SAVED: {cc.INBOX}: ", out)
        self.assertNotIn("NOT REWRITTEN", out)

    def test_atomic_editor_save_is_retained_and_stops_remaining_rewrites(self):
        plan, _ = self.plan_from_disk()
        original_exchange = cc._exchange
        concurrent = LEGACY_BOARD + "\nA new concurrent owner must survive.\n"

        def exchange_after_editor_save(src, dst):
            self.assertEqual(Path(dst).name, cc.BOARD)  # first target only
            editor = self.root / "editor-save.tmp"
            editor.write_text(concurrent, encoding="utf-8")
            os.replace(editor, dst)
            original_exchange(src, dst)

        with mock.patch.object(cc, "_exchange", side_effect=exchange_after_editor_save) as exchange:
            code, out = self.run_cli("--apply")
        self.assertEqual(code, 1, out)
        self.assertEqual(exchange.call_count, 1)
        run = self.receipt()["runs"][-1]
        self.assertEqual(run["status"], "partial")
        self.assertEqual(run["replaced"], [cc.BOARD])
        self.assertEqual(set(run["rescued"]), {cc.BOARD})
        self.assertNotIn(cc.BOARD, run["skipped"])
        recovery = Path(run["recovery"][cc.BOARD])
        self.assertEqual((recovery / "planned").read_text(encoding="utf-8"), LEGACY_BOARD)
        self.assertEqual((recovery / "displaced").read_text(encoding="utf-8"), concurrent)
        self.assertEqual((self.root / cc.BOARD).read_text(encoding="utf-8"), plan.files[cc.BOARD].after)
        for name in (cc.HANDOFF, cc.INBOX):
            self.assertIn("stopped after", run["skipped"][name])
            self.assertEqual((self.root / name).read_text(encoding="utf-8"), TEXTS[name])
        self.assertIn(f"REWRITTEN; CONCURRENT WRITE SAVED: {cc.BOARD}: ", out)
        self.assertIn(str(recovery), out)
        self.assertFalse((self.root / cc.LOCK_DIR).exists())

    def test_open_writer_after_return_still_has_named_recovery_inode(self):
        path = self.root / "late-writer.md"
        before, proposed, late = b"original\n", b"compacted\n", b"after return\n"
        path.write_bytes(before)
        stamp = cc.stamp_of(path)
        original_inode = path.stat().st_ino
        self.archive.mkdir(parents=True)
        with path.open("ab") as writer:
            result = cc.replace_if_unchanged(path, proposed, stamp, 0o644, self.archive, NOW)
            self.assertTrue(result.written)
            self.assertIsNone(result.note)
            recovery = Path(result.recovery)
            for name in ("planned", "displaced"):
                self.assertEqual((recovery / name).stat().st_ino, original_inode)
                self.assertEqual((recovery / name).read_bytes(), before)
            writer.write(late)
            writer.flush()
        self.assertEqual(path.read_bytes(), proposed)
        for name in ("planned", "displaced"):
            self.assertEqual((recovery / name).read_bytes(), before + late)
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_recovery_directories_synced_before_exchange(self):
        path = self.root / cc.INBOX
        stamp = cc.stamp_of(path)
        self.archive.mkdir(parents=True)
        events = []
        original_sync, original_exchange = cc.fsync_dir, cc._exchange

        def sync_and_record(directory):
            original_sync(directory)
            events.append(("sync", Path(directory)))

        def exchange_and_record(src, dst):
            events.append(("exchange", Path(src)))
            original_exchange(src, dst)

        with mock.patch.object(cc, "fsync_dir", side_effect=sync_and_record), \
                mock.patch.object(cc, "_exchange", side_effect=exchange_and_record):
            result = cc.replace_if_unchanged(path, b"proposal\n", stamp, 0o644, self.archive, NOW)
        self.assertTrue(result.written)
        self.assertIsNone(result.note)
        recovery = Path(result.recovery)
        exchange_index = events.index(("exchange", recovery / "displaced"))
        before_exchange = events[:exchange_index]
        child_index = before_exchange.index(("sync", recovery))
        parent_index = before_exchange.index(("sync", self.archive))
        self.assertLess(child_index, parent_index)
        self.assertEqual(path.read_bytes(), b"proposal\n")

    def test_unsupported_exchange_keeps_live_inode_and_bytes(self):
        path = self.root / cc.INBOX
        stamp, before = cc.stamp_of(path), path.read_bytes()
        inode = path.stat().st_ino
        self.archive.mkdir(parents=True)
        with mock.patch.object(cc, "_exchange", side_effect=OSError(errno.ENOTSUP, "unsupported")):
            result = cc.replace_if_unchanged(path, b"proposal\n", stamp, 0o644, self.archive, NOW)
        self.assertFalse(result.written)
        self.assertIn("exchange unavailable or failed", result.note)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual((Path(result.recovery) / "planned").read_bytes(), before)
        self.assertEqual((Path(result.recovery) / "displaced").read_bytes(), b"proposal\n")

    def test_unsupported_platform_never_attempts_exchange(self):
        path = self.root / cc.INBOX
        stamp, before = cc.stamp_of(path), tree_state(self.root)
        with mock.patch.object(cc.sys, "platform", "unsupported-platform"), \
                mock.patch.object(cc, "_exchange") as exchange:
            result = cc.replace_if_unchanged(path, b"proposal\n", stamp, 0o644, self.archive, NOW)
        self.assertFalse(result.written)
        self.assertIn("unavailable", result.note)
        self.assertIsNone(result.recovery)
        exchange.assert_not_called()
        self.assertEqual(tree_state(self.root), before)

    def test_racing_symlink_or_directory_is_retained_without_following(self):
        self.archive.mkdir(parents=True)
        original_exchange = cc._exchange
        with tempfile.TemporaryDirectory() as outside:
            sentinel = Path(outside) / "outside.md"
            sentinel.write_bytes(b"outside content must stay untouched\n")
            outside_before = (sentinel.read_bytes(), sentinel.stat().st_ino, sentinel.stat().st_mtime_ns)
            for kind in ("symlink", "directory"):
                with self.subTest(kind=kind):
                    path = self.root / f"race-{kind}.md"
                    path.write_bytes(b"planned original\n")
                    stamp = cc.stamp_of(path)

                    def exchange_after_type_change(src, dst):
                        Path(dst).unlink()
                        if kind == "symlink":
                            Path(dst).symlink_to(sentinel)
                        else:
                            Path(dst).mkdir()
                            (Path(dst) / "child.md").write_bytes(b"concurrent directory content\n")
                        original_exchange(src, dst)

                    with mock.patch.object(cc, "_exchange", side_effect=exchange_after_type_change):
                        result = cc.replace_if_unchanged(path, b"proposal\n", stamp, 0o644, self.archive, NOW)
                    self.assertTrue(result.written)
                    self.assertIn("concurrent content or type", result.note)
                    self.assertIn("no automatic rollback", result.note)
                    recovery = Path(result.recovery)
                    self.assertEqual((recovery / "planned").read_bytes(), b"planned original\n")
                    displaced = recovery / "displaced"
                    if kind == "symlink":
                        self.assertTrue(displaced.is_symlink())
                        self.assertEqual(os.readlink(displaced), str(sentinel))
                    else:
                        self.assertTrue(displaced.is_dir())
                        self.assertEqual((displaced / "child.md").read_bytes(), b"concurrent directory content\n")
                    self.assertEqual(path.read_bytes(), b"proposal\n")
                    self.assertEqual((sentinel.read_bytes(), sentinel.stat().st_ino,
                                      sentinel.stat().st_mtime_ns), outside_before)

    def test_board_rules_is_created_only_when_missing_and_never_overwritten(self):
        plan, _ = self.plan_from_disk()
        self.assertEqual(self.run_cli("--apply")[0], 0)
        rules = self.root / cc.RULES
        self.assertEqual(rules.read_text(encoding="utf-8"), plan.rules_new)
        self.assertTrue(self.receipt()["runs"][-1]["rules_created"])
        # Someone edits board_rules.md and the Rules section reappears on the board.
        rules.write_text("# hand-edited rules\nkeep me\n", encoding="utf-8")
        edited = (rules.read_bytes(), rules.stat().st_mtime_ns)
        (self.root / cc.BOARD).write_text(LEGACY_BOARD, encoding="utf-8")
        code, out = self.run_cli("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual((rules.read_bytes(), rules.stat().st_mtime_ns), edited)
        run = self.receipt()["runs"][-1]
        self.assertFalse(run["rules_created"])
        self.assertIn(cc.BOARD, run["replaced"])
        self.assertIn(("archive", "rules-copy"), [(m["dest"], m["reason"]) for m in run["moved"][cc.BOARD]])
        self.assertIn("## Rules (scawful, 2026-09-26: fans)", (self.archive / cc.BOARD).read_text(encoding="utf-8"))

    def test_board_rules_created_by_someone_else_after_planning_is_left_alone(self):
        plan, stamps = self.plan_from_disk()
        self.assertIsNotNone(plan.rules_new)
        original_write_temp = cc.write_temp
        theirs = "# board rules written by another agent mid-run\n"

        def write_temp_then_create_rules(path, data, mode=None):
            tmp = original_write_temp(path, data, mode)
            if path.name == cc.RULES:
                (self.root / cc.RULES).write_text(theirs, encoding="utf-8")
            return tmp

        cc.write_temp = write_temp_then_create_rules
        try:
            run = cc.apply_plan(plan, self.root, stamps)
        finally:
            cc.write_temp = original_write_temp
        self.assertEqual(run["status"], "partial")
        self.assertFalse(run["rules_created"])
        self.assertIn("created by someone else", run["skipped"][cc.RULES])
        self.assertEqual((self.root / cc.RULES).read_text(encoding="utf-8"), theirs)
        # Without board_rules.md the Rules section must stay on the board.
        self.assertIn(cc.RULES, run["skipped"][cc.BOARD])
        self.assertEqual((self.root / cc.BOARD).read_text(encoding="utf-8"), LEGACY_BOARD)
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_failure_after_first_archive_append_is_recorded_so_rerun_does_not_duplicate(self):
        plan, stamps = self.plan_from_disk()
        original_append = cc.append_verified

        def fail_on_second_file(path, chunk, blocks):
            if path.name == cc.HANDOFF:
                raise cc.Refused("simulated disk error")
            original_append(path, chunk, blocks)

        cc.append_verified = fail_on_second_file
        try:
            with self.assertRaises(cc.Refused):
                cc.apply_plan(plan, self.root, stamps)
        finally:
            cc.append_verified = original_append
        self.assertEqual(self.receipt()["runs"][-1]["archived"][cc.BOARD],
                         [m.block.sha for m in plan.files[cc.BOARD].archived])
        self.assertEqual((self.root / cc.BOARD).read_text(encoding="utf-8"), LEGACY_BOARD)
        board_archive = (self.archive / cc.BOARD).read_text(encoding="utf-8")
        self.assertEqual(self.run_cli("--apply")[0], 0)
        self.assertEqual((self.archive / cc.BOARD).read_text(encoding="utf-8"), board_archive)
        self.assertEqual(self.receipt()["runs"][-1]["status"], "applied")

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


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.archive = self.root / "archive" / "coordination" / "2026-10-17"
        self.texts = {
            cc.BOARD: LEGACY_BOARD + "\n" + owner_section("Cursor", "2026-10-17 19:40Z", result="canonical") + "\n",
            cc.HANDOFF: LEGACY_HANDOFF,
            cc.INBOX: LEGACY_INBOX + STRICT_ASK + "\n",
        }
        for name, text in self.texts.items():
            (self.root / name).write_text(text, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    run_cli = ApplyTests.run_cli

    def test_migrate_dry_run_writes_nothing(self):
        before = tree_state(self.root)
        code, out = self.run_cli("--migrate", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("migrate, dry run", out)
        self.assertEqual(tree_state(self.root), before)

    def test_migrate_archives_every_byte_and_seeds_the_new_format(self):
        code, out = self.run_cli("--migrate", "--apply")
        self.assertEqual(code, 0, out)
        for name, text in self.texts.items():
            self.assertIn(text, (self.archive / name).read_text(encoding="utf-8"))
        inbox = (self.root / cc.INBOX).read_text(encoding="utf-8").splitlines()
        self.assertEqual(inbox, [GOAL, cc.INBOX_FORMAT, STRICT_ASK])
        board = (self.root / cc.BOARD).read_text(encoding="utf-8")
        self.assertTrue(board.startswith(cc.BOARD_TITLE + "\n" + cc.LOCK_SEED + "\n" + GOAL + "\n"))
        self.assertIn("Result: canonical", board)  # canonical, fresh owner sections are carried forward
        self.assertIn("Result: newer", board)
        self.assertIn(cc.idle_stub("Claude"), board)  # stale canonical section is not
        self.assertNotIn("Combined Yaze", board)
        self.assertTrue((self.root / cc.RULES).exists())
        handoff = (self.root / cc.HANDOFF).read_text(encoding="utf-8").splitlines()
        self.assertEqual(handoff[0], cc.HANDOFF_TITLE)
        run = json.loads((self.archive / cc.RECEIPT).read_text(encoding="utf-8"))["runs"][-1]
        self.assertEqual((run["mode"], run["status"]), ("migrate", "applied"))
        self.assertEqual(run["archived"][cc.BOARD], [cc.sha256_text(self.texts[cc.BOARD])])

    def test_migrate_refuses_without_goal_on_line_1(self):
        lines = self.texts[cc.INBOX].splitlines()
        (self.root / cc.INBOX).write_text("\n".join(lines[1:] + [lines[0]]) + "\n", encoding="utf-8")
        before = tree_state(self.root)
        code, out = self.run_cli("--migrate", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)
        self.assertEqual(tree_state(self.root), before)

    def test_second_migrate_and_daily_run_make_no_change(self):
        self.assertEqual(self.run_cli("--migrate", "--apply")[0], 0)
        first = tree_state(self.root)
        code, out = self.run_cli("--migrate", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: no-change", out)
        self.assertIn("a migrate run is already recorded", out)
        self.assertEqual(self.run_cli("--apply")[0], 0)
        self.assertEqual(tree_state(self.root), first)


if __name__ == "__main__":
    unittest.main()
