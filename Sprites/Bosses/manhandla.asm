; =========================================================
; Manhandla / Big ChuChu Sprite

!SPRID              = Sprite_Manhandla
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 01  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Manhandla_Prep, Sprite_Manhandla_Long)

Sprite_Manhandla_Long:
{
  %BossLong_DefeatedRemnant()
  PHB : PHK : PLB
  JSR Sprite_Manhandla_CheckForNextPhaseOrDeath
  LDA.w SprMiscD, X : CMP.b #$02 : BCC .phase1
    JSR Sprite_BigChuchu_Draw
    JMP .continue
  .phase1
    JSR Sprite_Manhandla_Draw
  .continue
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Manhandla_Main
  .SpriteIsNotActive
  PLB
  RTL
}

pushpc
; Sprite_DoTheDeath#PrepareEnemyDrop.post_death_stuff
org $06FA25
  LDA.w $0E20, X : CMP.b #$88
pullpc

Sprite_Manhandla_Prep:
{
  %BossPrep_DefeatedRemnant()
  PHB : PHK : PLB
  LDA.b #$04 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$80 : STA.w SprHealth, X
  LDA.w SprSubtype, X : STA.w SprAction, X
  PLB
  RTL
}

; If both the heads are dead, it's okay for this sprite to "die"
; Then we transition to the chuchu phase.
Sprite_Manhandla_CheckForNextPhaseOrDeath:
{
  ; Only the body owns phase transitions; flowers and blasts share this routine.
  LDA.w SprSubtype, X : BNE .not_dead
  ; Later phases no longer own the old head slots; retain their speed setup.
  LDA.w SprMiscD, X : BNE .offspring3_dead

  ; All three heads need to be dead before we become big chuchu
  LDA.w Offspring1_Id : TAY
  LDA.w SprState, Y : BEQ .offspring1_dead
    JMP .not_dead
  .offspring1_dead
  LDA.b #$05 : STA.w $36

  LDA.w Offspring2_Id : TAY
  LDA.w SprState, Y : BEQ .offspring2_dead
    JMP .not_dead
  .offspring2_dead
  LDA.b #$06 : STA.w $36

  LDA.w Offspring3_Id : TAY
  LDA.w SprState, Y : BEQ .offspring3_dead
    JMP .not_dead
  .offspring3_dead
  LDA.b #$07 : STA.w $36

  LDA.w SprMiscD, X : BNE .phase2
      LDA.b #$01 : STA.w SprMiscD, X
      LDA.b #$40 : STA.w SprTimerA, X
      LDA.b #$40 : STA.w SprHealth, X ; Refill the health
      LDA.b #$08 : STA.w SprNbrOAM, X ; Give more OAM
      LDA.b #$07 : STA.w SprAction, X ; Chuchu Emerge
      LDA.b #$0A : STA.w $36
    .not_dead
    RTS
  .phase2
  LDA.w SprMiscD, X : CMP.b #$03 : BEQ +
    LDA.w SprHealth, X : CMP.b #$04 : BCS .phase2_not_dead
      LDA.b #$50 : STA.w SprTimerA, X
      LDA.b #$09 : STA.w SprAction, X
      LDA.b #$13 : STA $012C
      LDA.b #$04 : STA.w SprMiscD, X
      LDA.b #$0A : STA.w $36
    .phase2_not_dead
  +

  RTS
}

SetLeftHeadPos:
  REP #$20
  LDA.w SprCachedX : SEC : SBC.w #$0016
  SEP #$20
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  REP #$20
  LDA.w SprCachedY : SEC : SBC.w #$000F
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y
  RTS

SetRightHeadPos:
  REP #$20
  LDA.w SprCachedX : CLC : ADC.w #$0016
  SEP #$20
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  REP #$20
  LDA.w SprCachedY : SEC : SBC.w #$000F
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y
  RTS

SetCenterHeadPos:
  REP #$20
  LDA.w SprCachedX
  SEP #$20
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  REP #$20
  LDA.w SprCachedY
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y
  RTS

