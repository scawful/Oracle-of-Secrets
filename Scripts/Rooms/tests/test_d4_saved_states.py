"""Saved-room derivation and refusal controls; no ROM writes or emulator."""
import json
import types
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'Scripts/Rooms'))
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import d4_water_rooms as producer
import d4_water_collision as collision
import sky_d8_room_writer as rooms


def obj(ident, x, y, size=0):
    if ident < 0x100:
        return bytes([x * 4 + (size >> 2), y * 4 + (size & 3), ident])
    if ident < 0x140:
        return bytes([0xfc | x >> 4, (x & 15) << 4 | y >> 2,
                      (y & 3) << 6 | (ident & 63)])
    return rooms.encode_type3(ident, x, y)


def raw(lists, header=b'\x00\x00', doors=(b'\x00\x00',)):
    return rooms.encode_object_stream(header, lists, doors)[0]


def fixture():
    common = [obj(0x11f, 24, 8), obj(0x124, 13, 9), obj(0x129, 12, 27),
              obj(0xfee, 6, 49), obj(0xfef, 55, 49), obj(0x005, 49, 3)]
    dry = [obj(0x132, 30, 25), obj(0x132, 12, 39)]
    wet = [obj(0x133, 30, 25), obj(0x133, 12, 39),
           obj(0x135, 42, 25), obj(0x135, 16, 39), obj(0x135, 51, 39)]
    return raw([common + dry, [obj(0xdb, 24, 28, 15)], []]), raw([
        common + wet, [obj(0xd9, 24, 28, 15), obj(0xe7, 24, 28, 15)], []])


def edit(blob, change):
    s = producer.parse_stream(blob)
    change(s)
    return raw(s.lists, s.header, s.doors)


def trace(blob):
    # Synthetic per-object writer trace. Actual qualified native trace is a
    # separate preparation check; these fixtures test binding/refusal behavior.
    s = producer.parse_stream(blob)
    cases = []
    for layer, records in enumerate(s.lists):
        for record in records:
            x, y = producer.record_xy(record)
            cases.append(dict(object_index=len(cases), object_layer=layer,
                object_id_dec=producer.object_id(record), object_x=x, object_y=y,
                room_id=0x25, size=0 if record[0] >= 0xfc
                else ((record[0] & 3) << 2) | (record[1] & 3),
                tiles=[dict(x_tile=x, y_tile=y, layer=0)]))
    return dict(case_count=len(cases), cases=cases)


