; ==============================================================================
; Items/fire_burn_bushes.asm — Overworld Bush Burning (Lit Deku Stick & Fire Rod)
; ==============================================================================
; Reuses the vanilla Overworld bush-cut routine `HandleItemTileAction_Overworld`
; ($1BBD7A -> `OverworldTileAction_Bush` $1BBE8D) so burning a bush Tile16
; ($0036 green bush or $072A dark bush) produces the exact same result as
; cutting it with the sword:
;   - Tile16 replacement ($0DC7/$0DC8 or revealed under-bush secret/stairs/hole)
;   - Overworld_MemorizeMap16Change + Overworld_DrawMap16 + Lyra/Sky hooks
;   - 4 flying leaf-debris garnish tiles + vanilla bush prize-pack drop roll
; plus a small flame puff (`Ancilla $2F` for Deku Stick, `FireRodShot_Halted`
; for Fire Rod) and flame SFX ($2A).
;
; Non-bush tiles (tall grass $037E, signs, rocks, pegs $021B, trees) are
; rejected before touching $0301 or $1BBD7A, leaving their behavior unchanged.
;
; Relocated off full Bank $2B into Bank $36 ($36F800-$36FAFF, 768 bytes)
; immediately following Sprites/Objects/dungeon_web.asm ($36F200-$36F7FF).
; ==============================================================================

HandleItemTileAction_Overworld = $1BBD7A
Ancilla_Class1_OffsetY         = $088953
Ancilla_Class1_OffsetX         = $088967

pushpc
org $36F800
FireBurnBushes_CodeStart:

; ==============================================================================
; DekuStick_CheckHeldBush / DekuStick_CheckSwipeBush: Overworld bush burning
; ==============================================================================
; Probe offsets indexed by DIR ($2F: 0=Up, 2=Down, 4=Left, 6=Right).
; Held X reuses Deku_TorchProbeX (+8, +8, -4, +20); Held Y aligns Left/Right
; with Link's 16x16 lower-body collision box (+12) while keeping Up/Down (-4/+24).
Deku_HeldBushOffY:
  dw -4, 24, 12, 12
Deku_SwipeBushOffX:
  dw 8, 8, -10, 24
Deku_SwipeBushOffY:
  dw -10, 26, 12, 12

DekuStick_CheckHeldBush:
{
  LDA.b $1B : BNE .exit
  LDA.l DekuStick_State : CMP.b #$02 : BNE .exit

  LDX.b $2F
  REP #$20
  LDA.l Deku_TorchProbeX, X : CLC : ADC.b $22 : STA.b $02
  LDA.l Deku_HeldBushOffY, X : CLC : ADC.b $20 : STA.b $00
  SEP #$20

  JSL Fire_TryBurnOverworldBush : BCC .exit
  JSL Fire_ConvertBushPoofToFlame
.exit
  RTL
}

DekuStick_CheckSwipeBush:
{
  LDA.b $1B : BNE .miss
  LDA.l DekuStick_SwipeTimer : BPL .miss ; Unlit swipe never burns bushes

  ; Probe 1: Close held-flame point
  LDX.b $2F
  REP #$20
  LDA.l Deku_TorchProbeX, X : CLC : ADC.b $22 : STA.b $02
  LDA.l Deku_HeldBushOffY, X : CLC : ADC.b $20 : STA.b $00
  SEP #$20
  JSL Fire_TryBurnOverworldBush : BCS .burned

  ; Probe 2: Extended swipe-thrust flame point
  LDX.b $2F
  REP #$20
  LDA.l Deku_SwipeBushOffX, X : CLC : ADC.b $22 : STA.b $02
  LDA.l Deku_SwipeBushOffY, X : CLC : ADC.b $20 : STA.b $00
  SEP #$20
  JSL Fire_TryBurnOverworldBush : BCC .miss

.burned
  JSL Fire_ConvertBushPoofToFlame
  LDA.l DekuStick_SwipeTimer : ORA.b #$40 : STA.l DekuStick_SwipeTimer
  SEC
  RTL

.miss
  CLC
  RTL
}

