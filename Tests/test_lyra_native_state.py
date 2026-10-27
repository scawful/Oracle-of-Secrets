"""Native consumer drift, legacy compatibility, and conflicting return rows."""
import copy
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts/Build"))
import lyra_native_state as S


# Complete reviewed instruction fixtures, including entry-to-scanner branches
# and the eventual LDA.l $1BBB73,X. No actual ROM is needed by the test suite.
HOOK_ENTRANCE_BODY = bytes.fromhex(
    "c231a52018690700850038ed08072d0a070a0a0a8506a5224a4a4a850238ed0c072d0e07186506a8"
    "aabf00207e0a0a0aaaa52f29ff00d059bf02803d29ff41c9e900f02bc94901f04cc96901f047bbbf"
    "02207e0a0a0aaabf00803d29ff41c94941f030c96941f02bc9e940d0608888bba9a40d227cc91ba9"
    "a60d9f02207ea002002283c91be230a9158d2f01a90185146b803a88889c920629ff03c96901d012"
    "afc5f37e290f00c90300b021a918008d92069838e980008d9806e220a9158d2f0164b09c9006a90c"
    "8511e2306bbf04803d29ff018500bf06803d29ff018502a26000a500dff69234d008a502df589334"
    "f01ecaca10ec9cb804e2306badb804d0f8eeb804a905008df01ce2305caafd0f988500a20201a500"
    "caca3067df71ba1bd0f6ad0a04df6fb91bd0ebafd3f37e29ff00d032adda0229ff00c90100f0bdaf"
    "ccf37e29ff00f01ec90500f019c90e00f014c90100f00fc90700f005c90800d09be0760090968a4a"
    "aae220bf73bb1b8d0e01644d6446a90f8510a9068d0c01641164b0e2306b")
INLINE_ENTRANCE_BODY = bytes.fromhex(
    "c231a52018690700850038ed08072d0a070a0a0a8506a5224a4a4a850238ed0c072d0e07186506a8"
    "aabf00207e0a0a0aaaa52f29ff00d059bf0280bd29ff41c9e900f02bc94901f04cc96901f047bbbf"
    "02207e0a0a0aaabf0080bd29ff41c94941f030c96941f02bc9e940d0608888bba9a40d227cc91ba9"
    "a60d9f02207ea002002283c91be230a9158d2f01a90185146b803a88889c920629ff03c96901d012"
    "afc5f37e290f00c90300b021a918008d92069838e980008d9806e220a9158d2f0164b09c9006a90c"
    "8511e2306bbf0480bd29ff018500bf0680bd29ff018502a25600a500dfbfb81bd008a502df17b91b"
    "f01ecaca10ec9cb804e2306badb804d0f8eeb804a905008df01ce2305caafd0f988500a20201a500"
    "caca3067df71ba1bd0f6ad0a04df6fb91bd0ebafd3f37e29ff00d032adda0229ff00c90100f0bdaf"
    "ccf37e29ff00f01ec90500f019c90e00f014c90100f00fc90700f005c90800d09be0760090968a4a"
    "aae220bf73bb1b8d0e01644d6446a90f8510a9068d0c01641164b0e2306b")


def pc(address):
    return (address >> 16 & 127) * 32768 + (address & 32767)


def put(source, address, data):
    source[pc(address):pc(address) + len(data)] = data


def fixture(*, inline=False):
    source = bytearray(0x200000)
    for address in S.TAIL_LOAD_SITES:
        put(source, address, bytes.fromhex("bf80f27e"))
    for address, _ in S.TAIL_STORE_SITES:
        put(source, address, bytes.fromhex("9f80f27e"))
    for _, _, address, expected in S.BINDINGS:
        put(source, address, bytes.fromhex(expected))
    put(source, 0x1BBBF4, bytes.fromhex("226791346b"))
    put(source, 0x349167, bytes.fromhex("8b4bab22709134ab6b"))
    put(source, 0x349170, HOOK_ENTRANCE_BODY)
    if inline:
        put(source, 0x1BBBF4, INLINE_ENTRANCE_BODY)
    put(source, 0x02D998, bytes.fromhex(S.ENTRANCE_ROOM_VARIANTS[1][1]))
    put(source, 0x0FF008, S.ENTRANCE_ROOM_TRAMPOLINE)
    put(source, S.EXIT_ROOMS, b"\xff\xff" * 79)
    # Independent concrete conflict: entrance0B on map4B -> room83 -> map4B.
    put(source, 0x0F8016, b"\x83\x00")
    put(source, 0x02C829, b"\x44\x00")  # Stale vanilla table must not win.
    put(source, 0x1BB9D9, b"\x4b\x00")  # regular row53
    put(source, S.ENTRANCE_TILES + 53 * 2, b"\x2e\x1a")
    put(source, S.ENTRANCE_IDS + 53, b"\x0b")
    put(source, 0x02DDDC, b"\x83\x00")  # exit row41
    put(source, 0x02DE51, b"\x4b")
    return source


