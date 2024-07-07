; =========================================================
;  Oracle of Secrets - Mask Library
; =========================================================

; 00 = Human
; 01 = Deku 
; 02 = Zora
; 03 = Wolf
; 04 = Bunny Hood 
; 05 = Minish Form
; 06 = GBC Form
!CurrentMask  = $02B2

; Indexed by the bank number
!LinkGraphics = $BC
!ZoraDiving = $0AAB

; If set, deku is hovering and can drop bombs
DekuFloating   = $70

; If set, on deku platform and can hover
; Unset, will shoot deku bubble instead
DekuHover      = $71

; =========================================================

AddTransformationCloud = $09912C
Link_CheckNewY_ButtonPress = $07B073
LinkItem_EvaluateMagicCost = $07B0AB
Player_DoSfx2 = $078028

; =========================================================

incsrc "Masks/mask_routines.asm"

; Start of free space in bank 07
org $07F89D : pushpc

org $378000
  incbin gfx/bunny_link.4bpp
  incsrc "Masks/bunny_hood.asm"
  print  "End of Masks/bunny_hood.asm       ", pc

org $398000
  incbin gfx/minish_link.4bpp
  print  "End of Minish Form GFX            ", pc
  incsrc "Masks/minish_form.asm"

org $358000
  incbin gfx/deku_link.bin
  incsrc "Masks/deku_mask.asm"

org $368000
  incbin gfx/zora_link.4bpp
  incsrc "Masks/zora_mask.asm"

org $388000
  incbin gfx/wolf_link.4bpp
  incsrc "Masks/wolf_mask.asm"

org $3B8000
  incbin gfx/gbc_link.4bpp
  incsrc "Masks/gbc_form.asm"