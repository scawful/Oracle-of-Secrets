; =========================================================
; Sprite Properties
; =========================================================
!SPRID              = $9E ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 00  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 01   ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_MakuTree_Prep, Sprite_MakuTree_Long)

; =========================================================

Sprite_MakuTree_Long:
{
    PHB : PHK : PLB

    JSR Sprite_MakuTree_Draw ; Call the draw code
    JSL Sprite_CheckActive   ; Check if game is not paused
    BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

    JSR Sprite_MakuTree_Main ; Call the main sprite code

  .SpriteIsNotActive
    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code
}
; =========================================================

Sprite_MakuTree_Prep:
{
    PHB : PHK : PLB
    ; Check if the intro has executed already.
    LDA.l $7EF300 : BNE .intro_is_done
      STZ.w $0DD0, X ; Kill the sprite 
  .intro_is_done
    PLB
    RTL
}

; =========================================================

Sprite_MakuTree_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw MakuTree_Handler
  dw MakuTree_MeetLink
  dw MakuTree_GiveMoonPearl

  MakuTree_Handler:
  {
      ; Check the progress flags 
      LDA $7EF3D4 : CMP.b #$01 : BEQ .has_met_link
      %GotoAction(1)
      RTS

    .has_met_link
      %ShowSolicitedMessage($22) 
      RTS
  }

  MakuTree_MeetLink:
  {
      %ShowSolicitedMessage($20) : BCC .no_talk
      LDA #$01 : STA $7EF3D4
      LDA #$06 : STA $7EF3C7
      %GotoAction(2)
    .no_talk
      RTS
  }

  MakuTree_GiveMoonPearl:
  {
      ; Give Link the Moon Pearl
      LDY #$1F : JSL Link_ReceiveItem
      %GotoAction(0)
      RTS
  }

}

; =========================================================

Sprite_MakuTree_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06


  PHX
  LDX   .nbr_of_tiles, Y ;amount of tiles -1
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
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
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
.nbr_of_tiles
.x_offsets
.y_offsets
.chr
.properties
.sizes

}

