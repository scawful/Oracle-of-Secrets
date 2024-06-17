InCutScene = $7EF303

; Player2JoypadReturn
org $0083F8
  LDA InCutScene : BEQ .notInCutscene
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

; Sprite 

; Kydreeok Head die like Sidenexx
org $06EFFF
  CMP.b #$CF

org $06F003
  CMP.b #$CF

; Make Dark Link die like sidenexx
org $06F003
  CMP.b #$C1

; Make Helmet ChuChu recoil link
org $06F37D
  CMP.b #$05

; Make Kydreeok head recoil Link
org $06F381
  CMP.b #$CF

; =========================================================

; Fix the capital 'B' debug item cheat.
org $0CDC26
    db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; Follower_Disable
; Don't disable Kiki so we can switch maps with him.
org $09ACF3
  LDA.l $7EF3CC
  CMP.b #$0E

; Kiki, don't care if we're not in dark world
org $099FEB
#_099FEB: LDA.b $8A
#_099FED: AND.b #$FF

org $1EE48E
  NOP #6

; Kiki activate cutscene 3 (tail palace)
org $1EE630
LDA.b #$03 : STA.w $04C6
; =========================================================

incsrc ZSpriteLib/sprite_macros.asm
incsrc ZSpriteLib/sprite_hooks.asm

; TODO: Sprite_AttemptKillingOfKin

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

incsrc "Sprites/NPCs/bean_vendor.asm"
print  "End of bean_vendor.asm            ", pc

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

incsrc "Sprites/Enemies/helmet_chuchu.asm"
print  "End of helmet_chuchu.asm          ", pc

incsrc "Sprites/Enemies/booki.asm"

incsrc "Sprites/Enemies/thunder_ghost.asm"

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

incsrc "Sprites/Enemies/puffstool.asm"
print  "End of puffstool.asm              ", pc

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

incsrc "Sprites/NPCs/fortune_teller.asm"

; incsrc "Sprites/Bosses/octoboss.asm"
; print  "End of octoboss.asm               ", pc

warnpc $328000

org $328000

incsrc "Sprites/Bosses/twinrova.asm"
print  "End of twinrova.asm               ",  pc

incsrc "Sprites/Bosses/kydreeok.asm"
print  "End of kydreeok.asm               ",  pc

incsrc "Sprites/Bosses/kydreeok_head.asm"
print  "End of kydreeok_head.asm          ",  pc

incsrc "Sprites/Enemies/deku_scrub_enemy.asm"
print  "End of deku_scrub_enemy.asm       ",  pc