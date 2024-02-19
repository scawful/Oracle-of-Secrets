org    $3B8000
incbin gfx/gbc_link.4bpp

print pc 
UpdateGbcPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  LDA $7EF35B : AND.w #$00FF : CMP #$0001 : BEQ .blue_mail

  .loop
  LDA.l GameboyLinkPalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it

.blue_mail
  LDX #$001E
  .loop2
  LDA.l GameboyLinkBlueMail, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop2
  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

GameboyLinkPalette:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078, #$46FF
  dw #$22A2, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18
}

GameboyLinkBlueMail:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078, #$46FF
  dw #$4D25, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18
}

LinkState_GameboyInDungeonEntrance:
{

  LDA $0FFF : CMP #$00 : BEQ .return
    LDA $BC :  CMP #$06 : BEQ .return
   
    JSL UpdateGbcPalette
    LDA #$3B : STA $BC   ; change link's sprite 
   
.return

  JSL $0AFE80 ; Underworld_HandleLayerEffect
  RTL
}


org $07A9B1
LinkMode_MagicMirror:
{
  JSL LinkState_GameboyForm
}

org $0287A4
{
  JSL LinkState_GameboyInDungeonEntrance
}

pullpc
LinkState_GameboyForm:
{
  SEP #$30
  LDA $02B2 : CMP.b #$06 : BEQ .already_gbc
  LDA $7EF357 : BEQ .return                 ; doesnt have the pearl
  LDA $0FFF : BEQ .return                   ; not in dark world

.transform
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