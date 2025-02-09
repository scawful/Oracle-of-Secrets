; =========================================================
;  Kydrog Boss
; =========================================================

!SPRID              = Sprite_KydrogBoss
!NbrTiles           = 11  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this KydrogBoss (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
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
!Boss               = $01  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_KydrogBoss_Prep, Sprite_KydrogBoss_Long)

!ConsecutiveHits    = $AC ; 0x01
!KydrogPhase        = $7A ; 0x01
!WalkSpeed          = 10  ; 0x01

Sprite_KydrogBoss_Long:
{
  PHB : PHK : PLB
  JSR Sprite_KydrogBoss_Draw ; Call the draw code
  JSR Sprite_CheckIfFrozen
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_KydrogBoss_CheckIfDead
    JSR Sprite_KydrogBoss_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_KydrogBoss_CheckIfDead:
{
  LDA.w SprAction, X : CMP.b #$09 : BEQ .not_dead
    ; If health is negative, set back to zero
    LDA.w SprHealth, X : CMP.b #$C3 : BCC .health_not_negative
      LDA.b #$00 : STA.w SprHealth, X
    .health_not_negative

    LDA.w SprHealth, X : BNE .not_dead
      PHX
      LDA.b #$04 : STA.w SprState, X ;kill sprite boss style
      LDA.b #$09 : STA.w SprAction, X ;go to KydrogBoss_Death stage
      STZ.w $0D90,X

      LDA.b #$E0 : STA.w SprTimerA,X
      PLX
  .not_dead
  RTS
}

Sprite_KydrogBoss_Prep:
{
  PHB : PHK : PLB
  LDA #$00 : STA !KydrogPhase

  LDA.b #$A0 : STA.w SprHealth, X ; health
  LDA.b #$80 : STA.w SprDefl, X

  LDA.b #$03 : STA.w SprHitbox, X ; hitbox settings
  LDA.b #$07 : STA.w SprBump, X ; bump damage type
  LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X ; Not invincible

  JSR KydrogBoss_Set_Damage ; Set the damage table

  %SetSpriteSpeedX(15)
  %SetSpriteSpeedX(15)
  %SetHarmless(00)

  LDA #$80 : STA.w SprTimerD, X ; intro timer
  PLB
  RTL
}

pushpc
org $1ECD97
  LDA.b #$0A
pullpc

macro StopIfTooClose()
  LDA $0E : CMP.b #$0020 : BCS +
  CLC
  LDA $0F : CMP.b #$0020 : BCS +
  LDA.b #$20 : STA.w SprTimerD, X ; set timer E to 0x20
  %GotoAction(7)
  RTS
+
endmacro

RandomStalfosOffspring:
{
  JSL GetNumberSpawnStalfos
  LDA $00 : CMP.b #$04 : BCS .too_many_stalfos
    JSL GetRandomInt : AND.b #$3F : BNE +
      PHX : JSR Sprite_Offspring_Spawn : PLX
    +
    JSL GetRandomInt : AND.b #$3F : BNE ++
      PHX : JSR Sprite_Offspring_SpawnHead : PLX
    ++
  .too_many_stalfos
  RTS
}

BounceBasedOnPhase:
{
  LDA !KydrogPhase : CMP #$00 : BEQ .phase_one
    LDA #$10 : STA $08 : LDA #$20 : STA $09
  .phase_one
    JSL Sprite_BounceTowardPlayer
  RTS
}

KydrogBoss_DoMovement:
{
  PHX
  JSL Sprite_CheckDamageFromPlayer
  %DoDamageToPlayerSameLayerOnContact()
  PLX

  JSL Sprite_DamageFlash_Long
  JSR BounceBasedOnPhase

  JSR RandomStalfosOffspring

  %GotoAction(1)
  RTS
}

Sprite_KydrogBoss_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw KydrogBoss_Init          ; 00
  dw KydrogBoss_WalkState     ; 01
  dw KydrogBoss_WalkForward   ; 02
  dw KydrogBoss_WalkLeft      ; 03
  dw KydrogBoss_WalkRight     ; 04
  dw KydrogBoss_WalkBackward  ; 05
  dw KydrogBoss_TakeDamage    ; 06
  dw KydrogBoss_TauntPlayer   ; 07
  dw KydrogBoss_SummonStalfos ; 08
  dw KydrogBoss_Death         ; 09

  dw KydrogBoss_Ascend        ; 0A
  dw KydrogBoss_Descend       ; 0B
  dw KydrogBoss_Abscond       ; 0C

  KydrogBoss_Init:
  {
    %StartOnFrame(15)
    %PlayAnimation(15, 16, 8) ; Arms Crossed Animation
    ; JSR SetupMovieEffect
    ; JSR MovieEffect
    ; LDX.b #$00
    LDA.w SprTimerD, X : BNE +
      %GotoAction(1) ; Goto KydrogBoss_WalkState
    +
    RTS
  }

  KydrogBoss_WalkState:
  {
    JSR CheckForNextPhase
    LDA.w SprMiscA : BEQ .not_flashing
      LDA.b #$20 : STA.w SprTimerD, X
      %GotoAction(6) ; Goto KydrogBoss_TakeDamage
      RTS
    .not_flashing

    JSL GetRandomInt : AND.b #$0F : BNE .not_taunting
      LDA.b #$10 : STA.w SprTimerD, X
      %GotoAction(8) ; Goto KydrogBoss_TauntPlayer
      RTS
    .not_taunting

    ;   JSL GetRandomInt : AND.b #$0F : BNE .not_absconding
    ;     LDA.b #$20 : STA.w SprTimerD, X
    ;     %GotoAction(12) ; Goto KydrogBoss_Abscond
    ;     RTS
    ; .not_absconding

    LDA #$50 : STA $09, X
    JSL Sprite_DirectionToFacePlayer
    TYA : CMP.b #$02 : BCC .WalkRight
    .WalkForward
      %StopIfTooClose()
      JSL Sprite_IsBelowPlayer : TYA : BNE .WalkBackwards
        %GotoAction(2) ; Goto KydrogBoss_WalkForward
        RTS
      .WalkBackwards
      %GotoAction(5) ; Goto KydrogBoss_WalkBackwards
      RTS

    .WalkRight
      %StopIfTooClose()
      JSL Sprite_IsToRightOfPlayer : TYA : BNE .WalkLeft
        %GotoAction(4)
        RTS
      .WalkLeft
      %GotoAction(3) ; Goto KydrogBoss_WalkLeft
      RTS
  }

  KydrogBoss_WalkForward:
  {
    %PlayAnimation(0, 2, 8)
    JSR KydrogBoss_DoMovement
    RTS
  }

  KydrogBoss_WalkLeft:
  {
    %PlayAnimation(3, 5, 8)
    JSR KydrogBoss_DoMovement
    RTS
  }

  KydrogBoss_WalkRight:
  {
    %PlayAnimation(6, 8, 8)
    JSR KydrogBoss_DoMovement
    RTS
  }

  KydrogBoss_WalkBackward:
  {
    %PlayAnimation(9, 11, 8)
    JSR KydrogBoss_DoMovement
    RTS
  }

  KydrogBoss_TakeDamage: ;0x06
  {
    %StartOnFrame(12)
    %PlayAnimation(12, 14, 8)

    INC !ConsecutiveHits
    LDA !ConsecutiveHits : CMP #$10 : BCC .continue
      STZ !ConsecutiveHits
      ; SFX3.28
      LDA.b #$28 : JSL $0DBB8A  ; SpriteSFX_QueueSFX3WithPan
      %GotoAction($0A) ; Goto KydrogBoss_Ascend
      JSL Sprite_KillFriends
      RTS
    .continue

    PHX
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    JSL Sprite_DamageFlash_Long
    JSR RandomStalfosOffspring
    LDA.w SprTimerD, X : BNE +
      %GotoAction(1)
    +

    JSL GetRandomInt : AND.b #$1F : BNE ++
      ; SFX3.28
      LDA.b #$28 : JSL $0DBB8A  ; SpriteSFX_QueueSFX3WithPan
      %GotoAction($0A) ; Goto KydrogBoss_Ascend
    ++

    RTS
  }

  KydrogBoss_TauntPlayer: ;0x07
  {
    %StartOnFrame(15)
    %PlayAnimation(15, 16, 8) ; Arms Crossed Animation
    PHX
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    JSL Sprite_DamageFlash_Long
    LDA.w SprTimerD, X : BNE .continue_timer
      LDA.b #$20 : STA.w SprTimerD, X ; set timer E to 0x20
      %GotoAction(8)
    .continue_timer
    RTS
  }

  KydrogBoss_SummonStalfos: ;0x08
  {
    %StartOnFrame(17)
    %PlayAnimation(17, 17, 10)
    PHX
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    JSL Sprite_DamageFlash_Long

    JSR RandomStalfosOffspring

    LDA.w SprTimerD, X : BNE +
      JSR Kydrog_ThrowBoneAtPlayer
      %GotoAction(1)
    +
    RTS
  }

  KydrogBoss_Death: ;0x09
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 0, 10)

    JSL Sprite_KillFriends
    LDA.w SprFlash, X : INC : CMP.b #$08 : BNE .dontReset
      LDA.b #$00
    .dontReset
    STA.w SprFlash, X

    RTS
  }

  KydrogBoss_Ascend: ; 0x0A
  {
    %StartOnFrame(17)
    %PlayAnimation(17, 17, 10)

    JSR RandomStalfosOffspring

    ; Increase the Z for a bit until he is off screen
    LDA.w SprHeight, X : CLC : ADC.b #$04
    STA.w SprHeight, X : CMP.b #$B0 : BCC .not_off_screen
      LDA #$40 : STA.w SprTimerD, X
      %GotoAction($0B)
    .not_off_screen

    RTS
  }

  KydrogBoss_Descend:
  {
    %StartOnFrame(17)
    %PlayAnimation(17, 17, 10)

    JSR RandomStalfosOffspring

    LDA.w SprTimerD, X : BEQ .no_track_player

    LDA $20 : STA.w SprY, X
    LDA $22 : STA.w SprX, X
    ; PHX : JSL $01F3EC : PLX ; Light Torch

    LDA.w SprTimerD, X : BNE .wait_a_second
    .no_track_player

    ; Decrease the Z for a bit until he is at level with Link
    LDA.w SprHeight, X : SEC : SBC.b #$04 : STA.w SprHeight, X
    CMP.b #$04 : BCS .not_off_screen
      %GotoAction(1)
    .not_off_screen

    .wait_a_second
    RTS
  }

  KydrogBoss_Abscond: ; 0x0C
  {
    %StartOnFrame(13)
    %PlayAnimation(13, 13, 10)

    JSL GetRandomInt : AND.b #$3F : BNE +
      LDA.b SprXSpeed : CLC : ADC.b #$08 : STA.w SprXSpeed
      LDA.b SprXRound : CLC : ADC.b #$02 : STA.w SprXRound
      LDA.w SprTimerD, X : BNE .not_done
        %GotoAction(1)
        RTS
    +
    LDA.b SprYSpeed : CLC : ADC.b #$08 : STA.w SprYSpeed
    LDA.b SprYRound : CLC : ADC.b #$02 : STA.w SprYRound
    LDA.w SprTimerD, X : BNE .not_done
    %GotoAction(1)

    .not_done
    JSL Sprite_Move
    RTS
  }
}

