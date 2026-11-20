; =========================================================
; Eon Abyss GBC interiors.
;
; Indoors in the Eon Abyss ($7EF3CA == $40), rooms listed in AbyssGbc_RoomStyle
; draw GBC-style art; Kalyxo Light World ($00) and Special Overworld ($80) stay
; 100% vanilla SNES even for shared room IDs:
;   1. AbyssGbc_RemapBg runs inside GfxSheet_GetPtr_BgCA after the normal table
;      lookup and swaps the BG sheet pointer for the style's GBC copy.
;   2. Palettes_Load_UnderworldSet ($1BEE74) gets a wrapper; after the vanilla
;      load it overwrites BG rows 2-7 (15 colours each) in the aux palette buffer.
; No blockset, collision, sheet-row or room-data writes. Data and sheets come
; from Scripts/Generate/gen_abyss_gbc.py (Dungeons/Data/abyss_gbc/).
;
; Vanilla only loads BG sheets on entrance loads (all 8 slots) and stair/hole
; transitions (slots 3-6); door scrolls load none. So:
;   3. AbyssGbc_FullLoadEntry (at $00E219, start of the BG half of
;      InitializeTilesets) records the style the loaded sheets belong to in
;      !AbyssGbc_LoadedStyle.
;   4. The three room-transition sheet calls ($028A63 door, $028CED hole/warp,
;      $02940F stairs) first run AbyssGbc_SyncStyle. When the new room's style
;      differs from the loaded one it blanks the screen and re-runs the vanilla
;      BG loader, so the screen blinks black only at a style boundary.
;   5. On a door scroll that changes style, the palette wrapper also copies
;      BG rows 2-7 from the aux buffer to the main buffer.
; =========================================================

!AbyssGbc_LoadedStyle = $7F5408 ; UNUSED_7F5000 tail (clear of Gust Jar $0273-$027F)
!AbyssGbc_PalStyle    = $7F5409 ; style of the last BG palette load

pushpc

assert read4($00E219) == $00A930C2 && read4($00E21D) == $21168D20, "InitializeTilesets BG entry moved"
org $00E219 ; @hook module=Dungeons name=AbyssGbc_FullLoadEntry kind=jsl target=AbyssGbc_FullLoadEntry protected_size=8
  JSL AbyssGbc_FullLoadEntry
  NOP #4
assert pc() == $00E221

assert read4($028A63) == $00D6F922, "door transition sprite sheet call moved"
org $028A63 ; @hook module=Dungeons name=AbyssGbc_DoorTrans kind=jsl target=AbyssGbc_DoorTrans protected_size=4
  JSL AbyssGbc_DoorTrans

assert read4($028CED) == $00D66E22, "hole/warp aux sheet call moved"
org $028CED ; @hook module=Dungeons name=AbyssGbc_AuxTrans kind=jsl target=AbyssGbc_AuxTrans protected_size=4
  JSL AbyssGbc_AuxTrans

assert read4($02940F) == $00D66E22, "stairs aux sheet call moved"
org $02940F ; @hook module=Dungeons name=AbyssGbc_AuxTrans kind=jsl target=AbyssGbc_AuxTrans protected_size=4
  JSL AbyssGbc_AuxTrans

assert read2($1BEE74) == $21C2 && read1($1BEE76) == $AE && read2($1BEE77) == $0AB6, "Palettes_Load_UnderworldSet entry moved"
org $1BEE74 ; @hook module=Dungeons name=AbyssGbc_PalWrap kind=jml target=AbyssGbc_PalWrap protected_size=5
  JML AbyssGbc_PalWrap
  NOP
assert pc() == $1BEE79

org $5A8000
; Entry from GfxSheet_GetPtr_BgCA: M=8, X=16, X = BG sheet ID, $C8-$CA = pointer.
; Exit: same widths, X preserved, $C8-$CA replaced when the room style maps it.
AbyssGbc_RemapBg:
{
  LDA.l $7E001B : BEQ .done
  LDA.l $7EF3CA : CMP.b #$40 : BNE .done
  PHX
  REP #$20
  LDA.l $7E00A0 : CMP.w #$0128 : BCS .pop
  TAX
  SEP #$20
  LDA.l AbyssGbc_RoomStyle,X : BEQ .pop
  DEC : XBA
  LDA 1,S                       ; sheet ID (low byte of the pushed X)
  REP #$20 : TAX : SEP #$20     ; X = (style-1)*256 + sheet
  LDA.l AbyssGbc_SheetMap,X : BEQ .pop
  REP #$20
  AND.w #$00FF : DEC : ASL #2 : TAX
  LDA.l AbyssGbc_Ptr,X : STA.b $C8
  SEP #$20
  LDA.l AbyssGbc_Ptr+2,X : STA.b $CA
.pop
  SEP #$20
  PLX
.done
  RTL
}

