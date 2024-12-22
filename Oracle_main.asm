; =========================================================
;           The Legend of Zelda: Oracle of Secrets
;                   Composed by: Scawful
;
; Expanded Banks:
;   21-2A ZS Reserved
;   2B  - Items: all_items.asm
;   2C  - Underworld: dungeons.asm
;   2D  - Menu
;   2E  - HUD
;   2F  - Expanded Message Bank
;   30-32 Sprites: all_sprites.asm
;   33  - Moosh Form Gfx and Palette
;   34  - Time System, Custom Overworld Overlays, Gfx
;   35  - Deku Link Gfx and Palette
;   36  - Zora Link Gfx and Palette
;   37  - Bunny Link Gfx and Palette
;   38  - Wolf Link Gfx and Palette
;   39  - Minish Link Gfx
;   3A  - Mask Routines, Custom Ancillae (Deku Bubble)
;   3B  - GBC Link Gfx
;   3C  - Unused
;   3D  - ZS Tile16
;   3E  - LW ZS Tile32
;   3F  - DW ZS Tile32
;   40  - LW World Map
;   41  - DW World Map
; =========================================================

; ZSCustomOverworld version
; Kept in case of serious issues which impedes progress
ZS_CUSTOM_OW_V2 = 1
incsrc "Overworld/ZSCustomOverworld_Latest.asm"
print  "End of ZSCustomOverworld.asm      ", pc

; Vanilla WRAM and SRAM
incsrc "Core/ram.asm"

namespace Oracle
{
  print ""
  print "Applying patches to Oracle of Secrets"
  print ""

  incsrc "Core/music_macros.asm"
  incsrc "Core/symbols.asm"
  incsrc "Core/message.asm"

  print "  -- Music --  "
  print ""

  incsrc "Music/lost_woods_v2.asm"
  print  "End of Music/lost_woods_v2.asm    ", pc

  incsrc "Music/color_dungeon_theme.asm"
  print  "End of color_dungeon_theme.asm    ", pc

  incsrc "Music/deku_theme.asm"
  print  "End of Music/deku_theme.asm       ", pc

  incsrc "Music/song_of_healing.asm"
  print  "End of Music/song_of_healing.asm  ", pc

  print ""

  print "  -- Overworld --  "
  print ""

  incsrc "Overworld/overworld.asm"

  print ""

  print "  -- Dungeon --  "
  print ""

  incsrc "Dungeons/dungeons.asm"

  print ""

  print "  -- Sprites --  "
  print ""

  incsrc "Sprites/all_sprites.asm"

  print ""

  print "  -- Masks --  "
  print ""

  incsrc "Masks/all_masks.asm"

  print ""

  print "  -- Items --  "
  print ""

  incsrc "Items/all_items.asm"

  print ""

  print "  -- Menu --  "
  print ""

  incsrc "Menu/menu.asm"

  incsrc "Util/item_cheat.asm"

  ; incsrc "Music/ww_ganondorf.asm"
  ; incsrc "Music/great_sea.asm"

  print ""
  print "Finished applying patches"
}
namespace off
