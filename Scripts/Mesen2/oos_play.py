#!/usr/bin/env python3
"""oos-play: open or refresh scawful's Mesen2 play window with the latest build.

Manages ONE instance, `oos-rc-play` (socket /tmp/mesen2-oos-rc-play.sock,
profile ~/Library/Application Support/Mesen2-instances/oos-rc-play). Agent
instances are listed, never touched.

  oos-play              window closed: open it on the latest staged build.
                        window open:   offer the latest build (Load now / Later
                                       banner); nothing if it already runs it.
  oos-play --now        window open: live-load now (backup state + .srm first).
  oos-play --rom PATH   use PATH instead of Roms/Playtest/oos-play.sfc.
  oos-play --status     show the play window, agent instances and the heavy lock.
  oos-play --offer-only offer if the window is open; never open it.
  oos-play --place      snap the open window to the default size and position.

The latest build is Roms/Playtest/oos-play.sfc (staged by
Scripts/Build/stage_playtest.py; label from Roms/Playtest/latest.json). The
profile keeps one save for every Oracle ROM ("Oracle": {"PersistentSaveName":
"oos-play"} in its settings.json); this script sets it if missing.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "Scripts/Mesen2/mesen2_client.py"
LAUNCHER = REPO / "Scripts/Mesen2/mesen2_launch_instance.sh"
PLAYTEST = REPO / "Roms/Playtest"
INSTANCE = "oos-rc-play"
SOCK = Path(f"/tmp/mesen2-{INSTANCE}.sock")
PROFILE = Path.home() / "Library/Application Support/Mesen2-instances" / INSTANCE


def use_instance(name: str) -> None:
    """Testing hook: manage another instance name instead of the play window."""
    global INSTANCE, SOCK, PROFILE
    INSTANCE = name
    SOCK = Path(f"/tmp/mesen2-{name}.sock")
    PROFILE = Path.home() / "Library/Application Support/Mesen2-instances" / name
SAVE_NAME = "oos-play"
HEAVY_LOCK = Path("/tmp/oos-heavy.lock")


def socket_alive(path: Path) -> bool:
    if not path.exists():
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        s.close()


def client(sock: Path, *args: str, timeout: float = 15) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLIENT), "--socket", str(sock), *args],
                          capture_output=True, text=True, timeout=timeout)


def loaded_rom(sock: Path, timeout: float = 15) -> dict | None:
    try:
        r = client(sock, "rom-info", "--json", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    try:
        text = r.stdout[r.stdout.index("{"):]
        return json.loads(text)
    except (ValueError, json.JSONDecodeError):
        return None


def label_for(rom: Path) -> str:
    latest = PLAYTEST / "latest.json"
    if rom.name == "oos-play.sfc" and latest.is_file():
        info = json.loads(latest.read_text())
        return f"v{info['version']}-b{info['build']}"
    return rom.stem


DEFAULT_MESEN_HOME = Path.home() / "Documents/Mesen2"
PLAY_ROM = PLAYTEST / "oos-play.sfc"


def _recent_files(data: dict) -> list:
    recent = data.get("RecentFiles")
    if isinstance(recent, dict):
        return recent.setdefault("Items", [])
    if isinstance(recent, list):
        return recent
    data["RecentFiles"] = []
    return data["RecentFiles"]


def _rom_file(item: dict) -> dict | None:
    rom_file = item.get("RomFile")
    if isinstance(rom_file, dict) and rom_file.get("Path"):
        return rom_file
    if item.get("Path"):
        return item
    return None


def _put_play_rom_first(settings: Path, rom: Path) -> None:
    """Drop recent-file entries whose ROM is gone, and keep the play ROM first.

    Mesen stores each entry as {RomFile: {Path, InnerFile, InnerFileIndex}, PatchFile}.
    """
    if not settings.is_file():
        return
    data = json.loads(settings.read_text(encoding="utf-8-sig"))
    items = _recent_files(data)
    play = {
        "RomFile": {"Path": str(rom), "InnerFile": "", "InnerFileIndex": 0},
        "PatchFile": None,
    }
    kept = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rom_file = _rom_file(item)
        if rom_file is None:
            continue
        path = Path(rom_file.get("Path") or "")
        if not path.is_file() or path.resolve() == rom.resolve():
            continue
        if "RomFile" not in item:
            item = {"RomFile": rom_file, "PatchFile": item.get("PatchFile")}
        kept.append(item)
    items[:] = [play, *kept]
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8-sig")


def _retarget_missing_rgd(path: Path, rom: Path) -> bool:
    """Point an Oracle recent-game tile at the play ROM when its file is gone."""
    with zipfile.ZipFile(path) as src:
        if "RomInfo.txt" not in src.namelist():
            return False
        lines = src.read("RomInfo.txt").decode("utf-8", "replace").splitlines()
        if len(lines) < 2 or not lines[0].lower().startswith("oos"):
            return False
        target = Path(lines[1].strip())
        if target.is_file():
            return False
        patch = lines[2] if len(lines) > 2 else ""
        info = f"{rom.name}\n{rom}\n{patch}\n".encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for item in src.infolist():
                payload = info if item.filename == "RomInfo.txt" else src.read(item.filename)
                out.writestr(item, payload)
    path.write_bytes(buf.getvalue())
    return True


def refresh_recent_games(rom: Path | None = None) -> None:
    """Keep Mesen's recent-game tiles pointed at the staged play ROM.

    The dock app uses ~/Documents/Mesen2. The play window uses its own profile.
    Tiles are *.rgd files; the File menu uses RecentFiles in settings.json.
    """
    rom = (rom or PLAY_ROM).resolve()
    if not rom.is_file():
        return
    homes = []
    for home in (DEFAULT_MESEN_HOME, PROFILE):
        if home not in homes:
            homes.append(home)
    play_rgd = PROFILE / "RecentGames" / "oos-play.rgd"
    for home in homes:
        folder = home / "RecentGames"
        folder.mkdir(parents=True, exist_ok=True)
        retargeted = []
        for rgd in folder.glob("*.rgd"):
            try:
                if _retarget_missing_rgd(rgd, rom):
                    retargeted.append(rgd.name)
            except (zipfile.BadZipFile, OSError) as exc:
                print(f"recent games: skipped {rgd.name} ({exc})")
        if home != PROFILE and play_rgd.is_file():
            dest = folder / "oos-play.rgd"
            shutil.copy2(play_rgd, dest)
            os.utime(dest, None)
        _put_play_rom_first(home / "settings.json", rom)
        if retargeted:
            print(f"recent games: {home.name} now opens {rom.name} ({', '.join(retargeted)})")


def ensure_shared_save() -> None:
    settings = PROFILE / "settings.json"
    if not settings.is_file():
        return  # the launcher seeds it on first run
    data = json.loads(settings.read_text(encoding="utf-8-sig"))
    changed = False
    oracle = data.setdefault("Oracle", {})
    if oracle.get("PersistentSaveName") != SAVE_NAME:
        oracle["PersistentSaveName"] = SAVE_NAME
        changed = True
        print(f"play profile: shared Oracle save set to {SAVE_NAME}.srm")
    if not oracle.get("PlayerWindow"):
        oracle["PlayerWindow"] = True  # title "Oracle <build> [play]" (mesen2-oos claude/offer-rom)
        changed = True
        print("play profile: marked as the player window")
    main_window = data.setdefault("MainWindow", {})
    if main_window.get("WindowIsMaximized"):
        main_window["WindowIsMaximized"] = False  # oos-play sizes the window itself
        changed = True
        print("play profile: no longer starts maximized")
    if changed:
        settings.write_text(json.dumps(data, indent=2), encoding="utf-8-sig")


def play_pid() -> int | None:
    """The play window's pid from Mesen's status file (its title no longer names the instance)."""
    try:
        return int(json.loads(SOCK.with_suffix(".status").read_text())["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def bring_to_current_space(wait_s: float = 0.0, place: bool = False) -> None:
    """Move the play window to the yabai space scawful is on and focus it.

    Only for actions he triggers (Play, Load now, launch); the passive offer
    after staging never moves windows. No-op without yabai. The yabai rule keeps
    Mesen on the tiled-window sub-layer, so focus is enough to show it.
    """
    import shutil
    import time
    yabai = shutil.which("yabai")
    if not yabai:
        return
    def query(*args):
        r = subprocess.run([yabai, "-m", "query", *args], capture_output=True, text=True)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    deadline = time.monotonic() + wait_s
    while True:
        wins = query("--windows") or []
        match = [w for w in wins if w.get("pid") == play_pid()
                 or ("Mesen" in w.get("app", "") and f"[{INSTANCE}]" in w.get("title", ""))]
        if match or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    if not match:
        return
    space = (query("--spaces", "--space") or {}).get("index")
    wid = str(match[0]["id"])
    if space and match[0].get("space") != space:
        subprocess.run([yabai, "-m", "window", wid, "--space", str(space)], capture_output=True)
    display = query("--displays", "--display") or {}
    frame = (query("--windows", "--window", wid) or match[0]).get("frame", {})
    target = natural_frame(display.get("frame", {}))
    if target and (place or needs_placing(frame, display.get("frame", {}))):
        x, y, w, h = target
        subprocess.run([yabai, "-m", "window", wid, "--resize", f"abs:{w}:{h}"], capture_output=True)
        subprocess.run([yabai, "-m", "window", wid, "--move", f"abs:{x}:{y}"], capture_output=True)
    subprocess.run([yabai, "-m", "window", "--focus", wid], capture_output=True)


# SNES picture 256x224; Mesen adds its menu bar + offer-banner area (77 px,
# measured: scawful's Option+4 window was 512x525 = 2x picture + 77).
SNES_W, SNES_H, MESEN_CHROME_H = 256, 224, 77
MENU_BAR_H = 38


def natural_frame(disp: dict) -> tuple[int, int, int, int] | None:
    """Largest integer scale whose window uses <= 60% of the usable height and
    width; centered horizontally, a third of the spare height above it (a bit
    above center). 1512x982: 2x = 512x525 (scawful's pick, 2026-09-26)."""
    if not disp:
        return None
    dw, dh, dx, dy = disp["w"], disp["h"], disp["x"], disp["y"]
    scale = 1
    for s in range(1, 9):
        if SNES_H * s + MESEN_CHROME_H <= (dh - MENU_BAR_H) * 0.6 and SNES_W * s <= dw * 0.6:
            scale = s
    w, h = SNES_W * scale, SNES_H * scale + MESEN_CHROME_H
    x = dx + (dw - w) // 2
    y = dy + MENU_BAR_H + max(0, (dh - MENU_BAR_H - h) // 3)
    return int(x), int(y), int(w), int(h)


def needs_placing(frame: dict, disp: dict) -> bool:
    """Oversized (taller than 90% of the display) or mostly off-screen."""
    if not frame or not disp:
        return False
    too_big = frame["h"] > disp["h"] * 0.9 or frame["w"] > disp["w"] * 0.9
    cx, cy = frame["x"] + frame["w"] / 2, frame["y"] + frame["h"] / 2
    off = not (disp["x"] <= cx <= disp["x"] + disp["w"] and disp["y"] <= cy <= disp["y"] + disp["h"])
    return too_big or off


def status_json() -> int:
    """One JSON object for barista (fast: socket checks plus one rom-info)."""
    latest = PLAYTEST / "latest.json"
    latest_info = json.loads(latest.read_text()) if latest.is_file() else {}
    latest_label = (f"v{latest_info['version']}-b{latest_info['build']}"
                    if latest_info else None)
    play = {"open": socket_alive(SOCK), "rom": None, "label": None, "current": None}
    if play["open"]:
        info = loaded_rom(SOCK, timeout=3) or {}
        play["rom"] = info.get("filename")
        latest_rom = PLAYTEST / "oos-play.sfc"
        if info.get("sha1") and latest_rom.is_file():
            play["current"] = (str(info["sha1"]).upper()
                               == hashlib.sha1(latest_rom.read_bytes()).hexdigest().upper())
        play["label"] = latest_label if play["current"] else play["rom"]
    others = [Path(p) for p in glob.glob("/tmp/mesen2-*.sock") if Path(p) != SOCK]
    alive = sorted(p.name[7:-5] for p in others if socket_alive(p))
    owner = ((HEAVY_LOCK / "owner").read_text().strip()
             if (HEAVY_LOCK / "owner").is_file() else ("?" if HEAVY_LOCK.exists() else None))
    short = f"b{latest_info['build']}" if latest_info else "-"
    running = "old"
    if not play["open"]:
        head = f"closed, {short} ready"
    elif play["current"]:
        head = f"{short} open"
    else:
        # Name the staged build the window runs, if its SHA-1 matches one.
        running = "old"
        target = str((loaded_rom(SOCK, timeout=3) or {}).get("sha1", "")).upper()
        for staged in sorted(PLAYTEST.glob("oos-v*-b*.sfc")):
            if hashlib.sha1(staged.read_bytes()).hexdigest().upper() == target:
                running = "b" + staged.stem.rsplit("-b", 1)[-1]
        head = f"{running} open, {short} ready"
    line = f"{head} | {len(alive)} agent emu" + (" | lock held" if owner else "")
    # Compact form for the barista popup row (its icon carries the state).
    if not play["open"]:
        state, short_line = "closed", short
    elif play["current"]:
        state, short_line = "current", short
    else:
        state, short_line = "outdated", f"{running}→{short}"
    if alive:
        short_line += f" · {len(alive)}"
    print(json.dumps({"play_window": play, "latest": latest_label, "agent_instances": alive,
                      "heavy_lock": owner, "line": line, "state": state, "short": short_line}))
    return 0


def status() -> int:
    print(f"play window ({INSTANCE}):", end=" ")
    if socket_alive(SOCK):
        info = loaded_rom(SOCK) or {}
        print(f"open, ROM {info.get('filename', '?')} sha1 {str(info.get('sha1', '?'))[:12]}")
    else:
        print("closed" + (" (stale socket)" if SOCK.exists() else ""))
    others = [Path(p) for p in glob.glob("/tmp/mesen2-*.sock") if Path(p) != SOCK]
    print(f"agent instances: {len(others)} socket(s)")
    for sock in sorted(others):
        state = "alive" if socket_alive(sock) else "stale"
        rom = (loaded_rom(sock) or {}).get("filename", "-") if state == "alive" else "-"
        print(f"  {sock.name[7:-5]:<28} {state:<6} {rom}")
    owner = (HEAVY_LOCK / "owner").read_text().strip() if (HEAVY_LOCK / "owner").is_file() else None
    print(f"heavy lock: {'held by ' + owner if HEAVY_LOCK.exists() else 'free'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", type=Path, default=PLAYTEST / "oos-play.sfc")
    parser.add_argument("--now", action="store_true", help="live-load instead of offering")
    parser.add_argument("--notes", default="", help="one line shown in the banner")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--place", action="store_true",
                        help="snap the open window to the default size and position")
    parser.add_argument("--json", action="store_true", help="with --status: one JSON object (barista)")
    parser.add_argument("--offer-only", action="store_true",
                        help="offer if the window is open; never launch it (used by stage_playtest.py)")
    parser.add_argument("--instance", default=INSTANCE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.instance != INSTANCE:
        use_instance(args.instance)
    refresh_recent_games(args.rom if args.rom.is_file() else None)

    if args.status:
        return status_json() if args.json else status()
    if args.place:
        bring_to_current_space(place=True)
        return 0
    rom = args.rom.resolve()
    if not rom.is_file():
        raise SystemExit(f"oos-play: {rom} not found (stage a build first)")
    label = label_for(rom)
    ensure_shared_save()

    if socket_alive(SOCK):
        info = loaded_rom(SOCK) or {}
        target_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest().upper()
        if str(info.get("sha1", "")).upper() == target_sha1:
            print(f"play window already runs {label} ({rom.name})")
            if not args.offer_only:
                bring_to_current_space()
            return 0
        if args.now:
            r = client(SOCK, "load-rom-live", str(rom), "--label", label, timeout=60)
            print(r.stdout.strip() or r.stderr.strip())
            bring_to_current_space()
            return r.returncode
        notes = args.notes or (json.loads((PLAYTEST / "latest.json").read_text()).get("name", "")
                               if (PLAYTEST / "latest.json").is_file() else "")
        r = client(SOCK, "offer-rom", str(rom), "--label", label, "--notes", notes)
        print(r.stdout.strip() or r.stderr.strip())
        print(f"offered {label} to the play window (Load now / Later banner)")
        if not args.offer_only:
            bring_to_current_space()
        return r.returncode

    if args.offer_only:
        print("play window closed; nothing offered (run oos-play to open it)")
        return 0
    if SOCK.exists():
        SOCK.unlink()  # stale: nothing listens on it
    env = dict(os.environ)
    seeded = (PROFILE / "settings.json").is_file()
    cmd = ["bash", str(LAUNCHER), "--instance", INSTANCE, "--rom", str(rom)]
    if seeded:
        cmd.insert(4, "--no-copy-settings")  # keep the play profile as is
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    if r.returncode != 0:
        print(r.stdout[-800:], r.stderr[-800:], sep="\n")
        return r.returncode
    print(f"opened the play window on {label} ({rom.name})")
    bring_to_current_space(wait_s=8.0, place=True)
    if not seeded:
        ensure_shared_save()
        print("first launch: shared save takes effect from the next launch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
