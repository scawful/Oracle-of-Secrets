; Inherits Free Space from Bank07
org $07FA80
!RAM_MAGIC = $7EF36E

; Variant reads of the selected item: shared action routines (bombs, rod,
; hookshot chain) pick Bombchu/Portal/Byrna/Goldstar/Switch Hook by the
; item ID. Under 2-item binding an X action must see the X item, so these
; sites call ItemBindings_EffectiveItem (Items/item_bindings.asm).
; M8; A and N/Z out, X/Y kept.
macro SelectedItem()
  JSL ItemBindings_EffectiveItem
endmacro
incsrc "Items/bottle_net.asm"

; Starts Expanded Bank 0x2B
incsrc "Items/ocarina.asm"
incsrc "Items/jump_feather.asm"
incsrc "Items/book_of_secrets.asm"
incsrc "Items/sword_collect.asm"
incsrc "Items/goldstar.asm"
incsrc "Items/switch_hook.asm"
incsrc "Items/portal_rod.asm"
incsrc "Items/fishing_rod.asm"
incsrc "Items/magic_rings.asm"
incsrc "Items/fist_damage.asm"
incsrc "Items/bombchu.asm"
incsrc "Items/bombchu_pickup.asm"
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
incsrc "Items/fire_burn_bushes.asm"

; Dedicated receipt $4C; all existing receipt IDs retain their native rows.
incsrc "Items/bombchu_receipt.asm"

; Optional Bombchu room gate uses this existing stream: bank $2C has only
; dispatcher space before Somaria. No existing item or fixed owner is moved.
if !ENABLE_D6_CHU_GATE_97 == 1
incsrc "Dungeons/d6_chu_gate_97.asm"
endif

; Soaring visited bits + bird picker. Bank $34 is full; every access in
; the file is long (.l / JML / JSL), so it runs from this bank unchanged.
if !ENABLE_MENU_MAP_TRAVEL == 1
incsrc "Overworld/travel_destinations.asm"
%log_end("Overworld/travel_destinations.asm", !LOG_ITEMS)
endif

; Abyss load spawn menu: bank $34 is full. Entered only by JML, exits by
; JML/RTL, absolute operands are low WRAM (mirrored), so it runs from here.
incsrc "Overworld/abyss_spawn_menu.asm"

; Lyra overlay fix: bank $34 is full. JSL entries only, exits by RTL/JML,
; operands are direct page, long or immediate, so it runs from here.
if !ENABLE_LYRA_OVERLAY_FIX == 1
incsrc "Overworld/lyra_overlay_fix.asm"
endif

; Ranch milk sale: bank $30 is full. Entered by JSL, exits by RTL, operands
; are long, immediate or low WRAM ($1CE8, mirrored), so it runs from here.
if !ENABLE_RANCH_MILK == 1
incsrc "Sprites/NPCs/ranch_milk.asm"
endif

; Lyra talkers: banks $30/$32 are full. Entered by JML (prep hook) and JSL
; (Oracle $BB dispatch); table reads run under PHK : PLB and other absolute
; operands are low WRAM (mirrored), so the file runs from here.
if !ENABLE_LYRA_TALKERS == 1
  %log_start("lyra_talker", !LOG_SPRITES)
  incsrc "Sprites/NPCs/lyra_talker.asm"
  %log_end("lyra_talker", !LOG_SPRITES)
endif

; Piratian moved back to Bank $32 (Sprites/all_sprites.asm) once boss raw
; graphics extraction reopened >24 KB in Bank $32.

; Goron88 shared-stop occupancy: bank $31 is full. Entered by JSL from
; MinecartLong; reads only low-WRAM sprite tables (mirrored), so it runs from here.
%Goron88_EmitSharedStopOccupancy()

; Overworld/richard_quest.asm returned to Bank $34 (Overworld/overworld.asm).

; Room $78 Lanmola surface/stagger states (Hammer opening). Sprite banks
; $30/$31 are full with D8 Farore follow on; every entry is long and every
; absolute operand is mirrored WRAM, so the file runs from this bank.
incsrc "Sprites/Bosses/lanmola_hammer78.asm"

; Dual-item binding + 2-item HUD routines: bank $2B is full before the D8 boss
; tile slot ($2BE000) and menu banks $2D/$2E are full; all entries are JSL/RTL
; with long/mirrored reads, placed after room_state_code ($548000-$5487FF).
pushpc
org $548800
ItemBindings_SpanStart:
incsrc "Items/item_bindings_adapter.asm"
incsrc "Items/item_bindings_dispatch.asm"
assert pc()-ItemBindings_SpanStart <= $600, "Dual-item binding exceeded its $600 span"

HudCodex_SpanStart:
incsrc "Menu/menu_hud_codex.asm"
assert pc()-HudCodex_SpanStart <= $200, "2-item HUD routines exceeded their $200 span"

incsrc "Menu/menu_item_bindings.asm"
print "End of dual-item/2-item HUD       ", pc
assert pc() <= $54A000, "Dual-item/2-item HUD exceeded $54A000"
pullpc

; Two-slot sword helpers for the Equipment menu (Menu banks $2D/$2E are full).
incsrc "Menu/menu_sword_slots.asm"
incsrc "Menu/menu_tunic.asm"
incsrc "Items/heavy_sword.asm"

; Menu cursor memory, page-edge crossing, map return, tunic popup (bank $2D full).
if !ENABLE_MENU_MAP_TRAVEL == 1
incsrc "Menu/menu_cursor_flow.asm"
endif

; Cached HUD update (Menu bank $2E has <64 bytes before D8 boss slot $2EB800).
if !DISABLE_MENU == 0
incsrc "Menu/menu_hud_cache.asm"
endif

if !DISABLE_SPRITES == 0
incsrc "Sprites/NPCs/village_animals.asm"
endif

incsrc "Items/mirror_shield_palette.asm"

; Sprites/NPCs/dream_entry_fx.asm owns $2BF000-$2BFFFF.
print "Bank2B Free Space: ", dec($2BE000-pc()), " bytes"
assert pc() <= $2BF000, "Items bank $2B reached the dream entry FX region ($2BF000)"
; Sprites/Bosses/d8_boss.asm owns $2BE000-$2BEFFF (stage 1 + beam tiles).
assert pc() <= $2BE000, "Items bank $2B reached the D8 boss tile slot ($2BE000)"

pushpc
; League of its own
incsrc "Items/ice_rod.asm"
%log_end("Items/ice_rod.asm", !LOG_ITEMS)
pullpc
