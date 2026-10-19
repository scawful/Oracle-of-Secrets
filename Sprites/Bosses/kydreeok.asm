; =========================================================
; Kydreeok: final boss body ($7A), the fight director.
;
; The body is BG2 (moved through $0422/$0424 by MoveBody); the wings and
; legs are 8 OAM entries in region E; a ground shadow uses 3 region A
; entries while it flies. Two heads ($CF, kydreeok_head.asm) ride on
; necks from its shoulders.
;
; Frame budget: the body runs after the heads and calls BossKit_FrameEnd
; last (Sprites/Bosses/boss_kit.asm). New turns (BossDirector_Ready) and
; head regrowth ask BossKit_CanSpend first.
;
; Flight: crouch -> take off to !Kydreeok_CruiseAltitude -> glide after
; the player -> hover while the shadow flashes -> dive and land with an
; earthquake. SprHeight is the altitude; Kydreeok_SetAltitude raises the
; BG2 body with it, and Sprite_PrepOamCoord raises the wings, legs and
; head anchors.
;
; Pacing (scawful 2026-10-19, decisions.org "Kydreeok fight: three
; stages"): the body is the BossDirector (boss_director.asm). One head or
; the body holds the attack token; every attack has a telegraph, a punish
; window and a per-head cooldown, and a rest follows each turn.
;   Stage 1 Bite: two heads take turns biting; a bitten head lies stuck.
;   Stage 2 Fire: one head left; fire breath, then it pants out of sword
;     reach until a shot knocks it down. The body steps between 3 spots.
;   Stage 3 Sky: the dragon form, both heads regrow. Head turns, then a
;     flight and dive that slams both heads to the floor. A dead head
;     regrows after 20 s, with a rumble for the last 4 s.
; The turn code is in bank $3A at the end of this file.
; =========================================================

!SPRID              = Sprite_Kydreeok
!NbrTiles           = 02  ; Region A entries - 1: the 3-tile ground shadow
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = $07 ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 01  ; 00 = normal sprite, 01 = sprite is a boss

!Kydreeok_CruiseAltitude = 32

; Body actions (Sprite_Kydreeok_Main order).
!Kyd_Stand  = $01
!Kyd_Walk   = $02
!Kyd_Roar   = $03
!Kyd_Dead   = $05
!Kyd_Crouch = $06
!Kyd_Glide  = $08

; Head actions (Sprite_KydreeokHead_Main order, kydreeok_head.asm).
!KydHead_Rise    = $00
!KydHead_Idle    = $01
!KydHead_Bite    = $02 ; rear back, shake: the bite telegraph
!KydHead_Strike  = $03
!KydHead_Breath  = $04 ; rise, glow: the breath telegraph
!KydHead_Fire    = $05
!KydHead_Recover = $06 ; Recover..Stunned are harmless to touch
!KydHead_Stuck   = $07
!KydHead_Pant    = $08
!KydHead_Stunned = $09
!KydHead_Spit    = $0A ; glow: the fireball telegraph

; Turn codes in the stage patterns. 0-2 are head attacks; their cooldown
; id is code * 2 + head subtype (0 = left, 1 = right).
!KydTurn_Bite   = 0
!KydTurn_Breath = 1
!KydTurn_Spit   = 2
!KydTurn_Move   = 3
!KydTurn_Fly    = 4

; Kydreeok_Knob: A = knob, out A = its value in the current stage.
; Knobs 0-2 are the telegraphs of turn codes 0-2.
!KydKnob_Stuck = 3
!KydKnob_Pant  = 4
!KydKnob_Stun  = 5
!KydKnob_Rest  = 6
!KydKnob_Cool  = 7

; Orders from Kydreeok_TakeTurn to the standing body.
!KydOrder_None = 0
!KydOrder_Walk = 1
!KydOrder_Fly  = 2
!KydOrder_Roar = 3

!Kyd_CrouchTime = 40 ; flight telegraph
!Kyd_DiveWarn   = 40 ; last glide frames: hover, the shadow flashes
!Kyd_SlamTime   = 75 ; heads stuck on the floor after a dive
!Kyd_WalkSpeed  = 16 ; 1 px a frame

; BossDir_Var bytes (boss_director.asm).
Kydreeok_NextHead = BossDir_Var+0 ; subtype of the head whose turn is next
Kydreeok_Spot     = BossDir_Var+1 ; stage 2 spot, 0-3 (home, right, home, left)
Kydreeok_Flags    = BossDir_Var+2 ; bit 0: walk to the spot first; bit 1: combo follow-up next
Kydreeok_Regrow   = BossDir_Var+3 ; stage 3 regrow timer in 8-frame steps, 0 = off
Kydreeok_HomeX    = BossDir_Var+4 ; word: the spawn spot
Kydreeok_HomeY    = BossDir_Var+6 ; word

%Set_Sprite_Properties(Sprite_Kydreeok_Prep, Sprite_Kydreeok_Long)

Sprite_Kydreeok_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Kydreeok_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Kydreeok_Main
    JSR Sprite_Kydreeok_CheckIfDead
    ; Stage 3: a lost head grows back on a fixed timer.
    JSL Kydreeok_RegrowTick : BCC .no_regrow
      JSR Kydreeok_SpawnHead
    .no_regrow
    JSL BossDirector_Tick
    ; Last boss work this frame: sample the load, run the earthquake.
    JSL BossKit_FrameEnd
  .SpriteIsNotActive
  LDA.w SprState, X : BNE .not_inactive
    JSR ApplyEndPalette
  .not_inactive
  PLB
  RTL
}

