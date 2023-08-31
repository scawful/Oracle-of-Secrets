;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $XX ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 2   ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 01  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 0   ; 00 to 31, can be viewed in sprite draw tool
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

;==============================================================================

%Set_Sprite_Properties(Sprite_Minecart_Prep, Sprite_Minecart_Long) 

;==============================================================================

Sprite_Minecart_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Minecart_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Minecart_Main ; Call the main sprite code

.SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

;==============================================================================

Sprite_Minecart_Prep:
{
  PHB : PHK : PLB

  PLB
  RTL
}

;==============================================================================

Sprite_Minecart_Main:
{
  LDA.w SprAction, X                        ; Load the SprAction
  JSL   UseImplicitRegIndexedLocalJumpTable ; Goto the SprAction we are currently in

  dw Minecart_Start
  dw Minecart_Waiting

  ; 00
  Minecart_Start:
  {
  
    RTS
  }

  Minecart_Waiting:
  {
    JSR Sprite_Minecraft_CheckIfPlayerIsOn : BCC .not_on_platform
        ;Cancel Falling
    JSL Player_HaltDashAttackLong
    LDA #$00 : STA $5D : STA $5B : STA $57 : STA $5E
    STA $59

  .not_on_platform
    LDA $0E00,            X : BNE + ;wait before moving
    LDA #$10 : STA $0E00, X         ;Wait before checking first tile on ground!
    INC $0D80,            X


    LDA.b #$01 : STA $041A
  +
    RTS 
  }

}

Sprite_Minecraft_CheckPlayerDirection:
{
  REP #$20
  STZ $0B7E : STZ $0B7C ; Not needed propbably
  
  LDA $0DB0,           X : AND #$00FF : ASL : TAY ;Load Direction*2
  LDA SpeedTableWordX, Y : STA $0B7C
  LDA SpeedTableWordY, Y : STA $0B7E

  SEP #$20

  RTS
}

Sprite_Minecraft_CheckIfPlayerIsOn:
{
  REP #$20
  LDA $22 : CLC : ADC #$0009 : CMP $0FD8 : BCC .OutsideLeft
  LDA $22 : SEC : SBC #$002C : CMP $0FD8 : BCS .OutsideRight

  LDA $20 : CLC : ADC #$0012 : CMP $0FDA : BCC .OutsideUp
  LDA $20 : SEC : SBC #$0016 : CMP $0FDA : BCS .OutsideDown
  SEP #$21
  RTS                                                       ;Return with carry setted

.OutsideLeft
.OutsideRight
.OutsideDown
.OutsideUp
  SEP #$20
  CLC : RTS ;Return with carry cleared
}
;==============================================================================

Sprite_Minecart_Draw:
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


; Insert Draw data 
}