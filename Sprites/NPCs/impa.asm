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

; Prevent Impa from setting spawn point
org $05ED43
Zelda_BecomeFollower:
STZ.w $02E4
NOP #6
; #_05ED46: LDA.b #$02
; #_05ED48: STA.l $7EF3C8

; Prevent Impa from changing the song
org $05ED63
NOP #5
; #_05ED63: LDA.b #$10 ; SONG 10
; #_05ED65: STA.w $012C

pullpc