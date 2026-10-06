"""Yaze registry generators and save-state catalog routing (2026-10-06 repo cleanup follow-up).

Generators must read checked-in inputs (Data/planning, Docs/Technical/Sheets, Docs/Dev/Planning), refuse to
publish on missing inputs or an invalid graph, and leave any existing output unchanged when they refuse.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATE = REPO_ROOT / "Scripts" / "Generate"
STORY = GENERATE / "extract_story_events.py"
OVERWORLD = GENERATE / "extract_overworld_registry.py"
if str(GENERATE) not in sys.path:
    sys.path.insert(0, str(GENERATE))  # the exporter imports sibling generators
SENTINEL = '{"sentinel": "prior output must survive a refused run"}\n'


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*argv: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=str(cwd), capture_output=True, text=True)


class StoryEventsTest(unittest.TestCase):
    def test_checked_in_input_regenerates_valid_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "story_events.json"
            result = run(str(STORY), "--output", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            ids = {event["id"] for event in data["events"]}
            self.assertGreaterEqual(len(ids), 10)
            self.assertEqual(len(ids), len(data["events"]), "duplicate event ids")
            for edge in data["edges"]:
                self.assertIn(edge["from"], ids)
                self.assertIn(edge["to"], ids)
            self.assertEqual(data["_meta"]["source"] if "_meta" in data else "Data/planning/Story_Event_Graph.md",
                             "Data/planning/Story_Event_Graph.md")
            self.assertFalse((Path(tmp) / "story_events.json.tmp").exists())

    def test_missing_input_refuses_and_keeps_prior_output(self) -> None:
        module = load(STORY, "story_missing")
        with tempfile.TemporaryDirectory() as tmp:
            empty_root = Path(tmp) / "root"
            empty_root.mkdir()
            out = Path(tmp) / "story_events.json"
            out.write_text(SENTINEL, encoding="utf-8")
            module.find_project_root = lambda: empty_root
            sys_argv = sys.argv
            try:
                sys.argv = [str(STORY), "--output", str(out)]
                with self.assertRaises(SystemExit) as raised:
                    module.main()
            finally:
                sys.argv = sys_argv
            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(out.read_text(encoding="utf-8"), SENTINEL)

    def test_dangling_edges_and_empty_graph_are_invalid(self) -> None:
        module = load(STORY, "story_validate")
        self.assertFalse(module.validate_story_events({"events": [], "edges": []}))
        events = [{"id": "EV-%03d" % i, "name": "event %d" % i} for i in range(1, 12)]
        dangling = {"events": events, "edges": [{"from": "EV-001", "to": "EV-099"}]}
        self.assertFalse(module.validate_story_events(dangling))

    def test_invalid_graph_refuses_and_keeps_prior_output(self) -> None:
        module = load(STORY, "story_invalid")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "story_events.json"
            out.write_text(SENTINEL, encoding="utf-8")
            module.build_story_events = lambda root: {"events": [], "edges": [{"from": "EV-001", "to": "EV-002"}]}
            sys_argv = sys.argv
            try:
                sys.argv = [str(STORY), "--output", str(out)]
                with self.assertRaises(SystemExit) as raised:
                    module.main()
            finally:
                sys.argv = sys_argv
            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(out.read_text(encoding="utf-8"), SENTINEL)


class OverworldRegistryTest(unittest.TestCase):
    def test_checked_in_inputs_regenerate_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overworld.json"
            result = run(str(OVERWORLD), "--output", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreater(len(data["areas"]), 0)

    def test_missing_inputs_refuse_and_keep_prior_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overworld.json"
            out.write_text(SENTINEL, encoding="utf-8")
            result = run(str(OVERWORLD), "--project-root", tmp, "--output", str(out))
            self.assertEqual(result.returncode, 1)
            self.assertIn("required input", result.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), SENTINEL)

    def test_every_required_input_is_checked_in(self) -> None:
        module = load(OVERWORLD, "overworld_inputs")
        tracked = set(subprocess.run(["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True,
                                     text=True, check=True).stdout.splitlines())
        for path in module.required_inputs(REPO_ROOT):
            self.assertIn(str(path.relative_to(REPO_ROOT)), tracked)


class DisposableRefreshTest(unittest.TestCase):
    """export_yazeproj_bundle --refresh-planning runs the generators in the repo it is started from."""

    def test_full_refresh_in_disposable_copy(self) -> None:
        exporter = load(GENERATE / "export_yazeproj_bundle.py", "exporter_refresh")
        tracked = subprocess.run(["git", "ls-files", "Scripts", "Data", "Docs", "CLAUDE.md"], cwd=str(REPO_ROOT),
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        planning = REPO_ROOT / "Docs" / "Dev" / "Planning"
        before = {p.name: p.read_bytes() for p in planning.glob("*.json")}
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            for rel in tracked:
                src = REPO_ROOT / rel
                if src.is_file():
                    dst = copy / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            exporter.refresh_planning_outputs(copy)
            for name in ("overworld.json", "oracle_resource_labels.json", "story_events.json"):
                data = json.loads((copy / "Docs" / "Dev" / "Planning" / name).read_text(encoding="utf-8"))
                self.assertTrue(data, name)
        after = {p.name: p.read_bytes() for p in planning.glob("*.json")}
        self.assertEqual(before, after, "refresh in a copy must not touch the real repo")


class SaveStateCatalogTest(unittest.TestCase):
    def test_named_state_resolves_from_data_debug(self) -> None:
        runner = load(REPO_ROOT / "Scripts" / "Validate" / "test_runner.py", "runner_catalog")
        manifest = REPO_ROOT / "Data" / "debug" / "save_state_library.json"
        self.assertTrue(manifest.is_file())
        resolved = runner.resolve_save_state({"id": "pre_d6_entrance"}, REPO_ROOT, manifest)
        self.assertEqual(resolved["kind"], "path")
        self.assertTrue(str(resolved["path"]).endswith("pre_d6_entrance.mss"))

    def test_consumers_point_at_data_debug(self) -> None:
        for rel in ("Scripts/Validate/test_runner.py", "Scripts/Debug/capture_state.py",
                    "Scripts/Debug/capture_overworld_states.py"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn('"Data" / "debug" / "save_state_library.json"', text, rel)
            self.assertNotIn('"Debugging" / "Testing" / "save_state_library.json"', text, rel)


if __name__ == "__main__":
    unittest.main()
