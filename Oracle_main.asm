; =========================================================
;           The Legend of Zelda: Oracle of Secrets
;                   Composed by: Scawful
;
; Custom Code and Data Memory Map:
;
;   Bank $20 ($208000): Expanded Music (Music/all_music.asm)
;   Bank $21-$27: Editor reserved; bank $23 split in Core/ZS ROM MAP.txt
;   Bank $28 ($288000): ZSCustomOverworld (Overworld/ZSCustomOverworld.asm)
;   Bank $29-$2A: Editor reserved; selected D3 streams remain Yaze-owned
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

incsrc    "Util/macros.asm"
incsrc    "Config/module_flags.asm"
incsrc    "Config/feature_flags.asm"
; Resource bodies remain opt-in until the saved-ROM compiler binds them.
if not(defined("SPECIAL_OVERWORLD_RESOURCES_ENABLED"))
  !SPECIAL_OVERWORLD_RESOURCES_ENABLED = 0
endif
; Palette lifecycle remains opt-in until the resident palette compiler binds it.
if not(defined("SPECIAL_OVERWORLD_PALETTE_ENABLED"))
  !SPECIAL_OVERWORLD_PALETTE_ENABLED = 0
endif
assert !SPECIAL_OVERWORLD_PALETTE_ENABLED == 0 || !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
; The input descriptor selects native readers; stale cache files cannot
; activate them for a direct legacy assembly. Build regenerates this include.
if read4($28F000) == $4F534F4F && read4($28F004) == $32393157
if read2($28F008) == $0003 || read2($28F008) == $0004 || read2($28F008) == $0005
  assert canreadfile1(".cache/special_overworld_reader_constants.asm", 0), "Run build_rom.sh to generate native reader constants"
  incsrc ".cache/special_overworld_reader_constants.asm"
  assert !SPECIAL_OVERWORLD_NATIVE == 1, "Native reader constants do not match the selected ROM"
  assert read4($28F01C) == !SPECIAL_OVERWORLD_DIRECTORY_CRC, "Native reader constants are stale; run build_rom.sh"
  if read2($28F008) == $0005
    assert !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1, "Revision5 requires explicit semantic Build admission"
    assert defined("SPECIAL_OVERWORLD_SEMANTIC_REVISION"), "Revision5 semantic bindings are missing"
    assert !SPECIAL_OVERWORLD_SEMANTIC_REVISION == 5, "Revision5 semantic bindings have the wrong format"
  endif
endif
endif
if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
  assert !SPECIAL_OVERWORLD_NATIVE == 1, "Native palette lifecycle requires native readers"
  assert !DISABLE_OVERWORLD == 0, "Native palette lifecycle requires the overworld module"
endif
assert !ENABLE_ONE_RING == 1, "Page 3 Layout A requires !ENABLE_ONE_RING == 1"
assert !ENABLE_GOLDSTAR_CELL == 1, "Goldstar cell is permanently active"
incsrc    "Core/structs.asm"

; Vanilla WRAM and SRAM
incsrc    "Core/ram.asm"

namespace Oracle
{
  ; Core always included — symbols, RAM, SRAM, message system
  incsrc "Core/link.asm"
  incsrc "Core/sram.asm"
  incsrc "Core/symbols.asm"
  if !ENABLE_KALYXO_BOAT == 1
    assert !DISABLE_OVERWORLD == 0
  endif
  incsrc "Core/message.asm"
  incsrc "Core/progression.asm"

  ; --- Conditionally included modules ---
  ; Toggle !DISABLE_* flags in Util/macros.asm for bug isolation.
  ; Dependencies:
  ;   Music     — standalone, no cross-module deps
  ;   Overworld — uses Core symbols; ZSCustomOverworld also loaded separately
  ;   Dungeon   — uses Core symbols, some Sprite symbols
  ;   Sprites   — uses Core symbols, Items symbols (ForcePrizeDrop, etc.)
  ;   Masks     — uses Core + Sprites symbols
  ;   Items     — uses Core symbols, some Sprite symbols
  ;   Menu      — uses Core symbols, some Items symbols
  ;   Patches   — uses Core symbols, modifies vanilla ROM addresses

  if !DISABLE_MUSIC == 0
    %log_section("Music", !LOG_MUSIC)
    incsrc "Music/all_music.asm"
  else
    print "*** MUSIC DISABLED ***"
  endif

  if !DISABLE_OVERWORLD == 0
    %log_section("Overworld", !LOG_OVERWORLD)
    incsrc "Overworld/overworld.asm"
    incsrc "Core/credits_text.asm" ; staff-roll names (generate_credits_text.py)
  else
    print "*** OVERWORLD DISABLED ***"
  endif