Sprite_Manhandla_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Manhandla_Intro
  dw Manhandla_FrontHead ; 0x01
  dw Manhandla_LeftHead  ; 0x02
  dw Manhandla_RightHead ; 0x03
  dw BigChuchu_Main      ; 0x04
  dw Flower_Flicker      ; 0x05
  dw Manhandla_Body      ; 0x06
  dw BigChuchu_Emerge    ; 0x07
  dw BigChuchu_Flower    ; 0x08
  dw BigChuchu_Dead      ; 0x09
  dw ChuchuBlast         ; 0x0A

  Manhandla_Intro:
  {
    LDA.w SprSubtype, X : BNE .not_main
      LDA.w SprX, X : SEC : SBC.b #$04 : STA.w SprX, X
      JSR SpawnLeftManhandlaHead
      JSR SpawnRightManhandlaHead
      JSR SpawnCenterMandhandlaHead
      LDA.b #$06 : STA.w SprFrame, X
      LDA.b #$60 : STA.w SprTimerD, X ; First telegraphed volley timer
      LDA.b #$28 : STA.w SprTimerE, X ; Course re-target timer
      STZ.w SprMiscE, X               ; 0 = Stalking
      STZ.w SprMiscF, X
      %GotoAction(6) ; Manhandla_Body
      RTS
    .not_main

    LDA.w SprSubtype, X : STA.w SprAction, X
    RTS
  }

  Manhandla_FrontHead:
  {
    %PlayAnimation(0,1,10)

    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    RTS
  }

  Manhandla_LeftHead:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)

    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    RTS
  }

  Manhandla_RightHead:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)

    PHX
    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    RTS
  }

  ; Phase 2: Big Chuchu structured 4-beat combat loop (SprMiscE):
  ;   0 = Stalk -> 1 = Swell Telegraph -> (A: Aimed Blast Pair | B: Elastic Lunge) -> 3 = Punish Window
  BigChuchu_Main:
  {
    LDA.w SprTimerC, X : BEQ .active
      %PlayAnimation(0,2,8)
      RTS
    .active

    JSR BigChuchu_RunBeat

    PHX
    JSL Sprite_DamageFlash_Long
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    LDY.w Offspring3_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head3
    LDA.w SprState, Y : BEQ .offspring3_dead
      JSR SetCenterHeadPos
      .offspring3_dead
    .not_head3

    RTS
  }

  ; Transformation Act B: BG2 pod flickers out while SprMiscD stays 1 so
  ; Sprite_Manhandla_Draw renders frames 11..12 cleanly (fixes old BigChuchu OOB!).
  Flower_Flicker:
  {
    %StartOnFrame(11)
    %PlayAnimation(11, 12, 6)
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; Invulnerable during dissolve
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X

    ; Accelerating BG2 pod dissolve flicker
    LDA $1C : ORA.b #$01 : STA $1C ; turn on BG2 (Body)
    LDA.w SprTimerA, X : CMP.b #$14 : BCS .slow_flicker
      AND.b #$01 : BEQ .flicker_done
        BRA .hide_bg2
    .slow_flicker
    AND.b #$02 : BEQ .flicker_done
    .hide_bg2
      LDA $1C : AND.b #$FE : STA $1C ; turn off BG2 (Body)
    .flicker_done

    ; Subtle vertical shudder during pod dissolve
    REP #$20
    STZ.w $011A
    LDA.b $1A : AND.w #$0002 : DEC A : STA.w $011C
    SEP #$20

    LDA.w SprTimerA, X : BEQ .finish_bloom
      RTS
    .finish_bloom
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      STZ.w $0422
      STZ.w $0424
      LDA $1C : AND.b #$FE : STA $1C ; turn off BG2 (Body)
      LDA.b #$02 : STA.w SprMiscD, X ; Now switch renderer cleanly to BigChuchu
      STZ.w SprFrame, X              ; Frame 0 (valid BigChuchu frame!)
      LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X ; Vulnerable again
      LDA.b #$32 : JSL Sound_SetSfx3PanLong ; Elastic BOING reveal!
      STZ.w SprMiscC, X
      STZ.w SprMiscE, X
      STZ.w SprMiscF, X
      LDA.b #$48 : STA.w SprTimerD, X
      LDA.b #$28 : STA.w SprTimerE, X
      %GotoAction($04)

      LDA.b #$10 : STA.w SprTimerC, X
      LDA.b #$8D : STA.w SprHitbox, X

      LDA #$88
      JSL Sprite_SpawnDynamically : BMI .return
        TYA : STA.w Offspring3_Id
        PHX
        JSR SetCenterHeadPos
        LDA.b #$08 : STA.w SprSubtype, Y
        STA.w SprAction, Y
        LDA.b #$20 : STA.w SprHealth, Y
        LDA.b #$07 : STA.w SprNbrOAM, Y
        ; Spawn 16 px below center so 16 frames of DEC SprY arrive cleanly at +0!
        LDA.w SprY, Y : CLC : ADC.b #$10 : STA.w SprY, Y
        LDA.b #$10 : STA.w SprTimerC, Y
        TYX
        STZ.w SprYRound, X
        STZ.w SprXRound, X
        PLX
      .return
    RTS
  }

  Manhandla_Body:
  {
    LDA.w SprMiscE, X : BNE .telegraph_volley

    ; --- Stalking state (SprMiscE == 0) ---
    %PlayAnimation(6,8,12)
    PHX
    JSR Sprite_Manhandla_Move
    PLX
    LDA.w SprTimerD, X : BNE .post_ai
      ; Enter telegraphed volley wind-up (34 frames)
      LDA.b #$01 : STA.w SprMiscE, X
      LDA.b #$22 : STA.w SprTimerD, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      LDA.b #$2A : JSL Sound_SetSfx3PanLong ; Bud charge telegraph cue
      BRA .post_ai

    ; --- Telegraphed Volley state (SprMiscE == 1) ---
    .telegraph_volley
    %PlayAnimation(6,8,4)
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.w SprTimerD, X : BNE .post_ai
      JSR Mothula_SpawnBeams
      STZ.w SprMiscE, X
      ; Scale next volley cadence by surviving heads (3->120, 2->92, 1->68)
      JSR Manhandla_CountAliveHeads
      TAY
      LDA.w .volley_cd, Y : STA.w SprTimerD, X

    .post_ai
    PHX
    JSL Sprite_DamageFlash_Long
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    LDY.w Offspring1_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head
      LDA.w SprState, Y : BEQ .offspring1_dead
        JSR SetLeftHeadPos
      .offspring1_dead
    .not_head

    LDY.w Offspring2_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head2
      LDA.w SprState, Y : BEQ .offspring2_dead
        JSR SetRightHeadPos
      .offspring2_dead
    .not_head2

    LDY.w Offspring3_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head3
      LDA.w SprState, Y : BEQ .offspring3_dead
        JSR SetCenterHeadPos
      .offspring3_dead
    .not_head3
    PLX
    RTS

    .volley_cd
    db $44, $44, $5C, $78
  }

  ; Transformation Act A (64 frames, invulnerable): room shudder, rising SFX,
  ; smooth bud -> split -> petals progression (frames 9 -> 10 -> 11) before Flower_Flicker.
  BigChuchu_Emerge:
  {
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; Invulnerable during transform
    JSL Sprite_DamageFlash_Long

    ; Room rumble shudder (+-2 px X, +-1 px Y)
    REP #$20
    LDA.b $1A : AND.w #$0002 : ASL A : SEC : SBC.w #$0002 : STA.w $011A
    LDA.b $1A : AND.w #$0001 : ASL A : DEC A : STA.w $011C
    SEP #$20

    ; Staged audio beats
    LDA.w SprTimerA, X
    CMP.b #$3F : BNE +
      LDA.b #$35 : JSL Sound_SetSfx2PanLong ; Shaking rumble start
    +
    LDA.w SprTimerA, X
    CMP.b #$2A : BNE +
      LDA.b #$2A : JSL Sound_SetSfx3PanLong ; Swell power cue
    +
    LDA.w SprTimerA, X
    CMP.b #$16 : BNE +
      LDA.b #$30 : JSL Sound_SetSfx3PanLong ; Petal crack cue
    +

    ; Clean monotonic bloom progression: 9 -> 10 -> 11
    LDA.w SprTimerA, X
    CMP.b #$2C : BCS .bud_closed
    CMP.b #$16 : BCS .bud_cracking
      LDA.b #$0B : STA.w SprFrame, X ; Frame 11: full petals bursting
      BRA .check_done
    .bud_cracking
      LDA.b #$0A : STA.w SprFrame, X ; Frame 10: bud splitting open
      BRA .check_done
    .bud_closed
      LDA.b #$09 : STA.w SprFrame, X ; Frame 9: tight bud swelling

    .check_done
    LDA.w SprTimerA, X : BNE +
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      LDA.b #$0C : JSL Sound_SetSfx2PanLong ; Pod burst shockwave!
      ; Keep SprMiscD == 1 through Flower_Flicker so frames 11..12 stay valid!
      LDA.b #$24 : STA.w SprTimerA, X
      %GotoAction($05)
    +
    RTS
  }

  BigChuchu_Flower:
  {
    %PlayAnimation(12, 12, 1)
    JSL Sprite_DamageFlash_Long
    LDA.w SprTimerC, X : BEQ +
        LDA.w SprY, X : DEC : STA.w SprY, X
    +
    RTS
  }

  BigChuchu_Dead:
  {
    LDA.b #$FF
    STA.w $0BC0, X
    LDA.b #$04 : STA.w SprState, X
    STZ.w SprHealth, X
    ; Die like a vanilla boss so Explode_VerifyPrizing drops the heart
    ; container; its pickup sets the defeated bit and starts the crystal.
    ; Refight rooms (tag2 $3F) keep the explosion without a prize.
    LDA.b $AF : CMP.b #$3F : BEQ .no_prize
      JSL Sprite_KillFriends
      STZ.w SprFrame, X
    .no_prize
    RTS
  }

  ChuchuBlast:
  {
    %PlayAnimation(3, 4, 4)
    JSL Sprite_Move
    JSL Sprite_CheckTileCollision : BNE .despawn
    LDA.w SprTimerE, X : BEQ .despawn
    %DoDamageToPlayerSameLayerOnContact()
    RTS
    .despawn
    STZ.w SprState, X
    RTS
  }
}

