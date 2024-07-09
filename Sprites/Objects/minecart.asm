; =========================================================
; Minecart Sprite Properties
; =========================================================

!SPRID              = Sprite_Minecart
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
!Hitbox             = 14    ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Minecart_Prep, Sprite_Minecart_Long) 

; =========================================================

; Link is in cart
!LinkInCart         = $35
!MinecartSpeed      = 20
!DoubleSpeed        = 30

North = $00
East  = $01
South = $02
West  = $03
; nesw
; 0 - north
; 1 - east
; 2 - south
; 3 - west
!MinecartDirection  = $012B

Up = $00
Down = $01
Left = $02
Right = $03
; $0DE0[0x10] - (Sprite) ;functions
;     udlr 
;     0 - up
;     1 - down
;     2 - left
;     3 - right
!SpriteDirection    = $0DE0

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

    STZ.w SprMiscF, X ; Clear the auto-move flag
    STZ.w SprMiscG, X ; Clear the active tossing flag

    ; If the subtype is > 4, then it's an active cart
    LDA.w SprSubtype, X : CMP.b #$04 : BCC .continue
      LDA.w SprSubtype, X : SEC : SBC.b #$03 : STA.w SprSubtype, X
      LDA.b #$01 : STA.w SprMiscF, X ; Set the auto-move flag
    .continue
    LDA #$00 : STA $0CAA, X ; Sprite persist in dungeon
    LDA #$04 : STA $0E40, X ; Nbr Oam Entries 
    LDA #$40 : STA $0E60, x ; Impervious props 
    LDA #$E0 : STA $0F60, X ; Persist 
    LDA #$00 : STA.w SprBump, X ; No bump damage 
    LDA #$00 : STA $0B6B, X ; Set interactive hitbox? 

    STZ.w !MinecartDirection

    LDA SprSubtype, X : CMP.b #$00 : BEQ .north
                        CMP.b #$01 : BEQ .east
                        CMP.b #$02 : BEQ .south
                        CMP.b #$03 : BEQ .west

    .north
      %GotoAction(1) ; Minecart_WaitVert
      JMP   .done
    .east
      LDA.b #East : STA !MinecartDirection
      LDA.b #Right : STA !SpriteDirection, X
      %GotoAction(0) ; Minecart_WaitHoriz
      JMP .done
    .south
      LDA #$02 : STA !MinecartDirection
      LDA #$01 : STA !SpriteDirection, X
      %GotoAction(1) ; Minecart_WaitVert
      JMP .done
    .west
      LDA.b #West : STA !MinecartDirection
      LDA.b #Left : STA !SpriteDirection, X
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
  
  JSL Link_HandleMovingAnimation_FullLongEntry
  JSL HandleIndoorCameraAndDoors
  
  JSL Link_CancelDash
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
  STZ.w $02F5
  STZ.w SprYSpeed, X
  STZ.w SprXSpeed, X
  STZ.w !LinkInCart
endmacro

; =========================================================
; Handle the tossing of the cart
; Changes the subtype of the cart to indicate the direction
; the cart is facing and sets the velocity of the cart
; based on the direction it is facing.

HandleToss:
{
  ; Check links facing direction $2F and apply velocity
  LDA $2F : CMP.b #$00 : BEQ .toss_north
            CMP.b #$02 : BEQ .toss_south
            CMP.b #$04 : BEQ .toss_east
            CMP.b #$06 : BEQ .toss_west
  .toss_north
    LDA.b #-!DoubleSpeed : STA.w SprYSpeed, X
    LDA #$00 : STA.w SprSubtype, X : STA !SpriteDirection, X
    %GotoAction(1) ; Minecart_WaitVert
    JMP .continue
  .toss_south 
    LDA.b #!DoubleSpeed : STA.w SprYSpeed, X
    LDA #$02 : STA.w SprSubtype,       X
    LDA #$01 : STA !SpriteDirection, X
    %GotoAction(1) ; Minecart_WaitVert
    JMP .continue
  .toss_east
    LDA.b #-!DoubleSpeed : STA.w SprXSpeed, X
    LDA #$01 : STA.w SprSubtype,       X
    LDA #$03 : STA !SpriteDirection, X
    %GotoAction(0) ; Minecart_WaitHoriz
    JMP .continue
  .toss_west
    LDA.b #!DoubleSpeed : STA.w SprXSpeed, X
    LDA #$03 : STA.w SprSubtype,       X
    LDA #$02 : STA !SpriteDirection, X
    %GotoAction(0) ; Minecart_WaitHoriz
  .continue
  LDA #$01 : STA.w SprMiscG, X
  LDA #$12 : STA.w SprTimerC, X
  STA.w SprYRound, X : STA.w SprXRound, X
  RTS
}

