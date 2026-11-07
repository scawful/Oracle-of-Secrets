"""One-time actor lowering controls; no ROM allocation or runtime claim."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lyra_native_loaders as N
import native_overworld_authoring_metadata as M


def fixture():
    authored = {m: dict(sprites=[], doors=[], exits=[]) for m in range(160, 192)}
    geometry = {m: dict(parent=m, area_size=0) for m in authored}
    for parent, size, members in ((0xA0, 2, [0xA0, 0xA1]),
                                  (0xA6, 1, [0xA6, 0xA7, 0xAE, 0xAF]),
                                  (0xB0, 1, [0xB0, 0xB1, 0xB8, 0xB9]),
                                  (0xB3, 1, [0xB3, 0xB4, 0xBB, 0xBC]),
                                  (0xBE, 2, [0xBE, 0xBF])):
        for m in members:
            geometry[m] = dict(parent=parent, area_size=size)
    for m, identity, x, y in ((0xB0, 0x5001, 23, 14), (0xB0, 0x5002, 15, 21),
                               (0xB1, 0x5005, 8, 12), (0xB8, 0x5003, 13, 11),
                               (0xB9, 0x5004, 5, 13)):
        authored[m]['sprites'].append(dict(id=identity, sprite_id=0x52, x=x, y=y, state=1))
    authored[0xB0]['doors'] = [dict(id=0x6001, x=21, y=9, entrance_id=0x0B)]
    authored[0xB0]['exits'] = [dict(id=0x6002, x=22, y=11, room_id=0x83, exit_row=None)]
    return authored, geometry


class NativeActorImportTest(unittest.TestCase):
    def test_canonical_ids_grouping_and_pending_endpoints_match_both_consumers(self):
        authored, geometry = fixture()
        before = copy.deepcopy((authored, geometry))
        streams, metadata = N.lower_authored_actor_lists(authored, geometry)
        self.assertEqual(len(streams), 96)
        self.assertEqual(streams[(0xB0, 1)], bytes([
            14, 23, 0x52, 21, 15, 0x52, 12, 40, 0x52,
            43, 13, 0x52, 45, 37, 0x52, 255]))
        self.assertTrue(all(raw == b'\xFF' for key, raw in streams.items()
                            if key != (0xB0, 1)))
        self.assertEqual(hashlib.sha256(metadata).hexdigest(),
                         'f4a8e2cd3c1fede254883fc646b0faa6d9c93389cb85b71c74e8fe58a7597781')
        value = M.decode(metadata, 192)
        self.assertEqual([p['id'] for p in value['placements']],
                         [0x5001, 0x5002, 0x5005, 0x5003, 0x5004, 0x6001, 0x6002])
        self.assertEqual(value['placements'][6]['target'], 0x83)
        self.assertIsNone(value['placements'][6]['row'])
        self.assertEqual((authored, geometry), before)

    def test_source_traversal_order_is_not_sorted_by_placement_id(self):
        authored, geometry = fixture()
        authored = dict(reversed(list(authored.items())))
        streams, metadata = N.lower_authored_actor_lists(authored, geometry)
        rows = M.decode(metadata, 192)['placements'][:5]
        self.assertEqual([p['id'] for p in rows], [0x5004, 0x5003, 0x5005, 0x5001, 0x5002])
        self.assertEqual(streams[(0xB0, 1)][:3], bytes([45, 37, 0x52]))

    def test_explicit_reassignment_and_wide_tall_coordinates(self):
        authored, geometry = fixture()
        for m in geometry:
            geometry[m] = dict(parent=m, area_size=0)
        streams, metadata = N.lower_authored_actor_lists(authored, geometry)
        self.assertEqual(streams[(0xB1, 1)], bytes([12, 8, 0x52, 255]))
        self.assertEqual(M.decode(metadata, 192)['placements'][2]['owner_map'], 0xB1)
        for m in (0xA0, 0xA1):
            geometry[m] = dict(parent=0xA0, area_size=2)
        for m in (0xA2, 0xAA):
            geometry[m] = dict(parent=0xA2, area_size=3)
        for m, identity in ((0xA1, 1), (0xAA, 2)):
            authored[m]['sprites'] = [dict(id=identity, sprite_id=0, x=31, y=31, state=2)]
        streams, _ = N.lower_authored_actor_lists(authored, geometry)
        self.assertEqual(streams[(0xA0, 2)], bytes([31, 63, 0, 255]))
        self.assertEqual(streams[(0xA2, 2)], bytes([63, 31, 0, 255]))

    def test_optional_targets_and_explicit_return_zero_are_preserved(self):
        authored, geometry = fixture()
        for target in (None, 0):
            authored[0xB0]['doors'][0]['entrance_id'] = target
            authored[0xB0]['exits'][0]['exit_row'] = 0
            _, metadata = N.lower_authored_actor_lists(authored, geometry)
            rows = M.decode(metadata, 192)['placements']
            self.assertEqual(rows[5]['target'], target)
            self.assertIsNone(rows[5]['row'])
            self.assertEqual(rows[6]['row'], 0)

    def test_missing_assignments_bad_fields_and_cross_kind_duplicate_ids_refuse(self):
        changes = [lambda a, g: a.pop(0xA0), lambda a, g: g.pop(0xA0),
                   lambda a, g: g[0xB1].update(parent=0xB1),
                   lambda a, g: a[0xA0].update(sprites=None),
                   lambda a, g: a[0xB0]['sprites'][0].update(x=32),
                   lambda a, g: a[0xB0]['sprites'][0].update(state=True),
                   lambda a, g: a[0xB0]['sprites'][0].update(id=0),
                   lambda a, g: a[0xB0]['sprites'][0].update(subtype=1),
                   lambda a, g: a[0xB0]['doors'][0].update(id=0x5001),
                   lambda a, g: a[0xB0]['exits'][0].update(exit_row=0x83)]
        for change in changes:
            authored, geometry = fixture()
            change(authored, geometry)
            before = copy.deepcopy((authored, geometry))
            with self.assertRaises(ValueError):
                N.lower_authored_actor_lists(authored, geometry)
            self.assertEqual((authored, geometry), before)

    def test_row_metadata_capacity_and_next_identity_exhaustion(self):
        authored, geometry = fixture()
        for value in authored.values():
            value.update(sprites=[], doors=[], exits=[])
        authored[0xA0]['sprites'] = [dict(id=i + 1, x=0, y=0, state=0, sprite_id=0)
                                     for i in range(128)]
        self.assertEqual(len(N.lower_authored_actor_lists(authored, geometry)[0][(0xA0, 0)]), 385)
        authored[0xA0]['sprites'].append(dict(id=129, x=0, y=0, state=0, sprite_id=0))
        with self.assertRaises(ValueError):
            N.lower_authored_actor_lists(authored, geometry)
        authored[0xA0]['sprites'] = []
        authored[0xA0]['doors'] = [dict(id=i + 1, x=0, y=0, entrance_id=None) for i in range(255)]
        self.assertEqual(len(M.decode(N.lower_authored_actor_lists(authored, geometry)[1], 192)
                             ['placements']), 255)
        authored[0xA0]['doors'].append(dict(id=256, x=0, y=0, entrance_id=None))
        with self.assertRaises(ValueError):
            N.lower_authored_actor_lists(authored, geometry)
        authored[0xA0]['doors'] = [dict(id=0xFFFFFFFF, x=0, y=0, entrance_id=None)]
        with self.assertRaises(ValueError):
            N.lower_authored_actor_lists(authored, geometry)


if __name__ == '__main__':
    unittest.main()
