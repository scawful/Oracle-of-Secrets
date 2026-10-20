#!/usr/bin/env python3
"""Compiled D3 message setup and one-shot delivery; synthetic WRAM, no stubs.

Calls the actual native minimal-message routine. This does not render text,
advance its close animation, or prove a controller-driven capture/exit scene.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SWORD, SP, digest, physical, require, symbol
from d3_prison_hall import put

CAPTURE = "D3Prison_ShowCaptureTaunt"
EXIT = "D3Prison_TryExitMessage"
PENDING, MARKER = 0x7FF368, 0xD355
REGIONS = ((0x7E0000, 0x2000), (0x7EF300, 0x100), (0x7FF340, 0x40))
STACK = set(range(0x7E0000 + SP - 0x80, 0x7E0000 + SP + 1))
TRAMPOLINE = set(range(0x7F8000, 0x7F8004))


@dataclass(frozen=True)
class Case:
    name: str
    helper: str = EXIT
    outcome: str = "show"  # show, wait, cancel, absent
    p: int = 0xF5
    slot: int = 5
    changes: dict[int, tuple[int, int]] = field(default_factory=dict)


def cases():
    rows = []
    # Both helpers promise the full A (including hidden B), X/Y and M/X ABI.
    for p in (0x05, 0x15, 0x25, 0x34):
        rows.append(Case(f"capture-widths-{p:02x}", CAPTURE, p=p,
                         slot=15 if p == 0x34 else 5))
        rows.append(Case(f"exit-widths-{p:02x}", p=p,
                         changes={SWORD: (4 if p == 0x34 else 2, 1)}))
    for name, changes in (
        ("wrong-module", {0x7E0010: (7, 1)}),
        ("indoors", {0x7E001B: (1, 1)}),
        ("wrong-room", {0x7E00A0: (0x54, 2)}),
        ("room-page-alias", {0x7E00A0: (0x155, 2)}),
        ("missing-capture", {FLAGS: (0xAA, 1)}),
        ("pending-state", {FLAGS: (0xAF, 1)}),
        ("not-escaped", {FLAGS: (0xA9, 1)}),
        ("first-sword", {SWORD: (1, 1)}),
        ("invalid-sword", {SWORD: (5, 1)}),
        ("smith-sword", {SWORD: (0xFF, 1)}),
    ):
        rows.append(Case("exit-cancels-" + name, outcome="cancel", changes=changes))
    for name, address in (("transition", 0x7E0011), ("link-action", 0x7E005D),
                          ("link-lock", 0x7E02E4), ("scene-lock", 0x7E0FFC),
                          ("sprite-freeze", 0x7E0FC1)):
        rows.append(Case("exit-waits-" + name, outcome="wait",
                         changes={address: (1, 1)}))
    rows.extend((Case("exit-absent", outcome="absent", changes={PENDING: (0, 2)}),
                 Case("exit-unknown-marker", outcome="absent",
                      changes={PENDING: (0xD354, 2)})))
    return rows


def fixture(case, entry, seed=None):
    blocks = ({b: bytearray(v) for b, v in seed.items()} if seed is not None else
              {b: bytearray((i * 37 + 11) & 255 for i in range(n)) for b, n in REGIONS})
    defaults = {0x7E0010: (7 if case.helper == CAPTURE else 9, 1),
                0x7E0011: (0, 1), 0x7E001B: (0, 1),
                0x7E00A0: (0x55, 2), FLAGS: (0xAB, 1), SWORD: (2, 1),
                0x7E0022: (0x0958, 2), 0x7E0020: (0x0638, 2),
                0x7E005D: (0, 1), 0x7E02E4: (0, 1),
                0x7E0FFC: (0, 1), 0x7E0FC1: (0, 1), PENDING: (MARKER, 2)}
    if seed is not None:
        # Model only native close restoring 09/00. Keep actual consumed marker,
        # message ID, caches and all other first-call outputs for repeat proof.
        defaults = {0x7E0010: (9, 1), 0x7E0011: (0, 1)}
    for address, (value, width) in (defaults | case.changes).items():
        put(blocks, address, value, width)
    registers = dict(a=0xBE11, x=case.slot,
                     y=0x5A if case.p & 0x10 else 0xB65A,
                     p=case.p, db=0x35, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=b, bytes=list(v)) for b, v in blocks.items()],
                   reads=[dict(address=b, length=len(v)) for b, v in blocks.items()],
                   trace_writes=True, max_steps=700)
    return blocks, request


def verify(case, before, request, result):
    label = case.name
    require(result.get("returned"), f"{label}: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected stub or device access")
    regs = result["registers"]
    for key in ("a", "x", "y", "db", "d", "sp"):
        require(regs[key] == request["registers"][key], f"{label}: ABI changed {key}")
    require(regs["e"] == 0, f"{label}: left native mode")
    show = case.outcome == "show"
    p = case.p if case.helper == CAPTURE else (case.p & 0xFE) | int(show)
    require(regs["p"] == p, f"{label}: P=${regs['p']:02X}, expected ${p:02X}")
    expected = {b: bytearray(v) for b, v in before.items()}
    allowed = STACK | TRAMPOLINE

    def change(address, value, width=1):
        put(expected, address, value, width)
        allowed.update(range(address, address + width))

    if case.helper == EXIT and case.outcome in ("show", "cancel"):
        change(PENDING, 0, 2)
    if show:
        if case.helper == CAPTURE:
            change(0x7E0F80 + case.slot, 0xC1)
        message = 0x1CC if case.helper == CAPTURE else 0x1D1
        change(0x7E1CF0, message, 2)
        # Independent expected effects of real Sprite_ShowMessageMinimal.
        change(0x7E0223, 0); change(0x7E1CD8, 0)
        change(0x7E010C, before[0x7E0000][0x10])
        change(0x7E0010, 0x0E); change(0x7E0011, 2)
        for source, target in ((0x22, 0x7E0FC2), (0x20, 0x7E0FC4)):
            change(target, int.from_bytes(before[0x7E0000][source:source+2], "little"), 2)
    require(len(result["reads"]) == len(REGIONS), f"{label}: missing memory region")
    actual = {}
    for (base, size), read in zip(REGIONS, result["reads"]):
        data = bytearray(read["bytes"])
        require(len(data) == size, f"{label}: truncated memory region")
        actual[base] = data
        for offset, (got, want) in enumerate(zip(data, expected[base])):
            address = base + offset
            require(address in STACK or got == want,
                    f"{label}: ${address:06X}=${got:02X}, expected ${want:02X}")
    trace = [(physical(w["address"]), w["value"]) for w in result.get("writes", [])]
    writes = {address for address, _ in trace}
    require(writes <= allowed, f"{label}: undeclared writes {sorted(writes - allowed)}")
    changed = {b+i for b, data in expected.items() for i, value in enumerate(data)
               if b+i not in STACK and value != before[b][i]}
    require(changed <= writes, f"{label}: missing expected stores")
    if show and case.helper == EXIT:
        # Consume before entering text; a later reentrant tick cannot duplicate it.
        consumed = [i for i, (address, value) in enumerate(trace)
                    if address in (PENDING, PENDING+1) and value == 0]
        opened = [i for i, (address, value) in enumerate(trace)
                  if address == 0x7E0010 and value == 0x0E]
        require(len(consumed) == 2 and len(opened) == 1 and max(consumed) < opened[0],
                f"{label}: pending message not consumed before text opens")
    return dict(name=label, helper=case.helper, passed=True, steps=result["steps"]), actual


def run(runner, rom, plans):
    result = subprocess.run([str(runner), str(rom)],
                            input="".join(json.dumps(p[2])+"\n" for p in plans),
                            capture_output=True, text=True, timeout=30)
    require(result.returncode == 0,
            f"CPU runner exited {result.returncode}: {result.stderr.strip()}")
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    require(len(rows) == len(plans), "Wrong CPU result count")
    return [verify(case, before, request, row)
            for (case, before, request), row in zip(plans, rows)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inputs = {p: p.read_bytes() for p in (args.rom, args.symbols, args.cpu_runner)}
    rom, symbols = inputs[args.rom], inputs[args.symbols].decode()
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            "Expected headerless LoROM <=4MiB")
    entries = {name: symbol(symbols, name) for name in (CAPTURE, EXIT)}
    native_pc = 5*0x8000 + (0xFA8E & 0x7FFF)
    require(rom[native_pc:native_pc+20] == bytes.fromhex(
        "9c23029cd81ca9028511a5108d0c01a90e85106b"),
        "Native Sprite_ShowMessageMinimal differs from inspected instructions")
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                "Output overwrites input")
    plans = [(case, *fixture(case, entries[case.helper])) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-dialogue-") as folder:
        copy = Path(folder)/"candidate.sfc"; copy.write_bytes(rom + b"\xFF" * padding)
        checked = run(args.cpu_runner, copy, plans)
        first_index = next(i for i, (case, _, _) in enumerate(plans) if case.helper == EXIT)
        repeat = replace(plans[first_index][0], name="exit-not-repeated-after-close",
                         outcome="absent", changes={})
        repeated = (repeat, *fixture(repeat, entries[EXIT], checked[first_index][1]))
        checked.extend(run(args.cpu_runner, copy, [repeated]))
    require(all(p.read_bytes() == data for p, data in inputs.items()), "Input changed")
    rows = [row for row, _ in checked]
    report = dict(passed=True, case_count=len(rows), cases=rows, stubs=[],
                  entries={n: f"{a:06X}" for n, a in entries.items()},
                  input_sha256={str(p): digest(v) for p, v in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  runner_copy_padding_bytes=padding, source_inputs_unchanged=True,
                  claim="Compiled message setup, cancellation, wait, once-only and ABI proof; "
                        "synthetic WRAM, actual native minimal-message routine, no stubs. "
                        "Text rendering, close animation and native scenes require separate checks.")
    text = json.dumps(report, indent=2)+"\n"
    if args.output: args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