CheckForNextPhase:
{
  LDA !KydrogPhase : CMP.b #$00 : BEQ .phase_one
                     CMP.b #$01 : BEQ .phase_two
                     CMP.b #$02 : BEQ .phase_three
                     CMP.b #$03 : BEQ .phase_four
                     RTS

  .phase_one
    ; Check for phase two
    LDA.w SprHealth,X : CMP.b #$20 : BCC .phase_two
    RTS

  .phase_two
    LDA.w SprHealth,X : CMP.b #$20 : BCC .phase_three
    LDA !KydrogPhase : CMP.b #$01 : BEQ .return
    LDA #$80 : STA.w SprHealth, X
    LDA #$01 : STA.w SprAction, X
    STA !KydrogPhase
    INC.w SprFlash, X
    RTS

  .phase_three
    LDA.w SprHealth,X : CMP.b #$20 : BCC .phase_four
    LDA !KydrogPhase : CMP.b #$02 : BEQ .return
    LDA #$80 : STA.w SprHealth, X
    LDA #$02 : STA.w SprAction, X
    STA !KydrogPhase
    RTS

  .phase_four

    LDA #$03 : STA.w SprAction, X
    STA !KydrogPhase
  .return
  RTS
}

; TODO: Use a timer to unfreeze the sprite
Sprite_CheckIfFrozen:
{
  LDA.w SprState, X : CMP.b #$0B : BNE .not_frozen
    LDA.w SprTimerC, X : BNE .not_frozen
      LDA.b #$00 : STA.l $7FFA3C,X
      LDA.b #$09 : STA.w SprState, X
    .not_frozen
  RTS
}

