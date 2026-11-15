#!/usr/bin/env python3
"""Private Epona site clip runner (QUEUE138 long-jump / ride-tour lane).

Offline: validate site JSON + ROM horse NMI + seed.
Execute: boot cured seed → warp → mount → ride routes → AVI → RESULT.json.

Never oos-rc-play. No shared Roms/ writes. Output must be a new directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
OOS = HERE.parents[1]
SITES_DIR = HERE / "horse_ride_sites"
SCRATCH = Path("/Users/scawful/src/hobby/oracle-of-secrets-scratch/horse-ride-clips-20261115")
CLIENT = Path("/Users/scawful/src/hobby/mesen2-oos/tools/oos_client")
SESSION_ROOT = Path(
    "/Users/scawful/src/hobby/oracle-of-secrets-worktrees/d4-actor-integration-20261106"
)
BOOT_PATH = Path(
    "/Users/scawful/src/hobby/oracle-of-secrets-scratch/"
    "zora-combined-water-candidate-20261114/native-case04/boot_confirmed_pause.py"
)
ICLOUD = Path(
    "/Users/scawful/Library/Mobile Documents/com~apple~CloudDocs/"
    "Oracle of Secrets/2026-11-15 - Dev Updates and Test ROMs"
)

# Setup-only WRAM allowlist: OracleCheats warp bytes + diag mount + Link XY.
WHITELIST = {
    0x7EF3CA,
    0x7E0FFF,
    0x7E00A0,
    0x7E00A1,
    0x7E010A,
    0x7E04AA,
    0x7E0013,
    0x7E009B,
    0x7E0011,
    0x7E00B0,
    0x7E0010,
    0x7E1EE6,
    0x7E1EE7,
    0x7E1EFD,
    0x7E00BC,
    0x7EC67E,
    0x7EC67F,
    0x7E02B2,
    0x7E0022,
    0x7E0023,
    0x7E0020,
    0x7E0021,
    # OW camera scroll (npc_a place sync so DefaultNpc stays on-screen)
    0x7E00E2,
    0x7E00E3,
    0x7E00E8,
    0x7E00E9,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def load_module(path: Path, name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def warm_debugger(bridge, logfile: Path, clock=time.monotonic, sleep=time.sleep):
    original = bridge.send_command

    def traced(command, *args, **kwargs):
        try:
            reply = original(command, *args, **kwargs)
        except BaseException as exc:
            with logfile.open("a") as f:
                f.write(json.dumps({"command": command, "exception": repr(exc)}) + "\n")
            raise
        if command in ("CPU", "PAUSE", "STATE"):
            with logfile.open("a") as f:
                f.write(json.dumps({"command": command, "reply": reply}) + "\n")
        return reply

    bridge.send_command = traced
    try:
        deadline = clock() + 3.0
        while True:
            remaining = deadline - clock()
            require(remaining > 0, "fresh-process running readiness exceeded 3s")
            reply = bridge.send_command("STATE", timeout=remaining)
            require(clock() < deadline, "fresh-process running readiness exceeded 3s")
            if reply.get("success") is True:
                data = reply.get("data")
                if isinstance(data, str):
                    data = json.loads(data)
                require(
                    isinstance(data, dict) and data.get("running") is True,
                    "unexpected startup STATE payload",
                )
                break
            require(
                reply.get("success") is False
                and reply.get("error") == "No ROM loaded",
                "unexpected startup STATE failure",
            )
            sleep(min(0.02, max(0, deadline - clock())))
        require(bridge.pause(), "fresh-process debugger pause")
        pause_deadline = clock() + 3.0
        data = None
        while clock() < pause_deadline:
            reply = bridge.send_command("STATE")
            data = reply.get("data")
            if isinstance(data, str):
                data = json.loads(data)
            if (
                reply.get("success") is True
                and isinstance(data, dict)
                and data.get("paused") is True
            ):
                break
            sleep(0.02)
        require(
            isinstance(data, dict) and data.get("paused") is True,
            "fresh debugger not ready",
        )
    finally:
        bridge.send_command = original


def resolve_site(path: Path) -> dict:
    sys.path.insert(0, str(CLIENT))
    from mesen2_client_lib.horse_ride import rom_has_horse_nmi, validate_site

    raw = json.loads(path.read_text())
    site = validate_site(raw)
    rom = Path(site["rom"]).expanduser()
    require(rom.is_file(), f"rom missing: {rom}")
    site["rom_path"] = rom
    site["rom_sha1"] = sha1(rom)
    site["rom_sha256"] = sha256(rom)
    site["horse_nmi"] = rom_has_horse_nmi(rom)
    if site.get("map_rom"):
        mp = Path(site["map_rom"]).expanduser()
        site["map_rom_exists"] = mp.is_file()
        if mp.is_file():
            site["map_rom_sha1"] = sha1(mp)
            site["map_rom_horse_nmi"] = rom_has_horse_nmi(mp)
    seed = Path(site["seed"]).expanduser() if site.get("seed") else None
    if seed is None or not seed.is_file():
        seed = Path(
            "/Users/scawful/src/hobby/oracle-of-secrets-scratch/"
            "horse-front-codex-20261115/current-master-anchor02/private01/"
            "native12/ranch-cured-original.srm"
        )
    require(seed.is_file(), f"seed missing: {seed}")
    site["seed_path"] = seed
    return site


def preflight_seed(seed: Path) -> None:
    data = seed.read_bytes()
    require(len(data) == 8192, "seed length")
    require(data[:0x500] == data[0xF00:0x1400], "seed File1 mirrors")
    require(
        sum(int.from_bytes(data[i : i + 2], "little") for i in range(0, 0x500, 2))
        & 65535
        == 0x5A5A,
        "seed checksum",
    )
    require(
        data[0x3D8] & 1 and data[0x34C] and data[0x36D] == 24 and data[0x36C] == 32
        and data[0x3CC] == 0,
        "seed cure/ocarina/HP/follower",
    )


def x_delta(a: dict | None, b: dict | None) -> int:
    if not a or not b:
        return 0
    return abs(int(b.get("x", b[0] if isinstance(b, (list, tuple)) else 0))
               - int(a.get("x", a[0] if isinstance(a, (list, tuple)) else 0)))


def leg_end_xy(leg) -> tuple[int, int] | None:
    if not leg or not leg.end:
        return None
    return int(leg.end[0]), int(leg.end[1])


def run_execute(site: dict, out: Path, *, copy_icloud: bool) -> dict:
    sys.path[:0] = [str(CLIENT), str(SESSION_ROOT / "Scripts/Agents")]
    os.environ["OOS_ROOT"] = str(OOS)
    os.environ["MESEN2_OOS_ROOT"] = str(CLIENT.parents[1])

    from native_session import NativeSession
    import heavy_lock
    from mesen2_client_lib.bridge import MesenBridge
    from mesen2_client_lib.oracle_cheats import OracleCheats
    from mesen2_client_lib.horse_ride import (
        CURRENT_MASK,
        HORSE_FORM,
        HorseRideDriver,
        advance_exact,
        legs_as_dicts,
    )

    BOOT = load_module(BOOT_PATH, "horse_boot")
    BOOT.FIELDS = {
        "cure": 0x3D8,
        "ocarina": 0x34C,
        "health": 0x36D,
        "max_health": 0x36C,
        "follower": 0x3CC,
    }

    game = site["rom_path"]
    seed = site["seed_path"]
    want_sha1 = site["rom_sha1"]
    log: dict = {
        "status": "RUNNING",
        "site": site["id"],
        "label": site["label"],
        "area": f"0x{site['area']:02X}",
        "rom": str(game),
        "rom_sha1": want_sha1,
        "rom_sha256": site["rom_sha256"],
        "horse_nmi": site["horse_nmi"],
        "mount": site["mount"],
        "events": [],
        "legs": {},
        "checks": {},
    }
    require(site["horse_nmi"], "ROM lacks horse NMI hook (0x22 at 0xB5C); use horse-capable native build")

    session = NativeSession(
        f"Cursor-Horse-{site['id']}",
        f"private horse site clip {site['id']}; never oos-rc-play",
        out / "session",
        deadline=480,
        wait=600,
    )
    driver: HorseRideDriver | None = None
    case = None
    recording_path = out / f"{site['id']}.avi"

    class Case(BOOT.Case):
        def __init__(self_inner):
            self_inner.out = out
            self_inner.log = log
            self_inner.rom = game
            self_inner.want_sha1 = want_sha1
            self_inner.setup = False
            self_inner.guard = None
            self_inner.frames = 0
            self_inner.start_frame = None
            self_inner.pid = None
            BOOT.profile(out / "profile", seed.read_bytes())
            self_inner.pid, sock = session.launch_mesen(
                game,
                home=out / "profile",
                launcher_args=(
                    "--headless",
                    "--no-save-settings",
                    "--no-copy-settings",
                    "--no-seed-project-states",
                    "--no-state-set",
                    "--app",
                    "/Applications/Mesen2 OOS.app",
                ),
            )
            log.update(pid=self_inner.pid, socket=str(sock))
            (out / "RUNNING.json").write_text(json.dumps(log, indent=2))
            print(json.dumps({"pid": self_inner.pid, "socket": str(sock)}), flush=True)
            self_inner.b = MesenBridge(str(sock), auto_reconnect=False, max_retries=0)
            original_write = self_inner.b.write_block

            def write(a, data, **kw):
                require(
                    self_inner.setup
                    and a in WHITELIST
                    and len(data) == 1
                    and not kw.get("memtype"),
                    f"forbidden runtime write @ {a:#x}",
                )
                log.setdefault("diagnostic_writes", []).append(
                    {"address": hex(a), "before": self_inner.r(a), "after": data[0]}
                )
                return original_write(a, data, **kw)

            self_inner.b.write_block = write
            self_inner.b.write_memory = lambda a, v, memtype=None: write(
                a, bytes([v]), memtype=memtype
            )
            self_inner.b.write_memory16 = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("16bit writes prohibited")
            )
            end = time.monotonic() + 12
            while self_inner.b.get_rom_info().get("sha1", "").lower() != want_sha1.lower():
                require(time.monotonic() < end, "ROM identity timeout")
                time.sleep(0.1)
            warm_debugger(self_inner.b, out / "startup-replies.jsonl")
            self_inner.identity()

        def identity(self_inner):
            info = self_inner.b.get_rom_info()
            require(
                info.get("sha1", "").lower() == want_sha1.lower(),
                "ROM identity changed",
            )
            frame = int(info["frameCount"])
            if self_inner.start_frame is None:
                self_inner.start_frame = frame
            require(
                0 <= frame - self_inner.start_frame <= 7200,
                "7200-frame ceiling",
            )
            return info

        def command(self_inner, name, **args):
            reply = self_inner.b.send_command(name, args)
            with (out / "commands.jsonl").open("a") as f:
                f.write(json.dumps({"command": name, "args": args, "reply": reply}) + "\n")
            require(reply.get("success"), name + ": " + str(reply))
            return reply.get("data", {})

        def r(self_inner, addr, n=1):
            if n == 2:
                return self_inner.b.read_memory16(addr)
            return self_inner.b.read_memory(addr)

        def place_xy(self_inner, x: int, y: int, *, sync_camera: bool = False) -> None:
            self_inner.setup = True
            try:
                self_inner.b.write_memory(0x7E0022, x & 0xFF)
                self_inner.b.write_memory(0x7E0023, (x >> 8) & 0xFF)
                self_inner.b.write_memory(0x7E0020, y & 0xFF)
                self_inner.b.write_memory(0x7E0021, (y >> 8) & 0xFF)
                if sync_camera:
                    # Center OW camera on Link so dynamic Persist sprites are on-screen.
                    cx = max(0, x - 128)
                    cy = max(0, y - 112)
                    self_inner.b.write_memory(0x7E00E2, cx & 0xFF)
                    self_inner.b.write_memory(0x7E00E3, (cx >> 8) & 0xFF)
                    self_inner.b.write_memory(0x7E00E8, cy & 0xFF)
                    self_inner.b.write_memory(0x7E00E9, (cy >> 8) & 0xFF)
            finally:
                self_inner.setup = False

        def shot(self_inner, name: str) -> None:
            png = self_inner.b.screenshot()
            if png:
                (out / f"{name}.png").write_bytes(png)

    try:
        with session:
            try:
                case = Case()
                case.boot()
                before = case.inventory()
                require(
                    before["cure"] & 1
                    and before["ocarina"]
                    and before["health"] == 24
                    and before["follower"] == 0,
                    "cold seed admission",
                )
                case.guard = before

                def send(name, **args):
                    return case.command(name, **args)

                def ensure_paused() -> None:
                    for _ in range(50):
                        reply = case.b.send_command("STATE")
                        data = reply.get("data")
                        if isinstance(data, str):
                            data = json.loads(data)
                        if isinstance(data, dict) and data.get("paused") is True:
                            return
                        case.b.pause()
                        time.sleep(0.01)
                    raise RuntimeError("could not pause owned instance for FRAME step")

                def advance(n):
                    for _ in range(n):
                        ensure_paused()
                        advance_exact(case.b, 1, timeout=6)
                        case.frames += 1
                        case.identity()
                        if case.guard:
                            require(
                                case.inventory() == case.guard,
                                "HP/inventory/follower changed",
                            )

                def write_byte(a, v):
                    case.setup = True
                    try:
                        case.b.write_memory(a, v)
                    finally:
                        case.setup = False

                driver = HorseRideDriver(
                    case.b,
                    send=send,
                    advance=advance,
                    write_byte=write_byte,
                    frame_budget=7200,
                )

                # Warp to Ranch for npc_a; else warp_area (may differ from target area).
                warp_to = 0 if site["mount"] == "npc_a" else int(site.get("warp_area", site["area"]))
                case.setup = True
                try:
                    arrival = OracleCheats(case.b, root=OOS).warp_area(warp_to)
                finally:
                    case.setup = False
                require(arrival.get("ok"), f"warp failed: {arrival}")
                # OracleCheats may leave the emu running; exact FRAME needs pause.
                require(case.b.pause(), "pause after warp")
                case.tick = lambda frames=2, button="": driver.tick(frames, button)

                sx, sy = site["start_xy"]
                target_area = int(site["area"])

                def count_horse_npc() -> int:
                    n = 0
                    for i in range(16):
                        if driver.r8(0x7E0DD0 + i) and driver.r8(0x7E0E20 + i) == 0x2D:
                            n += 1
                    return n

                if site["mount"] == "diag":
                    driver.tick(20)
                    # Non-warpable targets (e.g. $24): walk from neighbor via enter route.
                    if driver.r8(0x7E008A) != target_area and "enter" in site["routes"]:
                        # Seed just west of the east seam when coming from warp_area.
                        case.place_xy(max(0, sx - 48), sy)
                        driver.tick(4)
                        driver.run_route(
                            site["routes"]["enter"],
                            settle=2,
                            require_form=0,
                            stall=20,
                        )
                        log["events"].append(
                            {
                                "enter": True,
                                "area": driver.r8(0x7E008A),
                                "sample": driver.sample_dict(),
                            }
                        )
                    if driver.r8(0x7E008A) != target_area:
                        case.place_xy(sx, sy)
                        driver.tick(30)
                    # Accept warp neighbor when target has no exit-table room ($24).
                    allowed = {target_area, int(site.get("warp_area", target_area))}
                    require(
                        driver.r8(0x7E008A) in allowed,
                        f"failed to reach area 0x{target_area:02X} "
                        f"(at 0x{driver.r8(0x7E008A):02X}; allowed "
                        f"{sorted(hex(a) for a in allowed)})",
                    )
                    case.place_xy(sx, sy)
                    driver.tick(8)
                    require(case.b.pause(), "pause after place")
                    require(case.b.pause(), "pause before record")
                    driver.record_start(recording_path)
                    driver.diag_mount()
                    log["events"].append({"mount": "diag", "sample": driver.sample_dict()})
                else:
                    # horse_on warp_area($00) via room $03 lands at ~(200,99); vG landed
                    # beside DefaultNpc ~(456,668). Teleport + sync OW camera so $2D is
                    # on-screen (far landing + off-camera cull broke npc_a on horse_on).
                    nx, ny = site["npc_xy"]
                    case.place_xy(nx, ny, sync_camera=True)
                    spawned = False
                    for _ in range(120):
                        driver.tick(1)
                        if (
                            driver.r8(0x7E0010) == 9
                            and driver.r8(0x7E0011) == 0
                            and count_horse_npc()
                        ):
                            spawned = True
                            break
                    require(spawned, "Ranch Epona $2D did not spawn after camera-synced place")
                    require(
                        driver.approach_xy(nx, ny, radius=26, max_steps=40),
                        "not within A-mount range",
                    )
                    log["events"].append(
                        {
                            "label": "pre_mount",
                            "horses": count_horse_npc(),
                            "sample": driver.sample_dict(),
                        }
                    )
                    require(case.b.pause(), "pause before record")
                    driver.record_start(recording_path)
                    mounted = False
                    for attempt in range(5):
                        try:
                            driver.mount_npc_a(settle=40)
                            mounted = True
                            break
                        except Exception as exc:
                            log.setdefault("mount_attempts", []).append(
                                {
                                    "attempt": attempt,
                                    "error": str(exc),
                                    "horses": count_horse_npc(),
                                }
                            )
                            driver.tick(8)
                    require(mounted, "A did not mount Ranch Epona after retries")
                    log["events"].append({"mount": "npc_a", "sample": driver.sample_dict()})

                case.shot("mounted")
                routes = site["routes"]
                checks = log["checks"]

                def run_named(name: str, require_form):
                    if name not in routes:
                        return None
                    start = driver.sample_dict()
                    legs = driver.run_route(
                        routes[name],
                        settle=4,
                        require_form=require_form,
                        stall=12,
                    )
                    end = driver.sample_dict()
                    log["legs"][name] = {
                        "start": start,
                        "end": end,
                        "legs": legs_as_dicts(legs),
                        "jumped": any(L.jumped for L in legs),
                        "dx": abs(end["link_x"] - start["link_x"]),
                        "dy": abs(end["link_y"] - start["link_y"]),
                    }
                    case.shot(name)
                    return log["legs"][name]

                if "control" in routes:
                    run_named("control", HORSE_FORM)
                    dis = driver.dismount_r()
                    checks["dismount"] = {
                        "ok": dis.form == int(site["expect"].get("form_dismounted", 0)),
                        "form": dis.form,
                    }
                    case.shot("dismounted")
                else:
                    # Site gap: prefer jump-aware ride (QUEUE138), then post probes.
                    use_jump = bool(site["expect"].get("use_jump_ride", True))
                    ew_btn = "right"
                    we_btn = "left"
                    if "mounted_ew" in routes and routes["mounted_ew"]:
                        ew_btn = routes["mounted_ew"][0][0]
                    if "mounted_we" in routes and routes["mounted_we"]:
                        we_btn = routes["mounted_we"][0][0]

                    if use_jump:
                        ew_j = driver.ride_until_jump_land(ew_btn, limit=160)
                        log["legs"]["mounted_ew"] = ew_j
                        case.shot("mounted_ew")
                        checks["mounted_ew"] = {
                            "ok": bool(ew_j.get("ok")),
                            "jumped": ew_j.get("jumped"),
                            "landed": ew_j.get("landed"),
                        }
                        checks["ew_post"] = driver.post_land_probes(
                            ("up", "left"), n=6, remount=True, label="ew_post"
                        )
                    else:
                        ew = run_named("mounted_ew", HORSE_FORM)
                        checks["mounted_ew"] = {
                            "ok": bool(ew and ew["dx"] >= int(site["expect"].get("mounted_cross_x_delta_min", 24))),
                            "dx": (ew or {}).get("dx"),
                            "jumped": (ew or {}).get("jumped"),
                        }

                    if "mounted_we" in routes:
                        case.place_xy(sx + 80, sy)
                        driver.tick(5)
                        if driver.r8(CURRENT_MASK) != HORSE_FORM:
                            driver.diag_mount()
                        if use_jump:
                            we_j = driver.ride_until_jump_land(we_btn, limit=160)
                            log["legs"]["mounted_we"] = we_j
                            case.shot("mounted_we")
                            checks["mounted_we"] = {
                                "ok": bool(we_j.get("ok")),
                                "jumped": we_j.get("jumped"),
                                "landed": we_j.get("landed"),
                            }
                            checks["we_post"] = driver.post_land_probes(
                                ("right", "up", "down"), n=6, remount=True, label="we_post"
                            )
                        else:
                            run_named("mounted_we", HORSE_FORM)

                    if site["watch"].get("post_land_freeze"):
                        checks["freeze_watch"] = driver.watch_post_land_freeze(
                            frames=int(site["watch"].get("freeze_frames", 30)),
                            button=str(site["watch"].get("freeze_button", ew_btn)),
                        )

                    # Foot control: dismount, place at start, try cross without horse.
                    if driver.r8(CURRENT_MASK) == HORSE_FORM:
                        driver.dismount_r(settle=40)
                    case.place_xy(sx, sy)
                    driver.tick(8)
                    foot = run_named("foot", require_form=0)
                    min_dx = int(site["expect"].get("mounted_cross_x_delta_min", 24))
                    if foot and site["expect"].get("foot_must_fail_cross", True):
                        checks["foot"] = {
                            "ok": foot["dx"] < min_dx,
                            "dx": foot["dx"],
                            "note": "foot must not clear gap",
                        }

                driver.record_stop()
                log["avi"] = recording_path.name if recording_path.is_file() else None

                # Aggregate status.
                fails = [
                    k
                    for k, v in checks.items()
                    if isinstance(v, dict) and v.get("ok") is False
                    and k in ("mounted_ew", "mounted_we", "foot", "ew_post", "we_post", "dismount")
                ]
                freezes = [
                    k
                    for k, v in checks.items()
                    if isinstance(v, dict) and v.get("freeze")
                ]
                if freezes and fails:
                    log["status"] = "STOP_POST_LAND_FREEZE"
                    log["freeze_keys"] = freezes
                    log["failed"] = fails
                elif freezes:
                    log["status"] = "STOP_POST_LAND_FREEZE"
                    log["freeze_keys"] = freezes
                elif fails:
                    log["status"] = "FAIL_CHECKS"
                    log["failed"] = fails
                else:
                    log["status"] = "PASS"

                if copy_icloud and log["status"] == "PASS" and recording_path.is_file():
                    ICLOUD.mkdir(parents=True, exist_ok=True)
                    dest = ICLOUD / f"epona-{site['id']}-{want_sha1[:8]}.avi"
                    shutil.copy2(recording_path, dest)
                    log["icloud"] = str(dest)

            except BaseException as exc:
                log["status"] = "STOP_FIRST_FAILURE"
                log["error"] = repr(exc)
                if case:
                    try:
                        case.shot("STOP")
                    except Exception as ee:
                        log["evidence_error"] = repr(ee)
                raise
            finally:
                if driver and driver.recording:
                    try:
                        driver.record_stop()
                    except Exception as ee:
                        log["record_stop_error"] = repr(ee)
    finally:
        log["teardown"] = getattr(session, "teardown_result", None)
        (out / "RESULT.json").write_text(json.dumps(log, indent=2) + "\n")
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--site",
        required=True,
        help="site id or path to site JSON under horse_ride_sites/",
    )
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--output", type=Path, help="new output directory")
    ap.add_argument(
        "--icloud",
        action="store_true",
        help="copy AVI to iCloud Dev Updates folder on PASS",
    )
    args = ap.parse_args()

    site_arg = Path(args.site)
    if site_arg.suffix == ".json" and site_arg.is_file():
        site_path = site_arg
    else:
        site_path = SITES_DIR / f"{args.site}.json"
        if not site_path.is_file():
            site_path = SITES_DIR / args.site
    require(site_path.is_file(), f"site not found: {site_path}")

    site = resolve_site(site_path)
    preflight_seed(site["seed_path"])
    offline = {
        "status": "READY_OFFLINE",
        "site": site["id"],
        "area": f"0x{site['area']:02X}",
        "rom": str(site["rom_path"]),
        "rom_sha1": site["rom_sha1"],
        "horse_nmi": site["horse_nmi"],
        "mount": site["mount"],
        "routes": list(site["routes"].keys()),
        "map_rom": site.get("map_rom") or None,
        "map_rom_horse_nmi": site.get("map_rom_horse_nmi"),
        "native": False,
    }
    if not args.execute:
        print(json.dumps(offline, indent=2))
        return 0 if site["horse_nmi"] else 2

    require(args.output is not None, "--output required with --execute")
    out = args.output.expanduser().resolve()
    require(not out.exists(), f"output must be new: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    (out / "SITE.json").write_text(json.dumps(site, indent=2, default=str) + "\n")
    (out / "OFFLINE.json").write_text(json.dumps(offline, indent=2) + "\n")

    try:
        log = run_execute(site, out, copy_icloud=bool(args.icloud))
    except BaseException as exc:
        # RESULT already written inside run_execute finally when possible
        result_path = out / "RESULT.json"
        if result_path.is_file():
            log = json.loads(result_path.read_text())
        else:
            log = {"status": "STOP_FIRST_FAILURE", "error": repr(exc)}
            result_path.write_text(json.dumps(log, indent=2) + "\n")
        print(json.dumps({"status": log.get("status"), "error": log.get("error")}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": log.get("status"),
                "site": site["id"],
                "avi": log.get("avi"),
                "checks": log.get("checks"),
                "icloud": log.get("icloud"),
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0 if log.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
