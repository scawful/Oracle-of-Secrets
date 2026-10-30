; Inherits Free Space from Bank07
org $07FA80
!RAM_MAGIC = $7EF36E
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
  ; Menu caller supplies M/X=8 and keeps its count pointer in $00-$03.
  ; A local JSR preserves that pointer and matches the handlers' RTS exits.
  LDA.w $020B
  ASL A : TAX
  JSR (.handlers, X)
  RTL

  .handlers
  dw Link_Banana
  dw Link_Pineapple
  dw Link_RockMeat
  dw Link_Seashells
  dw Link_Honeycombs
  dw Link_DekuSticks

  Link_Banana:
  {
    LDA.l CURHP : CMP.w MAXHP : BCS .full
      LDA.l CURHP : CLC : ADC.b #$10
      CMP.w MAXHP : BCC .store
        LDA.l MAXHP
      .store
      STA.l CURHP
      LDA.b #$00
      SEC : RTS
    .full
    CLC : RTS
  }

  Link_Pineapple:
  {
    LDA.l !RAM_MAGIC : CMP.b #$80 : BCS .full
      LDA.b #$80 : STA.l !RAM_MAGIC
      LDA.b #$00
      SEC : RTS
    .full
    CLC : RTS
  }

  Link_RockMeat:
  {
    CLC : RTS
  }

  Link_Seashells:
  {
    CLC : RTS
  }

  Link_Honeycombs:
  {
    ; Refuse if an activation is already pending
    LDA.l PendingSupplyAction : BNE .fail

    ; Refuse if an active bee already exists in the room
    ; Note: Wild bees use ID $79. Player bees use ID $B2 with $0D80 != 0.
    ; Windmill Guy uses ID $B2 with $0D80 == 0; do not treat Windmill Guy as a bee.
    LDX.b #$0F
  .check_active
    LDA.w $0E20, X : CMP.b #$79 : BEQ .bee_active
                     CMP.b #$B2 : BNE .not_bee
    LDA.w $0D80, X : BEQ .not_bee ; Windmill Guy ($0D80 == 0) is not a bee
  .bee_active
    LDA.w $0DD0, X : BNE .fail
  .not_bee
    DEX : BPL .check_active

    ; Refuse if fewer than 3 sprite slots are free (slot pressure check)
    LDX.b #$0F
    LDY.b #$00
  .count_free
    LDA.w $0DD0, X : BNE .slot_used
      INY
  .slot_used
    DEX : BPL .count_free
    CPY.b #$03 : BCC .fail

    ; Queue Honeycomb swarm for execution when menu closes
    LDA.b #!SUPPLY_ACTION_HONEYCOMB : STA.l PendingSupplyAction
    LDA.b #$01 ; A=1 indicates deferred exit activation to menu caller
    SEC
    RTS

  .fail
    CLC
    RTS
  }

  Link_DekuSticks:
  {
    ; Refuse if an activation is already pending
    LDA.l PendingSupplyAction : BNE .fail

    ; Refuse if a stick is ALREADY drawn
    LDA.l DekuStick_State : BNE .fail

    ; Refuse if Link has 0 Deku Sticks
    LDA.l DekuSticks : BEQ .fail

    ; Queue Deku Stick draw for execution when menu closes
    LDA.b #!SUPPLY_ACTION_DEKUSTICK : STA.l PendingSupplyAction
    LDA.b #$01 ; A=1 indicates deferred exit activation to menu caller
    SEC
    RTS

  .fail
    CLC
    RTS
  }

}

