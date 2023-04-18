;===========================================================
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
;===========================================================

namespace Oracle
{
  print ""
  print "Applying patches to Oracle of Secrets"
  print ""

  incsrc "Util/ram.asm"
  incsrc "Util/functions.asm"

  ; ---------------------------------------------------------
  ; Sprites

  incsrc "Sprites/farore_and_maku.asm"
  print  "End of farore_and_maku.asm        ", pc

  incsrc "Sprites/Kydrog/kydrog.asm"
  print  "End of kydrog.asm                 ", pc

  ; ---------------------------------------------------------
  ; Transformation Masks

  incsrc "Masks/mask_routines.asm"

  incsrc "Masks/deku_mask.asm"
  print  "End of Masks/deku_mask.asm        ", pc

  incsrc "Masks/zora_mask.asm"
  print  "End of Masks/zora_mask.asm        ", pc

  incsrc "Masks/wolf_mask.asm"
  print  "End of Masks/wolf_mask.asm        ", pc

  incsrc "Masks/bunny_hood.asm"
  print  "End of Masks/bunny_hood.asm       ", pc


  ; ---------------------------------------------------------
  ; Items

  incsrc "Items/jump_feather.asm"
  print  "End of Items/jump_feather.asm     ", pc

  incsrc "Items/ice_rod.asm"
  print  "End of Items/ice_rod.asm          ", pc

  incsrc "Items/book_of_secrets.asm"
  print  "End of Items/book_of_secrets.asm  ", pc

  ; incsrc "Items/bottle_net.asm"
  ; print "End of Items/bottle_net.asm        ", pc


  ; ---------------------------------------------------------
  ; Events

  incsrc "Events/house_tag.asm"
  print  "End of Events/house_tag.asm       ", pc

  incsrc "Events/lost_sea.asm"
  print  "End of Events/lost_sea.asm         ", pc


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


  ; ---------------------------------------------------------
  ; Custom Menu and HUD

  incsrc "Menu/menu.asm"
  print  "End of Menu/menu.asm              ", pc


  ; ---------------------------------------------------------
  incsrc "Debug/debug.asm"
  print  "End of Debug/debug.asm            ", pc
  

  print ""
  print "Finished applying patches"
}
namespace off
