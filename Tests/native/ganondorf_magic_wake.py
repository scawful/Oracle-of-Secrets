#!/usr/bin/env python3
"""Five attach-only native groups for Ganondorf/bat snapshots and bat wake.

Uses BatCastFixture's owned private session, exact ROM/state checks, bounded
deadline and cleanup. Logged actor/Link positions, actions and timers select
starting conditions; native emitters allocate every tested magic effect.
No CPU/PC, HP, immunity, ROM, SRAM, garnish or ancilla writes occur here.
"""
from __future__ import annotations

import ganondorf_playtest_polish as core
from ganondorf_bat_cast import BatCastFixture


class MagicWakeFixture(BatCastFixture):
    def __init__(self, *args):
        super().__init__(*args)
        self.result["claim"] = "native controlled magic emission, caps, snapshot OAM, wake contact/fade, lifetimes and floor coexistence; no human-play acceptance"

    def magic(self, mode=None):
        return [slot for slot in range(16) if self.field("state", slot)
                and self.field("kind", slot) == 0x46
                and (self.field("action", slot) in (4, 5) if mode is None
                     else self.field("action", slot) == mode)]

    def source(self, slot):
        return dict(slot=slot, position=self.position(slot), frame=self.field("frame", slot),
                    height=self.field("height", slot), floor=self.r(0x7E0F20 + slot),
                    bat=self.field("kind", slot) == 0x46)

    def assert_spawn(self, slot, mode, parent, source):
        row = dict(slot=slot, action=self.field("action", slot), state=self.field("state", slot),
                   owner=self.field("d", slot), position=self.position(slot), frame=self.field("frame", slot),
                   height=self.field("height", slot), floor=self.r(0x7E0F20 + slot),
                   timer=self.field("timer_a", slot), subtype=self.field("subtype", slot),
                   velocity=[self.field("xspeed", slot), self.field("yspeed", slot)],
                   damage=self.r(0x7E0CD2 + slot), hitbox=self.r(0x7E0F60 + slot),
                   deflection=self.r(0x7E0CAA + slot), oam_flags=self.r(0x7E0E40 + slot))
        core.require(row["action"] == mode and row["state"] == 9 and row["owner"] == parent
                     and row["position"] == source["position"] and row["frame"] == source["frame"]
                     and row["height"] == source["height"] and row["floor"] == source["floor"]
                     and row["velocity"] == [0, 0] and row["subtype"] == int(source["bat"])
                     and row["timer"] == (32 if mode == 4 else 12)
                     and row["damage"] == 1 and row["deflection"] == 0x46
                     and row["hitbox"] == (0x59 if mode == 4 else 0x40)
                     and row["oam_flags"] == (0x40 if mode == 4 else 0x80 if source["bat"] else 0x85),
                     f"Native magic allocation differs from its captured source: {row}/{source}")
        return row

    def body_emission(self, rally=False):
        if rally:
            parent, ball, _ = self.spawn(9, 0, 64)
            self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
            for key, value in (("timer_b", 0), ("timer_c", 0), ("b", 0)):
                self.set(key, parent, value, "native active-volley glide emits a body snapshot")
        else:
            parent = self.prepare(local=(0x38, 0x98), gap=136)
            self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
            self.set("timer_a", parent, 0xFF, "long Float cooldown isolates moving snapshot emission")
            self.set("timer_b", parent, 0, "clear inherited fixture emitter suppression")
            ball = None
        self.run_to(self.labels["GanonMagic_TryAfterimage"], f"x == {parent}")
        source, before = self.source(parent), set(self.magic(5))
        self.run_to(self.labels["GanonMagic_TryAfterimage_after_spawn"], f"x == {parent}")
        added = set(self.magic(5)) - before
        core.require(len(added) == 1 and self.field("timer_b", parent) == 8,
                     "Native moving body did not allocate one snapshot on its8-tick cadence")
        ghost = added.pop()
        row = self.assert_spawn(ghost, 5, parent, source)
        if rally:
            core.require(self.field("action", parent) == 3 and self.field("d", parent) == ball,
                         "Body snapshot changed the active rally pointer or action")
        return parent, ghost, dict(source=source, effect=row, rally_ball=ball)

    def bat_emission(self):
        parent, bat, birth = self.spawn_bat()
        self.run_to(self.labels["GanonMagic_TryBatEffects"], f"x == {bat}")
        source = self.source(bat)
        self.run_to(self.labels["GanonMagic_TryBatEffects_after_spawn"], f"x == {bat}")
        wakes, ghosts = self.magic(4), self.magic(5)
        core.require(len(wakes) == len(ghosts) == 1 and self.field("timer_b", bat) == 8,
                     "Native bat did not emit one wake and one snapshot on its shared8-tick cadence")
        wake, ghost = wakes[0], ghosts[0]
        row = dict(birth=birth, source=source, wake=self.assert_spawn(wake, 4, parent, source),
                   afterimage=self.assert_spawn(ghost, 5, parent, source))
        return parent, bat, wake, ghost, row

    def isolate(self, parent, bat):
        self.set("state", bat, 0, "declared gone bat isolates its already-emitted static effects")
        self.hold_parent(parent)

    def emission_static_snapshots_and_caps(self):
        body = []
        for rally in (False, True):
            parent, ghost, row = self.body_emission(rally)
            origin = self.position(ghost)
            self.frames(7)
            core.require(self.field("action", ghost) == 5 and self.position(ghost) == origin
                         and self.field("frame", ghost) == row["source"]["frame"]
                         and self.position(parent) != origin,
                         "Body afterimage moved/animated with its moving source")
            row["parent_after_seven_ticks"] = self.position(parent)
            body.append(row)

        parent, bat, wake, ghost, row = self.bat_emission()
        self.hold_parent(parent)
        x, y = self.position(parent)
        self.link(x - 64, y - 32, "Link behind the moving bat avoids contact during cap observation")
        origins = {slot: self.source(slot) for slot in (wake, ghost)}
        samples = []
        for tick in range(2, 34, 2):
            self.frames(2)
            wakes, ghosts = self.magic(4), self.magic(5)
            core.require(len(wakes) <= 4 and len(ghosts) <= 2,
                         "Native repeated bat emission exceeded four wakes or two shared snapshots")
            if tick <= 6:
                for slot, source in origins.items():
                    core.require(self.position(slot) == source["position"]
                                 and self.field("frame", slot) == source["frame"],
                                 "Bat wake/snapshot followed its moving emitter")
            samples.append(dict(tick_upper_bound=tick + 1, wakes=len(wakes), afterimages=len(ghosts),
                                bat_position=self.position(bat)))
        (self.a.out / "magic-wake.png").write_bytes(self.b.screenshot())
        core.require(max(sample["wakes"] for sample in samples) == 4
                     and max(sample["afterimages"] for sample in samples) == 2,
                     "Native repeated emission did not exercise both effect caps")
        self.result["cases"].append(dict(name="native-body-bat-emission-static-snapshots-and-caps", passed=True,
                                          body=body, bat=row, cap_samples=samples))

    def active_contact_and_harmless_fade(self):
        parent, bat, wake, ghost, row = self.bat_emission()
        self.isolate(parent, bat)
        core.require(self.r(0x7E037B) == self.r(0x7E031F) == 0,
                     "Checkpoint immunity prevents native wake contact qualification")
        hp = self.r(0x7EF36D)
        x, y = self.position(wake)
        self.link(x, y - 8, "declared Link overlap tests an active static wake through native contact")
        self.run_to(self.labels["GanonMagic_Main_exit"], f"x == {wake}")
        queued = self.r(0x7E0373)
        core.require(queued > 0 and self.field("timer_a", wake) > 8,
                     "Active wake did not queue nonzero ordinary native damage")
        self.frames(2)
        core.require(0 < self.r(0x7EF36D) < hp, "Active wake contact did not reduce actual Link health")
        active = dict(hp_before=hp, hp_after=self.r(0x7EF36D), queued_damage=queued, emission=row)

        harmless = []
        for mode in (4, 5):
            parent, bat, wake, ghost, _ = self.bat_emission()
            self.isolate(parent, bat)
            target = wake if mode == 4 else ghost
            other = ghost if mode == 4 else wake
            self.set("state", other, 0, "remove the other static effect to isolate harmless contact")
            if mode == 4:
                self.set("timer_a", wake, 8, "declared final-eight-tick fade boundary must be harmless")
            core.require(self.r(0x7E037B) == self.r(0x7E031F) == 0,
                         "Fresh checkpoint immunity prevents harmless-contact control")
            x, y = self.position(target)
            self.link(x, y - 8, "declared Link overlap with harmless wake fade or pose snapshot")
            hp = self.r(0x7EF36D)
            self.frames(4)
            core.require(self.r(0x7EF36D) == hp and self.r(0x7E0373) == 0
                         and self.r(0x7E037B) == 0,
                         "Harmless wake fade or afterimage queued damage or changed health")
            harmless.append(dict(mode=mode, hp_before=hp, hp_after=self.r(0x7EF36D),
                                 timer=self.field("timer_a", target)))
        self.result["cases"].append(dict(name="active-wake-contact-versus-harmless-fade-and-snapshot", passed=True,
                                          active=active, harmless=harmless))

    def current_oam(self):
        pointer, high = self.r16(0x7E0090), self.r16(0x7E0092)
        core.require(0x0800 <= pointer <= 0x09FC and 0x0A20 <= high <= 0x0A9F,
                     f"Magic draw has an invalid OAM allocation: {pointer:04X}/{high:04X}")
        return dict(pointer=pointer, entry=list(self.block(0x7E0000 | pointer, 4)),
                    size=self.r(0x7E0000 | high) & 2)

    def snapshot_oam(self, slot):
        row = self.current_oam()
        frame = self.field("frame", slot)
        first = self.table("start_index", 22)[frame]
        count = self.table("nbr_of_tiles", 22)[frame] + 1
        core.require(count == (1 if self.field("subtype", slot) else 6),
                     "Native snapshot selected an unexpected piece count")
        tiles = self.table("chr", first + count)
        xoff = self.table("x_offsets", (first + count)*2)
        yoff = self.table("y_offsets", (first + count)*2)
        x, y = self.position(slot)
        base = (x - self.r16(0x7E00E2), y - self.r16(0x7E00E8) - self.field("height", slot))
        entries = [list(self.block(0x7E0000 | (row["pointer"] + index*4), 4)) for index in range(count)]
        high = self.r16(0x7E0092)
        for piece, index in enumerate(reversed(range(first, first + count))):
            dx = int.from_bytes(xoff[index*2:index*2+2], "little", signed=True)
            dy = int.from_bytes(yoff[index*2:index*2+2], "little", signed=True)
            item = entries[piece]
            core.require(item[0] == (base[0] + dx) & 255 and item[1] == (base[1] + dy) & 255
                         and item[2] == tiles[index] and item[1] < 0xF0
                         and (item[3] >> 1) & 7 == 6 and self.r(0x7E0000 | (high + piece)) & 2,
                         "Completed snapshot OAM differs from its captured frame/position/height")
        row.update(frame=frame, pieces=count, entries=entries)
        return row

    def exact_lifetimes_floors_and_owner_cleanup(self):
        parent, bat, wake, ghost, row = self.bat_emission()
        self.isolate(parent, bat)
        starts = {}
        for slot in sorted((wake, ghost), reverse=True):
            self.run_to(self.labels["GanonMagic_Main"], f"x == {slot}")
            starts[slot] = dict(frame=self.r(0x7E001A), timer=self.field("timer_a", slot))
            if slot == wake:
                core.require(self.current_oam()["size"] == 2,
                             "First-eight-tick wake did not draw the captured16px bat silhouette")
        events = []
        for slot, target in ((wake, 24), (ghost, 0), (wake, 8), (wake, 0)):
            self.run_to(self.labels["GanonMagic_Main"], f"x == {slot} && [$0DF0+x] == {target}")
            elapsed = (self.r(0x7E001A) - starts[slot]["frame"]) & 255
            core.require(elapsed == starts[slot]["timer"] - target,
                         "Magic native lifetime did not decrement exactly once per game frame")
            if slot == wake and target == 24:
                core.require(self.current_oam()["size"] == 0,
                             "Wake did not become an8px ember after its initial eight silhouette ticks")
            events.append(dict(slot=slot, timer=target, elapsed=elapsed))
            if target == 0:
                self.run_to(self.labels["Sprite_GanonBall_Long_not_active"], f"x == {slot}")
                core.require(self.field("state", slot) == 0, "Expired magic effect retained a native sprite slot")

        guards = []
        for fault in ("invalid-owner", "dead-owner", "outside-room"):
            parent, bat, wake, ghost, _ = self.bat_emission()
            self.isolate(parent, bat)
            if fault == "dead-owner":
                self.set("action", parent, 6, "declared defeated owner removes both effect modes directly")
            for slot in (wake, ghost):
                if fault == "invalid-owner":
                    self.set("d", slot, 0xFF, "invalid root owner must be rejected before indexed access")
                elif fault == "outside-room":
                    x, y = self.position(slot)
                    self.locate(slot, x ^ 0x200, y, "effect outside the current512px room must not wrap tile/OAM state")
            for slot in sorted((wake, ghost), reverse=True):
                if fault != "outside-room":
                    self.run_to(self.labels["GanonMagic_Main_kill"], f"x == {slot}")
                self.run_to(self.labels["Sprite_GanonBall_Long_not_active"], f"x == {slot}")
                core.require(self.field("state", slot) == 0,
                             f"Native {fault} guard retained mode4/5 magic")
            guards.append(dict(fault=fault, remaining_magic=self.magic()))
        self.result["cases"].append(dict(name="exact-magic-lifetimes-floor-copy-and-owner-cleanup", passed=True,
                                          emission=row, first_native_ticks=starts, events=events, guards=guards))

    def fill_except(self, keep):
        slots = [slot for slot in range(16) if slot not in keep]
        for slot in slots:
            for key, value in (("kind", 0x46), ("state", 9), ("action", 2), ("timer_a", 96), ("d", 0xFF)):
                self.set(key, slot, value, "declared harmless puff occupies a dynamic slot immediately before allocation")
        return slots

    def full_sprite_allocation_recovery(self):
        parent = self.prepare(local=(0x38, 0x98), gap=136)
        self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
        for key, value in (("timer_a", 0xFF), ("timer_b", 0)):
            self.set(key, parent, value, "moving Float reaches the native snapshot allocator with effects enabled")
        self.run_to(self.labels["GanonMagic_TryAfterimage"], f"x == {parent}")
        fillers = self.fill_except({parent})
        self.run_to(self.labels["GanonMagic_TryAfterimage_after_spawn"], f"x == {parent}")
        core.require(not self.magic() and self.field("action", parent) == 1,
                     "Full table snapshot attempt changed combat or allocated an effect")
        self.set("state", fillers[0], 0, "one released dynamic slot permits a later native snapshot")
        self.set("timer_b", parent, 0, "declared next cadence tests recovery after one failed allocation")
        before = self.position(parent)
        self.run_to(self.labels["GanonMagic_TryAfterimage_after_spawn"], f"x == {parent}")
        self.frames(4)
        core.require(len(self.magic(5)) == 1 and self.position(parent) != before,
                     "Moving body did not recover when an effect slot became free")
        body = dict(fillers=fillers, snapshot=self.magic(5), position=self.position(parent))

        parent, bat, _ = self.spawn_bat()
        self.hold_parent(parent)
        self.run_to(self.labels["GanonMagic_TryBatEffects"], f"x == {bat}")
        fillers = self.fill_except({parent, bat})
        velocity = [self.field("xspeed", bat), self.field("yspeed", bat)]
        self.run_to(self.labels["GanonMagic_TryBatEffects_after_spawn"], f"x == {bat}")
        core.require(not self.magic() and self.field("state", bat) == 9 and self.field("action", bat) == 3
                     and velocity == [self.field("xspeed", bat), self.field("yspeed", bat)],
                     "Full table magic attempts removed or changed the independent bat")
        for slot in fillers[:2]:
            self.set("state", slot, 0, "two released dynamic slots permit the next native wake/snapshot pair")
        self.set("timer_b", bat, 0, "declared next bat cadence tests allocation recovery")
        before = self.position(bat)
        self.run_to(self.labels["GanonMagic_TryBatEffects_after_spawn"], f"x == {bat}")
        core.require(len(self.magic(4)) == len(self.magic(5)) == 1 and self.position(bat) != before,
                     "Bat did not keep moving and resume its wake/snapshot pair after capacity returned")
        self.result["cases"].append(dict(name="full-sprite-table-body-and-bat-effect-recovery", passed=True,
                                          body=body, bat=dict(fillers=fillers, wake=self.magic(4),
                                              snapshot=self.magic(5), position=self.position(bat))))

    def snapshot_oam_and_native_stomp(self):
        parent, first, _ = self.body_emission()
        self.set("timer_b", parent, 0, "declared next cadence creates a second native body snapshot for draw-cap proof")
        self.run_to(self.labels["GanonMagic_TryAfterimage_after_spawn"], f"x == {parent}")
        ghosts = self.magic(5)
        core.require(len(ghosts) == 2 and first in ghosts, "Native body draw-cap control lacks two snapshots")
        self.hold_parent(parent)
        condition = " || ".join(f"x == {slot}" for slot in ghosts)
        draws = []
        for _ in range(8):
            cpu = self.run_to(self.labels["GanonMagic_DrawAfterimage_draw"], condition)
            slot = core.number(cpu.get("x", cpu.get("X", -1)))
            self.run_to(self.labels["GanonMagic_DrawAfterimage_done"], f"x == {slot}")
            frame = self.field("frame", slot)
            count = self.table("nbr_of_tiles", 22)[frame] + 1
            core.require(count == 6, "Moving body snapshot did not retain its six-piece body art")
            draws.append(dict(slot=slot, frame=frame, pieces=count, game_frame=self.r(0x7E001A),
                              oam=self.snapshot_oam(slot)))
        core.require(all((b["game_frame"] - a["game_frame"]) & 255 == 1 for a, b in zip(draws, draws[1:]))
                     and {row["slot"] for row in draws} == set(ghosts),
                     "Two body snapshots drew together or failed to alternate their per-frame OAM allowance")

        parent, bat, wake, ghost, emission = self.bat_emission()
        self.set("timer_b", bat, 0xFF, "suppress later emissions while existing effects coexist with the native stomp")
        self.run_to(self.labels["GanonMagic_DrawAfterimage_draw"], f"x == {ghost}")
        self.run_to(self.labels["GanonMagic_DrawAfterimage_done"], f"x == {ghost}")
        bat_oam = self.snapshot_oam(ghost)
        core.require(bat_oam["size"] == 2
                     and self.table("nbr_of_tiles", 22)[self.field("frame", ghost)] == 0,
                     "Bat snapshot did not retain its single16px silhouette")
        for key, value in (("action", 7), ("g", 1), ("height", 4), ("timer_a", 0),
                           ("timer_b", 0xFF), ("subtype", 0)):
            self.set(key, parent, value, "declared final native stomp descent beside existing wake and snapshot")
        after_impact = self.after_jsr("Ganondorf_Stomp", "Ganondorf_SpawnFloorCollapse", "Ganondorf_SpawnFloorCollapse")
        self.run_to(after_impact, f"x == {parent}")
        overlords = self.overlords()
        core.require(len(overlords) == 1 and overlords[0]["kind"] == 0x0C
                     and self.field("state", wake) == self.field("state", ghost) == 9
                     and self.field("action", wake) == 4 and self.field("action", ghost) == 5
                     and self.field("g", parent) == 2,
                     "Native stomp did not allocate falling floor while both magic modes remained alive")
        picture = self.b.screenshot()
        core.require(picture, "Magic/stomp screenshot rejected")
        (self.a.out / "magic-native-stomp.png").write_bytes(picture)
        floor = self.native_floor_garnish(overlords[0])
        self.result["cases"].append(dict(name="body-snapshot-draw-cap-bat-oam-and-native-falling-floor", passed=True,
                                          body_draws=draws, bat_snapshot_oam=bat_oam, emission=emission,
                                          overlord=overlords[0], native_garnish_and_pit=floor))


def main():
    return core.run_fixture(core.parse_args(), MagicWakeFixture,
                            ("emission_static_snapshots_and_caps", "active_contact_and_harmless_fade",
                             "exact_lifetimes_floors_and_owner_cleanup", "full_sprite_allocation_recovery",
                             "snapshot_oam_and_native_stomp"))


if __name__ == "__main__":
    raise SystemExit(main())