class SavedStateTest(unittest.TestCase):
    def setUp(self):
        self.low, self.high = fixture()

    def test_selected_pair_is_exact(self):
        got = producer.derive_states(self.low, self.low, self.high)
        self.assertEqual((got.low, got.high), (self.low, self.high))

    def test_saved_common_edit_reaches_both_states(self):
        old, new = obj(0x005, 49, 3), obj(0x005, 51, 3)
        saved = edit(self.low, lambda s: s.lists[0].__setitem__(5, new))
        got = producer.derive_states(saved, self.low, self.high)
        for blob in (got.low, got.high):
            records = producer.parse_stream(blob).lists[0]
            self.assertIn(new, records)
            self.assertNotIn(old, records)
        producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_unrelated_added_and_removed_objects_are_preserved(self):
        addition = obj(0x3a, 60, 5)
        def change(s):
            s.lists[0].remove(obj(0x005, 49, 3))
            s.lists[2].append(addition)
        saved = edit(self.low, change)
        got = producer.derive_states(saved, self.low, self.high)
        self.assertIn(addition, producer.parse_stream(got.high).lists[2])
        producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_missing_or_duplicate_dry_contact_refuses(self):
        for duplicate in (False, True):
            def change(s):
                rec = obj(0x132, 30, 25)
                s.lists[0].append(rec) if duplicate else s.lists[0].remove(rec)
            saved = edit(self.low, change)
            with self.assertRaises(producer.StateDerivationError):
                producer.derive_states(saved, self.low, self.high)

    def test_changed_hatch_refuses_instead_of_reusing_old_catch_bounds(self):
        saved = edit(self.low, lambda s: s.lists[0].__setitem__(1, obj(0x124, 14, 9)))
        with self.assertRaisesRegex(producer.StateDerivationError, 'contact 124 changed'):
            producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_changed_floor_layout_or_door_refuses(self):
        for saved in (edit(self.low, lambda s: setattr(s, 'header', b'\x01\x00')),
                      edit(self.low, lambda s: s.doors.append(b'\x10\x00'))):
            with self.assertRaises(producer.StateDerivationError):
                producer.derive_states(saved, self.low, self.high)

    def test_already_high_canonical_input_refuses(self):
        with self.assertRaises(producer.StateDerivationError):
            producer.derive_states(self.high, self.low, self.high)

    def test_high_insertion_order_drift_refuses(self):
        def change(s):
            s.lists[0].insert(0, s.lists[0].pop())
        high = edit(self.high, change)
        with self.assertRaisesRegex(producer.StateDerivationError, 'insertion order'):
            producer.derive_states(self.low, self.low, high)
        saved = edit(self.low, lambda s: s.lists[2].append(obj(0x3a, 60, 5)))
        with self.assertRaisesRegex(producer.StateDerivationError, 'insertion order'):
            producer.derive_states(saved, self.low, high)

    def test_added_state_surface_outside_old_footprint_still_refuses(self):
        for ident in (0xc9, 0xdb, 0x132, 0x124):
            saved = edit(self.low, lambda s: s.lists[0].append(obj(ident, 60, 5)))
            with self.assertRaises(producer.StateDerivationError):
                producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_new_object_painting_into_water_contact_refuses(self):
        saved = edit(self.low, lambda s: s.lists[0].append(obj(0x3a, 24, 28)))
        with self.assertRaisesRegex(producer.StateDerivationError, 'overlaps'):
            producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_blank_catch_manual_apron_and_low_landing_are_still_owned(self):
        for x, y in ((10, 14), (14, 34), (31, 22)):
            saved = edit(self.low, lambda s: s.lists[0].append(obj(0x3a, x, y)))
            with self.assertRaisesRegex(producer.StateDerivationError, 'overlaps'):
                producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_incomplete_wrong_identity_and_untraced_objects_refuse(self):
        for corrupt in ('missing', 'identity', 'empty', 'size', 'room'):
            t = trace(self.low)
            if corrupt == 'missing':
                t['cases'].pop()
            elif corrupt == 'identity':
                t['cases'][0]['object_x'] += 1
            elif corrupt == 'empty':
                t['cases'][0]['tiles'] = []
            elif corrupt == 'size':
                t['cases'][0]['size'] += 1
            else:
                t['cases'][0]['room_id'] += 1
            with self.assertRaises(producer.StateDerivationError):
                producer.prepare_saved_room25(self.low, self.low, self.high, t)

    def test_duplicate_actor_contact_record_cannot_hide_as_decoration(self):
        saved = edit(self.low, lambda s: s.lists[0].append(obj(0x11f, 24, 8)))
        with self.assertRaises(producer.StateDerivationError):
            producer.prepare_saved_room25(saved, self.low, self.high, trace(saved))

    def test_malformed_stream_refuses(self):
        for data in (self.low[:-1], self.low + b'\x00'):
            with self.assertRaises((producer.StateDerivationError, rooms.PlanError)):
                producer.parse_stream(data)

    def test_native_hops_follow_all_auto_stairs(self):
        got = producer.derive_states(self.low, self.low, self.high)
        ids = [producer.object_id(r) for r in producer.parse_stream(got.high).lists[0]]
        self.assertLess(max(i for i, v in enumerate(ids) if v == 0x133),
                        min(i for i, v in enumerate(ids) if v == 0x135))

    def test_type3_sizes_bind_actual_native_trace_values(self):
        t = trace(self.low)
        for case in t['cases']:
            if case['object_id_dec'] == 0xfee:
                case['size'] = 11  # actual qualified native FEE trace
            if case['object_id_dec'] == 0xfef:
                case['size'] = 15  # actual qualified native FEF trace
        producer.prepare_saved_room25(self.low, self.low, self.high, t)


class SelectedNativeKitTest(unittest.TestCase):
    def setUp(self):
        fixtures = Path(__file__).parent / 'fixtures/d4'
        self.low = (fixtures/'25-low.bin').read_bytes()
        self.high = (fixtures/'25-high.bin').read_bytes()

    def test_final_four_contact_transform_not_old_five_contact_high(self):
        producer.validate_selected_pair(self.low, self.high)
        got = producer.derive_states(self.low, self.low, self.high)
        self.assertEqual(got.high, self.high)
        self.assertEqual(producer.sha(got.high),
                         'c94564667a77edbafa1f48c99451406258bee185b469603e93780b7a36f713d1')
        self.assertEqual(len(producer.surface_cells(got.high, {0xc9})), 1328)

    def test_old_or_changed_profile_is_not_silently_used(self):
        changed = edit(self.high, lambda s: s.lists[1].pop())
        with self.assertRaisesRegex(producer.StateDerivationError, 'unqualified'):
            producer.validate_selected_pair(self.low, changed)

    def test_qualified_recovery_roles_and_bad_pose(self):
        runtime = types.SimpleNamespace(read_hub_roles_strict=lambda base: ([], []),
            write_hub_contacts=lambda *args: None,
            hub_contact_words=lambda *args: [2672,1125,2672,1264,2664,1096,
                                             2664,1136,2608,2713,1128,1145])
        self.assertEqual(len(producer.validated_hub_words(runtime, b'fixture')), 12)
        runtime.hub_contact_words = lambda *args: [0]*12
        with self.assertRaisesRegex(producer.StateDerivationError, 'saved actors/hatch'):
            producer.validated_hub_words(runtime, b'fixture')


