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

; =========================================================

; Fix the capital 'B' debug item cheat.
org $0CDC26
    db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; =========================================================

incsrc ZSpriteLib/sprite_macros.asm
incsrc ZSpriteLib/sprite_hooks.asm

; SpritePrep_HauntedGroveOstritch
org $068BB2
NOP #11

; HauntedGroveRabbit_Idle
org $1E9A8F
NOP #5

; MedallionTablet (Goron)
; Responds to the hammer now instead of the sword.
org $05F274
  LDA.l $7EF34B

org $08C2E3
  dw $006F ; BUTTER SWORD DIALOGUE

;=========================================================

org    $308000
incsrc ZSpriteLib/sprite_new_table.asm

incsrc "Sprites/NPCs/farore.asm"
print  "End of farore.asm                 ", pc

incsrc "Sprites/Bosses/kydrog.asm"
print  "End of kydrog.asm                 ", pc

incsrc "Sprites/NPCs/maku_tree.asm"
print  "End of maku_tree.asm              ", pc

incsrc "Sprites/NPCs/mask_salesman.asm"
print  "End of mask_salesman.asm          ", pc


incsrc "Sprites/Bosses/twinrova.asm"
print  "End of twinrova.asm               ",  pc

incsrc "Sprites/Bosses/kydreeok.asm"
print  "End of kydreeok.asm               ",  pc

incsrc "Sprites/Bosses/kydreeok_head.asm"
print  "End of kydreeok_head.asm          ",  pc

incsrc "Sprites/Enemies/deku_scrub_enemy.asm"
print  "End of deku_scrub_enemy.asm       ",  pc

;=========================================================

org    $318000
incsrc ZSpriteLib/sprite_new_functions.asm

incsrc "Sprites/Bosses/kydrog_boss.asm"
print  "End of kydrog_boss.asm            ", pc

incsrc "Sprites/NPCs/deku_scrub.asm"
print  "End of deku_scrub.asm             ", pc

incsrc "Sprites/Enemies/anti_kirby.asm"
print  "End of anti_kirby.asm             ", pc

incsrc "Sprites/Enemies/sea_urchin.asm"
print  "End of sea_urchin.asm             ", pc

incsrc "Sprites/Objects/switch_track.asm"
print  "End of switch_track.asm           ", pc

incsrc "Sprites/Objects/mineswitch.asm"
print  "End of mineswitch.asm             ", pc

incsrc "Sprites/NPCs/village_dog.asm"
print  "End of village_dog.asm            ",  pc

incsrc "Sprites/Objects/minecart.asm"
print  "End of minecart.asm               ",  pc

incsrc "Sprites/Bosses/dark_link.asm"
print  "End of dark_link.asm              ", pc

incsrc "Sprites/NPCs/korok.asm"
print  "End of korok.asm                  ", pc


incsrc "Sprites/Objects/deku_leaf.asm"
print  "End of deku_leaf.asm              ",  pc

incsrc "Sprites/Objects/portal_sprite.asm"
print  "End of portal_sprite.asm          ",  pc

incsrc "Sprites/NPCs/impa.asm"
print  "End of impa.asm                   ",  pc

incsrc "Sprites/Enemies/poltergeist.asm"
print  "End of poltergeist.asm            ",  pc

incsrc "Sprites/Enemies/pols_voice.asm"
print  "End of pols_voice.asm             ",  pc



incsrc "Sprites/NPCs/zora_princess.asm"
print  "End of zora_princess.asm          ",  pc

incsrc "Sprites/Bosses/wolfos.asm"
print  "End of wolfos.asm                 ",  pc

incsrc "Sprites/Objects/ice_block.asm"
print  "End of ice_block.asm              ",  pc

incsrc "Sprites/Objects/whirlpool.asm"

incsrc "Sprites/NPCs/ranch_girl.asm"
print  "End of Ranch Girl.asm             ", pc

incsrc "Sprites/NPCs/bug_net_kid.asm"

incsrc "Sprites/Bosses/king_dodongo.asm"

incsrc "Sprites/Bosses/arrghus.asm"
print  "End of arrghus.asm                ", pc

incsrc "Sprites/Bosses/mothula.asm"
print  "End of mothula.asm                ", pc

incsrc "Sprites/Bosses/lanmola.asm"
print  "End of Lanmola.asm                ", pc

incsrc "Sprites/Bosses/lanmola_Expanded.asm"
print  "End of Lanmola_Expanded.asm       ", pc

incsrc "Sprites/NPCs/old_man.asm"

; incsrc "Sprites/Bosses/octoboss.asm"
; print  "End of octoboss.asm               ", pc



warnpc $328000