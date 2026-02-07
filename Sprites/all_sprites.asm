; =========================================================

incsrc Core/sprite_macros.asm
incsrc "Sprites/sprite_registry_ids.asm"

; =========================================================
; Bank $30
org    $308000
%log_start("Bank 30", !LOG_SPRITES)

incsrc Core/sprite_new_table.asm

%log_start("Sprite_Farore", !LOG_SPRITES)
incsrc "Sprites/NPCs/farore.asm"
%log_end("Sprite_Farore", !LOG_SPRITES)

%log_start("hyrule_dream", !LOG_SPRITES)
incsrc "Sprites/NPCs/hyrule_dream.asm"
%log_end("hyrule_dream", !LOG_SPRITES)

%log_start("Sprite_KydrogNPC", !LOG_SPRITES)
incsrc "Sprites/Bosses/kydrog.asm"
%log_end("Sprite_KydrogNPC", !LOG_SPRITES)

%log_start("Sprite_MakuTree", !LOG_SPRITES)
incsrc "Sprites/NPCs/maku_tree.asm"
%log_end("Sprite_MakuTree", !LOG_SPRITES)

%log_start("Sprite_MaskSalesman", !LOG_SPRITES)
incsrc "Sprites/NPCs/mask_salesman.asm"
%log_end("Sprite_MaskSalesman", !LOG_SPRITES)

%log_start("windmill_guy", !LOG_SPRITES)
incsrc "Sprites/NPCs/windmill_guy.asm"
%log_end("windmill_guy", !LOG_SPRITES)

%log_start("village_elder", !LOG_SPRITES)
incsrc "Sprites/NPCs/village_elder.asm"
incsrc "Sprites/NPCs/bean_vendor.asm"
%log_end("village_elder", !LOG_SPRITES)

%log_start("octoboss", !LOG_SPRITES)
incsrc "Sprites/Bosses/octoboss.asm"
%log_end("octoboss", !LOG_SPRITES)

%log_start("mermaid", !LOG_SPRITES)
incsrc "Sprites/NPCs/mermaid.asm"
%log_end("mermaid", !LOG_SPRITES)

%log_start("maple", !LOG_SPRITES)
incsrc "Sprites/NPCs/maple.asm"
%log_end("maple", !LOG_SPRITES)

%log_start("manhandla", !LOG_SPRITES)
incsrc "Sprites/Bosses/manhandla.asm"
%log_end("manhandla", !LOG_SPRITES)

%log_start("business_scrub", !LOG_SPRITES)
incsrc "Sprites/Enemies/business_scrub.asm"
%log_end("business_scrub", !LOG_SPRITES)

%log_start("eon_scrub", !LOG_SPRITES)
incsrc "Sprites/Enemies/eon_scrub.asm"
%log_end("eon_scrub", !LOG_SPRITES)

%log_start("goriya", !LOG_SPRITES)
incsrc "Sprites/Enemies/goriya.asm"
%log_end("goriya", !LOG_SPRITES)

%log_start("darknut", !LOG_SPRITES)
incsrc "Sprites/Enemies/darknut.asm"
%log_end("darknut", !LOG_SPRITES)

%log_start("custom_guard", !LOG_SPRITES)
incsrc "Sprites/Enemies/custom_guard.asm"
%log_end("custom_guard", !LOG_SPRITES)

%log_start("sea_urchin", !LOG_SPRITES)
incsrc "Sprites/Enemies/sea_urchin.asm"
%log_end("sea_urchin", !LOG_SPRITES)

%log_start("korok", !LOG_SPRITES)
incsrc "Sprites/NPCs/korok.asm"
%log_end("korok", !LOG_SPRITES)

%log_start("vasu", !LOG_SPRITES)
incsrc "Sprites/NPCs/vasu.asm"
%log_end("vasu", !LOG_SPRITES)

%log_start("keese", !LOG_SPRITES)
incsrc "Sprites/Enemies/keese.asm"
%log_end("keese", !LOG_SPRITES)

%log_start("vampire_bat", !LOG_SPRITES)
incsrc "Sprites/Bosses/vampire_bat.asm"
%log_end("vampire_bat", !LOG_SPRITES)

%log_start("bottle_vendor", !LOG_SPRITES)
incsrc "Sprites/NPCs/bottle_vendor.asm"
%log_end("bottle_vendor", !LOG_SPRITES)

