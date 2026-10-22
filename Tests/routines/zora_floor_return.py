#!/usr/bin/env python3
"""Check the compiled Zora floor-return hook/helper on Yaze's 65816 CPU.

The unchanged five-byte ROM hook runs from a same-bank low-WRAM wrapper; its
JSL executes the actual ROM helper. A trailing RTL ends the hook-boundary check
before vanilla's BNE. Private WRAM fixtures and temporary LoROM padding supply
the harness. This is CPU/ABI evidence, not native transition or save proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM, SP, WRAPPER, HOOK = 0x7E0000, 0x1FFF, 0x021E00, 0x0296C0
INITIAL = dict(a=0xBEEF, x=0xA6, y=0x5B, db=0x5A, d=0, sp=SP)
A5_SENTINEL = 0xA7
CASES = (
    # name, destination, source, initial floor, expected floor, initial P
    ("target-floor-minus2-to-minus1", 0x0035, 0x0044, 0xFE, 0xFF, 0x54),
    ("target-byte-wrap-preserves-a5", 0x0035, 0x0044, 0xFF, 0x00, 0xD7),
    ("wrong-source", 0x0035, 0x0045, 0xFE, 0xFE, 0xD7),
    ("wrong-destination", 0x0036, 0x0044, 0xFE, 0xFE, 0x54),
    ("destination-high-byte-0135", 0x0135, 0x0044, 0xFE, 0xFE, 0xD7),
    ("source-high-byte-0144", 0x0035, 0x0144, 0xFE, 0xFE, 0x54),
    ("hera-comparison-equal", 0x0017, 0x0044, 0xFE, 0xFE, 0xD7),
    ("comparison-less-than-17", 0x0016, 0x0044, 0xFE, 0xFE, 0x54),
)


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def symbol(text, name):
    matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?"
                         + re.escape(name) + r"\s*$", text, re.M)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, f"Missing/ambiguous symbol: {name}")
    return addresses.pop()


def raw(rom, address, size):
    offset = ((address >> 16) & 127) * 0x8000 + (address & 0x7FFF)
    data = rom[offset:offset + size]
    require(len(data) == size, f"ROM range missing at {address:06X}")
    return data


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 127) < 0x40 and offset < 0x2000,
            f"Unexpected non-WRAM write {address:06X}")
    return WRAM + offset


def fixture(case, hook_bytes):
    _, destination, source, floor, _, status = case
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    ram[0xA0:0xA2] = destination.to_bytes(2, "little")
    ram[0xA2:0xA4] = source.to_bytes(2, "little")
    ram[0xA4:0xA6] = bytes((floor, A5_SENTINEL))
    start = WRAPPER & 0xFFFF
    ram[start:start + 6] = hook_bytes + b"\x6B"
    request = dict(entry=WRAPPER, reset_ram=True,
                   registers=dict(INITIAL, p=status),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=100)
    return ram, request


def verify(case, before, result):
    name, destination, source, floor, expected_floor, status = case
    require(result.get("returned"), f"{name}: CPU did not return: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{name}: unexpected simulated engine/device path")
    regs = result["registers"]
    expected_regs = dict(INITIAL, a=destination, e=0)
    for key, expected in expected_regs.items():
        require(regs[key] == expected,
                f"{name}: ABI {key}={regs[key]}, expected {expected}")
    difference = (destination - 0x17) & 0xFFFF
    nzc = (0x80 if difference & 0x8000 else 0) | (0x02 if difference == 0 else 0)
    nzc |= int(destination >= 0x17)
    require(regs["p"] & 0x83 == nzc,
            f"{name}: CMP #$0017 NZC={regs['p'] & 0x83:02X}, expected {nzc:02X}")
    require(regs["p"] & ~0x83 == status & ~0x83,
            f"{name}: non-comparison flags changed: {regs['p']:02X}")
    require(regs["p"] & 0x30 == 0x10, f"{name}: expected M16/X8")
    after = bytes(result["reads"][0]["bytes"])
    require(len(after) == len(before), f"{name}: incomplete WRAM readback")
    require(after[0xA4:0xA6] == bytes((expected_floor, A5_SENTINEL)),
            f"{name}: floor/A5={after[0xA4:0xA6].hex()}, expected {expected_floor:02X}{A5_SENTINEL:02X}")
    # Runner JSL, real hook JSL, and helper PHP use exactly seven stack bytes.
    allowed = set(range(WRAM + SP - 6, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's real JSL trampoline.
    target = expected_floor != floor
    if target:
        allowed.add(WRAM + 0xA4)
    writes = [physical(write["address"]) for write in result.get("writes", [])]
    unexpected = set(writes) - allowed
    require(not unexpected, f"{name}: unexpected writes {sorted(unexpected)}")
    require(writes.count(WRAM + 0xA4) == int(target),
            f"{name}: floor write count {writes.count(WRAM + 0xA4)}, expected {int(target)}")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{name}: unexpected WRAM change {WRAM + offset:06X}: {old:02X}->{new:02X}")
    return dict(name=name, passed=True, destination=f"{destination:04X}",
                source=f"{source:04X}", initial_floor=f"{floor:02X}",
                final_floor=f"{after[0xA4]:02X}", a5=f"{after[0xA5]:02X}",
                comparison_nzc=f"{nzc:02X}", registers=regs, steps=result["steps"],
                floor_write_count=writes.count(WRAM + 0xA4), write_count=len(writes))


def execute(args):
    rom, symbols = args.rom.read_bytes(), args.symbols.read_bytes()
    runner_hash = digest(args.cpu_runner.read_bytes())
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    entry = symbol(symbols.decode(), "ZoraTemple_WarpReturnFloor")
    hook_bytes = raw(rom, HOOK, 5)
    require(hook_bytes == b"\x22" + entry.to_bytes(3, "little") + b"\xEA",
            "Compiled hook must be JSL helper / NOP")
    require(raw(rom, HOOK - 2, 2) == b"\xC2\x20"
            and raw(rom, HOOK + 5, 6) == bytes.fromhex("D004A20486A4"),
            "Original M16 entry / Hera BNE and floor assignment changed")
    require(0x2CFC00 <= entry and entry + 26 <= 0x2CFD00,
            "Helper outside its reserved bank-$2C allocation")
    helper = raw(rom, entry, 26)
    plans = [(case, *fixture(case, hook_bytes)) for case in CASES]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="zora-floor-return-") as folder:
        copy = Path(folder) / "fixture.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(args.cpu_runner.resolve()), str(copy)],
                             input="".join(json.dumps(request) + "\n"
                                           for _, _, request in plans),
                             text=True, capture_output=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), f"Expected {len(plans)} CPU responses, got {len(lines)}")
    results = [verify(case, before, json.loads(line))
               for (case, before, _), line in zip(plans, lines)]
    require(args.rom.read_bytes() == rom and args.symbols.read_bytes() == symbols,
            "Input ROM/symbols changed during the check")
    require(digest(args.cpu_runner.read_bytes()) == runner_hash, "Existing CPU runner changed")
    return dict(passed=True, cases=results, rom_sha256=digest(rom),
                symbols_sha256=digest(symbols), runner_sha256=runner_hash,
                script_sha256=digest(Path(__file__).read_bytes()),
                hook=f"{HOOK:06X}", hook_bytes=hook_bytes.hex(), helper=f"{entry:06X}",
                helper_bytes=helper.hex(), wrapper=f"{WRAPPER:06X}", stubs=[],
                runner_copy_padding_bytes=padding, source_inputs_unchanged=True,
                claim="Actual compiled hook/helper on Yaze CPU with private WRAM fixtures; "
                      "comparison boundary only; no native transition, camera, save or earned-route proof")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(args)
    except Exception as exc:
        result = dict(passed=False, error=repr(exc), script_sha256=digest(Path(__file__).read_bytes()))
    text = json.dumps(result, indent=2) + "\n"
    args.output.write_text(text)
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
