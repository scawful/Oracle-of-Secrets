#!/usr/bin/env python3
"""Compact the AFS coordination files: agent_board.md, inbox.md, agent_handoff.md.

The default run is a dry run: it prints the plan and writes nothing. --apply
appends every removed block, verbatim and in original order, to
archive/coordination/<UTC date>/<file> first, reads the archive back, and only
then rewrites the live files. Nothing is deleted. Each live file is written to a
temp file, re-checked against the plan (sha256, size, mtime) right before
os.replace, and skipped if it changed since planning; the archive appends stay
recorded in receipt.json, so a re-run does not archive them twice. A write that
lands in the old file during the swap is saved next to the archive and reported
as REWRITTEN; CONCURRENT WRITE SAVED (merge it back by hand).

--migrate is the one-time switch to the new format (design section 6.3): every
current byte of the three files is archived verbatim, then the files are seeded
with the new format. Only line 1 of inbox.md (the goal), new-format inbox lines
(YYYY-MM-DD HH:MMZ ... (path)) and canonical owner sections are carried forward.

Format (design: AFS handoffs/reset_audit_2026-10-17/afs_format.md, section 3):
  inbox.md          line 1 "Current goal: ..." (scawful sets it; never moved),
                    line 2 FORMAT, then one line per open ask, claim or release:
                    YYYY-MM-DD HH:MMZ from -> to: ask (path)
                    Lines prefixed DONE, lines older than --inbox-max-age-days,
                    headings, status blocks and bullets move to the archive.
  agent_board.md    title (points to scratchpad/board_rules.md), "Heavy lock:"
                    line, "Current goal:" line, then one section per owner:
                    "## <Owner> — YYYY-MM-DD HH:MMZ" and five lines
                    Result/Ran/Next/Holds/Handoff (<=160 chars each).
                    "## <Owner> <anything> — <date>" counts as that owner's
                    section (flagged). "## <Owner>-<Suffix> — ..." (a side
                    session, e.g. Claude-Kydrog) is its own owner: kept while
                    fresh, listed in the handoff index, archived with no idle
                    stub once stale. A recent section that names no owner is
                    flagged and stays on the board until it ages out.
  agent_handoff.md  start-here index: goal pointer, board, decisions, one
                    handoff path per owner (taken from the board).
  board_rules.md    the board's "## Rules" section, moved once, verbatim.

Usage:
  python3 Scripts/Agents/coord_compact.py                     # dry run on the AFS scratchpad
  python3 Scripts/Agents/coord_compact.py --root <copy>       # dry run on a copy
  python3 Scripts/Agents/coord_compact.py --apply             # archive, then rewrite
  python3 Scripts/Agents/coord_compact.py --migrate           # one-time migration plan (dry run)
  python3 Scripts/Agents/coord_compact.py --migrate --apply   # archive everything, seed new format
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "2"
BOARD = "agent_board.md"
HANDOFF = "agent_handoff.md"
INBOX = "inbox.md"
RULES = "board_rules.md"
TARGETS = (BOARD, HANDOFF, INBOX)
RECEIPT = "receipt.json"
LOCK_DIR = ".coord_compact.lock"
LOCK_STALE_SECONDS = 600
ARCHIVE_SUBDIR = ("archive", "coordination")
DEFAULT_ROOT = Path.home() / ".context" / "projects" / "oracle-of-secrets" / "scratchpad"
DEFAULT_OWNERS = ("Codex", "Claude", "Cursor")
OWNER_LABELS = ("Result", "Ran", "Next", "Holds", "Handoff")

BOARD_LINE_MAX = 160
INBOX_LINE_MAX = 240
OWNER_BODY_LINES_MAX = 5
OWNER_SECTION_BYTES_MAX = 800
FILE_BYTES_CAP = {INBOX: 4096, BOARD: 6144, HANDOFF: 2048}
INBOX_LINES_CAP = 25
REPORT_LIST_MAX = 30

RULES_POINTER = "scratchpad/board_rules.md"
BOARD_TITLE = (
    "# Agent board — each owner overwrites only its own section (5 lines, <=160 chars each). "
    f"Load rules: {RULES_POINTER}. History: archive/coordination/"
)
BOARD_TITLE_PREFIX = "# Agent board —"
LOCK_SEED = "Heavy lock: unknown — truth is /tmp/oos-heavy.lock/owner (missing = free)"
INBOX_FORMAT = (
    "FORMAT: YYYY-MM-DD HH:MMZ from -> to: ask (path). One line, <=240 chars. "
    "Asks, claims and releases only; status goes on agent_board.md. "
    "Prefix DONE when answered; coord_compact.py archives it."
)
HANDOFF_TITLE = (
    "# Agent handoff — start-here index. Status lives on agent_board.md. "
    "History: archive/coordination/"
)
RULES_TITLE = (
    "# Board load rules — moved verbatim from agent_board.md by coord_compact.py. "
    "Read before taking a heavy resource."
)

HEADING_RE = re.compile(r"^#{1,3} ")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
GOAL_RE = re.compile(r"^(?:Current goal|GOAL):\s*\S")
RULES_RE = re.compile(r"^## Rules\b")
MSG_RE = re.compile(
    r"^(?P<done>DONE\b[:\s]*)?"
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:[ T](?P<hh>\d{2}):(?P<mm>\d{2})(?::\d{2})?(?:Z|\s?UTC)?)?"
    r"\s+(?P<sender>[A-Za-z][\w.-]*)\s*(?:->|→)\s*(?P<to>[^:]+?):\s*\S"
)
# The new inbox format, the only message lines --migrate carries forward.
STRICT_MSG_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z [A-Za-z][\w.-]* -> [^:]+: .*\S.*\([^()]+\)\s*$")
TRAILING_PATH_RE = re.compile(r"\([^()]*\)\s*$")

# Dates in legacy headings: "2026-10-17", "2026-10-17 21:02:40 UTC", "October 17, 20:30 UTC", "October16".
ISO_DATE_RE = re.compile(
    r"(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})"
    r"(?:[ T](?P<hh>\d{1,2}):(?P<mi>\d{2})(?::\d{2})?\s*(?P<tz>Z|UTC|EDT|EST)?)?")
MONTH_DATE_RE = re.compile(
    r"\b(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s*(?P<d>\d{1,2})\b(?:,?\s*(?P<y>\d{4}))?")
TIME_RE = re.compile(r"(?<![\d:])(?P<hh>\d{1,2}):(?P<mi>\d{2})(?::\d{2})?\s*(?P<tz>Z|UTC|EDT|EST)?\b")
TZ_HOURS = {None: 0, "Z": 0, "UTC": 0, "EDT": -4, "EST": -5}
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


class Refused(Exception):
    """The run stops without writing (or without writing anything further)."""


# --------------------------------------------------------------------------- blocks

@dataclass
class Block:
    start: int  # 0-based index of the block's first line in the source file
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def sha(self) -> str:
        return sha256_text(self.text)

    @property
    def first(self) -> str:
        return self.lines[0]


@dataclass
class Move:
    block: Block
    dest: str  # "keep", "archive" or "rules"
    reason: str


def sha256_text(text: str) -> str:
    """Hex sha256 of text encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_lines(text: str) -> list[str]:
    """Lines of text without newlines; a final newline adds no empty line."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def nonblank(lines: list[str]) -> list[str]:
    """lines without the blank and whitespace-only ones."""
    return [line for line in lines if line.strip()]


def normalized(lines: list[str]) -> list[str]:
    """Lines compared for 'is this already in the target form': blank lines and
    trailing whitespace do not count."""
    return [line.rstrip() for line in lines if line.strip()]


def _trimmed(start: int, chunk: list[str]) -> Block | None:
    a, b = 0, len(chunk)
    while a < b and not chunk[a].strip():
        a += 1
    while b > a and not chunk[b - 1].strip():
        b -= 1
    return Block(start + a, chunk[a:b]) if b > a else None


def split_sections(text: str) -> list[Block]:
    """Board/handoff: a block runs from a #/##/### heading to the line before the
    next heading. Text before the first heading is one block. Headings inside
    code fences do not split."""
    lines = split_lines(text)
    cuts = [0]
    fence = False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if i and not fence and HEADING_RE.match(line):
            cuts.append(i)
    cuts.append(len(lines))
    blocks = []
    for a, b in zip(cuts, cuts[1:]):
        block = _trimmed(a, lines[a:b])
        if block:
            blocks.append(block)
    return blocks


def _inbox_line_breaks_block(line: str) -> bool:
    return bool(MSG_RE.match(line) or GOAL_RE.match(line) or line.startswith("FORMAT:"))


def split_inbox(text: str) -> list[Block]:
    """Inbox: one non-blank line is one block, except that a heading and the
    paragraphs under it (a status block) form one block. A message, goal or
    FORMAT line always starts its own block."""
    lines = split_lines(text)
    blocks: list[Block] = []
    cur_start, cur = -1, []

    def flush() -> None:
        nonlocal cur_start, cur
        if cur:
            block = _trimmed(cur_start, cur)
            if block:
                blocks.append(block)
        cur_start, cur = -1, []

    for i, line in enumerate(lines):
        if HEADING_RE.match(line):
            flush()
            cur_start, cur = i, [line]
        elif _inbox_line_breaks_block(line):
            flush()
            blocks.append(Block(i, [line]))
        elif cur:
            cur.append(line)
        elif line.strip():
            blocks.append(Block(i, [line]))
    flush()
    return blocks


# --------------------------------------------------------------------------- plan

@dataclass
class FilePlan:
    name: str
    before: str
    blocks: list[Block]
    moves: list[Move]
    after: str | None
    flags: list[str] = field(default_factory=list)
    archive_whole: bool = False  # --migrate: archive the whole file verbatim, not just moved blocks

    @property
    def archived(self) -> list[Move]:
        return [m for m in self.moves if m.dest == "archive"]

    @property
    def changed(self) -> bool:
        return self.after is not None and self.after != self.before


@dataclass
class Plan:
    now: dt.datetime
    files: dict[str, FilePlan]
    rules_new: str | None
    errors: list[str]
    notes: list[str]
    goal_line: str | None
    goal_line_number: int | None
    duplicate_paragraphs: tuple[int, int]
    migrate: bool = False

    @property
    def changes(self) -> bool:
        return bool(self.rules_new) or any(fp.changed for fp in self.files.values())


def parse_now(value: str | None) -> dt.datetime:
    """--now as an aware UTC datetime, or the current UTC second when value is
    empty. A value with no zone is taken as UTC."""
    if not value:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    """moment in UTC as 'YYYY-MM-DDTHH:MM:SSZ'."""
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def message_time(match: re.Match) -> dt.datetime | None:
    """UTC time of an inbox line matched by MSG_RE (midnight when it has no
    time), or None for an impossible date."""
    try:
        day = dt.datetime.strptime(match.group("date"), "%Y-%m-%d")
        if match.group("hh") is not None:
            day = day.replace(hour=int(match.group("hh")), minute=int(match.group("mm")))
    except ValueError:
        return None
    return day.replace(tzinfo=dt.timezone.utc)


def heading_time(heading: str, now: dt.datetime) -> tuple[dt.datetime | None, bool]:
    """(UTC time, has_time) for the first date in a legacy heading, or (None, False).
    A month-name date without a year takes the year that does not put it in the future."""
    try:
        iso_match = ISO_DATE_RE.search(heading)
        if iso_match:
            day = dt.datetime(int(iso_match["y"]), int(iso_match["mo"]), int(iso_match["d"]),
                              tzinfo=dt.timezone.utc)
            if iso_match["hh"] is not None:
                return _at(day, iso_match["hh"], iso_match["mi"], iso_match["tz"]), True
            rest = heading[iso_match.end():]
        else:
            month_match = MONTH_DATE_RE.search(heading)
            if not month_match:
                return None, False
            month = MONTHS.index(month_match["mon"][:3].lower()) + 1
            year = int(month_match["y"]) if month_match["y"] else now.year
            day = dt.datetime(year, month, int(month_match["d"]), tzinfo=dt.timezone.utc)
            if not month_match["y"] and day > now + dt.timedelta(days=1):
                day = day.replace(year=year - 1)
            rest = heading[month_match.end():]
        time_match = TIME_RE.search(rest)
        if time_match:
            return _at(day, time_match["hh"], time_match["mi"], time_match["tz"]), True
        return day, False
    except ValueError:
        return None, False


def _at(day: dt.datetime, hh: str, mi: str, tz: str | None) -> dt.datetime:
    local = day.replace(hour=int(hh), minute=int(mi))
    return local - dt.timedelta(hours=TZ_HOURS.get(tz, 0))


def is_fresh(stamp: dt.datetime, has_time: bool, now: dt.datetime, max_age: dt.timedelta) -> bool:
    """True if stamp is no older than max_age at now."""
    end = stamp if has_time else stamp + dt.timedelta(days=1)  # a bare date counts until its day ends
    return now - end <= max_age


def owner_heading_re(owners: tuple[str, ...]) -> re.Pattern:
    """A canonical owner heading: '## <Owner> — YYYY-MM-DD HH:MMZ' (group stamp)
    or '## <Owner> — idle' (group idle)."""
    names = "|".join(re.escape(o) for o in owners)
    return re.compile(
        rf"^## (?P<owner>{names})\s+[—–-]{{1,2}}\s+"
        rf"(?:(?P<stamp>\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}})Z|(?P<idle>idle))\s*$",
        re.IGNORECASE,
    )


def owner_first_word_re(owners: tuple[str, ...]) -> re.Pattern:
    """A heading whose first word is an owner name. A hyphen continues the name, so
    '## Claude-Kydrog ...' is not Claude's heading."""
    names = "|".join(re.escape(o) for o in owners)
    return re.compile(rf"^#{{1,3}}\s+(?P<owner>{names})(?![\w-])", re.IGNORECASE)


