; ========================================
; GBC Link
; ========================================

UpdateGbcPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  LDA $7EF35B : AND.w #$00FF : CMP #$0001 : BEQ .blue_mail
  LDA $7EF35B : AND.w #$00FF : CMP #$0002 : BEQ .red_mail

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
.red_mail
  LDX #$001E
  .loop3
  LDA.l GameboyLinkRedMail, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop3
  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

GameboyLinkPalette:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078
  dw #$46FF, #$22A2, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18
}

GameboyLinkBlueMail:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078
  dw #$46FF, #$4D25, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18
}

GameboyLinkRedMail:
{
  dw #$0000, #$7FFF, #$237E, #$B711, #$369E, #$14A5, #$01FF, #$1078
  dw #$46FF, #$081D, #$3B68, #$0A4A, #$12EF, #$2A5C, #$1571, #$7A18
}

LinkState_GameboyInDungeonEntrance:
{
  ; if link is in the dark world, change his sprite to the gbc one
  LDA $0FFF : CMP #$00 : BEQ .return
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
      LDA $BC :  CMP #$06 : BEQ .return
    
      JSL UpdateGbcPalette
      LDA #$3B : STA $BC   ; change link's sprite 
   
.return

  JSL $0AFE80 ; Underworld_HandleLayerEffect
  RTL
}

; Retain GBC sprite when exiting DW dungeons
LoadOverworld_CheckForGbcLink:
{
  LDA $0FFF : BEQ .return_lw
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
      LDA.b #$06 : STA $02B2
      LDA.b #$3B : STA $BC   ; change link's sprite 
      JSL UpdateGbcPalette
      JMP .return
   
.return_lw
  STZ.w $02B2
  
.return
  JSL Palette_ArmorAndGloves
  STZ.b $B0
  STZ.b $11
  RTL
}

OverworldTransition_CheckForGbcLink:
{
  LDA $0FFF : BEQ .return 
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
      LDA #$3B : STA $BC   ; change link's sprite
      LDA #$06 : STA $02B2
      JSL Palette_ArmorAndGloves
  .return
  JSL $07E6A6 ; Link_HandleMovingAnimation_FullLongEntry
  RTL
}

; Module08_02_LoadAndAdvance
org $02EDC0
  JSL LoadOverworld_CheckForGbcLink

org $02ABDA
  JSL OverworldTransition_CheckForGbcLink

org $07A9B1
LinkMode_MagicMirror:
  JSL LinkState_GameboyForm

org $0287A4
  JSL LinkState_GameboyInDungeonEntrance

pullpc
LinkState_GameboyForm:
{
  SEP #$30
  LDA $02B2 : CMP.b #$06 : BEQ .already_gbc
    LDA $0FFF : BEQ .return ; not in dark world
      .transform
      %PlayerTransform()

      LDA #$3B : STA $BC   ; change link's sprite 
      LDA #$06 : STA $02B2
      JSL UpdateGbcPalette
      BRA .return

  .already_gbc
  %PlayerTransform()
  LDA #$10 : STA $BC
  STZ $02B2
  JSL Palette_ArmorAndGloves
  
  .return
  JSL $07F1E6 
  RTL
}
pushpc