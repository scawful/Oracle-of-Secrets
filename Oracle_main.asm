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
  print  "End of Menu/menu.asm            ", pc

  incsrc "Book/book.asm"
  print  "End of Book/Book.asm            ", pc

  incsrc "BunnyHood/bunnyhood.asm"
  print  "End of BunnyHood/bunnyhood.asm  ", pc

  incsrc "IceRod/icerod.asm"
  print  "End of IceRod/icerod.asm        ", pc

  incsrc "Intro/intro.asm"
  print  "End of Intro/intro.asm          ", pc

  incsrc "KeyBlock/keyblock.asm"
  print  "End of KeyBlock/keyblock.asm    ", pc

  incsrc "LostSea/lostsea.asm"
  print  "End of LostSea/lostsea.asm      ", pc

  print ""
  print "Finished applying patches"
}
namespace off