BigChuchu_RunBeat:
{
  LDA.w SprMiscE, X
  JSL JumpTableLocal

  dw BigChuchu_BeatStalk
  dw BigChuchu_BeatSwell
  dw BigChuchu_BeatLunge
  dw BigChuchu_BeatPunish
}

BigChuchu_BeatStalk:
{
  %PlayAnimation(0,2,12)
  PHX
  JSR Sprite_Manhandla_Move
  PLX
  LDA.w SprTimerD, X : BNE .done
    LDA.b #$01 : STA.w SprMiscE, X
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$1E
    LDY.w SprHealth, X : CPY.b #$21 : BCS +
      LDA.b #$16 ; Enraged faster telegraph below half HP
    +
    STA.w SprTimerD, X
    LDA.b #$32 : JSL Sound_SetSfx3PanLong ; Elastic coil wind-up cue
  .done
  RTS
}

BigChuchu_BeatSwell:
{
  %PlayAnimation(0,2,4)
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  LDA.w SprTimerD, X : BNE .done
    INC.w SprMiscF, X
    LDA.w SprMiscF, X : AND.b #$01 : BEQ .start_lunge
      ; Pattern A: Paired Aimed Spore Burst -> Punish Window
      JSR Chuchu_SpawnAimedPair
      LDA.b #$30 : JSL Sound_SetSfx3PanLong
      LDA.b #$03 : STA.w SprMiscE, X
      LDA.b #$26
      LDY.w SprHealth, X : CPY.b #$21 : BCS +
        LDA.b #$1C
      +
      STA.w SprTimerD, X
      RTS
    .start_lunge
    ; Pattern B: Elastic Lunge Dash toward Link
    LDA.b #$1C
    LDY.w SprHealth, X : CPY.b #$21 : BCS +
      LDA.b #$22 ; Enraged faster lunge
    +
    JSL Sprite_ApplySpeedTowardsPlayer
    LDA.b #$26 : JSL Sound_SetSfx3PanLong ; Lunge dash cue
    LDA.b #$02 : STA.w SprMiscE, X
    LDA.b #$1A : STA.w SprTimerD, X
  .done
  RTS
}

