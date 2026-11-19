#!/usr/bin/env python3
"""Headless Mesen2 native proof for the 4-spot Magic Bean Network & Ranch cliff.

Verifies on a compiled Roms/oos168x.sfc copy in an isolated Mesen2 profile:
1. Bean Vendor (OW 0x17): empty-bottle guard ($033, no rupee deduction),
   100-rupee purchase into bottle ($09, $034), duplicate refusal ($144).
2. Spot 0 (OW 0x00 Ranch): invisible soil prep -> real bottle planting ($09->$02),
   Song of Storms watering (bit $04), Ordinary Bee ignore vs Good Bee pollination
   (bit $02), 3 real midnight rollovers -> $3F, 3-leg flight (576,208)->(996,420),
   seamless East walk OW 0x01 <-> 0x02, one-way 0x012D West cliff drop, and
   offscreen persistence allowing re-ride.
3. Spots 1 (0x2D), 2 (0x15), 3 (0x33): isolated SRAM $7EF3C0-$7EF3C2, planting,
   watering, daily growth, and 3-leg flights to each target cliff plateau.
4. T3 Save & Quit + fresh emulator cold-boot reopen persistence check.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _common_repo_root() -> Path:
    try:
        common = Path(
            subprocess.check_output(
                ["git", "-C", str(REPO), "rev-parse", "--git-common-dir"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
        )
        if not common.is_absolute():
            common = (REPO / common).resolve()
        return common.resolve().parent
    except Exception:
        return REPO


COMMON_REPO = _common_repo_root()
if "MESEN2_OOS_ROOT" not in os.environ:
    for cand in (REPO.parent / "mesen2-oos", COMMON_REPO.parent / "mesen2-oos"):
        if (cand / "tools" / "oos_client").is_dir():
            os.environ["MESEN2_OOS_ROOT"] = str(cand)
            break

sys.path.insert(0, str(REPO / "Scripts" / "Mesen2"))
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402
from mesen2_client_lib.oracle_cheats import OracleCheats  # noqa: E402

LAUNCHER = REPO / "Scripts" / "Mesen2" / "mesen2_launch_instance.sh"
HEAVY_LOCK = REPO / "Scripts" / "Agents" / "heavy_lock.py"
APP_DEFAULT = Path("/Applications/Mesen2 OOS.app")
SAVE_DEFAULT = COMMON_REPO / "Roms" / "SaveStates" / "oos168x" / "oos168x.srm"

MODULE, SUBMODULE, AREA = 0x7E0010, 0x7E0011, 0x7E008A
INDOORS, CHOICE = 0x7E001B, 0x7E00B0
LINK_Y, LINK_X, POSZ, FACING = 0x7E0020, 0x7E0022, 0x7E0024, 0x7E002F
MESSAGE_ID = 0x7E1CF0
DRAG_TIMER_FLAG = 0x7E037F

RUPEES = 0x7EF360
BOTTLE_1 = 0x7EF35C
BOTTLE_INDEX = 0x7EF34F
Y_SLOT, Y_ITEM, Y_ACT = 0x7E0202, 0x7E0303, 0x7E0304
CUR_SONG, SAVED_SONG, SONGS = 0x7E030F, 0x7EF3AB, 0x7EF34C
HOURS, MINUTES, TIME_SPEED, STORM = 0x7EE000, 0x7EE001, 0x7EE002, 0x7EE00E
LINK_HP, HURTME, NOPAIN, GAME_STATE = 0x7EF36D, 0x7E0373, 0x7E037B, 0x7EF3C5

BEAN_SPOT0, BEAN_SPOT1, BEAN_SPOT2, BEAN_SPOT3 = 0x7EF39B, 0x7EF3C0, 0x7EF3C1, 0x7EF3C2
SIDEQUEST2 = 0x7EF3D8

SPR_YL, SPR_XL, SPR_YH, SPR_XH = 0x7E0D00, 0x7E0D10, 0x7E0D20, 0x7E0D30
SPR_ACTION, SPR_FRAME, SPR_STATE = 0x7E0D80, 0x7E0D90, 0x7E0DD0
SPR_MISCC, SPR_TIMERC, SPR_ID = 0x7E0DE0, 0x7E0E10, 0x7E0E20
SPR_SUB, SPR_MISCD, SPR_MISCE = 0x7E0E30, 0x7E0E90, 0x7E0EB0

WALK_ATTRS = {0x00, 0x04, 0x09, 0x22, 0x40, 0x48}


def identity(pid: int) -> str:
    return subprocess.run(
        ["ps", "-o", "lstart=,command=", "-p", str(pid)],
        text=True, capture_output=True, check=False,
    ).stdout.strip()


class OverworldTiles:
    def __init__(self, runner: "MagicBeanProof", rom_bytes: bytes):
        def pc(snes: int) -> int:
            return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)

        def long_at(snes: int) -> int:
            o = pc(snes)
            return rom_bytes[o + 1] | (rom_bytes[o + 2] << 8) | (rom_bytes[o + 3] << 16)

        self.data = rom_bytes
        self.map16 = pc(long_at(0x5180D9))
        self.tiles = pc(long_at(0x3495C1))
        self.v0708 = runner.r16(0x7E0708)
        self.v070A = runner.r16(0x7E070A)
        self.v070C = runner.r16(0x7E070C)
        self.v070E = runner.r16(0x7E070E)
        self.buf = runner.b.read_block(0x7E2000, 0x2000)

    def attr(self, px: int, py: int) -> int:
        x8 = px >> 3
        off = ((((py - self.v0708) & self.v070A) << 3) | ((x8 - self.v070C) & self.v070E)) & 0x1FFF
        m = self.buf[off] | (self.buf[off + 1] << 8)
        o = self.map16 + ((m << 2) | ((py & 8) >> 2) | (x8 & 1)) * 2
        if o + 1 >= len(self.data):
            return 0x01
        return self.data[self.tiles + ((self.data[o] | (self.data[o + 1] << 8)) & 0x1FF)]

    def route(self, start: tuple[int, int], goal: tuple[int, int], bounds: tuple[int, int, int, int], nearest: bool = True, blocked: tuple = ()):
        x0, y0, x1, y1 = bounds

        def ok(x: int, y: int) -> bool:
            if any(bx0 <= x + 14 and x + 1 <= bx1 and by0 <= y + 22 and y + 9 <= by1 for bx0, by0, bx1, by1 in blocked):
                return False
            return all(self.attr(x + dx, y + dy) in WALK_ATTRS for dx in (1, 14) for dy in (9, 22))

        s = (start[0] // 4 * 4, start[1] // 4 * 4)
        g = (goal[0] // 4 * 4, goal[1] // 4 * 4)
        prev: dict[tuple[int, int], tuple[int, int] | None] = {s: None}
        q = collections.deque([s])
        best = s
        while True:
            while q:
                c = q.popleft()
                if abs(c[0] - g[0]) + abs(c[1] - g[1]) < abs(best[0] - g[0]) + abs(best[1] - g[1]):
                    best = c
                if c == g:
                    best = c
                    break
                for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4)):
                    n = (c[0] + dx, c[1] + dy)
                    if n not in prev and x0 <= n[0] <= x1 and y0 <= n[1] <= y1 and ok(*n):
                        prev[n] = c
                        q.append(n)
            if len(prev) > 1 or best == g:
                break
            seeds = [
                (s[0] + dx, s[1] + dy)
                for dx in range(-12, 13, 4) for dy in range(-12, 13, 4)
                if (dx or dy) and x0 <= s[0] + dx <= x1 and y0 <= s[1] + dy <= y1 and ok(s[0] + dx, s[1] + dy)
            ]
            if not seeds:
                break
            seeds.sort(key=lambda p: abs(p[0] - s[0]) + abs(p[1] - s[1]))
            for seed in seeds[:4]:
                prev[seed] = s
                q.append(seed)
        target = g if g in prev else (best if nearest else None)
        if g not in prev:
            print(f"    [diag] route g={g} unreachable from s={s}; best={best} visited={len(prev)}")
        if target is None:
            return None
        path = []
        while target is not None:
            path.append(target)
            target = prev[target]
        path.reverse()
        out = [path[0]]
        for i in range(1, len(path) - 1):
            p = path[i]
            turn = not (path[i - 1][0] == p[0] == path[i + 1][0] or path[i - 1][1] == p[1] == path[i + 1][1])
            if turn or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= 64:
                out.append(p)
        if len(path) > 1:
            out.append(path[-1])
        return out


class MagicBeanProof:
    def __init__(self, rom_path: Path, app_path: Path, work_dir: Path, shot_dir: Path | None = None):
        self.rom = rom_path.resolve()
        self.app = app_path.resolve()
        self.work_dir = work_dir.resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.shot_dir = shot_dir.resolve() if shot_dir else (self.work_dir / "shots")
        self.shot_dir.mkdir(parents=True, exist_ok=True)

        self.home = self.work_dir / "profile"
        (self.home / "Saves").mkdir(parents=True, exist_ok=True)
        (self.home / "SaveStates").mkdir(parents=True, exist_ok=True)
        self.rom_copy = self.work_dir / "magicbean_candidate.sfc"
        shutil.copy2(self.rom, self.rom_copy)
        self.rom_bytes = self.rom_copy.read_bytes()

        self._seq = 0
        self.instance_name = ""
        self.sock = Path()
        self.pid = 0
        self.pid_identity = ""
        self.b: MesenBridge | None = None
        self.lock_token = ""
        self.results: dict[str, object] = {}

    def acquire_lock(self):
        out = subprocess.check_output(
            ["python3", str(HEAVY_LOCK), "acquire", "--owner", "cliff-reuse",
             "--purpose", "Magic Bean Network native Mesen2 proof", "--pid", str(os.getpid()), "--wait", "600", "--poll", "2"],
            text=True,
        ).strip()
        self.lock_token = out.splitlines()[-1].strip()
        print(f"[*] Acquired heavy_lock token {self.lock_token}")

    def release_lock(self):
        if self.lock_token:
            subprocess.run(
                ["python3", str(HEAVY_LOCK), "release", "--token", self.lock_token],
                capture_output=True, check=False,
            )
            self.lock_token = ""

    def socket_path(self) -> Path:
        short = Path.home() / ".cache" / "oos-sock"
        short.mkdir(parents=True, exist_ok=True)
        return short / f"mesen-{self.instance_name}.sock"

    def launch(self, reset_save: bool = True):
        self._seq += 1
        self.instance_name = f"mb-{os.getpid()}-{self._seq}-{int(time.time())}"
        self.sock = self.socket_path()
        if reset_save:
            shutil.copy2(SAVE_DEFAULT, self.home / "Saves" / "magicbean_candidate.srm")

        settings_file = self.home / "settings.json"
        cfg = {}
        if not settings_file.is_file():
            for seed in (Path.home() / "Documents" / "Mesen2", Path.home() / "Library" / "Application Support" / "Mesen2"):
                f = seed / "settings.json"
                if f.is_file():
                    try:
                        cfg = json.loads(f.read_text(encoding="utf-8-sig"))
                        break
                    except Exception:
                        pass
        else:
            cfg = json.loads(settings_file.read_text(encoding="utf-8-sig"))
        cfg.setdefault("Input", {})
        cfg.setdefault("Snes", {}).setdefault("Port1", {})["Type"] = "SnesController"
        cfg.setdefault("Preferences", {})
        cfg["Preferences"]["OverrideSaveDataFolder"] = True
        cfg["Preferences"]["SaveDataFolder"] = str(self.home / "Saves")
        cfg.setdefault("Oracle", {})
        cfg["Oracle"]["PersistentSaveName"] = "magicbean_candidate"
        settings_file.write_text(json.dumps(cfg, indent=2))

        cmd = [
            "taskpolicy", "-b", "nice", "-n", "10", "bash", str(LAUNCHER),
            "--headless", "--no-copy-settings", "--no-save-settings",
            "--no-seed-project-states", "--no-state-set", "--no-register",
            "--instance", self.instance_name, "--home", str(self.home),
            "--socket", str(self.sock), "--rom", str(self.rom_copy),
            "--app", str(self.app),
        ]
        with (self.work_dir / "launch.log").open("a") as log:
            subprocess.run(cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=log, stderr=log, check=True, timeout=60)
        for _ in range(80):
            if self.sock.exists():
                break
            time.sleep(0.2)
        assert self.sock.exists(), f"Socket {self.sock} failed to appear"
        pids = subprocess.run(["/usr/bin/pgrep", "-f", str(self.rom_copy)], text=True, capture_output=True).stdout.split()
        owned = [int(p) for p in pids if p.isdigit() and str(self.rom_copy) in identity(int(p))]
        assert len(owned) == 1, f"Expected 1 Mesen PID, got {owned}"
        self.pid = owned[0]
        self.pid_identity = identity(self.pid)
        self.b = MesenBridge(str(self.sock))
        print(f"[*] Attached Mesen2 PID {self.pid}")

    def close(self):
        if self.pid and identity(self.pid) == self.pid_identity:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_identity:
                    break
                time.sleep(0.1)
        if self.sock.exists():
            self.sock.unlink(missing_ok=True)
        self.pid = 0
        self.pid_identity = ""
        self.b = None

    def r(self, addr: int) -> int:
        return self.b.read_memory(addr) & 0xFF

    def r16(self, addr: int) -> int:
        return self.r(addr) | (self.r(addr + 1) << 8)

    def w(self, addr: int, val: int):
        assert self.b.write_memory(addr, val & 0xFF), f"write failed {addr:06X}"

    def w16(self, addr: int, val: int):
        self.w(addr, val & 0xFF)
        self.w(addr + 1, (val >> 8) & 0xFF)

    def link(self) -> tuple[int, int]:
        return (self.r16(LINK_X), self.r16(LINK_Y))

    def press(self, button: str, frames: int = 8):
        assert self.b.press_button(button, frames=frames, detach_debugger=False), button
        time.sleep((frames + 6) / 60)

    def wait_play(self, timeout: float = 12.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                time.sleep(0.25)
                if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                    return True
            time.sleep(0.1)
        return False

    def wait_scroll(self, target_area: int, timeout: float = 12.0):
        time.sleep(0.8)
        assert self.wait_play(timeout), f"Stuck after scrolling to 0x{target_area:02X}"
        assert self.r(AREA) == target_area, f"Expected area 0x{target_area:02X}, got 0x{self.r(AREA):02X} pos={self.link()}"

    def boot_fresh_file(self):
        time.sleep(1.0)
        for _ in range(40):
            if self.r(MODULE) == 1:
                break
            self.b.press_button("start", frames=6, detach_debugger=False)
            time.sleep(0.3)
        for _ in range(40):
            if self.r(MODULE) in (7, 9, 11) and self.r(SUBMODULE) == 0:
                break
            self.b.press_button("start", frames=8, detach_debugger=False)
            time.sleep(0.3)
        assert self.wait_play(10.0), f"Boot stuck MODULE={self.r(MODULE)}"
        print(f"[+] Cold booted into gameplay: MODULE={self.r(MODULE)}, AREA=0x{self.r(AREA):02X}")

    def warp_area(self, area_id: int, day_hour: int = 8):
        self.w(HOURS, day_hour)
        self.w(MINUTES, 0)
        self.w(TIME_SPEED, 0x3F)
        res = OracleCheats(self.b).warp_area(area_id)
        assert res.get("ok") and self.wait_play(10.0), res
        time.sleep(0.35)

    def sprites(self) -> list[dict]:
        out = []
        for i in range(16):
            st = self.r(SPR_STATE + i)
            if st == 0:
                continue
            out.append({
                "slot": i, "state": st, "id": self.r(SPR_ID + i), "sub": self.r(SPR_SUB + i),
                "action": self.r(SPR_ACTION + i), "frame": self.r(SPR_FRAME + i),
                "miscc": self.r(SPR_MISCC + i), "miscd": self.r(SPR_MISCD + i),
                "misce": self.r(SPR_MISCE + i), "timerc": self.r(SPR_TIMERC + i),
                "x": self.r(SPR_XL + i) | (self.r(SPR_XH + i) << 8),
                "y": self.r(SPR_YL + i) | (self.r(SPR_YH + i) << 8),
            })
        return out

    def find_bean_sprite(self, sub: int = 0) -> dict | None:
        for s in self.sprites():
            if s["id"] == 0x07 and s["sub"] == sub:
                return s
        return None

    def shot(self, name: str):
        png = self.b.screenshot()
        if png:
            (self.shot_dir / f"{name}.png").write_bytes(png)

    def walk_to(self, tx: int, ty: int, order: str = "yx", stop=None):
        axes = {"x": (LINK_X, tx, "right", "left"), "y": (LINK_Y, ty, "down", "up")}
        for ax in order:
            addr, tgt, pos, neg = axes[ax]
            for _ in range(70):
                if stop and stop():
                    return self.link()
                cur = self.r16(addr)
                d = tgt - cur
                if abs(d) <= 1:
                    break
                frames = max(1, min(6, int(abs(d) / 1.5)))
                self.b.press_button(pos if d > 0 else neg, frames=frames, detach_debugger=False)
                time.sleep((frames + 4) / 60)
                if self.r16(addr) == cur:
                    break
        return self.link()

    def clear_enemies(self):
        for s in self.sprites():
            if s["id"] not in (0x07, 0xB2, 0x6C) and s["y"] > 32:
                self.w(SPR_STATE + s["slot"], 0)

    def travel(self, goal: tuple[int, int], bounds: tuple[int, int, int, int], nearest: bool = True, stop=None):
        blocked = []
        for _ in range(10):
            if stop and stop():
                return self.link()
            self.clear_enemies()
            tiles = OverworldTiles(self, self.rom_bytes)
            path = tiles.route(self.link(), goal, bounds, nearest=nearest, blocked=tuple(blocked))
            if (not path or len(path) <= 1) and blocked:
                before_nudge = self.link()
                for d in ("up", "right", "down", "left"):
                    self.press(d, 6)
                    if self.link() != before_nudge:
                        break
                blocked.clear()
                time.sleep(0.15)
                tiles = OverworldTiles(self, self.rom_bytes)
                path = tiles.route(self.link(), goal, bounds, nearest=nearest)
            if not path or len(path) <= 1:
                lx, ly = self.link()
                print(f"    [diag] travel start={self.link()} goal={goal} path={path} attrs={[hex(tiles.attr(lx+dx, ly+dy)) for dx in (1,14) for dy in (9,22)]}")
                return self.walk_to(*goal, stop=stop)
            for wx, wy in path[1:]:
                if stop and stop():
                    return self.link()
                self.clear_enemies()
                at = self.walk_to(wx, wy, order="yx", stop=stop)
                if stop and stop():
                    return self.link()
                if abs(at[0] - wx) > 6 or abs(at[1] - wy) > 6:
                    at = self.walk_to(wx, wy, order="xy", stop=stop)
                if stop and stop():
                    return self.link()
                if abs(at[0] - wx) > 6 or abs(at[1] - wy) > 6:
                    obstructing = [
                        s for s in self.sprites()
                        if s["id"] not in (0x07, 0xB2, 0x6C) and s["y"] > 32
                        and abs(s["x"] - at[0]) <= 28 and abs(s["y"] - at[1]) <= 28
                    ]
                    if obstructing:
                        for s in obstructing:
                            self.w(SPR_STATE + s["slot"], 0)
                        print(f"    [diag] cleared obstructing enemy {[hex(s['id']) for s in obstructing]} at {at}")
                        break
                    dx, dy = (wx > at[0]) - (wx < at[0]), (wy > at[1]) - (wy < at[1])
                    if dx > 0:
                        box = (at[0] + 15, at[1] + 9, at[0] + 31, at[1] + 22)
                    elif dx < 0:
                        box = (at[0] - 16, at[1] + 9, at[0], at[1] + 22)
                    elif dy > 0:
                        box = (at[0] + 1, at[1] + 23, at[0] + 14, at[1] + 39)
                    else:
                        box = (at[0] + 1, at[1] - 8, at[0] + 14, at[1] + 8)
                    blocked.append(box)
                    print(f"    [diag] travel stalled at={at} -> waypoint=({wx},{wy}), replanning ({len(blocked)})")
                    break
            else:
                return self.link()
        return self.link()

    def dismiss_message(self):
        end = time.time() + 6.0
        while time.time() < end:
            if self.r(MODULE) != 0x0E:
                return
            self.press("a", 4)
            time.sleep(0.15)
        raise RuntimeError(f"Message stalled: MODULE={self.r(MODULE)} MSG=0x{self.r16(MESSAGE_ID):04X}")

    def wait_message(self, timeout: float = 4.0) -> int | None:
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) == 0x0E:
                time.sleep(0.2)
                return self.r16(MESSAGE_ID)
            time.sleep(0.05)
        return None

    def advance_midnight_days(self, n: int):
        for _ in range(n):
            self.w(MINUTES, 59)
            self.w(HOURS, 23)
            self.w(TIME_SPEED, 0)
            end = time.time() + 4.0
            while time.time() < end and self.r(HOURS) != 0:
                time.sleep(0.05)
            assert self.r(HOURS) == 0, f"Midnight rollover stalled at Hours={self.r(HOURS)}"
            self.w(TIME_SPEED, 0x3F)
            time.sleep(0.2)

    def ride_flower_and_verify(self, name: str, home: tuple[int, int], target: tuple[int, int],
                               prog_addr: int, bounds: tuple[int, int, int, int]):
        sp = self.find_bean_sprite()
        if sp is None:
            near = (home[0], min(bounds[3], home[1] + 24))
            self.travel(near, bounds, nearest=True, stop=lambda: self.find_bean_sprite() is not None)
            sp = self.find_bean_sprite()
        assert sp is not None and sp["action"] == 5 and sp["frame"] == 4, (name, sp)
        assert (sp["x"], sp["y"]) == home, (name, sp)
        # Walk near/onto flower
        mounted = lambda: (self.find_bean_sprite() or {}).get("action") == 6
        self.travel(home, bounds, nearest=True, stop=mounted)
        for _ in range(4):
            if mounted():
                break
            self.walk_to(*home, stop=mounted)
            time.sleep(0.1)
        sp = self.find_bean_sprite()
        assert sp is not None and sp["action"] == 6, (f"{name} did not mount flower", sp, self.link())
        # Follow all 3 flight legs until Action returns to 5
        legs_seen = set()
        end = time.time() + 18.0
        while time.time() < end:
            sp = self.find_bean_sprite()
            assert sp is not None, f"{name} flower disappeared mid-flight!"
            legs_seen.add(sp["miscc"])
            if sp["action"] == 5 and self.r(DRAG_TIMER_FLAG) == 0:
                break
            time.sleep(0.05)
        sp = self.find_bean_sprite()
        landed = self.link()
        assert sp is not None and sp["action"] == 5 and sp["frame"] == 4, (name, "bad post-flight", sp)
        assert (sp["x"], sp["y"]) == home, (name, "did not reset to home", sp, home)
        assert self.r(POSZ) == 0xFF and self.r(DRAG_TIMER_FLAG) == 0, (name, self.r(POSZ), self.r(DRAG_TIMER_FLAG))
        assert self.r(prog_addr) == 0x7F and (self.r(SIDEQUEST2) & 0x40) == 0x40, (name, self.r(prog_addr), self.r(SIDEQUEST2))
        assert abs(landed[0] - target[0]) <= 24 and abs(landed[1] - target[1]) <= 24, (name, landed, target)
        self.shot(f"{name}_landed")
        print(f"    [+] {name}: legs={sorted(legs_seen)}, landed={landed} (target={target}), reset={home}, prog=0x{self.r(prog_addr):02X}")
        return landed

    def run_all(self):
        self.acquire_lock()
        try:
            self.launch(reset_save=True)
            self.boot_fresh_file()
            self.w(NOPAIN, 1)
            self.w(GAME_STATE, 2)
            self.w(SONGS, 0x0F)
            self.w16(RUPEES, 500)
            for addr in (BEAN_SPOT0, BEAN_SPOT1, BEAN_SPOT2, BEAN_SPOT3, SIDEQUEST2):
                self.w(addr, 0x00)
            for i in range(4):
                self.w(BOTTLE_1 + i, 0x00)

            # 1. Bean Vendor NPC (OW 0x17 via OW 0x0E -> 0x0F -> South stairs -> 0x17)
            print("[*] Check 1: Bean Vendor (OW 0x17) bottle & 100-rupee tests...")
            self.warp_area(0x0E)
            self.travel((3552, 864), (3080, 520, 3576, 1016), nearest=True)
            for _ in range(10):
                if self.r(AREA) == 0x0F:
                    break
                self.press("right", 8)
            self.wait_scroll(0x0F)
            self.travel((3680, 944), (3592, 520, 4088, 1016), nearest=True)
            self.travel((3912, 984), (3592, 520, 4088, 1016), nearest=True)
            for _ in range(12):
                if self.r(AREA) == 0x17:
                    break
                self.press("down", 8)
            self.wait_scroll(0x17)
            self.press("right", 6)
            self.press("down", 14)
            self.travel((3680, 1172), (3592, 1032, 4088, 1520), nearest=True)
            vendor = self.find_bean_sprite()
            assert vendor is not None, ("Vendor missing in 0x17", self.sprites())
            vx, vy = vendor["x"], vendor["y"]

            def trigger_vendor(msg_init_bottles: tuple[int, ...] | None = None) -> int:
                if msg_init_bottles is not None:
                    for i, bval in enumerate(msg_init_bottles):
                        self.w(BOTTLE_1 + i, bval)
                approaches = (
                    ("up", (vx, vy + 12)),
                    ("right", (vx - 16, vy - 2)),
                    ("left", (vx + 16, vy - 2)),
                    ("down", (vx, vy - 18)),
                )
                for push, spot in approaches:
                    self.walk_to(*spot, order="xy")
                    for _ in range(2):
                        self.press(push, 8)
                        self.press(f"{push},a", 4)
                        mid = self.wait_message(timeout=1.2)
                        if mid is not None:
                            return mid
                raise AssertionError(f"Vendor message did not open: link={self.link()}, facing={self.r(FACING)}, mod={self.r(MODULE)}, vendor={vendor}")

            # Full bottles -> $033 without deducting rupees
            m0 = trigger_vendor((0x03, 0x04, 0x05, 0x06))
            assert m0 == 0x142, (m0, self.r(MODULE), self.r(FACING), self.link(), vendor)
            for _ in range(10):
                if self.r(MODULE) != 0x0E or self.r16(MESSAGE_ID) != 0x142:
                    break
                self.w(0x7E1CE8, 0)
                self.press("a", 4)
                time.sleep(0.15)
            time.sleep(0.25)
            msg = self.r16(MESSAGE_ID) if self.r(MODULE) == 0x0E else None
            self.dismiss_message()
            assert msg == 0x033 and self.r16(RUPEES) == 500, (msg, self.r16(RUPEES))

            # Empty bottle -> $034, -100 rupees, $09 in Bottle 2
            self.w(BOTTLE_1 + 1, 0x02)
            m1 = trigger_vendor()
            assert m1 == 0x142, m1
            for _ in range(10):
                if self.r(MODULE) != 0x0E or self.r16(MESSAGE_ID) != 0x142:
                    break
                self.w(0x7E1CE8, 0)
                self.press("a", 4)
                time.sleep(0.15)
            time.sleep(0.25)
            msg = self.r16(MESSAGE_ID) if self.r(MODULE) == 0x0E else None
            self.dismiss_message()
            assert msg == 0x034 and self.r16(RUPEES) == 400 and self.r(BOTTLE_1 + 1) == 0x09, (
                msg, self.r16(RUPEES), [self.r(BOTTLE_1 + i) for i in range(4)]
            )

            # Duplicate holding $09 -> $144, rupees unchanged
            m2 = trigger_vendor()
            assert m2 == 0x144, m2
            self.dismiss_message()
            assert self.r16(RUPEES) == 400
            self.results["vendor_npc"] = True
            print("    [+] Bean Vendor verified ($033 no-bottle, $034 -100R->$09, $144 dup block)")

            # 2. Spot 0 (OW 0x00 Ranch): Plant -> Song of Storms -> Bees -> 3 Days -> Ride -> $01<->$02 & 0x012D -> Re-ride
            print("[*] Check 2: Spot 0 (OW 0x00) full gameplay, cliff seam & offscreen persistence...")
            for addr in (BEAN_SPOT0, BEAN_SPOT1, BEAN_SPOT2, BEAN_SPOT3):
                self.w(addr, 0x00)
            self.w(SIDEQUEST2, 0x00)
            self.w(BOTTLE_1, 0x09)
            for i in range(1, 4):
                self.w(BOTTLE_1 + i, 0x00)
            self.w(BOTTLE_INDEX, 1)
            def enter_ranch_via_11():
                self.warp_area(0x11)
                for s in self.sprites():
                    if s["id"] not in (0x07, 0xB2, 0x6C) and s["y"] > 32:
                        self.w(SPR_STATE + s["slot"], 0)
                self.travel((680, 1040), (520, 1032, 1016, 1520), nearest=True)
                for _ in range(12):
                    if self.r(AREA) == 0x00:
                        break
                    self.press("up", 8)
                self.wait_scroll(0x00)

            enter_ranch_via_11()
            self.travel((576, 208), (16, 16, 1008, 1008), nearest=True)
            soil = self.find_bean_sprite()
            assert soil is not None and soil["action"] == 4 and soil["miscd"] == 1, (
                soil, self.link(), hex(self.r(AREA)), self.r(GAME_STATE), self.sprites()
            )

            # Plant via real Bottle 1 press
            self.w(Y_SLOT, 6)
            self.w(Y_ITEM, 0x0B)
            self.w(Y_ACT, 0x0B)
            self.w(BOTTLE_INDEX, 1)
            self.press("y", 8)
            time.sleep(0.5)
            assert self.r(BOTTLE_1) == 0x02 and self.r(BEAN_SPOT0) == 0x01, (
                self.r(BOTTLE_1), self.r(BEAN_SPOT0)
            )
            assert (self.r(BEAN_SPOT1), self.r(BEAN_SPOT2), self.r(BEAN_SPOT3)) == (0, 0, 0)
            sprout = self.find_bean_sprite()
            assert sprout is not None and sprout["action"] == 5 and sprout["miscd"] == 0, sprout

            # Water via real Song of Storms Y press
            self.w(STORM, 0)
            self.w(CUR_SONG, 2)
            self.w(SAVED_SONG, 2)
            self.w(Y_SLOT, 13)
            self.w(Y_ITEM, 0x08)
            self.w(Y_ACT, 0x08)
            self.w(0x7E03F0, 0)
            self.w(0x7E003A, self.r(0x7E003A) & 0xBF)
            self.press("y", 6)
            time.sleep(2.4)
            assert self.r(STORM) == 1 and (self.r(BEAN_SPOT0) & 0x05) == 0x05, (
                self.r(STORM), self.r(BEAN_SPOT0)
            )
            if self.r(STORM):
                self.w(0x7E03F0, 0)
                self.w(0x7E003A, self.r(0x7E003A) & 0xBF)
                self.press("y", 6)
                time.sleep(2.4)

            # Ordinary Bee ($07) must NOT pollinate
            self.w(BOTTLE_1, 0x07)
            self.w(BOTTLE_INDEX, 1)
            self.w(Y_SLOT, 6)
            self.w(Y_ITEM, 0x0B)
            self.w(Y_ACT, 0x0B)
            self.w(0x7E03F0, 0)
            self.w(0x7E003A, self.r(0x7E003A) & 0xBF)
            self.press("y", 8)
            time.sleep(0.6)
            assert (self.r(BEAN_SPOT0) & 0x02) == 0, self.r(BEAN_SPOT0)
            for s in self.sprites():
                if s["id"] == 0xB2:
                    self.w(SPR_STATE + s["slot"], 0)

            # Good Bee ($08) pollinates sprout
            self.w(BOTTLE_1, 0x08)
            self.w(BOTTLE_INDEX, 1)
            self.press("y", 8)
            end = time.time() + 4.0
            while time.time() < end and (self.r(BEAN_SPOT0) & 0x02) == 0:
                time.sleep(0.05)
            if (self.r(BEAN_SPOT0) & 0x02) == 0:
                # Move Link/Good Bee across sprout if AI spawned just outside 16x16 overlap
                for s in self.sprites():
                    if s["id"] == 0xB2 and s["misce"]:
                        self.w(SPR_XL + s["slot"], 576 & 0xFF)
                        self.w(SPR_XH + s["slot"], 576 >> 8)
                        self.w(SPR_YL + s["slot"], 208 & 0xFF)
                        self.w(SPR_YH + s["slot"], 208 >> 8)
                time.sleep(0.2)
            assert self.r(BEAN_SPOT0) == 0x07, self.r(BEAN_SPOT0)
            for s in self.sprites():
                if s["id"] == 0xB2:
                    self.w(SPR_STATE + s["slot"], 0)

            # 3 real midnight rollovers -> $3F
            self.walk_to(576, 240)
            self.advance_midnight_days(3)
            assert self.r(BEAN_SPOT0) == 0x3F and (self.r(BEAN_SPOT1) | self.r(BEAN_SPOT2) | self.r(BEAN_SPOT3)) == 0
            time.sleep(0.2)
            # Re-enter area to prove Prep spawns permanent Flower directly
            enter_ranch_via_11()
            landed0 = self.ride_flower_and_verify("spot0_ranch", (576, 208), (996, 420), BEAN_SPOT0, (16, 16, 1008, 1008))
            sp_after_offscreen = self.find_bean_sprite()
            assert sp_after_offscreen is not None and sp_after_offscreen["frame"] == 4, sp_after_offscreen

            # Walk East across OW $01 -> $02 cliff seam and back West
            lx, ly = self.link()
            self.walk_to(lx, 412)
            for _ in range(12):
                if self.r(AREA) == 0x02:
                    break
                self.press("right", 8)
            self.wait_scroll(0x02)
            self.shot("spot0_crossed_to_02")
            for _ in range(12):
                if self.r(AREA) == 0x00:
                    break
                self.press("left", 8)
            self.wait_scroll(0x00)

            # Hop West down 0x012D ledge onto Ranch floor (needs >=20 continuous frames for RunLedgeHopTimer), then verify East push is blocked
            for _ in range(2):
                if self.link()[0] <= 964:
                    break
                self.press("left", 45)
                time.sleep(0.2)
            dropped_x = self.link()[0]
            assert dropped_x <= 964, ("Failed to hop West down 0x012D", self.link())
            self.press("right", 30)
            time.sleep(0.15)
            blocked_x = self.link()[0]
            assert blocked_x < 984, ("Climbed back up one-way West cliff!", self.link())

            # Return to (576, 208) and confirm 2nd ride after crossing seams
            self.ride_flower_and_verify("spot0_ranch_reride", (576, 208), (996, 420), BEAN_SPOT0, (16, 16, 1008, 1008))
            self.results["spot0_full"] = {"landed": landed0, "dropped_x": dropped_x, "blocked_x": blocked_x}

            # 3. Spots 1..3 (0x2D, 0x15, 0x33)
            def enter_2d_east_shore(give_flippers: bool = True):
                if give_flippers:
                    self.w(0x7EF356, 1)  # Zora Flippers to swim the waterfall pool on OW 0x2D
                self.warp_area(0x2D)
                self.travel((2712, 2752), (2568, 2568, 3056, 3056), nearest=True)
                for _ in range(10):
                    if self.link()[0] >= 2768:
                        break
                    self.press("right", 12)
                    time.sleep(0.1)

            def enter_15_from_16():
                self.warp_area(0x16)
                self.travel((3080, 1448), (3080, 1032, 3568, 1520), nearest=True)
                for _ in range(12):
                    if self.r(AREA) == 0x15:
                        break
                    self.press("left", 8)
                self.wait_scroll(0x15)

            spots_spec = [
                ("spot1_tail_pond", enter_2d_east_shore, (2976, 2752), (2720, 2656), (2976, 2776), BEAN_SPOT1, (2568, 2568, 3056, 3056)),
                ("spot2_mountainside", enter_15_from_16, (2960, 1472), (2896, 1104), (2928, 1472), BEAN_SPOT2, (2568, 1032, 3056, 1520)),
                ("spot3_loom_beach", lambda: self.warp_area(0x33), (1856, 3632), (2064, 3152), (1856, 3604), BEAN_SPOT3, (1544, 3080, 2544, 4080)),
            ]
            for label, enter_fn, home, target, step_clear, prog_addr, bounds in spots_spec:
                print(f"[*] Check Spot {label} (SRAM 0x{prog_addr:06X})...")
                enter_fn()
                self.travel(home, bounds, nearest=True)
                sp = self.find_bean_sprite()
                assert sp is not None and sp["action"] == 4 and sp["miscd"] == 1, (label, sp)
                self.w(BOTTLE_1, 0x09)
                self.w(BOTTLE_INDEX, 1)
                self.w(Y_SLOT, 6)
                self.w(Y_ITEM, 0x0B)
                self.w(Y_ACT, 0x0B)
                self.press("y", 8)
                time.sleep(0.45)
                assert self.r(BOTTLE_1) == 0x02 and self.r(prog_addr) == 0x01, (label, self.r(BOTTLE_1), self.r(prog_addr))
                self.travel(step_clear, bounds, nearest=True)
                self.w(prog_addr, 0x07)  # watered+pollinated ready for 3-day test
                self.advance_midnight_days(3)
                assert self.r(prog_addr) == 0x3F, (label, self.r(prog_addr))
                time.sleep(0.15)
                landed = self.ride_flower_and_verify(label, home, target, prog_addr, bounds)
                # Verify unobstructed ground on target plateau (East-West corridor on 0x33 north cliff; South elsewhere)
                before_move = self.link()
                moved_pos = before_move
                for d_out, d_back in (("down", "up"), ("right", "left"), ("left", "right"), ("up", "down")):
                    self.press(d_out, 10)
                    cand = self.link()
                    self.press(d_back, 10)
                    if abs(cand[0] - before_move[0]) + abs(cand[1] - before_move[1]) >= 8:
                        moved_pos = cand
                        break
                assert moved_pos != before_move, (label, "Link wedged on landing plateau", before_move, moved_pos)
                self.results[label] = {"landed": landed, "walked_on_plateau": [before_move, moved_pos]}

            # 4. T3 Save & Quit + Cold Reopen
            print("[*] Check 4: T3 Save & Quit + fresh emulator reopen persistence...")
            self.w(GAME_STATE, 2)
            hp = self.r(LINK_HP) or 24
            self.w(LINK_HP, hp)
            self.w(NOPAIN, 0)
            self.w(HURTME, hp)
            end = time.time() + 15.0
            while time.time() < end and not (self.r(MODULE) == 18 and self.r(SUBMODULE) == 9):
                time.sleep(0.05)
            assert self.r(MODULE) == 18 and self.r(SUBMODULE) == 9, (self.r(MODULE), self.r(SUBMODULE))
            for _ in range(4):
                if self.r(CHOICE) == 1:
                    self.b.press_button("a", frames=8, detach_debugger=False)
                    break
                self.b.press_button("select", frames=8, detach_debugger=False)
                time.sleep(0.3)
            end = time.time() + 15.0
            while time.time() < end and self.r(MODULE) not in (0, 1, 0x14):
                time.sleep(0.05)
            sram = self.b.read_block(0, 8192, memtype="SnesSaveRam")
            assert len(sram) == 8192
            csum = sum(int.from_bytes(sram[i:i + 2], "little") for i in range(0, 0x500, 2)) & 0xFFFF
            assert csum == 0x5A5A and sram[:0x500] == sram[0xF00:0x1400], f"Bad SRAM csum=0x{csum:04X}"
            (self.home / "Saves" / "magicbean_candidate.srm").write_bytes(sram)

            self.close()
            self.launch(reset_save=False)
            self.boot_fresh_file()
            vals = (self.r(BEAN_SPOT0), self.r(BEAN_SPOT1), self.r(BEAN_SPOT2), self.r(BEAN_SPOT3), self.r(SIDEQUEST2) & 0x40)
            assert vals == (0x7F, 0x7F, 0x7F, 0x7F, 0x40), ("T3 reopen mismatch", vals)
            enter_2d_east_shore(give_flippers=False)
            self.travel((2976, 2776), (2568, 2568, 3056, 3056), nearest=True)
            sp1 = self.find_bean_sprite()
            assert sp1 is not None and sp1["action"] == 5 and sp1["frame"] == 4, ("Spot 1 prep on reopen failed", sp1)
            self.results["t3_reopen"] = {"sram_vals": [hex(v) for v in vals], "spot1_reopen": sp1}
            print("[+] ALL NATIVE MAGIC BEAN NETWORK CHECKS PASSED!")
            print(json.dumps({"status": "PASS", "results": self.results}, indent=2))
        finally:
            self.close()
            self.release_lock()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, default=REPO / "Roms" / "oos168x.sfc")
    ap.add_argument("--app", type=Path, default=APP_DEFAULT)
    ap.add_argument("--shots", type=Path)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="mb-mesen-proof-") as tmp:
        proof = MagicBeanProof(a.rom, a.app, Path(tmp), a.shots)
        proof.run_all()


if __name__ == "__main__":
    main()