%log_start("leever", !LOG_SPRITES)
incsrc "Sprites/Enemies/leever.asm"
%log_end("leever", !LOG_SPRITES)

%log_start("pedestal", !LOG_SPRITES)
incsrc "Sprites/Objects/pedestal.asm"
%log_end("pedestal", !LOG_SPRITES)

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
  ; Hooked into UnderworldTransition_ScrollRoom ($02BE5E). Keep this hook
  ; transparent to the caller: preserve DB/X/Y/P and re-emit the original
  ; `LDA $11 : CMP #$02` flags for the caller's branch.
  PHP
  PHX
  PHY
  PHB : PHK : PLB

  LDA.b $A0 : CMP.b #$5A : BNE +
    JSR ApplyManhandlaGraphics
    JSR ApplyManhandlaPalette
  +

  PLB
  PLY
  PLX
  PLP

  LDA.b $11 : CMP.b #$02
  RTL
}

%log_end("Bank 30", !LOG_SPRITES)

; =========================================================
; Bank $31
org    $318000
%log_start("Bank 31", !LOG_SPRITES)

incsrc Core/sprite_functions.asm

%log_start("kydrog_boss", !LOG_SPRITES)
incsrc "Sprites/Bosses/kydrog_boss.asm"
%log_end("kydrog_boss", !LOG_SPRITES)

%log_start("deku_scrub", !LOG_SPRITES)
incsrc "Sprites/NPCs/deku_scrub.asm"
%log_end("deku_scrub", !LOG_SPRITES)

%log_start("anti_kirby", !LOG_SPRITES)
incsrc "Sprites/Enemies/anti_kirby.asm"
%log_end("anti_kirby", !LOG_SPRITES)

%log_start("helmet_chuchu", !LOG_SPRITES)
incsrc "Sprites/Enemies/helmet_chuchu.asm"
%log_end("helmet_chuchu", !LOG_SPRITES)

%log_start("booki", !LOG_SPRITES)
incsrc "Sprites/Enemies/booki.asm"
%log_end("booki", !LOG_SPRITES)

%log_start("thunder_ghost", !LOG_SPRITES)
incsrc "Sprites/Enemies/thunder_ghost.asm"
%log_end("thunder_ghost", !LOG_SPRITES)

%log_start("switch_track", !LOG_SPRITES)
incsrc "Sprites/Objects/switch_track.asm"
%log_end("switch_track", !LOG_SPRITES)

%log_start("mineswitch", !LOG_SPRITES)
incsrc "Sprites/Objects/mineswitch.asm"
%log_end("mineswitch", !LOG_SPRITES)

%log_start("village_dog", !LOG_SPRITES)
incsrc "Sprites/NPCs/village_dog.asm"
%log_end("village_dog", !LOG_SPRITES)

%log_start("minecart", !LOG_SPRITES)
incsrc "Sprites/Objects/minecart.asm"
%log_end("minecart", !LOG_SPRITES)

%log_start("dark_link", !LOG_SPRITES)
incsrc "Sprites/Bosses/dark_link.asm"
%log_end("dark_link", !LOG_SPRITES)

%log_start("puffstool", !LOG_SPRITES)
incsrc "Sprites/Enemies/puffstool.asm"
%log_end("puffstool", !LOG_SPRITES)

%log_start("deku_leaf", !LOG_SPRITES)
; Also beach whirlpool
incsrc "Sprites/Objects/deku_leaf.asm"
%log_end("deku_leaf", !LOG_SPRITES)

%log_start("portal_sprite", !LOG_SPRITES)
incsrc "Sprites/Objects/portal_sprite.asm"
%log_end("portal_sprite", !LOG_SPRITES)

%log_start("impa", !LOG_SPRITES)
incsrc "Sprites/NPCs/impa.asm"
%log_end("impa", !LOG_SPRITES)

%log_start("poltergeist", !LOG_SPRITES)
incsrc "Sprites/Enemies/poltergeist.asm"
%log_end("poltergeist", !LOG_SPRITES)

%log_start("pols_voice", !LOG_SPRITES)
incsrc "Sprites/Enemies/pols_voice.asm"
%log_end("pols_voice", !LOG_SPRITES)