Sprite_Kydreeok_Prep:
{
  PHB : PHK : PLB
  if !ENABLE_DREAM_RETURN == 1
    ; Power dream stage (maple.asm): no boss, heads or final-boss music while
    ; a pendant dream runs.
    JSL DreamReturn_IsDreaming : BCC .not_dreaming
      STZ.w SprState, X
      PLB
      RTL
    .not_dreaming
  endif
  JSL BossKit_Reset
  JSL BossDirector_Reset
  ; The heads read the body from their first frame.
  TXA : STA.w Kydreeok_Id
  LDA.b #$40 : STA.w SprTimerA, X
  LDA.b #$08 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move
  LDA.b #$09 : STA.w SprBump,   X ; bump damage type
  STZ.w SprHeight, X

  ; Home: the body walks back here after each landing and stage change.
  ; (MoveBody overwrites SprMiscB, so it lives in director RAM.)
  LDA.w SprX,  X : STA.l Kydreeok_HomeX
  LDA.w SprXH, X : STA.l Kydreeok_HomeX+1
  LDA.w SprY,  X : STA.l Kydreeok_HomeY
  LDA.w SprYH, X : STA.l Kydreeok_HomeY+1

  ; Intro: the room shakes while both heads grow out of the shoulders.
  LDA.b #$20 : STA.l BossKit_Quake
  LDA.b #$35 : JSL Sound_SetSfx2PanLong
  LDA.b #$00 : JSR Kydreeok_SpawnHead
  LDA.b #$01 : JSR Kydreeok_SpawnHead

  JSR ApplyPalette

  ; Final Boss theme 1F
  LDA #$1F : STA $012C

  PLB
  RTL
}

; Y = a head slot. Carry set while it holds a live Kydreeok head. A dead
; head's slot can be reused by a fireball or an explosion.
Kydreeok_HeadAlive:
{
  LDA.w SprState, Y : BEQ .no
  LDA.w SprType, Y : CMP.b #Sprite_KydreeokHead : BNE .no
    SEC
    RTS
  .no
  CLC
  RTS
}

; A = subtype (0 = left, 1 = right). Spawns a head on its shoulder;
; its Prep starts the rise.
Kydreeok_SpawnHead:
{
  PHA
  LDA.b #Sprite_KydreeokHead
  JSL Sprite_SpawnDynamically : BPL .spawned
    PLA
    RTS
  .spawned
  PLA : STA.w SprSubtype, Y : BNE .right
    TYA : STA.w Offspring1_Id
    BRA .place
  .right
    TYA : STA.w Offspring2_Id
  .place
  PHX
  TYX
  JSR KydreeokHead_Anchor
  LDA.b $04 : STA.w SprX, X
  LDA.b $05 : STA.w SprXH, X
  LDA.b $06 : STA.w SprY, X
  LDA.b $07 : STA.w SprYH, X
  STZ.w SprYRound, X
  STZ.w SprXRound, X
  JSL Sprite_KydreeokHead_Prep ; Sprite_SpawnDynamically skips Prep: HP, SprBump
  PLX
  RTS
}

Sprite_Kydreeok_CheckIfDead:
{
  ; Already dying: Kydreeok_Dead owns SprTimerA.
  LDA.w SprAction, X : CMP.b #$05 : BEQ .not_dead
  LDY.w Offspring1_Id : JSR Kydreeok_HeadAlive : BCS .not_dead
  LDY.w Offspring2_Id : JSR Kydreeok_HeadAlive : BCS .not_dead

  LDA.w SprMiscD, X : CMP.b #$02 : BEQ .dead
    ; Phase two: new graphics, a faster body, both heads grow back.
    LDA.b #$02 : STA.w SprMiscD, X
    LDA.b #$0A : STA $36
    LDY.b #$01 : JSR ApplyKydreeokGraphics
    LDA.b #$20 : STA.l BossKit_Quake
    LDA.b #$35 : JSL Sound_SetSfx2PanLong
    LDA.b #$00 : JSR Kydreeok_SpawnHead
    LDA.b #$01 : JSR Kydreeok_SpawnHead
    RTS
  .dead
    LDA.b #$60 : STA.w SprTimerA, X
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$05 : STA.w SprAction, X
    LDA.b #$13 : STA $012C
  .not_dead
  RTS
}

; A = new altitude. Raises or lowers the BG2 body by the change; the OAM
; parts and the head anchors follow SprHeight.
; Out: A = altitude, Z set on the ground.
Kydreeok_SetAltitude:
{
  STA.b $00
  SEC : SBC.w SprHeight, X
  REP #$20
  %BossKit_Sext16()
  CLC : ADC.w $0424 : STA.w $0424
  SEP #$20
  LDA.b $00 : STA.w SprHeight, X
  RTS
}

