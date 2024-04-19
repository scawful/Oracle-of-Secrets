; =========================================================
; Minecart Sprite Properties
; =========================================================

!SPRID              = $A3   ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 08    ; Number of tiles used in a frame
!Harmless           = 01    ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00    ; Is your sprite going super fast? put 01 if it is
!Health             = 00    ; Number of Health the sprite have
!Damage             = 00    ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00    ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01    ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00    ; 01 = small shadow, 00 = no shadow
!Shadow             = 00    ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00    ; Unused in this template (can be 0 to 7)
!Hitbox             = 00    ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01    ; 01 = your sprite continue to live offscreen
!Statis             = 00    ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00    ; 01 = will check both layer for collision
!CanFall            = 00    ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00    ; 01 = deflect arrows
!WaterSprite        = 00    ; 01 = can only walk shallow water
!Blockable          = 00    ; 01 = can be blocked by link's shield?
!Prize              = 00    ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00    ; 01 = Play different sound when taking damage
!Interaction        = 00    ; ?? No documentation
!Statue             = 00    ; 01 = Sprite is statue
!DeflectProjectiles = 00    ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00    ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00    ; 01 = Impervious to sword and hammer attacks
!Boss               = 00    ; 00 = normal sprite, 01 = sprite is a boss

; =========================================================

%Set_Sprite_Properties(Sprite_Minecart_Prep, Sprite_Minecart_Long) 

; =========================================================

; Link is in cart
!LinkInCart         = $35
!MinecartSpeed      = 20
!DoubleSpeed        = 30

; nesw
; 0 - north
; 1 - east
; 2 - south
; 3 - west
!MinecartDirection  = $012B

; $0DE0[0x10] - (Sprite) ;functions
;     udlr 
;     0 - up
;     1 - down
;     2 - left
;     3 - right
!SpriteDirection    = $0DE0

; Bitfield for carry-related actions.
; .... ..tl
;   t - tossing object
;   l - lifting object
!LinkCarryOrToss    = $0309

; =========================================================

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

; =========================================================

Sprite_Minecart_Prep:
{
    PHB : PHK : PLB
    
    ; If the subtype is > 4, then it's a dummy cart
    LDA SprSubtype, X : CMP.b #$04 : BCC .continue
      LDA SprSubtype, X : SEC : SBC.b #$04 : STA SprSubtype, X
      ; If link is in a cart, then draw the dummy cart

      LDA !LinkInCart : BNE .dummy_continue
        ; .clear_cart
        STZ.w $0DD0, X ; Otherwise, clear the sprite
        PLB
        RTL

  .continue
    ; Unused dummy cart code
    ; LDA.w !LinkInCart : AND.b #$FF : BEQ .dummy_continue
    ; JMP .clear_cart
  .dummy_continue
    LDA SprY, X : SEC : SBC.b #$04 : STA SprY, X
    
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
                        CMP.b #$04 : BEQ .north
                        CMP.b #$05 : BEQ .east
                        CMP.b #$06 : BEQ .south
                        CMP.b #$07 : BEQ .west

  .north
    STZ.w !MinecartDirection
    %GotoAction(1) ; Minecart_WaitVert
    JMP   .done
  .east
    LDA #$01 : STA !MinecartDirection
    %GotoAction(0) ; Minecart_WaitHoriz
    JMP .done
  .south
    LDA #$02 : STA !MinecartDirection
    %GotoAction(1) ; Minecart_WaitVert
    JMP .done
  .west
    LDA #$03 : STA !MinecartDirection
    %GotoAction(0) ; Minecart_WaitHoriz

  .done
    PLB
    RTL
}

; =========================================================

macro HandlePlayerCamera()
  LDA $22 : SEC : SBC $3F : STA $31
  LDA $20 : SEC : SBC $3E : STA $30
  PHX 
  
  JSL $07E6A6 ; Link_HandleMovingAnimation_FullLongEntry
  JSL $07F42F ; HandleIndoorCameraAndDoors_Long
  
  JSL Player_HaltDashAttack
  PLX 
