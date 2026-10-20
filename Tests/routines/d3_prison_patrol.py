#!/usr/bin/env python3
"""Compiled D3 patrol scope, fixed movement and sight checks, without stubs.

Synthetic WRAM is explicit. The complete fade, room reload, art and controller
route remain native checks; this does not claim gameplay acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SAVE, SP, SWORD, WRAM, digest, physical, require, symbol

CONTEXT = "D3Prison_PatrolContext"
INIT = "D3Prison_PatrolInit"
STEP = "D3Prison_PatrolStep"
SIGHT = "D3Prison_PatrolCanSee"
CAUGHT = "D3Prison_PatrolCaught"
DISPATCH = "D3Prison_PatrolDispatch"
MAIN = "D3Prison_GuardMain"
SLOT = 7
REGIONS = ((WRAM, 0x2000), (SAVE, 0x100))


def pos(x, y):
    return {0xD10+SLOT: x & 255, 0xD30+SLOT: x >> 8,
            0xD00+SLOT: y & 255, 0xD20+SLOT: y >> 8}


def link(x, y):
    return {0x22: x & 255, 0x23: x >> 8, 0x20: y & 255, 0x21: y >> 8}


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    carry: int | None = None
    changes: dict[int, int] = field(default_factory=dict)
    expected: dict[int, int] = field(default_factory=dict)
    writes: tuple[int, ...] = ()
    p: int = 0xF5
    db: int = 0x35


def cases():
    rows = [Case("context-captured-unarmed", CONTEXT, 1),
            Case("context-preserves-owned-draw-during-menu", CONTEXT, 1,
                 changes={0x10: 0x0E}),
            Case("context-reserved-flag-retained", CONTEXT, 1,
                 changes={FLAGS: 0xA1}, p=0x34, db=0x7E)]
    for name, change in (
        ("other-room", {0xA0: 0x54}),
        ("full-room-alias", {0xA1: 1}),
        ("other-dungeon", {0x40C: 0x0A}),
        ("outdoors", {0x1B: 0}),
        ("other-sprite", {0xE20+SLOT: 0x42}),
        ("dying-sprite", {0xDD0+SLOT: 6}),
        ("not-captured", {FLAGS: 0}),
        ("pending", {FLAGS: 0x24}),
        ("reclaimed", {FLAGS: 0x29}),
        ("escaped", {FLAGS: 0x2B}),
        ("mixed-pending", {FLAGS: 0x25}),
        ("missing-backup", {FLAGS: 1}),
        ("invalid-backup", {FLAGS: 0x51}),
        ("holding-blade", {SWORD: 2}),
        ("smith-sentinel", {SWORD: 0xFF}),
    ):
        rows.append(Case("context-"+name, CONTEXT, 0, changes=change))
    for flag in (0x11, 0x41):
        rows.append(Case(f"context-valid-backup-{flag:02x}", CONTEXT, 1,
                         changes={FLAGS: flag}))

    init_fields = (0xD00, 0xE30, 0xDE0, 0xEB0,
                   0xDC0, 0xE90, 0xD80, 0xD40, 0xD50)
    for name, source, target, subtype in (
        ("upper", (0x8F0, 0xC60), (0x8F0, 0xC80), 0xE3),
        ("lower", (0x880, 0xD60), (0x880, 0xD78), 0xE4),
    ):
        expected = pos(*target)
        expected.update({0xE30+SLOT: subtype, 0xDE0+SLOT: 0,
                         0xEB0+SLOT: 0, 0xDC0+SLOT: 0x0B,
                         0xE90+SLOT: 0, 0xD80+SLOT: 0,
                         0xD40+SLOT: 0, 0xD50+SLOT: 0})
        rows.append(Case("init-"+name, INIT, 1,
                         changes={**pos(*source), 0xE30+SLOT: 0},
                         expected=expected, writes=tuple(v+SLOT for v in init_fields),
                         p=0x34 if name == "upper" else 0xF5))
    rows.extend((
        Case("init-owned-idempotent", INIT, 1),
        Case("init-lower-owned-idempotent", INIT, 1, changes={0xE30+SLOT: 0xE4}),
        Case("init-other-source-noop", INIT, 0,
             changes={**pos(0x8EF, 0xC60), 0xE30+SLOT: 0}),
        Case("init-nonzero-subtype-noop", INIT, 0,
             changes={**pos(0x8F0, 0xC60), 0xE30+SLOT: 2}),
        Case("init-high-x-alias-noop", INIT, 0,
             changes={**pos(0x9F0, 0xC60), 0xE30+SLOT: 0}),
        Case("init-high-y-alias-noop", INIT, 0,
             changes={**pos(0x8F0, 0xE60), 0xE30+SLOT: 0}),
        Case("init-outside-prison-noop", INIT, 0, changes={0xA0: 0x54}),
    ))

    step_fields = tuple(v+SLOT for v in
                        (0xD10, 0xD30, 0xDE0, 0xEB0, 0xDC0, 0xE90))
    for name, start, subtype, facing, phase, end, next_facing, next_gfx in (
        ("upper-right", 0x8F0, 0xE3, 0, 0, 0x8F1, 0, 0x0B),
        ("upper-left", 0x8F0, 0xE3, 1, 0, 0x8EF, 1, 4),
        ("upper-right-byte-carry", 0x8FF, 0xE3, 0, 7, 0x900, 0, 0x0C),
        ("upper-left-byte-borrow", 0x900, 0xE3, 1, 15, 0x8FF, 1, 6),
        ("upper-right-endpoint", 0x97F, 0xE3, 0, 0, 0x980, 1, 4),
        ("upper-left-endpoint", 0x841, 0xE3, 1, 0, 0x840, 0, 0x0B),
        ("lower-right-endpoint", 0x9AF, 0xE4, 0, 23, 0x9B0, 1, 5),
        ("lower-left-endpoint", 0x881, 0xE4, 1, 0, 0x880, 0, 0x0B),
        ("phase-wrap", 0x8F0, 0xE3, 0, 255, 0x8F1, 0, 0x0B),
    ):
        changes = {**pos(start, 0xD78 if subtype == 0xE4 else 0xC80),
                   0xE30+SLOT: subtype, 0xDE0+SLOT: facing,
                   0xEB0+SLOT: facing, 0xE90+SLOT: phase}
        expected = {0xD10+SLOT: end & 255, 0xD30+SLOT: end >> 8,
                    0xDE0+SLOT: next_facing, 0xEB0+SLOT: next_facing,
                    0xE90+SLOT: (phase+1) & 255, 0xDC0+SLOT: next_gfx}
        rows.append(Case("step-"+name, STEP, changes=changes,
                         expected=expected, writes=step_fields,
                         p=0x34 if name == "upper-left" else 0xF5))
    rows.extend((Case("step-unowned-noop", STEP, changes={0xE30+SLOT: 0}),
                 Case("step-reclaimed-noop", STEP, changes={FLAGS: 0x29}),
                 Case("caught-unowned-noop", CAUGHT, 0, changes={0xE30+SLOT: 0}),
                 Case("caught-reclaimed-noop", CAUGHT, 0, changes={FLAGS: 0x29})))
    for name, address, value in (("menu", 0x10, 0x0E),
                                 ("transition", 0x11, 2),
                                 ("link-lock", 0x2E4, 1),
                                 ("message-lock", 0xFFC, 1),
                                 ("sprite-freeze", 0xFC1, 1)):
        for helper in (STEP, SIGHT, CAUGHT):
            rows.append(Case(f"{helper.rsplit('_', 1)[-1]}-{name}-no-op", helper,
                             None if helper == STEP else 0,
                             changes={address: value}))

    for name, change, seen in (
        ("front-limit64", link(0x930, 0xC80), 1),
        ("front65-rejected", link(0x931, 0xC80), 0),
        ("behind13-rejected", link(0x8E3, 0xC80), 0),
        ("contact-behind12", link(0x8E4, 0xC80), 1),
        ("north12", link(0x920, 0xC74), 1),
        ("north13-rejected", link(0x920, 0xC73), 0),
        ("south12", link(0x920, 0xC8C), 1),
        ("south13-rejected", link(0x920, 0xC8D), 0),
        ("left-front64", {**link(0x8B0, 0xC80), 0xDE0+SLOT: 1}, 1),
        ("left-front65-rejected", {**link(0x8AF, 0xC80), 0xDE0+SLOT: 1}, 0),
        ("left-behind13-rejected", {**link(0x8FD, 0xC80), 0xDE0+SLOT: 1}, 0),
        ("left-contact-behind12", {**link(0x8FC, 0xC80), 0xDE0+SLOT: 1}, 1),
        ("minish-is-visible", {0x2B2: 5}, 1),
        ("cape-does-not-disable-sight", {0x55: 1}, 1),
        ("different-floor-rejected", {0xEE: 1}, 0),
        ("upper-soldier-across-partition", link(0x920, 0xD80), 0),
        ("lower-soldier-visible", {**pos(0x880, 0xD78),
                                    **link(0x8C0, 0xD78), 0xE30+SLOT: 0xE4}, 1),
        ("lower-soldier-across-partition", {**pos(0x880, 0xC80),
                                            **link(0x8C0, 0xC80), 0xE30+SLOT: 0xE4}, 0),
        ("right-wall-boundary", {**pos(0x9A0, 0xC80), **link(0x9D0, 0xC80)}, 0),
        ("right-floor-last-cell", {**pos(0x9A0, 0xC80), **link(0x9CF, 0xC80)}, 1),
        ("left-wall-boundary", {**pos(0x840, 0xC80), **link(0x82F, 0xC80),
                                 0xDE0+SLOT: 1}, 0),
        ("left-floor-first-cell", {**pos(0x840, 0xC80), **link(0x830, 0xC80),
                                    0xDE0+SLOT: 1}, 1),
        ("north-wall-boundary", {**pos(0x8F0, 0xC30), **link(0x920, 0xC2F)}, 0),
        ("north-floor-first-row", {**pos(0x8F0, 0xC30), **link(0x920, 0xC30)}, 1),
        ("south-wall-boundary", {**pos(0x8F0, 0xCCF), **link(0x920, 0xCD0)}, 0),
        ("south-floor-last-row", {**pos(0x8F0, 0xCCF), **link(0x920, 0xCCF)}, 1),
        ("actor-outside-chamber", {**pos(0x82F, 0xC80), **link(0x840, 0xC80)}, 0),
        ("unowned-not-detecting", {0xE30+SLOT: 0}, 0),
        ("reclaimed-not-detecting", {FLAGS: 0x29}, 0),
    ):
        rows.append(Case("sight-"+name, SIGHT, seen, changes=change,
                         p=0x34 if seen else 0xF5))
    return rows


def normalize(address):
    return address if address >= WRAM else WRAM+address


def store(blocks, address, value):
    address = normalize(address)
    for base, data in blocks.items():
        if base <= address < base+len(data):
            data[address-base] = value
            return
    raise AssertionError(f"Fixture outside inspected memory: ${address:06X}")


def fixture(case, entry):
    blocks = {base: bytearray((n*37+11) & 255 for n in range(length))
              for base, length in REGIONS}
    defaults = {0x10: 7, 0x11: 0, 0x1B: 1, 0x40C: 0x10, 0xA0: 0x64, 0xA1: 0,
                0x2E4: 0, 0xFFC: 0, 0xFC1: 0, 0xEE: 0, 0x2B2: 0, 0x55: 0,
                FLAGS: 0x21, SWORD: 0, 0xE20+SLOT: 0x41, 0xDD0+SLOT: 9,
                0xE30+SLOT: 0xE3, 0xF20+SLOT: 0, 0xDE0+SLOT: 0,
                0xEB0+SLOT: 0, 0xE90+SLOT: 0, 0xDC0+SLOT: 0x0B,
                **pos(0x8F0, 0xC80), **link(0x930, 0xC80)}
    for address, value in {**defaults, **case.changes}.items():
        store(blocks, address, value)
    registers = dict(a=0xBE9A, x=SLOT, y=0x5A, p=case.p, db=case.db, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=b, bytes=list(v)) for b, v in blocks.items()],
                   reads=[dict(address=b, length=len(v)) for b, v in blocks.items()],
                   trace_writes=True, max_steps=1600)
    return blocks, request


def verify(case, before, request, result):
    label = case.name
    require(result.get("returned"), f"{label}: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected engine stub/device access")
    regs = result["registers"]
    for key in ("x", "y", "db", "d", "sp"):
        require(regs[key] == request["registers"][key], f"{label}: ABI changed {key}")
    require(regs["e"] == 0, f"{label}: left native mode")
    expected_p = case.p if case.carry is None else (case.p & 0xFE) | case.carry
    require(regs["p"] == expected_p,
            f"{label}: P=${regs['p']:02X}, expected ${expected_p:02X}")
    expected = {b: bytearray(v) for b, v in before.items()}
    for address, value in case.expected.items():
        store(expected, address, value)
    stack = set(range(WRAM+SP-0x60, WRAM+SP+1))
    allowed = stack | set(range(0x7F8000, 0x7F8004))
    allowed.update(normalize(a) for a in case.writes)
    if case.helper == SIGHT:
        allowed.update(range(WRAM, WRAM+6))  # Must restore caller scratch below.
    require(len(result["reads"]) == len(REGIONS), f"{label}: missing WRAM reads")
    for (base, size), read in zip(REGIONS, result["reads"]):
        actual = bytes(read["bytes"])
        require(len(actual) == size, f"{label}: truncated read")
        for offset, (value, want) in enumerate(zip(actual, expected[base])):
            address = base+offset
            require(address in stack or value == want,
                    f"{label}: ${address:06X}=${value:02X}, expected ${want:02X}")
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    require(writes <= allowed, f"{label}: undeclared stores {sorted(writes-allowed)}")
    changed = {b+i for b, data in expected.items()
               for i, value in enumerate(data) if before[b][i] != value}
    require(changed <= writes, f"{label}: changed value missing traced store")
    return dict(name=label, helper=case.helper, passed=True,
                carry=regs["p"] & 1, steps=result["steps"])


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
    entries = {name: symbol(symbols, name)
               for name in (CONTEXT, INIT, STEP, SIGHT, CAUGHT, DISPATCH, MAIN)}
    pc = lambda address: (address >> 16)*0x8000 + (address & 0x7FFF)
    hook = pc(0x05C227)
    require(rom[hook:hook+4] == b"\x5C"+entries[DISPATCH].to_bytes(3, "little"),
            "Native Guard_Main prologue does not dispatch to tested patrol")
    main_code = rom[pc(entries[MAIN]):pc(entries[STEP])]
    for name in (STEP, SIGHT, CAUGHT):
        require(b"\x22"+entries[name].to_bytes(3, "little") in main_code,
                f"GuardMain does not call tested {name}")
    plans = [(case, *fixture(case, entries[case.helper])) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-patrol-") as folder:
        copy = Path(folder)/"candidate.sfc"
        copy.write_bytes(rom+b"\xFF"*padding)
        run = subprocess.run([str(args.runner), str(copy)],
                             input="".join(json.dumps(v[2])+"\n" for v in plans),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Wrong number of CPU results")
    results = [verify(case, before, request, json.loads(line))
               for (case, before, request), line in zip(plans, lines)]
    require(all(p.read_bytes() == data for p, data in inputs.items()),
            "Input changed during CPU checks")
    report = dict(passed=True, case_count=len(results), cases=results,
                  entries={name: f"{addr:06X}" for name, addr in entries.items()},
                  input_sha256={str(p): digest(data) for p, data in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  imported_helpers_sha256=digest(Path(__file__).with_name("d3_prison_state.py").read_bytes()),
                  runner_copy_padding_bytes=padding, stubs=[],
                  claim="Compiled patrol leaf CPU/ABI checks using synthetic WRAM; "
                        "not drawing, collision geometry, caught fade, or native traversal acceptance.")
    text = json.dumps(report, indent=2)+"\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
