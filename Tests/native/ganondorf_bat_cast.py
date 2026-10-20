#!/usr/bin/env python3
"""Five bounded, attach-only checks for Ganondorf's independent cast bat.

The caller owns a paused headless session and an exact-candidate room00 state.
Only logged actor/Link starting positions, actions and timers are fixture inputs.
The inherited wall/torch helper may log one fallback collision cell. Sword input
uses the controller. No CPU/PC, HP, immunity, ROM or SRAM writes occur, and this
script never launches Mesen or accesses a visible play session.
"""
from __future__ import annotations

import ganondorf_playtest_polish as core
from ganondorf_spacing_impacts import SpacingImpactFixture


HUMAN_CAST_FRAMES = (12, 16, 5, 17, 18)
BAT_FRAMES = (19, 20, 21)


class BatCastFixture(SpacingImpactFixture):
    def __init__(self, *args):
        super().__init__(*args)
        self.result["claim"] = "native controlled independent bat cast, OAM, contact, sword and cleanup checks; no human-play acceptance"

    def prepare_bat(self):
        parent = self.prepare()
        self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
        for key, value in (("action", 5), ("timer_a", 48), ("frame", 12),
                           ("d", 0xFF), ("xspeed", 0), ("yspeed", 0)):
            self.set(key, parent, value, "declared between-volley human cast starting state")
        return parent

    def bat_birth(self, parent):
        self.run_to(self.labels["Ganondorf_CastBat_bat_spawned"], f"x == {parent}")
        bats = self.actors(3)
        core.require(len(bats) == 1, "Native action5 did not allocate exactly one independent bat")
        bat = bats[0]
        x, y = self.position(parent)
        expected = (x, (y - self.field("height", parent) - 8) & 0xFFFF)
        core.require(self.field("timer_a", parent) == 24 and self.field("d", parent) == 0xFF,
                     "Native bat release changed the rally pointer or its24-tick release point")
        core.require(self.position(bat) == expected, "Native bat did not spawn at its true16px body-center origin")
        state = {key: self.field(key, bat) for key in ("state", "kind", "action", "d", "height", "timer_a", "b")}
        core.require(state == dict(state=9, kind=0x46, action=3, d=parent, height=0, timer_a=96, b=0),
                     f"Native bat state differs: {state}")
        properties = {"health": self.r(0x7E0E50 + bat), "damage": self.r(0x7E0CD2 + bat),
                      "gfx": self.r(0x7E0E60 + bat), "deflection": self.r(0x7E0CAA + bat)}
        core.require(properties == dict(health=1, damage=2, gfx=0x80, deflection=0x40),
                     f"Native bat weapon/damage properties differ: {properties}")
        velocity = (self.field("xspeed", bat), self.field("yspeed", bat))
        signed = tuple(value - 256 if value & 0x80 else value for value in velocity)
        core.require(22**2 <= sum(value*value for value in signed) <= 26**2,
                     "Native bat launch velocity differs from its18 projected speed")
        return bat, dict(parent=parent, bat=bat, origin=expected, state=state,
                         properties=properties, launch_velocity=velocity)

    def spawn_bat(self):
        parent = self.prepare_bat()
        bat, row = self.bat_birth(parent)
        return parent, bat, row

    def actor_oam(self, slot, human=False):
        if human:
            target = self.labels["Ganondorf_Draw_skip"]
        else:
            target = self.after_jsr("Sprite_GanonBall_Long", "Sprite_GanonBall_Prep", "GanonBall_Draw")
        self.run_to(target, f"x == {slot}")
        frame = self.field("frame", slot)
        core.require(frame in (HUMAN_CAST_FRAMES if human else BAT_FRAMES),
                     "Human/child native draw selected the other actor's art")
        pointer = self.r16(0x7E0090)
        core.require(0x0800 <= pointer <= 0x09FC, "Native cast actor has an invalid OAM allocation")
        first = self.table("start_index", 22)[frame]
        count = self.table("nbr_of_tiles", 22)[frame] + 1
        entries = [list(self.block(0x7E0000 | (pointer + index*4), 4)) for index in range(count)]
        tiles = self.table("chr", first + count)
        xoffset = self.table("x_offsets", (first + count)*2)
        yoffset = self.table("y_offsets", (first + count)*2)
        x, y = self.position(slot)
        base = (x - self.r16(0x7E00E2), y - self.r16(0x7E00E8) - self.field("height", slot))
        for item, index in zip(entries, reversed(range(first, first + count))):
            dx = int.from_bytes(xoffset[index*2:index*2+2], "little", signed=True)
            dy = int.from_bytes(yoffset[index*2:index*2+2], "little", signed=True)
            core.require(item[0] == (base[0] + dx) & 255 and item[1] == (base[1] + dy) & 255
                         and item[2] == tiles[index] and (item[3] >> 1) & 7 == 6 and item[1] < 0xF0,
                         f"Native cast OAM differs from authored frame{frame}")
            if not human:
                core.require(count == 1 and dx == dy == 0
                             and self.table("sizes", first + 1)[first] == 2,
                             "Independent bat must draw one16x16 tile at origin0,0")
        return dict(slot=slot, frame=frame, game_frame=self.r(0x7E001A), pointer=pointer, entries=entries)

    def human_cast_and_child_oam(self):
        parent = self.prepare_bat()
        ready = self.draw(parent, (12,))
        windup = self.draw(parent, (16,))
        bat, row = self.bat_birth(parent)
        # Native sprite slots run from15 down to0. Capture both completed draws
        # in that order to prove distinct allocations in one game frame.
        draws = [self.actor_oam(slot, human=slot == parent) for slot in sorted((parent, bat), reverse=True)]
        core.require(draws[0]["game_frame"] == draws[1]["game_frame"]
                     and draws[0]["pointer"] != draws[1]["pointer"],
                     "Human and independent bat did not coexist in distinct same-frame OAM")
        x, y = self.position(parent)
        self.link(x - 64, y - 32, "Link crosses behind the caster; launched bat must retain its fixed aim")
        poses, flaps, positions, velocities = [12, 16], [], [], []
        for _ in range(20):
            self.frames(1)
            core.require(self.field("action", parent) == 5 and self.field("action", bat) == 3,
                         "Native child or human cast ended before the bounded animation sample")
            poses.append(self.field("frame", parent))
            flaps.append(self.field("frame", bat))
            positions.append(self.position(bat))
            velocities.append((self.field("xspeed", bat), self.field("yspeed", bat)))
            core.require(self.field("d", parent) == 0xFF and self.field("b", bat) == 0,
                         "Independent bat entered the rally/reflection channel")
        core.require(set(poses) == set(HUMAN_CAST_FRAMES) and set(flaps) == set(BAT_FRAMES),
                     "Human cast or independent flap sequence did not cover all authored frames")
        core.require(len(set(positions)) > 1 and len(set(velocities)) == 1,
                     "Independent bat did not move on a fixed launch velocity")
        before = self.position(parent)
        self.run_to(self.labels["Ganondorf_Stomp"], f"x == {parent}")
        core.require(self.field("action", parent) == 7 and self.position(parent) != before
                     and self.field("action", bat) == 3 and self.field("state", bat) == 9,
                     "Human cast did not relocate and start stomp while its child remained independent")
        self.result["cases"].append(dict(name="human-cast-independent-child-oam", passed=True, **row,
                                          ready=ready, windup=windup, draws=draws, human_frames=poses,
                                          bat_frames=flaps, positions=positions, velocities=velocities,
                                          parent_after_relocation=self.position(parent)))

    def assert_puff(self, parent, bat, reason):
        self.run_to(self.labels["Sprite_GanonBall_Long_not_active"], f"x == {bat}")
        core.require(self.field("state", bat) == 9 and self.field("action", bat) == 2
                     and self.field("timer_a", bat) == 16 and self.field("d", bat) == 0xFF
                     and not self.actors(1) and self.field("action", parent) != 4
                     and self.field("d", parent) == 0xFF
                     and self.r(0x7E0EF0 + bat) == self.r(0x7E0CE2 + bat) == 0
                     and self.r(0x7E0EA0 + bat) == self.field("flash", bat) == 0
                     and self.r(0x7E0E60 + bat) & 0x40,
                     f"{reason} did not produce a harmless independent puff without shards or boss stun")
        return dict(action=self.field("action", bat), timer=self.field("timer_a", bat),
                    parent_action=self.field("action", parent), shards=len(self.actors(1)))

    def hold_parent(self, parent):
        for key, value in (("action", 0), ("timer_a", 0xFF), ("frame", 0)):
            self.set(key, parent, value, "human Intro hold isolates child lifetime and cleanup from subsequent attacks")

    def input_frames(self, count, buttons):
        self.owner()
        core.require(self.paused() and not self.breakpoints, "Controller FRAME requires paused CPU without breakpoints")
        core.payload(self.b.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"}))
        before = core.number(core.payload(self.b.send_command("STATE"))["frame"])
        core.payload(self.b.send_command("FRAME", {"count": str(count)}))
        until = min(self.deadline, core.time.monotonic() + 5)
        while core.time.monotonic() < until:
            after = core.number(core.payload(self.b.send_command("STATE"))["frame"])
            if after >= before + count and self.paused():
                core.require(after <= before + count + 1, "Controller FRAME overshot")
                self.neutral()
                return
            core.time.sleep(0.003)
        raise RuntimeError("Controller FRAME deadline exceeded")

    def contact_and_native_sword(self):
        parent, bat, birth = self.spawn_bat()
        core.require(self.r(0x7E037B) == self.r(0x7E031F) == 0,
                     "Candidate checkpoint has player immunity; native bat contact cannot be qualified")
        hp = self.r(0x7EF36D)
        x, y = self.position(bat)
        self.locate(parent, x + 64, y + 64, "move human body away to isolate child contact damage")
        self.link(x, y - 8, "declared player overlap with the cast bat's ordinary native damage box")
        self.run_to(self.labels["GanonBat_Main_dissipate"], f"x == {bat}")
        damage = self.r(0x7EF36D)
        core.require(0 < damage < hp, "Independent cast bat did not cause ordinary native contact damage")
        contact = self.assert_puff(parent, bat, "Bat contact")
        contact.update(hp_before=hp, hp_after=damage, birth=birth)

        parent, bat, birth = self.spawn_bat()
        core.require(self.r(0x7EF359) >= 2, "Native sword control needs the checkpoint's Master Sword")
        hp, hits = self.r(0x7EF36D), self.field("f", parent)
        # Face with the controller, then place one stationary attack target in
        # the ordinary sword arc. No sword/action-box RAM is injected.
        self.input_frames(1, "RIGHT")
        x, y = self.r16(0x7E0022), self.r16(0x7E0020)
        self.locate(parent, x - 64, y + 64, "human body outside the native sword target and contact probe")
        self.locate(bat, x + 20, y + 4, "stationary child target in Link's right-facing native sword arc")
        for key in ("xspeed", "yspeed"):
            self.set(key, bat, 0, "stationary target isolates generic weapon response from flight geometry")
        core.payload(self.b.send_command("INPUT", {"buttons": "B", "frames": "0", "player": "0"}))
        self.run_to(self.labels["GanonBat_Main_weapon_hit"], f"x == {bat}")
        sword = dict(native_weapon_hit=True, sword_animation=self.r(0x7E003C), birth=birth)
        sword.update(self.assert_puff(parent, bat, "Native sword hit"))
        self.neutral()
        core.require(self.r(0x7EF36D) == hp and self.field("f", parent) == hits,
                     "Sword child control damaged Link or changed Ganondorf's remaining hits")
        self.hold_parent(parent)
        self.frames(20)
        core.require(self.field("state", bat) == 0 and not self.actors(1),
                     "Sword-hit puff re-entered a delayed native death/stun module or emitted a drop/shard actor")
        sword["expired_without_delayed_death"] = True
        self.result["cases"].append(dict(name="bat-contact-and-native-sword", passed=True,
                                          contact=contact, sword=sword))

    def walls_torches_and_lifetime(self):
        rows = []
        for attr in (None, 0xC0, 0xCF):
            parent, bat, _ = self.spawn_bat()
            self.hold_parent(parent)
            surface = self.surface(bat, attr)
            ox, oy = self.r16(0x7E0022) & 0xFE00, self.r16(0x7E0020) & 0xFE00
            self.locate(bat, ox + surface["x"] - 11, oy + surface["y"] - 4,
                        "bat leading edge enters the selected live wall/torch collision cell")
            self.set("xspeed", bat, 16, "one native bat tick enters the wall or candle")
            self.set("yspeed", bat, 0, "horizontal bat background control")
            self.link(ox + 0x80, oy + 0xC0, "player away from the wall/candle contact probe")
            self.run_to(self.labels["GanonBat_Main_dissipate"], f"x == {bat}")
            rows.append(dict(surface=surface, puff=self.assert_puff(parent, bat, "Bat wall/candle impact")))
            self.frames(20)
            core.require(not self.field("state", bat), "Bat wall/candle puff exceeded its16-tick lifetime")

        parent, bat, _ = self.spawn_bat()
        self.hold_parent(parent)
        for key in ("xspeed", "yspeed"):
            self.set(key, bat, 0, "stationary floor target isolates the native96-tick lifetime")
        self.run_to(self.labels["GanonBat_Main_dissipate"], f"x == {bat}")
        core.require(self.field("timer_a", bat) == 0, "Stationary clear-floor bat ended before its native lifetime")
        life = self.assert_puff(parent, bat, "Bat lifetime expiry")
        self.frames(20)
        core.require(not self.field("state", bat), "Expired bat retained an immortal dissipation actor")
        self.result["cases"].append(dict(name="bat-walls-candles-and-bounded-lifetime", passed=True,
                                          surfaces=rows, lifetime=life))

    def orphan_and_room_guard(self):
        rows = []
        for fault in ("invalid-slot", "missing-parent", "wrong-parent-type", "dead-parent", "outside-room"):
            parent, bat, _ = self.spawn_bat()
            if fault == "invalid-slot":
                self.set("d", bat, 0xFF, "invalid parent index tests the native indexed-access guard")
            elif fault == "missing-parent":
                self.set("state", parent, 0, "declared gone parent tests orphan cleanup")
            elif fault == "wrong-parent-type":
                self.set("kind", parent, 0x46, "reused parent slot tests native type validation")
                self.set("action", parent, 2, "harmless reused slot does not execute boss behavior")
            elif fault == "dead-parent":
                self.set("action", parent, 6, "declared defeated human tests immediate child cleanup")
            else:
                x, y = self.position(bat)
                self.locate(bat, x ^ 0x200, y, "bat outside the current512px room must die before tile lookup wraps")
            self.run_to(self.labels["GanonBat_Main_kill"], f"x == {bat}")
            self.run_to(self.labels["Sprite_GanonBall_Long_not_active"], f"x == {bat}")
            core.require(self.field("state", bat) == 0 and not self.actors(1),
                         f"Native {fault} child survived or created fragments")
            rows.append(dict(fault=fault, state=self.field("state", bat)))
        self.result["cases"].append(dict(name="bat-parent-and-room-guards", passed=True, controls=rows))

    def occupy_slots(self, parent):
        slots = [slot for slot in range(16) if slot != parent]
        for slot in slots:
            for key, value in (("kind", 0x46), ("state", 9), ("action", 2), ("timer_a", 96), ("d", 0xFF)):
                self.set(key, slot, value, "declared harmless puff occupies one dynamic sprite slot")
        return slots

    def slot_exhaustion_recovery(self):
        parent = self.prepare_bat()
        occupied = self.occupy_slots(parent)
        self.run_to(self.labels["Ganondorf_CastBat_bat_spawned"], f"x == {parent}")
        core.require(not self.actors(3) and self.field("d", parent) == 0xFF,
                     "Full sprite table allocated a bat or corrupted the rally pointer")
        self.run_to(self.labels["Ganondorf_Stomp"], f"x == {parent}")
        core.require(self.field("action", parent) == 7, "No-slot bat cast failed to reach ordinary stomp recovery")
        bat_recovery = dict(occupied=occupied, action=self.field("action", parent), bat_count=len(self.actors(3)))

        parent = self.prepare()
        self.charge(parent)
        occupied = self.occupy_slots(parent)
        self.run_to(self.labels["Ganondorf_Cast_cancel"], f"x == {parent}")
        self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
        core.require(self.field("action", parent) == 1 and self.field("timer_a", parent) > 0
                     and self.field("d", parent) == 0xFF and not self.actors(0),
                     "No-slot normal cast did not return to Float for a bounded retry")
        self.result["cases"].append(dict(name="bat-and-rally-slot-exhaustion-recovery", passed=True,
                                          bat=bat_recovery, rally=dict(occupied=occupied,
                                              action=self.field("action", parent), timer=self.field("timer_a", parent))))


def main():
    return core.run_fixture(core.parse_args(), BatCastFixture,
                            ("human_cast_and_child_oam", "contact_and_native_sword", "walls_torches_and_lifetime",
                             "orphan_and_room_guard", "slot_exhaustion_recovery"))


if __name__ == "__main__":
    raise SystemExit(main())
