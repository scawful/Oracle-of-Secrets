"""Smoke gate safety tests: fakes only, never import/connect an emulator client."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("run_build_smoke", ROOT / "Scripts/Build/run_build_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.commands = []

    def request(self, command):
        self.commands.append(command)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def response(data):
    return {"success": True, "data": data}


class SmokePreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.root = self.directory / "source"
        (self.root / "Tests/smoke").mkdir(parents=True)
        self.manifest = self.root / "Tests/manifest.json"
        self.definition = self.root / "Tests/smoke/fixture.json"
        self.manifest.write_text(json.dumps({"suites": {"smoke": {"tests": ["smoke/fixture.json"]}}}))
        self.definition.write_text(json.dumps({"name": "Fixture", "steps": []}))
        self.rom = self.directory / "candidate.sfc"
        self.rom.write_bytes(b"an isolated exact ROM fixture")
        self.endpoint = str(self.directory / "owned-agent.sock")
        self.hashes = smoke.file_identity(self.rom)
        self.good_info = {"filename": "candidate.sfc", "sha1": self.hashes["sha1"]}
        self.state = {"running": True, "paused": False, "frame": 12}
        self.runner = Mock(return_value=subprocess.CompletedProcess([], 0, "suite passed", ""))
        self.factory = Mock()

    def run_gate(self, responses=None, *, status=None, endpoint=None, verify_only=False):
        self.client = FakeClient(responses if responses is not None else [
            response(self.state), response(self.good_info),
            response(self.state), response(self.good_info),
        ])
        self.factory.return_value = self.client
        return smoke.run_smoke(
            self.rom, self.endpoint if endpoint is None else endpoint, root=self.root,
            client_factory=self.factory, runner=self.runner,
            status_reader=Mock(return_value=status or {}),
            verify_only=verify_only,
            environ={"MESEN2_SOCKET_PATH": "/wrong.sock", "OOS_TEST_BACKEND": "yaze", "OOS_MOE_ENABLED": "1",
                     "MESEN_AUTO_UNSTASH": "1", "MESEN_AUTO_STASH": "1", "MESEN_STASH_ON_FAIL": "1"},
        )

    def test_success_selects_exact_endpoint_and_rechecks_hash(self):
        code, receipt = self.run_gate()
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["expected"], self.hashes)
        self.factory.assert_called_once_with(self.endpoint)
        self.assertEqual(self.client.commands, ["STATE", "ROMINFO", "STATE", "ROMINFO"])
        args, kwargs = self.runner.call_args
        self.assertEqual(args[0], ["bash", str(self.root / "Scripts/Validate/run_regression_tests.sh"),
                                   "smoke", "--no-moe", "--fail-fast", "--skip-load",
                                   "--rom", str(self.rom)])
        self.assertEqual(kwargs["env"]["MESEN2_SOCKET_PATH"], self.endpoint)
        self.assertEqual(kwargs["env"]["OOS_TEST_BACKEND"], "socket")
        self.assertEqual(kwargs["env"]["OOS_TEST_REQUIRE_EMULATOR"], "1")
        self.assertEqual(kwargs["env"]["OOS_TEST_REQUIRE_ARTIFACTS"], "1")
        self.assertEqual(kwargs["env"]["MESEN_AUTO_FOCUS"], "0")
        self.assertEqual(kwargs["env"]["MESEN_AUTO_UNSTASH"], "0")
        self.assertEqual(kwargs["env"]["MESEN_AUTO_STASH"], "0")
        self.assertEqual(kwargs["env"]["MESEN_STASH_ON_FAIL"], "0")
        self.assertEqual(kwargs["env"]["MESEN2_HANDHELD"], "0")
        self.assertEqual(kwargs["cwd"], str(self.root))

    def test_missing_listed_definition_fails_before_connect_or_suite(self):
        self.manifest.write_text(json.dumps({"suites": {"smoke": {
            "tests": ["smoke/fixture.json", "smoke/missing.json"]}}}))
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("definition is missing", receipt["error"])
        self.factory.assert_not_called()
        self.runner.assert_not_called()

    def test_empty_manifest_list_fails_before_connect_or_suite(self):
        self.manifest.write_text(json.dumps({"suites": {"smoke": {"tests": []}}}))
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("at least one", receipt["error"])
        self.factory.assert_not_called()
        self.runner.assert_not_called()

    def test_literal_rom_must_match_selected_artifact(self):
        self.definition.write_text(json.dumps({"steps": [
            {"type": "exec", "command": ["python3", "lint.py", "--rom", "Roms/oos168x.sfc"]}
        ]}))
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("parameterize", receipt["error"])
        self.assertIn("oos168x.sfc", receipt["error"])
        self.factory.assert_not_called()
        self.runner.assert_not_called()

    def test_matching_literal_rom_passes_and_is_recorded(self):
        self.definition.write_text(json.dumps({"steps": [
            {"type": "exec", "command": ["python3", "lint.py", "--rom", str(self.rom)]}
        ]}))
        code, receipt = self.run_gate()
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt["suite_definition"]["literal_rom_inputs"], [str(self.rom)])
        self.assertEqual(receipt["suite_definition"]["definitions"], [str(self.definition)])

    def test_current_manifest_binds_rom_by_placeholder_for_any_build(self):
        for rom in ("Roms/oos168x.sfc", "Roms/oos999x.sfc"):
            details = smoke.check_smoke_definitions(ROOT, ROOT / rom)
            self.assertEqual(len(details["definitions"]), 3)
            self.assertEqual(details["literal_rom_inputs"], [])
        lint = json.loads((ROOT / "Tests/smoke/lint_pass.json").read_text())
        self.assertTrue(any("{rom}" in step.get("command", []) for step in lint["steps"]))

    def test_verify_only_does_not_require_smoke_definitions(self):
        self.manifest.unlink()
        code, receipt = self.run_gate(verify_only=True)
        self.assertEqual(code, 0, receipt)
        self.assertNotIn("suite_definition", receipt)
        self.runner.assert_not_called()

    def test_sha256_and_json_string_data_are_supported(self):
        info = {"filename": "candidate.sfc", "sha256": self.hashes["sha256"].upper()}
        code, receipt = self.run_gate([response(json.dumps(self.state)), response(json.dumps(info))] * 2)
        self.assertEqual(code, 0, receipt)

    def test_verify_only_checks_identity_without_suite_or_mutation_commands(self):
        code, receipt = self.run_gate(verify_only=True)
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt["check"], "rom-identity")
        self.assertEqual(receipt["scope"], "identity_only")
        self.assertEqual(receipt["status"], "passed")
        self.assertFalse(receipt["suite_started"])
        self.assertNotIn("command", receipt)
        self.assertNotIn("postflight", receipt)
        self.assertEqual(self.client.commands, ["STATE", "ROMINFO"])
        self.runner.assert_not_called()

    def test_verify_only_rejects_wrong_rom_without_starting_suite(self):
        code, receipt = self.run_gate([
            response(self.state), response({"sha1": "f" * 40}),
        ], verify_only=True)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["scope"], "identity_only")
        self.assertIn("does not match", receipt["error"])
        self.runner.assert_not_called()

    def test_verify_only_refuses_protected_endpoint_before_connecting(self):
        code, receipt = self.run_gate(endpoint="/tmp/mesen2-oos-rc-play.sock", verify_only=True)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["scope"], "identity_only")
        self.factory.assert_not_called()
        self.runner.assert_not_called()

    def test_cli_forwards_verify_only_and_emits_identity_scope(self):
        result = {"check": "rom-identity", "scope": "identity_only", "status": "passed"}
        with patch.object(smoke, "run_smoke", return_value=(0, result)) as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = smoke.main(["--rom", str(self.rom), "--socket", self.endpoint, "--verify-only"])
        self.assertEqual(code, 0)
        run.assert_called_once_with(self.rom, self.endpoint, verify_only=True)
        self.assertEqual(json.loads(output.getvalue())["scope"], "identity_only")

    def test_wrong_preflight_rom_fails_without_starting_suite(self):
        code, receipt = self.run_gate([response(self.state), response({"sha1": "f" * 40})])
        self.assertEqual(code, 1)
        self.assertIn("does not match", receipt["error"])
        self.runner.assert_not_called()

    def test_missing_or_unavailable_preflight_is_exit_two(self):
        for replies in ([smoke.SmokeError("no endpoint", unavailable=True)],
                        [{"success": False, "error": "No ROM loaded"}],
                        [response({"running": False})],
                        [response(self.state), response({"filename": "candidate.sfc"})]):
            with self.subTest(replies=replies):
                code, receipt = self.run_gate(replies)
                self.assertEqual(code, 2)
                self.assertEqual(receipt["status"], "unavailable")
                self.runner.assert_not_called()

    def test_wrong_postflight_rom_is_failure(self):
        code, receipt = self.run_gate([
            response(self.state), response(self.good_info),
            response(self.state), response({"sha1": "f" * 40}),
        ])
        self.assertEqual(code, 1)
        self.assertTrue(receipt["suite_started"])
        self.assertIn("does not match", receipt["error"])

    def test_lost_postflight_is_failure_not_optional_skip(self):
        code, receipt = self.run_gate([
            response(self.state), response(self.good_info),
            smoke.SmokeError("endpoint disappeared", unavailable=True),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(receipt["status"], "failed")

    def test_suite_failure_stays_fatal_and_identity_is_rechecked(self):
        self.runner.return_value = subprocess.CompletedProcess([], 2, "missing script", "suite error")
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(receipt["suite_returncode"], 2)
        self.assertEqual(receipt["suite_stdout"], "missing script")
        self.assertIn("postflight", receipt)
        self.assertEqual(self.client.commands, ["STATE", "ROMINFO", "STATE", "ROMINFO"])

    def test_suite_timeout_is_failure_and_identity_is_rechecked(self):
        self.runner.side_effect = subprocess.TimeoutExpired("suite", 180)
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("suite_error", receipt)
        self.assertIn("postflight", receipt)

    def test_changed_file_during_suite_is_failure(self):
        def change_rom(*args, **kwargs):
            self.rom.write_bytes(b"different artifact at same path")
            return subprocess.CompletedProcess([], 0, "", "")
        self.runner.side_effect = change_rom
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("file changed", receipt["error"])

    def test_protected_socket_is_refused_before_connecting(self):
        code, receipt = self.run_gate(endpoint="/tmp/mesen2-oos-rc-play.sock")
        self.assertEqual(code, 1)
        self.assertIn("protected user", receipt["error"])
        self.factory.assert_not_called()
        self.runner.assert_not_called()

    def test_protected_status_name_and_rom_filename_are_refused(self):
        code, receipt = self.run_gate(status={"instanceName": "oos-rc-play"})
        self.assertEqual(code, 1)
        self.assertEqual(self.client.commands, [])
        self.runner.assert_not_called()
        code, receipt = self.run_gate([response(self.state), response(dict(self.good_info, filename="oos-play.sfc"))])
        self.assertEqual(code, 1)
        self.runner.assert_not_called()

    def test_status_hash_or_socket_disagreement_fails(self):
        for status in ({"romHash": "f" * 40}, {"socketPath": "/other.sock"}):
            with self.subTest(status=status):
                code, receipt = self.run_gate(status=status)
                self.assertEqual(code, 1)
                self.runner.assert_not_called()

    def test_optional_state_hash_must_also_match(self):
        code, receipt = self.run_gate([response(dict(self.state, romHash="f" * 40)), response(self.good_info)])
        self.assertEqual(code, 1)
        self.assertIn("STATE sha1", receipt["error"])
        self.runner.assert_not_called()

    def test_changed_status_process_during_suite_fails(self):
        client = FakeClient([response(self.state), response(self.good_info)] * 2)
        code, receipt = smoke.run_smoke(
            self.rom, self.endpoint, root=self.root, client_factory=lambda endpoint: client,
            runner=self.runner, status_reader=Mock(side_effect=[{"pid": 123}, {"pid": 456}]),
        )
        self.assertEqual(code, 1)
        self.assertIn("process changed", receipt["error"])

    def test_malformed_protocol_is_failure_not_unavailable(self):
        code, receipt = self.run_gate([response("not JSON")])
        self.assertEqual(code, 1)
        self.runner.assert_not_called()

    def test_missing_rom_or_blank_socket_is_not_unavailable(self):
        self.rom.unlink()
        code, receipt = self.run_gate()
        self.assertEqual(code, 1)
        self.factory.assert_not_called()
        code, receipt = self.run_gate(endpoint="")
        self.assertEqual(code, 1)
        self.factory.assert_not_called()

    def test_status_reader_uses_only_explicit_sidecar(self):
        path = Path(self.endpoint).with_suffix(".status")
        self.assertEqual(smoke.read_status(self.endpoint), {})
        path.write_text(json.dumps({"socketPath": self.endpoint, "romHash": self.hashes["sha1"]}))
        self.assertEqual(smoke.read_status(self.endpoint)["romHash"], self.hashes["sha1"])
        path.write_text("not json")
        with self.assertRaises(smoke.SmokeError):
            smoke.read_status(self.endpoint)

    def test_cli_requires_rom_and_socket_without_client_creation(self):
        with patch.object(smoke, "run_smoke") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(smoke.main([]), 1)
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")


class ProtocolAndWrapperTest(unittest.TestCase):
    def test_socket_protocol_uses_given_path_and_read_only_command(self):
        conn = Mock()
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        stream = io.BytesIO(b'{"success":true,"data":{"running":true}}\n')
        conn.makefile.return_value = stream
        with patch.object(smoke.socket, "socket", return_value=conn) as factory:
            result = smoke.ExactEndpoint("/fixture/explicit.sock").request("STATE")
        factory.assert_called_once_with(smoke.socket.AF_UNIX, smoke.socket.SOCK_STREAM)
        conn.connect.assert_called_once_with("/fixture/explicit.sock")
        self.assertEqual(json.loads(conn.sendall.call_args.args[0]), {"type": "STATE"})
        self.assertTrue(result["data"]["running"])
        with self.assertRaises(smoke.SmokeError):
            smoke.ExactEndpoint("/fixture/explicit.sock").request("LOAD")

    def test_socket_connection_failure_is_unavailable_without_fallback(self):
        conn = Mock()
        conn.connect.side_effect = ConnectionRefusedError("fixture refuses connection")
        with patch.object(smoke.socket, "socket", return_value=conn) as factory:
            with self.assertRaises(smoke.SmokeError) as raised:
                smoke.ExactEndpoint("/fixture/explicit.sock").request("STATE")
        self.assertTrue(raised.exception.unavailable)
        factory.assert_called_once()
        conn.connect.assert_called_once_with("/fixture/explicit.sock")

    def test_wrapper_forwards_skip_load_without_running_real_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "Scripts/Validate/run_regression_tests.sh"
            wrapper.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "Scripts/Validate/run_regression_tests.sh", wrapper)
            (root / "Tests").mkdir()
            (root / "Tests/manifest.json").write_text("{}")
            bindir = root / "bin"
            bindir.mkdir()
            stub = bindir / "python3"
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            stub.chmod(0o755)
            result = subprocess.run(
                ["bash", str(wrapper), "smoke", "--skip-load", "--no-moe", "--fail-fast"],
                capture_output=True, text=True,
                env=dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"]),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                "Scripts/Validate/test_runner.py", "--suite", "smoke", "--manifest",
                str(root / "Tests/manifest.json"), "--skip-load", "--fail-fast",
            ])


if __name__ == "__main__":
    unittest.main()