def sub_owners(blocks: list[Block], owners: tuple[str, ...]) -> tuple[str, ...]:
    """'<Owner>-<Suffix>' names (side sessions, e.g. Claude-Kydrog) that head a board
    section, in board order, skipping names already in owners."""
    names = "|".join(re.escape(o) for o in owners)
    sub_re = re.compile(rf"^#{{1,3}}\s+(?P<owner>(?:{names})-[A-Za-z0-9][\w-]*)", re.IGNORECASE)
    seen = {o.lower() for o in owners}
    found: list[str] = []
    for block in blocks:
        match = sub_re.match(block.first)
        if match and match.group("owner").lower() not in seen:
            seen.add(match.group("owner").lower())
            found.append(match.group("owner"))
    return tuple(found)


def idle_stub(owner: str) -> str:
    """The placeholder section for an owner with no current section."""
    return "\n".join([f"## {owner} — idle"] + [f"{label}: -" for label in OWNER_LABELS])


@dataclass
class InboxResult:
    plan: FilePlan
    goal: Block | None
    stray_goal_lines: list[int]


def plan_inbox(text: str, now: dt.datetime, max_age_days: float, strict: bool = False) -> InboxResult:
    """The goal is pinned to line 1 (the first non-blank line). A goal-looking line
    anywhere else is archived and flagged; it never replaces line 1."""
    blocks = split_inbox(text)
    moves: list[Move] = []
    goal = blocks[0] if blocks and len(blocks[0].lines) == 1 and GOAL_RE.match(blocks[0].first) else None
    stray_goals: list[int] = []
    format_line: str | None = None
    open_lines: list[str] = []
    max_age = dt.timedelta(days=max_age_days)
    for block in blocks:
        line = block.first
        single = len(block.lines) == 1
        if block is goal:
            moves.append(Move(block, "keep", "goal"))
            continue
        if single and GOAL_RE.match(line):
            stray_goals.append(block.start + 1)
            moves.append(Move(block, "archive", "extra-goal"))
            continue
        if single and line.rstrip() == INBOX_FORMAT and format_line is None:
            format_line = line
            moves.append(Move(block, "keep", "format"))
            continue
        match = MSG_RE.match(line) if single else None
        when = message_time(match) if match else None
        if match and when is not None:
            if match.group("done"):
                moves.append(Move(block, "archive", "done"))
            elif now - when > max_age:
                moves.append(Move(block, "archive", "expired"))
            elif strict and not STRICT_MSG_RE.match(line):
                moves.append(Move(block, "archive", "old-format"))
            else:
                moves.append(Move(block, "keep", "open"))
                open_lines.append(line)
            continue
        reason = "format-refresh" if single and line.startswith("FORMAT:") else "not-an-ask"
        moves.append(Move(block, "archive", reason))

    after = None
    flags: list[str] = []
    if stray_goals and goal is not None:
        flags.append(f"goal-looking line(s) not on line 1 archived (extra-goal), line 1 stays the goal: "
                     f"source lines {_line_list(stray_goals)}")
    if goal is not None:
        after = "\n".join([goal.first, format_line or INBOX_FORMAT] + open_lines) + "\n"
        long_open = [m.block.start + 1 for m in moves
                     if m.reason == "open" and len(m.block.first) > INBOX_LINE_MAX]
        no_path = [m.block.start + 1 for m in moves
                   if m.reason == "open" and not TRAILING_PATH_RE.search(m.block.first)]
        if long_open:
            flags.append(f"{len(long_open)} open lines over {INBOX_LINE_MAX} chars "
                         f"(source lines {_line_list(long_open)})")
        if no_path:
            flags.append(f"{len(no_path)} open lines without a trailing (path) "
                         f"(source lines {_line_list(no_path)})")
        if len(goal.first) > INBOX_LINE_MAX:
            flags.append(f"goal line is {len(goal.first)} chars (inbox line cap {INBOX_LINE_MAX})")
        lines_after = len(split_lines(after))
        if lines_after > INBOX_LINES_CAP:
            flags.append(f"after: {lines_after} lines, over the {INBOX_LINES_CAP}-line cap")
    return InboxResult(FilePlan(INBOX, text, blocks, moves, after, flags), goal, stray_goals)


