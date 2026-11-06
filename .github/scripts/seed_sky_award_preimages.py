#!/usr/bin/env python3
"""Seed the synthetic CI ROM with preimages from guarded ASM sources.

Scope: CI ASM Syntax Check only. The bytes come from the source's own
`assert readN($ADDR[+$OFF]) == $VALUE[ || readN(same) == $OTHER]` guards, so
Asar's asserts pass on the zero-filled synthetic ROM. This does not show the
real base ROM matches; build_rom.sh checks the asserts against the real ROM.

Fails closed: any read*() use that is not a fully parsed guard, unsupported
widths, unmapped or out-of-range LoROM addresses, oversized values,
conflicting overlaps and conflicting nonzero bytes already in the ROM are
errors, and every check runs before the ROM file is written.

BombchuReceiptHook is the one supported read-guard macro: its complete
definition must match the reviewed template, with exactly 25 literal callers.
It expands into the same literal read4/read1..3 guards parsed below.
"""
import argparse
from pathlib import Path
import re
import sys

ROM_SIZE = 2 * 1024 * 1024
WIDTHS = (1, 2, 3, 4)

_READ = re.compile(r"\bread\w*\s*\(", re.IGNORECASE)
_TERM = re.compile(
    r"read(?P<width>\d+)\(\$(?P<addr>[0-9A-Fa-f]{6})(?:\+\$(?P<off>[0-9A-Fa-f]+))?\)"
    r"\s*==\s*\$(?P<value>[0-9A-Fa-f]+)")
_ASSERT = re.compile(r"assert\s+(?P<expr>.+?)\s*,\s*\"[^\"]*\"")
_MACRO = re.compile(r"macro\s+(\w+)\b", re.IGNORECASE)
_ORG = re.compile(r"org\s+\$([0-9A-Fa-f]{6})", re.IGNORECASE)
_RECEIPT_USE = re.compile(r"%\s*BombchuReceiptHook\b", re.IGNORECASE)
_RECEIPT_CALL = re.compile(
    r"%BombchuReceiptHook\(\s*\$(?P<site>[0-9A-Fa-f]{6})\s*,\s*"
    r"\$(?P<preimage>[0-9A-Fa-f]+)\s*,\s*\$(?P<tail>[0-9A-Fa-f]+)\s*,\s*"
    r"(?P<count>\d+)\s*,\s*(?P<target>[A-Za-z_]\w*)\s*,\s*(?P<jump>[01])\s*\)")
_RECEIPT_TEMPLATE = """\
macro BombchuReceiptHook(site, preimage, tail, count, target, jump)
  assert pc() == <site>, "Bombchu receipt caller org changed"
  assert read4(<site>) == <preimage>, "Bombchu receipt reader preimage changed"
if <count> == 5
  assert read1(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
elseif <count> == 6
  assert read2(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
elseif <count> == 7
  assert read3(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
endif
if <jump> == 1
  JML <target>
else
  JSL <target>
endif
  NOP #<count>-4
  assert pc() == <site>+<count>
endmacro
"""


class SeedError(Exception):
    pass


def strip_comment(line):
    in_string = False
    for index, char in enumerate(line):
        if char == '"':
            in_string = not in_string
        elif char == ";" and not in_string:
            return line[:index]
    return line


def lorom_offset(snes):
    """Headerless LoROM file offset of a mapped ROM address."""
    if not 0 <= snes <= 0xFFFFFF:
        raise SeedError(f"${snes:X} is not a 24-bit address")
    bank = (snes >> 16) & 0x7F
    if bank >= 0x7E or snes & 0xFFFF < 0x8000:
        raise SeedError(f"${snes:06X} is not a mapped LoROM ROM address")
    return bank * 0x8000 + (snes & 0x7FFF)


def parse_term(text, where):
    match = _TERM.fullmatch(text.strip())
    if not match:
        raise SeedError(f"{where}: unsupported read guard term: {text.strip()}")
    width = int(match["width"])
    if width not in WIDTHS:
        raise SeedError(f"{where}: unsupported read width read{width}")
    address = int(match["addr"], 16) + int(match["off"] or "0", 16)
    value = int(match["value"], 16)
    if len(match["value"]) > 2 * width or value >> (8 * width):
        raise SeedError(f"{where}: ${match['value']} does not fit read{width}")
    return width, address, value


