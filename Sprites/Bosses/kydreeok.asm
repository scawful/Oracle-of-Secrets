; =========================================================
; Kydreeok: final boss body ($7A), the fight director.
;
; The body is BG2 (moved through $0422/$0424 by MoveBody); the wings and
; legs are 8 OAM entries in region E; a ground shadow uses 3 region A
; entries while it flies. Two heads ($CF, kydreeok_head.asm) ride on
; necks from its shoulders.
;
; Frame budget: the body runs after the heads and calls BossKit_FrameEnd
; last (Sprites/Bosses/boss_kit.asm). Take-offs, head respawns and head
; attacks ask BossKit_CanSpend first.
;
; Flight: crouch -> take off to !Kydreeok_CruiseAltitude -> glide after
; the player -> dive and land with an earthquake. SprHeight is the
; altitude; Kydreeok_SetAltitude raises the BG2 body with it, and
; Sprite_PrepOamCoord raises the wings, legs and head anchors.
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

%Set_Sprite_Properties(Sprite_Kydreeok_Prep, Sprite_Kydreeok_Long)

Sprite_Kydreeok_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Kydreeok_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Kydreeok_Main
    JSR Sprite_Kydreeok_CheckIfDead
    JSR MaybeRespawnHead
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
  ; The heads read the body from their first frame.
  TXA : STA.w Kydreeok_Id
  LDA.b #$40 : STA.w SprTimerA, X
  LDA.b #$08 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move
  LDA.b #$09 : STA.w SprBump,   X ; bump damage type
  STZ.w SprHeight, X

  ; Cache the origin position of the sprite.
  LDA.w SprX, X : STA.w SprMiscA, X
  LDA.w SprY, X : STA.w SprMiscB, X

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

; Head may respawn if the other isn't killed in time
MaybeRespawnHead:
{
  ; No new heads once the body is dying (Kydreeok_Dead, action 5).
  LDA.w SprAction, X : CMP.b #$05 : BEQ .done
  JSL BossKit_CanSpend : BCC .done
  LDY.w Offspring1_Id : JSR Kydreeok_HeadAlive : BCS .left_alive
    JSL GetRandomInt : AND.b #$7F : BNE .left_alive
      LDA.b #$00 : JSR Kydreeok_SpawnHead
  .left_alive
  LDY.w Offspring2_Id : JSR Kydreeok_HeadAlive : BCS .done
    JSL GetRandomInt : AND.b #$7F : BNE .done
      LDA.b #$01 : JSR Kydreeok_SpawnHead
  .done
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
                  Kydreeok_StageControl,
                  Kydreeok_MoveXandY,
                  Kydreeok_MoveXorY,
                  Kydreeok_KeepWalking,
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
  ; 0x01 - stand still (after the intro and after each landing)
  Kydreeok_StageControl:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    STZ.w SprYSpeed, X : STZ.w SprXSpeed, X
    JSL MoveBody
    JSR StopIfOutOfBounds

    LDA.w SprTimerA, X : BNE .continue
      %GotoAction(2)
    .continue

    RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  Kydreeok_MoveXandY:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA $36
    JSL Sprite_ApplySpeedTowardsPlayer
    JSR StopIfOutOfBounds
    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    %GotoAction(4)

    RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Kydreeok_MoveXorY:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA $36 : STA $00
    JSL Sprite_ApplySpeedTowardsPlayerXOrY
    JSR StopIfOutOfBounds
    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    %GotoAction(4)
    RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Kydreeok_KeepWalking:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA.w SprMiscD, X : CMP.b #$02 : BEQ .phase_two
      JSL GetRandomInt : AND.b #$7F : BNE .dont_fly
      BRA .take_off
    .phase_two
      JSL GetRandomInt : AND.b #$3F : BNE .dont_fly
    .take_off
      JSL BossKit_CanSpend : BCC .dont_fly
        STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
        LDA.b #$0A : STA.w SprTimerA, X
        %GotoAction(6)
        RTS
    .dont_fly

    PHX
    REP #$20

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently
    LDA $20 : SBC.w SprCachedY : CMP.w #$FFFB : BCC .notEqualY
      SEP #$20
      %GotoAction(2) ; Kydreeok_MoveXandY
      BRA .notEqualX
    .notEqualY

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently
    LDA $22 : SBC.w SprCachedX : CMP.w #$FFFB : BCC .notEqualX
      SEP #$20
      %GotoAction(2) ; Kydreeok_MoveXandY
    .notEqualX

    SEP #$20
    JSR StopIfOutOfBounds

    ; if both velocities are 0 go back to the Stalk_Player_XORY to re-set the course
    LDA.w SprYSpeed, X : BNE .notZero
      LDA.w SprXSpeed, X : BNE .notZero
        %GotoAction(3) ; Kydreeok_MoveXorY
    .notZero

    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    PLX

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
      LDA.b #$60
      LDY.w SprMiscD, X : CPY.b #$02 : BNE .glide_time
        LDA.b #$80
      .glide_time
      STA.w SprTimerA, X
      LDA $36 : CLC : ADC.b #$04
      JSL Sprite_ApplySpeedTowardsPlayer
      %GotoAction(8)
    .climbing
    RTS
  }

  ; -------------------------------------------------------
  ; 0x08 - glide after the player, re-aiming every 32 frames.
  ; No body contact in the air; the heads keep attacking.
  Kydreeok_Glide:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 08)

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
  ; the room, then the body stands still for a moment.
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
      LDA.b #$18 : STA.w SprTimerA, X
      %GotoAction(1)
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
  LDA.w SprHeight, X : BNE .airborne
    LDA.b #$F0
    LDY.b #$01 : STA ($90), Y
    LDY.b #$05 : STA ($90), Y
    LDY.b #$09 : STA ($90), Y
    RTS
  .airborne
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