BigChuchu_BeatLunge:
{
  %PlayAnimation(0,2,5)
  PHX
  JSR Manhandla_StopIfOutOfBounds
  JSL MoveBody
  PLX
  LDA.w SprTimerD, X : CMP.b #$0D : BNE +
    JSR Chuchu_SpawnBlast ; Drop one trailing aimed orb mid-lunge
  +
  LDA.w SprTimerD, X : BNE .done
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$21 : JSL Sound_SetSfx2PanLong ; Squelchy landing thud
    LDA.b #$03 : STA.w SprMiscE, X
    LDA.b #$2C
    LDY.w SprHealth, X : CPY.b #$21 : BCS +
      LDA.b #$20
    +
    STA.w SprTimerD, X
  .done
  RTS
}

BigChuchu_BeatPunish:
{
  %PlayAnimation(0,2,18)
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  LDA.w SprTimerD, X : BNE .done
    STZ.w SprMiscE, X
    LDA.b #$4C
    LDY.w SprHealth, X : CPY.b #$21 : BCS +
      LDA.b #$36
    +
    STA.w SprTimerD, X
  .done
  RTS
}

; Out: A = count of living Phase 1 heads (0..3). Guards against reused beam slots.
Manhandla_CountAliveHeads:
{
  PHY
  LDA.b #$00 : STA.b $00
  LDY.w Offspring1_Id : JSR .check_head
  LDY.w Offspring2_Id : JSR .check_head
  LDY.w Offspring3_Id : JSR .check_head
  LDA.b $00
  PLY
  RTS

  .check_head
  LDA.w SprState, Y : BEQ .dead
  LDA.w SprType, Y : CMP.b #$88 : BNE .dead
  LDA.w SprSubtype, Y : BEQ .dead
  CMP.b #$04 : BCS .dead
    INC.b $00
  .dead
  RTS
}

