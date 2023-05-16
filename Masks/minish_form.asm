

; =============================================================================
; Minish Form Link
; 
; =============================================================================

LinkState_CheckForMinishForm:
{
  SEP #$30

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP.b #$05 : BEQ .already_minish

  LDA #$3A : STA $BC   ; change link's sprite 
  LDA #$05 : STA $02B2 ; Set the current mask form
  REP #$30
  RTS 

.already_minish
  LDA #$10 : STA $BC : STZ $02B2
  REP #$30
  RTS
}

org $07DA2A
  TileDetection_OverworldAttributeJumpTable:

; Tile ID 64
org $07DAF2
  dw $F89D

org $3A8000
incbin gfx/minish_link.4bpp