# Source caller prefixes copied from reviewed b917146d; each test remains ROM-free.
TAIL_CALLER_FIXTURES = {
    'Frame8': (0x348A58, bytes.fromhex('20cb84e6c8a5c8c91ed0269cc60464b09c10079ce4029cc10f9c1a019c1b019c1c019c1d01a68a22bef634092022d7f634')),
    'Castle_EndAnimation': (0x348ABC, bytes.fromhex('e6b064c89cc60464b09c10079ce4029cc10f9c1a019c1b019c1c019c1d01a91b8d2f01a68a22bef634092022d7f634')),
    'TailPalace_Frame2': (0x348D99, bytes.fromhex('a5c8f0034cba8dc230a9f10aa22803227cc91ba9f30aa2a803227cc91be230e61420cb84e6c8a5c8c91ed02ae6b064c89cc60464b09c10079ce4029cc10f9c1a019c1b019c1c019c1d01a68a22bef634092022d7f634')),
    'Goron_Frame4': (0x348EB9, bytes.fromhex('a5c8f0034cd58ec230a98707a2a00f227cc91be230e614a91b8d2f0120cb84e6c8a5c8c91ed02ae6b064c89cc60464b09c10079ce4029cc10f9c1a019c1b019c1c019c1d01a68a22bef634092022d7f634')),
    'Fortress_Frame4': (0x3490EA, bytes.fromhex('a5c8f0034c0b91c230a99c09a25403227cc91ba99c09a25603227cc91be230e614e6c8a5c8c91ed053e6b064c89cc60464b09c10079ce4029cc10f9c1a019c1b019c1c019c1d01a68a22bef634092022d7f634')),
    'Sprite_Octoboss_Long': (0x3096AA, bytes.fromhex('8b4babbd900ed04fa9049d400e9ea00bdaa68a22bef634')),
    'EmergeWaitGiveItem': (0x309AED, bytes.fromhex('bd000ed015bd900d1a9d900dc9099005a9099d900da9029d000ebd100ed01cfe800d20f3a0bcb00ea90799800ddaa68a22bef634094022d7f634')),
    'Sprite_Goron_Prep': (0x2CDE8D, bytes.fromhex('8b4babadff0ff024ad8a00c955d005a9049d800d2271ba0d2901f008a9059d800d4cc8dea9039d800d4cc8dedaa68a22bef634')),
}


def tail_fixture():
    source = fixture()
    labels = {"TailEvent_Load": 0x34F6BE, "TailEvent_Store": 0x34F6D7,
              "TailEvent_MigrateSave": 0x34F6F0, "LoadCheckpointOrWorld": 0x34F61E,
              "TailEventFlags": 0x7EF4C0, "TailEventVersion": 0x7EF4E0}
    dependency_name, dependency_entry, dependency_hex = S.TAIL_M8_DEPENDENCY
    labels[dependency_name] = dependency_entry
    put(source, dependency_entry, bytes.fromhex(dependency_hex))
    for name, raw in S.TAIL_HELPERS.items():
        put(source, labels[name], bytes.fromhex(raw))
    for address in S.TAIL_LOAD_SITES:
        put(source, address, bytes.fromhex("22bef634"))
    for address, prefix in S.TAIL_STORE_SITES:
        put(source, address - 2, bytes.fromhex(prefix + "22d7f634"))
    for name, (address, raw) in TAIL_CALLER_FIXTURES.items():
        labels[name] = address
        put(source, address, raw)
    put(source, 0x028192, bytes.fromhex("5c1ef634"))
    put(source, 0x34F61E, bytes.fromhex("22f0f634"))
    symbols = "[labels]\n" + "\n".join(
        f"{address >> 16:02X}:{address & 65535:04X} Oracle_{name}" for name, address in labels.items())
    claims = []
    for name, base, size in (("TailEventFlags", 0x7EF4C0, 32), ("TailEventVersion", 0x7EF4E0, 1)):
        row = dict(id=name, base=base, size=size, status="shared", space="save_buffer",
                   condition={}, aliases=[],
                   binding=dict(source="shared:Core/sram.asm", symbol=name, bank00_mirror=False))
        if name == "TailEventFlags":
            row.update(count=32, stride=1)
        claims.append(row)
    return source, symbols, dict(claims=claims, allocation_available=False)