; Out: A = effective stalking speed (preserves $36 contract for phase checker).
Manhandla_EffectiveSpeed:
{
  LDA.w SprMiscD, X : CMP.b #$02 : BCS .chuchu_speed
    JSR Manhandla_CountAliveHeads
    TAY
    LDA.w .head_speed, Y
    RTS
  .chuchu_speed
  LDA.w SprHealth, X : CMP.b #$21 : BCC .enraged
    LDA.b #$0C
    RTS
  .enraged
  LDA.b #$10
  RTS

  .head_speed
  db $0C, $0B, $08, $06
}

Sprite_Manhandla_Move:
{
  LDA.w SprMiscC, X
  JSL JumpTableLocal

  dw StageControl
  dw MoveXandY
  dw MoveXorY
  dw KeepWalking

  StageControl:
  {
    STZ.w SprYSpeed, X : STZ.w SprXSpeed, X ; set velocities to 0
    JSL MoveBody
    JSR Manhandla_StopIfOutOfBounds
    LDA.w SprTimerA, X : BNE .continue
      INC.w SprMiscC, X
    .continue
    RTS
  }

  MoveXandY:
  {
    JSR Manhandla_EffectiveSpeed
    JSL Sprite_ApplySpeedTowardsPlayer
    JSR Manhandla_StopIfOutOfBounds
    JSL MoveBody
    LDA.b #$28 : STA.w SprTimerE, X
    INC.w SprMiscC, X
    RTS
  }

  MoveXorY:
  {
    JSR Manhandla_EffectiveSpeed : STA $00
    JSL Sprite_ApplySpeedTowardsPlayerXOrY
    JSR Manhandla_StopIfOutOfBounds
    JSL MoveBody
    LDA.b #$28 : STA.w SprTimerE, X
    INC.w SprMiscC, X
    RTS
  }

  KeepWalking:
  {
    PHX
    ; Re-target cleanly when the course timer expires or Link crosses our axis
    LDA.w SprTimerE, X : BEQ .retarget

    REP #$20
    LDA.b $20 : SEC : SBC.w SprCachedY : BPL + : EOR.w #$FFFF : INC A : +
    CMP.w #$0006 : BCC .retarget16
    LDA.b $22 : SEC : SBC.w SprCachedX : BPL + : EOR.w #$FFFF : INC A : +
    CMP.w #$0006 : BCS .keep_course

    .retarget16
    SEP #$20
    .retarget
    LDA.b #$01 : STA.w SprMiscC, X
    BRA .move_now

    .keep_course
    SEP #$20
    .move_now
    JSR Manhandla_StopIfOutOfBounds

    ; If both velocities are 0, immediately pick a fresh vector
    LDA.w SprYSpeed, X : ORA.w SprXSpeed, X : BNE .notZero
      LDA.b #$01 : STA.w SprMiscC, X
    .notZero

    JSL MoveBody

    PLX ; restores X
    RTS
  }
}