HandleLiftAndToss:
{
  JSR CheckIfPlayerIsOn : BCC .not_tossing
    LDA.w LinkCarryOrToss : CMP.b #$02 : BNE .not_tossing
      JSR HandleToss
  .not_tossing
  JSL Sprite_CheckIfLifted
  JSL Sprite_Move
  JSR HandleTossedCart
  RTS
}

HandleTossedCart:
{
  LDA.w SprMiscG, X : BEQ .not_tossed
    LDA.w SprHeight, X : BEQ .low_enough
      DEC.w SprHeight, X
      RTS
    .low_enough

    LDA.w SprTimerC, X : BNE .not_tossed
      LDA SprX, X : AND.b #$F8 : STA.w SprX, X
      LDA SprY, X : AND.b #$F8 : STA.w SprY, X
      STZ.w SprMiscG, X
      STZ.w SprYSpeed, X
      STZ.w SprXSpeed, X
      STZ.w SprHeight, X
  .not_tossed
  RTS
}

; =========================================================

Sprite_Minecart_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable

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
    LDA LinkCarryOrToss : AND #$03 : BNE .lifting
      LDA SprTimerA, X : BNE .not_ready
        JSR CheckIfPlayerIsOn : BCC .not_ready
        LDA.w SprMiscF, X : BNE .active_cart
          LDA $F4 : AND.b #$80 : BEQ .not_ready ; Check for B button
        .active_cart
        JSL Link_CancelDash            ; Stop the player from dashing
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
          RTS

    .not_ready
    .lifting
      JSR HandleLiftAndToss
      JSL ThrownSprite_TileAndSpriteInteraction_long
      RTS
  }
  
  ; -------------------------------------------------------
  ; 0x01
  Minecart_WaitVert:
  {
    %PlayAnimation(2,3,8)
    LDA LinkCarryOrToss : AND #$03 : BNE .lifting
      LDA SprTimerA, X : BNE .not_ready
        JSR CheckIfPlayerIsOn : BCC .not_ready
        LDA.w SprMiscF, X : BNE .active_cart
          LDA $F4 : AND.b #$80 : BEQ .not_ready ; Check for B button
        .active_cart
        JSL Link_CancelDash            ; Stop the player from dashing
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
          RTS

      .not_ready
    .lifting
      JSR HandleLiftAndToss
      JSL ThrownSprite_TileAndSpriteInteraction_long
      RTS 
  }

  ; -------------------------------------------------------
  ; 0x02
  Minecart_MoveNorth:
  {
    %PlayAnimation(2,3,8)
    %InitMovement()

    LDA $36 : BNE .fast_speed
      LDA.b #-!MinecartSpeed : STA.w SprYSpeed, X
      JMP   .continue
    .fast_speed
    LDA.b #-!DoubleSpeed : STA.w SprYSpeed, X
    .continue
    JSL Sprite_MoveVert

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
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
    
    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
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
      LDA.b #!MinecartSpeed : STA.w SprYSpeed, X
      JMP   .continue
    .fast_speed
      LDA.b #!DoubleSpeed : STA.w SprYSpeed, X
    .continue
    JSL Sprite_MoveVert

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
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
    
    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
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
      LDA #$40 : STA.w SprTimerA, X
      LDA.w !SpriteDirection, X : CMP.b #$00 : BEQ .vert
        CMP.b #$02 : BEQ .vert
        JMP .horiz
      .vert
        %GotoAction(1) ; Minecart_WaitVert
        RTS
      .horiz
        %GotoAction(0)
    .not_ready
      RTS
  }
}

; =========================================================

