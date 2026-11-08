; =========================================================
; Per-dungeon wall-profile selector (flag !ENABLE_WALL_PROFILE_SELECTOR, default 0)
;
; Remaps the data offset of 30 wall object classes per room. Rooms are bound
; to profiles per dungeon / room group in Dungeons/Data/wall_profiles/
; wall_profiles.json (Scripts/Generate/gen_wall_profiles.py build).
; Method: WRAM window. The hook copies the selected span into
; WallSel_Buffer ($7E1EA9, 32 bytes) and returns the offset that makes
; the vanilla drawer read `$9B52+n,X` from that buffer:
;   $00:9B52 + $8357 = $01:1EA9 (abs,X carries into bank $01),
;   and $01:0000-$1FFF mirrors WRAM $7E:0000-$1FFF.
; No DBR change, no stack splice, no DP scratch.
;
; Hook sites (both 4-byte LDA.l table,X, followed by TAX / LDY $08 /
; JMP ($000E)):
;   H1 $01:8979  LDA.l $018000,X  subtype 1, X = obj*2  ($00-$1EE)
;   H2 $01:89AE  LDA.l $0183F0,X  subtype 2, X = (obj&$3F)*2 ($00-$7E)
; Entry at both: M=16 X=16 DBR=$00 DP=$0000 C=0.
; Exit: A = data offset relative to $9B52; P restored by PLP.
; Clobbers A/X/Y only; caller overwrites X (TAX) and Y (LDY $08).
; Room ID source: $A0 (never $048E; it is copied after LoadRoom).
;
; A profile may also route graphics (blockset row, palette, slot-3 tile
; types); see the Graphics route block below and Dungeons/wall_profile_gfx.asm.
;
; Included from Dungeons/dungeons.asm only when
; !ENABLE_WALL_PROFILE_SELECTOR == 1. Flag 0 = no bytes emitted.
; Code and tables own the fixed slot $44E000-$44FFFF (end of the Docks
; bank, clear of the $44C000 Docks map streams), so enabling the flag shifts no bank $2C stream code and the
; per-dungeon tables can grow without touching the $2CF700 tail.
; All data reads are LDA.l; the only .w store relies on DBR=$00.
; =========================================================

!WallSel_BufferOffset = ((WallSel_Buffer&$FFFF)+$10000-$9B52)&$FFFF

assert (WallSel_Buffer&$FFFF)+$20 <= $2000, "WallSel_Buffer must stay in the $0000-$1FFF WRAM mirror"
assert WallSel_Buffer == $7E1EA9, "WallSel_Buffer moved; recheck drawer read window"
assert !WallSel_BufferOffset == $8357, "WallSel_Buffer offset changed; recheck drawer read window"

; ---- vanilla hook-site bytes (fail the build if anything moved) ----
assert read1($018979) == $BF && read2($01897A) == $8000 && read1($01897C) == $01, "H1 site changed"
assert read1($01897D) == $AA, "H1 TAX changed"
assert read1($0189AE) == $BF && read2($0189AF) == $83F0 && read1($0189B1) == $01, "H2 site changed"
assert read1($0189B2) == $AA, "H2 TAX changed"

pushpc
org $018979 ; @hook module=Dungeons name=WallSel_Sub1 kind=jsl target=WallSel_Sub1 expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL WallSel_Sub1
org $0189AE ; @hook module=Dungeons name=WallSel_Sub2 kind=jsl target=WallSel_Sub2 expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL WallSel_Sub2
pullpc

pushpc
org $44E000
; Tables first: the generated file defines !WALLSEL_PROFILE_COUNT,
; and asar defines must precede use.
incsrc "Dungeons/Data/wall_profiles/wall_profiles.asm"

; ---------------------------------------------------------
; H1: subtype 1. X = obj*2.
WallSel_Sub1:
{
  PHP
  LDA.l $018000,X : PHA          ; vanilla offset
  TXA : LSR : TAX
  LDA.l WallSel_Sub1Class,X
  BRA WallSel_Common
}

; H2: subtype 2. X = (obj&$3F)*2.
WallSel_Sub2:
{
  PHP
  LDA.l $0183F0,X : PHA          ; vanilla offset
  TXA : LSR : TAX
  LDA.l WallSel_Sub2Class,X
  ; fall through
}

