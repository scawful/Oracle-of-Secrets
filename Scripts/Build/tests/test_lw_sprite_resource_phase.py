"""Execute the assembled LW phase wrapper and real CheckIfNight guards.

This bounded instruction model checks the hook ABI and selector, not PPU or
actor reload timing. Native day/night entry remains a separate verification.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
ASAR = shutil.which('asar')


def routine(text, name):
    return text.split(name + ':\n{', 1)[1].split('\n}', 1)[0]


def assemble(directory, cap, guard, *, old=False):
    source = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
    body = routine(source, 'Sprite_LoadGfxProperties_Interupt')
    # The special palette cache loop is deliberately outside the changed block.
    body = body.split('    DEX : DEX : BPL .loop', 1)[1]
    if old:
        body = 'LDY.w #$003E\nLDA.l $7EF3C5\nRTL\n'
    clock = (ROOT / 'Overworld/time_system.asm').read_text()
    text = f'''lorom
!ENABLE_D7_FARORE_RESCUE_SEQUENCE = {cap}
!ENABLE_PART00_NIGHT_FIX = {guard}
!GameState_FaroreRescued = $03
!GameState_KydrogComplete = $02
GameState = $7EF3C5
KydrogFaroreRemoved = $7EF300
Crystals = $7EF37A
struct TimeState $7EE000
 .Hours: skip 1
endstruct
org $288000
Probe:
{{
{body}
}}
org $348000
Oracle_CheckIfNight:
{{
{routine(clock, 'CheckIfNight')}
}}
LoadPeacetimeSprites:
{{
{routine(clock, 'LoadPeacetimeSprites')}
}}
'''
    asm, rom = directory / 'probe.asm', directory / 'probe.sfc'
    asm.write_text(text)
    rom.write_bytes(bytes(0x200000))
    result = subprocess.run([ASAR, '--no-title-check', '--fix-checksum=off',
                             str(asm), str(rom)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return rom.read_bytes()


class Machine:
    """Fail-closed subset for these assembled routines; byte-accurate stack."""

    def __init__(self, rom, *, state, hour, area=2, crystals=0, removed=1):
        self.rom = rom
        self.mem = {0x7EF3C5: state, 0x7EE000: hour, 0x7E008A: area,
                    0x7EF37A: crystals, 0x7EF300: removed}
        self.pc, self.a, self.x, self.y = 0x288000, 0xABCD, 0xBEEF, 0xCAFE
        self.p, self.d, self.db = 0x45, 0x1234, 0x80
        self.stack = [0x5A, 0xC3]  # Caller bytes below the inherited JSL frame.
        self.push(0x12, 1)
        self.push(0x3456, 2)
        self.helper_entry = None

    def read(self, addr):
        bank, low = addr >> 16, addr & 0xFFFF
        if bank in (0, 0x80) and low < 0x2000:
            addr = 0x7E0000 | low
        if addr in self.mem:
            return self.mem[addr]
        if low >= 0x8000 and bank not in (0x7E, 0x7F):
            return self.rom[(bank & 0x7F) * 0x8000 + (low & 0x7FFF)]
        return 0

    def fetch(self, size=1):
        value = sum(self.read(self.pc + i) << (8 * i) for i in range(size))
        self.pc += size
        return value

    def push(self, value, size):
        self.stack.extend((value >> (8 * i)) & 255 for i in reversed(range(size)))

    def pull(self, size):
        return sum(self.stack.pop() << (8 * i) for i in range(size))

    def set_p(self, value):
        self.p = value
        if value & 0x10:
            self.x &= 255
            self.y &= 255

    def nz(self, value, size):
        mask = (1 << (8 * size)) - 1
        self.p = (self.p & ~0x82) | (2 if not value & mask else 0)
        if value & (1 << (8 * size - 1)):
            self.p |= 0x80

    def load_a(self, value, size):
        self.a = value if size == 2 else (self.a & 0xFF00) | (value & 255)
        self.nz(value, size)

    def run(self):
        for _ in range(200):
            if self.pc == 0x348000:
                self.helper_entry = (self.p & 0x30, self.d)
            op = self.fetch()
            m, x = (1 if self.p & 0x20 else 2), (1 if self.p & 0x10 else 2)
            if op in (0x08, 0x8B, 0x0B, 0xDA, 0x5A):
                value, size = {0x08: (self.p, 1), 0x8B: (self.db, 1),
                               0x0B: (self.d, 2), 0xDA: (self.x, x),
                               0x5A: (self.y, x)}[op]
                self.push(value, size)
            elif op == 0xF4:
                self.push(self.fetch(2), 2)
            elif op in (0x28, 0xAB, 0x2B, 0xFA, 0x7A):
                size = 1 if op in (0x28, 0xAB) else (2 if op == 0x2B else x)
                value = self.pull(size)
                if op == 0x28:
                    self.set_p(value)
                else:
                    setattr(self, {0xAB: 'db', 0x2B: 'd', 0xFA: 'x', 0x7A: 'y'}[op], value)
                    self.nz(value, size)
            elif op in (0xE2, 0xC2):
                value = self.fetch()
                self.set_p(self.p | value if op == 0xE2 else self.p & ~value)
            elif op == 0x22:
                target = self.fetch(3)
                self.push(self.pc >> 16, 1)
                self.push((self.pc - 1) & 0xFFFF, 2)
                self.pc = target
            elif op == 0x20:
                target = self.fetch(2)
                self.push((self.pc - 1) & 0xFFFF, 2)
                self.pc = (self.pc & 0xFF0000) | target
            elif op in (0x60, 0x6B):
                target = (self.pull(2) + 1) & 0xFFFF
                bank = self.pull(1) if op == 0x6B else self.pc >> 16
                self.pc = bank << 16 | target
                if self.pc == 0x123457:
                    return self
            elif op in (0xAF, 0xAD, 0xA5):
                size = {0xAF: 3, 0xAD: 2, 0xA5: 1}[op]
                addr = self.fetch(size)
                if size == 2:
                    addr |= self.db << 16
                elif size == 1:
                    addr = (addr + self.d) & 0xFFFF
                self.load_a(sum(self.read(addr + i) << (8 * i) for i in range(m)), m)
            elif op == 0xA9:
                self.load_a(self.fetch(m), m)
            elif op == 0xA0:
                self.y = self.fetch(x)
                self.nz(self.y, x)
            elif op == 0x29:
                self.load_a(self.a & self.fetch(m), m)
            elif op == 0xC9:
                value = self.fetch(m)
                a = self.a & ((1 << (8 * m)) - 1)
                self.p = (self.p & ~1) | int(a >= value)
                self.nz(a - value, m)
            elif op in (0x90, 0xB0, 0xF0, 0xD0):
                delta = self.fetch()
                take = {0x90: not self.p & 1, 0xB0: self.p & 1,
                        0xF0: self.p & 2, 0xD0: not self.p & 2}[op]
                if take:
                    self.pc += delta if delta < 128 else delta - 256
            elif op == 0x4C:
                self.pc = (self.pc & 0xFF0000) | self.fetch(2)
            elif op in (0x18, 0x38):
                self.p = (self.p & ~1) | int(op == 0x38)
            else:
                raise AssertionError(f'Unsupported opcode {op:02X} at {self.pc - 1:06X}')
        raise AssertionError('Execution exceeded bounded routine size')


@unittest.skipUnless(ASAR, 'Asar required for actual source execution')
class LightWorldSpriteResourcePhaseTest(unittest.TestCase):
    def test_actual_selector_guards_and_abi_in_both_cap_modes(self):
        for cap in (0, 1):
            for guard in (0, 1):
                with tempfile.TemporaryDirectory() as directory:
                    rom = assemble(Path(directory), cap, guard)
                # Independent expected phase cases, including peacetime first.
                cases = [({'state': 0, 'hour': 23}, 0),
                         ({'state': 1, 'hour': 23}, 1),
                         ({'state': 2, 'hour': 6}, 2),
                         ({'state': 2, 'hour': 17}, 2),
                         ({'state': 2, 'hour': 18}, 3),
                         ({'state': 2, 'hour': 5}, 3),
                         ({'state': 2, 'hour': 23, 'removed': 0}, 2 if guard else 3),
                         ({'state': 3, 'hour': 12}, 2 if cap else 3),
                         ({'state': 3, 'hour': 23}, 3),
                         ({'state': 2, 'hour': 23, 'area': 0x2E, 'crystals': 0x10}, 1),
                         ({'state': 2, 'hour': 23, 'area': 0x2F, 'crystals': 0x10}, 1),
                         ({'state': 2, 'hour': 23, 'area': 0x1E, 'crystals': 0x20}, 1)]
                for values, phase in cases:
                    with self.subTest(cap=cap, guard=guard, **values):
                        cpu = Machine(rom, **values)
                        before = dict(cpu.mem)
                        cpu.run()
                        self.assertEqual(cpu.a, 4 if cap and phase == 3 else phase)
                        self.assertEqual((cpu.x, cpu.y, cpu.d, cpu.db),
                                         (0xBEEF, 0x003E, 0x1234, 0x80))
                        self.assertEqual(cpu.p, 0x45)  # M/X/C/V restored, LDY N/Z clear.
                        self.assertEqual(cpu.helper_entry, (0x30, 0))
                        self.assertEqual(cpu.stack, [0x5A, 0xC3])
                        self.assertEqual(cpu.mem, before)

    def test_original_hook_selects_day_row_for_night_control(self):
        with tempfile.TemporaryDirectory() as directory:
            old = assemble(Path(directory), 1, 1, old=True)
        cpu = Machine(old, state=2, hour=23).run()
        self.assertEqual(cpu.a, 2)
        self.assertNotEqual(cpu.a, 4)  # Native cap-enabled comparison needs4.


if __name__ == '__main__':
    unittest.main()
