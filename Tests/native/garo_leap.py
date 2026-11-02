#!/usr/bin/env python3
"""Garo Master moves: lunge, cape hop, and the evasive leap.

Lunge: Y while holding Link's facing direction (instant fixed-length dash).
Cape hop: Y again during the lunge (Roc's Feather style jump, immune).
Leap: a d-pad tap away from Link's facing while the guard is open.

Attach-only. The caller launches one headless private Mesen2 instance, boots
file 1 into Link's House room 0104 and writes SESSION.json (same shape as
garo_combat_fixture.py). Fixture writes: Garo/sword ownership only. Link,
guard, cooldown, recoil and immunity are only driven by controller input.

--expect candidate asserts the moves. --expect baseline runs the same inputs
on the pre-leap ROM: Y only opens the guard, the tap only turns and walks Link.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
if "--support-root" in sys.argv:
    sys.path.insert(0, sys.argv[sys.argv.index("--support-root") + 1])
import garo_combat_fixture as garo

prototype, native, menu = garo.prototype, garo.native, garo.menu
GUARD, COOLDOWN = garo.GUARD, garo.COOLDOWN
Z, BUMP, RECOIL, IMMUNE, STATE = 0x7E0024, 0x7E004D, 0x7E0046, 0x7E037B, 0x7E005D
DASH, LUNGE_TIMER = 0x11, 0x7E07FF
FACING = {"Up": 0, "Down": 2, "Left": 4, "Right": 6}
AWAY = {"Left": "Right", "Right": "Left", "Up": "Down", "Down": "Up"}


def grounded(row):
    # Vanilla normal movement uses FF; zero is also visible on the landing frame.
    return (row["z"] in (0, 0xFF) and row["link_state"] == 0
            and row["recoil_flags"] == 0 and row["recoil"] == 0 and row["immune"] == 0)


def height(z):
    return z if 0 < z < 0x80 else 0


def describe():
    return dict(native_executed=False, room="0104",
                cases=["turn-guard: Y with a new d-pad press toward a fresh facing still opens the guard",
                       "lunge: facing Right, Y while holding Right dashes right with the sword out, ends by itself",
                       "cape-hop: Y again during the lunge jumps right, immune in flight, lands clean",
                       "back-leap: guard facing Left, then tap Right",
                       "side-leap: guard facing Left, then tap Down",
                       "cooldown: Y right after landing opens no guard; it opens once the cooldown ends"],
                fixture_writes="Garo/sword ownership only when absent",
                prohibited_writes=["CPU", "Link position", "guard/cooldown timers", "recoil/immunity",
                                   "module", "room", "story", "SRAM", "save state", "ROM"])


class GaroLeapFlow(garo.GaroCombatFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 600
        self.expect = args.expect
        self.result["scope"] = describe()
        self.result["scope"]["expect"] = self.expect

    def row(self, label):
        state = self.sample(label)
        state.update(z=self.r(Z), immune=self.r(IMMUNE), link_state=self.r(STATE),
                     lunge_timer=self.r(LUNGE_TIMER))
        return state

    def center(self):
        # Walk by controller into the open middle of the house floor.
        for _ in range(120):
            x, y = self.xy()
            if 0x0950 <= x < 0x0970 and 0x2180 <= y < 0x21A0:
                return
            pad = ("Right" if x < 0x0950 else "Left" if x >= 0x0970 else
                   "Down" if y < 0x2180 else "Up")
            self.advance(pad, 1)
        native.require(False, "Could not walk Link to the floor centre")

    def face(self, pad, lunge=False):
        self.settle_combat(); self.center()
        if lunge:
            self.lunge_start()
        else:
            self.advance(pad, 3); self.advance("", 2)
        native.require(self.r(0x7E002F) == FACING[pad], f"Link did not face {pad}")

    def lunge_start(self):
        # Go left of the table before walking down into the bottom aisle.
        for axis, target, low, high in ((0, 0x0940, "Left", "Right"),
                                        (1, 0x21BC, "Up", "Down")):
            for _ in range(160):
                value = self.xy()[axis]
                if abs(value - target) <= 1:
                    break
                self.advance(low if value > target else high, 1)
            else:
                native.require(False, "Could not walk Link into the clear lunge aisle")
        for _ in range(12):
            if self.xy()[0] >= 0x0948:
                break
            self.advance("Right", 1)
        native.require(0x0948 <= self.xy()[0] <= 0x0949, "Lunge start is outside its two-pixel bound")
        self.advance("", 2)

    def check_lunge_floor(self):
        self.assert_room()
        native.require(self.r(0x7E00EE) == 0, "Lunge aisle requires the lower floor")
        x, y = self.xy()
        tiles = self.block(0x7F2000, 0x2000)
        # Cover 80 px of travel plus Link's width and feet, not just his origin.
        offsets = {((yy & 0x1F8) << 3) + ((xx & 0x1FF) >> 3)
                   for yy in range(y + 8, y + 24) for xx in range(x, x + 96)}
        self.check("Live lunge corridor is ordinary floor", sorted({tiles[i] for i in offsets}), [0])
        self.result.setdefault("floor_checks", []).append(dict(start=[x, y],
            offsets=sorted(offsets), values=[tiles[i] for i in sorted(offsets)]))

    def open_guard(self, buttons="Y"):
        self.advance(buttons, 2)
        self.until(lambda: self.r(GUARD) > 0, "Y did not open the guard", 4)

    def turn_guard(self):
        self.face("Right")
        self.open_guard("Y,Left")
        rows = [self.row("turn-guard")]
        for _ in range(8):
            self.advance("Left", 1); rows.append(self.row("turn-guard"))
        return dict(guard_opened=True, leaped=any(r["recoil_flags"] for r in rows),
                    facing_end=rows[-1]["facing"])

    def lunge(self, hop=False):
        self.face("Right", lunge=True)
        self.check_lunge_floor()
        start = self.xy()
        previous = getattr(self, "plain_lunge_start", None)
        if hop:
            native.require(previous is not None and all(abs(a - b) <= 1 for a, b in zip(start, previous)),
                           "Lunge and cape-hop need the same start within one pixel")
        else:
            self.plain_lunge_start = start
        x0, _ = start
        self.advance("Y,Right", 1)
        rows = [self.row("lunge-press")]
        for _ in range(90):
            if hop and len(rows) == 5:
                self.advance("Y", 1); rows.append(self.row("hop-press"))
                continue
            self.advance("", 1); rows.append(self.row("cape-hop" if hop and len(rows) > 5 else "lunge"))
            r = rows[-1]
            if len(rows) > 5 and grounded(r):
                break
        dash = [r for r in rows if r["link_state"] == DASH]
        air = [r for r in rows if r["link_state"] == 2 and r["recoil_flags"] == 2]
        x1, _ = self.xy()
        self.shot("garo-cape-hop" if hop else "garo-lunge")
        end = rows[-1]
        return dict(start=start, end=self.xy(), lunged=bool(dash), dash_frames=len(dash),
                    sword_out=bool(dash) and all(r["sword_state"] == 9 for r in dash[1:]),
                    hopped=bool(air), air_frames=len(air), z_max=max(height(r["z"]) for r in rows),
                    immune_in_flight=all(r["immune"] for r in air) if air else None,
                    guard_opened=any(r["guard"] for r in rows), dx=x1 - x0,
                    bonked=any(r["recoil_flags"] == 1 for r in rows),
                    timer_expired=bool(dash) and dash[-1]["lunge_timer"] == 1 and end["lunge_timer"] == 0,
                    landed_clean=grounded(end) and end["lunge_timer"] == 0,
                    cooldown_at_end=end["cooldown"], frames=len(rows))

    def leap(self, guard_facing, tap):
        self.face(guard_facing)
        self.open_guard()
        self.advance("", 2)
        x0, y0 = self.xy()
        guard_at_tap = self.r(GUARD)
        self.advance(tap, 2)
        rows = [self.row("leap-tap")]
        for _ in range(40):
            self.advance("", 1); rows.append(self.row("leap"))
            if grounded(rows[-1]) and len(rows) > 4:
                break
        flight = [r for r in rows if r["recoil_flags"]]
        x1, y1 = self.xy()
        self.shot(f"garo-leap-{guard_facing.lower()}-{tap.lower()}")
        return dict(guard_at_tap=guard_at_tap, leaped=bool(flight), flight_frames=len(flight),
                    airborne_frames=sum(1 for r in rows if height(r["z"])),
                    z_max=max(height(r["z"]) for r in rows),
                    dx=x1 - x0, dy=y1 - y0,
                    facing_kept=all(r["facing"] == FACING[guard_facing] for r in flight) if flight else None,
                    facing_end=rows[-1]["facing"],
                    immune_in_flight=all(r["immune"] for r in flight) if flight else None,
                    landed_clean=grounded(rows[-1]),
                    cooldown_at_landing=rows[-1]["cooldown"], frames=len(rows))

    def lunge_contact(self):
        self.face("Left")
        self.spawn_target()
        target_hp = 0x7E0E50 + self.slot
        before = self.r(target_hp)
        rows = []
        try:
            self.advance("Y,Left", 2)
            for _ in range(24):
                rows.append(dict(hp=self.r(target_hp), state=self.r(0x7E0DD0 + self.slot),
                                 lunge_timer=self.r(LUNGE_TIMER), link_state=self.r(STATE)))
                self.advance("", 1)
            # Lethal native damage can wrap HP; state 6 is the death module.
            damaged = any(r["hp"] < before or r["state"] == 6 for r in rows)
            self.check("Lunge reaches native dash state", any(r["lunge_timer"] for r in rows), True)
            self.check("Lunge damages native enemy", damaged, True)
            return dict(initial_hp=before, trace=rows, damaged=damaged)
        finally:
            self.remove_target()

    def cooldown(self):
        self.face("Left")
        self.open_guard()
        self.advance("", 2)
        self.advance("Right", 2)
        self.until(lambda: self.r(BUMP) == 0 and self.r(RECOIL) == 0 and self.r(Z) in (0, 0xFF)
                   and self.r(STATE) == 0 and self.r(IMMUNE) == 0, "Leap did not land", 60)
        left = self.r(COOLDOWN)
        native.require(left > 0, "Landing left no cooldown to test")
        self.advance("Y", 2); self.advance("", 1)
        blocked = self.r(GUARD) == 0
        self.until(lambda: self.r(COOLDOWN) == 0, "Cooldown did not expire", 120)
        self.advance("", 2)
        self.open_guard()
        return dict(cooldown_after_landing=left, guard_blocked=blocked, guard_after_cooldown=True)

    def case(self, name, fn):
        entry = dict(name=name)
        self.result["cases"].append(entry)
        try:
            entry.update(fn())
            entry["completed"] = True
        except Exception as error:
            entry["error"] = repr(error)
        finally:
            self.input("")
        return entry

    def verdict(self, cases):
        turn, back, side = cases["turn-guard"], cases["back-leap"], cases["side-leap"]
        lunge, hop = cases["lunge"], cases["cape-hop"]
        v = {"all selected cases complete": bool(cases) and all(
                 case.get("completed") is True and "error" not in case for case in cases.values()),
             "turn-guard opens a guard, no leap": turn.get("completed", False) and not turn.get("leaped")}
        if self.expect == "candidate":
            v["lunge dashes right with the sword out"] = bool(lunge.get("lunged") and lunge.get("sword_out")
                                                             and lunge.get("dx", 0) > 0 and not lunge.get("hopped")
                                                             and not lunge.get("bonked"))
            v["lunge ends by itself"] = bool(lunge.get("landed_clean") and lunge.get("timer_expired")
                                              and 0 < lunge.get("dash_frames", 0) <= 20)
            v["cape-hop jumps from the lunge, immune"] = bool(hop.get("lunged") and hop.get("hopped")
                                                             and hop.get("z_max") and hop.get("immune_in_flight")
                                                             and not hop.get("bonked"))
            v["cape-hop goes farther than the lunge"] = hop.get("dx", 0) > lunge.get("dx", 0) > 0
            v["cape-hop lands clean"] = bool(hop.get("landed_clean"))
            cd = cases["cooldown"]
            v["back-leap moves right, facing kept"] = bool(back.get("leaped") and back.get("dx", 0) > 0
                                                           and back.get("facing_kept"))
            v["back-leap hops and is immune"] = bool(back.get("airborne_frames") and back.get("immune_in_flight"))
            v["back-leap lands clean"] = bool(back.get("landed_clean"))
            v["side-leap moves down, facing kept"] = bool(side.get("leaped") and side.get("dy", 0) > 0
                                                          and side.get("facing_kept"))
            v["cooldown blocks then recovers"] = bool(cd.get("guard_blocked") and cd.get("guard_after_cooldown"))
            v["lunge damages native enemy"] = bool(cases["lunge-contact"].get("damaged"))
        else:
            v["control Y+forward only guards"] = (lunge.get("completed", False) and not lunge.get("lunged")
                                                  and lunge.get("guard_opened", False) and not hop.get("hopped"))
            v["control tap does not leap"] = (back.get("completed", False) and not back.get("leaped")
                                              and side.get("completed", False) and not side.get("leaped"))
            v["control tap turns Link"] = back.get("facing_end") == FACING["Right"]
        return v

    def run(self):
        self.assert_room()
        protected = {str(a): self.r(a) for a in garo.PROTECTED}
        self.bind_garo()
        cases = {}
        cases["turn-guard"] = self.case("turn-guard", self.turn_guard)
        cases["lunge"] = self.case("lunge", self.lunge)
        cases["cape-hop"] = self.case("cape-hop", lambda: self.lunge(hop=True))
        cases["back-leap"] = self.case("back-leap", lambda: self.leap("Left", "Right"))
        cases["side-leap"] = self.case("side-leap", lambda: self.leap("Left", "Down"))
        if self.expect == "candidate":
            cases["cooldown"] = self.case("cooldown", self.cooldown)
            cases["lunge-contact"] = self.case("lunge-contact", self.lunge_contact)
        self.result["verdict"] = self.verdict(cases)
        self.check("Story/rings/progression unchanged", {str(a): self.r(a) for a in garo.PROTECTED}, protected)
        self.result["runtime_checks_passed"] = all(self.result["verdict"].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path, required="--describe" not in sys.argv)
    parser.add_argument("--support-root", type=Path)
    parser.add_argument("--expect", choices=("candidate", "baseline"), default="candidate")
    parser.add_argument("--output", type=Path, default=ROOT / "native/garo-leap")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures, "Use --describe or explicitly --execute-fixtures")
    session = json.loads(args.session.read_text())
    values = dict(session)
    for key in ("status_file", "owner_file", "owned_rom", "symbols"):
        values[key] = Path(values[key])
    values.update(output=args.output, expect=args.expect, counter_spacing="immediate")
    identity = SimpleNamespace(**values)
    native.require(native.digest(identity.owned_rom.read_bytes()) == identity.rom_sha256,
                   "Private ROM hash differs from SESSION.json")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(identity.pid)], text=True)
    native.require("--headless" in command and str(identity.owned_rom) in command,
                   "PID is not the recorded private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, session["client_root"])
    from mesen2_client_lib.bridge import MesenBridge
    flow = GaroLeapFlow(identity, MesenBridge(identity.socket, auto_reconnect=False, max_retries=0))
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused private session without breakpoints")
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        try:
            flow.input("")
        except Exception as error:
            flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], verdict=flow.result.get("verdict"),
                          error=flow.result.get("error"), result=str(args.output / "RESULT.json")), indent=2))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