class AuthoredEndpointBindingTest(unittest.TestCase):
    def plan(self, source, area, *, door=None, exit=None, areas=None):
        shape = dict(parent_map_id=0xA1, size='large', maps=[0xA1,0xA2,0xA9,0xAA])
        metadata = dict(doors=[] if door is None else [door], exits=[] if exit is None else [exit])
        return S.plan_native_state(source, [area], authoring=[(area,metadata)],
                                   gameplay_areas=(shape,) if areas is None else areas)

    def door_source(self, area=0xAA, x=5, y=6):
        source = fixture()
        tile = 2*(x+(area-0xA1)%8*32+64*(y+(area-0xA1)//8*32))
        put(source,S.ENTRANCE_SCREENS+53*2,(0xA1).to_bytes(2,'little'))
        put(source,S.ENTRANCE_TILES+53*2,tile.to_bytes(2,'little'))
        return source,dict(id=1,x=x,y=y,entrance_id=0x0B),tile

    def test_every_large_member_resolves_door_tile_and_parent_before_entrance_id(self):
        for area in (0xA1,0xA2,0xA9,0xAA):
            source,door,tile = self.door_source(area)
            row = self.plan(source,area,door=door)['requested_doors'][0]
            self.assertEqual((row['parent_map_id'],row['expected_tile_index']),(0xA1,tile))
            self.assertEqual(row['consumed_row']['row'],53)
            self.assertTrue(row['tile_match_verified'])
            self.assertFalse(row['allocation_granted'])

    def test_higher_duplicate_with_another_id_shadows_an_existing_correct_entrance(self):
        source,door,tile = self.door_source()
        put(source,S.ENTRANCE_SCREENS+128*2,(0xA1).to_bytes(2,'little'))
        put(source,S.ENTRANCE_TILES+128*2,tile.to_bytes(2,'little'))
        put(source,S.ENTRANCE_IDS+128,b'\x0c')
        row = self.plan(source,0xAA,door=door)['requested_doors'][0]
        self.assertEqual(row['matching_rows'][0]['row'],53)
        self.assertEqual(row['consumed_row']['row'],128)
        self.assertFalse(row['tile_match_verified'])

    def test_wrong_tile_unassigned_shape_and_drifted_scanner_do_not_admit_door(self):
        source,door,tile = self.door_source()
        door['x'] += 1
        self.assertFalse(self.plan(source,0xAA,door=door)['requested_doors'][0]['tile_match_verified'])
        source,door,_ = self.door_source()
        row = self.plan(source,0xAA,door=door,areas=())['requested_doors'][0]
        self.assertIsNone(row['parent_map_id'])
        self.assertIsNone(row['expected_tile_index'])
        self.assertFalse(row['tile_match_verified'])
        source[pc(0x1BBBF4)] ^= 1
        self.assertFalse(self.plan(source,0xAA,door=door)['requested_doors'][0]['tile_match_verified'])

    def test_physical_exit_cell_matches_global_pixel_destination_without_rewriting_camera(self):
        source=fixture(); area=0xAA; entry=dict(id=2,x=5,y=6,room_id=0x83,exit_row=41)
        put(source,S.EXIT_MAPS+41,bytes([area]))
        x=(area&7)*512+5*16; y=((area&0x3F)>>3)*512+6*16
        put(source,S.EXIT_PLAYER_X+41*2,(x+7).to_bytes(2,'little'))
        put(source,S.EXIT_PLAYER_Y+41*2,(y+15).to_bytes(2,'little'))
        row=self.plan(source,area,exit=entry)['requested_returns'][0]
        self.assertTrue(row['requested_row_consumed'])
        self.assertTrue(row['position_match_verified'])
        self.assertEqual(row['expected_player_cell'],dict(x=x,y=y))
        self.assertFalse(row['save_reopen_supported'])
        put(source,S.EXIT_PLAYER_X+41*2,(x+16).to_bytes(2,'little'))
        self.assertFalse(self.plan(source,area,exit=entry)['requested_returns'][0]['position_match_verified'])

    def test_higher_exit_duplicate_and_cached_room_do_not_invent_an_authored_destination(self):
        source=fixture();entry=dict(id=2,x=0,y=0,room_id=0x83,exit_row=41)
        put(source,S.EXIT_ROOMS+78*2,(0x83).to_bytes(2,'little'))
        put(source,S.EXIT_MAPS+78,b'\xa0')
        row=self.plan(source,0xAA,exit=entry)['requested_returns'][0]
        self.assertFalse(row['requested_row_consumed'])
        self.assertFalse(row['position_match_verified'])
        entry['room_id']=0x100
        row=self.plan(source,0xAA,exit=entry)['requested_returns'][0]
        self.assertEqual(row['path'],'cached_entrance')
        self.assertIsNone(row['saved_player_position'])
        self.assertFalse(row['position_match_verified'])

    def test_malformed_explicit_shape_is_not_treated_as_unassigned(self):
        source,door,_=self.door_source()
        for bad in (None,False,{},''):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                S.plan_native_state(source,[0xAA],authoring=[(0xAA,dict(doors=[door],exits=[]))],
                                    gameplay_areas=bad)


class LyraNativeStateTest(unittest.TestCase):
    def test_legacy_ids_keep_exact_address_including_99(self):
        rows = [S.legacy_event_row(area) for area in range(160)]
        self.assertEqual([r["legacy_address"] for r in rows], list(range(0x7EF280, 0x7EF320)))
        self.assertEqual(rows[0x99]["legacy_address"], 0x7EF319)
        self.assertTrue(all(r["compatibility"] == "legacy_unchanged" for r in rows))
        self.assertFalse(rows[0x7F]["aliases_other_owner"])
        self.assertEqual(rows[0x80]["owner"], "story_extension")
        self.assertEqual(rows[0x90]["owner"], "item_extension")

    def test_tail_addresses_are_saved_aliases_not_granted_event_storage(self):
        plan = S.plan_native_state(fixture(), list(range(0xA0, 0xC0)))
        self.assertTrue(plan["consumers_verified"])
        self.assertEqual([r["legacy_address"] for r in plan["event_rows"]],
                         list(range(0x7EF320, 0x7EF340)))
        self.assertIsNone(plan["persistent_event_storage"])
        self.assertIsNone(plan["event_initialization_migration"])
        self.assertEqual(plan["save"]["buffer"], [0x7EF000, 0x7EF500])
        self.assertEqual(plan["save"]["checksum_address"], 0x7EF4FE)
        self.assertTrue(all(not c["persisted"] for c in plan["caches"]))
        self.assertFalse(plan["allocation_granted"])
        self.assertFalse(plan["runtime_ready"])
        self.assertIn("SAVE_DEATH_CONTINUE_POLICY_UNCHOSEN",
                      [r["code"] for r in plan["runtime_blockers"]])

    def test_every_fixed_consumer_drift_refuses_verification(self):
        for name, _, address, _ in S.BINDINGS:
            with self.subTest(consumer=name):
                source = fixture()
                source[pc(address)] ^= 1
                result = S.plan_native_state(source, [0xA1])
                self.assertFalse(result["consumers_verified"])
                self.assertIn(name, result["runtime_blockers"][0]["consumers"])

    def test_active_hook_selects_scanner_and_ignores_unreachable_old_copy(self):
        source = fixture()
        put(source, 0x359280, S.ENTRANCE_SCAN)
        self.assertTrue(S.plan_native_state(source, [])["consumers_verified"])
        for address in (0x1BBBF4, 0x349167, 0x349266, 0x349280):
            with self.subTest(address=address):
                changed = source.copy()
                changed[pc(address)] ^= 1
                result = S.plan_native_state(changed, [])
                self.assertIn("entrance_scan", result["runtime_blockers"][0]["consumers"])

    def test_actual_zs_room_decoder_wins_over_vanilla_table(self):
        metadata = dict(doors=[dict(id=1, entrance_id=0x0B)], exits=[])
        result = S.plan_native_state(fixture(), [0xB0], authoring=[(0xB0, metadata)])
        door = result["requested_doors"][0]
        self.assertEqual(result["entrance_room_decoder"]["table_snes"], 0x0F8000)
        self.assertEqual(door["resolved_room_id"], 0x83)
        self.assertEqual(door["matching_rows"], [])
        self.assertEqual(door["same_entrance_other_maps"],
                         [dict(row=53, map_id=0x4B, tile_index=0x1A2E)])
        self.assertFalse(door["tile_match_verified"])
        source = fixture()
        source[pc(0x0FF008) + 6] ^= 1  # DB selection cannot drift silently.
        result = S.plan_native_state(source, [0xB0], authoring=[(0xB0, metadata)])
        self.assertIsNone(result["entrance_room_decoder"])
        self.assertIsNone(result["requested_doors"][0]["resolved_room_id"])

    def test_saved_editor_inline_scanner_is_bound_separately_from_normal_build_hook(self):
        source = fixture(inline=True)
        result = S.plan_native_state(source, [])
        self.assertTrue(result["consumers_verified"])
        binding = next(r for r in result["consumers"] if r["id"] == "entrance_scan")
        self.assertEqual(binding["variant"], "inline_source")
        self.assertEqual(binding["scanner_pc"], pc(0x1BBD04))

    def test_early_rtl_before_scanner_refuses_for_both_actual_paths(self):
        for inline, entry in ((False, 0x349170), (True, 0x1BBBF4)):
            with self.subTest(inline=inline):
                source = fixture(inline=inline)
                source[pc(entry) + 2] = 0x6B
                result = S.plan_native_state(source, [0xB0])
                self.assertFalse(result["consumers_verified"])
                self.assertIn("entrance_scan", result["runtime_blockers"][0]["consumers"])

    def test_redirected_entrance_id_reader_refuses_for_both_actual_paths(self):
        for inline, entry in ((False, 0x349170), (True, 0x1BBBF4)):
            with self.subTest(inline=inline):
                source = fixture(inline=inline)
                reader = pc(entry) + 0x16B
                self.assertEqual(source[reader:reader + 4], bytes.fromhex("bf73bb1b"))
                source[reader + 1] = 0x74
                result = S.plan_native_state(source, [0xB0])
                self.assertFalse(result["consumers_verified"])
                self.assertIn("entrance_scan", result["runtime_blockers"][0]["consumers"])

    def test_vanilla_room_decoder_is_a_separate_supported_consumer(self):
        source = fixture()
        put(source, 0x02D998, bytes.fromhex(S.ENTRANCE_ROOM_VARIANTS[0][1]))
        result = S.plan_native_state(source, [])
        self.assertTrue(result["consumers_verified"])
        self.assertEqual(result["entrance_room_decoder"]["table_snes"], 0x02C813)

    def test_room83_keeps_existing_return_and_needs_explicit_binding(self):
        result = S.room_return(fixture(), 0x83, 0xB0, None)
        self.assertEqual(result["path"], "custom_exit_table")
        self.assertEqual(result["consumed_row"], dict(row=41, map_id=0x4B))
        self.assertFalse(result["requested_row_consumed"])
        self.assertFalse(S.room_return(fixture(), 0x83, 0xB0, 41)["requested_row_consumed"])
        self.assertTrue(S.room_return(fixture(), 0x83, 0x4B, 41)["requested_row_consumed"])
        self.assertFalse(result["allocation_granted"])

    def test_cached_room_boundaries_and_custom_104_exception(self):
        for room, path in ((0xFF, "custom_exit_table"), (0x100, "cached_entrance"),
                           (0x104, "custom_exit_table"), (0x17F, "cached_entrance"),
                           (0x180, "custom_exit_table")):
            with self.subTest(room=room):
                result = S.room_return(fixture(), room, 0xB0, None)
                self.assertEqual(result["path"], path)
                self.assertFalse(result["save_reopen_supported"])

    def test_descending_exit_scan_does_not_allow_selecting_shadowed_row(self):
        source = fixture()
        put(source, S.EXIT_ROOMS + 78 * 2, b"\x83\x00")
        put(source, S.EXIT_MAPS + 78, b"\xb0")
        self.assertFalse(S.room_return(source, 0x83, 0x4B, 41)["requested_row_consumed"])
        self.assertTrue(S.room_return(source, 0x83, 0xB0, 78)["requested_row_consumed"])
        self.assertIsNone(S.room_return(source, 0x432, 0xB0, None)["consumed_row"])

    def test_invalid_selection_and_exit_slot_refuse(self):
        for maps in ([True], [0xC0], [0xA1, 0xA1], [[0xA1]], ["A1"]):
            with self.subTest(maps=maps), self.assertRaises(ValueError):
                S.plan_native_state(fixture(), maps)
        for row in (-1, 79, True):
            with self.subTest(row=row), self.assertRaises(ValueError):
                S.room_return(fixture(), 0x83, 0xB0, row)

    def test_tail_variant_binds_active_helpers_callers_migration_and_named_ledger(self):
        source, symbols, ledger = tail_fixture()
        plan = S.plan_native_state(source, [0x00, 0x99, 0xA0, 0xBF], symbols=symbols, ownership=ledger)
        self.assertTrue(plan["consumers_verified"])
        impl = plan["event_implementation"]
        self.assertTrue(impl["verified"])
        self.assertTrue(all(row["verified"] for row in impl["bindings"]))
        self.assertEqual(impl["writer_width_bits"], 8)
        self.assertFalse(impl["multi_byte_tail_store_supported"])
        self.assertEqual([row["effective_event_address"] for row in plan["event_rows"]],
                         [0x7EF280, 0x7EF319, 0x7EF4C0, 0x7EF4DF])
        self.assertEqual(plan["event_rows"][1]["compatibility"], "legacy_unchanged")
        self.assertEqual(plan["event_rows"][2]["legacy_address"], 0x7EF320)
        self.assertEqual(plan["persistent_event_storage"]["bytes"], 32)
        self.assertEqual(plan["event_initialization_migration"]["current_version"], 0xA1)
        self.assertEqual([row["code"] for row in plan["runtime_blockers"]],
                         ["SAVE_DEATH_CONTINUE_POLICY_UNCHOSEN", "ENTRY_RETURN_BINDING_UNQUALIFIED"])
        self.assertFalse(plan["runtime_ready"])
        self.assertFalse(plan["allocation_granted"])

    def test_tail_helper_mutation_and_redirected_live_target_ignore_dead_copy(self):
        source, symbols, ledger = tail_fixture()
        cases = [(0x34F6BE, 0x6B), (0x34F6D7, 0x6B), (0x34F6F0, 0x6B),
                 (0x02EF56 + 1, 0xD7), (0x1BC0CC + 1, 0xBE)]
        for address, value in cases:
            with self.subTest(address=address):
                changed = source.copy()
                put(changed, 0x35F6BE, bytes.fromhex(S.TAIL_HELPERS["TailEvent_Load"]))
                changed[pc(address)] = value
                plan = S.plan_native_state(changed, [0xA0], symbols=symbols, ownership=ledger)
                self.assertFalse(plan["consumers_verified"])
                self.assertIsNone(plan["persistent_event_storage"])

    def test_each_fixed_site_and_source_caller_refuses_drift_or_mixed_legacy(self):
        source, symbols, ledger = tail_fixture()
        sites = [(a, "load") for a in S.TAIL_LOAD_SITES]
        sites += [(a, "store") for a, _ in S.TAIL_STORE_SITES]
        for address, kind in sites:
            with self.subTest(site=address):
                changed = source.copy()
                put(changed, address, bytes.fromhex("bf80f27e" if kind == "load" else "9f80f27e"))
                self.assertFalse(S.plan_native_state(changed, [0xA0], symbols=symbols,
                                                    ownership=ledger)["consumers_verified"])
        for name, (address, _) in TAIL_CALLER_FIXTURES.items():
            with self.subTest(caller=name):
                changed = source.copy()
                changed[pc(address)] = 0x6B
                self.assertFalse(S.plan_native_state(changed, [0xA0], symbols=symbols,
                                                    ownership=ledger)["consumers_verified"])

    def test_missing_migration_hook_call_or_body_refuses_storage_recognition(self):
        source, symbols, ledger = tail_fixture()
        for address in (0x028192, 0x34F61E, 0x34F6F0 + 5):
            with self.subTest(address=address):
                changed = source.copy()
                changed[pc(address)] ^= 1
                plan = S.plan_native_state(changed, [0xBF], symbols=symbols, ownership=ledger)
                self.assertFalse(plan["event_implementation"]["verified"])
                self.assertIsNone(plan["event_initialization_migration"])
                self.assertIn("EVENT_INITIALIZATION_MIGRATION_UNCHOSEN",
                              [row["code"] for row in plan["runtime_blockers"]])

    def test_missing_divergent_duplicate_or_overlapping_claims_fail_closed(self):
        source, symbols, ledger = tail_fixture()
        cases = [None, dict(claims=[]), copy.deepcopy(ledger), copy.deepcopy(ledger),
                 copy.deepcopy(ledger), copy.deepcopy(ledger)]
        cases[2]["claims"][0]["base"] += 1
        cases[3]["claims"].append(copy.deepcopy(ledger["claims"][0]))
        cases[4]["claims"].append(dict(id="other", base=0x7EF4D0, size=1, space="save_buffer"))
        cases[5]["claims"][1]["binding"]["symbol"] = "other"
        for value in cases:
            with self.subTest(ledger=value):
                plan = S.plan_native_state(source, [0xA0], symbols=symbols, ownership=value)
                self.assertFalse(plan["consumers_verified"])
                self.assertIsNone(plan["persistent_event_storage"])

    def test_symbols_are_required_and_cannot_select_a_different_helper_or_caller(self):
        source, symbols, ledger = tail_fixture()
        for value in (None, symbols.replace("34:F6BE Oracle_TailEvent_Load", "35:F6BE Oracle_TailEvent_Load"),
                      symbols.replace("34:8A58 Oracle_Frame8", "35:8A58 Oracle_Frame8"),
                      symbols + "\n34:F6BE Oracle_TailEvent_Load"):
            with self.subTest(symbols=value):
                plan = S.plan_native_state(source, [0xA0], symbols=value, ownership=ledger)
                self.assertFalse(plan["consumers_verified"])
        # Returning all fixed hooks to legacy cannot advertise the new helpers.
        legacy = fixture()
        self.assertFalse(S.plan_native_state(legacy, [0xA0], symbols=symbols,
                                            ownership=ledger)["consumers_verified"])

    def test_m8_store_context_change_refuses_tail_variant(self):
        source, symbols, ledger = tail_fixture()
        for address, _ in S.TAIL_STORE_SITES:
            with self.subTest(address=address):
                changed = source.copy()
                changed[pc(address) - 2] = 0xEA
                self.assertFalse(S.plan_native_state(changed, [0xA0], symbols=symbols,
                                                    ownership=ledger)["consumers_verified"])

    def test_relabeling_each_caller_to_a_matching_dead_copy_cannot_hide_live_damage(self):
        source, symbols, ledger = tail_fixture()
        for name, _, _, calls in S.TAIL_SOURCE_CALLERS:
            with self.subTest(caller=name):
                changed = source.copy()
                changed.extend(bytes(0x400000 - len(changed)))
                address, body = TAIL_CALLER_FIXTURES[name]
                put(changed, 0x7DF000, body)
                changed[pc(address) + calls[0][0]] = 0xEA
                stale = f"{address >> 16:02X}:{address & 65535:04X} Oracle_{name}"
                relabeled = symbols.replace(stale, f"7D:F000 Oracle_{name}")
                result = S.plan_native_state(changed, [0xBF], symbols=relabeled, ownership=ledger)
                self.assertFalse(result["consumers_verified"])
                self.assertIn(f"Unreviewed source caller entry: {name}",
                              result["event_implementation"]["failures"])

    def test_physical_wram_and_ambiguous_overlaps_cannot_hide_behind_space_name(self):
        source, symbols, ledger = tail_fixture()
        for space in ("wram", "save_buffer", "unknown_physical_space"):
            with self.subTest(space=space):
                changed = copy.deepcopy(ledger)
                changed["claims"].append(dict(id="foreign_wram", space=space, base=0x7EF4C5, size=1))
                result = S.plan_native_state(source, [0xA0], symbols=symbols, ownership=changed)
                self.assertFalse(result["consumers_verified"])
                self.assertIsNone(result["persistent_event_storage"])

    def test_m8_restorer_operand_and_dead_dependency_relabel_refuse(self):
        source, symbols, ledger = tail_fixture()
        changed = source.copy()
        name, address, raw = S.TAIL_M8_DEPENDENCY
        self.assertEqual(changed[pc(address) + 23:pc(address) + 26], bytes.fromhex("e22060"))
        changed[pc(address) + 24] = 0
        result = S.plan_native_state(changed, [0xBF], symbols=symbols, ownership=ledger)
        self.assertFalse(result["consumers_verified"])
        self.assertIn("tail_m8_ShakeScreen", result["event_implementation"]["failures"])
        changed.extend(bytes(0x400000 - len(changed)))
        put(changed, 0x7DF000, bytes.fromhex(raw))
        relabeled = symbols.replace("34:84CB Oracle_ShakeScreen", "7D:F000 Oracle_ShakeScreen")
        result = S.plan_native_state(changed, [0xBF], symbols=relabeled, ownership=ledger)
        self.assertFalse(result["consumers_verified"])
        self.assertIn("Unreviewed M8 dependency entry", result["event_implementation"]["failures"])

    def test_compiled_diagnostic_never_changes_full_image_shape_guard_or_input_bytes(self):
        source, symbols, ledger = tail_fixture()
        source = bytes(source[:0x1B0000])
        before = S._sha(source)
        with self.assertRaisesRegex(ValueError, "2MiB or4MiB"):
            S.plan_native_state(source, [0xA1], symbols=symbols, ownership=ledger)
        report = S.inspect_compiled_dispatch(source, [0xA1], symbols=symbols, ownership=ledger)
        self.assertTrue(report["consumers_verified"])
        self.assertEqual(report["source_rom_sha256"], before)
        self.assertEqual(report["source_rom_bytes"], 0x1B0000)
        self.assertEqual(report["image_scope"], "compiled_dispatch_inspection_only")
        self.assertFalse(report["runtime_ready"])
        self.assertIn("COMPOSED_IMAGE_IDENTITY_UNQUALIFIED", [b["code"] for b in report["runtime_blockers"]])
        self.assertEqual(S._sha(source), before)

    def test_read_only_compiled_cli_records_exact_inputs(self):
        source, symbols, ledger = tail_fixture()
        # Exercise the CLI with virtual files; this test writes no ROM file.
        files = {"fixture.sfc": bytes(source[:0x1B0000]), "fixture.sym": symbols.encode(),
                 "claims.json": json.dumps(ledger).encode()}
        before = copy.deepcopy(files)
        output = io.StringIO()
        with mock.patch.object(Path, "resolve", lambda path, **kwargs: path), \
             mock.patch.object(Path, "read_bytes", lambda path: files[str(path)]), \
             mock.patch.object(Path, "read_text", lambda path: files[str(path)].decode()):
            with contextlib.redirect_stdout(output):
                status = S.main(["--rom", "fixture.sfc", "--symbols", "fixture.sym", "--ownership", "claims.json",
                                 "--map", "0xA1", "--inspect-compiled-dispatch"])
            self.assertEqual(status, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(len(result["inputs"]), 3)
            self.assertEqual(result["source_rom_bytes"], 0x1B0000)
            self.assertEqual(files, before)


if __name__ == "__main__":
    unittest.main()
