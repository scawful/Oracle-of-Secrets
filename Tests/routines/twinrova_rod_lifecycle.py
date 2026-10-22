#!/usr/bin/env python3
"""Check compiled Twinrova rod setters and native-death cleanup on Yaze's CPU.

Each real ROM RTS helper runs through a same-bank low-WRAM JSR/RTL wrapper.
Private full-WRAM fixtures cover both phase-two rod rows and slots 0/15. Two
actual mode prefixes, copied only through the first engine-call boundary, check
that the visible frame changes with its rod row despite a live animation timer.
The native explosion/prize dispatcher stays byte-identical; the compiled Long
must call cleanup after Draw/Shadow and before CheckActive. No engine stubs,
synthetic CPU, native fight, rendered art, or prize acceptance is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM, SP, WRAPPER = 0x7E0000, 0x1FFF, 0x1E00
ROD_OFFSETS = (0x16CEB, 0x16CEC)
RESTORE = "Twinrova_RestoreRodDamageOnDeath"
SETTERS = {
    "Twinrova_RodDamageDefault": (0, 0),
    "Twinrova_RodDamageKoume": (0, 1),
    "Twinrova_RodDamageKotake": (1, 0),
}
MODES = {
    "Twinrova_KoumeMode": ("Twinrova_RodDamageKoume", "GetRandomInt", 8),
    "Twinrova_KotakeMode": ("Twinrova_RodDamageKotake", "Sprite_IsBelowPlayer", 9),
}
RUNNER_SHA = "c0df7c7ef5a501ae1f8318aa618564becd11282d200e37c6f92a373cb29e1535"
MAX_STEPS = 100
NATIVE_RANGES = (
    ("state-dispatch", 0x0684E2, 46,
     "8f77735cf571f11f1d9a8737249f3b62f45b5dbe55fe3c78aff6d6a4d070a325"),
    ("native-boss-death", 0x06F057, 29,
     "53428ac76d1a5750ce234dbb68f39427aa0662afd3632ae6853a76ca8ab8d079"),
    ("native-explosion-and-prize", 0x09ED9F, 439,
     "dc0d524520c970bd4ecf69c26812f4853932b44f5658c0964e55265381654473"),
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
    require(address & 0xFFFF >= 0x8000, f"Expected LoROM code: {address:06X}")
    offset = ((address >> 16) & 127) * 0x8000 + (address & 0x7FFF)
    data = rom[offset:offset + size]
    require(len(data) == size, f"ROM range missing: {address:06X}/{size}")
    return data


def jsr(address):
    return b"\x20" + (address & 0xFFFF).to_bytes(2, "little")


def jsl(address):
    return b"\x22" + address.to_bytes(3, "little")


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 127) < 0x40 and offset < 0x2000,
            f"Unexpected non-WRAM write: {address:06X}")
    return WRAM + offset


def contracts(rom, symbols):
    names = (RESTORE, *SETTERS, *MODES, "GetRandomInt", "Sprite_IsBelowPlayer",
             "Sprite_Twinrova_Long", "Sprite_Twinrova_Draw", "Sprite_DrawShadow",
             "Sprite_CheckActive", "Twinrova_Initialize")
    labels = {name: symbol(symbols, name) for name in names}
    bank = labels[RESTORE] >> 16
    require(bank < 0x40 and all(labels[name] >> 16 == bank
            for name in (RESTORE, *SETTERS, *MODES,
                         "Sprite_Twinrova_Long", "Sprite_Twinrova_Draw")),
            "Twinrova's local JSR helpers must share a low-WRAM-mirrored bank")
    expected_restore = (bytes.fromhex("BDD00DC904D003")
                        + jsr(labels["Twinrova_RodDamageDefault"]) + b"\x60")
    require(raw(rom, labels[RESTORE], len(expected_restore)) == expected_restore,
            "Compiled cleanup must check indexed state04 then call the default setter")
    for name, pair in SETTERS.items():
        expected = (b"\xA9" + bytes((pair[0],)) + bytes.fromhex("8FEB6C7F")
                    + b"\xA9" + bytes((pair[1],)) + bytes.fromhex("8FEC6C7F60"))
        require(raw(rom, labels[name], len(expected)) == expected,
                f"Compiled two-byte rod setter differs: {name}")
    prefix = (bytes.fromhex("8B4BAB") + jsr(labels["Sprite_Twinrova_Draw"])
              + jsl(labels["Sprite_DrawShadow"]) + jsr(labels[RESTORE])
              + jsl(labels["Sprite_CheckActive"]))
    require(raw(rom, labels["Sprite_Twinrova_Long"], len(prefix)) == prefix,
            "Compiled Long must retain Draw/Shadow -> cleanup -> CheckActive order")
    init_size = labels[RESTORE] - labels["Twinrova_Initialize"]
    require(0 < init_size <= 128 and raw(rom, labels["Twinrova_Initialize"], init_size)
            .endswith(jsr(labels["Twinrova_RodDamageDefault"]) + b"\x60"),
            "Shared Initialize must restore the loaded rod defaults")
    mode_prefixes = {}
    for name, (setter, engine, frame) in MODES.items():
        block = raw(rom, labels[name], 64)
        boundary = block.find(jsl(labels[engine]))
        require(0 < boundary < 64, f"Missing first engine-call boundary: {name}")
        copied = block[:boundary]
        require(copied.startswith(b"\xA9" + bytes((frame,)) + bytes.fromhex("9D900D"))
                and copied.endswith(jsr(labels[setter])),
                f"{name}: compiled prefix must fix its frame before setting its rod row")
        mode_prefixes[name] = copied
    native = []
    for name, address, size, sha in NATIVE_RANGES:
        require(digest(raw(rom, address, size)) == sha,
                f"Native pipeline changed: {name} at {address:06X}")
        native.append(dict(name=name, address=f"{address:06X}", size=size, sha256=sha))
    for address, expected in (
        (0x068548, bytes.fromhex("229FED0960")),
        (0x068526, bytes.fromhex("8B4BAB207192AB6B")),
        (0x069271, bytes.fromhex("BD200EC23029FF000AA8B983923A48E23060")),
        (0x06941F, bytes.fromhex("F8FF")),
    ):
        require(raw(rom, address, len(expected)) == expected,
                f"Native explosion-to-custom-Long route changed at {address:06X}")
    return labels, prefix, native, mode_prefixes


def cases():
    result = []
    for slot in (0, 15):
        for pair in ((0, 1), (1, 0)):
            suffix = f"slot{slot}-{pair[0]}{pair[1]}"
            result.append(dict(name="native-death-" + suffix, routine=RESTORE,
                               slot=slot, state=4, before=pair, after=(0, 0), rod_writes=1))
            for routine, expected in SETTERS.items():
                result.append(dict(name=routine + "-" + suffix, routine=routine,
                                   slot=slot, state=9, before=pair, after=expected, rod_writes=1))
        for state in (0, 6, 8, 9):
            pair = (slot & 1, 1 - (slot & 1))
            result.append(dict(name=f"state{state:02X}-control-slot{slot}", routine=RESTORE,
                               slot=slot, state=state, before=pair, after=pair, rod_writes=0))
    for name, slot, old_frame, old_pair in (
        ("Twinrova_KoumeMode", 0, 9, (1, 0)),
        ("Twinrova_KotakeMode", 15, 8, (0, 1)),
    ):
        setter, _, frame = MODES[name]
        result.append(dict(name=f"{name}-frame{old_frame}-to-{frame}-timer7", routine=name,
                           slot=slot, state=9, before=old_pair, after=SETTERS[setter],
                           rod_writes=1, frame_before=old_frame, frame_after=frame, timer_b=7))
    return result


def fixture(labels, mode_prefixes, case):
    entry = labels[case["routine"]]
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    ram[0xDD0:0xDE0] = bytes([4 if case["state"] != 4 else 9]) * 16
    ram[0xDD0 + case["slot"]] = case["state"]
    for offset, value in zip(ROD_OFFSETS, case["before"]):
        ram[offset] = value
    if case["routine"] in mode_prefixes:
        ram[0xD90 + case["slot"]] = case["frame_before"]
        ram[0xE00 + case["slot"]] = case["timer_b"]
        ram[0xD80 + case["slot"]] = case["frame_after"]
        code = mode_prefixes[case["routine"]] + b"\x6B"
    else:
        code = jsr(entry) + b"\x6B"
    ram[WRAPPER:WRAPPER + len(code)] = code
    initial = dict(a=0xBEA6, x=case["slot"], y=0x5B, p=0x75,
                   db=entry >> 16, d=0x0120, sp=SP)
    request = dict(entry=(entry & 0xFF0000) | WRAPPER, reset_ram=True,
                   registers=initial,
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=MAX_STEPS)
    return ram, initial, request


def verify(case, before, initial, result):
    name = case["name"]
    require(result.get("returned"), f"{name}: CPU did not return: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{name}: unexpected simulated engine/device path")
    require(0 < result["steps"] <= MAX_STEPS, f"{name}: instruction bound exceeded")
    regs = result["registers"]
    for key in ("x", "y", "db", "d", "sp"):
        require(regs[key] == initial[key],
                f"{name}: ABI {key}={regs[key]}, expected {initial[key]}")
    require(regs["e"] == 0 and regs["p"] & 0x30 == 0x30,
            f"{name}: native M8/X8 mode changed")
    require(regs["p"] & ~0x83 == initial["p"] & ~0x83,
            f"{name}: flags outside A/CMP NZC changed")
    low_a = case["after"][1] if case["rod_writes"] else case["state"]
    require(regs["a"] == 0xBE00 | low_a, f"{name}: A width/result differs")
    after = bytes(result["reads"][0]["bytes"])
    require(len(after) == len(before), f"{name}: incomplete full-WRAM readback")
    pair = tuple(after[offset] for offset in ROD_OFFSETS)
    require(pair == case["after"], f"{name}: rod row {pair}, expected {case['after']}")
    # Runner JSL + wrapper JSR + optional cleanup->default JSR: at most seven bytes.
    depth = 7 if case["routine"] == RESTORE and case["state"] == 4 else 5
    allowed = set(range(WRAM + SP - depth + 1, WRAM + SP + 1))
    allowed.update(range(0x7F8000, 0x7F8004))  # Existing runner's real JSL trampoline.
    if case["rod_writes"]:
        allowed.update(WRAM + offset for offset in ROD_OFFSETS)
    if "frame_after" in case:
        frame_at, timer_at = 0xD90 + case["slot"], 0xE00 + case["slot"]
        require(after[frame_at] == case["frame_after"] and after[timer_at] == case["timer_b"],
                f"{name}: mode frame/timer no longer matches its selected rod row")
        allowed.add(WRAM + frame_at)
    writes = [physical(write["address"]) for write in result.get("writes", [])]
    require(set(writes) <= allowed,
            f"{name}: unexpected writes {sorted(set(writes) - allowed)}")
    for offset in ROD_OFFSETS:
        count = writes.count(WRAM + offset)
        require(count == case["rod_writes"],
                f"{name}: rod write count {WRAM + offset:06X}={count}")
    if "frame_after" in case:
        require(writes.count(WRAM + frame_at) == 1 and WRAM + timer_at not in writes,
                f"{name}: expected one frame write and no live-timer write")
    for offset, (old, new) in enumerate(zip(before, after)):
        require(old == new or WRAM + offset in allowed,
                f"{name}: unexpected WRAM change {WRAM + offset:06X}: {old:02X}->{new:02X}")
    return dict(name=name, passed=True, routine=case["routine"], slot=case["slot"],
                state=f"{case['state']:02X}", before=list(case["before"]), after=list(pair),
                frame_before=case.get("frame_before"), frame_after=case.get("frame_after"),
                timer_b=case.get("timer_b"),
                rod_write_count_each=case["rod_writes"], registers=regs,
                steps=result["steps"], writes=result.get("writes", []),
                full_wram_sha256_before=digest(before), full_wram_sha256_after=digest(after))


def execute(args):
    rom, symbols = args.rom.read_bytes(), args.symbols.read_bytes()
    runner_hash = digest(args.cpu_runner.read_bytes())
    require(runner_hash == RUNNER_SHA, "Use the existing Zora35 Yaze CPU runner")
    require(0 < len(rom) <= 0x400000, "Expected headerless LoROM <=4MiB")
    labels, prefix, native, mode_prefixes = contracts(rom, symbols.decode())
    plans = [(case, *fixture(labels, mode_prefixes, case)) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix="twinrova-rod-lifecycle-") as folder:
        copy = Path(folder) / "fixture.sfc"
        copy.write_bytes(rom + bytes([255]) * padding)
        run = subprocess.run([str(args.cpu_runner.resolve()), str(copy)],
                             input="".join(json.dumps(request) + "\n"
                                           for _, _, _, request in plans),
                             text=True, capture_output=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), f"Expected {len(plans)} CPU responses, got {len(lines)}")
    results = [verify(case, before, initial, json.loads(line))
               for (case, before, initial, _), line in zip(plans, lines)]
    require(args.rom.read_bytes() == rom and args.symbols.read_bytes() == symbols,
            "Input ROM/symbols changed during the check")
    require(digest(args.cpu_runner.read_bytes()) == runner_hash, "Existing CPU runner changed")
    return dict(passed=True, cases=results, rom_sha256=digest(rom),
                symbols_sha256=digest(symbols), runner_sha256=runner_hash,
                script_sha256=digest(Path(__file__).read_bytes()),
                helpers={name: f"{labels[name]:06X}" for name in (RESTORE, *SETTERS)},
                compiled_long_prefix=prefix.hex(), native_pipeline=native,
                mode_prefixes={name: dict(source=f"{labels[name]:06X}", bytes=code.hex(),
                    stop_before=f"{labels[name] + len(code):06X}",
                    excluded_engine_call=MODES[name][1]) for name, code in mode_prefixes.items()},
                wrapper_offset=f"{WRAPPER:04X}", stubs=[], source_inputs_unchanged=True,
                runner_copy_padding_bytes=padding,
                claim="Actual compiled helpers on Yaze CPU with private WRAM fixtures; "
                      "native dispatcher bytes and Long call order checked; "
                      "no native fight, rendered-art, prize, save, or earned-route acceptance")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "symbols", "cpu-runner", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(args)
    except Exception as exc:
        result = dict(passed=False, error=repr(exc),
                      script_sha256=digest(Path(__file__).read_bytes()))
    text = json.dumps(result, indent=2) + "\n"
    args.output.write_text(text)
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