Sprite_Kydreeok_Main:
{
  %SpriteJumpTable(Kydreeok_Start,
                  Kydreeok_Stand,
                  Kydreeok_Walk,
                  Kydreeok_Roar,
                  Kydreeok_Stand,
                  Kydreeok_Dead,
                  Kydreeok_Crouch,
                  Kydreeok_TakeOff,
                  Kydreeok_Glide,
                  Kydreeok_Dive)

  ; -------------------------------------------------------
  ; 0x00
  Kydreeok_Start:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA.w SprMiscD, X : BNE .go
      LDY #$00
      JSR ApplyKydreeokGraphics
      JSR ApplyPalette
      LDA.b #$01 : STA.w SprMiscD, X
    .go

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA,            X : BNE .continue
      LDA #$40 : STA.w SprTimerA, X
      %GotoAction(1)
    .continue

    RTS
  }

  ; -------------------------------------------------------
  ; 0x01 - stand still and ask the director for the next order
  ; (Kydreeok_TakeTurn). Head attacks start from there too.
  Kydreeok_Stand:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    STZ.w SprYSpeed, X : STZ.w SprXSpeed, X
    JSL MoveBody
    JSR StopIfOutOfBounds

    LDA.w SprTimerA, X : BNE .wait
    JSL Kydreeok_TakeTurn : BEQ .wait
    DEC A : BNE .not_walk
      LDA.b #$A0 : STA.w SprTimerA, X ; give up on a blocked spot
      %GotoAction(!Kyd_Walk)
      RTS
    .not_walk
    DEC A : BNE .roar
      LDA.b #!Kyd_CrouchTime : STA.w SprTimerA, X
      %GotoAction(!Kyd_Crouch)
      RTS
    .roar
      LDA.b #$3C : STA.w SprTimerA, X
      %GotoAction(!Kyd_Roar)
    .wait
    RTS
  }

  ; -------------------------------------------------------
  ; 0x02 - walk 1 px a frame to the stage spot (Kydreeok_WalkStep)
  Kydreeok_Walk:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    JSL Kydreeok_WalkStep : BCS .arrived
    LDA.w SprTimerA, X : BEQ .arrived
      JSR StopIfOutOfBounds
      JSL MoveBody
      JSL Sprite_CheckDamageFromPlayer
      JSL Sprite_CheckDamageToPlayer
      RTS
    .arrived
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.l Kydreeok_Flags : AND.b #$FE : STA.l Kydreeok_Flags
    LDA.b #$10 : STA.w SprTimerA, X
    %GotoAction(!Kyd_Stand)
    RTS
  }

  ; -------------------------------------------------------
  ; 0x03 - stage change: beat the wings while the room shakes
  Kydreeok_Roar:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 04)

    LDA.w SprTimerA, X : BNE .roaring
      %GotoAction(!Kyd_Stand)
    .roaring
    RTS
  }

  ; -------------------------------------------------------
  ; 0x05
  Kydreeok_Dead:
  {
    LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)
    ; Flicker the body every other frame using the timer
    LDA.w SprTimerA, X : AND.b #$01 : BEQ .flicker
      LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)
    .flicker

    ; Killed in the air: sink back to the ground.
    LDA.w SprHeight, X : BEQ .grounded
      SEC : SBC.b #$02 : BPL .sinking
        LDA.b #$00
      .sinking
      JSR Kydreeok_SetAltitude
    .grounded

    ; One explosion every 8 frames somewhere on the body.
    LDA.w SprTimerA, X : AND.b #$07 : BNE .no_space
    LDA.b #$00
    JSL Sprite_SpawnDynamically : BMI .no_space
      LDA.b #$0B : STA.w $0AAA
      LDA.b #$04 : STA.w SprState,Y
      LDA.b #$03 : STA.w SprNbrOAM,Y
      LDA.b #$0C : STA.w SprProps,Y
      JSL GetRandomInt : AND.b #$3F : SEC : SBC.b #$20 : STA.b $00
      JSL GetRandomInt : AND.b #$1F : SEC : SBC.b #$28 : STA.b $01
      LDA.b $00
      REP #$20
      %BossKit_Sext16()
      CLC : ADC.w SprCachedX
      SEP #$20
      STA.w SprX,Y : XBA : STA.w SprXH,Y
      LDA.b $01
      REP #$20
      %BossKit_Sext16()
      CLC : ADC.w SprCachedY
      SEP #$20
      STA.w SprY,Y : XBA : STA.w SprYH,Y
      LDA.b #$1F : STA.w SprTimerA,Y : STA.w $0D90,Y
      LDA.b #$02 : STA.w $0F20,Y
      LDA.b #$0C : JSL Sound_SetSfx2PanLong
    .no_space
    LDA.w SprTimerA, X : BNE .continue
      STZ.w $0422
      STZ.w $0424
      LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)
      LDA.b #$00 : STA.l BossKit_Quake
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      STZ.w SprState, X ; GG
    .continue
    RTS
  }

  ; -------------------------------------------------------
  ; 0x06 - crouch with the wings down before take-off
  Kydreeok_Crouch:
  {
    LDA.b #$02 : STA.w SprFrame, X
    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    LDA.w SprTimerA, X : BNE .crouching
      %GotoAction(7)
    .crouching
    RTS
  }

  ; -------------------------------------------------------
  ; 0x07 - beat the wings and climb 2 px a frame
  Kydreeok_TakeOff:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 04)
    JSL MoveBody

    LDA.w SprHeight, X : CLC : ADC.b #$02
    JSR Kydreeok_SetAltitude
    CMP.b #!Kydreeok_CruiseAltitude : BCC .climbing
      LDA.b #$80 : STA.w SprTimerA, X
      LDA $36 : CLC : ADC.b #$04
      JSL Sprite_ApplySpeedTowardsPlayer
      %GotoAction(8)
    .climbing
    RTS
  }

  ; -------------------------------------------------------
  ; 0x08 - glide after the player, re-aiming every 32 frames, then hover
  ; for !Kyd_DiveWarn frames while the shadow flashes: the dive lands
  ; there. No body contact in the air; the heads wait (the body holds
  ; the token).
  Kydreeok_Glide:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 08)

    LDA.w SprTimerA, X : CMP.b #!Kyd_DiveWarn : BCS .chase
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      BRA .no_aim
    .chase
    LDA.b $1A : AND.b #$1F : BNE .no_aim
      LDA $36 : CLC : ADC.b #$04
      JSL Sprite_ApplySpeedTowardsPlayer
    .no_aim
    JSR StopIfOutOfBounds
    JSL MoveBody

    ; Bob 2 px around the cruise altitude.
    LDA.b $1A : LSR A : LSR A : LSR A : AND.b #$07 : TAY
    LDA.w .bob, Y : CLC : ADC.b #!Kydreeok_CruiseAltitude
    JSR Kydreeok_SetAltitude

    LDA.w SprTimerA, X : BNE .gliding
      %GotoAction(9)
    .gliding
    RTS

    .bob
      db 0, 1, 2, 1, 0, -1, -2, -1
  }

  ; -------------------------------------------------------
  ; 0x09 - fold the wings and drop 4 px a frame; the landing shakes
  ; the room, then the body stands while the heads lie stuck, and walks
  ; home.
  Kydreeok_Dive:
  {
    LDA.b #$02 : STA.w SprFrame, X
    JSR StopIfOutOfBounds
    JSL MoveBody

    LDA.w SprHeight, X : SEC : SBC.b #$04 : BPL .falling
      LDA.b #$00
    .falling
    JSR Kydreeok_SetAltitude : BNE .airborne
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      LDA.b #$18 : STA.l BossKit_Quake
      LDA.b #$0C : JSL Sound_SetSfx2PanLong
      JSL Sprite_CheckDamageToPlayer
      ; Both heads slam onto the floor: the sword window.
      JSL Kydreeok_Landed
      LDA.b #!Kyd_SlamTime : STA.w SprTimerA, X
      %GotoAction(!Kyd_Stand)
    .airborne
    RTS
  }

}