;BA: Boomerang
;D1: Damage 1
;D2: Damage 2
;D3: Damage 3
;D4: Damage 4
;D5: Damage 5
;AR: Arrow Damage
;HS: Hookshot Damage
;BM: BombDamage
;SA: Silvers Damage
;PD: Powder Damage
;FR: Fire Rod Damage
;IR: Ice Rod Damage
;BB: Bombos Damage
;EF: Ether Damage
;QU: Quake Damage

KydrogBoss_Set_Damage:
{
  PHX
  LDX.b #$00

  .loop
  LDA .damageProperties, X : STA $7F6CB0, X
  INX : CPX.b #$10 : BNE .loop

  PLX
  RTS

  .damageProperties
  db $00, $01, $01, $01, $01, $01, $01, $00, $04, $01, $00, $01, $03, $01, $00, $01
      ;BA   D1   D2   D3   D4   D5   AR   HS   BM   SA   PD   FR   IR   BB   ET   QU
}

Sprite_Offspring_SpawnHead:
{
  JSL GetRandomInt : AND.b #$3F : BNE .normal_head
    LDA.b #$02 : BRA .alt_entry
  .normal_head
  LDA.b #$7C
  .alt_entry
  BRA Sprite_Offspring_Spawn_alt_entry
  RTS
}

