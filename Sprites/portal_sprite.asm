
; =========================================================
; Portal Sprite
; =========================================================

!SPRID              = $B6 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 01  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this Portal (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
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
%Set_Sprite_Properties(Sprite_Portal_Prep, Sprite_Portal_Long)


; =========================================================
; Long Sprite Code 
; =========================================================
Sprite_Portal_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Portal_Draw ; Call the draw code
  JSL Sprite_CheckActive ; Check if game is not paused
  BCC .SpriteIsNotActive ; Skip Main code is sprite is innactive

  JSR Sprite_Portal_Main ; Call the main sprite code

.SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code

}

; =========================================================
; Sprite Initialization code
; =========================================================
Sprite_Portal_Prep:
{
  PHB : PHK : PLB
  
  ; Persist outside of camera  
  LDA SprHitbox, X : AND.b #$20 : STA SprHitbox, X

  PLB
  RTL
}

; =========================================================
; FREE RAM: 0x08

BluePortal_X      = $7E06F8
BluePortal_Y      = $7E06F9
OrangePortal_X    = $7E06FA
OrangePortal_Y    = $7E06FB

BlueActive        = $7E06FC
OrangeActive      = $7E06FD
; OrangePortal_Y_Low  = $7E06FE
; OrangePortal_Y_High = $7E06FF

OrangeSpriteIndex = $7E0633
BlueSpriteIndex   = $7E0632



; =========================================================
; Main Sprite Code 
; =========================================================

