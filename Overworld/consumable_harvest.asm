; =========================================================
; Overworld In-Place Consumable Harvesting (Q-OOS-06, Option A)
;
; Allows Link to harvest the 12 approved non-sprite overworld supply pins from
; Scripts/Proposals/plan_consumable_islands.py without consuming sprite slots
; or Bank $2B bytes:
;   - Bananas ($7EF38B, offset +$00): Tiny Atoll palms ($A5)
;   - Seashells ($7EF391, offset +$06): Tide-pool shallows ($A2/$9A/$92/$AB)
;   - Honeycombs ($7EF393, offset +$08): Forest Glade / Korok apiary ($80/$81)
;   - Deku Sticks ($7EF395, offset +$0A): Deku Grove ($A8/$A9) & Tail Swamp ($2E/$2F)
;
; Runtime footprint:
;   - Bank $32 (included by Sprites/all_sprites.asm), 0 bytes in Bank $2B
;   - 4 transient WRAM bytes ($7F57F8-$7F57FB inside UNUSED_7F5000)
;   - Zero DP ($00-$0F) scratch usage; stack-relative area_x / area_y only
;   - Called once per frame from LinkMain_FrameHook (Masks/mask_routines.asm)
; =========================================================

!CONSUMABLE_HARVEST_DEFINED        = 1
!ConsumableHarvest_PinCount        = 12
!ConsumableHarvest_Cap             = $0A ; matches early_game_balance Banana cap
!ConsumableHarvest_PickupCooldown  = $0C ; 12 frames (0.2 s) after harvest
!ConsumableHarvest_FullCooldown    = $18 ; 24 frames (0.4 s) after bag-full buzz

assert Bananas+$00 == Bananas,   "Bananas offset drift"
assert Bananas+$06 == Seashells, "Seashells offset drift"
assert Bananas+$08 == Honeycomb, "Honeycomb offset drift"
assert Bananas+$0A == DekuSticks,"DekuSticks offset drift"