@dataclass
class Candidate:
    block: Block
    stamp: dt.datetime | None  # None: an idle stub
    has_time: bool
    canonical: bool  # "## <Owner> — YYYY-MM-DD HH:MMZ" or "## <Owner> — idle"


def plan_board(text: str, now: dt.datetime, owners: tuple[str, ...], max_age_hours: float,
               goal_line: str | None, rules_exists: bool,
               strict: bool = False) -> tuple[FilePlan, dict[str, str], Block | None]:
    """Decide where each board block goes. Returns the board plan, the kept section
    per owner (board order: owners, then sub-owners that are still current) and the
    Rules block to move to board_rules.md. A sub-owner ('<Owner>-<Suffix>') gets no
    idle stub: once it has no fresh section, its blocks are archived and its slot
    goes away. strict (--migrate): only canonical owner sections are carried forward."""
    blocks = split_sections(text)
    subs = sub_owners(blocks, owners)
    all_owners = owners + subs
    canon_re = owner_heading_re(all_owners)
    first_word_re = owner_first_word_re(all_owners)
    canonical_name = {o.lower(): o for o in all_owners}
    max_age = dt.timedelta(hours=max_age_hours)
    decided: dict[int, Move] = {}
    header: Block | None = None
    lock_line: str | None = None
    rules_block: Block | None = None
    candidates: dict[str, list[Candidate]] = {o: [] for o in all_owners}
    unattributed: list[Block] = []
    flags: list[str] = []

    for block in blocks:
        heading = block.first
        if header is None and heading.startswith(BOARD_TITLE_PREFIX):
            # The first title block holds the lock line, even if someone prepended above it.
            header = block
            lock_line = next((ln for ln in block.lines if ln.startswith("Heavy lock:")), None)
            continue
        if RULES_RE.match(heading):
            if not rules_exists and rules_block is None:
                rules_block = block
                decided[block.start] = Move(block, "rules", "rules")
            else:
                decided[block.start] = Move(block, "archive", "rules-copy")
            continue
        match = canon_re.match(heading)
        if match:
            owner = canonical_name[match.group("owner").lower()]
            if match.group("idle"):
                candidates[owner].append(Candidate(block, None, False, True))
                continue
            try:
                stamp = dt.datetime.strptime(match.group("stamp"), "%Y-%m-%d %H:%M").replace(
                    tzinfo=dt.timezone.utc)
            except ValueError:
                decided[block.start] = Move(block, "archive", "history")
                continue
            candidates[owner].append(Candidate(block, stamp, True, True))
            continue
        stamp, has_time = heading_time(heading, now) if HEADING_RE.match(heading) else (None, False)
        first_word = first_word_re.match(heading)
        if first_word and stamp is not None:
            owner = canonical_name[first_word.group("owner").lower()]
            candidates[owner].append(Candidate(block, stamp, has_time, False))
            continue
        if stamp is not None and is_fresh(stamp, has_time, now, max_age):
            if strict:
                decided[block.start] = Move(block, "archive", "unattributed")
            else:
                unattributed.append(block)
                decided[block.start] = Move(block, "keep", "unattributed")
            continue
        decided[block.start] = Move(block, "archive", "history")

    kept_sections: dict[str, str] = {}
    not_carried: list[int] = []
    for owner in all_owners:
        is_sub = owner in subs
        cands = candidates[owner]
        dated = [c for c in cands if c.stamp is not None and (c.canonical or not strict)]
        fresh = [c for c in dated if is_fresh(c.stamp, c.has_time, now, max_age)]
        idle = [c for c in cands if c.stamp is None]
        best: Candidate | None = None
        if fresh:
            best = max(fresh, key=lambda c: (c.stamp, c.has_time, c.canonical, -c.block.start))
        elif idle and not is_sub:
            best = idle[0]
        for cand in cands:
            block = cand.block
            if cand is best:
                decided[block.start] = Move(block, "keep", "owner" if cand.stamp else "owner-idle")
            elif strict and not cand.canonical:
                decided[block.start] = Move(block, "archive", "not-canonical")
                if is_fresh(cand.stamp, cand.has_time, now, max_age):
                    not_carried.append(block.start + 1)
            elif cand.stamp is not None and not is_fresh(cand.stamp, cand.has_time, now, max_age):
                decided[block.start] = Move(block, "archive", "stale-owner")
            elif cand.stamp is None and is_sub and best is None:
                decided[block.start] = Move(block, "archive", "sub-owner-idle")
            else:
                decided[block.start] = Move(block, "archive", "superseded")
        if best is None and is_sub:
            continue
        if best is None:
            kept_sections[owner] = idle_stub(owner)
        else:
            kept_sections[owner] = best.block.text
            if not best.canonical:
                flags.append(f"{owner} section (source line {best.block.start + 1}) has a legacy heading; kept "
                             f"as {owner}'s section by its first word. Rewrite as "
                             f"'## {owner} — YYYY-MM-DD HH:MMZ': {best.block.first[:90]}")
            flags.extend(owner_section_flags(owner, best.block))

    for block in unattributed:
        flags.append(f"unattributed recent section kept on the board (source line {block.start + 1}); "
                     f"its owner rewrites it as '## <Owner> — YYYY-MM-DD HH:MMZ': {block.first[:90]}")
    undated = [b.start + 1 for b in blocks if decided.get(b.start) and decided[b.start].reason == "history"
               and HEADING_RE.match(b.first) and heading_time(b.first, now)[0] is None]
    if undated:
        flags.append(f"{len(undated)} sections with no owner and no date archived (cannot tell if current): "
                     f"source lines {_line_list(undated)}")
    unattributed_archived = [m.block.start + 1 for m in decided.values() if m.reason == "unattributed"]
    if strict and (not_carried or unattributed_archived):
        lines = sorted(not_carried + unattributed_archived)
        flags.append(f"{len(lines)} recent non-canonical sections archived, not carried forward "
                     f"(owners re-post as canonical sections): source lines {_line_list(lines)}")

    header_lines = [BOARD_TITLE, lock_line or LOCK_SEED]
    if goal_line:
        header_lines.append(goal_line)
    header_text = "\n".join(header_lines)
    if header is not None:
        if normalized(header.lines) == normalized(header_lines):
            header_text = header.text  # already in form: keep it byte for byte
            decided[header.start] = Move(header, "keep", "header")
        else:
            decided[header.start] = Move(header, "archive", "header-refresh")

    moves = [decided[b.start] for b in blocks]
    after = None
    if goal_line:
        parts = [header_text] + list(kept_sections.values()) + [b.text for b in unattributed]
        after = "\n\n".join(parts) + "\n"
    return FilePlan(BOARD, text, blocks, moves, after, flags), kept_sections, rules_block


