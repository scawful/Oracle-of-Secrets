"""Offline admission tests; no Mesen process or socket client is created."""
import dataclasses
import hashlib
import json
from pathlib import Path
import plistlib
import socket
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import room_scenario_binding as admission


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix socket metadata required")
class RoomScenarioBindingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rsb-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.endpoint = self.root / "owned.sock"
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(self.endpoint))  # Metadata fixture only: no listen/connect.
        self.addCleanup(self.sock.close)
        self.rom = self.root / "rom.sfc"
        self.state = self.root / "state.mss"
        self.app = self.root / "Mesen"
        self.rom.write_bytes(b"exact ROM fixture")
        self.state.write_bytes(b"exact state fixture")
        self.app.write_bytes(b"executable identity fixture")
        self.record_path = self.root / "owned.json"
        self.record = {"instance": "owned-proof", "owner": "Codex-proof",
                       "socket": str(self.endpoint), "pid": 12345,
                       "active": True, "alive": True, "app_path": str(self.app)}
        self.write_record()
        self.status = self.endpoint.with_suffix(".status")
        self.status.write_text(json.dumps({"pid": 12345, "socketPath": str(self.endpoint)}))
        self.process = mock.patch.object(
            admission, "_process_identity",
            return_value=("Thu Oct 29 12:00:00 2026", str(self.app) + " --headless"))
        self.identity = self.process.start()
        self.addCleanup(self.process.stop)
        self.args = dict(rom=self.rom, expected_rom_sha256=self.sha(self.rom),
                         state=self.state, expected_state_sha256=self.sha(self.state),
                         socket_path=self.endpoint, session_record=self.record_path,
                         owner="Codex-proof")

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_record(self):
        self.record_path.write_text(json.dumps(self.record))

    def create(self, **overrides):
        return admission.RoomScenarioBinding.create(**(self.args | overrides))

    def test_binding_is_immutable_and_remote_operation_is_only_rominfo(self):
        binding = self.create()
        self.assertEqual(binding.rom_path, self.rom)
        self.assertEqual(binding.socket_path, str(self.endpoint))
        self.assertEqual(binding.pid, 12345)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            binding.owner = "another"
        bridge = mock.Mock()
        bridge.get_rom_info.return_value = {"sha1": hashlib.sha1(self.rom.read_bytes()).hexdigest()}
        binding.verify_remote(bridge)
        self.assertEqual(bridge.mock_calls, [mock.call.get_rom_info()])

    def test_missing_identity_and_local_hash_failure_never_inspect_process(self):
        for override in [{"expected_rom_sha256": ""}, {"expected_state_sha256": "bad"},
                         {"socket_path": ""}, {"owner": ""},
                         {"expected_rom_sha256": "0" * 64}, {"rom": self.root / "missing"}]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.create(**override)
        self.identity.assert_not_called()

    def test_wrong_endpoint_refuses_before_process_inspection(self):
        other = self.root / "other.sock"
        other.write_bytes(b"wrong endpoint")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.create(socket_path=other)
        self.identity.assert_not_called()

    def test_unowned_inactive_or_not_alive_record_refuses(self):
        for field, value in [("owner", "another"), ("active", False), ("alive", False),
                             ("active", 1), ("alive", "true")]:
            with self.subTest(field=field, value=value):
                original = self.record[field]
                self.record[field] = value
                self.write_record()
                with self.assertRaises(ValueError):
                    self.create()
                self.record[field] = original
        self.identity.assert_not_called()

    def test_named_status_pid_fallback_and_mismatch(self):
        self.record["pid"] = None
        self.write_record()
        self.assertEqual(self.create().pid, 12345)
        self.record["pid"] = 67890
        self.write_record()
        with self.assertRaisesRegex(ValueError, "PID differ"):
            self.create()

    def test_missing_or_wrong_status_binding_refuses(self):
        self.record["pid"] = None
        self.write_record()
        self.status.unlink()
        with self.assertRaisesRegex(ValueError, "no registry or status PID"):
            self.create()
        self.status.write_text(json.dumps({"pid": 12345, "socketPath": str(self.rom)}))
        with self.assertRaisesRegex(ValueError, "socketPath differs"):
            self.create()

    def test_protected_instance_and_sibling_pid_or_socket_alias_refuse(self):
        self.record["instance"] = "oos-rc-play"
        self.write_record()
        with self.assertRaisesRegex(ValueError, "protected"):
            self.create()
        self.record["instance"] = "owned-proof"
        self.write_record()
        sibling = self.root / "oos-rc-play.json"
        for other in [{"pid": 12345}, {"socket": str(self.endpoint)}]:
            sibling.write_text(json.dumps({"instance": "oos-rc-play", **other}))
            with self.assertRaisesRegex(ValueError, "aliases"):
                self.create()
        self.identity.assert_not_called()

    def test_duplicate_or_malformed_metadata_refuses(self):
        self.record_path.write_text('{"owner":"Codex-proof","owner":"another"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.create()
        self.record_path.write_text("[]")
        with self.assertRaises(ValueError):
            self.create()

    def test_protected_sibling_named_status_pid_alias_refuses(self):
        sibling_endpoint = self.root / "protected.sock"
        sibling_endpoint.write_bytes(b"metadata path only")
        sibling_endpoint.with_suffix(".status").write_text(json.dumps(
            {"pid": 12345, "socketPath": str(sibling_endpoint)}))
        (self.root / "oos-rc-play.json").write_text(json.dumps(
            {"instance": "oos-rc-play", "pid": None, "socket": str(sibling_endpoint)}))
        with self.assertRaisesRegex(ValueError, "aliases"):
            self.create()
        self.identity.assert_not_called()

    def test_launcher_bundle_entry_point_is_bound_to_live_command(self):
        bundle = self.root / "Mesen2 OOS.app"
        executable = bundle / "Contents" / "MacOS" / "Mesen2"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"app fixture")
        self.record["app_path"] = str(bundle)
        self.write_record()
        self.identity.return_value = ("a start", str(executable) + " --headless")
        self.assertEqual(self.create().app_path, executable)

    def test_bundle_plist_selects_nonstandard_executable_without_guessing(self):
        bundle = self.root / "Scenario.app"
        executable = bundle / "Contents" / "MacOS" / "Room Scenario Runner"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"plist fixture")
        with (bundle / "Contents" / "Info.plist").open("wb") as stream:
            plistlib.dump({"CFBundleExecutable": executable.name}, stream)
        self.record["app_path"] = str(bundle)
        self.write_record()
        self.identity.return_value = ("a start", str(executable) + " --headless")
        self.assertEqual(self.create().app_path, executable)
        self.identity.return_value = ("a start", str(bundle / "Contents/MacOS/Mesen"))
        with self.assertRaisesRegex(ValueError, "app_path"):
            self.create()

    def test_live_process_must_match_app_path(self):
        self.identity.return_value = ("a start", str(self.app) + "-unrelated")
        with self.assertRaisesRegex(ValueError, "app_path"):
            self.create()

    def test_pid_reuse_or_command_drift_invalidates_frozen_binding(self):
        binding = self.create()
        self.identity.return_value = ("different start", str(self.app) + " --headless")
        with self.assertRaisesRegex(ValueError, "identity changed"):
            binding.verify_local()

    def test_record_owner_or_state_bytes_drift_invalidates_binding(self):
        binding = self.create()
        self.state.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed after admission"):
            binding.verify_local()
        self.state.write_bytes(b"exact state fixture")
        self.record["owner"] = "another"
        self.write_record()
        with self.assertRaises(ValueError):
            binding.verify_local()

    def test_socket_replacement_and_regular_file_refuse(self):
        binding = self.create()
        with mock.patch.object(admission, "_socket_identity", return_value=(0, 0, 0)):
            with self.assertRaisesRegex(ValueError, "identity changed"):
                binding.verify_local()
        self.sock.close()
        self.endpoint.unlink()
        self.endpoint.write_bytes(b"not a socket")
        with self.assertRaisesRegex(ValueError, "not a Unix socket"):
            binding.verify_local()

    def test_remote_mismatch_and_missing_identity_do_not_call_mutations(self):
        binding = self.create()
        for reply in [{}, {"sha1": "0" * 40}, "not an identity", {"sha1": None}]:
            bridge = mock.Mock()
            bridge.get_rom_info.return_value = reply
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                binding.verify_remote(bridge)
            self.assertEqual(bridge.mock_calls, [mock.call.get_rom_info()])


if __name__ == "__main__":
    unittest.main()
