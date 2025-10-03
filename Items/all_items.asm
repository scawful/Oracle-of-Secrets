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
%log_end("Items/fist_damage.asm", !LOG_ITEMS)

MagicBeanGfx:
  incbin "gfx/magic_bean.bin"

MagicBeanSwapDynamicGfx:
{
  PHX : PHP
  REP #$30
  LDX #$01BE
  --
  LDA.l MagicBeanGfx, X : STA.l $7EA480, X
  DEX : DEX : BPL --
  PLP : PLX
  RTL
}

Link_ConsumeMagicBagItem:
{
  LDA.w $020B
  JSL JumpTableLocal

  dw Link_Banana
  dw Link_Pineapple
  dw Link_RockMeat
  dw Link_Seashells
  dw Link_Honeycombs
  dw Link_DekuSticks

  Link_Banana:
  {
    LDA.l CURHP : CMP.w MAXHP : BCS +
      LDA.l CURHP : CLC : ADC.b #$10 : STA.l CURHP
      LDA.b #$0D : STA.w $012F ; HUD Heart SFX
    +
    RTS
  }

  Link_Pineapple:
  {
    RTS
  }

  Link_RockMeat:
  {
    RTS
  }

  Link_Seashells:
  {
    RTS
  }

  Link_Honeycombs:
  {
    RTS
  }

  Link_DekuSticks:
  {
    RTS
  }

}


pushpc
; League of its own
incsrc "Items/ice_rod.asm"
%log_end("Items/ice_rod.asm", !LOG_ITEMS)
pullpc