; Stack here: [vanillaA:2][P:1][RTL:3]
WallSel_Common:
{
  AND.w #$00FF : CMP.w #$00FF : BEQ .fallback
  ASL : PHA                      ; [class*2]
  LDA.b $A0 : CMP.w #$0128 : BCS .fallback_pop
  TAX
  LDA.l WallSel_RoomProfile,X : AND.w #$00FF : BEQ .fallback_pop
  CMP.w #!WALLSEL_PROFILE_COUNT+1 : BCS .fallback_pop
  ASL : TAX
  LDA.l WallSel_ProfileBase-2,X
  CLC : ADC 1,S : TAX            ; slot*2
  LDA.l WallSel_SlotSrc,X : CMP.w #$FFFF : BEQ .fallback_pop
  PHA
  LDA.l WallSel_SlotLen,X : TAY  ; span-2
  PLX                            ; src offset of last word
.copy
  ; DBR=$00 here (same contract the vanilla drawers rely on), so .w
  ; writes $00:1EA9+Y = WRAM $7E:1EA9+Y.
  LDA.l WallSel_Data,X : STA.w WallSel_Buffer&$FFFF,Y
  DEX : DEX : DEY : DEY : BPL .copy
  PLA : PLA                      ; drop class*2 and vanilla A
  LDA.w #!WallSel_BufferOffset
  PLP
  RTL

.fallback_pop
  PLA                            ; drop class*2
.fallback
  PLA                            ; vanilla offset
  PLP
  RTL
}


; =========================================================
; Graphics route (generated !WALLSEL_GFX == 1 only).
; A profile with a gfx route swaps the room header's blockset ($0AA2)
; and BG palette ($0AB6) for a private blockset row and palette, so no
; room that shares the original blockset/palette changes.
;   blockset row !WALLSEL_GFX_BLOCKSET = row !WALLSEL_GFX_MAIN with
;     slot 3 -> sheet !WALLSEL_GFX_SHEET (Dungeons/wall_profile_gfx.asm)
;   palette !WALLSEL_GFX_PALETTE = copy of !WALLSEL_GFX_PALETTE_SRC with
;     !WALLSEL_GFX_PAL_COUNT words replaced from word !WALLSEL_GFX_PAL_FIRST
;   collision: chars $140-$1BF use group !WALLSEL_GFX_MAIN; chars
;     $C0-$FF (slot 3) use WallSel_Slot3TileTypes, and every other room
;     restores the vanilla UnderworldTileTypes+$C0 bytes.
; =========================================================
if !WALLSEL_GFX == 1

; H3 $01:B641: INY : LDA [$0D],Y : STA $0AA2 (header blockset byte).
; Entry: M=8 X=16, Y = header index. $0AB6 was stored at $01B629.
; Exit: M=8 X=16, Y advanced by one (as vanilla), X preserved.
WallSel_HeaderGfx:
{
  INY : LDA.b [$0D],Y : STA.l $7E0AA2
  PHX : PHP
  REP #$30
  LDA.b $A0 : CMP.w #$0128 : BCS .done
  TAX
  LDA.l WallSel_RoomProfile,X : AND.w #$00FF : BEQ .done
  CMP.w #!WALLSEL_PROFILE_COUNT+1 : BCS .done
  TAX
  SEP #$20
  LDA.l WallSel_ProfileBlockset-1,X : CMP.b #$FF : BEQ .done
  STA.l $7E0AA2
  LDA.l WallSel_ProfilePalette-1,X : STA.l $7E0AB6
.done
  PLP : PLX
  RTL
}

; Replaces the JSL at $0E942A (Underworld_LoadCustomTileTypes), which
; runs on every room load. Exit: M=8 X=8, like Dungeon_LoadCustomTileAttr.
WallSel_LoadTileAttr:
{
  SEP #$20
  LDA.l $7E0AA2 : CMP.b #!WALLSEL_GFX_BLOCKSET : BNE .plain
  LDA.b #!WALLSEL_GFX_MAIN : STA.l $7E0AA2
  JSL Dungeon_LoadCustomTileAttr ; exits M=8 X=8
  LDA.b #!WALLSEL_GFX_BLOCKSET : STA.l $7E0AA2
  REP #$30
  LDX.w #$003E
.copy
  LDA.l WallSel_Slot3TileTypes,X : STA.l $7EFEC0,X
  DEX : DEX : BPL .copy
  SEP #$30
  RTL
.plain
  JSL Dungeon_LoadCustomTileAttr
  REP #$30
  LDX.w #$003E
.restore
  LDA.l read3($0E97F6),X : STA.l $7EFEC0,X
  DEX : DEX : BPL .restore
  SEP #$30
  RTL
}

