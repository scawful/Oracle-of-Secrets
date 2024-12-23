; =========================================================
; Minecart Sprite
;
; Used in Goron Mines along with the SwitchTrack and
; Mineswitch sprite. Makes use of custom collision with
; somaria track corner tiles.
;
; The cart begins in an inactive state, horizontal or vertical
; and is activated by the player when they stand on the hitbox
; and press the B button. Based on the subtype of the cart,
; it will move in that direction until it encounters one of the
; following scenarions:
;
; Somaria Stop Tile    - Halt the cart and set its next direction
; Somaria Corner Track - Switch directions based on cart direction
;                        and corner tiletype.
; Somaria Any Track    - Switch direction based on player input
; Dungeon Transition   - Switch to Minecart follower and transition
;                        to the next room in a dungeon, spawning
;                        a new minecart sprite in the room at Link's
;                        location and configuring the direction to move
;                        in automatically (no B button to activate)
;
; NOTE: Current implementation forbades any two carts from co-existing
; as the !MinecartDirection variable will be overrode by the prep of
; the other cart and invalidate the current movement.

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

; SprSubtype and Minecart movement direction
; nesw
; 0 - north
; 1 - east
; 2 - south
; 3 - west
North = $00
East  = $01
South = $02
West  = $03
!MinecartDirection  = $012B

; Sprite Facing Direction
; udlr
; 0 - up
; 1 - down
; 2 - left
; 3 - right
Up = $00
Down = $01
Left = $02
Right = $03
!SpriteDirection    = $0DE0

; =========================================================

Sprite_Minecart_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Minecart_DrawTop    ; Draw behind Link
  JSR Sprite_Minecart_DrawBottom ; Draw in front of Link
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Minecart_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================
; The subtype of the minecart determines the direction it
; will move in, so if the subtype is 0 the cart will move
; north and start in WaitVert mode.

