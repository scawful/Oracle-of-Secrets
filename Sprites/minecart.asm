;==============================================================================
; Sprite Properties
;==============================================================================

!SPRID              = $BE            ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 08             ; Number of tiles used in a frame
!Harmless           = 01             ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00             ; Is your sprite going super fast? put 01 if it is
!Health             = 00             ; Number of Health the sprite have
!Damage             = 00             ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00             ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00             ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00             ; 01 = small shadow, 00 = no shadow
!Shadow             = 00             ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00             ; Unused in this template (can be 0 to 7)
!Hitbox             = 00             ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00             ; 01 = your sprite continue to live offscreen
!Statis             = 00             ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00             ; 01 = will check both layer for collision
!CanFall            = 00             ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00             ; 01 = deflect arrows
!WaterSprite        = 00             ; 01 = can only walk shallow water
!Blockable          = 00             ; 01 = can be blocked by link's shield?
!Prize              = 00             ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00             ; 01 = Play different sound when taking damage
!Interaction        = 00             ; ?? No documentation
!Statue             = 00             ; 01 = Sprite is statue
!DeflectProjectiles = 00             ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00             ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00             ; 01 = Impervious to sword and hammer attacks
!Boss               = 00             ; 00 = normal sprite, 01 = sprite is a boss

;==============================================================================

%Set_Sprite_Properties(Sprite_Minecart_Prep, Sprite_Minecart_Long) 

;==============================================================================

print               "Minecart: ", pc
Sprite_Minecart_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Minecart_DrawTop    ; Draws the top half behind Link
  JSR Sprite_Minecart_DrawBottom ; Draw the bottom half in front of Link
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

  LDA SprY, X : SEC : SBC.b #$04 : STA SprY, X ; SprY adjustment 
  
  LDA #$00 : STA $0CAA, X ; Sprite persist in dungeon
  LDA #$04 : STA $0E40, X ; Nbr Oam Entries 
  LDA #$40 : STA $0E60, x ; Impervious props 
  LDA #$E0 : STA $0F60, X ; Persist 
  LDA #$00 : STA $0CD2, X ; No bump damage 
  LDA #$00 : STA $0B6B, X ; Set interactive hitbox? 

  STZ.w $012B

  LDA SprSubtype, X : CMP.b #$00 : BEQ .north
                      CMP.b #$01 : BEQ .east
                      CMP.b #$02 : BEQ .south
                      CMP.b #$03 : BEQ .west

  .north
    %GotoAction(1) ; Minecart_MoveNorth
    JMP .done
  .east
    %GotoAction(0) ; Minecart_MoveEast
    JMP .done
  .south
    %GotoAction(1) ; Minecart_MoveSouth
    JMP .done
  .west
    %GotoAction(0) ; Minecart_MoveWest
    
  .done
  PLB
  RTL
}

;==============================================================================

macro HandlePlayerCamera()
    PHX 
    JSL $07E6A6               ; Link_HandleMovingAnimation_FullLongEntry
    JSL $07F42F               ; HandleIndoorCameraAndDoors_Long
    JSL Player_HaltDashAttack
    PLX 
endmacro

!MinecartSpeed     = 20
!MinecartDirection = $012B

