#!/usr/bin/env python3
"""Validate and normalize Oracle dialogue bundle IDs for z3ed imports.

This tool enforces the yaze-message-bundle contract:
- `id` is bank-local index (not absolute Oracle message ID)
- `bank` is one of: vanilla, expanded

Default mode is read-only validation.
Use `--write` to apply fixes in place.
"""

from __future__ import annotations

import argparse
import glob
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_BANKS = {"vanilla", "expanded"}


@dataclass
class FileReport:
    path: Path
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def _parse_int(text: str) -> int:
    return int(text, 0)


def _validate_messages_payload(data: dict[str, Any], report: FileReport) -> list[dict[str, Any]] | None:
    messages = data.get("messages")
    if not isinstance(messages, list):
        report.errors.append("missing or invalid 'messages' array")
        return None
    for idx, entry in enumerate(messages):
        if not isinstance(entry, dict):
            report.errors.append(f"messages[{idx}] is not an object")
    if report.errors:
        return None
    return messages


def _check_sequence(
    report: FileReport, ids: list[int], bank: str, *, require_contiguous: bool
) -> None:
    if not ids:
        return
    seen: set[int] = set()
    dupes: list[int] = []
    for value in ids:
        if value in seen:
            dupes.append(value)
        seen.add(value)
    if dupes:
        pretty = ", ".join(str(v) for v in sorted(set(dupes)))
        report.errors.append(f"{bank}: duplicate IDs: {pretty}")
    if not require_contiguous:
        return

    sorted_ids = sorted(set(ids))
    if len(sorted_ids) <= 1:
        return
    expected = list(range(sorted_ids[0], sorted_ids[-1] + 1))
    if sorted_ids != expected:
        gaps = [value for value in expected if value not in set(sorted_ids)]
        preview = ", ".join(str(v) for v in gaps[:8])
        suffix = "" if len(gaps) <= 8 else f" ... (+{len(gaps) - 8} more)"
        report.warnings.append(f"{bank}: non-contiguous IDs; gaps at {preview}{suffix}")