; =========================================================
; Originally from Trinexx_MoveBody $1DB2E5
; Also used by Manhandla (manhandla.asm).

MoveBody:
{
  ; Handle the shell bg movement
  ; Trinexx_MoveBody
  LDA.w SprX, X : PHA
  LDA.w SprY, X : PHA

  JSL Sprite_Move

  PLA
  LDY.b #$00 : SEC : SBC.w SprY, X : STA.w $0310
  BPL .pos_y_low
  DEY

  .pos_y_low
  STY.w $0311

  ; -----------------------------------------------------

  PLA
  LDY.b #$00 : SEC : SBC.w SprX, X : STA.w $0312
  BPL .pos_x_low

  DEY

  .pos_x_low
  STY.w $0313

  ; -----------------------------------------------------

  LDA.b #$01 : STA.w $0428

  LDA.w SprY, X : SEC : SBC.b #$0C : STA.w SprMiscB, X

  LDA.w $0B08 : SEC : SBC.w SprX, X
                CLC : ADC.b #$02
                CMP.b #$04 : BCS .not_at_target

  LDA.w $0B09 : SEC : SBC.w SprY, X
                CLC : ADC.b #$02
                CMP.b #$04 : BCS .not_at_target

  .adjust_phase ; Unused?
  LDA.b #$30 : STA.w SprTimerA, X

  .not_at_target
  ; LayerEffect_Trinexx $0AFEF0
  REP   #$20
  LDA.w $0422 : CLC : ADC.w $0312 : STA.w $0422
  LDA.w $0424 : CLC : ADC.w $0310 : STA.w $0424
  STZ.w $0312 : STZ.w $0310
  SEP   #$20

  RTL
}

; =========================================================

; Keep the body inside the arena: drop the speed that would carry it past
; an edge; at the bottom edge turn it back up.
StopIfOutOfBounds:
{
  REP #$20
  LDA.w SprCachedX : CMP.w #$0118
  SEP #$20
  BCS .not_left
    LDA.w SprXSpeed, X : BPL .not_left
      STZ.w SprXSpeed, X : STZ.w SprXRound, X
  .not_left

  REP #$20
  LDA.w SprCachedX : CMP.w #$01D8
  SEP #$20
  BCC .not_right
    LDA.w SprXSpeed, X : BMI .not_right
      STZ.w SprXSpeed, X : STZ.w SprXRound, X
  .not_right

  REP #$20
  LDA.w SprCachedY : CMP.w #$0060 ; the raised heads stay on screen
  SEP #$20
  BCS .not_up
    LDA.w SprYSpeed, X : BPL .not_up
      STZ.w SprYSpeed, X : STZ.w SprYRound, X
  .not_up

  REP #$20
  LDA.w SprCachedY : CMP.w #$00D0
  SEP #$20
  BCC .not_down
    LDA.w SprYSpeed, X : BMI .not_down
      LDA.b #-10 : STA.w SprYSpeed, X
      STZ.w SprYRound, X
  .not_down
  RTS
}

; =========================================================