Sprite_Minecart_Main:
{
  LDA.w SprAction, X                        ; Load the SprAction
  JSL   UseImplicitRegIndexedLocalJumpTable ; Goto the SprAction

  dw Minecart_WaitHoriz ; 0x00
  dw Minecart_WaitVert  ; 0x01
  dw Minecart_MoveNorth ; 0x02
  dw Minecart_MoveEast  ; 0x03
  dw Minecart_MoveSouth ; 0x04
  dw Minecart_MoveWest  ; 0x05
  dw Minecart_Release   ; 0x06

  ; ---------------------------------------------------------------------------
  ; 0x01
  Minecart_WaitHoriz:
  {
    %PlayAnimation(0,1,8)
    LDA SprTimerA, X : BNE .not_ready

    JSR CheckIfPlayerIsOn : BCC .not_on_platform

    JSL Player_HaltDashAttack            ; Stop the player from dashing
    LDA #$02 : STA $02F5                 ; Somaria platform and moving 
    LDA $0FDA : SEC : SBC #$0B : STA $20 ; Adjust player pos
    
    LDA !MinecartDirection : BNE .opposite_direction
      %GotoAction(5)  ; Minecart_MoveWest
      RTS

    .opposite_direction
      %GotoAction(3) ; Minecart_MoveEast
    .not_on_platform
    .not_ready
      RTS
  }
  
  ; ---------------------------------------------------------------------------
  ; 0x02
  Minecart_WaitVert:
  {
    %PlayAnimation(2,3,8)
    LDA SprTimerA, X : BNE .not_ready
    JSR CheckIfPlayerIsOn : BCC .not_on_platform

    JSL Player_HaltDashAttack            ; Stop the player from dashing
    LDA #$02 : STA $02F5                 ; Somaria platform and moving 
    LDA $0FDA : SEC : SBC #$0B : STA $20 ; Adjust player pos 
    
    LDA !MinecartDirection : BNE .opposite_direction
      %GotoAction(4)  ; Minecart_MoveSouth
      RTS
      
    .opposite_direction
      %GotoAction(2)  ; Minecart_MoveNorth
    .not_on_platform
    .not_ready
      RTS 
  }

  ; ---------------------------------------------------------------------------
  ; 0x03
  Minecart_MoveNorth:
  {
    %PlayAnimation(2,3,8)
    LDA.b #-!MinecartSpeed : STA SprYSpeed, X
    LDA   #$35 : STA $012E

    JSL Sprite_MoveVert
    LDA SprY, X : SEC : SBC #$04 : STA $20
    LDA $0FD8 : CLC : ADC #$02 : STA $22   ; X 
    JSR DragPlayer
    
    %HandlePlayerCamera()
    
    JSR HandleTileDirections


    RTS
  }

  ; ---------------------------------------------------------------------------
  ; 0x04
  Minecart_MoveEast:
  {
    %PlayAnimation(0,1,8)
    %HandlePlayerCamera()
    
    LDA.b #!MinecartSpeed : STA $0D50, X
    JSL   Sprite_MoveHoriz
    LDA   #$35 : STA $012E
    
    ; Make Link move with the minecart 
    LDA SprX, X : STA $22
    
    JSR DragPlayer

    %HandlePlayerCamera()
  
    JSR HandleTileDirections


    RTS
  }

  ; ---------------------------------------------------------------------------
  ; 0x05
  Minecart_MoveSouth:
  {
    %PlayAnimation(2,3,8)

    LDA.b #!MinecartSpeed : STA SprYSpeed, X

    JSL Sprite_MoveVert
    LDA SprY, X : SEC : SBC #$04 : STA $20
    LDA $0FD8 : CLC : ADC #$02 : STA $22   ; X 

    %HandlePlayerCamera()

    JSR HandleTileDirections

    LDA $40 : SEC : SBC.b #$FF : STA $40
    LDA $68 : SEC : SBC.b #$FF : STA $68


    RTS
  }

  ; ---------------------------------------------------------------------------
  ; 0x06
  Minecart_MoveWest:
  {
    %PlayAnimation(0,1,8)
    LDA.b #-!MinecartSpeed : STA $0D50, X
    JSL   Sprite_MoveHoriz
    LDA   #$35 : STA $012E
    
    ; Make Link move with the minecart 
    LDA SprX, X : STA $22

    JSR DragPlayer

    JSR HandleTileDirections

    ; ; Set Minecart sprite coords to look for tile attributes
    ; LDA.w SprY,  X : CLC : ADC.b #$04 : STA.b $00
    ; LDA.w SprYH, X : STA.b $01
    
    ; LDA.w SprX,  X : STA.b $02
    ; LDA.w SprXH, X : STA.b $03
    
    ; LDA.b #$00 : JSL Sprite_GetTileAttr
    
    ; ; Check for bottom left corner tile 
    ; LDA $0FA5 : CMP.b #$B1 : BNE .continue
    

    %HandlePlayerCamera()

    RTS
  }

  ; ---------------------------------------------------------------------------
  ; 0x07
  Minecart_Release:
  {
    STZ   $02F5
    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X

    LDA SprTimerD, X : BNE .not_ready

    %GotoAction(0)
    .not_ready
    RTS
  }
}

macro StopCart()
    STZ   $02F5
    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X
endmacro

macro SwapSubtype()
    LDA SprSubtype, X    ; Load the current direction subtype
    ; Assume the new direction is opposite to the current direction.
    ; This is just an example, adjust the logic as needed.
    EOR #$03             ; Toggle the least significant 2 bits (0 <-> 3, 1 <-> 2)
    STA SprSubtype, X    ; Store the new direction subtype
endmacro