; ------------------------------------------------------------------------------
; Fire_TryBurnOverworldBush
; ------------------------------------------------------------------------------
; Entry:
;   M=8, X=8 (any DBR in $00-$3F/$80-$BF)
;   $00..$01 = 16-bit target pixel Y
;   $02..$03 = 16-bit target pixel X
; Exit:
;   M=8, X=8; preserves DBR
;   SEC if an Overworld bush ($0036 / $072A) was burned ($72/$74 = bush pixel X/Y)
;   CLC if not on Overworld, off-screen, or target tile is not a bush
; ------------------------------------------------------------------------------
Fire_TryBurnOverworldBush:
{
  LDA.b $1B : BNE .miss_8

  REP #$30
  ; Viewport bounds check (matches Ancilla_CheckTileCollision_targeted $088A26)
  LDA.b $00 : SEC : SBC.b $E8 : CMP.w #$00E0 : BCS .miss_16
  LDA.b $02 : SEC : SBC.b $E2 : CMP.w #$0100 : BCS .miss_16

  ; Scale $02 = pixel_X >> 3 as required by HandleItemTileAction_Overworld ($1BBD7A)
  LSR.b $02 : LSR.b $02 : LSR.b $02

  ; O(1) pre-check in $7E2000: accept ONLY green bush ($0036) and dark bush ($072A)
  LDA.b $00 : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $06
  LDA.b $02 : SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06 : TAX
  LDA.l $7E2000, X
  CMP.w #$0036 : BEQ .is_bush
  CMP.w #$072A : BNE .miss_16

.is_bush
  ; Invoke vanilla HandleItemTileAction_Overworld (.powder -> OverworldTileAction_Bush)
  ; while preserving Link's live item/shovel flags ($0301 and $037A).
  PHB
  LDA.w $0301 : PHA
  LDA.w $037A : PHA
  LDA.w #$0040 : STA.w $0301
  STZ.w $037A
  SEP #$30

  JSL HandleItemTileAction_Overworld ; Exits M=8, X=8; sets $76 != 0, $72/$74 = bush X/Y

  REP #$20
  PLA : STA.w $037A
  PLA : STA.w $0301
  SEP #$30
  PLB

  LDA.b $76 : BEQ .miss_8
  SEC
  RTL

.miss_16
  SEP #$30
.miss_8
  CLC
  RTL
}

; ------------------------------------------------------------------------------
; Fire_ConvertBushPoofToFlame
; ------------------------------------------------------------------------------
; Converts the temporary Ancilla $3F (Magic Powder bush poof) just spawned by
; AncillaAdd_BushPoof into a stationary Ancilla $2F (Lamp small flame puff)
; at the burned bush coordinates and plays vanilla flame SFX ($2A).
; Entry/Exit: M=8, X=8; preserves X.
; ------------------------------------------------------------------------------
Fire_ConvertBushPoofToFlame:
{
  LDY.b #$04
.find_poof
  LDA.w $0C4A, Y : CMP.b #$3F : BEQ .found
  DEY : BPL .find_poof
  BRA .play_sfx

.found
  LDA.b #$2F : STA.w $0C4A, Y ; Ancilla 2F: Lamp small flame puff
  LDA.b #$17 : STA.w $0C68, Y ; 23-frame 3-stage flame puff countdown
  LDA.b #$10 : STA.w $0C90, Y ; AncillaObjectAllocation[$2F] (4 OAM slots)
  LDA.b #$00
  STA.w $0C54, Y
  STA.w $0C5E, Y
  STA.w $03B1, Y
  STA.w $0C72, Y
  STA.w $0280, Y
  STA.w $0C7C, Y

.play_sfx
  LDA.b #$2A : STA.w $012E ; Vanilla Lamp / Fire Rod flame SFX
  RTL
}

