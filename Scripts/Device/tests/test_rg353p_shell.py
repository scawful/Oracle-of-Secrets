#!/usr/bin/env python3
"""Host-only regression tests: every adb call is an isolated fake subprocess."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "oos_rg353p.sh"
SD = "/storage/0000-0000/snes/oos168x.sfc"
DROP = "/storage/emulated/0/OracleOfSecrets/oos168x.sfc"
STAGED = "/storage/emulated/0/Android/data/ca.mesen.oos/files/oos168x.sfc"
INTERNAL = "/data/data/ca.mesen.oos/files/oos168x.sfc"
AUTHORIZED = "List of devices attached\nrg-one\tdevice product:rk model:RG353P transport_id:1\n"


FAKE_ADB = r'''
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

state_path = Path(os.environ["FAKE_ADB_STATE"])
state = json.loads(state_path.read_text())
args = sys.argv[1:]
with Path(os.environ["FAKE_ADB_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\n")

def finish(code=0):
    state_path.write_text(json.dumps(state))
    raise SystemExit(code)

if args == ["devices", "-l"]:
    print(state["devices"], end="")
    finish(state.get("devices_exit", 0))
if len(args) < 3 or args[0] != "-s":
    raise SystemExit("unexpected adb invocation: " + repr(args))
args = args[2:]
if args[0] == "push":
    state["files"][args[2]] = Path(args[1]).read_text()
    finish()
if args[0] == "forward":
    finish()
if args[0] != "shell":
    raise SystemExit("unexpected adb operation: " + repr(args))
tokens = shlex.split(args[1]) if len(args) == 2 else args[1:]
commands = [[]]
for token in tokens:
    if token == "&&":
        commands.append([])
    else:
        commands[-1].append(token)
for command in commands:
    if command[:2] == ["run-as", "ca.mesen.oos"]:
        command = command[2:]
    files = state["files"]
    if command[:2] == ["pm", "path"]:
        if not state.get("installed", True):
            finish(1)
        print("package:/data/app/ca.mesen.oos/base.apk")
    elif command[:2] == ["test", "-f"]:
        if command[2] not in files:
            finish(1)
    elif command[0] == "sha256sum":
        if command[1] not in files:
            finish(1)
        digest = hashlib.sha256(files[command[1]].encode()).hexdigest()
        if command[1] == state.get("invalid_hash_path"):
            digest = "not-a-hash"
        print(digest + "  " + command[1])
    elif command[0] == "cp":
        source, destination = command[1:]
        if destination == state.get("fail_copy_to"):
            print("cp: permission denied", file=sys.stderr)
            finish(1)
        if source not in files:
            finish(1)
        files[destination] = files[source]
        if destination == state.get("corrupt_copy_to"):
            files[destination] += "corrupt"
    elif command[0] == "cat":
        if command[1] not in files:
            finish(1)
        print(files[command[1]], end="")
    elif command[:2] == ["mkdir", "-p"] or command[0] == "chmod":
        pass
    elif command[0] in ("am", "cmd"):
        pass
    else:
        raise SystemExit("unexpected shell command: " + repr(command))
finish()
'''


HELPER_STUB = '''
import json
import os
from pathlib import Path
import sys
record = {"argv": sys.argv[1:], "serial": os.environ.get("OOS_DEVICE_SERIAL")}
print(json.dumps(record))
adb_log = Path(os.environ["FAKE_ADB_LOG"])
record["adb_calls"] = len(adb_log.read_text().splitlines()) if adb_log.exists() else 0
with Path(os.environ["FAKE_HELPER_LOG"]).open("a") as log:
    log.write(json.dumps(record) + "\\n")
exits = json.loads(os.environ.get("FAKE_HELPER_EXITS", "{}"))
sys.exit(int(exits.get(sys.argv[1], os.environ.get("FAKE_HELPER_EXIT", "0"))))
'''


class HandheldShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oos-rg353p-shell-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        device_dir = self.root / "oracle" / "Scripts" / "Device"
        device_dir.mkdir(parents=True)
        self.script = device_dir / SOURCE.name
        shutil.copyfile(SOURCE, self.script)
        (device_dir / "oos_handheld.py").write_text(HELPER_STUB)
        (device_dir / "oos_workshop_collect.py").write_text(HELPER_STUB)
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_adb = fake_bin / "adb"
        fake_adb.write_text("#!" + sys.executable + "\n" + FAKE_ADB)
        fake_adb.chmod(0o755)
        self.state_path = self.root / "adb-state.json"
        self.log_path = self.root / "adb-log.jsonl"
        self.helper_log_path = self.root / "helper-log.jsonl"
        self.configure(files={SD: "fresh candidate", DROP: "older drop", STAGED: "stale candidate"})
        self.env = os.environ.copy()
        for key in ("OOS_DEVICE_SERIAL", "OOS_DEVICE_SNES_DIR", "OOS_DEVICE_DROP_DIR", "MESEN2_OOS_ROOT"):
            self.env.pop(key, None)
        self.env.update({
            "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_ADB_STATE": str(self.state_path),
            "FAKE_ADB_LOG": str(self.log_path),
            "FAKE_HELPER_LOG": str(self.helper_log_path),
        })

    def configure(self, **changes):
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "devices": AUTHORIZED, "files": {},
        }
        state.update(changes)
        self.state_path.write_text(json.dumps(state))

    def run_shell(self, *args, env=None):
        environment = self.env.copy()
        environment.update(env or {})
        return subprocess.run(
            ["/bin/bash", str(self.script), *args],
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def calls(self):
        return [json.loads(line) for line in self.log_path.read_text().splitlines()] if self.log_path.exists() else []

    def helper_calls(self):
        return [json.loads(line) for line in self.helper_log_path.read_text().splitlines()] if self.helper_log_path.exists() else []

    def local_rom(self, name="oos168x.sfc", content="new named candidate"):
        path = self.root / name
        path.write_text(content)
        return path

    def assert_not_launched(self):
        self.assertFalse(any("force-stop" in call or "start" in call for call in self.calls()))

    def assert_verified_launch(self, result, content, basename="oos168x.sfc"):
        self.assertEqual(result.returncode, 0, result.stderr)
        files = json.loads(self.state_path.read_text())["files"]
        staged = str(Path(STAGED).with_name(basename))
        internal = str(Path(INTERNAL).with_name(basename))
        self.assertEqual(files[staged], content)
        self.assertEqual(files[internal], content)
        self.assertIn("sha256=" + hashlib.sha256(content.encode()).hexdigest(), result.stdout)
        launches = [call for call in self.calls() if "start" in call]
        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0][-3:], ["--es", "rom", staged])

    def test_default_launch_replaces_stale_staged_rom_from_sd(self):
        result = self.run_shell("mesen-launch")
        self.assert_verified_launch(result, "fresh candidate")
        self.assertIn("source=" + SD, result.stdout)

    def test_missing_sd_uses_drop_before_existing_staged_rom(self):
        self.configure(files={DROP: "fresh drop", STAGED: "stale candidate"})
        result = self.run_shell("mesen-launch")
        self.assert_verified_launch(result, "fresh drop")
        self.assertIn("source=" + DROP, result.stdout)

    def test_staged_rom_is_last_fallback(self):
        self.configure(files={STAGED: "only candidate"})
        result = self.run_shell("mesen-launch")
        self.assert_verified_launch(result, "only candidate")
        self.assertIn("source=" + STAGED, result.stdout)

    def test_explicit_rom_is_preserved(self):
        explicit = "/storage/0000-0000/snes/selected.sfc"
        self.configure(files={SD: "default", explicit: "selected candidate"})
        result = self.run_shell("mesen-launch", "--rom-on-device", explicit)
        self.assert_verified_launch(result, "selected candidate", "selected.sfc")
        self.assertIn("source=" + explicit, result.stdout)

    def test_explicit_staged_rom_does_not_copy_onto_itself(self):
        explicit = str(Path(STAGED).with_name("selected.sfc"))
        self.configure(files={SD: "default", explicit: "selected candidate"})
        result = self.run_shell("mesen-launch", "--rom-on-device", explicit)
        self.assert_verified_launch(result, "selected candidate", "selected.sfc")
        copies = [call[-1] for call in self.calls() if call[-1].startswith("cp ")]
        self.assertFalse(copies)

    def test_missing_rom_does_not_launch(self):
        self.configure(files={})
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("device ROM missing", result.stderr)
        self.assert_not_launched()

    def test_copy_failure_is_not_hidden(self):
        for destination in (STAGED, INTERNAL):
            with self.subTest(destination=destination):
                self.configure(fail_copy_to=destination)
                result = self.run_shell("mesen-launch")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("permission denied", result.stderr)
                self.assertIn("failed to", result.stderr)
                self.assert_not_launched()

    def test_hash_mismatch_blocks_launch(self):
        for destination in (STAGED, INTERNAL):
            with self.subTest(destination=destination):
                self.configure(corrupt_copy_to=destination)
                result = self.run_shell("mesen-launch")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("sha256 mismatch", result.stderr)
                self.assert_not_launched()

    def test_invalid_hash_response_blocks_launch(self):
        self.configure(invalid_hash_path=SD)
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid sha256 response", result.stderr)
        self.assert_not_launched()

    def test_autodetect_refuses_non_rg353p(self):
        self.configure(devices="List of devices attached\npixel\tdevice model:Pixel_9\n")
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no authorized RG353P", result.stderr)
        self.assertEqual(self.calls(), [["devices", "-l"]])

    def test_autodetect_refuses_unauthorized_rg353p(self):
        self.configure(devices="List of devices attached\nrg-one\tunauthorized model:RG353P\n")
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [["devices", "-l"]])

    def test_autodetect_refuses_multiple_authorized_rg353p_devices(self):
        self.configure(devices=AUTHORIZED + "rg-two\tdevice model:RG353P\n")
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("multiple authorized RG353P", result.stderr)
        self.assertEqual(self.calls(), [["devices", "-l"]])

    def test_explicit_serial_must_be_authorized(self):
        for status in ("offline", "unauthorized", "missing"):
            with self.subTest(status=status):
                self.configure(devices=AUTHORIZED + ("selected\t" + status + " model:RG353P\n" if status != "missing" else ""))
                result = self.run_shell("mesen-launch", env={"OOS_DEVICE_SERIAL": "selected"})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing, offline, or unauthorized", result.stderr)
                self.assert_not_launched()
        self.assertTrue(all(call == ["devices", "-l"] for call in self.calls()))

    def test_explicit_serial_resolves_ambiguity(self):
        self.configure(devices=AUTHORIZED + "rg-two\tdevice model:RG353P\n")
        result = self.run_shell("mesen-launch", env={"OOS_DEVICE_SERIAL": "rg-two"})
        self.assert_verified_launch(result, "fresh candidate")
        self.assertTrue(all(call[:2] == ["-s", "rg-two"] for call in self.calls()[1:]))

    def test_exact_model_matching_does_not_select_rg353ps(self):
        self.configure(devices="List of devices attached\nother\tdevice model:RG353PS\n")
        result = self.run_shell("mesen-launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [["devices", "-l"]])

    def test_helper_commands_delegate_before_adb_or_sibling_resolution(self):
        for command in ("status", "capture", "backup", "prepare"):
            with self.subTest(command=command):
                result = self.run_shell(command, "--help", env={"OOS_DEVICE_SERIAL": "unavailable"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"argv": [command, "--help"], "serial": "unavailable"})
                self.assertEqual(self.calls(), [])

    def test_helper_failure_propagates(self):
        result = self.run_shell("capture", env={"FAKE_HELPER_EXIT": "7"})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.calls(), [])

    def test_collect_delegates_arguments_without_device_preflight(self):
        result = self.run_shell("collect", "--help", env={"OOS_DEVICE_SERIAL": "unavailable"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"argv": ["--help"], "serial": "unavailable"})
        self.assertEqual(self.calls(), [])

    def test_workshop_delegates_capture_and_propagates_failure(self):
        result = self.run_shell("mesen-workshop", "--port", "27123", env={"FAKE_HELPER_EXIT": "7"})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(json.loads(result.stdout), {"argv": ["capture", "--port", "27123"], "serial": "rg-one"})
        self.assertNotIn("handheld.png", result.stdout)
        self.assertEqual(self.calls(), [["devices", "-l"]])

    def test_mesen_discover_reads_private_workshop_status_through_run_as(self):
        workshop = '{"observedFps":40.25,"rom":"oos168x.sfc"}\n'
        self.configure(files={"files/workshop.json": workshop})
        result = self.run_shell("mesen-discover")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(workshop.strip(), result.stdout)
        self.assertNotIn("not written yet", result.stdout)
        self.assertIn(
            ["-s", "rg-one", "shell", "run-as", "ca.mesen.oos", "cat", "files/workshop.json"],
            self.calls(),
        )

    def test_mesen_env_uses_only_loopback_adb_forward(self):
        workshop = '{"bind":"127.0.0.1","transport":"adb-forward"}\n'
        self.configure(files={"files/workshop.json": workshop})
        result = self.run_shell("mesen-env", "--port", "27123")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            ["-s", "rg-one", "forward", "tcp:27123", "tcp:27123"],
            self.calls(),
        )
        generated = self.root / "oracle" / ".context" / "scratchpad" / "mesen2"
        env = (generated / "handheld.env").read_text()
        self.assertIn("MESEN2_SOCKET_PATH=tcp://127.0.0.1:27123", env)
        self.assertIn("MESEN2_TCP_HOST=127.0.0.1", env)
        self.assertNotIn("MESEN2_LAN", env)
        metadata = json.loads((generated / "handheld.json").read_text())
        self.assertEqual(metadata["socket"], "tcp://127.0.0.1:27123")
        self.assertEqual(metadata["via"], "adb")
        self.assertNotIn("lan", metadata)
        self.assertNotIn("lanEndpoint", metadata)

    def test_mesen_env_rejects_retired_lan_attach(self):
        result = self.run_shell("mesen-env", "--lan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workshop is loopback-only", result.stderr)
        self.assertFalse(any("forward" in call for call in self.calls()))

    def test_help_needs_neither_device_nor_sibling_checkout(self):
        result = self.run_shell("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("capture", result.stdout)
        self.assertNotIn("mesen-lan", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_named_push_backs_up_then_launches_and_checks_exact_rom(self):
        content = "new named candidate"
        digest = hashlib.sha256(content.encode()).hexdigest()
        name = "oos-168-20260915-minecart-junction-" + digest[:8] + ".sfc"
        rom = self.local_rom(name, content)
        result = self.run_shell("push", "--rom", str(rom), "--mesen")
        self.assert_verified_launch(result, content, name)
        files = json.loads(self.state_path.read_text())["files"]
        self.assertEqual(files[str(Path(SD).with_name(name))], content)
        self.assertEqual(files[str(Path(DROP).with_name(name))], content)
        self.assertEqual(files[SD], "fresh candidate")
        self.assertIn("source=" + str(Path(SD).with_name(name)), result.stdout)
        helper_calls = self.helper_calls()
        self.assertEqual(len(helper_calls), 2)
        self.assertEqual(helper_calls[0], {"argv": ["backup"], "serial": "rg-one", "adb_calls": 1})
        self.assertEqual(helper_calls[1], {
            "argv": ["status", "--expect-sha256", digest], "serial": "rg-one", "adb_calls": len(self.calls()),
        })

    def test_named_hash_mismatch_rejected_even_with_allow_base(self):
        rom = self.local_rom("oos-168-20260915-minecart-junction-00000000.sfc")
        for extra in ([], ["--allow-base"]):
            with self.subTest(extra=extra):
                result = self.run_shell("push", "--rom", str(rom), "--mesen", *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("named ROM hash mismatch", result.stderr)
                self.assert_not_launched()
        self.assertTrue(all(call == ["devices", "-l"] for call in self.calls()))
        self.assertEqual(self.helper_calls(), [])

    def test_named_format_requires_lowercase_hash_and_slug(self):
        for name in (
            "oos-168-20260915-minecart-junction-ABCDEF12.sfc",
            "oos-168-20260915-Minecart-junction-abcdef12.sfc",
            "oos-168-20260915-minecart_junction-abcdef12.sfc",
        ):
            with self.subTest(name=name):
                rom = self.local_rom(name)
                result = self.run_shell("push", "--rom", str(rom), "--mesen", "--allow-base")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing", result.stderr)
        self.assertTrue(all(call == ["devices", "-l"] for call in self.calls()))
        self.assertEqual(self.helper_calls(), [])

    def test_legacy_patched_rom_remains_supported(self):
        rom = self.local_rom()
        result = self.run_shell("push", "--rom", str(rom))
        self.assertEqual(result.returncode, 0, result.stderr)
        files = json.loads(self.state_path.read_text())["files"]
        self.assertEqual(files[SD], rom.read_text())
        self.assertEqual(files[DROP], rom.read_text())
        self.assert_not_launched()

    def test_base_rom_is_refused_without_explicit_override(self):
        rom = self.local_rom("oos168.sfc")
        result = self.run_shell("push", "--rom", str(rom), "--mesen")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing", result.stderr)
        self.assertEqual(self.calls(), [["devices", "-l"]])
        self.assertEqual(self.helper_calls(), [])

    def test_backup_failure_stops_before_any_device_write(self):
        rom = self.local_rom()
        result = self.run_shell("push", "--rom", str(rom), "--mesen", env={"FAKE_HELPER_EXITS": '{"backup": 7}'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("save backup failed", result.stderr)
        self.assertEqual(self.calls(), [["devices", "-l"]])
        self.assertEqual([call["argv"] for call in self.helper_calls()], [["backup"]])
        self.assertEqual(json.loads(self.state_path.read_text())["files"][SD], "fresh candidate")

    def test_loaded_identity_failure_propagates(self):
        rom = self.local_rom()
        result = self.run_shell("push", "--rom", str(rom), "--mesen", env={"FAKE_HELPER_EXITS": '{"status": 9}'})
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual([call["argv"][0] for call in self.helper_calls()], ["backup", "status"])
        self.assertTrue(any("start" in call for call in self.calls()))

    def test_mesen_and_snes9x_launch_flags_conflict(self):
        rom = self.local_rom()
        result = self.run_shell("push", "--rom", str(rom), "--mesen", "--launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be combined", result.stderr)
        self.assertEqual(self.calls(), [["devices", "-l"]])
        self.assertEqual(self.helper_calls(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
