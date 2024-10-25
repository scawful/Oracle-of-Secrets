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

; Mushroom Grotto ID 0x0C (Palace of Darkness)
; Tail Palace ID 0x0A (Swamp Palace)
; Kalyxo Castle ID 0x10 (Skull Woods)
; Zora Temple ID 0x16 (Thieves Town)
; Glacia Estate 0x12 (Ice Palace)
; Goron Mines 0x0E (Misery Mire)
; Dragon Ship 0x18 (Turtle Rock)

; =========================================================

; ZSCustomOverworld version
; Kept in case of serious issues which impedes progress
ZS_CUSTOM_OW_V2 = 1
if ZS_CUSTOM_OW_V2 == 1
  incsrc "Overworld/ZCustomOverworld2.asm"
  print  "End of ZCustomOverworld2.asm      ", pc
else
  incsrc "Overworld/ZCustomOverworld.asm"
  print  "End of ZCustomOverworld.asm       ", pc
endif

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

  ; -------------------------------------------------------
  ; Music

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

  print "  -- Events --  "
  print ""

  incsrc "Events/all_dreams.asm"

  print ""

  ; -------------------------------------------------------
  ; Custom Menu and HUD

  print "  -- Menu --  "
  print ""

  incsrc "Menu/menu.asm"

  ; -------------------------------------------------------
  ; Misc

  incsrc "Util/item_cheat.asm"

  ; -------------------------------------------------------

  ; incsrc "Music/ww_ganondorf.asm"

  ; incsrc "Music/great_sea.asm"

  print ""
  print "Finished applying patches"
}
namespace off
