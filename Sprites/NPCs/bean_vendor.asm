; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_BeanVendor
!NbrTiles           = 04  ; Number of tiles used in a frame
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
  JSR Sprite_BeanVendor_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_BeanVendor_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_BeanVendor_Prep:
{
  PHB : PHK : PLB

  LDA.b #$80 : STA.w SprDefl, X ; Persist in dungeons
  LDA.b #$40 : STA.w SprTimerA, X
  LDA.w SprSubtype, X : STA.w SprAction, X
  CMP.b #$02 : BEQ .OldMan

  LDA.b $8A : CMP.b #$00 : BEQ .RanchFlower

  .OldMan
  PLB
  RTL

  .RanchFlower
  LDA.b #$05 : STA.w SprAction, X
  PLB
  RTL
}

; =========================================================

Sprite_BeanVendor_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw BeanVendor
  dw MagicBean
  dw VillageElder
  dw SpawnMagicBean
  dw PlayerSaidNo
  dw MagicBean_RanchFlower

  ; 0x00 - Bean Vendor
  BeanVendor:
  {
    %PlayAnimation(0,0,1)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($142) : BCC .no_message
      %GotoAction(3)
    .no_message
    RTS
  }


  ; 0x01 - Liftable Magic Bean
  MagicBean:
  {
    %StartOnFrame(1)
    %PlayAnimation(1,1,1)

    ; TODO: Finish bottle logic
    LDA.w SprMiscE, X : CMP.b #$01 : BEQ .not_lifting
    LDA.w $0309 : CMP.b #$02 : BNE .not_lifting

      LDA.l $7EF35C : CMP.b #$02 : BEQ .bottle1_available
      LDA.l $7EF35D : CMP.b #$02 : BEQ .bottle2_available
      LDA.l $7EF35E : CMP.b #$02 : BEQ .bottle3_available
      LDA.l $7EF35F : CMP.b #$02 : BEQ .bottle4_available

      %ShowUnconditionalMessage($033)
      JMP .not_lifting

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
      RTS

    .not_lifting
    JSL Sprite_CheckIfLifted

    RTS
  }

  ; 0x02 - Village Elder
  VillageElder:
  {
    %PlayAnimation(2,3,16)
    JSL Sprite_PlayerCantPassThrough
    REP #$30
    LDA.l $7EF3C7 : AND.w #$00FF
    SEP #$30
    CMP.b #$07 : BCS .already_met
      %ShowSolicitedMessage($143) : BCC .no_message
        LDA.b #$02 : STA.l $7EF3C7
      .no_message
      RTS

    .already_met
    %ShowSolicitedMessage($019)
    RTS
  }

  ; 0x03 - Spawn Magic Bean
  SpawnMagicBean:
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
    %GotoAction(4)
    RTS
  }

  ; 0x04 - Player Said No
  PlayerSaidNo:
  {
    %PlayAnimation(0,0,1)
    %ShowUnconditionalMessage($144)
    %GotoAction(0)
    RTS
  }

  MagicBean_RanchFlower:
  {
    LDA.b #$04 : STA.w SprFrame, X
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }
}

ReleaseMagicBean:
{
  ; X is the bottle ID
  LDA.b $8A : CMP.b #$00 : BNE .not_the_ranch
    LDA.b #$07
    JSL Sprite_SpawnDynamically
    BMI .not_the_ranch

    LDA $20 : STA.w SprY, Y
    LDA $21 : STA.w SprYH, Y
    LDA $22 : STA.w SprX, Y
    LDA $23 : STA.w SprXH, Y

    LDA.b #$01 : STA.w SprAction, Y
    STA.w SprSubtype, Y
    LDA.b #$02 : STA.l $7EF35C, X
    RTL

  .not_the_ranch
  %ShowUnconditionalMessage($030)
  RTL
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
