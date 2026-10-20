#!/usr/bin/env python3
"""Eight bounded, attach-only spacing and background-impact native checks.

Uses the ownership, exact-ROM/state identity, 180-second deadline and cleanup
of ganondorf_playtest_polish. Position/stage inputs, two native RNG seeds and
individually logged fallback torch/pit collision cells are declared fixtures.
No CPU/PC, HP, immunity, ROM, SRAM, launcher or visible-session writes occur.
"""
from __future__ import annotations

import ganondorf_playtest_polish as core


class SpacingImpactFixture(core.Fixture):
    def __init__(self, *args):
        super().__init__(*args)
        self.collision_writes = set()
        self.result["claim"] = "native controlled spacing, cast, no-teleport and impact checks; no human-play acceptance"

    def allowed_write(self, address):
        return (super().allowed_write(address) or address == 0x7E0FA1
                or address in self.collision_writes)

    def actors(self, action=None):
        return [i for i in range(16) if self.field("state", i)
                and self.field("kind", i) == 0x46
                and (action is None or self.field("action", i) == action)]

    def locate(self, slot, x, y, reason):
        for key, value in (("x", x & 255), ("xh", (x >> 8) & 255),
                           ("y", y & 255), ("yh", (y >> 8) & 255)):
            self.set(key, slot, value, reason)

    def link(self, x, y, reason):
        self.write16(0x7E0022, x & 0xFFFF, reason)
        self.write16(0x7E0020, y & 0xFFFF, reason)

    def origin(self, parent):
        x, y = self.position(parent)
        return x, (y - self.field("height", parent) - 32) & 0xFFFF

    def gap(self, parent):
        x, y = self.origin(parent)
        dx, dy = abs(self.r16(0x7E0022) - x), abs(self.r16(0x7E0020) - y)
        return max(dx, dy) + min(dx, dy) // 2

    def prepare(self, hits=9, local=(0x70, 0x88), gap=None, link_local=None):
        parent = self.restore()
        ox, oy = self.r(0x7E0023) << 8, self.r(0x7E0021) << 8
        self.locate(parent, ox + local[0], oy + local[1], "declared Float starting perch")
        for key, value in (("height", 16), ("e", 0), ("f", hits), ("action", 1),
                           ("timer_a", 0), ("timer_b", 0xFF), ("timer_c", 0),
                           ("timer_d", 0), ("a", 0), ("b", 0), ("d", 0xFF),
                           ("custom", 0), ("frame", 0), ("xspeed", 0), ("yspeed", 0)):
            self.set(key, parent, value, "native Float spacing input; no forced Cast")
        x, y = self.origin(parent)
        if link_local is None:
            self.link(x + (core.cast_band(hits)[0] + 16 if gap is None else gap), y,
                      "declared Link separation from actual projectile origin")
        else:
            self.link(ox + link_local[0], oy + link_local[1], "declared arena-edge Link position")
        return parent

    def charge(self, parent, budget=320, observe=False):
        rows = []
        step = 1 if observe else 4
        for _ in range(0, budget, step):
            if self.field("action", parent) == 2:
                core.require(core.cast_band(self.field("f", parent))[0] <= self.gap(parent)
                             <= core.cast_band(self.field("f", parent))[1], "Float charged outside its launch band")
                return rows
            core.require(self.field("action", parent) == 1 and not self.actors(),
                         "Waiting Float allocated a ball or entered an unexpected action")
            self.frames(step)
            self.arena_bounds(parent)
            rows.append(dict(position=self.position(parent), gap=self.gap(parent),
                             action=self.field("action", parent)))
        raise RuntimeError("Native spacing movement never reached a cast position")

    def birth(self, parent, observe=False):
        poses = []
        if observe:
            for _ in range(56):
                poses.append(self.field("frame", parent))
                if self.field("timer_a", parent) <= 7:
                    break
                self.frames(1)
                core.require(self.field("action", parent) == 2, "Safe native charge cancelled early")
            ordered = [frame for i, frame in enumerate(poses) if not i or frame != poses[i-1]]
            stages = [next((i for i, value in enumerate(poses) if value == frame), -1)
                      for frame in (12, 13, 14, 15, 16)]
            core.require(all(i >= 0 for i in stages) and stages == sorted(stages)
                         and any(frame in (10, 11) for frame in poses),
                         f"Native lift/gather/charge/windup sequence incomplete: {ordered}")
        self.run_to(self.labels["Ganondorf_SpawnBall"], f"x == {parent}")
        origin, gap = self.origin(parent), self.gap(parent)
        band = core.cast_band(self.field("f", parent))
        core.require(band[0] <= gap <= band[1], f"Release ignored launch band: {gap}/{band}")
        self.run_to(self.labels["Ganondorf_Cast_ball_spawned"], f"x == {parent}")
        ball = self.field("d", parent)
        core.require(ball < 16 and ball in self.actors(0), "Native Cast did not allocate its tracked normal ball")
        core.require(self.position(ball) == origin, "Allocated ball differs from measured height-adjusted launch origin")
        return ball, dict(origin=origin, gap=gap, band=band, charge_frames=poses)

    def spawn(self, hits, dx=0, dy=-96):
        parent = self.prepare(hits)
        self.charge(parent, observe=True)
        ball, row = self.birth(parent)
        self.run_to(self.labels["Ganondorf_WaitBall"], f"x == {parent}")
        x, y = self.position(parent)
        self.link(x + dx, y + dy, "post-allocation Link position isolates rally geometry from cast policy")
        return parent, ball, [row]

    def far_approach(self):
        parent = self.prepare(local=(0x38, 0x98), gap=136)
        before, gap = self.position(parent), self.gap(parent)
        self.frames(8)
        after = self.position(parent)
        core.require(self.field("action", parent) == 1 and not self.actors()
                     and after[0] > before[0] and self.gap(parent) < gap
                     and self.gap(parent) > 112 and self.field("xspeed", parent) == 4,
                     "Expired cooldown did not approach slowly without casting from too far away")
        self.result["cases"].append(dict(name="spacing-far-approach", passed=True,
                                          before=before, after=after, gap_before=gap, gap_after=self.gap(parent)))

    def close_retreat_and_edges(self):
        parent = self.prepare(gap=40)
        before, gap = self.position(parent), self.gap(parent)
        self.frames(8)
        core.require(self.field("action", parent) == 1 and not self.actors()
                     and self.position(parent)[0] < before[0] and gap < self.gap(parent) < 56
                     and self.field("xspeed", parent) == 0xF8,
                     "Expired cooldown did not retreat without casting from too close")
        edges = []
        for local in ((0x28, 0x38), (0xD0, 0x38), (0x28, 0xD0), (0xD0, 0xD0), (0x70, 0x58), (0x70, 0x50)):
            parent = self.prepare(3, link_local=local)
            rows = self.charge(parent)
            edges.append(dict(link_local=local, ticks_upper_bound=len(rows)*4,
                              position=self.position(parent), gap=self.gap(parent)))
        self.result["cases"].append(dict(name="spacing-close-retreat-and-edge-liveness", passed=True,
                                          retreat_from=before, edges=edges))

    def staged_launches(self):
        for hits, speed in ((9, 0x10), (6, 0x14), (3, 0x18)):
            parent = self.prepare(hits)
            self.charge(parent, observe=True)
            ball, row = self.birth(parent, observe=hits == 9)
            core.require(self.field("e", ball) == speed, "Native launch speed differs from remaining-hit stage")
            if hits == 9:
                row["body_dma"] = self.block(0xA000, 0x1800, "SnesVideoRam") == self.raw(self.labels["GanondorfGraphics"], 0x1800)
                row["floor_dma"] = self.block(0xB800, 0x800, "SnesVideoRam") == self.raw(self.labels["GanondorfFloorGraphics"], 0x800)
                core.require(row["body_dma"] and row["floor_dma"], "Resident body/floor VRAM differs from exact candidate ROM")
            self.result["cases"].append(dict(name=f"spacing-native-launch-{hits}", passed=True,
                                              parent=parent, ball=ball, speed=speed, **row))

    def release_rush(self):
        parent = self.prepare()
        self.charge(parent, observe=True)
        self.frames(8)
        x, y = self.origin(parent)
        self.link(x + 8, y, "declared Link rush during charge; release must recheck spacing")
        self.run_to(self.labels["Ganondorf_Cast_cancel"], f"x == {parent}")
        core.require(self.gap(parent) < 56 and not self.actors(), "Rush fixture did not reach unsafe release cancellation")
        end = self.labels["Ganondorf_WaitBall"] - 1
        core.require(self.raw(end, 1) == b"\x60", "Cancel return boundary differs from native RTS")
        self.run_to(end, f"x == {parent}")
        state = {key: self.field(key, parent) for key in ("action", "timer_a", "a", "b", "frame", "xspeed", "yspeed")}
        core.require(state == dict(action=1, timer_a=8, a=0, b=0, frame=0, xspeed=0, yspeed=0)
                     and not self.actors(), f"Unsafe release did not retry cleanly: {state}")
        x, y = self.origin(parent)
        self.link(x + 72, y, "safe gap after cancelled cast permits ordinary retry")
        self.charge(parent, budget=40)
        ball, retry = self.birth(parent)
        self.result["cases"].append(dict(name="spacing-release-rush-retry", passed=True,
                                          cancelled=state, retry_ball=ball, retry=retry))

    def no_warp_and_bat(self):
        self.active_volley_no_warp()
        self.result["cases"][-1]["between_volley_bat_cast"] = self.bat_control()

    def bat_only(self):
        self.result["cases"].append(dict(name="between-volley-bat", passed=True,
                                          cast=self.bat_control()))

    def bat_control(self):
        parent = self.prepare()
        # FRAME can stop after the next action has already dispatched. Use
        # the native Main boundary before selecting the independent action.
        self.run_to(self.labels["Ganondorf_Main"], f"x == {parent}")
        for key, value in (("d", 0xFF), ("action", 5), ("timer_a", 48), ("frame", 12)):
            self.set(key, parent, value, "declared between-volley bat cast; no active rally ball")
        poses, flaps, children = [], [], set()
        for _ in range(50):
            self.frames(1)
            action = self.field("action", parent)
            if action == 7:
                break
            core.require(action == 5 and not self.actors(0) and self.field("d", parent) == 0xFF,
                         "Human bat cast entered a rally or changed its rally-ball pointer")
            poses.append(self.field("frame", parent))
            bats = self.actors(3)
            core.require(len(bats) <= 1, "One human bat cast allocated multiple independent children")
            for child in bats:
                children.add(child)
                core.require(self.field("d", child) == parent,
                             "Cast bat does not retain its independent parent reference")
                flaps.append(self.field("frame", child))
        core.require(action == 7 and set(poses) == {12, 16, 5, 17, 18},
                     "Human bat cast did not complete its five authored poses before stomp recovery")
        core.require(len(children) == 1 and set(flaps) == {19, 20, 21},
                     "Independent bat did not animate all three authored flap frames")
        return dict(parent=parent, children=sorted(children), human_frames=poses, bat_frames=flaps)

    def collision_map(self, ball):
        floor = self.r(0x7E0F20 + ball)
        base = 0x7F2000 + (0x1000 if floor else 0)
        return base, self.block(base, 0x1000)

    def surface(self, ball, attr=None):
        base, cells = self.collision_map(ball)
        table = self.raw(0x0DB971, 256)
        def solid(value):
            return value not in (0, 0x1C, 0x20, 0x21, 0x22) and value not in range(0x10, 0x14) and table[value] not in (0, 4)
        def clear(value):
            return value not in range(0x10, 0x14) and value not in range(0xC0, 0xD0) and not solid(value)
        candidates = [i for i, value in enumerate(cells)
                      if 34 <= i % 64 <= 62 and 5 <= i // 64 <= 25
                      and clear(cells[i-1]) and clear(cells[i-2])
                      and (value == attr if attr is not None else solid(value))]
        injected = False
        if not candidates:
            core.require(attr is not None, "Current room contains no reachable native wall test cell")
            candidates = [i for i, value in enumerate(cells)
                          if 38 <= i % 64 <= 54 and 10 <= i // 64 <= 20
                          and value in (0, 0x1C) and cells[i-1] in (0, 0x1C)
                          and cells[i-2] in (0, 0x1C) and cells[i+64] in (0, 0x1C)]
            core.require(candidates, "No clear floor cell for declared torch/pit attribute fixture")
            address = base + candidates[0]
            self.collision_writes.add(address)
            self.write(address, attr, "declared fallback collision attribute; natural torch absent or pit control")
            injected = True
        index = candidates[0]
        return dict(address=base+index, attr=self.r(base+index), injected=injected,
                    x=(index % 64)*8, y=(index // 64)*8)

    def place_impact(self, parent, ball, surface, reflected):
        # Native lookup masks world coordinates to the current 512px room.
        ox, oy = self.r16(0x7E0022) & 0xFE00, self.r16(0x7E0020) & 0xFE00
        x, y = ox + surface["x"] - 14, oy + surface["y"] - 2
        self.locate(ball, x, y, "leading edge enters selected live background collision cell")
        self.locate(parent, x + 48, y + 16, "parent target keeps reflected native aim toward selected wall")
        for key, value in (("action", 0), ("b", int(reflected)), ("c", 2), ("d", parent),
                           ("height", 0), ("xspeed", 0x10), ("yspeed", 0), ("e", 0x10)):
            self.set(key, ball, value, "normal outgoing/reflected impact input")
        self.set("height", parent, 16, "reflected aim target shares the ball's vertical origin")
        self.set("timer_c", parent, 0xFF, "freeze parent movement during one collision probe")
        self.set("d", parent, ball, "parent tracks the normal ball before impact")
        self.link(ox + 0x80, oy + 0xC0, "Link away from collision probe and shard fan")

    def impact_matrix(self):
        rows, damaging_proved = [], False
        for attr in (None, 0xC0, 0xCF, 0x20, 0x21, 0x22):
            for reflected in (False, True):
                outcomes = []
                for seed in ((0, 1) if attr is None else (0,)):
                    parent, ball, _ = self.spawn(9)
                    surface = self.surface(ball, attr)
                    self.place_impact(parent, ball, surface, reflected)
                    if attr in (0x20, 0x21, 0x22):
                        label = "GanonBall_Main_return_clear" if reflected else "GanonBall_Main_outgoing_clear"
                        self.run_to(self.labels[label], f"x == {ball}")
                        core.require(self.field("action", ball) == 0 and self.field("d", parent) == ball,
                                     "Pit-control attribute incorrectly dissipated the energy ball")
                        outcomes.append(dict(seed=None, shards=0, passable=True))
                        continue
                    self.run_to(self.labels["GanonBall_ImpactRoll"], f"x == {ball}")
                    core.require(self.field("action", ball) == 2 and self.field("timer_a", ball) == 16
                                 and self.field("d", parent) == 0xFF and self.field("d", ball) == 0xFF,
                                 "Background impact did not stop/detach the ball before native RNG")
                    self.write(0x7E0FA1, seed, "declared native GetRandomInt seed parity; no forced CPU branch")
                    self.run_to(self.labels["GanonBall_ImpactNoShards"], f"x == {ball}")
                    shards = self.actors(1)
                    core.require(len(shards) in (0, 3), "Native impact produced a partial or repeated shard burst")
                    for child in shards:
                        core.require(self.field("timer_a", child) == 40 and self.field("d", child) == 0xFF
                                     and self.r(0x7E0CD2+child) == 1 and self.r(0x7E0F60+child) & 31 == 0x19
                                     and self.field("xspeed", child) == 0xE8,
                                     "Shard TTL, independence, native damage box or inward fan differs")
                    detail = dict(seed=seed, rng_after=self.r(0x7E0FA1), shards=len(shards))
                    if shards and not damaging_proved:
                        child = shards[0]
                        core.require(self.r(0x7E037B) == 0 and self.r(0x7E031F) == 0,
                                     "Checkpoint has player immunity; cannot prove native shard damage")
                        hp = self.r(0x7EF36D)
                        x, y = self.position(child)
                        self.link(x, y-8, "declared player overlap tests the shard's ordinary native damage contact")
                        self.frames(3)
                        core.require(self.r(0x7EF36D) < hp, "Independent shard failed to damage Link through native contact")
                        detail["native_damage"] = dict(hp_before=hp, hp_after=self.r(0x7EF36D))
                        # A separate independent child hits the same wall. Its
                        # native shard path must dissipate without another fan.
                        other = next((i for i in shards[1:] if self.field("state", i)
                                      and self.field("action", i) == 1), None)
                        core.require(other is not None, "No second live shard for the no-repeat-burst control")
                        ox, oy = self.r16(0x7E0022) & 0xFE00, self.r16(0x7E0020) & 0xFE00
                        self.locate(other, ox+surface["x"]-11, oy+surface["y"]-4,
                                    "declared child-wall input must not emit another shard burst")
                        self.set("xspeed", other, 16, "one native child tick enters the wall leading edge")
                        self.set("yspeed", other, 0, "horizontal child-wall control")
                        count_before = len(self.actors())
                        self.run_to(self.labels["GanonBall_StartDissipation"], f"x == {other}")
                        self.run_to(self.labels["Sprite_GanonBall_Long_not_active"], f"x == {other}")
                        core.require(self.field("action", other) == 2 and self.field("timer_a", other) == 16
                                     and len(self.actors()) <= count_before,
                                     "Child-wall contact emitted another burst or retained damage action")
                        detail["child_wall_no_repeat_burst"] = dict(slot=other, actor_count_before=count_before,
                                                                    actor_count_after=len(self.actors()))
                        damaging_proved = True
                    outcomes.append(detail)
                    if attr is None and seed == 0:
                        # Normal impact art must finish without retaining an immortal effect.
                        self.frames(20)
                        core.require(not self.field("state", ball), "Normal dissipation exceeded its16-tick lifetime")
                if attr is None:
                    core.require({row["shards"] for row in outcomes} == {0, 3},
                                 "Native seeded wall controls did not exercise both50% outcomes")
                rows.append(dict(surface=surface, reflected=reflected, outcomes=outcomes))
        core.require(damaging_proved, "Impact matrix did not prove an independent dangerous shard")
        self.result["cases"].append(dict(name="background-impact-and-pit-matrix", passed=True, rows=rows))


def main():
    return core.run_fixture(core.parse_args(), SpacingImpactFixture,
                            ("far_approach", "close_retreat_and_edges", "staged_launches",
                             "release_rush", "no_warp_and_bat", "impact_matrix"))


if __name__ == "__main__":
    raise SystemExit(main())
