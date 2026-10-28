"""Assemble the real hookshot source cut; optional offline CPU ABI checks.

The sparse native windows and table values are explicit fixtures, not a game
build, an allocation grant or native gameplay qualification.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_native_loaders as L


class HookshotBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not asar:
            raise unittest.SkipTest('Asar required for hookshot source regression')
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.root = Path(cls.folder.name)
        native = (ROOT / 'Overworld/lyra_native_loaders.asm').read_text()
        helpers = native[native.index('macro LyraHookshotSubtract('):
                         native.index('Lyra_CurrentNativeCodeEnd:')]
        source = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
        first = source.index('org $08FA49 ;')
        last = source.index('assert pc() <= $08FA81 ;', first)
        hook = source[first:source.index('\n', last)]
        seed = bytearray(0x400000)

        def put(at, data):
            pc = L.A.pc(at)
            seed[pc:pc+len(data)] = data

        # Native frame computes worldless0700; the hookshot caller saves X8/Y8.
        put(0x02A5B1, bytes.fromhex('c220a52029001e0a0a0a8d0007a52229001e0d0007eb8d0007'))
        put(0x08BDC5, bytes.fromhex('202dfa'))
        put(0x08FA2D, bytes.fromhex('da5abdfa0b8500bd0e0c8501bd040c8502bd180c8503a51bd040c220'))
        put(0x08FA81, bytes.fromhex('e2207afa1860'))
        for area, y, x in ((0x07, 0, 0x0E00), (0x20, 0x0600, 0),
                           (0x21, 0x0600, 0), (0x30, 0x0C00, 0),
                           (0x31, 0x0C00, 0), (0x3F, 0x0E00, 0x0E00)):
            for old, current, value in ((0x288F38, 0xE09200, y),
                                        (0x289078, 0xE09380, x)):
                put(old+area*2, value.to_bytes(2, 'little'))
                put(current+area*2, value.to_bytes(2, 'little'))
        for area, y, x in ((0xA0, 0x0800, 0), (0xA1, 0x0800, 0x0200),
                           (0xB0, 0x0C00, 0), (0xBF, 0x0E00, 0x0E00)):
            put(0xE09200+area*2, y.to_bytes(2, 'little'))
            put(0xE09380+area*2, x.to_bytes(2, 'little'))
        cls.images = {}
        for mode in (0, 1):
            image = cls.root / f'mode{mode}.sfc'
            image.write_bytes(seed)
            driver = cls.root / f'mode{mode}.asm'
            driver.write_text('lorom\n'+f'!LYRA_CURRENT_MODE = {mode}\n'+
                '!LYRA_CURRENT_TABLE_transition_y = $E09200\n'+
                '!LYRA_CURRENT_TABLE_transition_x = $E09380\n'+
                'Pool_OverworldTransitionPositionY_New = $288F38\n'+
                'Pool_OverworldTransitionPositionX_New = $289078\n'+
                'OWCameraBoundsS = $0716\nOWCameraBoundsE = $0718\n'+
                'if !LYRA_CURRENT_MODE == 1\norg $E0CCBF\n'+helpers+
                'Lyra_CurrentNativeCodeEnd = pc()\nassert pc() <= $E10000\nendif\n'+hook+'\n')
            proc = subprocess.run([asar, '--no-title-check', '--fix-checksum=off',
                                   '--symbols=wla', str(driver), str(image)],
                                  capture_output=True, text=True, timeout=20)
            if proc.returncode:
                raise AssertionError(proc.stdout+proc.stderr)
            cls.images[mode] = image
        cls.labels = L._labels(cls.images[1].with_suffix('.sym').read_bytes())

    def run_cpu(self, mode, entry, writes, *, a=0, x=0, p=0x10, steps=100):
        runner = os.environ.get('OOS_CPU_RUNNER')
        if not runner:
            self.skipTest('Set OOS_CPU_RUNNER for emitted hookshot ABI regression')
        req = dict(entry=entry, reset_ram=True,
                   registers=dict(a=a, x=x, y=0xD3, p=p, db=8, d=0, sp=0x1FFF),
                   writes=writes, reads=[dict(address=0x7E0700, length=2)],
                   trace_writes=True, max_steps=steps)
        proc = subprocess.run([runner, str(self.images[mode])], input=json.dumps(req)+'\n',
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertFalse(result.get('stub_calls'))
        self.assertFalse(result.get('mmio_writes'))
        return result

    @staticmethod
    def word(at, value):
        return dict(address=at, bytes=list(value.to_bytes(2, 'little')))

    def test_assembled_helper_matches_reviewed_bytes_and_fixed_site_extents(self):
        current = self.images[1].read_bytes()
        start = L.A.pc(self.labels['Lyra_HookshotSubtractY'])
        end = L.A.pc(self.labels['Lyra_CurrentNativeCodeEnd'])
        self.assertEqual(end-start, 98)
        # Independently reviewed emitted bytes; source changes need a new review.
        self.assertEqual(hashlib.sha256(current[start:end]).hexdigest(),
                         '70f47c04a91585be5e4d1ae3d884a66d03e2c97e294c21568a665ff624d171d8')
        old = self.images[0].read_bytes()
        for axis, at, legacy in (('Y', 0x08FA57, 0x288F38), ('X', 0x08FA6D, 0x289078)):
            pc = L.A.pc(at)
            self.assertEqual(old[pc:pc+4], b'\xFF'+legacy.to_bytes(3, 'little'))
            self.assertEqual(current[pc:pc+4], b'\x22'+
                             self.labels['Lyra_HookshotSubtract'+axis].to_bytes(3, 'little'))
            self.assertEqual(self.labels['LyraCall_HookshotDelta'+axis], at)
        self.assertEqual(self.labels['LyraHost_Hookshot_IsCollisionCheckFutile_Interupt_End'], 0x08FA81)
        pc = L.A.pc(0x08FA49)
        sites = set(range(0x08FA57-0x08FA49, 0x08FA5B-0x08FA49)) | \
                set(range(0x08FA6D-0x08FA49, 0x08FA71-0x08FA49))
        self.assertTrue(all(old[pc+i] == current[pc+i] for i in range(0x38) if i not in sites))

    def test_true_cell_and_page_preserve_carry_overflow_and_x8(self):
        frame = self.run_cpu(1, 0x02A5B1,
            [self.word(0x7E0020, 0x0933), self.word(0x7E0022, 0x0100)], p=0x30, steps=13)
        self.assertEqual(frame['reads'][0]['bytes'], [0x40, 0])
        self.assertEqual(frame['registers']['p'] & 0x10, 0x10)
        for area, cell, axis, base in ((0xA0, 0x40, 'Y', 0x0800),
                (0xA1, 0x42, 'X', 0x0200), (0xB0, 0x60, 'Y', 0x0C00),
                (0xBF, 0x7E, 'X', 0x0E00), (0x30, 0x62, 'Y', 0x0C00),
                (0x87, 0x0E, 'X', 0x0E00)):
            for a, carry, flags in ((base, 0, 0x10), (base, 1, 0xD2),
                                    (0x8000, 1, 0x10), (0xABCD, 0, 0xD2)):
                with self.subTest(area=area, axis=axis, a=a, carry=carry):
                    p = flags | carry
                    row = self.run_cpu(1, self.labels['Lyra_HookshotSubtract'+axis],
                        [self.word(0x7E008A, area), self.word(0x7E0700, cell)], a=a, x=cell, p=p)
                    self.assertTrue(row['returned'])
                    r = row['registers'];full = a-base-(1-carry);value = full & 65535
                    expected_p = (p & ~0xC3) | (0x80 if value & 0x8000 else 0) | \
                        (0x40 if (a ^ base) & (a ^ value) & 0x8000 else 0) | \
                        (2 if value == 0 else 0) | int(full >= 0)
                    self.assertEqual((r['a'], r['p'], r['x'], r['y'], r['sp'], r['db'], r['d']),
                                     (value, expected_p, cell, 0xD3, 0x1FFF, 8, 0))

    def test_actual_caller_keeps_native_controls_and_repairs_lyra_collision_decision(self):
        def prefix(mode, writes):
            for limit in range(1, 90):
                row = self.run_cpu(mode, 0x08BDC5, writes, x=7, p=0x30, steps=limit)
                r = row['registers']
                if r['pb'] << 16 | r['pc'] == 0x08BDC8:
                    return r
            self.fail('Hookshot native caller did not return to08BDC8')
        for area, cell, axis, head_y, head_x in ((0xA0, 0x40, 'Y', 0x0820, 0x20),
                (0xA1, 0x42, 'X', 0x0820, 0x0220),
                (0x30, 0x62, 'X', 0x0D73, 0x0300), (0x87, 0x0E, 'X', 0x0103, 0x0E90)):
            with self.subTest(area=area, axis=axis):
                writes = [self.word(0x7E008A, area), self.word(0x7E0700, cell),
                    self.word(0x7E0716, 0x011E), self.word(0x7E0718, 0x0300 if area == 0x30 else 0x0100),
                    self.word(0x7E0C79, 0 if axis == 'Y' else 2),
                    dict(address=0x7E0C01, bytes=[head_y & 255]),
                    dict(address=0x7E0C15, bytes=[head_y >> 8]),
                    dict(address=0x7E0C0B, bytes=[head_x & 255]),
                    dict(address=0x7E0C1F, bytes=[head_x >> 8])]
                old, current = prefix(0, writes), prefix(1, writes)
                self.assertEqual((current['x'], current['y'], current['sp'], current['p'] & 0x30),
                                 (7, 0xD3, 0x1FFC, 0x30))
                if area < 0xA0:
                    self.assertEqual(current, old)
                else:
                    self.assertEqual((old['p'] & 1, current['p'] & 1), (1, 0))


if __name__ == '__main__':
    unittest.main()
