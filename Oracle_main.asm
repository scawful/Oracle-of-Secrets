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
;===========================================================
namespace Oracle
{
  print ""
  print "Applying patches to Oracle of Secrets"
  print ""

  incsrc "Util/ram.asm"
  incsrc "Util/functions.asm"

  incsrc "Menu/menu.asm"
  print  "End of Menu/menu.asm              ", pc

  incsrc "Events/intro.asm"
  print  "End of Events/intro.asm           ", pc

  incsrc "Events/lostsea.asm"
  print  "End of Events/lostsea.asm         ", pc

  incsrc "Items/ice_rod.asm"
  print  "End of Items/ice_rod.asm          ", pc


  incsrc "KeyBlock/keyblock.asm"
  print  "End of KeyBlock/keyblock.asm      ", pc

  incsrc "Items/book_of_secrets.asm"
  print  "End of Items/book_of_secrets.asm  ", pc

  incsrc "Debug/debug.asm"
  print  "End of Debug/debug.asm            ", pc
  
  incsrc "Masks/mask_routines.asm"

  incsrc "Masks/deku_mask.asm"
  print  "End of Masks/deku_mask.asm        ", pc

  incsrc "Masks/zora_mask.asm"
  print  "End of Masks/zora_mask.asm        ", pc

  incsrc "Masks/wolf_mask.asm"
  print  "End of Masks/wolf_mask.asm       ", pc

  incsrc "Masks/bunny_hood.asm"
  print  "End of Masks/bunny_hood.asm       ", pc

  print ""
  print "Finished applying patches"
}
namespace off
