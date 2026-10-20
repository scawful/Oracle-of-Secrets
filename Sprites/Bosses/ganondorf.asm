; =========================================================
; Ganondorf finale, slice 1 (phase 1 volley)
;
; Design: AFS handoffs/ganondorf_finale_2026-10-20/DESIGN.md sections 3-4.
; After Kydreeok dies in room $00, room tag $3D (Triforce door) calls
; Ganondorf_DoorGate. The gate spawns Ganondorf ($D3) once and keeps the
; door shut until he is defeated.
;
; Phase 1 loop:
;   float -> cast one energy ball ($46) at Link
;   Link hits the ball with the Master Sword (sword level >= 2) -> it flies back
;   Ganondorf returns it 1-3 times (random), faster each time
;   he varies his glide during rallies, with a short return stroke
;   the last return hits him -> stunned -> 3 sword hits -> he casts a bat
;   the independent bat flies at Link while he recovers and changes perch
;   between rallies he rises and stomps, dropping the four outer floor edges
;   9 sword hits in total -> he dies -> GanondorfFight = 2 -> door opens
;
; Original 32x40 art: one $1800 sheet, plus the vanilla $800 falling-floor slot.
; Source art and generated OAM tables: Data/graphics/ganondorf/ and
; Scripts/Generate/build_ganondorf_art.py.
; Lives in free bank $2A, so it costs no bank $30-$32 bytes.
; =========================================================

