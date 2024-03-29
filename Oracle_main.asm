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
;   29 - ZS Reserved
;   2A - ZS Reserved
;   2B - Items: all_items.asm
;   2C - Dungeon Objects, Spike Subtype, Together Warp Tag
;   2D - Menu
;   2E - HUD
;   2F - 
;   30 - 
;   31 - Sprites: all_sprites.asm
;   32 - Time System
;   33 - Custom Collision Tables
;   34 - 
;   35 - Deku Link GFX
;   36 - Zora Link GFX
;   37 - Bunny Link GFX
;   38 - Wolf Link GFX
;   39 - Minish Link GFX
;   3A - StartupMasks, Palette_ArmorAndGloves, CgramAuxToMain
;   3B - GBC Link GFX
;   3C - Ocarina OW Control Code
;   3D - LW World Map
;   3E - DW World Map
;   3F - Load Custom GFX, Boat GFX
;
; =========================================================

incsrc "Overworld/custom_gfx.asm"
print  "End of custom_gfx.asm             ", pc
incsrc "Overworld/ZCustomOverworld.asm"
print  "End of ZCustomOverworld.asm       ", pc

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
  
  incsrc "Overworld/overworld.asm"

  print ""

  ; -------------------------------------------------------
  ; Dungeon

  print "  -- Dungeon --  "
  print ""

  incsrc "Dungeons/dungeons.asm"

  print ""

  ; -------------------------------------------------------
  ; Music

  print "  -- Music --  "
  print ""

  incsrc "Music/lost_woods.asm"
  print  "End of Music/lost_woods.asm       ", pc

  incsrc "Music/dungeon_theme.asm"
  print  "End of Music/dungeon_theme.asm    ", pc

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

  ; -------------------------------------------------------
  incsrc "Util/all_items.asm"

  ;incsrc "Dungeons/house_walls.asm"

  print ""
  print "Finished applying patches"
}
namespace off
