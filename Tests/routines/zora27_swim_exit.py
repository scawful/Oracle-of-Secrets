#!/usr/bin/env python3
"""Check the compiled room-$27 north-stair swim exit on Yaze's 65816 CPU.

The actual five-byte ROM hook runs from a same-bank low-WRAM wrapper. Its JSL
executes the ROM helper and the native $07983A/$079873 momentum reset, with no
engine stubs. Private WRAM fixtures supply each guard state; a trailing RTL
ends the check before vanilla clears the submodule. This is CPU/ABI evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM, SP, WRAPPER, HOOK = 0x7E0000, 0x1FFF, 0x021E00, 0x028F7C
INITIAL = dict(a=0xBEEF, x=0xA6, y=0x5B, db=0x02, d=0, sp=SP)
RESET_BYTE = (0x02CB, 0x034F, 0x032A)
RESET_WORD = (0x032F, 0x0331, 0x0326, 0x0328, 0x032B,
              0x032D, 0x033C, 0x033E, 0x0334, 0x0336)
RESET_OFFSETS = set(RESET_BYTE)
RESET_OFFSETS.update(offset + byte for offset in RESET_WORD for byte in (0, 1))
EXIT_OFFSETS = {0x5D, 0x0345} | RESET_OFFSETS
BASE = {0xA0: 0x27, 0xA1: 0, 0x1B: 1, 0x11: 8, 0x67: 0, 0xF411: 1,
        0x5D: 4, 0x0345: 1, 0xEE: 0, 0x0476: 0, 0xA4: 0,
        0xA5: 0xA7, 0xB0: 0x95, 0x0418: 0xA9}
CASES = (
    # name, byte overrides, cleanup expected, initial P, initial D, initial DB
    ("filled-north-exit-native-zero-swim-input", {}, True, 0x30, 0, 0x02),
    ("filled-bit-and-nonzero-water-full-register-save",
     {0xF411: 0xA5, 0x0345: 0x80, 0x67: 0x18}, True, 0xFF, 0x1234, 0x7F),
    ("wrong-room", {0xA0: 0x26}, False, 0xFF, 0, 0x02),
    ("foreign-db-d-vanilla-store-addressing", {0xA0: 0x26}, False, 0x30, 0x0100, 0x7F),
    ("room-high-byte-0127", {0xA1: 1}, False, 0x30, 0, 0x02),
    ("room35-floor-return-control", {0xA0: 0x35, 0xA4: 0xFF}, False, 0xFF, 0, 0x02),
    ("outdoors", {0x1B: 0}, False, 0x30, 0, 0x02),
    ("south-stair-module", {0x11: 0x10, 0x67: 4, 0x0476: 1}, False, 0xFF, 0, 0x02),
    ("wrong-submodule", {0x11: 0}, False, 0x30, 0, 0x02),
    ("reservoir-dry-other-flag-set", {0xF411: 2}, False, 0x30, 0, 0x02),
    ("link-not-swimming", {0x5D: 0}, False, 0xFF, 0, 0x02),
    ("not-in-deep-water", {0x0345: 0}, False, 0x30, 0, 0x02),
    ("lower-ee-plane", {0xEE: 1}, False, 0xFF, 0, 0x02),
    ("lower-stair-plane", {0x0476: 1}, False, 0x30, 0, 0x02),
    ("wrong-floor", {0xA4: 0xFF}, False, 0xFF, 0, 0x02),
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
    _, overrides, _, status, direct_page, data_bank = case
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    for offset, value in (BASE | overrides).items():
        ram[offset] = value
    # Every reset byte begins nonzero, making every expected cleanup observable.
    for offset in RESET_OFFSETS:
        ram[offset] = 0x6D
    start = WRAPPER & 0xFFFF
    ram[start:start + 6] = hook_bytes + b"\x6B"
    registers = dict(INITIAL, p=status, d=direct_page, db=data_bank)
    request = dict(entry=WRAPPER, reset_ram=True, registers=registers,
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=150)
    return ram, request


def verify(case, before, result):
    name, _, cleanup, status, direct_page, data_bank = case
    require(result.get("returned"), f"{name}: CPU did not return: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{name}: unexpected simulated engine/device path")
    regs = result["registers"]
    expected_regs = dict(INITIAL, p=status, d=direct_page, db=data_bank, e=0)
    for key, expected in expected_regs.items():
        require(regs[key] == expected,
                f"{name}: ABI {key}={regs[key]}, expected {expected}")
    require(regs["p"] & 0x30 == 0x30, f"{name}: expected M8/X8")

    after = bytes(result["reads"][0]["bytes"])
    require(len(after) == len(before), f"{name}: incomplete WRAM readback")
    # Original STZ direct page uses D; original absolute STZ uses the caller DB.
    displaced = {physical((direct_page + 0xB0) & 0xFFFF) - WRAM,
                 physical((data_bank << 16) | 0x0418) - WRAM}
    state_writes = displaced | (EXIT_OFFSETS if cleanup else set())
    for offset in state_writes:
        require(after[offset] == 0,
                f"{name}: expected zero at {WRAM + offset:06X}, got {after[offset]:02X}")
    # Runner/hook JSLs + PHP + full A/X/Y + DB/D = 16 saved bytes.
    # PHK temporarily uses byte 17. Native JSL + PHB + JSR reaches byte 22.
    stack_depth = 22 if cleanup else 17
    stack = set(range(WRAM + SP - stack_depth + 1, WRAM + SP + 1))
    trampoline = set(range(0x7F8000, 0x7F8004))
    allowed = stack | trampoline | {WRAM + offset for offset in state_writes}
    writes = [physical(write["address"]) for write in result.get("writes", [])]
    unexpected = set(writes) - allowed
    require(not unexpected, f"{name}: unexpected writes {sorted(unexpected)}")
    counts = Counter(address for address in writes if address not in stack | trampoline)
    expected_counts = Counter({WRAM + offset: 1 for offset in state_writes})
    require(counts == expected_counts,
            f"{name}: state write counts {dict(counts)}, expected {dict(expected_counts)}")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{name}: unexpected WRAM change {WRAM + offset:06X}: {old:02X}->{new:02X}")
    # These include the plane/floor and the high bytes beside both replaced STZs.
    for offset in (0xA0, 0xA1, 0xA4, 0xA5, 0xB1, 0xEE, 0x0476, 0x0419, 0xF411):
        require(after[offset] == before[offset], f"{name}: preserved state changed at {offset:04X}")
    return dict(name=name, passed=True, cleanup=cleanup, registers=regs,
                steps=result["steps"], state_write_addresses=[f"{address:06X}" for address in sorted(counts)],
                write_count=len(writes), maximum_stack_depth=stack_depth)


def execute(args):
    rom, symbols = args.rom.read_bytes(), args.symbols.read_bytes()
    runner_hash = digest(args.cpu_runner.read_bytes())
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    text = symbols.decode()
    entry = symbol(text, "ZoraTemple_StairSwimExit_Long")
    end = symbol(text, "ZoraTemple_StairSwimExit_End")
    floor_entry = symbol(text, "ZoraTemple_WarpReturnFloor")
    floor_end = symbol(text, "ZoraTemple_WarpReturnFloor_End")
    require(0x2C8000 <= floor_entry < floor_end == entry < end <= 0x2CFD00,
            "Helpers are outside their ordered bank-$2C stream or overlap SomariaSocketDoor")
    hook_bytes = raw(rom, HOOK, 5)
    require(hook_bytes == b"\x22" + entry.to_bytes(3, "little") + b"\xEA",
            "Compiled hook must be JSL helper / NOP")
    require(raw(rom, HOOK + 5, 2) == bytes.fromhex("6411"),
            "Vanilla submodule clear following the displaced STZ pair changed")
    helper = raw(rom, entry, end - entry)
    require(helper.count(bytes.fromhex("223a9807")) == 1,
            "Helper must call actual Link_ResetSwimmingState exactly once")
    native_reset = raw(rom, 0x07983A, 17)
    native_accel = raw(rom, 0x079873, 35)
    require(native_reset == bytes.fromhex("8b4bab9ccb029c4f039c2a03207398ab6b"),
            "Native Link_ResetSwimmingState changed; review its write contract")
    require(native_accel == bytes.fromhex(
        "c2209c2f039c31039c26039c28039c2b039c2d039c3c039c3e039c34039c3603e22060"),
        "Native ResetAllAcceleration changed; review its write contract")
    require(floor_end - floor_entry == 26 and raw(rom, 0x0296C0, 5)
            == b"\x22" + floor_entry.to_bytes(3, "little") + b"\xEA",
            "Existing floor-return byte count or symbol-bound hook changed")
    require(raw(rom, floor_entry, 26) == bytes.fromhex(
        "08a5a0c93500d00ba5a2c94400d004e220e6a428a5a0c917006b"),
        "Existing floor-return helper changed")

    plans = [(case, *fixture(case, hook_bytes)) for case in CASES]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="zora27-swim-exit-") as folder:
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
                helper_end=f"{end:06X}", helper_bytes=helper.hex(),
                native_reset="07983A", native_reset_bytes=native_reset.hex(),
                native_accel="079873", native_accel_bytes=native_accel.hex(),
                wrapper=f"{WRAPPER:06X}", stubs=[], runner_copy_padding_bytes=padding,
                source_inputs_unchanged=True,
                claim="Actual compiled hook/helper and native swim reset on Yaze CPU with "
                      "private WRAM fixtures; hook-boundary ABI/write proof; native controller "
                      "route, chest interaction and save/reopen require separate evidence")


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
