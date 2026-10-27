"""Strict private-output guards and legacy compatibility, using 64-byte fixtures."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "apply_rom_byte_patch", Path(__file__).resolve().parents[1] / "apply_rom_byte_patch.py")
patcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patcher)


class ApplyRomBytePatchTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="byte-patch-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source, self.input, self.output = (
            self.root / name for name in ("source", "input", "private"))
        for directory in (self.source, self.input, self.output):
            directory.mkdir(mode=0o700)
        self.original = bytes(range(64))
        self.candidate = bytearray(self.original)
        self.candidate[5], self.candidate[32] = 0xF5, 0xF4
        self.candidate = bytes(self.candidate)
        self.rom = self.input / "input.bin"
        self.rom.write_bytes(self.original)
        self.head, self.diff = "a" * 40, b""
        self.paired = {}
        for relative in patcher.PAIRED_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
            self.paired[relative] = path.read_bytes()
        self.spec = dict(
            schema_version=2, write_policy="private_output_only", base_size=64,
            base_sha256=patcher.sha256(self.original),
            result_sha256=patcher.sha256(self.candidate), changed_bytes=2,
            source=dict(head=self.head, diff_sha256=patcher.sha256(self.diff),
                        files={rel: patcher.sha256(data) for rel, data in self.paired.items()}),
            private_edits=[dict(id="first", pc="0x05", snes="$008005", before="05", after="F5"),
                           dict(id="second", pc="0x20", snes="$008020", before="20", after="F4")],
            preserve_ranges=[dict(id="untouched", pc_start="0x00", pc_end_exclusive="0x05",
                                  sha256=patcher.sha256(self.original[:5]))])
        self.args = argparse.Namespace(
            patch=self.input / "patch.json", rom=self.rom, source_root=self.source,
            output_root=self.output, output=self.output / "result.bin",
            write_output=False, apply=False)
        self.args.patch.write_text(json.dumps(self.spec))
        git = mock.patch.object(patcher.subprocess, "check_output", side_effect=self.git)
        self.addCleanup(git.stop)
        git.start()

    def git(self, command, **kwargs):
        self.assertEqual(command[:3], ["git", "-C", str(self.args.source_root)])
        if command[3:] == ["rev-parse", "HEAD"]:
            return self.head + "\n"
        if command[3:] == ["diff", "--binary", "HEAD"]:
            return self.diff
        if command[3:] == ["rev-parse", "--git-common-dir"]:
            return str(self.root / "main" / ".git") + "\n"
        self.fail(f"Unexpected subprocess: {command}")

    def cli(self, *flags, strict=False, spec=None):
        self.args.patch.write_text(json.dumps(self.spec if spec is None else spec))
        argv = [str(patcher.__file__), str(self.args.patch), "--rom", str(self.rom)]
        if strict:
            for option in ("output", "output_root", "source_root"):
                argv.extend(("--" + option.replace("_", "-"), str(getattr(self.args, option))))
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(patcher.sys, "argv", [*argv, *flags]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            result = patcher.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_default_strict_dry_run_and_exact_in_memory_readback(self):
        candidate, report = patcher.strict_plan(self.args, self.spec)
        self.assertEqual(candidate, self.candidate)
        self.assertEqual({i for i, pair in enumerate(zip(self.original, candidate))
                          if pair[0] != pair[1]}, {5, 32})
        self.assertEqual([edit["in_memory_readback"] for edit in report["edits"]], ["f5", "f4"])
        code, stdout, stderr = self.cli(strict=True)
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), report)
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["written"])
        self.assertFalse(self.args.output.exists())
        self.assertEqual(self.rom.read_bytes(), self.original)

    def test_explicit_private_output_readback_preserves_inputs(self):
        code, stdout, stderr = self.cli("--write-output", strict=True)
        report = json.loads(stdout)
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue(report["written"])
        self.assertFalse(report["dry_run"])
        self.assertEqual(report["output_readback_sha256"], patcher.sha256(self.candidate))
        self.assertEqual(self.args.output.read_bytes(), self.candidate)
        self.assertEqual(self.args.output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.rom.read_bytes(), self.original)
        for rel, data in self.paired.items():
            self.assertEqual((self.source / rel).read_bytes(), data)

    def test_full_base_identity_is_required_despite_matching_preimages(self):
        changed = bytearray(self.original)
        changed[63] ^= 1
        self.rom.write_bytes(changed)
        self.assertEqual(bytes(changed[i] for i in (5, 32)), b"\x05\x20")
        with self.assertRaisesRegex(ValueError, "Exact base size/SHA256"):
            patcher.strict_plan(self.args, self.spec)
        self.assertEqual(self.rom.read_bytes(), changed)
        self.assertFalse(self.args.output.exists())

    def test_result_size_hash_and_preserved_range_guards(self):
        cases = [
            ("size", {"base_size": 63}, "base size/SHA256"),
            ("short hash", {"base_sha256": self.spec["base_sha256"][:12]}, "full lowercase"),
            ("result", {"result_sha256": "0" * 64}, "result SHA256"),
            ("count", {"changed_bytes": 1}, "changed-byte set/count"),
            ("preserved hash", {"preserve_ranges": [dict(id="bad", pc_start="0", pc_end_exclusive="5",
                                                         sha256="0" * 64)]}, "Preserved range differs"),
            ("preserved bounds", {"preserve_ranges": [dict(id="bad", pc_start="0", pc_end_exclusive="41",
                                                           sha256="0" * 64)]}, "outside the input"),
        ]
        for name, changes, error in cases:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, error):
                patcher.strict_plan(self.args, dict(self.spec, **changes))
        self.assertEqual(self.rom.read_bytes(), self.original)

    def test_invalid_edit_spans_addresses_and_preimages_refuse(self):
        first = self.spec["private_edits"][0]
        cases = [
            ("empty list", [], "must not be empty"),
            ("empty bytes", [dict(first, before="", after="")], "empty, unequal-length"),
            ("unequal length", [dict(first, after="F500")], "empty, unequal-length"),
            ("negative", [dict(first, pc="-1")], "outside the input"),
            ("out of bounds", [dict(first, pc="3F", before="3F40", after="F5F4")], "outside the input"),
            ("overlap", [first, dict(first)], "overlap"),
            ("address mismatch", [dict(first, snes="$008006")], "addresses disagree"),
            ("low-half address", [dict(first, snes="$000005")], "LoROM address"),
            ("over-24-bit address", [dict(first, snes="$1008005")], "LoROM address"),
            ("wrong before", [dict(first, before="06")], "Exact before bytes differ"),
            ("unchanged edit", [dict(first, after="05")], "changed-byte set/count"),
        ]
        cases.extend((f"reserved bank {bank}", [dict(first, snes=f"${bank}8005")], "LoROM address")
                     for bank in ("7E", "7F", "FE", "FF"))
        for name, edits, error in cases:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, error):
                patcher.strict_plan(self.args, dict(self.spec, private_edits=edits))
        self.assertEqual(self.rom.read_bytes(), self.original)
        self.assertFalse(self.args.output.exists())

    def test_strict_already_after_is_not_legacy_idempotence(self):
        self.rom.write_bytes(self.candidate)
        spec = dict(self.spec, base_sha256=patcher.sha256(self.candidate))
        with self.assertRaisesRegex(ValueError, "Exact before bytes differ"):
            patcher.strict_plan(self.args, spec)
        self.assertEqual(self.rom.read_bytes(), self.candidate)

    def test_source_head_complete_diff_and_paired_file_binding(self):
        for name in ("head", "diff", "paired bytes", "paired names", "paired symlink"):
            with self.subTest(name=name):
                spec = copy.deepcopy(self.spec)
                relative = patcher.PAIRED_FILES[0]
                path = self.source / relative
                if name == "head":
                    spec["source"]["head"] = "b" * 40
                elif name == "diff":
                    spec["source"]["diff_sha256"] = patcher.sha256(b"stale diff")
                elif name == "paired bytes":
                    path.write_bytes(b"modified source")
                elif name == "paired names":
                    spec["source"]["files"]["extra"] = "0" * 64
                else:
                    target = self.root / "paired-target.bin"
                    target.write_bytes(self.paired[relative])
                    path.unlink()
                    path.symlink_to(target)
                try:
                    with self.assertRaisesRegex(ValueError, "source HEAD|source hash|source binding"):
                        patcher.strict_plan(self.args, spec)
                    self.assertFalse(self.args.output.exists())
                finally:
                    if path.is_symlink():
                        path.unlink()
                    path.write_bytes(self.paired[relative])

    def test_private_root_cannot_overlap_source_input_main_or_broad_ancestor(self):
        for name, root in (("source", self.source / "out"), ("input", self.input / "out"),
                           ("main checkout", self.root / "main" / "out"), ("broad root", self.root)):
            with self.subTest(name=name):
                root.mkdir(mode=0o700, parents=True, exist_ok=True)
                args = argparse.Namespace(**vars(self.args))
                args.output_root, args.output = root, root / "result.bin"
                with self.assertRaisesRegex(ValueError, "overlaps an input or source"):
                    patcher.strict_plan(args, self.spec)
        # Exercise the script's source-root protection without writing in its real checkout.
        installed = self.root / "installed"
        installed.mkdir(mode=0o700)
        args = argparse.Namespace(**dict(vars(self.args), output_root=installed,
                                        output=installed / "result.bin"))
        with mock.patch.object(patcher, "__file__", str(installed / "Scripts/Build/tool.py")), \
                self.assertRaisesRegex(ValueError, "overlaps an input or source"):
            patcher.strict_plan(args, self.spec)

    def test_absolute_direct_child_and_mode0700_are_required(self):
        for field in ("source_root", "output_root", "output"):
            with self.subTest(relative=field):
                args = argparse.Namespace(**dict(vars(self.args), **{field: Path("relative")}))
                with self.assertRaisesRegex(ValueError, "must be absolute"):
                    patcher.strict_paths(args, self.root / "main")
        args = argparse.Namespace(**dict(vars(self.args), output=self.output / "nested/result.bin"))
        with self.assertRaisesRegex(ValueError, "direct child"):
            patcher.strict_plan(args, self.spec)
        self.output.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "mode0700"):
            patcher.strict_plan(self.args, self.spec)

    def test_symlink_output_root_or_parent_is_refused(self):
        link = self.root / "linked-private"
        link.symlink_to(self.output, target_is_directory=True)
        for name, root in (("root", link), ("parent", link / "nested")):
            with self.subTest(name=name):
                if name == "parent":
                    (self.output / "nested").mkdir(mode=0o700)
                args = argparse.Namespace(**dict(vars(self.args), output_root=root,
                                                output=root / "result.bin"))
                with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                    patcher.strict_plan(args, self.spec)

    def test_existing_dangling_hardlink_and_alias_destinations_refuse(self):
        for name in ("existing", "dangling", "hardlink", "symlink input", "input alias"):
            with self.subTest(name=name):
                args = argparse.Namespace(**vars(self.args))
                if name == "existing":
                    args.output.write_bytes(b"retained")
                elif name == "dangling":
                    args.output.symlink_to(self.root / "absent")
                elif name == "hardlink":
                    os.link(self.rom, args.output)
                elif name == "symlink input":
                    args.output.symlink_to(self.rom)
                else:
                    args.output_root, args.output = self.input, self.rom
                try:
                    with self.assertRaises(ValueError):
                        patcher.strict_plan(args, self.spec)
                    self.assertEqual(self.rom.read_bytes(), self.original)
                    if name == "existing":
                        self.assertEqual(args.output.read_bytes(), b"retained")
                finally:
                    if name != "input alias":
                        args.output.unlink()

    def test_exclusive_create_race_cannot_replace_a_new_destination(self):
        self.args.write_output = True
        original_open = os.open
        creation_flags = []

        def raced_open(path, flags, *args, **kwargs):
            if flags & os.O_CREAT:
                creation_flags.append(flags)
                self.args.output.write_bytes(b"other creator")
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(patcher.os, "open", side_effect=raced_open), \
                self.assertRaises(FileExistsError), redirect_stdout(io.StringIO()):
            patcher.strict_output(self.args, self.spec)
        self.assertEqual(len(creation_flags), 1)
        self.assertTrue(creation_flags[0] & os.O_EXCL)
        self.assertTrue(creation_flags[0] & os.O_NOFOLLOW)
        self.assertEqual(self.args.output.read_bytes(), b"other creator")
        self.assertEqual(self.rom.read_bytes(), self.original)

    def test_selected_recipe_cannot_change_before_output_planning(self):
        for scenario in ("CLI byte change", "direct cached spec"):
            with self.subTest(scenario=scenario):
                self.args.patch.write_text(json.dumps(self.spec))
                if scenario == "CLI byte change":
                    source_state = patcher.source_state

                    def mutate_recipe_after_source_check(root, expected):
                        state = source_state(root, expected)
                        self.args.patch.write_bytes(self.args.patch.read_bytes() + b"\n")
                        return state

                    with mock.patch.object(patcher, "source_state", side_effect=mutate_recipe_after_source_check) as checked:
                        code, stdout, stderr = self.cli("--write-output", strict=True)
                    self.assertEqual(checked.call_count, 1)
                    self.assertEqual((code, stdout), (1, ""))
                    self.assertIn("Recipe changed after selection", stderr)
                    self.assertEqual(json.loads(self.args.patch.read_bytes()), self.spec)
                else:
                    self.args.patch.write_text(json.dumps(dict(self.spec, selection="different recipe")))
                    with self.assertRaisesRegex(ValueError, "Recipe changed after selection"):
                        patcher.strict_plan(self.args, self.spec)
                self.assertFalse(self.args.output.exists())
                self.assertEqual(self.rom.read_bytes(), self.original)

    def test_schema2_apply_and_unsupported_schema_cannot_fall_through(self):
        for policy in ("private_output_only", None, "private_outpt_only"):
            with self.subTest(policy=policy):
                spec = copy.deepcopy(self.spec)
                if policy is None:
                    spec.pop("write_policy")
                else:
                    spec["write_policy"] = policy
                with self.assertRaises(SystemExit) as error:
                    self.cli("--apply", spec=spec)
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(self.rom.read_bytes(), self.original)
        for version in (0, 3, "2", 2.0, True, None):
            with self.subTest(version=version), self.assertRaises(SystemExit) as error:
                self.cli("--apply", spec=dict(self.spec, schema_version=version))
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(self.rom.read_bytes(), self.original)

    def test_schema2_refuses_legacy_consumer_and_dual_edit_keys(self):
        self.assertNotIn("edits", self.spec)
        dual = dict(self.spec, edits=self.spec["private_edits"])
        with self.assertRaisesRegex(ValueError, "without a legacy edits key"):
            patcher.strict_plan(self.args, dual)
        # Exact maintained consumer from 8b004e65, available without Git history.
        fixture = Path(__file__).with_name("fixtures") / "apply_rom_byte_patch_legacy_8b004e65.py"
        source = fixture.read_bytes()
        self.assertEqual(patcher.sha256(source),
                         "54bc05d0e186f77f23af3e58fc73b3783883d91511dff8b53e1daf572c1d0ef5")
        legacy = {"__name__": "legacy_byte_patch"}
        exec(compile(source, str(fixture), "exec"), legacy)
        argv = ["legacy_byte_patch", str(self.args.patch), "--rom", str(self.rom), "--apply"]
        with mock.patch.object(patcher.sys, "argv", argv), redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(KeyError, "edits"):
            legacy["main"]()
        self.assertEqual(self.rom.read_bytes(), self.original)
        self.assertFalse(self.args.output.exists())

    def test_legacy_default_apply_idempotence_and_failure_status_are_unchanged(self):
        spec = dict(edits=self.spec["private_edits"])
        code, stdout, _ = self.cli(spec=spec)
        self.assertEqual(code, 0)
        self.assertIn("dry run: 2 edit(s) pending", stdout)
        self.assertEqual(self.rom.read_bytes(), self.original)
        code, stdout, _ = self.cli("--apply", spec=spec)
        self.assertEqual(code, 0)
        self.assertIn("wrote 2 edit(s)", stdout)
        self.assertEqual(self.rom.read_bytes(), self.candidate)
        code, stdout, _ = self.cli("--apply", spec=spec)
        self.assertEqual(code, 0)
        self.assertIn("already F5", stdout)
        self.assertIn("wrote 0 edit(s)", stdout)
        self.assertEqual(self.rom.read_bytes(), self.candidate)
        self.rom.write_bytes(b"\xFF" * 64)
        code, stdout, _ = self.cli("--apply", spec=spec)
        self.assertEqual(code, 1)
        self.assertIn("aborted: nothing written", stdout)
        self.assertEqual(self.rom.read_bytes(), b"\xFF" * 64)


if __name__ == "__main__":
    unittest.main()