def owner_section_flags(owner: str, block: Block) -> list[str]:
    """Report-only flags for a kept owner section: over the body-line, byte or
    line-length cap, or missing one of the five labels."""
    flags = []
    body = nonblank(block.lines[1:])
    size = len(block.text.encode("utf-8"))
    where = f"{owner} section (source line {block.start + 1})"
    if len(body) > OWNER_BODY_LINES_MAX:
        flags.append(f"{where}: {len(body)} body lines, over {OWNER_BODY_LINES_MAX}")
    if size > OWNER_SECTION_BYTES_MAX:
        flags.append(f"{where}: {size} B, over {OWNER_SECTION_BYTES_MAX} B")
    long_lines = [ln for ln in block.lines if len(ln) > BOARD_LINE_MAX]
    if long_lines:
        flags.append(f"{where}: {len(long_lines)} lines over {BOARD_LINE_MAX} chars")
    missing = [label for label in OWNER_LABELS
               if not any(ln.startswith(f"{label}:") for ln in body)]
    if missing:
        flags.append(f"{where}: missing {', '.join(m + ':' for m in missing)}")
    return flags


def handoff_path_of(section: str) -> str:
    """The value of a section's 'Handoff:' line, or '-' when it is missing or empty."""
    for line in section.split("\n"):
        if line.startswith("Handoff:"):
            value = line[len("Handoff:"):].strip()
            return value or "-"
    return "-"


def handoff_index_lines(owners: tuple[str, ...], kept_sections: dict[str, str]) -> list[str]:
    """The agent_handoff.md start-here index: fixed pointers, then one
    '<Owner>: <handoff path>' line per owner in owners order."""
    return [
        HANDOFF_TITLE,
        "Goal: inbox.md line 1 (scawful sets it).",
        f"Board: agent_board.md (one 5-line section per owner). Load rules: {RULES_POINTER}.",
        "Decisions: Oracle repo Docs/Planning/Status/decisions.org (OPEN headings).",
        *[f"{owner}: {handoff_path_of(kept_sections[owner])}" for owner in owners],
        "Archive: archive/coordination/<YYYY-MM-DD>/ (moved verbatim by Scripts/Agents/coord_compact.py).",
    ]