Ganon_SetupActionHitbox = $06F57E ; SetupActionHitbox_long (Link's weapon box -> pos1)

!Ganon_HitsPerStun  = 3
!Ganon_TotalHits    = 9
!Ganon_BallSpeed    = $10
!Ganon_BallSpeedMid = $14
!Ganon_BallSpeedEnd = $18
!Ganon_BallSpeedMax = $30
!Ganon_GlideSpeed   = $08
!Ganon_BatSpeed     = $18
!Ganon_BatLifetime  = $60

!Ganon_FrameIdle     = 0
!Ganon_FrameCast     = 1
!Ganon_FrameHurt     = 2
!Ganon_FrameRelease  = 5
; Frames 6/7 remain in the source sheet for future side-art revisions.
!Ganon_FrameBackA    = 8
!Ganon_FrameChargeA  = 10
!Ganon_FrameReady    = 12
!Ganon_FrameHalf     = 13
!Ganon_FrameRaised   = 14
!Ganon_FrameGather   = 15
!Ganon_FrameWindup   = 16
!Ganon_FrameFollow   = 17
!Ganon_FrameRecover  = 18
!Ganon_FrameBat      = 19

pushpc
org $2A8000

; =========================================================
; Ganondorf ($D3)

!SPRID              = Sprite_Ganondorf
!NbrTiles           = 07  ; zero-based: up to 6 body + held ball + shadow
!Harmless           = 00
!HVelocity          = 00
!Health             = 00  ; set in prep; refilled each frame (hits are counted)
!Damage             = 04  ; contact damage class
!DeathAnimation     = 00
!ImperviousAll      = 01  ; cleared only while stunned
!SmallShadow        = 00
!Shadow             = 01
!Palette            = 00
!Hitbox             = 10  ; retain slice 1's $0A combat box (32x40 at -8/-8)
!Persist            = 01
!Statis             = 00
!CollisionLayer     = 01
!CanFall            = 00
!DeflectArrow       = 01
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 00
!ImpervSwordHammer  = 00
!Boss               = 01
%Set_Sprite_Properties(Sprite_Ganondorf_Prep, Sprite_Ganondorf_Long)

Sprite_Ganondorf_Long:
{
  PHB : PHK : PLB
  ; Fairy revive: the game over module reloaded the sheets and palettes. Graphics only; the
  ; fight (hits, stun count, action, teleport spot, ball) keeps running from where it was.
  LDA.w BossReinject : BEQ .no_reinject
    STZ.w BossReinject
    JSL ApplyGanondorfGraphics
    JSL ApplyGanondorfPalette
  .no_reinject
  JSR Ganondorf_Draw
  JSL Sprite_CheckActive : BCC .not_active
    JSR Ganondorf_Main
  .not_active
  PLB
  RTL
}

; X = sprite slot. Also called by Ganondorf_DoorGate after a dynamic spawn.
Sprite_Ganondorf_Prep:
{
  PHB : PHK : PLB
  LDA.b #$FF : STA.w SprHealth, X
  LDA.b #!Ganon_TotalHits : STA.w SprMiscF, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; impervious
  LDA.b #$10 : STA.w SprHeight, X
  LDA.b #$FF : STA.w SprMiscD, X ; no ball yet
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w SprMiscA, X ; Float escape target; overwritten by the stun hit counter
  STZ.w SprMiscB, X ; no return stroke during the initial front-facing cast
  STZ.w SprMiscG, X
  ; SprCustom ($1CC0,X): bits 0-1 = movement mode, bit 7 = frozen rear return.
  ; The existing per-sprite array is otherwise unused; no shared RAM is added.
  STZ.w SprCustom, X ; 0 clockwise/pursuit, 1 counterclockwise/glide, 2 weave
  STZ.w SprSubtype, X ; four falling-floor edges, independent of the hit counter
  STZ.w SprTimerD, X
  STZ.w SprTimerB, X
  STZ.w SprMiscE, X
  STZ.w SprMiscC, X ; logical return: 0 front, 1 right, 2 left, 3 back
  LDA.b #$40 : STA.w SprTimerA, X
  JSL ApplyGanondorfGraphics
  JSL ApplyGanondorfPalette
  LDA.b #$1F : STA.w $012C ; final-boss theme, independent of Kydreeok's death fanfare
  STZ.w BossReinject
  PLB
  RTL
}

Ganondorf_Main:
{
  LDA.b #$FF : STA.w SprHealth, X ; damage is counted in SprMiscF, never by HP
  %SpriteJumpTable(Ganondorf_Intro,
                   Ganondorf_Float,
                   Ganondorf_Cast,
                   Ganondorf_WaitBall,
                   Ganondorf_Stunned,
                   Ganondorf_CastBat,
                   Ganondorf_Dead,
                   Ganondorf_Stomp)

  ; 0: appear (flicker)
  Ganondorf_Intro:
  {
    JSR Ganondorf_Bob
    LDA.w SprTimerA, X : BNE .wait
      %GotoAction(1)
      LDA.b #$40 : STA.w SprTimerA, X
    .wait
    RTS
  }

  ; 1: establish a deliberate launch gap, then charge when the cooldown permits
  Ganondorf_Float:
  {
    JSR Ganondorf_Bob
    JSR Ganondorf_Chase
    JSL Sprite_CheckDamageToPlayer
    LDA.w SprTimerA, X : BNE .wait
      JSR Ganondorf_CheckCastSpacing : BCC .wait
      %GotoAction(2)
      STZ.w SprMiscA, X
      STZ.w SprMiscB, X
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.b #!Ganon_FrameReady : STA.w SprFrame, X
      LDA.b #$30 : STA.w SprTimerA, X
    .wait
    RTS
  }

  ; 2: front-facing lift, gather, charge and windup (42 ticks), then release.
  ; The held ball is one OAM piece, not an active/damaging child sprite.
  Ganondorf_Cast:
  {
    JSR Ganondorf_Bob
    LDA.w SprTimerA, X : CMP.b #$07 : BCC .release
    CMP.b #$0D : BCC .windup
    CMP.b #$19 : BCC .charge
    CMP.b #$1F : BCC .gather
    CMP.b #$25 : BCC .raised
    CMP.b #$2B : BCC .half
      LDA.b #!Ganon_FrameReady : BRA .set_pose
    .half
      LDA.b #!Ganon_FrameHalf : BRA .set_pose
    .raised
      LDA.b #!Ganon_FrameRaised : BRA .set_pose
    .gather
      LDA.b #!Ganon_FrameGather : BRA .set_pose
    .windup
      LDA.b #!Ganon_FrameWindup : BRA .set_pose
    .charge
      LDA.b $1A : LSR #3 : AND.b #$01
      CLC : ADC.b #!Ganon_FrameChargeA
    .set_pose
      STA.w SprFrame, X
      RTS
    .release
    JSR Ganondorf_CheckCastSpacing : BCC .cancel
    JSR Ganondorf_SpawnBall
    .ball_spawned
    BCC .cancel
    LDA.b #!Ganon_FrameRelease : STA.w SprFrame, X
    ; Enter rally immediately so a close reflection can already stun him.
    %GotoAction(3)
    LDA.b #$10 : STA.w SprTimerC, X
    RTS
    .cancel
    %GotoAction(1)
    LDA.b #$08 : STA.w SprTimerA, X
    STZ.w SprMiscA, X
    STZ.w SprMiscB, X
    STZ.w SprFrame, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
  }

  ; 3: rally in progress; the ball moves us to Stunned when it lands
  Ganondorf_WaitBall:
  {
    JSR Ganondorf_Bob
    JSR Ganondorf_VolleyMove
    LDA.w SprTimerD, X : BNE .contact_done
    JSL Sprite_CheckDamageToPlayer
    .contact_done
    ; The first cast stays front-facing; later returns face the outgoing ball.
    LDA.w SprMiscB, X : BEQ .first_cast
      JSR Ganondorf_SetVolleyPose
      BRA .check_ball
    .first_cast
    LDA.w SprTimerC, X : BEQ .pose
    CMP.b #$0D : BCS .first_release
    CMP.b #$07 : BCS .first_follow
      LDA.b #!Ganon_FrameRecover : BRA .pose
    .first_follow
      LDA.b #!Ganon_FrameFollow : BRA .pose
    .first_release
      LDA.b #!Ganon_FrameRelease
    .pose
    STA.w SprFrame, X
    .check_ball
    LDY.w SprMiscD, X : BMI .ball_gone
    LDA.w SprState, Y : BEQ .ball_gone
    LDA.w SprType, Y : CMP.b #Sprite_GanonBall : BNE .ball_gone
    LDA.w SprAction, Y : BNE .ball_gone ; fragments and dissipation end the rally
      RTS
    .ball_gone
    LDA.b #$FF : STA.w SprMiscD, X
    JSR Ganondorf_StartStomp
    RTS
  }

  ; 4: grounded and vulnerable to the sword
  Ganondorf_Stunned:
  {
    LDA.b #$02 : STA.w SprFrame, X
    STZ.w SprHeight, X
    JSL Sprite_CheckDamageFromPlayer : BCC .no_hit
      DEC.w SprMiscF, X : BEQ .die
      DEC.w SprMiscA, X : BEQ .cast_bat
    .no_hit
    LDA.w SprTimerA, X : BNE .exit
    .cast_bat
    JSR Ganondorf_StartBatCast
    .exit
    RTS

    .die
    %GotoAction(6)
    LDA.b #$80 : STA.w SprTimerA, X
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
    JSL Sprite_KillFriends
    RTS
  }

  ; 5: remain human, telegraph a cast, then release an independent bat.
  ; Relocation happens only after the cast has finished, outside a live rally.
  Ganondorf_CastBat:
  {
    JSR Ganondorf_Bob
    LDA.w SprTimerA, X : BEQ .recover
    CMP.b #$25 : BCS .ready
    CMP.b #$19 : BCS .windup
    CMP.b #$18 : BNE .released
      JSR Ganondorf_SpawnBat
    .bat_spawned
    .released
    LDA.w SprTimerA, X : CMP.b #$11 : BCS .release
    CMP.b #$09 : BCS .follow
      LDA.b #!Ganon_FrameRecover : BRA .pose
    .ready
      LDA.b #!Ganon_FrameReady : BRA .pose
    .windup
      LDA.b #!Ganon_FrameWindup : BRA .pose
    .release
      LDA.b #!Ganon_FrameRelease : BRA .pose
    .follow
      LDA.b #!Ganon_FrameFollow
    .pose
    STA.w SprFrame, X
    RTS
    .recover
      JSR Ganondorf_Relocate
      LDA.b #$10 : STA.w SprHeight, X
      JSR Ganondorf_StartStomp
    RTS
  }

  ; 6: flicker out, then let the door open
  Ganondorf_Dead:
  {
    LDA.b #$02 : STA.w SprFrame, X
    LDA.w SprTimerA, X : BNE .exit
      LDA.b #$02 : STA.l GanondorfFight
      STZ.w SprState, X
    .exit
    RTS
  }
}

Ganondorf_StartBatCast:
{
  %GotoAction(5)
  LDA.b #$30 : STA.w SprTimerA, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  STZ.w SprMiscB, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #!Ganon_FrameReady : STA.w SprFrame, X
  LDA.b #$10 : STA.w SprHeight, X
  RTS
}

; Hover height $0C-$14, one pixel every 4 frames.
Ganondorf_Bob:
{
  LDA.b $1A : AND.b #$03 : BNE .exit
  LDA.w SprMiscE, X : BNE .down
    INC.w SprHeight, X
    LDA.w SprHeight, X : CMP.b #$14 : BCC .exit
      INC.w SprMiscE, X
      RTS
  .down
    DEC.w SprHeight, X
    LDA.w SprHeight, X : CMP.b #$0D : BCS .exit
      STZ.w SprMiscE, X
  .exit
  RTS
}

; Float approaches the desired launch gap slowly and recedes when too close.
; A blocked retreat latches a farthest arena corner until enough space opens.
; SprMiscA is free in Float; the native stun entry overwrites its hit counter.
Ganondorf_Chase:
{
  JSR Ganondorf_GetLaunchGap
  JSR Ganondorf_GetSpacingBand
  REP #$20
  LDA.b $08 : CLC : ADC.w #$0008 : CMP.b $0C
  SEP #$20
  BEQ .hold
  BCS .recede
    STZ.w SprMiscA, X
    LDA.b #$04 : STA.b $0E
    JSR Ganondorf_ApplyFloatVelocity
    BRA .move
  .recede
  LDA.w SprMiscA, X : BMI .escape
    LDA.b #$08 : STA.b $0E
    JSR Ganondorf_ApplyFloatVelocity
    LDA.w SprXSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
    LDA.w SprYSpeed, X : EOR.b #$FF : INC A : STA.w SprYSpeed, X
    LDA.w SprXSpeed, X : ORA.w SprYSpeed, X : BNE .recede_move
      JSR Ganondorf_ChooseEscapeCorner
      BRA .escape
    .recede_move
    JSR Ganondorf_MoveClamped : BCC .pose
      JSR Ganondorf_ChooseEscapeCorner
      BRA .pose
  .escape
  JSR Ganondorf_EscapeVelocity
  BRA .move
  .hold
  STZ.w SprMiscA, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  .move
  JSR Ganondorf_MoveClamped
  .pose
  JSR Ganondorf_CompareLinkY : BCC .back
    STZ.w SprFrame, X
    RTS
  .back
    LDA.b $1A : LSR #3 : AND.b #$01
    CLC : ADC.b #!Ganon_FrameBackA : STA.w SprFrame, X
    RTS
}

; Launch position matches SpawnBall exactly, including the hovering height.
; Returns signed 16-bit deltas in $04/$06 and approximate gap in $0C.
; Internal ABI: A/X/Y enter 8-bit; only A widens temporarily, X is preserved.
Ganondorf_GetLaunchGap:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : SEC : SBC.w SprHeight, X : STA.b $02
  LDA.w SprYH, X : SBC.b #$00 : STA.b $03
  REP #$20
  LDA.b $02 : SEC : SBC.w #$0020 : STA.b $02
  SEP #$20
  JSR Ganondorf_ScoreLaunchPoint
  RTS
}

