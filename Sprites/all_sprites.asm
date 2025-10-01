; =========================================================

incsrc Core/sprite_macros.asm

org    $308000
incsrc Core/sprite_new_table.asm

Sprite_Farore    = $73
incsrc "Sprites/NPCs/farore.asm"
%print_debug("End of farore.asm                 ")
incsrc "Sprites/NPCs/hyrule_dream.asm"
%print_debug("End of hyrule_dream.asm           ")

Sprite_KydrogNPC = $7B
incsrc "Sprites/Bosses/kydrog.asm"
%print_debug("End of kydrog.asm                 ")

Sprite_MakuTree = $9E
incsrc "Sprites/NPCs/maku_tree.asm"
%print_debug("End of maku_tree.asm              ")

Sprite_MaskSalesman = $E8
incsrc "Sprites/NPCs/mask_salesman.asm"
%print_debug("End of mask_salesman.asm          ")

Sprite_BeanVendor     = $07
Sprite_VillageElder   = $07
incsrc "Sprites/NPCs/village_elder.asm"
incsrc "Sprites/NPCs/bean_vendor.asm"
%print_debug("End of bean_vendor.asm            ")

incsrc "Sprites/Bosses/octoboss.asm"
%print_debug("End of octoboss.asm               ")

Sprite_Mermaid   = $F0
Sprite_Maple     = $F0 ; Subtype 1
Sprite_Librarian = $F0 ; Subtype 2
incsrc "Sprites/NPCs/mermaid.asm"
%print_debug("End of mermaid.asm                ")
incsrc "Sprites/NPCs/maple.asm"
%print_debug("End of maple.asm                  ")

Sprite_Manhandla = $88
incsrc "Sprites/Bosses/manhandla.asm"
%print_debug("End of manhandla.asm              ")

Sprite_BusinessScrub = $14
incsrc "Sprites/Enemies/business_scrub.asm"
%print_debug("End of business_scrub.asm         ")

incsrc "Sprites/Enemies/eon_scrub.asm"
%print_debug("End of eon_scrub.asm              ")

Sprite_Goriya = $2C
incsrc "Sprites/Enemies/goriya.asm"
%print_debug("End of goriya.asm                 ")

Sprite_Darknut = $1D
incsrc "Sprites/Enemies/darknut.asm"
%print_debug("End of darknut.asm                ")

Sprite_SeaUrchin = $AE
incsrc "Sprites/Enemies/sea_urchin.asm"
%print_debug("End of sea_urchin.asm             ")

Sprite_Korok = $F1
incsrc "Sprites/NPCs/korok.asm"
%print_debug("End of korok.asm                  ")

Sprite_Vasu = $D7
incsrc "Sprites/NPCs/vasu.asm"
%print_debug("End of vasu.asm                   ")

incsrc "Sprites/Enemies/keese.asm"
%print_debug("End of keese.asm                  ")
incsrc "Sprites/Bosses/vampire_bat.asm"
%print_debug("End of vampire_bat.asm            ")

incsrc "Sprites/NPCs/bottle_vendor.asm"
%print_debug("End of bottle_vendor.asm          ")

incsrc "Sprites/Enemies/leever.asm"
%print_debug("End of leever.asm                 ")

incsrc "Sprites/Objects/pedestal.asm"
%print_debug("End of pedestal.asm               ")

DontTeleportWithoutFlippers:
{
  LDA.l $7EF356 : BNE +
    RTL
  +
  LDA.b #$2E : STA.b $11
  RTL
}

PutRollerBeneathLink:
{
  JSL Sprite_OAM_AllocateDeferToPlayer
  LDA.w $0DC0,X
  ASL A
  RTL
}

Graphics_Transfer:
{
  LDA.b $A0 : CMP.b #$5A : BNE +
    JSR ApplyManhandlaGraphics
    JSR ApplyManhandlaPalette
  +
  LDA.b $11 : CMP.b #$02
  RTL
}

%print_debug("End of Sprites Bank 30            ")

; =========================================================

%print_debug("")
%print_debug("Bank 31 Sprites")
%print_debug("")

org    $318000
incsrc Core/sprite_functions.asm
%print_debug("End of sprite_functions.asm       ")

Sprite_KydrogBoss = $CB
incsrc "Sprites/Bosses/kydrog_boss.asm"
%print_debug("End of kydrog_boss.asm            ")

Sprite_DekuScrubNPCs = $A0
incsrc "Sprites/NPCs/deku_scrub.asm"
%print_debug("End of deku_scrub.asm             ")

Sprite_AntiKirby = $A8
incsrc "Sprites/Enemies/anti_kirby.asm"
%print_debug("End of anti_kirby.asm             ")

Sprite_HelmetChuchu = $05
incsrc "Sprites/Enemies/helmet_chuchu.asm"
%print_debug("End of helmet_chuchu.asm          ")

