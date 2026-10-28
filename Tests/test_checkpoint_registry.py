"""Host policy/record proof only; no game, assembler, persistence or allocation proof."""
from pathlib import Path
import sys
import unittest
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import checkpoint_registry as C

SHA = '1' * 64


def record(key=1, domain=C.Domain.SPECIAL, map_id=0xA0, parent=0xA0):
    # Distinct diagnostic payload words, not selected gameplay coordinates.
    cache = bytearray(range(50))
    cache[0:2] = parent.to_bytes(2, 'little')
    cache[12:14] = map_id.to_bytes(2, 'little')
    return C.RegionalCheckpoint(key, domain, map_id, parent, bytes(cache), SHA)


def registry(*rows, epoch=1):
    return C.Registry.compile(rows, epoch=epoch, source_rom_sha256=SHA)


class CheckpointRegistryTests(unittest.TestCase):
    def test_full_records_preserved_sorted_and_bound(self):
        a, b = record(4), record(2, C.Domain.MINISH)
        r = registry(a, b)
        self.assertEqual([x.key for x in r.records], [2, 4])
        self.assertEqual(len(r.packed_records), 2 * C.RECORD_BYTES)
        self.assertEqual(r.packed_records[8:58], b.exit_cache)
        self.assertEqual(r.packed_records[66:116], a.exit_cache)
        self.assertNotEqual(r.content_sha256, registry(a, b, epoch=2).content_sha256)

    def test_all_four_domains_use_identical_resolution(self):
        for domain in C.Domain:
            with self.subTest(domain=domain):
                row = record(domain=domain)
                r = registry(row)
                s = C.activate_checkpoint(1, domain=domain, map_id=0xA0, registry=r)
                self.assertEqual(C.resolve_checkpoint(s, registry=r).checkpoint, row)

    def test_unknown_or_absent_checkpoint_uses_existing_native_Home_adapter(self):
        r = registry()
        for key in (0, 1, 0xFFFF):
            result = C.resolve_checkpoint(C.SavedCheckpoint(1, 1, key), registry=r)
            self.assertEqual(result.route, 'home')
            self.assertEqual(result.override, C.native_spawn_adapter(0))

    def test_dungeon_entrance_precedes_regional_and_story_override(self):
        r = registry(record())
        s = C.SavedCheckpoint(1, 1, 1)
        for override in (None, C.native_spawn_adapter(2), C.ScriptOverride(C.OverrideKind.ABYSS_SCRIPT)):
            self.assertEqual(C.resolve_checkpoint(s, registry=r, dungeon_entrance_continue=True,
                             script_override=override).route, 'dungeon_entrance')
        self.assertEqual(s, C.SavedCheckpoint(1, 1, 1))

    def test_temporary_native_Abyss_and_Goron_overrides_preserve_key(self):
        r, saved = registry(record()), C.SavedCheckpoint(1, 1, 1)
        for override in (C.native_spawn_adapter(2), C.ScriptOverride(C.OverrideKind.ABYSS_SCRIPT),
                         C.native_spawn_adapter(7)):
            before = saved.encode()
            self.assertEqual(C.resolve_checkpoint(saved, registry=r, script_override=override).override, override)
            self.assertEqual(saved.encode(), before)
            self.assertEqual(C.resolve_checkpoint(saved, registry=r).route, 'regional_checkpoint')

    def test_legacy_native_adapter_bounds_every_selector(self):
        for selector in range(7):
            self.assertEqual(C.native_spawn_adapter(selector).native_spawn, selector)
        self.assertEqual(C.native_spawn_adapter(7).kind, C.OverrideKind.GORON_FACTORY)
        for selector in (-1, 8, 0xFF, True):
            with self.assertRaises(ValueError): C.native_spawn_adapter(selector)

    def test_activation_requires_explicit_matching_record_domain_and_map(self):
        r = registry(record())
        for key, domain, map_id in ((0, C.Domain.SPECIAL, 0xA0), (1, C.Domain.MINISH, 0xA0),
                                    (1, C.Domain.SPECIAL, 0xA1), (1, 2, 0xA0)):
            with self.assertRaises(ValueError):
                C.activate_checkpoint(key, domain=domain, map_id=map_id, registry=r)

    def test_old_unknown_epoch_and_retired_keys_migrate_to_none(self):
        r = registry(record())
        for raw in (bytes(4), b'\xff' * 4, bytes((1, 2, 1, 0)), bytes((1, 1, 2, 0))):
            saved, reason = C.restore_saved_checkpoint(raw, r)
            self.assertEqual(saved.key, 0)
            self.assertNotEqual(reason, 'current')
        saved, reason = C.restore_saved_checkpoint(bytes((1, 1, 1, 0)), r)
        self.assertEqual((saved.encode(), reason), (bytes((1, 1, 1, 0)), 'current'))
        with self.assertRaises(ValueError): C.restore_saved_checkpoint(b'\x00', r)

    def test_bad_destinations_refuse_before_any_packed_output(self):
        row = record()
        for bad in (replace(row, exit_cache=row.exit_cache[:-2]), replace(row, parent_map=0xA1),
                    replace(row, map_id=0xA1), replace(row, source_rom_sha256='2' * 64),
                    replace(row, domain=2), replace(row, key=0), replace(row, map_id=0xC0),
                    replace(row, domain=C.Domain.MINISH, map_id=0xC0),
                    replace(row, domain=C.Domain.MINISH, map_id=0xFF)):
            with self.assertRaises(ValueError): registry(bad)
        with self.assertRaises(ValueError): registry(row, row)
        with self.assertRaises(ValueError): registry(row, epoch=0)

    def test_registry_limits_and_record_identity_are_not_silently_coerced(self):
        with self.assertRaises(ValueError):
            registry(*(record(key) for key in range(1, 258)))
        with self.assertRaises(ValueError):
            C.Registry.compile([], epoch=1, source_rom_sha256='not-a-source-hash')
        r = registry(record())
        changed = registry(replace(record(), exit_cache=record().exit_cache[:-1] + b'\xff'))
        self.assertNotEqual(r.content_sha256, changed.content_sha256)

    def test_key_domain_does_not_alias_temporary_native_C8(self):
        # Key7 is legal globally; a regional key never invokes legacy selector7.
        r = registry(record(7))
        result = C.resolve_checkpoint(C.SavedCheckpoint(1, 1, 7), registry=r)
        self.assertEqual(result.route, 'regional_checkpoint')
        self.assertIsNone(result.override)

    def test_raw_unvalidated_override_and_context_refuse(self):
        saved, r = C.SavedCheckpoint(1, 1, 0), registry()
        with self.assertRaises(ValueError): C.resolve_checkpoint(saved, registry=r, script_override=7)
        with self.assertRaises(ValueError): C.resolve_checkpoint(saved, registry=r, dungeon_entrance_continue=1)
        with self.assertRaises(ValueError): C.ScriptOverride(C.OverrideKind.NATIVE_SPAWN, 7)


if __name__ == '__main__': unittest.main()