; ---------------------------------------------------------
; ConsumableHarvest_FrameTick
; Entry: called via JSL from LinkMain_FrameHook (M=8, X=8).
; Preserves P, DB, and DP $00-$0F; LinkMain_FrameHook saves A/X/Y.
; ---------------------------------------------------------
ConsumableHarvest_FrameTick:
{
  PHP
  PHB : PHK : PLB
  SEP #$30

  ; Keep latches intact while pause menu / map / textbox ($10 == $0E) is open.
  LDA.b $10
  CMP.b #$0E : BEQ .exit
  CMP.b #$09 : BNE .reset_and_exit

  ; Overworld outdoors only ($1B == 0); entering an interior refreshes latches.
  LDA.b $1B : BNE .reset_and_exit

  ; Wait for live overworld submodule ($11 == 0) before checking area/harvest.
  LDA.b $11 : BNE .exit

  ; Reset per-visit pin latches whenever Link enters a different OW parent area
  ; or returns from an interior/reload (LastArea == $FF).
  LDA.b $8A
  CMP.l ConsumableHarvest_LastArea : BEQ .same_area
    STA.l ConsumableHarvest_LastArea
    LDA.b #$00
    STA.l ConsumableHarvest_LatchLo
    STA.l ConsumableHarvest_LatchHi
    STA.l ConsumableHarvest_Cooldown
  .same_area

  ; Skip while cutscenes/menus freeze player control.
  LDA.w $0FFC : ORA.w $02E4 : BNE .exit

  ; Tick debounce timer once per live overworld frame.
  LDA.l ConsumableHarvest_Cooldown : BEQ .cooldown_clear
    DEC A
    STA.l ConsumableHarvest_Cooldown
    BRA .exit
  .cooldown_clear

  ; Fast area filter: skip coordinate math on maps with no harvest pins.
  LDA.b $8A
  LDX.b #!ConsumableHarvest_PinCount-1
  .area_scan
    CMP.w ConsumableHarvest_PinParent, X : BEQ .area_has_pins
    DEX
    BPL .area_scan
  BRA .exit

.reset_and_exit
  LDA.b #$FF : STA.l ConsumableHarvest_LastArea
.exit
  PLB
  PLP
  RTL

.area_has_pins
  ; Compute Link's parent-area tile coordinates using the engine's exact
  ; ZSCustomOverworld / GetMap16Tile origin and wrap masks ($0708-$070E):
  ;   area_y = (((LinkY + 12) - $0708) & $070A) >> 4   (0..31 or 0..63)
  ;   area_x = ((((LinkX + 8) >> 3) - $070C) & $070E) >> 1
  ; Push onto stack so DP $00-$0F is never clobbered: 1,S = area_x, 2,S = area_y.
  REP #$20
  LDA.b $20 : CLC : ADC.w #$000C
  SEC : SBC.w $0708
  AND.w $070A
  LSR #4
  SEP #$20
  PHA                                         ; -> 2,S after area_x push

  REP #$20
  LDA.b $22 : CLC : ADC.w #$0008
  LSR #3
  SEC : SBC.w $070C
  AND.w $070E
  LSR A
  SEP #$20
  PHA                                         ; -> 1,S = area_x

  LDX.b #$00
  .pin_loop
    LDA.w ConsumableHarvest_PinParent, X
    CMP.b $8A : BNE .next_pin

    ; Skip if this pin was already harvested during the current visit.
    CPX.b #$08 : BCS .check_latch_hi
      LDA.l ConsumableHarvest_LatchLo
      AND.w ConsumableHarvest_BitMask, X
      BNE .next_pin
      BRA .check_coords
    .check_latch_hi
      LDA.l ConsumableHarvest_LatchHi
      AND.w ConsumableHarvest_BitMask, X
      BNE .next_pin

    .check_coords
    ; Match within +/- 1 Tile16 in both X and Y (3x3 tile footprint around pin).
    LDA 1,S
    SEC : SBC.w ConsumableHarvest_PinX, X
    CLC : ADC.b #$01
    CMP.b #$03 : BCS .next_pin

    LDA 2,S
    SEC : SBC.w ConsumableHarvest_PinY, X
    CLC : ADC.b #$01
    CMP.b #$03 : BCS .next_pin

    ; Check gesture class for this pin:
    ;   kind 0 (palm / apiary / thicket): sword ($3C), dash/bonk ($0372 / $5D=$02,$11,$12), or fresh A ($F6&$80)
    ;   kind 1 (tide-pool seashell): shovel ($037A&$01), Gust Jar ($0273), swim ($5D=$04),
    ;                                shallow wade ($0351=$01), sword ($3C), or fresh A ($F6&$80)
    LDA.w ConsumableHarvest_PinKind, X : BNE .check_kind_seashell

    ; --- kind 0: palm / apiary / thicket ---
    LDA.b $3C : BNE .trigger
    LDA.w $0372 : BNE .trigger
    LDA.b $F6 : BIT.b #$80 : BNE .trigger
    LDA.b $5D
    CMP.b #$02 : BEQ .trigger
    CMP.b #$11 : BEQ .trigger
    CMP.b #$12 : BEQ .trigger
    BRA .next_pin

    ; --- kind 1: tide-pool seashell ---
    .check_kind_seashell
    LDA.w $037A : BIT.b #$01 : BNE .trigger
    LDA.w $0273 : BNE .trigger
    LDA.b $3C : BNE .trigger
    LDA.b $F6 : BIT.b #$80 : BNE .trigger
    LDA.b $5D : CMP.b #$04 : BEQ .trigger
    LDA.w $0351 : CMP.b #$01 : BEQ .trigger

  .next_pin
    INX
    CPX.b #!ConsumableHarvest_PinCount
    BCS .pop_and_exit
    BRL .pin_loop

.pop_and_exit
  PLA                                         ; drop area_x
  PLA                                         ; drop area_y
  PLB
  PLP
  RTL

.trigger
  ; Pin X triggered! Save pin index in Y, load SRAM offset from Bananas into X.
  TXY
  LDA.w ConsumableHarvest_PinSramOff, Y : TAX
  LDA.l Bananas, X
  CMP.b #!ConsumableHarvest_Cap : BCS .inventory_full
    INC A
    STA.l Bananas, X

    ; Latch pin Y so it yields once per area visit.
    CPY.b #$08 : BCS .set_latch_hi
      LDA.l ConsumableHarvest_LatchLo
      ORA.w ConsumableHarvest_BitMask, Y
      STA.l ConsumableHarvest_LatchLo
      BRA .pickup_sfx
    .set_latch_hi
      LDA.l ConsumableHarvest_LatchHi
      ORA.w ConsumableHarvest_BitMask, Y
      STA.l ConsumableHarvest_LatchHi
    .pickup_sfx
    LDA.b #$0B : STA.w $012F                  ; SFX3.$0B heart/item pickup chime
    LDA.b #!ConsumableHarvest_PickupCooldown
    STA.l ConsumableHarvest_Cooldown
    BRA .pop_and_exit

.inventory_full
  ; Avoid buzz spam while passively swimming/wading over a seashell pin when full.
  LDA.w ConsumableHarvest_PinKind, Y : BEQ .buzz_full
    LDA.b $F6 : AND.b #$80
    ORA.b $3C
    ORA.w $0273
    BNE .buzz_full
    LDA.w $037A : BIT.b #$01 : BEQ .pop_and_exit
  .buzz_full
  LDA.b #$3C : STA.w $012E                    ; SFX2.$3C error/full buzz
  LDA.b #!ConsumableHarvest_FullCooldown
  STA.l ConsumableHarvest_Cooldown
  BRA .pop_and_exit
}

