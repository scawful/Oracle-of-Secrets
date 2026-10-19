#!/usr/bin/env python3
"""Check compiled D3 prison transactions with the existing 65816 CPU runner.

Uses real candidate instructions and synthetic WRAM, without engine stubs or a
running SNES. The optional default/control pair must be byte-identical, proving
that the diagnostic-off build did not change the ROM. No input file is modified.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM, SAVE, SP = 0x7E0000, 0x7EF300, 0x1FFF
FLAGS, SWORD = 0x7EF306, 0x7EF359
ARM = "Oracle_PrisonSequence_PostMeadowBlade"
CAPTURE = "D3Prison_Capture"
RECLAIM = "D3Prison_Reclaim"
ESCAPE = "D3Prison_CompleteEscape"


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def symbol(text, name):
    matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+"
                         r"(?:Oracle_)?" + re.escape(name) + r"\s*$", text, re.M)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, f"Missing/ambiguous compiled symbol: {name}")
    return addresses.pop()


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 0x7F) < 0x40 and offset < 0x2000,
            f"Unexpected non-WRAM write ${address:06X}")
    return WRAM + offset


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    flags: int
    sword: int
    expected_flags: int
    expected_sword: int
    carry: int | None
    room: int = 0x56
    dungeon: int = 0x10
    indoors: int = 1
    module: int = 7
    submodule: int = 0
    item: int = 1
    p: int = 0xF5  # M/X8, unrelated status bits and incoming C set.
    db: int = 0x35  # Deliberately different from the helper's code bank.
    y: int = 4


def cases():
    arm = Case("receipt-arms-preserves-reserved", ARM, 0x80, 2, 0x84, 2, None)
    capture = Case("capture-stores-blade", CAPTURE, 0x84, 2, 0xA1, 0, 1)
    reclaim = Case("reclaim-restores-blade", RECLAIM, 0xA1, 0, 0xA9, 2, 1, room=0x54)
    escape = Case("exit-commits-escape", ESCAPE, 0xA9, 2, 0xAB, 2, 1,
                  room=0x55, module=8)
    result = [arm, capture, reclaim, escape]

    def reject(base, name, **changes):
        case = replace(base, name=name, **changes)
        result.append(replace(case, expected_flags=case.flags,
                              expected_sword=case.sword,
                              carry=None if case.helper == ARM else 0))

    for name, changes in (
        ("receipt-other-item", dict(item=0)),
        ("receipt-room-alias", dict(room=0x156)),
        ("receipt-other-room", dict(room=0x54)),
        ("receipt-old-wrong-dungeon", dict(dungeon=0x0A)),
        ("receipt-outdoors", dict(indoors=0)),
        ("receipt-other-sword", dict(sword=3)),
        ("receipt-already-captured", dict(flags=0xA1)),
        ("receipt-already-escaped", dict(flags=0x82)),
        ("receipt-partial-reclaimed", dict(flags=0x88)),
        ("receipt-repeat-is-idempotent", dict(flags=0x84)),
    ):
        reject(arm, name, **changes)
    result.append(replace(arm, name="receipt-native-standing", flags=0,
                          expected_flags=4, y=0, p=0x34))

    for name, changes in (
        ("capture-not-armed", dict(flags=0x80)),
        ("capture-repeat-keeps-backup", dict(flags=0xA1, sword=0)),
        ("capture-escaped", dict(flags=0xAB)),
        ("capture-partial-state", dict(flags=0x85)),
        ("capture-no-sword", dict(sword=0)),
        ("capture-smith-sentinel", dict(sword=0xFF)),
        ("capture-later-sword", dict(sword=3)),
        ("capture-full-room-id", dict(room=0x156)),
        ("capture-other-room", dict(room=0x55)),
        ("capture-other-dungeon", dict(dungeon=0x0A)),
        ("capture-outdoors", dict(indoors=0)),
        ("capture-menu", dict(module=0x0E)),
        ("capture-room-transition", dict(submodule=2)),
    ):
        reject(capture, name, **changes)

    for name, changes in (
        ("reclaim-repeat", dict(flags=0xA9, sword=2)),
        ("reclaim-before-capture", dict(flags=0x84)),
        ("reclaim-mixed-pending", dict(flags=0xA5)),
        ("reclaim-no-backup", dict(flags=0x81)),
        ("reclaim-invalid-backup-five", dict(flags=0xD1)),
        ("reclaim-invalid-backup-seven", dict(flags=0xF1)),
        ("reclaim-smith-sentinel", dict(sword=0xFF)),
        ("reclaim-invalid-current-five", dict(sword=5)),
        ("reclaim-full-room-id", dict(room=0x154)),
        ("reclaim-wrong-table-room", dict(room=0x55)),
        ("reclaim-other-dungeon", dict(dungeon=0x0A)),
        ("reclaim-not-player-control", dict(submodule=0x15)),
    ):
        reject(reclaim, name, **changes)
    result.extend((
        replace(reclaim, name="reclaim-keeps-better-sword", sword=4, expected_sword=4),
        replace(reclaim, name="reclaim-valid-backup-one", flags=0x91,
                expected_flags=0x99, expected_sword=1),
        replace(reclaim, name="reclaim-valid-backup-four", flags=0x41,
                expected_flags=0x49, expected_sword=4),
    ))

    for name, changes in (
        ("exit-repeat", dict(flags=0xAB)),
        ("exit-before-reclaim", dict(flags=0xA1, sword=0)),
        ("exit-partial-reclaimed-only", dict(flags=0xA8)),
        ("exit-still-pending", dict(flags=0xAD)),
        ("exit-no-backup", dict(flags=0x89)),
        ("exit-invalid-backup", dict(flags=0xD9)),
        ("exit-sword-not-restored", dict(sword=1)),
        ("exit-smith-sentinel", dict(sword=0xFF)),
        ("exit-full-room-id", dict(room=0x155)),
        ("exit-other-room", dict(room=0x54)),
        ("exit-merely-entered-room55", dict(module=7)),
        ("exit-outdoor-context-already-erased", dict(indoors=0, dungeon=0xFF)),
        ("exit-other-dungeon", dict(dungeon=0x0A)),
    ):
        reject(escape, name, **changes)
    result.append(replace(escape, name="exit-keeps-later-sword", sword=4,
                          expected_sword=4))

    # Receipt hook promises M/X8 only; the three transaction leaves promise
    # width transparency. Cover all remaining native M/X combinations, with
    # high index-register canaries when X=16 and both incoming Carry values.
    for base in (capture, reclaim, escape):
        for p in (0x04, 0x14, 0x24):
            result.append(replace(base, name=f"{base.name}-p{p:02X}", p=p,
                                  db=0x7E, y=0xA65A if not p & 0x10 else 0x5A))
    return result


def fixture(case, entry):
    low = bytearray((n * 37 + 11) & 255 for n in range(0x2000))
    save = bytearray((n * 53 + 17) & 255 for n in range(0x100))
    low[0x10], low[0x11], low[0x1B] = case.module, case.submodule, case.indoors
    low[0xA0:0xA2] = case.room.to_bytes(2, "little")
    low[0x40C] = case.dungeon
    low[0x5D], low[0x2D8], low[0x2D9] = 0xA6, 0xC7, 0x59
    low[0xC5E:0xC68] = bytes([0x01] * 10)
    x = 7 if case.p & 0x10 else 0xA517
    if case.helper == ARM:
        low[0xC5E + x] = case.item  # Neighbour slots remain item01 as canaries.
    save[FLAGS - SAVE], save[SWORD - SAVE] = case.flags, case.sword
    registers = dict(a=0xBE11, x=x, y=case.y, p=case.p, db=case.db, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=WRAM, bytes=list(low)),
                           dict(address=SAVE, bytes=list(save))],
                   reads=[dict(address=WRAM, length=len(low)),
                          dict(address=SAVE, length=len(save))],
                   trace_writes=True, max_steps=400)
    return low, save, request


def verify(case, low, save, request, result):
    label = case.name
    require(result.get("returned"), f"{label}: CPU failed: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected engine stub/device access")
    regs = result["registers"]
    for key in ("x", "y", "db", "d", "sp"):
        require(regs[key] == request["registers"][key], f"{label}: ABI changed {key}")
    require(regs["e"] == 0, f"{label}: left native CPU mode")
    expected_p = case.p
    if case.helper == ARM:
        expected_p = (case.p & ~0x82) | (0x02 if case.item == 0 else case.item & 0x80)
        require(regs["a"] == 0xBE00 | case.item, f"{label}: native item A not replayed")
    status_mask = 0xFF if case.carry is None else 0xFE
    require(regs["p"] & status_mask == expected_p & status_mask,
            f"{label}: caller status/width changed")
    if case.carry is not None:
        require(regs["p"] & 1 == case.carry, f"{label}: wrong transaction Carry")

    expected_low, expected_save = bytearray(low), bytearray(save)
    expected_save[FLAGS - SAVE] = case.expected_flags
    expected_save[SWORD - SAVE] = case.expected_sword
    allowed = set(range(WRAM + SP - 0x20, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's real JSL trampoline.
    if case.helper == ARM:
        expected_low[0x2E9] = 0
        allowed.add(WRAM + 0x2E9)
        # An idempotent arm may write its unchanged pending value.
        if case.expected_flags & 4 and not case.flags & 0x0B and case.item == 1:
            allowed.add(FLAGS)
    elif case.carry:
        allowed.add(FLAGS)
        if case.helper in (CAPTURE, RECLAIM):
            allowed.add(SWORD)
    after_low, after_save = (bytes(r["bytes"]) for r in result["reads"])
    require(after_save == expected_save, f"{label}: flags/Sword/save canary mismatch")
    for offset, (actual, expected) in enumerate(zip(after_low, expected_low)):
        if WRAM + offset not in range(WRAM + SP - 0x20, WRAM + SP + 1):
            require(actual == expected, f"{label}: low WRAM mismatch ${WRAM + offset:06X}")
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    require(writes <= allowed, f"{label}: undeclared writes {sorted(writes - allowed)}")
    for address, old, new in ((FLAGS, case.flags, case.expected_flags),
                              (SWORD, case.sword, case.expected_sword)):
        if old != new:
            require(address in writes, f"{label}: missing traced transaction store")
    return dict(name=label, helper=case.helper, passed=True, steps=result["steps"],
                before=dict(flags=case.flags, sword=case.sword),
                after=dict(flags=case.expected_flags, sword=case.expected_sword),
                carry=regs["p"] & 1, registers=regs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Diagnostic-enabled ROM")
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--cpu-runner", type=Path, required=True)
    parser.add_argument("--default-rom", type=Path)
    parser.add_argument("--control-rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    require(bool(args.default_rom) == bool(args.control_rom),
            "Provide both --default-rom and --control-rom, or neither")
    inputs = {args.rom: args.rom.read_bytes(), args.symbols: args.symbols.read_bytes(),
              args.cpu_runner: args.cpu_runner.read_bytes()}
    rom, sym = inputs[args.rom], inputs[args.symbols]
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            "Expected headerless LoROM <=4 MiB")
    entries = {name: symbol(sym.decode(), name) for name in (ARM, CAPTURE, RECLAIM, ESCAPE)}
    hook = (0x08 * 0x8000) + (0xC43B & 0x7FFF)
    require(rom[hook:hook + 6] == bytes([0x22]) + entries[ARM].to_bytes(3, "little") + b"\xEA\xEA",
            "Native receipt hook does not dispatch to the tested arm routine")
    default_identity = None
    if args.default_rom:
        for path in (args.default_rom, args.control_rom):
            inputs[path] = path.read_bytes()
        require(inputs[args.default_rom] == inputs[args.control_rom],
                "Diagnostic-off ROM differs from its baseline control")
        default_identity = dict(passed=True, sha256=digest(inputs[args.default_rom]),
                                bytes=len(inputs[args.default_rom]))
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                "Output path must not overwrite an input")

    plans = [(case, *fixture(case, entries[case.helper])) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-state-") as folder:
        copy = Path(folder) / "candidate.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input="".join(json.dumps(plan[3]) + "\n" for plan in plans),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Wrong number of CPU runner results")
    results = [verify(case, low, save, request, json.loads(line))
               for (case, low, save, request), line in zip(plans, lines)]
    require(all(path.read_bytes() == before for path, before in inputs.items()),
            "An input ROM, symbol file or runner changed during the test")
    result = dict(passed=True, cases=results, case_count=len(results),
                  entries={name: f"{address:06X}" for name, address in entries.items()},
                  input_sha256={str(path): digest(data) for path, data in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  default_off_identity=default_identity, runner_copy_padding_bytes=padding,
                  source_inputs_unchanged=True, stubs=[],
                  claim="Compiled D3 state/ABI proof with synthetic WRAM. No cell landing, "
                        "hall staging, boss gate, native save/reopen, or gameplay acceptance.")
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
