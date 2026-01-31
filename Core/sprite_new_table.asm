pushpc
org $06FFF8 ; New Jumptable for sprites
NewMainSprFunction:
  JSL SpriteActiveExp_MainLong
  RTS

org $068EB9
NewSprPrepFunction:
  JSL Sprite_PrepExp_Long
  RTS
pullpc


SpriteActiveExp_MainLong:
{
  PHB : PHK : PLB
  JSL NewSprTable
  PLB
  RTL
}

NewSprTable:
{
  LDA $0E20, X ; Load Sprite ID
  REP #$30
  AND.w #$00FF
  CMP.w #$00F3 : BCS .null_sprite ; Bounds check: ID must be <= $F2
  STA $06
  ASL A ; *2
  CLC : ADC $06 ; *3
  TAY

  LDA NewSprRoutinesLong, Y ; Load sprite Address
  STA $06
  SEP #$20
  LDA NewSprRoutinesLong+2, Y
  STA $08
  ORA $06 : ORA $07 : BEQ .null_sprite ; Guard: skip if pointer is $000000
  SEP #$30 ; M=8-bit, X/Y=8-bit — JumpTableLocal stack math expects X=8.
  JMP [$0006]

  .null_sprite
  SEP #$30
  RTL
}

Sprite_PrepExp_Long:
{
  PHB : PHK : PLB
  JSL NewSprPrepTable
  PLB
  RTL
}

NewSprPrepTable:
{
  LDA $0E20, X ; Load Sprite ID
  REP #$30
  AND.w #$00FF
  CMP.w #$00F3 : BCS .null_sprite ; Bounds check: ID must be <= $F2
  STA $06
  ASL A ; *2
  CLC : ADC $06 ; *3
  TAY

  LDA NewSprPrepRoutinesLong, Y ; Load sprite Address
  STA $06
  SEP #$20
  LDA NewSprPrepRoutinesLong+2, Y
  STA $08
  ORA $06 : ORA $07 : BEQ .null_sprite ; Guard: skip if pointer is $000000
  SEP #$30 ; M=8-bit, X/Y=8-bit — JumpTableLocal stack math expects X=8.
  JMP [$0006]

  .null_sprite
  SEP #$30
  RTL
}

NewSprRoutinesLong:
{
  fillbyte $00
  fill $2FD
}

NewSprPrepRoutinesLong:
{
  fillbyte $00
  fill $2FD
}
