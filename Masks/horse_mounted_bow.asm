; Mounted bow prototype (!ENABLE_HORSE_MOUNTED_BOW).
; Bank $53 slice after park ($53D000-$53DFFF) and grounded clearance ($53E000-$53E7FF).
; Relocated from $53DF80 so park-anywhere can fill through $53E000.

!HorseMountedBow_RiderYAdjust = -14

pushpc
org $53E800
HorseForm_SuppressMountedButtons:
{
  LDA.b #$80 : TRB.b $F4
  LDA.w $0303 : CMP.b #$03 : BNE .block_y
  LDA.l $7EF340 : BEQ .block_y
  LDA.l $7EF377 : BEQ .block_y
  STZ.b $3C
  RTS
  .block_y
  LDA.b #$40 : TRB.b $F4
  STZ.b $3C
  RTS
}

HorseMountedBow_SetArrowCoords:
{
  PHP
  SEP #$20
  LDA.w !CurrentMask : CMP.b #$09 : BNE .write
  LDA.l $7EF340 : BEQ .write
  REP #$20
  LDA.b $00 : CLC : ADC.w #!HorseMountedBow_RiderYAdjust : STA.b $00
  SEP #$20
  LDA.w $0C72, X : ORA.b #$02 : STA.w $0C72, X
  .write
  LDA.b $00 : STA.w $0BFA, X
  LDA.b $01 : STA.w $0C0E, X
  LDA.b $02 : STA.w $0C04, X
  LDA.b $03 : STA.w $0C18, X
  PLP
  JML $0990FC ; SEC (AncillaAdd_Arrow success tail)
}
HorseMountedBow_End:
assert pc() <= $53E900, "Mounted bow slice overlapped next bank53 allocation"
pullpc

pushpc
org $0990F7 ; @hook module=Masks name=HorseMountedBow_SetArrowCoords kind=jsl target=HorseMountedBow_SetArrowCoords
  JSL HorseMountedBow_SetArrowCoords
  NOP
assert pc() == $0990FC
pullpc
