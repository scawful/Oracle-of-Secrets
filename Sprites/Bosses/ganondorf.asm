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
;   the last return hits him -> stunned -> 3 sword hits -> he teleports
;   9 sword hits in total -> he dies -> GanondorfFight = 2 -> door opens
;
; Original 32x40 art with trimmed cape edges, shared 16x16 tiles, one $1000 sheet.
; Source art and generated OAM tables: Data/graphics/ganondorf/ and
; Scripts/Generate/build_ganondorf_art.py.
; Lives in free bank $2A, so it costs no bank $30-$32 bytes.
; =========================================================

Ganon_SetupActionHitbox = $06F57E ; SetupActionHitbox_long (Link's weapon box -> pos1)

!Ganon_HitsPerStun  = 3
!Ganon_TotalHits    = 9
!Ganon_BallSpeed    = $18
!Ganon_BallSpeedMax = $30
!Ganon_GlideSpeed   = $08

!Ganon_FrameIdle     = 0
!Ganon_FrameCast     = 1
!Ganon_FrameHurt     = 2
!Ganon_FrameRelease  = 5
!Ganon_FrameRight    = 6
!Ganon_FrameLeft     = 7
!Ganon_FrameBackA    = 8
!Ganon_FrameChargeA  = 10

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
  STZ.w SprMiscE, X
  STZ.w SprMiscC, X ; chase facing: 0 front, 1 right, 2 left, 3 back
  LDA.b #$40 : STA.w SprTimerA, X
  JSL ApplyGanondorfGraphics
  JSL ApplyGanondorfPalette
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
                   Ganondorf_Teleport,
                   Ganondorf_Dead)

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

  ; 1: hover, then cast
  Ganondorf_Float:
  {
    JSR Ganondorf_Bob
    JSR Ganondorf_Chase
    JSL Sprite_CheckDamageToPlayer
    LDA.w SprTimerA, X : BNE .wait
      %GotoAction(2)
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.b #!Ganon_FrameChargeA : STA.w SprFrame, X
      LDA.b #$20 : STA.w SprTimerA, X
    .wait
    RTS
  }

  ; 2: front-facing charge (24 ticks), then compact release (8 ticks).
  ; The held ball is one OAM piece, not an active/damaging child sprite.
  Ganondorf_Cast:
  {
    JSR Ganondorf_Bob
    LDA.w SprTimerA, X : CMP.b #$09 : BCC .release
      LDA.b $1A : LSR #3 : AND.b #$01
      CLC : ADC.b #!Ganon_FrameChargeA : STA.w SprFrame, X
      RTS
    .release
    JSR Ganondorf_SpawnBall
    LDA.b #!Ganon_FrameRelease : STA.w SprFrame, X
    ; Enter rally immediately so a close reflection can already stun him.
    %GotoAction(3)
    LDA.b #$08 : STA.w SprTimerC, X
    RTS
  }

  ; 3: rally in progress; the ball moves us to Stunned when it lands
  Ganondorf_WaitBall:
  {
    JSR Ganondorf_Bob
    JSL Sprite_CheckDamageToPlayer
    ; Swing pose for a moment after each return (SprTimerC set by the ball)
    LDA.w SprTimerC, X : BEQ .pose
      LDA.b #!Ganon_FrameRelease
    .pose
    STA.w SprFrame, X

    LDY.w SprMiscD, X : BMI .ball_gone
    LDA.w SprState, Y : BEQ .ball_gone
    LDA.w SprType, Y : CMP.b #Sprite_GanonBall : BNE .ball_gone
      RTS
    .ball_gone
    LDA.b #$FF : STA.w SprMiscD, X
    %GotoAction(1)
    LDA.b #$40 : STA.w SprTimerA, X
    RTS
  }

  ; 4: grounded and vulnerable to the sword
  Ganondorf_Stunned:
  {
    LDA.b #$02 : STA.w SprFrame, X
    STZ.w SprHeight, X
    JSL Sprite_CheckDamageFromPlayer : BCC .no_hit
      DEC.w SprMiscF, X : BEQ .die
      DEC.w SprMiscA, X : BEQ .teleport
    .no_hit
    LDA.w SprTimerA, X : BNE .exit
    .teleport
    JSR Ganondorf_StartTeleport
    .exit
    RTS

    .die
    %GotoAction(6)
    LDA.b #$80 : STA.w SprTimerA, X
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
    JSL Sprite_KillFriends
    RTS
  }

  ; 5: vanish and reappear somewhere else
  Ganondorf_Teleport:
  {
    LDA.w SprTimerA, X : CMP.b #$18 : BNE .no_move
      JSL GetRandomInt : AND.b #$03 : TAY
      LDA.w .pos_x_lo, Y : STA.w SprX, X
      LDA.b $23 : STA.w SprXH, X ; same room quadrant as Link
      LDA.w .pos_y_lo, Y : STA.w SprY, X
      LDA.b $21 : STA.w SprYH, X
    .no_move
    LDA.w SprTimerA, X : BNE .exit
      LDA.b #$10 : STA.w SprHeight, X
      %GotoAction(1)
      LDA.b #$40 : STA.w SprTimerA, X
    .exit
    RTS

    ; Room $00 north arena (absolute coords; room $00 starts at $0000,$0000)
    .pos_x_lo : db $70, $48, $98, $70
    .pos_y_lo : db $78, $90, $90, $A8
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

Ganondorf_StartTeleport:
{
  %GotoAction(5)
  LDA.b #$30 : STA.w SprTimerA, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  STZ.w SprFrame, X
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

; Slow chase only between volleys. Choose a pose from the actual velocity;
; the cast always faces front and projectile aim remains independent.
Ganondorf_Chase:
{
  LDA.b #!Ganon_GlideSpeed : JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_Move

  LDA.w SprXSpeed, X : BPL .x_positive
    EOR.b #$FF : INC A
  .x_positive
  STA.b $00
  LDA.w SprYSpeed, X : BPL .y_positive
    EOR.b #$FF : INC A
  .y_positive
  CMP.b $00 : BCS .vertical

  LDA.w SprXSpeed, X : BMI .left
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #!Ganon_FrameRight : STA.w SprFrame, X
    RTS
  .left
    LDA.b #$02 : STA.w SprMiscC, X
    LDA.b #!Ganon_FrameLeft : STA.w SprFrame, X
    RTS
  .vertical
  LDA.w SprYSpeed, X : BMI .back
    STZ.w SprMiscC, X
    STZ.w SprFrame, X
    RTS
  .back
    LDA.b #$03 : STA.w SprMiscC, X
    LDA.b $1A : LSR #3 : AND.b #$01
    CLC : ADC.b #!Ganon_FrameBackA : STA.w SprFrame, X
    RTS
}

Ganondorf_SpawnBall:
{
  LDA.b #Sprite_GanonBall : JSL Sprite_SpawnDynamically : BMI .no_slot
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
    LDA.b #!Ganon_BallSpeed : STA.w SprMiscE, Y
    TXA : STA.w SprMiscD, Y ; parent slot
    JSL GetRandomInt : AND.b #$03 : BNE .returns
      INC A
    .returns
    STA.w SprMiscC, Y   ; Ganondorf's returns left (1-3)
    TYA : STA.w SprMiscD, X
    PHX
    TYX
    LDA.b #!Ganon_BallSpeed : JSL Sprite_ApplySpeedTowardsPlayer
    PLX
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
    RTS
  .no_slot
  LDA.b #$FF : STA.w SprMiscD, X
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

  .flicker : db 1, 0, 0, 0, 0, 1, 1
}

; =========================================================
; Energy ball ($46)

!SPRID              = Sprite_GanonBall
!NbrTiles           = 01
!Harmless           = 00
!HVelocity          = 01
!Health             = 00
!Damage             = 02
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
  LDA.b $1A : LSR #3 : AND.b #$01 : CLC : ADC.b #$03 : STA.w SprFrame, X
  JSR Ganon_DrawFrame
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

GanonBall_Main:
{
  ; The parent must still be Ganondorf
  LDY.w SprMiscD, X
  LDA.w SprState, Y : BEQ .kill_now
  LDA.w SprType, Y : CMP.b #Sprite_Ganondorf : BNE .kill_now

  LDA.w SprMiscB, X : BNE .to_ganondorf

  ; Heading to Link
  JSL Sprite_Move
  JSL Sprite_CheckTileCollision : BNE .kill_now
  JSR GanonBall_CheckSwordReflect : BCS .exit
  JSL Sprite_CheckDamageToPlayer : BCC .exit
  .kill_now
  STZ.w SprState, X
  .exit
  RTS

  .to_ganondorf
  JSR GanonBall_AimAtGanondorf
  JSL Sprite_Move
  JSL Sprite_SetupHitBox_Alt    ; ball -> pos1
  PHX
  LDA.w SprMiscD, X : TAX
  JSL Sprite_SetupHitBox        ; Ganondorf -> pos2
  PLX
  JSL CheckIfHitBoxesOverlap : BCC .exit

  LDY.w SprMiscD, X
  LDA.w SprMiscC, X : BEQ .stun_ganondorf
    ; Ganondorf sends it back, faster
    DEC.w SprMiscC, X
    STZ.w SprMiscB, X
    JSR GanonBall_SpeedUp
    LDA.w SprMiscE, X : JSL Sprite_ApplySpeedTowardsPlayer
    LDY.w SprMiscD, X
    LDA.b #$10 : STA.w SprTimerC, Y
    LDA.b #$05 : JSL SpriteSFX_QueueSFX2WithPan
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
    RTS

  .stun_ganondorf
  LDA.w SprAction, Y : CMP.b #$03 : BNE .kill
    LDA.b #$04 : STA.w SprAction, Y
    LDA.b #$A0 : STA.w SprTimerA, Y
    LDA.b #!Ganon_HitsPerStun : STA.w SprMiscA, Y
    LDA.b #$02 : STA.w SprFrame, Y
    LDA.b #$00 : STA.w SprHeight, Y
    LDA.w SprGfxProps, Y : AND.b #$BF : STA.w SprGfxProps, Y
    LDA.b #$FF : STA.w SprMiscD, Y
    LDA.b #$09 : JSL SpriteSFX_QueueSFX3WithPan
  .kill
  STZ.w SprState, X
  RTS
}

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
  RTS

  incsrc "ganondorf_frames.asm"
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
  LDA.w #$1000 : STA.w $4305
  LDX.b #$01 : STX.w $420B
  LDX.b #$0F : STX.w $2100
  SEP #$30
  PLX
  RTL
}

; OBJ palette 4, colors 1-15. Update both live and fade-target buffers;
; NMI performs the CGRAM upload. Color 0 remains transparent.
ApplyGanondorfPalette:
{
  PHP : REP #$30 : PHX
  LDX.w #$001C
  .color
    LDA.l GanondorfPalette+2, X
    STA.l $7EC682, X
    STA.l $7EC482, X
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

print "End of Ganondorf (bank $2A)        ", pc
assert pc() <= $2B0000, "Ganondorf code left bank $2A"
pullpc
