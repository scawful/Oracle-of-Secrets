; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_ThunderGhost
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 10  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
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
%Set_Sprite_Properties(Sprite_ThunderGhost_Prep, Sprite_ThunderGhost_Long)

; =========================================================

Sprite_ThunderGhost_Long:
{
  PHB : PHK : PLB
  ; Skip the body while in the vanilla dying state (SpriteModule_Die, $0DD0 == 6)
  ; so it cannot cover the death poof; see Sprite_Octorok_Long for details.
  LDA.w SprState, X : CMP.b #$06 : BEQ +
  JSR Sprite_ThunderGhost_Draw
  LDA.w SprAction, X : CMP.b #$03 : BCS +
    JSL Sprite_DrawShadow
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_ThunderGhost_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_ThunderGhost_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : BEQ +
    DEC A
  +
  TAY
  LDA.w .health, Y : STA.w SprHealth, X
  LDA.b #$08 : STA.w SprTimerB, X
  LDA.b #$08 : STA.w SprTimerA, X
  PLB
  RTL

  .health
    db $06, $0A, $0C, $10
}

; =========================================================

Sprite_ThunderGhost_Main:
{
  %SpriteJumpTable(ThunderGhostFaceForward,
                   ThunderGhostLeft,
                   ThunderGhostRight,
                   CastThunderLeft,
                   CastThunderRight)

  ThunderGhostFaceForward:
  {
    %PlayAnimation(0, 1, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  ThunderGhostLeft:
  {
    %PlayAnimation(2, 3, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  ThunderGhostRight:
  {
    %PlayAnimation(4, 5, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  CastThunderLeft:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 6, 16)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_MoveLong
    JSL Sprite_CheckTileCollision
    LDA.w SprCollision, X : BNE .despawn
    LDA.w SprTimerA, X : BNE .alive
    .despawn
      STZ.w SprState, X
    .alive
    RTS
  }

  CastThunderRight:
  {
    %StartOnFrame(7)
    %PlayAnimation(7, 7, 16)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_MoveLong
    JSL Sprite_CheckTileCollision
    LDA.w SprCollision, X : BNE .despawn
    LDA.w SprTimerA, X : BNE .alive
    .despawn
      STZ.w SprState, X
    .alive
    RTS
  }
}

Sprite_ThunderGhost_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling
  LDA.w SprTimerC, X : BNE ++
    JSL GetRandomInt : AND #$3F : BNE ++
      LDA.b #$40 : STA.w SprTimerC, X
      JSR SpawnLightningAttack
  ++

  LDA.w SprTimerA, X : BNE .Continue
    JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight
      %GotoAction(1)
      BRA .ResetFaceTimer
    .ToRight
    %GotoAction(2)
  .ResetFaceTimer
    LDA.b #$20 : STA.w SprTimerA, X
  .Continue

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw ThunderGhostMove

  ThunderGhostMove:
  {
    JSL GetRandomInt : AND.b #$03
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_CheckTileCollision

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    RTS
  }
}

SpawnLightningAttack:
{
  PHX
  LDA.b #$CD
  JSL Sprite_SpawnDynamically : BPL .spawned
    PLX
    RTS
  .spawned
    ; Y = spawned lightning bolt slot, X = parent Thunder Ghost slot.
    ; Save child slot before Sprite_IsToRightOfPlayer overwrites Y.
    PHY
    JSL Sprite_IsToRightOfPlayer
    TYA ; 1 = Link is left of ghost -> CastThunderLeft (3); 0 = right -> CastThunderRight (4)
    PLY
    CMP.b #$00 : BNE .cast_left
      ; CastThunderRight (action 4, frame 7), spawn at (SprX+12, SprY+12)
      LDA.b #$04 : STA.w SprSubtype, Y : STA.w SprAction, Y
      LDA.b #$07 : STA.w SprFrame, Y
      LDA.w SprX, X : CLC : ADC.b #$0C : STA.w SprX, Y
      LDA.w SprXH, X : ADC.b #$00 : STA.w SprXH, Y
      BRA .place_y
    .cast_left
      ; CastThunderLeft (action 3, frame 6), spawn at (SprX-12, SprY+12)
      LDA.b #$03 : STA.w SprSubtype, Y : STA.w SprAction, Y
      LDA.b #$06 : STA.w SprFrame, Y
      LDA.w SprX, X : SEC : SBC.b #$0C : STA.w SprX, Y
      LDA.w SprXH, X : SBC.b #$00 : STA.w SprXH, Y
    .place_y
    LDA.w SprY, X : CLC : ADC.b #$0C : STA.w SprY, Y
    LDA.w SprYH, X : ADC.b #$00 : STA.w SprYH, Y

    ; Match parent floor and configure clean projectile hitbox/impervious/lifetime.
    LDA.w SprFloor, X : STA.w SprFloor, Y
    LDA.b #$02 : STA.w SprHitbox, Y
    LDA.b #$03 : STA.w SprNbrOAM, Y
    LDA.b #$40 : STA.w SprGfxProps, Y
    LDA.b #$56 : STA.w SprDefl, Y
    LDA.b #$01 : STA.w SprTileDie, Y
    LDA.b #$FF : STA.w SprBulletproof, Y
    LDA.b #$40 : STA.w SprHealth, Y
    LDA.b #$04 : STA.w SprBump, Y
    LDA.b #$38 : STA.w SprTimerA, Y
    LDA.b #$00
    STA.w SprTimerB, Y
    STA.w SprCollision, Y
    STA.w SprXRound, Y
    STA.w SprYRound, Y

    ; Aim child projectile toward Link from its spawn coordinates.
    PHX
    TYX
    LDA.b #$18 : JSL Sprite_ApplySpeedTowardsPlayer
    PLX

  PLX

  RTS
}

; =========================================================

Sprite_ThunderGhost_Draw:
{
  %DrawSprite()

  .start_index
  db $00, $03, $06, $09, $0C, $0F, $12, $15
  .nbr_of_tiles
  db 2, 2, 2, 2, 2, 2, 2, 2
  .x_offsets
  dw 0, 0, 8
  dw 8, 0, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw 0, 4, -4
  dw 0, 4, 8
  .y_offsets
  dw -8, 0, -8
  dw -8, 0, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, 12, 8
  dw 0, 12, 0
  .chr
  db $3A, $02, $3B
  db $3A, $02, $3B
  db $20, $00, $01
  db $22, $10, $11
  db $20, $00, $01
  db $22, $10, $11
  db $28, $2A, $2B
  db $28, $2A, $2B
  .properties
  db $2B, $2B, $2B
  db $6B, $6B, $6B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $6B, $6B, $6B
  db $6B, $6B, $6B
  db $2B, $2B, $2B
  db $6B, $2B, $2B
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
}
