;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $BE ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 08  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
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

;==============================================================================

%Set_Sprite_Properties(Sprite_Minecart_Prep, Sprite_Minecart_Long) 

;==============================================================================

Sprite_Minecart_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Minecart_DrawTop    ; Call the draw code
  JSR Sprite_Minecart_DrawBottom
  JSL Sprite_CheckActive         ; Check if game is not paused
  BCC .SpriteIsNotActive         ; Skip Main code is sprite is innactive

  JSR Sprite_Minecart_Main ; Call the main sprite code

.SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

;==============================================================================

Sprite_Minecart_Prep:
{
  PHB : PHK : PLB

  ; Adjust the Y position so it aligns with the tracks.
  LDA $0D00, X : SEC : SBC.b #$04 : STA $0D00, X

  PLB
  RTL
}

;==============================================================================

!MinecartSpeed = 10

print          "Minecart: ", pc
Sprite_Minecart_Main:
{
  LDA.w SprAction, X                        ; Load the SprAction
  JSL   UseImplicitRegIndexedLocalJumpTable ; Goto the SprAction we are currently in

  dw Minecart_Adjust
  dw Minecart_Waiting
  dw Minecart_MoveHorizontal
  dw Minecart_MoveVertical

  Minecart_Adjust:
  {
    %PlayAnimation(0,1,8)
    LDA $0D10, X : SEC : SBC #$04 : STA $0D10, X
    LDA $0E30, X : STA $0DB0, X
    LDA #$06 : STA $0E40, X
    LDA #$40 : STA $0E60, x
    LDA #$E0 : STA $0F60, X
    LDA #$00 : STA $0CD2, X
    LDA #$00 : STA $0B6B, X ;Set interactive hitbox?
    LDA #$40 : STA $0E00, X

    INC $0D80, X
    
    RTS
  }

  Minecart_Waiting:
  {
    %PlayAnimation(0,1,8)
    JSR CheckIfPlayerIsOn : BCC .not_on_platform
        ;Cancel Falling
    JSL Player_HaltDashAttack
    LDA #$02 : STA $02F5
    LDA $0FDA : SEC : SBC #$0B : STA $20
    ; LDA #$01 : STA DungeonMainCheck
    %GotoAction(2)
    RTS

  .not_on_platform
    LDA $0E00,            X : BNE + ;wait before moving
    LDA #$10 : STA $0E00, X         ;Wait before checking first tile on ground!
    INC $0D80,            X

    LDA.b #$01 : STA $041A
  +
    RTS 
  }

  print pc
  Minecart_MoveHorizontal:
  {
    %PlayAnimation(0,1,8)
    LDA.b #-!MinecartSpeed : STA $0D50, X
    JSL   Sprite_MoveHoriz
    
    ; Make Link move with the minecart 
    LDA SprX, X : STA $22

    JSR DragPlayer
  
    ; Set Minecart sprite coords to look for tile attributes
    LDA.w $0D00, X : STA.b $00
    LDA.w $0D20, X : STA.b $01
    
    LDA.w $0D10, X : STA.b $02
    LDA.w $0D30, X : STA.b $03
    
    LDA.b #$00 : JSL $06E87B
    
    ; Check for Top Right Corner Tile
    LDA $0FA5 : CMP.b #$B1 : BNE .continue
    %StartOnFrame(2)
    LDA #$00 : STA $0D50, X ; Reset X Speed
    INC $0D80,            X
    RTS
  .continue

    PHX 
    JSL $07E6A6               ; Link_HandleMovingAnimation_FullLongEntry
    JSL $07F42F               ; HandleIndoorCameraAndDoors_Long
    JSL Player_HaltDashAttack
    PLX 

    RTS
  }

  Minecart_MoveVertical:
  {
    %PlayAnimation(2,3,8)
    LDA.b #-!MinecartSpeed : STA $0D40, X

    JSL Sprite_MoveVert
    LDA SprY, X : SEC : SBC #$04 : STA $20
    LDA $0FD8 : CLC : ADC #$02 : STA $22 ; X 

    JSR DragPlayer


    
    LDA.w $0D00, X : STA.b $00
    LDA.w $0D20, X : STA.b $01
    
    LDA.w $0D10, X : STA.b $02
    LDA.w $0D30, X : STA.b $03
    
    LDA.b #$00 : JSL $06E87B
    LDA   $0FA5 : CMP.b #$B4 : BNE .continue
    LDA $0FDA : SEC : SBC #$0B : STA $20
    %GotoAction(2)
    RTS
  .continue

    PHX 
    JSL $07E6A6               ; Link_HandleMovingAnimation_FullLongEntry
    JSL $07F42F               ; HandleIndoorCameraAndDoors_Long
    JSL Player_HaltDashAttack
    PLX 

    RTS
  }
  
}

DragPlayer:
{
  LDY.w $0DE0,                  X
  LDA.w DragPlayer_drag_x_low,  Y : CLC : ADC.w $0B7C : STA $0B7C
  LDA.w DragPlayer_drag_x_high, Y : ADC.w $0B7D : STA $0B7D
  
  LDA.w DragPlayer_drag_y_low,  Y : CLC : ADC.w $0B7E : STA $0B7E
  LDA.w DragPlayer_drag_y_high, Y : ADC.w $0B7F : STA $0B7F

.SomariaPlatform_DragLink
  REP #$20
  
  LDA $0FD8 : SEC : SBC.w #$0008 : CMP $22 : BEQ .x_done
                                        BPL .x_too_low
  
  DEC $0B7C
  
  BRA .x_done

.x_too_low

  INC $0B7C

.x_done
  ; Changing the modifier adjusts links position in the cart 
  LDA $0FDA : SEC : SBC.w #$0008 : CMP $20 : BEQ .y_done
                                        BPL .y_too_low
  
  DEC $0B7E
  
  BRA .y_done

.y_too_low

  INC $0B7E

.y_done

  SEP #$30
      
  RTS

; .drag_x_high
;   db 0,   0,  -1,   0,  -1

; .drag_x_low
;   db 0,   0,  -1,   1,  -1,   1,   1

; .drag_y_low
;   db -1,   1,   0,   0,  -1,   1,  -1,   1

; .drag_y_high
;   db -1,   0,   0,   0,  -1,   0,  -1,   0

.drag_x_high
  db 0,   0,  -1,   0

.drag_x_low
  db 0,   0,  -1,   1

.drag_y_low
  db -1,   1,   0,   0

.drag_y_high
  db -1,   0,   0,   0

}