; Replaces REP #$21 : LDX.w $0AB6 at $1BEE74. Pushes a long return to .tail so
; the vanilla RTL at $1BEEA7 lands here, then the caller's return is used.
AbyssGbc_PalWrap:
{
  PHK
  PER .tail-1
  REP #$21
  LDX.w $0AB6
  JML $1BEE79
.tail
  ; M=8, X=8 (vanilla SEP #$30 before RTL)
  PHP
  SEP #$30
  JSR AbyssGbc_GetStyle
  TAY
  EOR.l !AbyssGbc_PalStyle : PHA           ; nonzero = style changed since last load
  TYA : STA.l !AbyssGbc_PalStyle
  CPY.b #$00 : BEQ .sync
  REP #$30
  AND.w #$00FF : DEC : ASL : TAX
  LDA.l AbyssGbc_PalOffset,X : TAX        ; X = source offset (bytes)
  LDA.l $7E0AA8 : CLC : ADC.w #$0042 : TAY ; Y = destination offset in $7EC300
  LDA.w #$0005 : STA.b $08                 ; 6 rows
.row
  PHY
  LDA.w #$000E : STA.b $06                 ; 15 colours
.color
  LDA.l AbyssGbc_Pal,X
  PHX : TYX : STA.l $7EC300,X : PLX
  INX #2 : INY #2
  DEC.b $06 : BPL .color
  PLA : CLC : ADC.w #$0020 : TAY
  DEC.b $08 : BPL .row
.sync
  ; A door scroll loads only the aux buffer and nothing copies it to the main
  ; buffer, because vanilla palettes never change across a door. When the
  ; style changed, copy BG rows 2-7 across. Lights-out fades do it themselves.
  SEP #$30
  PLA : BEQ .out
  LDA.b $10 : CMP.b #$07 : BNE .out
  LDA.b $11 : CMP.b #$02 : BNE .out
  LDA.l $7EC005 : BNE .out
  REP #$30
  LDA.l $7E0AA8 : BNE .out
  LDX.w #$0042
.copy
  LDA.l $7EC300,X : STA.l $7EC500,X
  INX #2 : CPX.w #$0100 : BCC .copy
  SEP #$20
  INC.b $15
.out
  PLP
  RTL
}

; Exit: A (8-bit) = style of room $A0 under the same gate as AbyssGbc_RemapBg,
; 0 = vanilla art. Entry M=8, X=8. Clobbers X.
AbyssGbc_GetStyle:
{
  LDA.l $7E001B : BEQ .none
  LDA.l $7EF3CA : CMP.b #$40 : BNE .none
  REP #$30
  LDA.l $7E00A0 : CMP.w #$0128 : BCS .wide_none
  TAX
  LDA.l AbyssGbc_RoomStyle,X
  SEP #$30
  RTS
.wide_none
  SEP #$30
.none
  LDA.b #$00
  RTS
}

; Replaces REP #$30 : LDA.w #$2000 : STA.w VMADDR at $00E219. Every full BG
; sheet load passes here, so the recorded style always matches VRAM.
AbyssGbc_FullLoadEntry:
{
  SEP #$30
  JSR AbyssGbc_GetStyle : STA.l !AbyssGbc_LoadedStyle
  REP #$30
  LDA.w #$2000 : STA.l $002116
  RTL
}

; Reload all BG sheets when room $A0 needs a different style than VRAM holds.
; The vanilla loader writes VRAM directly, so the screen is force-blanked for
; its run: $13 feeds INIDISP at the end of every NMI, lag frames included.
AbyssGbc_SyncStyle:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  SEP #$30
  JSR AbyssGbc_GetStyle
  CMP.l !AbyssGbc_LoadedStyle : BEQ .done
  LDA.b $13 : PHA
  LDA.b #$80 : STA.b $13 : STA.l $002100
  PHK
  PER .ret-1
  PHB                              ; popped by the vanilla PLB at $00E2CE
  LDA.b #$00 : PHA : PLB
  LDA.b #$80 : STA.w $2115
  JML $00E219
.ret
  SEP #$30
  PLA : STA.b $13
.done
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

AbyssGbc_DoorTrans:
{
  JSL AbyssGbc_SyncStyle
  JML $00D6F9                      ; LoadTransAuxGFX_sprite
}

AbyssGbc_AuxTrans:
{
  JSL AbyssGbc_SyncStyle
  JML $00D66E                      ; LoadTransAuxGFX
}

incsrc "Dungeons/Data/abyss_gbc/abyss_gbc.asm"

pullpc
