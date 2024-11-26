; Happy Mask Salesman Sprite

!SPRID              = Sprite_MaskSalesman
!NbrTiles           = 02 ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 01  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this MaskSalesman (can be 0 to 7)
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

%Set_Sprite_Properties(Sprite_MaskSalesman_Prep, Sprite_MaskSalesman_Long)

Sprite_MaskSalesman_Long:
{
  PHB : PHK : PLB
  JSR Sprite_MaskSalesman_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_MaskSalesman_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_MaskSalesman_Prep:
{
  PHB : PHK : PLB
  PLB
  RTL
}

Sprite_MaskSalesman_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw InquiryHandler
  dw NoOcarina
  dw HasOcarina
  dw TeachLinkSong
  dw OfferBunnyHood
  dw OfferStoneMask
  dw PlayerSaidNoToMask
  dw PlayerHasAllMasks
  dw BoughtBunnyHood
  dw BoughtStoneMask
  dw NotEnoughMoney

  ; 0x00
  InquiryHandler:
  {
    %PlayAnimation(0, 1, 16)
    ; Player has a Lv1 Ocarina, skip to the you got it message
    LDA.l $7EF34C : CMP.b #$01 : BEQ .has_ocarina
      ; Player has no Ocarina or Lv2 Ocarina
      ; Do you want to buy a mask?
      %ShowSolicitedMessage($E5) : BCC .didnt_converse
        LDA $1CE8 : BNE .player_said_no

        ; Player wants to buy a mask
        LDA.l $7EF34C : CMP.b #$02 : BCS .has_song_healing

          ; No Ocarina yet
          %GotoAction(1)
          RTS

    .has_ocarina
    %GotoAction(2)
    RTS

    .has_song_healing
      LDA.l $7EF348 : CMP.b #$01 : BCS .has_bunny_mask
      %GotoAction(4)
      RTS
    .has_bunny_mask
      LDA.l $7EF352 : CMP.b #$01 : BCS .has_stone_mask
      %GotoAction(5)
      RTS
    .has_stone_mask
      %GotoAction(7)
      RTS

    .player_said_no
      %GotoAction(6)
    .didnt_converse
    RTS
  }

  ; 0x01 - Link has not yet gotten the Ocarina
  NoOcarina:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($E9) ; Go get the Ocarina first!
    %GotoAction(0)
    RTS
  }

  ; 0x02 - Link has the Ocarina, but not all the songs
  HasOcarina:
  {
    %PlayAnimation(0, 1, 16)
    %ShowSolicitedMessage($080) ; Oh! You got it!
    %GotoAction(3)
    RTS
  }

  ; 0x03
  TeachLinkSong:
  {
    LDA #$02 : STA $7EF34C ; Increment the number of songs Link has
    LDA.b #$13
    STA.w $0CF8
    JSL $0DBB67 ;  Link_CalculateSFXPan
    ORA.w $0CF8
    STA $012E ; Play the song learned sound
    %GotoAction(0)
    RTS
  }

  ; 0x04 - Offer Bunny Hood
  OfferBunnyHood:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($07F) ; Bunny Hood for 100 rupees?
    %GotoAction(8)
    RTS
  }

  ; 0x05 - Offer Stone Mask
  OfferStoneMask:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($082) ; Stone Mask for 650 rupees?
    %GotoAction(9)
    RTS
  }

  ; 0x06 - Player said no to buying a mask
  PlayerSaidNoToMask:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($E8)
    %GotoAction(0)
    RTS
  }

  ; 0x07 - Player has all the masks
  PlayerHasAllMasks:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($028)
    %GotoAction(0)
    RTS
  }

  BoughtBunnyHood:
  {
    %PlayAnimation(0, 1, 16)
    LDA $1CE8 : BNE .player_said_no
      REP #$20
      LDA.l $7EF360 : CMP.w #$64 ; 100 rupees
      SEP #$30
      BCC .not_enough_rupees

        LDY.b #$10 ; Bunny Hood
        STZ.w $02E9
        PHX
        JSL Link_ReceiveItem
        PLX

        REP #$20
        LDA.l $7EF360
        SEC : SBC.w #$64 ; Subtract 100 rupees
        STA.l $7EF360
        SEP #$30

        %ShowUnconditionalMessage($063)

        %GotoAction(0)
        RTS

      .not_enough_rupees
      %GotoAction($0A)
      RTS
    .player_said_no
    %GotoAction(6)
    RTS
  }

  BoughtStoneMask:
  {
    %PlayAnimation(0, 1, 16)
    LDA $1CE8 : BNE .player_said_no
      REP #$20
      LDA.l $7EF360 : CMP.w #$352 ; 850 rupees
      SEP #$30
      BCC .not_enough_rupees

        LDY #$19 ; Stone Mask
        STZ.w $02E9
        PHX
        JSL Link_ReceiveItem
        PLX

        REP #$20
        LDA.l $7EF360
        SEC : SBC.w #$352 ; Subtract 850 rupees
        STA.l $7EF360
        SEP #$30

        %ShowUnconditionalMessage($055)
        %GotoAction(0)
        RTS

      .not_enough_rupees
      %GotoAction($0A)
      RTS
    .player_said_no
    %GotoAction(6)
    RTS
  }

  NotEnoughMoney:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($029)
    %GotoAction(0)
    RTS
  }
}

Sprite_MaskSalesman_Draw:
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


.start_index
  db $00, $04
.nbr_of_tiles
  db 3, 3
.x_offsets
  dw -4, 12, 0, 0
  dw 4, -12, 0, 0
.y_offsets
  dw -8, -8, 0, -11
  dw -8, -8, 0, -10
.chr
  db $82, $84, $A0, $80
  db $82, $84, $A0, $80
.properties
  db $39, $39, $39, $39
  db $79, $79, $79, $39
.sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02

}
