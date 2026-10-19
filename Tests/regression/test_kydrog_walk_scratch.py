#!/usr/bin/env python3
"""Run the compiled Kydrog walk branch on Yaze's existing 65816 CPU runner.

Private WRAM fixtures enter after the random-taunt choice. A same-bank WRAM
JSR/RTL wrapper supplies the real RTS frame; production instructions and native
direction helpers are unchanged. This is CPU/ABI proof, not a running SNES.
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
SCENARIOS = (
    ("east", 64, 0, 4), ("west", -64, 0, 3),
    ("south", 0, 64, 2), ("north", 0, -64, 5),
    ("near", 8, 8, 7),
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def symbol(text):
    matches = re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?"
        r"KydrogBoss_WalkState_not_taunting\s*$", text, re.M)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, "Missing/ambiguous Kydrog walk symbol")
    return addresses.pop()


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 0x7F) < 0x40 and offset < 0x2000,
            f"Unexpected non-WRAM write {address:06X}")
    return WRAM + offset


def fixture(entry, slot, scenario):
    name, dx, dy, action = scenario
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x2000))
    ram[0x09], ram[0x10], ram[0x11], ram[0x18] = 0xA9, 7, 0, 0xA6
    ram[0x20:0x22] = (0x2380 - 8 + dy).to_bytes(2, "little")
    ram[0x22:0x24] = (0x1280 + dx).to_bytes(2, "little")
    for table, value in ((0xD00, 0x80), (0xD10, 0x80), (0xD20, 0x23),
                         (0xD30, 0x12), (0xD80, 1), (0xEE0, 0x5A), (0xF70, 0)):
        ram[table + slot] = value
    # Execute a real JSR in the original code bank through its low WRAM mirror.
    ram[WRAPPER:WRAPPER + 4] = bytes((0x20, entry & 255, entry >> 8 & 255, 0x6B))
    request = dict(entry=(entry & 0xFF0000) | WRAPPER, reset_ram=True,
                   registers=dict(a=0xBE11, x=slot, y=0x5A, p=0x30,
                                  db=entry >> 16, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=1000)
    return ram, request


def verify(entry, slot, scenario, before, result, control):
    name, _, _, action = scenario
    label = f"{'control' if control else 'candidate'}/slot{slot}/{name}"
    require(result.get("returned"), f"{label}: CPU failed: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected simulated engine/device path")
    regs = result["registers"]
    for key, expected in dict(x=slot, db=entry >> 16, d=0, sp=SP, e=0).items():
        require(regs[key] == expected, f"{label}: ABI {key}={regs[key]}")
    require(regs["p"] & 0x30 == 0x30, f"{label}: M/X width changed")
    after = bytes(result["reads"][0]["bytes"])
    # Explicit control failures: slot7 corrupts module, slot15 corrupts $18.
    target = {0: 0x09, 7: 0x10, 15: 0x18}[slot] if control else 0x09
    require(after[target] == 0x50, f"{label}: expected store absent")
    for address in (0x09, 0x10, 0x11, 0x18):
        if address != target:
            require(after[address] == before[address], f"{label}: changed ${address:02X}")
    require(after[0xD80 + slot] == action, f"{label}: wrong movement/taunt action")
    require(after[0xEE0 + slot] == (0x20 if name == "near" else 0x5A),
            f"{label}: wrong action timer")
    allowed = {WRAM + n for n in (0, 1, 0xE, 0xF, 0xFB5, target,
                                  0xD80 + slot, 0xEE0 + slot)}
    allowed.update(range(WRAM + SP - 0x20, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's real JSL trampoline.
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    require(WRAM + target in writes, f"{label}: no traced scratch write")
    require(writes <= allowed, f"{label}: undeclared write {sorted(writes - allowed)}")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{label}: unexpected final RAM change {WRAM + offset:06X}")
    return dict(name=label, passed=True, module=after[0x10], submodule=after[0x11],
                scratch09=after[0x09], transfer18=after[0x18], action=action,
                steps=result["steps"], observed_bug=bool(control and slot != 0))


def execute(runner, rom_path, symbols_path, control):
    rom, sym = rom_path.read_bytes(), symbols_path.read_bytes()
    entry = symbol(sym.decode())
    offset = ((entry >> 16) & 127) * 0x8000 + (entry & 0x7FFF)
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    require(rom[offset:offset + 8] == bytes.fromhex(
        "A950950922A0EA06" if control else "A950850922A0EA06"),
        "Unexpected compiled scratch-store/direction-call contract")
    plans = [(slot, scenario, *fixture(entry, slot, scenario))
             for slot in (0, 7, 15) for scenario in SCENARIOS]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="kydrog-walk-") as folder:
        copy = Path(folder) / "fixture.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(runner), str(copy)],
                             input="".join(json.dumps(p[3]) + "\n" for p in plans),
                             text=True, capture_output=True, timeout=30, check=True)
    output = run.stdout.splitlines()
    require(len(output) == len(plans), "Wrong number of CPU responses")
    cases = [verify(entry, slot, scenario, before, json.loads(line), control)
             for (slot, scenario, before, _), line in zip(plans, output)]
    require(rom_path.read_bytes() == rom and symbols_path.read_bytes() == sym,
            "Original input ROM/symbols changed")
    return dict(rom_sha256=hashlib.sha256(rom).hexdigest(),
                symbols_sha256=hashlib.sha256(sym).hexdigest(), entry=f"{entry:06X}",
                runner_copy_padding_bytes=padding, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("rom", "symbols", "control-rom", "control-symbols", "cpu-runner"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    runner = args.cpu_runner.resolve()
    runner_hash = hashlib.sha256(runner.read_bytes()).hexdigest()
    candidate = execute(runner, args.rom, args.symbols, False)
    control = execute(runner, args.control_rom, args.control_symbols, True)
    require(hashlib.sha256(runner.read_bytes()).hexdigest() == runner_hash,
            "Existing CPU runner changed during test")
    print(json.dumps(dict(passed=True, candidate=candidate, control=control,
                          runner_sha256=runner_hash, stubs=[],
                          claim="Compiled walk branch and native direction helpers; "
                                "private RAM fixtures, no SNES system/native gameplay proof"),
                     indent=2))


if __name__ == "__main__":
    main()
