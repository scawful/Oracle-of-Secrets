"""Host-only behaviour of Scripts/Validate/test_runner.py: no emulator, no ROM."""
import importlib.util
import hashlib
import io
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "Scripts/Validate/test_runner.py"
WRAPPER = ROOT / "Scripts/Validate/run_regression_tests.sh"
NO_EMULATOR_ENV = {"OOS_TEST_BACKEND": "none", "MESEN2_SOCKET_PATH": "/nonexistent/oos-test.sock",
                   "MESEN_AUTO_FOCUS": "0", "MESEN_AUTO_UNSTASH": "0", "NO_COLOR": "1"}
# Regression definitions using step types the runner has never implemented
# (read16+store, mem_watch, cpu_check). Remove an entry once its test is fixed.
KNOWN_BROKEN_DEFINITIONS = {"b009_mode_reset", "stack_corruption"}


def load_runner():
    spec = importlib.util.spec_from_file_location("oos_test_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def python_step(code, **fields):
    return {"type": "exec", "command": [sys.executable, "-c", code], **fields}


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class RunnerFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.placeholders = {
            "repo": str(ROOT),
            "rom": str(self.dir / "absent.sfc"),
            "sym": str(self.dir / "absent.sym"),
            "hooks": str(self.dir / "hooks.json"),
            "analyzer": str(self.dir / "oracle_analyzer.py"),
        }
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for key in ("OOS_TEST_REQUIRE_ARTIFACTS", "OOS_TEST_REQUIRE_EMULATOR", "OOS_TEST_ROM", "OOS_ANALYZER"):
            os.environ.pop(key, None)
        # Any emulator access in these tests is a bug.
        backend = mock.patch.object(runner, "get_backend", side_effect=AssertionError("emulator backend used"))
        backend.start()
        self.addCleanup(backend.stop)

    def write_test(self, **fields):
        path = self.dir / "fixture.json"
        path.write_text(json.dumps({"name": "Fixture", **fields}))
        return path

    def run_fixture(self, path, **kwargs):
        return runner.run_test(path, quiet=True, placeholders=self.placeholders, **kwargs)


class HostOnlyRunTest(RunnerFixture):
    def test_requires_emulator_false_runs_without_backend(self):
        path = self.write_test(requiresEmulator=False, steps=[python_step("pass")])
        self.assertEqual(self.run_fixture(path), ("passed", None))

    def test_failing_exec_step_fails_the_test(self):
        path = self.write_test(requiresEmulator=False, steps=[python_step("raise SystemExit(3)")])
        status, message = self.run_fixture(path)
        self.assertEqual(status, "failed")
        self.assertIn("Exec exit 3", message)

    def test_comment_step_is_a_no_op(self):
        path = self.write_test(requiresEmulator=False,
                               steps=[{"type": "comment", "description": "note"}, python_step("pass")])
        self.assertEqual(self.run_fixture(path), ("passed", None))

    def test_placeholders_expand_in_exec_arguments(self):
        check = "import sys; raise SystemExit(0 if sys.argv[1].endswith('absent.sfc') else 1)"
        path = self.write_test(requiresEmulator=False, steps=[
            {"type": "exec", "command": [sys.executable, "-c", check, "{rom}"]}])
        self.assertEqual(self.run_fixture(path), ("passed", None))

    def test_unknown_placeholder_fails_instead_of_passing_literally(self):
        path = self.write_test(requiresEmulator=False, steps=[python_step("pass", args=["{nope}"])])
        status, message = self.run_fixture(path)
        self.assertEqual(status, "failed")
        self.assertIn("{nope}", message)

    def test_missing_artifact_skips_only_that_step_and_says_so(self):
        path = self.write_test(requiresEmulator=False, steps=[
            python_step("pass"),
            python_step("raise SystemExit(1)", skipIfMissing=["{rom}"], description="needs ROM"),
        ])
        status, message = self.run_fixture(path)
        self.assertEqual(status, "passed")
        self.assertIn("1 of 2 steps skipped", message)
        self.assertIn("needs ROM", message)
        self.assertIn("absent.sfc", message)

    def test_present_artifact_runs_the_step(self):
        (self.dir / "absent.sfc").write_bytes(b"rom")
        path = self.write_test(requiresEmulator=False, steps=[
            python_step("raise SystemExit(1)", skipIfMissing=["{rom}"])])
        self.assertEqual(self.run_fixture(path)[0], "failed")

    def test_all_steps_skipped_is_a_skip_not_a_pass(self):
        path = self.write_test(requiresEmulator=False, steps=[python_step("pass", skipIfMissing=["{sym}"])])
        status, message = self.run_fixture(path)
        self.assertEqual(status, "skipped")
        self.assertIn("absent.sym", message)

    def test_require_artifacts_turns_a_skip_into_a_failure(self):
        os.environ["OOS_TEST_REQUIRE_ARTIFACTS"] = "1"
        path = self.write_test(requiresEmulator=False, steps=[python_step("pass", skipIfMissing=["{hooks}"])])
        status, message = self.run_fixture(path)
        self.assertEqual(status, "failed")
        self.assertIn("Missing required file", message)


class EmulatorTestWithoutBackendTest(RunnerFixture):
    class OfflineBackend:
        mode = "none"

        def backend_name(self):
            return "none"

        def send(self, cmd, *args, timeout=2.0):
            return False, "No available backend (socket or yaze)"

    def test_default_tests_still_skip_without_a_backend(self):
        path = self.write_test(steps=[{"type": "assert", "address": "$7E0010", "equals": 9}])
        with mock.patch.object(runner, "get_backend", return_value=self.OfflineBackend()):
            status, message = self.run_fixture(path)
            self.assertEqual(status, "skipped")
            self.assertIn("Bridge not connected", message)
            os.environ["OOS_TEST_REQUIRE_EMULATOR"] = "1"
            self.assertEqual(self.run_fixture(path)[0], "failed")


class PlaceholderTest(unittest.TestCase):
    def test_sym_and_hooks_follow_the_selected_rom(self):
        values = runner.build_placeholders(ROOT, "/builds/oos999x.sfc")
        self.assertEqual(values["rom"], "/builds/oos999x.sfc")
        self.assertEqual(values["sym"], "/builds/oos999x.sym")
        self.assertEqual(values["hooks"], "/builds/hooks.json")
        self.assertEqual(values["repo"], str(ROOT))

    def test_rom_precedence_is_argument_then_env_then_default(self):
        with mock.patch.dict(os.environ, {"OOS_TEST_ROM": "Roms/from_env.sfc", "OOS_ANALYZER": "/opt/analyzer.py"}):
            self.assertEqual(runner.build_placeholders(ROOT)["rom"], str(ROOT / "Roms/from_env.sfc"))
            self.assertEqual(runner.build_placeholders(ROOT, "/x.sfc")["rom"], "/x.sfc")
            self.assertEqual(runner.build_placeholders(ROOT)["analyzer"], "/opt/analyzer.py")
        with mock.patch.dict(os.environ):
            os.environ.pop("OOS_TEST_ROM", None)
            self.assertEqual(runner.build_placeholders(ROOT)["rom"], str(ROOT / "Roms/oos168x.sfc"))

    def test_unknown_placeholder_raises(self):
        with self.assertRaises(KeyError):
            runner.expand_placeholders("{typo}", {"rom": "x"})


class DryRunValidationTest(RunnerFixture):
    def dry_run(self, **fields):
        return self.run_fixture(self.write_test(**fields), dry_run=True)

    def test_missing_script_is_an_error(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": ["python3", "Scripts/Validate/no_such_script.py"]}])
        self.assertEqual(status, "failed")
        self.assertIn("script not found: Scripts/Validate/no_such_script.py", message)

    def test_existing_script_and_optional_missing_artifact_pass_with_warning(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": ["python3", "Scripts/Build/verify_feature_flags.py"]},
            {"type": "exec", "command": ["python3", "{analyzer}", "{rom}"],
             "skipIfMissing": ["{analyzer}", "{rom}"]},
        ])
        self.assertEqual(status, "passed", message)
        self.assertIn("would skip: missing", message)
        self.assertIn("oracle_analyzer.py", message)

    def test_unknown_step_type_is_an_error(self):
        status, message = self.dry_run(steps=[{"type": "mem_watch", "address": "$7E01FC"}])
        self.assertEqual(status, "failed")
        self.assertIn("unknown type 'mem_watch'", message)

    def test_unknown_placeholder_in_extra_args_is_an_error(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": [sys.executable, "-c", "pass"],
             "args": ["{missing_argument}"]}])
        self.assertEqual(status, "failed")
        self.assertIn("unknown placeholder {missing_argument}", message)

    def test_unknown_placeholder_in_environment_is_an_error(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": [sys.executable, "-c", "pass"],
             "env": {"ARTIFACT": "{missing_environment}"}}])
        self.assertEqual(status, "failed")
        self.assertIn("unknown placeholder {missing_environment}", message)

    def test_valid_placeholders_in_extra_args_and_environment_pass(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": [sys.executable, "-c", "pass"],
             "args": ["{rom}"], "env": {"ARTIFACT": "{hooks}"}}])
        self.assertEqual((status, message), ("passed", None))

    def test_non_list_extra_args_match_live_rejection(self):
        status, message = self.dry_run(requiresEmulator=False, steps=[
            {"type": "exec", "command": [sys.executable, "-c", "pass"],
             "args": "{rom}"}])
        self.assertEqual(status, "failed")
        self.assertIn("exec args must be a list", message)

    def test_emulator_steps_in_a_host_only_test_are_errors(self):
        status, message = self.dry_run(requiresEmulator=False, saveState={"id": "pre_d6_entrance"},
                                       steps=[{"type": "assert", "address": "$7E0010", "equals": 9}])
        self.assertEqual(status, "failed")
        self.assertIn("step 1: assert needs an emulator", message)
        self.assertIn("saveState needs an emulator", message)

    def test_unknown_save_state_id_is_an_error(self):
        status, message = self.dry_run(saveState={"id": "no_such_state"}, steps=[{"type": "wait", "ms": 1}])
        self.assertEqual(status, "failed")
        self.assertIn("'no_such_state' is not in Data/debug/save_state_library.json", message)

    def test_unknown_save_state_id_with_allow_missing_is_a_warning(self):
        status, message = self.dry_run(saveState={"id": "no_such_state", "allowMissing": True},
                                       steps=[{"type": "wait", "ms": 1}])
        self.assertEqual(status, "passed")
        self.assertIn("will always skip", message)

    def test_catalogued_save_state_id_is_accepted(self):
        status, message = self.dry_run(saveState={"id": "pre_d6_entrance"}, steps=[{"type": "wait", "ms": 1}])
        self.assertEqual(status, "passed", message)
        self.assertNotIn("is not in", message or "")

    def test_save_state_file_presence_is_checked_against_the_catalog(self):
        library = self.dir / "library.json"
        library.write_text(json.dumps({"library_root": "states",
                                       "entries": [{"id": "fixture_state", "path": "fixture.mss"}]}))
        test = {"saveState": {"id": "fixture_state"}, "steps": [{"type": "wait", "ms": 1}]}
        errors, warnings = runner.validate_test_definition(test, self.dir, self.placeholders, library)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["save state file not in this checkout: states/fixture.mss (the run would fail)"])
        (self.dir / "states").mkdir()
        (self.dir / "states/fixture.mss").write_bytes(b"state")
        self.assertEqual(runner.validate_test_definition(test, self.dir, self.placeholders, library), ([], []))

    def test_unknown_id_falls_back_to_the_tests_own_path(self):
        library = self.dir / "library.json"
        library.write_text(json.dumps({"entries": []}))
        (self.dir / "own.mss").write_bytes(b"state")
        resolved = runner.resolve_save_state({"id": "gone", "path": "own.mss"}, self.dir, library)
        self.assertEqual(resolved["kind"], "path")
        self.assertEqual(resolved["path"], self.dir / "own.mss")


