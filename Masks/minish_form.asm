; =============================================================================
; Minish Form Link
; 
; Reacts to Tile ID 64 to transform into Minish Link
; =============================================================================

org $3A8000
incbin gfx/minish_link.4bpp

; =============================================================================

org $07DA2A
  TileDetection_OverworldAttributeJumpTable:

; Tile ID 64
org $07DAF2
  dw LinkState_CheckForMinishForm
  dw LinkState_CheckMinishTile

; =============================================================================

; Start of free space in bank 07
org $07F89D
LinkState_CheckForMinishForm:
{
  SEP #$30

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP.b #$05 : BEQ .already_minish

  LDA.l $7EF359 : STA $0AA5 ; Store the current sword 
  LDA.l $7EF35A : STA $0AAF ; Store the current shield
  LDA.b #$00 : STA $7EF359 : STA $7EF35A ; Clear the sword and shield

  LDA #$3A : STA $BC   ; change link's sprite 
  LDA #$05 : STA $02B2 ; Set the current mask form
  REP #$30
  RTS 

.already_minish
  STZ $02B2
  LDA $0AA5 : STA.l $7EF359
  LDA $0AAF : STA.l $7EF35A
  LDA #$10 : STA $BC
  REP #$30
  RTS
}

print "==> LinkState_CheckForMinishForm  ", pc

LinkState_CheckMinishTile:
{
  LDA $02B2 : BEQ .blocked ; no form
  CMP.b #$05 : BNE .blocked ; not minish 
  
  LDA $0A : TSB $0343
  RTS

.blocked
  LDA $0A : TSB $0E ; Blocked
  
  RTS
}

print "==> LinkState_CheckMinishTile     ", pc