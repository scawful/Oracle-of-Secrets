"""Host policy/record proof only; no game, assembler, persistence or allocation proof."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Generate'))
import checkpoint_registry as C

SHA = '1' * 64


def record(key=1, domain=C.Domain.SPECIAL, map_id=0xA0, parent=0xA0):
    # Distinct diagnostic payload words, not selected gameplay coordinates.
    cache = bytearray(range(50))
    cache[0:2] = parent.to_bytes(2, 'little')
    cache[12:14] = map_id.to_bytes(2, 'little')
    return C.RegionalCheckpoint(key, domain, map_id, 1, parent, 0, bytes(cache), SHA)


def resolve(saved, **kwargs):
    return C.resolve_checkpoint(saved, resume_intent=C.ResumeIntent.REGIONAL, **kwargs)


def registry(*rows, epoch=1):
    members = {(r.map_id,r.domain,r.native_affinity,r.region_key) for r in rows}
    return C.Registry.compile(rows, memberships=[C.RegionMembership(*m) for m in members],
                              epoch=epoch, source_rom_sha256=SHA)


class CheckpointRegistryTests(unittest.TestCase):
    def test_full_records_preserved_sorted_and_bound(self):
        a, b = record(4), record(2, C.Domain.MINISH)
        r = registry(a, b)
        self.assertEqual([x.key for x in r.records], [2, 4])
        self.assertEqual(len(r.packed_records), 2 * C.RECORD_BYTES)
        self.assertEqual(r.packed_records[10:60], b.exit_cache)
        self.assertEqual(r.packed_records[70:120], a.exit_cache)
        self.assertNotEqual(r.content_sha256, registry(a, b, epoch=2).content_sha256)

    def test_all_four_domains_use_identical_resolution(self):
        for domain in C.Domain:
            with self.subTest(domain=domain):
                row = record(domain=domain)
                r = registry(row)
                s = C.activate_checkpoint(1, domain=domain, map_id=0xA0, region_key=1, registry=r)
                self.assertEqual(resolve(s, registry=r).checkpoint, row)

    def test_unknown_or_absent_checkpoint_uses_existing_native_Home_adapter(self):
        r = registry()
        for key in (0, 1, 0xFFFF):
            result = resolve(C.SavedCheckpoint(1, 1, key), registry=r)
            self.assertEqual(result.route, 'home')
            self.assertEqual(result.override, C.native_spawn_adapter(0))

    def test_dungeon_entrance_precedes_regional_and_story_override(self):
        r = registry(record())
        s = C.SavedCheckpoint(1, 1, 1)
        for override in (None, C.native_spawn_adapter(2), C.ScriptOverride(C.OverrideKind.ABYSS_SCRIPT)):
            self.assertEqual(resolve(s, registry=r, dungeon_entrance_continue=True,
                             script_override=override).route, 'dungeon_entrance')
        self.assertEqual(s, C.SavedCheckpoint(1, 1, 1))

    def test_temporary_native_Abyss_and_Goron_overrides_preserve_key(self):
        r, saved = registry(record()), C.SavedCheckpoint(1, 1, 1)
        for override in (C.native_spawn_adapter(2), C.ScriptOverride(C.OverrideKind.ABYSS_SCRIPT),
                         C.native_spawn_adapter(7)):
            before = saved.encode()
            self.assertEqual(resolve(saved, registry=r, script_override=override).override, override)
            self.assertEqual(saved.encode(), before)
            self.assertEqual(resolve(saved, registry=r).route, 'regional_checkpoint')

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
                C.activate_checkpoint(key, domain=domain, map_id=map_id, region_key=1, registry=r)

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

    def test_resume_matches_region_not_only_domain_and_never_clears_last_key(self):
        row = record()
        r, saved = registry(row), C.SavedCheckpoint(1, 1, row.key)
        before = saved.encode()
        for domain, region, expected in ((C.Domain.SPECIAL, 1, C.ResumeIntent.REGIONAL),
                (C.Domain.SPECIAL, 2, C.ResumeIntent.HOME),
                (C.Domain.MINISH, 1, C.ResumeIntent.HOME)):
            intent = C.prepare_resume_intent(saved, domain=domain, region_key=region, registry=r)
            self.assertEqual(intent, expected)
            route = C.resolve_checkpoint(saved, registry=r, resume_intent=intent)
            self.assertEqual(route.route, 'regional_checkpoint' if intent else 'home')
            self.assertEqual(saved.encode(), before)
        # Cold routing consumes a separately supplied snapshot, never raw8A.
        self.assertEqual(C.resolve_checkpoint(saved, registry=r,
                         resume_intent=C.ResumeIntent.HOME).route, 'home')
        self.assertEqual(saved.encode(), before)

    def test_activation_region_and_resume_input_are_explicit(self):
        r, saved = registry(record()), C.SavedCheckpoint(1, 1, 1)
        with self.assertRaises(ValueError):
            C.activate_checkpoint(1, domain=C.Domain.SPECIAL, map_id=0xA0, region_key=2, registry=r)
        with self.assertRaises(ValueError):
            C.prepare_resume_intent(saved, domain=C.Domain.SPECIAL, region_key=0, registry=r)
        with self.assertRaises(TypeError): C.resolve_checkpoint(saved, registry=r)
        with self.assertRaises(ValueError): C.resolve_checkpoint(saved, registry=r, resume_intent=1)

    def test_unplaced_runtime_tables_retain_region_and_complete_destination(self):
        row = record(7)
        r = registry(row)
        t = r.runtime_tables()
        self.assertEqual(t['CheckpointRegistry_Keys'], b'\x07\x00')
        self.assertEqual(t['CheckpointRegistry_Regions'], b'\x01\x00')
        self.assertEqual(t['CheckpointRegistry_Domains'], b'\x02\x00')
        self.assertEqual(t['CheckpointRegistry_Maps'], b'\xa0\x00')
        self.assertEqual(t['CheckpointRegistry_Records'][10:], row.exit_cache)

    def test_granted_state_has_exact_symbols_source_provenance_and_nine_baseline(self):
        import json, re, hashlib
        from allocation_contracts import read_ledger, source_evidence, ownership_conflicts
        from asm_source import _load_global_defines
        root = Path(__file__).resolve().parents[1]
        ledger = read_ledger(root/'Config/allocation_ownership.json')
        claim = next(c for c in ledger['claims'] if c['id'] == 'RegionalCheckpointSave')
        self.assertEqual((claim['base'], claim['size'], claim['condition']), (0x7EF3B4, 4, {}))
        selected = {k:v for k,v in ledger['sources'].items() if v['source_set'] == 'regional_checkpoint_runtime_25'}
        source_evidence({'sources': selected, 'claims': [claim]}, {'regional_checkpoint_runtime_25': root})
        source = (root/'Core/sram.asm').read_text()
        for name, value in (('RegionalCheckpointSchema', 0x7EF3B4), ('RegionalCheckpointEpoch', 0x7EF3B5),
                            ('RegionalCheckpointKey', 0x7EF3B6), ('RegionalCheckpointResumeIntent',0x7EF3B8), ('FreeBlock_Large', 0x7EF3B9)):
            self.assertRegex(source, rf'(?m)^{name}\s*= \${value:06X}\b')
        conflicts, _ = ownership_conflicts(ledger, _load_global_defines(root), pending=True)
        canonical = '\n'.join(sorted(json.dumps(c, sort_keys=True, separators=(',', ':')) for c in conflicts))+'\n'
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(),
                         '4da57a07ee0f6c8d8a741da0b30c8e87f64dd3fe8a182805e024ea6cbacc238c')
        asm = (root/'Overworld/checkpoint_state.asm').read_text()
        self.assertEqual(set(re.findall(r'STA\.l (\w+)', asm)),
                         {'RegionalCheckpointKey', 'RegionalCheckpointSchema', 'RegionalCheckpointEpoch',
                          'RegionalCheckpointResumeIntent', 'SavedWorld', 'SpawnPoint'})
        ow = (root/'Overworld/overworld.asm').read_text()
        self.assertLess(ow.index('Checkpoint_OrdinaryOverworldEnd = pc()'), ow.index('org $0794D9'))
        self.assertIn('(Checkpoint_OrdinaryOverworldEnd>>16) == $34', ow)
        self.assertIn('incsrc "Overworld/checkpoint_state.asm"', ow)
        self.assertEqual(_load_global_defines(root)['REGIONAL_CHECKPOINTS_ENABLED'], 0)

    def test_five_byte_migration_keeps_valid_key_when_only_intent_is_bad(self):
        r = registry(record())
        saved, intent, why = C.restore_runtime_state(bytes((1,1,1,0,9)), r)
        self.assertEqual((saved.key, intent, why), (1, C.ResumeIntent.HOME, 'unknown_resume_intent'))
        saved, intent, why = C.restore_runtime_state(bytes(5), r)
        self.assertEqual((saved.key, intent), (0, C.ResumeIntent.HOME))
        with self.assertRaises(ValueError): C.restore_runtime_state(bytes(4), r)

    def test_affinity_is_explicit_and_not_derived_from_logical_domain(self):
        row = replace(record(), domain=C.Domain.MINISH, native_affinity=0)
        r = registry(row)
        self.assertEqual(r.packed_records[2:4], bytes((3,0)))
        self.assertEqual(r.runtime_tables()['CheckpointRegions_Affinities'], bytes(2))
        with self.assertRaises(ValueError): registry(replace(row, native_affinity=0x80))

    def test_explicit_membership_covers_non_anchor_maps_without_extra_checkpoint(self):
        row = record()
        members = [C.RegionMembership(0xA0,C.Domain.SPECIAL,0,1),
                   C.RegionMembership(0xA1,C.Domain.SPECIAL,0,1),
                   C.RegionMembership(0xA2,C.Domain.SPECIAL,0,2)]
        r = C.Registry.compile([row], memberships=members, epoch=1, source_rom_sha256=SHA)
        self.assertEqual((len(r.records),len(r.memberships)),(1,3))
        state = C.SavedCheckpoint(1,1,1)
        self.assertEqual(C.prepare_resume_intent(state,domain=C.Domain.SPECIAL,region_key=members[1].region_key,
                         registry=r),C.ResumeIntent.REGIONAL)
        self.assertEqual(C.prepare_resume_intent(state,domain=C.Domain.SPECIAL,region_key=members[2].region_key,
                         registry=r),C.ResumeIntent.HOME)
        with self.assertRaises(ValueError):
            C.Registry.compile([row], memberships=members[1:], epoch=1, source_rom_sha256=SHA)

    def test_source_control_is_one_shared_native_cache_not_new_coordinates(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'Overworld/goron_checkpoint.asm').read_text()
        r = C.goron_control_registry(b'diagnostic-base-not-admission', source)
        self.assertEqual((r.records[0].domain, r.records[0].map_id, r.records[0].parent_map),
                         (C.Domain.LIGHT, 0x36, 0x36))
        self.assertEqual(len(r.records[0].exit_cache), 50)
        with self.assertRaises(ValueError):
            C.goron_control_registry(b'diagnostic', source.replace('dw $0036, $0016', 'dw $0037, $0016'))

    def test_runtime_capacity_counts_full_records_and_all_lookup_arrays(self):
        r = registry(*(record(key) for key in range(1,6)))
        result = C.validate_runtime_capacity(r, 892)
        self.assertEqual((result['data_bytes'], result['aggregate_bytes']), (348,1240))
        with self.assertRaises(ValueError):
            C.validate_runtime_capacity(registry(*(record(key) for key in range(1,7))),892)

    def test_registry_limits_and_record_identity_are_not_silently_coerced(self):
        with self.assertRaises(ValueError):
            registry(*(record(key) for key in range(1, 258)))
        with self.assertRaises(ValueError):
            C.Registry.compile([], memberships=[], epoch=1, source_rom_sha256='not-a-source-hash')
        r = registry(record())
        changed = registry(replace(record(), exit_cache=record().exit_cache[:-1] + b'\xff'))
        self.assertNotEqual(r.content_sha256, changed.content_sha256)

    def test_key_domain_does_not_alias_temporary_native_C8(self):
        # Key7 is legal globally; a regional key never invokes legacy selector7.
        r = registry(record(7))
        result = resolve(C.SavedCheckpoint(1, 1, 7), registry=r)
        self.assertEqual(result.route, 'regional_checkpoint')
        self.assertIsNone(result.override)

    def test_raw_unvalidated_override_and_context_refuse(self):
        saved, r = C.SavedCheckpoint(1, 1, 0), registry()
        with self.assertRaises(ValueError): resolve(saved, registry=r, script_override=7)
        with self.assertRaises(ValueError): resolve(saved, registry=r, dungeon_entrance_continue=1)
        with self.assertRaises(ValueError): C.ScriptOverride(C.OverrideKind.NATIVE_SPAWN, 7)


class PrivateCheckpointPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = b'diagnostic private plan, not a gameplay ROM'
        self.source_sha = hashlib.sha256(self.source).hexdigest()
        self.goron_source = (Path(__file__).resolve().parents[1]/'Overworld/goron_checkpoint.asm').read_text()
        # Reuse the explicit diagnostic record payload. No gameplay cache or
        # coordinates are selected/qualified by these pure host fixtures.
        self.cache = record(2).exit_cache
        self.receipt = self.root/'save.json'
        self.receipt.write_text('{"generation":7,"operation_id":"fixture-save-seven"}')
        self.cache_source = self.root/'diagnostic-cache-source.bin'
        self.cache_source.write_bytes(self.cache)
        pin = lambda p: dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.bindings = dict(source_rom_sha256=self.source_sha, document_sha256='2'*64,
            transfer_id='3'*64, live=dict(generation=7, operation_id='fixture-save-seven',
            save_receipt=pin(self.receipt)), selected_pair=[0xA0,0xA1], cache_source=pin(self.cache_source))
        self.plan = dict(kind='checkpoint.private_preview_plan.v1', scope='seeded_private_preview',
            production_admission=False, epoch=1, bindings=copy.deepcopy(self.bindings),
            entry=dict(key=2, domain='SPECIAL', native_affinity=0, map_id=0xA0, parent_map=0xA0,
                region_key=2, exit_cache_hex=self.cache.hex(), cache_sha256=hashlib.sha256(self.cache).hexdigest()),
            memberships=[dict(map_id=area, domain='SPECIAL', native_affinity=0, region_key=2)
                         for area in (0xA0,0xA1)])

    def compile(self, **overrides):
        args = dict(private_plan=self.plan, verified_bindings=self.bindings, expected_cache=self.cache)
        args.update(overrides)
        return C.runtime_registry(self.source, self.goron_source, **args)

    def test_default_retains_exact_one_row_control_and_private_seed_resolves_key2(self):
        default = C.runtime_registry(self.source, self.goron_source)
        control = C.goron_control_registry(self.source, self.goron_source)
        self.assertEqual(default, control)
        self.assertEqual(len(default.records), 1)
        preview = self.compile()
        self.assertEqual(preview.records[0], control.records[0])
        self.assertEqual(preview.records[0].pack(self.source_sha), control.packed_records)
        self.assertEqual([r.key for r in preview.records], [1,2])
        self.assertEqual(len(preview.memberships), 6)
        self.assertEqual(preview.records[1].exit_cache, self.cache)
        seeded = C.SavedCheckpoint(C.SCHEMA, preview.epoch, 2)
        route = resolve(seeded, registry=preview)
        self.assertEqual((route.route, route.checkpoint.domain, route.checkpoint.map_id),
                         ('regional_checkpoint',C.Domain.SPECIAL,0xA0))
        self.assertIsNone(route.override)
        self.assertEqual(C.validate_runtime_capacity(preview,0)['data_bytes'],184)

    def test_private_plan_requires_independent_bindings_and_cache(self):
        for changes in (dict(verified_bindings=None), dict(expected_cache=None),
                        dict(private_plan=None), dict(expected_cache=self.cache[:-1])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.compile(**changes)

    def test_source_transfer_document_and_later_save_retire_plan(self):
        for field in ('source_rom_sha256','document_sha256','transfer_id'):
            plan = copy.deepcopy(self.plan)
            plan['bindings'][field] = '9'*64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'bindings differ'):
                self.compile(private_plan=plan)
        for field, value in (('generation',8),('operation_id','later-same-byte-save')):
            fresh = copy.deepcopy(self.bindings)
            fresh['live'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'bindings differ'):
                self.compile(verified_bindings=fresh)
        changed_source = copy.deepcopy(self.bindings)
        changed_source['source_rom_sha256'] = '9'*64
        plan = copy.deepcopy(self.plan)
        plan['bindings'] = changed_source
        with self.assertRaisesRegex(ValueError,'bindings differ'):
            self.compile(private_plan=plan,verified_bindings=changed_source)

    def test_epoch_scope_key_domain_affinity_and_map_are_not_coerced(self):
        for key, value in (('epoch',2),('epoch',True),('scope','ordinary_build'),
                           ('production_admission',True),('production_admission',0)):
            plan = copy.deepcopy(self.plan)
            plan[key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                self.compile(private_plan=plan)
        for key,value in (('key',1),('key',True),('domain','LIGHT'),('domain',2),
                          ('native_affinity',0x40),('native_affinity',False),('map_id',0xA1),
                          ('parent_map',0xA1),('region_key',0),('region_key',True)):
            plan = copy.deepcopy(self.plan)
            plan['entry'][key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                self.compile(private_plan=plan)

    def test_unselected_pair_membership_and_foreign_region_refuse(self):
        for pair in ([0xA0,0xA2],[0xA1,0xA0],[0xA0,0xA0],[0xA0,True]):
            plan = copy.deepcopy(self.plan)
            bindings = copy.deepcopy(self.bindings)
            plan['bindings']['selected_pair'] = bindings['selected_pair'] = pair
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                self.compile(private_plan=plan,verified_bindings=bindings)
        for field,value in (('map_id',0xA2),('domain','LIGHT'),('native_affinity',0x40),('region_key',3)):
            plan = copy.deepcopy(self.plan)
            plan['memberships'][1][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'unselected'):
                self.compile(private_plan=plan)

    def test_cache_hash_foreign_payload_and_malformed_headers_refuse(self):
        for field,value in (('cache_sha256','9'*64),('exit_cache_hex',self.cache[:-1].hex())):
            plan = copy.deepcopy(self.plan)
            plan['entry'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.compile(private_plan=plan)
        foreign = self.cache[:-1]+bytes([self.cache[-1]^1])
        plan = copy.deepcopy(self.plan)
        plan['entry'].update(exit_cache_hex=foreign.hex(),cache_sha256=hashlib.sha256(foreign).hexdigest())
        with self.assertRaisesRegex(ValueError,'independent landing'):
            self.compile(private_plan=plan)
        for offset in (0,12):
            malformed = bytearray(self.cache)
            malformed[offset:offset+2] = b'\x36\x00'
            malformed = bytes(malformed)
            plan = copy.deepcopy(self.plan)
            plan['entry'].update(exit_cache_hex=malformed.hex(),cache_sha256=hashlib.sha256(malformed).hexdigest())
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError,'cache.*disagrees'):
                self.compile(private_plan=plan,expected_cache=malformed)

    def test_live_binding_types_and_exact_artifact_paths_refuse(self):
        for field,value in (('generation',True),('generation',0),('operation_id','bad operation')):
            plan = copy.deepcopy(self.plan)
            bindings = copy.deepcopy(self.bindings)
            plan['bindings']['live'][field] = bindings['live'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.compile(private_plan=plan,verified_bindings=bindings)
        other = self.root/'foreign-cache-source.bin'
        other.write_bytes(self.cache)
        plan = copy.deepcopy(self.plan)
        plan['bindings']['cache_source']['path'] = str(other)
        with self.assertRaisesRegex(ValueError,'bindings differ'):
            self.compile(private_plan=plan)
        self.receipt.write_bytes(self.receipt.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'Current saved input changed'):
            self.compile()

    def test_emission_preserves_every_runtime_byte_and_has_no_placement(self):
        registry = self.compile()
        emitted = C.emit_runtime_asm(registry)
        self.assertIn('!CHECKPOINT_REGISTRY_COUNT = 2\n',emitted['constants'])
        self.assertIn('!CHECKPOINT_REGION_MEMBER_COUNT = 6\n',emitted['constants'])
        self.assertNotIn('org ',emitted['constants'])
        decoded, current = {}, None
        for line in emitted['tables'].splitlines():
            if line.endswith(':'):
                current = line[:-1]
                decoded[current] = b''
            elif line.strip().startswith('db '):
                decoded[current] += bytes(int(n.strip()[1:],16) for n in line.strip()[3:].split(','))
        self.assertEqual(decoded,registry.runtime_tables())
        self.assertEqual(C.emit_runtime_asm(C.runtime_registry(self.source,self.goron_source))['constants'].count(
                         '!CHECKPOINT_REGISTRY_COUNT = 1\n'),1)

    def test_compiled_table_verifier_checks_data_layout_and_complete_cache(self):
        registry = self.compile()
        image, symbols, address = bytearray(0x200000), {}, C.CODE_BASE+0x300
        for name,raw in registry.runtime_tables().items():
            symbols['Oracle_'+name] = address
            pc = ((address>>16)&0x7F)*0x8000+(address&0x7FFF)
            image[pc:pc+len(raw)] = raw
            address += len(raw)
        result = C.verify_runtime_tables(registry,bytes(image),symbols)
        self.assertEqual((result['end'],result['data_bytes']),(address,184))
        for name in registry.runtime_tables():
            bad = bytearray(image)
            address = symbols['Oracle_'+name]
            bad[((address>>16)&0x7F)*0x8000+(address&0x7FFF)] ^= 1
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'disagrees with source'):
                C.verify_runtime_tables(registry,bytes(bad),symbols)
        bad_symbols = dict(symbols)
        bad_symbols['Oracle_CheckpointRegistry_Records'] += 1
        with self.assertRaisesRegex(ValueError,'layout differs'):
            C.verify_runtime_tables(registry,bytes(image),bad_symbols)


if __name__ == '__main__': unittest.main()
