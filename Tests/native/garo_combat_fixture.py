#!/usr/bin/env python3
"""Attach-only real-contact Garo fixture; --describe performs no IPC.

No launch, CPU injection, ROM/SRAM/save-state, Link-position, health, guard,
counter, damage-queue or immunity writes. One originally inactive sprite slot
is a declared enemy fixture. Its state 08 runs native property initialization;
its idle timer and velocity then keep the contact target stationary. The hut
does not have guard graphics, so screenshots do not qualify enemy artwork.
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
SESSION_PATH = ROOT / "SESSION.json"
if "--support-root" in sys.argv:
    sys.path.insert(0, sys.argv[sys.argv.index("--support-root") + 1])
elif "--session" in sys.argv:
    _session = json.loads(Path(sys.argv[sys.argv.index("--session") + 1]).read_text())
    sys.path.insert(0, _session["support_root"])
import new_items_prototype as prototype

native, menu = prototype.native, prototype.menu
TYPE = 0x4B  # native Green Knife Guard: no shield parry or prison capture path
CONTACT_START_GAP = 20
GUARD, COUNTER, COOLDOWN = 0x7E07EE, 0x7E07EF, 0x7E07F0
LUNGE_TIMER = 0x7E07FF
FACING = {"Up": 0, "Down": 2, "Left": 4, "Right": 6}
STATE, SPRTYPE = 0x0DD0, 0x0E20
# Native property reset/load destinations plus actor identity/context. Every
# entry is a per-sprite 16-byte array; no global state lies in this whitelist.
TABLES = (0x0B58, 0x0B89, 0x0BA0, 0x0BB0, 0x0BC0, 0x0BE0,
          0x0C9A, 0x0CAA, 0x0CBA, 0x0CD2, 0x0CE2,
          *range(0x0D00, 0x0F50 + 1, 0x10), 0x0F60, 0x0F70, 0x0F80,
          0x0F90, 0x1CC0)
LONG_TABLES = (0x7FF9C2, 0x7FFA1C, 0x7FFA2C, 0x7FFA3C, 0x7FFA4C)
PROTECTED = prototype.PROTECTED


def describe():
    return dict(native_executed=False, room="0104", sprite="4B Green Knife Guard",
                initial_slot_state=8, native_properties=True,
                actor_fixture="Unused slot, Link layer, 20 px left; native prep then idle timer FF and velocity 0",
                position_bounds="Link X0940..099F, Y2170..21AF; enemy X0928..099F",
                checks=["Controller binds sixth Garo mask and transforms with R",
                        "Face target, release direction, neutral Y guard, then move into real enemy contact",
                        "Y consumes earned counter, begins native sword slash and damages the target",
                        "Expired guard allows the same native enemy to reduce Link HP"],
                fixture_writes="Garo/sword ownership only when absent; one owned sprite slot and its native auxiliary arrays",
                prohibited_writes=["CPU", "Link position", "HP", "damage queue", "guard/counter timers",
                                   "immunity", "module", "room", "story", "SRAM", "save state", "ROM"],
                limitations=["Hut collision fixture, not Goron Mines acquisition or real encounter acceptance",
                             "Guard artwork is invalid in the hut graphics group",
                             "Stationary AI is declared; native hitbox, damage and sword collision are unchanged"])


class GaroCombatFlow(prototype.NewItemsFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 360
        self.result["scope"] = describe()
        self.counter_spacing = args.counter_spacing
        self.result["scope"]["counter_spacing"] = self.counter_spacing
        if self.counter_spacing == "controller":
            self.result["scope"]["known_limitation"] = (
                "Immediate Y at a 3px origin gap missed in native/garo-combat-4/RESULT.json: "
                "native left sword hitboxes extend past the overlapping enemy. This separate "
                "trial backs away and faces the enemy by controller before spending the same earned counter.")
        self.slot = None
        self.saved_slot = {}

    def xy(self):
        return (int.from_bytes(self.block(0x7E0022, 2), "little"),
                int.from_bytes(self.block(0x7E0020, 2), "little"))

    def assert_room(self):
        native.require(self.screen() == "gameplay" and self.r(0x7E0010) == 7
                       and self.r(0x7E0011) == 0 and self.r(0x7E001B) == 1
                       and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104,
                       "Fixture requires stable Link's House room 0104")

    def actor_write(self, table, value, reason, long=False):
        native.require(self.slot is not None, "No owned actor slot")
        address = (table if long else 0x7E0000 + table) + self.slot
        native.require(address in self.saved_slot, "Address is outside owned actor tables")
        self.check_owner()
        native.require(self.paused() and 0 <= value <= 255, "Actor write requires pause/byte")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Actor fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Actor fixture readback mismatch")

    def spawn_target(self):
        self.assert_room()
        native.require(self.slot is None, "Previous target must be removed")
        x, y = self.xy()
        native.require(0x0940 <= x < 0x09A0 and 0x2170 <= y < 0x21B0,
                       "Link is outside declared open-floor corridor; reposition by controller")
        # Hitbox $12 extends enemy X+2..X+14; Link is X+4..X+12.
        # Contact from the right starts at a <=10 px origin gap. Starting at
        # 20 leaves movement plus the native 4-frame contact stagger inside
        # the 12-frame guard; the original 26px setup reached it too late.
        enemy_x = x - CONTACT_START_GAP
        native.require(0x0928 <= enemy_x < 0x09A0, "Enemy would be outside room floor bounds")
        free = [i for i in range(15, -1, -1) if self.r(0x7E0000 + STATE + i) == 0]
        native.require(bool(free), "No unused sprite slot for controlled contact fixture")
        self.slot = free[0]
        addresses = [0x7E0000 + t + self.slot for t in TABLES]
        addresses += [t + self.slot for t in LONG_TABLES]
        self.saved_slot = {a: self.r(a) for a in addresses}
        hp = self.r(menu.HP)
        # The slot is inactive throughout setup. Native state 08, not a manual
        # property clone or direct CPU call, initializes its harmful properties.
        for table in TABLES:
            if table != STATE:
                self.actor_write(table, 0, "Clear stale fields in one inactive fixture slot")
        for table, value in ((SPRTYPE, TYPE), (0x0D10, enemy_x & 255), (0x0D30, enemy_x >> 8),
                             (0x0D00, y & 255), (0x0D20, y >> 8),
                             (0x0F20, self.r(0x7E00EE)), (0x0BC0, 255), (STATE, 8)):
            self.actor_write(table, value, "Declared native enemy placement/prep")
        self.advance("", 1)
        self.check("Native enemy prep reaches active state", self.r(0x7E0000 + STATE + self.slot), 9)
        self.check("Distant enemy prep causes no Link damage", self.r(menu.HP), hp)
        # GreenKnifeGuard_Idle does not move until this timer expires. Damage
        # checks precede its idle logic, so real contacts remain active.
        for table, value in ((0x0D80, 0), (0x0D40, 0), (0x0D50, 0),
                             (0x0DF0, 255), (0x0DE0, 0), (0x0EB0, 0)):
            self.actor_write(table, value, "Stationary enemy AI fixture; collision remains native")
        self.result.setdefault("actors", []).append(dict(slot=self.slot, type=TYPE,
            position=[enemy_x, y], layer=self.r(0x7E00EE), native_health=self.r(0x7E0E50 + self.slot),
            native_hitbox=self.r(0x7E0F60 + self.slot), native_bump=self.r(0x7E0CD2 + self.slot),
            native_oam_harm=self.r(0x7E0E40 + self.slot)))
        native.require(not self.r(0x7E0E40 + self.slot) & 0x80, "Native target is harmless")

    def remove_target(self):
        if self.slot is None:
            return
        self.actor_write(STATE, 0, "Deactivate owned fixture before restoring inactive slot")
        for address, value in self.saved_slot.items():
            if address == 0x7E0000 + STATE + self.slot:
                continue
            is_long = address >= 0x7F0000
            table = address - self.slot if is_long else address - self.slot - 0x7E0000
            self.actor_write(table, value, "Restore original inactive-slot byte", long=is_long)
        self.check("Fixture slot returns inactive", self.r(0x7E0000 + STATE + self.slot), 0)
        self.result["fixture_cleanup"].append(dict(slot=self.slot, restored=True))
        self.slot, self.saved_slot = None, {}

    def sample(self, label):
        state = dict(label=label, position=self.xy(), hp=self.r(menu.HP),
                     guard=self.r(GUARD), counter=self.r(COUNTER), cooldown=self.r(COOLDOWN),
                     damage_queue=self.r(0x7E0373), recovery=self.r(0x7E031F),
                     recoil=self.r(0x7E0046), sword_state=self.r(0x7E003C),
                     item_flags=self.r(0x7E003A), buttons_new=self.r(0x7E00F4),
                     buttons_held=self.r(0x7E00F0), mask=self.r(0x7E02B2),
                     facing=self.r(0x7E002F), weapon_y=self.r(0x7E0044),
                     weapon_x=self.r(0x7E0045), recoil_flags=self.r(0x7E004D),
                     guard_weapon_offset_y=self.r(0x7E0FAA),
                     guard_weapon_offset_x=self.r(0x7E0FAB),
                     action_state=self.r(0x7E0050), dash_state=self.r(0x7E0372),
                     link_state=self.r(0x7E005D), lunge_timer=self.r(LUNGE_TIMER))
        if self.slot is not None:
            state.update(enemy_state=self.r(0x7E0DD0 + self.slot),
                         enemy_hp=self.r(0x7E0E50 + self.slot),
                         enemy_damage=self.r(0x7E0CE2 + self.slot),
                         enemy_recoil=self.r(0x7E0EA0 + self.slot),
                         enemy_property_caa=self.r(0x7E0CAA + self.slot),
                         enemy_property_e60=self.r(0x7E0E60 + self.slot),
                         enemy_x=self.r(0x7E0D10 + self.slot) | self.r(0x7E0D30 + self.slot) << 8,
                         frame_low=self.r(0x7E001A))
        self.result.setdefault("trace", []).append(state)
        return state

    def settle_combat(self):
        self.ready()
        # PlayerTransform's native cloud temporarily freezes movement via
        # $02E1 even after the form and Link-state bytes look ready.
        self.until(lambda: self.r(0x7E02E1) == 0 and not self.ancilla(0x23),
                   "Transformation cloud/movement freeze did not finish", 220)
        self.until(lambda: all(self.r(a) == 0 for a in (GUARD, COUNTER, COOLDOWN,
                   0x7E031F, 0x7E0046, 0x7E003C, 0x7E0373)), "Combat recovery did not expire", 160)
        native.require(self.r(0x7E037B) == 0 and self.r(0x7E0055) == 0,
                       "Native damage suppression/cape is active; do not clear it by fixture")
        native.require(self.r(menu.HP) >= 16, "Need at least two hearts for damage-on control")

    def bind_garo(self):
        if self.r(0x7EF3AF) != 1:
            self.write(0x7EF3AF, 1, "Explicit Garo prototype ownership fixture")
        if not 1 <= self.r(prototype.SWORD) <= 4:
            self.write(prototype.SWORD, 1, "Ordinary sword for native counter")
        if self.r(0x7E02B2) == 8:
            self.until(lambda: self.r(0x7E02E1) == 0 and not self.ancilla(0x23),
                       "Existing Garo transformation cloud did not finish", 220)
            return
        native.require(self.r(0x7E02B2) in (0, 6) and self.r(0x7E0055) == 0,
                       "Start as ordinary Link or existing Garo")
        self.tap("Start"); self.wait_screen("items")
        self.tap("L"); self.wait_screen("equipment")
        for _ in range(4):
            if self.r(menu.CURSOR) < 6: break
            self.tap("Up")
        for _ in range(6):
            if self.r(menu.CURSOR) == 5: break
            self.tap("Right")
        self.check("Controller selects Garo", self.r(menu.CURSOR), 5)
        self.tap("A")
        self.check("Controller binds Garo", self.r(0x7EF3A8), 6)
        self.tap("Start"); self.wait_screen("gameplay")
        self.tap("R")
        self.until(lambda: self.r(0x7E02B2) == 8 and self.r(0x7E005D) == 0
                   and self.r(0x7E02E1) == 0 and not self.ancilla(0x23),
                   "Controller did not enter Garo", 220)

    def open_guard_toward(self, toward="Left"):
        native.require(toward in FACING, "Guard needs one cardinal facing")
        # INPUT is applied at the controller poll after vblank; one FRAME can
        # finish before ALTTP publishes that input to F0/F4. Match tap()'s
        # two-frame press/release before observing or replacing an edge.
        self.advance(toward, 2)
        self.advance("", 2)
        native.require(self.r(0x7E002F) == FACING[toward], "Controller did not face the contact target")
        native.require(self.r(COUNTER) == 0, "Guard trial starts with an existing counter")
        # Y with the facing direction held is the lunge gesture on PR264.
        self.advance("Y", 2)
        row = self.sample("guard-open")
        native.require(row["guard"] > 0, "Neutral Y did not open the guard")
        native.require(row["mask"] == 8 and row["facing"] == FACING[toward]
                       and row["buttons_held"] & 0x0F == 0,
                       "Guard did not open in Garo facing the target with direction released")
        native.require(row["link_state"] == 0 and row["dash_state"] == 0
                       and row["lunge_timer"] == 0, "Guard trial entered a dash/lunge")
        return row

    def parry_counter(self):
        self.settle_combat(); self.spawn_target()
        hp, enemy_hp = self.r(menu.HP), self.r(0x7E0E50 + self.slot)
        self.open_guard_toward()
        for _ in range(12):
            if self.r(COUNTER): break
            self.advance("Left", 1); self.sample("approach-guarded")
            native.require(self.r(menu.HP) == hp, "Real contact damaged Link during guard trial")
        native.require(0 < self.r(COUNTER) < 0x80, "No native contact parry; inspect spacing trace")
        self.check("Successful contact preserves HP", self.r(menu.HP), hp)
        self.check("Successful contact consumes guard", self.r(GUARD), 0)
        self.check("Successful contact clears queued damage", self.r(0x7E0373), 0)
        self.shot("garo-real-contact-parry")
        if self.counter_spacing == "controller":
            enemy_x = self.r(0x7E0D10 + self.slot) | self.r(0x7E0D30 + self.slot) << 8
            # Native sword tips miss an enemy already inside Link's body.
            # Keep the immediate trial unchanged; this separately labeled
            # control backs outside contact using only normal movement.
            for _ in range(14):
                if self.xy()[0] - enemy_x >= 16: break
                native.require(self.r(COUNTER) > 0, "Counter expired during controller spacing")
                self.advance("Right", 1)
                self.sample("counter-controller-backstep")
                native.require(self.r(menu.HP) == hp, "Spacing control took contact damage")
            native.require(self.xy()[0] - enemy_x >= 16, "Controller did not reach sword spacing")
            self.advance("Left", 1)
            self.advance("", 1)
            spaced = self.sample("counter-controller-facing")
            native.require(spaced["facing"] == 4 and spaced["counter"] > 0,
                           "Controller did not face target inside earned counter window")
            native.require(11 <= self.xy()[0] - enemy_x <= 22,
                           "Controller-spaced counter is outside native sword range")
        self.advance("", 2)  # ensure a fresh Y edge, without moving Link
        self.advance("Y", 2)
        after = self.sample("counter-Y")
        # Current CounterInput replaces the pending window with live-slash bit
        # 7; pre-flag controls cleared the byte. Neither retains timer bits.
        self.check("Y consumes earned counter", after["counter"] & 0x7F, 0)
        slash = after["sword_state"] != 0
        damaged = after["enemy_hp"] < enemy_hp or after["enemy_damage"] != 0
        for _ in range(18):
            self.advance("", 1)
            row = self.sample("native-counter-slash")
            slash |= row["sword_state"] != 0
            damaged |= row["enemy_hp"] < enemy_hp or row["enemy_damage"] != 0 or row["enemy_state"] == 6
            if slash and damaged: break
        self.check("Counter starts native sword slash", slash, True)
        self.check("Native counter damages target", damaged, True)
        self.until(lambda: self.r(COUNTER) == 0,
                   "Counter window/live-slash flag did not clear after the slash", 60)
        self.check("Counter state clears after the slash", self.r(COUNTER), 0)
        self.shot("garo-counter-hit")
        self.remove_target()

    def expired_guard_control(self):
        self.settle_combat(); self.spawn_target()
        hp = self.r(menu.HP)
        self.advance("Y", 1)
        native.require(self.r(GUARD) > 0, "Control never opened a guard")
        self.advance("", 16)
        self.check("Control guard expired before approach", self.r(GUARD), 0)
        self.check("Distant target has not hurt Link", self.r(menu.HP), hp)
        for _ in range(24):
            self.advance("Left", 1)
            row = self.sample("approach-after-expiry")
            if row["hp"] < hp: break
        native.require(self.r(menu.HP) < hp, "Expired guard did not allow real contact damage")
        self.check("Expired guard grants no counter", self.r(COUNTER), 0)
        self.shot("garo-expired-guard-damage")
        self.remove_target()

    def run(self):
        self.assert_room()
        # Reject a different/custom enemy implementation before any mutation.
        for address, expected in ((0x05B5FC, bytes.fromhex("a2bc")),
                                  (0x0686F1, bytes.fromhex("818b")),
                                  (0x05BCA2, bytes.fromhex("bd800e29084a7de0"))):
            pc = native.pc_offset(address)
            native.require(self.rom[pc:pc + len(expected)] == expected, "Native $4B contract differs")
        protected = {str(a): self.r(a) for a in PROTECTED}
        self.bind_garo()
        self.parry_counter()
        self.expired_guard_control()
        self.check("Story/rings/progression unchanged", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path, default=SESSION_PATH)
    parser.add_argument("--support-root", type=Path)
    parser.add_argument("--counter-spacing", choices=("immediate", "controller"), default="immediate")
    parser.add_argument("--output", type=Path, default=ROOT / "native/garo-combat")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures, "Use --describe or explicitly --execute-fixtures")
    session = json.loads(args.session.read_text())
    values = dict(session)
    for key in ("status_file", "owner_file", "owned_rom", "symbols"):
        values[key] = Path(values[key])
    values["output"] = args.output
    values["counter_spacing"] = args.counter_spacing
    identity = SimpleNamespace(**values)
    native.require(identity.socket.startswith("/tmp/mesen2-new-items-")
                   and identity.owner.startswith("codex-new-items-"), "Wrong private-session family")
    native.require(native.digest(identity.owned_rom.read_bytes()) == identity.rom_sha256,
                   "Private ROM hash differs from SESSION.json")
    native.require(native.digest(identity.symbols.read_bytes()) == identity.symbols_sha256,
                   "Symbols hash differs from SESSION.json")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(identity.pid)], text=True)
    native.require("--headless" in command and str(identity.owned_rom) in command,
                   "PID is not the recorded private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, session["client_root"])
    from mesen2_client_lib.bridge import MesenBridge
    flow = GaroCombatFlow(identity, MesenBridge(identity.socket, auto_reconnect=False, max_retries=0))
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
                # pause() acknowledges the command before the CPU has stopped.
                pause_deadline = time.monotonic() + 5
                while not flow.paused() and time.monotonic() < pause_deadline:
                    time.sleep(.01)
                native.require(flow.paused(), "Cleanup pause did not settle")
                flow.remove_target()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