  if !DISABLE_DUNGEON == 0
    %log_section("Dungeon", !LOG_DUNGEON)
    incsrc "Dungeons/dungeons.asm"
  else
    print "*** DUNGEON DISABLED ***"
  endif

  if !DISABLE_SPRITES == 0
    %log_section("Sprites", !LOG_SPRITES)
    incsrc "Sprites/all_sprites.asm"
  else
    print "*** SPRITES DISABLED ***"
  endif

  if !DISABLE_MASKS == 0
    %log_section("Masks", !LOG_MASKS)
    incsrc "Masks/all_masks.asm"
  else
    print "*** MASKS DISABLED ***"
  endif

  if !DISABLE_ITEMS == 0
    %log_section("Items", !LOG_ITEMS)
    incsrc "Items/all_items.asm"
  else
    print "*** ITEMS DISABLED ***"
  endif

  if !DISABLE_MENU == 0
    %log_section("Menu", !LOG_MENU)
    incsrc "Menu/menu.asm"
  else
    print "*** MENU DISABLED ***"
  endif

  ; RC opening sequence
    incsrc "Core/Cutscene/opening.asm"

  ; Intro Scene 0 storybook art engine
    incsrc "Core/Cutscene/attract_storybook.asm"

  ; Oracle title screen BG2 (default on; see Util/macros.asm).
    incsrc "Core/title/title_screen.asm"

  ; Oracle file select restyle, option E (default on; see Util/macros.asm).
    incsrc "Core/title/file_select.asm"

  ; Native 2-player feature
    incsrc "Sprites/Players/player2.asm"

  ; Part00 villager lines and checkpoint (default on; see Util/macros.asm).
  ; The Wisdom dream scene shares its room-sprites hook ($09C2C3), and so does
  ; the dream return (shows Link after Link_WarpToRoom hides him).
  incsrc "Core/part00.asm"

  ; Dream entry effect in Maple's hut (default on; see Util/macros.asm).
  ; Own region $2BF000; Part00_RoomSprites restores its colour math.
  if !DISABLE_SPRITES == 0
    incsrc "Sprites/NPCs/dream_entry_fx.asm"
  endif

  if !ENABLE_DEBUG_TOOLS == 1
    incsrc "Util/item_cheat.asm"
  endif

  if !DISABLE_PATCHES == 0
    incsrc "Core/patches.asm"
  else
    print "*** PATCHES DISABLED ***"
  endif

  ; incsrc "Core/capture.asm"

  print ""
  print "Finished applying patches"
}
namespace off

; ZSCustomOverworld operates outside Oracle namespace (global scope)
if !DISABLE_OVERWORLD == 0
  incsrc    "Overworld/ZSCustomOverworld.asm"
  %log_end("ZSCustomOverworld.asm", !LOG_OVERWORLD)
  ; QUEUE152: Ranch exit $2E landing beside DefaultNpc (vG XY).
  incsrc "Overworld/ranch_exit_2e_landing.asm"
else
  print "*** ZSCustomOverworld DISABLED ***"
endif

; Relocated graphics sheet pointer table (copies the base ROM rows).
incsrc "Core/gfx_sheet_table.asm"

; Source-owned compressed sheets patch their streams and rows of the table above.
if !ENABLE_SOURCE_SPRITE_SHEETS == 1
  if !ENABLE_D4_ZORA_REDESIGN == 1
    incsrc "Core/Generated/d4_zora_sprite_sheets/sheet_overrides.asm"
  else
    incsrc "Core/Generated/source_sprite_sheets/sheet_overrides.asm"
  endif
endif
if !DISABLE_MENU == 0
  incsrc "Core/Generated/menu_icons/menu_icon_overrides.asm"
endif
if !DISABLE_DUNGEON == 0
  incsrc "Core/Generated/dungeon_bg_sheets/bg_sheet_overrides.asm"
endif
  if !WALLSEL_GFX == 1
    incsrc "Dungeons/wall_profile_gfx.asm"
  endif

; Readers are emitted after the current source callers and graphics overrides.
if !SPECIAL_OVERWORLD_NATIVE == 1
  assert !DISABLE_OVERWORLD == 0, "Native special overworld requires the overworld module"
  incsrc "Overworld/lyra_native_loaders.asm"
  incsrc "Overworld/special_overworld_resident.asm"
  incsrc "Overworld/special_overworld_graphics.asm"
  incsrc "Overworld/special_overworld_palette.asm"
  if read2($28F008) == $0004 || read2($28F008) == $0005
    assert defined("SPECIAL_OVERWORLD_NATIVE_COMPILED"), "Run build_rom.sh to compile saved native resources"
    assert !SPECIAL_OVERWORLD_NATIVE_COMPILED == 1
  endif
  if !SPECIAL_OVERWORLD_NATIVE_COMPILED == 1
    incsrc ".cache/special_overworld_native_data.asm"
  endif
endif
