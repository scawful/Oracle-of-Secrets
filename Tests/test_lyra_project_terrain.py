"""Saved Yaze terrain compilation using synthetic definitions and owned spans."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_terrain as T


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
    def transport_document(self):
        data = fixture()
        data.update(schema_version=7, gameplay_areas=[], next_flight_point_id=8)
        for entry in data["maps"]:
            entry["authoring"]["properties"].update(copy.deepcopy(T.RUNTIME_PROPERTY_DEFAULTS))
        data["flight_points"] = [{"id": 7, "map_id": 0xA0, "x": 4, "y": 5,
                                  "name": "Sea point", "runtime_slot": None}]
        data["boat_transport"] = {
            "source_root": "/private/tmp/oracle-transport-source",
            "source_path": "Data/overworld/kalyxo_boat_placements.asm",
            "source_template": "%stv2_exit(0186, $98, $07B0, $00C0, 0, $06)\n"
                               "%stv2_exit(0187, $30, $0D70, $0300, 1, $06)\n",
            "endpoints": [
                {"exit_id": 0x186, "parent_map": 0x98, "world_x": 0xC1,
                 "world_y": 0x7B3, "area_size": 0, "facing": 6, "name": "Sea shore"},
                {"exit_id": 0x187, "parent_map": 0x30, "world_x": 0x300,
                 "world_y": 0xD70, "area_size": 1, "facing": 6, "name": "Kalyxo Docks"}]}
        return data

    def parse_transport(self, data, **kwargs):
        return T.parse_terrain_document(json.dumps(data), profile(),
                                         allow_authoring_drafts=True, **kwargs)

    def whirlpool_document(self):
        data = self.transport_document()
        data.update(schema_version=8, whirlpool_transport={
            "source_root": "C:/private/oracle-source",
            "source_path": "Data/overworld/whirlpool_placements.asm",
            "source_template": "; preserved baseline\n" + "".join(
                f"%whirlpool_route({slot}, {slot}, {slot}, 128, {slot * 512 + 128}, "
                "$1000, $FFFF, 0, 0, 0, $FFFA, $FFF6) ; route\n"
                for slot in range(8)),
            "routes": [dict(zip(T.WHIRLPOOL_FIELDS,
                                (slot, slot, 128, slot * 512 + 128,
                                 0x1000, 0xFFFF, 0, 0, 0, 0xFFFA, 0xFFF6)))
                       for slot in range(8)]})
        return data

    def resource_document(self):
        data = self.whirlpool_document()
        data.update(schema_version=9, next_native_resource_id=10)
        for entry in data["maps"]:
            entry["authoring"]["native_resources"] = None
        data["maps"][0]["authoring"]["native_resources"] = {
            "secrets": [{"id": 9, "x": 31, "y": 0, "secret_id": 0x86},
                        {"id": 7, "x": 0, "y": 31, "secret_id": 0xFF}],
            "event_behavior": {"kind": "native_secret_v1"}}
        return data

    def test_schema9_preserves_resources_order_counter_and_schema8_transport(self):
        data = self.resource_document()
        data["maps"][1]["authoring"]["native_resources"] = {
            "secrets": [], "event_behavior": None}
        data["maps"][-1]["authoring"]["native_resources"] = {
            "secrets": [{"id": 1, "x": 0, "y": 0, "secret_id": 0}],
            "event_behavior": None}
        before = copy.deepcopy(data)
        parsed = self.parse_transport(data)
        self.assertEqual(parsed.next_native_resource_id, 10)
        self.assertEqual(parsed.authoring, tuple(entry["authoring"] for entry in before["maps"]))
        self.assertEqual([s["id"] for s in parsed.authoring[0]["native_resources"]["secrets"]], [9, 7])
        self.assertEqual(parsed.authoring[0]["native_resources"]["secrets"][1]["secret_id"], 0xFF)
        self.assertEqual(parsed.authoring[1]["native_resources"], {"secrets": [], "event_behavior": None})
        self.assertIsNone(parsed.authoring[2]["native_resources"])
        legacy = self.parse_transport(self.whirlpool_document())
        for field in ("profile", "maps", "properties", "edge_connections", "flight_points",
                      "gameplay_areas", "boat_transport", "next_flight_point_id", "whirlpool_transport"):
            self.assertEqual(getattr(parsed, field), getattr(legacy, field), field)
        parsed.authoring[0]["native_resources"]["secrets"][0]["x"] = 0
        parsed.authoring[1]["native_resources"]["secrets"].append({"id": 1})
        self.assertEqual(data, before)

    def test_schema9_retains_null_empty_and_unknown_secret_drafts_but_refuses_strict_mode(self):
        for resources in (None, {"secrets": [], "event_behavior": None},
                          {"secrets": [], "event_behavior": {"kind": "native_secret_v1"}},
                          self.resource_document()["maps"][0]["authoring"]["native_resources"]):
            data = self.resource_document()
            for entry in data["maps"]:
                entry["authoring"]["native_resources"] = None
            data["maps"][0]["authoring"]["native_resources"] = copy.deepcopy(resources)
            with self.subTest(resources=resources):
                self.assertEqual(self.parse_transport(data).authoring[0]["native_resources"], resources)
                with self.assertRaisesRegex(ValueError, "Unsupported runtime metadata: native_resources"):
                    parse(data)

    def test_schema9_requires_exact_header_authoring_resource_and_record_keys(self):
        mutations = (
            lambda d: d.pop("next_native_resource_id"),
            lambda d: d.update(extra=1),
            lambda d: d["maps"][-1]["authoring"].pop("native_resources"),
            lambda d: d["maps"][0]["authoring"].update(extra=1),
            lambda d: d["maps"][0]["authoring"]["native_resources"].pop("secrets"),
            lambda d: d["maps"][0]["authoring"]["native_resources"].pop("event_behavior"),
            lambda d: d["maps"][0]["authoring"]["native_resources"].update(next_id=10),
            lambda d: d["maps"][0]["authoring"]["native_resources"]["secrets"][0].pop("secret_id"),
            lambda d: d["maps"][0]["authoring"]["native_resources"]["secrets"][0].update(bomb_offset=0),
        )
        for index, mutate in enumerate(mutations):
            data = self.resource_document()
            mutate(data)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "Malformed"):
                self.parse_transport(data)

    def test_schema9_rejects_wrong_resource_container_and_event_shapes(self):
        for value in (True, 0, [], "unselected"):
            data = self.resource_document()
            data["maps"][0]["authoring"]["native_resources"] = value
            with self.subTest(resources=value), self.assertRaisesRegex(ValueError, "native resources"):
                self.parse_transport(data)
        for value in (None, True, {}, "", [None]):
            data = self.resource_document()
            data["maps"][0]["authoring"]["native_resources"]["secrets"] = value
            with self.subTest(secrets=value), self.assertRaisesRegex(ValueError, "native secret"):
                self.parse_transport(data)
        for value in (True, [], "native_secret_v1", {}, {"kind": "script"},
                      {"kind": None}, {"kind": True}, {"kind": 1},
                      {"kind": "native_secret_v1", "flags": 2}):
            data = self.resource_document()
            data["maps"][0]["authoring"]["native_resources"]["event_behavior"] = value
            with self.subTest(event=value), self.assertRaisesRegex(ValueError, "native event behavior"):
                self.parse_transport(data)

    def test_schema9_rejects_invalid_secret_numeric_fields(self):
        for field, invalid in (
                ("id", (True, False, 1.0, "1", None, -1, 0, 0x100000000)),
                ("x", (True, False, 0.0, "0", None, -1, 32)),
                ("y", (True, False, 0.0, "0", None, -1, 32)),
                ("secret_id", (True, False, 0.0, "0", None, -1, 256))):
            for value in invalid:
                data = self.resource_document()
                data["maps"][0]["authoring"]["native_resources"]["secrets"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "native secret"):
                    self.parse_transport(data)

    def test_schema9_secret_ids_are_global_but_independent_of_other_families(self):
        for map_index in (0, 1, 31):
            data = self.resource_document()
            resources = data["maps"][map_index]["authoring"]["native_resources"]
            if resources is None:
                resources = {"secrets": [], "event_behavior": None}
                data["maps"][map_index]["authoring"]["native_resources"] = resources
            resources["secrets"].append({"id": 9, "x": 1, "y": 1, "secret_id": 1})
            with self.subTest(map_index=map_index), self.assertRaisesRegex(ValueError, "duplicate Lyra native secret"):
                self.parse_transport(data)
        data = self.resource_document()
        parsed = self.parse_transport(data)
        self.assertEqual(parsed.flight_points[0]["id"], 7)
        self.assertEqual(parsed.authoring[0]["native_resources"]["secrets"][1]["id"], 7)

    def test_schema9_preserves_persisted_high_water_and_exhaustion_without_allocating(self):
        for value in (True, False, 1.0, "10", None, -1, 0, 9, 0x100000001):
            data = self.resource_document()
            data["next_native_resource_id"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "next_native_resource_id"):
                self.parse_transport(data)
        data = self.resource_document()
        data["maps"][0]["authoring"]["native_resources"]["secrets"][0]["id"] = 0xFFFFFFFF
        data["next_native_resource_id"] = 0x100000000
        self.assertEqual(self.parse_transport(data).next_native_resource_id, 0x100000000)
        for entry in data["maps"]:
            entry["authoring"]["native_resources"] = None
        for value in (1, 123, 0x100000000):
            data["next_native_resource_id"] = value
            self.assertEqual(self.parse_transport(data).next_native_resource_id, value)

    def test_schema9_rejects_duplicate_json_keys_at_each_new_boundary(self):
        text = json.dumps(self.resource_document())
        for original, replacement in (
                ('"next_native_resource_id": 10', '"next_native_resource_id": 10, "next_native_resource_id": 10'),
                ('"native_resources": null', '"native_resources": null, "native_resources": null'),
                ('"event_behavior": {', '"event_behavior": null, "event_behavior": {'),
                ('"secret_id": 134', '"secret_id": 134, "secret_id": 134'),
                ('"kind": "native_secret_v1"', '"kind": "native_secret_v1", "kind": "native_secret_v1"')):
            self.assertIn(original, text)
            with self.subTest(original=original), self.assertRaisesRegex(ValueError, "Duplicate JSON"):
                T.parse_terrain_document(text.replace(original, replacement, 1), profile(),
                                         allow_authoring_drafts=True)

    def test_schema9_history_blocks_compilation_even_for_empty_or_unselected_subsets(self):
        from dataclasses import replace
        legacy = parse(fixture())
        self.assertFalse(T.has_native_resource_history(legacy))
        baseline = T.compile_terrain(legacy, definitions(), allocation(), map_ids=[0xA0])
        self.assertEqual([row.map_id for row in baseline.maps], [0xA0])
        variants = []
        for resources, counter in ((None, 1), (None, 123), (None, 0x100000000),
                                   ({"secrets": [], "event_behavior": None}, 1),
                                   ({"secrets": [{"id": 1, "x": 31, "y": 31, "secret_id": 255}],
                                     "event_behavior": None}, 2)):
            data = self.resource_document()
            for entry in data["maps"]:
                entry["authoring"]["native_resources"] = None
            data["maps"][-1]["authoring"]["native_resources"] = resources
            data["next_native_resource_id"] = counter
            variants.append(self.parse_transport(data))
        variants.append(replace(legacy, next_native_resource_id=2))
        for index, document in enumerate(variants):
            before = copy.deepcopy(document)
            self.assertTrue(T.has_native_resource_history(document))
            for selected in ([], [0xA0], None):
                with self.subTest(index=index, selected=selected), self.assertRaisesRegex(
                        ValueError, "NATIVE_RESOURCES_UNBOUND"):
                    T.compile_terrain(document, definitions(), allocation(), map_ids=selected)
            self.assertEqual(document, before)

    def test_resource_history_rejects_invalid_constructed_counter_without_normalizing(self):
        from dataclasses import replace
        legacy = parse(fixture())
        for counter in (True, 1.0, "1", 0, -1, 0x100000001):
            document = replace(legacy, next_native_resource_id=counter)
            with self.subTest(counter=counter), self.assertRaisesRegex(ValueError, "next_native_resource_id"):
                T.has_native_resource_history(document)

    def test_legacy_schemas_keep_unselected_resources_and_reject_schema9_extras(self):
        for version in range(3, 9):
            if version == 4:
                data, bindings = self.palette_document()
            else:
                data, bindings = self.whirlpool_document(), None
                data["schema_version"] = version
                if version < 8:
                    del data["whirlpool_transport"]
                if version < 7:
                    del data["boat_transport"], data["next_flight_point_id"]
                if version < 6:
                    for entry in data["maps"]:
                        for key in T.RUNTIME_PROPERTY_DEFAULTS:
                            del entry["authoring"]["properties"][key]
                if version < 5:
                    del data["gameplay_areas"]
                elif version == 5:
                    data["gameplay_areas"] = [{"parent_map_id": 0xA0, "size": "small", "maps": [0xA0]}]
            before = copy.deepcopy(data)
            with self.subTest(version=version):
                parsed = self.parse_transport(data, expected_asset_bindings=bindings)
                self.assertEqual(parsed.next_native_resource_id, 1)
                self.assertEqual(parsed.authoring, tuple(e["authoring"] for e in data["maps"]))
                self.assertTrue(all("native_resources" not in auth for auth in parsed.authoring))
                self.assertEqual(data, before)
                for domain in ("header", "authoring"):
                    extra = copy.deepcopy(data)
                    if domain == "header":
                        extra["next_native_resource_id"] = 1
                    else:
                        extra["maps"][0]["authoring"]["native_resources"] = None
                    with self.subTest(domain=domain), self.assertRaisesRegex(ValueError, "Malformed"):
                        self.parse_transport(extra, expected_asset_bindings=bindings)

    def test_schema8_preserves_edited_routes_raw_words_and_immutable_template(self):
        data = self.whirlpool_document()
        data["gameplay_areas"] = [{"parent_map_id": 0xB0, "size": "large",
                                    "maps": [0xB0, 0xB1, 0xB8, 0xB9]}]
        route = data["whirlpool_transport"]["routes"][0]
        route.update(source_map=0xB0, destination_map=0xB0, world_x=1000, world_y=4000)
        before = copy.deepcopy(data)
        parsed = self.parse_transport(data)
        self.assertEqual(parsed.whirlpool_transport, before["whirlpool_transport"])
        self.assertEqual(parsed.boat_transport, before["boat_transport"])
        self.assertEqual(parsed.next_flight_point_id, 8)
        self.assertEqual(parsed.whirlpool_transport["routes"][0]["scroll_mod_x"], 0xFFF6)
        parsed.whirlpool_transport["routes"][0]["world_x"] = 0
        self.assertEqual(data, before)
        data["whirlpool_transport"] = None
        self.assertIsNone(self.parse_transport(data).whirlpool_transport)
        del data["whirlpool_transport"]
        with self.assertRaisesRegex(ValueError, "header keys"):
            self.parse_transport(data)

    def test_schema8_rejects_malformed_route_shape_and_numeric_fields(self):
        original = self.whirlpool_document()
        for field in T.WHIRLPOOL_FIELDS:
            maximum = 0xBF if field.endswith("_map") else 4088 if field.startswith("world_") else 65535
            for value in (True, 0.0, -1, maximum + 1):
                data = copy.deepcopy(original)
                data["whirlpool_transport"]["routes"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "route"):
                    self.parse_transport(data)
        for count in (0, 7, 9):
            data = copy.deepcopy(original)
            data["whirlpool_transport"]["routes"] = (data["whirlpool_transport"]["routes"] * 2)[:count]
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "eight ordered"):
                self.parse_transport(data)
        for source in (1, 0x1B):
            data = copy.deepcopy(original)
            data["whirlpool_transport"]["routes"][0]["source_map"] = source
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "source parents"):
                self.parse_transport(data)
        for target in ("binding", "route"):
            data = copy.deepcopy(original)
            binding = data["whirlpool_transport"]
            (binding if target == "binding" else binding["routes"][0])["future"] = 1
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "keys"):
                self.parse_transport(data)

    def test_schema8_requires_numeric_complete_template_without_executing_source(self):
        original = self.whirlpool_document()
        for key, value in (("source_root", "relative"), ("source_root", "x" * 4097),
                           ("source_path", "../other.asm"), ("source_template", ""),
                           ("source_template", "x\0"), ("source_template", "x" * 65537)):
            data = copy.deepcopy(original)
            data["whirlpool_transport"][key] = value
            with self.subTest(key=key, value=value[:20]), self.assertRaises(ValueError):
                self.parse_transport(data)
        template = original["whirlpool_transport"]["source_template"]
        changes = (("%whirlpool_route(7,", "%whirlpool_route(8,"),
                   ("%whirlpool_route(7,", "%whirlpool_route(0,"),
                   ("$FFFF", "$10000"), ("$FFFF", "1+1"),
                   ("$FFFF", "-1"), ("$FFFF", "+1"),
                   (", $FFF6)", ")"), ("%whirlpool_route(0, 0,", "%whirlpool_route(0, 27,"))
        for old, new in changes:
            data = copy.deepcopy(original)
            data["whirlpool_transport"]["source_template"] = template.replace(old, new)
            with self.subTest(new=new), self.assertRaisesRegex(ValueError, "Whirlpool"):
                self.parse_transport(data)
        data = copy.deepcopy(original)
        data["whirlpool_transport"]["source_template"] = template + "%whirlpool_route(\n"
        with self.assertRaisesRegex(ValueError, "complete numeric"):
            self.parse_transport(data)

    def test_schema8_tail_routes_require_explicit_parent_and_exact_arrival_footprint(self):
        for size, width, height, members in (
                ("small", 512, 512, [0xA0]), ("wide", 1024, 512, [0xA0, 0xA1]),
                ("tall", 512, 1024, [0xA0, 0xA8]),
                ("large", 1024, 1024, [0xA0, 0xA1, 0xA8, 0xA9])):
            data = self.whirlpool_document()
            data["gameplay_areas"] = [{"parent_map_id": 0xA0, "size": size, "maps": members}]
            route = data["whirlpool_transport"]["routes"][0]
            route.update(source_map=0xA0, destination_map=0xA0,
                         world_x=width - 1, world_y=2048 + height - 1)
            with self.subTest(size=size):
                self.parse_transport(data)
            for field, value in (("world_x", width), ("world_y", 2047),
                                 ("world_y", 2048 + height),
                                 ("source_map", 0xA1), ("destination_map", 0xA1)):
                bad = copy.deepcopy(data)
                bad["whirlpool_transport"]["routes"][0][field] = value
                with self.subTest(size=size, field=field), self.assertRaisesRegex(ValueError, "explicit"):
                    self.parse_transport(bad)
            data["gameplay_areas"] = []
            with self.assertRaisesRegex(ValueError, "explicit gameplay area"):
                self.parse_transport(data)

    def test_schema7_preserves_transport_subtile_values_and_schema6_runtime_fields(self):
        data = self.transport_document()
        auth = data["maps"][-1]["authoring"]
        auth["properties"].update(mosaic=12, subscreen_overlay=0xA1,
                                   area_specific_bg_color=0x1234)
        auth["asset_bindings"] = ["a" * 64, "b" * 64, "c" * 64]
        before = copy.deepcopy(data)
        parsed = self.parse_transport(data, expected_asset_bindings={0xBF: tuple(auth["asset_bindings"])})
        self.assertEqual(parsed.boat_transport, data["boat_transport"])
        self.assertEqual(parsed.next_flight_point_id, 8)
        self.assertEqual(parsed.properties[-1], auth["properties"])
        self.assertEqual(parsed.flight_points[0], data["flight_points"][0])
        self.assertEqual(len(parsed.maps), 32)
        parsed.boat_transport["endpoints"][0]["world_x"] = 0
        self.assertEqual(data, before)

    def test_schema7_counter_is_nonrewinding_and_can_represent_exhaustion(self):
        original = self.transport_document()
        for value in (True, 0, 7, 0x100000001):
            data = copy.deepcopy(original)
            data["next_flight_point_id"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "next_flight_point_id"):
                self.parse_transport(data)
        original["flight_points"][0]["id"] = 0xFFFFFFFF
        original["next_flight_point_id"] = 0x100000000
        self.assertEqual(self.parse_transport(original).next_flight_point_id, 0x100000000)

    def test_schema7_rejects_invalid_or_duplicate_endpoint_payloads(self):
        for key, value in (("exit_id", True), ("exit_id", 0x187), ("world_x", 512),
                           ("parent_map", 0xC0), ("area_size", 4), ("facing", 1),
                           ("name", "bad\x00name"), ("name", "x" * 81)):
            data = self.transport_document()
            data["boat_transport"]["endpoints"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.parse_transport(data)

    def test_schema7_source_shape_is_strict_without_filesystem_access(self):
        for key, value in (("source_root", "relative"), ("source_path", "../other.asm"),
                           ("source_template", ""), ("source_template", "x\0"),
                           ("source_template", "x" * 65537), ("endpoints", [])):
            data = self.transport_document()
            data["boat_transport"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_transport(data)
        data = self.transport_document()
        data["boat_transport"]["unexpected"] = 1
        with self.assertRaisesRegex(ValueError, "Malformed boat transport keys"):
            self.parse_transport(data)

    def test_schema7_null_boat_and_legacy_counter_derivation(self):
        data = self.transport_document()
        data["boat_transport"] = None
        self.assertIsNone(self.parse_transport(data).boat_transport)
        data["schema_version"] = 6
        del data["boat_transport"], data["next_flight_point_id"]
        parsed = self.parse_transport(data)
        self.assertIsNone(parsed.boat_transport)
        self.assertEqual(parsed.next_flight_point_id, 8)
        self.assertEqual(parsed.properties[0]["mosaic"], 0)

    def test_schema7_rejects_unknown_header_and_runtime_property_keys(self):
        for domain in ("header", "properties"):
            data = self.transport_document()
            target = data if domain == "header" else data["maps"][0]["authoring"]["properties"]
            target["future"] = 1
            with self.subTest(domain=domain), self.assertRaisesRegex(ValueError, "Malformed"):
                self.parse_transport(data)
        data = self.transport_document()
        data["schema_version"] = 10
        with self.assertRaisesRegex(ValueError, "Expected Yaze Lyra schema"):
            self.parse_transport(data)

    def palette_document(self):
        data = fixture()
        data["schema_version"] = 4
        auth = data["maps"][31]["authoring"]
        auth["properties"]["background_palette"] = list(range(127)) + [0x7FFF]
        auth["asset_bindings"] = ["a" * 64, "b" * 64, "c" * 64]
        return data, {0xBF: tuple(auth["asset_bindings"])}

    def test_schema4_palette_survives_parse_and_selected_compile_without_aliasing(self):
        data, bindings = self.palette_document()
        original = copy.deepcopy(data)
        document = T.parse_terrain_document(json.dumps(data), profile(),
            expected_asset_bindings=bindings, allow_authoring_drafts=True)
        result = T.compile_terrain(document, definitions(), allocation(),
                                   map_ids=[0xBF])
        expected = original["maps"][31]["authoring"]["properties"]
        self.assertEqual(document.properties[31], expected)
        self.assertEqual(document.authoring[31], original["maps"][31]["authoring"])
        self.assertEqual(result.maps[0].properties, expected)
        self.assertNotIn("background_palette", document.properties[0])
        result.maps[0].properties["background_palette"][127] = 0
        self.assertEqual(document.properties[31]["background_palette"][127], 0x7FFF)
        self.assertEqual(data, original)

    def test_schema4_palette_requires_verified_bindings_and_explicit_draft_mode(self):
        data, bindings = self.palette_document()
        with self.assertRaisesRegex(ValueError, "Unsupported runtime metadata.*background_palette"):
            T.parse_terrain_document(json.dumps(data), profile(), expected_asset_bindings=bindings)
        for verified in (None, {0xBF: ("d" * 64,) * 3}):
            with self.subTest(verified=verified), self.assertRaisesRegex(
                    ValueError, "independently verified source assets"):
                T.parse_terrain_document(json.dumps(data), profile(),
                    expected_asset_bindings=verified, allow_authoring_drafts=True)
        data["maps"][31]["authoring"]["asset_bindings"] = [""] * 3
        with self.assertRaisesRegex(ValueError, "default map properties"):
            T.parse_terrain_document(json.dumps(data), profile(), allow_authoring_drafts=True)

    def test_schema4_matches_yaze_palette_shape_and_version_rules(self):
        original, bindings = self.palette_document()
        malformed = (None, {}, "native", [0] * 127, [0] * 129,
                     [-1] + [0] * 127, [0] * 127 + [0x8000],
                     [0.0] + [0] * 127, [True] + [0] * 127,
                     [2**64 - 1] + [0] * 127)
        for palette in malformed:
            data = copy.deepcopy(original)
            data["maps"][31]["authoring"]["properties"]["background_palette"] = palette
            with self.subTest(palette=palette), self.assertRaisesRegex(ValueError, "128 BGR555"):
                T.parse_terrain_document(json.dumps(data), profile(),
                    expected_asset_bindings=bindings, allow_authoring_drafts=True)
        legacy = copy.deepcopy(original)
        legacy["schema_version"] = 3
        with self.assertRaisesRegex(ValueError, "map properties keys"):
            T.parse_terrain_document(json.dumps(legacy), profile(),
                expected_asset_bindings=bindings, allow_authoring_drafts=True)
        no_override = fixture()
        no_override["schema_version"] = 4
        with self.assertRaisesRegex(ValueError, "schema 4 requires"):
            T.parse_terrain_document(json.dumps(no_override), profile(), allow_authoring_drafts=True)

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