endmacro

macro InitMovement()
  LDA.b $22 : STA.b $3F
  LDA.b $23 : STA.b $41
  LDA.b $20 : STA.b $3E
  LDA.b $21 : STA.b $40
endmacro

macro MoveCart()
  JSR HandleTileDirections
  JSR HandleDynamicSwitchTileDirections
  LDA #$35 : STA $012E                  ; Cart SFX
endmacro

macro StopCart()
    STZ   $02F5
    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X
    STZ.w !LinkInCart
endmacro

; TODO: Implement distance and gravity for cart tossing
macro HandleLiftAndToss()
    LDA.w !LinkCarryOrToss : AND #$02 : BNE .not_tossing
      ; Velocities for cart tossing
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X 
      STZ.w $0F90, X : STZ.w $0F70, X
  .not_tossing
    JSL Sprite_CheckIfLifted
    JSL Sprite_MoveXyz
endmacro

; =========================================================

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

  ; -------------------------------------------------------
  ; 0x00
  Minecart_WaitHoriz:
  {
      %PlayAnimation(0,1,8)
      LDA SprTimerA, X : BNE .not_ready

      LDA !LinkCarryOrToss : AND #$03 : BNE .lifting
        JSR CheckIfPlayerIsOn : BCC .not_ready
          LDA $F4 : AND.b #$80 : BEQ .not_ready ; Check for B button

            JSL Player_HaltDashAttack            ; Stop the player from dashing
            LDA #$02 : STA $02F5                 ; Somaria platform and moving 
            LDA $0FDA : SEC : SBC #$0B : STA $20 ; Adjust player pos
            LDA #$01 : STA !LinkInCart           ; Set Link in cart flag

            ; Check if the cart is facing east or west
            LDA SprSubtype, X : CMP.b #$03 : BNE .opposite_direction
              STA.w !MinecartDirection
              LDA   #$02 : STA !SpriteDirection, X
              %GotoAction(5)  ; Minecart_MoveWest
              RTS

            .opposite_direction
              STA.w !MinecartDirection
              LDA   #$03 : STA !SpriteDirection, X
              %GotoAction(3) ; Minecart_MoveEast

      .not_ready
    .lifting
      %HandleLiftAndToss()
      RTS
  }
  
  ; -------------------------------------------------------
  ; 0x01
  Minecart_WaitVert:
  {
      %PlayAnimation(2,3,8)
      LDA SprTimerA, X : BNE .not_ready

      LDA !LinkCarryOrToss : AND #$03 : BNE .lifting
        JSR CheckIfPlayerIsOn : BCC .not_ready
          LDA $F4 : AND.b #$80 : BEQ .not_ready ; Check for B button

            JSL Player_HaltDashAttack            ; Stop the player from dashing
            LDA #$02 : STA $02F5                 ; Somaria platform and moving 
            LDA $0FDA : SEC : SBC #$0B : STA $20 ; Adjust player pos 
            LDA #$01 : STA !LinkInCart           ; Set Link in cart flag
            
            ; Check if the cart is facing north or south
            LDA SprSubtype, X : BEQ .opposite_direction
              STA.w !MinecartDirection
              LDA   #$01 : STA !SpriteDirection, X
              %GotoAction(4)  ; Minecart_MoveSouth
              RTS
              
            .opposite_direction
              STA.w !MinecartDirection
              LDA   #$00 : STA !SpriteDirection, X
              %GotoAction(2)  ; Minecart_MoveNorth

      .not_ready
    .lifting
      %HandleLiftAndToss()
      RTS 
  }

  ; -------------------------------------------------------
  ; 0x02
  Minecart_MoveNorth:
  {
      %PlayAnimation(2,3,8)
      %InitMovement()

      LDA $36 : BNE .fast_speed
        LDA.b #-!MinecartSpeed : STA SprYSpeed, X
        JMP   .continue
    .fast_speed
      LDA.b #-!DoubleSpeed : STA SprYSpeed, X
    .continue
      JSL Sprite_MoveVert
      JSL Sprite_BounceFromTileCollision

      JSR DragPlayer
      JSR CheckForPlayerInput
      %HandlePlayerCamera()
      %MoveCart()

      RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Minecart_MoveEast:
  {
      %PlayAnimation(0,1,8)
      %InitMovement()
      LDA $36 : BNE .fast_speed
        LDA.b #!MinecartSpeed : STA $0D50, X
        JMP   .continue
    .fast_speed
        LDA.b #!DoubleSpeed : STA $0D50, X
    .continue
      JSL Sprite_MoveHoriz
      JSL Sprite_BounceFromTileCollision
      
      JSR DragPlayer
      JSR CheckForPlayerInput
      %HandlePlayerCamera()
      %MoveCart()

      RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Minecart_MoveSouth:
  {
      %PlayAnimation(2,3,8)
      %InitMovement()
      LDA $36 : BNE .fast_speed
        LDA.b #!MinecartSpeed : STA SprYSpeed, X
        JMP   .continue
    .fast_speed
        LDA.b #!DoubleSpeed : STA SprYSpeed, X
    .continue
      JSL Sprite_MoveVert
      JSL Sprite_BounceFromTileCollision

      JSR DragPlayer
      JSR CheckForPlayerInput
      %HandlePlayerCamera()
      %MoveCart()
      
      RTS
  }

  ; -------------------------------------------------------
  ; 0x05
  Minecart_MoveWest:
  {
      %PlayAnimation(0,1,8)
      %InitMovement()
      LDA   $36 : BNE .fast_speed
      LDA.b #-!MinecartSpeed : STA $0D50, X
              JMP .continue
    .fast_speed
        LDA.b #-!DoubleSpeed : STA $0D50, X
    .continue
      JSL Sprite_MoveHoriz
      JSL Sprite_BounceFromTileCollision
      
      JSR DragPlayer
      JSR CheckForPlayerInput
      %HandlePlayerCamera()
      %MoveCart()

      RTS
  }


  ; -------------------------------------------------------
  ; 0x06
  Minecart_Release:
  {
      %StopCart()

      LDA SprTimerD, X : BNE .not_ready
        LDA #$40 : STA SprTimerA, X
        %GotoAction(0)
    .not_ready
      RTS
  }
}

; =========================================================
; The purpose of this routine is to determine the direction
; the sprite is facing and then adjust the X and Y positions
; of the tile interaction lookup based on that direction.
; If implemented correctly this would make sure the sprite
; stays centered on the tracks when it makes corner turns.
; Currently, depending on where the tile is placed the 
; cart may make a turn too early and appear to be off center.

North = $00
East  = $01
South = $02
West  = $03

SetTileLookupPosBasedOnDirection:
{
    ; Based on the direction of the Minecart, adjust the 
    ; lookup position to be in front of the sprite
    LDA.w !MinecartDirection : CMP.b #$00 : BEQ .north
                               CMP.b #$01 : BEQ .east
                               CMP.b #$02 : BEQ .south
                               CMP.b #$03 : BEQ .west

  .north
    LDA.w SprY, X : SEC : SBC.b #$01 : STA.b $00
    LDA.w SprX, X : STA.b $02
    JMP   .return
  .east
    LDA.w SprX, X : CLC : ADC.b #$01 : STA.b $03
    LDA.w SprY, X : STA.b $00
    JMP   .return
  .south
    LDA.w SprY, X : SEC : SBC.b #$01 : STA.b $00
    LDA.w SprX, X : STA.b $02
    JMP   .return
  .west
    LDA.w SprX, X : AND #$F8 : SEC : SBC.b #$01 : STA.b $03
    LDA.w SprY, X : STA.b $00

  .return
    LDA.w SprYH, X : STA.b $01
    LDA.w SprXH, X : STA.b $03

    LDA.w SprX,  X : STA $0FD8
    LDA.w SprXH, X : STA $0FD9
    LDA.w SprY,  X : STA $0FDA
    LDA.w SprYH, X : STA $0FDB

    RTS
}

; =========================================================

print "HandleTileDirections ", pc
HandleTileDirections:
{
    ; Setup Minecart position to look for tile IDs
    ; We use AND #$F8 to clamp to a 16x16 grid, however this needs work.
    LDA.w SprY, X : AND #$F8 : STA.b $00 : LDA.w SprYH, X : STA.b $01
    LDA.w SprX, X : AND #$F8 : STA.b $02 : LDA.w SprXH, X : STA.b $03
    ; JSR SetTileLookupPosBasedOnDirection

    ; Fetch tile attributes based on current coordinates
    LDA.b #$00 : JSL Sprite_GetTileAttr
    
    ; Load the tile index 
    LDA $0FA5 : CLC : CMP.b #$01 : BNE .not_out_of_bounds
      ; If the tile is out of bounds, release the cart
      LDA #$40 : STA SprTimerD, X
      %GotoAction(6) ; Minecart_Release
      RTS
  .not_out_of_bounds
    ; Check if the tile is a stop tile
    CLC : CMP.b #$B7 : BCS .check_stop ; If tile ID is >= $B8, check for stop tiles
      
      .check_stop
        CLC : CMP.b #$B7 : BEQ .stop_north
        CLC : CMP.b #$B8 : BEQ .stop_south
        CLC : CMP.b #$B9 : BEQ .stop_west
        CLC : CMP.b #$BA : BEQ .stop_east
          JMP .check_for_movement ; if none of the above, continue with normal logic

        .stop_north
          ; Set the new direction to north and flip the cart's orientation
          LDA.b #South : STA SprSubtype,       X : STA.w !MinecartDirection
          LDA   #$01   : STA !SpriteDirection, X
          JMP   .go_vert
        
        .stop_south
          ; Set the new direction to south and flip the cart's orientation
          LDA.b #North : STA SprSubtype,       X : STZ.w !MinecartDirection
          LDA   #$00   : STA !SpriteDirection, X
          
          ; -----------------------------------------------
          .go_vert
            %SetTimerA($40)
            %StopCart()
            %GotoAction(1) ; Minecart_WaitVert
            JSL Player_ResetState
            RTS
        
        .stop_east
          ; Set the new direction to east and flip the cart's orientation
          LDA.b #West : STA SprSubtype,       X : STA.w !MinecartDirection
          LDA   #$03  : STA !SpriteDirection, X
          JMP   .go_horiz
        
        .stop_west
          ; Set the new direction to west and flip the cart's orientation
          LDA.b #East : STA SprSubtype,       X : STA.w !MinecartDirection
          LDA   #$02  : STA !SpriteDirection, X
          
          ; -----------------------------------------------
          .go_horiz
            %SetTimerA($40)
            %StopCart()
            %GotoAction(0) ; Minecart_WaitHoriz
            JSL Player_ResetState
            RTS

  ; -------------------------------------------------------
  .check_for_movement
    CLC : CMP.b #$B2 : BEQ .check_direction
    CLC : CMP.b #$B3 : BEQ .check_direction
    CLC : CMP.b #$B4 : BEQ .check_direction
    CLC : CMP.b #$B5 : BEQ .check_direction
      JMP .done

      ; Create a composite index based on current direction and tile type
      LDA SprSubtype, X ; Load the current direction subtype (0 to 3)
      ASL A             ; Multiply by 4 to offset rows in the lookup table
      TAY               ; Transfer to Y to use as an offset for the rows

      ; Load the tile type and subtract $B2 to normalize the tile type to 0 to 3
      LDA $0FA5 : SEC   : SBC.b #$B3
      ; Add the row and column offsets to index into the lookup table
      CLC : ADC.w .DirectionTileLookup, Y : TAY
        
  .check_direction
      LDA SprSubtype, X
      ASL #2  ; Multiply by 4 (shifting left by 2 bits) to offset rows in the lookup table
      STA $07 ; Store the action index in $07

      LDA $0FA5        ; Load the tile type
      SEC : SBC.b #$B2 ; Subtract $B2 to normalize the tile type to 0 to 3
      CLC : ADC.w $07  ; Add the action index to the tile type offset to get the composite index
      TAY              ; Transfer to Y to use as an offset for the rows
      LDA.w .DirectionTileLookup, Y : TAY

      ; JSR ClampSpritePositionToGrid
      CPY #$01 : BEQ .move_north
      CPY #$02 : BEQ .move_east
      CPY #$03 : BEQ .move_south
      CPY #$04 : BEQ .move_west
        JMP .done

        .move_north
          LDA #$00 : STA SprSubtype, X
          STA !SpriteDirection,      X
          %GotoAction(2) ; Minecart_MoveNorth
          RTS
        .move_east
          LDA #$01 : STA SprSubtype,       X
          LDA #$03 : STA !SpriteDirection, X
          %GotoAction(3) ; Minecart_MoveEast
          RTS
        .move_south
          LDA #$02 : STA SprSubtype,       X
          LDA #$01 : STA !SpriteDirection, X
          %GotoAction(4) ; Minecart_MoveSouth
          RTS
        .move_west
          LDA #$03 : STA SprSubtype,       X
          LDA #$02 : STA !SpriteDirection, X
          %GotoAction(5) ; Minecart_MoveWest
      .done
        RTS

  ; Direction to move on tile collision
  ; 00 - stop or nothing
  ; 01 - north
  ; 02 - east
  ; 03 - south
  ; 04 - west
  .DirectionTileLookup
  {
        ; TL,  BL,  TR,  BR, Stop
      db $02, $00, $04, $00 ; North
      db $00, $00, $03, $01 ; East
      db $00, $02, $00, $04 ; South
      db $03, $01, $00, $00 ; West
  }
  .unused_tile_ids 
  {    
      ;    TL,  BL,  TR,  BR
      db   $B2, $B3, $B4, $B5
      ; db $B0  - Horiz
      ; db $B1  | Vert 
      ; db $B8  Stop North
      ; db $B9  Stop South
      ; db $BA  Stop East
      ; db $BB  Stop West
      ; db $BE  + any direction
  }
}

; =========================================================
; Clamp the sprite position to a 16x16 grid
; Slows the game down if you run it too often :(

ClampSpritePositionToGrid:
{
    ; Check if SprX is already a multiple of 16
    LDA.w SprX, X : AND #$0F : BEQ .x_aligned
      LDA.w SprX, X : LSR : ASL : STA.w SprX, X
  .x_aligned
    ; Check if SprY is already a multiple of 16
    LDA.w SprY, X : AND #$0F : BEQ .y_aligned
      LDA.w SprY, X : LSR : ASL : STA.w SprY, X
  .y_aligned
    RTS
}

; =========================================================
; Check for the switch_track sprite and move based on the 
; state of that sprite.

HandleDynamicSwitchTileDirections:
{
    ; Find out if the sprite $B0 is in the room
    JSR CheckSpritePresence : BCC .no_b0

      PHX : LDA $02 : TAX
      JSR Link_SetupHitBox

      ; X is now the ID of the sprite $B0
      JSR Sprite_SetupHitBox
      PLX
      
      JSL CheckIfHitBoxesOverlap : BCC .no_b0

        LDA !MinecartDirection : CMP.b #$00 : BEQ .east_or_west
          CMP.b #$02 : BEQ .north_or_south

      .east_or_west
        LDA SwitchRam : BNE .go_west
        LDA #$01 : STA SprSubtype,       X
        LDA #$03 : STA !SpriteDirection, X
        %GotoAction(3) ; Minecart_MoveEast
        RTS

      .go_west
        LDA #$03 : STA SprSubtype,       X
        LDA #$02 : STA !SpriteDirection, X
        %GotoAction(5) ; Minecart_MoveWest
        RTS

      .north_or_south
        LDA SwitchRam : BNE .go_south
        LDA #$00 : STA SprSubtype, X
        STA !SpriteDirection,      X
        %GotoAction(2) ; Minecart_MoveNorth
        RTS

      .go_south
        LDA #$02 : STA SprSubtype,       X
        LDA #$01 : STA !SpriteDirection, X
        %GotoAction(4) ; Minecart_MoveSouth
        RTS

  .no_b0
    RTS
}

; =========================================================
; $00 = flag indicating presence of sprite ID $B0

CheckSpritePresence:
{
    PHX
    CLC        ; Assume sprite ID $B0 is not present
    LDX.b #$10
  .x_loop
    DEX
    
    LDY.b #$04
    .y_loop
      DEY
      LDA $0E20, X : CMP.b #$B0 : BEQ .set_flag
      BRA .not_b0

    .set_flag
      SEC         ; Set flag indicating sprite ID $B0 is present
      STX.w $02
      BRA   .done

  .not_b0
    CPY.b #$00 : BNE .y_loop
    CPX.b #$00 : BNE .x_loop
  .done
    PLX

    RTS
}

; =========================================================

DragYL = $0B7C
DragYH = $0B7D

DragPlayer:
{
    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA DragYH
    
    LDA.w .drag_y_low,  Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F

  .SomariaPlatform_DragLink
    REP #$20
    
    LDA $0FD8 : SEC : SBC.w #$0002
    CMP $22 : BEQ .x_done : BPL .x_too_low
    
    DEC $0B7C
    
    BRA .x_done

  .x_too_low

    INC $0B7C

  .x_done
    ; Changing the modifier adjusts links position in the cart 
    LDA $0FDA : SEC : SBC.w #$0008
    CMP $20 : BEQ .y_done : BPL .y_too_low
    
    DEC $0B7E
    
    BRA .y_done

  .y_too_low

    INC $0B7E

  .y_done

    SEP #$30
        
    RTS

  .drag_x_high
    db 0,   0,  -1,   0

  .drag_x_low
    db 0,   0,  -1,   1

  .drag_y_low
    db -1,   1,   0,   0

  .drag_y_high
    db -1,   0,   0,   0

  ; Alternate drag values provided by Zarby
  ; .drag_x_high
  ; db 0,   0,  -1,   0,  -1
  ; .drag_x_low
  ; db 0,   0,  -1,   1,  -1,   1,   1
  ; .drag_y_low
  ; db -1,   1,   0,   0,  -1,   1,  -1,   1
  ; .drag_y_high
  ; db -1,   0,   0,   0,  -1,   0,  -1,   0
}

; =========================================================

CheckForPlayerInput:
{
    LDA $5D : CMP #$02 : BEQ .release
      CMP #$06 : BNE .continue
  .release
    ; Release player in recoil
    %GotoAction(6) ; Minecart_Release
    RTS

  .continue

    ; Setup Minecart position to look for tile IDs
    LDA.w SprY, X : AND #$F8 : STA.b $00 : LDA.w SprYH, X : STA.b $01
    LDA.w SprX, X : AND #$F8 : STA.b $02 : LDA.w SprXH, X : STA.b $03

    ; Fetch tile attributes based on current coordinates
    LDA.b #$00 : JSL Sprite_GetTileAttr
    
    ; Load the tile index 
    LDA $0FA5 : CLC : CMP.b #$B6 : BNE .cant_input

      ; Check for input from the user (u,d,l,r)
      LDY !SpriteDirection,       X
      LDA $F0 : AND .d_pad_press, Y : STA $00 : AND.b #$08 : BEQ .not_pressing_up
        LDA.b #$00 : STA !SpriteDirection, X ; Moving Up 
        STA   SprSubtype,                  X
        %GotoAction(2) ; Minecart_MoveNorth
        BRA   .return

  .not_pressing_up:
      LDA   $00 : AND.b #$04 : BEQ .not_pressing_down
      LDA.b #$01 : STA !SpriteDirection, X
      LDA   #$02 : STA SprSubtype,       X
      %GotoAction(4) ; Minecart_MoveSouth
      BRA   .return

  .not_pressing_down
      LDA   $00 : AND.b #$02 : BEQ .not_pressing_left
      LDA.b #$02 : STA !SpriteDirection, X
      LDA   #$03 : STA SprSubtype,       X
      %GotoAction(5) ; Minecart_MoveWest
      BRA   .return

  .not_pressing_left
      LDA   $00 : AND.b #$01 : BEQ .always
      LDA.b #$03 : STA !SpriteDirection, X
      STA   SprSubtype,                  X
      %GotoAction(3) ; Minecart_MoveEast

  .always

  ;   LDA !SpriteDirection, X : CMP.b #$03 : BNE .not_going_right
  ;   ; Default heading in reaction to this tile is going up.
  ;   ; LDA.b #$00 : STA !SpriteDirection, X
  ; .not_going_right
  ;   ;STZ $0D80, X

  .return
      
  .cant_input
    RTS

  .d_pad_press
    db $0B, $07, $0E, $0D
}

; =========================================================
; Sets carry if player is overlapping the sprite
; Clear carry if player is outside the bounds

CheckIfPlayerIsOn:
{
    REP #$20
    LDA $22 : CLC : ADC #$0009 : CMP $0FD8 : BCC .left
    LDA $22 : SEC : SBC #$0009 : CMP $0FD8 : BCS .right

    LDA $20 : CLC : ADC #$0012 : CMP $0FDA : BCC .up
    LDA $20 : SEC : SBC #$0012 : CMP $0FDA : BCS .down
    
    SEP #$21 : RTS ; Return with carry set

  .left
  .right
  .up
  .down
    SEP #$20
    CLC : RTS ; Return with carry cleared
}

; =========================================================
; Draw the portion of the cart which is behind the player

Sprite_Minecart_DrawTop:
{
    JSL Sprite_PrepOamCoord
    LDA #$08
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

; =========================================================
; Draw the portion of the cart which is in front of the player

Sprite_Minecart_DrawBottom:
{
    JSL Sprite_PrepOamCoord
    LDA #$08
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

    ; Debug box which draws in the location of the hitbox from
    ; the code in HandleTileDirections / SetTileLookupPosBasedOnDirection
    ; The latter of which is an experimental function
    ; {
    ;   LDA $0FD8 : STA $00
    ;   LDA $0FDA : STA $02

    ;   PHY
    ;   JSL Sprite_PrepOamCoord
    ;   PLY

    ;   REP #$20

    ;   LDA   $00 : STA ($90), Y
    ;   AND.w #$0100 : STA $0E
    ;   INY
    ;   LDA   $02 : STA ($90), Y
    ;   CLC   : ADC #$0010 : CMP.w #$0100
    ;   SEP   #$20
    ;   BCC   .on_screen_y2

    ;   LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
    ;   STA   $0E
    ;   .on_screen_y2

    ;   INY
    ;   LDA #$3A : STA ($90), Y
    ;   INY
    ;   LDA #$B9 : STA ($90), Y

    ;   PHY 
          
    ;   TYA : LSR #2 : TAY
          
    ;   LDA #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
          
    ;   PLY : INY
    ; }

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