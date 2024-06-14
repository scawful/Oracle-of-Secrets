; ========================================================= 
; Sprite Properties
; ========================================================= 

!SPRID              = $00 ; The sprite ID you are overwriting (HEX)
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

%Set_Sprite_Properties(Sprite_Darknut_Prep, Sprite_Darknut_Long)

; =========================================================

Sprite_Darknut_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Darknut_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Darknut_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================

Sprite_Darknut_Prep:
{
  PHB : PHK : PLB
    

  PLB
  RTL
}

; =========================================================

DarknutSpeed = $04

Sprite_Darknut_Main:
{
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in
  dw MoveDown
  dw MoveUp
  dw MoveLeft
  dw MoveRight


  MoveDown:
  {
    %PlayAnimation(0,1,10)
    LDA #DarknutSpeed : STA.w SprSpeedY, X
    JSL Sprite_Move
    RTS
  }

  MoveUp:
  {
    %PlayAnimation(2,3,10)
    LDA #-DarknutSpeed : STA.w SprSpeedY, X
    JSL Sprite_Move
    RTS
  }

  MoveLeft:
  {
    %PlayAnimation(4,5,10)
    LDA #-DarknutSpeed : STA.w SprSpeedX, X
    JSL Sprite_Move
    RTS
  }

  MoveRight:
  {
    %PlayAnimation(6,7,10)
    LDA #DarknutSpeed : STA.w SprSpeedX, X
    JSL Sprite_Move
    RTS
  }

}

; =========================================================

Sprite_Darknut_Draw:
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
  db $00, $02, $04, $06, $08, $0A, $0C, $0E
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, -4
  dw 0, -4
  dw 0, -12
  dw 0, -12
  dw 0, 12
  dw 0, 12
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw -12, 0
  dw -12, 0
  .chr
  db $EA, $C0
  db $EA, $C0
  db $EC, $C2
  db $E4, $C2
  db $EC, $C2
  db $E4, $C2
  db $C0, $EE
  db $C0, $EE
  .properties
  db $39, $39
  db $79, $39
  db $39, $79
  db $39, $79
  db $79, $39
  db $79, $39
  db $F9, $39
  db $F9, $79
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}