ApplyPalette:
{
  REP #$20 ;Set A in 16bit mode

  ;note, this uses adresses like 7EC300 and not 7EC500 because the game
  ;will fade the colors into 7EC500 based on the colors found in 7EC300

  LDA #$7FFF : STA $7EC5E2 ;BG2
  LDA #$319B : STA $7EC5E4
  LDA #$15B6 : STA $7EC5E6
  LDA #$369E : STA $7EC5E8
  LDA #$14A5 : STA $7EC5EA
  LDA #$7E56 : STA $7EC5EC
  LDA #$65CA : STA $7EC5EE
  ; LDA #$14A5 : STA $7EC5F0
  ; LDA #$7E56 : STA $7EC5F2
  ; LDA #$65CA : STA $7EC5F4

  INC $15

  SEP #$20 ;Set A in 8bit mode

  RTS
}

ApplyEndPalette:
{
  REP #$20 ;Set A in 16bit mode

  ;note, this uses adresses like 7EC300 and not 7EC500 because the game
  ;will fade the colors into 7EC500 based on the colors found in 7EC300

  LDA #$1084 : STA $7EC5E2 ;BG2
  LDA #$210D : STA $7EC5E4
  LDA #$3191 : STA $7EC5E6
  LDA #$4E78 : STA $7EC5E8
  LDA #$14A5 : STA $7EC5EA
  LDA #$7E56 : STA $7EC5EC
  LDA #$65CA : STA $7EC5EE
  ; LDA #$14A5 : STA $7EC5F0
  ; LDA #$7E56 : STA $7EC5F2
  ; LDA #$65CA : STA $7EC5F4

  INC $15

  SEP #$20 ;Set A in 8bit mode

  RTS
}

; =========================================================

Sprite_Kydreeok_Draw:
{
  JSL Sprite_PrepOamCoord
  JSR Kydreeok_DrawShadow

  ; Wings and legs: 8 entries (32 bytes) in region E, under the heads.
  LDA.b #$20
  JSL OAM_AllocateFromRegionE

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX   .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .next_tile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .next_tile

  PLX

  RTS

  .start_index
    db $00, $08, $10
  .nbr_of_tiles
    db 7, 7, 7
  .x_offsets
    dw -20, -20, 20, 20, -16, -16, 16, 16
    dw -20, -36, 20, 36, -16, -16, 16, 16
    dw -20, -20, 20, 20, -16, -16, 16, 16
  .y_offsets
    dw -52, -36, -52, -36, -8, 8, -8, 8
    dw -36, -36, -36, -36, -6, 10, -8, 8
    dw -36, -20, -36, -20, -8, 8, -6, 10
  .chr
    db $CE, $EE, $CE, $EE, $00, $20, $00, $20
    db $0E, $0C, $0E, $0C, $00, $20, $00, $20
    db $CC, $EC, $CC, $EC, $00, $20, $00, $20
  .properties
    db $39, $39, $79, $79, $39, $39, $79, $79
    db $39, $39, $79, $79, $39, $39, $79, $79
    db $39, $39, $79, $79, $39, $39, $79, $79
}

; Ground shadow while airborne: 3 overlapping vanilla big-shadow tiles
; ($6C, as SpriteDraw_BigShadow) in the body's region A entries.
; In: $00/$02 from Sprite_PrepOamCoord (raised by the altitude). Keeps them.
Kydreeok_DrawShadow:
{
  LDA.w SprHeight, X : BEQ .hide
  ; Dive warning: the shadow flashes while the body hovers.
  LDA.w SprAction, X : CMP.b #!Kyd_Glide : BNE .airborne
  LDA.w SprTimerA, X : CMP.b #!Kyd_DiveWarn : BCS .airborne
  LDA.b $1A : AND.b #$04 : BEQ .airborne
  .hide
    LDA.b #$F0
    LDY.b #$01 : STA ($90), Y
    LDY.b #$05 : STA ($90), Y
    LDY.b #$09 : STA ($90), Y
    RTS
  .airborne
  LDA.w SprHeight, X
  REP #$20
  AND.w #$00FF : CLC : ADC.b $02 : CLC : ADC.w #$000C : STA.b $0C
  SEP #$20

  PHX
  LDX.b #$02
  LDY.b #$00
  .tile
    LDA.w .offset_x, X
    REP #$20
    %BossKit_Sext16()
    CLC : ADC.b $00 : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $0C : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen
      LDA.b #$F0 : STA ($90), Y
    .on_screen
    INY : LDA.b #$6C : STA ($90), Y
    INY : LDA.b #$28 : STA ($90), Y
    PHY
    TYA : LSR A : LSR A : TAY
    LDA.b $0F : ORA.b #$02 : STA ($92), Y
    PLY : INY
  DEX : BPL .tile
  PLX
  RTS

  .offset_x
    db -12, 0, 12
}

ApplyKydreeokGraphics:
{
  PHX
  REP #$20               ; A = 16, XY = 8
  LDX #$80 : STX $2100   ; turn the screen off (required)
  LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
  LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
  LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register
                          ; "001 => 2 registers write once (2 bytes: p, p+1)"
  CPY #$01 : BEQ .phase2
    LDA.w #KydreeokGraphics : STA $4302
    LDX.b #KydreeokGraphics>>16 : STX $4304
    JMP .continue
  .phase2
  LDA.w #KydreeokPhase2Graphics : STA $4302
  LDX.b #KydreeokPhase2Graphics>>16 : STX $4304
  .continue
  LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
  LDX   #$01 : STX $420B                  ; Do the DMA
  LDX #$0F : STX $2100                    ; Turn the screen back on
  SEP #$30
  PLX
  RTS

  KydreeokGraphics:
    incbin kydreeok.bin

  KydreeokPhase2Graphics:
    incbin kydreeok_phase2.bin
}

