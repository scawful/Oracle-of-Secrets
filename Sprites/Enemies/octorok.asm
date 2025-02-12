; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $08
!NbrTiles           = 05  ; Number of tiles used in a frame
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

%Set_Sprite_Properties(Sprite_Octorok_Prep, Sprite_Octorok_Long)

Sprite_Octorok_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Octorok_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w SprSubtype, X : BEQ +
      JSL Sprite_DrawWaterRipple
      JSR Sprite_WaterOctorok_Main
      JMP ++
    +
    JSL Sprite_DrawShadow
    JSR Sprite_Octorok_Main
    ++
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Octorok_Prep:
{
  PHB : PHK : PLB

  PLB
  RTL
}

Sprite_Octorok_Main:
{
  JSR Sprite_Octorok_Move

  ; TILETYPE 08
  LDA.l $7FF9C2,X : CMP.b #$08 : BEQ .water_tile
    ; TILETYPE 09
    CMP.b #$09 : BNE .not_water_tile
  .water_tile
    LDA.b #$01 : STA.w SprSubtype, X
    STZ.w SprAction, X
    STZ.w SprMiscG, X
    RTS
  .not_water_tile

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Octorok_MoveDown
  dw Octorok_MoveUp
  dw Octorok_MoveLeft
  dw Octorok_MoveRight

  Octorok_MoveDown:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  Octorok_MoveUp:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  Octorok_MoveLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  Octorok_MoveRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }
}

Sprite_Octorok_Move:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_Move
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_CheckDamageToPlayer

  ; Set the SprAction based on the direction
  LDA.w SprMiscC, X : AND.b #$03 : TAY
  LDA.w .direction, Y : STA.w SprAction, X

  LDA.w SprMiscF, X : AND.b #$01 : BNE .octorok_used_barrage
    LDA.w SprMiscC, X : AND.b #$02 : ASL A : STA.b $00
    INC.w SprDelay, X
    LDA.w SprDelay, X
    LSR A
    LSR A
    LSR A
    AND.b #$03
    ORA.b $00
    STA.w SprGfx, X

    LDA.w SprTimerA, X : BNE .wait
      INC.w SprMiscF,X

      LDY.w SprType,X
      LDA.w .timer-8,Y : STA.w SprTimerA,X

      RTS

  .wait
  LDY.w SprMiscC, X

  LDA.w .speed_x, Y : STA.w SprXSpeed, X
  LDA.w .speed_y, Y : STA.w SprYSpeed, X

  JSL Sprite_CheckTileCollision
  LDA.w $0E70, X : BEQ .no_collision
    LDA.w SprMiscC,X : EOR.b #$01 : STA.w SprMiscC,X
    BRA .exit
  .no_collision
  RTS

  .octorok_used_barrage
  STZ.w SprXSpeed, X : STZ.w SprYSpeed,X
  LDA.w SprTimerA, X : BNE Octorock_ShootEmUp
    INC.w SprMiscF, X
    LDA.w SprMiscC, X
    PHA
    JSL GetRandomInt : AND.b #$3F : ADC.b #$30 : STA.w SprTimerA, X
    AND.b #$03 : STA.w SprMiscC, X
    PLA
    CMP.w SprMiscC, X : BEQ .exit
      EOR.w SprMiscC, X : BNE .exit
        LDA.b #$08 : STA.w SprTimerB,X
  .exit
  RTS

  .direction
    db   3,   2,   0,   1

  .speed_x
    db  24, -24,   0,   0

  .speed_y
    db   0,   0,  24, -24

  .timer
    db  60, 128, 160, 128
}

Octorock_ShootEmUp:
{
  ; Use SprMiscD as a flag to shoot 4 ways for awhile before going back to single shot

  LDA.w SprMiscD, X : BEQ .continue
    LDA.w SprTimerD, X : BNE .four_ways
      LDA.b #$01 : STA.w SprMiscD, X
  .continue
  JSL GetRandomInt : AND.b #$1F : BNE .single_shot
  .four_ways
    LDA.b #$01 : STA.w SprMiscD, X
    LDA.b #$20 : STA.w SprTimerD, X
    JSR Octorok_Shoot4Ways
    RTS
  .single_shot
  JSR Octorok_ShootSingle
  RTS
}

; =========================================================

Sprite_WaterOctorok_Main:
{
  JSR Sprite_WaterOctorok_Attack

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaterOctorok_FaceDown
  dw WaterOctorok_FaceUp
  dw WaterOctorok_FaceLeft
  dw WaterOctorok_FaceRight
  dw WaterOctorok_FaceHidden

  WaterOctorok_FaceDown:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  WaterOctorok_FaceUp:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  WaterOctorok_FaceLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  WaterOctorok_FaceRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }

  WaterOctorok_FaceHidden:
  {
    %StartOnFrame(8)
    %PlayAnimation(8,8,10)
    RTS
  }
}

