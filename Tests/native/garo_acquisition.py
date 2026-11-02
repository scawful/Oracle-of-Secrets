#!/usr/bin/env python3
"""Attach-only acquisition of the placed Garo in daytime overworld $36.

setup: declare six WRAM progression/inventory/clock bytes, load entrance $1B
and area $36 through the native engine, then check distant Healing rejection.
acquire: approach by caller controls, --approach-route, or --noclip-approach;
check stale Healing and Storms rejection, fresh Healing acquisition, and R equip.
save-reopen: use native Save/Quit, reset and file1 reopen; reload area $36
and repeat the selected travel fixture to check persistence and NPC absence.
Optional --noclip-approach logs LinkWallCheat ($7E037F)=1 during bounded
controller movement and restores 0 before encounter checks. It takes precedence
over --approach-route. Ordinary progression and the full travel route are not
qualified by this encounter fixture. Each RESULT covers only its selected phase.
After each warp, four logged Link XY bytes place the start at C28/E38
below the cave fence. Never writes CPU, actor, SongFlag or SRAM directly. Native Save/Quit intentionally saves the private fixture.
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
import new_items_prototype as prototype

native, menu = prototype.native, prototype.menu
OWNED, BOUND = 0x7EF3AF, 0x7EF3A8
NPC_X, NPC_Y = 0xEF8, 0xEE8  # stream $09CBCC entry2, native prep adds 8
SETUP = {0x7EF3C5: 2, 0x7EE000: 8, 0x7EE001: 0,
         0x7EF34C: 3, OWNED: 0, BOUND: 0}
WARP_BYTES = {0x7E010E, 0x7E010F, 0x7E010A, 0x7E04AA, 0x7E001B,
              0x7E0011, 0x7E00B0, 0x7E0010, 0x7E00A0, 0x7E00A1,
              0x7E0013, 0x7E009B}


def describe():
    return dict(native_executed=False, acquisition_route_tested=False,
                phases={"setup": "Declare daytime fixture; engine entrance1B then area36; check distant Healing rejection",
                        "acquire": "Travel to placed NPC; check stale Healing and Storms rejection, fresh Healing acquisition, and R equip",
                        "save-reopen": "Native save/reset/file1; engine reload and travel fixture; check ownership, binding, NPC absence and repeat Healing"},
                setup_writes={f"{a:06X}": v for a, v in SETUP.items()},
                warp_writes="Logged OracleCheats entrance1B/area36 loader bytes plus four declared Link XY bytes for cave-exit start C28/E38",
                travel_writes="Only with --noclip-approach: logged LinkWallCheat $7E037F=1 for bounded controller travel, restored to 0 before encounter checks",
                npc="Existing sprite57, area36, daytime list1, native position EF8/EE8",
                route="Acquire accepts a prepared nearby session, --approach-route, or --noclip-approach. Save-reopen requires either travel option. Noclip takes precedence; JSON routes contain directional {buttons,frames} steps only.",
                qualification="Encounter and save checks only; normal progression and the full travel route remain unqualified. Each RESULT reports its selected phase, not all three phases.",
                prohibited_writes=["CPU", "actor", "SongFlag", "SRAM", "save state", "ROM"],
                persistence="Only the save-reopen phase intentionally saves the private progression fixture via game controls")


class GaroAcquisitionFlow(prototype.NewItemsFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 600
        self.result["scope"] = describe()
        self.result["scope"]["native_executed"] = True
        self.result["phase"] = args.phase
        self.result["inputs"] = vars(args)

    def write(self, address, value, reason):
        native.require(self.a.phase == "setup" and SETUP.get(address) == value,
                       "Write is outside the declared setup fixture")
        self.record_write(address, value, reason)

    def record_write(self, address, value, reason):
        self.check_owner()
        native.require(self.paused(), "WRAM fixture requires confirmed pause")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "WRAM fixture rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "WRAM fixture readback differs")

    def pause_settle(self):
        self.b.pause()
        end = min(self.deadline, time.monotonic() + 5)
        while not self.paused() and time.monotonic() < end:
            time.sleep(.01)
        native.require(self.paused(), "Pause acknowledgement did not settle")

    def actors(self):
        return [dict(slot=i, state=self.r(0x7E0DD0+i), type=self.r(0x7E0E20+i),
                     x=self.r(0x7E0D10+i) | self.r(0x7E0D30+i) << 8,
                     y=self.r(0x7E0D00+i) | self.r(0x7E0D20+i) << 8,
                     layer=self.r(0x7E0F20+i))
                for i in range(16) if self.r(0x7E0DD0+i)]

    def xy(self):
        return tuple(int.from_bytes(self.block(a, 2), "little") for a in (0x7E0022, 0x7E0020))

    def sample(self, label):
        row = dict(label=label, position=self.xy(), module=self.r(0x7E0010), submodule=self.r(0x7E0011),
                   area=self.r(0x7E008A), owned=self.r(OWNED), bound=self.r(BOUND), form=self.r(0x7E02B2),
                   song=self.r(0x7E030F), song_flag=self.r(0x7E00FE), flute_timer=self.r(0x7E03F0),
                   item=self.r(0x7E0202), effective_action=self.r(0x7E0304), actors=self.actors())
        self.result.setdefault("trace", []).append(row)
        return row

    def area_ready(self):
        self.ready()
        native.require((self.r(0x7E0010), self.r(0x7E0011), self.r(0x7E001B),
                        self.r(0x7E008A), self.r(0x7E008B)) == (9, 0, 0, 0x36, 0),
                       "Need ordinary overworld control in area36")
        native.require(self.r(0x7EF3C5) == 2 and 6 <= self.r(0x7EE000) < 18,
                       "Garo encounter requires the declared daytime phase")

    def ordinary_form(self):
        self.ready()
        if self.r(0x7E02B2) == 8:
            self.tap("R")
        self.until(lambda: self.r(0x7E02B2) in (0, 6) and self.r(0x7E02E1) == 0
                   and not self.ancilla(0x23), "Need ordinary Link with no transformation cloud", 240)

    def warp_to_desert(self):
        from mesen2_client_lib.oracle_cheats import OracleCheats
        flow = self

        class LoggedWarps(OracleCheats):
            def w(self, address, value):
                native.require(address in WARP_BYTES, "Unexpected warp control write")
                flow.record_write(address, value, "Declared native entrance1B/area36 loader fixture")

            def _poke(self, writes):
                paused = flow.paused()
                flow.pause_settle()
                try:
                    for address, value in writes:
                        self.w(address, value)
                finally:
                    if not paused:
                        native.require(self.b.resume(), "Warp resume rejected")

        self.check_owner()
        self.input("")
        warps = LoggedWarps(self.b, self.a.root)
        # Use the other existing table exit on area36: Beach Cave. The mine
        # exit lands behind its gate and can immediately send Link indoors.
        area = next(a for a in warps.warps["areas"] if a["area"] == "0x36")
        area.update(via_room="0x00ED", exit_index="0x1C", x="0x0C28", y="0x0DB8",
                    landing="outside Beach Cave End (declared loader fixture)")
        for label, action in (("entrance1B", lambda: warps.warp_entrance(0x1B, method="reload")),
                              ("area36", lambda: warps.warp_area(0x36))):
            reply = action()
            self.pause_settle()
            self.result.setdefault("warps", []).append(dict(step=label, result=reply))
            native.require(reply.get("ok"), f"Native {label} warp failed: {reply}")
        self.advance("", 120)  # Finish the native doorway exit before movement.
        self.area_ready()
        # Engine exit leaves Link in the cave trigger footprint. A declared
        # same-screen start below its fence prevents immediate re-entry.
        for address, value in ((0x7E0022, 0x28), (0x7E0023, 0x0C),
                               (0x7E0020, 0x38), (0x7E0021, 0x0E)):
            self.record_write(address, value, "Declared cave-exit start fixture C28/E38")
        self.advance("", 4)

    def equipment_slot(self, target):
        native.require(self.screen() == "equipment", "Need Equipment screen")
        row = 0 if target < 6 else 1 if target < 12 else 2 if target < 16 else 3
        bounds = ((0, 6), (6, 12), (12, 16), (16, 22))[row]
        for _ in range(4):
            if bounds[0] <= self.r(menu.CURSOR) < bounds[1]: break
            self.tap("Down")
        native.require(bounds[0] <= self.r(menu.CURSOR) < bounds[1], "Owned Equipment row is unreachable")
        for _ in range(bounds[1]-bounds[0]):
            if self.r(menu.CURSOR) == target: break
            self.tap("Right")
        self.check("Controller selects Equipment slot", self.r(menu.CURSOR), target)

    def select_song(self, song):
        native.require(song in (1, 2), "Only Healing/Storms belong to this scenario")
        self.ready()
        self.tap("Start"); self.wait_screen("items")
        self.tap("L"); self.wait_screen("equipment")
        self.equipment_slot(11+song)
        self.tap("A")
        self.check("Controller selects song", self.r(0x7E030F), song)
        self.check("Song selection equips Ocarina", self.r(0x7E0202), 0x0D)
        self.tap("Start"); self.wait_screen("gameplay")

    def play_song(self, song, label):
        self.select_song(song)
        self.sample(label+"-before")
        self.tap("Y", 3)
        self.sample(label+"-cast")
        self.until(lambda: not self.r(0x7E003A) & 0x40,
                   "Native flute animation did not finish", 180)
        self.sample(label+"-finished")

    def approach(self):
        if self.a.noclip_approach:
            self.area_ready()
            prior = self.r(0x7E037F)
            native.require(prior == 0, "Travel fixture requires normal collision initially")
            try:
                self.record_write(0x7E037F, 1, "Declared native wall-cheat controller travel fixture")
                for axis, target, negative, positive in ((1, NPC_Y+32, "Up", "Down"),
                                                          (0, NPC_X+32, "Left", "Right"),
                                                          (1, NPC_Y-16, "Up", "Down")):
                    for _ in range(90):
                        delta = target-self.xy()[axis]
                        if abs(delta) <= 3: break
                        self.advance(positive if delta > 0 else negative,
                                     max(1, min(30, abs(delta)//2)))
                        native.require(self.r(0x7E008A) == 0x36, "Travel left area36")
                    native.require(abs(target-self.xy()[axis]) <= 3, "Travel target unreachable")
            finally:
                self.input("")
                self.record_write(0x7E037F, prior, "Restore normal collision before encounter")
            self.advance("", 4)
            self.check("Normal collision restored", self.r(0x7E037F), 0)
            self.sample("noclip-travel-end")
            return
        for step in self.a.route:
            self.advance(step["buttons"], step["frames"])
        if self.a.route:
            self.advance("", 4)
            self.sample("controller-approach-end")

    def require_near(self):
        x, y = self.xy()
        native.require(-48 <= x-NPC_X < 48 and -48 <= y-NPC_Y < 48,
                       "Declared controller travel must reach the authored NPC")

    def setup(self):
        native.require(self.r(0x7E0010) in (7, 9) and self.r(0x7E0011) == 0,
                       "Setup requires existing stable private gameplay")
        self.ordinary_form()
        for address, value in SETUP.items():
            self.write(address, value, "Explicit daytime Garo acquisition starting fixture")
        self.warp_to_desert()
        x, y = self.xy()
        native.require(abs(x-NPC_X) >= 48 or abs(y-NPC_Y) >= 48, "Setup landing is not distant from Garo")
        self.sample("distant-start"); self.shot("garo-distant-start")
        self.play_song(1, "distant-healing")
        self.check("Distant Healing grants no mask", self.r(OWNED), 0)
        self.check("Distant Healing leaves song flag for stale-song control", self.r(0x7E00FE), 1)
        self.shot("garo-distant-healing-rejected")
        self.result["next_action"] = "Approach Garo by controller, then run acquire; keep ownership0 and do not play a new song en route."

    def acquire(self):
        self.area_ready(); self.ordinary_form()
        self.check("Acquisition starts without mask", self.r(OWNED), 0)
        self.check("Stale Healing fixture before approach", (self.r(0x7E00FE), self.r(0x7E03F0)), (1, 0))
        self.approach(); self.area_ready(); self.require_near()
        self.check("Stale Healing retained after approach", (self.r(0x7E00FE), self.r(0x7E03F0)), (1, 0))
        self.advance("", 4)
        self.check("Approach does not consume stale distant Healing", self.r(OWNED), 0)
        npcs = [s for s in self.actors() if s["type"] == 0x57]
        native.require(len(npcs) == 1 and npcs[0]["state"] == 9, "Need the real active placed Garo")
        native.require(npcs[0]["layer"] == self.r(0x7E00EE), "Garo and Link are on different layers")
        self.check("Placed Garo coordinates", (npcs[0]["x"], npcs[0]["y"]), (NPC_X, NPC_Y))
        self.sample("near-stale-song-rejected"); self.shot("garo-near-before")
        self.play_song(2, "near-storms")
        self.check("Storms grants no mask", self.r(OWNED), 0)
        self.check("Storms leaves non-Healing song flag", self.r(0x7E00FE), 3)
        self.play_song(1, "near-healing")
        self.check("Fresh nearby Healing grants exactly one mask", self.r(OWNED), 1)
        self.check("Successful Healing consumes SongFlag", self.r(0x7E00FE), 0)
        self.check("Successful Healing despawns Garo", [s for s in self.actors() if s["type"] == 0x57], [])
        self.check("Reward does not auto-bind", self.r(BOUND), 0)
        self.shot("garo-acquired")
        self.tap("Start"); self.wait_screen("items")
        self.tap("L"); self.wait_screen("equipment")
        self.equipment_slot(5); self.tap("A")
        self.check("Controller binds acquired mask", self.r(BOUND), 6)
        self.shot("garo-acquired-equipment")
        self.tap("Start"); self.wait_screen("gameplay"); self.tap("R")
        self.until(lambda: self.r(0x7E02B2) == 8 and self.r(0x7E02E1) == 0
                   and not self.ancilla(0x23), "R did not equip earned Garo mask", 240)
        self.sample("acquired-mask-equipped"); self.shot("garo-acquired-form")

    def save_reopen(self):
        native.require(bool(self.a.route) or self.a.noclip_approach, "save-reopen needs a travel fixture to inspect the NPC location after reload")
        self.check("Save phase requires acquired mask", self.r(OWNED), 1)
        self.check("Save phase requires acquired binding", self.r(BOUND), 6)
        self.ordinary_form(); self.shot("garo-before-save")
        self.tap("Select", 90); self.shot("garo-save-choice")
        for _ in range(4):
            if self.r(0x7E1CE8) == 1: break
            self.tap("Down", 15)
        self.check("Controller selects Save and Quit", self.r(0x7E1CE8), 1)
        self.shot("garo-save-selected"); self.tap("A", 180)
        for _ in range(30):
            if (self.r(0x7E0010), self.r(0x7E0011)) == (0, 8): break
            self.advance("", 60)
        native.require((self.r(0x7E0010), self.r(0x7E0011)) == (0, 8),
                       "Native Save/Quit did not return to title")
        saved = bytes(self.b.read_block(0, 8192, "SnesSaveRam"))
        native.require(len(saved) == 8192, "Short native SRAM read")
        (self.a.output/"native-save.srm").write_bytes(saved)
        self.check_owner(); native.require(self.b.reset(), "Private reset rejected"); self.pause_settle()
        self.advance("", 120)  # Let the asynchronous reset leave the old title state.
        for _ in range(60):
            if (self.r(0x7E0010), self.r(0x7E0011)) == (0, 8): break
            self.advance("", 60)
        native.require((self.r(0x7E0010), self.r(0x7E0011)) == (0, 8), "Reset title not ready")
        self.tap("Start", 120)
        self.until(lambda: (self.r(0x7E0010), self.r(0x7E0011)) == (1, 5), "File select not ready", 400)
        self.tap("Start", 180); self.wait_screen("gameplay")
        self.check("Native reopen preserves Garo ownership", self.r(OWNED), 1)
        self.check("Native reopen preserves Garo binding", self.r(BOUND), 6)
        self.shot("garo-fresh-reopen")
        self.warp_to_desert(); self.approach(); self.area_ready(); self.require_near()
        self.advance("", 8)
        self.check("Owned Garo stays absent at its loaded placement", [s for s in self.actors() if s["type"] == 0x57], [])
        self.play_song(1, "repeat-healing")
        self.check("Repeat Healing does not change ownership", self.r(OWNED), 1)
        self.check("No NPC consumes repeat Healing", self.r(0x7E00FE), 1)
        self.sample("reentry-no-duplicate"); self.shot("garo-reentry-no-duplicate")

    def run(self):
        getattr(self, self.a.phase.replace("-", "_"))()
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--phase", choices=("setup", "acquire", "save-reopen"), default="setup")
    parser.add_argument("--approach-route", type=Path)
    parser.add_argument("--noclip-approach", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output, "Need --execute-fixtures, --session and --output")
    values = json.loads(args.session.read_text())
    for key in ("status_file", "owner_file", "owned_rom", "symbols", "client_root"):
        values[key] = Path(values[key])
    route = json.loads(args.approach_route.read_text()) if args.approach_route else []
    native.require(isinstance(route, list) and len(route) <= 80, "Route must be a bounded JSON list")
    for step in route:
        native.require(isinstance(step, dict) and set(step) == {"buttons", "frames"}
                       and isinstance(step["buttons"], str) and isinstance(step["frames"], int)
                       and 1 <= step["frames"] <= 120
                       and all(b in ("Up", "Down", "Left", "Right", "") for b in step["buttons"].split(",")),
                       "Route accepts only directional controller steps, 1..120 frames each")
    native.require(sum(s["frames"] for s in route) <= 1800, "Approach route exceeds 1800 frames")
    native.require(args.phase != "save-reopen" or route or args.noclip_approach, "save-reopen requires --approach-route")
    values.update(output=args.output, phase=args.phase, root=args.root, route=route, noclip_approach=args.noclip_approach)
    identity = SimpleNamespace(**values)
    native.require(identity.socket.startswith("/tmp/mesen2-new-items-")
                   and identity.owner.startswith("codex-new-items-") and "oos-rc-play" not in str(values),
                   "Only the owned new-items private session is admitted")
    native.require(native.digest(identity.owned_rom.read_bytes()) == identity.rom_sha256, "ROM hash differs from session")
    native.require(native.digest(identity.symbols.read_bytes()) == identity.symbols_sha256, "Symbols hash differs from session")
    identity.rom_sha1 = native.digest(identity.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(identity.pid)], text=True)
    native.require("--headless" in command and str(identity.owned_rom) in command, "PID is not the recorded private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(identity.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = GaroAcquisitionFlow(identity, MesenBridge(identity.socket, auto_reconnect=False, max_retries=0))
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused private session without breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.check_owner(); flow.input(""); flow.pause_settle()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output/"RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str)+"\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output/"RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
