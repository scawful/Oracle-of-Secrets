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

!HVelocity = $06

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

  PLB
  RTL
}

;==============================================================================

Sprite_Minecart_Main:
{
  LDA.w SprAction, X                        ; Load the SprAction
  JSL   UseImplicitRegIndexedLocalJumpTable ; Goto the SprAction we are currently in

  dw   Minecart_Adjust
  dw   Minecart_Waiting
  dw   Minecart_Moving
  dw   Minecart_Moving2

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
    LDA #$FF : STA $021B

    INC $0D80, X
    
    RTS
  }

  Minecart_Waiting:
  {
    %PlayAnimation(0,1,8)
    JSR CheckIfPlayerIsOn : BCC .not_on_platform
        ;Cancel Falling
    JSL Player_HaltDashAttack
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
    
  Minecart_Moving: ;Check for pixel X+24, Y+16 if tileid = 0D41
  {
    JSL Sprite_Move
    LDA $5D : CMP #$02 : BNE +
        RTS
    +

    LDA $021B : CMP #$FF : BEQ .NoPlatformSetted ;if == FF then go check if we're on this platform
    CPX $021B : BNE .DoNotCheckThisPlatform      ;Is the platform the one we're currently standing on?
    LDA #$FF : STA $021B

    .NoPlatformSetted
        
    JSR CheckIfPlayerIsOn : BCC .NotOnPlatform
    STX $021B                                  ;We are on that platform so put that in 
    

    LDY $039D                                 ;Load Hookshot slot
    LDA $0C4A, Y : CMP #$1F : BNE .noHookshot
    LDA #$13 : STA $5D                        ;we're in hookshot mode then!!
    .noHookshot

    LDA $5D : CMP #$13 : BNE .dontstopPlatform ;Hookshotting!! stop the platform
        ;Prevent platform from moving 
        STZ $0D50, X : STZ $0D40, X
        REP #$20
        STZ $0B7E : STZ $0B7C
        SEP #$20
        ;Prevent timers from going down as well
        INC $0E10, X
        INC $0E00, X

    RTS
    .dontstopPlatform
    
    JSL Player_HaltDashAttack
    ;Cancel Falling
    STZ $5D  : STZ $5B : STZ $57 : STZ $5E : STZ $59
    
    LDA $0E10, X : BNE .Waiting

    JSR CheckPlayerDirection

    .DoNotCheckThisPlatform
    .NotOnPlatform
    LDA $5B : CMP #$02 : BEQ .Check5D ;IF $5B == 2 then we're falling!
        BRA .skip5D
    .Check5D
        LDA $5D : CMP #$01 : BEQ .Falling ;Branch if we're falling!
        
        .skip5D
        LDA $0E10, X : BNE .Waiting
        STZ $0D50, X : STZ $0D40, X ;Not Needed probably
        LDY $0DB0, X                ;Load Directtion
        LDA SpeedTableX, Y : STA $0D50, X
        LDA SpeedTableY, Y : STA $0D40, X

        JSR Sprite_Move
        JSR GetTileIDAtPosition
    +

    .Waiting
    RTS
    .Falling
    ;Keep Timer incremented
    INC $0E10, X
    INC $0E00, X
    
    RTS
  }

  Minecart_Moving2: ;Check for pixel X+24, Y+16 if tileid = 0D41 ;04
  {
    LDY $0DB0, X ;Load Directtion
    LDA SpeedTableX, Y : STA $0D50, X
    LDA SpeedTableY, Y : STA $0D40, X

    JSR Sprite_Move
    JSR GetTileIDAtPosition

    REP #$20
    LDA $0FD8 : CLC : ADC #$0010 : STA $00
    LDA $0FDA : CLC : ADC #$0008 : STA $02
    SEP #$20
    DEX
    LDA $00 : STA $0D10, X                 ;X low
    LDA $01 : STA $0D30, X                 ;X High

    LDA $02 : STA $0D00, X ;Y low
    LDA $03 : STA $0D20, X ;Y high
    INX
    RTS     
  }


}

;Up, Right, Down, Left
SpeedTableX:
  db 00, 16, 00, -16
SpeedTableY:
  db -16, 00, 16, 00

SpeedTableWordX:
  dw 00, 01, 00, -01
SpeedTableWordY:
  dw -01, 00, 01, 00


CheckPlayerDirection:
{
  REP #$20
  STZ $0B7E : STZ $0B7C ; Not needed propbably
  
  LDA $0DB0,           X : AND #$00FF : ASL : TAY ;Load Direction*2
  LDA SpeedTableWordX, Y : STA $0B7C
  LDA SpeedTableWordY, Y : STA $0B7E

  SEP #$20

  RTS
}

CheckIfPlayerIsOn:
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