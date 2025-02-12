; =========================================================

!SPRID              = Sprite_Puffstool
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 0   ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0   ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Puffstool_Prep, Sprite_Puffstool_Long)

; =========================================================

Sprite_Puffstool_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Puffstool_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Puffstool_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_Puffstool_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  LDA.b #$80 : STA.w SprDefl, X
  PLB
  RTL

  .health
    db $04, $08, $0A, $10
}

; =========================================================

Sprite_Puffstool_Main:
{
  %SpriteJumpTable(Puffstool_Walking,
                   Puffstool_Stunned,
                   Puffstool_Spores)

  Puffstool_Walking:
  {
    %PlayAnimation(0,6,10)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA, X : BNE +
      JSL Sprite_SelectNewDirection
    +
    JSL Sprite_MoveXyz
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long
    JSL ThrownSprite_TileAndSpriteInteraction_long
    JSL Sprite_CheckIfRecoiling
    JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
      %GotoAction(1)
      %SetTimerA($60)
      %SetTimerF($20)
    .no_dano

    RTS
  }

  Puffstool_Stunned:
  {
    %PlayAnimation(7,7,10)

    JSL Sprite_CheckIfLifted
    JSL Sprite_DamageFlash_Long
    JSL ThrownSprite_TileAndSpriteInteraction_long

    LDA.w SprTimerA, X : BNE +
      %GotoAction(0)

      JSL GetRandomInt : AND.b #$1F : BEQ .bomb
        JSR Puffstool_SpawnSpores
        RTS
      .bomb
      LDA.b #$4A ; SPRITE 4A
      LDY.b #$0B
      JSL Sprite_SpawnDynamically : BMI .no_space
        JSL Sprite_SetSpawnedCoordinates
        JSL Sprite_TransmuteToBomb
      .no_space
    +
    RTS
  }

  Puffstool_Spores:
  {
    %StartOnFrame(8)
    %PlayAnimation(8,11,10)

    JSL Sprite_MoveXyz
    JSL Sprite_CheckDamageToPlayerSameLayer

    LDA.w SprTimerC, X : BNE +
      JSL ForcePrizeDrop_long
      STZ.w SprState, X
    +
    RTS
  }
}

Puffstool_SpawnSpores:
{
  LDA.b #$0C ; SFX2.0C
  JSL $0DBB7C ; SpriteSFX_QueueSFX2WithPan

  LDA.b #$03 : STA.b $0D

  .nth_child
  LDA.b #$B1 : JSL Sprite_SpawnDynamically : BMI .no_space
    JSL Sprite_SetSpawnedCoordinates
    PHX

    LDX.b $0D
    LDA.w .speed_x, X : STA.w SprXSpeed, Y
    LDA.w .speed_y, X : STA.w SprYSpeed, Y
    LDA.b #$20 : STA.w $0F80, Y
    LDA.b #$FF : STA.w $0E80, Y
    LDA.b #$40 : STA.w SprTimerC, Y
    LDA.b #$01 : STA.w SprSubtype, Y
    LDA.b #$02 : STA.w SprAction, Y

    PLX
  .no_space
  DEC.b $0D
  BPL .nth_child
  RTS

  .speed_x
  db  11, -11, -11, 11

  .speed_y
  db   0,  11,   0, -11
}

; =========================================================

Sprite_Puffstool_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $02, $04, $06, $08, $0A, $0C, $0E, $0F, $10, $11, $12
  .nbr_of_tiles
    db 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 4
  .y_offsets
    dw -8, 0
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0
    dw 0
    dw 0
    dw 0
    dw 4
  .chr
    db $C0, $D0
    db $D2, $C2
    db $D4, $C4
    db $D2, $C2
    db $D0, $C0
    db $D2, $C2
    db $D4, $C4
    db $D6
    db $EA
    db $C8
    db $E8
    db $F7
  .properties
    db $33, $33
    db $33, $33
    db $33, $33
    db $33, $33
    db $33, $33
    db $73, $73
    db $73, $73
    db $3D
    db $33
    db $33
    db $33
    db $33
  .sizes
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02
    db $02
    db $02
    db $02
    db $00
}
