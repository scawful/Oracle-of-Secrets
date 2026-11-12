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

# Ages beat (Items/switch_hook.asm): cling 17, rise 16, swap 1, fall 16.
CLING, RISE = 17, 16
SWAP = CLING + RISE + 1
LAND = SWAP + 16
LINK_STATE_HOOK = 0x13
# Swappable types (Items/switch_hook.asm SwitchHook_Targets): ice, statue, diamond.
TARGETS = (0xD5, 0x1C, 0x8E)


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
                room=word(0x7E00A0), module=read8(0x7E0010), submodule=read8(0x7E0011),
                camera=(word(0x7E00E2), word(0x7E00E8)),
                selected=read8(0x7E0202), effective=read8(0x7E0304),
                owned=read8(0x7EF3AE), mask=read8(0x7E02B2),
                active=read8(0x7E07F8), drag=read8(0x7E037E),
                ancilla=[read8(0x7E0C4A + index) for index in range(5)],
                beat=read8(0x7E0268), z=word(0x7E0024), target_height=read8(0x7E0F70 + slot),
                link_state=read8(0x7E005D), unhittable=read8(0x7E037B),
                plate=read8(0x7E0642), gbc=read8(0x7E0FFF), facing=read8(0x7E002F))


def check_minish(snap):
    """Every frame must show Minish Cap Link: no GBC form, no mask form 6."""
    require(snap["gbc"] == 0, "GBC Link form ($0FFF) in a non-Abyss capture")
    require(snap["mask"] != 6, "Mask form 6 in a Minish Cap Link capture")


def check_exchange(before, after, camera_may_move=False):
    """Full 16-bit positions are compared; a low-byte-only swap must fail.

    camera_may_move: the Ages beat steps the camera toward Link after landing.
    The settle itself is checked by check_beat() and the caller's idle frames."""
    require(before["type"] in TARGETS and before["type"] == after["type"],
            "Exchange changed/wrong sprite type")
    require(before["state"] == after["state"] == 9, "Exchange target is not a live block")
    require(before["floor"] == before["layer"], "Fixture is on a different layer")
    require(after["link"] == (before["block"][0], (before["block"][1] - 8) & 0xFFFF),
            "Link did not receive the complete block position/standing offset")
    require(after["block"] == (before["link"][0], (before["link"][1] + 8) & 0xFFFF),
            "Block did not receive the complete Link position/standing offset")
    names = ["room", "module", "layer", "floor", "slot", "block_origin",
             "selected", "effective", "owned", "mask"]
    if not camera_may_move:
        names.append("camera")
    for name in names:
        require(before[name] == after[name], f"Exchange unexpectedly changed {name}")
    require(after["active"] == 0, "Exchange left its shot latch active")
    require(after["drag"] == 0, "Exchange left a vanilla hookshot pull active")
    require(0x1F not in after["ancilla"], "Exchange left a hookshot ancilla behind")


def check_beat(before, trace):
    """Ages order: positions hold through cling+rise, swap at the peak, then fall
    and camera settle; Link stays in the hook state and unhittable throughout."""
    beat = [snap for snap in trace if snap["beat"]]
    require(bool(beat), "No swap beat frames traced")
    # In-room plate/shutter/peg submodules ($11 = $05/$16/$17) hold the beat.
    held = [snap for snap in beat if snap.get("submodule", 0)]
    require(all(snap["submodule"] in (0x05, 0x16, 0x17) for snap in held),
            "Beat survived a transition submodule")
    # A lag frame during the camera scroll samples one counter twice and then
    # skips one (0 then 2); only that balanced pair is allowed.
    lag = 0
    for prev, snap in zip(beat, beat[1:]):
        step = snap["beat"] - prev["beat"]
        if snap.get("submodule", 0):
            require(step == 0, "Beat counter advanced during a held submodule")
        elif step == 0 and not lag:
            lag = 1
        else:
            require(step == 1 + lag, "Beat counter did not advance one step per running frame")
            lag = 0
    require(not lag, "Beat counter stalled at the end of the trace")
    counters = [snap["beat"] for snap in beat]
    require(counters[-1] >= LAND, "Beat ended before the landing frame")
    for snap in beat:
        require(snap["link_state"] == LINK_STATE_HOOK, "Control returned during the beat")
        require(snap["unhittable"] == 1, "Link became hittable during the beat")
        # Cling frames keep vanilla grounded Z ($FFFF); heights start at CLING+1.
        require(snap["target_height"] == (snap["z"] & 0xFF) or snap["beat"] <= CLING,
                "Target and Link heights differ during rise/fall")
        if snap["beat"] < SWAP:
            require(snap["link"] == before["link"] and snap["block"] == before["block"],
                    "Positions changed before the swap frame")
        else:
            require(snap["link"] != before["link"], "Positions not exchanged after the swap frame")
    peak = max(snap["z"] for snap in beat if snap["beat"] > CLING)
    require(peak == RISE, f"Rise peak {peak} != {RISE}")
    require(beat[-1]["z"] == 0 and beat[-1]["target_height"] == 0, "Beat ended in the air")
    settle = [snap for snap in beat if snap["beat"] > LAND]
    for prev, snap in zip(settle, settle[1:]):
        require(prev["camera"] != snap["camera"] or snap is settle[-1],
                "Beat held control after the camera stopped")
    return dict(frames=len(beat), held_frames=len(held), peak=peak, settle_frames=len(settle),
                swap_beat=SWAP, land_beat=LAND, last_beat=counters[-1])


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
    moved = copy.deepcopy(after)
    moved["camera"] = (0x10, 0)
    check_exchange(before, moved, camera_may_move=True)
    trace = []
    for counter in range(1, LAND + 3):
        z = min(counter - CLING, RISE) if counter > CLING else 0xFFFF
        if counter > SWAP:
            z = max(0, LAND - counter)
        frame = copy.deepcopy(before if counter < SWAP else after)
        frame.update(beat=counter, z=z, target_height=z, link_state=LINK_STATE_HOOK, unhittable=1,
                     camera=(counter - LAND if counter > LAND else 0, 0))
        trace.append(frame)
    check_beat(before, trace)
    paused = copy.deepcopy(trace)
    stall = copy.deepcopy(paused[SWAP])
    stall["submodule"] = 0x17
    paused.insert(SWAP + 1, stall)
    require(check_beat(before, paused)["held_frames"] == 1, "Plate pause frame not counted")
    stall = copy.deepcopy(stall)
    stall["submodule"] = 0x02
    paused[SWAP + 1] = stall
    try:
        check_beat(before, paused)
    except AssertionError:
        pass
    else:
        raise AssertionError("Beat check accepted a transition submodule")
    lagged = copy.deepcopy(trace)
    lagged[SWAP + 2]["beat"] -= 1
    check_beat(before, lagged)
    skipped = copy.deepcopy(trace)
    del skipped[SWAP + 2]
    try:
        check_beat(before, skipped)
    except AssertionError:
        pass
    else:
        raise AssertionError("Beat check accepted a skipped counter")
    for key, value in (("z", 3), ("unhittable", 0), ("link_state", 0)):
        bad = copy.deepcopy(trace)
        bad[CLING + 8][key] = value
        try:
            check_beat(before, bad)
        except AssertionError:
            failures += 1
    require(failures == 8, "Beat assertions missed a bad trace")
    check_minish(before)
    try:
        check_minish(dict(before, gbc=1))
    except AssertionError:
        pass
    else:
        raise AssertionError("Minish check accepted GBC Link")
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
