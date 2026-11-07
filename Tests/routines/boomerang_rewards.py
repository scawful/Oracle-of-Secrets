#!/usr/bin/env python3
"""Run compiled receipt/recovery code on the existing Yaze 65816 runner.

Private RAM fixtures; no instruction stubs or save/game writes. This is CPU/ABI
evidence, separate from native menu interaction and real Save/fresh-process load.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import tempfile

from portal_first_cast import physical, require, symbol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    image = args.rom.read_bytes()
    text = args.symbols.read_text()
    plans = []
    saved_address, size, sp = 0x7EF000, 0x500, 0x1FFF
    receipt = symbol(text, "ItemReceipt_KeepGoldstar")
    version = symbol(text, "GoldstarInventoryVersion")

    def add(name, entry, saved, expected, registers, extra=()):
        request = dict(entry=entry, reset_ram=True, registers=registers,
                       writes=[dict(address=saved_address, bytes=list(saved)), *extra],
                       reads=[dict(address=saved_address, length=size)],
                       trace_writes=True, max_steps=1000)
        plans.append((name, saved, expected, registers, request))

    for item, prior in itertools.product((0x0C, 0x2A, 0x1B, 0x1C), (0, 1, 2)):
        at = 0x341 if item in (0x0C, 0x2A) else 0x354
        incoming = 1 if item in (0x0C, 0x1B) else 2
        before = bytearray((i * 37 + 11) & 255 for i in range(size))
        before[version - saved_address] = 0xA5
        before[at] = prior
        expected = bytearray(before)
        expected[at] = (max(prior, incoming) if item in (0x0C, 0x1B)
                        and not args.control else incoming)
        regs = dict(a=0xAB00 | incoming, x=0x23, y=item, p=0x34,
                    db=9, d=0, sp=sp)
        target = saved_address + at
        add(f"receipt-{item:02X}-from-{prior}", receipt, before, expected, regs,
            [dict(address=0x7E0000, bytes=list(target.to_bytes(3, "little")))])

    if not args.control:
        entry = symbol(text, "Boomerang_RecoverLegacyReward")
        for first, second, tier, widths in itertools.product(
                (False, True), (False, True), (0, 1, 2, 255), (0, 0x10, 0x20, 0x30)):
            before = bytearray((i * 37 + 11) & 255 for i in range(size))
            before[0x82] = (before[0x82] & ~0x10) | (0x10 if first else 0)
            before[0x1D0] = (before[0x1D0] & ~0x10) | (0x10 if second else 0)
            before[0x341] = tier
            expected = bytearray(before)
            if first and second and tier < 2:
                expected[0x341] = 2
            regs = dict(a=0xAB56, x=0x23 if widths & 0x10 else 0x1234,
                        y=0x45 if widths & 0x10 else 0x5678,
                        p=0xCD | widths, db=9, d=0x120, sp=sp)
            add(f"recovery-{int(first)}{int(second)}-tier{tier}-P{regs['p']:02X}",
                entry, before, expected, regs)

    with tempfile.TemporaryDirectory(prefix="boomerang-cpu-") as folder:
        rom = Path(folder) / "candidate.sfc"
        rom.write_bytes(image + bytes([255]) * ((-len(image)) % 0x8000))
        run = subprocess.run([str(args.cpu_runner.resolve()), str(rom)],
                             input="".join(json.dumps(p[4]) + "\n" for p in plans),
                             text=True, capture_output=True, check=True, timeout=30)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), "Missing CPU results")
    results = []
    for (name, before, expected, registers, _), line in zip(plans, lines):
        result = json.loads(line)
        require(result.get("returned"), name + ": helper failed to return")
        require(not result.get("stub_calls") and not result.get("mmio_writes"),
                name + ": unexpected simulated/device path")
        require(bytes(result["reads"][0]["bytes"]) == expected,
                name + ": saved data differs from expected complete block")
        cpu = result["registers"]
        for key in ("x", "y", "d", "sp"):
            require(cpu[key] == registers[key], name + ": ABI changed " + key)
        require(cpu["db"] == registers["db"], name + ": DBR changed")
        require(cpu["p"] & 0x30 == registers["p"] & 0x30, name + ": width changed")
        if name.startswith("recovery"):
            require(cpu["a"] == registers["a"] and cpu["p"] == registers["p"],
                    name + ": full A/P not preserved")
        allowed = {saved_address + i for i, (a, b) in enumerate(zip(before, expected)) if a != b}
        allowed.update(range(0x7E0000 + sp - 16, 0x7E0000 + sp + 1))
        allowed.update(range(0x7F8000, 0x7F8004))
        # An idempotent receipt may write its existing value.
        if name.startswith("receipt"):
            allowed.add(saved_address + (0x341 if registers["y"] in (0x0C, 0x2A) else 0x354))
        for write in result.get("writes", []):
            require(physical(write["address"]) in allowed, name + ": unexpected RAM write")
        results.append(dict(name=name, passed=True, steps=result["steps"]))
    require(args.rom.read_bytes() == image, "Input ROM changed")
    print(json.dumps(dict(passed=True, control=args.control, cases=results,
                         rom_sha256=hashlib.sha256(image).hexdigest(),
                         claim="compiled CPU/ABI fixtures; not native save/reopen"), indent=2))


if __name__ == "__main__":
    main()
