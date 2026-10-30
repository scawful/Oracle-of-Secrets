"""Admission planning preserves drafts and refuses incomplete native consumers."""
import copy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts/Build"))
import lyra_project_admission as A
import lyra_project_terrain as T


def profile():
    return {**{k: copy.deepcopy(T.DEFAULT_PROPERTIES[k]) for k in
            ("graphics_sheets", "main_palette", "palette_set", "animated_sheet")},
            "tile_count": 4096, "tile16_definition_fingerprint": A.sha(bytes(4096 * 8)),
            "graphics_fingerprint": "2" * 64, "palette_fingerprint": "3" * 64,
            "animation_fingerprint": "4" * 64}


def document():
    return dict(schema="yaze.lyra-terrain", schema_version=3, columns=8, rows=4,
        map_width=32, map_height=32, tile_pixels=16, profile=profile(),
        maps=[dict(map_id=area, tiles16=[[0] * 32 for _ in range(32)],
                   authoring=dict(properties=copy.deepcopy(T.DEFAULT_PROPERTIES),
                                  sprites=[], doors=[], exits=[], asset_bindings=[""] * 3))
              for area in range(0xA0, 0xC0)], flight_points=[], edge_connections=[])


def source_rom():
    source = bytearray(0x200000)
    source[0x865:0x868] = (0xBD8000).to_bytes(3, "little")
    source[A.pc(A.EMPTY_ACTORS)] = 255
    source[A.pc(A.EMPTY_HIDDEN_ITEMS):A.pc(A.EMPTY_HIDDEN_ITEMS) + 2] = b"\xff\xff"
    stream = 0x100000
    source[stream:stream + 259] = b"\xe0\xff" + bytes(256) + b"\xff"
    for table in (0x02F94D, 0x02FB2D):
        for area in range(160):
            at = A.pc(table) + area * 3
            source[at:at + 3] = A.snes(stream).to_bytes(3, "little")
    return bytes(source)


def observation(source, data):
    text = json.dumps(data)
    return text, dict(source_rom_sha256=A.sha(source), terrain_sha256=A.sha(text.encode()),
        map_count=32, donor_map=0x3A, native_tile32_capacity=0x4540, profile=copy.deepcopy(data["profile"]),
        verified_asset_bindings=[copy.deepcopy(e["authoring"]["asset_bindings"]) for e in data["maps"]],
        native_definitions=[list(A.read_tile32(source, i)) for i in range(0x4540)])


def allocation(source, **admission):
    return dict(kind="lyra.project_runtime_allocation.v1", source_rom_sha256=A.sha(source),
        expanded_size=0x400000, table_range=[A.TABLE_START, A.TABLE_END],
        code_range=[A.CODE_START, A.CODE_END], stream_ranges=[[0x3D4000, 0x3E0000]],
        owned_tile32_ids=[], admission=dict(candidate_maps=[], candidate_edge_ids=[],
            production_maps=[], production_edge_ids=[], **admission))


class LyraAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = source_rom()

    def plan(self, data=None, alloc=None, maps=None):
        text, proof = observation(self.source, data or document())
        return A.plan_admission(self.source, text, proof, alloc, candidate_maps=maps)

    def test_schema4_draft_outside_render_closure_does_not_block_native_subset(self):
        data = document()
        data["schema_version"] = 4
        auth = data["maps"][31]["authoring"]
        auth["properties"]["background_palette"] = [0x7FFF] * 128
        auth["asset_bindings"] = ["a" * 64] * 3
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = self.plan(data, alloc)
        self.assertTrue(plan["candidate_data_plan_ready"])
        self.assertEqual(plan["consumption_blockers"], [])
        self.assertIn(0xBF, plan["preserved_draft_maps"])
        self.assertNotIn("background_palette", plan["appearance"]["selector_rows"][0])

    def test_schema4_selected_palette_reports_exact_payload_and_prevents_publication(self):
        data = document()
        data["schema_version"] = 4
        colors = list(range(127)) + [0x7FFF]
        for index in (1, 2, 9, 10):
            auth = data["maps"][index]["authoring"]
            auth["properties"]["background_palette"] = colors[:]
            auth["asset_bindings"] = ["a" * 64] * 3
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = self.plan(data, alloc)
        palette = plan["appearance"]["selector_rows"][0]["background_palette"]
        payload = bytes.fromhex(palette["payload_hex"])
        self.assertEqual(payload, b"".join(color.to_bytes(2, "little") for color in colors))
        self.assertEqual(palette["sha256"], A.sha(payload))
        self.assertEqual(palette["word_count"], 128)
        self.assertEqual(palette["runtime_consumer"], "unbound")
        self.assertEqual(plan["consumption_blockers"], [dict(
            code="UNSUPPORTED_BACKGROUND_PALETTE", map_id=0xA1)])
        self.assertFalse(plan["candidate_data_plan_ready"])
        self.assertFalse(plan["runtime_build_ready"])
        self.assertEqual(plan["production_maps"], [])
        self.assertEqual(plan["streams"], [])
        self.assertEqual(plan["relocated_tables"], [])

    def test_schema4_render_dependency_override_is_not_silently_ignored(self):
        data = document()
        data["schema_version"] = 4
        auth = data["maps"][2]["authoring"]
        auth["properties"]["background_palette"] = [0] * 128
        auth["asset_bindings"] = ["a" * 64] * 3
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = self.plan(data, alloc)
        self.assertIn(dict(code="RENDER_APPEARANCE_UNPROVEN", map_id=0xA1,
            source_map=0xA2, fields=["background_palette"]), plan["consumption_blockers"])
        context = next(row for row in plan["appearance"]["render_contexts"]
                       if row["source_map"] == 0xA2)
        self.assertEqual(context["background_palette"]["payload_hex"], bytes(256).hex())
        self.assertEqual(context["background_palette"]["sha256"], A.sha(bytes(256)))
        self.assertFalse(plan["candidate_data_plan_ready"])
        self.assertEqual(plan["streams"], [])
        text, proof = observation(self.source, data)
        parsed = T.parse_terrain_document(text, profile(), allow_authoring_drafts=True,
            expected_asset_bindings={0xA2: tuple(auth["asset_bindings"])})
        compiled = T.compile_terrain(parsed, {i: (0,) * 4 for i in range(0x4540)},
            A.parse_allocation(allocation(self.source), self.source),
            map_ids=[0xA1, 0xA2, 0xA9, 0xAA])
        with self.assertRaisesRegex(ValueError, "no background palette consumer"):
            A.relocated_table_payloads(self.source, parsed, compiled, [0xA1])

    def test_empty_default_cannot_enable_or_publish(self):
        plan = self.plan()
        self.assertEqual(plan["candidate_maps"], [])
        self.assertEqual(plan["production_maps"], [])
        self.assertEqual(plan["render_maps"], [])
        self.assertEqual(plan["streams"], [])
        self.assertEqual(plan["relocated_tables"], [])
        self.assertFalse(plan["runtime_build_ready"])
        self.assertFalse(plan["production_endpoints_enabled"])
        self.assertEqual(plan["native_state_contract"]["event_rows"], [])

    def test_state_contract_keeps_terrain_readiness_separate_and_reports_real_return(self):
        data = document()
        data["maps"][0xB0 - 0xA0]["authoring"]["doors"] = [dict(
            id=1, x=3, y=4, entrance_id=0x0B)]
        data["maps"][0xB0 - 0xA0]["authoring"]["exits"] = [dict(
            id=2, room_id=0x83, x=2, y=5, exit_row=None)]
        plan = self.plan(data, maps=[0xB0])
        state = plan["native_state_contract"]
        self.assertEqual(state["requested_returns"][0]["path"], "custom_exit_table")
        self.assertFalse(state["requested_returns"][0]["requested_row_consumed"])
        self.assertIn("PERSISTENT_EVENT_STORAGE_UNALLOCATED",
                      [b["code"] for b in state["runtime_blockers"]])
        self.assertFalse(state["runtime_ready"])
        # A source mismatch is reported, rather than promoted by valid terrain.
        self.assertFalse(state["consumers_verified"])
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        terrain = self.plan(alloc=alloc)
        self.assertTrue(terrain["candidate_data_plan_ready"])
        self.assertFalse(terrain["native_state_contract"]["runtime_ready"])

    def test_recognized_tail_state_cannot_admit_power_or_promote_terrain_to_runtime(self):
        from test_lyra_native_state import tail_fixture
        source, symbols, ledger = tail_fixture()
        # Add only this suite's native terrain/table fixtures to the standalone
        # state image. Nothing is written to an actual ROM or reservation.
        for index, value in enumerate(self.source):
            if value:
                source[index] = value
        text, proof = observation(source, document())
        alloc = allocation(source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = A.plan_admission(source, text, proof, alloc,
                                state_symbols=symbols, state_ownership=ledger)
        self.assertTrue(plan["candidate_data_plan_ready"])
        self.assertTrue(plan["native_state_contract"]["consumers_verified"])
        self.assertIsNotNone(plan["native_state_contract"]["persistent_event_storage"])
        self.assertFalse(plan["runtime_build_ready"])
        self.assertFalse(plan["production_endpoints_enabled"])
        self.assertEqual(plan["production_maps"], [])
        self.assertEqual(plan["production_edge_ids"], [])
        data = document()
        data["maps"][0xB0 - 0xA0]["authoring"]["doors"] = [dict(id=1, x=3, y=4, entrance_id=0x0B)]
        data["maps"][0xB0 - 0xA0]["authoring"]["exits"] = [dict(id=2, room_id=0x83, x=2, y=5, exit_row=None)]
        text, proof = observation(source, data)
        alloc = allocation(source)
        alloc["admission"]["candidate_maps"] = [0xB0]
        power = A.plan_admission(source, text, proof, alloc,
                                 state_symbols=symbols, state_ownership=ledger)
        self.assertFalse(power["candidate_data_plan_ready"])
        self.assertTrue(power["native_state_contract"]["consumers_verified"])
        self.assertIn(dict(code="UNSUPPORTED_ACTIVE_METADATA", map_id=0xB0, field="doors"),
                      power["consumption_blockers"])
        self.assertFalse(power["native_state_contract"]["requested_returns"][0]["requested_row_consumed"])
        self.assertFalse(power["native_state_contract"]["runtime_ready"])
        self.assertEqual(power["production_maps"], [])

    def test_a1_render_closure_is_not_traversal_admission(self):
        plan = self.plan(maps=[0xA1])
        self.assertEqual(plan["render_maps"], [0xA1, 0xA2, 0xA9, 0xAA])
        self.assertEqual(plan["render_only_maps"], [0xA2, 0xA9, 0xAA])
        self.assertEqual(plan["candidate_maps"], [0xA1])
        self.assertEqual(plan["consumption_blockers"], [dict(code="ALLOCATION_REQUIRED")])
        self.assertFalse(plan["candidate_data_plan_ready"])
        directory, closure = A.render_dependency_plan([0xBF, 0xA1])
        self.assertEqual(directory[0xBF], (0xBF,) * 4)
        self.assertEqual(closure, (0xA1, 0xA2, 0xA9, 0xAA, 0xBF))

    def test_owned_subset_streams_and_legacy_table_copies_are_deterministic(self):
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        first = self.plan(alloc=alloc)
        self.assertEqual(first, self.plan(alloc=alloc))
        self.assertTrue(first["candidate_data_plan_ready"])
        self.assertEqual(len(first["streams"]), 8)
        self.assertEqual(sum(s["bytes"] for s in first["streams"]), 2072)
        self.assertEqual(first["new_tile32_definitions"], [])
        self.assertEqual(first["reused_tile32_ids"], [0])
        self.assertEqual(len(first["relocated_tables"]), 30)
        self.assertEqual(first["legacy_table_writes"], [])
        self.assertEqual(first["native_parent_count"], 160)
        for row in first["relocated_tables"]:
            old = self.source[A.pc(row["legacy_snes"]):A.pc(row["legacy_snes"]) + row["legacy_rows"] * row["stride"]]
            self.assertEqual(row["legacy_sha256"], A.sha(old))
        self.assertEqual(first["event_aliases"][0]["legacy_address"], 0x7EF321)

    def test_schema9_history_reports_document_wide_blocker_without_streams_or_default_tables(self):
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        baseline = self.plan(alloc=alloc)
        self.assertTrue(baseline["candidate_data_plan_ready"])
        self.assertTrue(baseline["streams"])
        self.assertTrue(baseline["relocated_tables"])
        for resources, counter in ((None, 1), (None, 0x100000000),
                                   ({"secrets": [], "event_behavior": None}, 1),
                                   ({"secrets": [{"id": 1, "x": 31, "y": 31, "secret_id": 255}],
                                     "event_behavior": None}, 2)):
            data = document()
            data.update(schema_version=9, gameplay_areas=[], boat_transport=None,
                        next_flight_point_id=1, whirlpool_transport=None,
                        next_native_resource_id=counter)
            for row in data["maps"]:
                row["authoring"]["properties"].update(T.RUNTIME_PROPERTY_DEFAULTS)
                row["authoring"]["native_resources"] = None
            data["maps"][-1]["authoring"]["native_resources"] = resources
            before = copy.deepcopy((data, alloc))
            with self.subTest(resources=resources, counter=counter):
                planned = self.plan(data, alloc)
                self.assertIn(dict(code="NATIVE_RESOURCES_UNBOUND", field="native_resources"),
                              planned["consumption_blockers"])
                self.assertFalse(planned["candidate_data_plan_ready"])
                self.assertEqual(planned["streams"], [])
                self.assertEqual(planned["relocated_tables"], [])
                self.assertEqual((data, alloc), before)
                parsed = T.parse_terrain_document(json.dumps(data), profile(), allow_authoring_drafts=True)
                for current in (False, True):
                    self.assertIn(dict(code="NATIVE_RESOURCES_UNBOUND", field="native_resources"),
                                  A.consumer_blockers(parsed, [], (), current_source=current))

    def test_drafts_outside_subset_keep_cells_entities_profiles_and_flights(self):
        data = document()
        draft = data["maps"][0xBF - 0xA0]
        draft["tiles16"][31][31] = 4095
        draft["authoring"]["sprites"] = [dict(id=1, sprite_id=8, x=31, y=31, state=2)]
        draft["authoring"]["doors"] = [dict(id=2, x=3, y=4, entrance_id=None)]
        draft["authoring"]["exits"] = [dict(id=3, room_id=0x127, x=2, y=5, exit_row=78)]
        draft["authoring"]["properties"]["main_palette"] = 5
        draft["authoring"]["asset_bindings"] = ["a" * 64] * 3
        data["flight_points"] = [dict(id=1, map_id=0xBF, x=0, y=31, name="Draft landing", runtime_slot=None)]
        before = copy.deepcopy(data)
        text, proof = observation(self.source, data)
        parsed = T.parse_terrain_document(text, profile(), allow_authoring_drafts=True,
            expected_asset_bindings={0xBF: tuple(draft["authoring"]["asset_bindings"])})
        self.assertEqual(parsed.maps[-1][-1], 4095)
        self.assertEqual(parsed.authoring[-1], draft["authoring"])
        self.assertEqual(list(parsed.flight_points), data["flight_points"])
        self.assertEqual(data, before)
        plan = A.plan_admission(self.source, text, proof, candidate_maps=[0xA1])
        self.assertEqual(plan["consumption_blockers"], [dict(code="ALLOCATION_REQUIRED")])

    def test_current_sprite_phases_require_complete_selected_source_families(self):
        import lyra_current_transfer as current
        data = document()
        auth = data['maps'][1]['authoring']
        auth['properties'].update(sprite_graphics=[0, 27, 4], sprite_palettes=[1, 0, 0],
                                  music=[1, 2, 3, 4])
        auth['sprites'] = [dict(id=1, sprite_id=0x52, x=0, y=0, state=1)]
        auth['asset_bindings'] = ['a' * 64] * 3
        parsed = T.parse_terrain_document(json.dumps(data), profile(), allow_authoring_drafts=True,
                                         expected_asset_bindings={0xA1: ('a' * 64,) * 3})
        phase = lambda field: dict(code='UNSUPPORTED_PHASE_SELECTOR', map_id=0xA1, field=field)
        source_contract = json.loads(Path(current.CURRENT_SOURCE_CONTRACT).read_bytes())
        legacy = A.consumer_blockers(parsed, [0xA1], ())
        for field in ('sprite_graphics', 'sprite_palettes', 'music'):
            self.assertIn(phase(field), legacy)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source-contract.json'
            with mock.patch.object(current, 'CURRENT_SOURCE_CONTRACT', path):
                path.write_text(json.dumps(source_contract))
                active = A.consumer_blockers(parsed, [0xA1], (), current_source=True)
                self.assertNotIn(phase('sprite_graphics'), active)
                self.assertNotIn(phase('sprite_palettes'), active)
                self.assertIn(phase('music'), active)
                self.assertIn(dict(code='UNSUPPORTED_ACTIVE_METADATA', map_id=0xA1,
                                   field='sprites'), active)
                mutants = []
                for field, value in (('rows', 64), ('rows', True), ('families', 'invalid')):
                    bad = copy.deepcopy(source_contract)
                    bad['tables'][field] = value
                    mutants.append(bad)
                for family in ('special_sprite_gfx_phase1', 'special_sprite_palettes_phase2'):
                    bad = copy.deepcopy(source_contract)
                    bad['tables']['families'].remove(family)
                    mutants.append(bad)
                bad = copy.deepcopy(source_contract)
                bad['tables']['families'][-1] = bad['tables']['families'][-2]
                mutants.append(bad)
                bad = copy.deepcopy(source_contract)
                bad['kind'] = 'unsupported'
                mutants.append(bad)
                for bad in mutants:
                    path.write_text(json.dumps(bad))
                    blocked = A.consumer_blockers(parsed, [0xA1], (), current_source=True)
                    self.assertIn(phase('sprite_graphics'), blocked)
                    self.assertIn(phase('sprite_palettes'), blocked)
                path.write_text('{malformed')
                self.assertIn(phase('sprite_graphics'),
                              A.consumer_blockers(parsed, [0xA1], (), current_source=True))

    def test_active_metadata_and_phase_disagreement_block_consumption(self):
        for key, entity in (("sprites", dict(id=1, sprite_id=4, x=0, y=0, state=0)),
                            ("doors", dict(id=1, x=0, y=0, entrance_id=None)),
                            ("exits", dict(id=1, room_id=0, x=0, y=0, exit_row=None))):
            with self.subTest(key=key):
                data = document()
                data["maps"][1]["authoring"][key] = [entity]
                plan = self.plan(data, maps=[0xA1])
                self.assertIn(dict(code="UNSUPPORTED_ACTIVE_METADATA", map_id=0xA1, field=key), plan["consumption_blockers"])
                self.assertEqual(plan["streams"], [])
        for key, values in (("music", [1, 2, 3, 4]), ("sprite_graphics", [2, 3, 4]),
                            ("sprite_palettes", [3, 4, 5])):
            data = document()
            data["maps"][1]["authoring"]["properties"][key] = values
            data["maps"][1]["authoring"]["asset_bindings"] = ["b" * 64] * 3
            self.assertIn(dict(code="UNSUPPORTED_PHASE_SELECTOR", map_id=0xA1, field=key),
                          self.plan(data, maps=[0xA1])["consumption_blockers"])

    def test_render_dependency_profile_mismatch_blocks_but_draft_metadata_is_not_active(self):
        data = document()
        dep = data["maps"][2]["authoring"]
        dep["properties"]["palette_set"] = 3
        dep["asset_bindings"] = ["c" * 64] * 3
        self.assertIn(dict(code="RENDER_APPEARANCE_UNPROVEN", map_id=0xA1, source_map=0xA2, fields=["palette_set"]),
                      self.plan(data, maps=[0xA1])["consumption_blockers"])
        dep["properties"]["palette_set"] = 1
        dep["asset_bindings"] = [""] * 3
        dep["doors"] = [dict(id=2, x=1, y=1, entrance_id=None)]
        self.assertNotIn(dict(code="UNSUPPORTED_ACTIVE_METADATA", map_id=0xA2, field="doors"),
                         self.plan(data, maps=[0xA1])["consumption_blockers"])

    def test_saved_per_map_selectors_reach_native_rows_without_donor_override(self):
        data = document()
        for index in (1, 2, 9, 10):
            auth = data["maps"][index]["authoring"]
            auth["properties"]["graphics_sheets"][5] = 0x60
            auth["properties"]["palette_set"] = 3
            auth["asset_bindings"] = ["a" * 64] * 3
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = self.plan(data, alloc)
        self.assertTrue(plan["appearance"]["coherent"])
        self.assertTrue(plan["candidate_data_plan_ready"])
        row = plan["appearance"]["selector_rows"][0]
        self.assertEqual(row["graphics_sheets"][5], 0x60)
        self.assertEqual(row["palette_set"], 3)
        table_row = next(r for r in row["native_table_rows"] if r["table"] == "gfx")
        self.assertEqual(bytes.fromhex(table_row["payload_hex"])[5], 0x60)
        self.assertEqual(table_row["pc"], A.TABLE_START + 0x540 + 0xA1 * 8)
        # Independent complete-table reconstruction proves the compiled row
        # consumes saved selectors, rather than the common donor profile.
        payload = bytearray(192 * 8)
        native = self.source[A.pc(0x288480):A.pc(0x288480) + 160 * 8]
        payload[:len(native)] = native
        payload[0xA1 * 8:0xA2 * 8] = bytes(row["graphics_sheets"])
        table = next(r for r in plan["relocated_tables"] if r["name"] == "gfx")
        self.assertEqual(table["proposed_sha256"], A.sha(payload))

    def test_unused_sheet_difference_can_be_proved_but_used_difference_stays_closed(self):
        data = document()
        data["maps"][1]["authoring"]["properties"]["graphics_sheets"][5] = 0x60
        data["maps"][1]["authoring"]["asset_bindings"] = ["b" * 64] * 3
        # Synthetic Tile16 definitions use only CHR0, so slot5 is irrelevant.
        self.assertTrue(self.plan(data, maps=[0xA1])["appearance"]["coherent"])
        source = bytearray(self.source)
        source[0x1E8000:0x1E8008] = (320).to_bytes(2, "little") * 4
        data["profile"]["tile16_definition_fingerprint"] = A.sha(source[0x1E8000:0x1F0000])
        text, proof = observation(bytes(source), data)
        plan = A.plan_admission(bytes(source), text, proof, candidate_maps=[0xA1])
        self.assertFalse(plan["appearance"]["coherent"])
        self.assertIn(dict(code="RENDER_APPEARANCE_UNPROVEN", map_id=0xA1,
                           source_map=0xA2, fields=["graphics_sheets[5]"]), plan["consumption_blockers"])
        self.assertEqual(plan["streams"], [])

    def test_isolated_footprint_is_explicit_and_propagated_into_compiler(self):
        alloc = allocation(self.source)
        alloc["admission"].update(candidate_maps=[0xA1], render_footprints=[
            dict(map_id=0xA1, quadrant_maps=[0xA1] * 4)])
        plan = self.plan(alloc=alloc)
        self.assertEqual(plan["render_directory"], [dict(map_id=0xA1, quadrant_maps=[0xA1] * 4)])
        self.assertEqual(plan["render_maps"], [0xA1])
        self.assertEqual(len(plan["streams"]), 2)
        self.assertIn("ISOLATED_FOOTPRINT_NATIVE_QUALIFICATION_REQUIRED", plan["qualification_blockers"])
        self.assertEqual(plan["production_maps"], [])
        doc = T.parse_terrain_document(json.dumps(document()), profile())
        compiled = T.compile_terrain(doc, {i: (0, 0, 0, 0) for i in range(0x4540)},
            A.parse_allocation(alloc, self.source), map_ids=[0xA1], render_directory={0xA1: (0xA1,) * 4})
        self.assertEqual(compiled.maps[0].quadrant_maps, (0xA1,) * 4)
        for bad in ([0xA2] * 4, [0xA1, 0xA1, 0xA1, True]):
            alloc["admission"]["render_footprints"][0]["quadrant_maps"] = bad
            with self.assertRaisesRegex(ValueError, "natural or explicitly isolated"):
                self.plan(alloc=alloc)
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            T.compile_terrain(doc, {i: (0, 0, 0, 0) for i in range(0x4540)},
                A.parse_allocation(alloc, self.source), map_ids=[0xA1],
                render_directory={0xA1: T.quadrant_map_plan(0xA1)})

    def test_current_tile16_binding_and_missing_tile32_are_not_silently_accepted(self):
        text, proof = observation(self.source, document())
        altered = bytearray(self.source)
        altered[0x1E8000] = 1
        proof["source_rom_sha256"] = A.sha(altered)
        with self.assertRaisesRegex(ValueError, "Native Tile16 observation"):
            A.plan_admission(bytes(altered), text, proof, candidate_maps=[0xA1])
        data = document()
        data["maps"][1]["tiles16"][0][0] = 1
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        plan = self.plan(data, alloc)
        self.assertEqual(plan["tile32_requirements"]["missing_definitions"], [[1, 0, 0, 0]])
        self.assertIn(dict(code="TILE32_ALLOCATION_REQUIRED", missing_definitions=1), plan["consumption_blockers"])
        self.assertEqual(plan["streams"], [])

    def test_new_reservation_never_admits_a_padded_two_mib_prefix(self):
        import lyra_project_allocation as reservation
        from lyra_historical_fixture import historical_ledger_path
        alloc = reservation.derive_allocation(A.expanded_rom(self.source), ledger_path=historical_ledger_path(self))
        alloc["source_rom_sha256"] = A.sha(self.source)
        with self.assertRaisesRegex(ValueError, "actual unheadered4MiB"):
            self.plan(alloc=alloc)

    def test_production_admission_and_selection_mismatch_refuse(self):
        for key, ids in (("production_maps", [0xA1]), ("production_edge_ids", [1])):
            alloc = allocation(self.source)
            alloc["admission"][key] = ids
            with self.assertRaisesRegex(ValueError, "Production admission"):
                self.plan(alloc=alloc)
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        with self.assertRaisesRegex(ValueError, "differs"):
            self.plan(alloc=alloc, maps=[0xA0])
        for ids in ([True], [0xA1, 0xA1], [0xC0]):
            with self.assertRaises(ValueError):
                self.plan(maps=ids)

    def test_only_selected_edges_produce_reciprocal_bounds(self):
        data = document()
        data["edge_connections"] = [dict(id=1, map_a=0x99, map_b=0xA1,
            passage=dict(first_tile=15, last_tile=16)),
            dict(id=2, map_a=0xA0, map_b=0xA8, passage=None)]
        alloc = allocation(self.source)
        alloc["admission"].update(candidate_maps=[0xA1], candidate_edge_ids=[1])
        plan = self.plan(data, alloc)
        self.assertEqual([e["direction"] for e in plan["directed_edges"]], ["south", "north"])
        self.assertEqual([(e["first_pixel"], e["end_pixel"]) for e in plan["directed_edges"]], [(240, 272)] * 2)
        self.assertEqual(plan["unselected_edge_ids"], [2])
        self.assertIn("ENDPOINT_APPEARANCE_DECISION_REQUIRED", plan["qualification_blockers"])
        alloc["admission"]["candidate_edge_ids"] = [2]
        with self.assertRaisesRegex(ValueError, "passage"):
            self.plan(data, alloc)
        alloc["admission"]["candidate_edge_ids"] = [3]
        with self.assertRaisesRegex(ValueError, "missing edge"):
            self.plan(data, alloc)

    def test_stale_native_observation_bindings_and_dictionary_refuse(self):
        data = document()
        text, proof = observation(self.source, data)
        for key, value in (("source_rom_sha256", "0" * 64), ("terrain_sha256", "0" * 64),
                           ("native_tile32_capacity", 160)):
            changed = copy.deepcopy(proof)
            changed[key] = value
            with self.assertRaisesRegex(ValueError, "stale or incomplete"):
                A.plan_admission(self.source, text, changed)
        proof["native_definitions"][5] = [4095] * 4
        with self.assertRaisesRegex(ValueError, "differs from source"):
            A.plan_admission(self.source, text, proof)
        data["maps"][1]["authoring"]["asset_bindings"] = ["a" * 64] * 3
        text, proof = observation(self.source, data)
        proof["verified_asset_bindings"][1] = ["b" * 64] * 3
        with self.assertRaisesRegex(ValueError, "bindings differ"):
            A.plan_admission(self.source, text, proof)

    def test_allocation_source_occupancy_and_overlap_refuse(self):
        alloc = allocation(self.source)
        alloc["source_rom_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "bound to the input"):
            self.plan(alloc=alloc)
        alloc = allocation(self.source)
        alloc["stream_ranges"] = [[A.CODE_START, A.CODE_END]]
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            self.plan(alloc=alloc)
        occupied = bytearray(A.expanded_rom(self.source))
        occupied[0x3D4000] = 0
        with self.assertRaisesRegex(ValueError, "occupied"):
            A.verify_allocation(occupied, T.Allocation(((0x3D4000, 0x3E0000),)))

    def test_new_tile32_allocation_cannot_overwrite_legacy_reference(self):
        data = document()
        data["maps"][1]["tiles16"][0][0] = 1
        alloc = allocation(self.source)
        alloc["admission"]["candidate_maps"] = [0xA1]
        alloc["owned_tile32_ids"] = [0]
        with self.assertRaisesRegex(ValueError, "still referenced by native map00"):
            self.plan(data, alloc)
        # Directly exercise independent legacy readback with a changed used ID.
        class Compiled:
            new_definitions = ((0, (1, 1, 1, 1)),)
        with self.assertRaisesRegex(ValueError, "native map00"):
            A.require_legacy_definition_preservation(self.source, Compiled())

    def test_valid_draft_parser_still_rejects_malformed_entities(self):
        for mutate in (
            lambda d: d["maps"][31]["authoring"].update(doors=[dict(id=1, x=True, y=0, entrance_id=None)]),
            lambda d: d["maps"][31]["authoring"].update(sprites=[dict(id=1, x=0, y=0, sprite_id=256, state=0)]),
            lambda d: d.update(flight_points=[dict(id=1, map_id=191, x=0, y=0, name="x\ny", runtime_slot=None)]),
        ):
            data = document()
            mutate(data)
            with self.assertRaises(ValueError):
                self.plan(data)

    def test_cli_keeps_linked_project_asset_anchor_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target, opened = root / "target", root / "opened"
            target.mkdir()
            opened.mkdir()
            descriptor = target / "Oracle.yaze"
            descriptor.write_text("[files]\nlyra_terrain_file=terrain.json\n")
            linked = opened / "Oracle.yaze"
            linked.symlink_to(descriptor)
            text, proof = observation(self.source, document())
            (opened / "terrain.json").write_text(text)
            (target / "terrain.json").write_text("wrong asset anchor")
            rom, cli = root / "test.sfc", root / "z3ed"
            rom.write_bytes(self.source)
            cli.write_text("mocked read-only verifier")

            def verify(z3ed, project, source):
                self.assertEqual(project, linked)
                self.assertEqual(T.resolve_project_terrain(project), (opened / "terrain.json").resolve())
                return proof

            output = io.StringIO()
            with mock.patch.object(A, "native_verify", side_effect=verify), contextlib.redirect_stdout(output):
                self.assertEqual(A.main(["--project", str(linked), "--rom", str(rom),
                                         "--z3ed", str(cli)]), 0)
            plan = json.loads(output.getvalue())
            self.assertEqual(plan["inputs"][0]["path"], str(linked))
            self.assertEqual(plan["terrain_sha256"], A.sha(text.encode()))

            def mutating_verifier(*args):
                descriptor.write_text(descriptor.read_text() + "# unexpected mutation\n")
                return proof

            with mock.patch.object(A, "native_verify", side_effect=mutating_verifier):
                with self.assertRaisesRegex(ValueError, "changed an input"):
                    A.main(["--project", str(linked), "--rom", str(rom), "--z3ed", str(cli)])


if __name__ == "__main__":
    unittest.main()
