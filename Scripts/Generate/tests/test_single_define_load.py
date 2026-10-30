from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

import asm_source  # noqa: E402
import generate_hack_manifest  # noqa: E402
import generate_hooks_json  # noqa: E402

LOADER_OWNERS = (asm_source, generate_hooks_json, generate_hack_manifest)


@contextmanager
def counted_loads(fail: bool = False):
    calls: list[Path] = []
    original = asm_source._load_global_defines

    def load(root: Path) -> dict[str, int]:
        calls.append(Path(root))
        if fail:
            raise ValueError("CURRENT_BUILD_CONTEXT_STALE: generated input differs")
        return original(root)

    with ExitStack() as stack:
        for owner in LOADER_OWNERS:
            stack.enter_context(
                mock.patch.object(owner, "_load_global_defines", load))
        yield calls


class SourceFixture:
    def __init__(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name).resolve()
        self.write("Util/macros.asm", "!ENABLE_PATCH = 1\n")
        self.write("Config/module_flags.asm", "!DISABLE_SPRITES = 0\n")
        self.write("Config/feature_flags.asm", "!ENABLE_EXTRA = 0\n")
        self.write("Oracle_main.asm", 'incsrc "Core/hooks.asm"\n')
        self.write(
            "Core/hooks.asm",
            "macro Patch()\n"
            "org $0288C0 : JSL MacroTarget\n"
            "endmacro\n"
            "org $0080C9 : JML NMI_Hook\n"
            "if !ENABLE_PATCH == 1\n"
            "%Patch()\n"
            "endif\n"
            "if !ENABLE_EXTRA == 1\n"
            "org $028000 : JSL Disabled\n"
            "endif\n",
        )
        rom = self.root / "Roms/oos168x.sfc"
        rom.parent.mkdir(parents=True)
        rom.write_bytes(bytes(0x8000))

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def close(self) -> None:
        self._temp.cleanup()


class SingleDefineLoadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = SourceFixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def run_hooks_main(self, output: Path) -> int:
        argv = ["generate_hooks_json.py", "--root", str(self.fixture.root),
                "-o", str(output), "--rom", "Roms/oos168x.sfc"]
        with mock.patch.object(sys, "argv", argv):
            return generate_hooks_json.main()

    def test_hooks_main_loads_defines_once(self) -> None:
        output = self.fixture.root / "Roms/hooks.json"
        with counted_loads() as calls:
            self.assertEqual(self.run_hooks_main(output), 0)
        self.assertEqual(calls, [self.fixture.root])
        hooks = json.loads(output.read_text())["hooks"]
        self.assertEqual(
            [(hook["address"], hook["name"]) for hook in hooks],
            [("0x0080C9", "NMI_Hook"), ("0x0288C0", "MacroTarget")],
        )

    def test_default_scan_hooks_loads_defines_once(self) -> None:
        with counted_loads() as calls:
            hooks = generate_hooks_json.scan_hooks(self.fixture.root)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(hooks), 2)

    def test_python_scan_manifest_loads_defines_once(self) -> None:
        with counted_loads() as calls:
            manifest = generate_hack_manifest.generate_manifest(
                self.fixture.root)
        self.assertEqual(calls, [self.fixture.root])
        self.assertEqual(manifest["hook_source"]["mode"], "python-scan")

    def test_stale_context_still_refuses_before_output(self) -> None:
        output = self.fixture.root / "Roms/hooks.json"
        with counted_loads(fail=True) as calls:
            self.assertEqual(self.run_hooks_main(output), 1)
            with self.assertRaisesRegex(ValueError, "CURRENT_BUILD_CONTEXT_STALE"):
                generate_hack_manifest.generate_manifest(self.fixture.root)
        self.assertEqual(len(calls), 2)
        self.assertFalse(output.exists())


