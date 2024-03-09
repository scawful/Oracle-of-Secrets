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

; ==============================================================================

; Fix the capital 'B' debug item cheat.
org $0CDC26
    db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; ==============================================================================

incsrc ZSpriteLib/sprite_macros.asm
incsrc ZSpriteLib/sprite_hooks.asm

;==============================================================================

org    $308000
incsrc ZSpriteLib/sprite_new_table.asm

;==============================================================================

org    $318000
incsrc ZSpriteLib/sprite_new_functions.asm

incsrc "Sprites/farore.asm"
print  "End of farore.asm                 ", pc

incsrc "Sprites/Bosses/kydrog.asm"
print  "End of kydrog.asm                 ", pc

incsrc "Sprites/Bosses/kydrog_boss.asm"
print  "End of kydrog_boss.asm            ", pc

incsrc "Sprites/maku_tree.asm"
print  "End of maku_tree.asm              ", pc

incsrc "Sprites/NPCs/mask_salesman.asm"
print  "End of mask_salesman.asm          ", pc

incsrc "Sprites/NPCs/deku_scrub.asm"
print  "End of deku_scrub.asm             ", pc

incsrc "Sprites/Enemies/anti_kirby.asm"
print  "End of anti_kirby.asm             ", pc

incsrc "Sprites/Enemies/sea_urchin.asm"
print  "End of sea_urchin.asm             ", pc

incsrc "Sprites/switch_track.asm"
print  "End of switch_track.asm           ", pc

incsrc "Sprites/mineswitch.asm"
print  "End of mineswitch.asm             ", pc

incsrc "Sprites/NPCs/village_dog.asm"
print  "End of village_dog.asm            ",  pc

incsrc "Sprites/minecart.asm"
print  "End of minecart.asm               ",  pc

incsrc "Sprites/Bosses/twinrova.asm"
print  "End of twinrova.asm               ",  pc

incsrc "Sprites/Bosses/kydreeok.asm"
incsrc "Sprites/Bosses/kydreeok_head.asm"

incsrc "Sprites/deku_leaf.asm"

incsrc "Sprites/portal_sprite.asm"
print  "End of portal_sprite.asm          ",  pc

incsrc "Sprites/impa.asm"
print  "End of impa.asm                   ",  pc

incsrc "Sprites/Enemies/poltergeist.asm"
print  "End of poltergeist.asm            ",  pc

incsrc "Sprites/Enemies/pols_voice.asm"
print  "End of pols_voice.asm             ",  pc

incsrc "Sprites/Enemies/deku_scrub_enemy.asm"
print  "End of deku_scrub_enemy.asm       ",  pc

incsrc "Sprites/Bosses/arrghus.asm"
print  "End of arrghus.asm                ", pc

incsrc "Sprites/Bosses/mothula.asm"
print  "End of mothula.asm                ", pc

incsrc "Sprites/Bosses/lanmola.asm"
print  "End of Lanmola.asm                ", pc

incsrc "Sprites/Bosses/lanmola_Expanded.asm"
print  "End of Lanmola_Expanded.asm       ", pc

incsrc "Sprites/NPCs/bug_net_kid.asm"

warnpc $328000