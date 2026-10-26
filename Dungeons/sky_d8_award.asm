; =========================================================
; Sky (D8) essence award — crystal ceremony, then dungeon exit
;
; Identity is the full room word $A1:$A0 == $0096 (Sky boss room). Sky
; shares dungeon ID $10 with D3 (entrance $29), so $040C never selects it.
; The Sky essence is Crystals bit 7 (!Crystal_D8_Sky); bits 0-6 are kept.
; Room $0196 and every other room take the legacy paths below; with
; !ENABLE_D7_FARORE_RESCUE_SEQUENCE the D7 ($040C == $18) maiden paths go to
; d7_farore_rescue.asm.
;
; Legacy prize index guard: RoomTagPrizeChecks ($02A1A4) and the heart-tag
; .prizes table ($01C6FC) have 13 entries, $040C/2 = $00-$0C. Larger
; indices (Fortress $1A reads code byte $AD at $02A1B1) are refused before
; any table read: no spawn, no door, no crystal write, no Module07_18.
;
; Ceremony: the native fall/receipt/rise, palette and music lifecycle and
; Module07_18 run unchanged. Sky skips only the room lookups that do not
; list $0096, the maiden's follower graphics/SRAM write, her draw and her
; three speeches with the D3 map-icon update. The invisible maiden keeps
; driving the crystal growth stages, then stage 8 (KickOutOfDungeon) calls
; PrepareDungeonExitFromBossFight, whose Sky exit is room $0090.
;
; Every gateway is reached by JML from a vanilla site, so the native return
; address stays on the stack and DBR/D are the caller's (D=$0000, DBR in a
; bank that mirrors WRAM $0000-$1FFF). WRAM operands match the native code
; at each site; Crystals is read with long addressing.
; =========================================================

pushpc

; RoomTag_PrizeTriggerDoorDoor: LDA.w $040C : LSR A : TAX
assert read4($01C508) == $4A040CAD, "PrizeTriggerDoorDoor entry moved"
assert read1($01C50C) == $AA, "PrizeTriggerDoorDoor entry moved"
assert read4($01C50D) == $7EF3CAAF, "PrizeTriggerDoorDoor world check moved"
assert read2($01C529) == $30C2, "PrizeTriggerDoorDoor .open_door moved"
assert read2($01C53E) == $30E2, "PrizeTriggerDoorDoor .exit moved"
assert read1($01C540) == $60, "PrizeTriggerDoorDoor .exit moved"
org $01C508 : JML SkyD8_PrizeTriggerDoor ; @hook module=Dungeons name=SkyD8_PrizeTriggerDoor kind=jml target=SkyD8_PrizeTriggerDoor expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $01C50D

; RoomTag_GetHeartForPrize: LDA.w $0403 : AND.b #$80
assert read4($01C709) == $290403AD, "GetHeartForPrize entry moved"
assert read1($01C70D) == $80, "GetHeartForPrize entry moved"
assert read2($01C70E) == $3DF0, "GetHeartForPrize heart branch moved"
assert read1($01C742) == $22, "GetHeartForPrize spawn JSL moved"
assert read4($01C749) == $AE740EA6, "GetHeartForPrize .delete_tag moved"
assert read1($01C74D) == $60, "GetHeartForPrize .exit moved"
org $01C709 : JML SkyD8_HeartPrizeTag ; @hook module=Dungeons name=SkyD8_HeartPrizeTag kind=jml target=SkyD8_HeartPrizeTag expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $01C70E

; Ancilla3E_RisingCrystal collector: PHX at $08CC3A, then
; LDA.w $040C : LSR A : TAX. $08CC48 (crystal store) stays with its owner.
assert read1($08CC3A) == $DA, "Rising crystal PHX moved"
assert read4($08CC3B) == $4A040CAD, "Rising crystal collector moved"
assert read1($08CC3F) == $AA, "Rising crystal collector moved"
assert read4($08CC40) == $7EF37AAF, "Rising crystal Crystals load moved"
assert read4($08CC44) == $02A1A41F, "Rising crystal mask OR moved"
assert read1($08CC48) == $8F || read1($08CC48) == $22, "Rising crystal store moved"
assert read4($08C453) == $9C0C4A9E, "Item receipt delete tail moved"
assert read2($08C457) == $0FC1, "Item receipt delete tail moved"
assert read1($08C459) == $60, "Item receipt delete tail moved"
org $08CC3B : JML SkyD8_CrystalCollector ; @hook module=Dungeons name=SkyD8_CrystalCollector kind=jml target=SkyD8_CrystalCollector expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $08CC40

