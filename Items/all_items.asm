; Inherits Free Space from Bank07
incsrc "Items/bottle_net.asm"

; Starts Expanded Bank 0x2B
incsrc "Items/ocarina.asm"
incsrc "Items/jump_feather.asm"
incsrc "Items/book_of_secrets.asm"
incsrc "Items/sword_collect.asm"
incsrc "Items/goldstar.asm"
incsrc "Items/portal_rod.asm"
incsrc "Items/fishing_rod.asm"
incsrc "Items/magic_rings.asm"
incsrc "Items/fist_damage.asm"
print  "End of Items/fist_damage.asm      ", pc

MagicBeanGfx:
  incbin "gfx/magic_bean.bin"

MagicBeanSwapDynamicGfx:
{
  PHX
  PHP

  REP #$30

  LDX #$01BE
  --
  LDA.l MagicBeanGfx, X : STA.l $7EA480, X
  DEX : DEX
  BPL --

  PLP
  PLX
  RTL
}

pushpc
; League of its own
incsrc "Items/ice_rod.asm"
print  "End of Items/ice_rod.asm          ", pc
pullpc
