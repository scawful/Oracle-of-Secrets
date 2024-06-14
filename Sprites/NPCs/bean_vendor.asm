; ========================================================= 
; Sprite Properties
; ========================================================= 

!SPRID              = $07 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 00  ; Number of tiles used in a frame
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
%Set_Sprite_Properties(Sprite_BeanVendor_Prep, Sprite_BeanVendor_Long)

; =========================================================

Sprite_BeanVendor_Long:
{
  PHB : PHK : PLB

  LDA.w SprSubtype, X : CMP.b #$05 : BNE .NotGaebora
    JSR Sprite_KaeoporaGaebora_Draw
    JMP .HandleSprite
  .NotGaebora
  JSR Sprite_BeanVendor_Draw
  .HandleSprite
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_BeanVendor_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================

Sprite_BeanVendor_Prep:
{
  PHB : PHK : PLB
    
  LDA.w SprSubtype, X : STA SprAction, X

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
  dw KaeoporaGaebora

  ; 0x00 - Bean Vendor
  BeanVendor:
  {
    %PlayAnimation(0,0,1)

    JSL Sprite_PlayerCantPassThrough

    %ShowSolicitedMessage($142) : BCC .no_message
      LDA $1CE8 : BNE .player_said_no
        %GotoAction(3)
        RTS
      .player_said_no
      %GotoAction(4)
    .no_message
    RTS
  }

  
  ; 0x01 - Liftable Magic Bean
  MagicBean:
  {
    %PlayAnimation(1,1,1)
    
    JSL Sprite_CheckIfLifted
    
    RTS
  }

  ; 0x02 - Village Elder
  VillageElder:
  {
    %PlayAnimation(2,3,8)
    JSL Sprite_PlayerCantPassThrough

    %ShowSolicitedMessage($143) : BCC .no_message
    
    .no_message

    RTS
  }

  ; 0x03 - Spawn Magic Bean
  SpawnMagicBean:
  {
    %PlayAnimation(0,0,1)

    LDA.b #$07 
    JSL Sprite_SpawnDynamically
    LDA.b #$02 : STA.w SprAction, Y
    LDA.w SprX, X : CLC : ADC.b #$08 : STA $00
    LDA.w SprY, X : STA $02
    LDA.w SprYH, X : STA $03
    LDA.w SprXH, X : STA $01
    ; TODO: Set a flag that says you've got the magic bean
    %ShowUnconditionalMessage($144)
    %GotoAction(0)
    RTS
  }

  ; 0x04 - Player Said No
  PlayerSaidNo:
  {
    %PlayAnimation(0,0,1)
    %ShowUnconditionalMessage($145)
    %GotoAction(0)
    RTS
  }

  ; 0x05 - Kaeopora Gaebora
  KaeoporaGaebora:
  {
    %PlayAnimation(0,0,1)
    RTS 
  }
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
  db $00, $04, $05, $0B
  .nbr_of_tiles
  db 3, 0, 5, 5
  .x_offsets
  dw -4, 4, 4, -4
  dw 0
  dw -4, -4, 4, 4, -4, -4
  dw -4, -4, 4, 4, -4, -4
  .y_offsets
  dw 4, 4, -4, -4
  dw 0
  dw 4, -4, 4, -4, 8, 16
  dw -4, 4, 4, -4, 8, 16
  .chr
  db $A8, $A9, $99, $98
  db $A6
  db $9B, $8B, $9B, $8B, $BB, $BC
  db $8B, $8D, $8D, $8B, $BB, $BC
  .properties
  db $3B, $3B, $3B, $3B
  db $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  .sizes
  db $02, $02, $02, $02
  db $02
  db $02, $02, $02, $02, $00, $00
  db $02, $02, $02, $02, $00, $00
}

Sprite_KaeoporaGaebora_Draw:
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


  ; ========================================================= 
  .start_index
  db $00
  .nbr_of_tiles
  db 3
  .x_offsets
  dw -8, -8, 8, 8
  .y_offsets
  dw 0, -16, 0, -16
  .chr
  db $AE, $8E, $AE, $8E
  .properties
  db $3B, $3B, $7B, $7B
  .sizes
  db $02, $02, $02, $02
}