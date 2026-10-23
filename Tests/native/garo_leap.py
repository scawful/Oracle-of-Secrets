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

    def face(self, pad):
        self.settle_combat(); self.center()
        self.advance(pad, 3); self.advance("", 2)
        native.require(self.r(0x7E002F) == FACING[pad], f"Link did not face {pad}")

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
        self.face("Right")
        x0, _ = self.xy()
        self.advance("Y,Right", 1)
        rows = [self.row("lunge-press")]
        for _ in range(60):
            if hop and len(rows) == 5:
                self.advance("Y", 1); rows.append(self.row("hop-press"))
                continue
            self.advance("", 1); rows.append(self.row("cape-hop" if hop and len(rows) > 5 else "lunge"))
            r = rows[-1]
            if len(rows) > 5 and r["link_state"] == 0 and r["recoil_flags"] == 0 and r["z"] == 0:
                break
        dash = [r for r in rows if r["link_state"] == DASH]
        air = [r for r in rows if r["link_state"] == 2]
        x1, _ = self.xy()
        self.shot("garo-cape-hop" if hop else "garo-lunge")
        end = rows[-1]
        return dict(lunged=bool(dash), dash_frames=len(dash),
                    sword_out=bool(dash) and all(r["sword_state"] == 9 for r in dash[1:]),
                    hopped=bool(air), air_frames=len(air), z_max=max(r["z"] for r in rows),
                    immune_in_flight=all(r["immune"] for r in air) if air else None,
                    guard_opened=any(r["guard"] for r in rows), dx=x1 - x0,
                    landed_clean=end["link_state"] == 0 and end["recoil_flags"] == 0
                    and end["immune"] == 0 and end["lunge_timer"] == 0,
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
            if rows[-1]["recoil_flags"] == 0 and rows[-1]["recoil"] == 0 and rows[-1]["z"] == 0 \
                    and len(rows) > 4:
                break
        flight = [r for r in rows if r["recoil_flags"]]
        x1, y1 = self.xy()
        self.shot(f"garo-leap-{guard_facing.lower()}-{tap.lower()}")
        return dict(guard_at_tap=guard_at_tap, leaped=bool(flight), flight_frames=len(flight),
                    airborne_frames=sum(1 for r in rows if r["z"]), z_max=max(r["z"] for r in rows),
                    dx=x1 - x0, dy=y1 - y0,
                    facing_kept=all(r["facing"] == FACING[guard_facing] for r in flight) if flight else None,
                    facing_end=rows[-1]["facing"],
                    immune_in_flight=all(r["immune"] for r in flight) if flight else None,
                    landed_clean=rows[-1]["recoil_flags"] == 0 and rows[-1]["immune"] == 0
                    and rows[-1]["link_state"] == 0,
                    cooldown_at_landing=rows[-1]["cooldown"], frames=len(rows))

    def cooldown(self):
        self.face("Left")
        self.open_guard()
        self.advance("", 2)
        self.advance("Right", 2)
        self.until(lambda: self.r(BUMP) == 0 and self.r(RECOIL) == 0 and self.r(Z) == 0
                   and self.r(STATE) == 0, "Leap did not land", 60)
        left = self.r(COOLDOWN)
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
        v = {"turn-guard opens a guard, no leap": turn.get("completed", False) and not turn.get("leaped")}
        if self.expect == "candidate":
            v["lunge dashes right with the sword out"] = bool(lunge.get("lunged") and lunge.get("sword_out")
                                                             and lunge.get("dx", 0) > 0 and not lunge.get("hopped"))
            v["lunge ends by itself"] = bool(lunge.get("landed_clean") and 0 < lunge.get("dash_frames", 0) <= 20)
            v["cape-hop jumps from the lunge, immune"] = bool(hop.get("lunged") and hop.get("hopped")
                                                             and hop.get("z_max") and hop.get("immune_in_flight"))
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