Sprite_WaterOctorok_Attack:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckDamageToPlayer

  LDA.w SprMiscG, X
  JSL JumpTableLocal

  dw WaterOctorok_Hidden
  dw WaterOctorok_PoppingUp
  dw WaterOctorok_Attacking
  dw WaterOctorok_Hiding

  WaterOctorok_Hidden:
  {
    LDA.w SprTimerA, X : BEQ +
      RTS
    +

    JSL GetDistance8bit_Long
    CMP.b #$40 : BCC .not_close_enough ; LD < 64
      INC.w SprMiscG, X
      %SetTimerA($10)
    .not_close_enough
    RTS
  }

   WaterOctorok_PoppingUp:
   {
     JSL Sprite_CheckDamageFromPlayer
     LDA.w SprTimerA, X : BNE +
       INC.w SprMiscG, X
       %SetTimerA($20)
       JSL Sprite_DirectionToFacePlayer
       ; LDA.w SprMiscC, X : AND.b #$03 : TAY
       ; LDA.w Sprite_Octorok_Move_direction, Y : STA.w SprAction, X
     +
     RTS
   }

   WaterOctorok_Attacking:
   {
     JSL Sprite_CheckDamageFromPlayer
     LDA.w SprTimerA, X : BNE +
       INC.w SprMiscG, X
       %SetTimerA($10)
       RTS
     +
     JSR Octorok_ShootSingle
     RTS
   }

   WaterOctorok_Hiding:
   {
     LDA.w SprTimerA, X : BNE +
       LDA.b #$04 : STA.w SprAction, X
       STZ.w SprMiscG, X
       %SetTimerA($40)
     +
     RTS
   }
}

; =========================================================

Octorok_ShootSingle:
{
  LDA.w SprTimerA, X : CMP.b #$1C : BNE .bide_time
    PHA
    JSR Octorok_SpawnRock
    PLA
  .bide_time
  LSR #3
  TAY
  LDA.w .mouth_anim_step, Y : STA.w SprMiscB, X
  RTS

  .mouth_anim_step
    db $00, $02, $02, $02
    db $01, $01, $01, $00
    db $00, $00, $00, $00
    db $02, $02, $02, $02
    db $02, $01, $01, $00
}

Octorok_Shoot4Ways:
{
  LDA.w SprTimerA, X
  PHA
  CMP.b #$80 : BCS .animate
    AND.b #$0F : BNE .delay_turn
    PHA
    LDY.w SprMiscC, X
    LDA.w .next_direction, Y : STA.w SprMiscC, X
    PLA
    .delay_turn
    CMP.b #$08 : BNE .animate
      JSR Octorok_SpawnRock
  .animate
  PLA
  LSR #4
  TAY
  LDA.w .mouth_anim_step, Y : STA.w SprMiscB, X
  RTS

  .next_direction
    db $02, $03, $01, $00

  .mouth_anim_step
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $01, $00
}

; =========================================================

Octorok_SpawnRock:
{
  LDA.b #$07 : JSL SpriteSFX_QueueSFX2WithPan
  LDA.b #$0C : JSL Sprite_SpawnDynamically : BMI .fired_a_blank
    PHX

    LDA.w SprMiscC,X
    TAX

    LDA.b $00 : CLC : ADC.w .offset_x_low,X : STA.w SprX,Y
    LDA.b $01 : ADC.w .offset_x_high,X : STA.w SprXH,Y
    LDA.b $02 : CLC : ADC.w .offset_y_low,X : STA.w SprY,Y
    LDA.b $03 : ADC.w .offset_y_high,X : STA.w SprYH,Y

    LDA.w SprMiscC,Y
    TAX

    LDA.w .rock_speed_x,X : STA.w SprXSpeed,Y
    LDA.w .rock_speed_y,X : STA.w SprYSpeed,Y

    PLX
  .fired_a_blank
  RTS

  .offset_x_low
    db  12, -12,   0,   0

  .offset_x_high
    db   0,  -1,   0,   0

  .offset_y_low
    db   4,   4,  12, -12

  .offset_y_high
    db   0,   0,   0,  -1

  .rock_speed_x
    db  44, -44,   0,   0

  .rock_speed_y
    db   0,   0,  44, -44
}

; =========================================================

Sprite_Octorok_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0
  .chr
  db $80
  db $80
  db $82
  db $82
  db $A0
  db $A2
  db $A0
  db $A2
  db $AA ; Water Octorok
  .properties
  db $0D
  db $4D
  db $0D
  db $4D
  db $0D
  db $0D
  db $4D
  db $4D
  db $3D ; Water Octorok
}
