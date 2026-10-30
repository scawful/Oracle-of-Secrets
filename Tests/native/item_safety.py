#!/usr/bin/env python3
"""Attach-only item safety regressions, using the maintained native fixture API.

The supervisor owns the exact private ROM/process/lease and cold House0104
baseline. Each case reloads only that same-ROM baseline, never as save-file
proof. Controller input reaches the actual menu/item calls. Paused fixtures
declare inventory, a fishing bite/session, actor occupancy and counter canaries.
No CPU, Link position, room, story, ROM or battery SRAM writes are made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time

sys.dont_write_bytecode = True
import quest_collectibles as menu

native = menu.native
MODE, FLOATER = 0x7F5BA2, 0x7F5BA3
SPRITES, SPRITE_SIZE = 0x7E0B00, 0x500
INVENTORY = {0x7EF351, 0x7EF34D, 0x7EF34E, 0x7EF35C, 0x7EF3A2}
TRANSIENT = {MODE, FLOATER, 0x7E030D, 0x7E0317, 0x7E0321, 0x7E032B,
             0x7E001C, 0x7E0435, 0x7E044C, 0x7E044D}
ACTOR_TABLES = (0xDD0, 0xDA0, 0xDB0, 0xE20)


class ItemSafetyFlow(menu.QuestFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.fixed = args.expect == "candidate"
        self.deadline = time.monotonic() + 480
        self.baseline = args.output / "same-rom-house.mss"
        self.result["scope"] = __doc__

    def write(self, address, value, reason):
        actor = any(0x7E0000 + table <= address < 0x7E0010 + table
                    for table in ACTOR_TABLES)
        native.require(address in INVENTORY | TRANSIENT or actor,
                       f"Fixture address outside item-safety contract: {address:06X}")
        self.check_owner()
        native.require(self.paused() and 0 <= value <= 255, "Fixture needs paused CPU and byte value")
        before = self.r(address)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        self.check(f"fixture {address:06X}", self.r(address), value)
        self.result["writes"].append(dict(address=f"{address:06X}", before=before,
                                          value=value, reason=reason))

    def reset_case(self, name):
        native.require(not self.breakpoints, "Case leaked a breakpoint")
        self.input("")
        native.require(self.b.load_state(path=str(self.baseline)), "Own same-ROM baseline reload rejected")
        # Load can recreate the debugger. Its first CPU/memory request clears
        # Pause, so instantiate it before requesting and confirming Pause.
        native.require(bool(self.b.get_cpu_state()), "Debugger unavailable after baseline reload")
        native.require(self.b.pause(), "Pause after own baseline rejected")
        until = min(self.deadline, time.monotonic() + 5)
        while not self.paused():
            native.require(time.monotonic() < until, "Pause did not settle after baseline reload")
            time.sleep(.01)
        self.result["cases"].append(dict(name=name))
        self.check("baseline room", int.from_bytes(self.block(0x7E00A0, 2), "little"), 0x104)

    def ready(self):
        for _ in range(80):
            if (self.screen() == "gameplay" and not self.r(0x7E0011)
                    and not self.r(0x7E005D) and not self.r(0x7E037A)
                    and not self.r(0x7E003A) & 0xC0):
                return
            self.advance("", 2)
        raise RuntimeError("Link did not regain ordinary item control")

    def equip(self, item):
        self.ready()
        self.tap("Start"); self.wait_screen("items")
        for _ in range(30):
            if self.r(0x7E0202) == item:
                break
            self.tap("Right")
        self.check("controller item selection", self.r(0x7E0202), item)
        self.tap("Start"); self.wait_screen("gameplay")
        self.ready()

    def enter(self, name, button, hold=False):
        self.advance("", 2)
        self.input(button)
        cpu = self.run_to({self.symbol(name) if isinstance(name, str) else name})
        if not hold:
            self.input("")
        return cpu

    def call_in(self, name, target, occurrence=0, size=0x200):
        address = self.symbol(name)
        start = native.pc_offset(address)
        needle = b"\x22" + target.to_bytes(3, "little")
        hits = [offset for offset in range(size - 3)
                if self.rom[start + offset:start + offset + 4] == needle]
        native.require(len(hits) > occurrence, "Missing actual native call in " + name)
        return address + hits[occurrence]

    def occupancy(self, free=None):
        for slot in range(16):
            self.write(0x7E0DD0 + slot, 0 if slot == free else 9,
                       "Paused occupancy at actual allocator; cleared before any sprite AI")

    def idle_fishing_menu(self):
        self.reset_case("idle Fishing Rod menu preserves remembered actor")
        self.write(0x7EF351, 1, "Fishing ownership")
        self.equip(0x10)
        self.enter("Menu_InitGraphics", "Start")
        self.write(MODE, 0, "No fishing session")
        self.write(FLOATER, 0, "Stale slot zero")
        self.write(0x7E0DD0, 9, "Guard actor while menu freezes sprite AI")
        call = self.call_in("Menu_InitGraphics", self.symbol("DismissRodFromMenu"))
        self.run_to({call})
        cpu = self.cpu()
        self.run_to({call + 4})
        self.check("idle menu actor state", self.r(0x7E0DD0), 9 if self.fixed else 0)
        self.check("idle menu stack", self.cpu()["sp"], cpu["sp"])

    def fishing_allocation(self, prize=False):
        self.reset_case("failed fishing " + ("prize" if prize else "cast"))
        self.write(0x7EF351, 1, "Fishing ownership")
        self.equip(0x10)
        if prize:
            self.tap("Y")
            for _ in range(60):
                if self.r(MODE) == 1:
                    break
                self.advance("", 2)
            self.check("successful cast reached rod-out mode", self.r(MODE), 1)
            slot = self.r(FLOATER)
            native.require(slot < 16, "Successful cast has no bounded floater")
            self.write(0x7E0DB0 + slot, 1, "Declared bite on the live owned floater; not a natural-water test")
            call = self.call_in("LinkItem_FishingRod", 0x1DF65D, occurrence=1)
        else:
            call = self.call_in("LinkItem_FishingRod", 0x1DF65D)
        self.advance("", 2)
        self.input("Y")
        self.run_to({call}); self.input("")
        self.occupancy()
        before = self.block(SPRITES, SPRITE_SIZE)
        cpu = self.cpu()
        ret = self.call_in("LinkItem_FishingRodAndPortalRod", self.symbol("LinkItem_FishingRod")) + 4
        self.run_to({ret})
        after = self.block(SPRITES, SPRITE_SIZE)
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.result["cases"][-1]["sprite_changes"] = changed
        self.check("failed allocation preserves sprite/indexed RAM", before == after, self.fixed)
        # The call stack has unwound both the JSL return and the callee's PHB.
        self.check("fishing returns to bank07", native.number(self.cpu()["pc"]), ret)
        self.check("failed cast clears session", self.r(MODE), 2 if prize else (0 if self.fixed else 0))

    def fairy(self, success=False):
        self.reset_case("fairy " + ("one free slot" if success else "full pool"))
        self.write(0x7EF35C, 6, "Bottle1 contains one fairy")
        self.equip(6)
        self.enter("LinkItem_Bottles_LinkItem_FairyBottle", "Y")
        self.occupancy(free=15 if success else None)
        self.run_to({self.symbol("LinkItem_Bottles_bottle_exit")})
        self.check("fairy bottle contents", self.r(0x7EF35C), 2 if success or not self.fixed else 6)
        if success:
            self.check("one fairy spawned", self.r(0x7E0E2F), 0xE3)
            self.check("fairy active", self.r(0x7E0DDF), 9)

    def catch_counter(self, direction, offset):
        self.reset_case("catch initialization " + direction)
        self.write(0x7EF35C, 2, "Empty Bottle1")
        self.equip(6)
        self.tap(direction)
        # The item dispatcher visits CatchBottle on neutral frames too. Stop
        # after its fresh-Y gate, before the facing/counter initializer, so
        # ordinary movement setup cannot legitimately clear the canaries.
        start = self.symbol("LinkItem_CatchBottle")
        pc = native.pc_offset(start)
        native.require(self.rom[pc + 8:pc + 11] == bytes.fromhex("20 73 B0")
                       and self.rom[pc + 13:pc + 15] == bytes.fromhex("A5 2F"),
                       "Catch fresh-press initializer boundary moved")
        entry = self.enter(start + 13, "Y", hold=True)
        self.check("catch fresh Y accepted", self.r(0x7E003A) & 0x40, 0x40)
        self.result["cases"][-1]["entry"] = dict(cpu=entry, y_latch=self.r(0x7E003A),
                                                   new_input=self.r(0x7E00F4), doorway=self.r(0x7E006C))
        for address in (0x7E030D, 0x7E0317, 0x7E0321, 0x7E032B):
            self.write(address, 0xA6 if address != 0x7E030D else 3, "Paused animation/counter canary")
        self.run_to({self.symbol("LinkItem_CatchBottle_y_press")})
        self.input("")
        self.check("catch counter reset", self.r(0x7E030D), 0 if self.fixed or offset == 0 else 3)
        for address in (0x7E0317, 0x7E0321, 0x7E032B):
            expected = 0 if not self.fixed and address == 0x7E030D + offset else 0xA6
            self.check("catch preserves unrelated counter byte", self.r(address), expected)

    def book(self):
        self.reset_case("Book-only L reveal and release")
        self.write(0x7EF34E, 1, "Book ownership")
        self.write(0x7EF34D, 0, "No Roc's Feather")
        original = self.r(0x7E001C)
        native.require(original & 2, "House fixture must begin with BG2 enabled")
        self.advance("L", 2)
        self.check("Book hides only BG2", self.r(0x7E001C), original & ~2 if self.fixed else original)
        self.advance("", 2)
        self.check("Book restores layer bit on release", self.r(0x7E001C), original)
        self.write(0x7EF34E, 0, "Remove Book")
        self.write(0x7EF34D, 1, "Feather-only control")
        self.advance("L", 2)
        self.check("Feather alone cannot reveal", self.r(0x7E001C), original)
        self.write(0x7EF34E, 1, "Book for disabled-layer control")
        self.advance("", 2)
        self.write(0x7E001C, original & ~2, "Loader-disabled BG2 fixture")
        self.advance("L", 2); self.advance("", 2)
        self.check("Book never enables an originally disabled layer", self.r(0x7E001C), original & ~2)

    def rings(self):
        self.reset_case("six ring descriptions and stale-text clearing")
        self.write(0x7EF3A2, 0x3F, "All six rings appraised")
        self.tap("Start"); self.wait_screen("items")
        self.tap("L"); self.wait_screen("equipment")
        for _ in range(4):
            if 6 <= self.r(menu.CURSOR) < 12:
                break
            self.tap("Down")
        for ring in range(6):
            target = 6 + ring
            for _ in range(6):
                if self.r(menu.CURSOR) == target:
                    break
                self.tap("Right")
            self.check("ring cursor", self.r(menu.CURSOR), target)
            start = native.pc_offset(self.symbol("Menu_RingDescriptions")) + ring * 32
            words = [int.from_bytes(self.rom[i:i + 2], "little") for i in range(start, start + 32, 2)]
            self.check("matching ring effect text", self.words(8, 16, 16) == words, self.fixed)
            if ring in (0, 4):
                self.shot("ring-description-" + str(ring))
        for _ in range(4):
            if self.r(menu.CURSOR) >= 18:
                break
            self.tap("Down")
        start = native.pc_offset(self.symbol("menu_frame")) + (16 * 32 + 8) * 2
        words = [int.from_bytes(self.rom[i:i + 2], "little") for i in range(start, start + 32, 2)]
        self.check("non-ring clears effect text", self.words(8, 16, 16), words)
        self.shot("ring-description-cleared")

    def run(self):
        native.require(self.screen() == "gameplay" and not self.r(0x7E0011), "Need stable House gameplay")
        native.require(self.b.save_state(path=str(self.baseline)), "Own same-ROM baseline capture rejected")
        self.idle_fishing_menu()
        self.fishing_allocation()
        self.fishing_allocation(prize=True)
        self.fairy()
        self.fairy(success=True)
        for direction, offset in (("Up", 0), ("Down", 10), ("Left", 20), ("Right", 30)):
            self.catch_counter(direction, offset)
        self.book()
        self.rings()
        self.reset_case("clean same-ROM return")
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--expect", choices=("control", "candidate"), required=True)
    parser.add_argument("--execute-fixtures", action="store_true", required=True)
    args = parser.parse_args()
    session = json.loads(args.session.read_text())
    for key in ("owner_file", "status_file", "owned_rom", "symbols", "output"):
        session[key] = Path(session[key])
    native.require(session["owner"].startswith("codex-item-safety-"), "Only owned item-safety sessions admitted")
    native.require(hashlib.sha256(session["owned_rom"].read_bytes()).hexdigest() == session["rom_sha256"], "ROM hash mismatch")
    native.require(hashlib.sha256(session["symbols"].read_bytes()).hexdigest() == session["symbols_sha256"], "Symbol hash mismatch")
    session["expect"] = args.expect
    sys.path.insert(0, session["client_root"])
    from mesen2_client_lib.bridge import MesenBridge
    flow = ItemSafetyFlow(SimpleNamespace(**session), MesenBridge(session["socket"], auto_reconnect=False, max_retries=0))
    try:
        flow.check_owner(); flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        try:
            flow.input("")
            native.require(flow.b.pause(), "Final fixture Pause rejected")
            for ident in list(flow.breakpoints):
                flow.remove(ident)
        except Exception as error:
            flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed")
                                     and not flow.result["cleanup_errors"])
        (session["output"] / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
