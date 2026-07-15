from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from Scripts.Agent import oracle_agent_gateway as gateway


class OracleAgentGatewayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def touch(self, relative: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_actions_use_categorized_paths(self) -> None:
        tests_dir = self.root / "Tests"
        tests_dir.mkdir()
        build = self.touch("Scripts/Build/build_rom.sh")
        export = self.touch("Scripts/Generate/export_symbols.py")
        regression = self.touch("Scripts/Validate/run_regression_tests.sh")
        service = self.touch("Scripts/yaze_service.sh")
        mesen = self.touch("Scripts/Mesen2/mesen2_client.py")
        base = self.touch("Roms/oos168.sfc")
        project = self.touch("Oracle-of-Secrets.yaze")

        spawned: list[list[str]] = []

        def capture_spawn(cmd: list[str], cwd: Path | None = None) -> dict[str, object]:
            spawned.append(cmd)
            return {"ok": True, "cmd": cmd, "cwd": cwd}

        with (
            mock.patch.object(gateway, "_resolve_oos_root", return_value=self.root),
            mock.patch.object(gateway, "_spawn", side_effect=capture_spawn),
            mock.patch.object(gateway, "_yaze_allowed", return_value=True),
            mock.patch.object(gateway, "_open_path", return_value={"ok": True}) as open_path,
        ):
            gateway.action_open_tests_dir({})
            self.assertEqual(open_path.call_args.args[0], tests_dir)

            gateway.action_build_rom({"version": "168"})
            self.assertIn(str(build), spawned[-1])

            gateway.action_export_symbols({"sync": False})
            self.assertIn(str(export), spawned[-1])

            gateway.action_run_smoke_tests({})
            self.assertIn(str(regression), spawned[-1])

            gateway.action_run_test_suite({"suite": "full"})
            self.assertIn(str(regression), spawned[-1])

            gateway.action_yaze_start({})
            self.assertEqual(spawned[-1], [str(service), "start", "--rom", str(base)])

            gateway.action_yaze_gui_toggle({})
            self.assertEqual(
                spawned[-1], [str(service), "gui-toggle", "--rom", str(project)]
            )

        with (
            mock.patch.object(gateway, "_resolve_oos_root", return_value=self.root),
            mock.patch.object(gateway, "_run", return_value={"ok": True}) as run,
        ):
            gateway._run_mesen2_cli(["diagnostics", "--json"])
            self.assertEqual(
                run.call_args.args[0],
                [gateway.sys.executable, str(mesen), "diagnostics", "--json"],
            )

    def test_canonical_base_precedes_patched_default(self) -> None:
        base = self.touch("Roms/oos168.sfc")
        patched = self.touch("Roms/oos168x.sfc")

        self.assertEqual(gateway._resolve_default_rom(self.root), base)
        self.assertEqual(gateway._resolve_default_rom(self.root, skip_patched=True), base)
        self.assertEqual(gateway._resolve_default_rom(self.root, prefer="test"), patched)

    def test_editor_selection_fails_closed_without_known_base(self) -> None:
        self.touch("Scripts/yaze_service.sh")
        for name in (
            "oos168x.sfc",
            "oos999x.sfc",
            "oos-patched.sfc",
            "Zelda_OracleOfSecrets.sfc",
            "mystery.sfc",
        ):
            self.touch(f"Roms/{name}")

        self.assertIsNone(gateway._resolve_default_rom(self.root, skip_patched=True))
        with (
            mock.patch.object(gateway, "_resolve_oos_root", return_value=self.root),
            mock.patch.object(gateway, "_yaze_allowed", return_value=True),
            mock.patch.object(gateway, "_spawn") as spawn,
        ):
            result = gateway.action_yaze_gui_toggle({})

        self.assertFalse(result["ok"])
        self.assertIn("No safe yaze project or base ROM", result["error"])
        spawn.assert_not_called()


class YazeServiceSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.service = cls.repo_root / "Scripts/yaze_service.sh"
        cls.true_bin = shutil.which("true")
        if cls.true_bin is None:
            raise unittest.SkipTest("true executable not found")

    def run_service(self, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "YAZE_GUI_PID_FILE": str(Path(tmp) / "gui.pid"),
                    "YAZE_GUI_LOG_FILE": str(Path(tmp) / "gui.log"),
                }
            )
            return subprocess.run(
                ["bash", str(self.service), *args, "--gui-bin", self.true_bin],
                cwd=self.repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_gui_default_uses_project_not_patched_output(self) -> None:
        result = self.run_service("gui-start")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Oracle-of-Secrets.yaze", result.stdout)
        self.assertNotIn("oos168x.sfc", result.stdout)

    def test_gui_rejects_patched_rom_without_named_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patched = Path(tmp) / "oos999x.sfc"
            patched.touch()

            result = self.run_service("gui-start", "--rom", str(patched))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing patched GUI edit target", result.stderr)
        self.assertIn("--allow-patched-gui-rom", result.stderr)

    def test_named_override_allows_patched_gui_rom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patched = Path(tmp) / "oos999x.sfc"
            patched.touch()

            result = self.run_service(
                "gui-start",
                "--rom",
                str(patched),
                "--allow-patched-gui-rom",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(patched), result.stdout)


if __name__ == "__main__":
    unittest.main()
