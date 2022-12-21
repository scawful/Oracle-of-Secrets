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
  LDA #$38 : STA $BC                   ; change link's sprite 
  LDA #$03 : STA $02B2
  BRA .return

.unequip
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

org $388000
incbin wolf_link.4bpp