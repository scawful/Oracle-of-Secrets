#!/usr/bin/env python3
"""Generate annotations.json from ASM comment tags.

Supported tags (in comments):
- @watch [fmt=hex|dec|bin]
- @assert <freeform> (stored as raw string)
- @abi <token> (captured for reference)
- @no_return (captured for reference)
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ASM_DEFINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\$[0-9A-Fa-f]{4,6})")
ASM_LABEL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*:")
STRUCT_START = re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)\s+(\$[0-9A-Fa-f]+)")
STRUCT_FIELD = re.compile(r"^\s*\.([A-Za-z_][A-Za-z0-9_]*)\s*:\s*skip\s+([^;\s]+)")
STRUCT_END = re.compile(r"^\s*endstruct\b")

TAG_WATCH = re.compile(r"@watch\b", re.IGNORECASE)
TAG_ASSERT = re.compile(r"@assert\b", re.IGNORECASE)
TAG_ABI = re.compile(r"@abi\s+([^\s;]+)", re.IGNORECASE)
TAG_NO_RETURN = re.compile(r"@no_return\b", re.IGNORECASE)
TAG_FMT = re.compile(r"fmt=([a-z]+)", re.IGNORECASE)

SKIP_DIRS = {"Roms", "SaveStates", "build", ".git", ".context"}


def _extract_comment(line: str) -> str:
    if ";" not in line:
        return ""
    return line.split(";", 1)[1].strip()


def _parse_addr(token: str) -> int | None:
    token = token.strip()
    if token.startswith("$"):
        token = token[1:]
    try:
        return int(token, 16)
    except ValueError:
        return None


def _parse_size(token: str) -> int | None:
    token = token.strip()
    if token.startswith("$"):
        token = token[1:]
        base = 16
    else:
        base = 10
    try:
        return int(token, base)
    except ValueError:
        return None


def collect_annotations(root: Path) -> list[dict]:
    annotations: list[dict] = []
    for path in root.rglob("*.asm"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root)
        struct_name: str | None = None
        struct_base: int | None = None
        struct_offset = 0
        for idx, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            struct_field_name = ""
            struct_field_addr: int | None = None

            start_match = STRUCT_START.match(line)
            if start_match:
                struct_name = start_match.group(1)
                struct_base = _parse_addr(start_match.group(2))
                struct_offset = 0
                continue

            if STRUCT_END.match(line):
                struct_name = None
                struct_base = None
                struct_offset = 0
                continue

            field_match = STRUCT_FIELD.match(line)
            if field_match and struct_name and struct_base is not None:
                field_name = field_match.group(1)
                size = _parse_size(field_match.group(2))
                if size is not None:
                    struct_field_name = f"{struct_name}.{field_name}"
                    struct_field_addr = struct_base + struct_offset
                    struct_offset += size

            comment = _extract_comment(line)
            if not comment:
                continue

            if TAG_WATCH.search(comment):
                fmt = ""
                fmt_match = TAG_FMT.search(comment)
                if fmt_match:
                    fmt = fmt_match.group(1).lower()

                addr = None
                label = ""
                if struct_field_name:
                    label = struct_field_name
                    addr = struct_field_addr
                else:
                    define = ASM_DEFINE.match(line)
                    if define:
                        label = define.group(1)
                        addr = _parse_addr(define.group(2))
                    else:
                        label_match = ASM_LABEL.match(line)
                        if label_match:
                            label = label_match.group(1)

                annotations.append({
                    "type": "watch",
                    "label": label,
                    "address": f"0x{addr:06X}" if addr is not None else None,
                    "format": fmt,
                    "source": f"{rel}:{idx}",
                    "note": comment,
                })

            if TAG_ASSERT.search(comment):
                expr = TAG_ASSERT.split(comment, 1)[1].strip()
                annotations.append({
                    "type": "assert",
                    "expr": expr,
                    "source": f"{rel}:{idx}",
                })

            if TAG_ABI.search(comment) or TAG_NO_RETURN.search(comment):
                annotations.append({
                    "type": "abi",
                    "note": comment,
                    "source": f"{rel}:{idx}",
                })

    return annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate annotations.json from ASM tags")
    parser.add_argument("--root", type=Path, required=True, help="Root directory to scan")
    parser.add_argument("--out", type=Path, required=True, help="Output annotations.json path")
    args = parser.parse_args()

    annotations = collect_annotations(args.root)
    payload = {
        "version": 1,
        "annotations": annotations,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(annotations)} annotations to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
