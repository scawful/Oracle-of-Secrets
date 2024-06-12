
; Bitfield of less important progression
; .fbh .zsu
;   u - Uncle visited in secret passage; controls spawn (0: spawn | 1: gone)
;   s - Priest visited in sanc after Zelda is kidnapped again
;   z - Zelda brought to sanc
;   h - Uncle has left Link's house; controls spawn (0: spawn | 1: gone)
;   b - Book of Mudora obtained/mentioned; controls Aginah dialog
;   f - Flipped by fortune tellers to decide which fortune set to give
PROGLITE        = $7EF3C6

; 0x00 - Link's house
; 0x01 - Sanctuary (Hall of Secrets)
; 0x02 - Prison
; 0x03 - Uncle
; 0x04 - Throne
; 0x05 - Old man cave
; 0x06 - Old man home
SPAWNPT         = $7EF3C8

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

org $05EBCF
NOP #8
; LDA.l $7EF359
; #_05EBD3: CMP.b #$02
; #_05EBD5: BCS .have_master_sword

; Prevent Impa from setting spawn point
org $05ED43
Zelda_BecomeFollower:
STZ.w $02E4
NOP #6
; #_05ED46: LDA.b #$02
; #_05ED48: STA.l $7EF3C8

; Prevent Impa from changing the song
org $05ED10
NOP #5

; LDA.b #$19 ; SONG 19
;#_05ED12: STA.w $012C
org $05ED63
NOP #5
; #_05ED63: LDA.b #$10 ; SONG 10
; #_05ED65: STA.w $012C

pullpc