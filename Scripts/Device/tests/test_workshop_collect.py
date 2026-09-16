"""Workshop import checks use an in-memory device; no emulator controls exist."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oos_workshop_collect as subject


class Device:
    serial = "test-device"

    def __init__(self, status="complete", kind="checkpoint"):
        group = "checkpoints" if kind == "checkpoint" else "issues"
        self.directory = subject.REMOTE + "/" + group + "/20260915-test-123"
        self.files = {self.directory + "/state.mss": b"MSS-state-data",
                      self.directory + "/screenshot.png": b"PNG-test-data"}
        self.manifest = {"schema": subject.SCHEMA, "id": "20260915-test-123",
                         "status": status, "kind": kind,
                         "files": [{"name": Path(p).name, "size": len(b), "sha256": subject.sha256(b)}
                                   for p, b in self.files.items()]}
        self.calls = []
        self.changed = None
        self.alias = None
        self.refresh()

    def refresh(self):
        self.files[self.directory + "/manifest.json"] = json.dumps(self.manifest).encode()

    def shell(self, *args):
        self.calls.append(args)
        if args[0] == "find":
            return (self.directory + "\n").encode()
        if args[:2] == ("readlink", "-f"):
            path = args[2]
            if self.alias and path.endswith("state.mss"):
                return self.alias.encode()
            return path.replace("/data/data/", "/data/user/0/").encode()
        if args[:3] == ("stat", "-c", "%s"):
            return str(len(self.files[args[3]])).encode()
        raise AssertionError("Unexpected device operation " + repr(args))

    def hash(self, path):
        self.calls.append(("hash", path))
        return subject.sha256(self.files[path])

    def read(self, path):
        self.calls.append(("read", path))
        data = self.files[path]
        if path == self.changed:
            self.files[path] += b"changed"
        return data


class CollectTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.parent = Path(tmp.name)

    def run_collect(self, device):
        return subject.collect(device, self.parent)

    def test_copies_checkpoint_and_issue_without_device_mutation(self):
        for kind in ("checkpoint", "issue"):
            d = Device(kind=kind)
            before = dict(d.files)
            result = self.run_collect(d)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["complete_count"], 1)
            self.assertEqual(d.files, before)
            target = Path(result["folder"]) / result["items"][0]["folder"]
            self.assertEqual((target / "state.mss").read_bytes(), b"MSS-state-data")
            self.assertIsNone(result["items"][0]["title"])
            self.assertIsNone(result["items"][0]["note"])

    def test_app_private_adapter_scopes_reads_through_run_as(self):
        class Base:
            serial = "usb-device"

            def __init__(self):
                self.calls = []

            def shell(self, *args):
                self.calls.append(args)
                if args[2] == "cat":
                    return b"private-data"
                if args[2] == "sha256sum":
                    return (subject.sha256(b"private-data") + "  file\n").encode()
                raise AssertionError(args)

        base = Base()
        scoped = subject.AppFilesDevice(base)
        self.assertEqual(scoped.read("/data/data/ca.mesen.oos/files/file"),
                         b"private-data")
        self.assertEqual(scoped.hash("/data/data/ca.mesen.oos/files/file"),
                         subject.sha256(b"private-data"))
        self.assertEqual(base.calls[0][:3],
                         ("run-as", "ca.mesen.oos", "cat"))
        self.assertEqual(base.calls[1][:3],
                         ("run-as", "ca.mesen.oos", "sha256sum"))

    def test_copies_optional_title_and_note(self):
        d = Device()
        d.manifest["title"] = "Before stairs"
        d.manifest["note"] = "Hold Down"
        d.manifest["game_state"] = {
            "link": {"x": 0x1234, "y": 0x5678},
            "game": {"mode": 0x09, "overworld_area": "0x2A"},
        }
        d.manifest["sprites"] = {
            "count": 1,
            "sprites": [{"slot": 3, "type": 0x6C}],
        }
        d.manifest["warnings"] = []
        d.refresh()
        result = self.run_collect(d)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["items"][0]["title"], "Before stairs")
        self.assertEqual(result["items"][0]["note"], "Hold Down")
        self.assertEqual(result["items"][0]["game_state"]["link"]["x"], 0x1234)
        self.assertEqual(result["items"][0]["sprites"]["sprites"][0]["slot"], 3)
        self.assertEqual(result["items"][0]["warnings"], [])

    def test_repeated_collection_never_overwrites_local_evidence(self):
        d = Device()
        one, two = self.run_collect(d), self.run_collect(d)
        self.assertNotEqual(one["folder"], two["folder"])

    def test_partial_device_result_is_retained_and_not_claimed_complete(self):
        result = self.run_collect(Device(status="partial"))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["items"][0]["files"]), 2)
        self.assertEqual(result["complete_count"], 0)

    def test_wrong_checksum_is_rejected(self):
        d = Device()
        d.files[d.directory + "/state.mss"] = b"MSS-wrong-data"
        result = self.run_collect(d)
        self.assertEqual(result["status"], "partial")
        self.assertIn("checksum", result["items"][0]["error"])
        self.assertEqual([f["name"] for f in result["items"][0]["files"]], ["screenshot.png"])

    def test_case_alias_cannot_overwrite_collected_state(self):
        d = Device()
        d.files[d.directory + "/STATE.MSS"] = b"different"
        d.manifest["files"].append({"name": "STATE.MSS", "size": 9,
                                   "sha256": subject.sha256(b"different")})
        d.refresh()
        result = self.run_collect(d)
        self.assertEqual(result["status"], "partial")
        target = Path(result["folder"]) / result["items"][0]["folder"]
        self.assertEqual((target / "state.mss").read_bytes(), b"MSS-state-data")

    def test_timeout_retains_collection_report_and_other_components(self):
        d = Device()
        original = d.read
        def read(path):
            if path.endswith("state.mss"):
                raise subprocess.TimeoutExpired(["adb", "shell", "cat"], 15)
            return original(path)
        with patch.object(d, "read", side_effect=read):
            result = self.run_collect(d)
        self.assertEqual(result["status"], "partial")
        self.assertTrue((Path(result["folder"]) / "collection.json").is_file())
        self.assertEqual([f["name"] for f in result["items"][0]["files"]], ["screenshot.png"])

    def test_changing_file_is_rejected(self):
        d = Device()
        d.changed = d.directory + "/state.mss"
        self.assertEqual(self.run_collect(d)["status"], "partial")

    def test_symlink_outside_bundle_is_rejected(self):
        d = Device()
        d.alias = "/data/user/0/ca.mesen.oos/files/Saves/oos168x.srm"
        result = self.run_collect(d)
        self.assertIn("symlink", result["items"][0]["error"])

    def test_path_traversal_and_duplicate_files_are_rejected(self):
        for name in ("../outside", "/outside", "manifest.json", "screenshot.png"):
            d = Device()
            d.manifest["files"][0]["name"] = name
            d.refresh()
            self.assertEqual(self.run_collect(d)["status"], "partial")

    def test_bad_identity_and_manifest_shape_are_rejected(self):
        for mutate in (lambda d: d.manifest.update(id="wrong"),
                       lambda d: d.manifest.update(files={}),
                       lambda d: d.manifest.update(kind="wrong"),
                       lambda d: d.manifest.update(files=[])):
            d = Device()
            mutate(d)
            d.refresh()
            self.assertEqual(self.run_collect(d)["status"], "partial")


if __name__ == "__main__":
    unittest.main()