HandleTileDirections:
{
    LDA SprTimerA, X : BEQ +
      RTS
    +

    ; If the cart got disconnected from the player, release them.
    JSR CheckIfPlayerIsOn : BCS .player_on_cart
      %GotoAction(6) ; Minecart_Release
      RTS
    .player_on_cart

    ; Setup Minecart position to look for tile IDs
    ; We use AND #$F8 to clamp to a 16x16 grid, however this needs work.
    LDA.w SprY, X : AND #$F8 : STA.b $00 : LDA.w SprYH, X : STA.b $01
    LDA.w SprX, X : AND #$F8 : STA.b $02 : LDA.w SprXH, X : STA.b $03

    ; Fetch tile attributes based on current coordinates
    LDA.b #$00 : JSL Sprite_GetTileAttr : LDA $0FA5 

    CMP.b #$02 : BNE .not_out_of_bounds
      ; If the tile is out of bounds, release the cart
      LDA #$40 : STA.w SprTimerD, X
      %GotoAction(6) ; Minecart_Release
      RTS
    
    .not_out_of_bounds
    ; Check if the tile is a stop tile
    CMP.b #$B7 : BEQ .stop_north
    CMP.b #$B8 : BEQ .stop_south
    CMP.b #$B9 : BEQ .stop_west
    CMP.b #$BA : BEQ .stop_east
    JMP .check_for_movement ; if none of the above, continue with normal logic

    .stop_north
      ; Set the new direction to north and flip the cart's orientation
      LDA.b #South : STA.w SprSubtype,       X : STA.w !MinecartDirection
      LDA   #$01   : STA !SpriteDirection, X
      JMP   .go_vert
    
    .stop_south
      ; Set the new direction to south and flip the cart's orientation
      LDA.b #North : STA.w SprSubtype,       X : STZ.w !MinecartDirection
      LDA   #$00   : STA !SpriteDirection, X
      
    ; -----------------------------------------------
    .go_vert
      %SetTimerA($40)
      %StopCart()
      %GotoAction(1) ; Minecart_WaitVert
      JSL Link_ResetProperties_A
      RTS
    
    .stop_east
      ; Set the new direction to east and flip the cart's orientation
      LDA.b #West : STA.w SprSubtype,       X : STA.w !MinecartDirection
      LDA   #$02  : STA !SpriteDirection, X
      JMP   .go_horiz
    
    .stop_west
      ; Set the new direction to west and flip the cart's orientation
      LDA.b #East : STA.w SprSubtype,       X : STA.w !MinecartDirection
      LDA   #$03  : STA !SpriteDirection, X
      
    ; -----------------------------------------------
    .go_horiz
      %SetTimerA($40)
      %StopCart()
      %GotoAction(0) ; Minecart_WaitHoriz
      JSL Link_ResetProperties_A
      RTS

    ; -----------------------------------------------------
    .check_for_movement
    CMP.b #$B2 : BEQ .check_direction
    CMP.b #$B3 : BEQ .check_direction
    CMP.b #$B4 : BEQ .check_direction
    CMP.b #$B5 : BEQ .check_direction
    CMP.b #$B0 : BEQ .horiz
    CMP.b #$B1 : BEQ .vert
    CMP.b #$BB : BEQ .horiz
    CMP.b #$BC : BEQ .vert
      JMP .done

    .horiz
      ; Are we moving left or right?
      LDA SprSubtype, X : CMP.b #$03 : BEQ .inverse_horiz_velocity
        LDA.b #!MinecartSpeed : STA.w SprXSpeed, X
        LDA.b #East : STA !MinecartDirection
        JMP .done
      .inverse_horiz_velocity
        LDA.b #-!MinecartSpeed : STA.w SprXSpeed, X
        LDA.b #West : STA !MinecartDirection
        JMP .done
    .vert
      ; Are we moving up or down?
      LDA SprSubtype, X : CMP.b #$00 : BEQ .inverse_vert_velocity
        LDA.b #!MinecartSpeed : STA.w SprYSpeed, X
        JMP .done
    .inverse_vert_velocity
        LDA.b #-!MinecartSpeed : STA.w SprYSpeed, X
        JMP .done
        
    .check_direction
      LDA SprSubtype, X
      ASL #2  ; Multiply by 4 (shifting left by 2 bits) to offset rows in the lookup table
      STA $07 ; Store the action index in $07

      LDA $0FA5        ; Load the tile type
      SEC : SBC.b #$B2 ; Subtract $B2 to normalize the tile type to 0 to 3
      CLC : ADC.w $07  ; Add the action index to the tile type offset to get the composite index
      TAY              ; Transfer to Y to use as an offset for the rows
      LDA.w .DirectionTileLookup, Y : TAY

      CPY #$01 : BEQ .move_north
      CPY #$02 : BEQ .move_east
      CPY #$03 : BEQ .move_south
      CPY #$04 : BEQ .move_west
        JMP .done

        .move_north
          LDA #$00 : STA.w SprSubtype, X : STA !MinecartDirection
          STA !SpriteDirection,      X
          %GotoAction(2) ; Minecart_MoveNorth
          LDA SprX, X : AND #$F8 : STA.w SprX, X
          JMP .done
        .move_east
          LDA #$01 : STA.w SprSubtype, X : STA !MinecartDirection
          STA !MinecartDirection
          LDA #$03 : STA !SpriteDirection, X
          LDA SprY, X : AND #$F8 : STA.w SprY, X
          %GotoAction(3) ; Minecart_MoveEast
          JMP .done
        .move_south
          LDA #$02 : STA.w SprSubtype, X : STA !MinecartDirection
          LDA #$01 : STA !SpriteDirection, X
          %GotoAction(4) ; Minecart_MoveSouth
          LDA SprX, X : AND #$F8 : STA.w SprX, X
          JMP .done
        .move_west
          LDA #$03 : STA.w SprSubtype, X : STA !MinecartDirection
          LDA #$02 : STA !SpriteDirection, X
          LDA SprY, X : AND #$F8 : STA.w SprY, X
          %GotoAction(5) ; Minecart_MoveWest
      .done
        LDA #$0F : STA.w SprTimerA, X
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
}

