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
  STA $06
  ASL A ; *2
  CLC : ADC $06 ; *3
  TAY

  LDA NewSprRoutinesLong, Y ; Load sprite Address
  STA $06
  SEP #$20 ; Previously SEP #$30 -_- (that's fine for sprites below ~0x40 over that it will crash)
  LDA NewSprRoutinesLong+2, Y 
  STA $08
  SEP #$30
  JMP [$0006]

  ;do a JML and sprite will RTL back to previous code
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
  STA $06
  ASL A ; *2
  CLC : ADC $06 ; *3
  TAY

  LDA NewSprPrepRoutinesLong, Y ; Load sprite Address
  STA $06
  SEP #$20 ; Previously SEP #$30 -_- (that's fine for sprites below ~0x40 over that it will crash)
  LDA NewSprPrepRoutinesLong+2, Y 
  STA $08
  SEP #$30
  JMP [$0006]
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