class RepositoryDefinitionsTest(unittest.TestCase):
    def test_every_test_definition_validates(self):
        placeholders = runner.build_placeholders(ROOT)
        broken = {}
        for path in sorted((ROOT / "Tests").rglob("*.json")):
            if path.name == "manifest.json":
                continue
            errors, _ = runner.validate_test_definition(json.loads(path.read_text()), ROOT, placeholders)
            if errors:
                broken[path.stem] = errors
        unexpected = {name: errors for name, errors in broken.items() if name not in KNOWN_BROKEN_DEFINITIONS}
        self.assertEqual(unexpected, {})

    def test_lint_pass_is_host_only_and_uses_current_script_paths(self):
        lint = json.loads((ROOT / "Tests/smoke/lint_pass.json").read_text())
        self.assertIs(lint["requiresEmulator"], False)
        scripts = [step["command"][1] for step in lint["steps"]]
        self.assertEqual(scripts, [
            "Scripts/Build/verify_feature_flags.py",
            "Scripts/Validate/verify_hooks_json.py",
            "Scripts/Validate/validate_sprite_registry.py",
            "{analyzer}",
            "Scripts/Build/check_zscream_overlap.py",
        ])
        for step in lint["steps"]:
            self.assertFalse([arg for arg in step["command"] if arg.endswith(".sfc")], step)

    def test_suite_entries_resolve_beside_the_manifest(self):
        manifest = json.loads((ROOT / "Tests/manifest.json").read_text())
        files = runner.get_tests_for_suite(manifest, "smoke", ROOT / "Tests")
        self.assertEqual([p.relative_to(ROOT).as_posix() for p in files],
                         ["Tests/smoke/boot_test.json", "Tests/smoke/basic_transition.json",
                          "Tests/smoke/lint_pass.json"])
        self.assertEqual(runner.missing_suite_entries(manifest, "regression", ROOT / "Tests"), [])


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *args, cwd=ROOT):
        return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=300,
                              env=dict(os.environ, **NO_EMULATOR_ENV))

    def test_smoke_suite_runs_lint_pass_without_an_emulator(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("bash", str(WRAPPER), "smoke", "--no-moe", "-q",
                                  "--rom", str(Path(directory) / "absent.sfc"))
        output = strip_ansi(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("lint_pass: PASS — 3 of 5 steps skipped", output)
        self.assertIn("absent.sfc", output)
        self.assertIn("Results: 1 passed, 0 failed, 2 skipped", output)

    def test_dry_run_reports_manifest_entries_that_do_not_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"suites": {"smoke": {"tests": ["smoke/missing.json"]}}}))
            result = self.run_cli(sys.executable, str(RUNNER), "--suite", "smoke", "--manifest",
                                  str(manifest), "--dry-run", "-q")
        output = strip_ansi(result.stdout)
        self.assertEqual(result.returncode, 1, output)
        self.assertIn("listed in manifest but missing", output)

    def test_wrapper_forwards_dry_run_and_absolute_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "Scripts/Validate/run_regression_tests.sh"
            wrapper.parent.mkdir(parents=True)
            shutil.copyfile(WRAPPER, wrapper)
            (root / "Tests").mkdir()
            (root / "Tests/manifest.json").write_text("{}")
            bindir = root / "bin"
            bindir.mkdir()
            stub = bindir / "python3"
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            stub.chmod(0o755)
            result = subprocess.run(
                ["bash", str(wrapper), "smoke", "--no-moe", "--dry-run", "--rom", "builds/oos9x.sfc"],
                cwd=root, capture_output=True, text=True,
                env=dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"]),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-3:],
                         ["--dry-run", "--rom", str(Path(os.path.realpath(directory)) / "builds/oos9x.sfc")])


