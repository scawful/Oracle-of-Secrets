"""Compiled Sky BG1 context and ordinary transition controls on retained CPU.

The transition reload service is a declared probe: these tests qualify its
selection and caller preservation, not a native PPU upload or game walk.
"""
import struct
import unittest
import test_special_overworld_semantic_kernel as T

R = T.R
word = T.word
OVERLAY = 0x4E9000

def index862():
    raw = bytearray(160)
    raw[0x862 >> 5] = 1
    raw[128 + (0x862 & 31)] = 1
    return bytes(raw)

@unittest.skipUnless(R.ASSEMBLER and T.RUNNER, 'Asar and existing OOS_65816_RUNNER required')
class SkyOverlayResidencyTest(unittest.TestCase):
    def build(self, transition=False, docks=False):
        tables = {f.name: f.snes for f in R.N.current_table_layout(R.N.TABLE_BASE)}
        updates = []
        for page in (0x87, 0x8D, 0x8E, 0x8F):
            updates += [(tables['parent'] + page, bytes([page])),
                        (tables['area_size'] + page, b'\0')]
            record = (0x4E9400).to_bytes(3, 'little') + (0x4E9500).to_bytes(3, 'little') + bytes([0, 1])
            updates.append((0x4E8000 + (page - 128) * 8, record))
            for offset, ptr in ((0, 0x4E9700), (8, 0x4E9800)):
                record = (0x4E9400).to_bytes(3, 'little') + ptr.to_bytes(3, 'little') + bytes([0, 1])
                updates.append((OVERLAY + (page - 128) * 16 + offset, record))
        updates += [(0x4E9400, index862()),
                    (0x4E9500, bytes(8) + struct.pack('<4H', *([0x0C22] * 4))),
                    (0x4E9700, bytes(8) + struct.pack('<4H', *([0x09C0] * 4))),
                    (0x4E9800, bytes(8) + struct.pack('<4H', *([0x11C1] * 4))),
                    (0x3D8000 + 0x862 * 8, struct.pack('<4H', *([0x1DC2] * 4)))]
        extra = ''
        if transition:
            zs = (R.ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
            first = zs.index('org $0BFEB6 ; $05FEB6 ; @hook module=Overworld')
            last = zs.index('assert pc() <= $0BFFA8', first)
            fixed_color_source = zs[first:last]

            updates += [(0x02EF50, bytes.fromhex('2252F60E')),
                        (0x02C242, bytes.fromhex('22008137' if docks else '22008037')),
                        (0x02C23E, bytes.fromhex('e008e010')),
                        # Exact current native finalize tail, including music-cache
                        # relocation. Camera/scroll services are declared probes.
                        (0x02C246, bytes.fromhex('a002ad9c064ab002a0fe8400a2024ab002a200a0ffa5003001c818752095209875219521b520ae9c0629fedf3ec202d021641164b0a68abf00c97e4a4a4a4a8d2d01ad3001c9f1d009bf00c97e290f8d2c012090bbad1604f0032073f260'))]
            extra = f'''org $348000
namespace Oracle
incsrc "{R.ROOT / 'Overworld/lyra_overlay_fix.asm'}"
org $4DCB60
!SPECIAL_OVERWORLD_RESOURCE_CODE_END = $4DD000
incsrc "{R.ROOT / 'Overworld/sky_overlay_transition.asm'}"
namespace off
Docks_ShouldHideSubscreen:
  CLC : RTL
org $02C300
NativeFinalizeCaller:
  JSR $C242 : RTL
org $02BB90
CameraProbe:
  INC.w $0F04 : RTS
org $02F273
ScrollProbe:
  INC.w $0F06 : RTS
org $378000
OriginalAnimation:
  INC.w $0F00 : RTL
org $378100
ExistingDocksChain:
  INC.w $0F08 : JML $378000
org $02C310
PriorBusyReturnControl:
  JSR $C246 : RTL
org $02B1F4
ReloadProbe:
  REP #$20 : LDA.b $8A : STA.l $7EC213
  SEP #$30
  LDA.b #$9C : STA.b $8C
  LDA.l $7EE00E : BEQ .calm
  LDA.b #$9F : STA.b $8C
.calm:
  LDA.w $0F10 : CMP.b #$FF : BNE .selected
  STA.b $8C
.selected:
  LDA.b #$04 : STA.b $17 : STA.w $0710
  LDA.b #$01 : STA.b $1D
  INC.w $0F02 : RTL
org $0BFE70
  REP #$30 : JML $0BFEB6
{fixed_color_source}
org $378200
Pool_EnableRainMireEvent:
  db $00,$00
ReplaceBGColor:
  INC.w $0F0A : RTL
SpecialBgHorizOffsetAdjustment:
  RTL
'''
        a = T.Artifact([T.row(0x8D, 0x862, (0x10B6,) * 4)],
            overrides=dict(ENABLE_SKY_OVERWORLD_ROUTE=1, ENABLE_LYRA_OVERLAY_FIX=1,
                           LYRA_CURRENT_RESIDENT_OVERLAY_DIRECTORY=OVERLAY),
            image_updates=updates, extra_source=extra)
        self.addCleanup(a.close)
        self.assertEqual(a.proc.returncode, 0, a.proc.stdout + a.proc.stderr)
        return a

    def test_foreground_full_stripes_mutable_do_not_fall_into_overlay(self):
        a = self.build()
        for helper in ('Full0', 'Horizontal0', 'Vertical0', 'Mutable0'):
            ram = bytearray(65536)
            word(ram, 0x8A, 0x8D); word(ram, 0xC213, 0x87)
            word(ram, 4, 0x2000); ram[6] = 0x7E; word(ram, 2, 2)
            word(ram, 0x84, 0x3D0 if helper == 'Horizontal0' else 0x410)
            r, out, before = a.call('Lyra_Resident' + helper,
                x=32 if helper == 'Full0' else 0x862 * 8,
                y=0x862 * 8 if helper == 'Full0' else 32,
                db=0x3D, ram=ram)
            self.assertEqual(r['registers']['a'], 0x0C22, helper)
            for key in ('x', 'y', 'db', 'd', 'sp'):
                self.assertEqual(r['registers'][key], before[key], key)
            self.assertEqual(out[:0x1F80], ram[:0x1F80])
            self.assertEqual(out[0x2000:], ram[0x2000:])

    def test_same862_overlay_contexts_and_missing_controls(self):
        a = self.build()
        for host, picture, indoors, expected in (
            (0x87, 0x9C, 0, 0x09C0), (0x8D, 0x9C, 0, 0x09C0),
            (0x8E, 0x9F, 0, 0x11C1), (0x8F, 0x9C, 0, 0x09C0),
            (0x8C, 0x9C, 0, 0x1DC2), (0x8D, 0x96, 0, 0x1DC2),
            (0x8D, 0x9C, 1, 0x1DC2), (0xC0, 0x9C, 0, 0x1DC2)):
            ram = bytearray(65536)
            word(ram, 0x8A, picture); word(ram, 0xC213, host)
            word(ram, 4, 0x4000); ram[6] = 0x7E; ram[0x1B] = indoors
            r, out, before = a.call('Lyra_ResidentFull0', x=32, y=0x862*8, db=0x3D, ram=ram)
            self.assertEqual(r['registers']['a'], expected, (host, picture, indoors))
            for key in ('x', 'y', 'db', 'd', 'sp'):
                self.assertEqual(r['registers'][key], before[key])
            self.assertEqual(out[:0x1F80], ram[:0x1F80])
        ram = bytearray(65536); word(ram, 0x8A, 0x8D)
        r, _, _ = a.call('Lyra_SemanticTerrainSourceWord', a=0, x=0x862*8, ram=ram)
        self.assertEqual(r['registers']['a'], 0x10B6, 'collision/action source remains foreground')

    def test_finish_transition_refreshes_same_picture_once_and_preserves_camera(self):
        a = self.build(transition=True)
        for host in (0x87, 0x8D, 0x8E, 0x8F):
            ram = bytearray(65536)
            ram[0x10] = 9; ram[0x11] = 8; ram[0x8C] = 0x9C; ram[0x69C] = 1
            word(ram, 0x8A, host); word(ram, 0xC213, 0x8D if host == 0x87 else 0x87)
            for at in (0x20, 0x22, 0x84, 0x86, 0x88, 0xE0, 0xE2, 0xE6, 0xE8, 0x410, 0x416, 0x418):
                word(ram, at, 0x1234)
            r, out, before = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, x=23, y=45, ram=ram)
            self.assertEqual(out[0xF02], 1); self.assertEqual(out[0xF00], 1)
            self.assertEqual(int.from_bytes(out[0xC213:0xC215], 'little'), host)
            self.assertEqual(out[0x11], 8)
            self.assertEqual(int.from_bytes(out[0x20:0x22], 'little'), 0x1236)
            for at in (0x22, 0x84, 0x86, 0x88, 0xE0, 0xE2, 0xE6, 0xE8, 0x410, 0x416, 0x418):
                self.assertEqual(out[at:at+2], ram[at:at+2])
            for key in ('db', 'd', 'sp'):
                self.assertEqual(r['registers'][key], before[key])
            out[0x17] = out[0x710] = 0
            _, again, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=out)
            self.assertEqual(again[0xF02], 1); self.assertEqual(again[0xF00], 2)

    def test_busy_upload_waits_without_finishing_or_losing_host_refresh(self):
        a = self.build(transition=True)
        for field in (0x17, 0x710):
            ram = bytearray(65536); ram[0x10] = 9; ram[0x11] = 8
            word(ram, 0x8A, 0x8D); word(ram, 0xC213, 0x87); ram[field] = 4
            word(ram, 0x20, 0x106); ram[0x69C] = 1
            _, out, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=ram)
            self.assertEqual(out[0xF00], 0); self.assertEqual(out[0xF02], 0)
            self.assertEqual(out[0x11], 8)
            self.assertEqual(out[0x20:0x22], ram[0x20:0x22])
            self.assertEqual(out[0xF04], 0)
            out[field] = 0
            _, resumed, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=out)
            self.assertEqual(resumed[0xF00], 1); self.assertEqual(resumed[0xF02], 1)
            self.assertEqual(int.from_bytes(resumed[0x20:0x22], 'little'), 0x108)
            self.assertEqual(resumed[0x11], 0)
            self.assertEqual(resumed[0xF04], 1)

    def test_docks_chain_and_prior_busy_return_control(self):
        a = self.build(transition=True, docks=True)
        ram = bytearray(65536); ram[0x10] = 9; ram[0x11] = 8
        word(ram, 0x8A, 0x8D); word(ram, 0xC213, 0x87)
        word(ram, 0x20, 0x106); ram[0x69C] = 1; ram[0x17] = 4
        _, old, _ = a.call('PriorBusyReturnControl', p=0x30, db=0, d=0, ram=ram)
        self.assertEqual(old[0x11], 0, 'prior return into caller wrongly finishes arrival')
        self.assertEqual(int.from_bytes(old[0x20:0x22], 'little'), 0x108)
        r, held, before = a.call('NativeFinalizeCaller', p=0x31, db=0, d=0, x=21, y=43, ram=ram)
        for key in ('x', 'y', 'db', 'd', 'sp', 'p', 'a'):
            self.assertEqual(r['registers'][key], before[key], key)
        self.assertEqual(held[0x11], 8); self.assertEqual(held[0xF08], 0)
        held[0x17] = 0
        _, out, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=held)
        self.assertEqual(out[0xF02], 1); self.assertEqual(out[0xF08], 1)
        self.assertEqual(out[0xF00], 1); self.assertEqual(out[0x11], 0)

    def test_post_reload_actual_fixed_color_and_bg1_scroll_preserve_bg2_camera(self):
        a = self.build(transition=True)
        for overlay in (0x9C, 0x9F, 0xFF):
            ram = bytearray(65536); ram[0x10] = 9; ram[0x11] = 8
            word(ram, 0x8A, 0x8D); word(ram, 0xC213, 0x87)
            word(ram, 0xE0, 0x1111); word(ram, 0xE6, 0x2222)
            word(ram, 0xE2, 0x3333); word(ram, 0xE8, 0x4444)
            ram[0xE00E] = int(overlay == 0x9F)
            ram[0xF10] = 0xFF if overlay == 0xFF else 0
            _, out, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=ram)
            self.assertEqual(out[0xF0A], 1)
            self.assertEqual(out[0xE2:0xE4], ram[0xE2:0xE4])
            self.assertEqual(out[0xE8:0xEA], ram[0xE8:0xEA])
            if overlay == 0x9C:
                self.assertEqual(out[0x9C:0x9F], bytes.fromhex('264a87'))
                self.assertEqual(out[0xE0:0xE2], ram[0xE2:0xE4])
                self.assertEqual(out[0xE6:0xE8], ram[0xE8:0xEA])
            else:
                self.assertEqual(out[0x9C:0x9F], bytes.fromhex('204080'))
                self.assertEqual(out[0xE0:0xE2], ram[0xE0:0xE2])
                self.assertEqual(out[0xE6:0xE8], ram[0xE6:0xE8])
            self.assertEqual(out[0x1D], int(overlay != 0xFF))
            if overlay == 0xFF:
                self.assertEqual(out[0x9A], 0)

    def test_special_exits_and_unselected_hosts_keep_original_path(self):
        a = self.build(transition=True)
        for host, exit_room, rain in ((0x87, 0x180, 0), (0x8D, 0x181, 1),
            (0x8E, 0x182, 0), (0x8F, 0x189, 1), (0x8C, 0, 0)):
            ram = bytearray(65536); ram[0x10] = 9; ram[0x11] = 8
            word(ram, 0x8A, host); word(ram, 0xA0, exit_room); ram[0xE00E] = rain
            _, out, _ = a.call('NativeFinalizeCaller', p=0x30, db=0, d=0, ram=ram)
            self.assertEqual(out[0xF02], 0); self.assertEqual(out[0xF00], 1)
        for host, rain, carry in ((0x87, 0, 0), (0x8D, 0, 0), (0x8E, 1, 0),
                                   (0x8F, 0, 0), (0x8C, 0, 1), (0x8C, 1, 0)):
            ram = bytearray(65536); word(ram, 0x8A, host); ram[0xE00E] = rain
            r, _, _ = a.call('Oracle_LyraOverlay_UseTablePath', p=0, db=0, d=0, ram=ram)
            self.assertEqual(r['registers']['p'] & 1, carry)
