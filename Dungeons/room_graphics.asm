; Maple room graphics profile: the existing room, collision and wake geometry.
;
; Profile contract: room $00F, entrance $68, main/secondary groups $03/$03.
; Eight compressed BG sheets replace the source pointer at the common native
; decompressor. Native conversion, transition buffers and VRAM uploads stay in
; charge. No persistent WRAM, free sheet ID, or per-frame transfer is used.
;
; Normal entrance and Maple's Module06 dream return load all eight sheets.
; Leaving through the exit clears $1B before overworld graphics load. Dream
; destinations change $A0 and their existing DreamRoom_LoadSheets reloads BG.
; A new interior door/stair connection into/out of Maple needs its own proof:
; native room transitions may retain the main group and zero auxiliary slots.
;
; Storage: new bank $45, $458000-$45BFFF (PC $228000-$22BFFF), outside the
; two-MiB editable base and current source emissions. Bank $42 contains Garo; $43 menu icons; $44 docks.
; The full reserved input must be absent/zero; the composed base uses zero padding.
; @source usdasm/bank_00.asm Decompress_background_arbitrary $00E78F
; @source usdasm/bank_1B.asm Palettes_LoadMultiple $1BEF51

pushpc

!MapleGraphicsAllocation = $458000
while !MapleGraphicsAllocation < $45C000
  assert read1(!MapleGraphicsAllocation, $00) == $00, "Maple graphics bank $45 allocation is occupied"
  !MapleGraphicsAllocation #= !MapleGraphicsAllocation+1
endwhile

; Refuse a changed loader/profile rather than replacing an unrelated instruction.
assert read4($00E78F) == $85CF80B9 && read1($00E793) == $CA, "BG decompressor entry moved"
assert read4($1BEF51) == $85001BA9 && read1($1BEF55) == $02, "Palette source-bank setup moved"
assert read2($0F80D0) == $000F && read1($0F9668) == $03, "Maple entrance profile changed"
!MapleGraphicsHeader = (read1($01B5E7)<<16)|read2(read3($01B5DD)+$001E)
assert read1(!MapleGraphicsHeader+2) == $03, "Maple room graphics group changed"

; M=8, X width inherited, DB=$00, D=$0000. Replaces the five-byte source-bank
; load; original JSR/RTS stack stays in bank $00. X/Y/DB/D and incoming P survive.
org $00E78F ; @hook module=Dungeons name=RoomGraphics_BackgroundSource kind=jml target=RoomGraphics_BackgroundSource expected_m=8 expected_exit_m=8
  JML RoomGraphics_BackgroundSource
  NOP
assert pc() == $00E794

; M=16, X=16, D=$0000. The caller already saved destination/count into $04/$06/
; $08. This replaces only LDA #$001B : STA $02 and preserves the native loop.
org $1BEF51 ; @hook module=Dungeons name=RoomGraphics_PaletteSource kind=jsl target=RoomGraphics_PaletteSource expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL RoomGraphics_PaletteSource
  NOP
assert pc() == $1BEF56

org $458000

RoomGraphics_BackgroundSource:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  JSR RoomGraphics_IsMaple : BCC .original

  ; The eight source IDs are distinct in this pinned profile. Matching by ID
  ; works for both full loads and cached/auxiliary transition decompression.
  ; Maple's animated sheets $5C/$5D are not in this list and remain native.
  TYA : AND.w #$00FF
  LDX.w #$0000
  .find_sheet
    CMP.l RoomGraphics_MapleSourceIds, X : BEQ .profile
    INX : INX
    CPX.w #$0010 : BCC .find_sheet

  .original
  PLY : PLX : PLA
  PLP
  LDA.w $CF80, Y : STA.b $CA
  JML $00E794                        ; original high/low pointer loads

  .profile
  LDA.l RoomGraphics_MapleSheetPointers, X : STA.b $C8
  SEP #$20
  LDA.b #RoomGraphics_MapleSheet0>>16 : STA.b $CA
  REP #$20
  PLY : PLX : PLA
  PLP
  JML $00E79E                        ; original decompressor, original return
}

RoomGraphics_PaletteSource:
{
  PHP
  ; All callers of this native site have M/X=16. The shared predicate uses A
  ; only; X/Y, DB, D and the native loop's $04/$06/$08 remain unchanged.
  JSR RoomGraphics_IsMaple : BCC .original
  LDA.b $04 : CMP.w #$0042 : BNE .original
  LDA.b $06 : CMP.w #$000E : BNE .original
  LDA.b $08 : CMP.w #$0005 : BNE .original

  LDA.w #RoomGraphics_MaplePalette : STA.b $00
  PLP
  LDA.w #RoomGraphics_MaplePalette>>16 : STA.b $02
  RTL

  .original
  PLP
  LDA.w #$001B : STA.b $02
  RTL
}

; M=16, any DB; A and carry are output/clobbered, X/Y/D/DB unchanged.
; Absolute-long RAM reads are required: code bank $45 has no low-WRAM mirror.
RoomGraphics_IsMaple:
{
  LDA.l $7E001B : AND.w #$00FF : CMP.w #$0001 : BNE .no
  LDA.l $7E00A0 : CMP.w #$000F : BNE .no
  LDA.l $7E0AA1 : CMP.w #$0303 : BNE .no
  SEC
  RTS
  .no
  CLC
  RTS
}

RoomGraphics_MapleSourceIds:
  dw $0061, $0001, $0013, $0007, $000E, $0023, $001C, $000F
RoomGraphics_MapleSheetPointers:
  dw RoomGraphics_MapleSheet0, RoomGraphics_MapleSheet1
  dw RoomGraphics_MapleSheet2, RoomGraphics_MapleSheet3
  dw RoomGraphics_MapleSheet4, RoomGraphics_MapleSheet5
  dw RoomGraphics_MapleSheet6, RoomGraphics_MapleSheet7

RoomGraphics_MapleSheet0:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_0.lz2"
RoomGraphics_MapleSheet1:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_1.lz2"
RoomGraphics_MapleSheet2:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_2.lz2"
RoomGraphics_MapleSheet3:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_3.lz2"
RoomGraphics_MapleSheet4:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_4.lz2"
RoomGraphics_MapleSheet5:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_5.lz2"
RoomGraphics_MapleSheet6:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_6.lz2"
RoomGraphics_MapleSheet7:
  incbin "../Data/graphics/room_profiles/maple/generated/sheets/slot_7.lz2"

; Six rows x 15 BGR555 colors. Native Palettes_LoadMultiple handles $0AA8 and
; the fade target. Palettes_Load_UnderworldSet then restores its ORIGINAL saved
; source pointer; Palettes_LoadSingle resets source bank $1B for OBJ environment
; colors. The BG profile therefore does not recolor that sprite half-row.
RoomGraphics_MaplePalette:
  incbin "../Data/graphics/room_profiles/maple/generated/palettes/dungeon_main.bin"
RoomGraphics_MaplePaletteEnd:
assert RoomGraphics_MaplePaletteEnd-RoomGraphics_MaplePalette == 180, "Maple palette must contain 90 BGR555 words"
assert pc() <= $45C000, "Maple room graphics exceed bank $45 reservation"

pullpc
