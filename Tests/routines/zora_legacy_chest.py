#!/usr/bin/env python3
"""Check the compiled legacy Wisdom chest selector with private CPU fixtures.

The wrapper executes the real four-byte hook and following STA $0C. It stops
before vanilla's big-key check, chest update and item receipt. This checks the
selector's ABI and writes, not controller interaction or physical save proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from zora_floor_return import digest, physical, raw, require, symbol

WRAM, SP, WRAPPER, HOOK = 0x7E0000, 0x1FFF, 0x011E00, 0x01EC09
DEFAULT = dict(room=0x007A, index=0x0087, flippers=1, flippers_next=0,
               pendants=0, pendants_next=0, opened9a=0x0010, live=0, status=0x45)
CASES = (
    ("legacy-unopened-7a", {}, True),
    ("normal-wisdom-owned", dict(pendants=1), False),
    ("other-pendants-preserved", dict(pendants=6), True),
    ("wisdom-with-other-pendants", dict(pendants=7), False),
    ("no-flippers", dict(flippers=0), False),
    ("flippers-adjacent-byte-only", dict(flippers=0, flippers_next=1), False),
    ("pendants-adjacent-byte-only", dict(pendants_next=1), True),
    ("9a-unopened", dict(opened9a=0), False),
    ("9a-other-chest-bit", dict(opened9a=0x0020), False),
    ("9a-live-mask-is-wrong-saved-bit", dict(opened9a=0x0100), False),
    ("9a-doors-only", dict(opened9a=0xF000), False),
    ("9a-open-with-other-room-flags", dict(opened9a=0xF01F), True),
    ("7a-already-open-live", dict(live=0x0100), False),
    ("7a-other-live-chest-only", dict(live=0x0200), True),
    ("repeat-after-wisdom-receipt", dict(pendants=1, live=0x0100), False),
    ("room-high-byte-017a", dict(room=0x017A), False),
    ("other-room", dict(room=0x009A), False),
    ("other-table-row", dict(index=0x008A), False),
    ("table-index-high-byte", dict(index=0x0187), False),
    ("legacy-carry-overflow-clear", dict(status=0x04), True),
)


def fixture(changes, hook, rom):
    state = dict(DEFAULT, **changes)
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    for offset, value in ((0xA0, state["room"]), (0x0402, state["live"]),
                          (0xF134, state["opened9a"])):
        ram[offset:offset + 2] = value.to_bytes(2, "little")
    ram[0xF356:0xF358] = bytes((state["flippers"], state["flippers_next"]))
    ram[0xF374:0xF376] = bytes((state["pendants"], state["pendants_next"]))
    wrapper = hook + bytes.fromhex("850c6b")
    ram[WRAPPER & 0xFFFF:(WRAPPER & 0xFFFF) + len(wrapper)] = wrapper
    registers = dict(a=0xBEEF, x=state["index"], y=0, db=0, d=0,
                     sp=SP, p=state["status"])
    request = dict(entry=WRAPPER, reset_ram=True, registers=registers,
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=100)
    original = int.from_bytes(raw(rom, 0x01E970 + state["index"], 2), "little")
    return state, ram, registers, request, original


def verify(name, recover, state, before, registers, original, result):
    require(result.get("returned"), f"{name}: CPU did not return: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{name}: unexpected engine/device path")
    expected = (original & 0xFF00) | 0x38 if recover else original
    nz = (0x80 if expected & 0x8000 else 0) | (0x02 if not expected else 0)
    wanted = dict(registers, a=expected, p=(state["status"] & ~0x82) | nz, e=0)
    for key, value in wanted.items():
        require(result["registers"][key] == value,
                f"{name}: {key}={result['registers'][key]}, expected {value}")
    after = bytes(result["reads"][0]["bytes"])
    require(len(after) == len(before), f"{name}: incomplete WRAM readback")
    require(after[0x0C:0x0E] == expected.to_bytes(2, "little"),
            f"{name}: ordinary chest item word changed")
    allowed = set(range(WRAM + SP - 8, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Runner's JSL trampoline.
    allowed.update((WRAM + 0x0C, WRAM + 0x0D))
    writes = [physical(write["address"]) for write in result.get("writes", [])]
    require(not set(writes) - allowed, f"{name}: writes outside item/stack")
    require(writes.count(WRAM + 0x0C) == writes.count(WRAM + 0x0D) == 1,
            f"{name}: expected one ordinary word store")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{name}: unexpected WRAM change at {WRAM + offset:06X}")
    return dict(name=name, passed=True, recovered=recover, original=f"{original:04X}",
                selected=f"{expected:04X}", registers=result["registers"], steps=result["steps"])


def execute(args):
    rom, symbols = args.rom.read_bytes(), args.symbols.read_bytes()
    runner_hash = digest(args.cpu_runner.read_bytes())
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    text = symbols.decode()
    entry = symbol(text, "ZoraWisdom_LegacyChestItem")
    end = symbol(text, "ZoraWisdom_LegacyChestItem_End")
    require(0x2C8000 <= entry < end <= 0x2CFD00, "Selector outside bank-$2C stream")
    hook = raw(rom, HOOK, 4)
    require(hook == b"\x22" + entry.to_bytes(3, "little"), "Compiled chest JSL changed")
    require(raw(rom, HOOK + 4, 6) == bytes.fromhex("850cbf6ee901"),
            "Ordinary item store or following chest-type read changed")
    require(raw(rom, 0x01E9F5, 3) == bytes.fromhex("7a8017")
            and raw(rom, 0x01EA1C, 3) == bytes.fromhex("9a8038"),
            "Expected current chest records/rewards missing")
    require(raw(rom, 0x009900, 12) == bytes.fromhex("000100020004000800100020"),
            "Live chest-mask table changed")
    plans = [(name, recover, *fixture(changes, hook, rom)) for name, changes, recover in CASES]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="zora-legacy-chest-") as folder:
        copy = Path(folder) / "fixture.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(args.cpu_runner.resolve()), str(copy)],
                             input="".join(json.dumps(plan[-2]) + "\n" for plan in plans),
                             text=True, capture_output=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Incomplete CPU responses")
    cases = [verify(name, recover, state, before, registers, original, json.loads(line))
             for (name, recover, state, before, registers, _, original), line in zip(plans, lines)]
    require(args.rom.read_bytes() == rom and args.symbols.read_bytes() == symbols,
            "Input ROM/symbols changed during check")
    require(digest(args.cpu_runner.read_bytes()) == runner_hash, "CPU runner changed")
    return dict(passed=True, cases=cases, rom_sha256=digest(rom),
                symbols_sha256=digest(symbols), runner_sha256=runner_hash,
                script_sha256=digest(Path(__file__).read_bytes()),
                helper=f"{entry:06X}", helper_end=f"{end:06X}", hook=hook.hex(),
                runner_copy_padding_bytes=padding, source_inputs_unchanged=True,
                claim="Compiled selector and ordinary item-store ABI/write boundary; "
                      "no native chest, item receipt or physical save/reopen proof")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for source in (args.rom, args.symbols, args.cpu_runner, Path(__file__)):
        same_path = args.output.resolve() == source.resolve()
        same_file = args.output.exists() and source.exists() and args.output.samefile(source)
        if same_path or same_file:
            parser.error("--output must not alias an input or this script")
    try:
        result = execute(args)
    except Exception as exc:
        result = dict(passed=False, error=repr(exc))
    text = json.dumps(result, indent=2) + "\n"
    args.output.write_text(text)
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