CheckIfPlayerIsOn:
{
  REP #$20
  LDA $22 : CLC : ADC #$0009 : CMP $0FD8 : BCC .OutsideLeft
  LDA $22 : SEC : SBC #$0009 : CMP $0FD8 : BCS .OutsideRight

  LDA $20 : CLC : ADC #$0012 : CMP $0FDA : BCC .OutsideUp
  LDA $20 : SEC : SBC #$0012 : CMP $0FDA : BCS .OutsideDown
  SEP #$21
  RTS                                                       ;Return with carry setted

.OutsideLeft
.OutsideRight
.OutsideDown
.OutsideUp
  SEP #$20
  CLC : RTS ;Return with carry cleared
}


;  0
;3   1
;  2

;$0FD8 = X 16bit
;$0FDA = Y 16bit
GetTileIDAtPosition:
{
  LDA $0E00, X : BEQ + ;Wait 10 frames after every collision with a corner to prevent doing same collison over and over
      RTS ;do not check if timer != 0
  +
  PHX
  REP #$30

  LDA $0FD8 : CLC : ADC #$0018 : AND #$01FF : LSR #03 : STA $00                   ;512 >> 3
  LDA $0FDA : CLC : ADC #$0010 : AND #$01F8 : ASL #03 : CLC : ADC $00 : ASL : TAX ; that is basically >> 3   << 3 so /8 *8  *2 since array is word values
  ;tilemap position!
  LDA $7E4000, X : AND #$03FF
  CMP #$0141 : BEQ .TopRightCorner
  CMP #$0140 : BEQ .TopLeftCorner
  CMP #$0150 : BEQ .BottomLeftCorner
  CMP #$0151 : BEQ .BottomRightCorner
  CMP #$0143 : BEQ .WaitingReverse
  SEP #$30
  PLX
  RTS

.TopRightCorner
  SEP #$30
  PLX
  LDA #$0A : STA $0E00, X
      LDA $0DB0, X : CMP #$00 : BNE .GoingLeft
          LDA #$03 : STA $0DB0, X
          RTS
      .GoingLeft
          LDA #$02 : STA $0DB0, X
          RTS

.TopLeftCorner
  SEP #$30
  PLX
  LDA #$0A : STA $0E00, X
      LDA $0DB0, X : CMP #$03 : BNE .GoingRight
          LDA #$02 : STA $0DB0, X
          RTS
      .GoingRight
          LDA #$01 : STA $0DB0, X
          RTS

.BottomLeftCorner
  SEP #$30
  PLX
  LDA #$0A : STA $0E00, X
      LDA $0DB0, X : CMP #$02 : BNE .GoingUp
          LDA #$01 : STA $0DB0, X
          RTS
      .GoingUp
          LDA #$00 : STA $0DB0, X
          RTS

.BottomRightCorner
  SEP #$30
  PLX
  LDA #$0A : STA $0E00, X
      LDA $0DB0, X : CMP #$01 : BNE .GoingDown
          LDA #$00 : STA $0DB0, X
          RTS
      .GoingDown
          LDA #$03 : STA $0DB0, X
          RTS
.WaitingReverse
  SEP #$30
  PLX
  LDA #$50 : STA $0E00, X
  LDA #$30 : STA $0E10, X
      LDA $0DB0,            X : CMP #$00 : BNE +
      LDA #$02 : STA $0DB0, X
      RTS
      +
      LDA $0DB0,            X : CMP #$01 : BNE +
      LDA #$03 : STA $0DB0, X
      RTS
      +
      LDA $0DB0,            X : CMP #$02 : BNE +
      LDA #$00 : STA $0DB0, X
      RTS
      +
      LDA $0DB0,            X : CMP #$03 : BNE +
      LDA #$01 : STA $0DB0, X
      RTS
      +
      RTS
}

;==============================================================================

Sprite_Minecart_DrawTop:
{
  JSL Sprite_PrepOamCoord
  LDA #$18
  JSL OAM_AllocateFromRegionB

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

.start_index
  db $00, $02, $04, $06
.nbr_of_tiles
  db 1, 1, 1, 1
.x_offsets
  dw -8, 8
  dw -8, 8
  dw -8, 8
  dw -8, 8
.y_offsets
  dw -12, -12
  dw -11, -11
  dw -8, -8
  dw -7, -7
.chr
  db $40, $40
  db $40, $40
  db $42, $42
  db $42, $42
.properties
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
.sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}


Sprite_Minecart_DrawBottom:
{
  JSL Sprite_PrepOamCoord
  LDA #$18
  JSL OAM_AllocateFromRegionC

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

.start_index
  db $00, $02, $04, $06
.nbr_of_tiles
  db 1, 1, 1, 1
.x_offsets
  dw -8, 8
  dw -8, 8
  dw -8, 8
  dw -8, 8
.y_offsets
  dw 4, 4
  dw 5, 5
  dw 8, 8
  dw 9, 9
.chr
  db $60, $60
  db $60, $60
  db $62, $62
  db $62, $62
.properties
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
.sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}