; =========================================================

incsrc Core/sprite_macros.asm

org    $308000
incsrc Core/sprite_new_table.asm

Sprite_Farore    = $73
incsrc "Sprites/NPCs/farore.asm"
print  "End of farore.asm                 ", pc
incsrc "Sprites/NPCs/hyrule_dream.asm"
print  "End of hyrule_dream.asm           ", pc

Sprite_KydrogNPC = $7B
incsrc "Sprites/Bosses/kydrog.asm"
print  "End of kydrog.asm                 ", pc

Sprite_MakuTree = $9E
incsrc "Sprites/NPCs/maku_tree.asm"
print  "End of maku_tree.asm              ", pc

Sprite_MaskSalesman = $E8
incsrc "Sprites/NPCs/mask_salesman.asm"
print  "End of mask_salesman.asm          ", pc

Sprite_BeanVendor     = $07
Sprite_VillageElder   = $07
incsrc "Sprites/NPCs/village_elder.asm"
incsrc "Sprites/NPCs/bean_vendor.asm"
print  "End of bean_vendor.asm            ", pc

incsrc "Sprites/Bosses/octoboss.asm"
print  "End of octoboss.asm               ", pc

Sprite_Mermaid   = $F0
Sprite_Maple     = $F0 ; Subtype 1
Sprite_Librarian = $F0 ; Subtype 2
incsrc "Sprites/NPCs/mermaid.asm"
print  "End of mermaid.asm                ", pc
incsrc "Sprites/NPCs/maple.asm"
print  "End of maple.asm                  ", pc

Sprite_Manhandla = $88
incsrc "Sprites/Bosses/manhandla.asm"
print  "End of manhandla.asm              ", pc

Sprite_BusinessScrub = $14
incsrc "Sprites/Enemies/business_scrub.asm"
print  "End of business_scrub.asm         ",  pc

incsrc "Sprites/Enemies/eon_scrub.asm"
print  "End of eon_scrub.asm              ",  pc

Sprite_Goriya = $2C
incsrc "Sprites/Enemies/goriya.asm"
print  "End of goriya.asm                 ",  pc

Sprite_Darknut = $1D
incsrc "Sprites/Enemies/darknut.asm"
print  "End of darknut.asm                ",  pc

Sprite_SeaUrchin = $AE
incsrc "Sprites/Enemies/sea_urchin.asm"
print  "End of sea_urchin.asm             ", pc

Sprite_Korok = $F1
incsrc "Sprites/NPCs/korok.asm"
print  "End of korok.asm                  ", pc

Sprite_Vasu = $D7
incsrc "Sprites/NPCs/vasu.asm"
print  "End of vasu.asm                   ", pc

incsrc "Sprites/Enemies/keese.asm"
print  "End of keese.asm                  ", pc
incsrc "Sprites/Bosses/vampire_bat.asm"
print  "End of vampire_bat.asm            ", pc

incsrc "Sprites/NPCs/bottle_vendor.asm"
print  "End of bottle_vendor.asm          ", pc

incsrc "Sprites/Enemies/leever.asm"
print  "End of leever.asm                 ", pc

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

print "End of Sprites Bank 30            ", pc

; UnderworldTransition_ScrollRoom
org $02BE5E : JSL Graphics_Transfer

; Whirlpool
org $1EEEE4 : JSL DontTeleportWithoutFlippers

; SpriteDraw_Roller
org $058EE6 : JSL PutRollerBeneathLink

; =========================================================

print  ""
print  "Bank 31 Sprites"
print  ""

org    $318000
incsrc Core/sprite_functions.asm
print  "End of sprite_functions.asm       ", pc

Sprite_KydrogBoss = $CB
incsrc "Sprites/Bosses/kydrog_boss.asm"
print  "End of kydrog_boss.asm            ", pc

Sprite_DekuScrubNPCs = $A0
incsrc "Sprites/NPCs/deku_scrub.asm"
print  "End of deku_scrub.asm             ", pc

Sprite_AntiKirby = $A8
incsrc "Sprites/Enemies/anti_kirby.asm"
print  "End of anti_kirby.asm             ", pc

Sprite_HelmetChuchu = $05
incsrc "Sprites/Enemies/helmet_chuchu.asm"
print  "End of helmet_chuchu.asm          ", pc

Sprite_Booki = $CC
incsrc "Sprites/Enemies/booki.asm"
print  "End of booki.asm                  ", pc

Sprite_ThunderGhost = $CD
incsrc "Sprites/Enemies/thunder_ghost.asm"
print  "End of thunder_ghost.asm          ", pc