print pc
HandleTileDirections:
{
    ; Setup Minecart position to look for tile IDs
    LDA.w SprY,  X : STA.b $00 : LDA.w SprYH, X : STA.b $01
    LDA.w SprX,  X : STA.b $02 : LDA.w SprXH, X : STA.b $03

    ; Fetch tile attributes based on current coordinates
    LDA.b #$00 : JSL Sprite_GetTileAttr
    
    ; Load the tile index 
    LDA $0FA5 

    CLC : CMP.b #$01 : BNE .not_out_of_bounds
    LDA #$40 : STA SprTimerD, X
    %GotoAction(6) ; Minecart_Release
    RTS
  .not_out_of_bounds

    ; Check if the tile is a stop tile
    CLC : CMP.b #$B7 : BCS .check_stop ; If tile ID is >= $B8, check for stop tiles
    
    .check_stop
    CLC : CMP.b #$B7 : BEQ .stop_north
    CLC : CMP.b #$B8 : BEQ .stop_south
    CLC : CMP.b #$B9 : BEQ .stop_east
    CLC : CMP.b #$BA : BEQ .stop_west
    JMP .check_for_movement ; if none of the above, continue with normal logic

      .stop_north
        ; Set the new direction to north and flip the cart's orientation
        LDA.b South : STA SprSubtype, X
        STZ.w !MinecartDirection
        JMP .go_vert
      
      .stop_south
        ; Set the new direction to south and flip the cart's orientation
        LDA.b North : STA SprSubtype, X
        LDA #$01 : STA !MinecartDirection
        .go_vert
        %SetTimerA($40)
        %StopCart()
        %GotoAction(1) ; Minecart_WaitVert
        RTS
      
      .stop_east
        ; Set the new direction to east and flip the cart's orientation
        LDA.b West : STA SprSubtype, X
        LDA #$01 : STA !MinecartDirection
        JMP .go_horiz
      
      .stop_west
        ; Set the new direction to west and flip the cart's orientation
        LDA.b East : STA SprSubtype, X
        STZ.w !MinecartDirection
        .go_horiz
        %SetTimerA($40)
        %StopCart()
        %GotoAction(0) ; Minecart_WaitHoriz
        RTS
    ; ---------------------------------------------------------------------------

  .check_for_movement
    ; Check for movement tiles
    CLC : CMP.b #$B2 : BEQ .check_direction
    CLC : CMP.b #$B3 : BEQ .check_direction
    CLC : CMP.b #$B4 : BEQ .check_direction
    CLC : CMP.b #$B5 : BEQ .check_direction
    JMP .done

        ; Create a composite index based on current direction and tile type
        LDA SprSubtype, X ; Load the current direction subtype (0 to 3)
        ASL A             ; Multiply by 4 (shifting left by 2 bits) to offset rows in the lookup table
        TAY               ; Transfer to Y to use as an offset for the rows

        LDA $0FA5         ; Load the tile type
        SEC : SBC.b #$B3  ; Subtract $B2 to normalize the tile type to 0 to 3
        CLC
        ADC.w .DirectionTileLookup, Y ; Add the row and column offsets to index into the lookup table
        TAY

    ; Direction to move on tile collision
    ; 00 - stop or nothing
    ; 01 - north
    ; 02 - east
    ; 03 - south
    ; 04 - west

    North = $00
    East  = $01
    South = $02
    West  = $03

    .DirectionTileLookup
    {
        ; TL,  BL,  TR,  BR, Stop
      db $02, $00, $04, $00   ; North
      db $00, $00, $03, $01   ; East
      db $00, $02, $00, $04   ; South
      db $03, $01, $00, $00   ; West
    }
        
  .check_direction
        print pc
        LDA SprSubtype, X 
        BNE .not_zero
        
      .not_zero
        ASL #2             ; Multiply by 4 (shifting left by 2 bits) to offset rows in the lookup table
        STA $07            ; Store the action index in $07

        LDA $0FA5         ; Load the tile type
        SEC : SBC.b #$B2  ; Subtract $B2 to normalize the tile type to 0 to 3
        CLC : ADC.w $07   ; Add the action index to the tile type offset to get the composite index
        TAY
      
        LDA.w .DirectionTileLookup, Y
        TAY

    .execute_action
        CPY #$01 : BEQ .move_north
        CPY #$02 : BEQ .move_east
        CPY #$03 : BEQ .move_south
        CPY #$04 : BEQ .move_west
        JMP .done

    .move_north
        LDA #$00 : STA SprSubtype, X
        %GotoAction(2) ; Minecart_MoveNorth
        RTS
    .move_east
        LDA #$01 : STA SprSubtype, X
        %GotoAction(3) ; Minecart_MoveEast
        RTS
    .move_south
        LDA #$02 : STA SprSubtype, X
        %GotoAction(4) ; Minecart_MoveSouth
        RTS
    .move_west
        LDA #$03 : STA SprSubtype, X
        %GotoAction(5) ; Minecart_MoveWest
    .done
        RTS

.tile_ids
    ; db $B0                ; - Horiz
    ; db $B1                ; | Vert
        ; TL,  BL,  TR,  BR
    db   $B2, $B3, $B4, $B5
    ; db $B8                Stop North
    ; db $B9                Stop South
    ; db $BA                Stop East
    ; db $BB                Stop West

    ; db $BE                ; + any direction
}

;==============================================================================

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

  .drag_x_high
    db 0,   0,  -1,   0,  -1

  .drag_x_low
    db 0,   0,  -1,   1,  -1,   1,   1

  .drag_y_low
    db -1,   1,   0,   0,  -1,   1,  -1,   1

  .drag_y_high
    db -1,   0,   0,   0,  -1,   0,  -1,   0

  ; .drag_x_high
  ; db 0,   0,  -1,   0

  ; .drag_x_low
  ; db 0,   0,  -1,   1

  ; .drag_y_low
  ; db -1,   1,   0,   0

  ; .drag_y_high
  ; db -1,   0,   0,   0

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