Manhandla_StopIfOutOfBounds:
{
  ; Left bound: if too far left and moving left (negative), bounce RIGHT (+8)
  REP #$20
  LDA.w SprCachedX : CMP.w #$153A : BCS .not_out_of_bounds_Left
    SEP #$20
    LDA.w SprXSpeed, X : BPL .not_out_of_bounds_Left
      LDA.b #$08 : STA.w SprXSpeed, X : STZ.w SprXRound, X

  .not_out_of_bounds_Left
  SEP #$20

  ; Right bound: if too far right and moving right (positive), bounce LEFT (-8)
  REP #$20
  LDA.w SprCachedX : CMP.w #$15C8 : BCC .not_out_of_bounds_Right
    SEP #$20
    LDA.w SprXSpeed, X : BMI .not_out_of_bounds_Right
      LDA.b #-08 : STA.w SprXSpeed, X : STZ.w SprXRound, X

  .not_out_of_bounds_Right
  SEP #$20

  ; Upper bound: if too high and moving up (negative), bounce DOWN (+8)
  REP #$20
  LDA.w SprCachedY : CMP.w #$0B3A : BCS .not_out_of_bounds_Up
    SEP #$20
    LDA.w SprYSpeed, X : BPL .not_out_of_bounds_Up
      LDA.b #$08 : STA.w SprYSpeed, X : STZ.w SprYRound, X

  .not_out_of_bounds_Up
  SEP #$20

  ; Lower bound: if too low and moving down (positive), bounce UP (-8)
  REP #$20
  LDA.w SprCachedY : CMP.w #$0BA6 : BCC .not_out_of_bounds_Down
    SEP #$20
    LDA.w SprYSpeed, X : BMI .not_out_of_bounds_Down
      LDA.b #-08 : STA.w SprYSpeed, X : STZ.w SprYRound, X

  .not_out_of_bounds_Down
  SEP #$20

  RTS
}

; Out: A = palette flash bits (damage flash OR transform/telegraph glow).
Manhandla_FlashBits:
{
  LDA.w SprAction, X : CMP.b #$07 : BEQ .glow ; BigChuchu_Emerge
  CMP.b #$05 : BEQ .glow                      ; Flower_Flicker
  LDA.w SprSubtype, X : BNE .damage
  LDA.w SprMiscE, X : CMP.b #$01 : BNE .damage ; Telegraphing volley / swell
  .glow
    LDA.b $1A : AND.b #$06 : ORA.w SprFlash, X
    RTS
  .damage
  LDA.w SprFlash, X
  RTS
}

Sprite_Manhandla_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  JSR Manhandla_FlashBits : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?

  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $02, $04, $08, $0C, $10, $14, $17, $1A, $1D, $23, $29, $33
  .nbr_of_tiles
  db 1, 1, 3, 3, 3, 3, 2, 2, 2, 5, 5, 9, 7
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 8, 8, 0
  dw 0, 8, 0, 8
  dw 0, -8, -8, 0
  dw 0, -8, 0, -8
  dw -12, -4, 12
  dw -12, -4, 12
  dw 12, 4, -12

  dw -12, -4, -12, -4, 12, 12
  dw -12, -4, -12, -4, 12, 12
  dw -16, -8, -16, -8, 16, 8, 16, 8, -12, 12
  dw -16, -8, -16, -8, 16, 8, 16, 8
  .y_offsets
  dw -8, 8
  dw 0, 16
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0

  dw -28, -28, -12, -12, -28, -12
  dw -24, -24, -8, -8, -24, -8
  dw -24, -24, -8, -8, -8, -8, -24, -24, -32, -32
  dw -24, -24, -8, -8, -8, -8, -24, -24
  .chr
  db $00, $20
  db $02, $22
  db $04, $05, $25, $24
  db $07, $08, $27, $28
  db $04, $05, $25, $24
  db $07, $08, $27, $28
  db $40, $41, $40
  db $43, $44, $46
  db $43, $44, $46

  db $4D, $4E, $6D, $6E, $4D, $6D
  db $8D, $8E, $AD, $AE, $8D, $AD
  db $CD, $CE, $ED, $EE, $ED, $EE, $CD, $CE, $AE, $AE
  db $CD, $CE, $ED, $EE, $ED, $EE, $CD, $CE
  .properties
  db $33, $33
  db $33, $33
  db $33, $33, $33, $33
  db $33, $33, $33, $33
  db $73, $73, $73, $73
  db $73, $73, $73, $73
  db $33, $33, $73
  db $33, $33, $73
  db $73, $73, $33

  db $33, $33, $33, $33, $73, $73
  db $33, $33, $33, $33, $73, $73
  db $33, $33, $33, $33, $73, $73, $73, $73, $32, $72
  db $33, $33, $33, $33, $73, $73, $73, $73
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02

  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02
}

