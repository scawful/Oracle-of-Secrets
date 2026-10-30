"""Actual resident resource ASM against independent, unallocated CPU fixtures.

The sparse images replace generated data dependencies, never product routines.
They do not run a SNES, publish an allocation, or establish native gameplay.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import asm_source as S

CACHE = 0x7E1E20  # Synthetic CPU fixture storage only; not an ownership grant.
NATIVE_CACHE = 0x7E04CB
ANIMATION_CACHE = 0x7E0FC0
FRAME_BASES = (0x7EA680, 0x7EAA80, 0x7EAE80)
SHEET_BASES = (0x7F2000, 0x7F2800, 0x7F3000, 0x7F0000,
               0x7F0800, 0x7F1000, 0x7F1800, 0x7F3800)
MAIN_SLOTS = (0, 1, 2, 7)


def pc(address):
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def labels(raw):
    return {name: int(bank + offset, 16) for bank, offset, name in re.findall(
        r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$', raw, re.M)}


def write(address, raw):
    return dict(address=address, bytes=list(raw))


def read(address, length):
    return dict(address=address, length=length)


def canonical_ram(address):
    if address >> 16 & 127 < 64 and address & 65535 < 8192:
        return 0x7E0000 | (address & 65535)
    return address


class ResidentResourceCpuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        cls.runner = os.environ.get('OOS_CPU_RUNNER')
        if not cls.asar or not cls.runner:
            raise unittest.SkipTest('Set ASAR_BIN and OOS_CPU_RUNNER for resident resource CPU checks')
        cls.temporary = tempfile.TemporaryDirectory(prefix='lyra-resident-resources-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.seed = bytearray(0x400000)
        cls.static = {slot: bytes((slot * 31 + i + 1) & 255 for i in range(32))
                      for slot in range(8)}
        cls.destinations = {slot: SHEET_BASES[slot] + (0x420 if slot == 7 else 0x20)
                            for slot in range(8)}
        for slot, raw in cls.static.items():
            cls.put(0x5C8000 + slot * 64, raw)
        cls.frames = {page: tuple(bytes((frame * 0x43 + i * 3 + page) & 255
                                       for i in range(1024)) for frame in range(3))
                      for page in (0xA0, 0xA2)}
        for page, origin, count in ((0xA0, 0x5E8000, 64), (0xA2, 0x5EB000, 1024)):
            pointers = []
            for frame, raw in enumerate(cls.frames[page]):
                address = origin + frame * 0x1000
                cls.put(address, raw)
                pointers.append(address)
            cls.put(0x5D8000 + (page - 0xA0) * 11,
                    b''.join(value.to_bytes(3, 'little') for value in pointers)
                    + count.to_bytes(2, 'little'))
        cls.seed = bytes(cls.seed)
        cls.constants = '\n'.join((
            '!LYRA_CURRENT_MODE = 1', '!ENABLE_KALYXO_BOAT = 0',
            '!ENABLE_OW_AREA_TILESETS = 0', '!LYRA_CURRENT_FIRST = $A0',
            '!LYRA_CURRENT_END = $C0', '!LYRA_CURRENT_PARENT_COUNT = $C0',
            '!LYRA_CURRENT_GFX_ORIGIN = $5B8000', '!LYRA_CURRENT_GFX_END = $5BC000',
            '!LYRA_CURRENT_RESIDENT_ENABLED = 1',
            '!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 1',
            '!LYRA_CURRENT_RESIDENT_ABI_VERSION = 1',
            '!LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE = $7E1E20',
            '!LYRA_CURRENT_RESIDENT_MAIN_CACHE_END = $7E1E24',
            '!LYRA_CURRENT_RESIDENT_MAIN_CACHE_RESET_BOUND = 1',
            '!LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE = $5DC000',
            '!LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END = $5DE000',
            '!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY = $5D8000'))
        cls.image, result = cls.assemble('enabled', cls.constants)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.symbols = labels(cls.image.with_suffix('.sym').read_text())

    @classmethod
    def put(cls, address, raw):
        cls.seed[pc(address):pc(address) + len(raw)] = raw

    @classmethod
    def table_source(cls):
        # An independent fixture for the maintained 22/7/8-byte ABI.
        constants = dict(ABIVersion=1, Bank=0x5B, ParentCount=192, HeaderSize=22,
                         NormalCount=0, NormalPtr=2, CacheMask=4,
                         TransitionMode=5, TransitionStart=6, TransitionEnd=8,
                         TransitionSource=10, StagingCount=13, StagingPtr=15,
                         LateFirst=17, LateEnd=18, LateSource=19,
                         NormalRecordSize=7, StagingRecordSize=8,
                         ModeNone=0, ModeRange=1, ModeStart=2, ModeNative=3)
        text = [f'!GfxRT_{name} = ${value:04X}' for name, value in constants.items()]
        text.append('SharedGraphicsParentProfiles:')
        for area in range(192):
            value = ('FixtureMain' if area == 0xA0 else 'FixtureAll' if area == 0xA1
                     else 'FixtureEmpty' if area == 0xA2 else '$0000')
            text.append('dw ' + (value + '&$FFFF' if not value.startswith('$') else value))
        for name, mask, count in (('FixtureMain', 0x87, 8), ('FixtureAll', 0xFF, 8),
                                  ('FixtureEmpty', 0, 0)):
            text += [name + ':', 'dw $0000,$0000', f'db ${mask:02X},$03',
                     'dw $0000,$0000', 'dl $000000',
                     f'dw ${count:04X},FixtureStaging&$FFFF', 'db $00,$00', 'dl $000000',
                     f'assert pc()-{name} == $0016']
        text.append('FixtureStaging:')
        for slot in range(8):
            text += [f'dl ${0x5C8000 + slot * 64:06X},${cls.destinations[slot]:06X}',
                     'dw $0020']
        return '\n'.join(text)

    @classmethod
    def assemble(cls, name, constants, *, resource_only=False, resource_source=None):
        image, driver = cls.folder / (name + '.sfc'), cls.folder / (name + '.asm')
        image.write_bytes(cls.seed)
        resource = ROOT / 'Overworld/lyra_resident_resources.asm'
        if resource_source is not None:
            resource = cls.folder / (name + '-resource.asm')
            resource.write_text(resource_source)
        source = ['lorom', constants]
        if not resource_only:
            runtime = (ROOT / 'Overworld/graphics_runtime.asm').read_text()
            dependency = 'incsrc "Data/Generated/lyra_project/graphics_runtime_tables.asm"'
            if runtime.count(dependency) != 1:
                raise AssertionError('Maintained current graphics table dependency changed')
            runtime = runtime.replace(dependency, cls.table_source(), 1)
            callbacks = (ROOT / 'Overworld/custom_gfx.asm').read_text()
            callbacks = callbacks[callbacks.index('InvalidateCustomGraphicsCache:'):
                                  callbacks.index('macro ApplyGraphicsSheet(')]
            # The extracted callbacks retain their actual closing conditional.
            source += ['namespace Oracle', 'org $5B8000', runtime, 'org $5BD000',
                       'if !LYRA_CURRENT_MODE == 1 || !ENABLE_KALYXO_BOAT == 1',
                       callbacks, 'namespace off']
        source += [f'incsrc "{resource}"', cls.native_stub()]
        driver.write_text('\n'.join(source) + '\n')
        result = subprocess.run([cls.asar, '--no-title-check', '--fix-checksum=off',
                                 '--symbols=wla', str(driver), str(image)],
                                capture_output=True, text=True, timeout=20)
        return image, result

    @staticmethod
    def native_stub():
        # A synthetic native return contract, not a decompressor implementation.
        return ('org $00D394\nPHB : PHK : PLB\nREP #$30\nLDX.w #$0000\n'
                '.frames\nLDA.w #$BABA\nSTA.l $7EA680,X\nSTA.l $7EAA80,X\n'
                'STA.l $7EAE80,X\nINX #2 : CPX.w #$0400 : BCC .frames\n'
                'LDA.w #$5A5A : STA.b $00 : STA.b $02 : STA.b $04\n'
                'LDA.w #$C3C3 : STA.b $0E\nLDA.w #$3C00 : STA.w $0134\n'
                'SEP #$30\nLDX.b #$80 : LDY.b #$FF\nPLB\nRTL\n')

    def run_cpu(self, requests, *, image=None):
        run = subprocess.run([self.runner, str(image or self.image)],
                             input=''.join(json.dumps(row) + '\n' for row in requests),
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        output = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(output), len(requests))
        for result in output:
            self.assertTrue(result['returned'], result)
            self.assertFalse(result.get('stub_calls'))
            self.assertFalse(result.get('mmio_writes'))
        return output

    def request(self, name, regs, *, writes=(), reads=(), max_steps=50000):
        return dict(entry=self.symbols['Oracle_' + name], reset_ram=True,
                    registers=regs, writes=list(writes), reads=list(reads),
                    trace_writes=True, max_steps=max_steps)

    @staticmethod
    def registers(p=0x41, **overrides):
        values = dict(a=0xABCD, x=0x45 if p & 0x10 else 0x2345,
                      y=0x67 if p & 0x10 else 0x4567, p=p, db=8, d=0x120, sp=0x1FFF)
        values.update(overrides)
        return values

    def assert_preserved(self, result, regs, *, a=None, p=None):
        expected = dict(regs, a=regs['a'] if a is None else a,
                        p=regs['p'] if p is None else p)
        for key in ('a', 'x', 'y', 'p', 'db', 'd', 'sp'):
            self.assertEqual(result['registers'][key], expected[key], key)

    def assert_writes_within(self, result, extra=()):
        allowed = set(range(0x7E1E80, 0x7E2000)) | set(extra)
        for observed in result['writes']:
            self.assertIn(canonical_ram(observed['address']), allowed)

    def test_reset_mark_repeat_and_native_resolver_preserve_abi_and_owned_backups(self):
        requests, expectations = [], []
        prior = bytes(range(10, 18))
        for p in (0x41, 0x71, 0x61, 0x49, 0x79):
            regs = self.registers(p)
            requests.append(self.request('ResidentGraphicsResetMainCache', regs,
                writes=[write(CACHE - 1, b'\x77' + bytes(4) + b'\x88')],
                reads=[read(CACHE - 1, 6)]))
            expectations.append(('reset', regs, b'\x77' + b'\xff' * 4 + b'\x88'))
            for area, indoor, start, backing in (
                    (0xA0, 0, prior, b'\x01\x02\x03\x04'),
                    (0xA0, 0, b'\xff' * 8, b'\x0a\x0b\x0c\x11'),
                    (0x9F, 0, prior, b'\x01\x02\x03\x04'),
                    (0xA0, 1, prior, b'\x01\x02\x03\x04')):
                selected = area == 0xA0 and not indoor
                marked = bytes(255 if slot in MAIN_SLOTS else value for slot, value in enumerate(start))
                saved = (bytes(start[slot] for slot in MAIN_SLOTS)
                         if selected and start != b'\xff' * 8 else backing)
                requests.append(self.request('SharedGraphicsInvalidateCache', regs,
                    writes=[write(0x7E008A, bytes([area])), write(0x7E001B, bytes([indoor])),
                            write(NATIVE_CACHE, start), write(CACHE, backing),
                            write(0x7EC2F5, b'\x31\x32\x33' + b'\x44' * 4 + b'\x99')],
                    reads=[read(NATIVE_CACHE, 8), read(CACHE, 4), read(0x7EC2F5, 8)]))
                expectations.append(('mark', regs, (marked if selected else start, saved)))
        for result, (kind, regs, expected) in zip(self.run_cpu(requests), expectations):
            with self.subTest(kind=kind, p=regs['p'], expected=expected):
                self.assert_preserved(result, regs)
                if kind == 'reset':
                    self.assertEqual(result['reads'][0]['bytes'], list(expected))
                else:
                    self.assertEqual(result['reads'][0]['bytes'], list(expected[0]))
                    self.assertEqual(result['reads'][1]['bytes'], list(expected[1]))
                    self.assertEqual(result['reads'][2]['bytes'], list(b'\x31\x32\x33' + b'\x44' * 4 + b'\x99'))
                allowed = set(range(CACHE, CACHE + 4))
                if kind == 'mark':
                    allowed.update(range(NATIVE_CACHE, NATIVE_CACHE + 8))
                self.assert_writes_within(result, allowed)

    def test_main_ff_resolution_includes_departure_and_rejects_invalid_or_stale_backup(self):
        requests, cases = [], []
        for slot in range(8):
            for raw, prior, backup in ((255, 255, 43), (255, 255, 255),
                                        (255, 17, 43), (7, 255, 43)):
                regs = self.registers(0x61, a=0xAB00 | raw, x=slot)
                saved = bytes([backup] * 4)
                expected = raw
                if raw == prior == 255:
                    expected = backup if slot in MAIN_SLOTS else 61 + slot - 3
                requests.append(self.request('ResolveCustomGraphicsTransitionSheet', regs,
                    writes=[write(0x7E008A, b'\x9f'), write(NATIVE_CACHE, bytes([prior] * 8)),
                            write(CACHE, saved), write(0x7EC2F8, bytes(range(61, 65)))],
                    reads=[read(CACHE, 4), read(NATIVE_CACHE, 8)]))
                cases.append((regs, expected))
        for result, (regs, expected) in zip(self.run_cpu(requests), cases):
            with self.subTest(slot=regs['x'], raw=regs['a'] & 255, expected=expected):
                self.assert_preserved(result, regs, a=0xAB00 | expected)
                self.assert_writes_within(result)

    def test_sparse_main_and_aux_staging_keep_holes_native_domain_and_live_scratch(self):
        requests, cases = [], []
        scratch = bytes((i * 13 + 7) & 255 for i in range(32))
        for helper, slots in (('SharedGraphicsStageNativeMain', set(MAIN_SLOTS)),
                              ('SharedGraphicsStageNative', set(range(3, 7)))):
            for p in (0x41, 0x71, 0x49, 0x79):
                for area, indoor in ((0xA1, 0), (0xA2, 0), (0x9F, 0), (0xA1, 1)):
                    regs = self.registers(p)
                    selected = slots if area == 0xA1 and not indoor else set()
                    requests.append(self.request(helper, regs,
                        writes=[write(0x7E008A, bytes([area])), write(0x7E001B, bytes([indoor])),
                                write(0x7E0120, scratch)] +
                               [write(base, b'\xa5' * 0x800) for base in SHEET_BASES],
                        reads=[read(base, 0x800) for base in SHEET_BASES] + [read(0x7E0120, 32)]))
                    cases.append((helper, regs, selected))
        for result, (helper, regs, selected) in zip(self.run_cpu(requests), cases):
            with self.subTest(helper=helper, p=regs['p'], selected=selected):
                self.assert_preserved(result, regs)
                allowed = set()
                for slot, observed in enumerate(result['reads'][:8]):
                    expected = bytearray(b'\xa5' * 0x800)
                    if slot in selected:
                        at = self.destinations[slot] - SHEET_BASES[slot]
                        expected[at:at + 32] = self.static[slot]
                        allowed.update(range(self.destinations[slot], self.destinations[slot] + 32))
                    self.assertEqual(observed['bytes'], list(expected), slot)
                self.assertEqual(result['reads'][-1]['bytes'], list(scratch))
                self.assert_writes_within(result, allowed)

    def test_animation_three_prefixes_zero_full_length_and_caller_abi(self):
        requests, cases = [], []
        scratch = bytes((i * 7 + 11) & 255 for i in range(32))
        for page, indoor in ((0xA0, 0), (0xA1, 0), (0xA2, 0),
                              (0x9F, 0), (0xC0, 0), (0xA0, 1)):
            for p in (0x41, 0x71, 0x61, 0x49, 0x79):
                regs = self.registers(p)
                selected = not indoor and 0xA0 <= page < 0xC0
                count = 64 if page == 0xA0 and selected else 1024 if page == 0xA2 and selected else 0
                requests.append(self.request('ResidentAnimationStage', regs,
                    writes=[write(0x7E008A, bytes([page])), write(0x7E001B, bytes([indoor])),
                            write(ANIMATION_CACHE, b'\x5b'), write(0x7E0120, scratch)] +
                           [write(base, b'\xa5' * 1024) for base in FRAME_BASES],
                    reads=[read(base, 1024) for base in FRAME_BASES] +
                          [read(ANIMATION_CACHE, 1), read(0x7E0120, 32)]))
                cases.append((page, regs, selected, count))
        for result, (page, regs, selected, count) in zip(self.run_cpu(requests), cases):
            with self.subTest(page=page, p=regs['p'], count=count):
                self.assert_preserved(result, regs)
                allowed = {ANIMATION_CACHE} if selected else set()
                for frame, observed in enumerate(result['reads'][:3]):
                    expected = self.frames[page][frame][:count] if count else b''
                    expected += b'\xa5' * (1024 - count)
                    self.assertEqual(observed['bytes'], list(expected), frame)
                    allowed.update(range(FRAME_BASES[frame], FRAME_BASES[frame] + count))
                self.assertEqual(result['reads'][3]['bytes'], [255 if selected else 0x5B])
                self.assertEqual(result['reads'][4]['bytes'], list(scratch))
                self.assert_writes_within(result, allowed)

    def test_animation_force_handles_unchanged_selector_disabled_pool_and_departure(self):
        requests, cases = [], []
        for page, indoor in ((0xA0, 0), (0xBF, 0), (0x9F, 0), (0xC0, 0), (0xA0, 1)):
            for old in (0x5B, 255):
                for p in (0x61, 0x71, 0x69, 0x79):
                    regs = self.registers(p)
                    expected = int((not indoor and 0xA0 <= page < 0xC0) or old == 255)
                    requests.append(self.request('ResidentAnimationForceTransition', regs,
                        writes=[write(0x7E008A, bytes([page])), write(0x7E001B, bytes([indoor])),
                                write(ANIMATION_CACHE, bytes([old]))], reads=[read(ANIMATION_CACHE, 1)]))
                    cases.append((regs, old, expected))
        for result, (regs, old, expected) in zip(self.run_cpu(requests), cases):
            with self.subTest(p=regs['p'], old=old, expected=expected):
                self.assert_preserved(result, regs, a=(regs['a'] & 0xFF00) | expected,
                                      p=(regs['p'] & ~0x82) | (0 if expected else 2))
                self.assertEqual(result['reads'][0]['bytes'], [old])
                self.assert_writes_within(result)

    def test_animation_malformed_extent_leaves_buffers_and_provenance_unchanged(self):
        for count in (1, 65, 1025):
            with self.subTest(byte_count=count):
                raw = bytearray(self.image.read_bytes())
                at = pc(0x5D8000) + 9
                raw[at:at + 2] = count.to_bytes(2, 'little')
                image = self.folder / f'bad-animation-count-{count}.sfc'
                image.write_bytes(raw)
                regs = self.registers(0x79)
                request = self.request('ResidentAnimationStage', regs,
                    writes=[write(0x7E008A, b'\xa0'), write(0x7E001B, b'\x00'),
                            write(ANIMATION_CACHE, b'\x5b')] +
                           [write(base, b'\xa5' * 1024) for base in FRAME_BASES],
                    reads=[read(base, 1024) for base in FRAME_BASES] + [read(ANIMATION_CACHE, 1)])
                result = self.run_cpu([request], image=image)[0]
                self.assert_preserved(result, regs)
                for observed in result['reads'][:3]:
                    self.assertEqual(observed['bytes'], [0xA5] * 1024)
                self.assertEqual(result['reads'][3]['bytes'], [0x5B])
                self.assert_writes_within(result)

    def test_old_word_sized_bank_store_control_loses_the_64_byte_prefix(self):
        source = (ROOT / 'Overworld/lyra_resident_resources.asm').read_text()
        fixed = '  SEP #$20\n  LDA.b #$7E : STA.b $05\n  REP #$20'
        self.assertEqual(source.count(fixed), 1, 'Maintained bank-store boundary changed')
        mutant = source.replace(fixed, '  LDA.w #$007E : STA.b $05', 1)
        image, assembled = self.assemble('old-word-bank-store', self.constants,
                                        resource_source=mutant)
        self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
        regs = self.registers(0x79)
        request = self.request('ResidentAnimationStage', regs,
            writes=[write(0x7E008A, b'\xa0'), write(0x7E001B, b'\x00'),
                    write(ANIMATION_CACHE, b'\x5b')] +
                   [write(base, b'\xa5' * 1024) for base in FRAME_BASES],
            reads=[read(base, 1024) for base in FRAME_BASES] + [read(ANIMATION_CACHE, 1)])
        result = self.run_cpu([request], image=image)[0]
        self.assert_preserved(result, regs)
        for frame, observed in enumerate(result['reads'][:3]):
            # The M16 store at05 clears count.low at06, skipping every copy.
            self.assertEqual(observed['bytes'], [0xA5] * 1024)
            self.assertNotEqual(observed['bytes'][:64], list(self.frames[0xA0][frame][:64]))
        self.assertEqual(result['reads'][3]['bytes'], [255])
        self.assert_writes_within(result, {ANIMATION_CACHE})

    def test_animation_wrapper_preserves_post_native_state_and_outside_prefix(self):
        regs = self.registers(0x71, d=0, a=0x1234, x=0x67, y=0x5A)
        request = self.request('ResidentAnimationDecompress', regs,
            writes=[write(0x7E008A, b'\xa0'), write(0x7E001B, b'\x00')],
            reads=[read(base, 1024) for base in FRAME_BASES] +
                  [read(0x7E0000, 6), read(0x7E000E, 2), read(0x7E0134, 2), read(ANIMATION_CACHE, 1)])
        result = self.run_cpu([request])[0]
        cpu = result['registers']
        self.assertEqual({key: cpu[key] for key in ('a', 'x', 'y', 'd', 'db', 'sp')},
                         dict(a=0x3C00, x=0x80, y=255, d=0, db=8, sp=0x1FFF))
        for frame, observed in enumerate(result['reads'][:3]):
            self.assertEqual(observed['bytes'], list(self.frames[0xA0][frame][:64] + b'\xba' * 960))
        self.assertEqual(result['reads'][3]['bytes'], [0x5A] * 6)
        self.assertEqual(result['reads'][4]['bytes'], [0xC3] * 2)
        self.assertEqual(result['reads'][5]['bytes'], [0, 0x3C])
        self.assertEqual(result['reads'][6]['bytes'], [255])

    def test_resource_gates_require_explicit_cache_reset_code_and_directory_bounds(self):
        resource = ROOT / 'Overworld/lyra_resident_resources.asm'
        disabled = self.folder / 'disabled.asm'
        image = self.folder / 'disabled.sfc'
        image.write_bytes(self.seed)
        disabled.write_text(f'lorom\nincsrc "{resource}"\n')
        result = subprocess.run([self.asar, '--no-title-check', '--fix-checksum=off',
                                 str(disabled), str(image)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(image.read_bytes(), self.seed)
        cases = (
            ('unbound-cache', self.constants.replace('!LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE = $7E1E20', '')),
            ('bad-cache-size', self.constants.replace('MAIN_CACHE_END = $7E1E24', 'MAIN_CACHE_END = $7E1E25')),
            ('unbound-reset', self.constants.replace('MAIN_CACHE_RESET_BOUND = 1', 'MAIN_CACHE_RESET_BOUND = 0')),
            ('wrong-abi', self.constants.replace('RESIDENT_ABI_VERSION = 1', 'RESIDENT_ABI_VERSION = 2')),
            ('bad-resource-code', self.constants.replace('RESOURCE_CODE_END = $5DE000', 'RESOURCE_CODE_END = $5EC001')),
            ('bad-animation-directory', self.constants.replace('ANIMATION_DIRECTORY = $5D8000', 'ANIMATION_DIRECTORY = $5DFF80')),
        )
        for name, constants in cases:
            with self.subTest(gate=name):
                _, result = self.assemble(name, constants)
                self.assertNotEqual(result.returncode, 0, 'Unbound resident resource source assembled')


class ResidentResourceCallersSourceTest(unittest.TestCase):
    """Guarded live-source wiring only; these checks do not execute callers."""
    @classmethod
    def setUpClass(cls):
        cls.zs = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '0'}):
            cls.defines = S._load_global_defines(ROOT)
        cls.defines.update(LYRA_CURRENT_MODE=1, LYRA_PROJECT_DATA_PRESENT=1,
                           LYRA_CURRENT_RESIDENT_ENABLED=1,
                           LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED=1)

    @classmethod
    def active(cls, source, *, enabled=True):
        defines = dict(cls.defines, LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED=int(enabled))
        result = []
        for _, line, _ in S._iter_active_lines(source.splitlines(), defines):
            line = line.split(';', 1)[0].strip()
            if not line or line in ('{', '}') or line.startswith('assert '):
                continue
            result.extend(part.strip() for part in line.split(':') if part.strip())
        return result

    def test_transition_forcing_precedes_disabled_and_equal_selector_exits(self):
        start = self.zs.index('CheckForChangeGraphicsTransitionLoad:\n')
        stop = self.zs.index('LoadTransMainGFX:\n', start)
        tokens = self.active(self.zs[start:stop])
        split = tokens.index('.mosaic')
        for ordinal, branch in enumerate((tokens[:split], tokens[split:]), 1):
            with self.subTest(transition=ordinal):
                force = branch.index('JSL Oracle_ResidentAnimationForceTransition')
                compare = branch.index('CMP.w AnimatedTileGFXSet')
                load = branch.index(f'.loadAnimated{ordinal}')
                self.assertEqual(branch[force + 1:force + 5], [
                    f'BEQ .nativeAnimatedDecision{ordinal}', 'JSL.l ReadAnimatedTable',
                    f'BRA .loadAnimated{ordinal}', f'.nativeAnimatedDecision{ordinal}'])
                self.assertLess(force, compare)
                self.assertGreater(load, compare)
                self.assertEqual(branch[load + 1:load + 5], [
                    'STA.w AnimatedTileGFXSet', 'DEC', 'TAY',
                    'JSL Oracle_ResidentAnimationDecompress'])
                if ordinal == 1:
                    self.assertLess(force, branch.index('LDA.l Pool_EnableAnimated'))

    def test_six_guarded_decompressors_and_all_five_cache_writers_rearm_residency(self):
        tokens = self.active(self.zs)
        self.assertEqual(tokens.count('JSL Oracle_ResidentAnimationDecompress'), 6)
        self.assertNotIn('JSL.l DecompOwAnimatedTiles', tokens)
        disabled = self.active(self.zs, enabled=False)
        self.assertNotIn('JSL Oracle_ResidentAnimationDecompress', disabled)
        self.assertNotIn('JSL Oracle_ResidentAnimationStage', disabled)
        self.assertEqual(disabled.count('JSL.l DecompOwAnimatedTiles'), 6)
        writers = [index for index, token in enumerate(tokens)
                   if token == 'STA.w AnimatedTileGFXSet']
        self.assertEqual(len(writers), 5)
        rearmed = dict(decompress=0, stage=0, mirror=0)
        for index in writers:
            following = tokens[index + 1:index + 4]
            if following[:2] == ['DEC', 'TAY']:
                self.assertEqual(following[2], 'JSL Oracle_ResidentAnimationDecompress')
                rearmed['decompress'] += 1
            elif following[0] == 'JSL Oracle_ResidentAnimationStage':
                rearmed['stage'] += 1
            else:
                self.assertEqual(following[:2], [
                    'STA.w TransGFXModule_PriorSheets+7', 'JSL Oracle_ResidentAnimationStage'])
                rearmed['mirror'] += 1
        self.assertEqual(rearmed, dict(decompress=2, stage=2, mirror=1))


class ResidentStartupOwnershipCpuTest(unittest.TestCase):
    """Actual startup bodies with a literal native boot M8/X8, DB0, D0 ABI.

    Only DekuStick_Drop and the unrelated boot continuation are RTL stubs.
    The sparse fixture does not load other Masks or palette routines, grant
    storage, or change the existing resident resource CPU cases above.
    """
    BOOT = 0x008827
    NATIVE_BOOT = bytes.fromhex('a9808513')

    @classmethod
    def setUpClass(cls):
        cls.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        cls.runner = os.environ.get('OOS_CPU_RUNNER')
        if not cls.asar or not cls.runner:
            raise unittest.SkipTest('Set ASAR_BIN and OOS_CPU_RUNNER for startup ownership checks')
        cls.temporary = tempfile.TemporaryDirectory(prefix='lyra-startup-ownership-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.images = {}
        masks = (ROOT / 'Masks/mask_routines.asm').read_text()
        palette = (ROOT / 'Overworld/project_bg_palette.asm').read_text()
        # Keep the actual conditional ownership declaration and complete body.
        cls.mask_header = masks[:masks.index('; Link Sprite hook before game starts')]
        cls.mask_body = masks[masks.index('org $3A8000\nStartupMasks:'):
                              masks.index('PlayerTransform:')]
        cls.palette_assignments = palette[palette.index('ProjectBGPalette_NativeReference ='):
                                         palette.index('; Any M/X. Byte stores only;')]
        cls.palette_bodies = palette[palette.index('ProjectBGPalette_Reset:'):
                                    palette.index('ProjectBGPalette_RestoreAndInvalidate:')]
        hook = palette.index('org $008827 ; @hook')
        end = palette.index('assert pc() == $00882B', hook)
        cls.palette_hook = palette[hook:end + len('assert pc() == $00882B')]
        writer = next(line for line in cls.mask_header.splitlines()
                      if line.startswith('org $008827'))
        # Non-emitting instrumentation follows the actual writer inside its
        # actual conditional. This detects duplicate ownership even when the
        # later patch would hide it in the final ROM bytes.
        marker = '\n!Fixture_MasksBootWriter = 1'
        cls.mask_header = cls.mask_header.replace(writer, writer + marker, 1)
        cls.legacy_header = writer + marker + '\nassert pc() == $00882B\n'

    @classmethod
    def assemble(cls, *, masks, bg, old_writer=False):
        key = masks, bg, old_writer
        if key in cls.images:
            return cls.images[key]
        name = f'masks-{int(masks)}-bg-{int(bg)}-old-{int(old_writer)}'
        image, driver = cls.folder / (name + '.sfc'), cls.folder / (name + '.asm')
        seed = bytearray(0x400000)
        seed[pc(cls.BOOT):pc(cls.BOOT) + 4] = cls.NATIVE_BOOT
        image.write_bytes(seed)
        source = ['lorom',
            '; Literal startup profile: native M8/X8, DB0/D0; no resident activation.',
            f'!DISABLE_MASKS = {int(not masks)}', f'!PROJECT_BG128_ENABLED = {int(bg)}',
            '!LYRA_CURRENT_RESIDENT_ENABLED = 0',
            '!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 0',
            '!PROJECT_BG128_CODE_BASE = $5FC000', 'namespace Oracle']
        if masks:
            source += [cls.legacy_header if old_writer else cls.mask_header, cls.mask_body,
                       'org $3A9000', 'DekuStick_Drop:', 'RTL']
        if bg:
            source += ['org !PROJECT_BG128_CODE_BASE', cls.palette_assignments, cls.palette_bodies,
                'assert not(defined("Fixture_MasksBootWriter")), "Startup boot site already has a writer"',
                'assert read4($008827) == $138580A9, "Native boot preimage differs"',
                cls.palette_hook]
        source += ['namespace off', 'org $00882B',
                   '; Synthetic return after the actual four-byte boot call.',
                   'Fixture_BootReturn:', 'RTL']
        driver.write_text('\n'.join(source) + '\n')
        assembled = subprocess.run([cls.asar, '--no-title-check', '--fix-checksum=off',
            '--symbols=wla', str(driver), str(image)], capture_output=True, text=True, timeout=20)
        result = image, assembled
        cls.images[key] = result
        return result

    def assert_startup(self, *, masks, bg):
        image, assembled = self.assemble(masks=masks, bg=bg)
        self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
        symbols = labels(image.with_suffix('.sym').read_text())
        target = 'Oracle_ProjectBGPalette_Startup' if bg else 'Oracle_StartupMasks'
        self.assertIn(target, symbols)
        raw = image.read_bytes()
        self.assertEqual(raw[pc(self.BOOT):pc(self.BOOT) + 4],
                         b'\x22' + symbols[target].to_bytes(3, 'little'))
        self.assertEqual('Oracle_StartupMasks' in symbols, masks)
        self.assertEqual('Oracle_ProjectBGPalette_Reset' in symbols, bg)
        requests, registers = [], []
        for x in (0, 0x77, 0xFF):
            regs = dict(a=0xABCD, x=x, y=0x35, p=0x31, db=0, d=0, sp=0x1FFF)
            registers.append(regs)
            requests.append(dict(entry=self.BOOT, reset_ram=True, registers=regs,
                writes=[write(0x7E0013, b'\x29'), write(0x7E00BC, b'\x5c'),
                        write(0x7E07ED, b'\x98' + b'\xe7' * 18 + b'\x99'),
                        write(0x7ECA00, b'\x6d' * 256), write(0x7ECB00, b'\x4e' * 256),
                        write(0x7ECC00, b'\xa5\x5a\x77')],
                reads=[read(0x7E0013, 1), read(0x7E00BC, 1), read(0x7E07ED, 20),
                       read(0x7ECA00, 256), read(0x7ECB00, 256), read(0x7ECC00, 3)],
                trace_writes=True, max_steps=1000))
        run = subprocess.run([self.runner, str(image)],
            input=''.join(json.dumps(row) + '\n' for row in requests),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        results = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(results), len(requests))
        for result, regs in zip(results, registers):
            with self.subTest(masks=masks, bg=bg, x=regs['x']):
                self.assertTrue(result['returned'], result)
                self.assertFalse(result.get('stub_calls'))
                self.assertFalse(result.get('mmio_writes'))
                for key in ('x', 'y', 'db', 'd', 'sp'):
                    self.assertEqual(result['registers'][key], regs[key], key)
                self.assertEqual(result['registers']['a'], 0xAB10 if masks else 0xAB80)
                self.assertEqual(result['registers']['p'] & ~0x82, regs['p'] & ~0x82)
                expected = [[0x80], [0x10 if masks else 0x5C],
                    list(b'\x98' + (bytes(18) if masks else b'\xe7' * 18) + b'\x99'),
                    [0x6D] * 256, [0x4E] * 256,
                    [0, 255, 0x77] if bg else [0xA5, 0x5A, 0x77]]
                self.assertEqual([row['bytes'] for row in result['reads']], expected)
                allowed = set(range(0x7E1E80, 0x7E2000)) | {0x7E0013}
                if masks:
                    allowed |= {0x7E00BC} | set(range(0x7E07EE, 0x7E0800))
                if bg:
                    allowed |= {0x7ECC00, 0x7ECC01}
                for observed in result['writes']:
                    self.assertIn(canonical_ram(observed['address']), allowed)

    def test_masks_on_bg_off_keeps_native_call_bytes_and_actual_masks_body(self):
        self.assert_startup(masks=True, bg=False)
        current, assembled = self.assemble(masks=True, bg=False)
        legacy, old = self.assemble(masks=True, bg=False, old_writer=True)
        self.assertEqual(old.returncode, 0, old.stdout + old.stderr)
        self.assertEqual(current.read_bytes(), legacy.read_bytes())

    def test_masks_on_bg_on_has_one_composed_owner_and_actual_masks_body(self):
        self.assert_startup(masks=True, bg=True)

    def test_masks_off_bg_on_resets_palette_without_a_masks_body(self):
        self.assert_startup(masks=False, bg=True)

    def test_old_unconditional_masks_writer_conflicts_with_bg_startup_owner(self):
        _, old = self.assemble(masks=True, bg=True, old_writer=True)
        self.assertNotEqual(old.returncode, 0, 'Old duplicate startup writers assembled unnoticed')
        self.assertIn('Startup boot site already has a writer', old.stdout + old.stderr)


if __name__ == '__main__':
    unittest.main()