def plan_handoff(text: str, index_lines: list[str] | None) -> FilePlan:
    """agent_handoff.md becomes the index. A first index block that already
    matches index_lines is kept byte for byte; every other block is archived.
    index_lines None (no goal): nothing is rewritten."""
    blocks = split_sections(text)
    moves = []
    seen_index = False
    kept: Block | None = None
    for block in blocks:
        is_index = not seen_index and block.first.rstrip() == HANDOFF_TITLE
        seen_index = seen_index or is_index
        if is_index and index_lines is not None and normalized(block.lines) == normalized(index_lines):
            kept = block
            moves.append(Move(block, "keep", "index"))
        else:
            moves.append(Move(block, "archive", "index-refresh" if is_index else "history"))
    after = None
    if index_lines is not None:
        after = (kept.text if kept else "\n".join(index_lines)) + "\n"
    return FilePlan(HANDOFF, text, blocks, moves, after)


def duplicate_paragraphs(texts: dict[str, str]) -> tuple[int, int]:
    """Paragraphs that appear in more than one file, and the bytes of the extra copies."""
    seen: dict[str, set[str]] = {}
    for name, text in texts.items():
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if para:
                seen.setdefault(para, set()).add(name)
    shared = {p: n for p, n in seen.items() if len(n) > 1}
    extra = sum((len(n) - 1) * len(p.encode("utf-8")) for p, n in shared.items())
    return len(shared), extra


def check_partition(fp: FilePlan) -> list[str]:
    """Never-delete check: the blocks rebuild the original (ignoring whitespace-only
    lines), every block has exactly one destination, and kept blocks are in the
    new text verbatim."""
    errors = []
    if nonblank(split_lines(fp.before)) != [ln for b in fp.blocks for ln in b.lines if ln.strip()]:
        errors.append(f"{fp.name}: blocks do not rebuild the original")
    starts = [m.block.start for m in fp.moves]
    if sorted(starts) != sorted(b.start for b in fp.blocks) or len(set(starts)) != len(starts):
        errors.append(f"{fp.name}: a block has no destination or more than one")
    if fp.after is not None:
        for move in fp.moves:
            if move.dest == "keep" and move.block.text not in fp.after:
                errors.append(f"{fp.name}: kept block at line {move.block.start + 1} is not in the output")
    return errors


def build_plan(texts: dict[str, str], now: dt.datetime, *, owners: tuple[str, ...] = DEFAULT_OWNERS,
               inbox_max_age_days: float = 7, board_max_age_hours: float = 72,
               rules_exists: bool = False, migrate: bool = False) -> Plan:
    """Plan all three files from their texts (a missing file counts as empty).
    Writes nothing. Refusals go in Plan.errors: no goal on inbox line 1, or a
    failed partition check."""
    texts = {name: texts.get(name) or "" for name in TARGETS}
    errors: list[str] = []
    notes: list[str] = []
    inbox = plan_inbox(texts[INBOX], now, inbox_max_age_days, strict=migrate)
    goal = inbox.goal
    goal_line = goal.first if goal else None
    if goal is None:
        hint = (f" A goal-looking line is at line {inbox.stray_goal_lines[0]}; scawful moves it to line 1."
                if inbox.stray_goal_lines else "")
        errors.append("inbox.md line 1 is not a 'Current goal:' line; scawful sets the goal. "
                      f"Nothing will be written.{hint}")
    board_plan, kept_sections, rules_block = plan_board(
        texts[BOARD], now, owners, board_max_age_hours, goal_line, rules_exists, strict=migrate)
    kept_subs = [o for o in kept_sections if o not in owners]
    if kept_subs:
        notes.append(f"sub-owner sections kept as their own owner (no idle stub; archived when stale): "
                     f"{', '.join(kept_subs)}")
    index_lines = handoff_index_lines(tuple(kept_sections), kept_sections) if goal else None
    handoff_plan = plan_handoff(texts[HANDOFF], index_lines)
    files = {BOARD: board_plan, HANDOFF: handoff_plan, INBOX: inbox.plan}
    for fp in files.values():
        fp.archive_whole = migrate
        errors.extend(check_partition(fp))
        cap = FILE_BYTES_CAP[fp.name]
        if fp.after is not None and len(fp.after.encode("utf-8")) > cap:
            fp.flags.append(f"after: {len(fp.after.encode('utf-8'))} B, over the {cap} B cap")
    rules_new = None
    if rules_block is not None:
        rules_new = RULES_TITLE + "\n\n" + rules_block.text + "\n"
    elif rules_exists:
        notes.append(f"{RULES} exists; any '## Rules' section left on the board is archived.")
    if migrate:
        notes.append("migrate: each changed file is archived whole and verbatim; only the goal line, "
                     "new-format inbox lines and canonical owner sections are carried forward.")
    return Plan(now, files, rules_new, errors, notes, goal_line,
                goal.start + 1 if goal else None, duplicate_paragraphs(texts), migrate)


# --------------------------------------------------------------------------- files

@dataclass(frozen=True)
class Stamp:
    exists: bool
    sha: str | None = None
    size: int | None = None
    mtime_ns: int | None = None


def stamp_of(path: Path) -> Stamp:
    """path's Stamp: missing, or its sha256, size and mtime. Refuses a symlink."""
    if path.is_symlink():
        raise Refused(f"{path} is a symlink; refusing to replace it")
    if not path.exists():
        return Stamp(False)
    data = path.read_bytes()
    st = path.stat()
    return Stamp(True, hashlib.sha256(data).hexdigest(), st.st_size, st.st_mtime_ns)


def read_targets(root: Path) -> tuple[dict[str, str], dict[str, Stamp]]:
    """Read the three live files and stamp them and board_rules.md. Refuses a
    file that changed between stamp and read, or that is not UTF-8."""
    texts: dict[str, str] = {}
    stamps: dict[str, Stamp] = {}
    for name in TARGETS + (RULES,):
        path = root / name
        stamp = stamp_of(path)
        if name in TARGETS and stamp.exists:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != stamp.sha:
                raise Refused(f"{name} changed while it was being read; re-run")
            try:
                texts[name] = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise Refused(f"{name} is not UTF-8: {exc}") from exc
        stamps[name] = stamp
    return texts, stamps