def expand_receipt_guards(text, name):
    """Validate the fixed receipt macro; leave unknown macro guards as errors."""
    lines = [(n, code) for n, raw in enumerate(text.splitlines(), 1)
             if (code := strip_comment(raw).strip())]
    output, sites = [], set()
    defined, callers, index = False, 0, 0
    while index < len(lines):
        number, code = lines[index]
        where = f"{name}:{number}"
        macro = _MACRO.match(code)
        if macro:
            end = index + 1
            while end < len(lines) and lines[end][1].lower() != "endmacro":
                if _MACRO.match(lines[end][1]):
                    raise SeedError(f"{where}: nested macro definition is unsupported")
                end += 1
            if end == len(lines):
                raise SeedError(f"{where}: unterminated macro definition")
            body = "\n".join(line for _, line in lines[index:end + 1])
            if macro[1] == "BombchuReceiptHook":
                if defined or re.sub(r"\s+", "", body) != re.sub(r"\s+", "", _RECEIPT_TEMPLATE):
                    raise SeedError(f"{where}: BombchuReceiptHook macro definition changed")
                defined = True
            elif _READ.search(body) or _RECEIPT_USE.search(body):
                raise SeedError(f"{where}: unsupported read-guard macro {macro[1]}")
            index = end + 1
            continue
        if _RECEIPT_USE.search(code):
            call = _RECEIPT_CALL.fullmatch(code)
            if not defined or not call:
                raise SeedError(f"{where}: expected a validated macro and literal receipt caller")
            address, count = int(call["site"], 16), int(call["count"])
            if count not in (4, 5, 6, 7):
                raise SeedError(f"{where}: receipt native count must be 4..7")
            org = _ORG.fullmatch(output[-1][1]) if output else None
            if not org or int(org[1], 16) != address:
                raise SeedError(f"{where}: receipt caller must follow its matching literal org")
            if (address & 0xFFFF) + count > 0x10000:
                raise SeedError(f"{where}: receipt native span crosses a bank")
            start = lorom_offset(address)
            span = set(range(start, start + count))
            if sites & span:
                raise SeedError(f"{where}: overlapping receipt native spans")
            sites.update(span)
            output.append((number, f'assert read4(${address:06X}) == ${call["preimage"]}, "receipt head"'))
            if count > 4:
                output.append((number, f'assert read{count - 4}(${address:06X}+$4) == ${call["tail"]}, "receipt tail"'))
            elif len(call["tail"]) > 2 or int(call["tail"], 16) != 0:
                raise SeedError(f"{where}: unused receipt tail must be zero")
            callers += 1
        else:
            output.append((number, code))
        index += 1
    if defined and callers != 25:
        raise SeedError(f"{name}: expected 25 receipt callers, found {callers}")
    return output


def parse_guards(text, name="source"):
    """Return [(line, width, snes, value)]; first OR alternative wins."""
    guards = []
    for number, code in expand_receipt_guards(text, name):
        if not _READ.search(code):
            continue
        where = f"{name}:{number}"
        match = _ASSERT.fullmatch(code)
        if not match:
            raise SeedError(f"{where}: read*() outside a supported assert: {code}")
        terms = [parse_term(term, where) for term in match["expr"].split("||")]
        width, address, value = terms[0]
        if any((w, a) != (width, address) for w, a, _ in terms[1:]):
            raise SeedError(f"{where}: OR alternatives must read the same width and address")
        guards.append((number, width, address, value))
    return guards


def guard_bytes(guards, rom_size=ROM_SIZE):
    """Map file offset -> byte, rejecting bank crossings, bounds and conflicts."""
    found = {}
    owner = {}
    for number, width, address, value in guards:
        if (address & 0xFFFF) + width > 0x10000:
            raise SeedError(f"line {number}: read{width}(${address:06X}) crosses a bank")
        start = lorom_offset(address)
        if start + width > rom_size:
            raise SeedError(f"line {number}: ${address:06X} is past the {rom_size}-byte ROM")
        for index in range(width):
            byte = (value >> (8 * index)) & 0xFF
            offset = start + index
            if offset in found and found[offset] != byte:
                raise SeedError(f"line {number}: PC ${offset:05X} conflicts with "
                                f"line {owner[offset]} (${found[offset]:02X} vs ${byte:02X})")
            found[offset] = byte
            owner.setdefault(offset, number)
    return found


def apply_seed(rom, seed):
    """Return a seeded copy of rom; validate everything before changing bytes."""
    if len(rom) != ROM_SIZE:
        raise SeedError(f"synthetic ROM is {len(rom)} bytes, expected {ROM_SIZE}")
    conflicts = [f"${offset:05X}=${rom[offset]:02X} (want ${byte:02X})"
                 for offset, byte in sorted(seed.items())
                 if rom[offset] not in (0, byte)]
    if conflicts:
        raise SeedError("existing nonzero bytes conflict: " + ", ".join(conflicts))
    seeded = bytearray(rom)
    for offset, byte in seed.items():
        seeded[offset] = byte
    return seeded


def seed_file(source, rom_path):
    guards = parse_guards(Path(source).read_text(), str(source))
    if not guards:
        raise SeedError(f"{source}: no read guards found")
    seed = guard_bytes(guards)
    rom_path = Path(rom_path)
    rom_path.write_bytes(apply_seed(rom_path.read_bytes(), seed))
    return len(guards), len(seed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="ASM source with supported preimage guards")
    parser.add_argument("rom", help="synthetic 2 MiB headerless test ROM")
    args = parser.parse_args(argv)
    try:
        guards, count = seed_file(args.source, args.rom)
    except SeedError as error:
        print(f"::error::Sky preimage seed: {error}", file=sys.stderr)
        return 1
    print(f"Sky preimage seed: {guards} guards, {count} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
