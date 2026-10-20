#!/usr/bin/env python3
"""Equipment menu selection sound queue, observed natively per input window.

run(active, output_path, expected_sound) drives the real controller route
START -> Items, L -> Equipment, then D-pad navigation, mask A, ring A wear,
stationary ring A unwear, song Y and START close. Each tap is one window with
its own write watch on 7E012F (SFX3 queue); the watch log keeps every write
and its PC, so NMI's later clear of the port cannot hide the queued ID.
expected_sound is 0x20 (candidate) or 0x22 (control build). Unwear and cursor
movement must queue 0x20 in both builds.

`active` is the caller's admitted, already paused cold House (room 0104)
session: .b (MesenBridge), .step(frames, buttons=''), optional .snap(label),
.job/.socket/.pid. The caller owns launch, identity, stopping and saves.
Fixture writes are limited to unearned inventory (Deku, Power ring
appraisal, Ocarina level), not acquisition proof. No cursor, menu, binding,
CPU or ROM writes. Stdlib only; --describe works offline.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True

SOUND_QUEUE, WATCH_DEPTH = 0x7E012F, 512
MOVE_SOUND, BOSS_DYING = 0x20, 0x22
# Action -> (label in active.job/candidatex.sym, offset of its STA.w $012F).
# The unwear site is the default !ENABLE_ONE_RING == 1 branch.
STORE_SITES = {"move": ("Menu_Equipment_Move_accept", 10),
               "select": ("Menu_Equipment_Select_sound", 2),
               "wear": ("Menu_Page3_ToggleRing_wear", 6),
               "unwear": ("Menu_Page3_ToggleRing", 14)}
MODULE, SUBMODULE, MENU, CURSOR, PAGE = 0x7E0010, 0x7E0011, 0x7E0200, 0x7E020B, 0x7E0731
ROOM, LINK_STATE, FORM, INVULN = 0x7E00A0, 0x7E005D, 0x7E02B2, 0x7E037B
Y_ITEM, CURRENT_SONG, HP, MAGIC = 0x7E0202, 0x7E030F, 0x7EF36D, 0x7EF36E
DEKU, OCARINA, MAGICRINGS = 0x7EF349, 0x7EF34C, 0x7EF3A2
RING_SLOT1, BOUND_MASK, SAVED_SONG = 0x7EF3A3, 0x7EF3A8, 0x7EF3AB
HOUSE_ROOM, POWER_BIT, POWER_ID = 0x0104, 0x20, 2
SLOT_DEKU, SLOT_POWER, SLOT_SONG1 = 0, 5, 11
ROW_STARTS = (0, 5, 11, 15, 21)          # masks, rings, songs, supplies
TAP_HOLD, TAP_SETTLE, SCREEN_STEP = 2, 4, 4
SCREEN_WAITS, NAV_TAPS, FRAME_BUDGET, DEADLINE_SECONDS = 60, 10, 1800, 240
FIXTURE_ADDRESSES = (DEKU, MAGICRINGS, OCARINA)
UNCHANGED = (ROOM, LINK_STATE, FORM, INVULN, HP, MAGIC)
SELECTIONS = (BOUND_MASK, RING_SLOT1, SAVED_SONG, CURRENT_SONG, Y_ITEM)


def describe():
    return {
        "fixture": "equipment_menu_sfx",
        "callable": "run(active, output_path, expected_sound) -> JSON-serializable dict; "
                    "output_path is the receipt file (e.g. out/'RESULT.json')",
        "expected_sound": {"0x20": "candidate 9886005996ab", "0x22": "control 4ff0efc02c70"},
        "route": ["START -> Items (module 0E, 0200=04)",
                  "L -> Equipment (0200=06, MenuScrollLevelH 7E0731 != 0)",
                  "D-pad to slot 0 Deku; A: BoundMask 7EF3A8=1, expected_sound",
                  "DOWN movement control 0 -> 5 Power ring: 0x20",
                  "if RingSlot1 7EF3A3 already 2: setup A unwear (0x20)",
                  "A wear: 7EF3A3=2, expected_sound; stationary A unwear: 7EF3A3=0, 0x20",
                  "D-pad to slot 11 song 1; Y: 030F=1, 7EF3AB=1, 0202=0D, expected_sound",
                  "START close -> House: module 07, submodule 0, room 0104"],
        "proof": "MEM_WATCH_WRITES 7E012F depth 512 per tap window; raw writes and PCs kept; "
                 "each action window needs exactly one nonzero write whose PC is its symbol-derived store",
        "store_sites": {action: f"{label}+{offset}: A9 <sound> 8D 2F 01 read back at PC-2"
                        for action, (label, offset) in STORE_SITES.items()},
        "action_sites": {"mask/song": "select", "ring wear": "wear", "unwear/setup": "unwear",
                         "movement": "move"},
        "fixture_writes": {"7EF349": "Deku = 1 only if 0",
                           "7EF3A2": "OR 0x20 (Power appraised) only if bit clear",
                           "7EF34C": "raise to 2 only if below 2"},
        "caps": {"tap_frames": TAP_HOLD + TAP_SETTLE, "screen_wait_frames": SCREEN_WAITS * SCREEN_STEP,
                 "nav_taps_per_target": NAV_TAPS, "frame_budget": FRAME_BUDGET,
                 "deadline_seconds": DEADLINE_SECONDS},
        "cleanup": "remove own watch IDs only; neutral input; paused; menu closed only on success",
        "native_executed": False,
    }


class Failure(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Failure(message)


def payload(reply, what):
    require(isinstance(reply, dict) and reply.get("success"), f"{what} failed: {reply!r}")
    data = reply.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as error:
            raise Failure(f"{what} returned unparsable data {data!r}") from error
    require(isinstance(data, dict), f"{what} returned non-object data {data!r}")
    return data


def number(value):
    if isinstance(value, bool):
        raise Failure(f"Boolean where a number was expected: {value!r}")
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def row(slot):
    return next(i for i in range(4) if ROW_STARTS[i] <= slot < ROW_STARTS[i + 1])


class EquipmentSfx:
    def __init__(self, active, output_path, expected_sound):
        self.active, self.output = active, Path(output_path)
        self.expected = expected_sound
        self.deadline = time.monotonic() + DEADLINE_SECONDS
        self.frames, self.watches, self.sites = 0, set(), {}
        self.result = {
            "fixture": "equipment_menu_sfx", "passed": False, "expected_sound": expected_sound,
            "role": {MOVE_SOUND: "candidate", BOSS_DYING: "control"}.get(
                expected_sound if type(expected_sound) is int else None, "invalid"),
            "session": {k: str(getattr(active, k, None)) for k in ("job", "socket", "pid")},
            "store_sites": {}, "checks": [], "fixture_writes": [], "windows": [], "snaps": [],
            "cleanup_errors": [],
        }

    @property
    def b(self):
        return self.active.b

    def r(self, address):
        return number(self.b.read_memory(address)) & 0xFF

    def room(self):
        return number(self.b.read_memory16(ROOM)) & 0xFFFF

    def paused(self):
        state = payload(self.b.send_command("STATE"), "STATE")
        require("paused" in state, "Native pause state is unknown")
        return bool(state["paused"])

    def neutral(self):
        reply = self.b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
        require(isinstance(reply, dict) and reply.get("success"), "Neutral INPUT rejected")

    def check(self, label, actual, expected):
        self.result["checks"].append(dict(name=label, actual=actual, expected=expected, passed=actual == expected))
        require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def snap(self, label):
        if callable(getattr(self.active, "snap", None)):
            self.result["snaps"].append(dict(label=label, data=self.active.snap(label)))

    def step(self, frames, buttons=""):
        require(time.monotonic() < self.deadline, "Fixture deadline exceeded")
        require(self.frames + frames <= FRAME_BUDGET, "Fixture frame budget exceeded")
        self.active.step(frames, buttons)
        self.frames += frames

    def screen(self):
        if self.r(MODULE) != 0x0E:
            return "gameplay" if (self.r(MODULE), self.r(SUBMODULE)) == (0x07, 0x00) else "transition"
        menu = self.r(MENU)
        if menu == 0x04:
            return "items"
        if menu == 0x06:
            return "equipment" if self.r(PAGE) else "quest"
        return f"menu-{menu:02X}"

    def wait_screen(self, expected):
        for _ in range(SCREEN_WAITS):
            if self.screen() == expected:
                self.check("screen", self.screen(), expected)
                return
            self.step(SCREEN_STEP)
        raise Failure(f"Timed out awaiting {expected}; got {self.screen()}")

    def watch_add(self):
        data = payload(self.b.mem_watch_add(SOUND_QUEUE, size=1, depth=WATCH_DEPTH), "MEM_WATCH_WRITES add")
        require("watch_id" in data, f"MEM_WATCH_WRITES add has no watch_id: {data!r}")
        ident = number(data["watch_id"])
        self.watches.add(ident)
        require(number(data.get("addr", -1)) == SOUND_QUEUE, f"Watch address differs: {data!r}")
        require(number(data.get("depth", -1)) == WATCH_DEPTH, f"Watch depth differs: {data!r}")
        return ident

    def watch_remove(self, ident):
        reply = self.b.mem_watch_remove(ident)
        require(isinstance(reply, dict) and reply.get("success"),
                f"MEM_WATCH_WRITES remove {ident} failed: {reply!r}")
        self.watches.discard(ident)

    def blame(self, ident):
        data = payload(self.b.mem_blame(watch_id=ident), "MEM_BLAME")
        raw = data.get("writes")
        require(isinstance(raw, list), f"MEM_BLAME has no writes list: {data!r}")
        require(number(data.get("count", len(raw))) == len(raw), "MEM_BLAME count differs from writes")
        require(len(raw) < WATCH_DEPTH, "Sound queue watch log saturated")
        writes = []
        for entry in raw:
            require(isinstance(entry, dict), f"Malformed write record {entry!r}")
            write = dict(pc=number(entry["pc"]), addr=number(entry["addr"]), value=number(entry["value"]),
                         opcode=entry.get("opcode"), cycle=entry.get("cycle"))
            require(write["addr"] == SOUND_QUEUE, f"Write outside watched address: {entry!r}")
            writes.append(write)
        return writes

    def window(self, label, kind, button):
        require(self.paused(), "Input window requires a paused session")
        entry = dict(label=label, kind=kind, button=button, cursor_before=self.r(CURSOR),
                     screen_before=self.screen(), queue_before=self.r(SOUND_QUEUE))
        self.result["windows"].append(entry)
        ident = self.watch_add()
        entry["watch_id"] = ident
        try:
            self.step(TAP_HOLD, button)
            self.step(TAP_SETTLE)
            entry["writes"] = self.blame(ident)
        finally:
            try:
                self.watch_remove(ident)
            except Exception as error:
                self.result["cleanup_errors"].append(f"watch {ident}: {error!r}")
        entry["nonzero"] = [w for w in entry["writes"] if w["value"]]
        entry.update(cursor_after=self.r(CURSOR), screen_after=self.screen(), frames=TAP_HOLD + TAP_SETTLE)
        entry["nonzero_pcs"] = [f"{w['pc']:06X}" for w in entry["nonzero"]]
        return entry

    def resolve_sites(self):
        symbols = (Path(str(self.active.job)) / "candidatex.sym").read_text(encoding="utf-8", errors="replace")
        for action, (label, offset) in STORE_SITES.items():
            found = {int(bank + addr, 16) for bank, addr in re.findall(
                rf"^([0-9A-Fa-f]{{2}}):([0-9A-Fa-f]{{4}})\s+(?:Oracle_)?{re.escape(label)}\s*$", symbols, re.M)}
            require(len(found) == 1, f"Missing/ambiguous symbol {label}: {sorted(f'{a:06X}' for a in found)}")
            base = found.pop()
            pc, sound = base + offset, self.expected if action in ("select", "wear") else MOVE_SOUND
            actual = bytes(self.b.read_block(pc - 2, 5))
            self.result["store_sites"][action] = dict(label=label, symbol=f"{base:06X}", offset=offset,
                                                      pc=f"{pc:06X}", sound=sound, bytes=actual.hex(" ").upper())
            require(actual == bytes((0xA9, sound, 0x8D, 0x2F, 0x01)),
                    f"{label}+{offset} is not LDA.b #${sound:02X} : STA.w $012F")
            self.sites[action] = (pc, sound)

    def expect_sounds(self, entry, site):
        pcs = [self.sites[site][0]] if site else []
        entry.update(site=site, expected_pcs=[f"{pc:06X}" for pc in pcs])
        self.check(entry["label"] + " nonzero 7E012F writes", [w["value"] for w in entry["nonzero"]],
                   [self.sites[site][1]] if site else [])
        self.check(entry["label"] + " store PC", [w["pc"] for w in entry["nonzero"]], pcs)

    def move(self, label, button):
        entry = self.window(label, "movement", button)
        self.check(label + " stays on Equipment", entry["screen_after"], "equipment")
        moved = entry["cursor_after"] != entry["cursor_before"]
        self.expect_sounds(entry, "move" if moved else None)
        return entry

    def navigate(self, target):
        for _ in range(NAV_TAPS):
            cursor = self.r(CURSOR)
            require(cursor < ROW_STARTS[-1], f"Equipment cursor invalid: {cursor:02X}")
            if cursor == target:
                return
            if row(cursor) != row(target):
                button = "DOWN" if (row(target) - row(cursor)) % 4 <= 2 else "UP"
            else:
                button = "LEFT"
            self.move(f"navigate {cursor} -> {target}", button)
        raise Failure(f"Cursor did not reach slot {target} in {NAV_TAPS} taps")

    def select(self, label, button, slot, site, kind="selection"):
        self.check(label + " cursor", self.r(CURSOR), slot)
        entry = self.window(label, kind, button)
        self.check(label + " stays on Equipment", entry["screen_after"], "equipment")
        self.check(label + " cursor stationary", entry["cursor_after"], slot)
        self.expect_sounds(entry, site)
        return entry

    def fixture(self, address, wanted, reason):
        require(address in FIXTURE_ADDRESSES and self.paused(), "Fixture write outside paused contract")
        before = self.r(address)
        entry = dict(address=f"{address:06X}", before=before, reason=reason)
        self.result["fixture_writes"].append(entry)
        if wanted == before:
            entry["skipped"] = "already satisfied"
            return
        entry["value"] = wanted
        require(self.b.write_memory(address, wanted), f"Fixture write {address:06X} rejected")
        entry["readback"] = self.r(address)
        require(entry["readback"] == wanted, f"Fixture readback {address:06X} differs")

    def run(self):
        require(self.expected in (MOVE_SOUND, BOSS_DYING) and type(self.expected) is int,
                "expected_sound must be int 0x20 (candidate) or 0x22 (control)")
        require(self.paused(), "Session must be paused at admission")
        self.neutral()
        self.check("start in House gameplay", [self.screen(), self.room()], ["gameplay", HOUSE_ROOM])
        self.check("start human on foot", [self.r(LINK_STATE), self.r(FORM)], [0, 0])
        self.resolve_sites()
        baseline = {f"{a:06X}": self.r(a) for a in UNCHANGED}
        self.result["baseline"] = baseline
        self.result["selections_before"] = {f"{a:06X}": self.r(a) for a in SELECTIONS}

        self.fixture(DEKU, self.r(DEKU) or 1, "Deku owned for slot 0")
        self.fixture(MAGICRINGS, self.r(MAGICRINGS) | POWER_BIT, "Power ring appraised, other bits kept")
        self.fixture(OCARINA, max(self.r(OCARINA), 2), "Ocarina >= 2 so song 1 is owned")
        self.check("fixtures leave actor/room/vitals", {f"{a:06X}": self.r(a) for a in UNCHANGED}, baseline)

        self.window("open menu", "route", "START")
        self.wait_screen("items")
        self.window("Items -> Equipment", "route", "L")
        self.wait_screen("equipment")
        self.snap("equipment-open")

        self.navigate(SLOT_DEKU)
        self.select("mask A Deku", "A", SLOT_DEKU, "select")
        self.check("mask bound without transform", [self.r(BOUND_MASK), self.r(FORM)], [1, 0])
        self.snap("equipment-mask")

        control = self.move("movement control DOWN 0 -> 5", "DOWN")
        self.check("movement control cursor", [control["cursor_before"], control["cursor_after"]],
                   [SLOT_DEKU, SLOT_POWER])

        self.navigate(SLOT_POWER)
        self.result["ring_initial"] = self.r(RING_SLOT1)
        if self.result["ring_initial"] == POWER_ID:
            self.select("setup ring A unwear", "A", SLOT_POWER, "unwear", kind="setup")
            self.check("setup ring removed", self.r(RING_SLOT1), 0)
        self.select("ring A wear", "A", SLOT_POWER, "wear")
        self.check("Power ring worn", self.r(RING_SLOT1), POWER_ID)
        self.snap("equipment-ring-worn")
        self.select("ring A unwear (stationary)", "A", SLOT_POWER, "unwear")
        self.check("Power ring removed", self.r(RING_SLOT1), 0)

        self.navigate(SLOT_SONG1)
        self.select("song Y 1", "Y", SLOT_SONG1, "select")
        self.check("song 1 selected", [self.r(CURRENT_SONG), self.r(SAVED_SONG), self.r(Y_ITEM)], [1, 1, 0x0D])
        self.snap("equipment-song")

        values = [w["value"] for e in self.result["windows"] if e["kind"] in ("selection", "movement", "setup")
                  for w in e["nonzero"]]
        if self.expected == MOVE_SOUND:
            self.check("no 0x22 in candidate selection/movement windows", BOSS_DYING in values, False)

        self.window("close menu", "route", "START")
        self.wait_screen("gameplay")
        self.check("closed back in House", self.room(), HOUSE_ROOM)
        self.check("actor/room/vitals unchanged", {f"{a:06X}": self.r(a) for a in UNCHANGED}, baseline)
        self.check("selections retained after close", [self.r(BOUND_MASK), self.r(RING_SLOT1), self.r(SAVED_SONG)],
                   [1, 0, 1])
        self.result["selections_after"] = {f"{a:06X}": self.r(a) for a in SELECTIONS}
        self.snap("house-closed")
        self.result["runtime_checks_passed"] = True

    def cleanup(self):
        for ident in sorted(self.watches):
            try:
                self.watch_remove(ident)
            except Exception as error:
                self.result["cleanup_errors"].append(f"watch {ident}: {error!r}")
        for name, op in (("neutral", self.neutral), ("pause", lambda: self.b.pause())):
            try:
                op()
            except Exception as error:
                self.result["cleanup_errors"].append(f"{name}: {error!r}")
        try:
            require(self.paused(), "Session not paused after cleanup")
            listed = payload(self.b.mem_watch_list(), "MEM_WATCH_WRITES list").get("watches", [])
            left = {number(w.get("watch_id")) for w in listed if isinstance(w, dict)}
            owned = {w["watch_id"] for w in self.result["windows"] if "watch_id" in w}
            require(not left & owned, f"Own watches remain: {sorted(left & owned)}")
        except Exception as error:
            self.result["cleanup_errors"].append(repr(error))


def run(active, output_path, expected_sound):
    flow = EquipmentSfx(active, output_path, expected_sound)
    try:
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
        try:
            flow.snap("failure")
        except Exception as snap_error:
            flow.result["cleanup_errors"].append(f"failure snap: {snap_error!r}")
    finally:
        try:
            flow.cleanup()
        except Exception as error:
            flow.result["cleanup_errors"].append(repr(error))
        flow.result["frames"] = flow.frames
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"]
                                     and "error" not in flow.result)
        flow.output.parent.mkdir(parents=True, exist_ok=True)
        flow.output.write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    return json.loads(json.dumps(flow.result, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--describe", action="store_true", help="print the offline contract and exit")
    args = parser.parse_args()
    if not args.describe:
        parser.error("import run(active, output_path, expected_sound) from the caller; only --describe runs offline")
    print(json.dumps(describe(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
