#!/usr/bin/env python3
"""Seed the synthetic CI ROM with the preimage bytes Dungeons/sky_d8_award.asm asserts.

Scope: CI ASM Syntax Check only. The bytes come from the source's own
`assert readN($ADDR[+$OFF]) == $VALUE[ || readN(same) == $OTHER]` guards, so
Asar's asserts pass on the zero-filled synthetic ROM. This does not show the
real base ROM matches; build_rom.sh checks the asserts against the real ROM.

Fails closed: any read*() use that is not a fully parsed guard, unsupported
widths, unmapped or out-of-range LoROM addresses, oversized values,
conflicting overlaps and conflicting nonzero bytes already in the ROM are
errors, and every check runs before the ROM file is written.
"""
import argparse
from pathlib import Path
import re
import sys

ROM_SIZE = 2 * 1024 * 1024
WIDTHS = (1, 2, 4)

_READ = re.compile(r"\bread\w*\s*\(", re.IGNORECASE)
_TERM = re.compile(
    r"read(?P<width>\d+)\(\$(?P<addr>[0-9A-Fa-f]{6})(?:\+\$(?P<off>[0-9A-Fa-f]+))?\)"
    r"\s*==\s*\$(?P<value>[0-9A-Fa-f]+)")
_ASSERT = re.compile(r"assert\s+(?P<expr>.+?)\s*,\s*\"[^\"]*\"")


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


def parse_guards(text, name="source"):
    """Return [(line, width, snes, value)]; first OR alternative wins."""
    guards = []
    for number, raw in enumerate(text.splitlines(), 1):
        code = strip_comment(raw).strip()
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
    parser.add_argument("source", help="Dungeons/sky_d8_award.asm")
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
