#!/usr/bin/env python3
"""Execute compiled ferry admission, cancellation and handoff contracts.

Uses the maintained 65816 CPU runner. Loader, stripe, animation and Link OAM
callees are explicit test doubles where selected. This is CPU/state evidence;
the actual map loader, graphics, collision and controller journey need native
qualification on the same candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

WRAM = 0x7E0000
STATE = 0x7FF380
MAGIC = 0xB047


def require(value, message):
    if not value:
        raise AssertionError(message)


def labels(text):
    result = {}
    for bank, offset, name in re.findall(
            r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)\s*$", text, re.M):
        result[name.removeprefix("Oracle_")] = int(bank + offset, 16)
    return result


def put(data, offset, value, size=1):
    data[offset:offset + size] = value.to_bytes(size, "little")


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def fixture(area=0x30, x=0x300, y=0xD70):
    ram = bytearray(0x2000)
    put(ram, 0x10, 0x09 if area < 0x80 else 0x0B)
    put(ram, 0x8A, area, 2)
    put(ram, 0x20, y, 2)
    put(ram, 0x22, x, 2)
    put(ram, 0x2F, 4)  # boarding faces opposite the arrival facing
    put(ram, 0x13, 15)
    put(ram, 0xF6, 0x80)
    put(ram, 0x708, y & 0xFE00, 2)
    put(ram, 0x70A, 0x1F0, 2)
    put(ram, 0x70C, (x & 0xFE00) >> 3, 2)
    put(ram, 0x70E, 0x7E, 2)
    return ram, bytearray(0x20)


def request(entry, ram, state, *, stubs=(), registers=None):
    regs = dict(a=0xABCD, x=0x13, y=0x97, p=0x30, db=2, d=0, sp=0x1FFF)
    regs.update(registers or {})
    return dict(entry=entry, reset_ram=True, registers=regs,
                writes=[dict(address=WRAM, bytes=list(ram)),
                        dict(address=STATE, bytes=list(state))],
                reads=[dict(address=WRAM, length=len(ram)),
                       dict(address=STATE, length=len(state))],
                stubs=list(stubs), trace_writes=True, max_steps=3000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--symbols", required=True, type=Path)
    parser.add_argument("--cpu-runner", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sym = labels(args.symbols.read_text())
    cases = []

    def add(name, entry, ram, state, check, **kwargs):
        cases.append((name, request(sym[entry], ram, state, **kwargs), check))

    def admission(accepted):
        def check(result, ram, state):
            require(bool(result["registers"]["p"] & 1) == accepted, "admission carry")
            require(ram[0x10] == (0x0C if accepted else 0x09), "module")
            require(word(state, 0) == (MAGIC if accepted else 0), "ownership marker")
            for name, value in dict(x=0x13, y=0x97, db=2, d=0, sp=0x1FFF).items():
                require(result["registers"][name] == value, "gate ABI " + name)
            require(result["registers"]["p"] & 0x30 == 0x30, "gate widths")
        return check

    for name, x, y, accepted in (
            ("docks-exact", 0x300, 0xD70, True),
            ("docks-left-window", 0x2F9, 0xD70, True),
            ("docks-right-window", 0x307, 0xD70, True),
            ("outside-left-window", 0x2F8, 0xD70, False),
            ("outside-right-window", 0x308, 0xD70, False),
            ("outside-y-window", 0x300, 0xD78, False)):
        ram, state = fixture(x=x, y=y)
        add(name, "Boat_BoardGate", ram, state, admission(accepted))
    for name, address, value in (
            ("no-new-A", 0xF6, 0), ("wrong-facing", 0x2F, 6),
            ("unrelated-map", 0x8A, 0x31), ("indoors", 0x1B, 1),
            ("swimming", 0x5D, 4), ("carrying", 0x308, 1),
            ("hidden-player", 0x4B, 12), ("overlay-active", 0x4C6, 1),
            ("control-lock", 0x2E4, 1)):
        ram, state = fixture()
        put(ram, address, value)
        add(name, "Boat_BoardGate", ram, state, admission(False))

    # Exercise the actual patched near caller as well as its long callee.
    # Literal BCS $02A570 assembles as raw displacement $70 in Asar; a
    # symbolic target must emit $2E and land on the native bank-$02 RTS.
    ram, state = fixture()
    ram[0x1E00:0x1E04] = bytes.fromhex("203CA56B")
    cases.append(("patched-native-caller-returns", request(
        0x021E00, ram, state), admission(True)))

    ram, state = fixture(area=0x98, x=0xC0, y=0x7B0)

    def island(result, ram, state):
        require(ram[0x10] == 0x0C and word(state, 0) == MAGIC, "island admission")
        require(state[3] == 2, "island endpoint")
    add("island-return-admission", "Boat_BoardGate", ram, state, island)

    render = dict(address=0x0DA18E, return_="rtl")
    render["return"] = render.pop("return_")
    stripe = dict(address=0x1BC97C, **{"return": "rtl"})
    animate = dict(address=0x07E6A6, **{"return": "rtl"})

    def scene(phase, endpoint=0):
        ram, state = fixture()
        put(ram, 0x10, 0x0C)
        put(state, 0, MAGIC, 2)
        put(state, 2, phase)
        put(state, 3, endpoint)
        put(state, 6, 9)
        put(state, 8, 0xD70, 2)
        put(state, 10, 0x300, 2)
        put(state, 12, 0x100, 2)
        put(state, 14, 0xFC0, 2)
        put(state, 19, 4)
        return ram, state

    ram, state = scene(1)

    def boarding(result, ram, state):
        require(word(ram, 0x22) == 0x2FF, "one-pixel boarding movement")
        require(word(state, 4) == 1 and state[2] == 1, "boarding timer")
    add("boarding-step", "Boat_Module", ram, state, boarding, stubs=[render, animate])

    ram, state = scene(1)
    put(state, 4, 11, 2)

    def closed(result, ram, state):
        require(state[2] == 2 and state[7] == 1, "plank closes before fade")
        call = next(c for c in result["stub_calls"] if c["address"] == 0x1BC97C)
        require(call["registers"]["a"] == 0x2CD, "docks closed tile")
        require(call["registers"]["x"] == 0x100, "exact plank offset")
    add("bounded-plank-event", "Boat_Module", ram, state, closed, stubs=[render, stripe])

    for phase in (1, 2):
        ram, state = scene(phase)
        put(ram, 0xF4, 0x80)
        put(ram, 0x22, 0x2F4, 2)
        put(state, 7, int(phase == 2))

        def cancelled(result, ram, state):
            require(ram[0x10] == 9 and ram[0x13] == 15, "cancel restores control/display")
            require(word(ram, 0x22) == 0x300 and word(ram, 0x20) == 0xD70,
                    "cancel restores pre-boarding position")
            require(word(state, 0) == 0, "cancel releases ownership")
        add("cancel-phase-" + str(phase), "Boat_Module", ram, state, cancelled,
            stubs=[render, stripe])

    ram, state = scene(2)
    put(ram, 0x13, 0)

    def crossing(result, ram, state):
        require(word(ram, 0xA0) == 0x186 and state[2] == 3, "exit key selected")
        require(ram[0x13] == 0x80 and ram[0x11] == 0, "blanked ordinary-load setup")
    add("departure-selects-existing-exit", "Boat_Module", ram, state, crossing, stubs=[render])

    ram, state = scene(3)
    put(state, 16, 191, 2)
    loader = dict(address=0x0283BF, **{"return": "rtl"},
                  writes=[dict(address=WRAM + 0x10, bytes=[8])])

    def timeout(result, ram, state):
        require(ram[0x10] == 8 and word(ram, 0xA0) == 0x187, "timeout reloads source")
        require(word(state, 0) == 0 and ram[0x11] == 0, "timeout leaves no scene lock")
    add("loader-timeout-recovers-source", "Boat_Module", ram, state, timeout, stubs=[loader])

    for area, module in ((0x30, 9), (0x98, 11)):
        ram, state = scene(4)
        put(ram, 0x8A, area)

        def arrived(result, ram, state, module=module):
            require(ram[0x10] == module and ram[0x11] == 0, "arrival restores module")
            require(word(state, 0) == 0, "arrival releases scene")
        add(f"arrival-{area:02X}", "Boat_Module", ram, state, arrived, stubs=[render])

    for p in (0, 0x10, 0x20, 0x30):
        ram, state = scene(3)

        def reset(result, ram, state, p=p):
            require(word(state, 0) == 0, "file load cancels ownership")
            for key, value in dict(a=0xABCD, x=0x13, y=0x97, p=p, db=2, d=0,
                                   sp=0x1FFF).items():
                require(result["registers"][key] == value, "reset ABI " + key)
        add(f"file-reset-width-{p:02X}", "Boat_ResetSession", ram, state, reset,
            registers=dict(p=p))

    run = subprocess.run([str(args.cpu_runner), str(args.rom)],
                         input="".join(json.dumps(c[1]) + "\n" for c in cases),
                         capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(cases), "CPU response count")
    records = []
    failure = None
    for (name, req, check), line in zip(cases, lines):
        result = json.loads(line)
        try:
            require(result.get("returned"), str(result.get("error", result)))
            ram, state = (bytes(r["bytes"]) for r in result["reads"])
            check(result, ram, state)
            records.append(dict(name=name, passed=True, steps=result["steps"]))
        except AssertionError as error:
            records.append(dict(name=name, passed=False, error=str(error), result=result))
            failure = failure or name + ": " + str(error)
    report = dict(passed=failure is None, selected=len(cases),
                  passed_count=sum(r["passed"] for r in records),
                  failed_count=sum(not r["passed"] for r in records), skipped=0,
                  rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest(),
                  symbols_sha256=hashlib.sha256(args.symbols.read_bytes()).hexdigest(),
                  runner_sha256=hashlib.sha256(args.cpu_runner.read_bytes()).hexdigest(),
                  claim="compiled CPU contracts; explicit engine test doubles, no native journey claim",
                  cases=records)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}))
    require(failure is None, failure)


if __name__ == "__main__":
    main()
