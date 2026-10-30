"""Checkpoint contact through the native ground-displacement arithmetic.

Uses the existing CPU runner, not a SNES instance. Moving-floor/conveyor calls
are explicit RTS test doubles. No collision, controller or native-save claim.
"""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import unittest

import test_checkpoint_native_preview as F
from allocation_contracts import read_symbols


# Build09's07E370..07E405, including the real native fixed-point displacement
# loop. CurrentMask/Link state and floor drag are zero in this arithmetic case.
# The two JSR tails at07E3D5/07E3D8 are the only substituted instructions.
GROUND_DISPLACEMENT = bytes.fromhex(
    '8b4baba5208500853ea5228501853fa52185028540a52385038541a55dc909f007'
    'adf502c902f048a002a204a54dd004a001a202b927000a0a0a0a18792a00992a00'
    '5a08b927004a4a4a4ac908a000900409f0a0ff287520952098752195217a88caca'
    '10cf2095e520f0e580038b4babc220a520186d7e0b8520a522186d7c0b8522'
    'e220a52038e5008530a52238e5018531e220ab6b')
CONTACT = '''    LDA.b $20 : SEC : SBC.l CheckpointRegistry_Records+18,X
    CMP.w #$0002 : BCS .restore_index
    LDA.b $22 : SEC : SBC.l CheckpointRegistry_Records+20,X
    CMP.w #$0002 : BCS .restore_index'''
EXACT = '''    LDA.l CheckpointRegistry_Records+18,X : CMP.b $20 : BNE .restore_index
    LDA.l CheckpointRegistry_Records+20,X : CMP.b $22 : BNE .restore_index'''


@unittest.skipUnless(os.environ.get('OOS_CHECKPOINT_CPU_RUNNER'),
                     'Set OOS_CHECKPOINT_CPU_RUNNER to the existing CPU runner')
class CheckpointActivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = F.NativePreviewRegistryTests('test_v1_plan_and_bindings_are_unchanged')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.registry = self.fixture.compile()
        self.runner = Path(os.environ['OOS_CHECKPOINT_CPU_RUNNER'])
        self.assertTrue(self.runner.is_file())
        self.source = (F.ROOT / 'Overworld/checkpoint_state.asm').read_text()
        self.requests, self.answers = [], []
        self.reports = []

    def assembled(self, name, source):
        run, rom = self.fixture.assemble_runtime(name, self.registry, source=source)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        image = bytearray(rom.read_bytes())
        F.put(image, 0x07E370, GROUND_DISPLACEMENT)
        rom.write_bytes(image)
        labels = read_symbols(rom.with_suffix('.sym'))
        proof = F.C.verify_runtime_tables(self.registry, bytes(image), labels)
        self.reports.append(dict(name=name, code_bytes=proof['first_data']-F.C.CODE_BASE,
                                 data_bytes=proof['data_bytes'], end=proof['end']))
        return rom, labels

    def call(self, process, request):
        self.requests.append(request)
        process.stdin.write(json.dumps(request)+'\n')
        process.stdin.flush()
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'CPU runner response timeout')
        result = json.loads(process.stdout.readline())
        self.answers.append(result)
        self.assertTrue(result.get('returned'), result)
        self.assertEqual(result['registers']['sp'], 0x1FEF)
        self.assertFalse(result.get('mmio_writes'))
        return result

    def process(self, rom):
        p = subprocess.Popen([str(self.runner), str(rom)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
        def close():
            p.stdin.close()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
            p.stdout.close()
        self.addCleanup(close)
        return p

    def sample(self, p, labels, record, x, y, fraction, reset=False):
        writes = []
        if reset:
            writes = [dict(address=0x7EF3B4, bytes=[0]*5),
                dict(address=0x7EF3C5, bytes=[2]), dict(address=0x7EF3CA, bytes=[record.native_affinity]),
                dict(address=0x7E0010, bytes=[0x09 if record.map_id < 0x80 else 0x0B, 0]),
                dict(address=0x7E008A, bytes=[record.map_id]),
                dict(address=0x7E0020, bytes=list(y.to_bytes(2, 'little')+x.to_bytes(2, 'little'))),
                dict(address=0x7E002A, bytes=list(fraction))]
        r = self.call(p, dict(entry=labels['Oracle_Checkpoint_OnFrame'], reset_ram=reset,
            registers=dict(p=0x30, db=2, sp=0x1FEF), writes=writes, trace_writes=True,
            reads=[dict(address=0x7E0020, length=12), dict(address=0x7EF3B4, length=5)], max_steps=3000))
        self.assertFalse(r.get('stub_calls'))
        raw = bytes(r['reads'][0]['bytes'])
        state = dict(x=int.from_bytes(raw[2:4], 'little'), y=int.from_bytes(raw[:2], 'little'),
                     fraction=raw[10:12].hex(), checkpoint=bytes(r['reads'][1]['bytes']).hex())
        # Only the CPU may acquire a nonzero key; inputs initialize an empty state.
        self.assertEqual([w['bytes'] for w in writes if w['address'] == 0x7EF3B4],
                         [[0]*5] if reset else [])
        return state

    def walk(self, p, labels, record, axis, fraction):
        x = int.from_bytes(record.exit_cache[10:12], 'little')
        y = int.from_bytes(record.exit_cache[8:10], 'little')
        start = dict(x=x, y=y)
        start[axis] += 19
        samples = []
        for step in range(36):
            state = self.sample(p, labels, record, start['x'], start['y'],
                (fraction, 0) if axis == 'y' else (0, fraction), reset=step == 0)
            samples.append(state)
            if state['checkpoint'] == f'0101{record.key:02x}0001':
                break
            delta = (x if axis == 'x' else y) - state[axis]
            velocity = 0x18 if delta > 0 else 0xE8 if delta < 0 else 0
            r = self.call(p, dict(entry=0x07E370, registers=dict(p=0x30, db=2, sp=0x1FEF),
                writes=[dict(address=0x7E0027, bytes=[velocity, 0] if axis == 'y' else [0, velocity])],
                stubs=[dict(address=a, **{'return': 'rts'}) for a in (0x07E595, 0x07E5F0)],
                trace_writes=True, max_steps=3000))
            self.assertEqual([r['address'] for r in r['stub_calls']], [0x07E595, 0x07E5F0])
            self.assertFalse(any(0x7EF3B4 <= w['address'] < 0x7EF3B9 for w in r['writes']))
        return samples

    def evidence(self, name, rom):
        destination = os.environ.get('OOS_CHECKPOINT_ACTIVATION_EVIDENCE')
        if not destination:
            return
        out = Path(destination) / name
        out.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(rom, out/'compiled.sfc')
        shutil.copyfile(rom.with_suffix('.sym'), out/'compiled.sym')
        (out/'requests.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.requests))
        (out/'answers.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.answers))
        (out/'RESULT.json').write_text(json.dumps(dict(cases=self.reports,
            scope='CPU arithmetic/predicate only; moving-floor/conveyor tails are RTS doubles; '
                  'no collision, controller, loader or native-save proof'), indent=2)+'\n')
        self.requests.clear()
        self.answers.clear()

    def test_ground_subpixel_contact_and_exact_point_failure_control(self):
        self.assertEqual(self.source.count(CONTACT), 1)
        exact = self.source.replace(CONTACT, EXACT).replace(
            'LDA.b $1B : AND.w #$00FF : BEQ .outdoors\n    JMP .done\n  .outdoors',
            'LDA.b $1B : AND.w #$00FF : BNE .done')
        for name, source, code in (('contact', self.source, 906), ('exact-control', exact, 895)):
            rom, labels = self.assembled(name, source)
            self.assertEqual(self.reports[-1]['code_bytes'], code)
            p = self.process(rom)
            for record in self.registry.records:
                for axis in ('x', 'y'):
                    for fraction in (0, 0x80):
                        with self.subTest(code=name, key=record.key, axis=axis, fraction=fraction):
                            samples = self.walk(p, labels, record, axis, fraction)
                            activated = samples[-1]['checkpoint'] == f'0101{record.key:02x}0001'
                            self.assertEqual(activated, name == 'contact' or fraction == 0x80)
                            self.reports.append(dict(source=name, key=record.key, axis=axis,
                                initial_fraction=fraction, activated=activated, states=samples))
            self.evidence(name, rom)

    def test_contact_has_no_radius_beyond_the_two_pixel_footprint(self):
        rom, labels = self.assembled('footprint', self.source)
        p = self.process(rom)
        for record in self.registry.records:
            x = int.from_bytes(record.exit_cache[10:12], 'little')
            y = int.from_bytes(record.exit_cache[8:10], 'little')
            for dx, dy, accepted in ((0,0,True),(1,0,True),(0,1,True),(1,1,True),
                                     (-1,0,False),(2,0,False),(0,-1,False),(0,2,False)):
                with self.subTest(key=record.key, dx=dx, dy=dy):
                    state = self.sample(p, labels, record, x+dx, y+dy, (0,0), reset=True)
                    self.assertEqual(state['checkpoint'], f'0101{record.key:02x}0001' if accepted else '0101000000')
        self.evidence('footprint', rom)


if __name__ == '__main__':
    unittest.main()
