; =============================================================================
;           The Legend of Zelda: Oracle of Secrets
;                   Composed by: Scawful
;
; Hacks Included:
;   Inventory Screen Overhaul
;   Book Reveals Secrets
;   Bunny Hood Item
;   Ice Rod Freezes Water
;   Intro skip after leaving house
;   Key block link's awakening
;   Lost Sea Area Combo
;
; Expanded Banks Key:
;   21 - N/A
;   22 - N/A
;   23 - N/A
;   24 - N/A
;   25 - N/A
;   26 - N/A
;   27 - N/A
;   28 - Spike Subtype
;   29 - New Sprite Jump Table
;   2A - Jump Feather
;   2B - Book of Secrets
;   2C - N/A
;   2D - Menu
;   2E - HUD
;   2F - House Tag
;   30 - Custom Sprites and New Functions
;   31 - Deku Link Code
;   32 - None
;   33 - None
;   34 - Zora Link Code
;   35 - Deku Link GFX
;   36 - Zora Link GFX
;   37 - Bunny Link GFX
;   38 - Wolf Link GFX
;   39 - Minish Link GFX
;   3A - StartupMasks, Palette_ArmorAndGloves, CgramAuxToMain
;   3B - N/A
;   3C - N/A
;   3D - N/A
;   3F - Boat GFX
;
; Used Free RAM:
;   $B6   - Cutscene State
;
; =============================================================================

namespace Oracle
{
  print ""
  print "Applying patches to Oracle of Secrets"
  print ""

  incsrc "Util/ram.asm"
  incsrc "Util/functions.asm"
  incsrc "Util/music_macros.asm"

  ; ---------------------------------------------------------
  ; Overworld

  print "  -- Overworld --  "
  print ""

  incsrc "Overworld/pit_damage.asm"
  print  "End of Overworld/pit_damage.asm   ", pc

  incsrc "Overworld/master_sword.asm"
  print  "End of master_sword.asm           ", pc

  print ""

  ; ---------------------------------------------------------
  ; Dungeon

  print "  -- Dungeon --  "
  print ""

  incsrc "Dungeons/keyblock.asm"
  print  "End of Dungeons/keyblock.asm      ", pc

  incsrc "Dungeons/sanctuary_transition.asm"

  incsrc "Dungeons/entrances.asm"
  print  "End of Dungeons/entrances.asm     ", pc

  incsrc "Dungeons/mothula.asm"
  print  "End of Dungeons/mothula.asm       ", pc

  incsrc "Dungeons/enemy_damage.asm"
  print  "End of Dungeons/enemy_damage.asm  ", pc

  incsrc "Dungeons/together_warp_tag.asm"
  print  "End of together_warp_tag.asm      ", pc

  incsrc "Dungeons/arrghus.asm"
  print  "End of Dungeons/arrghus.asm       ", pc

  incsrc "Dungeons/Objects/object_handler.asm"
  print  "End of object_handler.asm         ", pc
  
  incsrc "Dungeons/spike_subtype.asm"
  print  "End of spike_subtype.asm          ", pc

  print ""

  ; ---------------------------------------------------------
  ; Music

  ; incsrc "Music/stone_tower_temple.asm"
  ; print  "End of stone_tower_temple.asm     ", pc

  incsrc "Music/frozen_hyrule.asm"
  print  "End of Music/frozen_hyrule.asm    ", pc

  incsrc "Music/lost_woods.asm"
  print  "End of Music/lost_woods.asm       ", pc

  incsrc "Music/dungeon_theme.asm"
  print  "End of Music/dungeon_theme.asm    ", pc

  incsrc "Music/entrance_music_fix.asm"

  ; incsrc "Music/boss_theme.asm"
  ; print  "End of Music/boss_theme.asm       ", pc

  print ""

  ; ---------------------------------------------------------
  ; Events

  print "  -- Events --  "
  print ""

  incsrc "Events/house_tag.asm"
  print  "End of Events/house_tag.asm       ", pc

  incsrc "Events/lost_woods.asm"
  print  "End of Events/lost_woods.asm      ", pc

  incsrc "Events/snow_overlay.asm"
  print  "End of Events/snow_overlay.asm    ", pc

  print ""

  ; ---------------------------------------------------------
  ; Graphics

  print "  -- Graphics --  "
  print ""

  incsrc "Graphics/boat_gfx.asm"
  print  "End of Graphics/boat_gfx.asm      ", pc

  incsrc "Events/maku_tree.asm"
  print  "End of Events/maku_tree.asm       ", pc

  print ""


  ; ---------------------------------------------------------
  ; Sprites

  print "  -- Sprites --  "
  print ""

  incsrc "Sprites/sprites.asm"

  print ""

  ; ---------------------------------------------------------
  ; Transformation Masks

  print "  -- Masks --  "
  print ""

  incsrc "Masks/all_masks.asm"

  print ""

  ; ---------------------------------------------------------
  ; Items

  print "  -- Items --  "
  print ""

  incsrc "Items/bottle_net.asm"
  print  "End of Items/bottle_net.asm       ", pc

  incsrc "Items/ocarina.asm"
  print  "End of Items/ocarina.asm          ", pc

  incsrc "Items/jump_feather.asm"
  print  "End of Items/jump_feather.asm     ", pc

  incsrc "Items/ice_rod.asm"
  print  "End of Items/ice_rod.asm          ", pc

  incsrc "Items/book_of_secrets.asm"
  print  "End of Items/book_of_secrets.asm  ", pc

  incsrc "Items/sword_collect.asm"
  print  "End of Items/sword_collect.asm    ", pc


  print ""

  ; ---------------------------------------------------------
  ; Custom Menu and HUD

  print "  -- Menu --  "
  print ""

  incsrc "Menu/menu.asm"
  print  "End of Menu/menu.asm              ", pc

  ; incsrc "Menu/rings/bestiary_hooks.asm"
  ; incsrc "Menu/rings/bestiary.asm"


  ; ---------------------------------------------------------
  incsrc "Util/all_items.asm"
  ; print  "End of Util/all_items.asm         ", pc

  print ""
  print "Finished applying patches"
}
namespace off
