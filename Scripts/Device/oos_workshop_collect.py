#!/usr/bin/env python3
"""Copy Workshop checkpoints and bug reports from the handheld without controls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from oos_handheld import Device, INTERNAL, PACKAGE, ROOT, now, sha256

REMOTE = INTERNAL + "/Workshop"
ARTIFACT_SCHEMA = "oos-workshop-artifact-v1"
VOICE_SCHEMA = "oos-workshop-voice-v1"
MAX_FILE_SIZE = 32 * 1024 * 1024
GROUPS = ("checkpoints", "issues", "voice-notes")


class AppFilesDevice:
    """Read app-private Workshop files through Android's debug run-as scope."""

    def __init__(self, device):
        self._device = device
        self.serial = device.serial

    def shell(self, *args):
        return self._device.shell("run-as", PACKAGE, *args)

    def read(self, path):
        return self.shell("cat", path)

    def hash(self, path):
        value = self.shell("sha256sum", path).decode().split()[0]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise RuntimeError(f"Invalid checksum for {path}")
        return value.lower()


def leaf(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}", value):
        raise ValueError("Invalid Workshop file or item name")
    return value


def verified_read(device, path, expected=None, size=None, canonical_root=REMOTE):
    # Manifests and filenames are device data, not trusted local paths.
    canonical = device.shell("readlink", "-f", path).decode().strip()
    relative = PurePosixPath(path).relative_to(REMOTE)
    if canonical != str(PurePosixPath(canonical_root) / relative):
        raise ValueError("Workshop file is a symlink or has an unexpected path: " + path)
    actual_size = int(device.shell("stat", "-c", "%s", path).decode().strip())
    if not 0 <= actual_size <= MAX_FILE_SIZE or (size is not None and actual_size != size):
        raise ValueError("Workshop file size mismatch or too large: " + path)
    before = device.hash(path)
    data = device.read(path)
    after = device.hash(path)
    if len(data) != actual_size or sha256(data) != before or before != after:
        raise ValueError("Workshop file changed while collecting: " + path)
    if expected is not None and before != expected:
        raise ValueError("Workshop file checksum mismatch: " + path)
    return data


def collect(device, parent):
    # Host tests use an in-memory device adapter. Real devices must enter the
    # app's UID before reading files/Workshop (mode 0700 on Android).
    if isinstance(device, Device):
        device = AppFilesDevice(device)
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="workshop-", dir=parent))
    result = {"schema": "oos-workshop-collection-v1", "collected_at": now(),
              "serial": device.serial, "folder": str(folder.resolve()),
              "status": "complete", "items": [], "errors": [],
              "policy": "Device files copied only; no controls, restore, migration, or deletion."}
    try:
        canonical_root = device.shell("readlink", "-f", REMOTE).decode().strip()
        def read(path, expected=None, size=None):
            return verified_read(device, path, expected, size, canonical_root)
        listing = device.shell("find", REMOTE, "-mindepth", "2", "-maxdepth", "2", "-type", "d")
        for path in sorted(set(listing.decode().splitlines())):
            item = {"source": path, "status": "unavailable"}
            result["items"].append(item)
            try:
                rel = PurePosixPath(path).relative_to(REMOTE)
                if len(rel.parts) != 2 or rel.parts[0] not in GROUPS:
                    raise ValueError("Unexpected Workshop item directory")
                group, identifier = rel.parts
                leaf(identifier)
                raw = read(path + "/manifest.json")
                manifest = json.loads(raw)
                if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
                    raise ValueError("Workshop manifest must contain a file list")
                if group == "voice-notes":
                    kind = "voice"
                    expected_schema = VOICE_SCHEMA
                else:
                    kind = "checkpoint" if group == "checkpoints" else "issue"
                    expected_schema = ARTIFACT_SCHEMA
                if (manifest.get("schema") != expected_schema or manifest.get("id") != identifier
                        or manifest.get("kind") != kind):
                    raise ValueError("Workshop manifest identity does not match its directory")
                target = folder / group / identifier
                target.mkdir(parents=True, exist_ok=False)
                (target / "manifest.json").write_bytes(raw)
                item.update(id=identifier, kind=kind, folder=str(target.relative_to(folder)),
                            device_status=manifest.get("status"),
                            title=manifest.get("title") if isinstance(manifest.get("title"), str) else None,
                            note=manifest.get("note") if isinstance(manifest.get("note"), str) else None,
                            frame=manifest.get("frame") if isinstance(manifest.get("frame"), int) else None,
                            sha1=manifest.get("sha1") if isinstance(manifest.get("sha1"), str) else None,
                            duration_ms=manifest.get("duration_ms")
                            if isinstance(manifest.get("duration_ms"), int) else None,
                            game_state=manifest.get("game_state")
                            if isinstance(manifest.get("game_state"), dict) else None,
                            sprites=manifest.get("sprites")
                            if isinstance(manifest.get("sprites"), dict) else None,
                            warnings=manifest.get("warnings")
                            if isinstance(manifest.get("warnings"), list) else [],
                            files=[])
                names = set()
                folded_names = {"manifest.json"}
                for entry in manifest.get("files", []):
                    try:
                        name = leaf(entry["name"])
                        if name.casefold() in folded_names:
                            raise ValueError("Duplicate or reserved filename in Workshop manifest")
                        folded_names.add(name.casefold())
                        digest = entry["sha256"]
                        size = entry["size"]
                        if (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                                or type(size) is not int or not 0 < size <= MAX_FILE_SIZE):
                            raise ValueError("Invalid Workshop file identity")
                        data = read(path + "/" + name, digest, size)
                        with (target / name).open("xb") as output:
                            output.write(data)
                        names.add(name)
                        item["files"].append({"name": name, "size": size, "sha256": digest})
                    except (OSError, RuntimeError, ValueError, KeyError, TypeError,
                            subprocess.TimeoutExpired) as exc:
                        item.setdefault("file_errors", []).append(str(exc))
                if read(path + "/manifest.json") != raw:
                    raise ValueError("Workshop manifest changed while collecting")
                if item.get("file_errors"):
                    raise ValueError("; ".join(item["file_errors"]))
                if manifest.get("status") != "complete":
                    raise ValueError("Device artifact is incomplete; available evidence was retained")
                if kind == "voice":
                    if "note.m4a" not in names:
                        raise ValueError("Completed voice note has no audio")
                else:
                    if not any(n.endswith(".png") for n in names):
                        raise ValueError("Completed artifact has no game screenshot")
                    if not any(n.endswith(".mss") for n in names):
                        raise ValueError("Completed artifact has no emulator state")
                item["status"] = "complete"
            except (OSError, RuntimeError, ValueError, KeyError, TypeError,
                    subprocess.TimeoutExpired) as exc:
                item["error"] = str(exc)
                result["status"] = "partial"
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        result["status"] = "partial"
        result["errors"].append(str(exc))
    result["complete_count"] = sum(i["status"] == "complete" for i in result["items"])
    (folder / "collection.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=os.getenv("OOS_DEVICE_SERIAL"))
    parser.add_argument("--out", type=Path, default=ROOT / "Roms/device-workshop",
                        help="Parent folder; each collection creates a unique child")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = collect(Device(args.serial), args.out)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Workshop: {result['complete_count']} complete items copied; {result['status']}.")
            print("Saved to: " + result["folder"])
            if result["status"] != "complete":
                print("Some items were unavailable or incomplete; see collection.json.")
            print("Device files and current game were left in place.")
        return 0 if result["status"] == "complete" else 2
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "unavailable", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