; =========================================================
; Kydreeok turn code (bank $3A, JSL). The pacing sheet is in AFS
; scratchpad/handoffs/kydreeok_stages_2026-10-19/PLAN.md.
; DBR stays $32 (WRAM mirror), so .w sprite RAM works; the tables here
; are read with .l. X = the calling sprite; X is kept.

pushpc
org $3AAA00

; Knob values by stage: rows are knobs (see !KydKnob_*), columns are
; stages 1, 2, 3. Frames.
Kydreeok_KnobTable:
  db  40,  32,  28 ; 0 bite telegraph
  db  40,  40,  32 ; 1 breath telegraph
  db  28,  24,  24 ; 2 fireball telegraph
  db  90,  90,  45 ; 3 stuck after a bite
  db  90,  90,  45 ; 4 pant after a breath
  db  60,  60,  45 ; 5 knocked down by a shot
  db  90,  75,  45 ; 6 rest after a turn
  db 240, 180, 120 ; 7 same-attack cooldown

; Stage patterns (!KydTurn_*), repeated in order.
Kydreeok_PatternStart:
  db 0, 3, 7
Kydreeok_PatternLen:
  db 3, 4, 6
Kydreeok_Pattern:
  db !KydTurn_Bite, !KydTurn_Bite, !KydTurn_Spit
  db !KydTurn_Breath, !KydTurn_Move, !KydTurn_Spit, !KydTurn_Move
  db !KydTurn_Bite, !KydTurn_Breath, !KydTurn_Fly
  db !KydTurn_Breath, !KydTurn_Bite, !KydTurn_Fly

; Head action that starts each head turn code (its telegraph).
Kydreeok_HeadAction:
  db !KydHead_Bite, !KydHead_Breath, !KydHead_Spit

; Stage 2 spots: X offset from home for Kydreeok_Spot 0-3.
Kydreeok_SpotX:
  db 0, 48, 0, -48

; Y = a slot. Carry set while it holds a live Kydreeok head. A dying
; head (SprState 6, the death poof) counts as lost, so the next stage
; starts with the poof.
KydDir_HeadAlive:
{
  LDA.w SprState, Y : BEQ .no
  CMP.b #$06 : BEQ .no
  LDA.w SprType, Y : CMP.b #Sprite_KydreeokHead : BNE .no
    SEC
    RTS
  .no
  CLC
  RTS
}

; A = head subtype (Z set for the left head). Out: Y = its slot.
KydDir_HeadSlot:
{
  BNE .right
    LDY.w Offspring1_Id
    RTS
  .right
  LDY.w Offspring2_Id
  RTS
}

; Out: X = BossDir_Stage - 1 (stage 0 counts as stage 1).
KydDir_StageIndex:
{
  LDA.l BossDir_Stage : BEQ .first
    DEC A
  .first
  TAX
  RTS
}

; Out: A = the turn code at the current pattern step.
KydDir_TurnCode:
{
  PHX
  JSR KydDir_StageIndex
  LDA.l Kydreeok_PatternStart, X : CLC : ADC.l BossDir_Turn : TAX
  LDA.l Kydreeok_Pattern, X
  PLX
  RTS
}

; Advance the pattern step, wrapping at the stage's length.
KydDir_NextTurn:
{
  PHX
  JSR KydDir_StageIndex
  LDA.l BossDir_Turn : INC A : CMP.l Kydreeok_PatternLen, X : BCC .keep
    LDA.b #$00
  .keep
  STA.l BossDir_Turn
  PLX
  RTS
}

; A = frames. The rest becomes at least A.
KydDir_RaiseRest:
{
  CMP.l BossDir_Rest : BCC .keep
    STA.l BossDir_Rest
  .keep
  RTS
}

; Out: A bit 0 = the left head lives, bit 1 = the right head lives.
Kydreeok_AliveBits:
{
  PHY
  LDA.b #$00 : PHA
  LDY.w Offspring1_Id : JSR KydDir_HeadAlive : BCC .left_dead
    LDA.b #$01 : STA $01, S
  .left_dead
  LDY.w Offspring2_Id : JSR KydDir_HeadAlive : BCC .right_dead
    LDA $01, S : ORA.b #$02 : STA $01, S
  .right_dead
  PLA
  PLY
  ORA.b #$00
  RTL
}

; X = the body. Out: A = the stage: 3 in the dragon form, else 1 with
; both heads, 2 with one.
Kydreeok_CurrentStage:
{
  LDA.w SprMiscD, X : CMP.b #$02 : BNE .heads
    LDA.b #$03
    RTL
  .heads
  JSL Kydreeok_AliveBits : CMP.b #$03 : BNE .one_head
    LDA.b #$01
    RTL
  .one_head
  LDA.b #$02
  RTL
}

