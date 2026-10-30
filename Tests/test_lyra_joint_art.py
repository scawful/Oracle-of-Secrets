"""Real assembler and refusal checks for the bounded current-save art emitter."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'Scripts/Build'), str(ROOT/'Scripts/Generate'),
                str(ROOT/'Scripts/Generate/tests')]
import lyra_joint_art as J
import lyra_project_prepare as Q
import lz2
from test_joint_palette_directory import input_rom, zs_fragment


class JointArtBuild(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        source = input_rom() + bytearray(0x200000)
        source[0x865:0x868] = J.A.snes(0x1E8000).to_bytes(3, 'little')
        for at in (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E):
            pc = J.A.pc(at); source[pc:pc+4] = bytes.fromhex('bf59940e')
        self.source = bytes(source)
        self.request = dict(live=dict(generation=3, operation_id='real-save-op'), transfer_id='1'*64)
        self.packet = dict(kind=J.KIND, source_rom_sha256=J.R.sha(self.source), generation=3,
                           operation_id='real-save-op', transfer_id='1'*64, writes=[], sheets=[])
        for role, ids in (('sky_tile16', J.SKY_IDS), ('ferry_tile16', J.FERRY_IDS)):
            for tile in sorted(ids):
                self.row(role, 0x1E8000+tile*8, bytes.fromhex('0010011002100310'))
        for pc, payload in J.PRESENTATION.items():
            self.row('presentation', pc, bytes.fromhex(payload))
        for sheet, (lo, hi) in enumerate(J.SHEET_SPANS, 0xDF):
            # Exercise the real decoder with the exact granted stream extents.
            for literal in range(1, 1536):
                stream = bytearray()
                lz2._emit_direct(stream, bytes(i % 256 for i in range(literal)))
                remaining = 1536-literal
                while remaining:
                    n = min(1024, remaining)
                    stream += lz2._hdr(1, n) + b'\0'; remaining -= n
                stream.append(255)
                if len(stream) == hi-lo:
                    break
            self.assertEqual(len(stream), hi-lo)
            path = self.folder/f'sheet{sheet:02x}.bin'; path.write_bytes(stream)
            pc = J.A.pc(lo)
            self.packet['sheets'].append(dict(global_sheet=sheet, stream=Q.bound(path),
                decoded_sha256=J.R.sha(lz2.decompress(stream)[0]),
                preimage_hex=self.source[pc:pc+len(stream)].hex()))
        graphics = self.folder/'ferry.bin'; graphics.write_bytes(bytes(0xB20))
        types = self.folder/'types.bin'; types.write_bytes(bytes([0, 2, 8]*29+[0, 2]))
        at = J.A.pc(0x0E9459)
        self.packet['ferry'] = dict(graphics=Q.bound(graphics), types=Q.bound(types),
                                    native_types_sha256=J.R.sha(self.source[at:at+512]))

    def row(self, role, at, payload):
        self.packet['writes'].append(dict(role=role, pc=at, payload_hex=payload.hex(),
                                         preimage_hex=self.source[at:at+len(payload)].hex()))

    def prepare(self, packet=None, **kwargs):
        path = self.folder/'packet.json'
        path.write_text(json.dumps(self.packet if packet is None else packet))
        return J.prepare(Q.bound(path), self.request, self.source, **kwargs)

    def test_saved_generation_and_grants_refuse_before_assembly(self):
        for field, value, message in (('generation', 2, 'GENERATION_STALE'),
                                       ('transfer_id', '2'*64, 'GENERATION_STALE')):
            bad = copy.deepcopy(self.packet); bad[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                self.prepare(bad)
        for change, message in ((lambda p:p['writes'].pop(), 'INCOMPLETE'),
            (lambda p:p['writes'][0].update(pc=0x1E8000), 'OUTSIDE_GRANT'),
            (lambda p:p['writes'][0].update(preimage_hex='ff'*8), 'PREIMAGE'),
            (lambda p:p['writes'][-1].update(payload_hex='df3be0e1e2e3e460'), 'OUTSIDE_GRANT')):
            bad = copy.deepcopy(self.packet); change(bad)
            with self.assertRaisesRegex(ValueError, message): self.prepare(bad)
        with self.assertRaisesRegex(ValueError, 'OVERLAP'):
            self.prepare(occupied=[(0x1E8000+min(J.SKY_IDS)*8, 0x1E8000+min(J.SKY_IDS)*8+8)])

    def test_bound_assets_and_native_collision_refuse_changes(self):
        bad = copy.deepcopy(self.packet); bad['sheets'][0]['decoded_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'SHEET_PAYLOAD_INVALID'): self.prepare(bad)
        bad = copy.deepcopy(self.packet); bad['ferry']['native_types_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'NATIVE_TYPES_CHANGED'): self.prepare(bad)
        path = Path(self.packet['ferry']['graphics']['path']); path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input changed'): self.prepare()

    def test_required_source_flags_cannot_fall_back_to_stock_readers(self):
        defines = dict(ENABLE_EXPANDED_GRAPHICS_TABLE=1, ENABLE_SOURCE_SPRITE_SHEETS=1,
                       ENABLE_OW_AREA_TILESETS=1)
        J.require_source_profile(dict(selected_source=dict(defines=defines)))
        for name in defines:
            bad = dict(defines); bad[name] = 0
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'SOURCE_FEATURES_UNBOUND'):
                J.require_source_profile(dict(selected_source=dict(defines=bad)))

    @unittest.skipUnless(os.environ.get('ASAR_BIN') or shutil.which('asar'), 'Asar unavailable')
    def test_real_assembler_emits_the_packet_and_four_palette_readers(self):
        plan, constants, data, binary = self.prepare()
        (self.folder/'binaries').mkdir()
        (self.folder/'binaries/joint-art.bin').write_bytes(binary)
        (self.folder/'data.asm').write_bytes(data)
        driver = f'''lorom
!ENABLE_OW_AREA_TILESETS = 1
!ENABLE_EON_OWL_ONE_SHOT = 0
!LYRA_CURRENT_MODE = 1
!DISABLE_OVERWORLD = 0
{constants}
PaletteIDtoOffset_OW_Main = $1BEC3B
PaletteData_owmain = $1BE6C8
org $3F8000
{zs_fragment()}
namespace Oracle
BoatBitmap = $E28000
AdditionalBitmap = $E2A000
SharedGraphicsRuntimeEnd = $E2E000
org $E2C000
SharedGraphicsResource_3fd640ea5f71e4301983dc4944b355f6d8582ea14797605688e5adaf37ffc3b4:
  incbin "Overworld/gfx/kalyxo_docks_slot3.bin"
incsrc "Overworld/area_tilesets.asm"
namespace off
incsrc "Core/gfx_sheet_table.asm"
incsrc "data.asm"
incsrc "Core/Generated/joint_palette/directory.asm"
incsrc "Overworld/joint_palette_readers.asm"
'''
        main = self.folder/'main.asm'; main.write_text(driver)
        rom = self.folder/'synthetic.sfc'; rom.write_bytes(self.source)
        sym = self.folder/'synthetic.sym'
        run = subprocess.run([os.environ.get('ASAR_BIN') or shutil.which('asar'), '--no-title-check',
            '--fix-checksum=on', '--symbols=wla', '--symbols-path='+str(sym), '-I'+str(ROOT),
            str(main), str(rom)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        image = rom.read_bytes()
        proof = J.verify(plan, image, sym.read_bytes(), ROOT)
        self.assertEqual(proof['art_writes_verified'], 272)
        self.assertEqual((proof['palette_readers_verified'], proof['collision_readers_verified']), (4, 4))
        self.assertEqual((proof['ferry_dock_bytes_verified'], proof['ferry_dma_descriptors_verified']), (0x800, 4))
        for pc, message in ((plan['writes'][0]['pc'][0], 'COMPILED_PAYLOAD'),
                            (J.A.pc(0xE2C000), 'DOCK_RESOURCE'),
                            (image.index(bytes.fromhex('002c000800c0e2')), 'DOCK_DMA'),
                            (J.A.pc(0x00E78F), 'EXPANDED_SHEET_READER'),
                            (J.A.pc(0x1BB730), 'PALETTE_PAYLOAD'),
                            (J.A.pc(0x1BEF16), 'PALETTE_READER'),
                            (J.A.pc(0x00886E), 'COLLISION_READER')):
            broken = bytearray(image); broken[pc] ^= 1
            with self.subTest(pc=pc), self.assertRaisesRegex(ValueError, message):
                J.verify(plan, broken, sym.read_bytes(), ROOT)
        # Independent review's control: without the expanded table include,
        # new pointer rows alone must not qualify a stock-loader image.
        no_readers = sym.read_bytes().replace(b'GfxSheet_Helpers', b'AbsentSheet_Helpers')
        with self.assertRaisesRegex(ValueError, 'EXPANDED_SHEET_READERS_MISSING'):
            J.verify(plan, image, no_readers, ROOT)


if __name__ == '__main__':
    unittest.main()
