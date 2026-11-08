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
; Pattern words only. Graphics sheets and palettes are not routed per room.
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


assert WallSel_Data_End-WallSel_Data <= $8000, "WallSel data too large"
assert (WallSel_Data&$FF0000) == ((WallSel_Data_End-1)&$FF0000), "WallSel_Data crosses a bank"
assert pc() <= $450000, "WallSel exceeded its 8 KiB slot $44E000-$44FFFF"
print "End of wall_profile_selector.asm  ", pc
pullpc