; A = knob (!KydKnob_* or a head turn code). Out: A = its value in the
; current stage. Keeps X and Y.
Kydreeok_Knob:
{
  PHX
  PHA
  ASL A : CLC : ADC $01, S : STA $01, S ; knob * 3
  JSR KydDir_StageIndex
  TXA : CLC : ADC $01, S : TAX
  PLA
  LDA.l Kydreeok_KnobTable, X
  PLX
  RTL
}

; The director, from Kydreeok_Stand. X = the body.
; Out: A = an order (!KydOrder_*), Z set for none.
Kydreeok_TakeTurn:
{
  ; A token held by a head that died or went back to idle is lost.
  LDA.l BossDir_Token : CMP.b #$FF : BEQ .token_ok
    TAY
    JSR KydDir_HeadAlive : BCC .lost
    LDA.w SprAction, Y : CMP.b #!KydHead_Bite : BCS .token_ok
    .lost
      LDA.b #60 : STA.b $01
      JSL BossDirector_Free
  .token_ok

  ; A new stage: roar, quake, a pause, then walk to the stage's spot.
  JSL Kydreeok_CurrentStage
  CMP.l BossDir_Stage : BEQ .same_stage
    PHA
    LDA.l BossDir_Stage : STA.b $00
    PLA : STA.l BossDir_Stage
    LDA.b #$00 : STA.l BossDir_Turn : STA.l Kydreeok_Spot
    LDA.l Kydreeok_Flags : AND.b #$FC : ORA.b #$01 : STA.l Kydreeok_Flags
    LDA.b $00 : BNE .roar
      ; The fight starts: a short pause, no roar.
      LDA.b #60 : JSR KydDir_RaiseRest
      LDA.b #!KydOrder_None
      RTL
    .roar
    LDA.b #120
    LDY.w SprMiscD, X : CPY.b #$02 : BNE .rest_set
      LDA.b #180
    .rest_set
    JSR KydDir_RaiseRest
    LDA.b #$20 : STA.l BossKit_Quake
    LDA.b #$35 : JSL Sound_SetSfx2PanLong
    LDA.b #!KydOrder_Roar
    RTL
  .same_stage

  ; Someone is mid-turn.
  LDA.l BossDir_Token : CMP.b #$FF : BEQ .free
    LDA.b #!KydOrder_None
    RTL
  .free

  ; Walk to the spot first (after a stage change or a landing). Moves
  ; happen during the rest, with a stomp.
  LDA.l Kydreeok_Flags : AND.b #$01 : BNE .walk
  JSR KydDir_TurnCode
  CMP.b #!KydTurn_Move : BNE .attack
    LDA.l Kydreeok_Spot : INC A : AND.b #$03 : STA.l Kydreeok_Spot
    JSR KydDir_NextTurn
    LDA.l Kydreeok_Flags : ORA.b #$01 : STA.l Kydreeok_Flags
  .walk
    LDA.b #$06 : STA.l BossKit_Quake
    LDA.b #!KydOrder_Walk
    RTL
  .attack

  ; Attacks wait for the rest, the hit grace and the frame budget.
  PHA
  JSL BossDirector_Ready : BCS .ready
    PLA
    LDA.b #!KydOrder_None
    RTL
  .ready
  PLA
  CMP.b #!KydTurn_Fly : BNE .head_turn
    TXA : JSL BossDirector_Take
    JSR KydDir_NextTurn
    LDA.b #$35 : JSL Sound_SetSfx2PanLong
    LDA.b #!KydOrder_Fly
    RTL
  .head_turn
  STA.b $02
  ; Desperation (stage 3, one head left): each head turn opens with a
  ; fireball spread; the pattern attack follows after a short rest.
  STZ.b $03
  LDA.l BossDir_Stage : CMP.b #$03 : BNE .pick
  JSL Kydreeok_AliveBits : CMP.b #$03 : BEQ .pick
    INC.b $03
    LDA.l Kydreeok_Flags : AND.b #$02 : BNE .pick
      LDA.b #!KydTurn_Spit : STA.b $02
  .pick
  ; The head whose turn it is, or the other one when it is dead.
  LDA.l Kydreeok_NextHead : JSR KydDir_HeadSlot : JSR KydDir_HeadAlive : BCS .have_head
    LDA.l Kydreeok_NextHead : EOR.b #$01 : STA.l Kydreeok_NextHead
    JSR KydDir_HeadSlot : JSR KydDir_HeadAlive : BCC .none
  .have_head
  ; Y = the head. It must be idle, and this attack off its cooldown.
  LDA.w SprAction, Y : CMP.b #!KydHead_Idle : BNE .none
  LDA.w SprSubtype, Y : AND.b #$01 : STA.b $04
  LDA.b $02 : ASL A : ORA.b $04 : JSL BossDirector_CoolLeft : BNE .none
  TYA : JSL BossDirector_Take
  LDA.b $02 : STA.w SprMiscD, Y
  LDA.b #$00 : STA.w SprMiscG, Y
  LDA.b $02 : JSL Kydreeok_Knob : STA.w SprTimerA, Y
  PHX
  LDX.b $02
  LDA.l Kydreeok_HeadAction, X : STA.w SprAction, Y
  PLX
  LDA.l Kydreeok_NextHead : EOR.b #$01 : STA.l Kydreeok_NextHead
  LDA.b $03 : BEQ .advance
    ; Desperation: the opener keeps the step; the follow-up advances it.
    LDA.l Kydreeok_Flags : EOR.b #$02 : STA.l Kydreeok_Flags
    AND.b #$02 : BNE .none
    BRA .step
  .advance
  LDA.l Kydreeok_Flags : AND.b #$FD : STA.l Kydreeok_Flags
  .step
  JSR KydDir_NextTurn
  .none
  LDA.b #!KydOrder_None
  RTL
}

