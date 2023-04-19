;==============================================================================
; Farore/Maku Tree - Sprite Uncle/Priest
; 
;
;==============================================================================

incsrc sprite_macros.asm
incsrc sprite_functions_hooks.asm

;==============================================================================

org $298000
incsrc sprite_new_table.asm

;==============================================================================

org $308000
incsrc sprite_new_functions.asm


;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $73; The sprite ID you are overwriting (HEX)
!NbrTiles           = 2 ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0  ; Number of Health the sprite have
!Damage             = 0  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 01  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 0  ; Unused in this template (can be 0 to 7)
!Hitbox             = 0  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

;==============================================================================

%Set_Sprite_Properties(Sprite_Farore_Prep, Sprite_Farore_Long) 

;==============================================================================

Sprite_Farore_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Farore_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Farore_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

;==============================================================================

Sprite_Farore_Prep:
{
  PHB : PHK : PLB
    
  ;   LDA.l $7EF300
  ; 	BEQ .PlayIntro
  ; 		STZ.w $0DD0, X ; Kill the sprite 
  ; .PlayIntro

  PLB
  RTL
}

;==============================================================================

; Movement key bitwise ---- udlr

WALKSPEED = 09

Sprite_Farore_Main:
{
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in

  dw IntroStart
  dw MoveUpTowardsFarore
  dw MoveLeftTowardsFarore
  dw WaitAndMessage
  dw FaroreFollowPlayer

  dw MakuArea_FaroreFollowPlayer


  IntroStart:
  {
    %GotoAction(1)
    RTS
  }

  MoveUpTowardsFarore:
  {
    LDA WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north
    
    LDA.b $20 ; Link's Y Position
    CMP.b #$9C ; Y = 6C
    BCC .linkistoofar

    %GotoAction(2)

  .linkistoofar
    %PlayAnimation(6, 6, 8) ; Farore look towards Link
    RTS
  }

  MoveLeftTowardsFarore:
  {
    ; Move Link Left 
    LDA WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$02 : STA.b $49 

    LDA.b $22 ; Link's X position 
    CMP.b #$1A
    BCS .linkistoofar

    STZ.b $49 ; kill automove
    LDA.b #$20
    STA.w SprTimerA, X ; set timer A to 0x10
    %PlayAnimation(0, 0, 8)
    %GotoAction(3)

  .linkistoofar
    RTS
  }


  WaitAndMessage:
  {
    
    %PlayAnimation(1, 2, 8)
    %MoveTowardPlayer(15)
    LDA.w SprTimerA, X : BNE +
    %ShowUnconditionalMessage($24)
    LDA.b #$01 : STA.l $7EF300 ; prevent intro from playing again with sram set
    ; STZ.w $0DD0, X ; Kill the sprite since it's not needed anymore 
    %GotoAction(4)
  +
    RTS
  }

  ; you could just squeeze it between link and the 1st follower
  ; by reusing the follow code but with lower delay
  ; $1A00[0x14] -   (Tagalong)
      
  ;     Low bytes of tagalong states' Y coordinates.

  ; $1A14[0x14] -   (Tagalong)
      
  ;     High bytes of tagalong states' Y coordinates.

  ; $1A28[0x14] -   (Tagalong)
      
  ;     Low bytes of tagalong states' X coordinates.

  ; $1A3C[0x14] -   (Tagalong)
      
  ;     High bytes of tagalong states' X coordinates.
  ; load current follower position divide it by 2
  ; and use that as index


  FaroreFollowPlayer:
  {
    LDA WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north
    %PlayAnimation(3, 4, 8)
    %MoveTowardPlayer(9)

    LDA #$02 : STA $7EF3C5   ; (0 - intro, 1 - pendants, 2 - crystals)
    LDA #$05 : STA $012D ; turn off rain sound
    LDA #$01 : STA $0728
    RTS
  }

  MakuArea_FaroreFollowPlayer:
  {
    %PlayAnimation(3, 4, 8)
    %MoveTowardPlayer(9)
    RTS
  }
}
;==============================================================================

Sprite_Farore_Draw:
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

;==============================================================================

.start_index
db $00, $02, $04, $06, $08, $0A, $0C
.nbr_of_tiles
db 1, 1, 1, 1, 1, 1, 1
.x_offsets
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, -1
.y_offsets
dw -8, 4
dw -8, 4
dw 4, -8
dw -8, 4
dw 4, -7
dw -8, 4
dw 4, -7
.chr
db $A8, $AA
db $A8, $88
db $AA, $A8
db $8A, $8C
db $8C, $8A
db $8A, $AC
db $AA, $86
.properties
db $3B, $3B
db $3B, $7B
db $3B, $3B
db $3B, $3B
db $7B, $3B
db $3B, $3B
db $3B, $7B
.sizes
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
}

;==============================================================================