; ------------------------------------------------------------------------------
; FireRod_CheckOverworldBush — Hooked at $08872C in FireRodShot_Moving
; ------------------------------------------------------------------------------
; Entry: M=8, X=8, DBR=$08, X = ancilla slot (0..4)
; Exit:  M=8, X=8, DBR=$08, X = ancilla slot (0..4) preserved
; Replays displaced `$08872C-$088736` (`INC $0C5E,X : LDA $0C72,X : AND #$F3 : STA $0C72,X`).
; On Overworld ($1B == 0) while moving ($0C54,X == 0) and at ground priority ($0280,X == 0),
; tests Probe 1 ($08+dir) and Probe 2 ($0C+dir) directly via Fire_TryBurnOverworldBush
; (which checks viewport bounds and $7E2000 against $0036 green bush / $072A dark bush
; without filtering on OverworldTileTypes, since $0036=$50 and $072A=$00 differ from $40)
; and halts the Fire Rod shot on the burned bush.
; ------------------------------------------------------------------------------
FireRod_CheckOverworldBush:
{
  ; Replay displaced instructions ($08872C-$088736)
  INC.w $0C5E, X
  LDA.w $0C72, X : AND.b #$F3 : STA.w $0C72, X

  ; Fast O(1) exits: Underworld, already collided, or elevated priority
  LDA.b $1B : BNE .exit
  LDA.w $0C54, X : BNE .exit
  LDA.w $0280, X : BNE .exit

.probe_1
  LDA.w $0C72, X : AND.b #$03 : ORA.b #$08 : TAY
  JSR .test_probe : BCS .burned

.probe_2
  LDA.w $0C72, X : AND.b #$03 : ORA.b #$0C : TAY
  JSR .test_probe : BCC .exit

.burned
  ; Remove Ancilla $3F poof spawned by $1BBD7A (slot != X) and halt this Fire Rod
  ; shot directly on the burned bush ($72, $74) as its vanilla small flame puff.
  LDY.b #$04
.clear_poof
  STY.b $00
  CPX.b $00 : BEQ .next_slot
  LDA.w $0C4A, Y : CMP.b #$3F : BNE .next_slot
    LDA.b #$00 : STA.w $0C4A, Y
    BRA .halt_shot
.next_slot
  DEY : BPL .clear_poof

.halt_shot
  LDA.b $72 : STA.w $0C04, X
  LDA.b $73 : STA.w $0C18, X
  LDA.b $74 : STA.w $0BFA, X
  LDA.b $75 : STA.w $0C0E, X
  INC.w $0C54, X
  LDA.b #$1F : STA.w $0C68, X
  LDA.b #$08 : STA.w $0C90, X
  LDA.b #$2A : STA.w $012E

.exit
  RTL

; Helper: Y = Class1 offset index ($08+dir or $0C+dir), X = ancilla slot.
; Preserves X and DBR; returns Carry from Fire_TryBurnOverworldBush.
.test_probe
  PHX
  TYX
  LDA.l Ancilla_Class1_OffsetY, X : STA.b $04
  LDA.l Ancilla_Class1_OffsetX, X : STA.b $05
  PLX
  LDA.w $0BFA, X : CLC : ADC.b $04 : STA.b $00
  LDA.w $0C0E, X : ADC.b #$00 : STA.b $01
  LDA.w $0C04, X : CLC : ADC.b $05 : STA.b $02
  LDA.w $0C18, X : ADC.b #$00 : STA.b $03
  PHX
  JSL Fire_TryBurnOverworldBush
  PLX
  RTS
}

FireBurnBushes_CodeEnd:
print "End of Items/fire_burn_bushes.asm     ", pc
assert pc() <= $36FB00, "FireBurnBushes overflowed $36F800-$36FAFF slot"

; FireRodShot_Moving ($08872C-$088736, 11 bytes):
; Replaces `INC.w $0C5E,X : LDA.w $0C72,X : AND.b #$F3 : STA.w $0C72,X`
org $08872C ; @hook module=Items name=FireRod_OverworldBushHook kind=jsl target=FireRod_CheckOverworldBush expected_m=8 expected_x=8
  JSL FireRod_CheckOverworldBush
  NOP #7
assert pc() == $088737
pullpc
