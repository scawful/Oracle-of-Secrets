pushpc
; Impa Fix
org $05EBCF
  LDA $7EF359 : CMP.b #$04

org $05ED63
  LDA.b #$03

pullpc