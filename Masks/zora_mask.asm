; =============================================================================

org $07A569
LinkItem_ZoraMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$02 : BEQ .unequip   ; is the zora mask on?
  LDA #$36 : STA $BC
  LDA #$02 : STA $02B2
  BRA .return
.unequip
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

org $368000
incbin gfx/zora_link.4bpp