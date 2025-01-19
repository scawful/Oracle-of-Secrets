; Tingle Sprite

!SPRID              = $22
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 02  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Tingle_Prep, Sprite_Tingle_Long)

Sprite_Tingle_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Tingle_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Tingle_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Tingle_Prep:
{
  PHB : PHK : PLB

  PLB
  RTL
}

Sprite_Tingle_Main:
{
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Tingle_Forward
  dw Tingle_Right
  dw Tingle_Left
  dw Tingle_MapPrompt
  dw Tingle_MapSales
  dw Tingle_PlayerSaidNo

  Tingle_Forward:
  {
    %PlayAnimation(0,0,10)
    JSR Sprite_Tingle_TrackPlayer
    RTS
  }

  Tingle_Right:
  {
    %PlayAnimation(1,1,10)
    JSR Sprite_Tingle_TrackPlayer
    RTS
  }

  Tingle_Left:
  {
    %PlayAnimation(2,2,10)
    JSR Sprite_Tingle_TrackPlayer
    RTS
  }

  Tingle_MapPrompt:
  {
    %PlayAnimation(0,0,10)
    LDA $1CE8 : BNE .said_no
      PHX
      LDA.l TingleId : ASL : TAX
      LDY.b #$01
      LDA.w .message_ids, X
      JSL Sprite_ShowMessageUnconditional
      PLX
      LDA.l TingleId : CMP.b #$07 : BEQ +
        %GotoAction(4)
        RTS
      +
      %GotoAction(0)
      RTS
    .said_no
    %GotoAction(5)
    RTS
    .message_ids
    dw $0191
    dw $0192
    dw $0193
    dw $0194
    dw $0195
    dw $0196
    dw $0197
    dw $0190
  }

  Tingle_MapSales:
  {
    %PlayAnimation(0,0,10)
    LDA $1CE8 : BNE .said_no
      REP #$20
      LDA.l TingleId : ASL : TAY
      LDA.l $7EF360 : CMP.w .cost, Y
      SEP #$30
      BCC .not_enough_rupees
        REP #$20
        LDA.l $7EF360 : SEC : SBC.w .cost, Y
        STA.l $7EF360
        SEP #$30
        LDA.l TingleMaps
        ORA.w .dungeon, Y
        STA.l TingleMaps
        LDA.l TingleId : INC A : STA.l TingleId
        %ShowUnconditionalMessage($018E) ; Purchased
        STZ.w SprAction, X
        RTS
      .not_enough_rupees
      %ShowUnconditionalMessage($018F) ; Not enough rupees
      STZ.w SprAction, X
      RTS
    .said_no
    %GotoAction(5)
    RTS

    .cost
    dw 50
    dw 75
    dw 100
    dw 80
    dw 90
    dw 60
    dw 120
    .dungeon
    db 01
    db 02
    db 04
    db 08
    db 16
    db 32
    db 64
  }

  Tingle_PlayerSaidNo:
  {
    %ShowUnconditionalMessage($0198)
    STZ.w SprAction, X
    RTS
  }
}

Sprite_Tingle_TrackPlayer:
{
  %ShowSolicitedMessage($018D) : BCC +
    %GotoAction(3)
    RTS
  +
  JSL Sprite_IsBelowPlayer : TYA : BEQ .below
    JSL Sprite_IsToRightOfPlayer : TYA : BNE .right
      LDA.b #$02 : STA.w SprAction, X
        JMP +
    .right
    LDA.b #$01 : STA.w SprAction, X
    JMP +
  .below
  STZ.w SprAction, X
  +
  RTS
}

Sprite_Tingle_Draw:
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

  .start_index
  db $00, $02, $04
  .nbr_of_tiles
  db 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -16, 0
  dw -16, 0
  dw -16, 0
  .chr
  db $C6, $E6
  db $C4, $E4
  db $C4, $E4
  .properties
  db $3B, $3B
  db $3B, $3B
  db $7B, $7B
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
}
