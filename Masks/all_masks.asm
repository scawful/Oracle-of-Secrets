; =========================================================
;  Oracle of Secrets - Mask Library
; =========================================================

; 00 = Human
; 01 = Deku 
; 02 = Zora
; 03 = Wolf
; 04 = Bunny Hood 
; 05 = Minish Form
!CurrentMask  = $02B2

; Indexed by the bank number
!LinkGraphics = $BC
!ZoraDiving = $0AAB

; =========================================================

org $09912C
  AddTransformationCloud:

org $07B073
  Link_CheckNewY_ButtonPress:

org $07B0AB
  LinkItem_EvaluateMagicCost:

org $078028
  Player_DoSfx2:

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