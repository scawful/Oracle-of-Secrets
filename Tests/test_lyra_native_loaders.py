"""ROM-free CPU contracts and fail-closed ordinary-reader binding checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import lyra_native_loaders as L
import lyra_project_admission as A


class CPU:
    """Small independent executor for the emitted helper instruction subset."""
    def __init__(self, code, *, a=0xABCD, x=0, y=0, p=0x41, db=0x28, d=0):
        self.code, self.pc = code, 0
        self.a, self.x, self.y, self.p, self.db, self.d = a, x, y, p, db, d
        self.stack, self.mem, self.writes = [], {}, []

    @staticmethod
    def physical(at):
        if at >> 16 & 0x7F < 0x40 and at & 0xFFFF < 0x2000:
            return 0x7E0000 | (at & 0xFFFF)
        return at

    def put(self, at, raw):
        for i, b in enumerate(raw):
            self.mem[self.physical(at + i)] = b

    def read(self, at, width):
        return sum(self.mem.get(self.physical(at + i), 0) << (8 * i) for i in range(width))

    def take(self, n=1):
        value = int.from_bytes(self.code[self.pc:self.pc + n], 'little')
        self.pc += n
        return value

    def nz(self, value, width):
        mask = (1 << (width * 8)) - 1
        self.p = (self.p & ~0x82) | (2 if value & mask == 0 else 0) | (0x80 if value & (mask + 1 >> 1) else 0)

    def load(self, value):
        width = 1 if self.p & 0x20 else 2
        self.a = (self.a & 0xFF00 | value & 255) if width == 1 else value
        self.nz(value, width)

    def run(self):
        for _ in range(100):
            op = self.take()
            width = 1 if self.p & 0x20 else 2
            iw = 1 if self.p & 0x10 else 2
            if op == 0x08:
                self.stack.append(self.p)
            elif op == 0xC2:
                self.p &= ~self.take()
            elif op == 0xE2:
                self.p |= self.take()
                if self.p & 0x10:
                    self.x &= 255
                    self.y &= 255
            elif op == 0x48:
                self.stack.extend(self.a.to_bytes(2, 'little')[:width][::-1])
            elif op == 0x68:
                self.load(sum(self.stack.pop() << (8 * i) for i in range(width)))
            elif op == 0x28:
                self.p = self.stack.pop()
                if self.p & 0x10:
                    self.x &= 255
                    self.y &= 255
            elif op in (0x8A, 0x98):
                self.load(self.x if op == 0x8A else self.y)
            elif op == 0x29:
                self.load(self.a & self.take(width))
            elif op in (0xC9, 0xC0):
                value = self.take(width if op == 0xC9 else iw)
                original = self.a if op == 0xC9 else self.y
                mask = (1 << (8 * (width if op == 0xC9 else iw))) - 1
                self.p = self.p & ~1 | int(original & mask >= value)
                self.nz((original - value) & mask, width if op == 0xC9 else iw)
            elif op in (0xD0, 0xF0):
                offset = self.take()
                if (not self.p & 2) == (op == 0xD0):
                    self.pc += offset if offset < 128 else offset - 256
            elif op in (0xAF, 0xBF, 0xB9, 0xAD, 0xA5):
                if op in (0xAF, 0xBF):
                    at = self.take(3) + (self.x if op == 0xBF else 0)
                elif op in (0xB9, 0xAD):
                    at = self.db << 16 | self.take(2)
                    at += self.y if op == 0xB9 else 0
                else:
                    at = self.d + self.take()
                self.load(self.read(at, width))
            elif op in (0x85, 0x8F):
                at = self.d + self.take() if op == 0x85 else self.take(3)
                raw = self.a.to_bytes(2, 'little')[:width]
                self.put(at, raw)
                self.writes.extend(self.physical(at + i) for i in range(width))
            elif op == 0xAB:
                self.db = self.stack.pop()
                self.nz(self.db, 1)
            elif op in (0x6B, 0x5C):
                return None if op == 0x6B else self.take(3)
            else:
                raise AssertionError(f'Unexpected helper opcode {op:02X} at{self.pc - 1}')
        raise AssertionError('Unbounded helper')


def compiled_fixture():
    """Synthetic code-contract fixture, never a qualified compiled image."""
    compiled, labels, cursor = bytearray(0x400000), {}, L.CODE_START
    bodies = [('Lyra_Read' + row[0], L.selector_bytes(row)) for row in L.SELECTORS]
    bodies += [(name, L._pointer_body('map32_high' if 'High' in name else 'map32_low', original))
               for _, name, original in L.POINTER_HOOKS]
    bodies += [('Lyra_SpritePointer', L.sprite_pointer_bytes()),
               ('Lyra_InitMusicTail', L.music_tail_bytes()), ('Lyra_ReadBackdrop', L.backdrop_bytes())]
    for name, raw in bodies:
        labels[name], labels[name + '_End'] = A.snes(cursor), A.snes(cursor + len(raw))
        compiled[cursor:cursor + len(raw)] = raw
        cursor += len(raw)
    labels['Lyra_NativeCodeStart'], labels['Lyra_NativeCodeEnd'] = A.snes(L.CODE_START), A.snes(cursor)
    def put(at, raw):
        at = A.pc(at)
        compiled[at:at + len(raw)] = raw
    def hook(at, target, opcode=0x22, padding=0):
        put(at, bytes([opcode]) + labels[target].to_bytes(3, 'little') + b'\xea' * padding)
    for i, (label, target) in enumerate(L.SOURCE_CALLS):
        labels[label] = L.FIXED_SOURCE_CALLS.get(label, A.snes(0x100000 + i * 4))
        hook(labels[label], target)
    for site in L.FIXED_SIZE_SITES:
        hook(site, 'Lyra_ReadSize')
    for site in L.FIXED_SPRITE_PALETTE_SITES:
        hook(site, 'Lyra_ReadSpritePalette')
    hook(0x1BC8B8, 'Lyra_ReadHiddenItems')
    hook(0x02C4BC, 'Lyra_InitMusicTail', 0x5C)
    hook(0x3483AA, 'Lyra_ReadBackdrop', 0x5C, 1)
    compiled[0x1A03AF:0x1A03D5] = L.BACKDROP_CONTINUATION
    labels['Lyra_RoutingGate'], labels['Lyra_RoutingReturn'] = 0x02A5DB, 0x02A5FB
    put(0x02A5DB, bytes.fromhex('a58ac9a1f01a'))
    put(0x02A5FB, bytes.fromhex('e22060'))
    labels['Lyra_Fixture_PreProfile'] = 0x02E58B
    put(0x02E58B, bytes.fromhex('a9f8ff85ece2308b4bab'))
    labels['Lyra_Fixture_PreOverlaySelect'] = 0x02B058
    put(0x02B058, bytes.fromhex('e0ff00d003'))
    labels['Lyra_Fixture_OverlayRestored'] = 0x02B0CF
    compiled[A.pc(0x02B0CF) - len(L.OVERLAY_RESTORE):A.pc(0x02B0CF)] = L.OVERLAY_RESTORE
    put(0x02B0CF, bytes.fromhex('e22060'))
    for i, name in enumerate(L.SOURCE_HOSTS):
        labels['LyraHost_' + name] = A.snes(0x110000 + i * 16)
        labels['LyraHost_' + name + '_End'] = A.snes(0x110004 + i * 16)
    symbols = '[labels]\n' + '\n'.join(f'{a >> 16:02X}:{a & 0xFFFF:04X} {n}' for n, a in labels.items()) + '\n'
    return bytes(compiled), labels, symbols


class NativeHelperTests(unittest.TestCase):
    def test_all_selectors_preserve_widths_hidden_b_flags_and_legacy_reads(self):
        for row in L.SELECTORS:
            name, _, old, reg, mask, selected_index, indexed = row
            for m in (0, 0x20):
                for ix in (0, 0x10):
                    for cv in (0, 1, 0x40, 0x41):
                        for index in (selected_index, 0x99, 0xA0, 0xA2, 0xBF):
                            if indexed:
                                index = selected_index + 5 if index == selected_index else index * 8
                            if ix:
                                index &= 255
                            kwargs = dict(x=index if reg == 'X' else 0x56, y=index if reg == 'Y' else 0x78, p=m | ix | cv)
                            cpu = CPU(L.selector_bytes(row), **kwargs)
                            legacy = old + index if reg == 'X' else (old & 0xFFFF) + index | 0x280000
                            target = L.selected_address(row) + (index if indexed else 0)
                            cpu.put(legacy, b'\x91\xc6')
                            cpu.put(target, b'\x3c\x57')
                            selected = index & mask == selected_index
                            expected = CPU(b'', **kwargs)
                            expected.load(0x573C if selected else 0xC691)
                            before = (cpu.x, cpu.y, cpu.db, cpu.d)
                            cpu.run()
                            self.assertEqual((cpu.a, cpu.p), (expected.a, expected.p), (name, m, ix, cv, index))
                            self.assertEqual((cpu.x, cpu.y, cpu.db, cpu.d), before)
                            self.assertEqual(cpu.stack, [])
                            self.assertEqual(cpu.writes, [])

    def test_pointer_helpers_use_isolated_row_and_preserve_real_load_outputs(self):
        for _, name, original in L.POINTER_HOOKS:
            table = 'map32_high' if 'High' in name else 'map32_low'
            for area in (0xA1, 0x23A1, 0x37, 0x99, 0xA0, 0xA2, 0xBF):
                cpu = CPU(L._pointer_body(table, original), x=0x1FE, y=0xBEEF, p=0x41, d=0x100, db=9)
                cpu.put(cpu.d + 0x8A, area.to_bytes(2, 'little'))
                cpu.put(original + cpu.x, b'\x11\x22\x83')
                cpu.put(L.table_address(table) + 0x1E3, b'\x44\x55\xfa')
                cpu.run()
                selected = area & 255 == 0xA1
                self.assertEqual(cpu.read(cpu.d + 0xC8, 3), 0xFA5544 if selected else 0x832211)
                self.assertEqual(cpu.a, 0xFA55 if selected else 0x8322)
                self.assertEqual((cpu.x, cpu.y, cpu.db, cpu.d, cpu.p & 0x71), (0x1FE, 0xBEEF, 9, 0x100, 0x41))
                self.assertEqual(cpu.stack, [])
                self.assertEqual(set(cpu.writes), {0x7E01C8, 0x7E01C9, 0x7E01CA})

    def test_sprite_phase_stride_selects_each_actual_table(self):
        for area in (0xA1, 0x99, 0xA2):
            for phase in (0, 2, 4, 6):
                cpu = CPU(L.sprite_pointer_bytes(), x=0x282, y=phase, p=0x41, db=9)
                cpu.put(0x040A, area.to_bytes(2, 'little'))
                cpu.put(0x289438 + 0x282, b'\x22\xc8')
                for i, name in enumerate(('sprite_phase0', 'sprite_phase1', 'sprite_phase2')):
                    cpu.put(L.table_address(name) + 0x142, bytes([0x80 + i, 0xC8]))
                cpu.run()
                expected = (0xC880 + (1 if phase == 4 else 2 if phase == 6 else 0)) if area == 0xA1 else 0xC822
                self.assertEqual(cpu.a, expected)
                self.assertEqual((cpu.x, cpu.y, cpu.db, cpu.p & 0x71), (0x282, phase, 9, 0x41))
                self.assertEqual(cpu.stack, [])

    def test_backdrop_only_a1_and_legacy_continuation(self):
        for area in (0xA1, 0x21A1, 0x80, 0x99, 0xA0, 0xA2, 0xBF):
            cpu = CPU(L.backdrop_bytes(), x=0x65, y=0xCAFE, p=0x41)
            cpu.put(0x8A, area.to_bytes(2, 'little'))
            cpu.put(L.table_address('bg_color') + 0x142, b'\x34\x12')
            continuation = cpu.run()
            self.assertEqual(continuation, None if area & 255 == 0xA1 else 0x3483AF)
            self.assertEqual(cpu.a, 0x1234 if area & 255 == 0xA1 else area & 255)
            self.assertEqual((cpu.x, cpu.y, cpu.p & 0x71), (0x65, 0xCAFE, 0x41))
            self.assertEqual(cpu.stack, [])

    def test_music_tail_consumes_only_inherited_db_and_one_cache_byte(self):
        cpu = CPU(L.music_tail_bytes(), x=0x1234, y=0x5678, p=0x21, db=2)
        cpu.stack = [0x7E]
        cpu.put(L.table_address('music_dark_special') + 0x61, b'\0')
        cpu.run()
        self.assertEqual(cpu.writes, [0x7EC9A1])
        self.assertEqual((cpu.db, cpu.p & 0x30, cpu.x, cpu.y), (0x7E, 0x30, 0x34, 0x78))
        self.assertEqual(cpu.stack, [])

    def test_descriptor_refuses_policy_fixture_or_unsupported_selector(self):
        raw = bytearray(b'LYR1' + bytes([1, 0xA1, 0, 0xA1] + [0xA1] * 4)
            + bytes([58, 59, 60, 61, 71, 96, 62, 91, 0, 1, 91, 0x30, 0x30, 0, 0, 0, 0x10, 7, 0, 0]) + bytes(32))
        self.assertEqual(L.descriptor_fields(bytes(raw))['graphics_sheets'][5], 96)
        for index, value in ((5, 0xB0), (8, 0xA2), (25, 255), (28, 32), (30, 1), (31, 1), (40, 1), (12, 255)):
            other = bytearray(raw)
            other[index] = value
            with self.assertRaises(ValueError):
                L.descriptor_fields(bytes(other))

    def test_bridge_aliases_allow_identical_and_reject_conflicting_addresses(self):
        symbols = '[labels]\nF8:C000 Lyra_ReadParent\nF8:C000 Oracle_Lyra_ReadParent\n'
        self.assertEqual(L._labels(symbols)['Lyra_ReadParent'], 0xF8C000)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            L._labels(symbols.replace('F8:C000 Oracle_', 'F8:C001 Oracle_'))

    def test_review_pending_is_fail_closed_and_never_uses_wla_as_authority(self):
        with mock.patch.object(L, 'REVIEWED_COMPILED_BINDING', None):
            with self.assertRaisesRegex(ValueError, 'independent first-assembly'):
                L._verify_reviewed_binding(bytes(0x400000), '[labels]\n')

    def test_populated_binding_refuses_each_missing_mandatory_inspection_symbol(self):
        compiled, _, symbols = compiled_fixture()
        baseline = L.inspect_unverified_native_loaders(compiled, symbols)
        required = {label for label, _ in L.SOURCE_CALLS}
        required.update('LyraHost_' + host + suffix for host in L.SOURCE_HOSTS for suffix in ('', '_End'))
        required.update(('Lyra_RoutingGate', 'Lyra_RoutingReturn'))
        with mock.patch.object(L, 'REVIEWED_COMPILED_BINDING', baseline):
            L._verify_reviewed_binding(compiled, symbols)
            for label in sorted(required):
                with self.subTest(label=label):
                    incomplete = '\n'.join(line for line in symbols.splitlines()
                                           if not line.endswith(' ' + label)) + '\n'
                    with self.assertRaisesRegex(ValueError, 'Missing mandatory native loader inspection symbols: ' + label):
                        L._verify_reviewed_binding(compiled, incomplete)

    def test_exact_bodies_refuse_early_return_operand_mutation_and_foreign_relocation(self):
        compiled, labels, _ = compiled_fixture()
        row = L.SELECTORS[0]
        name, expected = 'Lyra_ReadAnimated', L.selector_bytes(row)
        L._body(compiled, labels, name, expected)
        at = A.pc(labels[name])
        for offset in (0, 15):
            altered = bytearray(compiled)
            altered[at + offset] ^= 0xFF
            with self.assertRaisesRegex(ValueError, 'body differs'):
                L._body(bytes(altered), labels, name, expected)
        other = dict(labels, **{name: 0x7DF000, name + '_End': 0x7DF000 + len(expected)})
        with self.assertRaisesRegex(ValueError, 'body differs'):
            L._body(compiled, other, name, expected)

    def test_compiled_dependency_gate_restore_and_call_mutants_refused(self):
        compiled, labels, _ = compiled_fixture()
        receipt = L._verify_dependencies(b'', compiled, labels)
        self.assertEqual(receipt['routing_gate_pc'], A.pc(labels['Lyra_RoutingGate']))
        sites = (A.pc(labels['Lyra_RoutingGate']) + 4,
                 A.pc(labels['Lyra_Fixture_OverlayRestored']) - 1,
                 A.pc(labels['LyraCall_Gfx0_2']), 0x1A03AF)
        for at in sites:
            altered = bytearray(compiled)
            altered[at] ^= 0xFF
            with self.assertRaises(ValueError):
                L._verify_dependencies(b'', bytes(altered), labels)

    def test_candidate_inspection_cannot_be_promoted_to_verified_receipt(self):
        compiled, _, symbols = compiled_fixture()
        receipt = L.inspect_unverified_native_loaders(compiled, symbols)
        self.assertIs(receipt['qualified'], False)
        self.assertNotIn('compiled_consumers_verified', receipt)
        self.assertEqual(len(receipt['source_calls']), 74)
        self.assertEqual(len(receipt['consumer_spans']), 33)

    def test_reviewed_binding_refuses_routing_prefix_and_music_producer_mutations(self):
        compiled, labels, symbols = compiled_fixture()
        baseline = L.inspect_unverified_native_loaders(compiled, symbols)
        spans = {s['label']: s for s in baseline['consumer_spans']}
        self.assertEqual(spans['Lyra_RoutingPrefix']['pc'],
                         [A.pc(0x02A5D3), A.pc(labels['Lyra_RoutingGate'])])
        self.assertEqual(spans['Lyra_LegacyMusicInitializer']['pc'],
                         [A.pc(0x02C463), A.pc(0x02C4BC)])
        # This stand-in is a synthetic reviewed SOURCE constant for the unit
        # fixture only; the production constant remains unchanged.
        with mock.patch.object(L, 'REVIEWED_COMPILED_BINDING', baseline):
            L._verify_reviewed_binding(compiled, symbols)
            for site in (0x02A5D3, 0x02A5D7, 0x02C463, 0x02C4A1, 0x02C4B6):
                with self.subTest(site=f'{site:06X}'):
                    altered = bytearray(compiled)
                    altered[A.pc(site)] ^= 0xFF
                    with self.assertRaisesRegex(ValueError, 'active native consumer family differs'):
                        L._verify_reviewed_binding(bytes(altered), symbols)

    def test_rom_and_music_foreign_owners_refused(self):
        from lyra_historical_fixture import historical_ledger_path
        original = json.loads(historical_ledger_path(self).read_bytes())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ledger.json'
            for space, at, check in (('pc_rom', L.CODE_START, L._publication),
                                     ('wram', 0x7EC9A1, L._music_ownership),
                                     ('wram', 0xC9A1, L._music_ownership)):
                changed = copy.deepcopy(original)
                changed['claims'].append(dict(id='foreign', space=space, base=at, size=1))
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'conflict'):
                    check(path)
            for entry in original['claims']:
                if entry['id'] == 'music_cache_192':
                    entry['size'] = 160
            path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, 'music reservation'):
                L._music_ownership(path)


if __name__ == '__main__':
    unittest.main()
