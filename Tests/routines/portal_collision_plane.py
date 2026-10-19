#!/usr/bin/env python3
"""Characterize compiled Portal placement or check its plane-selection candidate.

Executes the actual RejectOnTileCollision RTS routine and native $06E87B tile
reader without stubs. A low-WRAM same-bank JSR/RTL supplies the normal call frame.
Only disposable WRAM fixtures and runner-required ROM padding are used. This is
CPU/ABI evidence, not a running SNES or a natural two-floor route.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM, SP, WRAPPER = 0x7E0000, 0x1FFF, 0x1E00
X_COORD, Y_COORD = 0x128, 0x230
CELL = ((Y_COORD & 0x1F8) << 3) + ((X_COORD & 0x1FF) >> 3)
CASES = (
    ("floor0-accept00", 0, 0, 0x00, 0x01),
    ("floor0-reject02", 7, 0, 0x02, 0x48),
    ("floor1-reject01", 7, 1, 0x00, 0x01),
    ("floor1-accept48", 15, 1, 0x02, 0x48),
)
NATIVE = bytes.fromhex(
    "8B4BAB2086E8AB6BBD200FC901C23064059005A900108505A51B29FF00F025"
    "A50229FF014A4A4A8504A50029F8010A0A0A186504186505DAAABF00207F"
    "FAE2308DA50F60")


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def symbol(text):
    matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+"
                         r"(?:Oracle_)?RejectOnTileCollision\s*$", text, re.M)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, "Missing/ambiguous placement symbol")
    return addresses.pop()


def pc(address):
    return ((address >> 16) & 127) * 0x8000 + (address & 0x7FFF)


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 127) < 0x40 and offset < 0x2000,
            f"Unexpected non-WRAM write {address:06X}")
    return WRAM + offset


def fixture(entry, case):
    name, slot, floor, a, b = case
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x2000))
    ram[0x10], ram[0x11], ram[0x1B], ram[0xEE] = 7, 0, 1, floor
    for address, value in ((0xD00, Y_COORD & 255), (0xD20, Y_COORD >> 8),
                           (0xD10, X_COORD & 255), (0xD30, X_COORD >> 8),
                           (0xDD0, 9), (0xF20, floor)):
        ram[address + slot] = value
    ram[0x12E], ram[0xFA5] = 0xA6, 0xD5
    ram[WRAPPER:WRAPPER + 4] = bytes((0x20, entry & 255, entry >> 8 & 255, 0x6B))
    planes = bytearray([0xC7] * 0x2000)
    planes[CELL], planes[0x1000 + CELL] = a, b
    request = dict(entry=(entry & 0xFF0000) | WRAPPER, reset_ram=True,
                   registers=dict(a=0xBE11, x=slot, y=0x5A, p=0x30,
                                  db=entry >> 16, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram)),
                           dict(address=0x7F2000, bytes=list(planes))],
                   reads=[dict(address=WRAM, length=len(ram)),
                          dict(address=0x7F2000, length=len(planes))],
                   trace_writes=True, max_steps=200)
    return ram, planes, request


def verify(entry, case, before, planes, result, control):
    name, slot, floor, a, b = case
    require(result.get("returned"), f"{name}: CPU failed: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{name}: unexpected simulated engine/device path")
    regs = result["registers"]
    for key, expected in dict(x=slot, y=0x5A, db=entry >> 16, d=0, sp=SP, e=0).items():
        require(regs[key] == expected, f"{name}: ABI {key}={regs[key]}")
    require(regs["p"] & 0x30 == 0x30, f"{name}: M/X width changed")
    after = bytes(result["reads"][0]["bytes"])
    require(bytes(result["reads"][1]["bytes"]) == planes, f"{name}: collision data modified")
    expected_attr = a if control or floor == 0 else b
    accepted = expected_attr in (0, 0x48)
    desired_attr = (a, b)[floor]
    require(after[0xFA5] == expected_attr, f"{name}: wrong collision-plane attribute")
    require(after[0xDD0 + slot] == (9 if accepted else 0), f"{name}: wrong acceptance")
    require(after[0x12E] == (0xA6 if accepted else 0x3C), f"{name}: wrong error SFX")
    for address in (0x10, 0x11, 0x1B, 0xEE, 0xF20 + slot):
        require(after[address] == before[address], f"{name}: changed context ${address:04X}")
    allowed = {WRAM + n for n in (*range(7), 0xFA5)}
    if not accepted:
        allowed.update((WRAM + 0x12E, WRAM + 0xDD0 + slot))
    allowed.update(range(WRAM + SP - 0x20, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's real JSL trampoline.
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    require(WRAM + 0xFA5 in writes, f"{name}: native reader did not publish its result")
    require(writes <= allowed, f"{name}: undeclared writes {sorted(writes - allowed)}")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{name}: unexpected final RAM change {WRAM + offset:06X}")
    return dict(name=name, passed=True, slot=slot, floor=floor,
                plane_a_attr=a, plane_b_attr=b, observed_attr=after[0xFA5],
                accepted=accepted, intended_acceptance=desired_attr in (0, 0x48),
                observed_bug=accepted != (desired_attr in (0, 0x48)),
                steps=result["steps"], registers=regs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("control", "candidate"), required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--cpu-runner", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    control = args.mode == "control"
    rom, sym = args.rom.read_bytes(), args.symbols.read_bytes()
    runner_hash = digest(args.cpu_runner.read_bytes())
    entry = symbol(sym.decode())
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    prefix = bytes.fromhex("BD000D29F88500BD200D8501BD100D29F88502BD300D8503")
    plane = bytes.fromhex("A900" if control else "BD200F")
    tail = bytes.fromhex("227BE806ADA50F18C900F00EC948F00AA93C8D2E01A9009DD00D60")
    require(rom[pc(entry):pc(entry) + len(prefix + plane + tail)] == prefix + plane + tail,
            "Unexpected compiled placement/plane-selection contract")
    require(rom[pc(0x06E87B):pc(0x06E87B) + len(NATIVE)] == NATIVE,
            "Native tile reader differs from reviewed bytes")
    plans = [(case, *fixture(entry, case)) for case in CASES]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="portal-plane-") as folder:
        copy = Path(folder) / "fixture.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input="".join(json.dumps(p[3]) + "\n" for p in plans),
                             text=True, capture_output=True, timeout=15, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Wrong number of CPU responses")
    cases = [verify(entry, case, ram, planes, json.loads(line), control)
             for (case, ram, planes, _), line in zip(plans, lines)]
    require(sum(c["observed_bug"] for c in cases) == (2 if control else 0),
            "Unexpected number of wrong-plane placement results")
    require(args.rom.read_bytes() == rom and args.symbols.read_bytes() == sym,
            "Original input ROM/symbols changed")
    require(digest(args.cpu_runner.read_bytes()) == runner_hash, "Existing CPU runner changed")
    result = dict(passed=True, mode=args.mode, rom_sha256=digest(rom),
                  symbols_sha256=digest(sym), runner_sha256=runner_hash,
                  script_sha256=digest(Path(__file__).read_bytes()),
                  entry=f"{entry:06X}", native_entry="06E87B", stubs=[],
                  fixture=dict(x=X_COORD, y=Y_COORD, plane_a_cell=f"{0x7F2000 + CELL:06X}",
                               plane_b_cell=f"{0x7F3000 + CELL:06X}"),
                  runner_copy_padding_bytes=padding, cases=cases,
                  source_inputs_unchanged=True,
                  claim="Compiled CPU characterization with synthetic two-plane WRAM; "
                        "control reproduces two wrong-plane outcomes; no native gameplay claim"
                        if control else "Compiled CPU regression with synthetic two-plane WRAM; "
                        "no native gameplay or natural-route claim")
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
