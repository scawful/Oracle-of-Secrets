; =========================================================
; Per-dungeon wall-profile selector (flag !ENABLE_WALL_PROFILE_SELECTOR, default 1)
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
; A profile may also carry a graphics kit (private blockset row, palette,
; tile types); see the Graphics kits block below and Dungeons/Data/kits/.
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
; Graphics kits (generated !WALLSEL_GFX == 1 only).
; A kit (Dungeons/Data/kits/<kit>.kit.json) gives one profile a private
; blockset row !WALLSEL_KIT_ROW0+kit and/or a private BG palette. H3 swaps
; the room header's blockset ($0AA2) and palette ($0AB6) for them, so no
; room that shares the original blockset/palette changes. The rows,
; palettes and sheet streams are written by Dungeons/Data/kits/kits.asm
; (included from Dungeons/wall_profile_gfx.asm), which also asserts that
; no room header uses a private row or palette id.
;   collision: chars $140-$1BF load from the kit's base blockset group;
;   chars $C0-$FF (and any other char a kit patches) are restored from
;   UnderworldTileTypes on every room, then the kit's tile types patched.
; =========================================================
if !WALLSEL_GFX == 1

; The existing UW converter chooses a palette half for an entire sheet.
; Kit slot 6 can now opt individual STATIC glyphs into the high half while
; inherited furniture stays low. The 3bpp stream and all CGRAM words stay intact.
; Entry $00:E636: M=16 X=8, DBR=00 DP=0000, Y=63, [$00]=decoded sheet,
; VMAIN/VMADDR already prepared. Native slot counter $0F=1 is physical slot 6.
; The native converter clobbers A/X/Y, $00-$01 and $BD-$CE. We use the same
; scratch, plus 3 stack bytes, and return via the original RTS at $00:E6B6.
assert read3($00E636) == $E00FA6 && read3($00E639) == $F7B004, "UW palette-half dispatch moved"
pushpc
org $00E636 ; @hook module=Dungeons name=WallSel_LoadMaskedGraphics kind=jml target=WallSel_LoadMaskedGraphics expected_m=16 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JML WallSel_LoadMaskedGraphics
  NOP #2
assert pc() == $00E63C, "UW palette-half hook crossed low converter"
pullpc

WallSel_LoadMaskedGraphics:
{
  BRA .entry
  ; Discovery is tied to the actual hook target, not a new fixed ROM region.
  db "WKPM", $01
  dl WallSel_RenderMetadata
.entry
  LDA.l $7E001B : AND.w #$00FF : BEQ .vanilla
  LDX.b $0F : CPX.b #$01 : BNE .vanilla
  LDA.l $7E0AA2 : AND.w #$00FF
  SEC : SBC.w #!WALLSEL_KIT_ROW0
  CMP.w #!WALLSEL_KIT_COUNT : BCS .vanilla
  ASL #6 : TAX
  PHX                              ; one-byte mask row base, maximum $C0
  BRA .tile
.vanilla
  LDX.b $0F : CPX.b #$04 : BCS .high
  JML $00E63C                       ; untouched native low converter
.high
  JML $00E5AF                       ; untouched native high converter
.tile
  TYA : AND.w #$00FF : EOR.w #$003F
  CLC : ADC 1,S : AND.w #$00FF : TAX
  LDA.l WallSel_KitHighPalette,X : AND.w #$00FF
  PHA                              ; this glyph's high-half opt-in (2 bytes)
  LDX.b #$0E
.planes01
  LDA.b [$00] : STA.w $2118
  XBA : ORA.b [$00] : AND.w #$00FF : STA.b $BF,X
  INC.b $00 : INC.b $00
  DEX : DEX : BPL .planes01
  LDX.b #$0E
.planes23
  LDA.b [$00] : AND.w #$00FF : STA.b $BD
  LDA 1,S : BEQ .low_pixel
  LDA.b $BD : ORA.b $BF,X : XBA : ORA.b $BD
  BRA .write
.low_pixel
  LDA.b $BD
.write
  STA.w $2118
  INC.b $00
  DEX : DEX : BPL .planes23
  PLA
  DEY : BPL .tile
  PLX
  LDX.b #$FF                        ; same X/Y and width as native conversion
  SEP #$20
  JML $00E6B6                       ; RTS to InitializeTilesets' original caller
}

; Room transitions first expand four auxiliary sheets into $7F0000-$7F1FFF.
; Replay the displaced entry then call the untouched native continuation, whose
; RTL returns here. Only slot 6 ($7F1800-$7F1FFF) receives the same glyph mask.
; Entry/exit M=8 X=8, DBR=00 DP=0000. The post-pass preserves the native return
; A (including hidden B), X/Y/P and scratch; it writes only selected plane 3.
assert read4($00DF1A) == $02857EA9, "UW transition converter entry moved"
pushpc
org $00DF1A ; @hook module=Dungeons name=WallSel_TransitionGraphics kind=jml target=WallSel_TransitionGraphics expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JML WallSel_TransitionGraphics
assert pc() == $00DF1E, "UW transition hook crossed native continuation"
pullpc

WallSel_TransitionGraphics:
{
  LDA.b #$7E : STA.b $02
  JSL $00DF1E                       ; original conversion, through its RTL
  JSL WallSel_MaskTransitionGraphics
  RTL
}

