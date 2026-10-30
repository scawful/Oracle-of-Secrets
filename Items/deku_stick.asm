; ==============================================================================
; Items/deku_stick.asm — Deku Stick consumable handler
; ==============================================================================
; State:
;   DekuStick_State      ($7E046D): 0 = none, 1 = held unlit, 2 = held lit, 3 = swiping
;   DekuStick_BurnTimer  ($7E046E): Active burn countdown ticks (1 tick = 16 frames; 75 = 20s)
;   DekuStick_SwipeTimer ($7E046F): Swipe animation / hit window frames (0 = idle)
;   DekuStickWear        ($7EF39F): Stored burn ticks of stowed worn stick (1-75, 0 = none)
; ==============================================================================

DekuStick_Main:
{
  LDA.l DekuStick_State : BNE +
    RTL
  +

  ; Guard 1: LinkState must be default ($5D == 0)
  LDA.l $7E005D : BNE .interrupted

  ; Guard 2: Not carrying an object ($0308 == 0)
  LDA.l $7E0308 : BNE .interrupted

  ; Guard 3: Not transformed by a mask (0 and 6 are normal Link)
  LDA.l $7E02B2 : BEQ +
  CMP.b #$06 : BNE .interrupted
+

  ; Active burn countdown (only when lit: State == 2)
  LDA.l DekuStick_State : CMP.b #$02 : BNE .done

  ; Freeze burn timer during pauses / submodules ($11 != 0)
  LDA.l $7E0011 : BNE .done

  ; Tick once every 16 frames ($1A & $0F == 0)
  LDA.l $7E001A : AND.b #$0F : BNE .done

  LDA.l DekuStick_BurnTimer : DEC A : STA.l DekuStick_BurnTimer
  BNE .done

  ; Burn timer reached 0: stick burned out!
  JSL DekuStick_Drop

  ; Extinguish sound
  LDA.b #$3C : STA.w $012E
  RTL

.interrupted
  ; Interruption: damage, fall, swim, bonk, carry, mask -> stick lost
  JSL DekuStick_Drop

.done
  RTL
}

DekuStick_Stow:
{
  ; Refund exactly one intact stick to inventory
  LDA.l DekuSticks : INC A : STA.l DekuSticks

  ; Determine retained wear:
  ; If BurnTimer == 75 ($4B), stick was unlit/fresh -> store 0 (no worn stick).
  ; If BurnTimer is between 1 and 74, stick is worn -> retain BurnTimer in SRAM.
  LDA.l DekuStick_BurnTimer
  CMP.b #$4B : BEQ .unlit
  CMP.b #$00 : BEQ .unlit
  CMP.b #$4C : BCS .unlit ; Out-of-range safety guard -> do not store invalid wear
    STA.l DekuStickWear
    BRA .clear_active

.unlit
  LDA.b #$00 : STA.l DekuStickWear

.clear_active
  LDA.b #$00
  STA.l DekuStick_State
  STA.l DekuStick_BurnTimer
  STA.l DekuStick_SwipeTimer

  ; Play equip / stow sound
  LDA.b #$20 : STA.w $012F
  RTL
}

DekuStick_Drop:
{
  ; Clear active state without refunding inventory (spent on draw)
  ; DekuStickWear was already zeroed on draw, so no wear is restored
  LDA.b #$00
  STA.l DekuStick_State
  STA.l DekuStick_BurnTimer
  STA.l DekuStick_SwipeTimer
  RTL
}

DekuStick_Ignite:
{
  ; Only an unlit stick (state 1) can ignite
  LDA.l DekuStick_State : CMP.b #$01 : BNE .exit
    LDA.b #$02 : STA.l DekuStick_State
    ; Preserves active BurnTimer! (Relighting preserves remaining wear budget)
    ; Play flame ignition sound
    LDA.b #$2D : STA.w $012F
  .exit
  RTL
}
