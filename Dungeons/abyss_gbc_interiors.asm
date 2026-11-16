; =========================================================
; Eon Abyss GBC interiors (flag !ENABLE_ABYSS_GBC_INTERIORS, default 0).
;
; Indoors in the Abyss ($7EF3CA != 0), rooms listed in AbyssGbc_RoomStyle draw
; GBC-style art:
;   1. AbyssGbc_RemapBg runs inside GfxSheet_GetPtr_BgCA after the normal table
;      lookup and swaps the BG sheet pointer for the style's GBC copy.
;   2. Palettes_Load_UnderworldSet ($1BEE74) gets a wrapper; after the vanilla
;      load it overwrites BG rows 2-7 (15 colours each) in the aux palette buffer.
; No blockset, collision, sheet-row or room-data writes. Data and sheets come
; from Scripts/Generate/gen_abyss_gbc.py (Dungeons/Data/abyss_gbc/).
;
; Known limit: slots 0-2 (main blockset) only load on entrance/stair loads, so
; they follow the room the Fortress was entered from; slots 3-6 and palettes
; follow each room.
; =========================================================

pushpc

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
  LDA.l $7EF3CA : BEQ .done
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
  LDA.l $7E001B : BEQ .out
  LDA.l $7EF3CA : BEQ .out
  REP #$30
  LDA.l $7E00A0 : CMP.w #$0128 : BCS .out
  TAX
  LDA.l AbyssGbc_RoomStyle,X : AND.w #$00FF : BEQ .out
  DEC : ASL : TAX
  LDA.l AbyssGbc_PalOffset,X : TAX        ; X = source offset (bytes)
  LDA.l $7E0AA8 : CLC : ADC.w #$0042 : TAY ; Y = destination offset in $7EC300
  PHB
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
  PLB
.out
  PLP
  RTL
}

incsrc "Dungeons/Data/abyss_gbc/abyss_gbc.asm"

pullpc