Sprite_Portal_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable
  dw StateHandler
  dw BluePortal
  dw OrangePortal

  dw BluePortal_WarpDungeon
  dw OrangePortal_WarpDungeon

  dw BluePortal_WarpOverworld
  dw OrangePortal_WarpOverworld


  StateHandler:
  {
    JSR CheckForDismissPortal

    LDA $7E0FA6 : BNE .BluePortal
    LDA #$01 : STA $0307
    TXA : STA OrangeSpriteIndex
    LDA $0D00, X : STA OrangePortal_X
    LDA $0D10, X : STA OrangePortal_Y
    
    %GotoAction(2)
    RTS
  .BluePortal
    LDA #$02 : STA $0307
    TXA : STA BlueSpriteIndex
    LDA $0D00, X : STA BluePortal_X
    LDA $0D10, X : STA BluePortal_Y
    
    %GotoAction(1)
    RTS
  }

  BluePortal:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,1,8)

    
    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
    STZ $11
  .not_warped_yet
  CLC

    LDA SprTimerD, X : BNE .NoOverlap

    
    JSR Link_SetupHitBox
    JSL $0683EA          ; Sprite_SetupHitbox_long 
    
    JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
    CLC

    LDA $1B : BEQ .outdoors

    %GotoAction(3) ; BluePortal_WarpDungeon
  .NoOverlap
    RTS

  .outdoors

    %GotoAction(5) ; BluePortal_WarpOverworld



    RTS
  }

  OrangePortal:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,8)
    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
    STZ $11
  .not_warped_yet
    CLC
    LDA SprTimerD, X : BNE .NoOverlap
    
    JSR Link_SetupHitBox
    JSL $0683EA          ; Sprite_SetupHitbox_long 
    
    JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
    CLC
    ; JSL $01FF28 ; Player_CacheStatePriorToHandler
    
    LDA $1B : BEQ .outdoors
    %GotoAction(4) ; OrangePortal_WarpDungeon
    
  .NoOverlap
    RTS

  .outdoors
    %GotoAction(6) ; OrangePortal_WarpOverworld

    RTS
  }

  BluePortal_WarpDungeon:
  {
    LDA $7EC184 : STA $20
    LDA $7EC186 : STA $22

    LDA $7EC188 : STA $0600
    LDA $7EC18A : STA $0604
    LDA $7EC18C : STA $0608
    LDA $7EC18E : STA $060C
    ; LDA $7EC190 : STA $0610
    ; LDA $7EC192 : STA $0612
    ; LDA $7EC194 : STA $0614
    ; LDA $7EC196 : STA $0616
  
    PHX
    LDA OrangeSpriteIndex : TAX
    LDA #$40 : STA SprTimerD, X
    LDA $0D00,                X : STA $7EC184
    STA BluePortal_Y
    LDA $0D10,                X : STA $7EC186
    STA BluePortal_X
    PLX

    LDA #$14 : STA $11
    %GotoAction(1) ; Return to BluePortal
    RTS
  }

  OrangePortal_WarpDungeon:
  {
    LDA $7EC184 : STA $20
    LDA $7EC186 : STA $22

    ; Camera Scroll Boundaries 
    LDA $7EC188 : STA $0600 ; Small Room North 
    LDA $7EC18A : STA $0604 ; Small Room South
    LDA $7EC18C : STA $0608 ; Small Room West 
    LDA $7EC18E : STA $060C ; Small Room South
    ; LDA $7EC190 : STA $0610 
    ; LDA $7EC192 : STA $0612
    ; LDA $7EC194 : STA $0614
    ; LDA $7EC196 : STA $0616

    PHX
    LDA BlueSpriteIndex : TAX
    LDA #$40 : STA SprTimerD, X
    LDA $0D00,                X : STA $7EC184
    STA OrangePortal_Y
    LDA $0D10,                X : STA $7EC186
    STA OrangePortal_X
    PLX


    LDA #$14 : STA $11
    %GotoAction(2) ; Return to OrangePortal
    RTS
  }

  BluePortal_WarpOverworld:
  {
    LDA OrangePortal_X : STA $20
    LDA OrangePortal_Y : STA $22
    LDA $7EC190 : STA $0610 
    LDA $7EC192 : STA $0612
    LDA $7EC194 : STA $0614
    LDA $7EC196 : STA $0616

    JSL $07E9D3 ; ApplyLinksMovementToCamera

    PHX ; Infinite loop prevention protocol
    LDA OrangeSpriteIndex : TAX
    LDA #$40 : STA SprTimerD, X
    
    PLX

        LDA #$01 : STA $5D
   ;LDA #$2A : STA $11

    %GotoAction(1) ; Return to BluePortal
    RTS
  }

  OrangePortal_WarpOverworld:
  {
    LDA BluePortal_X : STA $20
    LDA BluePortal_Y : STA $22
    LDA $7EC190 : STA $0610 
    LDA $7EC192 : STA $0612
    LDA $7EC194 : STA $0614
    LDA $7EC196 : STA $0616

    JSL $07E9D3 ; ApplyLinksMovementToCamera

    PHX
    LDA BlueSpriteIndex : TAX
    LDA #$40 : STA SprTimerD, X
    PLX

    LDA #$01 : STA $5D
    ;LDA #$2A : STA $11

    %GotoAction(2) ; Return to BluePortal
    RTS
  }
}

CheckForDismissPortal:
{
  LDA $06FE : CMP.b #$02 : BCC .return
  LDA $7E0FA6 : BEQ .DespawnOrange     ; Check what portal is spawning next 
  
  PHX
    LDA   BlueSpriteIndex : TAX
    STZ.w $0DD0, X
  PLX
  JMP .return

.DespawnOrange  

  PHX
    LDA   OrangeSpriteIndex : TAX
    STZ.w $0DD0, X
  PLX

.return
  INC $06FE ; This ticker needs to be reset when transitioning rooms and maps.
  RTS
}

;==========================================================


Sprite_Portal_Draw:
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


; Draw Data 

.start_index
  db $00, $01, $02, $03
.nbr_of_tiles
  db 0, 0, 0, 0
.x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
.y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
.chr
  db $EE
  db $EE
  db $EE
  db $EE
.properties
  db $34
  db $74
  db $32
  db $72
.sizes
  db $02
  db $02
  db $02
  db $02
}


; *$37705-$3772E LOCAL
Link_SetupHitBox:
{
; *$3770A ALTERNATE ENTRY POINT

  LDA.b #$08 : STA $02
                STA $03
  
  LDA $22 : CLC : ADC.b #$04 : STA $00
  LDA $23 : ADC.b #$00 : STA $08
  
  LDA $20 : ADC.b #$08 : STA $01
  LDA $21 : ADC.b #$00 : STA $09
  
  RTS
}