; From a head when its recovery ends. X = the head. If it holds the
; token: start that attack's cooldown and the rest (8 frames before a
; desperation follow-up), free the token.
Kydreeok_HeadDone:
{
  TXA : CMP.l BossDir_Token : BNE .not_holder
  LDA.b #!KydKnob_Cool : JSL Kydreeok_Knob : STA.b $00
  LDA.l Kydreeok_Flags : AND.b #$02 : BEQ .rest
    LDA.b #$08
    BRA .have_rest
  .rest
  LDA.b #!KydKnob_Rest : JSL Kydreeok_Knob
  .have_rest
  STA.b $01
  LDA.w SprMiscD, X : ASL A : STA.b $02
  LDA.w SprSubtype, X : AND.b #$01 : ORA.b $02
  JSL BossDirector_Release
  .not_holder
  RTL
}

; From the body when a dive lands. X = the body. Idle heads slam onto
; the floor and lie stuck; the token is freed with a long rest, and the
; body walks home next.
Kydreeok_Landed:
{
  LDY.w Offspring1_Id : LDA.b #-20 : JSR .slam
  LDY.w Offspring2_Id : LDA.b #20 : JSR .slam
  LDA.b #120 : STA.b $01
  JSL BossDirector_Free
  LDA.l Kydreeok_Flags : ORA.b #$01 : STA.l Kydreeok_Flags
  RTL

  ; Y = a head slot, A = its pose X offset.
  .slam
  PHA
  JSR KydDir_HeadAlive : BCC .skip
  LDA.w SprAction, Y : CMP.b #!KydHead_Idle : BNE .skip
    PLA : STA.w SprMiscE, Y
    LDA.b #36 : STA.w SprMiscF, Y
    LDA.b #!Kyd_SlamTime : STA.w SprTimerA, Y
    LDA.b #!KydHead_Stuck : STA.w SprAction, Y
    RTS
  .skip
  PLA
  RTS
}

; From Kydreeok_Walk. X = the body. Sets the speeds toward the stage
; spot (home, or home + Kydreeok_SpotX in stage 2).
; Carry set when the body is there.
Kydreeok_WalkStep:
{
  STZ.b $04
  LDA.b #$00
  PHA
  LDA.l BossDir_Stage : CMP.b #$02 : BNE .home
    PHX
    LDA.l Kydreeok_Spot : TAX
    LDA.l Kydreeok_SpotX, X : STA $02, S
    PLX
  .home
  PLA
  REP #$20
  %BossKit_Sext16()
  CLC : ADC.l Kydreeok_HomeX : STA.b $00
  SEP #$20

  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.b $00
  JSR .axis
  STA.w SprXSpeed, X

  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.l Kydreeok_HomeY
  JSR .axis
  STA.w SprYSpeed, X

  LDA.b $04 : CMP.b #$02
  RTL

  ; 16-bit A = position - target. Out: 8-bit A = speed; $04 counts the
  ; axes within 2 px.
  .axis
  CLC : ADC.w #$0002 : CMP.w #$0005
  SEP #$20
  BCS .far
    INC.b $04
    LDA.b #$00
    RTS
  .far
  XBA : BMI .plus
    LDA.b #-!Kyd_WalkSpeed
    RTS
  .plus
  LDA.b #!Kyd_WalkSpeed
  RTS
}

; From the body every frame. X = the body. In stage 3 a lost head grows
; back after 150 steps of 8 frames (20 s); the room rumbles in the last
; 4 s. Carry set: spawn the head, A = its subtype.
Kydreeok_RegrowTick:
{
  LDA.w SprAction, X : CMP.b #!Kyd_Dead : BEQ .off
  LDA.w SprMiscD, X : CMP.b #$02 : BNE .off
  JSL Kydreeok_AliveBits : CMP.b #$01 : BEQ .one_lost
  CMP.b #$02 : BNE .off
  .one_lost
  PHA
  LDA.l Kydreeok_Regrow : BNE .running
    LDA.b #150 : STA.l Kydreeok_Regrow
    BRA .no
  .running
  LDA.b $1A : AND.b #$07 : BNE .warn
    LDA.l Kydreeok_Regrow : DEC A : STA.l Kydreeok_Regrow : BNE .warn
      JSL BossKit_CanSpend : BCS .grow
        LDA.b #$01 : STA.l Kydreeok_Regrow
        BRA .no
      .grow
      ; The left head lives (bit 0): the right one (1) grows, and back.
      PLA : AND.b #$01
      SEC
      RTL
  .warn
  LDA.l Kydreeok_Regrow : CMP.b #30 : BCS .no
    LDA.b $1A : AND.b #$1F : BNE .no
      LDA.b #$08 : STA.l BossKit_Quake
      LDA.b #$35 : JSL Sound_SetSfx2PanLong
  .no
  PLA
  CLC
  RTL
  .off
  LDA.b #$00 : STA.l Kydreeok_Regrow
  CLC
  RTL
}

assert pc() <= $3AB000, "Kydreeok turn code crossed $3AB000"
pullpc
