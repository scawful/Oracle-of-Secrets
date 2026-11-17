#!/usr/bin/env python3
"""Check free space in the sprite code banks after assembly.

Sprites/all_sprites.asm prints "BankNN Free Space: N bytes" for banks $30-$32.
This reads those lines from the assembler log, prints one summary line, and
exits 1 when any bank is below the fail floor or a bank line is missing.
A bank below the warn floor still passes, with WARN in the summary.
"""
import argparse
import re
import sys

BANKS = ("30", "31", "32")
WARN_BELOW = 512
FAIL_BELOW = 64
LINE = re.compile(r"^Bank([0-9A-Fa-f]{2}) Free Space: (-?\d+) bytes\s*$")


def parse(text):
    """Return {bank: bytes}. The last line per bank wins (reassembly reruns)."""
    free = {}
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if m:
            free[m.group(1).upper()] = int(m.group(2))
    return free


def evaluate(free, warn_below=WARN_BELOW, fail_below=FAIL_BELOW):
    """Return (exit_code, summary)."""
    parts, failed, warned = [], False, False
    for bank in BANKS:
        if bank not in free:
            parts.append(f"${bank} MISSING")
            failed = True
            continue
        n = free[bank]
        tag = ""
        if n < fail_below:
            tag, failed = " FAIL", True
        elif n < warn_below:
            tag, warned = " WARN", True
        parts.append(f"${bank} {n} B{tag}")
    verdict = "FAIL" if failed else ("WARN" if warned else "OK")
    summary = (f"bank headroom {verdict}: " + ", ".join(parts)
               + f" (warn <{warn_below} B, fail <{fail_below} B)")
    return (1 if failed else 0), summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True, help="assembler stdout/stderr log")
    ap.add_argument("--warn-below", type=int, default=WARN_BELOW)
    ap.add_argument("--fail-below", type=int, default=FAIL_BELOW)
    a = ap.parse_args(argv)
    try:
        text = open(a.log, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"bank headroom FAIL: cannot read {a.log}: {exc}")
        return 1
    code, summary = evaluate(parse(text), a.warn_below, a.fail_below)
    print(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
