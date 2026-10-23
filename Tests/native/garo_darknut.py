#!/usr/bin/env python3
"""Garo parry/counter fixes and the armored Darknut ($1D subtype 1).

Attach-only. The caller launches one headless private Mesen2 instance, boots
file 1 into Link's House room 0104 and writes SESSION.json (same shape as
garo_combat_fixture.py). Fixture writes: Bow/arrows, Armor Ring slot, mail,
HP, Garo/sword ownership, Sword 1 for the multi-hit armor case, and one inactive sprite slot (type, subtype,
position, facing, alert timer). Link, guard, counter and sword state are only
driven by controller input.

--expect candidate asserts the fixed behavior. --expect baseline runs the
same cases on the pre-fix ROM and asserts both original bugs reproduce;
there the subtype byte is ignored, so the armored cases are controls that
show the arrow and the slash reach the knight.
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
DARKNUT, KNIFE_GUARD = 0x1D, 0x4B
GUARD, COUNTER, COOLDOWN = garo.GUARD, garo.COUNTER, garo.COOLDOWN
RING1, MAIL, BOW, ARROWS = 0x7EF3A3, 0x7EF35B, 0x7EF340, 0x7EF377
HP, MAXHP = menu.HP, menu.MAXHP
ARMOR_RING, BLUE_MAIL = 3, 1
SFX2 = 0x7E012E
SUBTYPE, ACTION, ALERT = 0x0E30, 0x0D80, 0x0EE0
ARROW_ANCILLA = 0x09
DARKNUT_CHR = {0xE0, 0xE2, 0xE4, 0xE6, 0xE8, 0xEF, 0xFF}
ALLOWED = prototype.ALLOWED | {RING1, MAIL, BOW, ARROWS, HP}


def describe():
    return dict(native_executed=False, room="0104",
                cases=["armored-arrow: Bow shot at an armored knight's back",
                       "armored-sword: ordinary B slash at an armored knight's back",
                       "ordinary-sword: same slash at a subtype 0 knight (control)",
                       "pointblank-counter: Garo parry then immediate Y on native $4B",
                       "armor-ring-parry: Armor Ring + blue mail, 1-damage Darknut contact",
                       "armored-counters: Garo parry/counter cycles until the armored knight dies"],
                fixture_writes="Bow/arrows, RingSlot1, mail, HP, Garo/sword ownership, Sword 1 for armor cycles; one owned sprite slot",
                prohibited_writes=["CPU", "Link position", "guard/counter timers", "damage queue",
                                   "module", "room", "story", "SRAM", "save state", "ROM"],
                limitations=["Link's House has no Darknut graphics; palette is read from OAM bits only",
                             "Knight placement and facing are fixture writes; collision and damage are native"])


class GaroDarknutFlow(garo.GaroCombatFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 900
        self.expect = args.expect
        self.result["scope"] = describe()
        self.result["scope"]["expect"] = self.expect
        self.watches = set()

    # Inventory/ring/mail/HP fixture bytes; sprite bytes go through actor_write.
    def write(self, address, value, reason):
        self.check_owner()
        native.require(address in ALLOWED and 0 <= value <= 255 and self.paused(),
                       f"Fixture write outside contract: {address:06X}")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Fixture readback differs")

    def heal(self):
        if self.r(HP) < self.r(MAXHP):
            self.write(HP, self.r(MAXHP), "Restore HP between cases")

    def watch(self, address):
        reply = self.b.mem_watch_add(address, 1, 128)
        native.require(reply.get("success"), "Native watch rejected: " + str(reply))
        value = reply.get("data", {})
        value = json.loads(value) if isinstance(value, str) else value
        ident = native.number(value["watch_id"])
        self.watches.add(ident)
        return ident

    def blame(self, ident):
        reply = self.b.mem_blame(watch_id=ident)
        value = reply.get("data", {})
        value = json.loads(value) if isinstance(value, str) else value
        self.b.mem_watch_remove(ident)
        self.watches.discard(ident)
        return [dict(pc=f"{native.number(w['pc']):06X}", value=native.number(w["value"]))
                for w in (value or {}).get("writes", [])]

    def enemy_x(self):
        return self.r(0x7E0D10 + self.slot) | self.r(0x7E0D30 + self.slot) << 8

    def gap(self):
        return self.xy()[0] - self.enemy_x()

    def enemy_hp(self):
        return self.r(0x7E0E50 + self.slot)

    def dead(self):
        return self.r(0x7E0DD0 + self.slot) in (0, 6)

    def oam_palettes(self):
        oam = self.block(0x7E0800, 0x200)
        return sorted({(oam[i + 3] >> 1) & 7 for i in range(0, 0x200, 4)
                       if oam[i + 2] in DARKNUT_CHR and oam[i + 3] & 1 and oam[i + 1] < 0xF0})

    def room_for(self, gap):
        # The knight goes `gap` px left of Link; walk right by controller until it fits.
        for _ in range(90):
            if self.xy()[0] - gap >= 0x0930:
                return
            self.advance("Right", 1)
        native.require(self.xy()[0] - gap >= 0x0930, "No floor left of Link for the knight")

    def combat_start(self):
        # A successful contact/counter moves Link. Restore a common clear
        # start by controller before another actor is placed to his left.
        for axis, target, low, high in ((0, 0x0960, "Left", "Right"),
                                        (1, 0x2188, "Up", "Down")):
            for _ in range(160):
                value = self.xy()[axis]
                if abs(value - target) <= 1:
                    break
                self.advance(low if value > target else high, 1)
            else:
                native.require(False, "Controller could not reach the contact floor start")
        self.advance("", 2)
        self.assert_room()
        native.require(self.r(0x7E00EE) == 0, "Contact floor requires the lower layer")
        x, y = self.xy()
        tiles = self.block(0x7F2000, 0x2000)
        offsets = {((yy & 0x1F8) << 3) + ((xx & 0x1FF) >> 3)
                   for yy in range(y + 8, y + 24) for xx in range(x - 20, x + 16)}
        self.check("Live contact corridor is ordinary floor", sorted({tiles[i] for i in offsets}), [0])
        self.sample("contact-floor-start")

    def spawn(self, kind, gap, subtype=0, action=0):
        self.assert_room()
        native.require(self.slot is None, "Previous target must be removed")
        x, y = self.xy()
        native.require(0x0940 <= x < 0x09A0 and 0x2170 <= y < 0x21B0,
                       "Link is outside the declared open-floor corridor")
        enemy_x = x - gap
        native.require(0x0928 <= enemy_x < 0x09A0, "Knight would be outside room floor bounds")
        free = [i for i in range(15, -1, -1) if self.r(0x7E0000 + garo.STATE + i) == 0]
        native.require(bool(free), "No unused sprite slot")
        self.slot = free[0]
        addresses = [0x7E0000 + t + self.slot for t in garo.TABLES]
        addresses += [t + self.slot for t in garo.LONG_TABLES]
        self.saved_slot = {a: self.r(a) for a in addresses}
        for table in garo.TABLES:
            if table != garo.STATE:
                self.actor_write(table, 0, "Clear stale fields in one inactive fixture slot")
        # Subtype goes in before state 08 so the native prep sees it, as the room loader does.
        for table, value in ((garo.SPRTYPE, kind), (SUBTYPE, subtype),
                             (0x0D10, enemy_x & 255), (0x0D30, enemy_x >> 8),
                             (0x0D00, y & 255), (0x0D20, y >> 8),
                             (0x0F20, self.r(0x7E00EE)), (0x0BC0, 255), (garo.STATE, 8)):
            self.actor_write(table, value, "Declared knight placement/prep")
        self.advance("", 1)
        self.check("Native prep reaches active state", self.r(0x7E0000 + garo.STATE + self.slot), 9)
        self.actor_write(ACTION, action, "Knight facing: 0 right (toward Link), 1 left (away)")
        actor = dict(slot=self.slot, type=kind, subtype=subtype, position=[enemy_x, y],
                     health=self.enemy_hp(), defl_caa=self.r(0x7E0CAA + self.slot),
                     flags_e60=self.r(0x7E0E60 + self.slot), tiledie_b6b=self.r(0x7E0B6B + self.slot))
        self.result.setdefault("actors", []).append(actor)
        return actor

    def place(self, gap, action, reason):
        # Move the existing knight; keeps its health. Alert timer cleared so it walks, not chases.
        x, y = self.xy()
        enemy_x = x - gap
        native.require(0x0928 <= enemy_x < 0x09A0, "Placement outside room floor bounds")
        for table, value in ((0x0D10, enemy_x & 255), (0x0D30, enemy_x >> 8),
                             (0x0D00, y & 255), (0x0D20, y >> 8), (ACTION, action),
                             (ALERT, 0), (0x0DF0, 0), (0x0D40, 0), (0x0D50, 0),
                             (0x0F30, 0), (0x0F40, 0)):
            self.actor_write(table, value, reason)

    # ---- cases --------------------------------------------------------------

    def case(self, name, fn):
        entry = dict(name=name)
        self.result["cases"].append(entry)
        try:
            self.heal(); self.settle_combat(); self.combat_start()
            entry.update(fn())
            entry["completed"] = True
        except Exception as error:
            entry["error"] = repr(error)
            entry["last_check"] = (self.result["checks"] or [None])[-1]
        finally:
            for ident in list(self.watches):
                self.b.mem_watch_remove(ident)
                self.watches.discard(ident)
            self.input("")
            self.remove_target()
        return entry

    def select_bow(self):
        self.ready()
        self.until(lambda: self.r(0x7E02E1) == 0 and not self.ancilla(0x23),
                   "Existing transformation cloud did not finish", 220)
        if self.r(0x7E02B2) == 8:
            self.tap("R")
        self.until(lambda: self.r(0x7E02B2) in (0, 6) and self.r(0x7E02E1) == 0
                   and not self.ancilla(0x23), "Controller did not restore ordinary Link", 220)
        self.ready()
        if not self.r(ARROWS):
            self.write(ARROWS, 10, "Arrows for the arrow case")
        native.require(self.r(BOW) >= 1, "Seed file has no Bow")
        self.tap("Start"); self.wait_screen("items")
        self.pick(1)
        self.tap("Start"); self.wait_screen("gameplay")
        self.ready()
        native.require(self.r(0x7E02B2) in (0, 6) and self.r(0x7E02E1) == 0
                       and not self.ancilla(0x23), "Bow selected before ordinary form settled")
        self.check("Controller selects Bow", self.r(0x7E0202), 1)
        native.require(self.r(BOW) >= 1 and self.r(ARROWS) > 0, "Bow case needs a Bow and arrows")

    def armored_arrow(self):
        self.ready(); self.heal()
        self.room_for(48)
        self.spawn(DARKNUT, 48, subtype=1, action=1)
        self.advance("Left", 1); self.advance("", 2)
        native.require(self.r(0x7E02B2) in (0, 6) and self.r(0x7E02E1) == 0
                       and not self.ancilla(0x23) and self.r(0x7E0202) == 1
                       and self.r(BOW) >= 1 and self.r(ARROWS) > 0
                       and self.r(0x7E002F) == garo.FACING["Left"],
                       "Arrow trial requires ordinary Link aiming a selected, supplied Bow at the knight")
        native.require(not self.ancilla(ARROW_ANCILLA), "Arrow trial starts with an existing arrow")
        hp0, sfx = self.enemy_hp(), self.watch(SFX2)
        self.advance("Y", 1)
        arrow_frames, hps = int(bool(self.ancilla(ARROW_ANCILLA))), [self.enemy_hp()]
        for _ in range(40):
            self.advance("", 1)
            arrow_frames += bool(self.ancilla(ARROW_ANCILLA))
            hps.append(self.enemy_hp())
            if self.dead():
                break
        native.require(arrow_frames > 0, "Bow trial never spawned a native arrow ancilla")
        return dict(enemy_hp_before=hp0, enemy_hp_min=min(hps), arrow_frames=arrow_frames,
                    damaged=min(hps) < hp0 or self.dead(), sfx2_writes=self.blame(sfx),
                    oam_palettes=self.oam_palettes())

    def sword_from_behind(self, subtype):
        self.ready(); self.heal()
        self.room_for(40)
        self.spawn(DARKNUT, 40, subtype=subtype, action=1)
        for _ in range(40):
            if self.gap() <= 18:
                break
            self.advance("Left", 1)
        self.advance("", 1)
        hp0, gap0, sfx = self.enemy_hp(), self.gap(), self.watch(SFX2)
        palettes = self.oam_palettes()
        self.advance("B", 2)
        rows = []
        for _ in range(24):
            self.advance("", 1)
            rows.append(self.sample("sword-from-behind"))
        writes = self.blame(sfx)
        return dict(gap_at_slash=gap0, enemy_hp_before=hp0, enemy_hp_min=min(r["enemy_hp"] for r in rows),
                    damaged=any(r["enemy_hp"] < hp0 or r["enemy_state"] == 6 for r in rows),
                    slash=any(r["sword_state"] for r in rows),
                    clink=any(w["value"] & 0x3F == 5 for w in writes), sfx2_writes=writes,
                    oam_palettes=palettes)

    def pointblank_counter(self):
        # Native $4B, no Armor Ring: the parry itself works on both ROMs.
        if self.r(RING1):
            self.write(RING1, 0, "No ring for the point-blank case")
        self.heal()
        self.parry_counter()  # garo_combat_fixture immediate spacing; raises on a miss
        return dict(counter_damaged=True)

    def guarded_contact(self, toward="Left"):
        hp = self.r(HP)
        cache_watches = {axis: self.watch(address) for axis, address in
                         (("x", 0x7E0FAB), ("y", 0x7E0FAA))}
        rows = [self.open_guard_toward(toward)]
        for _ in range(14):
            if self.r(COUNTER):
                break
            self.advance(toward, 1)
            rows.append(self.sample("guarded-approach"))
        return dict(parried=0 < self.r(COUNTER) < 0x80, link_hp_lost=hp - self.r(HP),
                    knockback=any(r["recoil"] or r["recoil_flags"] for r in rows),
                    frames=len(rows), gap=self.gap(),
                    guard_weapon_cache_writes={axis: self.blame(watch)
                                               for axis, watch in cache_watches.items()},
                    # End-of-frame observations only. Another sprite can overwrite
                    # this shared cache later in the pass; these values cannot
                    # prove the cache contents at the Darknut contact call.
                    guard_weapon_cache_samples=[
                        dict(x=r["guard_weapon_offset_x"], y=r["guard_weapon_offset_y"])
                        for r in rows])

    def counter_swing(self, hp0):
        native.require(0 < self.r(COUNTER) < 0x80, "Counter swing needs an earned pending window")
        self.advance("", 2)
        self.advance("Y", 2)
        rows = [self.sample("counter-Y")]
        flag_seen = rows[0]["counter"] & 0x80 != 0
        for _ in range(20):
            self.advance("", 1)
            rows.append(self.sample("counter-slash"))
            flag_seen |= rows[-1]["counter"] & 0x80 != 0
        cleared = False
        for _ in range(30):
            if self.r(COUNTER) == 0:
                cleared = True
                break
            self.advance("", 1)
        return dict(slash=any(r["sword_state"] for r in rows), counter_flag_seen=flag_seen,
                    counter_flag_cleared=cleared,
                    damaged=any(r["enemy_hp"] < hp0 or r["enemy_state"] in (0, 6) for r in rows))

    def armor_ring_parry(self):
        self.write(RING1, ARMOR_RING, "Wear the Armor Ring")
        self.write(MAIL, BLUE_MAIL, "Blue mail: Darknut bump group 0 deals 1, the ring halves it to 0")
        self.heal(); self.settle_combat()
        self.spawn(DARKNUT, garo.CONTACT_START_GAP, subtype=0, action=0)
        hp0 = self.enemy_hp()
        out = self.guarded_contact()
        if out["parried"]:
            out["counter"] = self.counter_swing(hp0)
        self.write(RING1, 0, "Remove the Armor Ring")
        return out

    def armored_counters(self):
        self.heal(); self.settle_combat()
        # The all-items seed has Sword 4: one counter kills before armor can
        # be observed on a survivor. Native prep scales health with the sword.
        self.write(prototype.SWORD, 1, "Ordinary sword for a surviving armor-restoration cycle")
        self.check("Armor cycles use Sword 1", self.r(prototype.SWORD), 1)
        self.room_for(garo.CONTACT_START_GAP)
        self.spawn(DARKNUT, garo.CONTACT_START_GAP, subtype=1, action=0)
        self.check("Sword 1 knight has native health 4", self.enemy_hp(), 4)
        cycles = []
        for cycle in range(8):
            if self.dead():
                break
            if cycle:
                self.until(lambda: self.dead() or self.r(0x7E0EA0 + self.slot) == 0,
                           "Knight recoil did not end", 120)
                if self.dead():
                    break
                # A fixed 56px gap to the left can put the actor outside the
                # room after Link has approached. Park at a bounded point on
                # the right, facing away, before walking Link back to start.
                self.place(self.xy()[0] - 0x0990, 0, "Park knight at X0990 facing away between cycles")
                self.heal(); self.settle_combat()
                self.combat_start()
                self.place(garo.CONTACT_START_GAP, 0, "Knight 20 px left of Link, facing him")
            hp0 = self.enemy_hp()
            row = dict(cycle=cycle, enemy_hp_before=hp0,
                       armor_e60=self.r(0x7E0E60 + self.slot), armor_caa=self.r(0x7E0CAA + self.slot))
            row.update(self.guarded_contact())
            if row["parried"]:
                row["counter"] = self.counter_swing(hp0)
            row["enemy_hp_after"] = self.enemy_hp()
            row["dead"] = self.dead()
            if not row["dead"]:
                row["armor_restored"] = (self.r(0x7E0E60 + self.slot) & 0x40 != 0
                                         and self.r(0x7E0CAA + self.slot) & 0x04 != 0)
            cycles.append(row)
        return dict(cycles=cycles, died=self.dead(), oam_palettes=self.oam_palettes())

    # ---- verdict ------------------------------------------------------------

    def verdict(self, cases):
        c = {k: v for k, v in cases.items()}
        v = {}
        if self.expect == "candidate":
            v["all selected cases complete"] = bool(c) and all(
                case.get("completed") is True and "error" not in case for case in c.values())
            v["armored knight ignores arrows"] = (c["armored-arrow"].get("arrow_frames", 0) > 0
                                                  and c["armored-arrow"].get("damaged") is False)
            v["armored knight clinks a normal slash"] = (c["armored-sword"].get("slash") is True
                                                        and c["armored-sword"].get("damaged") is False
                                                        and c["armored-sword"].get("clink") is True)
            v["ordinary knight takes sword damage"] = c["ordinary-sword"].get("damaged") is True
            v["point-blank counter connects"] = c["pointblank-counter"].get("completed") is True
            ring = c["armor-ring-parry"]
            v["Armor Ring 1-damage contact parries"] = (ring.get("parried") is True
                                                       and ring.get("knockback") is False
                                                       and ring.get("link_hp_lost") == 0)
            cycles = c["armored-counters"].get("cycles", [])
            counter_cycles = bool(cycles) and all(
                row.get("parried") is True and row.get("counter", {}).get("slash") is True
                and row.get("counter", {}).get("damaged") is True for row in cycles)
            v["armored knight dies to Garo counters"] = (
                c["armored-counters"].get("died") is True and counter_cycles)
            v["counter flag set by the counter and cleared after"] = bool(cycles) and all(
                row.get("parried") is True and row.get("counter", {}).get("counter_flag_seen") is True
                and row.get("counter", {}).get("counter_flag_cleared") is True for row in cycles)
            survived = [row for row in cycles if row.get("dead") is False]
            v["armor restored after each counter"] = counter_cycles and bool(survived) and all(
                row.get("armor_restored") is True for row in survived)
        else:
            v["control: arrow reaches the knight"] = c["armored-arrow"].get("damaged") is True
            v["control: slash from behind reaches the knight"] = c["armored-sword"].get("damaged") is True
            v["control: ordinary knight takes sword damage"] = c["ordinary-sword"].get("damaged") is True
            pb = c["pointblank-counter"]
            v["bug reproduces: point-blank counter misses"] = (
                "error" in pb and (pb.get("last_check") or {}).get("name") == "Native counter damages target")
            ring = c["armor-ring-parry"]
            v["bug reproduces: Armor Ring contact does not parry"] = (ring.get("parried") is False
                                                                    and ring.get("knockback") is True)
        return v

    def run(self):
        self.assert_room()
        protected = {str(a): self.r(a) for a in (0x7EF3C5, 0x7EF3C6, 0x7EF3D6, 0x7EF37A, 0x7EF374)}
        self.select_bow()
        cases = {}
        for name, fn in (("armored-arrow", self.armored_arrow),
                         ("armored-sword", lambda: self.sword_from_behind(1)),
                         ("ordinary-sword", lambda: self.sword_from_behind(0))):
            cases[name] = self.case(name, fn)
        self.bind_garo()
        for name, fn in (("pointblank-counter", self.pointblank_counter),
                         ("armor-ring-parry", self.armor_ring_parry),
                         ("armored-counters", self.armored_counters)):
            if name == "armored-counters" and self.expect == "baseline":
                continue
            cases[name] = self.case(name, fn)
        self.result["verdict"] = self.verdict(cases)
        self.check("Story/progression unchanged",
                   {str(a): self.r(a) for a in (0x7EF3C5, 0x7EF3C6, 0x7EF3D6, 0x7EF37A, 0x7EF374)}, protected)
        self.result["runtime_checks_passed"] = all(self.result["verdict"].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path, required="--describe" not in sys.argv)
    parser.add_argument("--support-root", type=Path)
    parser.add_argument("--expect", choices=("candidate", "baseline"), default="candidate")
    parser.add_argument("--output", type=Path, default=ROOT / "native/garo-darknut")
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
    flow = GaroDarknutFlow(identity, MesenBridge(identity.socket, auto_reconnect=False, max_retries=0))
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
                flow.check_owner(); flow.input(""); flow.b.pause()
                pause_deadline = time.monotonic() + 5
                while not flow.paused() and time.monotonic() < pause_deadline:
                    time.sleep(.01)
                flow.remove_target()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], verdict=flow.result.get("verdict"),
                          error=flow.result.get("error"), result=str(args.output / "RESULT.json")), indent=2))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
