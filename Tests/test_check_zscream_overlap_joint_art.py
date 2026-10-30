"""Overlap admission of the selected joint-art packet's guarded writes."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'Tests'), str(ROOT/'Scripts/Build')]
import check_zscream_overlap as O
import lyra_current_transfer as current
import lyra_joint_art as J
import lyra_project_prepare as Q
import test_lyra_joint_art as fixture

RUNTIME = 'runtime_data.asm'
ALL_ROM = [dict(start=0, end=0x3FFFFF, name='reserved')]


class JointArtOwnership(unittest.TestCase):
    setUp_packet = fixture.JointArtBuild.setUp
    row = fixture.JointArtBuild.row
    prepare_packet = fixture.JointArtBuild.prepare

    def setUp(self):
        self.setUp_packet()
        self.folder = self.folder.resolve()
        self.plan = self.prepare_packet()[0]
        self.base = self.folder/'saved.sfc'; self.base.write_bytes(self.source)
        self.request_path = self.folder/'request.json'
        self.request_path.write_text(json.dumps(self.request))
        self.origin = [0x300000, 0x304000]
        self.prepared = dict(joint_art=copy.deepcopy(self.plan), base_rom=str(self.base),
            saved_rom_sha256=J.R.sha(self.source), request=str(self.request_path),
            inputs=[Q.bound(self.request_path)],
            current_source_profile=dict(origins=dict(code=dict(pc=list(self.origin)))))
        compiled = bytearray(J.A.expanded_rom(self.source))
        for row in self.plan['writes']:
            a, b = row['pc']; compiled[a:b] = bytes.fromhex(row['payload_hex'])
        self.compiled = bytes(compiled)
        self.actual = dict(joint_art=dict(art_writes_verified=len(self.plan['writes'])))

    def spans(self, prepared=None, compiled=None, actual=None, occupied=()):
        return O.joint_art_spans(self.prepared if prepared is None else prepared,
                                 self.compiled if compiled is None else compiled,
                                 self.actual if actual is None else actual, list(occupied))

    def symbols(self, emissions):
        sources = sorted({source for source, _ in emissions})
        lines = ['[labels]', '[source files]']
        lines += [f'{i:04x} 01234567 {source}' for i, source in enumerate(sources)]
        lines.append('[addr-to-line mapping]')
        for number, (source, pc) in enumerate(emissions, 1):
            snes = J.A.snes(pc)
            lines.append(f'{snes >> 16:02X}:{snes & 0xFFFF:04X} {sources.index(source):04x}:{number:08x}')
        path = self.folder/'fixture.sym'; path.write_text('\n'.join(lines)+'\n')
        return path

    def unowned_pc(self):
        spans = [row['pc'] for row in self.plan['writes']]
        return next(pc for pc in range(0x1E8000, 0x400000, 8)
                    if not any(a <= pc < b for a, b in spans))

    def test_exact_selected_writes_are_admitted_only_for_runtime_data(self):
        spans = self.spans()
        self.assertEqual(spans, [row['pc'] for row in self.plan['writes']])
        self.assertEqual(len(spans), 272)
        owned = tuple((RUNTIME, a, b-1) for a, b in spans)
        joint = [(RUNTIME, a) for a, _ in spans] + [(RUNTIME, b-1) for _, b in spans]
        self.assertEqual(O.check_overlaps(self.symbols(joint), ALL_ROM, verified_regions=owned), [])
        # Without the joint-art admission the same emissions are build07's refusals.
        self.assertEqual(len(O.check_overlaps(self.symbols(joint), ALL_ROM)), len(joint))
        # Ordinary source at an admitted address, and generated data outside it, stay refused.
        controls = [('Overworld/ordinary.asm', spans[0][0]), (RUNTIME, self.unowned_pc())]
        hits = O.check_overlaps(self.symbols(controls), ALL_ROM, verified_regions=owned)
        self.assertEqual([hit['source'].rsplit(':', 1)[0] for hit in hits],
                         ['Overworld/ordinary.asm', RUNTIME])

    def test_changed_or_unselected_plan_refuses(self):
        cases = (
            ('payload', lambda p: p['writes'][0].update(payload_hex='ff'*8)),
            ('shifted', lambda p: p['writes'][0].update(pc=[p['writes'][0]['pc'][0]+8,
                                                            p['writes'][0]['pc'][1]+8])),
            ('extra', lambda p: p['writes'].append(dict(pc=[0x310000, 0x310008],
                                                        payload_hex='00'*8, preimage_hex='00'*8))),
            ('dropped', lambda p: p['writes'].pop()),
            ('preimage', lambda p: p['writes'][-1].update(preimage_hex='ff'*(len(p['writes'][-1]['preimage_hex'])//2))),
            ('inputs', lambda p: p['inputs'].pop()),
            ('scope', lambda p: p.update(unselected_maps=[])))
        for name, change in cases:
            prepared = copy.deepcopy(self.prepared); change(prepared['joint_art'])
            compiled = bytearray(self.compiled)
            for row in prepared['joint_art']['writes']:
                a, b = row['pc']
                if b <= len(compiled): compiled[a:b] = bytes.fromhex(row['payload_hex'])
            actual = dict(joint_art=dict(art_writes_verified=len(prepared['joint_art']['writes'])))
            with self.subTest(name), self.assertRaisesRegex(ValueError, 'JOINT_ART_OWNERSHIP_PLAN_DIFFERS'):
                self.spans(prepared, bytes(compiled), actual)

    def test_unbound_packet_request_or_source_refuses(self):
        Path(self.plan['binding']['path']).write_text(json.dumps(dict(self.packet, generation=4)))
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.spans()
        Path(self.plan['binding']['path']).write_text(json.dumps(self.packet))
        self.assertEqual(len(self.spans()), 272)
        for change, message in (
                (lambda p: p.update(inputs=[]), 'REQUEST_UNBOUND'),
                (lambda p: p.update(request=str(self.folder/'other.json')), 'REQUEST_UNBOUND'),
                (lambda p: p.update(saved_rom_sha256='0'*64), 'SOURCE_MISMATCH'),
                (lambda p: p['joint_art'].update(source_rom_sha256='0'*64), 'SOURCE_MISMATCH'),
                (lambda p: p.update(joint_art=[]), 'SOURCE_MISMATCH'),
                (lambda p: p['joint_art'].update(binding=dict(p['joint_art']['binding'], sha256='0'*64)),
                 'input changed')):
            prepared = copy.deepcopy(self.prepared); change(prepared)
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                self.spans(prepared)
        stale = dict(self.request, live=dict(self.request['live'], generation=4))
        self.request_path.write_text(json.dumps(stale))
        prepared = dict(self.prepared, inputs=[Q.bound(self.request_path)])
        with self.assertRaisesRegex(ValueError, 'JOINT_ART_SAVED_GENERATION_STALE'):
            self.spans(prepared)
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.spans()

    def test_candidate_bytes_and_actual_verification_are_required(self):
        for row in (self.plan['writes'][0], self.plan['writes'][-1]):
            compiled = bytearray(self.compiled); compiled[row['pc'][1]-1] ^= 1
            with self.subTest(pc=row['pc']), self.assertRaisesRegex(ValueError, 'PREIMAGE_OR_PAYLOAD_DIFFERS'):
                self.spans(compiled=bytes(compiled))
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_SIZE'):
            self.spans(compiled=self.compiled[:0x200000])
        for actual in ({}, dict(joint_art=None), dict(joint_art=dict(art_writes_verified=271))):
            with self.subTest(actual=actual), self.assertRaisesRegex(ValueError, 'OWNERSHIP_UNVERIFIED'):
                self.spans(actual=actual)
        changed = bytearray(self.source); at = self.plan['writes'][0]['pc'][0]; changed[at] ^= 1
        self.base.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'SOURCE_MISMATCH'):
            self.spans()

    def test_joint_writes_must_stay_disjoint_from_other_admitted_spans_and_origins(self):
        a, b = self.plan['writes'][0]['pc']
        with self.assertRaisesRegex(ValueError, 'JOINT_ART_WRITE_OVERLAP'):
            self.spans(occupied=[[a, b]])
        prepared = copy.deepcopy(self.prepared)
        prepared['current_source_profile']['origins']['graphics'] = dict(pc=[b-1, b+16])
        with self.assertRaisesRegex(ValueError, 'JOINT_ART_WRITE_OVERLAP'):
            self.spans(prepared)
        self.assertEqual(len(self.spans(occupied=[[0x310000, 0x310010]])), 272)

    def test_current_build_admission_adds_joint_spans_after_actual_verification(self):
        rom = self.folder/'candidate.sfc'; rom.write_bytes(self.compiled)
        symbols = self.folder/'candidate.sym'; symbols.write_text('[labels]\n')
        terrain = [0x310000, 0x310010]

        def regions(prepared, actual):
            raw = json.dumps(prepared).encode()
            folder = self.folder/'generated'; folder.mkdir(exist_ok=True)
            (folder/'prepare.json').write_bytes(raw)
            proof = dict(actual, prepared_sha256=J.R.sha(raw))
            receipt = self.folder/'proof.json'; receipt.write_text(json.dumps(proof))
            with mock.patch.object(current, 'verify_current_context', return_value={'prepare.json': raw}), \
                 mock.patch.object(current, 'verify_current_output', return_value=dict(actual)) as verify:
                result = O.lyra_owned_regions(receipt, rom, symbols, folder)
            verify.assert_called_once()
            return result, O.normalize_source_path(str((folder/RUNTIME).resolve()))

        prepared = dict(self.prepared, kind='lyra.current_build_prepare.v1',
                        terrain_plan=dict(target=dict(path=str(rom.resolve())), writes=[dict(pc=terrain)]),
                        tables=dict(tables=[]), bg128_plan=None)
        result, source = regions(prepared, self.actual)
        self.assertEqual(result, ((source, terrain[0], terrain[1]-1),
                                  *((source, a, b-1) for a, b in (r['pc'] for r in self.plan['writes']))))
        without = dict(prepared); without.pop('joint_art')
        self.assertEqual(regions(without, {})[0], ((source, terrain[0], terrain[1]-1),))
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_UNVERIFIED'):
            regions(prepared, {})
        overlapping = dict(prepared, terrain_plan=dict(prepared['terrain_plan'],
                                                       writes=[dict(pc=self.plan['writes'][0]['pc'])]))
        with self.assertRaisesRegex(ValueError, 'JOINT_ART_WRITE_OVERLAP'):
            regions(overlapping, self.actual)


FROZEN = os.environ.get('OOS_JOINT_ART_FROZEN_BUILD')
REQUEST = os.environ.get('OOS_JOINT_ART_REQUEST')


@unittest.skipUnless(FROZEN and REQUEST, 'Set OOS_JOINT_ART_FROZEN_BUILD and OOS_JOINT_ART_REQUEST '
                     'for the frozen build07 candidate reproduction')
class FrozenBuildJointArt(unittest.TestCase):
    """Actual build07 candidate: the refused emissions are exactly the packet's writes."""

    def setUp(self):
        build = Path(FROZEN)
        self.request_path = Path(REQUEST).resolve()
        request = current._json(Q.read_bound(Q.bound(self.request_path)))
        source = Q.read_bound(request['inputs']['rom'])
        policy = json.loads((build/'POLICY.json').read_bytes())
        self.compiled = (build/'ASSEMBLED_07/oos168x.sfc').read_bytes()
        self.symbols = build/'ASSEMBLED_07/oos168x.sym'
        self.proof = json.loads((build/'ASSEMBLED_07/oos168x.lyra-verification.json').read_bytes())
        self.assertEqual(J.R.sha(self.compiled), self.proof['compiled_rom_sha256'])
        self.assertEqual(J.R.sha(self.symbols.read_bytes()), self.proof['symbols_sha256'])
        self.prepared = dict(joint_art=J.prepare(policy['current_runtime']['joint_art'], request, source)[0],
            base_rom=request['inputs']['rom']['path'], saved_rom_sha256=J.R.sha(source),
            request=str(self.request_path), inputs=[Q.bound(self.request_path)],
            current_source_profile=json.loads((build/'SOURCE_PROFILE.json').read_bytes()))
        self.log = (build/'BUILD_07.log').read_text()

    def test_frozen_refusals_are_exactly_the_verified_joint_art_writes(self):
        spans = O.joint_art_spans(self.prepared, self.compiled, self.proof, [])
        self.assertEqual(len(spans), self.proof['joint_art']['art_writes_verified'])
        source = 'Data/Generated/lyra_project/runtime_data.asm'
        zs = O.parse_zs_map(ROOT/'Core/ZS ROM MAP.txt')
        before = O.check_overlaps(self.symbols, zs)
        after = O.check_overlaps(self.symbols, zs, verified_regions=tuple((source, a, b-1) for a, b in spans))
        key = lambda hit: (hit['pc'], hit['source'])
        admitted = set(map(key, before)) - set(map(key, after))
        self.assertEqual(len(admitted), int(re.search(r'\[!\] (\d+) unowned emission', self.log)[1]))
        listed = re.findall(r'^  (0x[0-9A-F]{6}) \(SNES 0x[0-9A-F]{6}\) \S+ \S+ \[([^\]]+)\]', self.log, re.M)
        self.assertEqual(len(listed), 30)
        self.assertLessEqual(set(listed), admitted)
        self.assertTrue(all(s.startswith(source+':') for _, s in admitted))
        # What remains are the later terrain/table lines that existing admission owns.
        last_joint = max(int(s.rsplit(':', 1)[1]) for _, s in admitted)
        self.assertTrue(after and all(hit['source'].startswith(source+':')
                                      and int(hit['source'].rsplit(':', 1)[1]) > last_joint for hit in after))

    def test_frozen_candidate_controls_refuse(self):
        row = self.prepared['joint_art']['writes'][0]
        broken = bytearray(self.compiled); broken[row['pc'][0]] ^= 1
        with self.assertRaisesRegex(ValueError, 'PREIMAGE_OR_PAYLOAD_DIFFERS'):
            O.joint_art_spans(self.prepared, bytes(broken), self.proof, [])
        changed = copy.deepcopy(self.prepared); changed['joint_art']['writes'].pop()
        with self.assertRaisesRegex(ValueError, 'PLAN_DIFFERS'):
            O.joint_art_spans(changed, self.compiled, self.proof, [])
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_UNVERIFIED'):
            O.joint_art_spans(self.prepared, self.compiled, {}, [])


if __name__ == '__main__':
    unittest.main()