def process_file(
    path: Path,
    *,
    expanded_base: int,
    vanilla_max: int,
    vanilla_promote_floor: int,
    promote_low_expanded_to_vanilla: bool,
    write: bool,
) -> FileReport:
    report = FileReport(path=path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        report.errors.append(f"failed to parse JSON: {exc}")
        return report

    if not isinstance(data, dict):
        report.errors.append("top-level JSON must be an object")
        return report

    messages = _validate_messages_payload(data, report)
    if messages is None:
        return report

    effective_ids: dict[str, list[int]] = {"vanilla": [], "expanded": []}

    for idx, entry in enumerate(messages):
        raw_id = entry.get("id")
        if not isinstance(raw_id, int):
            report.errors.append(f"messages[{idx}].id missing/invalid")
            continue

        bank = entry.get("bank", "vanilla")
        if not isinstance(bank, str):
            report.errors.append(f"messages[{idx}].bank must be string")
            continue
        bank = bank.strip().lower()
        if bank not in VALID_BANKS:
            report.errors.append(f"messages[{idx}].bank invalid: {bank!r}")
            continue

        new_bank = bank
        new_id = raw_id

        converted_from_absolute = False
        if bank == "expanded" and raw_id >= expanded_base:
            new_id = raw_id - expanded_base
            converted_from_absolute = True
            report.changes.append(
                f"messages[{idx}] expanded id {raw_id} -> {new_id} (base 0x{expanded_base:X})"
            )
        elif (
            bank == "expanded"
            and promote_low_expanded_to_vanilla
            and not converted_from_absolute
            and vanilla_promote_floor <= raw_id <= vanilla_max
        ):
            if promote_low_expanded_to_vanilla:
                new_bank = "vanilla"
                report.changes.append(
                    f"messages[{idx}] bank expanded -> vanilla (id {raw_id} in vanilla range)"
                )
        elif (
            bank == "expanded"
            and not converted_from_absolute
            and vanilla_promote_floor <= raw_id <= vanilla_max
        ):
            report.warnings.append(
                f"messages[{idx}] expanded id {raw_id} is in likely vanilla range "
                f"{vanilla_promote_floor}..{vanilla_max}; possible bank mismatch "
                "(use --promote-low-expanded-to-vanilla)"
            )

        if new_bank == "vanilla" and not (0 <= new_id <= vanilla_max):
            report.warnings.append(
                f"messages[{idx}] vanilla id {new_id} outside expected range 0..{vanilla_max}"
            )
        if new_bank == "expanded" and new_id < 0:
            report.errors.append(f"messages[{idx}] expanded id {new_id} must be >= 0")

        effective_ids[new_bank].append(new_id)

        if write:
            entry["id"] = new_id
            entry["bank"] = new_bank

    _check_sequence(report, effective_ids["vanilla"], "vanilla", require_contiguous=False)
    _check_sequence(report, effective_ids["expanded"], "expanded", require_contiguous=True)

    if write and not report.errors:
        target_counts = {
            "vanilla": len(effective_ids["vanilla"]),
            "expanded": len(effective_ids["expanded"]),
        }
        current_counts = data.get("counts")
        if not isinstance(current_counts, dict):
            data["counts"] = target_counts
            report.changes.append("set counts from messages")
        else:
            if current_counts.get("vanilla") != target_counts["vanilla"] or current_counts.get(
                "expanded"
            ) != target_counts["expanded"]:
                data["counts"] = target_counts
                report.changes.append(
                    f"updated counts to vanilla={target_counts['vanilla']}, "
                    f"expanded={target_counts['expanded']}"
                )

        path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--glob",
        default="Data/dialogue/*.json",
        help="Bundle glob pattern (default: %(default)s)",
    )
    parser.add_argument(
        "--expanded-base",
        default="0x18D",
        type=_parse_int,
        help="Absolute expanded base ID used by Oracle (default: %(default)s)",
    )
    parser.add_argument(
        "--vanilla-max",
        default=396,
        type=int,
        help="Max valid vanilla message ID (default: %(default)s)",
    )
    parser.add_argument(
        "--vanilla-promote-floor",
        default=256,
        type=int,
        help=(
            "Lower bound for treating expanded IDs as likely-mislabeled vanilla "
            "when --promote-low-expanded-to-vanilla is used (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--promote-low-expanded-to-vanilla",
        action="store_true",
        help="If expanded id <= vanilla-max, relabel bank to vanilla",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes in place (default is validate-only)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings are present",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in sorted(glob.glob(args.glob))]
    if not paths:
        print(f"[error] no files matched glob: {args.glob}")
        return 2

    total_changes = 0
    total_warnings = 0
    total_errors = 0

    for path in paths:
        report = process_file(
            path,
            expanded_base=args.expanded_base,
            vanilla_max=args.vanilla_max,
            vanilla_promote_floor=args.vanilla_promote_floor,
            promote_low_expanded_to_vanilla=args.promote_low_expanded_to_vanilla,
            write=args.write,
        )
        total_changes += len(report.changes)
        total_warnings += len(report.warnings)
        total_errors += len(report.errors)

        status = "OK"
        if report.errors:
            status = "ERROR"
        elif report.warnings:
            status = "WARN"
        elif report.changed:
            status = "CHANGED"

        print(f"[{status}] {path}")
        for line in report.changes:
            print(f"  change: {line}")
        for line in report.warnings:
            print(f"  warn:   {line}")
        for line in report.errors:
            print(f"  error:  {line}")

    print(
        f"\nsummary: files={len(paths)} changes={total_changes} "
        f"warnings={total_warnings} errors={total_errors}"
    )

    if total_errors:
        return 1
    if args.strict and total_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