WallSel_MaskTransitionGraphics:
{
  PHP : REP #$30 : PHA : PHX : PHY
  LDA.l $7E001B : AND.w #$00FF : BEQ .done
  LDA.l $7E0AA2 : AND.w #$00FF
  SEC : SBC.w #!WALLSEL_KIT_ROW0
  CMP.w #!WALLSEL_KIT_COUNT : BCS .done
  ASL #6 : PHA                      ; existing kit mask row base
  LDX.w #$1800                      ; physical slot 6 in transition staging
.tile
  PHX
  TXA : SEC : SBC.w #$1800 : LSR #5
  CLC : ADC 3,S : TAX
  LDA.l WallSel_KitHighPalette,X : AND.w #$00FF
  BEQ .unmasked
  PLX : PHX : LDY.w #$0007
.row
  LDA.l $7F0000,X : XBA : ORA.l $7F0000,X
  ORA.l $7F0010,X : AND.w #$00FF : XBA
  ORA.l $7F0010,X : STA.l $7F0010,X
  INX : INX : DEY : BPL .row
  PLX : BRA .next
.unmasked
  PLX
.next
  TXA : CLC : ADC.w #$0020 : TAX
  CPX.w #$2000 : BNE .tile
  PLA
.done
  PLY : PLX : PLA : PLP
  RTL
}

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
  LDA.l WallSel_ProfileBlockset-1,X : CMP.b #$FF : BEQ .palette
  STA.l $7E0AA2
.palette
  LDA.l WallSel_ProfilePalette-1,X : CMP.b #$FF : BEQ .done
  STA.l $7E0AB6
.done
  PLP : PLX
  RTL
}

; Replaces the JSL at $0E942A (Underworld_LoadCustomTileTypes), which
; runs on every room load. Dungeon_LoadCustomTileAttr sets its own DBR and
; widths and clobbers X/Y. Exit: M=8 X=8, like Dungeon_LoadCustomTileAttr.
WallSel_LoadTileAttr:
{
  SEP #$30
  LDA.l $7E0AA2 : SEC : SBC.b #!WALLSEL_KIT_ROW0
  CMP.b #!WALLSEL_KIT_COUNT : BCS .plain
  TAX                                    ; kit index
  LDA.l WallSel_KitBase,X : STA.l $7E0AA2
  PHX
  JSL Dungeon_LoadCustomTileAttr         ; $140-$1BF from the base group
  PLX
  TXA : CLC : ADC.b #!WALLSEL_KIT_ROW0 : STA.l $7E0AA2
  PHX
  JSR WallSel_RestoreTypes
  PLX
  TXA : ASL : TAX
  JSR (WallSel_KitPatchPtr,X)
  SEP #$30
  RTL
.plain
  JSL Dungeon_LoadCustomTileAttr
  JSR WallSel_RestoreTypes
  SEP #$30
  RTL
}

; Chars $C0-$FF back to UnderworldTileTypes+$C0 (the bytes
; LoadDefaultTileTypes copies), then the generated extra restores.
; Exit: M=8 X=8.
WallSel_RestoreTypes:
{
  REP #$30
  LDX.w #$003E
.restore
  LDA.l read3($0E97F6),X : STA.l $7EFEC0,X
  DEX : DEX : BPL .restore
  SEP #$30
  JMP WallSel_RestoreExtra
}

; DreamRoom_LoadSheets copies $0AA2 into the main set $0AA1; a kit row is
; not a main set, so map it back to the kit's base blockset.
; Entry/exit: A = blockset (8-bit); M, X, Y, DBR preserved.
WallSel_RowToMain:
{
  PHX : PHP
  SEP #$30
  PHA
  SEC : SBC.b #!WALLSEL_KIT_ROW0
  CMP.b #!WALLSEL_KIT_COUNT : BCS .keep
  TAX
  PLA
  LDA.l WallSel_KitBase,X
  PLP : PLX
  RTL
.keep
  PLA
  PLP : PLX
  RTL
}

assert read1($0E97F5) == $BF && read1($0E97F9) == $9F && read3($0E97FA) == $7EFEC0, "LoadDefaultTileTypes slot-3 copy moved"
assert !WALLSEL_KIT_COUNT >= 1, "a gfx route needs at least one kit row"

; ---- vanilla bytes ----
assert read1($01B641) == $C8 && read2($01B642) == $0DB7 && read1($01B644) == $8D && read2($01B645) == $0AA2, "H3 header blockset site changed"

pushpc
org $01B641 ; @hook module=Dungeons name=WallSel_HeaderGfx kind=jsl target=WallSel_HeaderGfx expected_m=8 expected_x=16 expected_exit_m=8 expected_exit_x=16
  JSL WallSel_HeaderGfx
  NOP #2
pullpc

else

WallSel_LoadTileAttr:
  JML Dungeon_LoadCustomTileAttr

WallSel_RowToMain:
  RTL

endif

assert WallSel_Data_End-WallSel_Data <= $8000, "WallSel data too large"
assert (WallSel_Data&$FF0000) == ((WallSel_Data_End-1)&$FF0000), "WallSel_Data crosses a bank"
assert pc() <= $450000, "WallSel exceeded its 8 KiB slot $44E000-$44FFFF"
print "End of wall_profile_selector.asm  ", pc
pullpc