; $00/$02 = launch point. max(abs(dx),abs(dy)) + floor(min/2) avoids
; multiplication and leaves enough reachable space at the arena center.
Ganondorf_ScoreLaunchPoint:
{
  REP #$20
  LDA.b $22 : SEC : SBC.b $00 : STA.b $04 : BPL .x_positive
    EOR.w #$FFFF : INC A
  .x_positive
  STA.b $08
  LDA.b $20 : SEC : SBC.b $02 : STA.b $06 : BPL .y_positive
    EOR.w #$FFFF : INC A
  .y_positive
  STA.b $0A
  CMP.b $08 : BCS .y_larger
    LSR A : CLC : ADC.b $08
    BRA .store
  .y_larger
  LDA.b $08 : LSR A : CLC : ADC.b $0A
  .store
  STA.b $0C
  SEP #$20
  RTS
}

; Remaining hits select the same three stages as projectile launch speed.
; $08/$0A are 16-bit minimum/maximum, leaving launch deltas $04/$06 intact.
Ganondorf_GetSpacingBand:
{
  LDY.b #$00
  LDA.w SprMiscF, X : CMP.b #$07 : BCS .stage_ready
    INY
    CMP.b #$04 : BCS .stage_ready
      INY
  .stage_ready
  LDA.w .minimum, Y : STA.b $08
  STZ.b $09
  LDA.w .maximum, Y : STA.b $0A
  STZ.b $0B
  RTS

  .minimum : db $38, $40, $48
  .maximum : db $70, $78, $80
}

