; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Vasu
!NbrTiles           = 03 ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
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
%Set_Sprite_Properties(Sprite_Vasu_Prep, Sprite_Vasu_Long)

; =========================================================

Sprite_Vasu_Long:
{
  PHB : PHK : PLB

  LDA.w SprSubtype, X : BNE +
    JSR Sprite_Vasu_Draw
    JMP ++
  +
    JSR Sprite_Error_Draw
  ++
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
  JSR Sprite_Vasu_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_Vasu_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.w SprSubtype, X : BEQ +
    LDA.b #$04 : STA.w SprAction, X
  +
  PLB
  RTL
}

; =========================================================

Sprite_Vasu_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Vasu_Idle
  dw Vasu_MessageHandler
  dw Vasu_AppraiseRing
  dw Vasu_RingAppraised

  dw Error_Idle

  Vasu_Idle:
  {
    %PlayAnimation(0,1,20)
    %ShowSolicitedMessage($00A9) : BCC .didnt_talk
      %GotoAction(1)
    .didnt_talk
    RTS
  }

  Vasu_MessageHandler:
  {
    %PlayAnimation(0,1,20)
    LDA.w MsgChoice : BEQ .appraise_rings
         CMP.b #$01 : BEQ .explain_rings
      ; Player said nevermind.
      %GotoAction(0)
      RTS
    .explain_rings
    %ShowUnconditionalMessage($00AA)
    %GotoAction(0)
    RTS
    .appraise_rings
    LDA.b #$40 : STA.w SprTimerB, X
    %GotoAction(2)
    RTS
  }

  Vasu_AppraiseRing:
  {
    %PlayAnimation(0,1,20)

    ; Check if the player has found any rings to appraise
    REP #$30
    LDA.l FOUNDRINGS
    AND.w #$00FF
    SEP #$30
    BEQ .no_rings
      ; Check if the player has any rings, if not give them one for free
      LDA.l MAGICRINGS : BEQ .no_rings_yet
        REP #$20
        LDA.l $7EF360
        CMP.w #$14 ; 20 rupees
        SEP #$30
        BCC .not_enough_rupees

          REP #$20
          LDA.l $7EF360
          SEC
          SBC.w #$14 ; Subtract 20 rupees
          STA.l $7EF360
          SEP #$30

          JMP .appraise_me

        .not_enough_rupees
          %ShowUnconditionalMessage($0189) ; 'You don't have enough rupees!'
          %GotoAction(0)
          RTS

      .no_rings_yet
      %ShowUnconditionalMessage($00AB) ; 'First one is free!'
      JMP .appraise_me

    .no_rings
    %ShowUnconditionalMessage($00AD) ; 'You don't have any rings!'
    %GotoAction(0)
    RTS

    .appraise_me
    ; Check the found rings and set the saved rings
    ; Get the bit from found rings and set it in MAGICRINGS
    LDA.l FOUNDRINGS
    ORA.l MAGICRINGS
    STA.l MAGICRINGS

    %GotoAction(3)

    RTS
  }

  Vasu_RingAppraised:
  {
    %PlayAnimation(0,1,20)
    %ShowUnconditionalMessage($00AC) ; 'Come back later for more appraisals!'

    %GotoAction(0)
    RTS
  }

  Error_Idle:
  {
    %PlayAnimation(0,1,24)
     ; "I am Error"
    %ShowSolicitedMessage($0121) : BCC +
      JSL GetRandomInt : AND.b #$06 : STA.l FOUNDRINGS
    +
    RTS
  }
}

; =========================================================

Sprite_Vasu_Draw:
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
  db $00, $02
  .nbr_of_tiles
  db 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw 0, -16
  dw 0, -16
  .chr
  db $20, $00
  db $20, $00
  .properties
  db $3B, $3B
  db $7B, $7B
  .sizes
  db $02, $02
  db $02, $02
}

; =========================================================

Sprite_Error_Draw:
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
  db $00, $01
  .nbr_of_tiles
  db 0, 0
  .x_offsets
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  .chr
  db $80
  db $80
  .properties
  db $39
  db $79
  .sizes
  db $02
  db $02
}