; BuildCrystalCutsceneTilemap, after REP #$20: LDX.b #$0E : LDA.b $A0
assert read2($029895) == $20C2, "Crystal tilemap REP moved"
assert read4($029897) == $A0A50EA2, "Crystal tilemap search moved"
assert read2($02989B) == $CACA, "Crystal tilemap search loop moved"
assert read2($0298A7) == $0885, "Crystal tilemap offset store moved"
org $029897 : JML SkyD8_CrystalTilemap ; @hook module=Dungeons name=SkyD8_CrystalTilemap kind=jml target=SkyD8_CrystalTilemap expected_m=16 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=4
assert pc() == $02989B

; PrepareDungeonExitFromBossFight: LDX.b #$0C : LDA.b $A0
assert read4($00F959) == $A0A50CA2, "Boss exit search moved"
assert read1($00F95D) == $CA, "Boss exit search loop moved"
assert read2($00F96A) == $20C9, "Boss exit Agahnim check moved"
assert read2($02DD8A+$84) == $0090, "Exit entry $42 is no longer room $0090"
assert read1($02DE28+$42) == $7A, "Room $0090 exit no longer leads to area $7A"
org $00F959 : JML SkyD8_BossExit ; @hook module=Dungeons name=SkyD8_BossExit kind=jml target=SkyD8_BossExit expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
assert pc() == $00F95D

; CrystalCutscene_SpawnMaiden: LDA.w $040C : CMP.b #$18
assert read4($1ECD8B) == $C9040CAD, "Maiden follower check moved"
assert read1($1ECD8F) == $18, "Maiden follower check moved"
assert read2($1ECD90) == $09D0, "Maiden follower branch moved"
assert read2($1ECDAD) == $289C, "Maiden offset setup moved"
org $1ECD8B : JML SkyD8_MaidenFollowerGfx ; @hook module=Dungeons name=SkyD8_MaidenFollowerGfx kind=jml target=SkyD8_MaidenFollowerGfx expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $1ECD90

; Sprite_AB_CrystalMaiden: LDA.w $0D80,X : CMP.b #$03
assert read4($1ECE1B) == $C90D80BD, "Maiden draw check moved"
assert read1($1ECE1F) == $03, "Maiden draw check moved"
assert read2($1ECE20) == $0490, "Maiden draw branch moved"
assert read2($1ECE26) == $01A9, "Maiden .invisible moved"
org $1ECE1B : JML SkyD8_MaidenDraw ; @hook module=Dungeons name=SkyD8_MaidenDraw kind=jml target=SkyD8_MaidenDraw expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $1ECE20

; CrystalMaiden_GiveSpeech: LDA.w $040C : SEC
assert read4($1ECECE) == $38040CAD, "Maiden speech index moved"
assert read2($1ECED2) == $0AE9, "Maiden speech index moved"
assert read1($1ECF17) == $60, "Maiden speech exit moved"
org $1ECECE : JML SkyD8_MaidenSpeech ; @hook module=Dungeons name=SkyD8_MaidenSpeech kind=jml target=SkyD8_MaidenSpeech expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
assert pc() == $1ECED2

; Vanilla routines d7_farore_rescue.asm calls (kept here so CI seeds them).
if !ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1
  assert read1($00E33A) == $6B, "Bank $00 RTL trampoline moved"
  assert read1($00E772) == $B9 || read1($00E772) == $5C, "Decompress_sprite_arbitrary moved"
  assert read2($00DFB8) == $0C84, "Do3To4Low16Bit moved"
  assert read1($00DEFF) == $AE, "Graphics_IncrementalVRAMUpload moved"
  assert read2($1BECC5) == $31C2, "Palettes_Load_SpriteAux1 moved"
  assert read1($1ECF07) == $AF, "Maiden speech MapIcon tail moved"
