; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_BeanVendor
!NbrTiles           = 05  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
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
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_BeanVendor_Prep, Sprite_BeanVendor_Long)

; =========================================================

Sprite_BeanVendor_Long:
{
  PHB : PHK : PLB
  LDA.w SprMiscD, X : BNE +
    JSR Sprite_BeanVendor_Draw
    JSL Sprite_DrawShadow
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w SprSubtype, X : BEQ +
      JSR Sprite_VillageElder_Main
      JMP ++
    +
    JSR Sprite_BeanVendor_Main
    ++
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_BeanVendor_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$40 : STA.w SprTimerA, X
  STZ.w SprMiscD, X

  LDA.b $8A : CMP.b #$00 : BNE +
    LDA.l MagicBeanProg : BNE .in_progress
      LDA.b #$04 : STA.w SprAction, X
      LDA.b #$01 : STA.w SprMiscD, X
      JMP +
    .in_progress
    CMP.b #$3F : BNE .not_flower
      ; Sprite is the flower on ranch map
      LDA.b #$05 : STA.w SprAction, X
      JMP +
    .not_flower
    CMP.b #$7F : BNE .not_done
      STZ.w SprState, X
    .not_done
  +
  PLB
  RTL
}

; =========================================================

Sprite_BeanVendor_Main:
{
  %SpriteJumpTable(BeanVendor,
                   MagicBean,
                   BeanVendor_SpawnMagicBean,
                   BeanVendor_PlayerSaidNo,
                   MagicBean_FertileSoil,
                   MagicBean_RanchFlower)

  BeanVendor:
  {
    %PlayAnimation(0,0,1)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($142) : BCC .no_message
      %GotoAction(2)
    .no_message
    RTS
  }

  MagicBean:
  {
    %SetFrame(1)

    LDA.w SprMiscE, X : CMP.b #$01 : BEQ .not_lifting
      LDA.w $0309 : CMP.b #$02 : BNE .not_lifting
        LDA.b $8A : BEQ +
          JSR MagicBean_BottleLogic
        +
       RTS

    .not_lifting
    LDA.b #Sprite_BeanVendor
    JSL Sprite_CheckCollisionWithSprite
    LDA.w SprMiscF, X : BEQ ++
      STZ.w SprState, X
    ++
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

  BeanVendor_SpawnMagicBean:
  {
    %PlayAnimation(0,0,1)
    LDA $1CE8 : BNE .player_said_no_or_not_enough_rupees
      REP #$20
      LDA.l $7EF360
      CMP.w #$64 ; 100 rupees
      SEP #$30
      BCC .player_said_no_or_not_enough_rupees

        REP #$20
        LDA.l $7EF360
        SEC
        SBC.w #$64 ; Subtract 100 rupees
        STA.l $7EF360
        SEP #$30

        LDA.w SprX, X : CLC : ADC.b #$16 : STA $00
        LDA.w SprY, X : STA $02
        LDA.w SprYH, X : STA $03
        LDA.w SprXH, X : STA $01
        LDA.b #$07
        JSL   Sprite_SpawnDynamically
        JSL   Sprite_SetSpawnedCoords
        LDA.b #$01 : STA.w SprAction, Y

        ; TODO: Set a flag that says you've got the magic bean
        %ShowUnconditionalMessage($145)
        %GotoAction(0)
        RTS
    .player_said_no_or_not_enough_rupees
    %GotoAction(3)
    RTS
  }

  BeanVendor_PlayerSaidNo:
  {
    %PlayAnimation(0,0,1)
    %ShowUnconditionalMessage($144)
    %GotoAction(0)
    RTS
  }

  MagicBean_FertileSoil:
  {
    LDA.b #Sprite_BeanVendor : STA.b $00
    JSL Sprite_CheckForPresence : BCC +
      PHX
      LDA.b $02 : TAX
      JSL Sprite_SetupHitBox
      PLX
      JSL Sprite_SetupHitBox_Alt
      JSL CheckIfHitBoxesOverlap : BCC +
        INC.w SprAction, X
        LDA.l MagicBeanProg
        ORA.b #$01
        STA.l MagicBeanProg
        STZ.w SprMiscD, X
    +
    RTS
  }

  MagicBean_RanchFlower:
  {
    ; Check for the good bee
    LDA.l MagicBeanProg : AND.b #$02 : BEQ +
      LDA.b #$B2 : STA.b $00
      ; bee sprite ID
      JSL Sprite_CheckForPresence : BCC +
        PHX
        LDA.b $02 : TAX
        JSL Sprite_SetupHitBox
        PLX
        JSL Sprite_SetupHitBox_Alt
        JSL CheckIfHitBoxesOverlap : BCC +
          LDA.l MagicBeanProg
          ORA.l #$02
          STA.l MagicBeanProg
          ; Set a timer and maybe a jingle effect?
    +
    AND.b #$3F : BEQ ++
      LDA.b #$04 : STA.w SprFrame, X
    ++
    RTS
  }
}

ReleaseMagicBean:
{
  ; X is the bottle ID
  LDA.b $8A : CMP.b #$00 : BNE .not_the_ranch
    LDA.b #$07
    JSL Sprite_SpawnDynamically : BMI .not_the_ranch
      LDA $20 : STA.w SprY, Y
      LDA $21 : STA.w SprYH, Y
      LDA $22 : STA.w SprX, Y
      LDA $23 : STA.w SprXH, Y
      LDA.b #$01 : STA.w SprAction, Y
      LDA.b #$02 : STA.l $7EF35C, X
      RTL
  .not_the_ranch
  %ShowUnconditionalMessage($030)
  RTL
}

MagicBean_BottleLogic:
{
  LDA.l $7EF35C : CMP.b #$02 : BEQ .bottle1_available
  LDA.l $7EF35D : CMP.b #$02 : BEQ .bottle2_available
  LDA.l $7EF35E : CMP.b #$02 : BEQ .bottle3_available
  LDA.l $7EF35F : CMP.b #$02 : BEQ .bottle4_available

    %ShowUnconditionalMessage($033)
    JMP .return

  .bottle1_available
  LDA.b #$09 : STA.l $7EF35C
  %ShowUnconditionalMessage($034)
  JMP .finish_storage

  .bottle2_available
  LDA.b #$09 : STA.l $7EF35D
  %ShowUnconditionalMessage($034)
  JMP .finish_storage

  .bottle3_available
  LDA.b #$09 : STA.l $7EF35E
  %ShowUnconditionalMessage($034)
  JMP .finish_storage

  .bottle4_available
  LDA.b #$09 : STA.l $7EF35F
  %ShowUnconditionalMessage($034)
  .finish_storage
  LDA.b #$01 : STA.w SprMiscE, X
  STZ.w SprState, X
  .return
  RTS
}

; =========================================================

Sprite_BeanVendor_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
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


  ; =======================================================
  .start_index
  db $00, $04, $05, $0B, $11
  .nbr_of_tiles
  db 3, 0, 5, 5, 3
  .x_offsets
  dw -4, 4, 4, -4
  dw 0
  dw -4, -4, 4, 4, -4, -4
  dw -4, -4, 4, 4, -4, -4
  dw -8, 8, -8, 8 ; Flower
  .y_offsets
  dw 4, 4, -4, -4
  dw 0
  dw 4, -4, 4, -4, 8, 16
  dw -4, 4, 4, -4, 8, 16
  dw 8, 8, -8, -8 ; Flower
  .chr
  db $A8, $A9, $99, $98
  db $A6
  db $9B, $8B, $9B, $8B, $BB, $BC
  db $8B, $8D, $8D, $8B, $BB, $BC
  db $A8, $A8, $A4, $A4 ; Flower
  .properties
  db $3B, $3B, $3B, $3B
  db $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  db $3B, $7B, $3B, $7B ; Flower
  .sizes
  db $02, $02, $02, $02
  db $02
  db $02, $02, $02, $02, $00, $00
  db $02, $02, $02, $02, $00, $00
  db $02, $02, $02, $02 ; Flower
}
