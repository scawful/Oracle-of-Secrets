; Collect items with sword
org $86F725
 JSL collectSword

pullpc
collectSword:
{
  ADC #$00
  STA $09
  LDA $79
  BEQ $01
  RTL

  LDA $0E20, x
  SEC
  SBC #$D8
  BCS $01
  RTL

  LDA $0E20, x
  SEC
  SBC #$E7
  BCC $01
  RTL

  PHY  
  LDY $3C
  BPL $02
  PLY  
  RTL

  LDA $F571, y
  BEQ $02
  PLY
  RTL

  PHX  
  LDA $2F
  ASL A
  ASL A
  ASL A
  CLC  
  ADC $3C
  TAX
  INX  
  LDY #$00
  LDA $45
  CLC
  ADC $F46D, x
  BPL $01
  DEY  
  CLC
  ADC $22
  STA $00
  TYA
  ADC $23
  STA $08
  LDY #$00
  LDA $44
  CLC
  ADC $F4EF, x
  BPL $01
  DEY
  CLC  
  ADC $20
  STA $01
  TYA
  ADC $21
  STA $09
  LDA $F4AE, x
  STA $02
  LDA $F530, x
  STA $03
  PLX
  PLY  
  RTL
}
pushpc