Sprite_Offspring_Spawn:
{
  JSL GetRandomInt : AND.b #$3F : BNE .normal_stalfos
    LDA.b #$85 : BRA .alt_entry
  .normal_stalfos
  ; Spawn the stalfos offspring
  LDA.b #$A7
  .alt_entry
  JSL Sprite_SpawnDynamically : BMI .return ;89

  LDA.b #$02 : STA.w SprSubtype, Y
  PHX
  REP #$20
  LDA.w SprCachedX : CLC : ADC.w #$000C
  SEP #$20
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  REP #$20
  LDA.w SprCachedY : CLC : ADC.w #$001E
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y

  TYX

  STZ.w SprYRound, X : STZ.w SprXRound, X
  LDA.b #$05 : STA.w SprBump, X
  PLX
  .return

  RTS
}

Kydrog_ThrowBoneAtPlayer:
{
  LDA.b #$A7 : JSL Sprite_SpawnDynamically : BMI .spawn_failed
    LDA.b #$01 : STA $0D90, Y ; Sprite state "falling into a pit"
    JSL Sprite_SetSpawnedCoords
    PHX
    TYX

    LDA.w SprX, X : CLC : ADC.b #$10 : STA.w SprX, X
    LDA.w SprY, X : SEC : SBC.b #$04 : STA.w SprY, X
    LDA.b #$20 : JSL Sprite_ApplySpeedTowardsPlayer
    LDA.b #$21 : STA.w SprNbrOAM, X : STA.w SprBulletproof, X
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
    LDA.b #$48 : STA.w SprDefl, X
    LDA.b #$10 : STA.w SprTimerC, X
    LDA.b #$14 : STA.w SprHitbox, X
    LDA.b #$07 : STA.w SprProps, X
    LDA.b #$20 : STA.w SprBump, X
    PLX
    LDA.b #$02 : JSL Sound_SetSfx2PanLong
  .spawn_failed
  RTS
}

; Y   = sprite index after you spawn it.
; $00 = your stalfos skull count
GetNumberSpawnStalfos:
{
  PHX
  STZ.w $00

  LDX.b #$10

  .x_loop
    DEX
    LDY.b #$04
    .y_loop
      DEY
      LDA $0E20, X : CMP.w .stalfos_ids, Y : BEQ .increment_count
      BRA .not_a_skull

    .increment_count
      LDA.w SprState, X : CMP.b #$00 : BEQ .not_a_skull
      INC $00

  .not_a_skull
    CPY.b #$00 : BNE .y_loop
    CPX.b #$00 : BNE .x_loop

    PLX

    RTL

  .stalfos_ids
    db $7C, $02, $A7, $85
}

