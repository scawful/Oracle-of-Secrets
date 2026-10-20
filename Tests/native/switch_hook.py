#!/usr/bin/env python3
"""Reusable assertions for the combined items native scenario; never launches Mesen.

The caller owns a paused private emulator and its declared ice-block/inventory
fixtures. Pass a byte reader to snapshot(), drive real Y input, and compare the
result with check_exchange() or check_rejected(). --self-test checks only these
assertion helpers, not the ROM or gameplay implementation.
"""
from __future__ import annotations

import argparse
import copy
import json


def require(value, message):
    if not value:
        raise AssertionError(message)


def snapshot(read8, slot):
    require(0 <= slot < 16, "Ice-block fixture slot outside 0..15")

    def word(address):
        return read8(address) | read8(address + 1) << 8

    def sprite_word(low, high):
        return read8(0x7E0000 + low + slot) | read8(0x7E0000 + high + slot) << 8

    return dict(link=(word(0x7E0022), word(0x7E0020)),
                block=(sprite_word(0xD10, 0xD30), sprite_word(0xD00, 0xD20)),
                block_origin=(sprite_word(0xE90, 0xEC0), sprite_word(0xEB0, 0xED0)),
                slot=slot, type=read8(0x7E0E20 + slot), state=read8(0x7E0DD0 + slot),
                floor=read8(0x7E0F20 + slot), layer=read8(0x7E00EE),
                room=word(0x7E00A0), module=read8(0x7E0010),
                camera=(word(0x7E00E2), word(0x7E00E8)),
                selected=read8(0x7E0202), effective=read8(0x7E0304),
                owned=read8(0x7EF3AE), mask=read8(0x7E02B2),
                active=read8(0x7E07F8), drag=read8(0x7E037E),
                ancilla=[read8(0x7E0C4A + index) for index in range(5)])


def check_exchange(before, after):
    """Full 16-bit positions are compared; a low-byte-only swap must fail."""
    require(before["type"] == after["type"] == 0xD5, "Exchange changed/wrong sprite type")
    require(before["state"] == after["state"] == 9, "Exchange target is not a live block")
    require(before["floor"] == before["layer"], "Fixture is on a different layer")
    require(after["link"] == (before["block"][0], (before["block"][1] - 8) & 0xFFFF),
            "Link did not receive the complete block position/standing offset")
    require(after["block"] == (before["link"][0], (before["link"][1] + 8) & 0xFFFF),
            "Block did not receive the complete Link position/standing offset")
    for name in ("room", "module", "layer", "floor", "camera", "slot", "block_origin",
                 "selected", "effective", "owned", "mask"):
        require(before[name] == after[name], f"Exchange unexpectedly changed {name}")
    require(after["active"] == 0, "Exchange left its shot latch active")
    require(after["drag"] == 0, "Exchange left a vanilla hookshot pull active")
    require(0x1F not in after["ancilla"], "Exchange left a hookshot ancilla behind")


def check_rejected(before, after):
    for name in ("link", "block", "block_origin", "room", "module", "layer", "floor",
                 "camera", "slot", "type", "state", "owned", "mask"):
        require(before[name] == after[name], f"Rejected target changed {name}")
    require(after["drag"] == 0, "Rejected target started a vanilla hookshot pull")


def describe():
    return dict(native_executed=False,
                required_cases=[
                    "Real Y cast, exchange stationary D5, walk away, cast back",
                    "Four launch directions; full-word X/Y across a page where view permits",
                    "Reject moving/airborne D5, other sprite IDs and opposite layer",
                    "Reject wall/pit/water under any of nine sampled landing/source cells",
                    "Wall hit retracts; ordinary Hookshot still pulls and Goldstar still rotates",
                    "Mask effective-action change and room transition delete only owned chain",
                ],
                fixture_contract={"inventory": {"7EF3AE": 1}, "target": "live stationary D5",
                                  "native_input": "Y; never call the swap routine in lieu of a cast",
                                  "floor": "read-only verified footprint on both ends",
                                  "no_sram_or_rom_writes": True})


def self_test():
    memory = {0x7E0022: 0xF0, 0x7E0023: 0x0A,
              0x7E0020: 0xF8, 0x7E0021: 0x0B,
              0x7E0D10: 0x08, 0x7E0D30: 0x0B,
              0x7E0D00: 0x18, 0x7E0D20: 0x0C,
              0x7E0E20: 0xD5, 0x7E0DD0: 9, 0x7EF3AE: 1,
              0x7E0202: 0x1D, 0x7E0304: 0x0E, 0x7E0010: 7}
    before = snapshot(lambda address: memory.get(address, 0), 0)
    require(before["link"] == (0x0AF0, 0x0BF8), "Reader dropped Link high bytes")
    require(before["block"] == (0x0B08, 0x0C18), "Reader dropped block high bytes")
    after = copy.deepcopy(before)
    after.update(link=(0x0B08, 0x0C10), block=(0x0AF0, 0x0C00))
    check_exchange(before, after)
    failures = 0
    for key, value in (("link", (0x0A08, 0x0B10)), ("block", (0x0BF0, 0x0C00)),
                       ("drag", 1), ("active", 0xA5), ("camera", (1, 0))):
        broken = copy.deepcopy(after)
        broken[key] = value
        try:
            check_exchange(before, broken)
        except AssertionError:
            failures += 1
    require(failures == 5, "Native exchange assertions missed a bad result")
    check_rejected(before, before)
    try:
        check_rejected(before, after)
    except AssertionError:
        return {"helper_self_test": "passed", "native_executed": False,
                "bad_exchange_results_rejected": failures, "unexpected_warp_rejected": True}
    raise AssertionError("Rejection assertions accepted a position exchange")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    print(json.dumps(self_test() if args.self_test else describe(), indent=2))
