; =============================================================================

org $07A569
LinkItem_ZoraMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return

  LDA $6C : BNE .return ; doorway

  LDA $0FFC : BNE .return ; cantopen menu

  LDA #$41 : STA $BC

.return
  RTS
}

org $418000
incbin zora_link.4bpp