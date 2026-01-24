#!/usr/bin/env python3
"""Audit docs for UNKNOWN verification metadata.

Usage:
  python3 scripts/verification_audit.py
  python3 scripts/verification_audit.py --report Docs/Status/verification_audit_report.md
"""

from pathlib import Path
import argparse
import re


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(description="Audit docs for UNKNOWN verification metadata.")
    parser.add_argument("--report", help="Write report to a markdown file")
    args = parser.parse_args()

    patterns = [
        root / "Docs/Core",
        root / "Docs/Technical",
        root / "Docs/Planning",
    ]

    entries = []
    for folder in patterns:
        if not folder.exists():
            continue
        for path in folder.rglob("*.md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"\*\*Last Verified:\*\*\s*(.+)", text)
            last_verified = match.group(1).strip() if match else "MISSING"
            if "UNKNOWN" in last_verified or last_verified == "MISSING":
                entries.append((path.relative_to(root), last_verified))

    lines = ["# Verification Audit Report", "", "Generated: local", ""]
    lines.append("| Document | Last Verified | Status |")
    lines.append("| --- | --- | --- |")
    for rel, last_verified in sorted(entries):
        status = "Needs audit" if "UNKNOWN" in last_verified or last_verified == "MISSING" else "OK"
        lines.append(f"| `{rel}` | {last_verified} | {status} |")

    report = "\n".join(lines) + "\n"

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
