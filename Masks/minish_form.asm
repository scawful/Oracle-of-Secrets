; =========================================================
; Minish Form Link
; 
; Reacts to Tile ID 64 to transform into Minish Link
; =========================================================

org    $398000
incbin gfx/minish_link.4bpp

; =========================================================
org    $07DA2A
  TileDetection_OverworldAttributeJumpTable:

; org $07DAEB ; Tile ID 61

org $07DAF2
  dw LinkState_CheckForMinishForm ; Tile ID 64
  dw LinkState_CheckMinishTile    ; Tile ID 65

; =========================================================
; Start of free space in bank 07
org $07F89D
LinkState_CheckForMinishForm:
{
  SEP #$30

  ; Check for the R button (like minish cap)
  %CheckNewR_ButtonPress() : BEQ .return

  ; Skip the code if you have a mask item out
  LDA $0202

  ; Check if the value in A (from $0202) is LT $13.
  CMP.b #$13 : BCC .continue

  ; Check if the value in A (from $0202) is GTE to $16.
  CMP.b #$17 : BCS .continue

  JMP .return

.continue

  LDA   !CurrentMask
  CMP.b #$05 : BEQ .already_minish ; return to human form
  CMP.b #$00 : BNE .return         ; don't transform if not human
  %PlayerTransform()

  LDA.l $7EF35A : STA $0AAF ; Store the current shield
  LDA.b #$00 : STA $7EF35A  ; Clear the shield

  LDA #$39 : STA $BC   ; Change link's sprite 
  LDA #$05 : STA $02B2 ; Set the current mask form
  BRA .return

.already_minish
  %PlayerTransform()
  %ResetToLinkGraphics()
  LDA $0AAF : STA.l $7EF35A ; restore the shield 

.return
  REP #$30
  RTS
}

; =============================================================================

LinkState_CheckMinishTile:
{
  LDA   $02B2 : BEQ .blocked ; no form
  CMP.b #$05 : BNE .blocked  ; not minish 
  
  LDA $0A : TSB $0343
  RTS

.blocked
  LDA $0A : TSB $0E ; Blocked
  
  RTS
}

print  "End of Masks/minish_form.asm      ", pc
pushpc

