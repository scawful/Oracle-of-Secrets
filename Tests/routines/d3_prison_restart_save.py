#!/usr/bin/env python3
"""Compare the D3 pre-save wrapper against real native death cleanup.

Executes $0BFFBF and the compiled wrapper on matching synthetic WRAM. No engine
routines are stubbed. This is CPU/ABI proof, not native saving or file-reopen
acceptance; actual SRAM serialization is outside this routine's boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_checkpoint import Case, REGIONS, fixture
from d3_prison_state import FLAGS, SWORD, SP, digest, physical, require, symbol

WRAPPER = "D3Prison_RestartBeforeSave"
NATIVE = 0x0BFFBF
HOOK = 0x09F540


def cases():
    return (
        Case("captured-already-unarmed", WRAPPER, 0x21, 0, True,
             module=0x12, p=0x35, db=0, saved_after=(0x21, 0)),
        Case("reclaimed-resets-before-save", WRAPPER, 0xA9, 2, True,
             module=0x17, p=0xF4, db=0, saved_after=(0xA1, 0)),
        Case("escaped-keeps-blade", WRAPPER, 0xAB, 2, False,
             module=0x17, p=0x35, db=0),
        Case("pending-does-not-reset", WRAPPER, 0xA4, 2, False,
             module=0x12, p=0xF4, db=0),
        Case("smith-sentinel-unchanged", WRAPPER, 0xA9, 0xFF, False,
             module=0x17, p=0x35, db=0),
        Case("ordinary-save-unchanged", WRAPPER, 0x80, 2, False,
             module=0x17, p=0xF4, db=0),
    )


def inspected(result, label):
    require(result.get("returned"), f"{label}: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected engine stub/device access")
    require(len(result["reads"]) == len(REGIONS), f"{label}: missing canary region")
    data = {}
    for (base, size), read in zip(REGIONS, result["reads"]):
        values = bytes(read["bytes"])
        require(len(values) == size, f"{label}: truncated region ${base:06X}")
        data.update((base + offset, value) for offset, value in enumerate(values))
    return data


def verify(case, request, direct, wrapped):
    label = case.name
    native_data = inspected(direct, label + "/native")
    wrapper_data = inspected(wrapped, label + "/wrapper")
    # Native cleanup itself changes X/Y/A/P. Match its actual return, not the
    # incoming registers; include the hidden accumulator high byte in A.
    for key in ("a", "x", "y", "p", "db", "d", "sp", "e"):
        require(wrapped["registers"][key] == direct["registers"][key],
                f"{label}: native return changed {key}")
    require(direct["registers"]["e"] == 0 and
            direct["registers"]["sp"] == request["registers"]["sp"],
            f"{label}: native cleanup did not return with balanced stack")
    require(native_data[FLAGS] == case.flags and native_data[SWORD] == case.sword,
            f"{label}: native control unexpectedly changed prison ownership")
    # $005E consumes incoming A before cleanup. This catches wrappers that
    # clobber A with their eligibility/reset logic before replaying native code.
    for suffix, result in (("native", direct), ("wrapper", wrapped)):
        stores = [v["value"] for v in result.get("writes", [])
                  if physical(v["address"]) == 0x7E005E]
        require(stores and stores[0] == request["registers"]["a"] & 0xFF,
                f"{label}/{suffix}: incoming A did not reach the first $005E store")
    expected = dict(native_data)
    if case.saved_after is not None:
        expected[FLAGS], expected[SWORD] = case.saved_after
    stack = set(range(0x7E0000 + SP - 0x40, 0x7E0000 + SP + 1))
    trampoline = set(range(0x7F8000, 0x7F8004))
    for address, actual in wrapper_data.items():
        if address not in stack:
            require(actual == expected[address],
                    f"{label}: ${address:06X}={actual:02X}, expected {expected[address]:02X}")
    native_writes = {physical(v["address"]) for v in direct.get("writes", [])}
    wrapper_writes = {physical(v["address"]) for v in wrapped.get("writes", [])}
    require(native_writes <= set(native_data) | stack | trampoline,
            f"{label}: native control wrote outside inspected memory")
    delta = {FLAGS, SWORD} if case.applies else set()
    require(wrapper_writes - stack - trampoline == (native_writes | delta) - stack - trampoline,
            f"{label}: cleanup/restart write set changed unexpectedly")
    return dict(name=label, passed=True, flags_before=case.flags,
                flags_after=wrapper_data[FLAGS], sword_before=case.sword,
                sword_after=wrapper_data[SWORD], registers=wrapped["registers"],
                native_steps=direct["steps"], wrapper_steps=wrapped["steps"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inputs = {p: p.read_bytes() for p in (args.rom, args.symbols, args.cpu_runner)}
    rom = inputs[args.rom]
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            "Expected headerless LoROM <=4 MiB")
    entry = symbol(inputs[args.symbols].decode(), WRAPPER)
    offset = (HOOK >> 16) * 0x8000 + (HOOK & 0x7FFF)
    require(rom[offset:offset + 4] == b"\x22" + entry.to_bytes(3, "little"),
            "Accepted-choice save hook does not dispatch to tested wrapper")
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                "Output must not overwrite an input")
    plans = []
    for case in cases():
        _, direct = fixture(case, NATIVE)
        _, wrapped = fixture(case, entry)
        for request in (direct, wrapped):
            # Native cleanup visits six ancilla slots and all Link reset fields.
            # No active carry/crystal case is needed to test the wrapper seam.
            low = request["writes"][0]["bytes"]
            low[0xC4A:0xC50] = [0] * 6
            low[0x308] = 0
            low[0x2EC] = 0
            request["max_steps"] = 1200
        plans.append((case, direct, wrapped))
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="d3-restart-save-") as folder:
        copy = Path(folder) / "candidate.sfc"
        copy.write_bytes(rom + b"\xFF" * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input="".join(json.dumps(request) + "\n"
                                           for _, direct, wrapped in plans
                                           for request in (direct, wrapped)),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == 2 * len(plans), "Wrong number of CPU runner results")
    results = [verify(case, direct_request, json.loads(lines[2*n]), json.loads(lines[2*n+1]))
               for n, (case, direct_request, _) in enumerate(plans)]
    require(all(path.read_bytes() == data for path, data in inputs.items()),
            "Input changed during CPU check")
    output = dict(passed=True, case_count=len(results), cpu_executions=len(lines),
                  cases=results, entries={WRAPPER: f"{entry:06X}", "native": f"{NATIVE:06X}"},
                  input_sha256={str(p): digest(data) for p, data in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  imported_helpers_sha256={name: digest(Path(__file__).with_name(name).read_bytes())
                                           for name in ("d3_prison_checkpoint.py", "d3_prison_state.py")},
                  runner_copy_padding_bytes=padding, stubs=[],
                  claim="Real native cleanup versus D3 pre-save wrapper CPU/ABI comparison; "
                        "synthetic WRAM, no SRAM serialization or native save/reopen acceptance.")
    text = json.dumps(output, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