def check_unchanged(path: Path, stamp: Stamp) -> None:
    """Refuse if path no longer matches the stamp taken when it was read."""
    if stamp_of(path) != stamp:
        raise Refused(f"{path.name} changed after it was read (sha256/size/mtime); "
                      "nothing was written. Re-run to plan against the new content.")


def ensure_inside(root: Path, path: Path) -> None:
    """Refuse if path resolves outside root (for example, through a symlink)."""
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise Refused(f"{path} resolves outside {root}")


def archive_dir(root: Path, now: dt.datetime) -> Path:
    """root/archive/coordination/<UTC date of now>. Each part that exists must
    resolve inside root. Creates nothing."""
    path = root
    for part in ARCHIVE_SUBDIR + (now.strftime("%Y-%m-%d"),):
        path = path / part
        if path.exists() or path.is_symlink():
            ensure_inside(root, path)
    return path


def fsync_dir(path: Path) -> None:
    """Best-effort fsync of a directory, so a rename or link in it is durable."""
    with contextlib.suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_temp(path: Path, data: bytes, mode: int | None = None) -> Path:
    """Write data to a new hidden temp file beside path (exclusive create),
    fsync it, apply mode if given, and return the temp file's path."""
    tmp = path.with_name(f".{path.name}.coord_compact.{os.getpid()}.tmp")
    with open(tmp, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if mode is not None:
        os.chmod(tmp, mode)
    return tmp


def _replace(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    """For files only this script writes (receipt.json)."""
    tmp = write_temp(path, data, mode)
    try:
        _replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    fsync_dir(path.parent)


def replace_if_unchanged(path: Path, data: bytes, stamp: Stamp, mode: int, rescue_dir: Path,
                         now: dt.datetime) -> tuple[bool, str | None]:
    """Compare-and-swap one live file. The temp file is written first; the target is
    re-checked against the plan (sha256, size, mtime) immediately before os.replace,
    through a handle that must still be the file at the path (same inode). A file
    that did not exist at planning is created only if still absent (os.link), never
    overwritten. Returns (written, note):
      (True, None)   rewritten;
      (False, why)   left alone;
      (True, note)   rewritten, but a write that landed in the displaced file during
                     the swap was saved to rescue_dir; note names that file."""
    tmp = write_temp(path, data, mode)
    try:
        if not stamp.exists:
            try:
                os.link(tmp, path)  # create only if still absent
            except FileExistsError:
                return False, "created by someone else after planning; left alone"
            return True, None
        try:
            held = open(path, "rb")
        except FileNotFoundError:
            return False, "removed after planning; left alone"
        with held:
            try:
                current = stamp_of(path)
                same_inode = os.fstat(held.fileno()).st_ino == os.stat(path).st_ino
            except (FileNotFoundError, Refused):
                return False, "changed after planning; left alone"
            if current != stamp or not same_inode:
                return False, "changed after planning (sha256/size/mtime); left alone, re-run"
            _replace(tmp, path)
            st = os.fstat(held.fileno())
            if (st.st_size, st.st_mtime_ns) != (stamp.size, stamp.mtime_ns):
                held.seek(0)
                rescue = rescue_dir / f"{path.name}.displaced-{now.strftime('%H%M%SZ')}-{os.getpid()}"
                with open(rescue, "xb") as out:
                    out.write(held.read())
                    out.flush()
                    os.fsync(out.fileno())
                return True, (f"the version written during the swap was saved to {rescue}; "
                              "merge it back by hand")
        return True, None
    finally:
        if tmp.exists():
            tmp.unlink()
        fsync_dir(path.parent)


def append_verified(path: Path, chunk: str, blocks: list[str]) -> None:
    """Append chunk to the archive file at path, then read it back. Refuses
    unless the file is the old bytes plus chunk and holds every text in blocks."""
    before = path.read_bytes() if path.exists() else b""
    if before and not before.endswith(b"\n"):
        chunk = "\n" + chunk
    data = chunk.encode("utf-8")
    with open(path, "ab") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    after = path.read_bytes()
    if after != before + data or any(text.encode("utf-8") not in after for text in blocks):
        raise Refused(f"archive read-back failed for {path}; live files were not touched")


def archive_chunk(name: str, fp: FilePlan, now: dt.datetime, texts: list[str], what: str) -> str:
    """One archive append: a header comment (version, time, source sha256,
    what) followed by the texts, blank-line separated."""
    header = (f"<!-- coord_compact v{VERSION} | {iso(now)} | from {name} sha256 "
              f"{sha256_text(fp.before)} | {what} -->")
    body = "\n\n".join(texts)
    if not body.endswith("\n"):
        body += "\n"
    return header + "\n\n" + body + "\n"


@contextlib.contextmanager
def compaction_lock(root: Path, now: dt.datetime):
    """Hold the root/.coord_compact.lock directory for one apply. A lock older
    than LOCK_STALE_SECONDS is taken over; a newer one refuses."""
    path = root / LOCK_DIR
    try:
        os.mkdir(path)
    except FileExistsError:
        age = time.time() - path.stat().st_mtime
        if age < LOCK_STALE_SECONDS:
            raise Refused(f"{path} is held ({age:.0f} s old); another compaction is running") from None
        release_lock(path)
        os.mkdir(path)
    (path / "owner").write_text(f"coord_compact pid {os.getpid()} {iso(now)}\n", encoding="utf-8")
    try:
        yield
    finally:
        release_lock(path)


def release_lock(path: Path) -> None:
    """Remove the lock directory and its owner file; already gone is fine."""
    with contextlib.suppress(FileNotFoundError):
        (path / "owner").unlink()
    with contextlib.suppress(FileNotFoundError):
        path.rmdir()


def load_receipt(path: Path) -> dict:
    """receipt.json as {'runs': [...]}, or a new one when it is missing.
    Refuses an unreadable receipt."""
    try:
        receipt = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}
        if not isinstance(receipt.get("runs"), list):
            raise ValueError("no 'runs' list")
    except (ValueError, AttributeError) as exc:
        raise Refused(f"{path} is unreadable ({exc}); fix it by hand") from exc
    return receipt


def earlier_migrations(root: Path) -> list[str]:
    """'<date dir> <time>' for each applied, partial or rescued --migrate run
    recorded in any receipt under root/archive/coordination/."""
    base = root.joinpath(*ARCHIVE_SUBDIR)
    found = []
    for receipt_path in sorted(base.glob("*/" + RECEIPT)) if base.is_dir() else []:
        with contextlib.suppress(ValueError, OSError, AttributeError):
            for run in json.loads(receipt_path.read_text(encoding="utf-8")).get("runs", []):
                if run.get("mode") == "migrate" and run.get("status") in ("applied", "partial", "rescued"):
                    found.append(f"{receipt_path.parent.name} {run.get('time')}")
    return found


def apply_plan(plan: Plan, root: Path, stamps: dict[str, Stamp]) -> dict:
    """Archive first, then rewrite. The receipt is saved after every step, so a
    failure part-way never makes a re-run archive the same block twice. Returns
    the receipt run record; status "partial" when a live file was left alone,
    "rescued" when every file was rewritten but a write that landed during a swap
    was saved aside (run["rescued"]) for a hand merge."""
    if plan.errors:
        raise Refused("; ".join(plan.errors))
    if not plan.changes:
        return {"status": "no-change"}
    with compaction_lock(root, plan.now):
        for name in TARGETS + (RULES,):
            check_unchanged(root / name, stamps[name])
        out_dir = archive_dir(root, plan.now)
        out_dir.mkdir(parents=True, exist_ok=True)
        ensure_inside(root, out_dir)
        receipt_path = out_dir / RECEIPT
        receipt = load_receipt(receipt_path)
        already = {(name, sha) for run in receipt["runs"]
                   for name, shas in run.get("archived", {}).items() for sha in shas}
        run = {
            "time": iso(plan.now), "version": VERSION, "mode": "migrate" if plan.migrate else "compact",
            "status": "archiving", "files": {}, "archived": {}, "moved": {}, "rules_created": False,
            "replaced": [], "skipped": {}, "rescued": {},
        }
        receipt["runs"].append(run)

        def save() -> None:
            atomic_write(receipt_path, (json.dumps(receipt, indent=1) + "\n").encode("utf-8"))

        for name in TARGETS:
            fp = plan.files[name]
            run["files"][name] = {
                "before_sha256": sha256_text(fp.before), "before_bytes": len(fp.before.encode("utf-8")),
                "after_sha256": sha256_text(fp.after), "after_bytes": len(fp.after.encode("utf-8")),
            }
            run["moved"][name] = [
                {"sha256": m.block.sha, "reason": m.reason, "dest": m.dest, "line": m.block.start + 1,
                 "bytes": len(m.block.text.encode("utf-8"))}
                for m in fp.moves if m.dest != "keep"
            ]
        save()

        for name in TARGETS:
            fp = plan.files[name]
            if fp.archive_whole:
                pieces = [(sha256_text(fp.before), fp.before)] if fp.changed and fp.before.strip() else []
                what = "whole file, verbatim (migrate)"
            else:
                pieces = [(m.block.sha, m.block.text) for m in fp.archived]
                what = f"{len(pieces)} blocks in original order"
            new = [(sha, text) for sha, text in pieces if (name, sha) not in already]
            if not new:
                continue
            if not fp.archive_whole:
                what = f"{len(new)} blocks in original order"
            texts = [text for _, text in new]
            append_verified(out_dir / name, archive_chunk(name, fp, plan.now, texts, what), texts)
            run["archived"][name] = [sha for sha, _ in new]
            save()

        rules_failed = False
        if plan.rules_new:
            written, note = replace_if_unchanged(root / RULES, plan.rules_new.encode("utf-8"), stamps[RULES],
                                                 0o644, out_dir, plan.now)
            if written:
                run["rules_created"] = True
            else:
                rules_failed = True
                run["skipped"][RULES] = note
            save()
        for name in TARGETS:
            fp = plan.files[name]
            if not fp.changed:
                continue
            if name == BOARD and rules_failed:
                run["skipped"][name] = f"{RULES} was not created, so the Rules section stays on the board"
                save()
                continue
            path = root / name
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
            written, note = replace_if_unchanged(path, fp.after.encode("utf-8"), stamps[name], mode, out_dir,
                                                 plan.now)
            if not written:
                run["skipped"][name] = note
            else:
                run["replaced"].append(name)
                if note:
                    run["rescued"][name] = note
            save()
        run["status"] = "partial" if run["skipped"] else "rescued" if run["rescued"] else "applied"
        save()
        run["archive_dir"] = str(out_dir)
        return run


# --------------------------------------------------------------------------- report

def _line_list(numbers: list[int], limit: int = 12) -> str:
    shown = ", ".join(str(n) for n in numbers[:limit])
    return shown + (f", … +{len(numbers) - limit} more" if len(numbers) > limit else "")


def _size(text: str | None) -> int:
    return len(text.encode("utf-8")) if text is not None else 0


def _tok(size: int) -> int:
    return round(size / 4)


def report_dict(plan: Plan, root: Path, applied: dict | None = None) -> dict:
    """The report as JSON-ready data: per-file sizes, kept and moved counts,
    moves by reason, flags, and the apply run record when there is one."""
    files = {}
    for name in TARGETS:
        fp = plan.files[name]
        reasons: dict[str, dict[str, int]] = {}
        for move in fp.moves:
            if move.dest == "keep":
                continue
            entry = reasons.setdefault(f"{move.dest}:{move.reason}", {"blocks": 0, "bytes": 0})
            entry["blocks"] += 1
            entry["bytes"] += _size(move.block.text)
        files[name] = {
            "before_bytes": _size(fp.before), "after_bytes": _size(fp.after) if fp.after is not None else None,
            "before_sha256": sha256_text(fp.before),
            "blocks_kept": sum(1 for m in fp.moves if m.dest == "keep"),
            "blocks_moved": sum(1 for m in fp.moves if m.dest != "keep"),
            "moved_by_reason": reasons, "flags": fp.flags,
            "moved": [{"line": m.block.start + 1, "reason": m.reason, "dest": m.dest,
                       "bytes": _size(m.block.text), "first_line": m.block.first[:90]}
                      for m in fp.moves if m.dest != "keep"],
        }
    return {
        "version": VERSION, "now": iso(plan.now), "root": str(root),
        "mode": "apply" if applied is not None else "dry-run",
        "migrate": plan.migrate,
        "errors": plan.errors, "notes": plan.notes, "files": files,
        "board_rules_new_bytes": _size(plan.rules_new) if plan.rules_new else 0,
        "goal_line_number_before": plan.goal_line_number,
        "duplicate_paragraphs_before": {"paragraphs": plan.duplicate_paragraphs[0],
                                        "extra_copy_bytes": plan.duplicate_paragraphs[1]},
        "archive_dir": str(Path(*ARCHIVE_SUBDIR, plan.now.strftime("%Y-%m-%d"))),
        "applied": applied,
    }


INBOX_NOT_ASK_REASONS = ("not-an-ask", "extra-goal", "format-refresh", "old-format")


def render_markdown(report: dict, list_moved: bool) -> str:
    """The report as markdown: size table, moves by reason, flags, archived
    inbox lines to re-post, notes, and the apply outcome."""
    out = []
    mode = "dry run — nothing written; add --apply to write" if report["mode"] == "dry-run" else "apply"
    if report.get("migrate"):
        mode = "migrate, " + mode
    out.append(f"# coord_compact v{report['version']} — {report['now']} ({mode})")
    out.append(f"Root: {report['root']}")
    if report["errors"]:
        out.append("")
        out.extend(f"REFUSED: {e}" for e in report["errors"])
    out.append("")
    out.append("| File | Before B | Before tok | After B | After tok | Kept | Moved |")
    out.append("|---|---|---|---|---|---|---|")
    total_before = total_after = 0
    for name in TARGETS:
        f = report["files"][name]
        after = f["after_bytes"]
        total_before += f["before_bytes"]
        total_after += after or 0
        after_cell = f"{after:,}" if after is not None else "-"
        after_tok = f"{_tok(after):,}" if after is not None else "-"
        out.append(f"| {name} | {f['before_bytes']:,} | {_tok(f['before_bytes']):,} | {after_cell} | "
                   f"{after_tok} | {f['blocks_kept']} | {f['blocks_moved']} |")
    rules = report["board_rules_new_bytes"]
    if rules and not report["errors"]:
        out.append(f"| {RULES} (new) | 0 | 0 | {rules:,} | {_tok(rules):,} | 1 | - |")
        total_after += rules
    out.append(f"| Total | {total_before:,} | {_tok(total_before):,} | {total_after:,} | {_tok(total_after):,} | | |")
    start_before = report["files"][INBOX]["before_bytes"] + report["files"][HANDOFF]["before_bytes"]
    start_after = (report["files"][INBOX]["after_bytes"] or 0) + (report["files"][HANDOFF]["after_bytes"] or 0)
    out.append("")
    out.append(f"Session-start read (inbox + handoff): {start_before:,} B / {_tok(start_before):,} tok -> "
               f"{start_after:,} B / {_tok(start_after):,} tok.")
    goal_line = report["goal_line_number_before"]
    out.append("Inbox line 1 is the goal: " + (f"yes (line {goal_line})" if goal_line else "no — refused") + ".")
    dup = report["duplicate_paragraphs_before"]
    out.append(f"Paragraphs in more than one file (before): {dup['paragraphs']} "
               f"({dup['extra_copy_bytes']:,} B of extra copies).")
    out.append(f"Archive: {report['archive_dir']}/{{{','.join(TARGETS)}}} + {RECEIPT} (append-only).")
    out.append("")
    out.append("Moved by reason:")
    for name in TARGETS:
        reasons = report["files"][name]["moved_by_reason"]
        parts = [f"{key} {v['blocks']} ({v['bytes']:,} B)" for key, v in sorted(reasons.items())]
        out.append(f"- {name}: {'; '.join(parts) if parts else 'nothing'}")
    flags = [(name, flag) for name in TARGETS for flag in report["files"][name]["flags"]]
    out.append("")
    out.append("Flags (reported, not edited):" if flags else "Flags: none")
    out.extend(f"- {name}: {flag}" for name, flag in flags)
    inbox_moved = report["files"][INBOX]["moved"]
    for title, picked in (
        ("Expired inbox lines (re-post if still open):",
         [m for m in inbox_moved if m["reason"] == "expired"]),
        ("Archived inbox lines that are not open asks in the format (re-post as one line if still needed):",
         [m for m in inbox_moved if m["reason"] in INBOX_NOT_ASK_REASONS]),
    ):
        if picked:
            out.append("")
            out.append(title)
            out.extend(f"- line {m['line']} ({m['reason']}, {m['bytes']:,} B): {m['first_line']}"
                       for m in picked[:REPORT_LIST_MAX])
            if len(picked) > REPORT_LIST_MAX:
                out.append(f"- … +{len(picked) - REPORT_LIST_MAX} more (--list-moved or --json lists all)")
    if report["notes"]:
        out.append("")
        out.extend(f"Note: {n}" for n in report["notes"])
    if list_moved:
        for name in TARGETS:
            out.append("")
            out.append(f"Moved from {name}:")
            out.extend(f"- L{m['line']} {m['dest']}:{m['reason']} {m['bytes']} B: {m['first_line']}"
                       for m in report["files"][name]["moved"])
    applied = report["applied"]
    if applied:
        out.append("")
        out.append(f"Applied: {applied.get('status')}"
                   + (f"; archive {applied['archive_dir']}" if applied.get("archive_dir") else ""))
        for name, why in (applied.get("skipped") or {}).items():
            out.append(f"NOT REWRITTEN: {name}: {why}")
        for name, note in (applied.get("rescued") or {}).items():
            out.append(f"REWRITTEN; CONCURRENT WRITE SAVED: {name}: {note}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit 1 on a refusal, or when an apply leaves a file
    alone or saves a concurrent write aside; 0 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT),
                        help="scratchpad directory holding the three files (default: AFS scratchpad)")
    write = parser.add_mutually_exclusive_group()
    write.add_argument("--apply", action="store_true", help="archive and rewrite")
    write.add_argument("--dry-run", action="store_true", help="print the plan only (the default)")
    parser.add_argument("--migrate", action="store_true",
                        help="one-time migration: archive all current content verbatim, seed the new format")
    parser.add_argument("--now", help="UTC time to plan against, e.g. 2026-10-17T20:00:00Z (tests)")
    parser.add_argument("--inbox-max-age-days", type=float, default=7)
    parser.add_argument("--board-max-age-hours", type=float, default=72)
    parser.add_argument("--owners", default=",".join(DEFAULT_OWNERS),
                        help="comma-separated board owners, in board order")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--list-moved", action="store_true", help="list every moved block")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).expanduser()
        if not root.is_dir():
            raise Refused(f"{root} is not a directory")
        root = root.resolve()
        owners = tuple(o.strip() for o in args.owners.split(",") if o.strip())
        if not owners:
            raise Refused("--owners is empty")
        texts, stamps = read_targets(root)
        plan = build_plan(texts, parse_now(args.now), owners=owners,
                          inbox_max_age_days=args.inbox_max_age_days,
                          board_max_age_hours=args.board_max_age_hours,
                          rules_exists=stamps[RULES].exists, migrate=args.migrate)
        if args.migrate:
            plan.notes.extend(f"a migrate run is already recorded ({m}); the daily run is plain --apply"
                              for m in earlier_migrations(root))
        applied = apply_plan(plan, root, stamps) if args.apply and not plan.errors else None
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    report = report_dict(plan, root, applied)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        sys.stdout.write(render_markdown(report, args.list_moved))
    return 1 if plan.errors or (applied and applied.get("status") in ("partial", "rescued")) else 0


if __name__ == "__main__":
    sys.exit(main())
