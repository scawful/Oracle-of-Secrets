; Piratian

!SPRID              = $0E
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
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
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Piratian_Prep, Sprite_Piratian_Long)

Sprite_Piratian_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Piratian_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Piratian_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Piratian_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  STZ.w SprMiscA, X
  LDA.w SprNbrOAM, X : ORA.b #$80 : STA.w SprNbrOAM, X
  PLB
  RTL

  .health
    db $08, $0A, $0C, $0F
}

Sprite_Piratian_Main:
{
  JSR Sprite_Piratian_Move

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Piratian_MoveDown
  dw Piratian_MoveUp
  dw Piratian_MoveLeft
  dw Piratian_MoveRight
  dw SkullHead

  Piratian_MoveDown:
  {
    %PlayAnimation(0,1,16)
    RTS
  }

  Piratian_MoveUp:
  {
    %PlayAnimation(2,3,16)
    RTS
  }

  Piratian_MoveLeft:
  {
    %PlayAnimation(4,5,16)
    RTS
  }

  Piratian_MoveRight:
  {
    %PlayAnimation(6,7,16)
    RTS
  }

  SkullHead:
  {
    %PlayAnimation(8,9,16)
    RTS
  }
}

Sprite_Piratian_Move:
{
  LDA.w SprTimerA, X : BNE +
    JSL Sprite_SelectNewDirection
    TYA
    CMP.b #$03 : BCC ++
      SEC : SBC.b #$03
    ++
    STA.w SprAction, X
  +

  JSL Sprite_MoveXyz
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_DamageFlash_Long
  JSL ThrownSprite_TileAndSpriteInteraction_long

  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
    LDA.b #$01 : STA.w SprMiscA, X
    LDA.w SprNbrOAM, X : AND.b #$7F : STA.w SprNbrOAM, X
    %SetTimerA($60)
    %SetTimerF($20)
  .no_dano

  LDA.w SprMiscA, X : BEQ .no_aggro
    LDA.b #$10 : STA.w SprTimerA, X
    LDA.b #$08
    JSL Sprite_ProjectSpeedTowardsPlayer
    JSL Sprite_CheckDamageToPlayer
    JMP .return
  .no_aggro

  JSR Sprite_Piratian_Friendly
  .return
  RTS
}

Sprite_Piratian_Friendly:
{
  LDA.w SprTimerD, X : BNE +
    %ShowMessageOnContact($01BB) : BCC +
      LDA.b #$FF : STA.w SprTimerD, X
  +
  RTS
}

Sprite_Piratian_Draw:
{
  %DrawSprite()

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08, $09
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  .chr
  db $8C
  db $8C
  db $8E
  db $8E
  db $AC
  db $AE
  db $AC
  db $AE
  db $0E
  db $2E
  .properties
  db $33
  db $73
  db $33
  db $73
  db $33
  db $33
  db $73
  db $73
  db $33
  db $33
  .sizes
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
}