class ResidentSourceContextTest(unittest.TestCase):
    NAMES = ("LYRA_CURRENT_RESIDENT_ENABLED",
             "LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED")

    def setUp(self) -> None:
        self.fixture = SourceFixture()
        self.addCleanup(self.fixture.close)
        self.environment = mock.patch.dict(os.environ, {asm_source.LYRA_CONTEXT_ENV: "0"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def prepare(self, constants: str, *, current: bool) -> None:
        self.fixture.write(asm_source.LYRA_CONSTANTS, constants)
        self.fixture.write("Data/Generated/lyra_project/prepare.json", json.dumps({
            "kind": "lyra.current_build_prepare.v1" if current else "lyra.ordinary_build_prepare.v1",
            "selected": True,
            "generated_files": {"runtime_constants.asm": hashlib.sha256(constants.encode()).hexdigest()},
            "allocation_granted": True,
            "producer_enforcement_verified": True,
            "runtime_admission": True,
        }))

    def test_unselected_resident_files_do_not_enable_direct_or_entry_scans(self) -> None:
        self.prepare("!LYRA_CURRENT_RESIDENT_ENABLED = 1\n"
                     "!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 1\n", current=True)
        self.fixture.write("Oracle_main.asm", "\n".join(
            f'if not(defined("{name}"))\n!{name} = 0\nendif' for name in self.NAMES)
            + '\nincsrc "Core/hooks.asm"\n')
        self.fixture.write("Core/hooks.asm",
            "if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1\n"
            "org $028000 : JSL Resident\nelse\norg $028000 : JSL Native\nendif\n")
        defines = asm_source._load_global_defines(self.fixture.root)
        self.assertEqual(tuple(defines[name] for name in self.NAMES), (0, 0))
        hooks = generate_hooks_json.scan_hooks(self.fixture.root)
        self.assertEqual([(hook.address, hook.name) for hook in hooks], [(0x028000, "Native")])

    def test_identical_defaults_are_root_only_and_never_authorize_one(self) -> None:
        for name in self.NAMES:
            with self.subTest(name=name):
                self.fixture.write("Oracle_main.asm", f'!{name} = 0\nincsrc "Core/hooks.asm"\n')
                self.fixture.write("Core/hooks.asm", "org $028000 : JSL Native\n")
                asm_source.collect_reachable_asm_sources(self.fixture.root)
                self.fixture.write("Core/hooks.asm", f"!{name} = 0\n")
                with self.assertRaisesRegex(asm_source.SourceGraphError, "reassigns preloaded global define"):
                    asm_source.collect_reachable_asm_sources(self.fixture.root)
                self.fixture.write("Oracle_main.asm", f"!{name} = 1\n")
                with self.assertRaisesRegex(asm_source.SourceGraphError, "reassigns preloaded global define"):
                    asm_source.collect_reachable_asm_sources(self.fixture.root)

    def test_historical_context_cannot_enable_resident_consumers(self) -> None:
        for enabled, resources in ((1, 0), (1, 1), (0, 1), (2, 0)):
            with self.subTest(enabled=enabled, resources=resources):
                self.prepare("!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 1\n"
                    f"!LYRA_CURRENT_RESIDENT_ENABLED = {enabled}\n"
                    f"!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = {resources}\n", current=False)
                with mock.patch.dict(os.environ, {asm_source.LYRA_CONTEXT_ENV: "1"}), \
                     self.assertRaisesRegex(ValueError, "requires current full32 admission"):
                    asm_source._load_global_defines(self.fixture.root)

    def test_forged_current_booleans_still_reach_actual_context_verifier(self) -> None:
        self.prepare("!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 0\n"
            "!LYRA_CURRENT_MODE = 1\n!LYRA_CURRENT_RESIDENT_ENABLED = 1\n"
            "!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 1\n", current=True)
        with mock.patch.object(sys, "path", [str(REPO_ROOT / "Scripts/Build"), *sys.path]), \
             mock.patch.dict(os.environ, {asm_source.LYRA_CONTEXT_ENV: "1"}), \
             self.assertRaisesRegex(ValueError, "Current context uses another source root"):
            asm_source._load_global_defines(self.fixture.root)


class RepositoryEquivalenceTest(unittest.TestCase):
    def test_threaded_defines_match_per_call_loads(self) -> None:
        sources = asm_source.collect_reachable_asm_sources(REPO_ROOT)
        defines = asm_source._load_global_defines(REPO_ROOT)
        self.assertEqual(
            generate_hooks_json.scan_hooks(REPO_ROOT, sources, defines=defines),
            generate_hooks_json.scan_hooks(REPO_ROOT, sources),
        )
        self.assertEqual(
            generate_hooks_json.scan_org_directives(
                REPO_ROOT, sources, defines=defines),
            generate_hooks_json.scan_org_directives(REPO_ROOT, sources),
        )
        self.assertEqual(
            generate_hack_manifest.collect_reachable_asm_sources(
                REPO_ROOT, defines=defines),
            generate_hack_manifest.collect_reachable_asm_sources(REPO_ROOT),
        )


if __name__ == "__main__":
    unittest.main()
