#!/usr/bin/env python3
"""Lint documentation for stale/banned references.

Goal: keep "current guidance" docs runnable and free of legacy/broken references.

Scope (current docs):
- Repo root docs: README.md, RUNBOOK.md, AGENTS.md, CLAUDE.md
- Docs/**/*.md excluding Docs/Archive/** and Docs/Debugging/Issues/archive/**
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


CURRENT_DOC_GLOBS: list[str] = [
    "README.md",
    "RUNBOOK.md",
    "AGENTS.md",
    "CLAUDE.md",
    "Docs/**/*.md",
]

EXCLUDE_SUBSTRINGS: tuple[str, ...] = (
    "Docs/Archive/",
    "Docs/Debugging/Issues/archive/",
)


# If any of these appear in current docs, they are considered a failure.
BANNED_SNIPPETS: tuple[str, ...] = (
    # Removed/obsolete stacks
    "mesen_cli.sh",
    "state_library.py",
    "mesen_launch.sh",
    "agent_workflow_start.sh",
    "agent_workflow_stop.sh",
    "mesen_socket_server.py",
    "mesen_live_bridge.lua",
    # External AI helper scripts (not part of supported Oracle debugging path)
    "yaze/scripts/ai/",
    "scripts/ai/",
    # Old/abandoned doc roots from previous reorganizations
    "Docs/Dev/",
    "Docs/Game/",
    "Docs/Ref/",
    "Docs/Tooling/",
    "Docs/Core/",
    "Docs/General/",
    "Docs/Issues/",
    "Docs/Status/",
)


# Detect references to scripts in this repo. Capture only the path portion, not args.
#
# Important: avoid matching `../other-repo/scripts/...` by requiring the reference
# to be either at start-of-line or preceded by whitespace / punctuation commonly
# used in docs.
SCRIPT_REF_RE = re.compile(
    r"(?:^|[\s`(\"'])"
    r"(?:\./)?"
    r"(scripts/[A-Za-z0-9_./-]+\.(?:py|sh))"
    r"\b"
)


@dataclass(frozen=True)
class Finding:
    path: Path
    lineno: int
    message: str


def iter_current_docs() -> list[Path]:
    docs: list[Path] = []
    for glob in CURRENT_DOC_GLOBS:
        for p in REPO_ROOT.glob(glob):
            p_rel = p.as_posix()
            if any(excl in p_rel for excl in EXCLUDE_SUBSTRINGS):
                continue
            if p.is_file():
                docs.append(p)
    # De-dupe + stable ordering
    return sorted(set(docs), key=lambda x: x.as_posix())


def main() -> int:
    findings: list[Finding] = []
    docs = iter_current_docs()

    for doc in docs:
        try:
            text = doc.read_text(errors="replace")
        except Exception as exc:
            findings.append(Finding(doc, 1, f"Could not read file: {exc}"))
            continue

        lines = text.splitlines()

        # Banned substrings
        for i, line in enumerate(lines, start=1):
            for banned in BANNED_SNIPPETS:
                if banned in line:
                    findings.append(Finding(doc, i, f"Banned reference: {banned}"))

        # Missing script references
        for i, line in enumerate(lines, start=1):
            for m in SCRIPT_REF_RE.finditer(line):
                rel = m.group(1)
                target = REPO_ROOT / rel
                if not target.exists():
                    findings.append(Finding(doc, i, f"Missing script reference: {rel}"))

    if not findings:
        print("docs-lint: OK")
        return 0

    print(f"docs-lint: FAIL ({len(findings)} finding(s))")
    for f in findings:
        rel = f.path.relative_to(REPO_ROOT)
        print(f"  {rel}:{f.lineno}: {f.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