; =========================================================
; Check for the switch_track sprite and move based on the 
; state of that sprite.

HandleDynamicSwitchTileDirections:
{
  ; Find out if the sprite $B0 is in the room
  JSR CheckSpritePresence : BCC .no_b0
    PHX 
    LDA $02 : TAX
    JSL Link_SetupHitBox
    JSL Sprite_SetupHitBox ; X is now the ID of the sprite $B0
    PLX
    
    JSL CheckIfHitBoxesOverlap : BCC .no_b0
      LDA !MinecartDirection : CMP.b #$00 : BEQ .east_or_west
                               CMP.b #$01 : BEQ .north_or_south
                               CMP.b #$02 : BEQ .east_or_west
                               CMP.b #$03 : BEQ .north_or_south
  .no_b0
    RTS

    .east_or_west
      LDA SwitchRam : BNE .go_west
      LDA #$01 : STA.w SprSubtype,       X
      STA.w !MinecartDirection
      LDA #$03 : STA !SpriteDirection, X
      %GotoAction(3) ; Minecart_MoveEast
      RTS

    .go_west
      LDA #$03 : STA.w SprSubtype,       X
      STA.w !MinecartDirection
      LDA #$02 : STA !SpriteDirection, X
      %GotoAction(5) ; Minecart_MoveWest
      RTS

    .north_or_south
      LDA SwitchRam : BNE .go_south
      LDA #$00 : STA.w SprSubtype, X
      STA.w !MinecartDirection
      STA !SpriteDirection,      X
      %GotoAction(2) ; Minecart_MoveNorth
      RTS

    .go_south
      LDA #$02 : STA.w SprSubtype,       X
      STA.w !MinecartDirection
      LDA #$01 : STA !SpriteDirection, X
      %GotoAction(4) ; Minecart_MoveSouth
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
; Check for input from the user (u,d,l,r) on tile B6, BD

CheckForPlayerInput:
{
  ; Setup Minecart position to look for tile IDs
  LDA.w SprY, X : AND #$F8 : STA.b $00 : LDA.w SprYH, X : STA.b $01
  LDA.w SprX, X : AND #$F8 : STA.b $02 : LDA.w SprXH, X : STA.b $03

  ; Fetch tile attributes based on current coordinates
  LDA.b #$00 : JSL Sprite_GetTileAttr
  
  ; Load the tile index 
  LDA $0FA5 : CLC : CMP.b #$B6 : BEQ .can_input
                    CMP.b #$BD : BEQ .can_input
    BRA .cant_input
  .can_input
  
  LDY !SpriteDirection,       X
  LDA $F0 : AND .d_pad_press, Y : STA $00 : AND.b #$08 : BEQ .not_pressing_up
    LDA.b #$00 : STA !SpriteDirection, X ; Moving Up
    LDA.b #North : STA !MinecartDirection
    STA   SprSubtype, X
    %GotoAction(2) ; Minecart_MoveNorth
    BRA   .return

  .not_pressing_up
  LDA.b $00 : AND.b #$04 : BEQ .not_pressing_down
    LDA.b #$01 : STA !SpriteDirection, X
    LDA.b #South : STA !MinecartDirection
    STA.w SprSubtype, X
    %GotoAction(4) ; Minecart_MoveSouth
    BRA   .return

  .not_pressing_down
  LDA.b $00 : AND.b #$02 : BEQ .not_pressing_left
    LDA.b #$02 : STA !SpriteDirection, X
    LDA.b  #West : STA !MinecartDirection
    STA.w SprSubtype, X
    %GotoAction(5) ; Minecart_MoveWest
    BRA   .return

  .not_pressing_left
  LDA.b $00 : AND.b #$01 : BEQ .return
    LDA.b #$03 : STA !SpriteDirection, X
    LDA.b #East : STA !MinecartDirection
    STA   SprSubtype, X
    %GotoAction(3) ; Minecart_MoveEast
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
    SEP #$21 
    RTS ; Return with carry set
  .left
  .right
  .up
  .down
  SEP #$20
  CLC 
  RTS ; Return with carry cleared
}


POSY            = $7E0020
POSYH           = $7E0021
POSX            = $7E0022
POSXH           = $7E0023

; 20 steps of animation and movement caching for followers
FOLLOWERYL      = $7E1A00
FOLLOWERYH      = $7E1A14

FOLLOWERXL      = $7E1A28
FOLLOWERXH      = $7E1A3C

FOLLOWERZ       = $7E1A50
FOLLOWERLAYER   = $7E1A64

; Follower head/body gfx offsets
FLWHO           = $7E0AE8
FLWHOH          = $7E0AE9
FLWBO           = $7E0AEA
FLWBOH          = $7E0AEB

; Follower head
FLWHGFXT        = $7E0AEC
FLWHGFXTH       = $7E0AED
FLWHGFXB        = $7E0AEE
FLWHGFXBH       = $7E0AEF

; Follower body
FLWBGFXT        = $7E0AF0
FLWBGFXTH       = $7E0AF1
FLWBGFXB        = $7E0AF2
FLWBGFXBH       = $7E0AF3

; Index from 0x00 to 0x13 for follower animation step index. Used for reading data.
FLWANIMIR       = $7E02CF

; Cache of follower properties
FOLLOWCYL       = $7EF3CD
FOLLOWCYH       = $7EF3CE
FOLLOWCXL       = $7EF3CF
FOLLOWCXH       = $7EF3D0

FollowerDraw_CalculateOAMCoords:
{
  REP #$20
  LDA.b $02 : STA.b ($90),Y
  INY

  CLC : ADC.w #$0080 : CMP.w #$0180 : BCS .off_screen
    LDA.b $02 : AND.w #$0100 : STA.b $74
    LDA.b $00 : STA.b ($90),Y

    CLC : ADC.w #$0010 : CMP.w #$0100 : BCC .on_screen

  .off_screen:
  LDA.w #$00F0 : STA.b ($90),Y

  .on_screen:
  SEP #$20
  INY
  RTS
}

MinecartFollower_Top:
{
    SEP #$30
    JSR FollowerDraw_CalculateOAMCoords
    LDA #$08
    JSL OAM_AllocateFromRegionB

    LDA $02CF : TAY 
    LDA .start_index, Y : STA $06
    
    PHX
    LDX .nbr_of_tiles, Y ; amount of tiles -1
    LDY.b #$00
  .nextTile

    PHX                 ; Save current Tile index
    TXA : CLC : ADC $06 ; Add Animation Index Offset
    PHA                 ; Keep the value with animation index offset
    ASL A : TAX

    REP #$20

    LDA $02 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $00 : CLC : ADC .y_offsets, X : STA ($90), Y
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
        
    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
    PLX : DEX : BPL .nextTile

    PLX

    RTS

  .start_index:
      db $00, $02, $04, $06
  .nbr_of_tiles:
      db 1, 1, 1, 1
  .x_offsets:
      dw -8, 8
      dw -8, 8
      dw -8, 8
      dw -8, 8
  .y_offsets:
      dw -12, -12
      dw -11, -11
      dw -8, -8
      dw -7, -7
  .chr:
      db $40, $40
      db $40, $40
      db $42, $42
      db $42, $42
  .properties:
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
}

MinecartFollower_Bottom:
{
    SEP #$30

    JSR FollowerDraw_CalculateOAMCoords
    LDA #$08
    JSL OAM_AllocateFromRegionC
    LDA $02CF : TAY 
    LDA .start_index, Y : STA $06

    PHX
    LDX .nbr_of_tiles, Y ; amount of tiles -1
    LDY.b #$00
  .nextTile

    PHX ; Save current Tile Index?
    TXA : CLC : ADC $06 ; Add Animation Index Offset
    PHA ; Keep the value with animation index offset?
    ASL A : TAX

    REP #$20

    LDA $02 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $00 : CLC : ADC .y_offsets, X : STA ($90), Y
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
        
    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
    PLX : DEX : BPL .nextTile

    PLX

    RTS

  .start_index:
      db $00, $02, $04, $06
  .nbr_of_tiles:
      db 1, 1, 1, 1
  .x_offsets:
      dw -8, 8
      dw -8, 8
      dw -8, 8
      dw -8, 8
  .y_offsets:
      dw 4, 4
      dw 5, 5
      dw 8, 8
      dw 9, 9
  .chr:
      db $60, $60
      db $60, $60
      db $62, $62
      db $62, $62
  .properties:
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
}

; Minecart Follower Main Routine and Draw
DrawMinecartFollower:
{
  JSL $099EFC ; Follower_Initialize

  LDX $012B 
  LDA .direction_to_anim, X
  STA $02CF

  JSR FollowerDraw_CachePosition
  JSR MinecartFollower_Top
  JSR MinecartFollower_Bottom

  LDA.b $11 : BNE .dont_spawn
    LDA !LinkInCart : BEQ .dont_spawn
      LDA.b #$A3 
      JSL Sprite_SpawnDynamically
      TYX
      JSL Sprite_SetSpawnedCoords
      LDA.w !MinecartDirection : CMP.b #$00 : BEQ .vert_adjust
                                 CMP.b #$02 : BEQ .vert_adjust
        LDA POSY : CLC : ADC #$08 : STA.w SprY, X
        LDA POSX : STA.w SprX, X
        JMP .finish_prep
      .vert_adjust
        LDA POSY : STA.w SprY, X
        LDA POSX : CLC : ADC #$02 : STA.w SprX, X
      .finish_prep
      LDA POSYH : STA.w SprYH, X
      LDA POSXH : STA.w SprXH, X
      LDA.w !MinecartDirection : CLC : ADC.b #$03 : STA.w SprSubtype, X

      LDA .direction_to_anim, X : STA $0D90, X
      JSL Sprite_Minecart_Prep
      LDA.b #$00 : STA.l $7EF3CC
  .dont_spawn
  RTS

.direction_to_anim
  db $02, $00, $02, $00
}

FollowerDraw_CachePosition:
{
  LDX.b #$00

  LDA.w $1A00, X : STA.b $00
  LDA.w $1A14, X : STA.b $01
  LDA.w $1A28, X : STA.b $02
  LDA.w $1A3C, X : STA.b $03
  LDA.w $1A64, X : STA.b $05

  ; -------------------------
  #_09A95B: AND.b #$20
  #_09A95D: LSR A
  #_09A95E: LSR A
  #_09A95F: TAY

  #_09A960: LDA.b $05
  #_09A962: AND.b #$03
  #_09A964: STA.b $04

  #_09A966: STZ.b $72
  ; Vanilla game would check some priority and collision
  ; variables based on the follower here and manipulate $72
  ; if the player was immobile. 
  
  CLC : ADC $04 : STA $04
  TYA : CLC : ADC $04 : STA $04
  ; -------------------------
  
  REP #$20
  LDA $0FB3 : AND.w #$00FF : ASL A : TAY
  LDA $20 : CMP $00 : BEQ .check_priority_for_region
                      BCS .use_region_b
      BRA .use_region_a
  .check_priority_for_region
    LDA $05 : AND.w #$0003 : BNE .use_region_b
    .use_region_a
      LDA.w .oam_region_offsets_a, Y
      BRA   .set_region
    .use_region_b
      LDA.w .oam_region_offsets_b, Y

  .set_region

  PHA
  
  LSR #2 : CLC : ADC.w #$0A20 : STA $92
  PLA    : CLC : ADC.w #$0800 : STA $90
  
  LDA $00 : SEC : SBC $E8 : STA $06
  LDA $02 : SEC : SBC $E2 : STA $08
  
  SEP #$20

  #_09AA85: LDA.w $02D7
  #_09AA88: INC A
  #_09AA89: CMP.b #$03
  #_09AA8B: BNE .set_repri

  #_09AA8D: LDA.b #$00

  .set_repri
  #_09AA8F: STA.w $02D7

  LDA $02D7 : ASL #2 : STA $05
  TXA : CLC : ADC $05 : TAX
  
  REP #$20
  
  LDA $06 : CLC : ADC.w #$0010 : STA $00
  LDA $08 : STA $02
  STZ $74
  
  SEP #$20

  RTS

  .oam_region_offsets_a
    dw $0170
    dw $00C0

  .oam_region_offsets_b
    dw $01C0
    dw $0110
}


CheckForMinecartFollowerDraw:
{
  PHB : PHK : PLB
  LDA.l $7EF3CC : CMP.b #$0B : BNE .not_minecart
    JSR DrawMinecartFollower
    
  .not_minecart
    ; LDA.b #$10
    ; STA.b $5E
    PLB 
    RTL
}

CheckForFollowerInterroomTransition:
{
  PHB : PHK : PLB
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  PLB
  JSL $01873A ; Underworld_LoadRoom
  RTL
}

CheckForFollowerIntraroomTransition:
{
  STA.l $7EC007
  PHB : PHK : PLB
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  PLB
  RTL
}

pushpc

; Follower_OldManUnused
org $09A41F
  JSL CheckForMinecartFollowerDraw
  RTS

; Module07_02_01_LoadNextRoom
org $028A5B
  JSL CheckForFollowerInterroomTransition

org $0289BF
  JSL CheckForFollowerIntraroomTransition

pullpc

; =========================================================
; Draw the portion of the cart which is behind the player

Sprite_Minecart_DrawTop:
{
    JSL Sprite_PrepOamCoord
    LDA #$08
    JSL OAM_AllocateFromRegionB

    LDA $0DC0, X : CLC : ADC $0D90, X : TAY ; Animation Frame
    LDA .start_index, Y : STA $06

    PHX
    LDX .nbr_of_tiles, Y ; amount of tiles -1
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

RoomTag_ShutterDoorRequiresCart:
{
  LDA.w !LinkInCart : BEQ .no_cart
    #_01C49E: REP #$30

    #_01C4A0: LDX.w #$0000
    #_01C4A3: CPX.w $0468
    #_01C4A6: BEQ .exit

    #_01C4A8: STZ.w $0468

    #_01C4AB: STZ.w $068E
    #_01C4AE: STZ.w $0690

    #_01C4B1: SEP #$30

    #_01C4B3: LDA.b #$1B ; SFX3.1B
    #_01C4B5: STA.w $012F

    #_01C4B8: LDA.b #$05
    #_01C4BA: STA.b $11

    .exit
    #_01C4BC: SEP #$30
  .no_cart
    JML $01CC5A
}

pushpc

; JML to return here 01CC5A
org $01CC08
RoomTag_Holes3:
JML RoomTag_ShutterDoorRequiresCart
; #_01CC08: LDA.b #$06
; #_01CC0A: BRA RoomTag_TriggerHoles

pullpc