; =========================================================
;           The Legend of Zelda: Oracle of Secrets
;                   Composed by: Scawful
;
; Expanded Banks:
;   21 - N/A
;   22 - N/A
;   23 - N/A
;   24 - N/A
;   25 - N/A
;   26 - N/A
;   27 - N/A
;   28 - ZS Reserved
;   29 - ZSprite Engine
;   2A - Sprites: all_sprites.asm
;   2B - Items: all_items.asm
;   2C - Dungeon Objects, Spike Subtype
;   2D - Menu
;   2E - HUD
;   2F - House Tag
;   30 - N/A
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
; =========================================================

namespace Oracle
{
  print ""
  print "Applying patches to Oracle of Secrets"
  print ""

  incsrc "Util/ram.asm"
  incsrc "Util/functions.asm"
  incsrc "Util/music_macros.asm"

  ; -------------------------------------------------------
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
  print  "End of Overworld/maku_tree.asm    ", pc

  incsrc "Overworld/lost_woods.asm"
  print  "End of Overworld/lost_woods.asm   ", pc

  print ""

  ; -------------------------------------------------------
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

  incsrc "Dungeons/Lanmola.asm"
  print "End of Dungeons/Lanmola.asm       ", pc

  incsrc "Dungeons/Lanmola_Expanded.asm"
  print "End of Dungeons/Lanmola_Expanded.asm ", pc
  
  incsrc "Dungeons/house_tag.asm"
  print  "End of Dungeons/house_tag.asm       ", pc

  print ""

  ; -------------------------------------------------------
  ; Music

  incsrc "Music/frozen_hyrule.asm"
  print  "End of Music/frozen_hyrule.asm    ", pc

  incsrc "Music/lost_woods.asm"
  print  "End of Music/lost_woods.asm       ", pc

  incsrc "Music/dungeon_theme.asm"
  print  "End of Music/dungeon_theme.asm    ", pc

  ; incsrc "Music/entrance_music_fix.asm"

  print ""

  ; -------------------------------------------------------
  ; Sprites

  print "  -- Sprites --  "
  print ""

  incsrc "Sprites/all_sprites.asm"

  print ""

  ; -------------------------------------------------------
  ; Transformation Masks

  print "  -- Masks --  "
  print ""

  incsrc "Masks/all_masks.asm"

  print ""

  ; -------------------------------------------------------
  ; Items

  print "  -- Items --  "
  print ""

  incsrc "Items/all_items.asm"

  print ""

  ; -------------------------------------------------------
  ; Custom Menu and HUD

  print "  -- Menu --  "
  print ""

  incsrc "Menu/menu.asm"
  print  "End of Menu/menu.asm              ", pc

  ; incsrc "Menu/rings/bestiary_hooks.asm"
  ; incsrc "Menu/rings/bestiary.asm"


  ; -------------------------------------------------------
  incsrc "Util/all_items.asm"
  ; print  "End of Util/all_items.asm         ", pc

  incsrc "Dungeons/house_walls.asm"

  print ""
  print "Finished applying patches"
}
namespace off