Sprite_Minecart_Prep:
{
  PHB : PHK : PLB

  STZ.w SprMiscF, X ; Clear the auto-move flag
  STZ.w SprMiscG, X ; Clear the active tossing flag

  ; If the subtype is > 4, then it's an active cart
  LDA.w SprSubtype, X : CMP.b #$04 : BCC +
    LDA.w SprSubtype, X : SEC : SBC.b #$04 : STA.w SprSubtype, X
    LDA.b #$01 : STA.w SprMiscF, X ; Set the auto-move flag
  +

  LDA.b #$04 : STA.w SprNbrOAM, X   ; Nbr Oam Entries
  LDA.b #$40 : STA.w SprGfxProps, X ; Impervious props
  LDA.b #$E0 : STA.w SprHitbox, X   ; Persist outside camera
  STZ.w SprDefl, X                  ; Sprite persist in dungeon
  STZ.w SprBump, X                  ; No bump damage
  STZ.w SprTileDie, X               ; Set interactive hitbox
  STZ.w !MinecartDirection
  STZ.w !SpriteDirection, X

  LDA.w SprSubtype, X : CMP.b #$00 : BEQ .north
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
    LDA.b #South : STA !MinecartDirection
    LDA.b #Down : STA !SpriteDirection, X
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
; Handle the tossing of the cart
; Changes the subtype of the cart to indicate the direction
; the cart is facing and sets the velocity of the cart
; based on the direction it is facing.

Minecart_HandleToss:
{
  LDA.b #$30 : STA.w SprTimerA, X
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

Minecart_HandleTossedCart:
{
  LDA.w SprMiscG, X : BEQ .not_tossed
    LDA.w SprHeight, X : BEQ .low_enough
      DEC.w SprHeight, X
      RTS
  .low_enough

  LDA.w SprTimerC, X : BNE .not_tossed
    LDA.w SprX, X : AND.b #$F8 : STA.w SprX, X
    LDA.w SprY, X : AND.b #$F8 : STA.w SprY, X
    STZ.w SprMiscG, X
    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X
    STZ.w SprHeight, X
  .not_tossed
  RTS
}

Minecart_HandleLiftAndToss:
{
  JSR CheckIfPlayerIsOn : BCC .not_tossing
    LDA.w LinkCarryOrToss : CMP.b #$02 : BNE .not_tossing
      JSR Minecart_HandleToss
  .not_tossing
  JSL Sprite_CheckIfLifted
  JSL Sprite_Move
  JSR Minecart_HandleTossedCart
  JSL ThrownSprite_TileAndSpriteInteraction_long
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
    LDA.w LinkCarryOrToss : AND #$03 : BNE .lifting
      LDA.w SprTimerA, X : BNE .not_ready
        JSR CheckIfPlayerIsOn : BCC .not_ready
          ; If the cart is active, we move immediately
          LDA.w SprMiscF, X : BNE .active_cart
            ; Check for B button
            LDA $F4 : AND.b #$80 : BEQ .not_ready
          .active_cart

          JSL Link_CancelDash
          LDA #$02 : STA.w LinkSomaria
          LDA #$01 : STA !LinkInCart
          ; Adjust player pos
          LDA.w SprCachedY : SEC : SBC #$0B : STA $20

          ; Check if the cart is facing east or west
          LDA.w SprSubtype, X : CMP.b #$03 : BNE +
            JSR Minecart_SetDirectionWest
            %GotoAction(5)  ; Minecart_MoveWest
            RTS
          +
          JSR Minecart_SetDirectionEast
          %GotoAction(3) ; Minecart_MoveEast
          RTS
      .not_ready
    .lifting
    JSR Minecart_HandleLiftAndToss
    RTS
  }

  ; -------------------------------------------------------
  ; 0x01
  Minecart_WaitVert:
  {
    %PlayAnimation(2,3,8)
    LDA.w LinkCarryOrToss : AND #$03 : BNE .lifting
      LDA.w SprTimerA, X : BNE .not_ready
        JSR CheckIfPlayerIsOn : BCC .not_ready
          ; If the cart is active, we move immediately
          LDA.w SprMiscF, X : BNE .active_cart
            ; Check for B button
            LDA $F4 : AND.b #$80 : BEQ .not_ready
          .active_cart

          JSL Link_CancelDash
          LDA.b #$02 : STA.w LinkSomaria
          LDA.b #$01 : STA.w !LinkInCart
          ; Adjust player pos
          LDA.w SprCachedY : SEC : SBC #$0B : STA $20

          ; Check if the cart is facing north or south
          LDA.w SprSubtype, X : BEQ +
            JSR Minecart_SetDirectionSouth
            %GotoAction(4)  ; Minecart_MoveSouth
            RTS
          +
          JSR Minecart_SetDirectionNorth
          %GotoAction(2)  ; Minecart_MoveNorth
          RTS
      .not_ready
    .lifting
    JSR Minecart_HandleLiftAndToss
    RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  Minecart_MoveNorth:
  {
    %PlayAnimation(2,3,8)
    JSR InitMovement
    LDA $36 : BNE .fast_speed
      LDA.b #-!MinecartSpeed : STA.w SprYSpeed, X
      JMP +
    .fast_speed
    LDA.b #-!DoubleSpeed : STA.w SprYSpeed, X
    +
    JSL Sprite_MoveVert

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
    JSR CheckForPlayerInput
    JSR HandlePlayerCameraAndMoveCart
    RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Minecart_MoveEast:
  {
    %PlayAnimation(0,1,8)
    JSR InitMovement
    LDA $36 : BNE .fast_speed
      LDA.b #!MinecartSpeed : STA.w SprXSpeed, X
      JMP +
    .fast_speed
    LDA.b #!DoubleSpeed : STA.w SprXSpeed, X
    +
    JSL Sprite_MoveHoriz

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
    JSR CheckForPlayerInput
    JSR HandlePlayerCameraAndMoveCart
    RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Minecart_MoveSouth:
  {
    %PlayAnimation(2,3,8)
    JSR InitMovement
    LDA $36 : BNE .fast_speed
      LDA.b #!MinecartSpeed : STA.w SprYSpeed, X
      JMP +
    .fast_speed
    LDA.b #!DoubleSpeed : STA.w SprYSpeed, X
    +
    JSL Sprite_MoveVert

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
    JSR CheckForPlayerInput
    JSR HandlePlayerCameraAndMoveCart
    RTS
  }

  ; -------------------------------------------------------
  ; 0x05
  Minecart_MoveWest:
  {
    %PlayAnimation(0,1,8)
    JSR InitMovement
    LDA   $36 : BNE .fast_speed
      LDA.b #-!MinecartSpeed : STA.w SprXSpeed, X
      JMP +
    .fast_speed
    LDA.b #-!DoubleSpeed : STA.w SprXSpeed, X
    +
    JSL Sprite_MoveHoriz

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
    JSR CheckForPlayerInput
    JSR HandlePlayerCameraAndMoveCart
    RTS
  }

  ; -------------------------------------------------------
  ; 0x06
  Minecart_Release:
  {
    JSR StopCart
    LDA.w SprTimerD, X : BNE .not_ready
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

HandlePlayerCameraAndMoveCart:
{
  LDA $22 : SEC : SBC $3F : STA $31
  LDA $20 : SEC : SBC $3E : STA $30
  PHX
  JSL Link_HandleMovingAnimation_FullLongEntry
  JSL HandleIndoorCameraAndDoors
  JSL Link_CancelDash
  PLX

  JSR HandleTileDirections
  JSR HandleDynamicSwitchTileDirections
  LDA #$35 : STA $012E ; Cart SFX
  RTS
}

StopCart:
{
  STZ.w LinkSomaria
  STZ.w SprYSpeed, X
  STZ.w SprXSpeed, X
  STZ.w !LinkInCart
  RTS
}

InitMovement:
{
  LDA.b $22 : STA.b $3F
  LDA.b $23 : STA.b $41
  LDA.b $20 : STA.b $3E
  LDA.b $21 : STA.b $40
  RTS
}

Minecart_SetDirectionNorth:
{
  LDA.b #North : STA.w SprSubtype, X : STZ.w !MinecartDirection
  LDA.b #Up  : STA !SpriteDirection, X
  RTS
}

Minecart_SetDirectionEast:
{
  LDA.b #East : STA.w SprSubtype, X : STA.w !MinecartDirection
  LDA.b #Right  : STA !SpriteDirection, X
  RTS
}

Minecart_SetDirectionSouth:
{
  LDA.b #South : STA.w SprSubtype, X : STA.w !MinecartDirection
  LDA.b #Down : STA.w !SpriteDirection, X
  RTS
}

Minecart_SetDirectionWest:
{
  LDA.b #West : STA.w SprSubtype, X : STA.w !MinecartDirection
  LDA.b #Left : STA.w !SpriteDirection, X
  RTS
}


; =========================================================
; A = $0FA5

CheckForOutOfBounds:
{
  CMP.b #$02 : BNE .not_out_of_bounds
    ; If the tile is out of bounds, release the cart
    LDA #$40 : STA.w SprTimerD, X
    %GotoAction(6) ; Minecart_Release
    RTS
  .not_out_of_bounds
  RTS
}

CheckForStopTiles:
{
  ; Check if the tile is a stop tile
  CMP.b #$B7 : BEQ .stop_north
  CMP.b #$B8 : BEQ .stop_south
  CMP.b #$B9 : BEQ .stop_west
  CMP.b #$BA : BEQ .stop_east
    RTS

  .stop_north
  JSR Minecart_SetDirectionSouth
  JMP .go_vert

  .stop_south
  JSR Minecart_SetDirectionNorth

  .go_vert
    %SetTimerA($40)
    JSR StopCart
    %GotoAction(1) ; Minecart_WaitVert
    JSL Link_ResetProperties_A
    RTS

  .stop_east
  JSR Minecart_SetDirectionWest
  JMP .go_horiz

  .stop_west
  JSR Minecart_SetDirectionEast

  .go_horiz
    %SetTimerA($40)
    JSR StopCart
    %GotoAction(0) ; Minecart_WaitHoriz
    JSL Link_ResetProperties_A
    RTS
}

CheckForCornerTiles:
{
  CMP.b #$B2 : BEQ .check_direction
  CMP.b #$B3 : BEQ .check_direction
  CMP.b #$B4 : BEQ .check_direction
  CMP.b #$B5 : BEQ .check_direction
    SEC
    RTS
  .check_direction
  LDA.w SprSubtype, X
  ASL #2  ; Multiply by 4 to offset rows in the lookup table
  STA $07 ; Store the action index in $07

  ; Subtract $B2 to normalize the tile type to 0 to 3
  LDA.w SPRTILE : SEC : SBC.b #$B2
  ; Add action index to tile type offset for the composite index
  ; Transfer to Y to use as an offset for the rows
  CLC : ADC.w $07 : TAY
  LDA.w .DirectionTileLookup, Y : TAY
  CPY #$01 : BEQ .move_north
  CPY #$02 : BEQ .move_east
  CPY #$03 : BEQ .move_south
  CPY #$04 : BEQ .move_west
    JMP .done

  .move_north
  JSR Minecart_SetDirectionNorth
  %GotoAction(2) ; Minecart_MoveNorth
  LDA.w SprX, X : AND #$F8 : STA.w SprX, X
  JMP .done

  .move_east
  JSR Minecart_SetDirectionEast
  LDA #$03 : STA !SpriteDirection, X
  LDA.w SprY, X : AND #$F8 : STA.w SprY, X
  %GotoAction(3) ; Minecart_MoveEast
  JMP .done

  .move_south
  JSR Minecart_SetDirectionSouth
  %GotoAction(4) ; Minecart_MoveSouth
  LDA.w SprX, X : AND #$F8 : STA.w SprX, X
  JMP .done

  .move_west
  JSR Minecart_SetDirectionWest
  LDA.w SprY, X : AND #$F8 : STA.w SprY, X
  %GotoAction(5) ; Minecart_MoveWest

  .done
  CLC
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

CheckForTrackTiles:
{
  CMP.b #$B0 : BEQ .horiz
  CMP.b #$B1 : BEQ .vert
  CMP.b #$BB : BEQ .horiz
  CMP.b #$BC : BEQ .vert
    JMP .done

  .horiz
  ; Are we moving left or right?
  LDA.w SprSubtype, X : CMP.b #$03 : BEQ .inverse_horiz_velocity
    LDA.b #!MinecartSpeed : STA.w SprXSpeed, X
    LDA.b #East : STA !MinecartDirection
    JMP .done
  .inverse_horiz_velocity
  LDA.b #-!MinecartSpeed : STA.w SprXSpeed, X
  LDA.b #West : STA !MinecartDirection
  JMP .done
  .vert
  ; Are we moving up or down?
  LDA.w SprSubtype, X : CMP.b #$00 : BEQ .inverse_vert_velocity
    LDA.b #!MinecartSpeed : STA.w SprYSpeed, X
    JMP .done
  .inverse_vert_velocity
  LDA.b #-!MinecartSpeed : STA.w SprYSpeed, X
  .done
  RTS
}

HandleTileDirections:
{
  LDA.w SprTimerA, X : BEQ +
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
  LDA.b #$00 : JSL Sprite_GetTileAttr
  LDA.w $0FA5
  JSR CheckForOutOfBounds
  JSR CheckForStopTiles
  JSR CheckForCornerTiles : BCC .done
  ; JSR CheckForTrackTiles
  .done
  LDA #$0F : STA.w SprTimerA, X
  RTS
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
      LDA.w SwitchRam : BNE .go_west
        JSR Minecart_SetDirectionEast
        %GotoAction(3) ; Minecart_MoveEast
        RTS
      .go_west
      JSR Minecart_SetDirectionWest
      %GotoAction(5) ; Minecart_MoveWest
      RTS

    .north_or_south
    LDA.w SwitchRam : BNE .go_south
      JSR Minecart_SetDirectionNorth
      %GotoAction(2) ; Minecart_MoveNorth
      RTS
    .go_south
    JSR Minecart_SetDirectionSouth
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
    JSR Minecart_SetDirectionNorth
    %GotoAction(2) ; Minecart_MoveNorth
    BRA   .return

  .not_pressing_up
  LDA.b $00 : AND.b #$04 : BEQ .not_pressing_down
    JSR Minecart_SetDirectionSouth
    %GotoAction(4) ; Minecart_MoveSouth
    BRA   .return

  .not_pressing_down
  LDA.b $00 : AND.b #$02 : BEQ .not_pressing_left
    JSR Minecart_SetDirectionWest
    %GotoAction(5) ; Minecart_MoveWest
    BRA   .return

  .not_pressing_left
  LDA.b $00 : AND.b #$01 : BEQ .return
    JSR Minecart_SetDirectionEast
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
  LDA $22 : CLC : ADC #$0009 : CMP.w SprCachedX : BCC .left
  LDA $22 : SEC : SBC #$0009 : CMP.w SprCachedX : BCS .right
  LDA $20 : CLC : ADC #$0012 : CMP.w SprCachedY : BCC .up
  LDA $20 : SEC : SBC #$0012 : CMP.w SprCachedY : BCS .down
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

; =========================================================
; Shutter door only opens if the player is in the cart

RoomTag_ShutterDoorRequiresCart:
{
  LDA.w !LinkInCart : BEQ .no_cart
    REP #$30
    LDX.w #$0000 : CPX.w $0468 : BEQ .exit
      STZ.w $0468
      STZ.w $068E
      STZ.w $0690
      SEP #$30

      ; SFX3.1B
      LDA.b #$1B : STA.w $012F
      LDA.b #$05 : STA.b $11
    .exit
    SEP #$30
  .no_cart
  JML $01CC5A
}

pushpc

; JML to return here 01CC5A
;org $01CC08
;RoomTag_Holes3:
;JML RoomTag_ShutterDoorRequiresCart
; LDA.b #$06 : BRA RoomTag_TriggerHoles

pullpc

