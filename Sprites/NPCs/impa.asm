pushpc
; Impa Fix
org $05EBCF
  LDA $7EF359 : CMP.b #$04

; Module15_0C
; Change overlay that Impa activates after intro
org $029E2E
#_029E2E: LDA.l $7EF2A3
#_029E32: ORA.b #$20
#_029E34: STA.l $7EF2A3



pullpc