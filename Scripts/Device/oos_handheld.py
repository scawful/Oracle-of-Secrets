#!/usr/bin/env python3
"""Identify a running handheld build, capture bugs, and copy save files.

Never sends game input, pause/resume/reset, ROM loads, or save-state loads.
USB forwarding is pinned to one device; newly allocated forwards are removed.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
import zlib

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "ca.mesen.oos"
EXTERNAL = f"/storage/emulated/0/Android/data/{PACKAGE}/files"
INTERNAL = f"/data/data/{PACKAGE}/files"
PNG = b"\x89PNG\r\n\x1a\n"
NAMED_ROM = re.compile(r"oos-(\d+)-(\d{8})-([a-z0-9]+(?:-[a-z0-9]+)*)-([a-f0-9]{8})$")
LABELS = {
    "part00-weather-2026-09-14": "Outdoor color/rain fix (September 14)",
    "part00-weather-2026-09-14-treefix": "Weather + tree tile fix (September 19)",
    "minecart-junction-2026-09-15": "Minecart junction fix (September 15)",
    "minecarts-2026-09-14": "Earlier minecart fixes (September 14)",
    "room25-2026-09-14": "Water-room fix (September 14)",
}
MAIN_ROM_LABEL = "Main build with tree fix (September 19)"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def execute(argv):
    result = subprocess.run(argv, capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip()
                           or result.stdout.decode(errors="replace").strip()
                           or f"command exited {result.returncode}: {argv[0]}")
    return result.stdout


def select_serial(listing, requested=None):
    rows = [line.split() for line in listing.splitlines()[1:] if line.strip()]
    if requested:
        if any(len(r) >= 2 and r[:2] == [requested, "device"] for r in rows):
            return requested
        raise RuntimeError(f"Selected device {requested} is offline, unauthorized, or missing")
    matches = [r[0] for r in rows if len(r) >= 2 and r[1] == "device" and "model:RG353P" in r]
    if len(matches) != 1:
        raise RuntimeError("Connect one authorized RG353P over USB, or set OOS_DEVICE_SERIAL explicitly")
    return matches[0]


class Device:
    def __init__(self, requested=None):
        self.serial = select_serial(execute(["adb", "devices", "-l"]).decode(), requested)

    def adb(self, *args):
        return execute(["adb", "-s", self.serial, *args])

    def shell(self, *args):
        # adb shell joins its arguments into remote shell code: quote each one.
        return self.adb("shell", shlex.join(args))

    def package_shell(self, *args):
        return self.shell("run-as", PACKAGE, *args)

    def file_shell(self, *args):
        # Android app-private files are mode 0700 and must be read as the app
        # UID. External/SD-card paths remain ordinary adb-shell operations.
        if any(str(arg).startswith((f"/data/data/{PACKAGE}/",
                                    f"/data/user/0/{PACKAGE}/"))
               for arg in args):
            return self.package_shell(*args)
        return self.shell(*args)

    def read(self, path):
        return self.file_shell("cat", path)

    def hash(self, path):
        value = self.file_shell("sha256sum", path).decode().split()[0]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise RuntimeError(f"Invalid checksum for {path}")
        return value.lower()

    def rom_identity(self, path):
        before = self.hash(path)
        # Host tests provide a strict in-memory device without file_shell.
        # Production Device instances use the scoped helper for app-private
        # paths and regular shell access everywhere else.
        file_shell = getattr(self, "file_shell", self.shell)
        sha1 = file_shell("sha1sum", path).decode().split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{40}", sha1) or self.hash(path) != before:
            raise RuntimeError(f"ROM changed while identifying it: {path}")
        return {"sha256": before, "sha1": sha1}


class Session:
    def __init__(self, args):
        self.device = None
        self.forward = None
        self.endpoint = args.endpoint
        if self.endpoint:
            url = urlparse(self.endpoint)
            if url.scheme != "tcp" or not url.hostname or not url.port or url.path:
                raise RuntimeError("Use an explicit tcp://HOST:PORT endpoint from a secure tunnel")
        else:
            self.device = Device(args.serial)
            rows = self.device.adb("forward", "--list").decode().splitlines()
            remote = f"tcp:{args.port}"
            match = next((r.split()[1] for r in rows if len(r.split()) == 3
                          and r.split()[0] == self.device.serial and r.split()[2] == remote
                          and r.split()[1].startswith("tcp:")), None)
            if match is None:
                port = self.device.adb("forward", "tcp:0", remote).decode().strip()
                if not port.isdigit():
                    raise RuntimeError("adb did not return the allocated forwarding port")
                match = self.forward = f"tcp:{port}"
            self.endpoint = f"tcp://127.0.0.1:{match.split(':')[1]}"
        try:
            # Reuse the project protocol client, always with an explicit endpoint.
            sys.path.insert(0, str(ROOT / "Scripts/Mesen2"))
            from mesen2_client_lib.bridge import MesenBridge
            self.bridge = MesenBridge(self.endpoint)
            self.bridge._auto_reconnect = False
        except Exception:
            self.close()
            raise

    def request(self, command):
        result = self.bridge.send_command(command, timeout=3)
        if not result.get("success"):
            raise RuntimeError(result.get("error", f"{command} failed"))
        return result.get("data")

    def close(self):
        if self.forward:
            try:
                self.device.adb("forward", "--remove", self.forward)
            except Exception as exc:
                print(f"warning: could not remove owned forward {self.forward}: {exc}", file=sys.stderr)


def catalog(root=ROOT):
    result = []
    # Today's editable/play target lives outside TestBuilds.
    main = root / "Roms/oos168x.sfc"
    if main.exists():
        data = main.read_bytes()
        result.append({"label": MAIN_ROM_LABEL, "id": "main",
                       "path": str(main), "sha1": hashlib.sha1(data).hexdigest(),
                       "sha256": sha256(data)})
    for rom in sorted((root / "Roms/TestBuilds").glob("*/oos168x.sfc")):
        data = rom.read_bytes()
        result.append({"label": LABELS.get(rom.parent.name, rom.parent.name),
                       "path": str(rom), "sha1": hashlib.sha1(data).hexdigest(),
                       "sha256": sha256(data)})
    for manifest in sorted((root / "Roms/HandheldBuilds").glob("*/build.json")):
        try:
            record = json.loads(manifest.read_text())
            name = record["rom_file"]
            if Path(name).name != name:
                continue
            rom = manifest.parent / name
            data = rom.read_bytes()
            if sha256(data) != record["sha256"]:
                continue
            result.insert(0, {"label": record["name"].replace("-", " "), "id": record["id"],
                              "path": str(rom), "sha1": hashlib.sha1(data).hexdigest(),
                              "sha256": sha256(data)})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def identify(rom, builds):
    signature = str(rom.get("sha1", "")).lower()
    return next((r for r in builds if r["sha1"] == signature), None)


def attempt(output, key, function):
    try:
        output[key] = function()
    except Exception as exc:
        output.setdefault("errors", {})[key] = str(exc)


def snapshot(session):
    result = {"observed_at": now(), "endpoint": session.endpoint,
              "transport": "USB" if session.device else "explicit TCP", "errors": {}}
    builds = catalog()
    attempt(result, "rom", lambda: session.request("ROMINFO"))
    attempt(result, "run_state", lambda: session.request("STATE"))
    result["build"] = identify(result.get("rom") or {}, builds)
    result["loaded_sha256"] = (result["build"] or {}).get("sha256")
    local = ROOT / "Roms/oos168x.sfc"
    if local.exists():
        data = local.read_bytes()
        result["local_build"] = identify({"sha1": hashlib.sha1(data).hexdigest()}, builds)
        result["local_sha256"] = sha256(data)
    if session.device:
        device = session.device
        result["serial"] = device.serial
        attempt(result, "model", lambda: device.shell("getprop", "ro.product.model").decode().strip())
        result["copies"] = []
        name = PurePosixPath(str((result.get("rom") or {}).get("filename", "oos168x.sfc"))).name
        for folder in (os.getenv("OOS_DEVICE_SNES_DIR", "/storage/0000-0000/snes"),
                       os.getenv("OOS_DEVICE_DROP_DIR", "/storage/emulated/0/OracleOfSecrets"),
                       EXTERNAL, INTERNAL):
            row = {"path": f"{folder}/{name}"}
            attempt(row, "identity", lambda: device.rom_identity(row["path"]))
            actual = row.get("identity") or {}
            row["known_build"] = identify(actual, builds)
            loaded_sha1 = str((result.get("rom") or {}).get("sha1", "")).lower()
            row["matches_loaded_build"] = actual.get("sha1") == loaded_sha1 if loaded_sha1 and actual else None
            if row["matches_loaded_build"]:
                result["loaded_sha256"] = actual["sha256"]
            result["copies"].append(row)
        attempt(result, "workshop_snapshot",
                lambda: json.loads(device.read(f"{INTERNAL}/workshop.json")))
        result["workshop_snapshot_is_live"] = False
    result["status"] = "ok" if result.get("rom") and result.get("run_state") else "partial"
    return result


def status_text(result):
    fallback = f"Unrecognized build: {(result.get('rom') or {}).get('filename', 'unavailable')}"
    label = (result.get("build") or {}).get("label", fallback)
    state = result.get("run_state") or {}
    lines = [f"Handheld: {result.get('model', 'Mesen')} ({result['transport']})",
             f"Running build: {label}",
             f"Game: {'paused' if state.get('paused') else 'running' if state else 'unavailable'}; frame {state.get('frame', '?')}",
             f"Loaded SHA1: {(result.get('rom') or {}).get('sha1', 'unavailable')}"]
    if state.get("debugging") is True:
        lines.append("Warning: debugger is attached (use STOP_DEBUGGER); FPS will be low until detached")
    copies = result.get("copies", [])
    if copies and result.get("rom"):
        matches = sum(r["matches_loaded_build"] is True for r in copies)
        lines.append(f"ROM copies: {matches}/{len(copies)} match the running build")
        for row in copies:
            if row["matches_loaded_build"] is not True:
                lines.append(f"  Check {row['path']}: {row.get('errors') or 'different or unrecognized build'}")
    elif copies:
        labels = sorted({r["known_build"]["label"] for r in copies if r.get("known_build")})
        lines.append("Stored ROM files: " + (", ".join(labels) if labels else "unrecognized or unavailable"))
        lines.append("Mesen is not responding. Open it on the handheld before checking the running build.")
    local = result.get("local_build") or {}
    if local:
        same = local.get("sha256") == (result.get("build") or {}).get("sha256")
        lines.append(f"Mac build: {local['label']} ({'same' if same else 'different from handheld'})")
    lines.extend(f"Unavailable: {key}: {value}" for key, value in result.get("errors", {}).items())
    lines.append("No game controls, ROM loads, or resets were sent.")
    return "\n".join(lines)


def new_bundle(parent, kind):
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.mkdtemp(prefix=f"{kind}-{stamp}-", dir=parent))


def emulator_fingerprint(device):
    """Identify the installed app now, not the app that created an old state."""
    paths = device.shell("pm", "path", PACKAGE).decode().splitlines()
    apks = [line.removeprefix("package:") for line in paths if line.startswith("package:")]
    if not apks:
        raise RuntimeError("Mesen APK path unavailable")
    return {"package": PACKAGE, "apks": [{"path": path, "sha256": device.hash(path)} for path in apks],
            "scope": "installed at collection time; does not establish save-state origin"}


def capture(session, args):
    folder = new_bundle(args.out or ROOT / "Roms/device-captures", "bug")
    result = snapshot(session)
    result.update(note=args.note, folder=str(folder), kind="bug-capture",
                  state_file="not created; this capture does not save or load emulator states")
    if session.device:
        attempt(result, "emulator_at_capture", lambda: emulator_fingerprint(session.device))
    screenshot = None
    try:
        encoded = session.request("SCREENSHOT")
        screenshot = base64.b64decode(encoded.strip('"'), validate=True)
        if not screenshot.startswith(PNG):
            raise RuntimeError("Socket screenshot is not a PNG")
        result["screenshot_source"] = "Mesen framebuffer"
    except Exception as exc:
        screenshot = None
        result["socket_screenshot_error"] = str(exc)
        if session.device:
            try:
                screenshot = session.device.adb("exec-out", "screencap", "-p")
                if not screenshot.startswith(PNG):
                    raise RuntimeError("Android screenshot is not a PNG")
                result["screenshot_source"] = "Android display (may include Workshop overlay)"
            except Exception as fallback:
                screenshot = None
                result["errors"]["screenshot"] = str(fallback)
        else:
            result["errors"]["screenshot"] = str(exc)
    if screenshot:
        (folder / "screenshot.png").write_bytes(screenshot)
        result["screenshot"] = {"file": "screenshot.png", "sha256": sha256(screenshot)}
    if session.device:
        try:
            display = session.device.adb("exec-out", "screencap", "-p")
            if not display.startswith(PNG):
                raise RuntimeError("Android display capture is not a PNG")
            (folder / "display.png").write_bytes(display)
            result["display"] = {"file": "display.png", "sha256": sha256(display)}
        except Exception as exc:
            result["errors"]["android_display"] = str(exc)
    attempt(result, "game_state", lambda: session.request("GAMESTATE"))
    attempt(result, "run_state_after", lambda: session.request("STATE"))
    attempt(result, "rom_after", lambda: session.request("ROMINFO"))
    before_sha1 = str((result.get("rom") or {}).get("sha1", "")).lower()
    after_sha1 = str((result.get("rom_after") or {}).get("sha1", "")).lower()
    result["same_loaded_rom"] = bool(re.fullmatch(r"[0-9a-f]{40}", before_sha1) and
                                     before_sha1 == after_sha1)
    result["snapshot_atomic"] = False
    result["status"] = "complete" if screenshot and result.get("run_state") and result["same_loaded_rom"] else "partial"
    result["capture_limits"] = "No pause was requested; frames can advance between reads. Workshop data is a cached hint."
    (folder / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    note = args.note or "Describe what happened and what you expected here."
    text = f"# Handheld bug capture\n\n{note}\n\n```text\n{status_text(result)}\n```\n\n"
    text += f"Capture: {result['status']}. {result['capture_limits']}\n\n"
    if screenshot:
        text += "![Captured screen](screenshot.png)\n\n"
    if result.get("display"):
        text += "![Android display including controls](display.png)\n\n"
    text += "Exact identity, read errors, and before/after frame observations are in `report.json`. No emulator state was created.\n"
    (folder / "README.md").write_text(text)
    return result


def save_name(name, stem=None):
    if not name.endswith((".srm", ".sav", ".mss", ".mss.label", ".frz", ".rtc", ".cht", ".config")):
        return False
    if stem:
        return name.startswith(stem + ".") or name.startswith(stem + "_")
    basename = name.split(".", 1)[0].split("_", 1)[0]
    return bool(re.fullmatch(r"oos\d+x", basename) or NAMED_ROM.fullmatch(basename))


def backup(args):
    if args.endpoint:
        raise RuntimeError("Save-file backup requires USB/adb access; omit --endpoint")
    device = Device(args.serial)
    profile = getattr(args, "profile", "handheld")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", profile):
        raise RuntimeError("--profile must use lowercase letters, digits, and single hyphens")
    folder = new_bundle(args.out or ROOT / "Roms/device-saves", f"backup-{profile}")
    result = {"status": "complete", "observed_at": now(), "serial": device.serial,
              "folder": str(folder), "profile": profile, "roots": [], "files": [],
              "limits": "Existing disk files only. No in-game save or emulator state was forced; unsaved progress is not included. Save-state ROM compatibility is unknown."}
    attempt(result, "emulator_at_backup", lambda: emulator_fingerprint(device))
    snes = os.getenv("OOS_DEVICE_SNES_DIR", "/storage/0000-0000/snes")
    drop = os.getenv("OOS_DEVICE_DROP_DIR", "/storage/emulated/0/OracleOfSecrets")
    roots = [("mesen-saves", f"{INTERNAL}/Saves", True),
             ("mesen-states", f"{INTERNAL}/SaveStates", True),
             ("mesen-external-saves", f"{EXTERNAL}/Saves", False),
             ("mesen-external-states", f"{EXTERNAL}/SaveStates", False),
             ("snes", snes, True), ("drop", drop, False),
             ("mesen-staged", EXTERNAL, True), ("mesen-internal", INTERNAL, True)]
    for label, remote, required in roots:
        inventory = {"path": remote, "label": label, "required": required}
        result["roots"].append(inventory)
        try:
            file_shell = getattr(device, "file_shell", device.shell)
            file_shell("ls", "-ld", remote)
            entries = file_shell("find", remote, "-maxdepth", "1", "-type", "f", "-print0")
            names = [p.decode() for p in entries.split(b"\0") if p]
            chosen = [p for p in names if save_name(PurePosixPath(p).name, args.stem)
                      or (PurePosixPath(p).suffix == ".sfc" and
                          ((args.stem and PurePosixPath(p).stem == args.stem) or
                           (not args.stem and (re.fullmatch(r"oos\d+x", PurePosixPath(p).stem) or
                                               NAMED_ROM.fullmatch(PurePosixPath(p).stem)))))]
            inventory.update(status="read", selected_files=len(chosen))
            for path in chosen:
                name = PurePosixPath(path).name
                if str(PurePosixPath(path).parent) != remote or not name:
                    raise RuntimeError("Unexpected path returned by directory listing")
                before = device.hash(path)
                data = device.read(path)
                after = device.hash(path)
                if sha256(data) != before or before != after:
                    raise RuntimeError(f"File changed during backup: {path}; save again and retry")
                target = folder / label / name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(data)
                result["files"].append({"source": path, "file": str(target.relative_to(folder)),
                                        "sha256": before, "size": len(data),
                                        "kind": "rom" if name.endswith(".sfc") else
                                                "save_ram" if name.endswith((".srm", ".sav")) else
                                                "save_state" if name.endswith((".mss", ".frz")) else "sidecar",
                                        "origin_rom_sha256": None if not name.endswith(".sfc") else before,
                                        "origin_emulator": None})
        except Exception as exc:
            inventory.update(status="unavailable", error=str(exc))
            if required or "No such file" not in str(exc):
                result["status"] = "partial"
    result["save_file_count"] = sum(save_name(PurePosixPath(r["source"]).name, args.stem) for r in result["files"])
    if not result["save_file_count"]:
        result["status"] = "partial"
    (folder / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    (folder / "README.md").write_text(f"# Handheld backup\n\nStatus: {result['status']}. Copied {result['save_file_count']} save/sidecar files plus listed ROMs.\n\n{result['limits']}\n\nSee `manifest.json` for exact source paths, hashes, and missing/inaccessible roots.\n")
    return result


def prepare(args):
    source = (args.rom or ROOT / "Roms/oos168x.sfc").resolve()
    match = re.fullmatch(r"oos(\d+)x\.sfc", source.name)
    if not match:
        raise RuntimeError("Prepare from an original patched oos<VERSION>x.sfc; base ROMs are refused")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.name):
        raise RuntimeError("--name must use lowercase letters, digits, and single hyphens")
    data = source.read_bytes()
    digest = sha256(data)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    build_id = f"oos-{match[1]}-{date}-{args.name}-{digest[:8]}"
    parent = args.out or ROOT / "Roms/HandheldBuilds"
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent / build_id
    folder.mkdir(exist_ok=False)
    name = build_id + ".sfc"
    (folder / name).write_bytes(data)
    record = {"schema": "oos-handheld-build-v1", "id": build_id, "name": args.name,
              "prepared_at": now(), "base_version": int(match[1]), "rom_file": name,
              "source": str(source), "sha256": digest, "sha1": hashlib.sha1(data).hexdigest(),
              "crc32": f"{zlib.crc32(data):08X}", "deployed": False,
              "verification": "packaged bytes only; consult the source package's verification report",
              "sram_policy": "explicit profile copy after compatibility check; never automatic",
              "state_policy": "requires exact ROM SHA256 and emulator build; keep human and synthetic checkpoints separate"}
    source_manifest = source.parent / "manifest.json"
    if source_manifest.exists():
        record["source_manifest"] = str(source_manifest)
        record["source_manifest_sha256"] = sha256(source_manifest.read_bytes())
    (folder / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    (folder / "README.md").write_text(f"# {args.name.replace('-', ' ')}\n\nBuild: `{build_id}`\n\nROM bytes match `{source}`. No saves are copied or renamed.\n\nSave RAM transfer is explicit; emulator states require the exact ROM and emulator build. Existing legacy saves stay in place.\n")
    return {"status": "complete", "folder": str(folder), "build": record,
            "deploy_command": shlex.join([str(ROOT / "Scripts/Device/oos_rg353p.sh"),
                                           "push", "--rom", str(folder / name), "--mesen"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "capture", "backup"):
        sub = commands.add_parser(name)
        sub.add_argument("--serial", default=os.getenv("OOS_DEVICE_SERIAL"))
        sub.add_argument("--endpoint", help="Explicit tcp://HOST:PORT from an existing secure tunnel")
        sub.add_argument("--port", type=int, default=27015, help="Device TCP port for USB forwarding")
        sub.add_argument("--json", action="store_true")
        if name != "status":
            sub.add_argument("--out", type=Path, help="Parent directory; each run creates a unique child")
        if name == "capture":
            sub.add_argument("--note", default="")
        if name == "status":
            sub.add_argument("--expect-sha256", help="Fail unless the loaded ROM matches this full hash")
        if name == "backup":
            sub.add_argument("--stem", help="Optional exact ROM stem; defaults to all legacy/named Oracle saves")
            sub.add_argument("--profile", default="handheld", help="Label this collection of save files")
    sub = commands.add_parser("prepare", help="Make an immutable named ROM package locally; no device access")
    sub.add_argument("--rom", type=Path)
    sub.add_argument("--name", required=True)
    sub.add_argument("--out", type=Path)
    sub.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if hasattr(args, "port") and not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    session = None
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "backup":
            result = backup(args)
        else:
            session = Session(args)
            result = snapshot(session) if args.command == "status" else capture(session, args)
            if args.command == "status" and args.expect_sha256:
                if not re.fullmatch(r"[0-9a-fA-F]{64}", args.expect_sha256):
                    raise RuntimeError("--expect-sha256 requires a full SHA256 digest")
                expected = args.expect_sha256.lower()
                deadline = time.monotonic() + 8
                while result.get("loaded_sha256") != expected and time.monotonic() < deadline:
                    time.sleep(0.4)
                    result = snapshot(session)
                result["expected_sha256"] = expected
                result["loaded_expected_build"] = result.get("loaded_sha256") == expected
                if not result["loaded_expected_build"]:
                    result["status"] = "partial"
                    result["errors"]["expected_build"] = "Loaded build does not match the requested SHA256"
        if args.json:
            print(json.dumps(result, indent=2))
        elif args.command == "status":
            print(status_text(result))
        elif args.command == "prepare":
            print(f"Prepared: {result['build']['id']}\nSaved: {result['folder']}\nNot deployed. To install this build:\n{result['deploy_command']}")
        else:
            print(f"{args.command.capitalize()}: {result['status']}\nSaved: {result['folder']}")
            if args.command == "backup":
                print(f"Save/sidecar files: {result['save_file_count']}\n{result['limits']}")
            else:
                print("Screenshot: " + ("saved" if result.get("screenshot") else "unavailable; see report.json"))
        return 0 if result["status"] in ("ok", "complete") else 2
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "unavailable", "error": str(exc)}))
        else:
            print(f"Handheld unavailable: {exc}", file=sys.stderr)
        return 2
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
