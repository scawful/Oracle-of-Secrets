org $07A3DB
LinkItem_Flute:

org $07A313
LinkItem_ShovelAndFlute:
{
  ; Play flute or use the Wolf Mask
  LDA $0202 : CMP.b #$0D : BNE LinkItem_WolfMask
  BRL LinkItem_Flute
}

; TODO: Make sure there's no inaccessible code issues past here 
; LinkItem_Shovel 
org $07A32C
LinkItem_WolfMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$03 : BEQ .unequip ; is the wolf mask already on?
  JSL UpdateWolfPalette
  LDA #$38 : STA $BC                   ; change link's sprite 
  LDA #$03 : STA $02B2
  BRA .return

.unequip
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

org $388000
incbin wolf_link.4bpp

UpdateWolfPalette:
{
  REP #$30 ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l mypalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15 ; update the palette
  RTL ; or RTS depending on where you need it
}


mypalette:
dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$1A3D, #$14B6, #$4650, #$362A, #$3F4E, #$162B, #$318A, #$39CC, #$1CE7, #$76D1, #$6565, #$7271, #$14B5, #$459B, #$3D95, #$22D0, #$567C, #$1890, #$7616, #$0000