; Carry set only when the current launch gap is in the inclusive stage band.
Ganondorf_CheckCastSpacing:
{
  JSR Ganondorf_GetLaunchGap
  JSR Ganondorf_GetSpacingBand
  REP #$20
  LDA.b $0C : CMP.b $08 : BCC .invalid
  CMP.b $0A : BEQ .valid
  BCS .invalid
  .valid
  SEP #$20
  SEC
  RTS
  .invalid
  SEP #$20
  CLC
  RTS
}

; $04/$06 = signed 16-bit target deltas, $0E = axis speed. This avoids the
; vanilla projection helper's signed low-byte limits at the opposite edges.
Ganondorf_ApplyFloatVelocity:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b $04 : ORA.b $05 : BEQ .y_axis
    LDA.b $05 : BMI .left
      LDA.b $0E : STA.w SprXSpeed, X
      BRA .y_axis
    .left
    LDA.b $0E : EOR.b #$FF : INC A : STA.w SprXSpeed, X
  .y_axis
  LDA.b $06 : ORA.b $07 : BEQ .done
    LDA.b $07 : BMI .up
      LDA.b $0E : STA.w SprYSpeed, X
      RTS
    .up
    LDA.b $0E : EOR.b #$FF : INC A : STA.w SprYSpeed, X
  .done
  RTS
}

Ganondorf_ChooseEscapeCorner:
{
  REP #$20
  STZ.b $0E
  SEP #$20
  LDY.b #$03
  .next
  LDA.w Ganondorf_EscapeX, Y : STA.b $00
  LDA.b $23 : STA.b $01
  LDA.w Ganondorf_EscapeY, Y
  SEC : SBC.w SprHeight, X : STA.b $02
  LDA.b $21 : SBC.b #$00 : STA.b $03
  REP #$20
  LDA.b $02 : SEC : SBC.w #$0020 : STA.b $02
  SEP #$20
  JSR Ganondorf_ScoreLaunchPoint
  REP #$20
  LDA.b $0C : CMP.b $0E : BCC .not_farthest
    STA.b $0E
    SEP #$20
    TYA : ORA.b #$80 : STA.w SprMiscA, X
  .not_farthest
  SEP #$20
  DEY : BPL .next
  RTS
}

Ganondorf_EscapeVelocity:
{
  LDA.w SprMiscA, X : AND.b #$03 : TAY
  LDA.w Ganondorf_EscapeX, Y : STA.b $04
  LDA.b $23 : STA.b $05
  LDA.w Ganondorf_EscapeY, Y : STA.b $06
  LDA.b $21 : STA.b $07
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $04 : SEC : SBC.b $00 : STA.b $04
  LDA.b $06 : SEC : SBC.b $02 : STA.b $06
  SEP #$20
  LDA.b #$08 : STA.b $0E
  JSR Ganondorf_ApplyFloatVelocity
  RTS
}

Ganondorf_EscapeX: db $38, $A8, $38, $A8
Ganondorf_EscapeY: db $58, $58, $B8, $B8

; Carry clear when Link is above the boss's ground position, set otherwise.
; Compare full coordinates without changing the 8-bit sprite index.
Ganondorf_CompareLinkY:
{
  LDA.w SprY, X : STA.b $00
  LDA.w SprYH, X : STA.b $01
  REP #$20
  LDA.b $20 : CMP.b $00
  SEP #$20
  RTS
}

Ganondorf_FreezeReturnPose:
{
  LDA.w SprCustom, X : AND.b #$03 : STA.w SprCustom, X
  JSR Ganondorf_CompareLinkY : BCS .done
    LDA.w SprCustom, X : ORA.b #$80 : STA.w SprCustom, X
  .done
  RTS
}

Ganondorf_TurnClockwise:
{
  LDA.w SprXSpeed, X : PHA
  LDA.w SprYSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
  PLA : STA.w SprYSpeed, X
  RTS
}

Ganondorf_TurnCounterclockwise:
{
  LDA.w SprXSpeed, X : PHA
  LDA.w SprYSpeed, X : STA.w SprXSpeed, X
  PLA : EOR.b #$FF : INC A : STA.w SprYSpeed, X
  RTS
}

; Change horizontal direction every 64 frames; keep the slow vertical pursuit.
Ganondorf_Weave:
{
  LDA.b $1A : AND.b #$40 : BNE .left
    LDA.b #!Ganon_GlideSpeed
    BRA .set
  .left
    LDA.b #!Ganon_GlideSpeed : EOR.b #$FF : INC A
  .set
  STA.w SprXSpeed, X
  RTS
}

