InCutScene = $7EF303

org        $0083F8
LDA        InCutScene : BEQ .notInCutscene
    STZ $F0
    STZ $F2
    STZ $F4
    STZ $F6
    STZ $F8
    STZ $FA ; kill all input

.notInCutscene

RTS

warnpc $00841E

incsrc ZSpriteLib/sprite_macros.asm
incsrc ZSpriteLib/sprite_functions_hooks.asm

;==============================================================================

org    $298000
incsrc ZSpriteLib/sprite_new_table.asm

;==============================================================================

org    $2A8000
incsrc ZSpriteLib/sprite_new_functions.asm

incsrc "Sprites/farore.asm"
print  "End of farore.asm                 ", pc

incsrc "Sprites/Kydrog/kydrog.asm"
print  "End of kydrog.asm                 ", pc

incsrc "Sprites/Kydrog/kydrog_boss.asm"
print  "End of kydrog_boss.asm            ", pc

incsrc "Sprites/maku_tree.asm"
print  "End of maku_tree.asm              ", pc

incsrc "Sprites/mask_salesman.asm"
print  "End of mask_salesman.asm          ", pc

incsrc "Sprites/deku_scrub.asm"
print  "End of deku_scrub.asm             ", pc

incsrc "Sprites/anti_kirby.asm"
print  "End of anti_kirby.asm             ", pc

incsrc "Sprites/VillageDog/village_dog.asm"
print  "End of village_dog.asm            ",  pc

incsrc "Sprites/minecart.asm"
print  "End of minecart.asm               ",  pc

incsrc "Sprites/twinrova.asm"

incsrc "Sprites/portal_sprite.asm"

incsrc "Sprites/impa.asm"
print  "End of impa.asm                   ",  pc


incsrc "Sprites/bug_net_kid.asm"


warnpc $2B8000