Supply_ProcessPendingExitAction:
{
  PHB : PHK : PLB
  LDA.l PendingSupplyAction : BNE +
    JMP .done
  +
  CMP.b #!SUPPLY_ACTION_HONEYCOMB : BEQ .action_honeycomb
  CMP.b #!SUPPLY_ACTION_DEKUSTICK : BNE +
    JMP .action_deku_stick
  +
  JMP .check_other

.action_honeycomb
  ; Clear pending request
  LDA.b #$00 : STA.l PendingSupplyAction

  ; Verify Link still owns at least 1 Honeycomb
  LDA.l Honeycomb : BNE +
    JMP .abort_error
  +

  ; Verify no active bee is in the room
  LDX.b #$0F
.exit_check_bee
  LDA.w $0E20, X : CMP.b #$79 : BEQ .exit_bee_active
                   CMP.b #$B2 : BNE .exit_not_bee
  LDA.w $0D80, X : BEQ .exit_not_bee ; Windmill Guy ($0D80 == 0) is not a bee
.exit_bee_active
  LDA.w $0DD0, X : BEQ +
    JMP .abort_error
  +
.exit_not_bee
  DEX : BPL .exit_check_bee

  ; Verify at least 3 sprite slots are available
  LDX.b #$0F
  LDY.b #$00
.exit_count_slots
  LDA.w $0DD0, X : BNE .exit_slot_used
    INY
.exit_slot_used
  DEX : BPL .exit_count_slots
  CPY.b #$03 : BCS +
    JMP .abort_error
  +

  ; Spawn 3 Good Bees using PlayerItem_ReleaseBee ($1EDCCF)
  ; Bee 1
  LDA.b $3A : AND.b #$BF : STA.b $3A
  STZ.w $0301
  JSL PlayerItem_ReleaseBee
  BPL +
    JMP .abort_error
  +
  TYX : LDA.b #$01 : STA.w $0EB0, X

  ; Bee 2
  LDA.b $3A : AND.b #$BF : STA.b $3A
  STZ.w $0301
  JSL PlayerItem_ReleaseBee
  BPL +
    JMP .abort_error
  +
  TYX : LDA.b #$01 : STA.w $0EB0, X

  ; Bee 3
  LDA.b $3A : AND.b #$BF : STA.b $3A
  STZ.w $0301
  JSL PlayerItem_ReleaseBee
  BPL +
    JMP .abort_error
  +
  TYX : LDA.b #$01 : STA.w $0EB0, X

  ; Swarm successfully deployed! Spend exactly one Honeycomb
  LDA.l Honeycomb : DEC A : STA.l Honeycomb

  ; Play bee release sound
  LDA.b #$2F : STA.w $012F
  BRA .done

.abort_error
  LDA.b #$3C : STA.w $012E
  BRA .done

.action_deku_stick
  ; Clear pending request
  LDA.b #$00 : STA.l PendingSupplyAction

  ; Re-verify guards upon returning to gameplay:
  ; 1. Must own at least 1 Deku Stick
  LDA.l DekuSticks : BEQ .abort_error_deku

  ; 2. Must not already have a stick drawn
  LDA.l DekuStick_State : BNE .abort_error_deku

  ; 3. Must be on ground in default state ($5D == 0)
  LDA.l $7E005D : BNE .abort_error_deku

  ; 4. Must not be carrying an object ($0308 == 0)
  LDA.l $7E0308 : BNE .abort_error_deku

  ; 5. Must not be transformed by a mask (0 and 6 are normal Link)
  LDA.l $7E02B2 : BEQ +
  CMP.b #$06 : BNE .abort_error_deku
+

  ; Successful draw!
  ; Check if we have a saved worn stick in DekuStickWear ($7EF39F)
  ; Valid worn budget is 1 to 74 ($01..$4A). Fresh budget is 75 ($4B).
  LDA.l DekuStickWear
  BEQ .draw_fresh
  CMP.b #$4B : BCS .draw_fresh ; 75 or out-of-range garbage -> fallback to fresh 75
    ; Valid worn budget stored:
    STA.l DekuStick_BurnTimer
    BRA .finish_draw

.draw_fresh
  LDA.b #$4B : STA.l DekuStick_BurnTimer ; 75 ticks (20s)

.finish_draw
  ; Clear stored wear now that the stick is active
  LDA.b #$00 : STA.l DekuStickWear

  ; Decrement inventory count exactly once
  LDA.l DekuSticks : DEC A : STA.l DekuSticks

  ; Set active state to 1 (held unlit)
  LDA.b #$01 : STA.l DekuStick_State
  LDA.b #$00 : STA.l DekuStick_SwipeTimer

  ; Play equip click sound
  LDA.b #$20 : STA.w $012F
  BRA .done

.abort_error_deku
  LDA.b #$3C : STA.w $012E

.check_other
.done
  PLB
  RTL
}

incsrc "Items/deku_stick.asm"


; Sprites/NPCs/dream_entry_fx.asm owns $2BF000-$2BFFFF.
assert pc() <= $2BF000, "Items bank $2B reached the dream entry FX region ($2BF000)"

pushpc
; League of its own
incsrc "Items/ice_rod.asm"
%log_end("Items/ice_rod.asm", !LOG_ITEMS)
pullpc