assert read1($0E97F5) == $BF && read1($0E97F9) == $9F && read3($0E97FA) == $7EFEC0, "LoadDefaultTileTypes slot-3 copy moved"

; ---- vanilla bytes / unused-slot guards ----
; asar math runs left to right without precedence: keep the parentheses.
assert read1($01B641) == $C8 && read2($01B642) == $0DB7 && read1($01B644) == $8D && read2($01B645) == $0AA2, "H3 header blockset site changed"
assert read1($00DD97+(!WALLSEL_GFX_BLOCKSET*4)) == $09 && read1($00DD97+(!WALLSEL_GFX_BLOCKSET*4)+1) == $00 && read1($00DD97+(!WALLSEL_GFX_BLOCKSET*4)+2) == $24 && read1($00DD97+(!WALLSEL_GFX_BLOCKSET*4)+3) == $1B, "gfx blockset row is not the vanilla spare row"
assert read2($1BEC4B+!WALLSEL_GFX_PALETTE) == $0D5C && read2($1BEC4B+!WALLSEL_GFX_PALETTE_SRC) == $02D0, "UW palette offsets changed"
; No room header may already use the private blockset or palette.
!wsg_r = 0
while !wsg_r < $128
  assert read1(($220000|read2($228000+(!wsg_r*2)))+2) != !WALLSEL_GFX_BLOCKSET, "a room header already uses the gfx blockset row"
  assert read1($0ED460+(read1(($220000|read2($228000+(!wsg_r*2)))+1)*4)) != !WALLSEL_GFX_PALETTE, "a room palette set already uses the gfx palette"
  !wsg_r #= !wsg_r+1
endwhile

pushpc
org $01B641 ; @hook module=Dungeons name=WallSel_HeaderGfx kind=jsl target=WallSel_HeaderGfx expected_m=8 expected_x=16 expected_exit_m=8 expected_exit_x=16
  JSL WallSel_HeaderGfx
  NOP #2

; Private blockset row: slot 3 -> new sheet, slots 4-6 copied from the main row.
assert !WALLSEL_GFX_BLOCKSET == $17 && !WALLSEL_GFX_PALETTE == $26, "org literals below assume blockset $17 / palette $26"
org $00DDF3 ; @hook module=Dungeons kind=data protected_size=4
  db !WALLSEL_GFX_SHEET, read1($00DD97+(!WALLSEL_GFX_MAIN*4)+1), read1($00DD97+(!WALLSEL_GFX_MAIN*4)+2), read1($00DD97+(!WALLSEL_GFX_MAIN*4)+3)

; Private palette: the source palette (90 words) with the profile words
; spliced in at !WALLSEL_GFX_PAL_FIRST, written as one contiguous block.
org $1BE490 ; @hook module=Dungeons kind=data protected_size=180
  !wsg_i = 0
  while !wsg_i < !WALLSEL_GFX_PAL_FIRST
    dw read2($1BD734+$02D0+(!wsg_i*2))
    !wsg_i #= !wsg_i+1
  endwhile
  dw !WALLSEL_GFX_PAL_WORDS
  !wsg_i #= !WALLSEL_GFX_PAL_FIRST+!WALLSEL_GFX_PAL_COUNT
  while !wsg_i < 90
    dw read2($1BD734+$02D0+(!wsg_i*2))
    !wsg_i #= !wsg_i+1
  endwhile
assert pc() == $1BE490+180, "gfx palette must be exactly 90 words"
pullpc

else

WallSel_LoadTileAttr:
  JML Dungeon_LoadCustomTileAttr

endif

assert WallSel_Data_End-WallSel_Data <= $8000, "WallSel data too large"
assert (WallSel_Data&$FF0000) == ((WallSel_Data_End-1)&$FF0000), "WallSel_Data crosses a bank"
if !WALLSEL_GFX == 1
  assert pc() <= $44F000, "WallSel code reached the gfx sheet stream at $44F000"
else
  assert pc() <= $450000, "WallSel exceeded its 8 KiB slot $44E000-$44FFFF"
endif
print "End of wall_profile_selector.asm  ", pc
pullpc
