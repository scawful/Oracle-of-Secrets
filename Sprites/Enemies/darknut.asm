; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Darknut
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 12  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 12  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Darknut_Prep, Sprite_Darknut_Long)

; =========================================================

Sprite_Darknut_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Darknut_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Darknut_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_Darknut_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #%01100000 : STA.w SprTileDie, X
  PLB
  RTL

  .health
    db $04, $06, $08, $0A
}

; =========================================================

DarknutSpeed = 04

Sprite_Darknut_Main:
{
  LDA.w POSX : STA $02
  LDA.w POSY : STA $03
  LDA.w SprX, X : STA $04
  LDA.w SprY, X : STA $05
  JSL GetDistance8bit_Long : CMP.b #$80 : BCS .no_probe
    ; JSL Sprite_SendOutProbe
    JSL Sprite_SpawnProbeAlways_long
  .no_probe

  ; TODO: Setup parrying sword gfx
  JSL Guard_ParrySwordAttacks

  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long

  JSL Sprite_CheckIfRecoiling

  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
    LDA.b #$FF : STA.w SprTimerD, X
  .no_dano

  LDA.w SprTimerA, X : BEQ +
    LDA.b #$90 : STA.w SprTimerD, X
  +
  LDA.w SprTimerD, X : BEQ ++
    LDA.b #$08 : JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_DirectionToFacePlayer
    TYA
    STA.w SprMiscC, X
    STA.w SprMiscE, X
    STA.w SprAction, X
    JSL Guard_ChaseLinkOnOneAxis
    JMP +++
  ++
  JSR Sprite_Darknut_BasicMove
  +++

  JSR Goriya_HandleTileCollision

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw FaceRight
  dw FaceLeft
  dw FaceDown
  dw FaceUp

  FaceUp:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  FaceDown:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  FaceLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  FaceRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }
}

Sprite_Darknut_BasicMove:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw MoveRight
  dw MoveLeft
  dw MoveDown
  dw MoveUp

  MoveUp:
  {
    LDA.b #-DarknutSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    RTS
  }

  MoveDown:
  {
    LDA.b #DarknutSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    RTS
  }

  MoveLeft:
  {
    LDA.b #-DarknutSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
  }

  MoveRight:
  {
    LDA.b #DarknutSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
  }
}

; =========================================================

Sprite_Darknut_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08

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

  LDA.w .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =======================================================
  .start_index
  db $00, $03, $06, $09, $0C, $0E, $10, $12
  .nbr_of_tiles
  db 2, 2, 2, 2, 1, 1, 1, 1
  .x_offsets
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, -12
  dw 0, -12
  dw 0, 12
  dw 0, 12
  .y_offsets
  dw -4, 0, -12
  dw -4, 0, -12
  dw 0, 12, 20
  dw 0, 12, 20
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
  .chr
  db $EF, $E6, $FF
  db $EF, $E6, $FF
  db $E2, $EF, $FF
  db $E2, $EF, $FF
  db $E0, $E8
  db $E4, $E8
  db $E0, $E8
  db $E4, $E8
  .properties
  db $B9, $39, $B9
  db $B9, $79, $B9
  db $39, $39, $39
  db $79, $39, $39
  db $39, $79
  db $39, $79
  db $79, $39
  db $79, $39
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02

}
