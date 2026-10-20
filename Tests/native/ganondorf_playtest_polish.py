#!/usr/bin/env python3
"""Attach-only Ganondorf palette, volley, movement, stomp and OAM fixture.

Caller supplies a paused, owned headless session and an arrival state created by
that exact candidate ROM. This script never launches/stops Mesen, writes CPU/PC,
changes ROM bytes, saves SRAM, or attaches to the user's visible fight. Logged
RAM inputs select charge/return conditions, warp eligibility and floor phase.
Native routines perform charge, return, three glide modes, warp, stomp and pit replacement.
Four-way ball aim/recoil remains independent of front/rear-only active body art.
The hidden-warp contact check includes a visible-contact positive control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
CLIENT_ROOT = Path.home() / "src/hobby/mesen2-oos/tools/oos_client"
TABLES = {"y": 0x0D00, "x": 0x0D10, "yh": 0x0D20, "xh": 0x0D30,
          "yspeed": 0x0D40, "xspeed": 0x0D50, "action": 0x0D80,
          "frame": 0x0D90, "a": 0x0DA0, "b": 0x0DB0, "c": 0x0DE0,
          "timer_a": 0x0DF0, "timer_b": 0x0E00, "timer_c": 0x0E10,
          "timer_d": 0x0EE0, "kind": 0x0E20, "subtype": 0x0E30,
          "d": 0x0E90, "e": 0x0EB0, "f": 0x0EC0, "state": 0x0DD0,
          "g": 0x0ED0, "height": 0x0F70, "flash": 0x0B89,
          "custom": 0x1CC0}
# SprMiscC keeps its four-way recoil meaning. SprCustom bit7 independently
# freezes front/rear body art for the stroke; its low two bits select a glide.
DIRECTIONS = (("front", 0, 0, 64, 1, 5), ("right", 1, 64, 0, 1, 5),
              ("left", 2, -64, 0, 1, 5), ("rear", 3, 0, -96, 8, 9),
              ("upper-right", 1, 64, -64, 8, 9),
              ("upper-left", 2, -64, -64, 8, 9),
              ("upper-horizontal", 1, 96, -8, 8, 9))
MOVEMENT_MODES = ((0, "clockwise"), (1, "counterclockwise"), (2, "weave"))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def digest(blob, algorithm="sha256"):
    return hashlib.new(algorithm, blob).hexdigest()


def payload(reply):
    require(reply.get("success"), "Native command rejected: " + str(reply))
    value = reply.get("data", {})
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def offset(address):
    require(address & 0x8000, "Expected LoROM ROM address")
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def symbols(text):
    result = {}
    priority = {}
    used_code = {"GanondorfPalette", "Ganon_DrawFrame", "Ganondorf_Draw_skip",
                 "Sprite_GanonBall_Long", "GanonBall_Main", "GanonBall_CheckSwordReflect",
                 "GanonBall_SetReturnFacing", "Ganondorf_Float", "Ganondorf_WaitBall", "Ganondorf_Stunned",
                 "Ganondorf_VolleyMove", "Ganondorf_StartStomp", "Ganondorf_Stomp",
                 "Ganondorf_Stomp_done", "Ganondorf_SpawnFloorCollapse",
                 "Ganondorf_WaitBall_contact_done"}
    used_code.update("Ganon_DrawFrame_" + name for name in
                     ("start_index", "nbr_of_tiles", "chr", "x_offsets", "y_offsets"))
    for bank, address, name in re.findall(
            r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)\s*$", text, re.M):
        preferred = int(name.startswith("Oracle_"))
        name = name.removeprefix("Oracle_")
        value = int(bank + address, 16)
        if name in result:
            if preferred < priority[name]:
                continue
            if preferred == priority[name] and name in used_code:
                require(result[name] == value, "Ambiguous fixture code symbol: " + name)
        result[name] = value
        priority[name] = preferred
    return result


class Fixture:
    def __init__(self, args, bridge, image, labels):
        self.a, self.b, self.image, self.labels = args, bridge, image, labels
        self.rom_sha1 = digest(image, "sha1")
        self.breakpoints = set()
        self.charge_checked = False
        self.deadline = time.monotonic() + 180
        self.result = {"passed": False, "cases": [], "writes": [], "cleanup_errors": [],
                       "claim": "native controlled volley/draw/mobility/stomp/contact fixtures; no human-play acceptance",
                       "rom_sha256": digest(image), "rom_sha1": self.rom_sha1,
                       "symbols_sha256": digest(args.symbols.read_bytes()),
                       "state_sha256": digest(args.state.read_bytes())}

    def owner(self, deadline=True):
        if deadline:
            require(time.monotonic() < self.deadline, "180-second fixture deadline exceeded")
        raw = self.a.owner_file.read_text().strip()
        try:
            record = json.loads(raw)
        except ValueError:
            record = None
        if isinstance(record, dict):
            require(record.get("owner") == self.a.owner and record.get("active", True) is True,
                    "Caller no longer owns active native reservation")
            for key in ("socket", "socketPath"):
                if key in record:
                    require(record[key] == self.a.socket, "Reservation socket differs")
        else:
            require(raw == self.a.owner, "Heavy-lock owner differs")
        info = self.b.get_rom_info()
        require(str(info.get("sha1", "")).lower() == self.rom_sha1,
                "Loaded raw ROM SHA1 differs from --rom")
        return info

    def paused(self):
        for _ in range(50):
            if payload(self.b.send_command("STATE")).get("paused") is True:
                return True
            time.sleep(0.003)
        return False

    def r(self, address):
        return self.b.read_memory(address)

    def r16(self, address):
        return self.b.read_memory16(address)

    def field(self, key, slot):
        return self.r(0x7E0000 + TABLES[key] + slot)

    def block(self, address, count, memtype=None):
        blob = bytes(self.b.read_block(address, count, memtype=memtype))
        require(len(blob) == count, f"Short native read: {address:06X}")
        return blob

    def raw(self, address, count):
        start = offset(address)
        blob = self.image[start:start + count]
        require(len(blob) == count, "ROM table exceeds image")
        return blob

    def table(self, name, count):
        return self.raw(self.labels["Ganon_DrawFrame_" + name], count)

    def after_jsr(self, start, end, target):
        entry = self.labels[start]
        code = self.raw(entry, self.labels[end] - entry)
        call = b"\x20" + (self.labels[target] & 0xFFFF).to_bytes(2, "little")
        require(code.count(call) == 1, f"Missing/ambiguous native {start} -> {target} JSR")
        return entry + code.index(call) + 3

    def write(self, address, value, reason):
        allowed = address in (0x7E0020, 0x7E0021, 0x7E0022, 0x7E0023)
        allowed |= any(0x7E0000 + table <= address < 0x7E0010 + table
                       for table in TABLES.values())
        require(allowed, f"Forbidden fixture address: {address:06X}")
        self.owner()
        require(self.paused(), "Fixture RAM write requires paused CPU")
        row = {"address": f"{address:06X}", "before": self.r(address),
               "value": value & 255, "reason": reason}
        self.result["writes"].append(row)
        with (self.a.out / "writes.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
            stream.flush()
        require(self.b.write_memory(address, value & 255), "Fixture write rejected")
        require(self.r(address) == (value & 255), "Fixture write readback differs")

    def set(self, key, slot, value, reason):
        self.write(0x7E0000 + TABLES[key] + slot, value, reason)

    def write16(self, address, value, reason):
        self.write(address, value & 255, reason)
        self.write(address + 1, (value >> 8) & 255, reason)

    def position(self, slot):
        return (self.field("x", slot) | self.field("xh", slot) << 8,
                self.field("y", slot) | self.field("yh", slot) << 8)

    def find(self, kind):
        found = [i for i in range(16) if self.field("state", i) and self.field("kind", i) == kind]
        require(len(found) <= 1, f"Multiple fixture actors of type {kind:02X}")
        return found[0] if found else None

    def neutral(self):
        payload(self.b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"}))

    def frames(self, count):
        self.owner()
        require(self.paused() and not self.breakpoints, "FRAME requires paused CPU without breakpoints")
        self.neutral()
        before = number(payload(self.b.send_command("STATE"))["frame"])
        payload(self.b.send_command("FRAME", {"count": str(count)}))
        until = min(self.deadline, time.monotonic() + 5)
        while time.monotonic() < until:
            after = number(payload(self.b.send_command("STATE"))["frame"])
            if after >= before + count and self.paused():
                require(after <= before + count + 1, "Native FRAME overshot")
                return
            time.sleep(0.003)
        raise RuntimeError("Native FRAME deadline exceeded")

    def run_to(self, address, condition):
        self.owner()
        require(self.paused(), "Breakpoint execution requires paused CPU")
        initial_cpu = self.b.get_cpu_state()
        initial_pc = number(initial_cpu.get("pc", initial_cpu.get("PC", -1)))
        initial_frame = self.r(0x7E001A)
        ident = self.b.add_breakpoint(address, condition=condition)
        require(isinstance(ident, int) and ident >= 0, "Owned breakpoint rejected")
        self.breakpoints.add(ident)
        try:
            require(self.b.resume(), "Owned resume rejected")
            until = min(self.deadline, time.monotonic() + 4)
            while time.monotonic() < until:
                if self.paused():
                    cpu = self.b.get_cpu_state()
                    actual = number(cpu.get("pc", cpu.get("PC", -1)))
                    target_hit = (actual & 0xFFFF) == (address & 0xFFFF)
                    progressed = ((initial_pc & 0xFFFF) != (address & 0xFFFF)
                                  or self.r(0x7E001A) != initial_frame)
                    if target_hit and progressed:
                        return cpu
                time.sleep(0.003)
            require(self.b.pause(), "Breakpoint timeout pause rejected")
            raise RuntimeError(f"Breakpoint timeout: {address:06X}; {condition}")
        finally:
            require(self.b.remove_breakpoint(ident), "Owned breakpoint removal rejected")
            self.breakpoints.remove(ident)

    def restore(self):
        self.owner()
        require(self.paused() and not self.breakpoints, "State load requires paused CPU without breakpoints")
        require(self.b.load_state(path=str(self.a.state.resolve())), "Candidate state load rejected")
        time.sleep(0.15)
        require(self.b.pause(), "Pause after state load rejected")
        require(self.paused(), "Pause after state load did not settle")
        self.owner()
        self.neutral()
        require(self.r(0x7E0010) == 7 and self.r(0x7E0011) == 0 and self.r16(0x7E00A0) == 0,
                "Fresh candidate state must be room00, module07/00")
        parent = self.find(0xD3)
        require(parent is not None, "Fresh candidate arrival state lacks Ganondorf")
        require(self.find(0x46) is None, "Arrival state must precede first active energy ball")
        return parent

    def draw(self, parent, expected, extra="", screenshot=None):
        previous = self.r(0x7E001A)
        wanted = " || ".join(f"[$0D90+x] == {frame}" for frame in expected)
        condition = f"x == {parent} && [$1A] != {previous} && ({wanted})"
        if extra:
            condition += " && (" + extra + ")"
        self.run_to(self.labels["Ganondorf_Draw_skip"], condition)
        frame = self.field("frame", parent)
        require(frame in expected, "Completed native draw selected an unexpected frame")
        timer = self.field("timer_c", parent)
        pointer = self.r16(0x7E0090)
        require(0x0800 <= pointer <= 0x09E0, f"Unexpected OAM allocation: {pointer:04X}")
        first = self.table("start_index", 12)[frame]
        count = self.table("nbr_of_tiles", 12)[frame] + 1
        blob = self.block(0x7E0000 | pointer, 32)
        entries = [dict(x=blob[i*4], y=blob[i*4+1], tile=blob[i*4+2], properties=blob[i*4+3])
                   for i in range(8)]
        tiles = self.table("chr", first + count)
        xoff = self.table("x_offsets", (first + count)*2)
        yoff = self.table("y_offsets", (first + count)*2)
        x, y = self.position(parent)
        base_x = x - self.r16(0x7E00E2)
        base_y = y - self.r16(0x7E00E8) - self.field("height", parent)
        kick = (0, 0)
        if self.field("action", parent) == 3 and self.field("b", parent) and timer:
            facing = self.field("c", parent)
            follow = ((0, 2), (2, 0), (-2, 0), (0, -2))
            kick = follow[facing] if timer <= 8 else tuple(-n for n in follow[facing])
        for index, table_index in enumerate(reversed(range(first, first + count))):
            item = entries[index]
            dx = int.from_bytes(xoff[table_index*2:table_index*2+2], "little", signed=True)
            dy = int.from_bytes(yoff[table_index*2:table_index*2+2], "little", signed=True)
            require(item["tile"] == tiles[table_index], "Live OAM tile differs from resident frame")
            require((item["properties"] >> 1) & 7 == 6, "Ganondorf/held ball OAM must select OBJ6")
            require(item["x"] == (base_x + dx + kick[0]) & 255
                    and item["y"] == (base_y + dy + kick[1]) & 255,
                    f"Draw-only recoil/offset differs: frame{frame}, piece{index}, kick{kick}")
            require(item["y"] < 0xF0, "Expected visible body/held-ball piece is hidden")
        require((entries[7]["properties"] >> 1) & 7 == 4 and entries[7]["y"] < 0xF0,
                "Ground shadow must remain visible on OBJ4")
        row = dict(frame=frame, timer=timer, facing=self.field("c", parent),
                   game_frame=self.r(0x7E001A), oam_pointer=pointer, pieces=count,
                   kick=kick, entries=entries, position=[x, y])
        if screenshot:
            picture = self.b.screenshot()
            require(picture, "Native screenshot rejected")
            path = self.a.out / (screenshot + ".png")
            path.write_bytes(picture)
            row["screenshot"] = str(path)
        return row

    def palette_and_intro(self):
        parent = self.restore()
        self.frames(4)
        palette = self.raw(self.labels["GanondorfPalette"] + 2, 30)
        checks = dict(cgram=self.block(0x1C2, 30, "SnesCgRam") == palette,
                      live_buffer=self.block(0x7EC6C2, 30) == palette,
                      fade_buffer=self.block(0x7EC4C2, 30) == palette)
        require(all(checks.values()), "OBJ6 CGRAM or palette buffers differ from generated art")
        shadow = int.from_bytes(self.block(0x19A, 2, "SnesCgRam"), "little")
        art13 = int.from_bytes(palette[24:26], "little")
        channels = [shadow & 31, (shadow >> 5) & 31, (shadow >> 10) & 31]
        require(shadow != art13 and max(channels) <= 10, "OBJ4 shadow color13 is not independently dark")
        self.set("action", parent, 0, "observe native Intro draw on consecutive frames")
        self.set("timer_a", parent, 0x40, "keep Intro active for four native draws")
        self.set("frame", parent, 0, "Intro's idle frame")
        self.set("flash", parent, 0, "remove fixture hit-flash color influence")
        draws = [self.draw(parent, (0,)) for _ in range(4)]
        require(all((b["game_frame"] - a["game_frame"]) & 255 == 1
                    for a, b in zip(draws, draws[1:])), "Intro draw skipped a native game frame")
        self.result["cases"].append(dict(name="palette-shadow-intro", passed=True,
                                          palette=checks, shadow_word=shadow,
                                          shadow_channels=channels, art_color13=art13, draws=draws))

    def spawn(self, hits, dx=0, dy=-96):
        parent = self.restore()
        x, y = self.position(parent)
        if dx == 0 and dy < 0:
            # The ball appears32px above the hovering body. A64px Link offset
            # can overlap its first hitbox; retain a clear native launch gap.
            dy = min(dy, -96)
        self.write16(0x7E0022, (x + dx) & 0xFFFF, "controlled Link position for native projectile aim")
        self.write16(0x7E0020, (y + dy) & 0xFFFF, "controlled Link position for native projectile aim")
        for key, value in (("f", hits), ("action", 2), ("timer_a", 0x20), ("timer_c", 0),
                           ("timer_b", 0xFF), ("timer_d", 0), ("g", 0), ("subtype", 0),
                           ("frame", 10), ("b", 0), ("xspeed", 0), ("yspeed", 0), ("flash", 0)):
            self.set(key, parent, value, "normal native Cast at selected remaining-hit stage")
        if not self.charge_checked:
            charge = [self.draw(parent, (frame,), screenshot=f"charge-{frame}") for frame in (10, 11)]
            require(all(row["pieces"] == 7 for row in charge), "Charge must draw six body pieces plus held ball")
            self.result["cases"].append(dict(name="initial-front-charge-oam", passed=True, draws=charge))
            self.charge_checked = True
        observed = []
        for _ in range(36):
            self.frames(1)
            frame = self.field("frame", parent)
            observed.append(frame)
            require(frame in (0, 5, 10, 11), "Initial cast selected a nonfront frame")
            ball = self.find(0x46)
            if ball is not None:
                require(self.field("b", parent) == 0, "Initial cast incorrectly marked as a return")
                return parent, ball, observed
        raise RuntimeError("Native Cast did not allocate its energy ball within36 frames")

    def launch_stages(self):
        for hits, expected in ((9, 0x10), (6, 0x14), (3, 0x18)):
            parent, ball, frames = self.spawn(hits)
            speed = self.field("e", ball)
            require(speed == expected, f"Launch stage {hits} expected{expected:02X}, got{speed:02X}")
            # Stop after the ball's own native draw, before its movement/main.
            entry = self.labels["Sprite_GanonBall_Long"]
            target = self.labels["Ganon_DrawFrame"]
            code = self.raw(entry, 40)
            call = b"\x20" + (target & 0xFFFF).to_bytes(2, "little")
            require(code.count(call) == 1, "Missing/ambiguous native ball draw JSR")
            self.run_to(entry + code.index(call) + 3, f"x == {ball}")
            pointer = self.r16(0x7E0090)
            require(0x0800 <= pointer <= 0x09FC, "Unexpected active-ball OAM allocation")
            active_oam = self.block(0x7E0000 | pointer, 4)
            require((active_oam[3] >> 1) & 7 == 6 and active_oam[1] < 0xF0,
                    "Active energy ball must remain visible on OBJ6")
            self.result["cases"].append(dict(name=f"launch-{hits}-remaining", passed=True,
                                              parent=parent, ball=ball, speed=speed,
                                              initial_front_frames=frames,
                                              active_ball_oam=list(active_oam)))

    def return_cases(self):
        entry = self.labels["GanonBall_Main"]
        end = self.labels["GanonBall_CheckSwordReflect"]
        target = self.labels["GanonBall_SetReturnFacing"]
        code = self.raw(entry, end - entry)
        call = b"\x20" + (target & 0xFFFF).to_bytes(2, "little")
        require(code.count(call) == 1, "Missing/ambiguous native return-facing JSR")
        after_facing = entry + code.index(call) + 3
        for index, (name, facing, dx, dy, windup, follow) in enumerate(DIRECTIONS):
            parent, ball, _ = self.spawn(9, dx, dy)
            x, y = self.position(parent)
            height = self.field("height", parent)
            mode = index % 3
            self.set("custom", parent, mode, "return-facing flag must preserve the selected glide mode")
            for key, value in (("x", x & 255), ("xh", x >> 8),
                               ("y", (y-height) & 255), ("yh", ((y-height) & 0xFFFF) >> 8),
                               ("height", 0), ("b", 1), ("c", 1), ("d", parent), ("e", 0x10)):
                self.set(key, ball, value, "controlled reflected ball near its parent's hitbox")
            self.set("c", parent, (facing + 1) % 4, "stale chase facing must be replaced by native outgoing aim")
            self.run_to(after_facing, f"x == {ball}")
            state = {key: self.field(key, parent) for key in ("b", "c", "timer_c", "frame", "custom")}
            frozen = 0x80 if dy < 0 else 0
            require(state == dict(b=1, c=facing, timer_c=16, frame=windup, custom=mode | frozen),
                    f"Native return state differs for {name}: {state}")
            aim = {key: self.field(key, ball) for key in ("xspeed", "yspeed")}
            if dx:
                require(aim["xspeed"] != 0 and bool(aim["xspeed"] & 0x80) == (dx < 0),
                        f"Native ball aim reversed its horizontal direction for {name}")
            else:
                require(aim["yspeed"] != 0 and bool(aim["yspeed"] & 0x80) == (dy < 0),
                        f"Native ball aim reversed its vertical direction for {name}")
            first = self.draw(parent, (windup,), "[$0E10+x] >= 11", "return-" + name + "-windup")
            crossed_y = None
            if name == "upper-horizontal":
                crossed_y = (self.position(parent)[1] + 48) & 0xFFFF
                self.write16(0x7E0020, crossed_y,
                             "Link crosses below the boss; return art must retain its frozen rear facing")
            second = self.draw(parent, (follow,), "[$0E10+x] >= 1 && [$0E10+x] <= 6",
                               "return-" + name + "-follow")
            require(first["kick"] == tuple(-v for v in second["kick"]),
                    "Return recoil did not reverse between windup and follow through")
            if frozen:
                require(first["frame"] == 8 and second["frame"] == 9,
                        "Rear return displayed a front pose")
            require(self.field("custom", parent) == (mode | frozen),
                    "Native stroke changed its frozen facing or glide mode")
            self.result["cases"].append(dict(name="return-" + name, passed=True,
                                              native_contact=state, ball_aim=aim,
                                              crossed_link_y=crossed_y, windup=first, follow=second))

    def rally_mobility(self):
        after_move = self.after_jsr("Ganondorf_WaitBall", "Ganondorf_Stunned", "Ganondorf_VolleyMove")
        deltas = []
        for mode, name in MOVEMENT_MODES:
            parent = self.restore()
            x, y = self.position(parent)
            self.write16(0x7E0022, x + 64, "Link to the right for a native Float direction check")
            self.write16(0x7E0020, y - 32, "Link above selects rear Float art independently of glide direction")
            for key, value in (("custom", mode), ("action", 1), ("timer_a", 0xFF),
                               ("frame", 0), ("b", 0), ("timer_c", 0), ("timer_d", 0)):
                self.set(key, parent, value, "controlled native Float in one of three glide modes")
            hover = []
            for _ in range(8):
                self.frames(1)
                frame = self.field("frame", parent)
                require(self.field("action", parent) == 1 and frame in (8, 9),
                        f"Float selected side/front art with Link above in mode{mode}: frame{frame}")
                self.arena_bounds(parent)
                hover.append(dict(position=self.position(parent), frame=frame))
            self.write16(0x7E0020, self.position(parent)[1] + 48,
                         "Link below selects front Float art without changing glide mode")
            self.frames(1)
            require(self.field("action", parent) == 1 and self.field("frame", parent) == 0,
                    f"Float did not return to front art with Link below in mode{mode}")

            parent, ball, _ = self.spawn(9, 0, 64)
            for key, value in (("custom", mode), ("timer_c", 0), ("b", 0)):
                self.set(key, parent, value, "finished initial stroke permits one native rally glide mode")
            start = self.position(parent)
            positions = [start]
            for _ in range(8):
                self.frames(1)
                require(self.field("action", parent) == 3 and self.field("state", ball)
                        and self.field("kind", ball) == 0x46,
                        f"Glide mode{mode} interrupted the active native volley")
                require(self.field("frame", parent) in (0, 1, 5, 8, 9),
                        f"WaitBall selected side art in mode{mode}")
                self.arena_bounds(parent)
                positions.append(self.position(parent))
            require(any(position != start for position in positions[1:]),
                    f"Rally glide mode{mode} did not change world position")
            require(self.field("f", parent) == 9, "Rally glide changed remaining-hit count")
            delta = tuple(end - begin for begin, end in zip(start, positions[-1]))
            deltas.append(delta)

            self.set("b", parent, 1, "a native return stroke keeps the current world position")
            self.set("timer_c", parent, 0x10, "observe four uninterrupted native stroke ticks")
            stroke_start = self.position(parent)
            for _ in range(4):
                self.frames(1)
                require(self.position(parent) == stroke_start and self.field("timer_c", parent) > 0,
                        f"Glide mode{mode} moved during the protected return stroke")
                require(self.field("frame", parent) in (1, 5, 8, 9),
                        f"WaitBall stroke selected side art in mode{mode}")
            self.set("timer_c", parent, 0, "resume native glide for full16-bit clamp probes")
            clamps = []
            origin_x = self.r(0x7E0023) << 8
            origin_y = self.r(0x7E0021) << 8
            # Deliberately cross quadrant high bytes. Low-byte-only clamps
            # would accept these positions and leave the boss off screen.
            for px, py in ((origin_x - 1, origin_y - 1),
                           (origin_x + 0x100, origin_y + 0x100)):
                self.set("x", parent, px & 255, "out-of-quadrant X for native full16-bit arena clamp")
                self.set("xh", parent, (px & 0xFFFF) >> 8, "out-of-quadrant X high byte")
                self.set("y", parent, py & 255, "out-of-quadrant Y for native full16-bit arena clamp")
                self.set("yh", parent, (py & 0xFFFF) >> 8, "out-of-quadrant Y high byte")
                self.run_to(after_move, f"x == {parent}")
                self.arena_bounds(parent)
                require(self.field("custom", parent) & 3 == mode,
                        "Arena clamp changed the selected glide mode")
                clamps.append(dict(before=[px & 0xFFFF, py & 0xFFFF], after=self.position(parent)))
            self.result["cases"].append(dict(name="rally-native-" + name, passed=True,
                                              mode=mode, parent=parent, ball=ball, float_draws=hover,
                                              positions=positions, delta=delta,
                                              protected_stroke_position=stroke_start, clamps=clamps))
        require(len(set(deltas)) == 3, f"Three rally modes produced identical short paths: {deltas}")

        parent, ball, _ = self.spawn(9, 0, 64)
        # A nonanchor position makes even a repeated random anchor observable.
        for key, value in (("x", 0x80), ("y", 0x80), ("timer_c", 0),
                           ("b", 1), ("timer_b", 0), ("timer_d", 0)):
            self.set(key, parent, value, "eligible between-stroke native rally warp")
        self.set("b", ball, 0, "native ball remains heading toward Link during warp")
        self.run_to(after_move, f"x == {parent} && [$0EE0+x] == 16")
        start = self.position(parent)
        require(self.field("action", parent) == 3 and self.field("timer_b", parent) == 0xC0,
                "Warp did not retain rally action3 and set cooldownC0")
        self.run_to(after_move, f"x == {parent} && [$0EE0+x] == 8")
        relocated = self.position(parent)
        require(relocated != start, "Native rally warp did not relocate at timer08")
        require((relocated[0] & 255, relocated[1] & 255) in
                ((0x70, 0x78), (0x48, 0x90), (0x98, 0x90), (0x70, 0xA8)),
                "Native rally warp selected an unexpected arena anchor")
        self.run_to(after_move, f"x == {parent} && [$0EE0+x] == 0")
        require(self.field("action", parent) == 3 and self.field("state", ball)
                and self.field("b", ball) == 0, "Warp replaced or interrupted the live rally")
        self.result["cases"].append(dict(name="rally-native-warp", passed=True,
                                          action=3, vanish_timer=16, relocate_timer=8,
                                          cooldown=self.field("timer_b", parent),
                                          before=start, relocated=relocated, after=self.position(parent)))

    def arena_bounds(self, parent):
        x, y = self.position(parent)
        origin_x = self.r(0x7E0023) << 8
        origin_y = self.r(0x7E0021) << 8
        require(origin_x + 0x38 <= x <= origin_x + 0xA8
                and origin_y + 0x58 <= y <= origin_y + 0xB8,
                f"Native glide left its full16-bit quadrant bounds: ({x:04X},{y:04X})")

    def overlords(self):
        return [dict(slot=slot, kind=self.r(0x7E0B00 + slot),
                     x=self.r(0x7E0B08 + slot) | self.r(0x7E0B10 + slot) << 8,
                     y=self.r(0x7E0B18 + slot) | self.r(0x7E0B20 + slot) << 8)
                for slot in range(8) if self.r(0x7E0B00 + slot)]

    def invisible_warp_contact(self):
        contact = 0x06F145
        require(self.raw(contact, 3) == bytes.fromhex("AD7B03"),
                "Native sprite-to-player contact entry differs")
        parent, ball, _ = self.spawn(9, 0, 64)
        self.set("timer_d", parent, 0x10, "hidden warp must skip native player-contact call")
        trap = self.b.add_breakpoint(contact, condition=f"x == {parent}")
        require(isinstance(trap, int) and trap >= 0, "Owned hidden-contact trap rejected")
        self.breakpoints.add(trap)
        try:
            # If contact executes, its owned trap pauses at06F145 and run_to
            # cannot reach contact_done: the case fails and both probes clean up.
            self.run_to(self.labels["Ganondorf_WaitBall_contact_done"],
                        f"x == {parent} && [$0EE0+x] != 0")
            hidden_timer = self.field("timer_d", parent)
            require(hidden_timer > 0 and self.field("action", parent) == 3
                    and self.field("state", ball), "Hidden-contact guard left the live warp")
        finally:
            require(self.b.remove_breakpoint(trap), "Owned hidden-contact trap removal rejected")
            self.breakpoints.remove(trap)
        parent, _, _ = self.spawn(9, 0, 64)
        self.set("timer_d", parent, 0, "visible rally positive control must call native contact")
        cpu = self.run_to(contact, f"x == {parent}")
        require(self.field("timer_d", parent) == 0 and self.field("action", parent) == 3,
                "Visible native contact positive control left rally action3")
        self.result["cases"].append(dict(name="invisible-warp-no-contact", passed=True,
                                          hidden_timer=hidden_timer,
                                          hidden_continuation=self.labels["Ganondorf_WaitBall_contact_done"],
                                          visible_contact_pc=number(cpu.get("pc", cpu.get("PC", -1)))))

    def native_floor_garnish(self, overlord):
        # Guard the fixed vanilla path before placing probes in the native bank.
        require(self.raw(0x09BC3B, 6) == bytes.fromhex("A9039F00F87F"),
                "Native falling-tile garnish03 allocator differs")
        require(self.raw(0x09B655, 6) == bytes.fromhex("A00422A9E701"),
                "Native garnish pit-tile JSL differs")
        cpu = self.run_to(0x09BC74, "[$7FF800+x] == 3")
        garnish = number(cpu.get("x", cpu.get("X", -1)))
        require(0 <= garnish < 30, "Native falling-tile garnish slot is invalid")
        gx = self.r(0x7FF83C + garnish) | self.r(0x7FF878 + garnish) << 8
        gy = self.r(0x7FF81E + garnish) | self.r(0x7FF85A + garnish) << 8
        require(gx == overlord["x"] and gy == (overlord["y"] + 16) & 0xFFFF,
                "Native garnish coordinates differ from stomp-created overlord")
        self.run_to(0x09B657, f"x == {garnish} && [$7FF90E+x] == 30")
        # The native common-tile call selects Y=$04 (pit), with its ordinary
        # coordinate-to-collision indexing. No tile/collision RAM is injected.
        x, y = self.r16(0x7E0000), self.r16(0x7E0002)
        collision = (((y + 1) & 0x1F8) << 3) | ((x & 0x1F8) >> 3)
        addresses = [0x7F2000 + collision + delta for delta in (0, 1, 0x40, 0x41)]
        before = [self.r(address) for address in addresses]
        self.run_to(0x09B65B, f"x == {garnish}")
        after = [self.r(address) for address in addresses]
        require(after == [0x20]*4, "Native falling-tile writer did not install four pit collision cells")
        return dict(garnish=garnish, kind=3, x=gx, y=gy, collision_addresses=addresses,
                    before=before, after=after, native_common_tile=4)

    def stomp_floor(self):
        after_start = self.after_jsr("Ganondorf_WaitBall", "Ganondorf_Stunned", "Ganondorf_StartStomp")
        after_impact = self.after_jsr("Ganondorf_Stomp", "Ganondorf_SpawnFloorCollapse",
                                      "Ganondorf_SpawnFloorCollapse")
        for phase in range(4):
            parent, ball, _ = self.spawn(9, 0, 64)
            require(not self.overlords(), "Fresh arrival unexpectedly contains an active overlord")
            self.set("state", ball, 0, "lost ball starts native WaitBall -> StartStomp path")
            self.set("subtype", parent, phase, "controlled independent floor-collapse phase")
            mode = phase % 3
            self.set("custom", parent, mode | 0x80,
                     "stomp recovery must advance the glide mode and clear the prior rear flag")
            self.run_to(after_start, f"x == {parent}")
            require(self.field("action", parent) == 7 and self.field("g", parent) == 0
                    and self.field("timer_a", parent) == 0x18,
                    "Native StartStomp did not enter action7 rise/windup18")
            start_height = self.field("height", parent)
            if phase:
                # The first case observes the full rise/fall. Later cases only
                # qualify the three remaining native phase-specific writers.
                self.set("g", parent, 1, "controlled final descent tick for floor phase")
                self.set("height", parent, 4, "one ordinary four-pixel descent remains")
                self.set("timer_a", parent, 0, "descent fixture has completed windup")
            else:
                self.run_to(self.labels["Ganondorf_Stomp_done"],
                            f"x == {parent} && [$0ED0+x] == 1")
                peak = self.field("height", parent)
                require(start_height < peak <= 0x28, "Native stomp did not rise toward height28")
            self.run_to(after_impact, f"x == {parent}")
            spawned = self.overlords()
            require(len(spawned) == 1 and spawned[0]["kind"] == 0x0C + phase,
                    f"Floor phase{phase} did not allocate its native directional falling tiles")
            require(self.field("height", parent) == 0 and self.field("g", parent) == 2
                    and self.field("timer_a", parent) == 0x18 and self.field("action", parent) == 7,
                    "Stomp impact did not enter its grounded recovery state")
            require(self.field("subtype", parent) == phase + 1 and self.field("f", parent) == 9,
                    "Floor phase did not advance independently of the remaining-hit count")
            row = dict(name=f"stomp-floor-phase-{phase}", passed=True, start_height=start_height,
                       overlord=spawned[0], hits=9, floor_phase_after=phase + 1)
            if phase == 0:
                row["peak_height"] = peak
                row["native_garnish_and_pit"] = self.native_floor_garnish(spawned[0])
            self.run_to(self.labels["Ganondorf_Float"], f"x == {parent} && [$0D80+x] == 1")
            next_mode = self.field("custom", parent)
            require(next_mode == (mode + 1) % 3,
                    "Stomp recovery did not cycle glide mode and clear the frozen rear flag")
            row["movement_mode_before"] = mode
            row["movement_mode_after_recovery"] = next_mode
            self.result["cases"].append(row)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("socket", "owner"):
        parser.add_argument("--" + name, required=True)
    for name in ("rom", "symbols", "state", "out", "owner-file"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--client-root", type=Path, default=CLIENT_ROOT)
    parser.add_argument("--allow-fixture-writes", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    require(args.allow_fixture_writes, "Explicit --allow-fixture-writes is required")
    require(args.owner.strip(), "An explicit reservation owner is required")
    require(not any(token in args.socket.lower() for token in
                    ("oos-ganondorf-play", "oos-rc-play", "oos-scawful-test", "liveuser", "live-user")),
            "Refusing the user's visible/live test socket")
    require(Path(args.socket).is_socket(), "Explicit private native socket does not exist")
    image = args.rom.read_bytes()
    require(len(image) >= 0x200000 and image[0x7FD5] in (0x20, 0x30),
            "--rom must contain a raw unheadered LoROM header and at least2MiB")
    labels = symbols(args.symbols.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    require(not (args.out / "RESULT.json").exists(), "Output already contains a prior fixture result")
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = Fixture(args, bridge, image, labels)
    owned = False
    try:
        fixture.owner()
        require(fixture.paused(), "Caller must supply a paused private candidate session")
        require(not bridge.list_breakpoints(), "Existing debug breakpoints; refuse shared session")
        owned = True
        fixture.palette_and_intro()
        fixture.launch_stages()
        fixture.return_cases()
        fixture.rally_mobility()
        fixture.invisible_warp_contact()
        fixture.stomp_floor()
        fixture.result["runtime_checks_passed"] = True
    except BaseException as error:
        fixture.result["error"] = repr(error)
    finally:
        if owned:
            try:
                fixture.owner(deadline=False)
                require(bridge.pause(), "Owned cleanup pause rejected")
                fixture.neutral()
                for ident in list(fixture.breakpoints):
                    require(bridge.remove_breakpoint(ident), "Owned cleanup breakpoint removal rejected")
                    fixture.breakpoints.remove(ident)
                fixture.result["cleanup_paused"] = fixture.paused()
                require(fixture.result["cleanup_paused"], "Private session did not remain paused")
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        for path, expected, label in ((args.rom, fixture.result["rom_sha256"], "ROM"),
                                      (args.symbols, fixture.result["symbols_sha256"], "symbols"),
                                      (args.state, fixture.result["state_sha256"], "input state")):
            if digest(path.read_bytes()) != expected:
                fixture.result["cleanup_errors"].append(label + " changed during fixture")
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed")
                                         and not fixture.result["cleanup_errors"])
        (args.out / "RESULT.json").write_text(json.dumps(fixture.result, indent=2) + "\n")
    print(json.dumps({"passed": fixture.result["passed"], "result": str(args.out / "RESULT.json")}))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