Sprite_SwitchTrack = $B0
incsrc "Sprites/Objects/switch_track.asm"
print  "End of switch_track.asm           ", pc

Sprite_Mineswitch = $AF
incsrc "Sprites/Objects/mineswitch.asm"
print  "End of mineswitch.asm             ", pc

Sprite_VillageDog = $25
incsrc "Sprites/NPCs/village_dog.asm"
print  "End of village_dog.asm            ",  pc

Sprite_Minecart = $A3
incsrc "Sprites/Objects/minecart.asm"
print  "End of minecart.asm               ",  pc

Sprite_DarkLink = $C1
incsrc "Sprites/Bosses/dark_link.asm"
print  "End of dark_link.asm              ", pc

Sprite_Puffstool = $B1
incsrc "Sprites/Enemies/puffstool.asm"
print  "End of puffstool.asm              ", pc

; Also beach whirlpool
Sprite_DekuLeaf = $77
incsrc "Sprites/Objects/deku_leaf.asm"
print  "End of deku_leaf.asm              ",  pc

Sprite_Portal = $03
incsrc "Sprites/Objects/portal_sprite.asm"
print  "End of portal_sprite.asm          ",  pc

incsrc "Sprites/NPCs/impa.asm"
print  "End of impa.asm                   ",  pc

Sprite_Poltergeist = $EF
incsrc "Sprites/Enemies/poltergeist.asm"
print  "End of poltergeist.asm            ",  pc

Sprite_PolsVoice = $A4
incsrc "Sprites/Enemies/pols_voice.asm"
print  "End of pols_voice.asm             ",  pc

Sprite_Wolfos = $A9
incsrc "Sprites/Bosses/wolfos.asm"
print  "End of wolfos.asm                 ",  pc

; TODO: Change from digging game guy?
Sprite_IceBlock = $D5
incsrc "Sprites/Objects/ice_block.asm"
print  "End of ice_block.asm              ",  pc

incsrc "Sprites/NPCs/ranch_girl.asm"
print  "End of Ranch Girl.asm             ", pc

assert pc() <= $328000

; =========================================================

print  ""
print  "Bank 32 Sprites"
print  ""

org $328000

Sprite_Twinrova = $CE
incsrc "Sprites/Bosses/twinrova.asm"
print  "End of twinrova.asm               ",  pc

Sprite_Kydreeok = $7A
incsrc "Sprites/Bosses/kydreeok.asm"
print  "End of kydreeok.asm               ",  pc

Sprite_KydreeokHead = $CF
incsrc "Sprites/Bosses/kydreeok_head.asm"
print  "End of kydreeok_head.asm          ",  pc

; =========================================================

incsrc "Sprites/NPCs/bug_net_kid.asm"
print  "End of bug_net_kid.asm            ", pc

incsrc "Sprites/Bosses/king_dodongo.asm"
print  "End of king_dodongo.asm           ", pc

incsrc "Sprites/Bosses/arrghus.asm"
print  "End of arrghus.asm                ", pc

incsrc "Sprites/NPCs/fortune_teller.asm"
print  "End of fortune_teller.asm         ", pc

; =========================================================

print ""
print "Bank 2C Sprites"
print ""

incsrc "Sprites/Bosses/lanmola.asm"
print  "End of Lanmola.asm                ", pc

incsrc "Sprites/Bosses/lanmola_Expanded.asm"
print  "End of Lanmola_Expanded.asm       ", pc

incsrc "Sprites/NPCs/followers.asm"
print  "End of followers.asm              ", pc

incsrc "Sprites/Enemies/octorok.asm"
print  "End of octorok.asm                ", pc

incsrc "Sprites/NPCs/piratian.asm"
print  "End of piratian.asm               ", pc

incsrc "Sprites/Objects/collectible.asm"
print  "End of collectible.asm            ", pc

Sprite_EonOwl   = $0A
Sprite_KaeporaGaebora = $0A
incsrc "Sprites/NPCs/eon_owl.asm"
print  "End of eon_owl.asm                ", pc

Sprite_ZoraPrincess = $B8
incsrc "Sprites/NPCs/eon_zora.asm"
incsrc "Sprites/NPCs/eon_zora_elder.asm"
incsrc "Sprites/NPCs/zora.asm"
incsrc "Sprites/NPCs/zora_princess.asm"
print  "End of zora_princess.asm          ", pc

incsrc "Sprites/NPCs/tingle.asm"
print  "End of tingle.asm                 ", pc

incsrc "Sprites/NPCs/goron.asm"
print  "End of goron.asm                  ", pc