%log_start("wolfos", !LOG_SPRITES)
incsrc "Sprites/Bosses/wolfos.asm"
%log_end("wolfos", !LOG_SPRITES)

%log_start("ice_block", !LOG_SPRITES)
; TODO: Change from digging game guy?
incsrc "Sprites/Objects/ice_block.asm"
%log_end("ice_block", !LOG_SPRITES)

assert pc() <= $328000

%log_end("Bank 31", !LOG_SPRITES)

; =========================================================
; Bank $32
org $328000
%log_start("Bank 32", !LOG_SPRITES)

%log_start("twinrova", !LOG_SPRITES)
incsrc "Sprites/Bosses/twinrova.asm"
%log_end("twinrova", !LOG_SPRITES)

%log_start("kydreeok", !LOG_SPRITES)
incsrc "Sprites/Bosses/kydreeok.asm"
%log_end("kydreeok", !LOG_SPRITES)

%log_start("kydreeok_head", !LOG_SPRITES)
incsrc "Sprites/Bosses/kydreeok_head.asm"
%log_end("kydreeok_head", !LOG_SPRITES)

%log_start("bug_net_kid", !LOG_SPRITES)
incsrc "Sprites/NPCs/bug_net_kid.asm"
%log_end("bug_net_kid", !LOG_SPRITES)

%log_start("king_dodongo", !LOG_SPRITES)
incsrc "Sprites/Bosses/king_dodongo.asm"
%log_end("king_dodongo", !LOG_SPRITES)

%log_start("arrghus", !LOG_SPRITES)
incsrc "Sprites/Bosses/arrghus.asm"
%log_end("arrghus", !LOG_SPRITES)

%log_start("fortune_teller", !LOG_SPRITES)
incsrc "Sprites/NPCs/fortune_teller.asm"
%log_end("fortune_teller", !LOG_SPRITES)

%log_start("ranch_girl", !LOG_SPRITES)
incsrc "Sprites/NPCs/ranch_girl.asm"
%log_end("ranch_girl", !LOG_SPRITES)

%log_start("cloud_bridge", !LOG_SPRITES)
incsrc "Sprites/Objects/cloud_bridge.asm"
%log_end("cloud_bridge", !LOG_SPRITES)

%log_end("Bank 32", !LOG_SPRITES)

; =========================================================
; Bank $2C
; Note: These sprites are located in the Dungeon bank

%log_start("lanmola", !LOG_DUNGEON)
incsrc "Sprites/Bosses/lanmola.asm"
%log_end("lanmola", !LOG_DUNGEON)

%log_start("lanmola_expanded", !LOG_DUNGEON)
incsrc "Sprites/Bosses/lanmola_Expanded.asm"
%log_end("lanmola_expanded", !LOG_DUNGEON)

%log_start("followers", !LOG_DUNGEON)
incsrc "Sprites/NPCs/followers.asm"
%log_end("followers", !LOG_DUNGEON)

%log_start("octorok", !LOG_DUNGEON)
incsrc "Sprites/Enemies/octorok.asm"
%log_end("octorok", !LOG_DUNGEON)

%log_start("piratian", !LOG_DUNGEON)
incsrc "Sprites/NPCs/piratian.asm"
%log_end("piratian", !LOG_DUNGEON)

%log_start("collectible", !LOG_DUNGEON)
incsrc "Sprites/Objects/collectible.asm"
%log_end("collectible", !LOG_DUNGEON)

%log_start("eon_owl", !LOG_DUNGEON)
incsrc "Sprites/NPCs/eon_owl.asm"
%log_end("eon_owl", !LOG_DUNGEON)

%log_start("zora_princess", !LOG_DUNGEON)
incsrc "Sprites/NPCs/eon_zora.asm"
incsrc "Sprites/NPCs/eon_zora_elder.asm"
incsrc "Sprites/NPCs/zora.asm"
incsrc "Sprites/NPCs/zora_princess.asm"
%log_end("zora_princess", !LOG_DUNGEON)

%log_start("tingle", !LOG_DUNGEON)
incsrc "Sprites/NPCs/tingle.asm"
%log_end("tingle", !LOG_DUNGEON)

%log_start("goron", !LOG_DUNGEON)
incsrc "Sprites/NPCs/goron.asm"
%log_end("goron", !LOG_DUNGEON)

; =========================================================