endif

pullpc

; Entry $01C508 (JSR from the room-tag dispatcher), M=8 X=8, $0E = tag slot.
; Sky: open (.open_door $01C529) only once the Sky essence is owned.
; Exit: $01C50D (legacy, X = $040C/2), $01C529 or $01C53E (SEP #$30 : RTS).
SkyD8_PrizeTriggerDoor:
{
  LDA.b $A1 : BNE .not_sky
  LDA.b $A0 : CMP.b #$96 : BNE .not_sky
    LDA.l Crystals : AND.b #!Crystal_D8_Sky : BEQ .exit
    JML $01C529
  .not_sky
  LDA.w $040C : LSR A : CMP.b #$0D : BCS .exit
  LDA.w $040C : LSR A : TAX
  JML $01C50D
  .exit
  JML $01C53E
}

; Entry $01C709 (JSR from the room-tag dispatcher), M=8 X=8, $0E = tag slot.
; Sky keeps the boss-heart requirement, reads Crystals in both worlds and
; spawns falling crystal type $06 through the existing $01C742 JSL with the
; native PHA of $0E (pulled at $01C746). Owned: delete the tag, no spawn.
; Exit: $01C70E (legacy, A/Z from LDA $0403 : AND #$80), $01C742, $01C749
; (delete tag : RTS) or $01C74D (RTS).
SkyD8_HeartPrizeTag:
{
  LDA.b $A1 : BNE .not_sky
  LDA.b $A0 : CMP.b #$96 : BNE .not_sky
    LDA.w $0403 : AND.b #$80 : BEQ .exit
    LDA.l Crystals : AND.b #!Crystal_D8_Sky : BNE .delete_tag
    LDA.b #$80 : STA.w $04C2
    LDA.b $0E : PHA
    LDA.b #$06
    JML $01C742
  .not_sky
  LDA.w $040C : LSR A : CMP.b #$0D : BCS .exit
  LDA.w $0403 : AND.b #$80
  JML $01C70E
  .delete_tag
  JML $01C749
  .exit
  JML $01C74D
}

; Entry $08CC3B, M=8 X=8, $11 == 0, the ancilla index is on the stack from
; the PHX at $08CC3A (pulled at $08CC81 on the native path).
; Sky: A = Crystals | !Crystal_D8_Sky, then the $08CC48 store and
; Module07_18 run natively. Legacy: $08CC40 with X = $040C/2.
; Refused (Sky already owned, or a legacy index past the table): PLX, end
; the receipt the way native receipts do ($08C423-$08C43B) plus the $02E4
; release Module16_04 performs, then $08C453 deletes the ancilla, clears
; $0FC1 and returns. Crystals, $11 and $B0 are not written.
SkyD8_CrystalCollector:
{
  LDA.b $A1 : BNE .not_sky
  LDA.b $A0 : CMP.b #$96 : BNE .not_sky
    LDA.l Crystals : AND.b #!Crystal_D8_Sky : BNE .refuse
    LDA.w $040C : LSR A : TAX
    LDA.l Crystals : ORA.b #!Crystal_D8_Sky
    JML $08CC48
  .not_sky
  LDA.w $040C : LSR A : CMP.b #$0D : BCS .refuse
  LDA.w $040C : LSR A : TAX
  JML $08CC40
  .refuse
  PLX
  LDY.b #$00
  LDA.w $0345 : BEQ .not_in_water
    LDY.b #$04
  .not_in_water
  STY.b $5D
  STZ.w $02D8 : STZ.w $02DA : STZ.w $037B
  STZ.w $02E9 : STZ.w $02E4
  JML $08C453
}

; Entry $029897, M=16 X=8. CrystalBossRooms has no $0096 entry, so Sky
; does not search it. The offset is a source-backed candidate: in the
; 64x64 BG1 tilemap it places the 8x8-tile crystal block at the center of
; Link's quadrant ($21/$23 bit 0), the quadrant CrystalCutscene_SpawnMaiden
; uses for the maiden: $0618 + $0040 (right) + $1000 (bottom). Native
; entries $0658/$1618/$1658 are members of this family. That is tilemap
; layout only; how the crystal actually appears in room $0096 is not
; natively qualified until root screenshots it in all four quadrants.
; Exit: $0298A7 (STA $08) or $02989B (legacy, X=$0E, A=$A0).
SkyD8_CrystalTilemap:
{
  LDA.b $A0 : CMP.w #$0096 : BNE .legacy
    LDA.w #$0618 : STA.b $08
    LDA.b $23 : AND.w #$0001 : BEQ .left_half
      LDA.b $08 : ORA.w #$0040 : STA.b $08
    .left_half
    LDA.b $21 : AND.w #$0001 : BEQ .top_half
      LDA.b $08 : ORA.w #$1000 : STA.b $08
    .top_half
    LDA.b $08
    JML $0298A7
  .legacy
  LDX.b #$0E
  LDA.b $A0
  JML $02989B
}

; Entry $00F959 (JSL caller's return on the stack), M=8 X=8, after the
; native death-count, key and room-flag saves. Boss-room list $00F92D has no
; $96, so Sky does not search it: exit room $90 (entrance $29's room; exit
; entry $42 -> area $7A). X only feeds CPX #$03 at $00F9BF; $04 selects
; the crystal victory (module $16, song fade).
; Exit: $00F96A (A = $A0 = $90) or $00F95D (legacy, X=$0C, A=$A0).
SkyD8_BossExit:
{
  LDA.b $A1 : BNE .legacy
  LDA.b $A0 : CMP.b #$96 : BNE .legacy
    LDA.b #$90 : STA.b $A0
    LDX.b #$04
    JML $00F96A
  .legacy
  LDX.b #$0C
  LDA.b $A0
  JML $00F95D
}

; Entry $1ECD8B, M=8 X=8, Y = maiden slot (kept).
; Sky: no maiden follower graphics and no $7EF3CC write.
; Exit: $1ECDAD or $1ECD90 (legacy, Z from CMP $040C,#$18).
SkyD8_MaidenFollowerGfx:
{
  LDA.b $A1 : BNE .legacy
  LDA.b $A0 : CMP.b #$96 : BNE .legacy
    JML $1ECDAD
  .legacy
if !ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1
  LDA.w $040C : CMP.b #$18 : BNE +
    JML D7Farore_Spawn
  +
endif
  LDA.w $040C : CMP.b #$18
  JML $1ECD90
}

; Entry $1ECE1B, M=8 X=8, X = maiden slot. Sky: never draw the maiden.
; Exit: $1ECE26 (.invisible) or $1ECE20 (legacy, C from CMP $0D80,X,#$03).
SkyD8_MaidenDraw:
{
  LDA.b $A1 : BNE .legacy
  LDA.b $A0 : CMP.b #$96 : BNE .legacy
    JML $1ECE26
  .legacy
if !ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1
  LDA.w $040C : CMP.b #$18 : BNE +
    JML D7Farore_Draw
  +
endif
  LDA.w $0D80, X : CMP.b #$03
  JML $1ECE20
}

; Entry $1ECECE (cutscene stage 5), M=8 X=8, X = maiden slot.
; Sky: no message and no MapIcon write; next frame runs stage 8
; (KickOutOfDungeon). Exit: $1ECF17 (RTS) or $1ECED2 (legacy, A=$040C, C=1).
SkyD8_MaidenSpeech:
{
  LDA.b $A1 : BNE .legacy
  LDA.b $A0 : CMP.b #$96 : BNE .legacy
    LDA.b #$08 : STA.w $0D80, X
    JML $1ECF17
  .legacy
if !ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1
  LDA.w $040C : CMP.b #$18 : BNE +
    JML D7Farore_Speech
  +
endif
  LDA.w $040C : SEC
  JML $1ECED2
}

assert pc() <= $2CFD00 ; do not overlap RoomTag_SomariaSocketDoor
