; Mounted bow prototype (!ENABLE_HORSE_MOUNTED_BOW).
; Bank $53 slice after park ($53D000-$53DFFF) and grounded clearance ($53E000-$53E7FF).
; Relocated from $53DF80 so park-anywhere can fill through $53E000.

pushpc
org $53E800
HorseForm_SuppressMountedButtons:
{
  LDA.b #$80 : TRB.b $F4
  LDA.l $7EF3CC : BNE .block_y              ; follower owns $4200/$4220
  LDA.w $0202 : CMP.b #$01 : BNE .block_y   ; allow Y press only when Bow is on Y
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
  SEP #$30
  LDA.w !CurrentMask : CMP.b #$09 : BNE .write
  LDA.l $7EF340 : BEQ .write
  LDA.b #$03 : STA.w $0C5E, X                ; skip 4 invisible wait frames ($08..$05)
  PHX
  LDA.b $76 : AND.b #$06 : TAX
  REP #$20
  LDA.b $00 : CLC : ADC.l .rider_dy, X : STA.b $00
  LDA.b $02 : CLC : ADC.l .rider_dx, X : STA.b $02
  SEP #$20
  PLX
  .write
  LDA.b $00 : STA.w $0BFA, X
  LDA.b $01 : STA.w $0C0E, X
  LDA.b $02 : STA.w $0C04, X
  LDA.b $03 : STA.w $0C18, X
  ; The hook is a JSL: return to its NOP at $0990FB, then the vanilla tail
  ; (SEC : PLB : RTL). A JML to $0990FC left the JSL return address under
  ; that PLB/RTL, so every arrow returned into WRAM. M=8 as the replaced
  ; SEP #$20 : JSR Ancilla_SetCoordinates left it.
  PLP
  SEP #$20
  RTL

  .rider_dy ; up, down, left, right
  dw -14, -8, -12, -12
  .rider_dx ; up, down, left, right
  dw 0, 0, -4, 4
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

incsrc "Masks/horse_minigame.asm"
