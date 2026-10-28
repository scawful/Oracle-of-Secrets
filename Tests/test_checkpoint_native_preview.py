"""Private native ferry/Sky checkpoint preview: host derivation and registry
shape only. No game, Save, gameplay or native-route proof."""
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import checkpoint_registry as C
import lyra_joint_art as J
import lyra_project_admission as A

FERRY_HEX = ('30001600100d8802600d0003300090087f0d0703000c1e0d00000003200b000e00ff00'
             '040020380000000000000000000000')
SKY_HEX = ('87001600a000180ef000900e870002050f01970e00001e01000e000f20ff0002000d00'
           '1000203b1000000000000000000000')
FERRY_FLOOR, DECK, SKY_FLOOR, WALL = 0xFC0, 0x10, 0x34, 0x20


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path):
    return dict(path=str(path), sha256=sha(Path(path).read_bytes()))


def grid_sha(grid):
    flat = [tile for row in grid for tile in row]
    return sha(struct.pack(f'<{len(flat)}H', *flat))


def put(image, address, raw):
    at = A.pc(address)
    image[at:at + len(raw)] = raw


def put_row(image, name, index, value):
    spec = next(s for s in A.SPECS if s[0] == name)
    at = A.pc(spec[1]) + (index - spec[3]) * spec[5]
    image[at:at + spec[5]] = value.to_bytes(spec[5], 'little')


def a0_cache():
    cache = bytearray(range(50))
    cache[0:2] = cache[12:14] = (0xA0).to_bytes(2, 'little')
    return bytes(cache)


def native_source():
    """Hollow 2 MiB source holding only the rows/atlas/types the derivation reads."""
    image = bytearray(0x200000)
    image[0x865:0x868] = (0xBD8000).to_bytes(3, 'little')
    put(image, 0x07DC40, bytes.fromhex('29ff0085060aaa7c2ada'))
    for attr, (address, body) in C._PREVIEW_FLOOR_HANDLERS.items():
        put(image, 0x07DA2A + attr * 2, address.to_bytes(2, 'little'))
        put(image, 0x070000 | address, body)
    atlas = A.pc(0xBD8000)
    for tile, words in ((FERRY_FLOOR, (0x0CCB, 0x0CCC, 0x0CCC, 0x0CCB)), (DECK, (0x0100,) * 4),
                        (SKY_FLOOR, (0x18A0,) * 4), (WALL, (0x0001,) * 4)):
        image[atlas + tile * 8:atlas + tile * 8 + 8] = struct.pack('<4H', *words)
    types = 0x71459
    image[types + 1] = 0x20
    image[types + 0xA0] = 0x48
    image[types + 0x100:types + 0x159] = b'\x09' * 0x59
    for area in (0x30, 0x31):
        put_row(image, 'parent', area, 0x30)
        put_row(image, 'area_size', area, 2)
    put_row(image, 'parent', 0x87, 0x87)
    put_row(image, 'area_size', 0x87, 0)
    for parent, rows in ((0x30, (0xC00, 0, 0xB20, 0xFF00, 0x38)), (0x87, (0, 0xE00, 0xFF20, 0xD00, 0x1B))):
        for name, value in zip(('transition_y', 'transition_x', 'scroll_north', 'scroll_west', 'area_gfx'), rows):
            put_row(image, name, parent, value)
    put_row(image, 'special_sprite_gfx', 0x87, 0x10)
    return bytes(image)


def native_grids():
    ferry = [[FERRY_FLOOR] * 64 for _ in range(32)]
    ferry[23][47] = DECK  # exit-walk cell typed only by the bound ferry data
    return {(0x30, 0x31): ferry, (0x87,): [[SKY_FLOOR] * 32 for _ in range(32)]}


class NativeFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = native_source()
        self.types = self.root / 'ferry.types.bin'
        self.types.write_bytes(bytes(0x59))
        self.packet = self.root / 'PACKET.json'
        self.packet.write_text(json.dumps(dict(ferry=dict(types=pin(self.types)))))
        self.request = dict(transfer_id='3' * 64, live=dict(generation=7, operation_id='fixture-save-seven'))
        self.binding = dict(source_rom_sha256=sha(self.source), transfer_id='3' * 64, generation=7,
                            operation_id='fixture-save-seven', joint_art=pin(self.packet),
                            ferry_types=pin(self.types))
        self.grids = native_grids()
        grid = mock.patch.object(C, '_native_scope_grid', side_effect=lambda image, maps: self.grids[maps])
        grid.start()
        self.addCleanup(grid.stop)

    def image(self, ferry_types=None):
        image = bytearray(A.expanded_rom(self.source))
        raw = self.types.read_bytes() if ferry_types is None else ferry_types
        put(image, J.AREA_DATA[0], raw)
        return bytes(image)

    def landing(self, key):
        spec = C.NATIVE_PREVIEW[key]
        grid = self.grids[spec['maps']]
        point = {3: [768, 352], 4: [144, 240]}[key]
        return dict(kind=C.NATIVE_LANDING_KIND, scope=spec['scope'], key=key, map_id=spec['parent'],
                    parent_map=spec['parent'], region_key=key, local_pixel=point, clear_radius=1,
                    tile16_id=grid[point[1] // 16][point[0] // 16],
                    tile_attributes={3: [0] * 4, 4: [0x48] * 4}[key], grid_sha256=grid_sha(grid),
                    binding=copy.deepcopy(self.binding))


class NativePreviewCacheTests(NativeFixture):
    def test_guarded_source_reproduces_reviewed_ferry_and_sky_caches(self):
        for key, expected in ((3, FERRY_HEX), (4, SKY_HEX)):
            cache, derived = C.native_preview_cache(self.image(), self.landing(key), self.binding)
            self.assertEqual(cache.hex(), expected)
            self.assertEqual(derived['cache_sha256'], sha(cache))
            self.assertFalse(derived['native_gameplay_verified'])
        _, ferry = C.native_preview_cache(self.image(), self.landing(3), self.binding)
        self.assertEqual((ferry['world_pixel'], ferry['stable_after_walk']), ([768, 3424], [768, 3443]))
        _, sky = C.native_preview_cache(self.image(), self.landing(4), self.binding)
        self.assertEqual((sky['world_pixel'], sky['clearance_attributes']), ([3728, 240], [0x48]))

    def test_supplied_cache_claims_are_not_landing_inputs(self):
        for extra in ('exit_cache_hex', 'cache_sha256', 'world_pixel'):
            landing = dict(self.landing(3), **{extra: FERRY_HEX})
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Malformed native preview landing'):
                C.native_preview_cache(self.image(), landing, self.binding)

    def test_save_packet_and_ferry_type_bindings_must_match(self):
        for field, value in (('source_rom_sha256', '0' * 64), ('transfer_id', '0' * 64), ('generation', 8),
                             ('operation_id', 'other-save'), ('joint_art', dict(path='/x', sha256='0' * 64)),
                             ('ferry_types', dict(path=str(self.types), sha256='0' * 64))):
            landing = self.landing(3)
            landing['binding'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'binding differs'):
                C.native_preview_cache(self.image(), landing, self.binding)

    def test_key_scope_map_and_region_are_approved_rows_only(self):
        for field, value in (('key', 5), ('key', True), ('scope', 'native_preview_87'), ('map_id', 0x31),
                             ('parent_map', 0x31), ('region_key', 4), ('region_key', 2), ('kind', 'v1')):
            landing = dict(self.landing(3), **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                C.native_preview_cache(self.image(), landing, self.binding)

    def test_camera_clamp_alignment_and_radius_range(self):
        for point in ([112, 352], [896, 352], [768, 64], [768, 368], [760, 352], [True, 352]):
            with self.subTest(point=point), self.assertRaisesRegex(ValueError, 'camera-legal'):
                C.native_preview_cache(self.image(), dict(self.landing(3), local_pixel=point), self.binding)
        for radius in (0, 5, True, None):
            with self.subTest(radius=radius), self.assertRaisesRegex(ValueError, 'radius 1..4'):
                C.native_preview_cache(self.image(), dict(self.landing(3), clear_radius=radius), self.binding)
        cache, derived = C.native_preview_cache(self.image(), dict(self.landing(4), clear_radius=4), self.binding)
        self.assertEqual((cache.hex(), derived['clear_radius']), (SKY_HEX, 4))

    def test_blocked_clearance_or_exit_walk_cell_refuses(self):
        for x, y in ((49, 21), (48, 24), (47, 24)):  # square corner, then +2 walk cells
            self.grids[(0x30, 0x31)][y][x] = WALL
            with self.subTest(cell=(x, y)), self.assertRaisesRegex(ValueError, 'blocked collision quarter'):
                C.native_preview_cache(self.image(), self.landing(3), self.binding)
            self.grids[(0x30, 0x31)][y][x] = FERRY_FLOOR

    def test_ferry_types_come_from_bound_packet_area_data_not_rom_types(self):
        for raw in (b'\x08' + bytes(0x58), b'\x02' * 0x59):
            with self.subTest(raw=raw[:1]), self.assertRaisesRegex(ValueError, 'blocked collision quarter'):
                C.native_preview_cache(self.image(raw), self.landing(3), self.binding)
        expanded = A.expanded_rom(self.source)
        with self.assertRaisesRegex(ValueError, 'blocked collision quarter'):
            C.native_preview_cache(expanded, self.landing(3), self.binding)

    def test_anchor_grid_topology_and_dispatcher_are_rederived(self):
        for field, value in (('tile16_id', DECK), ('tile_attributes', [0x48] * 4), ('grid_sha256', '0' * 64)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                C.native_preview_cache(self.image(), dict(self.landing(3), **{field: value}), self.binding)
        for name, area, value in (('parent', 0x31, 0x31), ('area_size', 0x30, 0), ('area_size', 0x87, 2)):
            image = bytearray(self.image())
            put_row(image, name, area, value)
            key = 3 if area < 0x80 else 4
            with self.subTest(name=name, area=area), self.assertRaisesRegex(ValueError, 'camera topology'):
                C.native_preview_cache(bytes(image), self.landing(key), self.binding)
        image = bytearray(self.image())
        put(image, 0x07DC47, b'\x00')
        with self.assertRaisesRegex(ValueError, 'floor dispatcher changed'):
            C.native_preview_cache(bytes(image), self.landing(3), self.binding)
        with self.assertRaisesRegex(ValueError, 'expanded packet-applied'):
            C.native_preview_cache(self.source, self.landing(3), self.binding)


class NativePreviewBinderTests(NativeFixture):
    def setUp(self):
        super().setUp()
        self.pins = []
        for key in C.NATIVE_PREVIEW:
            path = self.root / f'landing-{key}.json'
            path.write_text(json.dumps(self.landing(key)))
            self.pins.append(pin(path))
        self.plan = dict(kind=C.PREVIEW_PLAN_V2, bindings=dict(joint_art=pin(self.packet), native_landings=self.pins))
        lo = A.pc(J.AREA_DATA[0])
        self.packet_plan = dict(writes=[dict(pc=[lo, lo + 0x59], payload_hex=self.types.read_bytes().hex())],
                                inputs=[pin(self.packet)])

    def bind(self, runtime=None, plan=None):
        runtime = dict(joint_art=pin(self.packet)) if runtime is None else runtime
        with mock.patch.object(J, 'prepare', return_value=(self.packet_plan, '', b'', b'')) as prepare:
            result = C._bind_native_preview(ROOT, self.request, self.source, plan or self.plan, runtime)
        prepare.assert_called_once_with(runtime['joint_art'], self.request, self.source)
        return result

    def test_binder_applies_packet_and_derives_key_ordered_caches(self):
        caches, derived, inputs = self.bind()
        self.assertEqual([c.hex() for c in caches], [FERRY_HEX, SKY_HEX])
        self.assertEqual([row['key'] for row in derived], [3, 4])
        guarded = {str(ROOT / name) for name in C._NATIVE_SOURCE_GUARDS}
        self.assertTrue(guarded <= {row['path'] for row in inputs})
        self.assertTrue(all(p in inputs for p in (*self.pins, pin(self.packet))))

    def test_policy_packet_landing_order_and_saved_files_must_match(self):
        with self.assertRaisesRegex(ValueError, 'policy joint-art binding'):
            self.bind(runtime=dict(joint_art=dict(path='/other', sha256='0' * 64)))
        with self.assertRaisesRegex(ValueError, 'policy joint-art binding'):
            C._bind_native_preview(ROOT, self.request, self.source, self.plan, {})
        swapped = dict(self.plan, bindings=dict(self.plan['bindings'], native_landings=self.pins[::-1]))
        with self.assertRaisesRegex(ValueError, 'approved key order'):
            self.bind(plan=swapped)
        short = dict(self.plan, bindings=dict(self.plan['bindings'], native_landings=self.pins[:1]))
        with self.assertRaisesRegex(ValueError, 'one landing per native key'):
            self.bind(plan=short)
        Path(self.pins[1]['path']).write_text(json.dumps(dict(self.landing(4), clear_radius=2)))
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            self.bind()

    def test_packet_ferry_types_change_retires_landings(self):
        self.types.write_bytes(b'\x02' + bytes(0x58))
        self.packet.write_text(json.dumps(dict(ferry=dict(types=pin(self.types)))))
        runtime = dict(joint_art=pin(self.packet))
        plan = dict(self.plan, bindings=dict(self.plan['bindings'], joint_art=runtime['joint_art']))
        with self.assertRaisesRegex(ValueError, 'binding differs'):
            self.bind(runtime=runtime, plan=plan)

    def test_tileset_and_graphics_owner_guards_bind_native_dispatch(self):
        self.assertEqual(len(C.native_preview_sources(ROOT)), len(C._NATIVE_SOURCE_GUARDS))
        for name, needles in C._NATIVE_SOURCE_GUARDS.items():
            engine = self.root / ('engine-' + Path(name).stem)
            for other in C._NATIVE_SOURCE_GUARDS:
                (engine / other).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / other, engine / other)
            text = (engine / name).read_text()
            (engine / name).write_text(text.replace(needles[0], needles[0].replace(' ', '  ', 1), 1))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'owner changed'):
                C.native_preview_sources(engine)


class NativePreviewRegistryTests(NativeFixture):
    def setUp(self):
        super().setUp()
        self.goron = (ROOT / 'Overworld/goron_checkpoint.asm').read_text()
        self.control_source = b'diagnostic private plan, not a gameplay ROM'
        receipt, cache_source = self.root / 'save.json', self.root / 'a0-cache.bin'
        receipt.write_text('{"generation":7,"operation_id":"fixture-save-seven"}')
        cache_source.write_bytes(a0_cache())
        landings = []
        for key in C.NATIVE_PREVIEW:
            path = self.root / f'landing-{key}.json'
            path.write_text(json.dumps(self.landing(key)))
            landings.append(pin(path))
        self.bindings = dict(source_rom_sha256=sha(self.control_source), document_sha256='2' * 64,
            transfer_id='3' * 64, live=dict(generation=7, operation_id='fixture-save-seven',
            save_receipt=pin(receipt)), selected_pair=[0xA0, 0xA1], cache_source=pin(cache_source),
            joint_art=pin(self.packet), native_landings=landings)
        self.caches = [a0_cache(), bytes.fromhex(FERRY_HEX), bytes.fromhex(SKY_HEX)]
        entries = []
        for (key, domain, area), cache in zip(((2, 'SPECIAL', 0xA0), (3, 'LIGHT', 0x30), (4, 'SPECIAL', 0x87)),
                                              self.caches):
            entries.append(dict(key=key, domain=domain, native_affinity=0, map_id=area, parent_map=area,
                                region_key=key, exit_cache_hex=cache.hex(), cache_sha256=sha(cache)))
        members = [dict(map_id=m, domain=d, native_affinity=0, region_key=r)
                   for m, d, r in ((0xA0, 'SPECIAL', 2), (0xA1, 'SPECIAL', 2), (0x30, 'LIGHT', 3),
                                   (0x31, 'LIGHT', 3), (0x87, 'SPECIAL', 4))]
        self.plan = dict(kind=C.PREVIEW_PLAN_V2, scope='seeded_private_preview', production_admission=False,
                         epoch=1, bindings=copy.deepcopy(self.bindings), entries=entries, memberships=members)

    def compile(self, **overrides):
        args = dict(private_plan=self.plan, verified_bindings=self.bindings, expected_cache=b''.join(self.caches))
        args.update(overrides)
        return C.runtime_registry(self.control_source, self.goron, **args)

    def refuses(self, pattern=None, **overrides):
        with self.assertRaisesRegex(ValueError, pattern) if pattern else self.assertRaises(ValueError):
            self.compile(**overrides)

    def test_v2_compiles_four_records_nine_members_within_41_byte_margin(self):
        registry = self.compile()
        control = C.goron_control_registry(self.control_source, self.goron)
        self.assertEqual(registry.records[0], control.records[0])
        self.assertEqual([r.key for r in registry.records], [1, 2, 3, 4])
        self.assertEqual([r.region_key for r in registry.records[1:]], [2, 3, 4])
        self.assertEqual(len(registry.memberships), 9)
        for key, domain, area in ((3, C.Domain.LIGHT, 0x30), (4, C.Domain.SPECIAL, 0x87)):
            route = C.resolve_checkpoint(C.SavedCheckpoint(C.SCHEMA, registry.epoch, key), registry=registry,
                                         resume_intent=C.ResumeIntent.REGIONAL)
            self.assertEqual((route.route, route.checkpoint.domain, route.checkpoint.map_id),
                             ('regional_checkpoint', domain, area))
        fit = C.validate_runtime_capacity(registry, 895)
        self.assertEqual((fit['data_bytes'], fit['remaining']), (344, 41))
        C.validate_runtime_capacity(registry, 936)
        with self.assertRaisesRegex(ValueError, 'aggregate exceeds'):
            C.validate_runtime_capacity(registry, 937)
        constants = C.emit_runtime_asm(registry)['constants']
        self.assertIn('!CHECKPOINT_REGISTRY_COUNT = 4\n', constants)
        self.assertIn('!CHECKPOINT_REGION_MEMBER_COUNT = 9\n', constants)

    def test_v1_plan_and_bindings_are_unchanged(self):
        v1_bindings = {k: v for k, v in self.bindings.items() if k not in ('joint_art', 'native_landings')}
        a0 = self.plan['entries'][0]
        v1 = dict(kind='checkpoint.private_preview_plan.v1', scope='seeded_private_preview',
                  production_admission=False, epoch=1, bindings=copy.deepcopy(v1_bindings), entry=a0,
                  memberships=self.plan['memberships'][:2])
        registry = C.runtime_registry(self.control_source, self.goron, private_plan=v1,
                                      verified_bindings=v1_bindings, expected_cache=a0_cache())
        self.assertEqual((len(registry.records), len(registry.memberships)), (2, 6))
        with self.assertRaises(ValueError):
            C.runtime_registry(self.control_source, self.goron, private_plan=v1,
                               verified_bindings=self.bindings, expected_cache=a0_cache())
        self.refuses(verified_bindings=v1_bindings)

    def test_every_cache_must_equal_its_independent_derivation(self):
        self.refuses('every independently derived cache', expected_cache=a0_cache())
        self.refuses('every independently derived cache', expected_cache=b''.join(self.caches)[:-1])
        self.refuses(expected_cache=None)
        for index in (0, 1, 2):
            forged = bytearray(self.caches[index])
            forged[4] ^= 1
            claimed = copy.deepcopy(self.plan)
            claimed['entries'][index].update(exit_cache_hex=forged.hex(), cache_sha256=sha(bytes(forged)))
            with self.subTest(claimed=index):
                self.refuses('independent landing binding', private_plan=claimed)
            derived = list(self.caches)
            derived[index] = bytes(forged)
            with self.subTest(derived=index):
                self.refuses('independent landing binding', expected_cache=b''.join(derived))
            bad_sha = copy.deepcopy(self.plan)
            bad_sha['entries'][index]['cache_sha256'] = '0' * 64
            with self.subTest(sha=index):
                self.refuses('independent landing binding', private_plan=bad_sha)

    def test_entries_are_exact_approved_key_domain_map_region_affinity(self):
        for index, field, value in ((1, 'key', 5), (1, 'domain', 'SPECIAL'), (1, 'map_id', 0x31),
                                    (1, 'parent_map', 0x31), (1, 'region_key', 2), (1, 'native_affinity', 1),
                                    (2, 'domain', 'LIGHT'), (2, 'map_id', 0x80), (2, 'region_key', 3),
                                    (2, 'key', True), (0, 'region_key', 3), (0, 'region_key', 4),
                                    (0, 'region_key', 1), (0, 'map_id', 0xA1)):
            plan = copy.deepcopy(self.plan)
            plan['entries'][index][field] = value
            with self.subTest(index=index, field=field, value=value):
                self.refuses(private_plan=plan)
        for entries in (self.plan['entries'][::-1], self.plan['entries'][:2],
                        [*self.plan['entries'], self.plan['entries'][2]]):
            with self.subTest(entries=len(entries)):
                self.refuses(private_plan=dict(self.plan, entries=entries))
        plan = copy.deepcopy(self.plan)
        plan['entries'][1]['extra'] = 1
        self.refuses('Malformed private checkpoint entry', private_plan=plan)

    def test_memberships_are_exactly_the_derived_maps(self):
        members = self.plan['memberships']
        extra = dict(map_id=0x32, domain='LIGHT', native_affinity=0, region_key=3)
        for changed in (members[:-1], [*members, extra], members[::-1],
                        [*members[:2], dict(members[2], domain='SPECIAL'), *members[3:]],
                        [*members[:4], dict(members[4], region_key=True)]):
            with self.subTest(changed=changed):
                self.refuses('unselected map', private_plan=dict(self.plan, memberships=changed))

    def test_bindings_pin_save_packet_and_landings(self):
        for field, value in (('joint_art', dict(path='/other', sha256='0' * 64)),
                             ('native_landings', self.bindings['native_landings'][::-1])):
            bindings = dict(self.bindings, **{field: value})
            with self.subTest(field=field):
                self.refuses('bindings differ', verified_bindings=bindings)
        for field, value in (('joint_art', dict(path='relative.json', sha256='0' * 64)),
                             ('native_landings', self.bindings['native_landings'][:1]),
                             ('native_landings', None)):
            bindings = dict(self.bindings, **{field: value})
            plan = dict(self.plan, bindings=copy.deepcopy(bindings))
            with self.subTest(malformed=field):
                self.refuses(private_plan=plan, verified_bindings=bindings)
        bindings = dict(self.bindings, extra=1)
        self.refuses('Malformed private checkpoint v2 bindings', verified_bindings=bindings,
                     private_plan=dict(self.plan, bindings=copy.deepcopy(bindings)))
        for path in (self.packet, Path(self.bindings['native_landings'][0]['path'])):
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.subTest(changed=path.name):
                self.refuses('Current saved input changed')
            path.write_bytes(original)
        for field in ('production_admission', 'scope', 'epoch'):
            plan = dict(self.plan, **{field: {'production_admission': True, 'scope': 'x', 'epoch': 2}[field]})
            with self.subTest(plan=field):
                self.refuses(private_plan=plan)

    def test_real_asm_accepts_4_9_and_2_6_but_refuses_other_shapes(self):
        """Synthetic ROM checks the private build-shape guard and table wiring only."""
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not asar:
            self.skipTest('Asar required for the bounded checkpoint source fixture')
        from allocation_contracts import read_symbols
        fixture = self.root / 'assembly'
        (fixture / 'Overworld').mkdir(parents=True)
        shutil.copyfile(ROOT / 'Overworld/checkpoint_state.asm', fixture / 'Overworld/checkpoint_state.asm')
        generated = fixture / 'Data/Generated/lyra_project'
        generated.mkdir(parents=True)
        macro = re.search(r'macro RegionalCheckpoint_GoronControlCache\(\).*?endmacro', self.goron, re.S).group()
        header = '\n'.join(('lorom', '!REGIONAL_CHECKPOINTS_BOUND = 1', '!ENABLE_D3_PRISON_SEQUENCE = 0',
            '!LYRA_CURRENT_MODE = 1', '!LYRA_PROJECT_DATA_PRESENT = 1',
            '!LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED = 1', '!LYRA_PRIVATE_PILOT_INGRESS_ENABLED = 1',
            '!LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND = 1', '!LYRA_PRIVATE_CHECKPOINT_ENABLED = 1',
            'namespace Oracle', 'GameState = $7EF3C5', 'SpawnPoint = $7EF3C8', 'SavedWorld = $7EF3CA',
            'FollowerId = $7EF3CC', 'RegionalCheckpointSchema = $7EF3B4', 'RegionalCheckpointEpoch = $7EF3B5',
            'RegionalCheckpointKey = $7EF3B6', 'RegionalCheckpointResumeIntent = $7EF3B8',
            'Checkpoint_EnterPreparedCache = $348000', ''))

        def assemble(name, registry, constants=None):
            emitted = C.emit_runtime_asm(registry)
            (generated / 'checkpoint_registry_constants.asm').write_text(constants or emitted['constants'])
            (generated / 'checkpoint_registry_tables.asm').write_text(emitted['tables'])
            driver = fixture / (name + '.asm')
            driver.write_text(header + macro + '\norg $34F900\nincsrc "Overworld/checkpoint_state.asm"\n')
            image = bytearray(0x200000)
            for address, raw in ((0x09F540, '22bfff0b'), (0x02A5A2, '22008007'), (0x0CD049, '9c0e019c1007')):
                put(image, address, bytes.fromhex(raw))
            rom = fixture / (name + '.sfc')
            rom.write_bytes(image)
            run = subprocess.run([asar, '--no-title-check', '--fix-checksum=off', '--symbols=wla',
                                  '-I' + str(fixture), str(driver), str(rom)],
                                 capture_output=True, text=True, cwd=fixture, timeout=20)
            return run, rom

        v1_bindings = {k: v for k, v in self.bindings.items() if k not in ('joint_art', 'native_landings')}
        v1 = C.runtime_registry(self.control_source, self.goron, private_plan=dict(
            kind='checkpoint.private_preview_plan.v1', scope='seeded_private_preview', production_admission=False,
            epoch=1, bindings=copy.deepcopy(v1_bindings), entry=self.plan['entries'][0],
            memberships=self.plan['memberships'][:2]), verified_bindings=v1_bindings, expected_cache=a0_cache())
        for name, registry, data in (('native', self.compile(), 344), ('a0', v1, 184)):
            run, rom = assemble(name, registry)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            proof = C.verify_runtime_tables(registry, rom.read_bytes(), read_symbols(rom.with_suffix('.sym')))
            self.assertEqual((proof['first_data'] - C.CODE_BASE, proof['data_bytes']), (895, data))
            fit = C.validate_runtime_capacity(registry, 895)
            self.assertEqual(proof['end'], C.CODE_BASE + fit['aggregate_bytes'])
        constants = C.emit_runtime_asm(self.compile())['constants']
        for count, members in ((3, 8), (2, 9), (4, 6), (1, 4), (5, 10)):
            forged = constants.replace('!CHECKPOINT_REGISTRY_COUNT = 4\n', f'!CHECKPOINT_REGISTRY_COUNT = {count}\n')
            forged = forged.replace('!CHECKPOINT_REGION_MEMBER_COUNT = 9\n',
                                    f'!CHECKPOINT_REGION_MEMBER_COUNT = {members}\n')
            run, _ = assemble(f'forged-{count}-{members}', self.compile(), forged)
            with self.subTest(shape=(count, members)):
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('(2/6) or A0 plus native ferry/Sky (4/9)', run.stdout + run.stderr)


@unittest.skipUnless(os.environ.get('OOS_JOINT_ART_SOURCE_ROM') and os.environ.get('OOS_JOINT_ART_PACKET'),
                     'Set OOS_JOINT_ART_SOURCE_ROM and OOS_JOINT_ART_PACKET for the saved-source reproduction')
class SavedSourceReproductionTests(unittest.TestCase):
    """Read-only: the reviewed caches come from the actual packet-applied Save source."""

    def test_saved_source_and_packet_reproduce_reviewed_caches(self):
        import lyra_project_prepare as Q
        source = Path(os.environ['OOS_JOINT_ART_SOURCE_ROM']).read_bytes()
        packet_binding = Q.bound(os.environ['OOS_JOINT_ART_PACKET'])
        packet = json.loads(Q.read_bound(packet_binding))
        request = dict(transfer_id=packet['transfer_id'],
                       live=dict(generation=packet['generation'], operation_id=packet['operation_id']))
        image = bytearray(A.expanded_rom(source))
        for row in J.prepare(packet_binding, request, source)[0]['writes']:
            lo, hi = row['pc']
            image[lo:hi] = bytes.fromhex(row['payload_hex'])
        image = bytes(image)
        binding = dict(source_rom_sha256=sha(source), transfer_id=packet['transfer_id'],
                       generation=packet['generation'], operation_id=packet['operation_id'],
                       joint_art=packet_binding, ferry_types=packet['ferry']['types'])
        for key, point, attrs, expected in ((3, [768, 352], [0] * 4, FERRY_HEX),
                                            (4, [144, 240], [0x48] * 4, SKY_HEX)):
            spec = C.NATIVE_PREVIEW[key]
            grid = C._native_scope_grid(image, spec['maps'])
            landing = dict(kind=C.NATIVE_LANDING_KIND, scope=spec['scope'], key=key, map_id=spec['parent'],
                           parent_map=spec['parent'], region_key=key, local_pixel=point, clear_radius=1,
                           tile16_id=grid[point[1] // 16][point[0] // 16], tile_attributes=attrs,
                           grid_sha256=grid_sha(grid), binding=binding)
            with self.subTest(key=key):
                self.assertEqual(C.native_preview_cache(image, landing, binding)[0].hex(), expected)
                with self.assertRaisesRegex(ValueError, 'blocked collision quarter'):
                    C.native_preview_cache(image, dict(landing, clear_radius=2), binding)


if __name__ == '__main__':
    unittest.main()
