; =============================================================================
; Minish Form Link
; 
; Reacts to Tile ID 64 to transform into Minish Link
; =============================================================================

org $398000
incbin gfx/minish_link.4bpp

; =============================================================================

org $07DA2A
  TileDetection_OverworldAttributeJumpTable:

org $07DAF2
  dw LinkState_CheckForMinishForm ; Tile ID 64
  dw LinkState_CheckMinishTile    ; Tile ID 65

; =============================================================================

; Start of free space in bank 07
org $07F89D
LinkState_CheckForMinishForm:
{
  SEP #$30

  ; Check for the R button (like minish cap)
  LDA.b $F6 : BIT.b #$10 : BNE .r_button_press
  BRA .return
.r_button_press

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP.b #$05 : BEQ .already_minish

  LDA.l $7EF359 : STA $0AA5 ; Store the current sword 
  LDA.l $7EF35A : STA $0AAF ; Store the current shield
  LDA.b #$00 : STA $7EF359 : STA $7EF35A ; Clear the sword and shield

  LDA #$39 : STA $BC   ; change link's sprite 
  LDA #$05 : STA $02B2 ; Set the current mask form
  BRA .return

.already_minish
  STZ $02B2
  LDA $0AA5 : STA.l $7EF359
  LDA $0AAF : STA.l $7EF35A
  LDA #$10 : STA $BC

.return
  REP #$30
  RTS
}

; =============================================================================

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
pushpc

