#!/usr/bin/env python3
"""Compact the AFS coordination files: agent_board.md, inbox.md, agent_handoff.md.

The default run is a dry run: it prints the plan and writes nothing. --apply
appends every removed block, verbatim and in original order, to
archive/coordination/<UTC date>/<file> first, reads the archive back, and only
then rewrites the live files through a temp file and os.replace. Nothing is
deleted. If a target file changed after it was read (sha256, size or mtime),
the run stops before touching it.

Format (design: AFS handoffs/reset_audit_2026-10-17/afs_format.md, section 3):
  inbox.md          line 1 "Current goal: ...", line 2 FORMAT, then one line per
                    open ask, claim or release:
                    YYYY-MM-DD HH:MMZ from -> to: ask (path)
                    Lines prefixed DONE, lines older than --inbox-max-age-days,
                    headings, status blocks and bullets move to the archive.
  agent_board.md    title, "Heavy lock:" line, "Current goal:" line, then one
                    section per owner: "## <Owner> — YYYY-MM-DD HH:MMZ" and
                    five lines Result/Ran/Next/Holds/Handoff (<=160 chars each).
                    Older or duplicate owner sections and all other sections
                    move to the archive; an owner with no fresh section gets
                    an idle stub.
  agent_handoff.md  start-here index: goal pointer, board, decisions, one
                    handoff path per owner (taken from the board).
  board_rules.md    the board's "## Rules" section, moved once, verbatim.

Usage:
  python3 Scripts/Agents/coord_compact.py                  # dry run on the AFS scratchpad
  python3 Scripts/Agents/coord_compact.py --root <copy>    # dry run on a copy
  python3 Scripts/Agents/coord_compact.py --apply          # archive, then rewrite
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

VERSION = "1"
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

BOARD_TITLE = (
    "# Agent board — each owner overwrites only its own section (5 lines, <=160 chars each). "
    "Load rules: board_rules.md. History: archive/coordination/"
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
TRAILING_PATH_RE = re.compile(r"\([^()]*\)\s*$")


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
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def nonblank(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip()]


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

    @property
    def changes(self) -> bool:
        return bool(self.rules_new) or any(fp.changed for fp in self.files.values())


def parse_now(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def message_time(match: re.Match) -> dt.datetime | None:
    try:
        day = dt.datetime.strptime(match.group("date"), "%Y-%m-%d")
        if match.group("hh") is not None:
            day = day.replace(hour=int(match.group("hh")), minute=int(match.group("mm")))
    except ValueError:
        return None
    return day.replace(tzinfo=dt.timezone.utc)


def owner_heading_re(owners: tuple[str, ...]) -> re.Pattern:
    names = "|".join(re.escape(o) for o in owners)
    return re.compile(
        rf"^## (?P<owner>{names})\s+[—–-]{{1,2}}\s+"
        rf"(?:(?P<stamp>\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}})Z|(?P<idle>idle))\s*$",
        re.IGNORECASE,
    )


def idle_stub(owner: str) -> str:
    return "\n".join([f"## {owner} — idle"] + [f"{label}: -" for label in OWNER_LABELS])


def plan_inbox(text: str, now: dt.datetime, max_age_days: float) -> tuple[FilePlan, Block | None]:
    blocks = split_inbox(text)
    moves: list[Move] = []
    goal: Block | None = None
    format_kept = False
    open_lines: list[str] = []
    max_age = dt.timedelta(days=max_age_days)
    for block in blocks:
        line = block.first
        single = len(block.lines) == 1
        if single and GOAL_RE.match(line):
            if goal is None:
                goal = block
                moves.append(Move(block, "keep", "goal"))
            else:
                moves.append(Move(block, "archive", "extra-goal"))
            continue
        if single and line == INBOX_FORMAT and not format_kept:
            format_kept = True
            moves.append(Move(block, "keep", "format"))
            continue
        match = MSG_RE.match(line) if single else None
        when = message_time(match) if match else None
        if match and when is not None:
            if match.group("done"):
                moves.append(Move(block, "archive", "done"))
            elif now - when > max_age:
                moves.append(Move(block, "archive", "expired"))
            else:
                moves.append(Move(block, "keep", "open"))
                open_lines.append(line)
            continue
        reason = "format-refresh" if single and line.startswith("FORMAT:") else "not-an-ask"
        moves.append(Move(block, "archive", reason))

    after = None
    flags: list[str] = []
    if goal is not None:
        after = "\n".join([goal.first, INBOX_FORMAT] + open_lines) + "\n"
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
    return FilePlan(INBOX, text, blocks, moves, after, flags), goal


def plan_board(text: str, now: dt.datetime, owners: tuple[str, ...], max_age_hours: float,
               goal_line: str | None, rules_exists: bool) -> tuple[FilePlan, dict[str, str], Block | None]:
    blocks = split_sections(text)
    heading_re = owner_heading_re(owners)
    canonical = {o.lower(): o for o in owners}
    max_age = dt.timedelta(hours=max_age_hours)
    decided: dict[int, Move] = {}
    header: Block | None = None
    lock_line: str | None = None
    rules_block: Block | None = None
    candidates: dict[str, list[tuple[Block, dt.datetime | None]]] = {o: [] for o in owners}

    for block in blocks:
        heading = block.first
        if header is None and heading.startswith(BOARD_TITLE_PREFIX):
            # The first title block holds the lock line, even if someone prepended above it.
            header = block
            lock_line = next((ln for ln in block.lines if ln.startswith("Heavy lock:")), None)
            continue
        match = heading_re.match(heading)
        if match:
            owner = canonical[match.group("owner").lower()]
            stamp = None
            if match.group("stamp"):
                try:
                    stamp = dt.datetime.strptime(match.group("stamp"), "%Y-%m-%d %H:%M").replace(
                        tzinfo=dt.timezone.utc)
                except ValueError:
                    decided[block.start] = Move(block, "archive", "history")
                    continue
            candidates[owner].append((block, stamp))
            continue
        if RULES_RE.match(heading):
            if not rules_exists and rules_block is None:
                rules_block = block
                decided[block.start] = Move(block, "rules", "rules")
            else:
                decided[block.start] = Move(block, "archive", "rules-copy")
            continue
        decided[block.start] = Move(block, "archive", "history")

    kept_sections: dict[str, str] = {}
    flags: list[str] = []
    for owner in owners:
        dated = [(b, t) for b, t in candidates[owner] if t is not None]
        idle = [b for b, t in candidates[owner] if t is None]
        fresh = [(b, t) for b, t in dated if now - t <= max_age]
        best: Block | None = None
        if fresh:
            best = max(fresh, key=lambda bt: (bt[1], -bt[0].start))[0]
        elif idle:
            best = idle[0]
        for block, stamp in dated:
            if block is best:
                decided[block.start] = Move(block, "keep", "owner")
            elif stamp is not None and now - stamp > max_age:
                decided[block.start] = Move(block, "archive", "stale-owner")
            else:
                decided[block.start] = Move(block, "archive", "superseded")
        for block in idle:
            if block is best:
                decided[block.start] = Move(block, "keep", "owner-idle")
            else:
                decided[block.start] = Move(block, "archive", "superseded")
        if best is None:
            kept_sections[owner] = idle_stub(owner)
        else:
            kept_sections[owner] = best.text
            flags.extend(owner_section_flags(owner, best))

    header_lines = [BOARD_TITLE, lock_line or LOCK_SEED]
    if goal_line:
        header_lines.append(goal_line)
    if header is not None:
        same = nonblank(header.lines) == header_lines
        decided[header.start] = Move(header, "keep" if same else "archive",
                                     "header" if same else "header-refresh")

    moves = [decided[b.start] for b in blocks]
    after = None
    if goal_line:
        parts = ["\n".join(header_lines)] + [kept_sections[o] for o in owners]
        after = "\n\n".join(parts) + "\n"
    return FilePlan(BOARD, text, blocks, moves, after, flags), kept_sections, rules_block


def owner_section_flags(owner: str, block: Block) -> list[str]:
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
    for line in section.split("\n"):
        if line.startswith("Handoff:"):
            value = line[len("Handoff:"):].strip()
            return value or "-"
    return "-"


def handoff_index_lines(owners: tuple[str, ...], kept_sections: dict[str, str]) -> list[str]:
    return [
        HANDOFF_TITLE,
        "Goal: inbox.md line 1 (scawful sets it).",
        "Board: agent_board.md (one 5-line section per owner). Load rules: board_rules.md.",
        "Decisions: Oracle repo Docs/Planning/Status/decisions.org (OPEN headings).",
        *[f"{owner}: {handoff_path_of(kept_sections[owner])}" for owner in owners],
        "Archive: archive/coordination/<YYYY-MM-DD>/ (moved verbatim by Scripts/Agents/coord_compact.py).",
    ]


def plan_handoff(text: str, index_lines: list[str] | None) -> FilePlan:
    blocks = split_sections(text)
    moves = []
    seen_index = False
    for block in blocks:
        is_index = not seen_index and block.first == HANDOFF_TITLE
        seen_index = seen_index or is_index
        if is_index and index_lines is not None and nonblank(block.lines) == index_lines:
            moves.append(Move(block, "keep", "index"))
        else:
            moves.append(Move(block, "archive", "index-refresh" if is_index else "history"))
    after = "\n".join(index_lines) + "\n" if index_lines is not None else None
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
               rules_exists: bool = False) -> Plan:
    texts = {name: texts.get(name) or "" for name in TARGETS}
    errors: list[str] = []
    notes: list[str] = []
    inbox_plan, goal = plan_inbox(texts[INBOX], now, inbox_max_age_days)
    goal_line = goal.first if goal else None
    if goal is None:
        errors.append("inbox.md has no 'Current goal:' line; scawful sets the goal. Nothing will be written.")
    board_plan, kept_sections, rules_block = plan_board(
        texts[BOARD], now, owners, board_max_age_hours, goal_line, rules_exists)
    index_lines = handoff_index_lines(owners, kept_sections) if goal else None
    handoff_plan = plan_handoff(texts[HANDOFF], index_lines)
    files = {BOARD: board_plan, HANDOFF: handoff_plan, INBOX: inbox_plan}
    for fp in files.values():
        errors.extend(check_partition(fp))
        cap = FILE_BYTES_CAP[fp.name]
        if fp.after is not None and len(fp.after.encode("utf-8")) > cap:
            fp.flags.append(f"after: {len(fp.after.encode('utf-8'))} B, over the {cap} B cap")
    rules_new = None
    if rules_block is not None:
        rules_new = RULES_TITLE + "\n\n" + rules_block.text + "\n"
    elif rules_exists:
        notes.append("board_rules.md exists; any '## Rules' section left on the board is archived.")
    return Plan(now, files, rules_new, errors, notes, goal_line,
                goal.start + 1 if goal else None, duplicate_paragraphs(texts))


# --------------------------------------------------------------------------- files

@dataclass(frozen=True)
class Stamp:
    exists: bool
    sha: str | None = None
    size: int | None = None
    mtime_ns: int | None = None


def stamp_of(path: Path) -> Stamp:
    if path.is_symlink():
        raise Refused(f"{path} is a symlink; refusing to replace it")
    if not path.exists():
        return Stamp(False)
    data = path.read_bytes()
    st = path.stat()
    return Stamp(True, hashlib.sha256(data).hexdigest(), st.st_size, st.st_mtime_ns)


def read_targets(root: Path) -> tuple[dict[str, str], dict[str, Stamp]]:
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
    if stamp_of(path) != stamp:
        raise Refused(f"{path.name} changed after it was read (sha256/size/mtime); "
                      "it was not rewritten. Re-run to plan against the new content.")


def ensure_inside(root: Path, path: Path) -> None:
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise Refused(f"{path} resolves outside {root}")


def archive_dir(root: Path, now: dt.datetime) -> Path:
    path = root
    for part in ARCHIVE_SUBDIR + (now.strftime("%Y-%m-%d"),):
        path = path / part
        if path.exists() or path.is_symlink():
            ensure_inside(root, path)
    return path


def fsync_dir(path: Path) -> None:
    with contextlib.suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    tmp = path.with_name(f".{path.name}.coord_compact.{os.getpid()}.tmp")
    try:
        with open(tmp, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    fsync_dir(path.parent)


def append_verified(path: Path, chunk: str, blocks: list[Block]) -> None:
    before = path.read_bytes() if path.exists() else b""
    if before and not before.endswith(b"\n"):
        chunk = "\n" + chunk
    data = chunk.encode("utf-8")
    with open(path, "ab") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    after = path.read_bytes()
    if after != before + data or any(b.text.encode("utf-8") not in after for b in blocks):
        raise Refused(f"archive read-back failed for {path}; live files were not touched")


def archive_chunk(name: str, fp: FilePlan, now: dt.datetime, blocks: list[Block]) -> str:
    header = (f"<!-- coord_compact v{VERSION} | {iso(now)} | from {name} sha256 "
              f"{sha256_text(fp.before)} | {len(blocks)} blocks in original order -->")
    return header + "\n\n" + "\n\n".join(b.text for b in blocks) + "\n\n"


@contextlib.contextmanager
def compaction_lock(root: Path, now: dt.datetime):
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
    with contextlib.suppress(FileNotFoundError):
        (path / "owner").unlink()
    with contextlib.suppress(FileNotFoundError):
        path.rmdir()


def apply_plan(plan: Plan, root: Path, stamps: dict[str, Stamp]) -> dict:
    """Archive first, then rewrite. Returns the receipt run record."""
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
        try:
            receipt = (json.loads(receipt_path.read_text(encoding="utf-8"))
                       if receipt_path.exists() else {"runs": []})
            if not isinstance(receipt.get("runs"), list):
                raise ValueError("no 'runs' list")
        except (ValueError, AttributeError) as exc:
            raise Refused(f"{receipt_path} is unreadable ({exc}); fix it by hand") from exc
        already = {(name, sha) for run in receipt["runs"]
                   for name, shas in run.get("archived", {}).items() for sha in shas}
        run = {
            "time": iso(plan.now), "version": VERSION, "status": "archiving",
            "files": {}, "archived": {}, "moved": {}, "rules_created": False,
        }
        receipt["runs"].append(run)
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
            new_blocks = [m.block for m in fp.archived if (name, m.block.sha) not in already]
            if new_blocks:
                append_verified(out_dir / name, archive_chunk(name, fp, plan.now, new_blocks), new_blocks)
                run["archived"][name] = [b.sha for b in new_blocks]
        atomic_write(receipt_path, (json.dumps(receipt, indent=1) + "\n").encode("utf-8"))

        if plan.rules_new:
            check_unchanged(root / RULES, stamps[RULES])
            atomic_write(root / RULES, plan.rules_new.encode("utf-8"), 0o644)
            run["rules_created"] = True
        for name in TARGETS:
            fp = plan.files[name]
            if not fp.changed:
                continue
            path = root / name
            check_unchanged(path, stamps[name])
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
            atomic_write(path, fp.after.encode("utf-8"), mode)
        run["status"] = "applied"
        atomic_write(receipt_path, (json.dumps(receipt, indent=1) + "\n").encode("utf-8"))
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
        "errors": plan.errors, "notes": plan.notes, "files": files,
        "board_rules_new_bytes": _size(plan.rules_new) if plan.rules_new else 0,
        "goal_line_number_before": plan.goal_line_number,
        "duplicate_paragraphs_before": {"paragraphs": plan.duplicate_paragraphs[0],
                                        "extra_copy_bytes": plan.duplicate_paragraphs[1]},
        "archive_dir": str(Path(*ARCHIVE_SUBDIR, plan.now.strftime("%Y-%m-%d"))),
        "applied": applied,
    }


def render_markdown(report: dict, list_moved: bool) -> str:
    out = []
    mode = "dry run — nothing written; add --apply to write" if report["mode"] == "dry-run" else "apply"
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
    if rules:
        out.append(f"| {RULES} (new) | 0 | 0 | {rules:,} | {_tok(rules):,} | 1 | - |")
        total_after += rules
    out.append(f"| Total | {total_before:,} | {_tok(total_before):,} | {total_after:,} | {_tok(total_after):,} | | |")
    start_before = report["files"][INBOX]["before_bytes"] + report["files"][HANDOFF]["before_bytes"]
    start_after = (report["files"][INBOX]["after_bytes"] or 0) + (report["files"][HANDOFF]["after_bytes"] or 0)
    out.append("")
    out.append(f"Session-start read (inbox + handoff): {start_before:,} B / {_tok(start_before):,} tok -> "
               f"{start_after:,} B / {_tok(start_after):,} tok.")
    goal_line = report["goal_line_number_before"]
    out.append(f"Inbox line 1 is the goal: before {'yes' if goal_line == 1 else f'no (goal at line {goal_line})'}; "
               f"after {'yes' if goal_line else 'no goal line'}.")
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
    expired = [m for m in report["files"][INBOX]["moved"] if m["reason"] == "expired"]
    if expired:
        out.append("")
        out.append("Expired inbox lines (re-post if still open):")
        out.extend(f"- line {m['line']}: {m['first_line']}" for m in expired)
    if report["notes"]:
        out.append("")
        out.extend(f"Note: {n}" for n in report["notes"])
    if list_moved:
        for name in TARGETS:
            out.append("")
            out.append(f"Moved from {name}:")
            out.extend(f"- L{m['line']} {m['dest']}:{m['reason']} {m['bytes']} B: {m['first_line']}"
                       for m in report["files"][name]["moved"])
    if report["applied"]:
        out.append("")
        out.append(f"Applied: {report['applied'].get('status')}"
                   + (f"; archive {report['applied']['archive_dir']}" if report["applied"].get("archive_dir") else ""))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT),
                        help="scratchpad directory holding the three files (default: AFS scratchpad)")
    parser.add_argument("--apply", action="store_true", help="archive and rewrite (default: dry run)")
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
                          rules_exists=stamps[RULES].exists)
        applied = apply_plan(plan, root, stamps) if args.apply and not plan.errors else None
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    report = report_dict(plan, root, applied)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        sys.stdout.write(render_markdown(report, args.list_moved))
    return 1 if plan.errors else 0


if __name__ == "__main__":
    sys.exit(main())
