#!/usr/bin/env python3
"""Host-only handheld regression tests; no real adb or socket can be opened."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib


SOURCE = Path(__file__).resolve().parents[1] / "oos_handheld.py"
SPEC = importlib.util.spec_from_file_location("oos_handheld_test_subject", SOURCE)
handheld = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handheld)
REAL_CATALOG = handheld.catalog
REAL_DEVICE = handheld.Device

AUTHORIZED = "List of devices attached\nrg-one\tdevice product:rk model:RG353P transport_id:1\n"
PNG = handheld.PNG + b"test-framebuffer"
SD = "/storage/test-sd/snes"
DROP = "/storage/emulated/0/OracleOfSecrets"
APK = "/data/app/ca.mesen.oos/base.apk"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class FakeDevice:
    """An in-memory disk and strict allowlist of read-only device operations."""

    serial = "rg-one"

    def __init__(self, files=None, missing=None, changing=None, corrupt_reads=None):
        self.files = dict(files or {})
        self.files.setdefault(APK, b"installed emulator at collection time")
        self.missing = set(missing or ())
        self.changing = set(changing or ())
        self.corrupt_reads = set(corrupt_reads or ())
        self.calls = []
        self.hash_reads = {}
        self.forward_listing = b""
        self.android_screenshot = PNG

    def shell(self, *args):
        self.calls.append(("shell", *args))
        if args == ("getprop", "ro.product.model"):
            return b"RG353P\n"
        if args == ("pm", "path", handheld.PACKAGE):
            return ("package:" + APK + "\n").encode()
        if args[:1] == ("sha1sum",):
            if args[1] not in self.files:
                raise RuntimeError("No such file: " + args[1])
            return (hashlib.sha1(self.files[args[1]]).hexdigest() + "  " + args[1] + "\n").encode()
        if args[:2] == ("ls", "-ld"):
            if args[2] in self.missing:
                raise RuntimeError("No such file or directory: " + args[2])
            return b"directory exists\n"
        if args[:1] == ("find",) and args[2:] == ("-maxdepth", "1", "-type", "f", "-print0"):
            root = args[1]
            return b"".join(p.encode() + b"\0" for p in sorted(self.files)
                            if str(PurePosixPath(p).parent) == root)
        raise AssertionError("Unexpected device shell operation: " + repr(args))

    def read(self, path):
        self.calls.append(("read", path))
        if path not in self.files:
            raise RuntimeError("No such file: " + path)
        return self.files[path] + (b"changed during read" if path in self.corrupt_reads else b"")

    def hash(self, path):
        self.calls.append(("hash", path))
        if path not in self.files:
            raise RuntimeError("No such file: " + path)
        self.hash_reads[path] = self.hash_reads.get(path, 0) + 1
        data = self.files[path]
        if path in self.changing and self.hash_reads[path] > 1:
            data += b"changed after read"
        return digest(data)

    def rom_identity(self, path):
        return REAL_DEVICE.rom_identity(self, path)

    def adb(self, *args):
        self.calls.append(("adb", *args))
        if args == ("exec-out", "screencap", "-p"):
            if isinstance(self.android_screenshot, Exception):
                raise self.android_screenshot
            return self.android_screenshot
        if args == ("forward", "--list"):
            return self.forward_listing
        if args == ("forward", "tcp:0", "tcp:27015"):
            return b"41001\n"
        if args == ("forward", "--remove", "tcp:41001"):
            return b""
        raise AssertionError("Unexpected adb operation: " + repr(args))


class FakeSession:
    """Every command is recorded, including unexpected commands caught by caller."""

    endpoint = "tcp://127.0.0.1:41001"

    def __init__(self, rom, device=None, screenshot=None):
        self.device = device
        self.commands = []
        self.rom = rom
        self.screenshot = base64.b64encode(PNG).decode() if screenshot is None else screenshot

    def request(self, command):
        self.commands.append(command)
        if command == "ROMINFO":
            return self.rom
        if command == "STATE":
            return {"paused": False, "frame": 100 + len(self.commands)}
        if command == "GAMESTATE":
            return {"room": "0x87", "mode": 7}
        if command == "SCREENSHOT":
            if isinstance(self.screenshot, Exception):
                raise self.screenshot
            return self.screenshot
        raise AssertionError("Unexpected emulator command: " + command)


class HandheldTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="oos-handheld-unit-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "Roms").mkdir()
        self.args = argparse.Namespace(out=self.root / "output", note="Wrong background",
                                       endpoint=None, serial=None, port=27015, stem="oos168x")
        self.start_patch(patch.object(handheld, "ROOT", self.root))
        self.start_patch(patch.object(handheld, "execute", side_effect=AssertionError("Real adb forbidden")))
        self.start_patch(patch.object(subprocess, "run", side_effect=AssertionError("Real subprocess forbidden")))
        self.start_patch(patch.object(socket, "socket", side_effect=AssertionError("Real socket forbidden")))
        self.start_patch(patch.dict(os.environ, {"OOS_DEVICE_SNES_DIR": SD, "OOS_DEVICE_DROP_DIR": DROP}))
        data = b"known test ROM, not a real ROM"
        self.build = {"label": "Known test build", "path": "/test/oos168x.sfc",
                      "sha1": hashlib.sha1(data).hexdigest(), "sha256": digest(data)}
        self.start_patch(patch.object(handheld, "catalog", return_value=[self.build]))

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def session(self, **kwargs):
        return FakeSession({"sha1": self.build["sha1"], "filename": "oos168x.sfc"}, **kwargs)

    def assert_read_only(self, session):
        self.assertLessEqual(set(session.commands), {"ROMINFO", "STATE", "GAMESTATE", "SCREENSHOT"})
        self.assertFalse(set(session.commands) & {"PAUSE", "RESUME", "RESET", "LOAD", "LOADSTATE", "SAVESTATE"})
        if session.device:
            self.assert_device_reads_only(session.device)

    def assert_device_reads_only(self, device):
        for call in device.calls:
            with self.subTest(call=call):
                if call[0] == "shell":
                    self.assertIn(call[1], {"getprop", "ls", "find", "pm", "sha1sum"})
                elif call[0] == "adb":
                    self.assertTrue(call[1] == "forward" or call[1:] == ("exec-out", "screencap", "-p"))
                else:
                    self.assertIn(call[0], {"hash", "read"})

    def backup(self, device):
        with patch.object(handheld, "Device", return_value=device), patch.object(handheld, "Session") as session:
            result = handheld.backup(self.args)
        session.assert_not_called()
        self.assert_device_reads_only(device)
        return result

    def test_auto_selects_only_one_authorized_rg353p(self):
        listing = AUTHORIZED + "phone\tdevice model:Pixel_9\nother\tunauthorized model:RG353P\n"
        self.assertEqual(handheld.select_serial(listing), "rg-one")

    def test_auto_rejects_non_rg_ambiguous_and_unauthorized_devices(self):
        listings = ["List of devices attached\nphone\tdevice model:Pixel_9\n",
                    AUTHORIZED + "rg-two\tdevice model:RG353P\n",
                    "List of devices attached\nrg-one\tunauthorized model:RG353P\n",
                    "List of devices attached\nrg-one\toffline model:RG353P\n"]
        for listing in listings:
            with self.subTest(listing=listing), self.assertRaises(RuntimeError):
                handheld.select_serial(listing)

    def test_explicit_authorized_serial_is_an_intentional_override(self):
        listing = AUTHORIZED + "phone\tdevice model:Pixel_9\n"
        self.assertEqual(handheld.select_serial(listing, "phone"), "phone")
        for serial in ("missing", "rg-offline"):
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                handheld.select_serial(listing + "rg-offline\toffline model:RG353P\n", serial)

    def test_real_device_scopes_private_files_through_run_as(self):
        device = object.__new__(REAL_DEVICE)
        with patch.object(device, "shell", return_value=b"ok") as shell:
            self.assertEqual(
                device.file_shell("sha256sum",
                                  f"{handheld.INTERNAL}/Saves/oos168x.srm"),
                b"ok")
            shell.assert_called_once_with(
                "run-as", handheld.PACKAGE, "sha256sum",
                f"{handheld.INTERNAL}/Saves/oos168x.srm")

        with patch.object(device, "shell", return_value=b"external") as shell:
            self.assertEqual(
                device.file_shell("sha256sum", f"{SD}/oos168x.srm"),
                b"external")
            shell.assert_called_once_with("sha256sum", f"{SD}/oos168x.srm")

    def test_identity_uses_rom_hash_and_does_not_trust_a_familiar_filename(self):
        known = self.session()
        result = handheld.snapshot(known)
        self.assertEqual(result["build"], self.build)
        self.assertIn("Known test build", handheld.status_text(result))
        unknown = FakeSession({"sha1": "f" * 40, "filename": "oos168x.sfc"})
        result = handheld.snapshot(unknown)
        self.assertIsNone(result["build"])
        self.assertIn("Unrecognized build", handheld.status_text(result))
        self.assertIn("f" * 40, handheld.status_text(result))
        self.assert_read_only(known)
        self.assert_read_only(unknown)

    def test_identity_accepts_uppercase_sha1_but_not_an_empty_identity(self):
        self.assertEqual(handheld.identify({"sha1": self.build["sha1"].upper()}, [self.build]), self.build)
        self.assertIsNone(handheld.identify({}, [self.build]))

    def test_status_distinguishes_loaded_build_from_stale_disk_copies(self):
        device = FakeDevice({f"{SD}/oos168x.sfc": b"stale ROM"})
        session = self.session(device=device)
        result = handheld.snapshot(session)
        self.assertEqual(result["build"], self.build)
        row = next(r for r in result["copies"] if r["path"] == f"{SD}/oos168x.sfc")
        self.assertIs(row["matches_loaded_build"], False)
        self.assertFalse(result["workshop_snapshot_is_live"])
        self.assert_read_only(session)

    def test_status_reads_workshop_snapshot_from_app_private_storage(self):
        workshop = {"rom": "oos168x.sfc", "observedFps": 40.25}
        path = f"{handheld.INTERNAL}/workshop.json"
        device = FakeDevice({path: json.dumps(workshop).encode()})
        session = self.session(device=device)
        result = handheld.snapshot(session)
        self.assertEqual(result["workshop_snapshot"], workshop)
        self.assertIn(("read", path), device.calls)
        self.assertNotIn("workshop_snapshot", result["errors"])
        self.assert_read_only(session)

    def test_failed_capture_creates_unique_partial_report_without_advertising_old_image(self):
        session = self.session(screenshot=RuntimeError("framebuffer unavailable"))
        with patch.object(handheld, "datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
            first = handheld.capture(self.session(), self.args)
            first_folder = Path(first["folder"])
            original_image = (first_folder / "screenshot.png").read_bytes()
            failed = handheld.capture(session, self.args)
        failed_folder = Path(failed["folder"])
        self.assertNotEqual(failed_folder, first_folder)
        self.assertEqual(failed["status"], "partial")
        self.assertNotIn("screenshot", failed)
        self.assertFalse((failed_folder / "screenshot.png").exists())
        self.assertNotIn("![", (failed_folder / "README.md").read_text())
        self.assertEqual(json.loads((failed_folder / "report.json").read_text()), failed)
        self.assertIn("framebuffer unavailable", failed["errors"]["screenshot"])
        self.assertEqual((first_folder / "screenshot.png").read_bytes(), original_image)
        self.assert_read_only(session)

    def test_invalid_socket_and_android_images_do_not_create_a_screenshot(self):
        device = FakeDevice()
        device.android_screenshot = b"not an Android PNG"
        session = self.session(device=device, screenshot=base64.b64encode(b"not a PNG").decode())
        result = handheld.capture(session, self.args)
        self.assertEqual(result["status"], "partial")
        self.assertNotIn("screenshot", result)
        self.assertFalse((Path(result["folder"]) / "screenshot.png").exists())
        self.assertIn("not a PNG", result["errors"]["screenshot"])
        self.assert_read_only(session)

    def test_socket_failure_uses_android_image_with_explicit_source(self):
        device = FakeDevice()
        session = self.session(device=device, screenshot=RuntimeError("socket unavailable"))
        result = handheld.capture(session, self.args)
        self.assertEqual(result["status"], "complete")
        self.assertIn("Android display", result["screenshot_source"])
        self.assertIn("socket unavailable", result["socket_screenshot_error"])
        self.assertEqual(result["screenshot"]["sha256"], digest(PNG))
        self.assertFalse(result["snapshot_atomic"])
        self.assert_read_only(session)

    def test_backup_copies_internal_ram_states_and_checkpoint_labels(self):
        files = {f"{handheld.INTERNAL}/Saves/oos168x.srm": b"internal SRAM",
                 f"{handheld.INTERNAL}/SaveStates/oos168x_1.mss": b"state data",
                 f"{handheld.INTERNAL}/SaveStates/oos168x_1.mss.label": b"Outside Goron Mines",
                 f"{SD}/oos168x.srm": b"SD SRAM",
                 f"{SD}/oos168x.sfc": b"installed ROM",
                 f"{handheld.INTERNAL}/Debugger/oos168x.mlb": b"debug symbols",
                 f"{handheld.INTERNAL}/SaveStates/othergame_1.mss": b"unrelated state"}
        result = self.backup(FakeDevice(files))
        self.assertEqual(result["status"], "complete")
        copied = {r["source"]: r for r in result["files"]}
        wanted = set(files) - {f"{handheld.INTERNAL}/Debugger/oos168x.mlb",
                               f"{handheld.INTERNAL}/SaveStates/othergame_1.mss"}
        self.assertEqual(set(copied), wanted)
        for source, row in copied.items():
            with self.subTest(source=source):
                self.assertEqual((Path(result["folder"]) / row["file"]).read_bytes(), files[source])
                self.assertEqual(row["sha256"], digest(files[source]))
        self.assertIn("unknown", result["limits"].lower())
        self.assertIn("unsaved", result["limits"].lower())
        current_app = result["emulator_at_backup"]
        self.assertEqual(current_app["apks"][0]["sha256"], digest(b"installed emulator at collection time"))
        self.assertIn("does not establish save-state origin", current_app["scope"])

    def test_default_backup_includes_legacy_and_named_builds_but_not_similar_names(self):
        self.args.stem = None
        named = "oos-168-20260915-minecart-junction-992c2441"
        wanted = {f"{SD}/oos168x.srm": b"legacy SRAM",
                  f"{handheld.INTERNAL}/SaveStates/oos167x_2.mss": b"older state",
                  f"{SD}/{named}.sfc": b"named ROM",
                  f"{handheld.INTERNAL}/Saves/{named}.srm": b"named SRAM",
                  f"{handheld.INTERNAL}/SaveStates/{named}_3.mss": b"named state",
                  f"{handheld.INTERNAL}/SaveStates/{named}_3.mss.label": b"human checkpoint label"}
        other = {f"{SD}/oos168.srm": b"base name",
                 f"{SD}/oos168xx.srm": b"near match",
                 f"{SD}/oos-168-minecart-992c2441.srm": b"malformed name",
                 f"{SD}/{named}.srm.tmp": b"temporary file",
                 f"{SD}/other-game.srm": b"unrelated"}
        result = self.backup(FakeDevice({**wanted, **other}))
        self.assertEqual(result["status"], "complete")
        self.assertEqual({r["source"] for r in result["files"]}, set(wanted))
        self.assertEqual(result["save_file_count"], 5)

    def test_explicit_named_stem_excludes_other_named_and_legacy_profiles(self):
        named = "oos-168-20260915-minecart-junction-992c2441"
        self.args.stem = named
        wanted = f"{SD}/{named}.srm"
        files = {wanted: b"selected SRAM", f"{SD}/oos168x.srm": b"legacy SRAM",
                 f"{SD}/oos-168-20260915-weather-0c225e0f.srm": b"other named SRAM"}
        result = self.backup(FakeDevice(files))
        self.assertEqual({r["source"] for r in result["files"]}, {wanted})

    def test_backup_rejects_remote_hash_changes_without_claiming_a_good_copy(self):
        path = f"{handheld.INTERNAL}/Saves/oos168x.srm"
        result = self.backup(FakeDevice({path: b"SRAM"}, changing={path}))
        self.assertEqual(result["status"], "partial")
        self.assertNotIn(path, {r["source"] for r in result["files"]})
        self.assertTrue(any("changed during backup" in r.get("error", "") for r in result["roots"]))
        self.assertFalse(any(Path(result["folder"]).rglob("*.srm")))

    def test_backup_detects_read_corruption_even_when_remote_hashes_agree(self):
        path = f"{handheld.INTERNAL}/Saves/oos168x.srm"
        result = self.backup(FakeDevice({path: b"SRAM"}, corrupt_reads={path}))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["files"], [])

    def test_backup_reports_missing_required_root_despite_other_copied_saves(self):
        missing = f"{handheld.INTERNAL}/SaveStates"
        result = self.backup(FakeDevice({f"{SD}/oos168x.srm": b"available SRAM"}, missing={missing}))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["save_file_count"], 1)
        row = next(r for r in result["roots"] if r["path"] == missing)
        self.assertTrue(row["required"])
        self.assertEqual(row["status"], "unavailable")
        saved = json.loads((Path(result["folder"]) / "manifest.json").read_text())
        self.assertEqual(saved["status"], "partial")

    def test_backup_missing_optional_directory_does_not_hide_valid_saves(self):
        result = self.backup(FakeDevice({f"{SD}/oos168x.srm": b"SRAM"}, missing={DROP}))
        self.assertEqual(result["status"], "complete")
        row = next(r for r in result["roots"] if r["path"] == DROP)
        self.assertFalse(row["required"])
        self.assertEqual(row["status"], "unavailable")

    def test_backup_with_only_roms_is_partial(self):
        result = self.backup(FakeDevice({f"{SD}/oos168x.sfc": b"ROM without save"}))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["save_file_count"], 0)

    def test_backup_explicit_endpoint_fails_before_attempting_usb(self):
        self.args.endpoint = "tcp://192.0.2.1:27015"
        with patch.object(handheld, "Device") as device, self.assertRaisesRegex(RuntimeError, "requires USB"):
            handheld.backup(self.args)
        device.assert_not_called()

    def test_explicit_stem_has_filename_boundaries_and_accepts_checkpoint_labels(self):
        accepted = ["oos168x.srm", "oos168x_1.mss", "oos168x_1.mss.label"]
        rejected = ["oos168x-old.srm", "oos168xx.srm", "other_oos168x.srm",
                    "oos168x.mlb", "oos168x.srm.tmp", "oos168x_1.mss.label.tmp"]
        for name in accepted:
            with self.subTest(name=name):
                self.assertTrue(handheld.save_name(name, "oos168x"))
        for name in rejected:
            with self.subTest(name=name):
                self.assertFalse(handheld.save_name(name, "oos168x"))

    def test_session_only_removes_the_forward_it_allocated(self):
        device = FakeDevice()
        bridge_module = types.ModuleType("mesen2_client_lib.bridge")
        bridges = []

        class Bridge:
            def __init__(self, endpoint):
                self.endpoint = endpoint
                self.commands = []
                bridges.append(self)

            def send_command(self, command, timeout):
                self.commands.append(command)
                return {"success": True, "data": {"paused": False}}

        bridge_module.MesenBridge = Bridge
        for existing in (False, True):
            with self.subTest(existing=existing):
                device.calls.clear()
                device.forward_listing = b"rg-one tcp:42002 tcp:27015\n" if existing else b""
                with patch.object(handheld, "Device", return_value=device), \
                        patch.dict(sys.modules, {"mesen2_client_lib.bridge": bridge_module}), \
                        patch.object(sys, "path", list(sys.path)):
                    session = handheld.Session(self.args)
                    self.assertFalse(session.bridge._auto_reconnect)
                    session.request("STATE")
                    session.close()
                removes = [c for c in device.calls if c[:3] == ("adb", "forward", "--remove")]
                self.assertEqual(removes, [] if existing else [("adb", "forward", "--remove", "tcp:41001")])
                self.assertEqual(bridges[-1].commands, ["STATE"])

    def prepare(self, name="minecart-junction"):
        self.args.rom = self.root / "Roms/oos168x.sfc"
        self.args.name = name
        self.args.out = self.root / "Roms/HandheldBuilds"
        self.args.rom.write_bytes(b"compiled test bytes")
        with patch.object(handheld, "Device") as device, patch.object(handheld, "Session") as session, \
                patch.object(handheld, "datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
            result = handheld.prepare(self.args)
        device.assert_not_called()
        session.assert_not_called()
        return result

    def test_prepare_creates_named_immutable_package_with_exact_identity_and_no_saves(self):
        (self.root / "Roms/oos168x.srm").write_bytes(b"existing player progress")
        result = self.prepare()
        folder = Path(result["folder"])
        record = json.loads((folder / "build.json").read_text())
        data = (folder / record["rom_file"]).read_bytes()
        self.assertEqual(data, b"compiled test bytes")
        self.assertEqual(record["sha256"], digest(data))
        self.assertEqual(record["sha1"], hashlib.sha1(data).hexdigest())
        self.assertEqual(record["crc32"], f"{zlib.crc32(data):08X}")
        self.assertEqual(record["base_version"], 168)
        self.assertEqual(record["id"], "oos-168-20260915-minecart-junction-" + digest(data)[:8])
        self.assertEqual(record["rom_file"], record["id"] + ".sfc")
        self.assertFalse(record["deployed"])
        self.assertEqual({p.name for p in folder.iterdir()}, {record["rom_file"], "build.json", "README.md"})
        self.assertEqual((self.root / "Roms/oos168x.srm").read_bytes(), b"existing player progress")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((folder / record["rom_file"]).read_bytes(), data)

    def test_prepare_refuses_base_roms_and_path_like_names(self):
        self.args.rom = self.root / "Roms/oos168.sfc"
        self.args.rom.write_bytes(b"base ROM")
        self.args.name = "test"
        with self.assertRaisesRegex(RuntimeError, "base ROMs are refused"):
            handheld.prepare(self.args)
        for name in ("../escape", "Bad Name", "two--hyphens", "-leading"):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "--name"):
                self.prepare(name)
        self.assertFalse((self.root / "Roms/HandheldBuilds").exists())

    def test_catalog_rejects_a_prepared_package_after_its_rom_bytes_change(self):
        result = self.prepare()
        records = REAL_CATALOG(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sha256"], result["build"]["sha256"])
        rom = Path(result["folder"]) / result["build"]["rom_file"]
        rom.write_bytes(b"different bytes under the old trusted name")
        self.assertEqual(REAL_CATALOG(self.root), [])

    def test_status_expected_sha256_fails_for_a_different_loaded_rom(self):
        for expected, code in ((self.build["sha256"].upper(), 0), ("e" * 64, 2)):
            with self.subTest(expected=expected):
                session = self.session()
                session.close = lambda: None
                stdout = io.StringIO()
                with patch.object(sys, "argv", [str(SOURCE), "status", "--json", "--expect-sha256", expected]), \
                        patch.object(handheld, "Session", return_value=session), patch.object(sys, "stdout", stdout), \
                        patch.object(handheld.time, "monotonic", side_effect=[0, 9]), \
                        patch.object(handheld.time, "sleep", side_effect=AssertionError("Real retry delay forbidden")):
                    self.assertEqual(handheld.main(), code)
                result = json.loads(stdout.getvalue())
                self.assertEqual(result["loaded_expected_build"], code == 0)
                self.assert_read_only(session)

    def test_capture_reports_partial_when_loaded_rom_changes_between_reads(self):
        session = self.session()
        request = session.request

        def changing_rom(command):
            result = request(command)
            if command == "ROMINFO" and session.commands.count("ROMINFO") > 1:
                return {"sha1": "f" * 40}
            return result

        session.request = changing_rom
        result = handheld.capture(session, self.args)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["same_loaded_rom"])
        self.assert_read_only(session)

    def test_capture_cannot_claim_same_rom_when_hashes_are_missing(self):
        session = FakeSession({"filename": "oos168x.sfc"})
        result = handheld.capture(session, self.args)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["same_loaded_rom"])
        self.assert_read_only(session)

    def test_unknown_build_can_identify_sha256_from_a_matching_stable_device_copy(self):
        data = b"unregistered but identifiable device ROM"
        device = FakeDevice({f"{SD}/custom.sfc": data})
        session = FakeSession({"sha1": hashlib.sha1(data).hexdigest(), "filename": "custom.sfc"}, device=device)
        result = handheld.snapshot(session)
        self.assertIsNone(result["build"])
        self.assertEqual(result["loaded_sha256"], digest(data))
        self.assertIs(result["copies"][0]["matches_loaded_build"], True)
        self.assert_read_only(session)

    def test_changed_device_rom_cannot_supply_a_trusted_loaded_sha256(self):
        data = b"unregistered device ROM"
        path = f"{SD}/custom.sfc"
        device = FakeDevice({path: data}, changing={path})
        session = FakeSession({"sha1": hashlib.sha1(data).hexdigest(), "filename": "custom.sfc"}, device=device)
        result = handheld.snapshot(session)
        self.assertIsNone(result["loaded_sha256"])
        self.assertIsNone(result["copies"][0]["matches_loaded_build"])
        self.assertIn("changed", result["copies"][0]["errors"]["identity"])
        self.assert_read_only(session)


if __name__ == "__main__":
    unittest.main()
