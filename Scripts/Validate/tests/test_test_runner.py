"""Host-only behaviour of Scripts/Validate/test_runner.py: no emulator, no ROM."""
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
