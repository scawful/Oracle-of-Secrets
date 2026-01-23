#!/usr/bin/env python3
"""
Decode Mesen stack dump into possible return addresses with symbol lookup.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Tuple

from symbols import SymbolResolver, parse_int

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_input(value: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.exists():
        return path.read_text().strip()
    return value.strip()


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


def parse_stack(raw: str) -> Tuple[int | None, list[int]]:
    sp = None
    if raw.startswith("STACK:"):
        raw = raw[len("STACK:") :]
    if "sp=" in raw:
        prefix, _, tail = raw.partition(":")
        for part in prefix.split(","):
            if "sp=" in part:
                sp = parse_int(part.split("sp=", 1)[1])
        raw = tail
    hexstr = raw.replace(":", "").strip()
    if not hexstr:
        return sp, []
    hexstr = "".join(hexstr.split())
    if len(hexstr) % 2 == 1:
        hexstr = hexstr[:-1]
    bytes_out = []
    for i in range(0, len(hexstr), 2):
        try:
            bytes_out.append(int(hexstr[i : i + 2], 16))
        except ValueError:
            break
    return sp, bytes_out


def format_word(word: int | None) -> str:
    if word is None:
        return "????"
    return f"0x{word:04X}"


def format_long(value: int | None) -> str:
    if value is None:
        return "??????"
    return f"0x{value:06X}"


def is_plausible_bank(bank: int | None) -> bool:
    if bank is None:
        return False
    return (0x00 <= bank <= 0x3F) or (0x80 <= bank <= 0xBF)


def main() -> int:
    parser = argparse.ArgumentParser(description="Decode stack bytes into return addresses")
    parser.add_argument("--cpu", help="CPU response string (CPU:pc=...,pb=...,sp=...)")
    parser.add_argument("--stack", help="STACK response string or path to file")
    parser.add_argument("--sym", default=str(REPO_ROOT / "Roms" / "oos168x.sym"))
    parser.add_argument("--bank", help="Override bank for symbol lookup")
    parser.add_argument("--limit", type=int, default=16)
    args = parser.parse_args()

    cpu_raw = _read_input(args.cpu) if args.cpu else ""
    stack_raw = _read_input(args.stack) if args.stack else ""
    cpu = parse_cpu(cpu_raw)
    sp, stack_bytes = parse_stack(stack_raw)
    bank = parse_int(args.bank)
    if bank is None:
        bank = cpu.get("pb")

    resolver = SymbolResolver(Path(args.sym))

    print("# Stack Report")
    if bank is not None:
        print(f"Bank: 0x{bank:02X}")
    if sp is not None:
        print(f"SP: 0x{sp:04X}")
    print(f"Bytes: {len(stack_bytes)}")

    if not stack_bytes:
        print("No stack bytes to decode.")
        return 1

    print("\nPossible return addresses (16-bit, RTS-style):")
    count = 0
    for i in range(0, len(stack_bytes) - 1):
        if count >= args.limit:
            break
        lo = stack_bytes[i]
        hi = stack_bytes[i + 1]
        word = lo | (hi << 8)
        if bank is not None:
            callsite = (word - 1) & 0xFFFF
            label = resolver.resolve(bank, word) if bank is not None else None
            call_label = resolver.resolve(bank, callsite) if bank is not None else None
            print(
                f"  +{i:02X}: ret {format_word(word)} {label or ''} | call {format_word(callsite)} {call_label or ''}"
            )
        else:
            print(f"  +{i:02X}: ret {format_word(word)}")
        count += 1

    print("\nPossible return addresses (24-bit, RTL-style):")
    count = 0
    for i in range(0, len(stack_bytes) - 2):
        if count >= args.limit:
            break
        lo = stack_bytes[i]
        hi = stack_bytes[i + 1]
        bank_byte = stack_bytes[i + 2]
        if not is_plausible_bank(bank_byte):
            continue
        word = lo | (hi << 8)
        addr24 = (bank_byte << 16) | word
        callsite = (addr24 - 1) & 0xFFFFFF
        label = resolver.resolve(bank_byte, word)
        call_label = resolver.resolve((callsite >> 16) & 0xFF, callsite & 0xFFFF)
        print(
            f"  +{i:02X}: ret {format_long(addr24)} {label or ''} | call {format_long(callsite)} {call_label or ''}"
        )
        count += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
