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
;   28 - ZS Reserved
;   29 - ZSprite Jump Table
;   2A - Custom Sprites: Farore, Kydrog, Maku Tree, Mask Salesman
;                        Deku Scrub, Anti Kirby, Village Dog, Minecart
;                        Impa, Bug Net Kid
;   2B - Custom Items: Feather, Book, Sword Collect
;   2C - Dungeon Objects, Spike Subtype
;   2D - Menu
;   2E - HUD
;   2F - House Tag
;   30 - 
;   31 - Deku Link Code
;   32 - Entrance Music Fix 
;   33 - Together Warp Tag 
;   34 - N/A
;   35 - Deku Link GFX
;   36 - Zora Link GFX
;   37 - Bunny Link GFX
;   38 - Wolf Link GFX
;   39 - Minish Link GFX
;   3A - StartupMasks, Palette_ArmorAndGloves, CgramAuxToMain
;   3B - GBC Link GFX
;   3C - N/A
;   3D - N/A
;   3F - Load Custom GFX, Boat GFX
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

  incsrc "Overworld/custom_gfx.asm"
  print  "End of custom_gfx.asm             ", pc

  incsrc "Overworld/maku_tree.asm"
  print  "End of Overworld/maku_tree.asm       ", pc

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

  incsrc "Music/frozen_hyrule.asm"
  print  "End of Music/frozen_hyrule.asm    ", pc

  incsrc "Music/lost_woods.asm"
  print  "End of Music/lost_woods.asm       ", pc

  incsrc "Music/dungeon_theme.asm"
  print  "End of Music/dungeon_theme.asm    ", pc

  incsrc "Music/entrance_music_fix.asm"

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
  ; Sprites

  print "  -- Sprites --  "
  print ""

  incsrc "Sprites/all_sprites.asm"

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

  incsrc "Items/all_items.asm"

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