Sprite_BigChuchu_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY ; Animation Frame
  LDA.w .start_index, Y : STA $06
  JSR Manhandla_FlashBits : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?

  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $09, $12, $1B, $1C
  .nbr_of_tiles
  db 8, 8, 8, 0, 0
  .x_offsets
  dw -12, 4, 20, -12, 4, 12, -12, 4, 12
  dw -12, 4, 20, -12, 4, 12, -12, 4, 12
  dw -12, 4, 20, -12, 4, 12, -8, 8, 16
  dw 0
  dw 0
  .y_offsets
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 0
  dw 0
  .chr
  db $80, $82, $84, $90, $92, $93, $B0, $B2, $B3
  db $80, $82, $84, $90, $92, $93, $D0, $D2, $D3
  db $80, $82, $84, $90, $92, $93, $D6, $D8, $D9
  db $88
  db $A8
  .properties
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33
  db $33
  .sizes
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02
  db $02
}

Chuchu_SpawnBlast:
{
  LDA.b #$16 : JSL Sprite_ProjectSpeedTowardsPlayer
  LDA.b $01 : STA.b $06 ; aimed X speed
  LDA.b $00 : STA.b $07 ; aimed Y speed
  JMP Chuchu_EmitOrb
}

; Spawns two aimed spore orbs fanning ~+-14 degrees around the vector to Link.
Chuchu_SpawnAimedPair:
{
  LDA.b #$1A : JSL Sprite_ProjectSpeedTowardsPlayer
  LDA.b $01 : STA.b $08 ; base vx
  LDA.b $00 : STA.b $09 ; base vy
  ; Perpendicular spread delta = (vy/4, vx/4)
  LDA.b $09 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $0A
  LDA.b $08 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $0B

  ; Save Orb 2 speeds on stack across Sprite_SpawnDynamically
  LDA.b $08 : SEC : SBC.b $0A : PHA ; Orb 2 vx
  LDA.b $09 : CLC : ADC.b $0B : PHA ; Orb 2 vy

  ; Orb 1: (vx + vy/4, vy - vx/4)
  LDA.b $08 : CLC : ADC.b $0A : STA.b $06
  LDA.b $09 : SEC : SBC.b $0B : STA.b $07
  JSR Chuchu_EmitOrb

  ; Orb 2: pull saved speeds
  PLA : STA.b $07
  PLA : STA.b $06
  JMP Chuchu_EmitOrb
}

; In: $06 = X speed, $07 = Y speed. Spawns one ChuchuBlast orb with 2s lifetime.
Chuchu_EmitOrb:
{
  PHX
  LDA.b #$88
  JSL Sprite_SpawnDynamically : BMI .return
    LDA.b #$0A : STA.w SprSubtype, Y : STA.w SprAction, Y
    LDA.w SprX, X : STA.w SprX, Y
    LDA.w SprXH, X : STA.w SprXH, Y
    LDA.w SprY, X : CLC : ADC.b #$10 : STA.w SprY, Y
    LDA.w SprYH, X : ADC.b #$00 : STA.w SprYH, Y
    LDA.b $06 : STA.w SprXSpeed, Y
    LDA.b $07 : STA.w SprYSpeed, Y
    LDA.b #$00 : STA.w SprXRound, Y : STA.w SprYRound, Y
    LDA.b #$02 : STA.w SprMiscD, Y
    LDA.b #$00 : STA.w SprTileDie, Y
    LDA.b #$40 : STA.w SprProps, Y
    LDA.b #$04 : STA.w SprFrame, Y
    LDA.b #$10 : STA.w SprTimerB, Y
    LDA.b #$78 : STA.w SprTimerE, Y ; 2-second lifetime cap
    LDA.b #$00 : STA.w SprNbrOAM, Y
    LDA.b #$03 : STA.w SprHitbox, Y
  .return
  PLX
  RTS
}

