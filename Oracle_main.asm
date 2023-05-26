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
;   27 - Mask Routines(?)
;   28 - None
;   29 - Custom Sprite Jump Table
;   2A - Jump Feather
;   2B - Book of Secrets
;   2C - Bottle Net
;   2D - Menu
;   2E - HUD
;   2F - House Tag
;   30 - Custom Sprite Functions
;   31 - Deku Link Code
;   32 - Farore Sprite Code
;   33 - None
;   34 - Zora Link Code
;   35 - Deku Link GFX
;   36 - Zora Link GFX
;   37 - Bunny Link GFX
;   38 - Wolf Link GFX
;   39 - Palette_ArmorAndGloves  
;   3A - None
;   3B - None
;   3C - None
;   3D - None
;   3F - Boat GFX
;
; Used Free RAM:
;   $B6   - Cutscene State
;   $02B2 - Mask Form 
;   (0 = Human, 1 = Deku, 2 = Zora, 3 = Wolf, 4 = Bunny, 5 = Minish)
;   $0AAB - Diving Flag
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
  ; Music 

  ; incsrc "Music/stone_tower_temple.asm"
  ; print  "End of stone_tower_temple.asm     ", pc

  ; incsrc "Music/frozen_hyrule.asm"
  ; print  "End of Music/frozen_hyrule.asm    ", pc

  incsrc "Music/lost_woods.asm"
  print  "End of Music/lost_woods.asm       ", pc

  incsrc "Music/dungeon_theme.asm"
  print  "End of Music/dungeon_theme.asm    ", pc


  ; ---------------------------------------------------------
  ; Sprites

  ; org $02ECF8
  ;   dw $0029

  incsrc "Sprites/farore.asm"
  print  "End of farore.asm        ", pc

  incsrc "Sprites/Kydrog/kydrog.asm"
  print  "End of kydrog.asm                 ", pc

  incsrc "Sprites/Kydrog/kydrog_boss.asm"
  print  "End of kydrog_boss.asm            ", pc

  incsrc "Sprites/maku_tree.asm"
  print  "End of maku_tree.asm              ", pc

  incsrc "Sprites/mask_salesman.asm"
  print  "End of mask_salesman.asm          ", pc

  print ""

  ; ---------------------------------------------------------
  ; Transformation Masks

  print  "  -- Masks --  "
  print  ""

  incsrc "Masks/mask_routines.asm"

  incsrc "Masks/bunny_hood.asm"
  print  "End of Masks/bunny_hood.asm       ", pc
  
  incsrc "Masks/minish_form.asm"
  print  "End of Masks/minish_form.asm      ", pc

  incsrc "Masks/deku_mask.asm"
  print  "End of Masks/deku_mask.asm        ", pc

  incsrc "Masks/zora_mask.asm"
  print  "End of Masks/zora_mask.asm        ", pc

  incsrc "Masks/wolf_mask.asm"
  print  "End of Masks/wolf_mask.asm        ", pc

  print ""

  ; ---------------------------------------------------------
  ; Items

  print  "  -- Items --  "
  print  ""

  incsrc "Items/bottle_net.asm"
  print  "End of Items/bottle_net.asm       ", pc

  incsrc "Items/jump_feather.asm"
  print  "End of Items/jump_feather.asm     ", pc

  incsrc "Items/ice_rod.asm"
  print  "End of Items/ice_rod.asm          ", pc

  incsrc "Items/book_of_secrets.asm"
  print  "End of Items/book_of_secrets.asm  ", pc

  incsrc "Items/ocarina.asm"
  print  "End of Items/ocarina.asm          ", pc

  print ""

  ; ---------------------------------------------------------
  ; Events

  incsrc "Events/house_tag.asm"
  print  "End of Events/house_tag.asm       ", pc

  incsrc "Events/lost_sea.asm"
  print  "End of Events/lost_sea.asm        ", pc

  incsrc "Events/snow_overlay.asm"
  print  "End of Events/snow_overlay.asm    ", pc


  ; ---------------------------------------------------------
  ; Graphics

  incsrc "Graphics/boat_gfx.asm"
  print  "End of Graphics/boat_gfx.asm      ", pc

  incsrc "Events/maku_tree.asm"
  print  "End of Events/maku_tree.asm       ", pc


  ; ---------------------------------------------------------
  ; Dungeon

  incsrc "Dungeons/keyblock.asm"
  print  "End of Dungeons/keyblock.asm      ", pc

  incsrc "Dungeons/entrances.asm"
  print  "End of Dungeons/entrances.asm     ", pc


  ; ---------------------------------------------------------
  ; Custom Menu and HUD

  incsrc "Menu/menu.asm"
  print  "End of Menu/menu.asm              ", pc


  ; ---------------------------------------------------------
  incsrc "Debug/debug.asm"
  print  "End of Debug/debug.asm            ", pc

  ; Overworld area which has holes that hurt
  ; You can change the area to which holes will hurt the player! 
  ; currently it only allows you to choose one area
  ; 396DB, should be a 05 - Change to another area hex number

  print ""
  print "Finished applying patches"
}
namespace off
