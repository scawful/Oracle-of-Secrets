; =========================================================
; Wolf Mask 
; 
; Talk to animals 
; Dig for treasure ability (shovel)
; 
; =========================================================

UpdateWolfPalette:
{
    REP #$30   ; change 16bit mode
    LDX #$001E

  .loop
    LDA.l WolfPalette, X : STA $7EC6E0, X
    DEX : DEX : BPL .loop

    SEP #$30 ; go back to 8 bit mode
    INC $15  ; update the palette
    RTL      ; or RTS depending on where you need it
}

; =========================================================

WolfPalette:
  dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$1A3D, #$14B6
  dw #$4650, #$362A, #$3F4E, #$162B, #$318A, #$39CC, #$1CE7, #$76D1
  dw #$6565, #$7271, #$14B5, #$459B, #$3D95, #$22D0, #$567C, #$1890
  dw #$7616, #$0000
  
; =========================================================

org $07A3DB
  LinkItem_Flute:

org $07A32C
  LinkItem_Shovel:

; LinkItem_Shovel
org $07A3B2
  NOP #5

; DigGame_SpawnPrize
org $1DFD5E
  NOP #5

; =========================================================

org $07A313
LinkItem_ShovelAndFlute:
{
  ; Play flute or use the Wolf Mask
  LDA $0202 : CMP.b #$0D : BNE .use_wolf_mask
  BRL LinkItem_Flute
.use_wolf_mask
  JMP LinkItem_WolfMask
  
}
; warnpc $07A31F

; =========================================================

; Bank 07 Free Space
pullpc

LinkItem_WolfMask:
{
    LDA $02B2 : CMP #$03 : BNE .equip
      JSR LinkItem_Shovel

  .equip
    LDA.b #$03 
    JSL Link_TransformMask

  .return
    RTS
}

print "End of Masks/wolf_mask.asm        ", pc
pushpc