; =========================================================

; Sprite Recoil and Death
; TODO: Sprite_AttemptKillingOfKin
; Kydreeok Head die like Sidenexx
org $06F003 : CMP.b #$CF

; Remove sidenexx death from booki
org $06EFFF : NOP #4

; Make Dark Link die like sidenexx
org $06F003 : CMP.b #$C1

; Make Helmet ChuChu recoil link
org $06F37D : CMP.b #$05

; Make Kydreeok head recoil Link
org $06F381 : CMP.b #$CF

; =========================================================

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

assert pc() <= $00841E

; =========================================================

org $1EF27D
ShopItem_Banana:
{
  JSR $F4CE   ; SpriteDraw_ShopItem
  JSR $FE78   ; Sprite_CheckIfActive_Bank1E
  JSL $1EF4F3 ; Sprite_BehaveAsBarrier
  JSR $F391   ; ShopItem_CheckForAPress
  BCC .exit

    LDA.l Bananas : CMP.b #$0A : BCS .error
    LDA.b #$1E : LDY.b #$00
    JSR $F39E ; ShopItem_HandleCost
    BCC $F1A1 ; ShopItem_GiveFailureMessage

    STZ.w SprState,X
    INC.b Bananas

    LDY.b #$42 : JSR $F366 ; ShopItem_HandleReceipt

  .exit
  RTS
  .error
  JSR $F38A ; ShopItem_PlayBeep
}
assert pc() <= $1EF2AB

; =========================================================

; Shop item heart OAM
; SpriteDraw_ShopItem
org $1EF42E
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw   4,  16 : db $30, $02, $00, $00 ; 0
  dw   0,   0 : db $E5, $03, $00, $02 ; item
  dw   4,  11 : db $38, $03, $00, $00 ; shadow

; =========================================================

; Octoballoon_FormBabby
; Reduce by half the number of babies spawned
org $06D814 : LDA.b #$02

; SpritePrep_HauntedGroveOstritch
org $068BB2 : NOP #11

; HauntedGroveRabbit_Idle
org $1E9A8F : NOP #5

; MedallionTablet (Goron)
org $05F274 : LDA.l $7EF378 ; Unused SRAM

org $08C2E3 : dw $006F ; BUTTER SWORD DIALOGUE

; Fix the capital 'B' debug item cheat.
org $0CDC26 : db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; Update Catfish Item Get to Bottle
org $1DE184 : LDA.b #$16 : STA.w $0D90, X

; Follower_Disable
; Don't disable Kiki so we can switch maps with him.
org $09ACF3 : LDA.l $7EF3CC : CMP.b #$0E

; Kiki, don't care if we're not in dark world
org $099FEB : LDA.b $8A : AND.b #$FF

org $1EE48E : NOP #6

; Kiki activate cutscene 3 (tail palace)
org $1EE630 : LDA.b #$03 : STA.w $04C6

; Kid at ranch checks for flute
org $05FF7D : LDA.l $7EF34C : CMP.b #$01

; Raven Damage (LW/DW)
org $068963 : db $81, $84

; Running Man draw palette
org $05E9CD
SpriteDraw_RunningBoy:
  #_05E9CD: dw   0,  -8 : db $2C, $00, $00, $02
  #_05E9D5: dw   0,   0 : db $EE, $0E, $00, $02

  #_05E9DD: dw   0,  -7 : db $2C, $00, $00, $02
  #_05E9E5: dw   0,   1 : db $EE, $4E, $00, $02

  #_05E9ED: dw   0,  -8 : db $2A, $00, $00, $02
  #_05E9F5: dw   0,   0 : db $CA, $0E, $00, $02

  #_05E9FD: dw   0,  -7 : db $2A, $00, $00, $02
  #_05EA05: dw   0,   1 : db $CA, $4E, $00, $02

  #_05EA0D: dw   0,  -8 : db $2E, $00, $00, $02
  #_05EA15: dw   0,   0 : db $CC, $0E, $00, $02

  #_05EA1D: dw   0,  -7 : db $2E, $00, $00, $02
  #_05EA25: dw   0,   1 : db $CE, $0E, $00, $02

  #_05EA2D: dw   0,  -8 : db $2E, $40, $00, $02
  #_05EA35: dw   0,   0 : db $CC, $4E, $00, $02

  #_05EA3D: dw   0,  -7 : db $2E, $40, $00, $02
  #_05EA45: dw   0,   1 : db $CE, $4E, $00, $02

; Sword Barrier Sprite Prep
; Skip overworld flag check, sprite is indoors now
org $06891B : NOP #12
