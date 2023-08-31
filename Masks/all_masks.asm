;   $02B2 - Mask Form
;      00 = Human
;      01 = Deku 
;      02 = Zora
;      03 = Wolf
;      04 = Bunny Hood 
;      05 = Minish Form
;
;   $0AAB - Diving Flag

incsrc "Masks/mask_routines.asm"

incsrc "Masks/bunny_hood.asm"
print  "End of Masks/bunny_hood.asm       ", pc

incsrc "Masks/minish_form.asm"
incsrc "Masks/deku_mask.asm"
incsrc "Masks/zora_mask.asm"
incsrc "Masks/wolf_mask.asm"
incsrc "Masks/gbc_form.asm"