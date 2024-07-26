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

  JSR Sprite_Puffstool_Draw ; Call the draw code
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Puffstool_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
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
  db $0A, $10, $1A, $20
}

; =========================================================

Sprite_Puffstool_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Puffstool_Walking
  dw Puffstool_Stunned

  dw Puffstool_Spores

  Puffstool_Walking:
  {
    %PlayAnimation(0,6,10)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA, X : BNE +
      JSL Sprite_SelectNewDirection
    +
    
    JSL Sprite_MoveXyz
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_BounceOffWall
    JSL Sprite_DamageFlash_Long
    JSL ThrownSprite_TileAndSpriteInteraction_long

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
    JSL Sprite_MoveXyz
    JSL Sprite_CheckDamageToPlayerSameLayer

    LDA.w SprTimerC, X : BNE + 
      STZ.w SprState, X
    +
    RTS
  }
}

Puffstool_SpawnSpores:
{
  LDA.b #$0C ; SFX2.0C
  JSL $0DBB7C ; SpriteSFX_QueueSFX2WithPan

  LDA.b #$03
  STA.b $0D

  .nth_child
  LDA.b #$B1 ; SPRITE 10
  JSL Sprite_SpawnDynamically
  BMI .no_space

  JSL Sprite_SetSpawnedCoordinates

  PHX

  LDX.b $0D

  LDA.w .speed_x,X
  STA.w $0D50,Y

  LDA.w .speed_y,X
  STA.w $0D40, Y

  LDA.b #$30
  STA.w $0F80, Y

  LDA.b #$FF
  STA.w $0E80, Y

  LDA.b #$40 : STA.w SprTimerC, Y

  LDA.b #$01
  STA.w SprSubtype, Y

  LDA.b #$02
  STA.w SprAction, Y

  PLX

  .no_space
  DEC.b $0D
  BPL .nth_child
  RTS

.speed_x
  db  16, -11, -16, 11

.speed_y
  db   0,  11,   0, -11
}

; =========================================================

Sprite_Puffstool_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08 ; Palette damage flash

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

  ; =========================================================

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
