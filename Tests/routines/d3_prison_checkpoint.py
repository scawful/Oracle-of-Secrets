#!/usr/bin/env python3
"""Execute D3 cell-resume helpers on an existing 65816 CPU runner.

Only compiled CPU/ABI behavior is checked. The entrance profile remains a
diagnostic fixture; this does not qualify cell geometry or native save/reopen.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SWORD, SP, digest, physical, require, symbol

PREDICATE = "D3Prison_ShouldResumeCell"
PROFILE = "D3Prison_ApplyCellProfile"
REGIONS = ((0x7E0000, 0x2000), (0x7EC000, 0x200), (0x7EF300, 0x100))

# Reviewed diagnostic room-$65 profile, independent of compiled instructions.
# Geometry scout corrected Y to $0D78; $0DD8 was the south wall. This literal
# contract must not be derived from the candidate it is intended to verify.
CELL_BYTES = {
    0x7E002F: 0x00, 0x7E0AA1: 0x02, 0x7E0132: 0x10, 0x7E00A4: 0x00,
    0x7E040C: 0x10, 0x7E006C: 0x00, 0x7E00EE: 0x00, 0x7E0476: 0x00,
    0x7E00A6: 0x02, 0x7E00A7: 0x00, 0x7E00A9: 0x00, 0x7E00AA: 0x02,
}
CELL_WORDS = {
    0x7E010E: 0x0032, 0x7E00A0: 0x0065, 0x7E048E: 0x0065,
    0x7E00E8: 0x0D10, 0x7E00E6: 0x0D10, 0x7E0122: 0x0D10, 0x7E0124: 0x0D10,
    0x7E00E2: 0x0A00, 0x7E00E0: 0x0A00, 0x7E011E: 0x0A00, 0x7E0120: 0x0A00,
    0x7E0020: 0x0D78, 0x7E0022: 0x0A78,
    0x7E0618: 0x0187, 0x7E061A: 0x0189, 0x7E061C: 0x007F, 0x7E061E: 0x0081,
    0x7E00EC: 0x01F8, 0x7E0696: 0x1DEE, 0x7E0698: 0x0000,
    0x7E0610: 0x0000, 0x7E0612: 0x0110, 0x7E0614: 0x0000, 0x7E0616: 0x0100,
    0x7E0600: 0x0D00, 0x7E0602: 0x0C00, 0x7E0604: 0x0D10, 0x7E0606: 0x0D10,
    0x7E0608: 0x0A00, 0x7E060A: 0x0A00, 0x7E060C: 0x0A00, 0x7E060E: 0x0B00,
    0x7E04AA: 0x0000,
}


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    flags: int
    sword: int
    applies: bool
    module: int = 0
    p: int = 0xF5
    db: int = 0x35


def cases():
    return (
        # Deliberately cold/outdoor context. Eligibility must derive from the
        # saved prison transaction, not stale room, dungeon or indoor bytes.
        Case("cold-captured", PREDICATE, 0xA1, 0, True),
        Case("reclaimed-better-sword", PREDICATE, 0xA9, 4, True, module=9, p=0x04),
        Case("backup-one-current-zero", PREDICATE, 0x11, 0, True, p=0x14),
        Case("backup-four-current-one", PREDICATE, 0x41, 1, True, p=0x24),
        Case("pending-only", PREDICATE, 0xA4, 2, False),
        Case("captured-still-pending", PREDICATE, 0xA5, 0, False),
        Case("already-escaped", PREDICATE, 0xAB, 2, False),
        Case("reclaimed-without-capture", PREDICATE, 0xA8, 2, False),
        Case("missing-backup", PREDICATE, 0x81, 0, False),
        Case("backup-out-of-range", PREDICATE, 0xD1, 0, False),
        Case("current-sword-out-of-range", PREDICATE, 0xA1, 5, False),
        Case("smith-sentinel", PREDICATE, 0xA9, 0xFF, False),
        Case("file-load-cell-profile", PROFILE, 0xA1, 0, True, module=5, p=0xE5, db=2),
        Case("file-load-reclaimed-keeps-sword", PROFILE, 0xA9, 4, True,
             module=5, p=0x24, db=2),
        Case("ordinary-module06-entrance", PROFILE, 0xA1, 0, False,
             module=6, p=0xE5, db=2),
        Case("ordinary-module07-entrance", PROFILE, 0xA1, 0, False,
             module=7, p=0x24, db=2),
        Case("file-load-escaped-unchanged", PROFILE, 0xAB, 2, False,
             module=5, p=0xE5, db=2),
        Case("file-load-invalid-unchanged", PROFILE, 0x81, 0, False,
             module=5, p=0x24, db=2),
        Case("alternate-db-cell-profile", PROFILE, 0xA1, 0, True,
             module=5, p=0x27, db=0x0F),
        Case("alternate-db-ordinary-entrance", PROFILE, 0xA1, 0, False,
             module=6, p=0x27, db=0x0F),
    )


def put(regions, address, value, width=1):
    for base, data in regions.items():
        if base <= address and address + width <= base + len(data):
            data[address - base:address - base + width] = value.to_bytes(width, "little")
            return
    raise AssertionError(f"Fixture address outside inspected regions: ${address:06X}")


def fixture(case, entry):
    regions = {base: bytearray((n * 37 + (base >> 8) + 11) & 255 for n in range(size))
               for base, size in REGIONS}
    for address, value, width in ((0x7E0010, case.module, 1), (0x7E0011, 0x17, 1),
                                  (0x7E001B, 0, 1), (0x7E00A0, 0x0154, 2),
                                  (0x7E040C, 0xFF, 1), (FLAGS, case.flags, 1),
                                  (SWORD, case.sword, 1)):
        put(regions, address, value, width)
    x, y = (0x47, 0x5A) if case.p & 0x10 else (0x0154, 0xA65A)
    registers = dict(a=0xBE11, x=x, y=y, p=case.p, db=case.db, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=base, bytes=list(data)) for base, data in regions.items()],
                   reads=[dict(address=base, length=len(data)) for base, data in regions.items()],
                   trace_writes=True, max_steps=600)
    return regions, request


def verify(case, before, request, result):
    label = case.name
    require(result.get("returned"), f"{label}: CPU failed: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected stub/device call")
    regs = result["registers"]
    for key in ("x", "y", "db", "d", "sp"):
        require(regs[key] == request["registers"][key], f"{label}: ABI changed {key}")
    require(regs["e"] == 0, f"{label}: left native CPU mode")
    expected = {base: bytearray(data) for base, data in before.items()}
    allowed = set(range(0x7E0000 + SP - 0x30, 0x7E0000 + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's real JSL trampoline.
    if case.helper == PREDICATE:
        require(regs["p"] & 0xFE == case.p & 0xFE, f"{label}: changed caller status/width")
        require(regs["p"] & 1 == int(case.applies), f"{label}: wrong eligibility Carry")
    else:
        require(regs["a"] & 255 == 0x80, f"{label}: missing original LDA #$80 result")
        require(regs["p"] == (case.p & ~0x82) | 0x80,
                f"{label}: original N/Z or other caller status not preserved")
        put(expected, 0x7E0045, 0x80)
        allowed.add(0x7E0045)
        if case.applies:
            require(CELL_BYTES and CELL_WORDS, "Cell profile expectations have not been supplied")
            for width, values in ((1, CELL_BYTES), (2, CELL_WORDS)):
                for address, value in values.items():
                    put(expected, address, value, width)
                    allowed.update(range(address, address + width))

    reads = result["reads"]
    require(len(reads) == len(REGIONS), f"{label}: missing canary region")
    for (base, size), actual in zip(REGIONS, reads):
        data = bytes(actual["bytes"])
        require(len(data) == size, f"{label}: truncated canary region ${base:06X}")
        for offset, value in enumerate(data):
            address = base + offset
            if not 0x7E0000 + SP - 0x30 <= address <= 0x7E0000 + SP:
                require(value == expected[base][offset],
                        f"{label}: ${address:06X}={value:02X}, expected {expected[base][offset]:02X}")
    writes = {physical(w["address"]) for w in result.get("writes", [])}
    require(writes <= allowed, f"{label}: undeclared writes {sorted(writes - allowed)}")
    for base, data in expected.items():
        for offset, value in enumerate(data):
            if value != before[base][offset]:
                require(base + offset in writes, f"{label}: missing traced write ${base + offset:06X}")
    return dict(name=label, passed=True, helper=case.helper, applies=case.applies,
                flags=case.flags, sword=case.sword, module=case.module,
                steps=result["steps"], registers=regs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inputs = {p: p.read_bytes() for p in (args.rom, args.symbols, args.cpu_runner)}
    rom, symbols = inputs[args.rom], inputs[args.symbols].decode()
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            "Expected headerless LoROM <=4 MiB")
    require(CELL_BYTES and CELL_WORDS, "Cell profile expectations have not been supplied")
    entries = {name: symbol(symbols, name) for name in (PREDICATE, PROFILE)}
    hook = 2 * 0x8000 + (0xDADB & 0x7FFF)
    require(rom[hook:hook + 4] == b"\x22" + entries[PROFILE].to_bytes(3, "little"),
            "Native entrance hook does not dispatch to tested cell profile")
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                "Output must not overwrite an input")
    plans = [(case, *fixture(case, entries[case.helper])) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-checkpoint-") as folder:
        copy = Path(folder) / "candidate.sfc"
        copy.write_bytes(rom + b"\xFF" * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input="".join(json.dumps(p[2]) + "\n" for p in plans),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Wrong number of CPU results")
    results = [verify(case, before, request, json.loads(line))
               for (case, before, request), line in zip(plans, lines)]
    require(all(path.read_bytes() == data for path, data in inputs.items()), "Input changed during test")
    text = json.dumps(dict(passed=True, case_count=len(results), cases=results,
                          entries={name: f"{entry:06X}" for name, entry in entries.items()},
                          input_sha256={str(p): digest(data) for p, data in inputs.items()},
                          script_sha256=digest(Path(__file__).read_bytes()),
                          imported_helpers_sha256=digest(Path(__file__).with_name("d3_prison_state.py").read_bytes()),
                          runner_copy_padding_bytes=padding, source_inputs_unchanged=True, stubs=[],
                          claim="Compiled cell eligibility/entrance-profile CPU proof only; "
                                "no native save/reopen, geometry, or gameplay acceptance."), indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
