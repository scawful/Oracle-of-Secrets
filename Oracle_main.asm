; =========================================================
;           The Legend of Zelda: Oracle of Secrets
;                   Composed by: Scawful
;
; Custom Code and Data Memory Map:
;
;   Bank $20 ($208000): Expanded Music (Music/all_music.asm)
;   Bank $21-$27: ZS Reserved
;   Bank $28 ($288000): ZSCustomOverworld (Overworld/ZSCustomOverworld.asm)
;   Bank $29-$2A: ZS Reserved
;   Bank $2B ($2B8000): Items (Items/all_items.asm)
;   Bank $2C ($2C8000): Underworld/Dungeons (Dungeons/dungeons.asm)
;   Bank $2D ($2D8000): Menu (Menu/menu.asm)
;   Bank $2E ($2E8000): HUD (Menu/menu.asm)
;   Bank $2F ($2F8000): Expanded Message Bank (Core/message.asm)
;   Bank $30 ($308000): Sprites (Sprites/all_sprites.asm)
;   Bank $31 ($318000): Sprites (Sprites/all_sprites.asm)
;   Bank $32 ($328000): Sprites (Sprites/all_sprites.asm)
;   Bank $33 ($338000): Moosh Form Gfx and Palette (Masks/all_masks.asm)
;   Bank $34 ($348000): Time System, Custom Overworld Overlays, Gfx (Masks/all_masks.asm)
;   Bank $35 ($358000): Deku Link Gfx and Palette (Masks/all_masks.asm)
;   Bank $36 ($368000): Zora Link Gfx and Palette (Masks/all_masks.asm)
;   Bank $37 ($378000): Bunny Link Gfx and Palette (Masks/all_masks.asm)
;   Bank $38 ($388000): Wolf Link Gfx and Palette (Masks/all_masks.asm)
;   Bank $39 ($398000): Minish Link Gfx (Masks/all_masks.asm)
;   Bank $3A ($3A8000): Mask Routines, Custom Ancillae (Deku Bubble) (Masks/all_masks.asm)
;   Bank $3B ($3B8000): GBC Link Gfx (Masks/all_masks.asm)
;   Bank $3C: Unused
;   Bank $3D: ZS Tile16
;   Bank $3E: LW ZS Tile32
;   Bank $3F: DW ZS Tile32
;   Bank $40 ($408000): LW World Map (Overworld/overworld.asm)
;   Bank $41 ($418000): DW World Map (Overworld/overworld.asm)
;
;   Patches: Core/patches.asm and Util/item_cheat.asm use pushpc/pullpc and org
;            for targeted modifications within vanilla ROM addresses.
; =========================================================

incsrc "Util/macros.asm"

incsrc "Overworld/ZSCustomOverworld.asm"
%log_end("ZSCustomOverworld.asm", !LOG_OVERWORLD)

; Vanilla WRAM and SRAM
incsrc "Core/ram.asm"

namespace Oracle
{
  incsrc "Core/link.asm"
  incsrc "Core/sram.asm"
  incsrc "Core/symbols.asm"
  incsrc "Core/message.asm"

  %log_section("Music", !LOG_MUSIC)
  incsrc "Music/all_music.asm"

  %log_section("Overworld", !LOG_OVERWORLD)
  incsrc "Overworld/overworld.asm"

  %log_section("Dungeon", !LOG_DUNGEON)
  incsrc "Dungeons/dungeons.asm"

  %log_section("Sprites", !LOG_SPRITES)
  incsrc "Sprites/all_sprites.asm"

  %log_section("Masks", !LOG_MASKS)
  incsrc "Masks/all_masks.asm"

  %log_section("Items", !LOG_ITEMS)
  incsrc "Items/all_items.asm"

  %log_section("Menu", !LOG_MENU)
  incsrc "Menu/menu.asm"

  incsrc "Util/item_cheat.asm"
  incsrc "Core/patches.asm"
  ; incsrc "Core/capture.asm"

  print ""
  print "Finished applying patches"
}
namespace off