; Keep every movement mode inside the existing north-arena anchors. Construct
; full positions so a low-byte underflow cannot wrap to the opposite edge.
; Carry set when clamping blocked the movement; Float can choose an escape.
Ganondorf_MoveClamped:
{
  JSR GanonMagic_TryAfterimage
  JSL Sprite_Move
  REP #$20
  STZ.b $08
  SEP #$20
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  REP #$20
  LDA.b $22 : AND.w #$FF00 : ORA.w #$0038 : STA.b $02
  LDA.b $00 : CMP.b $02 : BCS .x_max
    LDA.b $02 : STA.b $00
    LDA.w #$0001 : STA.b $08
  .x_max
  LDA.b $02 : CLC : ADC.w #$0070 : CMP.b $00 : BCS .x_store
    STA.b $00
    LDA.w #$0001 : STA.b $08
  .x_store
  SEP #$20
  LDA.b $00 : STA.w SprX, X
  LDA.b $01 : STA.w SprXH, X
  LDA.w SprY, X : STA.b $00
  LDA.w SprYH, X : STA.b $01
  REP #$20
  LDA.b $20 : AND.w #$FF00 : ORA.w #$0058 : STA.b $02
  LDA.b $00 : CMP.b $02 : BCS .y_max
    LDA.b $02 : STA.b $00
    LDA.w #$0001 : STA.b $08
  .y_max
  LDA.b $02 : CLC : ADC.w #$0060 : CMP.b $00 : BCS .y_store
    STA.b $00
    LDA.w #$0001 : STA.b $08
  .y_store
  SEP #$20
  LDA.b $00 : STA.w SprY, X
  LDA.b $01 : STA.w SprYH, X
  LDA.b $08 : BEQ .unblocked
    SEC
    RTS
  .unblocked
  CLC
  RTS
}

