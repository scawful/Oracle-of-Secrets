"""Runtime backend ABI, sparse transfer equivalence and stale-output guards."""
from pathlib import Path
import copy
import contextlib
import io
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Graphics"))
import compile_graphics_pack as pack
import compile_runtime_graphics as runtime


class CompileRuntimeGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[3]
        cls.catalog_path = cls.root / "Overworld/graphics_catalog.json"
        cls.policy_path = cls.root / "Overworld/graphics_runtime_policy.json"
        cls.catalog, cls.assets = pack.load(cls.catalog_path)
        cls.policy = pack.read_json(cls.policy_path)

    def render(self, catalog=None, assets=None, policy=None):
        return runtime.render(catalog or self.catalog, assets or self.assets,
                              policy or self.policy, self.catalog_path.parent,
                              self.catalog_path.parent)

    def test_fixed_header_and_parent_word_pointer_abi(self):
        text, report = self.render()
        self.assertEqual(runtime.CONSTANTS["HeaderSize"], 22)
        expected = dict(NormalCount=0, NormalPtr=2, CacheMask=4, TransitionMode=5,
                        TransitionStart=6, TransitionEnd=8, TransitionSource=10,
                        StagingCount=13, StagingPtr=15, LateFirst=17, LateEnd=18, LateSource=19)
        for name, offset in expected.items():
            self.assertEqual(runtime.CONSTANTS[name], offset)
            self.assertIn(f"!GfxRT_{name} = ${offset:04X}", text)
        parents = text.split("SharedGraphicsParentProfiles:\n", 1)[1].split("; \"", 1)[0]
        self.assertEqual(len(re.findall(r"^  dw ", parents, re.M)), 160)
        self.assertIn("dw $0000 ; $39", parents)
        self.assertEqual(set(map(int, report["parent_profiles"])), {0x30, 0x32, 0x38, 0x83, 0x87})
        for key in report["enabled_profiles"]:
            body = text.split(runtime.profile_label(key) + ":\n", 1)[1].split("assert pc()-", 1)[0]
            size = 0
            for directive, values in re.findall(r"^  (db|dw|dl) (.+)$", body, re.M):
                size += {"db": 1, "dw": 2, "dl": 3}[directive] * len(values.split(","))
            self.assertEqual(size, 22, key)

    def test_sparse_normal_merge_keeps_exact_pixels_and_staging_holes(self):
        lowered = pack.lower_runtime_policy(self.catalog, self.assets, self.policy)
        records = lowered["profiles"]["stepped-waterfront-fort"]
        merged = runtime.merge_normal(records["normal"])
        self.assertLess(len(merged), 96)
        self.assertEqual(len(records["staging"]), 96)
        before = bytes((i * 37 + i // 32) & 255 for i in range(8192))
        expected, actual = bytearray(before), bytearray(before)
        for r in records["staging"]:
            at = r["wram_address"] - 0x7F0000
            expected[at:at + 32] = self.assets[r["resource_id"]][r["source_offset"]:r["source_offset"] + 32]
        for r in merged:
            at = 2 * (r["vram_word_address"] - 0x2C00)
            count, source = r["byte_count"], r["source_offset"]
            actual[at:at + count] = self.assets[r["resource_id"]][source:source + count]
        self.assertEqual(actual, expected)
        for ch in [302, 303, 318, 319, 328, 331, 332, 347, 348, 392, 436]:
            at = (ch - 0xC0) * 32
            self.assertEqual(actual[at:at + 32], before[at:at + 32])

    def test_merge_refuses_source_destination_and_resource_gaps(self):
        first = dict(resource_id="one", source_offset=0, vram_word_address=0x3000, byte_count=32)
        adjacent = dict(first, source_offset=32, vram_word_address=0x3010)
        self.assertEqual(runtime.merge_normal([first, adjacent]), [dict(first, byte_count=64)])
        for second in [dict(adjacent, source_offset=64), dict(adjacent, vram_word_address=0x3020),
                       dict(adjacent, resource_id="two")]:
            self.assertEqual(runtime.merge_normal([first, second]), [first, second])

    def test_native_high_import_background_contract_refuses_opaque_index8_only_when_declared(self):
        fort = self.catalog["profiles"]["stepped-waterfront-fort"]
        self.assertEqual(fort["authoring_contract"], {
            "schema_version": 1, "kind": "native-high-import",
            "background_pixel_index": 0, "forbidden_opaque_indices": [8]})
        # Recreate the original hardware defect while preserving size, valid
        # catalog SHA and transfer layout: the first pixel becomes opaque8.
        def inject_index8(profile_id):
            catalog, assets = copy.deepcopy(self.catalog), dict(self.assets)
            transfer = catalog["profiles"][profile_id]["transfers"][0]
            rid, at = transfer["resource_id"], transfer.get("source_offset", 0)
            data = bytearray(assets[rid])
            for plane in range(4):
                address = at + (plane // 2) * 16 + plane % 2
                data[address] = (data[address] & 0x7F) | (0x80 if plane == 3 else 0)
            assets[rid] = bytes(data)
            catalog["resources"][rid]["sha256"] = pack.sha256(assets[rid])
            return catalog, assets
        catalog, assets = inject_index8("stepped-waterfront-fort")
        with self.assertRaisesRegex(pack.PackError, "forbidden opaque index 8"):
            self.render(catalog=catalog, assets=assets)
        # Full4bpp art may deliberately use8. Tower has no such contract, so
        # its same pixel mutation is admitted; this is not a global8 ban.
        catalog, assets = inject_index8("sky-d8-tower")
        self.render(catalog=catalog, assets=assets)
        self.render()  # Canonical normalized fort admits transparent0.

    def test_disabled_profiles_emit_no_records_or_payload_dependencies(self):
        policy = copy.deepcopy(self.policy)
        for key in ["stepped-waterfront-fort", "sky-d8-tower"]:
            policy["profiles"][key]["runtime_enabled"] = False
        text, report = self.render(policy=policy)
        self.assertIn("dw $0000 ; $83", text)
        self.assertIn("dw $0000 ; $87", text)
        self.assertEqual(report["new_payload_count"], 0)
        self.assertNotIn("incbin", text)
        self.assertNotIn(runtime.profile_label("sky-d8-tower"), text)
        self.assertNotIn(runtime.profile_label("stepped-waterfront-fort"), text)

    def test_legacy_labels_verified_and_new_payloads_emitted_once(self):
        text, report = self.render()
        self.assertEqual(set(report["aliases"].values()), set(runtime.LEGACY_ALIASES.values()))
        self.assertEqual(report["new_payload_count"], 2)
        self.assertEqual(report["new_payload_bytes"], 5120)
        self.assertEqual(text.count("  incbin "), 2)
        self.assertIn("assert (SharedGraphicsTablesEnd>>16) == !GfxRT_Bank", text)
        self.assertIn("assert ((ShipExtendedGraphics&$FFFF)+$2000) <= $10000", text)
        catalog, assets = copy.deepcopy(self.catalog), dict(self.assets)
        rid = next(k for k, v in catalog["resources"].items() if v["path"] == "gfx/boat.bin")
        assets[rid] = bytes([assets[rid][0] ^ 1]) + assets[rid][1:]
        catalog["resources"][rid]["sha256"] = pack.sha256(assets[rid])
        with self.assertRaisesRegex(pack.PackError, "existing label bytes differ"):
            self.render(catalog=catalog, assets=assets)

    def test_portable_pack_compiles_with_the_same_runtime_records_and_aliases(self):
        canonical, expected = self.render()
        with tempfile.TemporaryDirectory() as directory:
            portable = Path(directory) / "pack"
            pack.compile_pack(self.catalog_path, portable)
            text, report = runtime.compile_tables(portable / "catalog.json", self.policy_path,
                                                  Path(directory) / "runtime.asm")
            # The full portable export changes asset paths only. Assembly
            # descriptors, content labels and bank allocation must stay exact.
            without_paths = lambda value: re.sub(r'^  incbin ".*"$', "  incbin <asset>",
                                                  value, flags=re.M)
            self.assertEqual(without_paths(text), without_paths(canonical))
            self.assertEqual({k: v for k, v in report.items() if k != "generated_sha256"}, expected)
            self.assertEqual(report["new_payload_bytes"], 5120)
            self.assertEqual(report["new_payload_count"], 2)

    def test_portable_changed_bytes_do_not_reuse_a_claimed_legacy_identity(self):
        catalog, assets = copy.deepcopy(self.catalog), dict(self.assets)
        for resource in catalog["resources"].values():
            resource["path"] = f"assets/{resource['sha256']}.4bpp.bin"
        rid = next(key for key in assets if assets[key] == (self.root / "Overworld/gfx/boat.bin").read_bytes())
        # Even a caller retaining the old ID/path cannot claim the ROM label
        # for changed data: validate its new SHA, then emit a separate payload.
        assets[rid] = bytes([assets[rid][0] ^ 1]) + assets[rid][1:]
        catalog["resources"][rid]["sha256"] = pack.sha256(assets[rid])
        text, report = self.render(catalog=catalog, assets=assets)
        self.assertNotIn(rid, report["aliases"])
        self.assertEqual(report["new_payload_count"], 3)
        self.assertEqual(report["new_payload_bytes"], 5120 + len(assets[rid]))
        self.assertIn("SharedGraphicsResource_" + pack.sha256(assets[rid]), text)

    def test_duplicate_portable_resources_share_one_verified_existing_label(self):
        catalog, assets = copy.deepcopy(self.catalog), dict(self.assets)
        old = next(key for key, value in catalog["resources"].items()
                   if value["path"] == "gfx/kalyxo_docks_slot3.bin")
        new = "same-existing-content"
        catalog["resources"][new] = dict(catalog["resources"][old], path="assets/copy.4bpp.bin")
        assets[new] = assets[old]
        catalog["profiles"]["duplicate"] = copy.deepcopy(catalog["profiles"]["loom-docks-approach"])
        catalog["profiles"]["duplicate"]["transfers"][0]["resource_id"] = new
        policy = copy.deepcopy(self.policy)
        policy["profiles"]["duplicate"] = copy.deepcopy(policy["profiles"]["loom-docks-approach"])
        policy["profiles"]["duplicate"]["transition"]["transfer"]["resource_id"] = new
        text, report = self.render(catalog=catalog, assets=assets, policy=policy)
        self.assertEqual(report["aliases"][old], "KalyxoDocksSlot3Graphics")
        self.assertEqual(report["aliases"][new], report["aliases"][old])
        self.assertEqual(report["new_payload_count"], 2)
        self.assertEqual(text.count("  incbin "), 2)

    def test_portable_reuse_refuses_missing_or_ambiguous_vetted_sources(self):
        catalog = copy.deepcopy(self.catalog)
        for resource in catalog["resources"].values():
            resource["path"] = f"assets/{resource['sha256']}.4bpp.bin"
        with tempfile.TemporaryDirectory() as directory:
            legacy_root = Path(directory)
            def render():
                return runtime.render(catalog, self.assets, self.policy,
                                      self.catalog_path.parent, self.catalog_path.parent,
                                      legacy_root=legacy_root)
            with self.assertRaisesRegex(pack.PackError, "cannot verify existing label bytes"):
                render()
            for path in runtime.LEGACY_ALIASES:
                destination = legacy_root / "Overworld" / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((self.root / "Overworld" / path).read_bytes())
            (legacy_root / "Overworld/gfx/boat2.bin").write_bytes(
                (legacy_root / "Overworld/gfx/boat.bin").read_bytes())
            with self.assertRaisesRegex(pack.PackError, "ambiguous existing label bytes"):
                render()

    def test_same_unknown_content_uses_one_payload_and_bank_overflow_refuses(self):
        catalog, assets = copy.deepcopy(self.catalog), dict(self.assets)
        old = next(k for k, v in catalog["resources"].items() if v["path"].endswith("tower_87.bin"))
        new = "duplicate-content"
        catalog["resources"][new] = dict(catalog["resources"][old], path="gfx/copy.bin")
        assets[new] = assets[old]
        catalog["profiles"]["duplicate"] = copy.deepcopy(catalog["profiles"]["sky-d8-tower"])
        catalog["profiles"]["duplicate"]["transfers"][0]["resource_id"] = new
        policy = copy.deepcopy(self.policy)
        policy["profiles"]["duplicate"] = copy.deepcopy(policy["profiles"]["sky-d8-tower"])
        policy["profiles"]["duplicate"]["transition"]["transfer"]["resource_id"] = new
        text, report = self.render(catalog=catalog, assets=assets, policy=policy)
        self.assertEqual(text.count("  incbin "), 2)
        self.assertEqual(report["new_payload_count"], 2)
        assets[old] = bytes(0x8000)
        catalog["resources"][old].update(sha256=pack.sha256(assets[old]), byte_count=0x8000)
        with self.assertRaisesRegex(pack.PackError, "exceed bank"):
            self.render(catalog=catalog, assets=assets, policy=policy)

    def test_check_mode_refuses_stale_without_writing_and_write_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runtime.asm"
            args = ["--catalog", str(self.catalog_path), "--policy", str(self.policy_path), "--output", str(output)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runtime.main(args + ["--write"]), 0)
                original = output.read_bytes()
                self.assertEqual(runtime.main(args + ["--check"]), 0)
                output.write_bytes(original + b"; stale\n")
                stale = output.read_bytes()
                self.assertEqual(runtime.main(args + ["--check"]), 1)
                self.assertEqual(output.read_bytes(), stale)
                self.assertEqual(runtime.main(args + ["--write"]), 0)
                self.assertEqual(output.read_bytes(), original)

    def test_committed_tables_are_current_and_inputs_are_not_written(self):
        protected = [self.catalog_path, self.policy_path] + [self.catalog_path.parent / r["path"]
                     for r in self.catalog["resources"].values()]
        before = {p: p.read_bytes() for p in protected}
        output = self.root / "Overworld/graphics_runtime_tables.asm"
        text, _ = runtime.compile_tables(self.catalog_path, self.policy_path, output)
        self.assertEqual(output.read_text(), text)
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        with self.assertRaisesRegex(pack.PackError, "overlaps"):
            runtime.compile_tables(self.catalog_path, self.policy_path, self.catalog_path)

    def test_external_catalog_cannot_overwrite_repository_canonical_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            catalog_path, policy_path = external / "catalog.json", external / "policy.json"
            catalog_path.write_bytes(pack.json_bytes(self.catalog))
            policy_path.write_bytes(pack.json_bytes(self.policy))
            for rid, resource in self.catalog["resources"].items():
                path = external / resource["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.assets[rid])
            protected = [self.catalog_path, self.policy_path] + [self.catalog_path.parent / r["path"]
                         for r in self.catalog["resources"].values()]
            before = {path: path.read_bytes() for path in protected}
            for output in protected:
                with self.subTest(output=output), self.assertRaisesRegex(pack.PackError, "overlaps"):
                    runtime.compile_tables(catalog_path, policy_path, output)
            self.assertEqual({path: path.read_bytes() for path in protected}, before)


if __name__ == "__main__":
    unittest.main()
