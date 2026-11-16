"""Compiled prison sight: real collision planes, bounded ray, unchanged contact."""
import json
from fractions import Fraction
import subprocess
import unittest
from unittest import mock

import test_prison_cell65 as P
import test_special_overworld_semantic_kernel as T


@unittest.skipUnless(T.R.ASSEMBLER and T.RUNNER, 'Asar and OOS_65816_RUNNER required')
class PrisonPatrolCoverTest(unittest.TestCase):
    def build(self, legacy=False):
        if not legacy:
            return P.PrisonCell65Test.inventory_artifact(self)
        # Restore the original range-only decision; the new helper is uncalled.
        # No checkout source is changed to run this fail-old control.
        patrol = (T.R.ROOT/'Dungeons/d3_prison_patrol.asm').read_text()
        new = 'CMP.w #$0041 : BCS .no\n  JSR D3Prison_PatrolSightClear : BCS .yes'
        self.assertEqual(patrol.count(new), 1)
        patrol = patrol.replace(new, 'CMP.w #$0041 : BCC .yes')
        sequence = (T.R.ROOT/'Dungeons/prison_sequence.asm').read_text()
        sequence = sequence.replace('incsrc "Dungeons/d3_prison_patrol.asm"', patrol)
        artifact = T.Artifact

        def old_artifact(*args, **kwargs):
            include = f'incsrc "{T.R.ROOT / "Dungeons/prison_sequence.asm"}"'
            self.assertEqual(kwargs['extra_source'].count(include), 1)
            kwargs['extra_source'] = kwargs['extra_source'].replace(include, sequence)
            return artifact(*args, **kwargs)

        with mock.patch.object(T, 'Artifact', side_effect=old_artifact):
            return P.PrisonCell65Test.inventory_artifact(self)

    @staticmethod
    def ram(gx=384, gy=128, lx=432, ly=128, floor=0, left=False, lower=False):
        ram = bytearray(65536)
        ram[:0x20] = bytes((i*17+3)&255 for i in range(0x20))
        ram[0x10] = 7
        ram[0x11] = 0
        ram[0x1B] = 1
        ram[0x40C] = 0x10
        ram[0xA0] = 0x64
        ram[0xF306] = 0x21
        slot = 3
        ram[0xDD0+slot] = 9
        ram[0xE20+slot] = 0x41
        ram[0xE30+slot] = 0xE4 if lower else 0xE3
        ram[0xDE0+slot] = int(left)
        ram[0xD10+slot], ram[0xD30+slot] = gx&255, 8+(gx>>8)
        ram[0xD00+slot], ram[0xD20+slot] = gy&255, 12+(gy>>8)
        ram[0xF20+slot] = ram[0xEE] = floor
        T.word(ram, 0x22, 0x800+lx)
        T.word(ram, 0x20, 0xC00+ly)
        return ram

    @staticmethod
    def plane(cells=(), attr=1, floor=0):
        data = bytearray(8192)
        for col, row in cells:
            data[floor*4096+row*64+col] = attr
        return data

    def visible(self, art, ram, plane, expected):
        registers = dict(a=0xA55A, x=3, y=6, p=0xF4, db=0x52, d=0, sp=0x1FFF)
        request = dict(entry=art.labels['D3Prison_PatrolCanSee'], reset_ram=True,
                       registers=registers,
                       writes=[dict(address=0x7E0000, bytes=list(ram)),
                               dict(address=0x7F2000, bytes=list(plane))],
                       reads=[dict(address=0x7E0000, length=65536),
                              dict(address=0x7F2000, length=8192)],
                       trace_writes=True, max_steps=7000)
        proc = subprocess.run([T.RUNNER, str(art.dir/'probe.sfc')],
                              input=json.dumps(request)+'\n', capture_output=True,
                              text=True, timeout=10, check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result.get('returned'), result)
        actual = result['registers']
        self.assertEqual(actual['p']&1, expected, f"steps={result['steps']}")
        for key in ('x', 'y', 'db', 'd', 'sp'):
            self.assertEqual(actual[key], registers[key], key)
        self.assertEqual(actual['p']&0xFE, registers['p']&0xFE)
        out = bytes(result['reads'][0]['bytes'])
        self.assertEqual(out[:0x1F80], ram[:0x1F80])
        self.assertEqual(out[0x2000:], ram[0x2000:])
        self.assertEqual(bytes(result['reads'][1]['bytes']), plane)
        # Restoring module/NMI bytes afterwards would still be unsafe. Check
        # every executed write, not only the final RAM image.
        for write in result['writes']:
            address = write['address'] & 0xFFFF
            self.assertTrue(address < 0x10 or 0x1F80 <= address <= 0x1FFF,
                            f'non-scratch transient write: {write}')
        T.CASES.append(dict(entry='prison-cover', steps=result['steps'], expected=expected,
                            routine_cpu_cycles=result['timing']['routine_cpu_cycles']))
        return result

    def test_fail_old_and_live_cover_removed(self):
        art = self.build()
        old = self.build(legacy=True)
        cover = self.plane([(51, 17), (52, 17)])
        ram = self.ram()
        self.visible(old, ram, cover, 1)  # Old guard sees directly through cover.
        self.visible(art, ram, cover, 0)
        self.visible(art, ram, self.plane(), 1)  # Live attr removal opens sight.
        size = art.labels['Prison_SequenceCodeEnd']-art.labels['Prison_SequenceCodeBegin']
        self.assertLessEqual(size, 0x2000)

    def test_both_full_solid_types_and_floor_selection(self):
        art = self.build()
        for floor in (0, 1):
            for attr in (1, 2):
                with self.subTest(floor=floor, attr=attr):
                    self.visible(art, self.ram(floor=floor),
                                 self.plane([(51, 17)], attr, floor), 0)
                    self.visible(art, self.ram(floor=floor),
                                 self.plane([(51, 17)], attr, 1-floor), 1)
        ram = self.ram()
        ram[0xEE] = 1
        self.visible(art, ram, self.plane(), 0)

    def test_non_opaque_attributes_and_off_ray_cells(self):
        art = self.build()
        for attr in (0, 3, 8, 0x10, 0x20, 0x28, 0x30, 0x40, 0x70, 0x80, 0xFF):
            with self.subTest(attr=attr):
                self.visible(art, self.ram(), self.plane([(51, 17)], attr), 1)
        self.visible(art, self.ram(), self.plane([(51, 16), (51, 18)]), 1)

    def test_lower_left_endpoint_and_subtile_ray(self):
        art = self.build()
        # Guard x128/y376 faces left; feet at136/388, Link at88/388.
        self.visible(art, self.ram(gx=128, gy=376, lx=80, ly=376, left=True, lower=True),
                     self.plane([(13, 48), (14, 48)]), 0)
        self.visible(art, self.ram(gx=128, gy=376, lx=80, ly=376, left=True, lower=True),
                     self.plane([(13, 47)]), 1)
        # Unaligned feet start397/140, end445/152. Middle is at421/146.
        self.visible(art, self.ram(gx=389, lx=437, ly=140), self.plane([(52, 18)]), 0)
        self.visible(art, self.ram(gx=389, lx=437, ly=140), self.plane([(52, 17)]), 1)
        # Descending ray crosses the other side of the same Tile8 boundary.
        self.visible(art, self.ram(gx=389, gy=140, lx=437, ly=128),
                     self.plane([(52, 18)]), 0)
        # Exact ray touches x392/y144. Both diagonal side cells block.
        for cell in ((49, 17), (48, 18)):
            self.visible(art, self.ram(gx=382, gy=131, lx=398, ly=139),
                         self.plane([cell]), 0)
        # Negative fractional Y immediately enters row17 below y144.
        self.visible(art, self.ram(gx=382, gy=132, lx=398, ly=131),
                     self.plane([(49, 17)]), 0)

    def test_real_endpoint_wait_sites(self):
        art = self.build()
        upper = self.ram(gx=383, lx=440)
        lower = self.ram(gx=129, gy=376, lx=72, ly=376, left=True, lower=True)
        for ram, cells in ((upper, [(52, 17), (53, 17), (52, 18), (53, 18)]),
                           (lower, [(12, 48), (13, 48), (12, 49), (13, 49)])):
            self.visible(art, ram, self.plane(cells), 0)
            self.visible(art, ram, self.plane(), 1)
        # At the exact endpoints Step has already reversed the guard.
        self.visible(art, self.ram(gx=384, lx=440, left=True), self.plane(), 0)
        self.visible(art, self.ram(gx=128, gy=376, lx=72, ly=376, lower=True),
                     self.plane(), 0)

    def test_independent_segment_cell_intersections(self):
        art = self.build()

        def intersects(start, delta, col, row):
            # Exact rational slab clipping, independent of grid stepping.
            low, high = Fraction(0), Fraction(1)
            for origin, change, tile in zip(start, delta, (col, row)):
                a = Fraction(tile*8-origin, change)
                b = Fraction((tile+1)*8-origin, change)
                low, high = max(low, min(a, b)), min(high, max(a, b))
            return low <= high

        for dx, dy in ((64, 12), (64, -12), (-64, 12), (-17, -5)):
            start = (309, 140)
            end = (start[0]+dx, start[1]+dy)
            ram = self.ram(gx=301, lx=301+dx, ly=128+dy, left=dx < 0)
            for col in range(min(start[0], end[0])//8-1, max(start[0], end[0])//8+2):
                for row in range(min(start[1], end[1])//8-1, max(start[1], end[1])//8+2):
                    with self.subTest(dx=dx, dy=dy, col=col, row=row):
                        self.visible(art, ram, self.plane([(col, row)]),
                                     int(not intersects(start, (dx, dy), col, row)))

    def test_existing_range_contact_and_context_boundaries(self):
        art = self.build()
        for distance, seen in ((12, 1), (13, 1), (64, 1), (65, 0), (-12, 1), (-13, 0)):
            with self.subTest(distance=distance):
                self.visible(art, self.ram(gx=300, lx=300+distance), self.plane(), seen)
        for dy, seen in ((-13, 0), (-12, 1), (12, 1), (13, 0)):
            with self.subTest(dy=dy):
                self.visible(art, self.ram(ly=128+dy), self.plane(), seen)
        # Contact remains contact, including behind a guard; no new immunity.
        self.visible(art, self.ram(gx=300, lx=288), bytes([1])*8192, 1)
        for gx, lx, seen in ((48, 64, 1), (47, 64, 0), (448, 463, 1), (448, 464, 0)):
            with self.subTest(gx=gx, lx=lx):
                self.visible(art, self.ram(gx=gx, lx=lx), self.plane(), seen)
        for address, value in ((0x11, 1), (0x2E4, 1), (0xFFC, 1), (0xFC1, 1),
                               (0xA0, 0x54), (0xE33, 0), (0xF306, 0x29), (0xF359, 2)):
            ram = self.ram()
            ram[address] = value
            with self.subTest(address=address):
                self.visible(art, ram, self.plane(), 0)
        ram = self.ram()
        ram[0x2B2] = 5  # Minish/mask does not become a stealth exception.
        self.visible(art, ram, self.plane(), 1)


if __name__ == '__main__':
    unittest.main()