class CommonProducerTest(unittest.TestCase):
    """Exercise the real producer transaction using injected external APIs.

    These are generated-stream/ASM fixtures, not ROM/Build/native tests.
    Maintained source/role/paint APIs retain their own independent gates.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'saved-input.fixture'
        self.source.write_bytes(b'synthetic external API fixture, not a game ROM')
        self.out = self.root/'generated'
        self.out.mkdir()
        (self.out/'water_gate_runtime_tables.asm').write_text('old complete include')
        f = Path(__file__).parent/'fixtures/d4'
        self.low, self.high = (f/'25-low.bin').read_bytes(), (f/'25-high.bin').read_bytes()
        data = self.root/'Data/Rooms/d4_water'
        data.mkdir(parents=True)
        (data/'25-low.bin').write_bytes(self.low)
        (data/'25-high.bin').write_bytes(self.high)
        self.flags = types.SimpleNamespace(_load_global_defines=lambda root:
                                          {'ENABLE_D4_WATER_CONTROLS': 1})
        def write_asm(path, *args):
            path.write_text('new generated runtime include\n')
        def write_contacts(path, words):
            with path.open('a') as output:
                output.write('typed ABI1 bound\n' if words else 'typed ABI1 unbound\n')
        self.runtime = types.SimpleNamespace(generate_tables=lambda *args, **kwargs: ({}, {}),
            write_asm=write_asm, write_hub_contacts=write_contacts)

    def generate(self, *, before_trace=None):
        def paint(command, **kwargs):
            path = next(x.split('=',1)[1] for x in command if x.startswith('--trace-out='))
            if before_trace:
                before_trace()
            Path(path).write_text(json.dumps(trace(self.low)))
        with patch.dict(sys.modules, {'asm_source': self.flags,
                'generate_water_gate_runtime_tables': self.runtime}), \
             patch.object(producer, 'validate_native_sources'), \
             patch.object(producer, 'saved_room25_input', return_value=self.low), \
             patch.object(producer, 'validate_legacy_collision'), \
             patch.object(producer, 'validated_hub_words', return_value=[1]*12), \
             patch.object(producer.subprocess, 'run', side_effect=paint):
            return producer.generate_saved(self.root, self.source, self.out, sys.executable)

    def test_common_producer_publishes_states_and_typed_include_together(self):
        result = self.generate()
        self.assertEqual(result['files'], 5)
        self.assertEqual((self.out/'d4_water/25-low.bin').read_bytes(), self.low)
        self.assertEqual((self.out/'d4_water/25-high.bin').read_bytes(), self.high)
        self.assertEqual((self.out/'d4_water/25-low-collision.bin').read_bytes(), b'\xff\xff')
        self.assertEqual((self.out/'d4_water/25-high-collision.bin').read_bytes(), b'\xff\xff')
        self.assertIn('ABI1 bound', (self.out/'water_gate_runtime_tables.asm').read_text())

    def test_concurrent_save_refuses_before_any_publication(self):
        with self.assertRaisesRegex(producer.StateDerivationError, 'changed while deriving'):
            self.generate(before_trace=lambda: self.source.write_bytes(b'new concurrent saved bytes'))
        self.assertEqual((self.out/'water_gate_runtime_tables.asm').read_text(), 'old complete include')
        self.assertFalse((self.out/'d4_water').exists())

    def test_bad_selected_surface_refuses_without_replacing_previous_include(self):
        (self.root/'Data/Rooms/d4_water/25-high.bin').write_bytes(b'old or incomplete profile')
        with self.assertRaisesRegex(producer.StateDerivationError, 'unqualified'):
            self.generate()
        self.assertEqual((self.out/'water_gate_runtime_tables.asm').read_text(), 'old complete include')
        self.assertFalse((self.out/'d4_water').exists())

    def test_runtime_include_failure_rolls_back_all_four_state_files(self):
        import sheet_overrides
        names = ['d4_water/'+name for name in ('25-low.bin', '25-high.bin',
                  '25-low-collision.bin', '25-high-collision.bin')]
        for name in names:
            path = self.out/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        paths = [self.out/n for n in names] + [self.out/'water_gate_runtime_tables.asm']
        before = {path: path.read_bytes() for path in paths}
        real = sheet_overrides.os.replace
        calls = 0
        def fail_once(a, b):
            nonlocal calls
            calls += 1
            if calls == 5:
                raise OSError('injected runtime include replacement failure')
            return real(a, b)
        with patch.object(sheet_overrides.os, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.generate()
        self.assertEqual({path: path.read_bytes() for path in paths}, before)


class NativeSourceFenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.controller = self.root/'Dungeons/d4_water_control.asm'
        self.controller.parent.mkdir(parents=True)
        self.good = (ROOT/'Dungeons/d4_water_control.asm').read_text()

    def test_empty_profile_admission_and_generated_consumers_required_together(self):
        # Use the actual controller: removing only the first admission leaves
        # the identical .next needle present, reproducing the reviewed defect.
        needle = 'LDA.b [$08],Y : CMP.w #$FFFF : BEQ .done'
        self.assertGreaterEqual(self.good.count(needle), 2)
        unsafe = self.good.replace(needle, 'LDA.b [$08],Y', 1)
        self.assertIn(needle, unsafe)
        for source in (unsafe,
                       self.good.replace('Dungeons/generated/d4_water/25-low.bin',
                                         'Data/Rooms/d4_water/25-low.bin')):
            self.controller.write_text(source)
            with patch.object(producer, 'NATIVE_ATTRIBUTE_SOURCES', {}):
                with self.assertRaises(producer.StateDerivationError):
                    producer.validate_native_sources(self.root)
        self.controller.write_text(self.good)
        with patch.object(producer, 'NATIVE_ATTRIBUTE_SOURCES', {}):
            producer.validate_native_sources(self.root)

    def test_changed_attribute_or_legacy_suppression_source_refuses(self):
        self.controller.write_text(self.good)
        source = self.root/'Dungeons/Collision/source.fixture'
        source.parent.mkdir()
        source.write_bytes(b'selected source')
        with patch.object(producer, 'NATIVE_ATTRIBUTE_SOURCES',
                          {'Dungeons/Collision/source.fixture': producer.sha(source.read_bytes())}):
            producer.validate_native_sources(self.root)
            source.write_bytes(b'changed source')
            with self.assertRaisesRegex(producer.StateDerivationError, 'source contract changed'):
                producer.validate_native_sources(self.root)


class CollisionCodecTest(unittest.TestCase):
    def test_empty_profile_requires_explicit_new_loader_admission(self):
        with self.assertRaises(ValueError):
            collision.decode_runs(b'\xff\xff')
        self.assertEqual(collision.decode_runs(b'\xff\xff', allow_empty=True), {})
    def test_roundtrip_two_planes_and_sentinel_first(self):
        cells = {0: 2, 4096: 8, 4097: 8, 8191: 1}
        encoded, _ = collision.encode(cells, 4096)
        self.assertEqual(collision.decode_runs(encoded), cells)

    def test_wrong_codec_empty_truncated_overlapping_and_oob_refuse(self):
        for raw in (b'\xff\xff', b'\x00\x00\x01',
                    bytes.fromhex('0000010000000108ffff'),
                    bytes.fromhex('ff1f0208ffff'),
                    bytes.fromhex('00000008ffff'),
                    bytes.fromhex('00000100ffff00')):
            with self.assertRaises(ValueError):
                collision.decode_runs(raw)


class NativeNorthBudgetTest(unittest.TestCase):
    def test_fifth_entry_across_lists_refuses_before_BgToggle_alias(self):
        five = raw([[obj(0x133, 1, 1), obj(0x133, 2, 1)],
                    [obj(0x135, 3, 1)], [obj(0x135, 4, 1), obj(0x135, 5, 1)]])
        with self.assertRaisesRegex(producer.StateDerivationError, 'four-word'):
            producer.validate_north_water_budget(five)

    def test_four_entries_and_interroom139_use_separate_storage(self):
        four = raw([[obj(0x133, 1, 1), obj(0x133, 2, 1), obj(0x139, 46, 4)],
                    [], [obj(0x135, 3, 1), obj(0x135, 4, 1)]])
        producer.validate_north_water_budget(four)

    def test_late133_after_135_refuses_even_across_lists(self):
        invalid = raw([[obj(0x135, 1, 1)], [], [obj(0x133, 2, 1)]])
        with self.assertRaisesRegex(producer.StateDerivationError, 'across all'):
            producer.validate_north_water_budget(invalid)


if __name__ == '__main__':
    unittest.main()
