#!/usr/bin/env python3
"""
Symbol helpers for Oracle of Secrets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    if s.startswith("$"):
        s = "0x" + s[1:]
    if s.lower().startswith("0x"):
        try:
            return int(s, 16)
        except ValueError:
            return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_sym(path: Path) -> dict[int, list[tuple[int, str]]]:
    data: dict[int, list[tuple[int, str]]] = {}
    if not path.exists():
        return data
    in_labels = False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[labels]"):
            in_labels = True
            continue
        if line.startswith("[") and in_labels:
            break
        if not in_labels or ":" not in line:
            continue
        try:
            left, right = line.split(":", 1)
            bank = int(left.strip(), 16)
            addr_str, label = right.split(" ", 1)
            addr = int(addr_str.strip(), 16)
            label = label.strip().lstrip(":")
        except Exception:
            continue
        data.setdefault(bank, []).append((addr, label))
    for bank in data:
        data[bank].sort()
    return data


def resolve_symbol(sym: dict[int, list[tuple[int, str]]], bank: int | None, pc: int | None) -> str | None:
    if bank is None or pc is None:
        return None
    entries = sym.get(bank)
    if not entries:
        return f"{bank:02X}:{pc:04X}"
    lo = 0
    hi = len(entries) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        addr, label = entries[mid]
        if addr == pc:
            best = (addr, label)
            break
        if addr < pc:
            best = (addr, label)
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return f"{bank:02X}:{pc:04X}"
    addr, label = best
    delta = pc - addr
    if delta == 0:
        return f"{label}"
    return f"{label}+0x{delta:X}"


@dataclass
class SymbolResolver:
    sym_path: Path
    symbols: dict[int, list[tuple[int, str]]]

    def __init__(self, sym_path: Path):
        self.sym_path = sym_path
        self.symbols = parse_sym(sym_path)

    def resolve(self, bank: int | None, pc: int | None) -> str | None:
        return resolve_symbol(self.symbols, bank, pc)

    def resolve_pc24(self, pc24: int | None) -> str | None:
        if pc24 is None:
            return None
        bank = (pc24 >> 16) & 0xFF
        pc = pc24 & 0xFFFF
        return self.resolve(bank, pc)


def find_label_sources(label: str, root: Path, limit: int = 5) -> list[str]:
    pattern = rf"^{label}:"
    try:
        result = subprocess.run(
            ["rg", "-n", "-m", str(limit), pattern, str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip()
        if output:
            return output.splitlines()
    except FileNotFoundError:
        pass
    return []


def parse_cpu(raw: str) -> dict[str, int | None]:
    cpu = {}
    if raw.startswith("CPU:"):
        raw = raw[len("CPU:") :]
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        cpu[key.strip()] = parse_int(val.strip())
    return cpu


def cmd_lookup(args: argparse.Namespace) -> int:
    sym_path = Path(args.sym)
    resolver = SymbolResolver(sym_path)
    bank = parse_int(args.bank)
    pc = parse_int(args.pc)
    if args.cpu:
        cpu = parse_cpu(args.cpu)
        bank = cpu.get("pb") if bank is None else bank
        pc = cpu.get("pc") if pc is None else pc
    if args.pc24:
        pc24 = parse_int(args.pc24)
        if pc24 is not None:
            bank = (pc24 >> 16) & 0xFF
            pc = pc24 & 0xFFFF
    label = resolver.resolve(bank, pc)
    if args.json:
        print(json.dumps({"bank": bank, "pc": pc, "label": label}))
    else:
        if bank is not None and pc is not None:
            print(f"{bank:02X}:{pc:04X} {label or ''}".rstrip())
        else:
            print(label or "unknown")
    if args.source and label:
        sources = find_label_sources(label.split("+", 1)[0], REPO_ROOT, limit=args.limit)
        if sources:
            print("\n".join(sources))
    return 0


def cmd_source(args: argparse.Namespace) -> int:
    sources = find_label_sources(args.label, REPO_ROOT, limit=args.limit)
    if sources:
        print("\n".join(sources))
        return 0
    print("No sources found.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Symbol lookup utilities")
    parser.add_argument("--sym", default=str(REPO_ROOT / "Roms" / "oos168x.sym"))
    sub = parser.add_subparsers(dest="cmd")

    lookup = sub.add_parser("lookup", help="Resolve bank:pc or pc24 to symbol")
    lookup.add_argument("--bank")
    lookup.add_argument("--pc")
    lookup.add_argument("--pc24")
    lookup.add_argument("--cpu", help="CPU response string (CPU:pc=...,pb=...)")
    lookup.add_argument("--json", action="store_true")
    lookup.add_argument("--source", action="store_true", help="Search for label in source tree")
    lookup.add_argument("--limit", type=int, default=5)
    lookup.set_defaults(func=cmd_lookup)

    source = sub.add_parser("source", help="Find label in source tree")
    source.add_argument("label")
    source.add_argument("--limit", type=int, default=5)
    source.set_defaults(func=cmd_source)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
