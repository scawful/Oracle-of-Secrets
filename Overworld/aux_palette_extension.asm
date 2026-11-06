; Aux ABI 1: legacy $00-$13, 32 authoring-owned records at $45F900.
; Every color uses the ordinary tint sink and palette upload scheduling.
; The input ROM owns the table; rebuilding must never overwrite edited colors.
if !ENABLE_OW_AUX_EXTENSION == 1
pushpc

assert read4($1BEEE8) == $B4AD21C2 && read1($1BEEEC) == $0A, "OWBG1 entry moved"
org $1BEEE8 ; @hook module=Overworld name=AuxPaletteBG1 kind=jml target=AuxPaletteBG1 protected_size=5
  JML AuxPaletteBG1 : NOP
assert pc() == $1BEEED

assert read4($1BEF0C) == $B5AD21C2 && read1($1BEF10) == $0A, "OWBG2 entry moved"
org $1BEF0C ; @hook module=Overworld name=AuxPaletteBG2 kind=jml target=AuxPaletteBG2 protected_size=5
  JML AuxPaletteBG2 : NOP
assert pc() == $1BEF11

; Data is initialized once in a private authoring input, not by this include.
assert read1($45FE3F, $100) != $100, "Aux ABI 1 requires the complete authoring table"

org $45F000
AuxPaletteBG1:
{
  REP #$21
  LDA.w $0AB4 : AND.w #$00FF
if !ENABLE_KALYXO_DOCKS_PROFILE == 1
  CMP.w #$0015 : BNE .load
  JSL DocksDeferAuxPalette : BCC .load
  SEP #$30
  RTL
  .load
endif
  CMP.w #$0014 : BCS .extension
  JML $1BEEED
  .extension
  REP #$10
  LDX.w #$0052
  BRA AuxPaletteExtension
}

AuxPaletteBG2:
{
  REP #$21
  LDA.w $0AB5 : AND.w #$00FF
if !ENABLE_KALYXO_DOCKS_PROFILE == 1
  CMP.w #$000D : BNE .load
  JSL DocksDeferAuxPalette : BCC .load
  SEP #$30
  RTL
  .load
endif
  CMP.w #$0014 : BCS .extension
  JML $1BEF11
  .extension
  REP #$10
  LDX.w #$00B2
}

; A=selector, X=destination; M/X16. Match vanilla's $00-$08 scratch,
; caller DBR/DP, clobbered A/X/Y, balanced long return, and M/X8 on exit.
AuxPaletteExtension:
{
  CMP.w #$0034 : BCS .done
  SEC : SBC.w #$0014 : STA.b $00
  ASL : STA.b $02
  ASL : ASL : STA.b $04
  ASL : ASL
  CLC : ADC.b $04 : ADC.b $02
  CLC : ADC.w #$F900 : STA.b $00
  LDA.w #$0045 : STA.b $02
  TXA : CLC : ADC.w $0AA8 : STA.b $04
  LDA.w #$0002 : STA.b $08
  .row
    LDA.b $04 : TAX
    LDY.w #$0006
    .color
      LDA.b [$00]
      JSL LoadDayNightPaletteEffect
      INC.b $00 : INC.b $00
      INX : INX
      DEY : BPL .color
    LDA.b $04 : CLC : ADC.w #$0020 : STA.b $04
    DEC.b $08 : BPL .row
  .done
  SEP #$30
  RTL
}
assert pc() <= $45F800, "Aux palette code exceeds its allocation"
pullpc
endif
