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

incsrc "Util/macros.asm"

incsrc "Overworld/ZSCustomOverworld.asm"
%print_debug("End of ZSCustomOverworld.asm      ")

; Vanilla WRAM and SRAM
incsrc "Core/ram.asm"

namespace Oracle
{
  incsrc "Core/link.asm"
  incsrc "Core/sram.asm"
  incsrc "Core/symbols.asm"
  incsrc "Core/message.asm"

  %print_debug("  -- Music --  ")
  %print_debug("")
  incsrc "Music/all_music.asm"
  %print_debug("")

  %print_debug("  -- Overworld --  ")
  %print_debug("")
  incsrc "Overworld/overworld.asm"
  %print_debug("")

  %print_debug("  -- Dungeon --  ")
  %print_debug("")
  incsrc "Dungeons/dungeons.asm"
  %print_debug("")

  %print_debug("  -- Sprites --  ")
  %print_debug("")
  incsrc "Sprites/all_sprites.asm"
  %print_debug("")

  %print_debug("  -- Masks --  ")
  %print_debug("")
  incsrc "Masks/all_masks.asm"
  %print_debug("")

  %print_debug("  -- Items --  ")
  %print_debug("")
  incsrc "Items/all_items.asm"
  %print_debug("")

  %print_debug("  -- Menu --  ")
  %print_debug("")
  incsrc "Menu/menu.asm"
  incsrc "Util/item_cheat.asm"
  incsrc "Core/patches.asm"

  %print_debug("")
  %print_debug("Finished applying patches")
}
namespace off
