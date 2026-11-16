"""Compiled native entrance join: paired-data cell profile and ordinary controls."""
import unittest
from pathlib import Path
import re
import test_special_overworld_semantic_kernel as T


@unittest.skipUnless(T.R.ASSEMBLER and T.RUNNER, 'Asar and OOS_65816_RUNNER required')
class PrisonCell65Test(unittest.TestCase):
    def inventory_artifact(self, paired=1, armory=0):
        symbols = '\n'.join(line for line in (T.R.ROOT/'Core/symbols.asm').read_text().splitlines()
                            if re.match(r'^Spr\w+\s*=',line))
        capture = (T.R.ROOT/'Sprites/Enemies/custom_guard.asm').read_text()
        capture = 'Oracle_CaptureAndWarp:' + capture.split('Oracle_CaptureAndWarp:',1)[1].split('; Post-item-get',1)[0]
        source = f'''
!Func02A5D3 = 1
!ENABLE_DREAM_RETURN = 1
!ENABLE_D4_WATER_CONTROLS = 1
!ENABLE_D3_PRISON_SEQUENCE = 1
!ENABLE_D3_PRISON_CELL65 = {paired}
!ENABLE_D3_PRISON_ARMORY = {armory}
!ENABLE_WALL_PROFILE_SELECTOR = 1
WallSel_Private_prison_armory_slot3 = $459172
!DISABLE_SPRITES = 0
!DISABLE_OVERWORLD = 0
!DISABLE_DUNGEON = 0
!DISABLE_MASKS = 0
!ENABLE_MINISH_AUTO_PORTAL = 1
!CastleAmbush_HasBeenCaptured = 1
!CastleAmbush_HasEscaped = 2
!CastleAmbush_BladeReclaimed = 8
!CastleAmbush_SwordMask = $70
!CastleAmbush_AmbushPending = 4
!Spawn_Prison = 2
!Spawn_Sanctuary = 1
CastleAmbushFlags = $7EF306
Sword = $7EF359
SpawnPoint = $7EF3C8
MinishPortalTimer = $7E07EC
MinishPortalFrame = $7E07ED
!Msg_CellmateHint1 = $1CF
!Msg_GuardCaptureTaunt = $1CC
!Msg_PostEscapeFlavor = $1D1
{symbols}
org $348000
incsrc "{T.R.ROOT/'Dungeons/prison_sequence.asm'}"
{capture}
ResetToLinkGraphics: STZ.w $02B2 : RTL
Sprite_CheckActive: SEC : RTL
org $0DB818
  RTL ; native sprite-slot prep service; selected fields checked below
org $05DF75
  LDA.w $040C : STA.w $0F72 ; actual DBR must reach low WRAM
  PHB : PLA : STA.w $0F73
  REP #$30 : LDY.w #0 : LDA.b ($08),Y : STA.w $0F74
  SEP #$30 : RTL ; observe real table read, not a visual qualification
org $07F4D0
  LDA.w $02FF : BEQ .ready
  SEC : RTL
.ready: CLC : RTL
org $00D2C8
  INC.w $0F70 : RTL ; sword graphics refresh observation
org $1BED03
  INC.w $0F71 : RTL ; sword palette refresh observation
org $0799AD
  STY.w $02D8 : PHX : LDX.b #$04
.find_free
  LDA.w $0C4A,X : BEQ .found
  DEX : BPL .find_free
  PLX : RTL
.found
  LDA.b #$01 : STA.w $02E4
  LDA.b #$22 : STA.w $0C4A,X
  LDA.b #$02 : STA.w $0C54,X
  LDA.b #$38 : STA.w $03B1,X
  PHX : JML $098610 ; actual hooked prefix, with native stacked slot
org $09877A
  JML $0987AE ; item graphics extraction is a service endpoint in this fixture
org $0987AE
  ; Exact native sword-refresh branch, including item00's skip.
  LDA.w $02D8 : BEQ .not_sword
  JSL $00D2C8
  JSL $1BED03
.not_sword
assert pc() == $0987BB
  PLX : PLX : RTL ; native ancilla setup remains a service endpoint
org $098615
  LDA.b #$01 : STA.l $7EF35A ; native fighter shield write control
  JML $09862A
org $09862A
  LDA.w $02D8 : INC A : STA.l $7EF359
  JML $09877A
org $05FA8E
  LDA.b #$0E : STA.b $10 : RTL ; native message takes control
org $02A1B1
  LDA.b #$19 : STA.b $11 : RTL ; native mirror fade starts
org $02B929
  INC.w $0F76 : RTL ; native room-save observation
org $02A1C7
  INC.w $0F77 : RTL ; native key-save observation
org $02856A
  RTL ; original bunny-status service
org $0BFFBF
  STA.w $005E : RTL ; native death cleanup consumes incoming A
org $348600
ExitNoticeFixture:
if !ENABLE_D3_PRISON_CELL65 == 1
  JSL PrisonEscape_RecordOutwardExit
  REP #$20 : LDA.l D3Prison_ExitMessage : STA.w $0F78
  SEP #$20 : LDA.b #$09 : STA.b $10
  JSL D3Prison_TryExitMessage
  REP #$20 : LDA.l D3Prison_ExitMessage : STA.w $0F7A
  SEP #$20
endif
  RTL
SeedExitNoticeFixture:
if !ENABLE_D3_PRISON_CELL65 == 1
  REP #$20 : LDA.w #!D3Prison_ExitMessageLive : STA.l D3Prison_ExitMessage
  SEP #$20
  JSL D3Prison_TryExitMessage
  REP #$20 : LDA.l D3Prison_ExitMessage : STA.w $0F7A
  SEP #$20
endif
  RTL
org $348500
KeyGateFixture:
if !ENABLE_D3_PRISON_CELL65 == 1
  PHB : PHA : PHY
  JML D3Prison_CellKeyBlockGate
else
  RTL
endif
org $01EBA6
  PLY : PLA : PLB : SEC : RTL ; native successful key-block unwind
org $01EBE1
  PLY : PLA : PLB : CLC : RTL ; native refusal unwind


'''
        art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0},extra_source=source,
            image_updates=[(0x098610,bytes.fromhex('acd802d015')), (0x09F540,bytes.fromhex('22bfff0b')),
                           (0x07D133,bytes.fromhex('2229b902')),
                           (0x05D543,bytes.fromhex('2263f01d')),
                           (0x02891B,bytes.fromhex('a5f02920')),
                           (0x07A965,bytes.fromhex('22b1a102')),
                           (0x1DC8D8,bytes.fromhex('229ecc1d')),
                           (0x05C227,bytes.fromhex('bdc00d48')),
                           (0x0283CE,bytes.fromhex('226a8502a510c908')),
                           (0x02DADB,bytes.fromhex('a980854585446b')),
                           (0x0588D6,bytes.fromhex('a510c91a')),
                           (0x00E1ED,bytes.fromhex('8fffc27e')),(0x00D775,bytes.fromhex('8fffc27e')),
                           (0x02E4A6,bytes.fromhex('641b9c5804'))])
        self.addCleanup(art.close)
        self.assertEqual(art.proc.returncode,0,art.proc.stdout+art.proc.stderr)
        return art





    def key_block_native_artifact(self, *, paired=1, legacy=False):
        recovery = (T.R.ROOT/'Dungeons/d3_prison_recovery.asm').read_text()
        gate = 'D3Prison_CellKeyBlockGate:' + recovery.split('D3Prison_CellKeyBlockGate:', 1)[1].split('; Accepted Game Over', 1)[0]
        if legacy:
            predicate = """  LDA.l CastleAmbushFlags
  AND.w #(!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped)
  CMP.w #!CastleAmbush_HasBeenCaptured : BEQ .denied"""
            self.assertEqual(gate.count(predicate), 1)
            gate = gate.replace(predicate, '  JSL D3Prison_ShouldResumeCell : BCS .denied')
        inventory = (T.R.ROOT/'Dungeons/d3_prison_inventory.asm').read_text()
        resume = 'D3Prison_ShouldResumeCell:' + inventory.split('D3Prison_ShouldResumeCell:', 1)[1].split('D3Prison_RestartEscape:', 1)[0]
        source = f"""
!ENABLE_D3_PRISON_CELL65 = {paired}
!ENABLE_D3_PRISON_ARMORY = 0
!ENABLE_WALL_PROFILE_SELECTOR = 1
WallSel_Private_prison_armory_slot3 = $459172
!CastleAmbush_HasBeenCaptured = 1
!CastleAmbush_HasEscaped = 2
!CastleAmbush_SwordMask = $70
CastleAmbushFlags = $7EF306
Sword = $7EF359
org $528000
{gate}
{resume}
incsrc "{T.R.ROOT/'Dungeons/keyblock.asm'}"
org $348500
NativeKeyBlockFixture:
  PHB : JML $01EB72
org $01EB72
  ; Exact retained 85344019 OpenItemChest prefix through the hook.
  REP #$30 : AND.w #$00FF : SEC : SBC.w #$0058
  STA.b $0E : ASL A : PHA : TAY : PHY
  LDA.w $06E0,Y : CMP.w #$8000 : BCC .not_key_block
  LDX.w $040C
assert pc() == $01EB8C
org $01EBE8
.not_key_block:
  PLY : PLA : SEP #$30 : PLB : CLC : RTL
org $019900
  dw $FF00 ; exact first native room-flag mask
org $01EBA6
  ; Exact native successful prefix; subsequent tile drawing is a service.
  LDA.w $0402 : ORA.w $9900,Y : STA.w $0402
  LDA.w #$1529 : STA.w $012E
assert pc() == $01EBB5
  PLY : PLA : SEP #$30 : PLB : SEC : RTL
org $01EBE1
  ; Exact native refusal unwind, including X/Y becoming eight-bit.
  PLY : PLA : SEP #$30 : PLB : CLC : RTL
"""
        art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0}, extra_source=source)
        self.addCleanup(art.close)
        self.assertEqual(art.proc.returncode, 0, art.proc.stdout + art.proc.stderr)
        for address, expected in ((0x01EB72, 'c23029ff0038e95800850e0a48a85ab9e006c90080905fae0c04'),
                                  (0x01EBA6, 'ad02041900998d0204a929158d2e01'),
                                  (0x01EBE1, '7a68e230ab186b')):
            at = T.R.N.pc(address)
            self.assertEqual(art.image[at:at+len(expected)//2].hex(), expected)
        return art

    def test_native_key_block_captivity_preserves_carried_keys(self):
        candidate = self.key_block_native_artifact()
        control = self.key_block_native_artifact(legacy=True)
        feature_off = self.key_block_native_artifact(paired=0)
        def exercise(art, *, room=0x65, flags=0x21, sword=0, keys=3, indoors=1, dungeon=0x10, opens=False):
            ram = bytearray(65536)
            T.word(ram, 0xA0, room); T.word(ram, 0x6E0, 0x8000)
            ram[0x1B]=indoors; ram[0x40C]=dungeon
            ram[0xF306]=flags; ram[0xF359]=sword
            ram[0xF36F]=keys; ram[0xF370]=0x80
            result,out,before = art.call('NativeKeyBlockFixture', ram=ram, a=0x58, x=0x1234, y=0x4567, p=0, db=1, d=0)
            self.assertEqual(out[0xF36F], keys-int(opens))
            self.assertEqual(out[0xF370], 0x80)
            self.assertEqual(out[0x402:0x404], bytes.fromhex('00ff') if opens else b'\0\0')
            self.assertEqual(out[0x12E:0x130], bytes.fromhex('2915') if opens else b'\0\0')
            expected_sram = bytearray(ram[0xF000:])
            expected_sram[0x36F] = keys-int(opens)
            self.assertEqual(out[0xF000:], expected_sram)
            regs=result['registers']
            self.assertEqual(regs['p'] & 0x31, 0x30 | int(opens))
            self.assertEqual(regs['x'], dungeon); self.assertEqual(regs['y'], 0)
            for key in ('db','d','sp'): self.assertEqual(regs[key], before[key])
        # The old source permits a real carried-key bypass with missing backup.
        exercise(control, flags=1, sword=0, opens=True)
        exercise(control, flags=0x21, sword=0)
        exercise(candidate, flags=1, sword=0)
        for flags,sword in ((0x21,0),(0x29,2),(0x51,0),(0x71,0),(0x21,0xFF),(0x25,0)):
            exercise(candidate, flags=flags, sword=sword)
        for changes in ({'flags':0x2B}, {'flags':0}, {'room':0x165}, {'room':0x64}, {'indoors':0}, {'dungeon':2}):
            exercise(candidate, **changes, opens=True)
        exercise(candidate, flags=0, keys=0)
        exercise(feature_off, flags=1, opens=True)
        exercise(feature_off, flags=0x21, opens=True)
        exercise(feature_off, flags=0x21, keys=0)

    def test_exit_notice_once_wait_cancel_and_real_flag_context(self):
        art=self.inventory_artifact()
        r=bytearray(65536);r[0x10]=8;r[0x1B]=1;r[0x40C]=0x10
        r[0xA0]=0x55;r[0xF306]=0x29;r[0xF359]=2
        _,out,_=art.call('ExitNoticeFixture',ram=r,p=0x30,db=2,d=0)
        self.assertEqual(out[0xF78:0xF7C],bytes.fromhex('55d30000'))
        self.assertEqual(out[0x1CF0:0x1CF2],bytes.fromhex('d101'))
        self.assertEqual(out[0x10],0x0E);self.assertEqual(out[0xF306],0x2B)
        # A cold/reset runner starts with no volatile token: completed save
        # alone must not repeat the notice.
        out[0x10]=9
        _,repeat,_=art.call('D3Prison_TryExitMessage',ram=out,p=0x30,db=2,d=0)
        self.assertEqual(repeat[0x10],9)
        for kind in ('busy','wrong_room','not_escaped','indoors'):
            q=bytearray(out);q[0x1CF0:0x1CF2]=b'\0\0'
            if kind=='busy':q[0x11]=1
            if kind=='wrong_room':q[0xA1]=1
            if kind=='not_escaped':q[0xF306]=0x29
            if kind=='indoors':q[0x1B]=1
            _,checked,_=art.call('SeedExitNoticeFixture',ram=q,p=0x30,db=2,d=0)
            self.assertEqual(checked[0x1CF0:0x1CF2],b'\0\0')
            self.assertEqual(checked[0xF7A:0xF7C],bytes.fromhex('55d3') if kind=='busy' else b'\0\0')

    def test_wing_boss_key_block_and_save_restart_controls(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x65;ram[0xF306]=0x21;ram[0xF36F]=3;ram[0xF370]=0x80
        for room,flags,sword,keys,opens in ((0x65,0x21,0,3,False),(0x65,0x29,2,3,False),(0x65,0x2B,2,3,True),(0x165,0x21,0,3,True),(0x64,0x21,0,3,True),(0x65,0,0,0,False)):
            r=bytearray(ram);T.word(r,0xA0,room);r[0xF306]=flags;r[0xF359]=sword;r[0xF36F]=keys
            result,out,before=art.call('KeyGateFixture',ram=r,p=0,db=1,d=0,x=0x1234,y=0x4567)
            self.assertEqual(bool(result['registers']['p']&1),opens)
            self.assertEqual(out[0xF36F],keys-int(opens));self.assertEqual(out[0xF370],0x80)
            for key in ('a','x','y','db','d','sp'):self.assertEqual(result['registers'][key],before[key])
        for escaped in (False,True):
            for sword in (0,1,2,3,4,0xFF):
                r=bytearray(ram);r[0xF306]=0x29|(2 if escaped else 0);r[0xF359]=sword
                result,out,before=art.call('D3Prison_BossGateIsOpen',ram=r,p=0x30,db=0x52,d=0)
                self.assertEqual(bool(result['registers']['p']&1),escaped and 2<=sword<=4)
                self.assertEqual(out[0xF000:],r[0xF000:])
        for room,target,flags,allow in ((0x80,0x55,0,False),(0x55,0x80,0x21,False),(0x80,0x55,0x2B,True),(0x180,0x55,0,True),(0x80,0x11,0,True)):
            r=bytearray(ram);T.word(r,0xA0,room);r[0xC000]=target;r[0xF306]=flags
            result,_,_=art.call('D3Prison_WingWarpAllowed',ram=r,p=0x30,db=7,d=0)
            self.assertEqual(bool(result['registers']['p']&1),allow)
        ram[0xF306]=0x29;ram[0xF359]=2
        result,out,before=art.call('D3Prison_RestartBeforeSave',ram=ram,a=0xAB12,p=0x30,db=9,d=0)
        self.assertEqual(out[0x5E],0x12);self.assertEqual(out[0xF306],0x21);self.assertEqual(out[0xF359],0)
        for key in ('a','x','y','db','d','sp'):self.assertEqual(result['registers'][key],before[key])
        off=self.inventory_artifact(paired=0)
        for address,size in ((0x098610,5),(0x09F540,4),(0x02891B,4),(0x07A965,4),(0x1DC8D8,4),(0x05C227,4),(0x0283CE,8),(0x07D133,4),(0x05D543,4),(0x02DADB,4)):
            at=T.R.N.pc(address);self.assertEqual(off.image[at:at+size],off.before[at:at+size],hex(address))

    def test_hall_stages_taunt_then_capture_and_pool_refusal(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x56;ram[0xF306]=4;ram[0xF359]=2
        T.word(ram,0x22,0xC80);T.word(ram,0x20,0xB80)
        def tick(r):
            result,out,before=art.call('D3Prison_PlayerControl',ram=r,p=0x30,db=0x52,x=7,y=9,d=0)
            for key in ('x','y','db','d','sp'):
                self.assertEqual(result['registers'][key],before[key],key)
            return out
        staged=tick(ram)
        self.assertEqual(staged[0xE30+15],0xE1);self.assertEqual(staged[0xE30+14],0xE2)
        self.assertEqual(staged[0xD10+15],0xEF);self.assertEqual(staged[0xD10+14],0xF7)
        self.assertEqual(staged[0x2E4],1);self.assertEqual(staged[0xF359],2)
        staged[0xF80+15]=0xBF
        message=tick(staged)
        self.assertEqual(message[0x10],0xE);self.assertEqual(message[0xF80+15],0xC1)
        self.assertEqual(message[0x1CF0:0x1CF2],b'\xcc\x01')
        self.assertEqual(message[0xF306],4);self.assertEqual(message[0xF359],2)
        waiting=tick(message);self.assertEqual(waiting[0xF359],2)
        message[0x10]=7;captured=tick(message)
        self.assertEqual(captured[0xF306],0x21);self.assertEqual(captured[0xF359],0)
        self.assertEqual(captured[0x11],0x19);self.assertEqual(captured[0xF3C8],2)
        self.assertEqual(captured[0xDD0+14:0xDD0+16],b'\0\0')
        self.assertEqual(captured[0x2E4],0);self.assertEqual(captured[0xFFC],0)
        for kind in ('full_pool','outside_hall','other_room','other_scene'):
            r=bytearray(ram)
            if kind=='full_pool':r[0xDD0:0xDE0]=bytes([9])*16
            if kind=='outside_hall':T.word(r,0x20,0xA80)
            if kind=='other_room':r[0xA1]=1
            if kind=='other_scene':r[0x2E4]=1
            out=tick(r)
            self.assertEqual(out[0xF306],4,kind);self.assertEqual(out[0xF359],2,kind)
            self.assertEqual(out[0xE30:0xE40],r[0xE30:0xE40],kind)
            self.assertEqual(out[0x2E4],r[0x2E4],kind)

    def test_patrol_visibility_turns_retry_and_reclaimed_fallback(self):
        art=self.inventory_artifact();slot=3
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x64;ram[0xF306]=0x21;ram[0x2B2]=5
        ram[0xDD0+slot]=9;ram[0xE20+slot]=0x41
        ram[0xD10+slot]=0xF0;ram[0xD30+slot]=8;ram[0xD00+slot]=0x60;ram[0xD20+slot]=0xC
        def call(label,r):
            result,out,before=art.call(label,ram=r,p=0x30,db=0x52,x=slot,y=6,d=0)
            for key in ('x','y','db','d','sp'):
                self.assertEqual(result['registers'][key],before[key],key)
            return result,out
        result,patrol=call('D3Prison_PatrolInit',ram)
        self.assertEqual(result['registers']['p']&1,1);self.assertEqual(patrol[0xE30+slot],0xE3)
        self.assertEqual(patrol[0xD00+slot],0x80)
        patrol[0xD10+slot]=0x7F;patrol[0xD30+slot]=9
        _,end=call('D3Prison_PatrolStep',patrol)
        self.assertEqual(end[0xD10+slot],0x80);self.assertEqual(end[0xDE0+slot],1)
        patrol[0xD10+slot]=0xF0;patrol[0xD30+slot]=8
        T.word(patrol,0x20,0xC80);T.word(patrol,0x22,0x910)
        result,seen=call('D3Prison_PatrolCanSee',patrol)
        self.assertEqual(result['registers']['p']&1,1,'Minish is visible in forward strip')
        for kind in ('behind','wall_band','other_floor','reclaimed','frozen'):
            r=bytearray(patrol)
            if kind=='behind':T.word(r,0x22,0x8D0)
            if kind=='wall_band':T.word(r,0x20,0xD10)
            if kind=='other_floor':r[0xEE]=1
            if kind=='reclaimed':r[0xF306]=0x29;r[0xF359]=2
            if kind=='frozen':r[0x11]=1
            result,_=call('D3Prison_PatrolCanSee',r)
            self.assertEqual(result['registers']['p']&1,0,kind)
        result,retry=call('D3Prison_PatrolCaught',patrol)
        self.assertEqual(result['registers']['p']&1,1)
        self.assertEqual(retry[0x11],0x19);self.assertEqual(retry[0x2B2],0)
        self.assertEqual(retry[0xF306],0x21);self.assertEqual(retry[0xF359],0)
        self.assertEqual(retry[0x10E:0x110],b'\x32\0')
        self.assertEqual(retry[:16],patrol[:16])

    def test_pending_exit_select_mirror_and_thief_custody(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x56;ram[0xF306]=4;ram[0xF359]=2;ram[0xF0]=0x20
        result,out,_=art.call('D3Prison_SelectGate',ram=ram,p=0x30,db=2,d=0)
        self.assertEqual(result['registers']['a']&255,0)
        _,out,_=art.call('D3Prison_MirrorGate',ram=ram,p=0x30,db=2,d=0)
        self.assertEqual(out[0x12E],0x3C);self.assertEqual(out[0x11],0)
        ram[0x10]=8
        result,out,_=art.call('D3Prison_PendingExitGate',ram=ram,p=0x30,db=2,d=0)
        self.assertEqual(result['registers']['p']&1,1);self.assertEqual(out[0x10],5)
        self.assertEqual(out[0x10E:0x110],b'\x28\0');self.assertEqual(out[0xF306],4)
        self.assertEqual(out[0xF76:0xF78],b'\1\1')
        ram[0xA0]=0x65;ram[0x48E]=0x65;ram[0x10]=7;ram[0xF306]=0x21;ram[0xF359]=0
        _,staged,_=art.call('D3Prison_ThiefStage',ram=ram,p=0x30,db=0x52,d=0)
        self.assertEqual(staged[0xE20+15],0xC4);self.assertEqual(staged[0xE30+15],0xD3)
        self.assertEqual(staged[0xDA0+15],0x65)
        _,again,_=art.call('D3Prison_ThiefStage',ram=staged,p=0x30,db=0x52,d=0)
        self.assertEqual(again[0xDD0:0xDE0],staged[0xDD0:0xDE0])
        staged[0xF306]=0x29;staged[0xF359]=2
        result,_,_=art.call('D3Prison_ThiefEligible',ram=staged,p=0x30,db=0x52,d=0)
        self.assertEqual(result['registers']['p']&1,0)

    def test_capture_reclaim_restart_and_actual_exit_transaction(self):
        art=self.inventory_artifact()
        def call(label,ram):
            result,out,before=art.call(label,a=0x32,x=3,y=5,p=0x30,db=2,d=0,ram=ram)
            for key in ('x','y','db','d','sp'):
                self.assertEqual(result['registers'][key],before[key],key)
            self.assertEqual(result['registers']['p']&0x30,0x30)
            return result,out
        for sword in (1,2,3,4):
            ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
            ram[0xA0]=0x56;ram[0xF359]=sword;ram[0xF306]=0x84
            result,captured=call('Oracle_CaptureAndWarp',ram)
            flags=0x81|(sword<<4)
            self.assertEqual(captured[0xF306],flags);self.assertEqual(captured[0xF359],0)
            self.assertEqual(captured[0xF3C8],2);self.assertEqual(captured[0x10],5)
            self.assertEqual(captured[0x10E:0x110],b'\x32\x00')
            _,loaded,_=art.call(0x02DADB,a=0xAB5A,x=0xCAFE,y=0xBEEF,
                               p=0x20,db=2,d=0,ram=captured)
            self.assertEqual(loaded[0xA0:0xA2],b'\x65\x00')
            self.assertEqual(loaded[0x20:0x24],bytes.fromhex('180dd00a'))
            captured[0x10]=7;captured[0xA0]=0x64
            _,retry=call('Oracle_CaptureAndWarp',captured)
            self.assertEqual(retry[0xF306],flags,'recapture retains sword backup')
            retry[0x10]=7;retry[0xA0]=0x54
            _,reclaimed=call('D3Prison_Reclaim',retry)
            self.assertEqual(reclaimed[0xF359],sword);self.assertEqual(reclaimed[0xF306],flags|8)
            _,restart=call('D3Prison_RestartEscape',reclaimed)
            self.assertEqual(restart[0xF359],0);self.assertEqual(restart[0xF306],flags)
            reclaimed[0x10]=8;reclaimed[0xA0]=0x55
            _,escaped=call('PrisonEscape_RecordOutwardExit',reclaimed)
            self.assertEqual(escaped[0xF306],flags|10);self.assertEqual(escaped[0xF3C8],1)
            # Getting to the exit without recovering the blade is insufficient.
            retry[0x10]=8;retry[0xA0]=0x55
            _,not_escaped=call('PrisonEscape_RecordOutwardExit',retry)
            self.assertEqual(not_escaped[0xF306],flags);self.assertEqual(not_escaped[0xF3C8],2)
        for sword,room,flags in ((0,0x56,0),(0xFF,0x56,0),(2,0x155,0),(2,0x56,3)):
            ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
            T.word(ram,0xA0,room);ram[0xF359]=sword;ram[0xF306]=flags
            result,out=call('Oracle_CaptureAndWarp',ram)
            self.assertEqual(result['registers']['p']&1,0)
            self.assertEqual(out[0xF000:],ram[0xF000:]);self.assertEqual(out[0x10],7)
        for sword,accepted in ((3,True),(0,False),(0xFF,False)):
            ram=bytearray(65536);ram[0xF306]=0x81;ram[0xF359]=sword
            result,out=call('D3Prison_RestartEscape',ram)
            self.assertEqual(bool(result['registers']['p']&1),accepted)
            self.assertEqual(out[0xF306],0xB1 if accepted else 0x81)
            self.assertEqual(out[0xF359],0 if accepted else sword)

    def test_room54_blade_stage_and_silent_front_interaction(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x21
        _,staged,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        slot=15
        self.assertEqual(staged[0xDD0+slot],9);self.assertEqual(staged[0xE20+slot],0x62)
        self.assertEqual(staged[0xE30+slot],0xD3);self.assertEqual(staged[0xDA0+slot],0x54)
        self.assertEqual(staged[0xD10+slot],0x80);self.assertEqual(staged[0xD30+slot],8)
        self.assertEqual(staged[0xD00+slot],0x80);self.assertEqual(staged[0xD20+slot],10)
        _,again,_=art.call('D3Prison_BladeStage',ram=staged,p=0x30,db=2,d=0)
        self.assertEqual(again[0xDD0:0xDE0],staged[0xDD0:0xDE0],'no duplicate actor')
        full=bytearray(ram);full[0xDD0:0xDE0]=bytes([9])*16
        _,out,_=art.call('D3Prison_BladeStage',ram=full,p=0x30,db=2,d=0)
        self.assertEqual(out[0xD00:0x1000],full[0xD00:0x1000],'no actor evicted')
        staged[0xF6]=0x80;T.word(staged,0x22,0x878);T.word(staged,0x20,0xA90)
        for changes,allowed in (({},True),({0xF6:0},False),({0x2F:2},False),
                                ({0x2B2:5},False),({0x2FF:1},False),({0xEE:1},False)):
            case=bytearray(staged)
            for at,value in changes.items():case[at]=value
            _,out,_=art.call('D3Prison_BladeMain',x=slot,ram=case,p=0x30,db=0x52,d=0)
            self.assertEqual(out[0xF359],2 if allowed else 0)
            self.assertEqual(out[0xF306],0x29 if allowed else 0x21)
            self.assertEqual(out[0xDD0+slot],9)
            self.assertEqual(out[0x5D],0x15 if allowed else 0)
            self.assertEqual(out[0xC4E],0x22 if allowed else 0)
            self.assertEqual(out[0xF70:0xF72],b'\x01\x01' if allowed else b'\x00\x00')
            self.assertEqual(out[0xF72:0xF76],bytes.fromhex('1038f8ff'),'low-WRAM and table reads share valid DBR')

    def test_blade_accepts_only_fresh_a_dash_startup(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x21
        _,ram,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        ram[0xF6]=0x80;T.word(ram,0x22,0x878);T.word(ram,0x20,0xA90)
        ram[0x5D]=0x11;ram[0x374]=0x1D;ram[0x372]=1;ram[0x2F1]=0x40
        for changes,allowed in (({},True),({0x374:0x1C},False),
                ({0x372:0},False),({0x5D:0x12},False),({0xF6:0},False),
                ({0x2FF:1},False),({0x2F:2},False),({0x2B2:5},False),
                ({0xEE:1},False),({0xC4E:0x22},False)):
            case=bytearray(ram)
            for at,value in changes.items():case[at]=value
            _,out,_=art.call('D3Prison_BladeMain',x=15,ram=case,p=0x30,db=0x52,d=0)
            self.assertEqual(out[0xF359],2 if allowed else 0)
            self.assertEqual(out[0xF306],0x29 if allowed else 0x21)
            self.assertEqual(out[0x5D],0x15 if allowed else case[0x5D])
            for at in (0x372,0x374,0x2F1):
                self.assertEqual(out[at],0 if allowed else case[at])

    def test_blade_pose_levels_slot_refusal_and_native_completion(self):
        art=self.inventory_artifact()
        for sword in range(1,5):
            for held in (0,4):
                ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
                ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=(sword<<4)|1
                ram[0xF359]=held;ram[0xF35A]=3
                _,ram,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
                ram[0xF6]=0x80;T.word(ram,0x22,0x878);T.word(ram,0x20,0xA90)
                for blocked in ('none','full','receipt'):
                    case=bytearray(ram)
                    if blocked=='full':case[0xC4A:0xC4F]=bytes([1,2,3,4,5])
                    if blocked=='receipt':case[0xC4A]=0x22
                    before=bytes(case)
                    _,out,_=art.call('D3Prison_BladeMain',x=15,ram=case,p=0x30,db=0x52,d=0)
                    if blocked!='none':
                        self.assertEqual(out[0xF306],before[0xF306])
                        self.assertEqual(out[0xF359:0xF35B],before[0xF359:0xF35B])
                        self.assertEqual(out[0xC4A:0xC4F],before[0xC4A:0xC4F]);continue
                    wanted=max(sword,held)
                    self.assertEqual(out[0xF359],wanted)
                    self.assertEqual(out[0xF35A],3,'no fighter receipt shield downgrade')
                    self.assertEqual(out[0x2D8],wanted-1,'matching existing sword icon')
                    self.assertEqual(out[0xF70:0xF72],bytes([1,1]),'each restored sword refreshes exactly once')
                    self.assertEqual(out[0x5D],0x15);self.assertEqual(out[0x2DA],1)
                    self.assertEqual(out[0x11],0,'no Master Sword scene')
                    self.assertEqual(out[0xDBF],4,'native allocator selected slot')
                    _,waiting,_=art.call('D3Prison_BladeMain',x=15,ram=out,p=0x30,db=0x52,d=0)
                    self.assertEqual(waiting[0x5D],0x15)
                    self.assertEqual(waiting[0xF70:0xF72],out[0xF70:0xF72],'no repeated grant')
                    # Actual type2 terminal clears02E9 before retiring its
                    # ancilla, while leaving the pose for the sprite owner.
                    waiting[0x2E9]=0;waiting[0xC4E]=0;waiting[0xC4A]=7
                    _,done,_=art.call('D3Prison_BladeMain',x=15,ram=waiting,p=0x30,db=0x52,d=0)
                    self.assertEqual(done[0x5D],0);self.assertEqual(done[0xDDF],0)
                    self.assertEqual(done[0xC4A],7)
                    self.assertEqual(done[0xF359],wanted)
        # A normal native receipt retains its inventory prefix in the same room.
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0xA0]=0x54
        ram[0x40C]=0x10;ram[0x2E9]=2;ram[0xF35A]=3
        _,out,_=art.call(0x0799AD,x=3,y=0,ram=ram,p=0x30,db=0,d=0)
        self.assertEqual(out[0xF359:0xF35B],bytes([1,1]))

    def test_blade_receipt_terminal_clear_and_foreign_ownership(self):
        art=self.inventory_artifact(armory=1)
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x21
        _,ram,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        ram[0xF6]=0x80;T.word(ram,0x22,0x878);T.word(ram,0x20,0xA95)
        _,owned,_=art.call('D3Prison_BladeMain',x=15,ram=ram,p=0x30,db=0x52,d=0)
        self.assertEqual((owned[0xDBF],owned[0xC4E],owned[0x5D]),(4,0x22,0x15))
        for name,changes,releases,despawns in (
                ('native-terminal',{0xC4E:0,0x2E9:0},True,True),
                ('owner-tag-retained',{0xC4E:0},True,True),
                ('active-own-receipt',{},False,False),
                ('replacement-effect',{0xC4E:7,0x2E9:0},False,True),
                ('other-receipt',{0xC4E:0,0xC4A:0x22,0x2E9:0},False,True),
                ('different-pose',{0xC4E:0,0x5D:2,0x2E9:0},False,True),
                ('foreign-receipt-type',{0xC4E:0,0x2E9:3},False,True),
                ('invalid-owned-slot',{0xDBF:5},False,True)):
            with self.subTest(name=name):
                case=bytearray(owned)
                for at,value in changes.items():case[at]=value
                result,out,before=art.call('D3Prison_BladeMain',x=15,ram=case,p=0x30,db=0x52,d=0)
                self.assertEqual(out[0xC4A:0xC54],case[0xC4A:0xC54],'no ancilla writes')
                self.assertEqual(out[0xF306],case[0xF306]);self.assertEqual(out[0xF359],2)
                for at in (0x5D,0x2DA,0x37B,0x2D8,0x2E4,0x2E9,0xFC1):
                    self.assertEqual(out[at],0 if releases else case[at])
                self.assertEqual(out[0xDDF],0 if despawns else 9)
                for key in ('x','db','d','sp'):
                    self.assertEqual(result['registers'][key],before[key])

    def test_blade_contact_follows_actor_and_cleanup_preserves_foreign_state(self):
        art=self.inventory_artifact()
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x21
        _,ram,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        ram[0xD1F]=0xC0;ram[0xD0F]=0xC0;ram[0xF6]=0x80
        for px,py,allowed in ((0x878,0xA90,False),(0x8B8,0xAD0,True),(0x8B8,0xAB0,False)):
            case=bytearray(ram);T.word(case,0x22,px);T.word(case,0x20,py)
            result,out,before=art.call('D3Prison_BladeMain',x=15,ram=case,p=0x30,db=0x52,d=0)
            self.assertEqual(out[0xF359],2 if allowed else 0)
            for key in ('x','db','d','sp'):self.assertEqual(result['registers'][key],before[key])
            if allowed:
                out[0xC4E]=0x07;out[0x5D]=0x02;out[0x2E4]=0x5A
                _,done,_=art.call('D3Prison_BladeMain',x=15,ram=out,p=0x30,db=0x52,d=0)
                self.assertEqual(done[0xC4E],7);self.assertEqual(done[0x5D],2)
                self.assertEqual(done[0x2E4],0x5A)

    def test_fighter_native_skip_and_removed_fix_control(self):
        art=self.inventory_artifact()
        pc=T.R.N.pc(0x0987AE)
        self.assertEqual(art.image[pc:pc+13],bytes.fromhex('add802f00822c8d2002203ed1b'))
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x11
        _,ram,_=art.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        ram[0xF6]=0x80;T.word(ram,0x22,0x878);T.word(ram,0x20,0xA90)
        _,out,_=art.call('D3Prison_BladeMain',x=15,ram=ram,p=0x30,db=0x52,d=0)
        self.assertEqual(out[0xF70:0xF72],bytes([1,1]))
        # Remove only the two added service calls from the synthetic compiled
        # candidate: sequence05 behavior must reproduce zero fighter refresh.
        image=bytearray(art.image);calls=bytes.fromhex('22c8d2002203ed1b')
        lo=T.R.N.pc(0x528000);hi=T.R.N.pc(0x52A000)
        self.assertEqual(image[lo:hi].count(calls),1)
        at=image.index(calls,lo,hi);image[at:at+8]=bytes([0xEA])*8
        (art.dir/'probe.sfc').write_bytes(image)
        try:
            _,control,_=art.call('D3Prison_BladeMain',x=15,ram=ram,p=0x30,db=0x52,d=0)
            self.assertEqual(control[0xF70:0xF72],bytes([0,0]))
            self.assertEqual(control[0xF359],1,'control still reclaims inventory')
        finally:(art.dir/'probe.sfc').write_bytes(art.image)
        # Unmarked ordinary fighter receipts still follow the native skip.
        plain=bytearray(65536);plain[0x2E9]=2
        _,ordinary,_=art.call(0x0799AD,x=3,y=0,ram=plain,p=0x30,db=0,d=0)
        self.assertEqual(ordinary[0xF70:0xF72],bytes([0,0]))

    def test_escape_only_at_actual_outward_room55_loader(self):
        for enabled in (0,1):
            extra = f'''
!ENABLE_D3_PRISON_SEQUENCE = {enabled}
!ENABLE_D3_PRISON_CELL65 = 0
!CastleAmbush_HasBeenCaptured = 1
!CastleAmbush_HasEscaped = 2
!Spawn_Sanctuary = 1
CastleAmbushFlags = $7EF306
SpawnPoint = $7EF3C8
org $348000
incsrc "{T.R.ROOT / 'Dungeons/prison_escape.asm'}"
org $028000
Caller: JSR $E4A3 : RTL
'''
            # Actual PHB/PHK/PLB and displaced stores. The bounded caller-tail
            # fixture then restores DBR/returns through the original JSR owner.
            art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0},
                extra_source=extra,
                image_updates=[(0x02E4A3,bytes.fromhex('8b4bab641b9c5804ab60'))])
            self.addCleanup(art.close)
            self.assertEqual(art.proc.returncode,0,art.proc.stdout+art.proc.stderr)
            cases=[{}, {'room':0x155}, {'room':0x65}, {'room':0x54}, {'room':5},
                   {'module':7}, {'module':0xA}, {'submodule':1}, {'indoor':0},
                   {'dungeon':2}, {'flags':0}, {'flags':2}, {'flags':3}, {'flags':0xA5}]
            for changes in cases:
                values=dict(room=0x55,module=8,submodule=0,indoor=1,dungeon=0x10,flags=1)
                values.update(changes)
                ram=bytearray((i*37+19)&255 for i in range(65536))
                T.word(ram,0xA0,values['room'])
                for at,key in ((0x10,'module'),(0x11,'submodule'),(0x1B,'indoor'),
                               (0x40C,'dungeon'),(0xF306,'flags')):ram[at]=values[key]
                ram[0xF3C8]=2
                result,out,before=art.call('Caller',a=0xAB5A,x=0x5A,y=0x42,p=0xB5,db=0x30,d=0,ram=ram)
                for key in ('a','x','y','db','d','sp'):
                    self.assertEqual(result['registers'][key],before[key],(key,enabled,changes))
                # Native PLB restores incoming DB30 and sets N/Z from that byte.
                self.assertEqual(result['registers']['p'],before['p'] & ~0x82)
                expected=bytearray(ram);expected[0x1B]=0;expected[0x458]=0
                commit=enabled and all(values[k]==v for k,v in
                    dict(room=0x55,module=8,submodule=0,indoor=1,dungeon=0x10).items()) and values['flags']&3==1
                if commit:expected[0xF306]|=2;expected[0xF3C8]=1
                self.assertEqual(out[:0x1FE0],expected[:0x1FE0],(enabled,changes))
                self.assertEqual(out[0x2000:],expected[0x2000:],(enabled,changes))

    def build(self, enabled=1):
        source = f'''
!ENABLE_D3_PRISON_SEQUENCE = 1
!ENABLE_D3_PRISON_CELL65 = {enabled}
!CastleAmbush_HasBeenCaptured = 1
!CastleAmbush_HasEscaped = 2
CastleAmbushFlags = $7EF306
!CastleAmbush_BladeReclaimed = 8
!CastleAmbush_SwordMask = $70
!CastleAmbush_AmbushPending = 4
Sword = $7EF359
org $348000
incsrc "{T.R.ROOT / 'Dungeons/d3_prison_inventory.asm'}"
incsrc "{T.R.ROOT / 'Dungeons/d3_prison_cell65.asm'}"
'''
        art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED': 0},
            extra_source=source,
            image_updates=[(0x02DADB, bytes.fromhex('a980854585446b'))])
        self.addCleanup(art.close)
        self.assertEqual(art.proc.returncode, 0, art.proc.stdout+art.proc.stderr)
        return art

    def invoke(self, art, flags=1, module=5, entrance=0x32):
        ram = bytearray((i*37+19)&255 for i in range(65536))
        ram[0x10] = module
        ram[0xF306] = flags
        T.word(ram, 0x10E, entrance)
        result, out, before = art.call(0x02DADB, a=0xAB5A, x=0xCAFE, y=0xBEEF,
                                    p=0x65, db=2, d=0, ram=ram)
        registers = result['registers']
        for key in ('x', 'y', 'db', 'd', 'sp'):
            self.assertEqual(registers[key], before[key], key)
        self.assertEqual(registers['a'], 0xAB80, 'including hidden accumulator B')
        self.assertEqual(registers['p'], (before['p'] & ~0x82) | 0x80)
        self.assertEqual(out[0x44:0x46], b'\x80\x80', 'original hook and caller tail')
        self.assertEqual(out[0xF000:], ram[0xF000:], 'no SRAM/inventory changes')
        return ram, out

    def test_active_capture_applies_whole_proven_profile(self):
        art = self.build()
        expected_words = {
            0xA0:0x65, 0x48E:0x65, 0x20:0xD18, 0x22:0xAD0,
            0xE8:0xCD0, 0xE6:0xCD0, 0x122:0xCD0, 0x124:0xCD0,
            0xE2:0xA58, 0xE0:0xA58, 0x11E:0xA58, 0x120:0xA58,
            0x608:0xA00, 0x60A:0xA00, 0x60C:0xA00,
            0x618:0x147, 0x61A:0x149, 0x61C:0xD7, 0x61E:0xD9,
            0xEC:0x1F8, 0x696:0x1DEE, 0x698:0, 0x610:0, 0x614:0,
            0x4AA:0, 0x612:0x110, 0x616:0x100,
            0x600:0xD00, 0x602:0xC00, 0x604:0xD10, 0x606:0xD10, 0x60E:0xB00}
        expected_bytes = {0x2F:0,0xA4:0,0x6C:0,0xEE:0,0x476:0,0xA9:0,
                          0xA6:2,0xA7:2,0xAA:2,0xAA1:2,0x132:0x10,0x40C:0x10}
        for flags in (1, 0x81, 0xA5):
            with self.subTest(flags=flags):
                _, out = self.invoke(art, flags=flags)
                for at,value in expected_words.items():
                    self.assertEqual(int.from_bytes(out[at:at+2], 'little'), value, hex(at))
                for at,value in expected_bytes.items():
                    self.assertEqual(out[at], value, hex(at))

    def test_ordinary_escaped_other_entrances_and_disabled_are_native(self):
        for enabled in (0,1):
            art = self.build(enabled)
            for flags in (0,1,2,3,0xA4,0xA7):
                for module,entrance in ((5,0x32),(6,0x32),(5,0x31),(5,0x132)):
                    if enabled and flags & 3 == 1 and module == 5 and entrance == 0x32:
                        continue
                    with self.subTest(enabled=enabled,flags=flags,module=module,entrance=entrance):
                        ram,out = self.invoke(art, flags, module, entrance)
                        # Stack scratch is caller-owned; all ordinary game state is exact.
                        ram[0x44:0x46] = b'\x80\x80'
                        self.assertEqual(out[:0x1FE0], ram[:0x1FE0])
                        self.assertEqual(out[0x2000:], ram[0x2000:])

    def test_prison_object_slots_preserve_all_eleven_existing_draws(self):
        # Compile the actual handler block, only resolving incbin paths for the
        # existing harness. No replacement renderer or simulated dispatcher.
        path = T.R.ROOT / 'Dungeons/Objects/object_handler.asm'
        source = path.read_text().split('CustomObjectHandler2:', 1)[1].split('\npushpc', 1)[0]
        lines = []
        for line in source.splitlines():
            if 'incbin Data/' in line:
                name = line.split('incbin Data/', 1)[1].strip()
                line = 'incbin "' + str(path.parent / 'Data' / name) + '"'
            lines.append(line)
        artifacts = []
        for enabled in (0,1):
            extra = f'!ENABLE_D3_PRISON_CELL65 = {enabled}\norg $348000\nCustomObjectHandler2:\n'+ '\n'.join(lines)
            art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0}, extra_source=extra)
            self.addCleanup(art.close)
            self.assertEqual(art.proc.returncode,0,art.proc.stdout+art.proc.stderr)
            artifacts.append(art)

        def draw(art, slot):
            ram = bytearray(65536)
            T.word(ram, 0xB2, slot>>2); T.word(ram,0xB4,slot&3)
            ram[0xBF:0xC2] = bytes.fromhex('00407e')
            result,out,before = art.call('CustomObjectHandler2',a=0x1234,x=0xBEEF,y=0,p=0x05,db=2,d=0,ram=ram)
            for key in ('x','db','d','sp'):
                self.assertEqual(result['registers'][key], before[key])
            self.assertEqual(result['registers']['p'] & 0x30, 0)
            return out[0x4000:0x6000]

        for slot in range(11):
            self.assertEqual(draw(artifacts[0],slot),draw(artifacts[1],slot),f'old slot {slot:02X}')
        for slot,name in ((11,'minish_stump.bin'),(12,'minish_wall_hole.bin')):
            asset = (path.parent/'Data'/name).read_bytes()
            expected = bytearray(0x2000); cursor=0;origin=0
            while True:
                command=int.from_bytes(asset[cursor:cursor+2],'little');cursor+=2
                if command==0:break
                count=command&31
                for i in range(count):
                    word=asset[cursor:cursor+2];cursor+=2
                    if word!=b'\0\0':expected[origin+i*2:origin+i*2+2]=word
                origin+=command>>8
            self.assertEqual(cursor,len(asset))
            self.assertEqual(draw(artifacts[1],slot),expected,name)


@unittest.skipUnless(T.R.ASSEMBLER, 'Asar required')
class PrisonIncludeOrderTest(unittest.TestCase):
    """Compile the production include order/configuration, without ZS game hooks."""
    def assemble_order(self, disabled=0, all_off=0, callback=1, paired=1,
                       restore_old_guard=False):
        main = (T.R.ROOT/'Oracle_main.asm').read_text()
        block = main.split('; ZSCustomOverworld operates outside Oracle namespace (global scope)\n', 1)[1]
        block = block.split('; Relocated graphics sheet pointer table', 1)[0]
        zs = (T.R.ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        initial = re.search(r'^!Func02A5D3 = .*$', zs, re.M).group(0)
        initial = initial.replace('$01', f'${callback:02X}')
        override = 'if !AllOff == 1' + zs.split('if !AllOff == 1', 1)[1].split('endif', 1)[0] + 'endif'
        config = initial + f'\n!AllOff = {all_off}\n' + override
        block = re.sub(r'  incsrc\s+"Overworld/ZSCustomOverworld.asm"', config, block)
        block = re.sub(r'^  %log_end.*$', '', block, flags=re.M)
        early = 'assert !Func02A5D3 == 1, "old early guard"\n' if restore_old_guard else ''
        # The production prison include must not reference a later ZS define.
        prison = (T.R.ROOT/'Dungeons/prison_sequence.asm').read_text()
        self.assertNotIn('!Func02A5D3', prison)
        art = T.Artifact([], overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED': 0},
            extra_source=f'!ENABLE_D3_PRISON_SEQUENCE = 1\n!ENABLE_D3_PRISON_CELL65 = {paired}\n!ENABLE_D3_PRISON_ARMORY = 0\n!DISABLE_OVERWORLD = {disabled}\n' + early + block)
        self.addCleanup(art.close)
        return art.proc

    def test_actual_order_accepts_enabled_and_rejects_missing_callbacks(self):
        for arguments, expected in (({}, None), ({'callback': 0}, 'normal overworld callback'),
                ({'all_off': 1}, 'normal overworld callback'),
                ({'disabled': 1}, 'requires ZSCustomOverworld'),
                ({'disabled': 1, 'paired': 0}, None),
                ({'restore_old_guard': True}, "Define 'Func02A5D3' wasn't found")):
            with self.subTest(arguments=arguments):
                proc = self.assemble_order(**arguments)
                output = proc.stdout + proc.stderr
                if expected is None:
                    self.assertEqual(proc.returncode, 0, output)
                else:
                    self.assertNotEqual(proc.returncode, 0, output)
                    self.assertIn(expected, output)
