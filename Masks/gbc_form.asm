org    $3B8000
incbin gfx/gbc_link.4bpp

UpdateGbcPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l GameboyLinkPalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

GameboyLinkPalette:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078, #$46FF
  dw #$22A2, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18, #$7FFF
  dw #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078, #$46FF, #$7E03
  dw #$7691, #$2678, #$435C, #$1199, #$7A18, #$7FFF, #$237E, #$B711
  dw #$369E, #$14A5, #$01FF, #$1078, #$46FF, #$147F, #$457E, #$6DF3
  dw #$7EB9, #$2A5C, #$2227, #$7A18, #$7FFF, #$237E, #$B711, #$369E
  dw #$14A5, #$01FF, #$1078, #$46FF, #$05FF, #$3B68, #$0A4A, #$12EF
  dw #$567E, #$1872, #$7A18, #$5276, #$0352
}

org $07A9B1
LinkMode_MagicMirror:
{
  JSL LinkState_GameboyForm
}

pullpc
LinkState_GameboyForm:
{
  SEP #$30
  LDA $02B2 : CMP.b #$06 : BEQ .already_gbc
  LDA $7EF357 : BEQ .return                 ; doesnt have the pearl
  LDA $0FFF : BEQ .return                   ; not in dark world
  %PlayerTransform()
  
  JSL UpdateGbcPalette
  LDA #$3B : STA $BC   ; change link's sprite 
  LDA #$06 : STA $02B2
  BRA .return

.already_gbc
  %PlayerTransform()
  LDA #$10 : STA $BC
  STZ $02B2
  
.not_gbc
.return
  JSL $07F1E6
  RTL
}
pushpc