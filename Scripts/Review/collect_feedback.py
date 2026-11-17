#!/usr/bin/env python3
"""Collect submitted Review Board feedback newer than a watermark.

Contract: scratchpad/handoffs/review_boards_v2_2026-11-17/SPEC.md (QUEUE238).
- Read-only on the review_boards directory.
- Reads both yaze.review_board_feedback.v1 and yaze.review_board_feedback.v2.
- Lists submitted history entries newer than --since (default: state file
  ~/.context/projects/oracle-of-secrets/scratchpad/operations/review_boards_seen.json),
  one line per board: id, decision, answers, comment (or JSON with --json).
- --mark-seen advances the state file atomically.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from publish_board import parse_iso_utc, resolve_default_dest, utc_now_iso

FEEDBACK_SCHEMAS = (
    "yaze.review_board_feedback.v1",
    "yaze.review_board_feedback.v2",
)

DEFAULT_STATE_FILE = Path(
    "~/.context/projects/oracle-of-secrets/scratchpad/operations/review_boards_seen.json"
).expanduser()


def load_seen_watermark(state_file: Path) -> datetime | None:
    if not state_file.is_file():
        return None
    data = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    stamp = data.get("last_seen_at")
    if isinstance(stamp, str) and stamp.strip():
        return parse_iso_utc(stamp)
    return None


def atomic_write_state(state_file: Path, payload: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{state_file.name}.tmp-", dir=str(state_file.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_file)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def collect_board_feedback(
    dest: Path, cutoff: datetime | None
) -> tuple[list[dict[str, Any]], datetime | None]:
    results: list[dict[str, Any]] = []
    newest_seen: datetime | None = cutoff
    if not dest.is_dir():
        return results, newest_seen

    for folder in sorted(dest.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        board_id = folder.name
        fb_file = folder / f"feedback-{board_id}.json"
        if not fb_file.is_file() or fb_file.is_symlink():
            continue
        try:
            data = json.loads(fb_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: skipping unreadable {fb_file}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        schema = data.get("schema", "")
        if schema and schema not in FEEDBACK_SCHEMAS:
            print(
                f"WARN: skipping unknown schema '{schema}' in {fb_file}",
                file=sys.stderr,
            )
            continue
        history = data.get("history")
        if not isinstance(history, list):
            continue

        new_entries: list[dict[str, Any]] = []
        latest_decision = ""
        latest_answers: dict[str, Any] = {}
        latest_comment = ""
        latest_at = ""

        for entry in history:
            if not isinstance(entry, dict):
                continue
            dec = entry.get("decision", "")
            if dec in ("looks_good", "needs_changes"):
                latest_decision = dec
            at_raw = entry.get("at", "")
            entry_dt: datetime | None = None
            if isinstance(at_raw, str) and at_raw.strip():
                try:
                    entry_dt = parse_iso_utc(at_raw)
                except ValueError:
                    entry_dt = None

            if cutoff is not None:
                if entry_dt is None or entry_dt <= cutoff:
                    continue

            if entry_dt is not None and (
                newest_seen is None or entry_dt > newest_seen
            ):
                newest_seen = entry_dt

            entry_answers = entry.get("answers")
            if isinstance(entry_answers, dict):
                latest_answers.update(entry_answers)
            entry_comment = entry.get("comment", "")
            if isinstance(entry_comment, str) and entry_comment:
                latest_comment = entry_comment
            if isinstance(at_raw, str) and at_raw:
                latest_at = at_raw
            new_entries.append(entry)

        if not new_entries:
            continue

        # Fall back to last new entry's decision if only comments were submitted.
        summary_decision = latest_decision or new_entries[-1].get("decision", "")
        if not latest_answers and isinstance(data.get("answers"), dict):
            latest_answers = dict(data["answers"])

        results.append(
            {
                "id": board_id,
                "status": data.get("status", summary_decision),
                "decision": summary_decision,
                "answers": latest_answers,
                "comment": latest_comment,
                "at": latest_at,
                "entries": new_entries,
            }
        )

    return results, newest_seen


def format_line(record: dict[str, Any]) -> str:
    answers_compact = json.dumps(
        record["answers"], separators=(",", ":"), sort_keys=True
    )
    comment_compact = json.dumps(record["comment"])
    return (
        f"{record['id']}\t"
        f"decision={record['decision']}\t"
        f"answers={answers_compact}\t"
        f"comment={comment_compact}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect submitted Review Board feedback newer than last seen."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Path to review_boards folder (default: live project.yaze app_data_folder/review_boards).",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="ISO-8601 UTC timestamp cutoff (overrides --state-file watermark for filtering).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help="Watermark JSON file read by default and updated when --mark-seen is passed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON array instead of one line per board.",
    )
    parser.add_argument(
        "--mark-seen",
        action="store_true",
        help="Advance --state-file watermark after reading.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        dest = (
            args.dest.expanduser().resolve()
            if args.dest is not None
            else resolve_default_dest()
        )
        state_file = args.state_file.expanduser().resolve()
        cutoff = (
            parse_iso_utc(args.since)
            if args.since is not None
            else load_seen_watermark(state_file)
        )
        records, newest_seen = collect_board_feedback(dest, cutoff)
        if args.mark_seen:
            watermark = (
                newest_seen.strftime("%Y-%m-%dT%H:%M:%SZ")
                if newest_seen is not None
                else utc_now_iso()
            )
            atomic_write_state(
                state_file,
                {
                    "last_seen_at": watermark,
                    "updated_at": utc_now_iso(),
                    "boards_count": len(records),
                },
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(records, indent=2, sort_keys=True))
    else:
        for record in records:
            print(format_line(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