; =========================================================
; Harvest Pin Tables (12 entries, parallel to plan_consumable_islands.py)
;   0: banana_atoll_palm  ($A5, area 16,16)  -> Bananas (+$00), kind 0
;   1: banana_atoll_west  ($A5, area  6, 8)  -> Bananas (+$00), kind 0
;   2: seashell_a2        ($A2, area 25,15)  -> Seashells (+$06), kind 1
;   3: seashell_9a        ($9A, area 25,11)  -> Seashells (+$06), kind 1
;   4: seashell_92        ($92, area 21,13)  -> Seashells (+$06), kind 1
;   5: seashell_ab        ($AB, area  9,18)  -> Seashells (+$06), kind 1
;   6: honey_glade_west   ($80, area  8,15)  -> Honeycomb (+$08), kind 0
;   7: honey_korok_lane   ($81, area  2,26)  -> Honeycomb (+$08), kind 0
;   8: stick_grove_a8     ($A8, area 23,17)  -> DekuSticks (+$0A), kind 0
;   9: stick_grove_a9     ($A8, area 46, 8)  -> DekuSticks (+$0A), kind 0 (map $A9 on wide parent $A8)
;  10: stick_swamp_2e     ($2E, area 24,24)  -> DekuSticks (+$0A), kind 0
;  11: stick_swamp_2f     ($2F, area 22,14)  -> DekuSticks (+$0A), kind 0
; =========================================================
ConsumableHarvest_PinParent:
  db $A5, $A5, $A2, $9A, $92, $AB, $80, $81, $A8, $A8, $2E, $2F

ConsumableHarvest_PinX:
  db 16, 6, 25, 25, 21, 9, 8, 2, 23, 46, 24, 22

ConsumableHarvest_PinY:
  db 16, 8, 15, 11, 13, 18, 15, 26, 17, 8, 24, 14

ConsumableHarvest_PinSramOff:
  db $00, $00, $06, $06, $06, $06, $08, $08, $0A, $0A, $0A, $0A

ConsumableHarvest_PinKind:
  db $00, $00, $01, $01, $01, $01, $00, $00, $00, $00, $00, $00

ConsumableHarvest_BitMask:
  db $01, $02, $04, $08, $10, $20, $40, $80, $01, $02, $04, $08
