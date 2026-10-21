"""Data-only phase contracts for the existing runtime and proposed sparse art."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Graphics"))
import compile_graphics_pack as pack


class GraphicsRuntimePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[3]
        cls.catalog_path = cls.root / "Overworld/graphics_catalog.json"
        cls.policy_path = cls.root / "Overworld/graphics_runtime_policy.json"
        cls.catalog, cls.assets = pack.load(cls.catalog_path)
        cls.policy = pack.read_json(cls.policy_path)

    def lower(self, catalog=None, policy=None):
        return pack.lower_runtime_policy(catalog or self.catalog, self.assets,
                                         policy or self.policy)

    def test_admitted_runtime_phases_keep_exact_contract_for_all_five_profiles(self):
        data = self.lower()
        p = data["profiles"]
        self.assertEqual(data["abi"], dict(outdoor_guard="$1B==0", parent="$8A",
                         normal="A8/XY8", transition="A16/XY8; preserve X/Y",
                         late="A8/XY16; preserve X/Y"))
        for name in ("kalyxo-docks", "dragon-ship"):
            self.assertEqual(p[name]["transition"]["mode"], "source_range")
            self.assertEqual(p[name]["transition"]["target_start_word"], 0x2C00)
            self.assertEqual(p[name]["transition"]["target_end_word"], 0x3C00)
            self.assertEqual(p[name]["cache_slot_mask"], 0x78)
        loom = p["loom-docks-approach"]
        self.assertEqual(loom["transition"]["mode"], "source_start")
        self.assertEqual(loom["transition"]["transfer"]["byte_count"], 2048)
        self.assertEqual(loom["transition"]["target_start_word"], 0x2C00)
        self.assertEqual(loom["cache_slot_mask"], 0x08)
        self.assertEqual(len(p["dragon-ship"]["normal"]), 2)
        self.assertEqual(p["sky-d8-tower"]["transition"]["mode"], "source_start")
        self.assertEqual(p["sky-d8-tower"]["transition"]["target_start_word"], 0x3800)
        self.assertEqual(p["sky-d8-tower"]["cache_slot_mask"], 0x40)
        self.assertTrue(p["sky-d8-tower"]["runtime_enabled"])
        self.assertTrue(p["stepped-waterfront-fort"]["runtime_enabled"])
        self.assertEqual({int(parent) for parent, b in data["parents"].items()
                          if b["runtime_enabled"]}, {0x30, 0x32, 0x38, 0x83, 0x87})
        self.assertNotIn("57", data["parents"])  # child $39 inherits parent $38

    def test_late_chunks_reconstruct_exact_ship_resource_without_extra_bytes(self):
        late = self.lower()["profiles"]["dragon-ship"]["late"]
        chunks = late["chunks"]
        self.assertEqual([c["step"] for c in chunks], list(range(0x50, 0x60)))
        self.assertEqual([c["source_offset"] for c in chunks], list(range(0, 8192, 512)))
        self.assertEqual([c["vram_word_address"] for c in chunks], list(range(0x5000, 0x6000, 256)))
        self.assertEqual({c["byte_count"] for c in chunks}, {512})
        joined = b"".join(self.assets[c["resource_id"]][c["source_offset"]:
                          c["source_offset"] + c["byte_count"]] for c in chunks)
        self.assertEqual(joined, self.assets[late["transfer"]["resource_id"]])
        self.assertEqual(len(joined), 8192)

    def test_sparse_staging_preserves_native_holes_and_unrelated_slots_byte_exact(self):
        fort = self.lower()["profiles"]["stepped-waterfront-fort"]
        records = fort["staging"]
        self.assertEqual(fort["transition"], dict(mode="native_staging", source_bank=0x7F))
        self.assertEqual(fort["cache_slot_mask"], 0x30)
        self.assertEqual(len(records), 96)
        self.assertEqual(sum(r["byte_count"] for r in records), 3072)
        before = bytes((i * 37 + i // 32) % 256 for i in range(8192))
        actual = bytearray(before)
        touched = set()
        for r in records:
            at = r["wram_address"] - 0x7F0000
            self.assertTrue(0x800 <= at < 0x1800)
            source = self.assets[r["resource_id"]]
            actual[at:at + 32] = source[r["source_offset"]:r["source_offset"] + 32]
            touched.update(range(at, at + 32))
        self.assertEqual(len(touched), 96 * 32)
        # Native filler must survive even though the source is tightly packed.
        untouched = [i for i in range(8192) if i not in touched]
        self.assertEqual(bytes(actual[i] for i in untouched), bytes(before[i] for i in untouched))
        holes = [ch for ch in range(0x100, 0x180)
                 if not set(range((ch - 0xC0) * 32, (ch - 0xC0 + 1) * 32)) & touched]
        self.assertEqual(len(holes), 32)
        for ch in [302, 303, 318, 319, 328, 331, 332, 347, 348, 392, 436]:
            at = (ch - 0xC0) * 32
            self.assertEqual(actual[at:at + 32], before[at:at + 32])
        expected = pack.validate(self.catalog, self.assets)[0x83][1]
        for ch, glyph in expected.items():
            at = (ch - 0xC0) * 32
            self.assertEqual(actual[at:at + 32], glyph)

    def test_missing_unknown_and_malformed_policy_fail_before_output(self):
        variants = []
        bad = copy.deepcopy(self.policy)
        del bad["profiles"]["dragon-ship"]
        variants.append(bad)
        bad = copy.deepcopy(self.policy)
        bad["profiles"]["other"] = bad["profiles"]["dragon-ship"]
        variants.append(bad)
        for field, value in [("runtime_enabled", 1), ("normal", "infer"),
                             ("cache_slots", [3, 3, 4, 5, 6]), ("unexpected", True)]:
            bad = copy.deepcopy(self.policy)
            bad["profiles"]["dragon-ship"][field] = value
            variants.append(bad)
        with tempfile.TemporaryDirectory() as directory:
            for index, bad in enumerate(variants):
                policy = Path(directory) / "bad.json"
                policy.write_bytes(pack.json_bytes(bad))
                output = Path(directory) / f"output-{index}"
                with self.subTest(index=index), self.assertRaises(pack.PackError):
                    pack.compile_pack(self.catalog_path, output, runtime_policy=policy)
                self.assertFalse(output.exists())

    def test_slice_layout_staging_and_late_mismatches_rejected(self):
        variants = []
        for field, value in [("source_offset", 32), ("vram_word_address", 0x2C10),
                             ("byte_count", 4096), ("resource_id", "missing")]:
            bad = copy.deepcopy(self.policy)
            bad["profiles"]["dragon-ship"]["transition"]["transfer"][field] = value
            variants.append(bad)
        for key, value in [("first_step", 0x51), ("end_step", 0x61), ("chunk_bytes", 1024)]:
            bad = copy.deepcopy(self.policy)
            bad["profiles"]["dragon-ship"]["late"][key] = value
            variants.append(bad)
        for mutate in [
            lambda p: p["stepped-waterfront-fort"]["staging"].update(wram_base=0x7F0800),
            lambda p: p["stepped-waterfront-fort"]["staging"].update(wram_base=float(0x7F0000)),
            lambda p: p["stepped-waterfront-fort"].update(cache_slots=[3, 4, 5]),
            lambda p: p["dragon-ship"].update(late=None),
            lambda p: p["kalyxo-docks"]["transition"].update(mode="source_start"),
        ]:
            bad = copy.deepcopy(self.policy)
            mutate(bad["profiles"])
            variants.append(bad)
        for index, policy in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(pack.PackError):
                self.lower(policy=policy)
        bad_catalog = copy.deepcopy(self.catalog)
        bad_catalog["profiles"]["loom-docks-approach"]["transfers"][0]["vram_word_address"] = 0x3000
        with self.assertRaises(pack.PackError):
            self.lower(catalog=bad_catalog)

    def test_semantic_policy_survives_profile_resource_and_transfer_reordering(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"] = dict(reversed(list(catalog["profiles"].items())))
        catalog["resources"] = dict(reversed(list(catalog["resources"].items())))
        catalog["profiles"]["dragon-ship"]["transfers"].reverse()
        expected, actual = self.lower(), self.lower(catalog=catalog)
        for name in expected["profiles"]:
            for field in ["transition", "cache_slot_mask", "staging", "late", "runtime_enabled"]:
                self.assertEqual(expected["profiles"][name][field], actual["profiles"][name][field])
        # Declared normal upload order remains intentional catalog data.
        self.assertEqual(actual["profiles"]["dragon-ship"]["normal"],
                         list(reversed(expected["profiles"]["dragon-ship"]["normal"])))

    def test_compilation_is_deterministic_bound_to_policy_and_remains_unlinked_data(self):
        protected = {self.catalog_path: self.catalog_path.read_bytes()}
        for resource in self.catalog["resources"].values():
            path = self.catalog_path.parent / resource["path"]
            protected[path] = path.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            outputs = [Path(directory) / name for name in ("first", "second")]
            receipts = [pack.compile_pack(self.catalog_path, out, runtime_policy=self.policy_path)
                        for out in outputs]
            self.assertEqual(receipts[0], receipts[1])
            self.assertEqual(receipts[0]["runtime_policy_source_sha256"],
                             pack.sha256(self.policy_path.read_bytes()))
            for path in outputs[0].rglob("*"):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (outputs[1] / path.relative_to(outputs[0])).read_bytes())
            asm = (outputs[0] / "runtime-phase-descriptors.asm").read_text()
            self.assertNotIn("\norg ", asm)
            self.assertNotIn("incsrc", asm)
            self.assertNotIn("JSL", asm)
            for parent, name in [(0x83, "stepped-waterfront-fort"), (0x87, "sky-d8-tower")]:
                self.assertIn(f"dl GraphicsRuntimePolicy_{pack.sha256(name.encode())} ; ${parent:02X}", asm)
            saved = json.loads((outputs[0] / "runtime-phase-policy.json").read_text())
            self.assertEqual(saved, self.lower())
        for path, before in protected.items():
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
