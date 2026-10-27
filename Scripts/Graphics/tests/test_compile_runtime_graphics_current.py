"""Current source tables and native160 controls; no ROM/65816 execution."""
from pathlib import Path
import contextlib
import copy
import io
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compile_graphics_pack as pack
import compile_runtime_graphics as runtime


class CurrentRuntimeGraphicsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "binding.asm").write_text("; host fixture, no allocation\n")
        binding = dict(path="binding.asm", sha256=pack.sha256(
            (self.root / "binding.asm").read_bytes()))
        self.contract = pack.read_json(runtime.ROOT / "Config/lyra_current_source_contract.json")
        self.contract["origins"]["graphics"] = dict(
            pc=[0x2D0000, 0x2D8000], snes=[0x5A8000, 0x5B0000],
            source_binding=dict(binding))
        self.contract["ledger"] = dict(binding)
        data = bytes(range(32))
        self.assets = {"fixture": data}
        self.catalog = dict(schema_version=2, resources={"fixture": dict(
            path="fixture.bin", format="snes4bpp", byte_count=32,
            sha256=pack.sha256(data))}, profiles={"fixture": dict(
                bg_character_base_word=0x2000, transfers=[dict(
                    resource_id="fixture", source_offset=0,
                    vram_word_address=0x2C00, byte_count=32)])},
            bindings=[dict(parent_maps=[0x9F], profile_id="fixture")])
        self.policy = dict(schema_version=1, profiles={"fixture": dict(
            runtime_enabled=True, normal="all_declared_transfers",
            cache_slots=[3], transition=dict(mode="native_staging"),
            staging=dict(mode="native_after_conversion", vram_start_word=0x2C00,
                         vram_end_word=0x3C00, wram_base=0x7F0000), late=None)})

    def bind_tail(self):
        self.catalog["bindings"].append(dict(
            parent_maps=list(range(0xA0, 0xC0)), profile_id="fixture"))

    def render(self, *, current=False):
        return runtime.render(self.catalog, self.assets, self.policy,
                              self.root, self.root, legacy_root=self.root,
                              current_contract=self.contract if current else None,
                              source_root=self.root)

    @staticmethod
    def parent_rows(text):
        return re.findall(r"^  dw (.+) ; \$([0-9A-F]{2})$", text, re.M)

    def test_native_9f_and_historical_a0_bf_c0_rejection(self):
        text, _ = self.render()
        self.assertEqual(len(self.parent_rows(text)), 160)
        for parent in (0xA0, 0xA1, 0xBF, 0xC0):
            with self.subTest(parent=parent):
                catalog = copy.deepcopy(self.catalog)
                catalog["bindings"][0]["parent_maps"] = [parent]
                with self.assertRaisesRegex(pack.PackError, "parent_map"):
                    pack.validate(catalog, self.assets)
                with self.assertRaisesRegex(pack.PackError, "parent_map"):
                    pack.lower_runtime_policy(catalog, self.assets, self.policy)

    def test_current_has_192_rows_and_native160_rows_are_identical(self):
        native, _ = self.render()
        self.bind_tail()
        current, report = self.render(current=True)
        rows = self.parent_rows(current)
        self.assertEqual(len(rows), 192)
        self.assertEqual(rows[:160], self.parent_rows(native))
        for parent in (0x9F, 0xA0, 0xA1, 0xBF):
            self.assertEqual(rows[parent], (runtime.profile_label("fixture") + "&$FFFF",
                                            f"{parent:02X}"))
        self.assertIn("!GfxRT_ParentCount = $00C0", current)
        self.assertIn("!GfxRT_Bank = $005A", current)
        self.assertIn("assert pc() == $5A8000", current)
        self.assertEqual(report["parent_count"], 192)
        self.assertEqual(report["normal_counts"], {"fixture": 1})
        self.assertEqual(report["staging_counts"], {"fixture": 1})

    def test_current_c0_rejected_and_missing_saved_tail_never_invented(self):
        with self.assertRaisesRegex(pack.PackError, "saved catalog rows"):
            self.render(current=True)
        self.bind_tail()
        self.catalog["bindings"][-1]["parent_maps"].append(0xC0)
        with self.assertRaisesRegex(pack.PackError, "parent_map"):
            self.render(current=True)

    def test_load_v2_uses_explicit_domain_and_v1_cannot_broaden(self):
        self.bind_tail()
        (self.root / "fixture.bin").write_bytes(self.assets["fixture"])
        path = self.root / "catalog.json"
        path.write_bytes(pack.json_bytes(self.catalog))
        with self.assertRaisesRegex(pack.PackError, "parent_map"):
            pack.load(path)
        loaded, assets = pack.load(path, parent_count=192)
        self.assertEqual(loaded, self.catalog)
        self.assertEqual(assets, self.assets)
        path.write_bytes(pack.json_bytes(dict(schema_version=1, areas=[])))
        with self.assertRaisesRegex(pack.PackError, "canonical saved V2"):
            pack.load(path, parent_count=192)

    def test_domain_does_not_accept_arbitrary_capacity_or_boolean(self):
        for count in (True, 161, 191, 193, 256):
            with self.subTest(count=count):
                with self.assertRaisesRegex(pack.PackError, "parent_count"):
                    pack.validate(self.catalog, self.assets, parent_count=count)
        self.contract["source_domain"]["first_map"] = 0xA1
        with self.assertRaisesRegex(pack.PackError, "native160 plus A0..BF"):
            self.render(current=True)

    def test_unbound_or_stale_source_and_ledger_refuse(self):
        for key in ("source_binding", "ledger"):
            with self.subTest(key=key):
                contract = copy.deepcopy(self.contract)
                binding = (contract["origins"]["graphics"][key] if key == "source_binding"
                           else contract[key])
                binding["sha256"] = "0" * 64
                with self.assertRaisesRegex(pack.PackError, "source binding changed"):
                    runtime.current_graphics_contract(contract, source_root=self.root)
        self.contract["origins"]["graphics"] = None
        with self.assertRaisesRegex(pack.PackError, "origin is unbound"):
            self.render(current=True)

    def test_origin_must_be_mapped_same_bank_and_source_bound(self):
        bound = copy.deepcopy(self.contract)
        absolute = str(self.root / "binding.asm")
        bound["origins"]["graphics"]["source_binding"]["path"] = absolute
        bound["ledger"]["path"] = absolute
        self.assertEqual(runtime.current_graphics_contract(
            bound, source_root=self.root)["parent_count"], 192)
        mutations = (
            dict(pc=[0x2D0001, 0x2D8001]),
            dict(snes=[0x5A8000, 0x5B8000]),
            dict(snes=[0x7E8000, 0x7F0000]),
            dict(source_binding=dict(path="../escape.asm", sha256="0" * 64)),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                contract = copy.deepcopy(self.contract)
                contract["origins"]["graphics"].update(mutation)
                with self.assertRaises(pack.PackError):
                    runtime.current_graphics_contract(contract, source_root=self.root)

    def test_grant_flags_and_other_engine_do_not_become_source_authority(self):
        for flag in ("allocation_granted", "publication_authorized",
                     "producer_enforcement_verified", "ordinary_build_ready",
                     "runtime_admission"):
            contract = copy.deepcopy(self.contract)
            contract[flag] = True
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(pack.PackError, "cannot grant publication"):
                    runtime.current_graphics_contract(contract, source_root=self.root)
        self.contract["engine_head"] = "0" * 40
        with self.assertRaisesRegex(pack.PackError, "provenance changed"):
            self.render(current=True)

    def test_same_bank_capacity_refuses_before_output(self):
        self.bind_tail()
        self.contract["origins"]["graphics"].update(
            pc=[0x2D0000, 0x2D0100], snes=[0x5A8000, 0x5A8100])
        with self.assertRaisesRegex(pack.PackError, "exceed bank"):
            self.render(current=True)

    def test_current_reuses_c19_ship_labels_but_not_historical_docks_origins(self):
        self.bind_tail()
        resource = self.catalog["resources"]["fixture"]
        for path, expected in (("gfx/boat.bin", "BoatBitmap"),
                               ("gfx/boat2.bin", "AdditionalBitmap")):
            with self.subTest(path=path):
                resource["path"] = path
                target = self.root / "Overworld" / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self.assets["fixture"])
                text, report = self.render(current=True)
                self.assertEqual(report["aliases"], {"fixture": expected})
                self.assertEqual(report["new_payload_count"], 0)
                self.assertIn("dl " + expected + "+$0000", text)
        resource["path"] = "gfx/kalyxo_docks_bg.bin"
        text, report = self.render(current=True)
        self.assertEqual(report["aliases"], {})
        self.assertEqual(report["new_payload_count"], 1)
        self.assertNotIn("KalyxoDocksBackgroundGraphics", text)
        self.assertNotIn("$448000", text)

    def test_native_custom_load_branch_retains_original_c19_instructions(self):
        asm = (runtime.ROOT / "Overworld/custom_gfx.asm").read_text()
        body = asm.split("CheckForChangeGraphicsNormalLoadBoat:", 1)[1].split("\n}", 1)[0]
        current, native = body.split("if !LYRA_CURRENT_MODE", 1)[1].split("endif", 1)
        self.assertIn("JML SharedGraphicsNormalLoad", current)
        self.assertIn("CMP.w #!LYRA_CURRENT_FIRST : BCC .native", current)
        self.assertIn("CMP.w #!LYRA_CURRENT_END : BCS .native", current)
        self.assertEqual(native.strip(), """LDA $8A : CMP.b #$38 : BEQ .load
  CMP.b #$30 : BNE .boat_area
  .load
    PHB : PHK : PLB
    JSR ApplyGraphics1
    JSR ApplyGraphics2
    PLB
  .boat_area
  RTL""")

    def test_actual_unbound_source_contract_write_refuses_without_output(self):
        output = self.root / "never-created.asm"
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = runtime.main([
                "--catalog", str(runtime.ROOT / "Overworld/graphics_catalog.json"),
                "--policy", str(runtime.ROOT / "Overworld/graphics_runtime_policy.json"),
                "--current-contract", str(runtime.ROOT / "Config/lyra_current_source_contract.json"),
                "--output", str(output), "--write"])
        self.assertEqual(code, 1)
        self.assertIn("origin is unbound", stderr.getvalue())
        self.assertFalse(output.exists())

    def test_committed_historical_table_and_current_lookup_boundaries(self):
        text = (runtime.ROOT / "Overworld/graphics_runtime_tables.asm").read_text()
        self.assertEqual(len(self.parent_rows(text)), 160)
        self.assertIn("!GfxRT_ParentCount = $00A0", text)
        asm = (runtime.ROOT / "Overworld/graphics_runtime.asm").read_text()
        self.assertIn("CMP.w #!GfxRT_ParentCount : BCS .none", asm)
        self.assertIn("assert !GfxRT_ParentCount == !LYRA_CURRENT_PARENT_COUNT", asm)
        self.assertIn('incsrc "Data/Generated/lyra_project/graphics_runtime_tables.asm"', asm)
        self.assertIn('incsrc "Overworld/graphics_runtime_tables.asm"', asm)
        self.assertNotIn("LDA.l $5B", asm)


if __name__ == "__main__":
    unittest.main()
