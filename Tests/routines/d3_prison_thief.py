#!/usr/bin/env python3
"""Compiled prison-thief predicates and staging; synthetic WRAM, no stubs.

Positive staging is compared with the real native sprite preparation routine.
Rendering, dialogue delivery and controller reachability remain native checks.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SAVE, SP, SWORD, WRAM, digest, physical, require, symbol

ELIGIBLE = "D3Prison_ThiefEligible"
TALK = "D3Prison_ThiefCanTalk"
STAGE_ELIGIBLE = "D3Prison_ThiefStageEligible"
STAGE = "D3Prison_ThiefStage"
NATIVE_PREP = 0x0DB818
REGIONS = ((WRAM, 0x2000), (SAVE, 0x100), (0x7FF980, 0x100))
STACK = set(range(WRAM+SP-0x80, WRAM+SP+1))
TRAMPOLINE = set(range(0x7F8000, 0x7F8004))


def word(address, value):
    return {address: value & 255, address+1: value >> 8}


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    carry: int | None = None
    changes: dict[int, int] = field(default_factory=dict)
    spawn: int | None = None
    p: int = 0xF5
    db: int = 0x35


def cases():
    rows = [Case("eligible-captured", ELIGIBLE, 1, p=0x34),
            Case("eligible-reserved-flag", ELIGIBLE, 1, changes={FLAGS: 0xA1}),
            Case("eligible-backup-one", ELIGIBLE, 1, changes={FLAGS: 0x11}),
            Case("eligible-backup-four", ELIGIBLE, 1, changes={FLAGS: 0x41})]
    for name, changes in (
        ("wrong-room", {0xA0: 0x64}), ("wrong-room-page", {0xA1: 1}),
        ("wrong-dungeon", {0x40C: 0x0A}), ("outdoors", {0x1B: 0}),
        ("not-captured", {FLAGS: 0}), ("pending", {FLAGS: 0x24}),
        ("mixed-pending", {FLAGS: 0x25}), ("reclaimed", {FLAGS: 0x29}),
        ("escaped", {FLAGS: 0x2B}), ("missing-backup", {FLAGS: 1}),
        ("invalid-backup", {FLAGS: 0x51}), ("has-sword", {SWORD: 2}),
        ("smith-sentinel", {SWORD: 0xFF}),
    ):
        rows.append(Case("eligible-"+name, ELIGIBLE, 0, changes=changes))
    rows.extend((Case("stage-uses-loading-room", STAGE_ELIGIBLE, 1,
                      changes={0xA0: 0x64, 0xA1: 1}, p=0x34),
                 Case("stage-wrong-loading-room", STAGE_ELIGIBLE, 0,
                      changes={0x48E: 0x64}),
                 Case("stage-loading-room-page", STAGE_ELIGIBLE, 0,
                      changes={0x48F: 1})))

    for name, changes, allowed in (
        ("near-center", {}, 1),
        ("left-bound", word(0x22, 0xAE0), 1),
        ("left-outside", word(0x22, 0xADF), 0),
        ("right-bound", word(0x22, 0xAE8), 1),
        ("right-outside", word(0x22, 0xAE9), 0),
        ("north-bound", word(0x20, 0xD48), 1),
        ("north-outside", word(0x20, 0xD47), 0),
        ("south-bound", word(0x20, 0xD58), 1),
        ("south-outside", word(0x20, 0xD59), 0),
        ("wrong-x-page", word(0x22, 0xBE4), 0),
        ("wrong-y-page", word(0x20, 0xE50), 0),
        ("old-talk-position", {**word(0x22, 0xAA8), **word(0x20, 0xD78)}, 0),
        ("wake-position", {**word(0x22, 0xAD0), **word(0x20, 0xD58)}, 0),
        ("south-bars", word(0x20, 0xD68), 0),
        ("thief-cell", {**word(0x22, 0xB50), **word(0x20, 0xD58)}, 0),
        ("face-up", {0x2F: 0}, 0),
        ("face-left", {0x2F: 4}, 0),
        ("different-floor", {0xEE: 1}, 0),
        ("minish", {0x2B2: 5}, 0),
        ("other-transformation", {0x2B2: 1}, 0),
        ("link-not-normal", {0x5D: 1}, 0),
        ("menu", {0x10: 0x0E}, 0),
        ("transition", {0x11: 2}, 0),
        ("link-locked", {0x2E4: 1}, 0),
        ("message-locked", {0xFFC: 1}, 0),
        ("sprite-frozen", {0xFC1: 1}, 0),
        ("no-new-A", {0xF6: 0}, 0),
        ("other-new-button", {0xF6: 0x40}, 0),
        ("native-busy-recoil", {0x4D: 1}, 0),
        ("native-busy-item", {0x2DA: 1}, 0),
        ("native-busy-carry", {0x308: 0x80}, 0),
        ("native-busy-ancilla27-first", {0xC4A: 0x27}, 0),
        ("native-busy-ancilla27-last", {0xC4E: 0x27}, 0),
        ("unrelated-ancilla", {0xC4C: 5}, 1),
        ("reclaimed", {FLAGS: 0x29}, 0),
        ("escaped", {FLAGS: 0x2B}, 0),
    ):
        rows.append(Case("talk-"+name, TALK, allowed, changes=changes,
                         p=0x34 if allowed else 0xF5))

    # Keep several ordinary actors alive; the highest free slot wins and the
    # native allocator's $02 and other slots must remain exactly unchanged.
    rows.extend((
        Case("stage-highest-free-slot", STAGE, spawn=15,
             changes={0xDD0+5: 0, 0xDD0+15: 0}),
        Case("stage-single-free-slot", STAGE, spawn=5, p=0x34,
             changes={0xDD0+5: 0}),
        Case("stage-full-noop", STAGE),
        Case("stage-duplicate-noop", STAGE,
             changes={0xDD0+15: 0, 0xE20+12: 0xC4, 0xE30+12: 0xD3, 0xDA0+12: 0x65}),
        Case("stage-reclaimed-noop", STAGE, changes={FLAGS: 0x29, 0xDD0+15: 0}),
        Case("stage-wrong-room-noop", STAGE, changes={0x48E: 0x64, 0xDD0+15: 0}),
    ))
    return rows


def address(value):
    return value if value >= WRAM else WRAM+value


def store(blocks, location, value):
    location = address(location)
    for base, data in blocks.items():
        if base <= location < base+len(data):
            data[location-base] = value
            return
    raise AssertionError(f"Outside inspected memory ${location:06X}")


def fixture(case, entry, native=False):
    blocks = {base: bytearray((i*37+11) & 255 for i in range(size))
              for base, size in REGIONS}
    defaults = {0x10: 7, 0x11: 0, 0x1B: 1, 0x40C: 0x10,
                **word(0xA0, 0x65), **word(0x48E, 0x65),
                **word(0x22, 0xAE4), **word(0x20, 0xD50),
                0xEE: 0, 0x2F: 6, 0x2B2: 0, 0x5D: 0, 0xF6: 0x80,
                0x2E4: 0, 0xFFC: 0, 0xFC1: 0,
                0x4D: 0, 0x2DA: 0, 0x308: 0, FLAGS: 0x21, SWORD: 0}
    defaults.update({0xC4A+i: 0 for i in range(5)})
    for slot in range(16):
        defaults.update({0xDD0+slot: 9, 0xE20+slot: 0x41,
                         0xE30+slot: 0, 0xDA0+slot: 0})
    for location, value in {**defaults, **case.changes}.items():
        store(blocks, location, value)
    if native:
        require(case.spawn is not None, "Native control needs selected spawn slot")
        store(blocks, 0xE20+case.spawn, 0xC4)
    registers = dict(a=0xBE9A, x=case.spawn if native else 7, y=0x5A,
                     p=case.p, db=0 if native else case.db, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=b, bytes=list(v)) for b, v in blocks.items()],
                   reads=[dict(address=b, length=len(v)) for b, v in blocks.items()],
                   trace_writes=True, max_steps=2400)
    return blocks, request


def inspect(result, label):
    require(result.get("returned"), f"{label}: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: engine stub or MMIO access")
    require(len(result["reads"]) == len(REGIONS), f"{label}: missing memory reads")
    data = {}
    for (base, size), read in zip(REGIONS, result["reads"]):
        values = bytes(read["bytes"])
        require(len(values) == size, f"{label}: truncated memory read")
        data[base] = bytearray(values)
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    return data, writes


def verify(case, before, request, result, native=None):
    label = case.name
    actual, writes = inspect(result, label)
    regs = result["registers"]
    for key in ("x", "y", "db", "d", "sp"):
        require(regs[key] == request["registers"][key], f"{label}: ABI changed {key}")
    require(regs["e"] == 0, f"{label}: left native mode")
    p = case.p if case.carry is None else (case.p & 0xFE) | case.carry
    require(regs["p"] == p, f"{label}: P=${regs['p']:02X} expected ${p:02X}")
    if case.helper == STAGE:
        require(regs["a"] == request["registers"]["a"], f"{label}: stage changed full A")
    expected = {b: bytearray(v) for b, v in before.items()}
    allowed = STACK | TRAMPOLINE
    if native is not None:
        require(case.spawn is not None, "Unexpected native control")
        expected, native_writes = inspect(native, label+"/native-prep")
        slot = case.spawn
        # Vanilla reset/property writes, independently bounded to this one
        # actor. Compare native values rather than copying ROM data tables.
        prep_offsets = (0xF00, 0xE90, 0xD50, 0xD40, 0xF80, 0xD70, 0xD60,
                        0xF90, 0xD80, 0xDC0, 0xDE0, 0xDF0, 0xE00, 0xE10,
                        0xF10, 0xEB0, 0xEC0, 0xED0, 0xEF0, 0xE70, 0xF70,
                        0xE50, 0xEA0, 0xF40, 0xF30, 0xD90, 0xDA0, 0xDB0,
                        0xBB0, 0xE80, 0xBA0, 0xB89, 0xF50, 0xB58, 0xCE2,
                        0xE40, 0xF60, 0xBE0, 0xCAA, 0xCD2, 0xE60, 0xC9A, 0xB6B)
        prep_allowed = {WRAM+off+slot for off in prep_offsets}
        prep_allowed.update(base+slot for base in
                            (0x7FF9C2, 0x7FFA1C, 0x7FFA2C, 0x7FFA3C, 0x7FFA4C))
        require(native_writes <= allowed | prep_allowed,
                f"{label}: unexpected native prep writes {sorted(native_writes-allowed-prep_allowed)}")
        fields = {0xE20: 0xC4, 0xDD0: 9, 0xE30: 0xD3, 0xDA0: 0x65,
                  0xD10: 0x50, 0xD30: 0x0B, 0xD00: 0x58, 0xD20: 0x0D,
                  0xF20: 0, 0xF60: 0x40, 0xBA0: 1, 0xBC0: 0xFF,
                  0xCBA: 0, 0xF50: 0x0F, 0xDC0: 2, 0xEB0: 1, 0xDE0: 1,
                  0xD40: 0, 0xD50: 0}
        for offset, value in fields.items():
            store(expected, offset+slot, value)
        allowed |= prep_allowed | {WRAM+off+slot for off in fields}
    for base, values in expected.items():
        for offset, (value, want) in enumerate(zip(actual[base], values)):
            location = base+offset
            require(location in STACK or value == want,
                    f"{label}: ${location:06X}=${value:02X}, expected ${want:02X}")
    require(writes <= allowed, f"{label}: undeclared writes {sorted(writes-allowed)}")
    changed = {base+i for base, values in expected.items()
               for i, value in enumerate(values)
               if before[base][i] != value and base+i not in STACK}
    require(changed <= writes, f"{label}: missing traced stores")
    return dict(name=label, helper=case.helper, passed=True, steps=result["steps"],
                native_control_steps=native["steps"] if native else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--runner", "--cpu-runner", dest="runner", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inputs = {p: p.read_bytes() for p in (args.rom, args.symbols, args.runner)}
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                "Output must not overwrite input")
    rom, symbols = inputs[args.rom], inputs[args.symbols].decode()
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            "Expected headerless LoROM <=4 MiB")
    entries = {name: symbol(symbols, name) for name in (ELIGIBLE, TALK, STAGE_ELIGIBLE, STAGE)}
    dispatch = symbol(symbols, "D3Prison_ThiefDispatch")
    hook = (0x1D*0x8000)+(0xC8D8 & 0x7FFF)
    require(rom[hook:hook+4] == b"\x5C"+dispatch.to_bytes(3, "little"),
            "Native thief entry does not dispatch to the tested implementation")
    plans, requests = [], []
    for case in cases():
        before, request = fixture(case, entries[case.helper])
        index = len(requests); requests.append(request)
        if case.spawn is not None:
            _, control = fixture(case, NATIVE_PREP, native=True)
            requests.append(control)
        plans.append((case, before, request, index))
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-thief-") as folder:
        copy = Path(folder)/"candidate.sfc"; copy.write_bytes(rom+b"\xFF"*padding)
        run = subprocess.run([str(args.runner), str(copy)],
                             input="".join(json.dumps(r)+"\n" for r in requests),
                             capture_output=True, text=True, timeout=30, check=True)
    results = [json.loads(line) for line in run.stdout.splitlines()]
    require(len(results) == len(requests), "Wrong number of CPU results")
    checks = [verify(case, before, request, results[index],
                     results[index+1] if case.spawn is not None else None)
              for case, before, request, index in plans]
    require(all(p.read_bytes() == data for p, data in inputs.items()), "Input changed during test")
    report = dict(passed=True, case_count=len(checks), cpu_executions=len(results), cases=checks,
                  input_sha256={str(p): digest(data) for p, data in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  imported_helpers_sha256=digest(Path(__file__).with_name("d3_prison_state.py").read_bytes()),
                  entries={name: f"{value:06X}" for name, value in entries.items()},
                  runner_copy_padding_bytes=padding, stubs=[],
                  claim="Compiled thief predicates and actual native-prep staging comparison; "
                        "synthetic WRAM, not drawing, message delivery or native reachability.")
    text = json.dumps(report, indent=2)+"\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