Sprite_Booki = $CC
incsrc "Sprites/Enemies/booki.asm"
%print_debug("End of booki.asm                  ")

Sprite_ThunderGhost = $CD
incsrc "Sprites/Enemies/thunder_ghost.asm"
%print_debug("End of thunder_ghost.asm          ")

Sprite_SwitchTrack = $B0
incsrc "Sprites/Objects/switch_track.asm"
%print_debug("End of switch_track.asm           ")

Sprite_Mineswitch = $AF
incsrc "Sprites/Objects/mineswitch.asm"
%print_debug("End of mineswitch.asm             ")

Sprite_VillageDog = $25
incsrc "Sprites/NPCs/village_dog.asm"
%print_debug("End of village_dog.asm            ")

Sprite_Minecart = $A3
incsrc "Sprites/Objects/minecart.asm"
%print_debug("End of minecart.asm               ")

Sprite_DarkLink = $C1
incsrc "Sprites/Bosses/dark_link.asm"
%print_debug("End of dark_link.asm              ")

Sprite_Puffstool = $B1
incsrc "Sprites/Enemies/puffstool.asm"
%print_debug("End of puffstool.asm              ")

; Also beach whirlpool
Sprite_DekuLeaf = $77
incsrc "Sprites/Objects/deku_leaf.asm"
%print_debug("End of deku_leaf.asm              ")

Sprite_Portal = $03
incsrc "Sprites/Objects/portal_sprite.asm"
%print_debug("End of portal_sprite.asm          ")

incsrc "Sprites/NPCs/impa.asm"
%print_debug("End of impa.asm                   ")

Sprite_Poltergeist = $EF
incsrc "Sprites/Enemies/poltergeist.asm"
%print_debug("End of poltergeist.asm            ")

Sprite_PolsVoice = $A4
incsrc "Sprites/Enemies/pols_voice.asm"
%print_debug("End of pols_voice.asm             ")

Sprite_Wolfos = $A9
incsrc "Sprites/Bosses/wolfos.asm"
%print_debug("End of wolfos.asm                 ")

; TODO: Change from digging game guy?
Sprite_IceBlock = $D5
incsrc "Sprites/Objects/ice_block.asm"
%print_debug("End of ice_block.asm              ")

incsrc "Sprites/NPCs/ranch_girl.asm"
%print_debug("End of Ranch Girl.asm             ")

assert pc() <= $328000

; =========================================================

%print_debug("")
%print_debug("Bank 32 Sprites")
%print_debug("")

org $328000

Sprite_Twinrova = $CE
incsrc "Sprites/Bosses/twinrova.asm"
%print_debug("End of twinrova.asm               ")

Sprite_Kydreeok = $7A
incsrc "Sprites/Bosses/kydreeok.asm"
%print_debug("End of kydreeok.asm               ")

Sprite_KydreeokHead = $CF
incsrc "Sprites/Bosses/kydreeok_head.asm"
%print_debug("End of kydreeok_head.asm          ")

; =========================================================

incsrc "Sprites/NPCs/bug_net_kid.asm"
%print_debug("End of bug_net_kid.asm            ")

incsrc "Sprites/Bosses/king_dodongo.asm"
%print_debug("End of king_dodongo.asm           ")

incsrc "Sprites/Bosses/arrghus.asm"
%print_debug("End of arrghus.asm                ")

incsrc "Sprites/NPCs/fortune_teller.asm"
%print_debug("End of fortune_teller.asm         ")

; =========================================================

%print_debug("")
%print_debug("Bank 2C Sprites")
%print_debug("")

incsrc "Sprites/Bosses/lanmola.asm"
%print_debug("End of Lanmola.asm                ")

incsrc "Sprites/Bosses/lanmola_Expanded.asm"
%print_debug("End of Lanmola_Expanded.asm       ")

incsrc "Sprites/NPCs/followers.asm"
%print_debug("End of followers.asm              ")

incsrc "Sprites/Enemies/octorok.asm"
%print_debug("End of octorok.asm                ")

incsrc "Sprites/NPCs/piratian.asm"
%print_debug("End of piratian.asm               ")

incsrc "Sprites/Objects/collectible.asm"
%print_debug("End of collectible.asm            ")

Sprite_EonOwl   = $0A
Sprite_KaeporaGaebora = $0A
incsrc "Sprites/NPCs/eon_owl.asm"
%print_debug("End of eon_owl.asm                ")

Sprite_ZoraPrincess = $B8
incsrc "Sprites/NPCs/eon_zora.asm"
incsrc "Sprites/NPCs/eon_zora_elder.asm"
incsrc "Sprites/NPCs/zora.asm"
incsrc "Sprites/NPCs/zora_princess.asm"
%print_debug("End of zora_princess.asm          ")

incsrc "Sprites/NPCs/tingle.asm"
%print_debug("End of tingle.asm                 ")

incsrc "Sprites/NPCs/goron.asm"
%print_debug("End of goron.asm                  ")

; =========================================================