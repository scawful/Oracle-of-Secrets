

; 0x00 - Link's house
; 0x01 - Sanctuary (Hall of Secrets)
; 0x02 - Castle Prison
; 0x03 - Castle Basement
; 0x04 - Throne
; 0x05 - Old man cave
; 0x06 - Old man home
SPAWNPT         = $7EF3C8

; set spawn point flag for hall of secrets by impa
Impa_SetSpawnPointFlag:
{
  STA.l $7EF372
  LDA.l $7EF3D6 : ORA.b #$04 : STA.l $7EF3D6
  RTL
}

pushpc

; Zelda_AtSanctuary
org $05EE46
  JSL Impa_SetSpawnPointFlag

; TODO: Figure out what to do with this
org $05EBCF
  LDA $7EF359 : CMP.b #$05

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
#_05ED46: LDA.b #$00
#_05ED48: STA.l $7EF3C8

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