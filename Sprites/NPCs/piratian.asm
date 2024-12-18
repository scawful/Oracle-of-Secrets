; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $0E ; The sprite ID you are overwriting (HEX)
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

; =========================================================

Sprite_Piratian_Prep:
{
  PHB : PHK : PLB

  PLB
  RTL
}

; =========================================================

Sprite_Piratian_Main:
{
  JSR Sprite_Piratian_Move

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

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
  JSL Sprite_BounceOffWall
  JSL Sprite_DamageFlash_Long
  JSL ThrownSprite_TileAndSpriteInteraction_long

  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
    %SetTimerA($60)
    %SetTimerF($20)
  .no_dano

  RTS
}

; =========================================================

Sprite_Piratian_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06


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
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================
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

