; =========================================================
; Ganondorf finale, last phase: "the beast" (room $00)
;
; Included by ganondorf.asm inside its bank $2A block when
; !ENABLE_GANON_BEAST == 1. The beast is a second Ganondorf ($D3) slot that
; runs actions 8-15 (beast state = SprAction - 8). It reuses Ganondorf's
; sheet and frames; only its OBJ palette differs (red/blue swapped at runtime).
;
; Hand-off: Ganondorf_Dead (timer 0) spawns the beast, sets GanondorfFight = 3,
; then frees Ganondorf. GanondorfFight = 3 keeps the Triforce door shut
; (Ganondorf_DoorGate). The beast's death scene ends with GanondorfFight = 2,
; so the existing gate opens the door.
;
; States (SprAction):
;   8  Enter       96 frames, ring R0 becomes malice (option A)
;   9  Stalk       90-150 frames, walks toward Link inside the arena clamp
;   10 Throw       32 frames wind-up, then the trident leaves (-> 11 same frame)
;   11 Trident     up to 120 frames; core open; trident flies out and back
;   12 Roar/charge 48 frames roar, then a straight charge to the clamp edge
;   13 Dazed       150 frames; core open; no contact damage
;   14 Core hit    40 frames flinch; hits 2 and 4 start malice stages 1 and 2
;   15 Dead        $C0 frames death scene; all malice is disarmed on entry
;
; Core hit: Master Sword or better ($7EF359 >= 2), no item in use ($0301 = 0),
; only in states 11 and 13 (state 10 becomes 11 the frame the trident leaves).
; Six core hits kill the beast.
;
; Sprite-local bytes (no new WRAM):
;   SprTimerA state timer         SprTimerB malice warning   SprTimerC trident out
;   SprMiscA  bits 0-1 stalk cycle (mod 3), bit 7 charge phase in state 12
;   SprMiscB  trident: 0 held, 1 out, 2 returning
;   SprMiscC/SprMiscD trident X/Y low bytes (high bytes = the beast's)
;   SprMiscE/SprMiscG trident X/Y step, signed pixels per frame
;   SprMiscF  core hits left
;   SprSubtype malice job: 0 idle, 1 R0, 2 stage 1, 3 stage 2; bit 7 = warning
;   SprCustom  malice cursor (cells written so far)
;
; Art: no new art. Real art replaces Ganondorf frame use in Beast_* poses,
; the trident OAM piece (chr/props below) and Beast_ApplyPalette.
; =========================================================

; ---- Malice floor look (BG palette row and tile16 words) ----
!Malice_PalRow     = 6
!Malice_TL         = (!Malice_PalRow<<10)|$00EC
!Malice_TR         = (!Malice_PalRow<<10)|$00ED
!Malice_BL         = (!Malice_PalRow<<10)|$00FC
!Malice_BR         = (!Malice_PalRow<<10)|$00FD
!Malice_Col10      = $280A
!Malice_Col11      = $4C14
!Malice_Col12      = $701C
!Malice_ColPulse   = $7E9F
!Malice_ColAddr    = $7EC500+(!Malice_PalRow*$20)+(10*2) ; live row, colors 10-12
!Malice_ColMirror  = $7EC300+(!Malice_PalRow*$20)+(10*2) ; fade-target row
!Malice_Attr       = $0D0D  ; tile type $0D (spike floor) on both tile8 halves

; Option A: ring R0 (the stomp pit ring) becomes malice at beast Enter.
; 0 = leave the pits as they are.
!Beast_MaliceR0    = 1

!Malice_CellsPerFrame = 4
!Malice_QueueMax      = $00E4 ; last $1000 value that still fits one 24-byte entry
!Malice_WarnTime      = 60

; ---- Beast tuning ----
!Beast_CoreHits     = 6
!Beast_EnterTime    = 96
!Beast_EnterBlink   = 48
!Beast_StalkMin     = 90
!Beast_StalkMax     = 150
!Beast_ThrowTime    = 32
!Beast_TridentTime  = 120
!Beast_TridentOut   = 40
!Beast_TridentSpeed = $40   ; 4 px per frame after >>4
!Beast_TridentBack  = 4     ; px per axis per frame on the return
!Beast_RoarTime     = 48
!Beast_ChargeTime   = 64    ; fallback if the clamp never blocks the charge
!Beast_DazedTime    = 150
!Beast_HitTime      = 40
!Beast_DeadTime     = $C0
!Beast_WalkSpeed    = $0C
!Beast_ChargeSpeed  = $20
!Beast_HandX        = 18
!Beast_HandY        = -20

; Trident placeholder: Ganondorf's energy ball tile, OBJ palette 6.
!Beast_TridentChr   = $6A
!Beast_TridentProps = $3D
!Beast_TridentSlot  = 6     ; OAM piece index; beast frames use at most 6 pieces

!Beast_ActEnter   = $08
!Beast_ActStalk   = $09
!Beast_ActThrow   = $0A
!Beast_ActTrident = $0B
!Beast_ActRoar    = $0C
!Beast_ActDazed   = $0D
!Beast_ActHit     = $0E
!Beast_ActDead    = $0F

; =========================================================
; Spawn from Ganondorf_Dead. X = Ganondorf slot.
; Carry set = beast spawned; carry clear = no free slot (retry next frame).
Beast_Spawn:
{
  LDA.b #Sprite_Ganondorf : JSL Sprite_SpawnDynamically : BPL .spawned
    CLC
    RTS
  .spawned
  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprYH, X : STA.w SprYH, Y
  LDA.w SprFloor, X : STA.w SprFloor, Y
  PHX
  TYX
  JSR Beast_Init
  PLX
  SEC
  RTS
}

; X = beast slot.
Beast_Init:
{
  LDA.b #$FF : STA.w SprHealth, X
  LDA.b #!Beast_CoreHits : STA.w SprMiscF, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; impervious
  LDA.b #!Beast_ActEnter : STA.w SprAction, X
  LDA.b #!Beast_EnterTime : STA.w SprTimerA, X
  LDA.b #$00
  STA.w SprHeight, X
  STA.w SprFrame, X
  STA.w SprMiscA, X
  STA.w SprMiscB, X
  STA.w SprMiscC, X
  STA.w SprMiscD, X
  STA.w SprMiscE, X
  STA.w SprMiscG, X
  STA.w SprCustom, X
  STA.w SprTimerB, X
  STA.w SprTimerC, X
  STA.w SprTimerD, X
  STA.w SprXSpeed, X
  STA.w SprYSpeed, X
if !Beast_MaliceR0 == 1
  LDA.b #$01
endif
  STA.w SprSubtype, X ; malice job R0 (or idle)
  JSR Beast_ClearCollapse
  JSR Beast_ApplyPalette
  LDA.b #$00 : JSR Malice_SetColors
  RTS
}

; Stop the stomp floor collapse: overlords $0C-$0F and pending falling-tile
; garnishes ($03), so no pit lands on a malice cell after R0 is written.
Beast_ClearCollapse:
{
  LDY.b #$07
  .overlord
    LDA.w OverlordId, Y : CMP.b #$0C : BCC .next_overlord
    CMP.b #$10 : BCS .next_overlord
      LDA.b #$00 : STA.w OverlordId, Y
    .next_overlord
    DEY : BPL .overlord
  PHX
  LDX.b #$1D
  .garnish
    LDA.l $7FF800, X : CMP.b #$03 : BNE .next_garnish
      LDA.b #$00 : STA.l $7FF800, X
    .next_garnish
    DEX : BPL .garnish
  PLX
  RTS
}

; Beast OBJ palette: Ganondorf's 15 colors with red and blue swapped, written to
; OBJ row 6 live and fade-target buffers. Keeps X.
Beast_ApplyPalette:
{
  PHX
  REP #$30
  LDX.w #$001C
  .color
    LDA.l GanondorfPalette+2, X : STA.b $00
    AND.w #$03E0 : STA.b $02          ; green stays
    LDA.b $00 : AND.w #$001F
    XBA : ASL A : ASL A : ORA.b $02 : STA.b $02 ; red -> blue
    LDA.b $00 : XBA : LSR A : LSR A
    AND.w #$001F : ORA.b $02          ; blue -> red
    STA.l $7EC6C2, X
    STA.l $7EC4C2, X
    DEX : DEX : BPL .color
  SEP #$30
  LDA.b #$01 : STA.b $15
  PLX
  RTS
}

; Fairy revive (BossReinject): graphics are reapplied by the caller.
Beast_Reinject:
{
  JSR Beast_ApplyPalette
  LDA.b #$00 : JSR Malice_SetColors
  RTS
}

; =========================================================
Beast_Main:
{
  JSR Malice_Run
  LDA.w SprAction, X : SEC : SBC.b #$08
  JSL JumpTableLocal
  dw Beast_Enter
  dw Beast_Stalk
  dw Beast_Throw
  dw Beast_Trident
  dw Beast_Roar
  dw Beast_Dazed
  dw Beast_Hit
  dw Beast_Dead
}

; 8: appear where Ganondorf fell.
Beast_Enter:
{
  STZ.w SprFrame, X
  LDA.w SprTimerA, X : BNE .wait
    JSR Beast_GotoStalk
  .wait
  RTS
}

; 9: walk toward Link.
Beast_Stalk:
{
  LDA.b #!Beast_WalkSpeed : JSL Sprite_ApplySpeedTowardsPlayer
  JSR Ganondorf_MoveClamped
  JSR Beast_WalkPose
  JSL Sprite_CheckDamageToPlayer
  LDA.w SprTimerA, X : BNE .wait
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.w SprMiscA, X : AND.b #$03 : INC A
    CMP.b #$03 : BCC .cycle
      LDA.b #$00
    .cycle
    STA.w SprMiscA, X
    BEQ .roar
      LDA.b #!Beast_ActThrow : STA.w SprAction, X
      LDA.b #!Beast_ThrowTime : STA.w SprTimerA, X
      LDA.b #!Ganon_FrameWindup : STA.w SprFrame, X
      RTS
    .roar
    LDA.b #!Beast_ActRoar : STA.w SprAction, X
    LDA.b #!Beast_RoarTime : STA.w SprTimerA, X
    LDA.b #!Ganon_FrameCast : STA.w SprFrame, X
    LDA.b #$35 : STA.w $012E
  .wait
  RTS
}

; 10: wind-up, then throw. The state becomes 11 in the release frame, so the
; core is open from the moment the trident leaves ("2 after release").
Beast_Throw:
{
  LDA.b #!Ganon_FrameWindup : STA.w SprFrame, X
  JSL Sprite_CheckDamageToPlayer
  LDA.w SprTimerA, X : BNE .wait
    LDA.w SprX, X : CLC : ADC.b #!Beast_HandX : STA.w SprMiscC, X
    LDA.w SprY, X : CLC : ADC.b #!Beast_HandY : STA.w SprMiscD, X
    LDA.b #!Beast_TridentSpeed : JSL Sprite_ApplySpeedTowardsPlayer
    LDA.w SprXSpeed, X : JSR Beast_Speed16 : STA.w SprMiscE, X
    LDA.w SprYSpeed, X : JSR Beast_Speed16 : STA.w SprMiscG, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.b #$01 : STA.w SprMiscB, X
    LDA.b #!Beast_TridentOut : STA.w SprTimerC, X
    LDA.b #!Beast_ActTrident : STA.w SprAction, X
    LDA.b #!Beast_TridentTime : STA.w SprTimerA, X
    LDA.b #!Ganon_FrameRelease : STA.w SprFrame, X
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
  .wait
  RTS
}

; Signed speed (1/16 px) -> signed px per frame.
Beast_Speed16:
{
  CMP.b #$80 : ROR A
  CMP.b #$80 : ROR A
  CMP.b #$80 : ROR A
  CMP.b #$80 : ROR A
  RTS
}

; 11: hands empty, trident out and back. Core open.
Beast_Trident:
{
  JSR Beast_TryCoreHit : BCC .no_hit
    RTS
  .no_hit
  JSL Sprite_CheckDamageToPlayer
  JSR Beast_TridentMove
  JSR Beast_TridentDamage
  LDA.w SprTimerA, X : CMP.b #!Beast_TridentTime-8 : BCS .release_pose
    LDA.b #!Ganon_FrameRecover : BRA .pose
  .release_pose
    LDA.b #!Ganon_FrameRelease
  .pose
  STA.w SprFrame, X
  LDA.w SprMiscB, X : BEQ .caught
  LDA.w SprTimerA, X : BNE .wait
  .caught
    STZ.w SprMiscB, X
    JSR Beast_GotoStalk
  .wait
  RTS
}

; 12: roar (quake), then charge until the clamp stops the beast.
Beast_Roar:
{
  JSL Sprite_CheckDamageToPlayer
  LDA.w SprMiscA, X : BMI .charge
    LDA.b #!Ganon_FrameCast : STA.w SprFrame, X
    JSR Ganondorf_Quake
    LDA.w SprTimerA, X : BNE .wait
      JSR Ganondorf_StopQuake
      LDA.w SprMiscA, X : ORA.b #$80 : STA.w SprMiscA, X
      LDA.b #!Beast_ChargeSpeed : JSL Sprite_ApplySpeedTowardsPlayer
      LDA.b #!Beast_ChargeTime : STA.w SprTimerA, X
      LDA.b #!Ganon_FrameReady : STA.w SprFrame, X
    .wait
    RTS
  .charge
  JSR Ganondorf_MoveClamped : BCS .dazed
  LDA.w SprTimerA, X : BNE .wait
  .dazed
  LDA.w SprMiscA, X : AND.b #$7F : STA.w SprMiscA, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #!Beast_ActDazed : STA.w SprAction, X
  LDA.b #!Beast_DazedTime : STA.w SprTimerA, X
  LDA.b #!Ganon_FrameHurt : STA.w SprFrame, X
  LDA.b #$35 : STA.w $012E
  RTS
}

; 13: slumped, core open, no contact damage.
Beast_Dazed:
{
  LDA.b #!Ganon_FrameHurt : STA.w SprFrame, X
  JSR Beast_TryCoreHit : BCS .exit
  LDA.w SprTimerA, X : BNE .exit
    JSR Beast_GotoStalk
  .exit
  RTS
}

; 14: flinch after a core hit. Invulnerable, no contact damage.
Beast_Hit:
{
  LDA.b #!Ganon_FrameHurt : STA.w SprFrame, X
  LDA.w SprTimerA, X : BNE .wait
    JSR Beast_GotoStalk
  .wait
  RTS
}

; 15: death scene, same timeline as Ganondorf_Dead.
Beast_Dead:
{
  LDA.b #!Ganon_FrameHurt : STA.w SprFrame, X
  LDA.w SprTimerA, X : BNE .run
    JSR Ganondorf_StopQuake
    LDA.b #$02 : STA.l GanondorfFight
    STZ.w SprState, X
    RTS
  .run
  CMP.b #$30 : BCC .quiet
  JSR Ganondorf_Quake
  LDA.w SprTimerA, X : CMP.b #$A9 : BCC .to_black
    LDA.b #$00 : JSR Ganondorf_DeathPal
    RTS
  .to_black
  LDA.b $1A : AND.b #$01 : BNE .exit
    LDA.b #$01 : JSR Ganondorf_DeathPal
  .exit
  RTS
  .quiet
  JSR Ganondorf_StopQuake
  RTS
}

Beast_GotoStalk:
{
  LDA.b #!Beast_ActStalk : STA.w SprAction, X
  STZ.w SprMiscB, X
  JSL GetRandomInt : AND.b #$3F : CLC : ADC.b #!Beast_StalkMin
  CMP.b #!Beast_StalkMax : BCC .store
    LDA.b #!Beast_StalkMax
  .store
  STA.w SprTimerA, X
  STZ.w SprFrame, X
  RTS
}

; Front pose when Link is below, rear walk cycle when Link is above.
Beast_WalkPose:
{
  JSR Ganondorf_CompareLinkY : BCS .front
    LDA.b $1A : LSR A : LSR A : LSR A : AND.b #$01
    CLC : ADC.b #!Ganon_FrameBackA
    STA.w SprFrame, X
    RTS
  .front
  LDA.b #!Ganon_FrameIdle : STA.w SprFrame, X
  RTS
}

; Carry set = a core hit landed (state already changed).
Beast_TryCoreHit:
{
  LDA.l $7EF359 : CMP.b #$02 : BCC .no
  LDA.w $0301 : BNE .no
  LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X
  JSL Sprite_CheckDamageFromPlayer
  PHP
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  LDA.b #$FF : STA.w SprHealth, X
  PLP
  BCC .no
  STZ.w SprMiscB, X ; trident snaps back to the hand
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  DEC.w SprMiscF, X : BEQ .kill
    LDA.b #!Beast_ActHit : STA.w SprAction, X
    LDA.b #!Beast_HitTime : STA.w SprTimerA, X
    LDA.w SprMiscF, X
    CMP.b #!Beast_CoreHits-2 : BNE .not_stage1
      LDA.b #$02 : JSR Malice_Start
      BRA .hit_done
    .not_stage1
    CMP.b #!Beast_CoreHits-4 : BNE .hit_done
      LDA.b #$03 : JSR Malice_Start
    .hit_done
    SEC
    RTS
  .kill
  ; Disarm in the frame the beast enters state 15, before the death scene.
  JSR Malice_DisarmAll
  LDA.b #!Beast_ActDead : STA.w SprAction, X
  LDA.b #!Beast_DeadTime : STA.w SprTimerA, X
  LDA.b #$35 : STA.w $012E
  SEC
  RTS
  .no
  CLC
  RTS
}

; =========================================================
; Trident (drawn by the beast as one OAM piece; damage reuses the beast slot).

Beast_TridentMove:
{
  LDA.w SprMiscB, X : CMP.b #$01 : BNE .returning
    LDA.w SprMiscC, X : CLC : ADC.w SprMiscE, X : STA.w SprMiscC, X
    LDA.w SprMiscD, X : CLC : ADC.w SprMiscG, X : STA.w SprMiscD, X
    LDA.w SprTimerC, X : BEQ .turn
    LDA.w SprMiscC, X : CMP.b #$18 : BCC .turn
    CMP.b #$E9 : BCS .turn
    LDA.w SprMiscD, X : CMP.b #$28 : BCC .turn
    CMP.b #$E9 : BCS .turn
    RTS
    .turn
    LDA.b #$02 : STA.w SprMiscB, X
    RTS
  .returning
  CMP.b #$02 : BNE .done
  LDA.w SprX, X : CLC : ADC.b #!Beast_HandX : STA.b $00
  LDA.w SprY, X : CLC : ADC.b #!Beast_HandY : STA.b $01
  LDA.w SprMiscC, X : JSR .step : STA.w SprMiscC, X
  LDA.b $01 : STA.b $00
  LDA.w SprMiscD, X : JSR .step : STA.w SprMiscD, X
  CMP.b $01 : BNE .done
  LDA.w SprMiscC, X : PHA
  LDA.w SprX, X : CLC : ADC.b #!Beast_HandX : STA.b $00
  PLA : CMP.b $00 : BNE .done
    STZ.w SprMiscB, X ; caught
  .done
  RTS

  ; A = position, $00 = target. Unsigned step of !Beast_TridentBack toward it.
  .step
  CMP.b $00 : BEQ ..done : BCC ..up
    SEC : SBC.b #!Beast_TridentBack : BCC ..snap
    CMP.b $00 : BCS ..done
    ..snap
    LDA.b $00
    ..done
    RTS
  ..up
    CLC : ADC.b #!Beast_TridentBack : BCS ..snap
    CMP.b $00 : BCC ..done
    LDA.b $00
    RTS
}

; Contact damage from the flying trident: borrow the beast slot's position and
; the smallest hitbox for one Sprite_CheckDamageToPlayer call.
Beast_TridentDamage:
{
  LDA.w SprMiscB, X : BEQ .done
  LDA.w SprX, X : PHA
  LDA.w SprY, X : PHA
  LDA.w SprHitbox, X : PHA
  LDA.w SprMiscC, X : STA.w SprX, X
  LDA.w SprMiscD, X : STA.w SprY, X
  LDA.w SprHitbox, X : AND.b #$E0 : STA.w SprHitbox, X
  JSL Sprite_CheckDamageToPlayer
  PLA : STA.w SprHitbox, X
  PLA : STA.w SprY, X
  PLA : STA.w SprX, X
  .done
  RTS
}

; =========================================================
; Draw. Enter blinks in, a core hit flickers, the death scene flickers out.
Beast_Draw:
{
  LDA.w SprAction, X
  CMP.b #!Beast_ActEnter : BNE .not_enter
    LDA.w SprTimerA, X : CMP.b #!Beast_EnterTime-!Beast_EnterBlink : BCC .draw
    BRA .blink
  .not_enter
  CMP.b #!Beast_ActHit : BEQ .blink
  CMP.b #!Beast_ActDead : BNE .draw
    LDA.w SprTimerA, X : CMP.b #$30 : BCS .draw
  .blink
  LDA.b $1A : AND.b #$02 : BEQ .skip
  .draw
  JSR Ganon_DrawFrame
  LDA.w SprAction, X : CMP.b #!Beast_ActDead : BEQ .shadow
    JSR Beast_DrawTrident
  .shadow
  JSL Sprite_DrawShadow
  .skip
  RTS
}

; One 16x16 OAM piece in slot !Beast_TridentSlot. $00/$02 = the beast's
; screen position (preserved by Ganon_DrawFrame). Scratch $04-$05, $0A-$0D.
Beast_DrawTrident:
{
  LDY.w SprFrame, X
  LDA.w Ganon_DrawFrame_nbr_of_tiles, Y : CMP.b #!Beast_TridentSlot : BCC .fits
    RTS ; 7-piece frame: slot 6 belongs to the body
  .fits
  LDA.w SprMiscB, X : BNE .flying
    REP #$20
    LDA.b $00 : CLC : ADC.w #!Beast_HandX : STA.b $04
    LDA.b $02 : CLC : ADC.w #!Beast_HandY : STA.b $0A
    SEP #$20
    BRA .emit
  .flying
  STZ.b $05 : STZ.b $0B : STZ.b $0D
  LDA.w SprMiscC, X : STA.b $04
  LDA.w SprX, X : STA.b $0C
  REP #$20
  LDA.b $04 : SEC : SBC.b $0C : CLC : ADC.b $00 : STA.b $04
  SEP #$20
  LDA.w SprMiscD, X : STA.b $0A
  LDA.w SprY, X : STA.b $0C
  REP #$20
  LDA.b $0A : SEC : SBC.b $0C : CLC : ADC.b $02 : STA.b $0A
  SEP #$20
  .emit
  REP #$20
  LDA.b $04 : CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .off
  LDA.b $0A : CLC : ADC.w #$0010 : CMP.w #$0100 : BCS .off
  SEP #$20
  LDY.b #!Beast_TridentSlot*4
  LDA.b $04 : STA.b ($90), Y : INY
  LDA.b $0A : STA.b ($90), Y : INY
  LDA.b #!Beast_TridentChr : STA.b ($90), Y : INY
  LDA.b #!Beast_TridentProps : ORA.w SprFlash, X : STA.b ($90), Y
  LDY.b #!Beast_TridentSlot
  LDA.b $05 : AND.b #$01 : ORA.b #$02 : STA.b ($92), Y
  .done
  RTS
  .off
  SEP #$20
  RTS
}

; =========================================================
; Malice floor writer. Runs every beast frame from Beast_Main.
;   writing: up to !Malice_CellsPerFrame cells per frame while the VRAM queue
;            ($1000) has room. R0 writes words and attributes together; stages
;            write words only.
;   warning: !Malice_WarnTime frames, colors 10-12 pulse, room quakes.
;   arm:     every cell of the stage gets tile type $0D in one frame.

; A = job (2 or 3).
Malice_Start:
{
  STA.w SprSubtype, X
  STZ.w SprCustom, X
  RTS
}

Malice_Run:
{
  LDA.w SprSubtype, X : BNE .active
    RTS
  .active
  BMI .warning
  JSR Malice_LoadJob
  STZ.b $0B                   ; cells written this frame
  LDA.b #!Malice_CellsPerFrame : STA.b $0C
  STZ.b $0D
  LDA.w SprSubtype, X : CMP.b #$01 : BNE .loop
    INC.b $0D                 ; R0: attributes with the words
  .loop
    LDA.w SprCustom, X : CMP.b $0A : BCS .band_done
    REP #$20
    LDA.w $1000 : CMP.w #!Malice_QueueMax+1
    SEP #$20
    BCS .flush
    LDA.w SprCustom, X : ASL A : TAY
    JSR Malice_WriteCell
    INC.w SprCustom, X
    INC.b $0B
    DEC.b $0C : BNE .loop
  .flush
  JSR .upload
  RTS

  .band_done
  JSR .upload
  LDA.w SprSubtype, X : CMP.b #$01 : BNE .stage
    STZ.w SprSubtype, X
    RTS
  .stage
  ORA.b #$80 : STA.w SprSubtype, X
  LDA.b #!Malice_WarnTime : STA.w SprTimerB, X
  LDA.b #$35 : STA.w $012E
  RTS

  .warning
  LDA.w SprTimerB, X : BEQ .arm
    JSR Ganondorf_Quake
    LDA.b $1A : AND.b #$08 : JSR Malice_SetColors
    RTS
  .arm
  LDA.w SprSubtype, X : AND.b #$7F
  JSR Malice_LoadJobA
  REP #$20 : LDA.w #!Malice_Attr : STA.b $0E : SEP #$20
  JSR Malice_SetBandAttr
  LDA.b #$00 : JSR Malice_SetColors
  JSR Ganondorf_StopQuake
  STZ.w SprSubtype, X
  RTS

  .upload
  LDA.b $0B : BEQ ..none
    LDA.b #$01 : STA.b $14
  ..none
  RTS
}

; Out: $04-$05 = band table pointer (bank $2A via DBR), $0A = cell count.
Malice_LoadJob:
{
  LDA.w SprSubtype, X : AND.b #$7F
}
Malice_LoadJobA:
{
  TAY
  LDA.w .count, Y : STA.b $0A
  TYA : ASL A : TAY
  REP #$20
  LDA.w .pointer, Y : STA.b $04
  SEP #$20
  RTS

  .count
  db 0
  db (Malice_BandR0_End-Malice_BandR0)/2
  db (Malice_BandS1_End-Malice_BandS1)/2
  db (Malice_BandS2_End-Malice_BandS2)/2
  .pointer
  dw Malice_BandR0, Malice_BandR0, Malice_BandS1, Malice_BandS2
}

; Y = byte index into the band table. $0D != 0: also write the attributes.
; Keeps X and Y.
Malice_WriteCell:
{
  PHX : PHY
  REP #$30
  LDA.b ($04), Y : STA.b $06
  LDX.w $1000
  LDA.w #!Malice_TL : STA.w $1006, X
  LDA.w #!Malice_BL : STA.w $100C, X
  LDA.w #!Malice_TR : STA.w $1012, X
  LDA.w #!Malice_BR : STA.w $1018, X
  LDX.b $06
  LDA.w #!Malice_TL : STA.l $7E2000, X
  LDA.w #!Malice_TR : STA.l $7E2002, X
  LDA.w #!Malice_BL : STA.l $7E2080, X
  LDA.w #!Malice_BR : STA.l $7E2082, X
  LDA.b $0D : AND.w #$00FF : BEQ .words_only
    TXA : LSR A : TAX
    LDA.w #!Malice_Attr
    STA.l $7F2000, X
    STA.l $7F2040, X
  .words_only
  JSR Beast_QueueTail
  SEP #$30
  PLY : PLX
  RTS
}

; $0E-$0F = attribute word, $04/$0A = band from Malice_LoadJobA. Keeps X.
Malice_SetBandAttr:
{
  PHX
  LDA.b $0A : STA.b $0C
  REP #$30
  LDY.w #$0000
  .cell
    LDA.b ($04), Y : LSR A : TAX
    LDA.b $0E
    STA.l $7F2000, X
    STA.l $7F2040, X
    INY : INY
    SEP #$20
    DEC.b $0C
    REP #$20
    BNE .cell
  SEP #$30
  PLX
  RTS
}

; Cancel any job and set every band cell to tile type $00 (no damage).
; Words stay. Keeps X.
Malice_DisarmAll:
{
  STZ.w SprSubtype, X
  STZ.w SprCustom, X
  STZ.w SprTimerB, X
  REP #$20 : STZ.b $0E : SEP #$20
if !Beast_MaliceR0 == 1
  LDA.b #$01 : JSR Malice_LoadJobA : JSR Malice_SetBandAttr
endif
  LDA.b #$02 : JSR Malice_LoadJobA : JSR Malice_SetBandAttr
  LDA.b #$03 : JSR Malice_LoadJobA : JSR Malice_SetBandAttr
  LDA.b #$00 : JSR Malice_SetColors
  JSR Ganondorf_StopQuake
  RTS
}

; A = 0: steady malice colors; else the bright warning color. Keeps X.
Malice_SetColors:
{
  REP #$20
  AND.w #$00FF : BEQ .steady
    LDA.w #!Malice_ColPulse
    STA.l !Malice_ColAddr : STA.l !Malice_ColMirror
    STA.l !Malice_ColAddr+2 : STA.l !Malice_ColMirror+2
    STA.l !Malice_ColAddr+4 : STA.l !Malice_ColMirror+4
    BRA .done
  .steady
  LDA.w #!Malice_Col10 : STA.l !Malice_ColAddr : STA.l !Malice_ColMirror
  LDA.w #!Malice_Col11 : STA.l !Malice_ColAddr+2 : STA.l !Malice_ColMirror+2
  LDA.w #!Malice_Col12 : STA.l !Malice_ColAddr+4 : STA.l !Malice_ColMirror+4
  .done
  SEP #$20
  LDA.b #$01 : STA.b $15
  RTS
}

; Copies of floor_puzzle.asm replace_tile_continue / draw_one_corner (bank $2A
; cannot JSR into the dungeon bank). In: M=16 X=16, $06 = tilemap offset,
; tile words already at $1006/$100C/$1012/$1018 + $1000.
Beast_QueueTail:
{
  LDX.w $1000
  LDA.w #$0000 : JSR Beast_DrawCorner : STA.w $1002, X
  LDA.w #$0080 : JSR Beast_DrawCorner : STA.w $1008, X
  LDA.w #$0002 : JSR Beast_DrawCorner : STA.w $100E, X
  LDA.w #$0082 : JSR Beast_DrawCorner : STA.w $1014, X
  LDA.w #$0100
  STA.w $1004, X
  STA.w $100A, X
  STA.w $1010, X
  STA.w $1016, X
  LDA.w #$FFFF : STA.w $101A, X
  TXA : CLC : ADC.w #$0018 : STA.w $1000
  RTS
}

Beast_DrawCorner:
{
  CLC : ADC.b $06 : STA.b $0E
  AND.w #$0040
  LSR A : LSR A : LSR A : LSR A
  XBA : STA.b $08
  LDA.b $0E : AND.w #$303F : LSR A : ORA.b $08 : STA.b $08
  LDA.b $0E : AND.w #$0F80 : LSR A : LSR A : ORA.b $08
  XBA
  RTS
}

; Band tables: tilemap byte offsets (row*$40+col)*2 of each tile16's top-left
; tile8. Generated by abyss-finale02/beast/tools/bands.py from the
; MALICE_FLOOR_FACTS rectangles. Torch tiles (37,25) and (57,25) excluded.
Malice_BandR0:
  dw $02C6, $02CA, $02CE, $02D2, $02D6, $02DA, $02DE, $02E2
  dw $02E6, $02EA, $02EE, $02F2, $02F6, $03F6, $04F6, $05F6
  dw $06F6, $07F6, $08F6, $09F6, $0AF6, $0BF6, $0CF6, $0DF6
  dw $0DF2, $0DEE, $0DEA, $0DE6, $0DE2, $0DDE, $0DDA, $0DD6
  dw $0DD2, $0DCE, $0DCA, $0DC6, $0CC6, $0BC6, $0AC6, $09C6
  dw $08C6, $07C6, $06C6, $05C6, $04C6, $03C6
Malice_BandR0_End:
Malice_BandS1:
  dw $03CA, $03CE, $03D2, $03D6, $03DA, $03DE, $03E2, $03E6
  dw $03EA, $03EE, $03F2, $04F2, $05F2, $06F2, $07F2, $08F2
  dw $09F2, $0AF2, $0BF2, $0CEE, $0CEA, $0CE6, $0CE2, $0CDE
  dw $0CDA, $0CD6, $0CD2, $0CCE, $0BCA, $0ACA, $09CA, $08CA
  dw $07CA, $06CA, $05CA, $04CA
Malice_BandS1_End:
Malice_BandS2:
  dw $04CE, $04D2, $04D6, $04DA, $04DE, $04E2, $04E6, $04EA
  dw $04EE, $05EE, $06EE, $07EE, $08EE, $09EE, $0AEE, $0BEE
  dw $0BEA, $0BE6, $0BE2, $0BDE, $0BDA, $0BD6, $0BD2, $0BCE
  dw $0ACE, $09CE, $08CE, $07CE, $06CE, $05CE
Malice_BandS2_End:
