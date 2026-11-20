; Overworld Palette Extension ABI:
;   Main ($06-$15): 16 authoring-owned records (70B each) at $45F400..$45F85F
;   Aux  ($14-$33): 32 authoring-owned records (42B each) at $45F900..$45FE3F (Aux ABI 1)
;   Anim ($0E-$1D): 16 authoring-owned records (14B each) at $45FE40..$45FF1F
; Every color uses the ordinary tint sink and palette upload scheduling.
; The input ROM owns the tables; rebuilding must never overwrite edited colors.
if !ENABLE_OW_AUX_EXTENSION == 1
pushpc

assert read4($1BEEA8) == $B8AE21C2 && read1($1BEEAC) == $0A, "OWAnim entry moved"
org $1BEEA8 ; @hook module=Overworld name=AnimPaletteBG kind=jml target=AnimPaletteBG protected_size=5
  JML AnimPaletteBG : NOP
assert pc() == $1BEEAD

assert read4($1BEEC7) == $B3AD21C2 && read1($1BEECB) == $0A, "OWMain entry moved"
org $1BEEC7 ; @hook module=Overworld name=MainPaletteBG kind=jml target=MainPaletteBG protected_size=5
  JML MainPaletteBG : NOP
assert pc() == $1BEECC

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
  CMP.w #$0015 : BNE .load
  JSL DocksDeferAuxPalette : BCC .load
  SEP #$30
  RTL
  .load
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
  CMP.w #$000D : BNE .load
  JSL DocksDeferAuxPalette : BCC .load
  SEP #$30
  RTL
  .load
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
  CMP.w #$0034 : BCC .in_range
  JMP PaletteExtensionDone
  .in_range
  SEC : SBC.w #$0014 : STA.b $00
  ASL : STA.b $02
  ASL : ASL : STA.b $04
  ASL : ASL
  CLC : ADC.b $04 : ADC.b $02
  CLC : ADC.w #$F900 : STA.b $00
  LDA.w #$0045 : STA.b $02
  TXA : CLC : ADC.l $7E0AA8 : STA.b $04
  LDA.w #$0002 : STA.b $08
  JMP PaletteExtensionRowLoop
}

; Extended Overworld Main palette ($06..$15, 70B = 5 rows x 7 colors at $45F400).
; Buffer-only loader ($1BEEC7) -> writes $7EC300 via LoadDayNightPaletteEffect.
MainPaletteBG:
{
  REP #$21
  LDA.w $0AB3 : AND.w #$00FF
  CMP.w #$0006 : BCS .extension
  JML $1BEECC
  .extension
  CMP.w #$0016 : BCC .in_range
  JMP PaletteExtensionDone
  .in_range
  REP #$10
  SEC : SBC.w #$0006
  ASL : STA.b $02                ; 2*n
  ASL : STA.b $04                ; 4*n
  ASL #4                         ; 64*n
  CLC : ADC.b $04 : ADC.b $02    ; 70*n
  CLC : ADC.w #$F400 : STA.b $00
  LDA.w #$0045 : STA.b $02
  LDA.w #$0042 : CLC : ADC.l $7E0AA8 : STA.b $04
  LDA.w #$0004 : STA.b $08
  JMP PaletteExtensionRowLoop
}

; Extended Overworld Animated palette ($0E..$1D, 14B = 1 row x 7 colors at $45FE40).
; Buffer-only loader ($1BEEA8) -> writes $7EC3E2..$7EC3EE via LoadDayNightPaletteEffect.
AnimPaletteBG:
{
  REP #$21
  LDA.w $0AB8 : AND.w #$00FF
  CMP.w #$000E : BCS .extension
  TAX
  JML $1BEEAD
  .extension
  CMP.w #$001E : BCC .in_range
  JMP PaletteExtensionDone
  .in_range
  REP #$10
  SEC : SBC.w #$000E
  ASL : STA.b $02                ; 2*n
  ASL : STA.b $04                ; 4*n
  ASL                            ; 8*n
  CLC : ADC.b $04 : ADC.b $02    ; 14*n
  CLC : ADC.w #$FE40 : STA.b $00
  LDA.w #$0045 : STA.b $02
  LDA.w #$00E2 : CLC : ADC.l $7E0AA8 : STA.b $04
  STZ.b $08
}

PaletteExtensionRowLoop:
{
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
}
PaletteExtensionDone:
  SEP #$30
  RTL

; Non-buffer Main palette loader called from Palette_OverworldBgMain2 during
; smooth overworld transitions ($0AB3 = $06..$15 -> writes both $7EC300 & $7EC500).
MainPaletteBG2:
{
  ; Entry: M=16, X=8, A = ($0AB3 & $00FF) >= $0006.
  CMP.w #$0016 : BCC .in_range
  JMP PaletteExtensionDone
  .in_range
  REP #$10
  SEC : SBC.w #$0006
  ASL : STA.b $02                ; 2*n
  ASL : STA.b $04                ; 4*n
  ASL #4                         ; 64*n
  CLC : ADC.b $04 : ADC.b $02    ; 70*n
  CLC : ADC.w #$F400 : STA.b $00
  LDA.w #$0045 : STA.b $02
  LDA.w #$0042 : STA.b $04
  LDA.w #$0004 : STA.b $08
  .row
    LDA.l $7E0AA8 : CLC : ADC.b $04 : TAX
    LDY.w #$0006
    .color
      LDA.b [$00]
      STA.l TimeState.SubColor
      BEQ +
        PHX
        JSL Oracle_ColorSubEffect
        PLX
      +
      STA.l $7EC300, X
      STA.l $7EC500, X
      INC.b $00 : INC.b $00
      INX : INX
      DEY : BPL .color
    LDA.b $04 : CLC : ADC.w #$0020 : STA.b $04
    DEC.b $08 : BPL .row
  SEP #$30
  RTL
}

assert pc() <= $45F400, "Overworld palette extension code exceeds $45F400 table start"
pullpc
endif