Ganondorf_SpawnBall:
{
  LDA.b #Sprite_GanonBall : JSL Sprite_SpawnDynamically : BPL .spawned
    BRL .no_slot
  .spawned
    ; Body center is x+8. A 16px ball at x has the same center.
    LDA.w SprX, X : STA.w SprX, Y
    LDA.w SprXH, X : STA.w SprXH, Y
    ; Match the held OAM ball at (0,-32), including 16-bit borrow.
    LDA.w SprY, X : SEC : SBC.w SprHeight, X : STA.b $00
    LDA.w SprYH, X : SBC.b #$00 : STA.b $01
    LDA.b $00 : SEC : SBC.b #$20 : STA.w SprY, Y
    LDA.b $01 : SBC.b #$00 : STA.w SprYH, Y
    LDA.w SprFloor, X : STA.w SprFloor, Y
    LDA.b #$00
    STA.w SprHeight, Y
    STA.w SprAction, Y
    STA.w SprMiscA, Y   ; rally count (Link's returns)
    STA.w SprMiscB, Y   ; 0 = heading to Link, 1 = heading to Ganondorf
    ; Open slowly; restore the original launch speed for the last three hits.
    LDA.b #!Ganon_BallSpeed : STA.w SprMiscE, Y
    LDA.w SprMiscF, X : CMP.b #$07 : BCS .speed_ready
      LDA.b #!Ganon_BallSpeedMid : STA.w SprMiscE, Y
      LDA.w SprMiscF, X : CMP.b #$04 : BCS .speed_ready
        LDA.b #!Ganon_BallSpeedEnd : STA.w SprMiscE, Y
    .speed_ready
    TXA : STA.w SprMiscD, Y ; parent slot
    JSL GetRandomInt : AND.b #$03 : BNE .returns
      INC A
    .returns
    STA.w SprMiscC, Y   ; Ganondorf's returns left (1-3)
    TYA : STA.w SprMiscD, X
    PHX
    TYX
    LDA.w SprMiscE, X : JSL Sprite_ApplySpeedTowardsPlayer
    PLX
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
    SEC
    RTS
  .no_slot
  LDA.b #$FF : STA.w SprMiscD, X
  CLC
  RTS
}

Ganondorf_Draw:
{
  LDY.w SprAction, X
  LDA.w .flicker, Y : BEQ .draw
    LDA.b $1A : AND.b #$02 : BEQ .skip
  .draw
  JSR Ganon_DrawFrame
  JSL Sprite_DrawShadow
  .skip
  RTS

  .flicker : db 0, 0, 0, 0, 0, 0, 1, 0
}

; Vary the glide while the ball is active. Never teleport during a live volley.
; Returns get an uninterrupted stroke; stale vanish timers are cleared.
Ganondorf_VolleyMove:
{
  STZ.w SprTimerD, X
  LDA.w SprTimerC, X : BNE .done
  LDA.b #!Ganon_GlideSpeed : JSL Sprite_ApplySpeedTowardsPlayer
  LDA.w SprCustom, X : AND.b #$03 : BEQ .clockwise
    CMP.b #$01 : BEQ .counterclockwise
      JSR Ganondorf_Weave
      BRA .move
  .clockwise
  JSR Ganondorf_TurnClockwise
  BRA .move
  .counterclockwise
  JSR Ganondorf_TurnCounterclockwise
  .move
  JSR Ganondorf_MoveClamped
  .done
  RTS
}

Ganondorf_Relocate:
{
  JSL GetRandomInt : AND.b #$03 : TAY
  LDA.w .x, Y : STA.w SprX, X
  LDA.b $23 : STA.w SprXH, X
  LDA.w .y, Y : STA.w SprY, X
  LDA.b $21 : STA.w SprYH, X
  STZ.w $0D70, X ; X subpixel
  STZ.w $0D60, X ; Y subpixel
  RTS

  .x : db $70, $48, $98, $70
  .y : db $78, $90, $90, $A8
}

Ganondorf_StartStomp:
{
  %GotoAction(7)
  STZ.w SprMiscG, X
  STZ.w SprMiscB, X
  STZ.w SprTimerD, X
  LDA.b #$18 : STA.w SprTimerA, X
  LDA.b #!Ganon_FrameCast : STA.w SprFrame, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  RTS
}

; Rise, slam, then recover. Floor changes are the native falling-tile overlords.
Ganondorf_Stomp:
{
  LDA.w SprMiscG, X : CMP.b #$02 : BEQ .recover
  CMP.b #$01 : BEQ .descend
    LDA.b #!Ganon_FrameCast : STA.w SprFrame, X
    LDA.w SprHeight, X : CMP.b #$28 : BCS .at_top
      INC.w SprHeight, X
    .at_top
    LDA.w SprTimerA, X : BNE .done
      INC.w SprMiscG, X
      LDA.b #!Ganon_FrameRelease : STA.w SprFrame, X
    .done
    RTS
  .descend
  LDA.w SprHeight, X : SEC : SBC.b #$04 : BCC .impact
    STA.w SprHeight, X
    BNE .done
  .impact
  STZ.w SprHeight, X
  LDA.b #$02 : STA.w SprMiscG, X
  LDA.b #$18 : STA.w SprTimerA, X
  LDA.b #!Ganon_FrameHurt : STA.w SprFrame, X
  LDA.b #$07 : STA.w $012D ; vanilla Ganon landing thud
  LDA.b #$0C : JSL SpriteSFX_QueueSFX2WithPan
  JSR Ganondorf_SpawnFloorCollapse
  RTS
  .recover
  JSL Sprite_CheckDamageToPlayer
  LDA.w SprTimerA, X : BEQ .rise_again
    AND.b #$01 : ASL A : TAY
    REP #$20
    LDA.w .shake, Y : STA.w $011C
    SEP #$20
    RTS
  .rise_again
  STZ.w $011C
  STZ.w $011D
  LDA.b #$10 : STA.w SprHeight, X
  ; Guarantee a different movement pattern for the next rally. Clear the
  ; completed return's rear-art flag without sharing the stomp substate.
  LDA.w SprCustom, X : AND.b #$03 : INC A : CMP.b #$03 : BCC .mode_ready
    LDA.b #$00
  .mode_ready
  STA.w SprCustom, X
  %GotoAction(1)
  LDA.b #$50 : STA.w SprTimerA, X
  RTS

  .shake : dw 1, -1
}

Ganondorf_SpawnFloorCollapse:
{
  LDA.w SprSubtype, X : CMP.b #$04 : BCS .done
  LDY.b #$07
  .next
  LDA.w OverlordId, Y : BEQ .free
    DEY : BPL .next
    RTS
  .free
  LDA.w SprSubtype, X : INC.w SprSubtype, X
  PHX
  TAX
  LDA.w .type, X : STA.w OverlordId, Y
  LDA.w .x, X : STA.w OverlordX, Y
  LDA.b $23 : STA.w OverlordXH, Y
  LDA.w .y, X : STA.w OverlordY, Y
  LDA.b $21 : STA.w OverlordYH, Y
  LDA.b #$00
  STA.w OverlordTimerA, Y
  STA.w OverlordTimerB, Y
  STA.w OverlordTimerC, Y
  PLX
  .done
  RTS

  .type : db $0C, $0D, $0E, $0F
  .x    : db $18, $D8, $D8, $18
  .y    : db $28, $28, $D8, $D8
}

; Two return poses plus a draw-only recoil. Freeze front/rear for the entire
; stroke; SprMiscC retains all four logical directions for aiming and recoil.
; Side frames remain dormant in the source art. The first cast stays front.
Ganondorf_SetVolleyPose:
{
  LDA.w SprCustom, X : BMI .rear
  LDA.w SprTimerC, X : BEQ .front_rest
  CMP.b #$0D : BCS .front_windup
  CMP.b #$09 : BCS .front_release
  CMP.b #$05 : BCS .front_follow
    LDA.b #!Ganon_FrameRecover : BRA .front_set
  .front_windup
    LDA.b #!Ganon_FrameWindup : BRA .front_set
  .front_release
    LDA.b #!Ganon_FrameRelease : BRA .front_set
  .front_follow
    LDA.b #!Ganon_FrameFollow : BRA .front_set
  .front_rest
    LDA.b #!Ganon_FrameIdle
  .front_set
  STA.w SprFrame, X
  RTS
  .rear
  LDY.b #$00
  LDA.w SprCustom, X : BPL .facing_ready
    INY
  .facing_ready
  LDA.w .rest, Y : STA.w SprFrame, X
  LDA.w SprTimerC, X : BEQ .done
    CMP.b #$09 : BCC .follow
      LDA.w .windup, Y
      BRA .set
    .follow
    LDA.w .followthrough, Y
    .set
    STA.w SprFrame, X
  .done
  RTS

  .rest          : db 0, 8
  .windup        : db 1, 8
  .followthrough : db 5, 9
}

; =========================================================
; Energy ball ($46)

!SPRID              = Sprite_GanonBall
!NbrTiles           = 01
!Harmless           = 00
!HVelocity          = 01
!Health             = 00
!Damage             = 01  ; native class1: half-heart; class2 is zero damage
!DeathAnimation     = 01
!ImperviousAll      = 01  ; only the reflect check below touches the sword
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 00
!Hitbox             = 00
!Persist            = 00
!Statis             = 01  ; never holds the room tag
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 01
!ImpervSwordHammer  = 01
!Boss               = 00
%Set_Sprite_Properties(Sprite_GanonBall_Prep, Sprite_GanonBall_Long)

Sprite_GanonBall_Long:
{
  PHB : PHK : PLB
  JSR GanonBall_Draw
  JSL Sprite_CheckActive : BCC .not_active
    JSR GanonBall_Main
  .not_active
  PLB
  RTL
}

; Only reached if a room places the ball; it needs a parent, so remove it.
Sprite_GanonBall_Prep:
{
  STZ.w SprState, X
  RTL
}

incsrc "ganondorf_ball_effects.asm"
incsrc "ganondorf_bat.asm"
incsrc "ganondorf_magic.asm"

; Carry set = Link's Master Sword (or better) hit the ball this frame.
; Guards match vanilla Sprite_CheckDamageFromLink for the Agahnim ball ($7B).
GanonBall_CheckSwordReflect:
{
  LDA.l $7EF359 : CMP.b #$02 : BCC .no
  LDA.b $EE : CMP.w SprFloor, X : BNE .no
  LDA.b $44 : CMP.b #$80 : BEQ .no
  LDA.b $3C : CMP.b #$09 : BPL .no
  JSL Ganon_SetupActionHitbox  ; Link's sword -> pos1
  JSL Sprite_SetupHitBox       ; ball -> pos2
  JSL CheckIfHitBoxesOverlap : BCC .no
    INC.w SprMiscA, X
    LDA.b #$01 : STA.w SprMiscB, X
    JSR GanonBall_SpeedUp
    JSR GanonBall_AimAtGanondorf
    LDA.b #$05 : JSL SpriteSFX_QueueSFX2WithPan
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
    SEC
    RTS
  .no
  CLC
  RTS
}

GanonBall_SpeedUp:
{
  LDA.w SprMiscE, X : CLC : ADC.b #$04
  CMP.b #!Ganon_BallSpeedMax : BCC .store
    LDA.b #!Ganon_BallSpeedMax
  .store
  STA.w SprMiscE, X
  RTS
}

; X = ball. Its velocity has just been aimed toward Link. Freeze the parent's
; return direction here, rather than reusing a chase direction from before casting.
GanonBall_SetReturnFacing:
{
  LDA.w SprXSpeed, X : BPL .x_positive
    EOR.b #$FF : INC A
  .x_positive
  STA.b $00
  LDA.w SprYSpeed, X : BPL .y_positive
    EOR.b #$FF : INC A
  .y_positive
  CMP.b $00 : BCS .vertical
  LDA.w SprXSpeed, X : BMI .left
    LDA.b #$01
    BRA .set
  .left
    LDA.b #$02
    BRA .set
  .vertical
  LDA.w SprYSpeed, X : BMI .back
    LDA.b #$00
    BRA .set
  .back
    LDA.b #$03
  .set
  LDY.w SprMiscD, X
  STA.w SprMiscC, Y
  LDA.b #$01 : STA.w SprMiscB, Y
  LDA.b #$10 : STA.w SprTimerC, Y
  PHX
  TYX
  JSR Ganondorf_FreezeReturnPose
  JSR Ganondorf_SetVolleyPose
  PLX
  RTS
}

; Point the ball at Ganondorf's body center (x+8, y-height).
GanonBall_AimAtGanondorf:
{
  LDY.w SprMiscD, X
  LDA.w SprX, Y : CLC : ADC.b #$08 : STA.b $04
  LDA.w SprXH, Y : ADC.b #$00 : STA.b $05
  LDA.w SprY, Y : SEC : SBC.w SprHeight, Y : STA.b $06
  LDA.w SprYH, Y : SBC.b #$00 : STA.b $07
  LDA.w SprMiscE, X : JSL Sprite_ProjectSpeedTowardsEntityLong
  LDA.b $00 : STA.w SprYSpeed, X
  LDA.b $01 : STA.w SprXSpeed, X
  RTS
}

; =========================================================
; Shared OAM draw (pattern from Twinrova). Frame = SprFrame:
;   0 idle, 1 cast, 2 hurt, 3-4 ball, 5 release, 6-7 side, 8-9 rear,
;   10-11 cast with an overhead ball. Left reuses right with OAM H-flips.

Ganon_DrawFrame:
{
  JSL Sprite_PrepOamCoord
  ; Keep world coordinates, hitboxes and the ground shadow fixed during recoil.
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  SEP #$20
  JSR Ganon_ApplyReturnKick
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDY.w SprFrame, X
  LDA.w .start_index, Y : STA.b $06
  LDA.w SprFlash, X : STA.b $08

  PHX
  LDX.w .nbr_of_tiles, Y
  LDY.b #$00
  .next_tile
  PHX
  TXA : CLC : ADC.b $06
  PHA
  ASL A : TAX

  REP #$20
  LDA.b $00 : CLC : ADC.w .x_offsets, X : STA.b ($90), Y
  AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : CLC : ADC.w .y_offsets, X : STA.b ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y
    LDA.b #$F0 : STA.b ($90), Y
    STA.b $0E
  .on_screen_y

  PLX
  INY
  LDA.w .chr, X : STA.b ($90), Y
  INY
  LDA.w .properties, X : ORA.b $08 : STA.b ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.w .sizes, X : ORA.b $0F : STA.b ($92), Y
  PLY : INY

  PLX : DEX : BPL .next_tile

  PLX
  REP #$20
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$20
  RTS

  incsrc "ganondorf_frames.asm"
}

Ganon_ApplyReturnKick:
{
  LDA.w SprType, X : CMP.b #Sprite_Ganondorf : BNE .done
  LDA.w SprAction, X : CMP.b #$03 : BNE .done
  LDA.w SprMiscB, X : BEQ .done
  LDA.w SprTimerC, X : BEQ .done
  LDY.w SprMiscC, X
  CMP.b #$09 : BCC .follow
    TYA : CLC : ADC.b #$04 : TAY
  .follow
  TYA : ASL A : TAY
  REP #$20
  LDA.b $00 : CLC : ADC.w .x_offsets, Y : STA.b $00
  LDA.b $02 : CLC : ADC.w .y_offsets, Y : STA.b $02
  SEP #$20
  .done
  RTS

  .x_offsets : dw 0, 2, -2, 0, 0, -2, 2, 0
  .y_offsets : dw 2, 0, 0, -2, -2, 0, 0, 2
}

; =========================================================
; Room tag $3D gate. Reached from maple.asm's DreamReturn_GanonDoorGate when
; the vanilla tag would open the Triforce door (every enemy dead).
; Carry set = keep the door shut.

Ganondorf_DoorGate:
{
  LDA.b $A0 : ORA.b $A1 : BNE .open
  LDA.l GanondorfFight : CMP.b #$02 : BEQ .open
  ; Kydreeok must have died first (kydreeok.asm sets FinaleBeat), then the placeholder beat runs out.
  LDA.w FinaleBeat : BEQ .shut
    PHX : PHY
    LDX.b #$0F
    .scan ; a live Ganondorf (fight = 1) means wait; a stale fight = 1 with none respawns him
      LDA.w SprState, X : BEQ .next
      LDA.w SprType, X : CMP.b #Sprite_Ganondorf : BEQ .wait
      .next
      DEX : BPL .scan
    LDA.w FinaleBeat : CMP.b #$01 : BEQ .go
      DEC.w FinaleBeat
      BRA .wait
    .go
    LDX.b #$00 ; spawn copies slot 0's position; overwritten below
    LDA.b #Sprite_Ganondorf : JSL Sprite_SpawnDynamically : BMI .full
      TYX
      LDA.b #$70 : STA.w SprX, X
      LDA.b $23 : STA.w SprXH, X ; Link's room quadrant
      LDA.b #$80 : STA.w SprY, X
      LDA.b $21 : STA.w SprYH, X
      LDA.b $EE : STA.w SprFloor, X
      JSL Sprite_Ganondorf_Prep
      LDA.b #$01 : STA.l GanondorfFight
    .full
    .wait
    PLY : PLX
    .shut
    SEC
    RTL
  .open
  CLC
  RTL
}

if !ENABLE_DREAM_RETURN == 0
  ; maple.asm owns this hook when the dream return is on.
  RoomTag_GanonDoor_Exit_Ganondorf = $01C7A1
  pushpc
  org $01C77F ; @hook module=Sprites name=Ganondorf_DoorGate kind=jsl target=Ganondorf_DoorGate expected_m=8 expected_x=8
    JSL Ganondorf_DoorGate
    BCS RoomTag_GanonDoor_Exit_Ganondorf
    assert pc() == $01C785
  pullpc
endif

; =========================================================
; Fairy revive hook. GameOver_ResituateLink ($09F742) is the last step of the fairy path
; (it hands Module12 back to the previous module); the room is not reloaded and sprites keep
; their state. Replaces `LDA.b #$90 : STA.w $031F` (A9 90 8D 1F 03 in the base ROM).
; Room $00 only: Kydreeok and Ganondorf see BossReinject on their next frame.

BossReinject_Set:
{
  LDA.b #$90 : STA.w $031F ; original
  LDA.b $A0 : ORA.b $A1 : BNE .not_finale_room
    LDA.b #$01 : STA.w BossReinject
  .not_finale_room
  RTL
}

pushpc
org $09F773 ; @hook module=Sprites name=BossReinject_Set kind=jsl target=BossReinject_Set expected_m=8 expected_x=8
  JSL BossReinject_Set : NOP
  assert pc() == $09F778
pullpc

; =========================================================
; Graphics -> second OBJ name table (VRAM $5000), like Twinrova.

ApplyGanondorfGraphics:
{
  PHX
  REP #$20
  LDX.b #$80 : STX.w $2100
  LDX.b #$80 : STX.w $2115
  LDA.w #$5000 : STA.w $2116
  LDA.w #$1801 : STA.w $4300
  LDA.w #GanondorfGraphics : STA.w $4302
  LDX.b #GanondorfGraphics>>16 : STX.w $4304
  LDA.w #$1800 : STA.w $4305
  LDX.b #$01 : STX.w $420B
  ; Kydreeok replaced both OBJ pages. Restore vanilla falling-floor sheet $33
  ; in the upper slot before the native falling-tile garnishes need it.
  LDA.w #$5C00 : STA.w $2116
  LDA.w #GanondorfFloorGraphics : STA.w $4302
  LDX.b #GanondorfFloorGraphics>>16 : STX.w $4304
  LDA.w #$0800 : STA.w $4305
  LDX.b #$01 : STX.w $420B
  LDX.b #$0F : STX.w $2100
  SEP #$30
  PLX
  RTL
}

; OBJ palette 6, colors 1-15. Palette 4 belongs to the vanilla shadows.
; Update both live and fade-target buffers;
; NMI performs the CGRAM upload. Color 0 remains transparent.
ApplyGanondorfPalette:
{
  PHP : REP #$30 : PHX
  LDX.w #$001C
  .color
    LDA.l GanondorfPalette+2, X
    STA.l $7EC6C2, X
    STA.l $7EC4C2, X
    DEX : DEX : BPL .color
  SEP #$20
  LDA.b #$01 : STA.b $15
  PLX : PLP
  RTL
}

GanondorfPalette:
  incbin ganondorf.pal

GanondorfGraphics:
  incbin ganondorf.bin

GanondorfFloorGraphics:
  incbin ganondorf_floor.bin

print "End of Ganondorf (bank $2A)        ", pc
assert pc() <= $2B0000, "Ganondorf code left bank $2A"
pullpc