class ModuleIsolationScriptsTest(unittest.TestCase):
    def test_shell_script_calls_existing_scripts(self):
        text = (ROOT / "Scripts/Validate/run_module_isolation.sh").read_text()
        commands = re.findall(r"(?:python3 |\./)(Scripts/[\w./-]+\.(?:py|sh))", text)
        self.assertTrue(commands)
        for rel in commands:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_auto_script_dry_run_resolves_repo_paths(self):
        auto = ROOT / "Scripts/Validate/run_module_isolation_auto.py"
        spec = importlib.util.spec_from_file_location("oos_isolation_auto", auto)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.REPO_ROOT, ROOT)
        for path in (module.SET_MODULE_FLAGS, module.BUILD_ROM, module.MESEN2_CLIENT, module.BISECT_SOFTLOCK):
            self.assertTrue(path.is_file(), path)
        result = subprocess.run([sys.executable, str(auto), "--dry-run", "--module", "menu"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"ROM: {ROOT / 'Roms/oos168x.sfc'}", result.stdout)



class StrictRoomScenarioTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rom = self.root / "case.sfc"
        self.state = self.root / "baseline.mss"
        self.record = self.root / "owned.json"
        self.rom.write_bytes(b"immutable rom")
        self.state.write_bytes(b"immutable state")
        self.record.write_text("{}")
        self.path = self.root / "case.json"
        self.case = {"name": "Room probe", "timeout_seconds": 2,
                     "saveState": {"path": "baseline.mss"},
                     "preconditions": [{"address": "$7E0010", "equals": 7}],
                     "steps": [{"type": "assert", "address": "$7E00A0", "size": 2,
                                "equals": 0x104, "description": "Full room identity"}]}
        self.events = []
        self.paused, self.frame, self.frame_tick = False, 100, 1
        self.debugger_initialized = False
        self.control = mock.Mock()
        self.control.send_command.side_effect = self.control_command
        self.control.press_button.side_effect = self.control_input
        self.memory = {0x7E0010: 7, 0x7E00A0: 0x104, 0x7EF36F: 0}
        self.binding = mock.Mock()
        self.binding.rom_path, self.binding.state_path = self.rom, self.state
        self.binding.socket_path = str(self.root / "owned.sock")
        self.binding.session_record, self.binding.owner = self.record, "agent"
        self.binding.pid, self.binding.process_identity = 123, "owned Mesen process"
        self.binding.rom_sha256 = hashlib.sha256(self.rom.read_bytes()).hexdigest()
        self.binding.rom_sha1 = hashlib.sha1(self.rom.read_bytes()).hexdigest()
        self.binding.state_sha256 = hashlib.sha256(self.state.read_bytes()).hexdigest()
        self.binding.verify_local.side_effect = self.verify_local
        self.binding.verify_remote.side_effect = lambda bridge: self.events.append("ROMINFO")
        self.backend = mock.Mock()
        self.backend.send.side_effect = self.send
        for name in ("get_backend", "_prepare_emulator", "run_yabai"):
            patch = mock.patch.object(runner, name, side_effect=AssertionError(f"legacy {name} used"))
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(runner, "_room_binding_create", return_value=self.binding)
        self.create = patch.start()
        self.addCleanup(patch.stop)
        self.real_bridge_factory = runner._new_room_bridge
        self.real_backend_factory = runner._new_room_backend
        patch = mock.patch.object(runner, "_new_room_bridge", side_effect=lambda binding: self.events.append("bridge") or self.control)
        self.bridge = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(runner, "_new_room_backend", side_effect=lambda *args: self.events.append("client") or self.backend)
        self.client = patch.start()
        self.addCleanup(patch.stop)

    def verify_local(self):
        if hashlib.sha256(self.state.read_bytes()).hexdigest() != self.binding.state_sha256:
            raise ValueError("Baseline state changed")

    def control_command(self, command, params=None, **kwargs):
        self.events.append(command)
        if command == "PAUSE":
            self.paused = True
        elif command == "RESUME":
            self.paused = False
        if command == "STATE":
            if not self.paused:
                self.frame += self.frame_tick
            return {"success": True, "data": {"running": True, "paused": self.paused,
                                               "frame": self.frame, "fps": 60}}
        return {"success": True, "data": "OK"}

    def control_input(self, buttons, frames=5, player=0, detach_debugger=True):
        self.events.append(f"INPUT:{buttons}:{frames}")
        self.assertFalse(detach_debugger, "strict input started a delayed detach thread")
        self.assertEqual(player, 0)
        if not self.debugger_initialized:
            self.debugger_initialized = True
            self.paused = False  # The actual first GetDebugger(true) does this.
        return True

    def send(self, command, *args, **kwargs):
        self.events.append(command)
        if command == "loadstate":
            self.assertTrue(self.paused, "baseline load was not frozen")
            self.frame = 1000
            self.memory[0x7EF36F] = 0
            return True, "loaded immutable baseline"
        if command in ("read", "read16"):
            address = runner._parse_addr(args[0])
            return True, f"READ:0x{address:06X}=0x{self.memory.get(address, 0):04X}"
        if command in ("write", "write16"):
            self.assertTrue(self.paused, "fixture applied while game was running")
            self.memory[runner._parse_addr(args[0])] = int(args[1])
        return True, "ok"

    def run_case(self, **kwargs):
        self.path.write_text(json.dumps(self.case))
        return self.invoke(**kwargs)

    def invoke(self, **kwargs):
        return runner.run_room_scenario(self.path, rom=self.rom,
            expected_rom_sha256=self.binding.rom_sha256,
            expected_state_sha256=self.binding.state_sha256,
            socket_path=self.binding.socket_path, session_record=self.record,
            owner="agent", **kwargs)

    def test_dry_run_validates_local_identity_without_any_remote_constructor(self):
        result = self.run_case(dry_run=True)
        self.assertEqual(result["status"], "validated", result)
        self.assertEqual(self.events, [])
        self.bridge.assert_not_called()
        self.client.assert_not_called()
        self.assertEqual(result["identity"]["state_sha256"], self.binding.state_sha256)

    def test_explicit_factories_use_inert_bridge_and_never_ambient_endpoint(self):
        # Exercise the real factories independently from the mocked run boundary.
        bridge_factory = self.real_bridge_factory
        backend_factory = self.real_backend_factory
        inert = object()
        with mock.patch.object(runner, "HAS_SOCKET_BACKEND", True), \
                mock.patch.object(runner, "MesenBridge", create=True, return_value=inert) as bridge_class, \
                mock.patch.object(runner, "OracleDebugClient", create=True) as client_class:
            self.assertIs(bridge_factory(self.binding), inert)
            bridge_class.assert_called_once_with(self.binding.socket_path,
                                                 auto_reconnect=False, max_retries=0)
            backend = backend_factory(self.binding, inert)
            client_class.assert_called_once_with(socket_path=self.binding.socket_path)
            self.assertIs(backend.client.bridge, inert)

    def test_documented_example_has_strict_shape_but_remains_unbound(self):
        example = json.loads((ROOT / "Tests/examples/room_scenario.json").read_text())
        runner._validate_room_case(example)
        state = ROOT / "Tests/examples" / example["saveState"]["path"]
        self.assertFalse(state.exists())

    def test_invalid_local_binding_refuses_before_remote_constructors(self):
        self.create.side_effect = ValueError("owner/endpoint mismatch")
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.assertIn("owner/endpoint mismatch", result["error"])
        self.assertEqual(self.events, [])

    def test_slots_fallbacks_skips_and_arbitrary_commands_refuse_offline(self):
        originals = json.loads(json.dumps(self.case))
        bad_cases = []
        for state in ({"slot": 1}, {"path": "baseline.mss", "id": "fallback"},
                      {"path": "baseline.mss", "allowMissing": True}):
            case = json.loads(json.dumps(originals)); case["saveState"] = state; bad_cases.append(case)
        for kind in ("exec", "command", "write", "write16"):
            case = json.loads(json.dumps(originals)); case["steps"][0]["type"] = kind; bad_cases.append(case)
        case = json.loads(json.dumps(originals)); case["steps"][0]["skipIfMissing"] = ["missing"]; bad_cases.append(case)
        for case in bad_cases:
            with self.subTest(case=case):
                self.case = case
                self.assertEqual(self.run_case()["status"], "failed")
        self.assertEqual(self.events, [])
        self.create.assert_not_called()

    def test_missing_preconditions_or_named_checks_refuse_offline(self):
        self.case["preconditions"] = []
        self.assertEqual(self.run_case()["status"], "failed")
        self.case["preconditions"] = [{"address": "$7E0010", "equals": 7}]
        self.case["steps"][0].pop("description")
        self.assertEqual(self.run_case()["status"], "failed")
        self.assertEqual(self.events, [])

    def test_nonfinite_bounds_and_rom_fixture_writes_refuse_offline(self):
        self.case["timeout_seconds"] = float("inf")
        self.assertEqual(self.run_case()["status"], "failed")
        self.case["timeout_seconds"] = 2
        self.case["fixtures"] = [{"type": "write", "address": "$018000", "value": 0, "description": "unsafe ROM"}]
        self.assertEqual(self.run_case()["status"], "failed")
        self.assertEqual(self.events, [])

    def test_rominfo_is_first_remote_operation_and_mismatch_never_builds_client(self):
        self.binding.verify_remote.side_effect = ValueError("ROMINFO mismatch")
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.client.assert_not_called()
        self.backend.send.assert_not_called()

    def test_post_load_identity_mismatch_stops_before_reads_or_fixtures(self):
        calls = [0]
        def remote(bridge):
            self.events.append("ROMINFO")
            calls[0] += 1
            if calls[0] >= 3:
                raise ValueError("ROM changed after state load")
        self.binding.verify_remote.side_effect = remote
        self.case["fixtures"] = [{"type": "write", "address": "$7EF36F", "value": 1, "description": "one key"}]
        result = self.run_case(repeat=3)
        self.assertEqual(result["status"], "failed")
        self.assertLess(self.events.index("PAUSE"), self.events.index("loadstate"))
        self.assertNotIn("read", self.events)
        self.assertNotIn("write", self.events)
        self.assertNotIn("RESUME", self.events)
        self.assertEqual(result["cleanup"]["status"], "refused_identity")

    def test_repeat_reloads_baseline_and_records_ordered_named_checks(self):
        self.case["fixtures"] = [{"type": "write", "address": "$7EF36F", "value": 1, "description": "one key"}]
        self.case["steps"].append({"type": "assert", "address": "$7EF36F", "equals": 1, "description": "Key fixture applied"})
        result = self.run_case(repeat=2)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(self.events.count("loadstate"), 2)
        self.assertEqual(self.events.count("client"), 1)
        self.assertEqual(self.events.count("write"), 2)
        self.assertEqual([c["name"] for c in result["runs"][1]["checks"]],
                         ["Full room identity", "Key fixture applied"])
        self.assertTrue(result["runs"][0]["fixtures"][0]["passed"])
        self.assertEqual(result["mode"], "fast_state_reset")
        self.assertIn("Fresh-launch", result["gaps"][0])

    def test_fixture_readback_failure_stops_before_actions(self):
        self.case["fixtures"] = [{"type": "write", "address": "$7EF36F", "value": 1, "description": "one key"}]
        def send(command, *args, **kwargs):
            if command == "write":
                self.events.append(command)
                return True, "write ignored by server"
            return self.send(command, *args, **kwargs)
        self.backend.send.side_effect = send
        result = self.run_case(repeat=2)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Fixture readback failed", result["error"])
        self.assertEqual(result["runs"][0]["steps"], [])
        self.assertEqual(self.events.count("loadstate"), 1)

    def test_failed_initial_precondition_prevents_fixture_write(self):
        self.case["preconditions"][0]["equals"] = 9
        self.case["fixtures"] = [{"type": "write", "address": "$7EF36F", "value": 1, "description": "one key"}]
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("write", self.events)
        self.assertFalse(result["runs"][0]["preconditions"][0]["passed"])

    def test_first_failed_check_stops_all_remaining_repeats(self):
        self.case["steps"][0]["equals"] = 0x105
        result = self.run_case(repeat=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["runs"]), 1)
        self.assertEqual(self.events.count("loadstate"), 1)
        self.assertFalse(result["runs"][0]["checks"][0]["passed"])

    def test_bound_state_change_during_case_cannot_start_next_repeat(self):
        def send(command, *args, **kwargs):
            answer = self.send(command, *args, **kwargs)
            if command == "read16":
                self.state.write_bytes(b"changed")
            return answer
        self.backend.send.side_effect = send
        result = self.run_case(repeat=2)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Baseline state changed", result["error"])
        self.assertEqual(self.events.count("loadstate"), 1)

    def test_setup_stays_paused_and_actions_resume_then_cleanup_pauses(self):
        self.case["fixtures"] = [{"type": "write", "address": "$7EF36F", "value": 1, "description": "one key"}]
        result = self.run_case()
        self.assertEqual(result["status"], "passed", result)
        self.assertLess(self.events.index("INPUT::0"), self.events.index("PAUSE"))
        self.assertLess(self.events.index("PAUSE"), self.events.index("loadstate"))
        self.assertLess(self.events.index("write"), self.events.index("RESUME"))
        self.assertEqual(result["runs"][0]["setup_frame_before"], result["runs"][0]["setup_frame_after"])
        self.assertEqual(result["cleanup"]["status"], "paused_input_cleared")
        self.assertTrue(self.paused)

    def test_setup_advancement_refuses_before_actions(self):
        def send(command, *args, **kwargs):
            answer = self.send(command, *args, **kwargs)
            if command == "read":
                self.frame += 1
            return answer
        self.backend.send.side_effect = send
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.assertIn("Room setup advanced", result["error"])
        self.assertNotIn("RESUME", self.events)
        self.assertTrue(self.paused)

    def test_strict_input_observes_frames_and_never_uses_client_fallback(self):
        self.case["steps"].insert(0, {"type": "press", "button": "LEFT", "frames": 3})
        result = self.run_case()
        self.assertEqual(result["status"], "passed", result)
        self.assertNotIn("press", self.events)
        observation = result["runs"][0]["steps"][0]["input_observation"]
        self.assertEqual(observation["requested_input_polls"], 3)
        self.assertGreaterEqual(observation["observed_frame_advance"], 3)
        self.assertIn("INPUT:LEFT:3", self.events)
        self.assertTrue(self.paused)

    def test_input_refusal_does_not_fallback_to_ram(self):
        self.case["steps"].insert(0, {"type": "press", "button": "LEFT", "frames": 1})
        original = self.control_input
        self.control.press_button.side_effect = lambda buttons, **kw: False if buttons else original(buttons, **kw)
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.assertIn("fallback is forbidden", result["error"])
        self.assertNotIn("write", self.events)
        self.assertNotIn("press", self.events)
        self.assertTrue(self.paused)

    def test_condition_size_requires_json_integer_before_admission(self):
        for target in (self.case["preconditions"][0], self.case["steps"][0]):
            with self.subTest(target=target):
                target["size"] = "2"
                result = self.run_case()
                self.assertEqual(result["status"], "failed")
                self.assertIn("address/size", result["error"])
                del target["size"]
        self.assertEqual(self.events, [])
        self.create.assert_not_called()

    def test_button_tokens_reject_internal_spaces_and_send_canonical_edges(self):
        self.case["steps"].insert(0, {"type": "press", "button": "U P", "frames": 1})
        result = self.run_case()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.events, [])
        self.create.assert_not_called()
        self.case["steps"][0]["button"] = " up , a "
        result = self.run_case()
        self.assertEqual(result["status"], "passed", result)
        self.assertIn("INPUT:UP,A:1", self.events)

    def test_input_completion_excludes_frames_before_dispatch_ack(self):
        self.case["steps"].insert(0, {"type": "press", "button": "LEFT", "frames": 3})
        release_frames = []
        original = self.control_input
        def delayed_input(buttons, **kwargs):
            if buttons:
                self.frame += 100  # Running frames elapsed before INPUT acknowledgement.
            elif "INPUT:LEFT:3" in self.events:
                release_frames.append(self.frame)
            return original(buttons, **kwargs)
        self.control.press_button.side_effect = delayed_input
        result = self.run_case()
        self.assertEqual(result["status"], "passed", result)
        observation = result["runs"][0]["steps"][0]["input_observation"]
        self.assertGreaterEqual(observation["frame_after_input_ack"] - observation["frame_before"], 100)
        self.assertGreaterEqual(release_frames[0] - observation["frame_after_input_ack"], 3)
        self.assertEqual(observation["observed_frame_advance"],
                         observation["frame_after"] - observation["frame_after_input_ack"])

    def test_stalled_frame_counter_stops_before_next_action(self):
        self.frame_tick = 0
        self.case["steps"].insert(0, {"type": "press", "button": "LEFT", "frames": 1, "timeout": 0.03})
        result = self.run_case(repeat=2)
        self.assertEqual(result["status"], "failed")
        observation = result["runs"][0]["steps"][0]["input_observation"]
        self.assertEqual(observation["observed_frame_advance"], 0)
        self.assertIn("deadline", observation["error"])
        self.assertEqual(self.events.count("loadstate"), 1)
        self.assertTrue(self.paused)

    def test_duplicate_nonfinite_fractional_and_ambiguous_json_refuse_offline(self):
        baseline = json.loads(json.dumps(self.case))
        payloads = [json.dumps(baseline).replace('"path": "baseline.mss"',
                    '"path": "other.mss", "path": "baseline.mss"')]
        for fields in ({"notes": float("nan")}, {"notes": float("inf")}):
            payloads.append(json.dumps(dict(baseline, **fields)))
        for key, value in (("address", 123.5), ("address", True), ("equals", float("inf")),
                           ("equals", 1.5), ("not_equals", 1)):
            case = json.loads(json.dumps(baseline)); case["steps"][0][key] = value
            payloads.append(json.dumps(case))
        case = json.loads(json.dumps(baseline)); case["steps"][0] = {"type": "press", "button": "RESET", "frames": 1}
        payloads.append(json.dumps(case))
        case = json.loads(json.dumps(baseline)); case["steps"].insert(0, {"type": "wait", "seconds": 1, "ms": 10})
        payloads.append(json.dumps(case))
        for payload in payloads:
            with self.subTest(payload=payload):
                self.path.write_text(payload)
                self.assertEqual(self.invoke()["status"], "failed")
        self.assertEqual(self.events, [])
        self.create.assert_not_called()

    def test_main_strict_receipt_is_clean_json_without_legacy_ui(self):
        self.path.write_text(json.dumps(self.case))
        argv = [str(RUNNER), str(self.path), "--room-scenario", "--rom", str(self.rom),
                "--expected-rom-sha256", self.binding.rom_sha256,
                "--expected-state-sha256", self.binding.state_sha256,
                "--mesen-socket", self.binding.socket_path, "--session-record", str(self.record),
                "--session-owner", "agent", "--dry-run", "--output-format", "json"]
        with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "validated")
        self.bridge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