Sprite_KydrogBoss_Draw:
{
    JSL Sprite_PrepOamCoord
    JSL Sprite_OAM_AllocateDeferToPlayer
    ; JSL OAM_AllocateFromRegionE

    LDA $0DC0, X : CLC : ADC $0D90, X : ASL : TAY ; Animation Frame
    REP #$20
    LDA .start_index, Y : STA $06 ; Needs to be 16 bit ; Y = 00, 02, 04, 06
    SEP #$20

    LDA.w SprFlash, X : STA $08

    PHX ; Store Sprite ID
    REP #$20
    LDA .nbr_of_tiles, Y ;amount of tiles -1 ; doesn't need to be 16 bit ;Y = 00, 02, 04, 06
    REP #$30
    TAX
    LDY.w #$0000

  .nextTile
    REP #$30

    PHX ; Save current tile index
    TXA : CLC : ADC $06 ; Add Animation Index Offset

    PHA ; Keep the value with animation index offset

    ASL A : TAX ; *2 for the X and Y position

    REP #$30 ; X and Y position must be 16 bit

    LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC : ADC #$0010 : CMP.w #$0100
    SEP #$20 ; change A back to 8bit but not X and Y
    BCC .on_screen_y

    LDA.b #$F0 : STA ($90), Y ; Put the sprite out of the way
    STA $0E
  .on_screen_y

    PLX ; Pullback Animation Index Offset
    ; so X here is (nbr of tiles + animation index)
    INY
    LDA .chr, X : STA ($90), Y
    INY

    ; Set palette flash modifier
    LDA .properties, X : ORA $08 : STA ($90), Y

    REP #$30
    PHY
    TYA : LSR #2 : TAY ; divide Y by 4
    SEP #$20 ;set A back to 8bit but not X and Y
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY
    PLX : DEX : BPL .nextTile

    SEP #$30

    PLX

    RTS

  .start_index
    dw $00, $0B, $15, $1F, $27, $2D, $35, $3D, $43, $4C, $57, $66, $71, $7A, $87, $91, $99, $A1
  .nbr_of_tiles
    dw 10, 9, 9, 7, 5, 7, 7, 5, 8, 10, 14, 10, 8, 12, 9, 7, 7, 6
  .x_offsets
    dw -8, 8, 8, 0, 8, 0, -8, -8, 16, 16, -8
    dw -8, 8, -8, 0, 16, 16, -8, 16, 0, 8
    dw -8, 8, 0, 16, -8, -8, -8, 16, 0, 8
    dw 0, 0, 16, 8, 0, 16, 16, 16
    dw 16, 0, 0, 16, 16, 0
    dw 0, 16, 8, 16, 0, 16, 12, 0
    dw 4, -4, 12, 4, -4, -4, 4, -4
    dw 4, -12, 4, -12, -4, 16
    dw 4, -4, 4, -4, -4, 12, 12, -4, 12
    dw 0, 8, 8, 0, 0, 8, -8, -8, -8, 16, 16
    dw 0, 8, 8, 0, 8, 0, 0, 8, 8, -8, -8, -8, 16, 16, 16
    dw 0, 8, 8, 0, 0, 8, 16, 16, 16, -8, -8
    dw -8, -8, 8, 16, 8, 8, 16, 0, 8
    dw 0, -8, 8, 8, -8, -8, 0, 8, 0, 8, 16, 16, 16
    dw -8, 16, 8, 8, 16, 0, 16, -8, 0, 8
    dw -8, 8, -8, -8, 8, 8, -8, 16
    dw -8, 8, 0, 8, -8, 8, -8, 16
    dw -12, 4, 12, -4, 0, 16, 8
  .y_offsets
    dw -20, -20, -4, 4, 4, 12, 4, 12, 4, 12, -4
    dw -19, -19, 4, 4, 4, 12, -4, -4, -3, -3
    dw -20, -20, 4, 4, 4, 12, -4, -4, -4, -4
    dw -20, -4, -4, -4, 4, 4, 12, -20
    dw -20, -4, 4, -4, 4, -20
    dw -20, -20, -4, -4, 4, 4, 12, -4
    dw -20, -20, -4, -4, -4, -12, 4, 4
    dw -20, -20, -4, -4, 4, 0
    dw -20, -20, -4, -4, 4, 0, 8, -12, -4
    dw -20, -20, -12, 0, -4, -4, -8, 0, 8, 0, -8
    dw -20, -20, -12, -4, -4, 0, 8, 0, 8, 0, 8, -8, 0, 8, -8
    dw -20, -20, -12, 0, -4, -4, -8, 0, 8, 0, -8
    dw -24, -8, -24, -8, -8, 0, 0, 8, 8
    dw -8, -24, -24, -8, -8, 0, 8, 8, 0, 0, 0, 8, -8
    dw -16, -16, -16, -8, -8, 0, 0, 0, -24, -24
    dw 0, 0, -16, -24, -16, -24, -16, -16
    dw 0, 0, -8, -8, -24, -24, -8, -8
    dw -4, -4, -20, -20, 12, 12, 12
  .chr
    db $87, $87, $A7, $80, $81, $A4, $93, $A3, $96, $A6, $A7
    db $87, $87, $B3, $80, $92, $A2, $83, $83, $A8, $A8
    db $87, $87, $80, $B2, $A1, $B1, $83, $83, $A8, $A8
    db $C9, $E9, $EB, $EA, $C0, $C2, $D2, $CB
    db $CE, $EC, $C3, $EE, $C5, $CC
    db $C9, $CB, $FA, $FB, $C6, $C8, $D8, $E9
    db $C9, $CB, $E9, $EA, $EB, $DB, $E1, $E0
    db $CC, $CE, $EC, $EE, $E3, $E5
    db $C9, $CB, $FA, $FB, $E6, $E8, $F8, $DE, $E9
    db $89, $89, $99, $8E, $A9, $A9, $82, $92, $A2, $B3, $83
    db $89, $89, $99, $A9, $A9, $8D, $9D, $8D, $9D, $8C, $9C, $83, $A1, $B1, $82
    db $89, $89, $99, $8E, $A9, $A9, $83, $93, $A3, $B2, $83
    db $45, $65, $45, $65, $66, $77, $75, $BD, $BE
    db $6F, $4E, $4E, $6F, $47, $57, $7C, $7D, $AA, $AB, $6E, $7E, $83
    db $84, $84, $85, $95, $5D, $AA, $6D, $6D, $8A, $8A
    db $AC, $AE, $50, $40, $50, $40, $52, $52
    db $AC, $AE, $63, $63, $42, $42, $60, $60
    db $68, $6A, $4B, $49, $70, $72, $71
  .properties
    db $39, $79, $79, $39, $39, $39, $39, $39, $39, $39, $39
    db $39, $79, $39, $39, $39, $39, $39, $79, $39, $79
    db $39, $79, $79, $39, $39, $39, $39, $79, $39, $79
    db $39, $39, $39, $39, $39, $39, $39, $39
    db $39, $39, $39, $39, $39, $39
    db $39, $39, $39, $39, $39, $39, $39, $39
    db $79, $79, $79, $79, $79, $79, $39, $39
    db $79, $79, $79, $79, $39, $39
    db $79, $79, $79, $79, $39, $39, $39, $79, $79
    db $39, $79, $79, $39, $39, $79, $79, $79, $79, $79, $79
    db $39, $79, $79, $39, $79, $39, $39, $79, $79, $39, $39, $39, $79, $79, $39
    db $39, $79, $79, $79, $39, $79, $79, $79, $79, $79, $39
    db $39, $39, $79, $79, $79, $39, $79, $39, $39
    db $39, $39, $79, $79, $39, $39, $39, $39, $39, $39, $39, $39, $79
    db $39, $79, $79, $79, $39, $39, $39, $79, $39, $79
    db $39, $39, $39, $39, $79, $79, $39, $79
    db $39, $39, $39, $79, $39, $79, $39, $79
    db $39, $39, $39, $39, $39, $39, $39
  .sizes
    db $02, $02, $02, $00, $00, $02, $00, $00, $00, $00, $02
    db $02, $02, $00, $02, $00, $00, $00, $00, $00, $00
    db $02, $02, $02, $00, $00, $00, $00, $00, $00, $00
    db $02, $00, $00, $00, $02, $00, $00, $00
    db $02, $02, $02, $02, $00, $02
    db $02, $00, $00, $00, $02, $00, $00, $00
    db $02, $00, $00, $00, $00, $00, $02, $02
    db $02, $02, $02, $02, $02, $00
    db $02, $00, $00, $00, $02, $00, $00, $00, $00
    db $02, $00, $00, $02, $00, $00, $00, $00, $00, $00, $00
    db $02, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $02, $00, $00, $02, $00, $00, $00, $00, $00, $00, $00
    db $02, $02, $02, $00, $00, $00, $00, $00, $00
    db $00, $02, $02, $00, $02, $02, $00, $00, $00, $00, $00, $00, $00
    db $02, $00, $00, $00, $00, $02, $00, $00, $00, $00
    db $02, $02, $02, $02, $02, $02, $00, $00
    db $02, $02, $02, $00, $02, $02, $00, $00
    db $02, $02, $02, $02, $00, $00, $00
}
