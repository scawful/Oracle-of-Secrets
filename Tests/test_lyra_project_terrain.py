"""Saved Yaze terrain compilation using synthetic definitions and owned spans."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "lyra_project_terrain", ROOT / "Scripts/Build/lyra_project_terrain.py")
T = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = T
SPEC.loader.exec_module(T)


def profile():
    return {**{key: copy.deepcopy(T.DEFAULT_PROPERTIES[key]) for key in
               ("graphics_sheets", "main_palette", "palette_set", "animated_sheet")},
            "tile_count": 4096, "tile16_definition_fingerprint": "1" * 64,
            "graphics_fingerprint": "2" * 64, "palette_fingerprint": "3" * 64,
            "animation_fingerprint": "4" * 64}


def fixture():
    maps = []
    for index in range(32):
        # Each map has distinguishable corners, including every B7..BF edge.
        cells = [[index + 1] * 32 for _ in range(32)]
        cells[0][:2], cells[1][:2] = [0, 1], [2, 3]
        cells[-1][-1] = 4095
        maps.append({"map_id": 0xA0 + index, "tiles16": cells,
                     "authoring": {"properties": copy.deepcopy(T.DEFAULT_PROPERTIES),
                                   "sprites": [], "doors": [], "exits": [],
                                   "asset_bindings": ["", "", ""]}})
    return {"schema": "yaze.lyra-terrain", "schema_version": 3,
            "columns": 8, "rows": 4, "map_width": 32, "map_height": 32,
            "tile_pixels": 16, "profile": profile(), "maps": maps,
            "flight_points": [], "edge_connections": []}


def parse(data):
    return T.parse_terrain_document(json.dumps(data), profile())


def definitions(capacity=128):
    # Index 0 already owns a frequently used native quartet. No slot becomes
    # writable merely because these test maps do not reference it.
    return {index: (0, 1, 2, 3) if index == 0 else (3000 + index,) * 4
            for index in range(capacity)}


def allocation(**overrides):
    values = {"stream_ranges": ((0x20000, 0x28000),),
              "owned_tile32_ids": tuple(range(1, 128)), "tile32_capacity": 128}
    values.update(overrides)
    return T.Allocation(**values)


class LyraProjectTerrainTest(unittest.TestCase):
    def test_subset_preserves_actual_ids_metadata_and_exact_readback(self):
        data, native = fixture(), definitions()
        selected = (0xA1, 0xA2, 0xA9, 0xAA)
        verified = {}
        for area in selected:
            auth = data["maps"][area - T.FIRST_MAP]["authoring"]
            auth["properties"]["music"] = [area, 1, 2, 3]
            auth["asset_bindings"] = ["a" * 64, "b" * 64, "c" * 64]
            verified[area] = tuple(auth["asset_bindings"])
        data["edge_connections"] = [
            {"id": 1, "map_a": 0xA1, "map_b": 0xA9,
             "passage": {"first_tile": 14, "last_tile": 17}},
            {"id": 2, "map_a": 0xA0, "map_b": 0xA8, "passage": None}]
        document = T.parse_terrain_document(json.dumps(data), profile(),
                    expected_asset_bindings=verified)
        owned = allocation()
        original = copy.deepcopy((document, native, owned))
        result = T.compile_terrain(document, native, owned,
                                   map_ids=(0xAA, 0xA9, 0xA2, 0xA1))
        self.assertEqual([p.map_id for p in result.maps], list(selected))
        self.assertEqual(len(result.stream_writes), 8)
        self.assertEqual(sum(len(s.payload) for s in result.stream_writes), 2072)
        self.assertEqual(result.edge_connections, document.edge_connections)
        resolved = {**native, **dict(result.new_definitions)}
        for plan in result.maps:
            with self.subTest(map_id=plan.map_id):
                source = data["maps"][plan.map_id - T.FIRST_MAP]
                self.assertEqual(plan.properties, source["authoring"]["properties"])
                self.assertEqual(plan.quadrant_maps, T.quadrant_map_plan(plan.map_id))
                high = T.decode_literal_stream(plan.high.payload)
                low = T.decode_literal_stream(plan.low.payload)
                tile_ids = tuple(a << 8 | b for a, b in zip(high, low))
                self.assertEqual(tile_ids, plan.tiles32)
                rebuilt = [[None] * 32 for _ in range(32)]
                for index, tile in enumerate(tile_ids):
                    row, column = divmod(index, 16)
                    for quadrant, value in enumerate(resolved[tile]):
                        rebuilt[row * 2 + quadrant // 2][column * 2 + quadrant % 2] = value
                self.assertEqual(rebuilt, source["tiles16"])
        self.assertEqual((document, native, owned), original)
        result.maps[0].properties["music"][0] = 0
        self.assertEqual((document, native, owned), original)

    def test_subset_order_is_independent_for_lists_sets_and_generators(self):
        document, native, owned = parse(fixture()), definitions(), allocation()
        expected = T.compile_terrain(document, native, owned,
                                     map_ids=(0xA1, 0xA2, 0xA9, 0xAA))
        for requested in ([0xAA, 0xA2, 0xA9, 0xA1],
                          {0xAA, 0xA1, 0xA9, 0xA2},
                          (area for area in (0xA9, 0xA1, 0xAA, 0xA2))):
            with self.subTest(requested=type(requested).__name__):
                self.assertEqual(T.compile_terrain(document, native, owned,
                                                   map_ids=requested), expected)

    def test_empty_selection_emits_nothing_but_validates_native_inputs(self):
        document, native = parse(fixture()), definitions()
        minimal = allocation(stream_ranges=((0x20000, 0x20001),),
                             owned_tile32_ids=())
        original = copy.deepcopy((document, native, minimal))
        for requested in ([], (), iter(())):
            result = T.compile_terrain(document, native, minimal, map_ids=requested)
            self.assertEqual(result.maps, ())
            self.assertEqual(result.stream_writes, ())
            self.assertEqual(result.new_definitions, ())
            self.assertEqual(result.edge_connections, document.edge_connections)
        self.assertEqual((document, native, minimal), original)
        for incomplete in ({}, {0: (0, 1, 2, 3)},
                           {**native, 3: (4096, 0, 0, 0)}):
            with self.subTest(native=incomplete), self.assertRaises(ValueError):
                T.compile_terrain(document, incomplete, minimal, map_ids=[])
        for malformed in (None, allocation(stream_ranges=()),
                          allocation(owned_tile32_ids=(1, 1)),
                          allocation(tile32_capacity=0),
                          allocation(stream_ranges=((0x20000, 0x24000),
                                                    (0x23000, 0x28000)))):
            with self.subTest(allocation=malformed), self.assertRaises(ValueError):
                T.compile_terrain(document, native, malformed, map_ids=[])

    def test_unselected_terrain_neither_consumes_nor_reserves_owned_ids(self):
        data = fixture()
        for entry in data["maps"]:
            entry["tiles16"] = [[900] * 32 for _ in range(32)]
        data["maps"][0]["tiles16"] = [[99] * 32 for _ in range(32)]
        data["maps"][1]["tiles16"] = [[10] * 32 for _ in range(32)]
        native = {0: (0,) * 4, 1: (99,) * 4, 2: (98,) * 4}
        result = T.compile_terrain(parse(data), native,
                    allocation(tile32_capacity=3, owned_tile32_ids=(1,)),
                    map_ids=[0xA1])
        self.assertEqual(result.new_definitions, ((1, (10,) * 4),))
        self.assertEqual([p.map_id for p in result.maps], [0xA1])
        self.assertEqual(set(result.maps[0].tiles32), {1})

    def test_later_selected_native_reuse_is_reserved_before_allocation(self):
        data = fixture()
        for entry in data["maps"]:
            entry["tiles16"] = [[30] * 32 for _ in range(32)]
        data["maps"][1]["tiles16"] = [[10] * 32 for _ in range(32)]
        data["maps"][10]["tiles16"] = [[20] * 32 for _ in range(32)]
        native = {0: (0,) * 4, 1: (20,) * 4, 2: (99,) * 4}
        result = T.compile_terrain(parse(data), native,
                    allocation(tile32_capacity=3, owned_tile32_ids=(1, 2)),
                    map_ids=(0xAA, 0xA1))
        self.assertEqual(result.new_definitions, ((2, (10,) * 4),))
        self.assertEqual([p.map_id for p in result.maps], [0xA1, 0xAA])
        self.assertEqual(set(result.maps[0].tiles32), {2})
        self.assertEqual(set(result.maps[1].tiles32), {1})

    def test_malformed_map_selections_refuse(self):
        document, native, owned = parse(fixture()), definitions(), allocation()
        malformed = ([True], [False], [0x9F], [0xC0], [0xA1 + 0.0],
                     ["A1"], [[0xA1]], [0xA1, 0xA1],
                     (area for area in (0xA1, 0xA1)),
                     1, 3.14, "", "A1", b"", {"bad": 0xA1})
        for requested in malformed:
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                T.compile_terrain(document, native, owned, map_ids=requested)
        with self.assertRaises(TypeError):
            T.compile_terrain(document, native, owned, [0xA1])

    def test_legacy_none_is_identical_to_explicit_all_maps(self):
        document, native, owned = parse(fixture()), definitions(), allocation()
        legacy = T.compile_terrain(document, native, owned)
        self.assertEqual(legacy, T.compile_terrain(document, native, owned,
                                                   map_ids=None))
        self.assertEqual(legacy, T.compile_terrain(document, native, owned,
                           map_ids=reversed(range(0xA0, 0xC0))))

    def test_all_32_maps_read_back_exactly_without_mutating_inputs(self):
        data, native = fixture(), definitions()
        document = parse(data)
        original = copy.deepcopy((document, native))
        result = T.compile_terrain(document, native, allocation())
        self.assertEqual((document, native), original)
        self.assertEqual([p.map_id for p in result.maps], list(range(0xA0, 0xC0)))
        self.assertEqual(len(result.stream_writes), 64)
        self.assertEqual(sum(len(s.payload) for s in result.stream_writes), 16576)
        rebuilt_defs = {**native, **dict(result.new_definitions)}
        spans = []
        for plan, source in zip(result.maps, data["maps"]):
            high, low = (T.decode_literal_stream(s.payload) for s in (plan.high, plan.low))
            ids = [a * 256 + b for a, b in zip(high, low)]
            rebuilt = [[None] * 32 for _ in range(32)]
            for index, tile in enumerate(ids):
                row, column = divmod(index, 16)
                for q, value in enumerate(rebuilt_defs[tile]):
                    rebuilt[row * 2 + q // 2][column * 2 + q % 2] = value
            self.assertEqual(rebuilt, source["tiles16"])
            self.assertEqual(ids[0], 0)
            self.assertEqual(plan.properties, source["authoring"]["properties"])
            for stream in (plan.high, plan.low):
                self.assertEqual(stream.payload[-1], 255)
                self.assertEqual(stream.pc // 0x8000,
                                 (stream.pc + len(stream.payload) - 1) // 0x8000)
                spans.append((stream.pc, stream.pc + len(stream.payload)))
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))
        self.assertEqual(result, T.compile_terrain(document, native, allocation()))

    def test_native_matches_reserved_before_allocating_other_quartets(self):
        data = fixture()
        for entry in data["maps"]:
            entry["tiles16"] = [[10] * 32 for _ in range(32)]
        data["maps"][-1]["tiles16"] = [[20] * 32 for _ in range(32)]
        native = {0: (0,) * 4, 1: (20,) * 4, 2: (99,) * 4}
        result = T.compile_terrain(parse(data), native,
                                   allocation(tile32_capacity=3, owned_tile32_ids=(1, 2)))
        self.assertEqual(result.new_definitions, ((2, (10,) * 4),))
        self.assertEqual(set(result.maps[-1].tiles32), {1})
        native = {0: (20,) * 4, 1: (20,) * 4, 2: (99,) * 4}
        result = T.compile_terrain(parse(data), native,
                                   allocation(tile32_capacity=3, owned_tile32_ids=(0,)))
        self.assertEqual(result.new_definitions, ((0, (10,) * 4),))
        self.assertEqual(set(result.maps[-1].tiles32), {1})

    def test_existing_high_tile32_ids_emit_native_high_low_byte_order(self):
        data = fixture()
        for entry in data["maps"]:
            entry["tiles16"] = [[(y % 2) * 2 + x % 2 for x in range(32)]
                                for y in range(32)]
        native = {index: (4095,) * 4 for index in range(0x2200)}
        native[0x2103] = (0, 1, 2, 3)
        result = T.compile_terrain(parse(data), native,
                    allocation(tile32_capacity=0x2200, owned_tile32_ids=()))
        self.assertEqual(result.new_definitions, ())
        for plan in result.maps:
            self.assertEqual(T.decode_literal_stream(plan.high.payload), b"\x21" * 256)
            self.assertEqual(T.decode_literal_stream(plan.low.payload), b"\x03" * 256)

    def test_missing_ownership_capacity_and_invalid_definitions_refuse(self):
        document = parse(fixture())
        for owned in ((), (1,), (True,), (1, 1), (128,)):
            with self.subTest(owned=owned), self.assertRaises(ValueError):
                T.compile_terrain(document, definitions(), allocation(owned_tile32_ids=owned))
        for native in ({}, {0: (0,) * 4}, {**definitions(), 3: (4096, 0, 0, 0)}):
            with self.subTest(native_size=len(native)), self.assertRaises(ValueError):
                T.compile_terrain(document, native, allocation())

    def test_bank_edges_disjoint_spans_and_fastrom_pointer_roundtrip(self):
        result = T.compile_terrain(parse(fixture()), definitions(), allocation(
            stream_ranges=((0x27FFE, 0x28110), (0x3F0000, 0x3F8000))))
        self.assertEqual(result.maps[0].high.pc, 0x28000)
        self.assertEqual(result.maps[0].low.pc, 0x3F0000)
        for stream in result.stream_writes:
            self.assertGreaterEqual(stream.snes >> 16, 0x80)
            pc = ((stream.snes & 0x7F0000) >> 1) | (stream.snes & 0x7FFF)
            self.assertEqual(pc, stream.pc)
        for ranges in ((), ((0x20000, 0x22000),), ((0x20000, 0x24000), (0x23000, 0x28000)),
                       ((0x400000, 0x410000),), ((False, 0x28000),)):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                T.compile_terrain(parse(fixture()), definitions(), allocation(stream_ranges=ranges))

    def test_last_row_and_right_column_quadrants_do_not_wrap(self):
        self.assertEqual(T.quadrant_map_plan(0xA0), (0xA0, 0xA1, 0xA8, 0xA9))
        self.assertEqual(T.quadrant_map_plan(0xB7), (0xB7, 0xB7, 0xBF, 0xBF))
        self.assertEqual(T.quadrant_map_plan(0xB8), (0xB8, 0xB9, 0xB8, 0xB9))
        self.assertEqual(T.quadrant_map_plan(0xBF), (0xBF,) * 4)
        for area in range(0xA0, 0xC0):
            for source in T.quadrant_map_plan(area):
                self.assertIn(source, range(0xA0, 0xC0))
        for area in (0x9F, 0xC0, True):
            with self.assertRaises(ValueError):
                T.quadrant_map_plan(area)

    def test_exact_schema_numeric_types_duplicate_keys_and_profile_refusals(self):
        mutations = (
            lambda d: d.update(schema_version=True),
            lambda d: d.update(schema_version=2),
            lambda d: d.update(columns=8.0),
            lambda d: d.update(extra="unknown"),
            lambda d: d["maps"].pop(),
            lambda d: d["maps"][0].update(map_id=0xBF),
            lambda d: d["maps"][0]["tiles16"][0].pop(),
            lambda d: d["maps"][0]["tiles16"][0].__setitem__(0, True),
            lambda d: d["maps"][0]["tiles16"][0].__setitem__(0, 4096),
            lambda d: d["profile"].update(graphics_fingerprint="f" * 64),
            lambda d: d["maps"][0]["authoring"]["properties"].update(main_palette=2),
        )
        for mutate in mutations:
            data = fixture()
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                parse(data)
        text = json.dumps(fixture()).replace('"schema_version": 3',
                                             '"schema_version": 3, "schema_version": 3')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            T.parse_terrain_document(text, profile())
        with self.assertRaisesRegex(ValueError, "4 MiB"):
            T.parse_terrain_document(" " * (T.MAX_DOCUMENT_BYTES + 1), profile())
        text = json.dumps(fixture()).replace('"schema_version": 3', '"schema_version": NaN')
        with self.assertRaisesRegex(ValueError, "numeric constant"):
            T.parse_terrain_document(text, profile())

    def test_runtime_metadata_never_silently_disappears(self):
        for key in ("sprites", "doors", "exits"):
            data = fixture()
            data["maps"][0]["authoring"][key] = [{"id": 1}]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Unsupported runtime"):
                parse(data)
        data = fixture()
        data["flight_points"] = [{"id": 1}]
        with self.assertRaisesRegex(ValueError, "flight_points"):
            parse(data)

    def test_story_state_bindings_require_external_verification(self):
        data = fixture()
        auth = data["maps"][0]["authoring"]
        auth["asset_bindings"] = ["a" * 64, "b" * 64, "c" * 64]
        auth["properties"]["music"] = [1, 2, 3, 4]
        with self.assertRaisesRegex(ValueError, "independently verified"):
            parse(data)
        document = T.parse_terrain_document(json.dumps(data), profile(),
                    expected_asset_bindings={0xA0: tuple(auth["asset_bindings"])})
        result = T.compile_terrain(document, definitions(), allocation())
        self.assertEqual(result.maps[0].properties["music"], [1, 2, 3, 4])
        auth["asset_bindings"] = ["", "", ""]
        with self.assertRaisesRegex(ValueError, "default map properties"):
            parse(data)

    def test_edges_preserve_selected_and_undecided_passages(self):
        data = fixture()
        data["edge_connections"] = [
            {"id": 1, "map_a": 0x99, "map_b": 0xA1,
             "passage": {"first_tile": 14, "last_tile": 17}},
            {"id": 2, "map_a": 0xA0, "map_b": 0xA8, "passage": None}]
        document = parse(data)
        result = T.compile_terrain(document, definitions(), allocation())
        self.assertEqual(list(document.edge_connections), data["edge_connections"])
        self.assertEqual(result.edge_connections, document.edge_connections)
        bad_edges = (
            {"id": 1, "map_a": 0xA7, "map_b": 0xA8, "passage": None},
            {"id": 1, "map_a": 0xA1, "map_b": 0x99, "passage": None},
            {"id": 1, "map_a": 0x90, "map_b": 0x98, "passage": None},
            {"id": 1, "map_a": 0xA0, "map_b": 0xA8,
             "passage": {"first_tile": 18, "last_tile": 17}},
            {"id": True, "map_a": 0xA0, "map_b": 0xA8, "passage": None},
        )
        for edge in bad_edges:
            data["edge_connections"] = [edge]
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                parse(data)
        data["edge_connections"] = [copy.deepcopy(data["edge_connections"][0])] * 2
        with self.assertRaises(ValueError):
            parse(data)
        edge = {"id": 1, "map_a": 0xA0, "map_b": 0xA8, "passage": None}
        data["edge_connections"] = [edge, {**edge, "id": 2}]
        with self.assertRaisesRegex(ValueError, "Duplicate Lyra edge map pair"):
            parse(data)

    def test_project_relative_asset_resolution_and_duplicate_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            assets.mkdir()
            terrain = assets / "terrain.json"
            terrain.write_text(json.dumps(fixture()))
            project = root / "project.yaze"
            project.write_text("[project]\nname=Lyra\n[files]\nlyra_terrain_file=assets/terrain.json\n")
            self.assertEqual(T.resolve_project_terrain(project), terrain.resolve())
            project.write_text(f"[files]\nlyra_terrain_file={terrain}\n")
            self.assertEqual(T.resolve_project_terrain(project), terrain.resolve())
            project.write_text("[files]\nlyra_terrain_file=x\nlyra_terrain_file=y\n")
            with self.assertRaisesRegex(ValueError, "Malformed Yaze project"):
                T.resolve_project_terrain(project)
            project.write_text("[DEFAULT]\nlyra_terrain_file=assets/terrain.json\n[files]\n")
            with self.assertRaisesRegex(ValueError, "no Lyra terrain asset"):
                T.resolve_project_terrain(project)
            real = root / "real"
            real.mkdir()
            target = real / "project.yaze"
            target.write_text("[files]\nlyra_terrain_file=assets/terrain.json\n")
            link = root / "opened.yaze"
            link.symlink_to(target)
            self.assertEqual(T.resolve_project_terrain(link), terrain.resolve())


if __name__ == "__main__":
    unittest.main()
