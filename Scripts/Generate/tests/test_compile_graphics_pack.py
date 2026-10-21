from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Graphics"))
import compile_graphics_pack as pack


class GraphicsPackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source"
        self.source.mkdir()
        # Distinct native 4bpp bitplanes, with a gap in target character IDs.
        first, second = bytearray(32), bytearray(32)
        first[0], second[16] = 0x80, 0x80
        (self.source / "first.bin").write_bytes(first)
        (self.source / "second.bin").write_bytes(second)
        self.legacy = {"schema_version": 1, "areas": [{
            "parent_map": 131, "bg_character_base_word": 0x2000,
            "transfers": [
                {"path": "first.bin", "format": "snes4bpp", "byte_count": 32,
                 "vram_word_address": 0x3000},
                {"path": "second.bin", "format": "snes4bpp", "byte_count": 32,
                 "vram_word_address": 0x3020}]}]}
        self.manifest = self.source / "preview.json"
        self.manifest.write_bytes(pack.json_bytes(self.legacy))

    def compile(self, name="compiled", reference=None):
        output = self.root / name
        return output, pack.compile_pack(self.manifest, output, reference)

    def test_sparse_glyphs_bundle_without_zero_filling_and_survive_move(self):
        output, receipt = self.compile()
        catalog, assets = pack.load(output / "catalog.json")
        self.assertEqual(len(assets), 1)
        self.assertEqual(receipt["resource_bytes"], 64)
        profile = catalog["profiles"]["ow-parent-83"]
        self.assertEqual([t["source_offset"] for t in profile["transfers"]], [0, 32])
        expected = pack.validate(*pack.load(self.manifest))
        self.assertEqual(set(expected[131][1]), {256, 258})
        self.assertEqual(pack.validate(catalog, assets), expected)
        self.assertEqual(pack.validate(*pack.load(output / "preview-v1.json")), expected)
        moved = self.root / "moved"
        shutil.copytree(output, moved)
        self.assertEqual(pack.validate(*pack.load(moved / "catalog.json")), expected)
        asm = (moved / "transfer-descriptors.asm").read_text()
        self.assertNotIn("org ", asm)
        self.assertIn("+$0020", asm)
        self.assertIn("dw $3020,$0020", asm)

    def test_shared_profiles_and_resource_identity_recompile_deterministically(self):
        output, _ = self.compile()
        catalog = pack.read_json(output / "catalog.json")
        catalog["bindings"][0]["parent_maps"] = [131, 135]
        (output / "catalog.json").write_bytes(pack.json_bytes(catalog))
        first, second = self.root / "first", self.root / "second"
        pack.compile_pack(output / "catalog.json", first)
        pack.compile_pack(output / "catalog.json", second)
        for path in first.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes())
        resolved = pack.validate(*pack.load(first / "catalog.json"))
        self.assertEqual(resolved[131], resolved[135])

    def test_stale_hash_and_invalid_slice_fail_before_output(self):
        output, _ = self.compile()
        catalog_path = output / "catalog.json"
        valid = pack.read_json(catalog_path)
        resource_id = next(iter(valid["resources"]))
        cases = []
        for value in [-32, 1, 64, 2**31, True, 0.0]:
            bad = json.loads(json.dumps(valid))
            bad["profiles"]["ow-parent-83"]["transfers"][0]["source_offset"] = value
            cases.append(bad)
        for value in ["short", "g" * 64, "0" * 64]:
            bad = json.loads(json.dumps(valid))
            bad["resources"][resource_id]["sha256"] = value
            cases.append(bad)
        for index, bad in enumerate(cases):
            catalog_path.write_bytes(pack.json_bytes(bad))
            destination = self.root / f"bad-{index}"
            with self.assertRaises(pack.PackError):
                pack.compile_pack(catalog_path, destination)
            self.assertFalse(destination.exists())

    def test_duplicate_parent_overlap_invalid_vram_and_json_keys_rejected(self):
        for mutate in [
            lambda d: d["areas"].append(d["areas"][0]),
            lambda d: d["areas"][0]["transfers"][1].update(vram_word_address=0x3000),
            lambda d: d["areas"][0]["transfers"][1].update(vram_word_address=0x3001),
            lambda d: d["areas"][0]["transfers"][1].update(vram_word_address=0x6000),
            lambda d: d["areas"][0].update(parent_map=160),
            lambda d: d["areas"][0].update(parent_map=False),
        ]:
            bad = json.loads(json.dumps(self.legacy))
            mutate(bad)
            self.manifest.write_bytes(pack.json_bytes(bad))
            with self.assertRaises(pack.PackError):
                pack.load(self.manifest)
        self.manifest.write_text('{"schema_version":1,"schema_version":2}')
        with self.assertRaisesRegex(pack.PackError, "duplicate JSON key"):
            pack.load(self.manifest)

    def test_runtime_reference_requires_exact_character_bytes(self):
        output, receipt = self.compile(reference=self.manifest)
        self.assertEqual(receipt["runtime_reference_parent_maps"], [131])
        (self.source / "first.bin").write_bytes(bytes(32))
        with self.assertRaisesRegex(pack.PackError, "runtime reference differs"):
            pack.compile_pack(output / "catalog.json", self.root / "mismatch", self.manifest)
        self.assertFalse((self.root / "mismatch").exists())

    def test_existing_directory_and_portable_path_escape_rejected(self):
        output, _ = self.compile()
        marker = output / "receipt.json"
        before = marker.read_bytes()
        with self.assertRaises(FileExistsError):
            pack.compile_pack(self.manifest, output)
        self.assertEqual(marker.read_bytes(), before)
        document = pack.read_json(output / "catalog.json")
        resource = next(iter(document["resources"].values()))
        resource["path"] = "../source/first.bin"
        (output / "catalog.json").write_bytes(pack.json_bytes(document))
        with self.assertRaisesRegex(pack.PackError, "not portable"):
            pack.load(output / "catalog.json")

    def test_oracle_catalog_retains_existing_docks_and_ship_native_bytes(self):
        repository = Path(__file__).resolve().parents[3]
        catalog_path = repository / "Overworld/graphics_catalog.json"
        reference = repository / "Data/graphics/overworld_graphics_preview.json"
        catalog, assets = pack.load(catalog_path)
        resolved = pack.validate(catalog, assets)
        self.assertEqual(set(resolved), {0x30, 0x32, 0x38, 0x83, 0x87})
        for parent, expected in pack.validate(*pack.load(reference)).items():
            self.assertEqual(resolved[parent], expected)
        self.assertEqual(len(resolved[0x83][1]), 96)
        self.assertEqual(len(resolved[0x87][1]), 64)
        output = self.root / "oracle"
        receipt = pack.compile_pack(catalog_path, output, reference)
        self.assertEqual(receipt["resource_count"], 6)
        self.assertEqual(receipt["resource_bytes"], 31744)


if __name__ == "__main__":
    unittest.main()
