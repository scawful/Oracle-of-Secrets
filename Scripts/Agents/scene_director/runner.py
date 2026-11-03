"""Run a scene in a private, headless Mesen2 OOS instance.

Ownership rules (AGENTS.md, heavy_lock.py):
  - Takes one heavy-lock slot for this process and releases it in `finally`.
  - Launches its own headless instance with a private profile, socket and ROM copy.
    It never attaches to an existing socket and refuses any name containing
    `oos-rc-play`. Cleanup SIGTERMs only the recorded PID, and only when that PID's
    command line still has --headless and our private ROM path.

Reused helpers (not rewritten):
  - MesenBridge from Scripts/Mesen2/mesen2_client_lib.
  - Tests/native/portal_rod_spawn_return.Fixture: check_owner, paused, block, input.
  - Tests/native/goron97_cart_gate.Route: axis, walk, tap, until, neutral, check
    (borrowed as methods; this class supplies the snap/advance/chunk they call).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace

from . import pathfind
from .scenefile import Scene, SceneError, load_fixture

REPO = Path(__file__).resolve().parents[3]
NATIVE = REPO / "Tests" / "native"
CLIENT = REPO / "Scripts" / "Mesen2"
LAUNCHER = REPO / "Scripts" / "Mesen2" / "mesen2_launch_instance.sh"
APP = Path("/Applications/Mesen2 OOS.app")
SETTINGS_TEMPLATES = (
    Path.home() / ".context/projects/oracle-of-secrets/scratchpad/handoffs/quest_collectibles_2026-10-18/spacing/profile/settings.json",
    Path.home() / "Documents/Mesen2/settings.json",
    Path.home() / "Library/Application Support/Mesen2/settings.json",
)
FORBIDDEN = "oos-rc-play"
# Determinism: Mesen fills WRAM/VRAM/ARAM/OAM/CGRAM at power-on from Snes.RamPowerOnState
# (Core/SNES/SnesConsole.cpp InitializeRam -> BaseCartridge::GetRamPowerOnState; the
# shared template says "Random", which made two identical runs end on different WRAM
# hashes in slice 1). EnableRandomPowerOnState randomizes PPU/CPU registers (SnesPpu.cpp).
POWER_ON = {"RamPowerOnState": "AllZeros", "EnableRandomPowerOnState": False}
# Entrance reload pokes, copied from mesen2-oos oracle_cheats.warp_entrance(method="reload").
ENTRANCE, CONTINUE_FLAG, RESPAWN_FLAG, FOLLOWER = 0x7E010E, 0x7E010A, 0x7E04AA, 0x7EF3CC
MENU = 0x7E0200  # Tests/native/quest_collectibles.py: 4 = Items screen while module $0E
EQUIPPED = 0x7E0202
# $2F DIR (Core/ram.asm:154): 0 up, 2 down, 4 left, 6 right.
FACING = {"up": 0, "down": 2, "left": 4, "right": 6}

# The client shim looks for a sibling mesen2-oos checkout; a worktree under
# oracle-of-secrets-worktrees/ has none, so fall back to the usual checkout.
if not os.environ.get("MESEN2_OOS_ROOT") and not (REPO.parent / "mesen2-oos").is_dir():
    os.environ["MESEN2_OOS_ROOT"] = str(Path.home() / "src/hobby/mesen2-oos")
for path in (NATIVE, CLIENT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
sys.dont_write_bytecode = True
import portal_rod_spawn_return as native  # noqa: E402
import goron97_cart_gate as goron  # noqa: E402

require = native.require
SCENE_DEADLINE = 900  # seconds; the Fixture default (120 s) is too short for a take
# Determinism: the first pause after launch lands on a wall-clock-dependent emulated frame
# (5..8 seen live), which shifted every later input by a few frames and changed one take
# frame in 64 between identical runs. Cold boots first step, input-free, to this absolute
# emulated frame, so every scene input lands on the same frame since power-on.
BOOT_ALIGN_FRAME = 60


class SceneFailed(RuntimeError):
    """A check or wait_until in the scene failed (exit code 1)."""


class SceneSession(native.Fixture):
    """Fixture plus the goron97 walker, without the goron97 room-specific checks."""

    axis = goron.Route.axis
    walk = goron.Route.walk
    tap = goron.Route.tap
    until = goron.Route.until
    neutral = goron.Route.neutral
    check = goron.Route.check

    def __init__(self, args, bridge, log_path: Path):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + SCENE_DEADLINE
        self.route = {"paths": {}}
        self.last, self.phase = None, "boot"
        self.frame_count, self.last_advance = None, 0
        self.recorder = None
        self.watch = {}
        self.result.update(checks=[], steps=[], walks=[])
        self.log = log_path.open("w")

    def r8(self, address):
        return self.block(address, 1)[0]

    def read(self, address, size):
        data = self.block(address, size)
        return int.from_bytes(data, "little")

    def snap(self):
        low = self.block(0x7E0000, 0x100)
        save = self.block(0x7EF36D, 1)
        word = lambda o: low[o] | low[o + 1] << 8  # noqa: E731
        room = word(0xA0)
        bx, by = (room & 15) * 512, (room >> 4) * 512
        self.last = {"module": low[0x10], "submodule": low[0x11], "indoors": low[0x1B], "room": room,
                     "x": word(0x22), "y": word(0x20), "lx": word(0x22) - bx, "ly": word(0x20) - by,
                     "layer": low[0xEE], "dir": low[0x2F], "mounted": low[0x35], "hp": save[0],
                     "frame": self.frame_count or 0}
        return self.last

    def chunk(self):
        return 1 if self.last and self.last["submodule"] != 0 else 4

    def advance(self, button="", frames=1):
        require(type(frames) is int and 1 <= frames <= 4, "advance takes 1..4 frames per FRAME call")
        if self.recorder is not None:
            frames = 1  # one PNG per emulated frame; callers count self.last_advance
        info = self.check_owner()
        require(self.paused(), "FRAME requires paused owned CPU")
        self.input(button)
        before = native.number(info["frameCount"])
        try:
            require(self.b.send_command("FRAME", {"count": str(frames)}).get("success"), "FRAME rejected")
            until = min(self.deadline, time.monotonic() + 5)
            while time.monotonic() < until:
                after = native.number(self.b.get_rom_info()["frameCount"])
                if after >= before + frames and self.paused():
                    require(after <= before + frames + 1, "FRAME overshoot")
                    break
                time.sleep(0.005)
            else:
                raise RuntimeError("FRAME timeout")
        finally:
            self.input("")
        self.frame_count, self.last_advance = after, after - before
        if self.recorder is not None:
            self.recorder.capture(self.b, after)
        s = self.snap()
        row = {"phase": self.phase, "button": button, "frames": frames, **s}
        if self.watch:
            row["watch"] = {name: self.evaluate(expr) for name, expr in self.watch.items()}
        self.log.write(json.dumps(row) + "\n")
        return s

    def hold(self, button, frames):
        spent = 0
        while spent < frames:
            self.advance(button, min(4, frames - spent))
            spent += self.last_advance

    def names(self):
        return dict(self.last)

    def evaluate(self, expr):
        return expr.evaluate(self.read, self.names())


# ---------------------------------------------------------------- boot ----

def _settings_template():
    for path in SETTINGS_TEMPLATES:
        if path.is_file():
            return path
    raise RuntimeError("no Mesen2 settings.json template found; looked in "
                       + ", ".join(map(str, SETTINGS_TEMPLATES)))


def profile_settings(cfg: dict, profile: Path) -> dict:
    """Private-profile settings: own save folders, fixed save name, deterministic power-on, audio on."""
    prefs = cfg.setdefault("Preferences", {})
    for kind, folder in (("SaveData", "Saves"), ("SaveState", "SaveStates")):
        prefs["Override" + kind + "Folder"] = True
        prefs[kind + "Folder"] = str(profile / folder)
    cfg.setdefault("Oracle", {})["PersistentSaveName"] = "scene"
    cfg.setdefault("Snes", {}).update(POWER_ON)
    cfg.setdefault("Audio", {}).update(AUDIO)
    return cfg


def _owned(pid, rom):
    try:
        command = subprocess.check_output(["/bin/ps", "-p", str(pid), "-o", "command="], text=True)
    except subprocess.CalledProcessError:
        return False
    return "--headless" in command and str(rom) in command


class PrivateMesen:
    """One headless instance this process launched; never anything else."""

    def __init__(self, rom: Path, work: Path, seed_srm: Path | None, owner: str):
        self.name = f"scene-{os.getpid()}"
        require(FORBIDDEN not in self.name and FORBIDDEN not in str(work), "refusing the oos-rc-play session")
        self.owner, self.work = owner, work
        self.socket = f"/tmp/mesen2-{self.name}.sock"
        self.status = Path(f"/tmp/mesen2-{self.name}.status")
        require(not Path(self.socket).exists() and not self.status.exists(),
                f"socket/status for {self.name} already exist; refusing to attach to someone else's instance")
        self.profile = work / "profile"
        self.rom = work / "scene.sfc"
        self.pid = None
        shutil.copy2(rom, self.rom)
        for folder in ("Saves", "SaveStates"):
            (self.profile / folder).mkdir(parents=True, exist_ok=True)
        cfg = json.loads(_settings_template().read_text(encoding="utf-8-sig"))
        (self.profile / "settings.json").write_text(json.dumps(profile_settings(cfg, self.profile)))
        if seed_srm is not None:
            require(seed_srm.stat().st_size == 8192, f"{seed_srm}: expected an 8192-byte SRM")
            shutil.copy2(seed_srm, self.profile / "Saves" / "scene.srm")

    def launch(self):
        cmd = ["/usr/sbin/taskpolicy", "-b", "nice", "-n", "10", "bash", str(LAUNCHER), "--headless",
               "--no-save-settings", "--no-copy-settings", "--no-register", "--no-seed-project-states",
               "--no-state-set", "--instance", self.name, "--owner", self.owner, "--home", str(self.profile),
               "--socket", self.socket, "--rom", str(self.rom), "--app", str(APP)]
        with (self.work / "launch.log").open("w") as out:
            subprocess.run(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT, check=True, timeout=30)
        for _ in range(200):
            if self.status.exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Mesen status file {self.status} never appeared (see {self.work}/launch.log)")
        self.pid = int(json.loads(self.status.read_text())["pid"])
        require(_owned(self.pid, self.rom), f"pid {self.pid} is not our headless private ROM process")

    def stop(self):
        if self.pid and _owned(self.pid, self.rom):
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if not _owned(self.pid, self.rom):
                    break
                time.sleep(0.1)


def _connect(m: PrivateMesen):
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(m.socket, auto_reconnect=False, max_retries=0)
    sha1 = hashlib.sha1(m.rom.read_bytes()).hexdigest()
    for _ in range(100):
        if str(bridge.get_rom_info().get("sha1", "")).lower() == sha1:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("ROM identity did not settle")
    bridge.pause()
    for _ in range(100):
        state = bridge.send_command("STATE").get("data", {})
        if isinstance(state, str):
            state = json.loads(state)
        if state.get("paused"):
            break
        time.sleep(0.02)
    else:
        raise RuntimeError("pause did not settle")
    for _ in range(50):
        if bridge.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"}).get("success"):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("controller INPUT not ready")
    return bridge, sha1


def _wait(s: SceneSession, predicate, frames, what):
    spent = 0
    while spent < frames:
        if predicate(s.last):
            return
        s.advance("", 4)
        spent += s.last_advance
    raise RuntimeError(f"boot: {what} not reached after {frames} frames; last {s.last}")


def _align_boot(s: SceneSession, target: int = BOOT_ALIGN_FRAME):
    """Advance input-free, one frame at a time, until the absolute emulated frame is `target`."""
    now = native.number(s.b.get_rom_info()["frameCount"])
    if now > target:
        raise RuntimeError(f"boot: first pause at emulated frame {now}, past the align frame {target}")
    s.frame_count = now
    while s.frame_count < target:
        s.advance("", 1)
    s.snap()
    require(s.frame_count == target, f"boot align ended on frame {s.frame_count}, wanted {target}")


def _cold_boot(s: SceneSession):
    """Title -> file select -> file 1, by controller only (boot_native.py pattern)."""
    _align_boot(s)
    _wait(s, lambda v: v["module"] == 0 and v["submodule"] == 8, 2700, "title (module 0/8)")
    s.tap("Start", 120)
    _wait(s, lambda v: v["module"] == 1 and v["submodule"] == 5, 300, "file select (module 1/5)")
    s.tap("Start", 180)
    _wait(s, lambda v: v["module"] in (7, 9) and v["submodule"] == 0, 1800, "gameplay (module 7/9, sub 0)")


def _apply_fixtures(s: SceneSession, paths):
    for path in paths:
        _poke(s, load_fixture(path), str(path))


def _poke(s: SceneSession, writes, source):
    require(s.paused(), "RAM writes need a paused CPU")
    for addr, kind, value in writes:
        size = 1 if kind == "u8" else 2
        before = s.read(addr, size)
        for i in range(size):
            require(s.b.write_memory(addr + i, (value >> (8 * i)) & 0xFF), f"write {addr:06X} rejected")
        after = s.read(addr, size)
        s.result["writes"].append({"source": source, "addr": f"{addr:06X}", "before": before,
                                   "value": value, "readback": after})
        require(after == value, f"{source}: readback {addr:06X}={after:#x}, wanted {value:#x}")


def _load_entrance(s: SceneSession, entrance: int):
    """oracle_cheats warp_entrance(method="reload") pokes, then wait for room play.

    Same-world only: the pokes keep $7EF3CA/$0FFF (the scene's save decides the world).
    Follower $02 makes Underworld_LoadEntrance load the spawn point instead.
    """
    if s.r8(FOLLOWER) == 0x02:
        raise SceneFailed(f"entrance {entrance:#04x}: follower $02 loads the spawn point; clear $7EF3CC")
    _poke(s, [(ENTRANCE, "u16", entrance), (CONTINUE_FLAG, "u8", 1), (RESPAWN_FLAG, "u8", 0),
              (0x7E001B, "u8", 1), (0x7E0011, "u8", 0), (0x7E00B0, "u8", 0), (0x7E0010, "u8", 0x05)],
          f"entrance {entrance:#04x}")
    s.neutral(4)
    _wait(s, lambda v: v["module"] in (7, 9) and v["submodule"] == 0, 900,
          f"entrance {entrance:#04x} room play (module 7/9, sub 0)")


def _menu_tap(s: SceneSession, button):
    s.advance(button, 2)
    s.neutral(6)


def _equip(s: SceneSession, step):
    """new_items_prototype.equip by controller: Start, Right until $0202 = item, Start."""
    item = step.args["item"]
    if s.r8(EQUIPPED) == item:
        return
    _menu_tap(s, "Start")
    _wait(s, lambda v: v["module"] == 0x0E and s.r8(MENU) == 4, 240, "Items screen (module $0E, $0200=4)")
    for _ in range(24):
        if s.r8(EQUIPPED) == item:
            break
        _menu_tap(s, "Right")
    else:
        raise SceneFailed(f"{step.label()}: item {item:#04x} not reachable on the Items screen")
    _menu_tap(s, "Start")
    _wait(s, lambda v: v["module"] in (7, 9) and v["submodule"] == 0, 240, "gameplay after the menu")


# Native recording route: Codex's accepted capture (promo_campaign_2026-11-02/
# codex-full-frame-assist-20261102/init-gated-full-frame/sunset_init_gated.py:151-190):
# `mesen_studio.py record start <avi> --wav` with no preset/size, so camera=false and the
# whole 256x224 framebuffer goes to the AVI, plus a separate 48 kHz stereo WAV.
STUDIO = Path(os.environ.get("OOS_MESEN_STUDIO") or Path.home() / (
    ".context/projects/oracle-of-secrets/scratchpad/handoffs/promo_capture_2026-10-26/"
    "capture-host-recovery/source/tools/studio/mesen_studio.py"))
NATIVE_SIZE = (256, 224)
AV_TOLERANCE = 0.1   # seconds, WAV vs video duration
MIN_MEAN_DB = -60.0  # volumedetect mean_volume floor (silence is about -91 dB)
# Audio on, no background/fast-forward ducking (same values as Codex's producer profile).
AUDIO = {"EnableAudio": True, "MasterVolume": 100, "MuteSoundInBackground": False,
         "ReduceSoundInBackground": False, "ReduceSoundInFastForward": False}


def _tool(name):
    return shutil.which(name) or f"/opt/homebrew/bin/{name}"


def png_size(blob):
    require(len(blob) >= 24 and blob[:16] == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "not a PNG")
    return int.from_bytes(blob[16:20], "big"), int.from_bytes(blob[20:24], "big")


def check_record_status(status, avi: Path):
    """Raise unless the recorder took the native full-frame route with its WAV."""
    video, audio = (status or {}).get("video") or {}, (status or {}).get("audio") or {}
    require(video.get("active") is True, f"recorder video not active: {status}")
    require(video.get("camera") is False, f"recorder video went through the camera: {status}")
    require(video.get("path") == str(avi), f"recorder video path {video.get('path')!r}, wanted {str(avi)!r}")
    require(audio.get("active") is True, f"recorder WAV not active: {status}")
    require(audio.get("path") == str(avi.with_suffix(".wav")),
            f"recorder WAV path {audio.get('path')!r}, wanted {str(avi.with_suffix('.wav'))!r}")


def check_record_stopped(status):
    video, audio = (status or {}).get("video") or {}, (status or {}).get("audio") or {}
    require(video.get("active") is not True and audio.get("active") is not True,
            f"recorder still active after stop: {status}")


def mean_volume(log):
    """mean_volume in dB from an ffmpeg volumedetect log."""
    for line in log.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split()[0])
    raise RuntimeError("volumedetect printed no mean_volume")


class Recorder:
    """Native Mesen AVI (ZMBV, 256x224) + WAV between record start/stop, muxed to mp4.

    The mp4 keeps every AVI frame (no trim, crop or frame-rate change), scaled 4x
    nearest-neighbour to 1024x896, with the WAV as AAC audio. The AVI and WAV stay.
    """

    def __init__(self, work: Path, mp4: Path):
        self.work, self.mp4 = work, mp4
        self.avi, self.wav = mp4.with_suffix(".avi"), mp4.with_suffix(".wav")
        self.count, self.first, self.active, self.report = 0, None, False, {}
        for path in (self.mp4, self.avi, self.wav):
            require(not path.exists(), f"{path} exists; record never overwrites")

    def studio(self, socket, *args):
        result = subprocess.run([sys.executable, str(STUDIO), "--socket", socket, *args], capture_output=True,
                                text=True, timeout=15, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        with (self.work / "studio.log").open("a") as log:
            log.write(f"$ studio {' '.join(args)}\nrc={result.returncode}\n{result.stdout}{result.stderr}\n")
        if result.returncode != 0:
            raise RuntimeError(f"studio {' '.join(args)} failed rc={result.returncode}: "
                               f"{(result.stderr or result.stdout).strip()}")
        return result.stdout

    def start(self, s):
        require(STUDIO.is_file(), f"mesen_studio.py not found: {STUDIO} (set OOS_MESEN_STUDIO)")
        s.check_owner()
        require(s.paused(), "record start needs a paused CPU")
        before = native.number(s.b.get_rom_info()["frameCount"])
        shot = s.b.screenshot()
        require(shot, "pre-record SCREENSHOT failed")
        (self.work / "record-viewport.png").write_bytes(shot)
        require(png_size(shot) == NATIVE_SIZE, f"pre-record viewport is {png_size(shot)}, wanted {NATIVE_SIZE}")
        self.studio(s.a.socket, "record", "start", str(self.avi), "--wav")
        status = json.loads(self.studio(s.a.socket, "record", "status"))
        (self.work / "record-status-start.json").write_text(json.dumps(status, indent=2) + "\n")
        self.report.update(status_start=status, start_frame=before)
        check_record_status(status, self.avi)
        s.check_owner()
        require(s.paused() and native.number(s.b.get_rom_info()["frameCount"]) == before,
                "record start advanced emulated frames")
        self.active = True

    def capture(self, bridge, frame):
        self.first = frame if self.first is None else self.first
        self.count += 1

    def stop(self, s):
        if not self.active:
            return
        self.active = False
        self.studio(s.a.socket, "record", "stop")
        status = json.loads(self.studio(s.a.socket, "record", "status"))
        (self.work / "record-status-stop.json").write_text(json.dumps(status, indent=2) + "\n")
        self.report["status_stop"] = status
        check_record_stopped(status)

    def finish(self):
        """Media checks on the AVI/WAV, then the mp4 mux and its checks. Call after stop()."""
        require(self.count > 0, "record captured no frames")
        ffprobe, ffmpeg = _tool("ffprobe"), _tool("ffmpeg")

        def probe(path):
            out = subprocess.run([ffprobe, "-v", "error", "-count_frames", "-show_entries",
                                  "stream=codec_type,codec_name,width,height,sample_rate,channels,"
                                  "nb_read_frames,avg_frame_rate,start_time,duration",
                                  "-show_entries", "format=duration", "-of", "json", str(path)],
                                 capture_output=True, text=True, timeout=120, check=True)
            return json.loads(out.stdout)

        def stream(data, kind):
            return next((x for x in data["streams"] if x["codec_type"] == kind), None)

        def volume(path):
            out = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:a:0",
                                  "-af", "volumedetect", "-f", "null", "-"],
                                 capture_output=True, text=True, timeout=120)
            require(out.returncode == 0, f"volumedetect failed on {path}")
            return out.stderr

        avi_probe, wav_probe = probe(self.avi), probe(self.wav)
        video, wav_audio = stream(avi_probe, "video"), stream(wav_probe, "audio")
        require(video is not None, "AVI has no video stream")
        require((int(video["width"]), int(video["height"])) == NATIVE_SIZE,
                f"AVI is {video['width']}x{video['height']}, wanted {NATIVE_SIZE}")
        frames = int(video["nb_read_frames"])
        require(abs(frames - self.count) <= 2, f"AVI has {frames} frames, scene advanced {self.count}")
        require(stream(avi_probe, "audio") is not None, "AVI has no audio stream")
        require(wav_audio is not None and int(wav_audio["sample_rate"]) == 48000 and int(wav_audio["channels"]) == 2,
                f"WAV is not 48 kHz stereo: {wav_audio}")
        fps = Fraction(video["avg_frame_rate"])
        video_s, wav_s = frames / float(fps), float(wav_audio["duration"])
        require(abs(wav_s - video_s) < AV_TOLERANCE, f"WAV {wav_s:.3f}s vs video {video_s:.3f}s")
        wav_log = volume(self.wav)
        (self.work / "volumedetect-wav.log").write_text(wav_log)
        framemd5 = subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-i", str(self.avi), "-map", "0:v:0",
                                   "-f", "framemd5", "-"], capture_output=True, text=True, timeout=300, check=True)
        (self.work / "avi-video.framemd5").write_text(framemd5.stdout)
        frame_hashes = "\n".join(line.rsplit(",", 1)[-1].strip() for line in framemd5.stdout.splitlines()
                                 if line and not line.startswith("#"))
        stills = {}
        for label, index in (("first", 0), ("last", frames - 1)):
            path = self.work / f"{label}-recorded-frame.png"
            subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-i", str(self.avi), "-map", "0:v:0",
                            "-vf", f"select=eq(n\\,{index})", "-fps_mode", "passthrough", "-frames:v", "1",
                            str(path)], capture_output=True, timeout=60, check=True)
            require(png_size(path.read_bytes()) == NATIVE_SIZE, f"{path} is not 256x224")
            stills[label] = {"index": index, "path": str(path), "sha256": _sha(path)}

        cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin", "-i", str(self.avi), "-i", str(self.wav),
               "-map", "0:v:0", "-map", "1:a:0", "-vf", "scale=iw*4:ih*4:flags=neighbor,format=yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-c:a", "aac", "-b:a", "192k",
               "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(self.mp4)]
        subprocess.run(cmd, check=True, timeout=900)
        mp4_probe = probe(self.mp4)
        mv, ma = stream(mp4_probe, "video"), stream(mp4_probe, "audio")
        require(ma is not None and ma["codec_name"] == "aac", "mp4 has no AAC audio stream")
        require(mv is not None and int(mv["nb_read_frames"]) == frames, "mp4 frame count differs from the AVI")
        mp4_video_s, mp4_audio_s = float(mv["duration"]), float(ma["duration"])
        require(abs(mp4_audio_s - mp4_video_s) < AV_TOLERANCE,
                f"mp4 audio {mp4_audio_s:.3f}s vs video {mp4_video_s:.3f}s")
        mp4_log = volume(self.mp4)
        (self.work / "volumedetect.log").write_text(mp4_log)
        mean = mean_volume(mp4_log)
        require(mean > MIN_MEAN_DB, f"mp4 mean volume {mean} dB is at or below {MIN_MEAN_DB} dB (silence)")
        self.report.update(
            mp4=str(self.mp4), avi=str(self.avi), wav=str(self.wav), audio=True, route="native-avi-wav",
            mp4_sha256=_sha(self.mp4), avi_sha256=_sha(self.avi), wav_sha256=_sha(self.wav),
            captured_frames=self.count, first_frame=self.first, avi_frames=frames, avi_fps=str(fps),
            video_seconds=video_s, wav_seconds=wav_s, wav_minus_video_seconds=wav_s - video_s,
            mp4_video_seconds=mp4_video_s, mp4_audio_seconds=mp4_audio_s,
            mp4_av_difference_seconds=mp4_audio_s - mp4_video_s, mean_volume_db=mean,
            wav_mean_volume_db=mean_volume(wav_log), mp4_size=f"{mv['width']}x{mv['height']}",
            video_frames_sha256=hashlib.sha256(frame_hashes.encode()).hexdigest(), stills=stills,
            export_command=cmd)
        return self.report


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- steps ----

def _walk_to(s: SceneSession, step):
    a = step.args
    v = s.last
    if v["module"] != 7 or not v["indoors"]:
        raise SceneFailed(f"{step.label()}: walk_to needs underworld gameplay (module 7, indoors); "
                          f"got module {v['module']:02X} indoors {v['indoors']}")
    base = pathfind.colmap_address(v["layer"])
    grid = pathfind.Grid(s.block(base, pathfind.LAYER_SIZE), allow_doors=a["allow_doors"],
                         allow_hazard_edge=a["allow_hazard_edge"], blocked=set(a["blocked"]))
    try:
        points = pathfind.find_path(grid, (v["lx"], v["ly"]), (a["x"], a["y"]))
    except pathfind.NoPathError as error:
        raise SceneFailed(f"{step.label()}: room {v['room']:03X} layer {v['layer']}: {error}") from None
    name = f"step{step.index}"
    s.route["paths"][name] = points
    s.walk(name)
    s.result["walks"].append({"step": step.index, "room": f"{v['room']:03X}", "layer": v["layer"],
                              "colmap": f"{base:06X}", "from": [v["lx"], v["ly"]], "to": [a["x"], a["y"]],
                              "waypoints": points, "arrived": [s.last["lx"], s.last["ly"]]})
    ok = abs(s.last["lx"] - a["x"]) <= 2 and abs(s.last["ly"] - a["y"]) <= 2
    if not ok:
        raise SceneFailed(f"{step.label()}: stopped at ({s.last['lx']}, {s.last['ly']}), "
                          f"target ({a['x']}, {a['y']}); nearest free node was used")


def _run_step(s: SceneSession, step):
    a = step.args
    if step.kind == "walk_to":
        _walk_to(s, step)
    elif step.kind == "face":
        # One frame turns Link ($2F) and moves him at most ~2 px; two frames moved 4 px live.
        s.advance(a["button"], 1)
        s.neutral(2)
        if s.last["dir"] != FACING[a["dir"]]:
            raise SceneFailed(f"{step.label()}: $2F DIR={s.last['dir']}, wanted {FACING[a['dir']]}")
    elif step.kind == "equip":
        _equip(s, step)
    elif step.kind == "poke":
        _poke(s, a["writes"], step.label())
    elif step.kind == "press":
        s.hold(a["button"], a["frames"])
        s.neutral(2)
    elif step.kind == "hold":
        s.hold(a["button"], a["frames"])
    elif step.kind == "wait_until":
        spent = 0
        while not s.evaluate(a["expr"]):
            if spent >= a["max_frames"]:
                raise SceneFailed(f"{step.label()}: {a['label']!r} still false after {a['max_frames']} frames")
            s.advance("", 1)
            spent += s.last_advance
    elif step.kind == "check":
        if not s.evaluate(a["expr"]):
            s.result["checks"].append({"phase": s.phase, "name": a["label"], "passed": False})
            raise SceneFailed(f"{step.label()}: check failed: {a['label']!r} (state {s.last})")
        s.result["checks"].append({"phase": s.phase, "name": a["label"], "passed": True})
    elif step.kind == "record":
        if a["action"] == "start":
            if s.recorder is None and s.pending_recorder is not None and not s.pending_recorder.active:
                s.pending_recorder.start(s)
                s.recorder = s.pending_recorder
        elif s.recorder is not None:
            s.recorder.stop(s)
            s.recorder = None
    else:  # load is handled before the loop
        raise SceneError(f"{step.label()}: unexpected step")


def run_scene(scene: Scene, rom: Path, out: Path | None = None, record: Path | None = None, log=print):
    """Run `scene` on a copy of `rom`. Returns the result dict; raises SceneFailed on a failed check."""
    load = scene.load
    if load is None:
        raise SceneError("the first step must be load (srm or state)")
    rom = Path(rom).resolve()
    require(rom.is_file(), f"ROM not found: {rom}")
    work = Path(out).resolve() if out else Path(tempfile.mkdtemp(prefix=f"oos-scene-{scene.name}-"))
    work.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "Scripts" / "Agents"))
    import heavy_lock
    owner = f"scene-director-{os.getpid()}"
    token = heavy_lock.acquire(owner, f"scene {scene.name}", pid=os.getpid(), wait=0)
    if token is None:
        raise RuntimeError("heavy lock is busy; not starting Mesen (python3 Scripts/Agents/heavy_lock.py status)")
    slot = next(p for p in heavy_lock.slot_paths() if (heavy_lock.read_owner(p) or {}).get("token") == token)
    mesen, session = None, None
    result = {"scene": scene.name, "scene_file": str(scene.path), "rom": str(rom),
              "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(), "work": str(work), "passed": False}
    try:
        mesen = PrivateMesen(rom, work, load.args.get("srm"), owner)
        mesen.launch()
        bridge, sha1 = _connect(mesen)
        args = SimpleNamespace(socket=mesen.socket, pid=mesen.pid, status_file=mesen.status,
                               owner_file=slot / "owner", owner=owner, rom_sha1=sha1, output=work)
        session = SceneSession(args, bridge, work / "frames.jsonl")
        session.pending_recorder = None
        session.watch = scene.watch or {}
        if record is not None or scene.uses_record():
            mp4 = Path(record).resolve() if record is not None else work / f"{scene.name}.mp4"
            session.pending_recorder = Recorder(work, mp4)
        session.check_owner()
        if "state" in load.args:
            require(bridge.load_state(path=str(load.args["state"])), f"load_state failed: {load.args['state']}")
            bridge.pause()
            session.snap()
        else:
            _cold_boot(session)
        _apply_fixtures(session, load.args["fixtures"])
        session.neutral(2)
        if "entrance" in load.args:
            _load_entrance(session, load.args["entrance"])
        if record is not None and not scene.uses_record():
            session.pending_recorder.start(session)  # --record alone: everything after load
            session.recorder = session.pending_recorder
        start = dict(session.last)
        result["start"] = start
        if start["module"] == 7 and start["indoors"]:
            # Diagnostic: the live collision layer the first walk_to will plan on.
            base = pathfind.colmap_address(start["layer"])
            (work / "colmap-start.bin").write_bytes(session.block(base, pathfind.LAYER_SIZE))
            result["start_colmap"] = f"{base:06X}"
        for step in scene.steps[1:]:
            session.phase = step.label()
            before = dict(session.last)
            log(f"{step.label()}: {step.args if step.kind not in ('wait_until', 'check') else step.args['label']}")
            _run_step(session, step)
            session.result["steps"].append({"step": step.index, "kind": step.kind,
                                            "before": before, "after": dict(session.last)})
        if session.recorder is not None:  # no "record stop": capture ran to the end
            session.recorder.stop(session)
            session.recorder = None
        wram = hashlib.sha256()
        for offset in range(0, 0x20000, 0x4000):
            wram.update(session.block(0x7E0000 + offset, 0x4000))
        shot = bridge.screenshot()
        if shot:
            (work / "final.png").write_bytes(shot)
        result.update(final=session.last, frame_count=session.frame_count, wram_sha256=wram.hexdigest())
        if session.pending_recorder is not None:
            mesen.stop()  # the AVI/WAV are closed by record stop; check and mux them offline
            result["record"] = session.pending_recorder.finish()
        result["passed"] = True
        return result
    finally:
        if session is not None:
            result.update(checks=session.result["checks"], steps=session.result["steps"],
                          walks=session.result["walks"], writes=session.result["writes"])
            try:
                session.input("")
            except BaseException:  # noqa: BLE001 - cleanup must continue
                pass
            if session.pending_recorder is not None:
                try:
                    session.pending_recorder.stop(session)  # failed mid-take: close the AVI/WAV
                except BaseException as error:  # noqa: BLE001 - cleanup must continue
                    result["record_stop_error"] = str(error)
                result.setdefault("record", session.pending_recorder.report)
            session.log.close()
        if mesen is not None:
            mesen.stop()
        heavy_lock.release(token)
        (work / "result.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
