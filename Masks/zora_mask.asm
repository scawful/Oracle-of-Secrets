; =============================================================================

org $07A569
LinkItem_ZoraMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return

  LDA $6C : BNE .return ; doorway

  LDA $0FFC : BNE .return ; cantopen menu

  LDY.b #$04
  LDA.b #$23
  
  JSL AddTransformationCloud

  LDA.b #$14 : JSR Player_DoSfx2

  LDA #$36 : STA $BC

.return
  RTS
}

org $368000
incbin zora_link.4bpp