Mothula_SpawnBeams:
{
  LDA.b #$36 ; SFX3.36
  JSL $0DBB8A ; SpriteSFX_QueueSFX3WithPan

  ; Aim vertical spread toward player (preserve aim flag on stack across spawn)
  JSL Sprite_IsBelowPlayer
  TYA : PHA ; 1,S = 1 if player is above Manhandla, 0 if below

  LDA.b #$02 : STA.w $0FB5

  .next_spawn
  LDA.b #$89 ; SPRITE 89
  JSL Sprite_SpawnDynamically : BMI .no_space
    JSL Sprite_SetSpawnedCoordinates
    LDA.b $02 : SEC : SBC.b $04
    CLC : ADC.b #$03 : STA.w SprY,Y
    LDA.b #$10 : STA.w SprTimerA,Y : STA.w SprBulletproof,Y

    PHX ; stack: [X, aim_flag]
    LDX.w $0FB5
    LDA.b $00 : CLC : ADC.w .speed_and_offset_x,X : STA.w SprX,Y
    LDA.w .speed_and_offset_x,X : STA.w SprXSpeed,Y
    LDA.w .speed_y,X
    PHA ; stack: [vy, X, aim_flag] -> aim_flag at 3,S
    LDA $03, S : BEQ .aim_down
      PLA : EOR.b #$FF : INC A : BRA .store_y
    .aim_down
    PLA
    .store_y
    STA.w SprYSpeed,Y
    LDA.b #$00 : STA.w SprHeight,Y
    PLX
  .no_space
  DEC.w $0FB5
  BPL .next_spawn
  PLA ; drop aim_flag
  RTS
  .speed_and_offset_x
  db -20,   0,  20

  .speed_y
  db  24,  32,  24
}

SpawnLeftManhandlaHead:
{
  LDA #$88
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA.w Offspring1_Id
    PHX
    JSR SetLeftHeadPos
    LDA.b #$03 : STA.w SprSubtype, Y
    STA.w SprAction, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps, X : ORA.b #$80 : STA.w SprGfxProps, Y
    TYX
    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

SpawnRightManhandlaHead:
{
  LDA #$88
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA.w Offspring2_Id
    PHX
    JSR SetRightHeadPos
    LDA.b #$02
    STA.w SprSubtype, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps, X : AND.b #$80 : STA.w SprGfxProps, Y
    TYX
    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

SpawnCenterMandhandlaHead:
{
  LDA #$88
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA.w Offspring3_Id
    PHX
    JSR SetCenterHeadPos
    LDA.b #$01
    STA.w SprSubtype, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps, X : AND.b #$80 : STA.w SprGfxProps, Y
    TYX
    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

ApplyManhandlaPalette:
{
  REP #$20 ;Set A in 16bit mode
  ; note, this uses adresses like 7EC300 and not 7EC500 because the game
  ; will fade the colors into 7EC500 based on the colors found in 7EC300
  LDA #$7FFF : STA $7EC5E2 ;BG2
  LDA #$08D9 : STA $7EC5E4
  LDA #$1E07 : STA $7EC5E6
  LDA #$4ACA : STA $7EC5E8
  LDA #$14A5 : STA $7EC5EA
  LDA #$133F : STA $7EC5EC
  LDA #$19DF : STA $7EC5EE
  INC $15
  SEP #$20 ;Set A in 8bit mode
  RTS
}

ApplyManhandlaGraphics:
{
  ; Called from transition code (e.g. UnderworldTransition_ScrollRoom).
  ; Do not assume X/Y width on entry: if X=16-bit, STX would write 2 bytes
  ; to PPU regs ($2100/$2101, etc) and PHX/PLX would desync the stack.
  PHP
  SEP #$10               ; Force X/Y=8-bit for STX and PHX/PLX symmetry.
  PHX
  REP #$20               ; A = 16
  LDX #$80 : STX $2100   ; turn the screen off (required)
  LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
  LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram, need to be divided by 2
  LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register
                          ; "001 => 2 registers write once (2 bytes: p, p+1)"

  LDA.w #ManhandlaGraphics : STA $4302
  LDX.b #ManhandlaGraphics>>16 : STX $4304

  LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
  LDX   #$01 : STX $420B                  ; Do the DMA
  LDX #$0F : STX $2100                    ; Turn the screen back on
  SEP #$30
  PLX
  PLP
  RTS
}

; Relocated from Bank $30 sprite code stream to dedicated Bank $54 asset slot
; (DMA-only via ApplyManhandlaGraphics; saves 8,192 B in Bank $30).
pushpc
org $54A000
ManhandlaGraphics_DataStart:
ManhandlaGraphics:
  incbin manhandla.bin
ManhandlaGraphics_DataEnd:
assert pc() <= $54C000, "ManhandlaGraphics overflowed $54A000-$54BFFF"
pullpc
