; =========================================================
; Minecart Sprite
;
; Used in Goron Mines along with the SwitchTrack and
; Mineswitch sprite. Makes use of custom collision with
; somaria track corner tiles.
;
; The cart begins in an inactive state, horizontal or vertical
; and is activated by the player when they stand on the hitbox
; and press the B button. Based on the SprMiscB of the cart,
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

; SprMiscB and Minecart movement direction
; nesw
; 0 - north
; 1 - east
; 2 - south
; 3 - west
North = $00
East  = $01
South = $02
West  = $03
!MinecartDirection  = $0DE0 ; = SprMiscC

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

; A "track" is one minecart that can exist in multiple different places.
; Allowing the player to leave a minecart in one room and then still find
; it in the same place upon returning to that room.

; There is a total possibility of 0x20 different subtypes that can be set.
; Therefore there can be a total of 0x20 different tracks.

; This value is used to keep track of which room the minecart was left
; in. Currently #$00 is reserved to keep track of new tracks that have
; not been used yet so tracks will not work when stopped in room 00. Up
; to $0768 used which is all free ram.
!MinecartTrackRoom = $0728

; Track X position. This is used to keep track of the possibility of
; there being more than one stop per track in the same room. Up to $07A8
; used which is all free ram.
!MinecartTrackX =  $0768

; Track X position. This is used to keep track of the possibility of
; there being more than one stop per track in the same room. Up to $07E8
; used which is all free ram.
!MinecartTrackY = $07A8

; This is used to keep track of which track we are on while riding
; the cart. We can only use one cart at a time so this is only 1 byte.
!MinecartTrackCache = $07E8

; This is used to keep track of which direction we are going during room
; transitions. We can only use one cart at a time so this is only 1 byte.
!MinecartDirectionCache = $07E9

; This is used to keep track of which cart in a room we are riding. This
; is based of the X value used to index sprite arrays.
!MinecartCurrent = $07EA

; =========================================================
; Collision setup:

; 0xB0 - Horizontal straight
; 0xB1 - Vertical straight
; 0xB2 - Top left corner
; 0xB3 - Bottom left corner
; 0xB4 - Top right corner
; 0xB5 - Bottom right corner
; 0xB6 - 4 way intersection
; 0xB7 - Stop north
; 0xB8 - Stop south
; 0xB9 - Stop west
; 0xBA - Stop east
; 0xBB - North T intersection
; 0xBC - South T intersection
; 0xBD - East T intersection
; 0xBE - West T intersection
; 0xD0 - Top left switch
; 0xD1 - Bottom left switch
; 0xD2 - Top right switch
; 0xD3 - Bottom right switch

; TL switch turns into TR when on
; BL switch turns into TL when on
; TR switch turns into BR when on
; BR switch turns into BL when on

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
; The SprMiscB of the minecart determines the direction it
; will move in, so if the SprMiscB is 0 the cart will move
; north and start in WaitVert mode.

Sprite_Minecart_Prep:
{
  PHB : PHK : PLB

  JSR UpdateCachedCoords

  LDA.w SprSubtype, X : ASL : TAY

  ; If Link is on the same track as this cart's track AND this cart is
  ; not the active cart, kill the cart.
  LDA.w SprSubtype, X : CMP.w !MinecartTrackCache : BNE .notSameTrack
    LDA.b !LinkInCart : BEQ .notInCart
      ; If the SprMiscB is > 4, then it's an active cart. This should only
      ; be the case when transitioning from a follower.
      LDA.w SprMiscB, X : CMP.b #$04 : BCS .active1
        BRA .killMinecart
    .notInCart
  .notSameTrack

  REP #$20
  ; Check if the track has already been initialized. If not we need to
  ; tell the game where the cart on the track starts
  LDA.w !MinecartTrackRoom, Y : BNE .trackAlreadySetUp
    LDA.w .TrackStartingX, Y : STA.w !MinecartTrackX, Y
    LDA.w .TrackStartingY, Y : STA.w !MinecartTrackY, Y
    LDA.w .TrackStartingRooms, Y : STA.w !MinecartTrackRoom, Y
  .trackAlreadySetUp

  ; Check if we are currently in the room where the track was left.
  CMP.b $A0 : BEQ .inRoom
    .killMinecart
    SEP #$20
    STZ.w SprState, X
    PLB
    RTL
  .inRoom

  ; Check if the coordinates match, if not kill the sprite.
  ; If cart isn't appearing in room, check here for values to match
  ; against the MinecartTrack table values.
  ; print "MinecartPrep_CheckCoords ", pc
  LDA.w !MinecartTrackX, Y : CMP.w SprCachedX : BNE .killMinecart
    LDA.w !MinecartTrackY, Y : CMP.w SprCachedY : BNE .killMinecart
      SEP #$20
  .active1

  STZ.w SprMiscG, X ; Clear the active tossing flag

  LDA.b #$04 : STA.w SprNbrOAM, X   ; Nbr Oam Entries
  LDA.b #$40 : STA.w SprGfxProps, X ; Impervious props
  LDA.b #$E0 : STA.w SprHitbox, X   ; Persist outside camera
  STZ.w SprDefl, X                  ; Sprite persist in dungeon
  STZ.w SprBump, X                  ; No bump damage
  STZ.w SprTileDie, X               ; Set interactive hitbox

  STZ.w !MinecartDirection, X
  STZ.w !SpriteDirection, X

  ; If the SprMiscB is > 4, then it's an active cart. This should only
  ; be the case when transitioning from a follower.
  LDA.w SprMiscB, X : CMP.b #$04 : BCC .notActive
    SEC : SBC.b #$04 : STA.w SprMiscB, X

    ; Go directly to the direction action we are facing. We add 2 to
    ; skip the Minecart_WaitHoriz and Minecart_WaitVert actions.
    CLC : ADC.b #$02 : STA.w SprAction, X

    BRA .active2
  .notActive
    ; Setup Minecart position to look for tile IDs
    ; We use AND #$F8 to clamp to a 8x8 grid.
    LDA.w SprY, X : AND #$F8 : STA.b $00
    LDA.w SprYH, X           : STA.b $01

    LDA.w SprX, X : AND #$F8 : STA.b $02
    LDA.w SprXH, X           : STA.b $03

    ; Fetch tile attributes based on current coordinates
    LDA.b #$00 : JSL Sprite_GetTileAttr

    ; Set our starting direction based on the stop tile we are on.
    ; This means minecarts should always be placed on top of a stop tile.
    LDA.w SPRTILE
    CMP.b #$B7 : BEQ .goSouth
    CMP.b #$B8 : BEQ .goNorth
    CMP.b #$B9 : BEQ .goEast
    CMP.b #$BA : BEQ .goWest
    .goNorth
      LDA.b #North : STA.w SprMiscB, X
      %GotoAction(1) ; Minecart_WaitVert
      JMP .done2
    .goEast
      LDA.b #East : STA.w SprMiscB, X
      %GotoAction(0) ; Minecart_WaitHoriz
      JMP .done2
    .goSouth
      LDA.b #South : STA.w SprMiscB, X
      %GotoAction(1) ; Minecart_WaitVert
      JMP .done2
    .goWest
      LDA.b #West : STA.w SprMiscB, X
      %GotoAction(0) ; Minecart_WaitHoriz
    .done2
  .active2

  STZ.w SprTimerB, X
  LDA.w SprMiscB, X : CMP.b #$00 : BEQ .north
                      CMP.b #$01 : BEQ .east
                      CMP.b #$02 : BEQ .south
                      CMP.b #$03 : BEQ .west
  .north
    ; Both !MinecartDirection and !SpriteDirection set to 0 earlier.
    BRA .vert

  .south
    LDA.b #South : STA !MinecartDirection, X
    LDA.b #Down  : STA !SpriteDirection, X

    .vert
    %PlayAnimation(2,3,8)
    LDA.b #$02 : STA.w $0D90, X

    BRA .done
  .east
    LDA.b #East  : STA !MinecartDirection, X
    LDA.b #Right : STA !SpriteDirection, X

    BRA .horz

  .west
    LDA.b #West : STA !MinecartDirection, X
    LDA.b #Left : STA !SpriteDirection, X

    .horz
    %PlayAnimation(0,1,8)
    LDA.b #$00 : STA.w $0D90, X

  .done
  PLB
  RTL

  incsrc "data/minecart_tracks.asm"
}

; =========================================================

Sprite_Minecart_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

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
          ; Check for B button
          LDA $F4 : AND.b #$80 : BEQ .not_ready

          ; Save what track we are currently riding.
          LDA.w SprSubtype, X : STA.w !MinecartTrackCache

          JSL Link_CancelDash
          LDA.b #$02 : STA.w LinkSomaria
          LDA.b #$01 : STA.w !LinkInCart
          ; Adjust player pos
          LDA.w SprCachedY : SEC : SBC #$0B : STA $20

          ; Check if the cart is facing east or west
          LDA.w SprMiscB, X : CMP.b #$03 : BNE +
            JSR Minecart_SetDirectionWest
            %GotoAction(5) ; Minecart_MoveWest
            RTS
          +
          JSR Minecart_SetDirectionEast
          %GotoAction(3) ; Minecart_MoveEast
          RTS
      .not_ready
    .lifting

    if !ENABLE_MINECART_LIFT_TOSS
      JSR Minecart_HandleLiftAndToss
    endif
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
          ; Check for B button
          LDA $F4 : AND.b #$80 : BEQ .not_ready

          ; Save what track we are currently riding.
          LDA.w SprSubtype, X : STA.w !MinecartTrackCache

          JSL Link_CancelDash
          LDA.b #$02 : STA.w LinkSomaria
          LDA.b #$01 : STA.w !LinkInCart
          ; Adjust player pos
          LDA.w SprCachedY : SEC : SBC #$0B : STA $20

          ; Check if the cart is facing north or south
          LDA.w SprMiscB, X : BEQ +
            JSR Minecart_SetDirectionSouth
            %GotoAction(4) ; Minecart_MoveSouth
            RTS
          +
          JSR Minecart_SetDirectionNorth
          %GotoAction(2) ; Minecart_MoveNorth
          RTS
      .not_ready
    .lifting

    if !ENABLE_MINECART_LIFT_TOSS
      JSR Minecart_HandleLiftAndToss
    endif
    RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  Minecart_MoveNorth:
  {
    %PlayAnimation(2,3,8)
    JSR InitMovement

    ; Used for an un-implemented speed switch feature.
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
    JSR HandlePlayerCameraAndMoveCart

    JSR HandleTileDirections

    RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Minecart_MoveEast:
  {
    %PlayAnimation(0,1,8)
    JSR InitMovement

    ; Used for an un-implemented speed switch feature.
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
    JSR HandlePlayerCameraAndMoveCart

    JSR HandleTileDirections

    RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Minecart_MoveSouth:
  {
    %PlayAnimation(2,3,8)
    JSR InitMovement

    ; Used for an un-implemented speed switch feature.
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
    JSR HandlePlayerCameraAndMoveCart

    JSR HandleTileDirections

    RTS
  }

  ; -------------------------------------------------------
  ; 0x05
  Minecart_MoveWest:
  {
    %PlayAnimation(0,1,8)
    JSR InitMovement

    ; Used for an un-implemented speed switch feature.
    LDA $36 : BNE .fast_speed
      LDA.b #-!MinecartSpeed : STA.w SprXSpeed, X
      JMP +
    .fast_speed
    LDA.b #-!DoubleSpeed : STA.w SprXSpeed, X
    +

    JSL Sprite_MoveHoriz

    ; Get direction of the cart (0 to 3)
    LDY.w !SpriteDirection, X
    JSL DragPlayer
    JSR HandlePlayerCameraAndMoveCart

    JSR HandleTileDirections

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
      %GotoAction(0) ; Minecart_WaitHoriz
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

  LDA #$35 : STA $012E ; Cart SFX
  RTS
}

StopCart:
{
  STZ.w LinkSomaria
  STZ.w SprYSpeed, X
  STZ.w SprXSpeed, X
  STZ.w !LinkInCart

  JSR RoundCoords

  LDA.w SprSubtype, X : ASL : TAY

  REP #$20
  LDA.w SprCachedX : STA.w !MinecartTrackX, Y
  LDA.w SprCachedY : STA.w !MinecartTrackY, Y
  LDA.w $A0 : STA.w !MinecartTrackRoom, Y
  SEP #$20

  ; !MinecartCurrent is an 8-bit sprite slot index, but it can be read with
  ; X=16-bit in transition hooks. Always keep the high byte cleared to avoid
  ; out-of-range indexing corruption if X width leaks.
  REP #$20
  STZ.w !MinecartCurrent
  SEP #$20

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
  ; Reset the animation timer and set the animation early to make it
  ; more snappy.
  STZ.w SprTimerB, X
  %PlayAnimation(2,3,8)

  LDA.b #North : STA.w SprMiscB, X
  STA.w !MinecartDirection, X : STA.w !MinecartDirectionCache
  LDA.b #Up    : STA !SpriteDirection, X

  PHP
  REP #$20
  TXA : AND.w #$00FF : STA.w !MinecartCurrent
  PLP
  RTS
}

Minecart_SetDirectionEast:
{
  ; Reset the animation timer and set the animation early to make it
  ; more snappy.
  STZ.w SprTimerB, X
  %PlayAnimation(0,1,8)

  LDA.b #East  : STA.w SprMiscB, X
  STA.w !MinecartDirection, X : STA.w !MinecartDirectionCache
  LDA.b #Right : STA !SpriteDirection, X

  PHP
  REP #$20
  TXA : AND.w #$00FF : STA.w !MinecartCurrent
  PLP
  RTS
}

Minecart_SetDirectionSouth:
{
  ; Reset the animation timer and set the animation early to make it
  ; more snappy.
  STZ.w SprTimerB, X
  %PlayAnimation(2,3,8)

  LDA.b #South : STA.w SprMiscB, X
  STA.w !MinecartDirection, X : STA.w !MinecartDirectionCache
  LDA.b #Down  : STA.w !SpriteDirection, X

  PHP
  REP #$20
  TXA : AND.w #$00FF : STA.w !MinecartCurrent
  PLP
  RTS
}

Minecart_SetDirectionWest:
{
  ; Reset the animation timer and set the animation early to make it
  ; more snappy.
  STZ.w SprTimerB, X
  %PlayAnimation(0,1,8)

  LDA.b #West : STA.w SprMiscB, X
  STA.w !MinecartDirection, X : STA.w !MinecartDirectionCache
  LDA.b #Left : STA.w !SpriteDirection, X

  PHP
  REP #$20
  TXA : AND.w #$00FF : STA.w !MinecartCurrent
  PLP
  RTS
}

; =========================================================

HandleTileDirections:
{
  ; If the cart got disconnected from the player, release them.
  JSR CheckIfPlayerIsOn : BCS .player_on_cart
    %GotoAction(6) ; Minecart_Release
    RTS
  .player_on_cart

  ; Setup Minecart position to look for tile IDs
  ; We use AND #$F8 to clamp to a 8x8 grid.
  LDA.w SprY, X : AND #$F8 : STA.b $00
  LDA.w SprYH, X           : STA.b $01

  LDA.w SprX, X : AND #$F8 : STA.b $02
  LDA.w SprXH, X           : STA.b $03

  ; Fetch tile attributes based on current coordinates
  LDA.b #$00 : JSL Sprite_GetTileAttr

  ; Debug: put the tile type into the rupee SRM.
  STA.l $7EF362 : STA.l $7EF360
  LDA.b #$00 : STA.l $7EF363 : STA.l $7EF361

  JSR CheckForOutOfBounds : BCC .notOutOfBounds
    JSR RoundCoords

    BRA .done
  .notOutOfBounds

  JSR CheckForStopTiles : BCC .noStop
    JSR RoundCoords

    BRA .done
  .noStop

  JSR CheckForPlayerInput : BCC .noInput
    JSR RoundCoords

    BRA .done
  .noInput

  JSR CheckForCornerTiles : BCC .noCorner
    JSR RoundCoords

    BRA .done
  .noCorner

  JSR HandleDynamicSwitchTileDirections : BCC .noSwitch
    JSR RoundCoords

  .noSwitch

  .done
  RTS
}

; =========================================================

CheckForOutOfBounds:
{
  LDA.w SPRTILE : CMP.b #$02 : BNE .not_out_of_bounds
    ; If the tile is out of bounds, release the cart
    LDA #$40 : STA.w SprTimerD, X
    %GotoAction(6) ; Minecart_Release

    SEC
    RTS
  .not_out_of_bounds

  CLC
  RTS
}

; CLC if no stop occured, SEC if stop occured.
CheckForStopTiles:
{
  LDA.w SPRTILE
  CMP.b #$B7 : BEQ .check_direction
  CMP.b #$B8 : BEQ .check_direction
  CMP.b #$B9 : BEQ .check_direction
  CMP.b #$BA : BEQ .check_direction
    CLC
    RTS
  .check_direction

  LDA.w SprMiscB, X
  ASL #2  ; Multiply by 4 to offset rows in the lookup table
  STA $07 ; Store the action index in $07

  ; Subtract $B7 to normalize the tile type to 0 to 3
  LDA.w SPRTILE : SEC : SBC.b #$B7

  CLC : ADC.w $07 : TAY
  LDA.w .DirectionTileLookup, Y

  ; Check if the tile is a stop tile
  CMP.b #$01 : BEQ .stop_north
  CMP.b #$02 : BEQ .stop_east
  CMP.b #$03 : BEQ .stop_south
  CMP.b #$04 : BEQ .stop_west
    CLC
    RTS

  .stop_north
  ; If the direction is already south, that means we have already stopped
  ; or are heading south and don't need to stop.
  JSR Minecart_SetDirectionSouth
  JMP .go_vert

  .stop_south
  ; If the direction is already north, that means we have already stopped
  ; or are heading north and don't need to stop.
  JSR Minecart_SetDirectionNorth

  .go_vert
    %SetTimerA($40)
    JSR StopCart
    %GotoAction(1) ; Minecart_WaitVert
    JSL Link_ResetProperties_A

    SEC
    RTS

  .stop_east
  ; If the direction is already west, that means we have already stopped
  ; or are heading west and don't need to stop.
  JSR Minecart_SetDirectionWest
  JMP .go_horiz

  .stop_west
  ; If the direction is already east, that means we have already stopped
  ; or are heading east and don't need to stop.
  JSR Minecart_SetDirectionEast

  .go_horiz
    %SetTimerA($40)
    JSR StopCart
    %GotoAction(0) ; Minecart_WaitHoriz
    JSL Link_ResetProperties_A

    SEC
    RTS

  ; Direction to move on tile collision
  ; 00 - stop or nothing
  ; 01 - north
  ; 02 - east
  ; 03 - south
  ; 04 - west
  .DirectionTileLookup
  {
    ; north east south west
    db $01, $00, $00, $00 ; North
    db $00, $00, $00, $02 ; East
    db $00, $03, $00, $00 ; South
    db $00, $00, $04, $00 ; West
  }
}

; Check for input from the user (u,d,l,r) on tile B6, BD
; CLC if not on an input tile or there was no input recieved.
CheckForPlayerInput:
{
  ; Load the tile index
  LDA.w SPRTILE : CMP.b #$B6 : BEQ .can_input ; Intersection
                  CMP.b #$BB : BEQ .can_input ; North T
                  CMP.b #$BC : BEQ .can_input ; South T
                  CMP.b #$BD : BEQ .can_input ; East T
                  CMP.b #$BE : BEQ .can_input ; West T
    CLC
    RTS
  .can_input
  ; Normalize the tile.
  SEC : SBC.b #$B6 : TAY

  ; Get an offset based on the tile the get the allowed directions.
  LDA.w .intersectionMap, Y

  ; Add the direction the cart is going to prevent the cart from
  ; returning from where it came from.
  CLC : ADC.w !SpriteDirection, X : STA.b $06 : TAY

  ; Filter the input.
  LDA $F0 : AND.w .d_pad_press, Y : STA $05 : AND.b #$08 : BEQ .not_pressing_up
    .north
    JSR Minecart_SetDirectionNorth
    %GotoAction(2) ; Minecart_MoveNorth

    SEC
    RTS

  .not_pressing_up
  LDA.b $05 : AND.b #$04 : BEQ .not_pressing_down
    .south
    JSR Minecart_SetDirectionSouth
    %GotoAction(4) ; Minecart_MoveSouth

    SEC
    RTS

  .not_pressing_down
  LDA.b $05 : AND.b #$02 : BEQ .not_pressing_left
    .west
    JSR Minecart_SetDirectionWest
    %GotoAction(5) ; Minecart_MoveWest

    SEC
    RTS

  .not_pressing_left
  LDA.b $05 : AND.b #$01 : BEQ .return
    .east
    JSR Minecart_SetDirectionEast
    %GotoAction(3) ; Minecart_MoveEast

    SEC
    RTS
  .return

  ; If no input was detected, we will assign a direction based on our
  ; current direction and what junction we are encountering, this is to
  ; prevent us from going off the top of a north junction or down off a
  ; south one for example.
  LDY.b $06
  LDA.w .defaultDirection, Y : CMP.b #North : BEQ .north
                               CMP.b #South : BEQ .south
                               CMP.b #East  : BEQ .east
                               CMP.b #West  : BEQ .west

  ; If we made it here, no input was found and no default directions were
  ; chosen.
  CLC
  RTS

  ; When setting the values for the "allowed" directions the cart can go
  ; on the junctions for both tables we do not allow the direction we are
  ; already going. If do allow the current direction the cart will get
  ; locked on the junction because it will constantly be coordinate
  ; clamped to within the junction tile, preventing it from escaping that
  ; tile.
  .d_pad_press
    ; udlr
    ; up, down, left, right
    db $0F, $0F, $0F, $0F ; Nothing
    db $0B, $07, $0E, $0D ; $B6 Intersection
    db $03, $03, $04, $04 ; $BB North T
    db $03, $03, $08, $08 ; $BC South T
    db $02, $02, $0C, $0C ; $BD East T
    db $01, $01, $0C, $0C ; $BE West T

  ; #$04 is don't change direction.
  .defaultDirection
    ; udlr
    ;  up,   down, left,  right
    db $04,  $04,  $04,   $04   ; Nothing
    db $04,  $04,  $04,   $04   ; $B6 Intersection
    db East, $04,  $04,   $04   ; $BB North T
    db $04,  East, $04,   $04   ; $BC South T
    db $04,  $04,  $04,   North ; $BD East T
    db $04,  $04,  North, $04   ; $BE West T

  .intersectionMap
    ;   B6,  B7,  B8,  B9,  BA,  BB,  BC,  BD,  BE
    db $04, $00, $00, $00, $00, $08, $0C, $10, $14
}

CheckForCornerTiles:
{
  LDA.w SPRTILE
  CMP.b #$B2 : BEQ .check_direction ; TL
  CMP.b #$B3 : BEQ .check_direction ; BL
  CMP.b #$B4 : BEQ .check_direction ; TR
  CMP.b #$B5 : BEQ .check_direction ; BR
    CLC
    RTS
  .check_direction
  LDA.w SprMiscB, X
  ASL #2  ; Multiply by 4 to offset rows in the lookup table
  STA $07 ; Store the action index in $07

  ; Subtract $B2 to normalize the tile type to 0 to 3
  LDA.w SPRTILE : SEC : SBC.b #$B2
  ; Add action index to tile type offset for the composite index
  ; Transfer to Y to use as an offset for the rows
  CLC : ADC.b $07 : TAY
  LDA.w .DirectionTileLookup, Y
  CMP.b #$01 : BEQ .move_north
  CMP.b #$02 : BEQ .move_east
  CMP.b #$03 : BEQ .move_south
  CMP.b #$04 : BEQ .move_west
    CLC
    RTS

  .move_north
  JSR Minecart_SetDirectionNorth
  %GotoAction(2) ; Minecart_MoveNorth
  BRA .done

  .move_east
  JSR Minecart_SetDirectionEast
  %GotoAction(3) ; Minecart_MoveEast
  BRA .done

  .move_south
  JSR Minecart_SetDirectionSouth
  %GotoAction(4) ; Minecart_MoveSouth
  BRA .done

  .move_west
  JSR Minecart_SetDirectionWest
  %GotoAction(5) ; Minecart_MoveWest

  .done
  SEC
  RTS

  ; Direction to move on tile collision
  ; 00 - stop or nothing
  ; 01 - north
  ; 02 - east
  ; 03 - south
  ; 04 - west
  .DirectionTileLookup
  {
    ;   TL,  BL,  TR,  BR   Coming from the:
    db $02, $00, $04, $00 ; North
    db $00, $00, $03, $01 ; East
    db $00, $02, $00, $04 ; South
    db $03, $01, $00, $00 ; West
  }
}

; Check for the switch_track sprite and move based on the
; state of that sprite.
HandleDynamicSwitchTileDirections:
{
  ; Check for the switch tile.
  LDA.w SPRTILE : CMP.b #$D0 : BEQ .onSwitchTile
                  CMP.b #$D1 : BEQ .onSwitchTile
                  CMP.b #$D2 : BEQ .onSwitchTile
                  CMP.b #$D3 : BEQ .onSwitchTile
    CLC
    RTS
  .onSwitchTile

  ; Find out if the sprite $B0 is in the room and if we are
  ; currently touching it.
  JSR CheckTrackSpritePresence : BCS .B0Present
    CLC
    RTS
  .B0Present

  LDA.w SprMiscB, X
  ASL #3 ; Multiply by 8 to offset rows in the lookup table
  STA.b $07 ; Store the action index in $07

  ; Get the subtype of the track so that we can get its on/off state.
  LDA.w SprSubtype, Y : TAY

  ; Normalize the tile data and get the type of track (TL, BL, TR, BR) and
  ; x2 so that we can read the correct column in the table.
  LDA.w SPRTILE : SEC : SBC.b #$D0 : ASL

  ; Add the current direction and the state of the switch to determine
  ; which direction we should go next.
  CLC : ADC.w SwitchRam, Y : CLC : ADC.b $07 : TAY
  LDA.w .DirectionTileLookup, Y
  CMP.b #$01 : BEQ .move_north
  CMP.b #$02 : BEQ .move_east
  CMP.b #$03 : BEQ .move_south
  CMP.b #$04 : BEQ .move_west
    CLC
    RTS

  .move_north
  JSR Minecart_SetDirectionNorth
  %GotoAction(2) ; Minecart_MoveNorth
  BRA .done

  .move_east
  JSR Minecart_SetDirectionEast
  %GotoAction(3) ; Minecart_MoveEast
  BRA .done

  .move_south
  JSR Minecart_SetDirectionSouth
  %GotoAction(4) ; Minecart_MoveSouth
  BRA .done

  .move_west
  JSR Minecart_SetDirectionWest
  %GotoAction(5) ; Minecart_MoveWest

  .done
  SEC
  RTS

  ; Direction to move on tile collision
  ; 00 - stop or nothing
  ; 01 - north
  ; 02 - east
  ; 03 - south
  ; 04 - west
  .DirectionTileLookup
  {
    ;  Off,  On, Off,  On, Off,  On, Off,  On
    ;   TL,  TL,  BL,  BL,  TR,  TR,  BR,  BR   Coming from the:
    db $02, $04, $00, $02, $04, $00, $00, $00 ; North
    db $00, $03, $00, $00, $03, $01, $01, $00 ; East
    db $00, $00, $02, $00, $00, $04, $04, $02 ; South
    db $03, $00, $01, $03, $00, $00, $00, $01 ; West
  }

  ; $D0 TL turns into TR when on.
  ; $D1 BL turns into TL when on.
  ; $D2 TR turns into BR when on.
  ; $D3 BR turns into BL when on.
}

; =========================================================

; $04 = sprite index of sprite ID $B0
; SEC if sprite is present.
CheckTrackSpritePresence:
{
  LDY.b #$10
  .loop
    DEY
    ; Check if the sprite is $B0
    LDA.w $0E20, Y : CMP.b #$B0 : BNE .not_b0
      ; Check if the high bytes of the coordinates match.
      LDA.w SprYH, X : CMP.w SprYH, Y : BNE .not_b0
      LDA.w SprXH, X : CMP.w SprXH, Y : BNE .not_b0
        ; Check if the low bytes match but round the cart's coordinates.
        ; Offset the Y by 8 so that we match the cart
        LDA.w SprY, X : CLC : ADC.b #$04 : AND.b #$F8 : CLC : ADC.b #$08
        CMP.w SprY, Y : BNE .not_b0
        LDA.w SprX, X : CLC : ADC.b #$04 : AND.b #$F8
        CMP.w SprX, Y : BNE .not_b0
          STY.b $04
          SEC ; Set flag indicating sprite ID $B0 is present.
          BRA .done
    .not_b0
  CPY.b #$00 : BNE .loop
  CLC ; Assume sprite ID $B0 is not present

  .done
  RTS
}

; SEC if player is overlapping the sprite
; CLC if player is outside the bounds
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

pushpc

org $0DFA68 ; @hook module=Sprites
  RebuildHUD_Keys:

org $028260 ; @hook module=Sprites
  JSL ResetTrackVars

pullpc

ResetTrackVars:
{
  ; Replaced code.
  JSL.l RebuildHUD_Keys

  LDA.b #$00 : STA.w !MinecartTrackCache
  LDX.b #$41
  .loop
  DEX
    STA.w !MinecartTrackRoom, X
    STA.w !MinecartTrackX, X
    STA.w !MinecartTrackY, X
  CPX.b #$00 : BNE .loop

  RTL
}

; =========================================================
; Handle the tossing of the cart
; Changes the SprMiscB of the cart to indicate the direction
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
    LDA #$00 : STA.w SprMiscB, X : STA !SpriteDirection, X
    %GotoAction(1) ; Minecart_WaitVert
    JMP .continue
  .toss_south
    LDA.b #!DoubleSpeed : STA.w SprYSpeed, X
    LDA #$02 : STA.w SprMiscB,       X
    LDA #$01 : STA !SpriteDirection, X
    %GotoAction(1) ; Minecart_WaitVert
    JMP .continue
  .toss_east
    LDA.b #-!DoubleSpeed : STA.w SprXSpeed, X
    LDA #$01 : STA.w SprMiscB,       X
    LDA #$03 : STA !SpriteDirection, X
    %GotoAction(0) ; Minecart_WaitHoriz
    JMP .continue
  .toss_west
    LDA.b #!DoubleSpeed : STA.w SprXSpeed, X
    LDA #$03 : STA.w SprMiscB,       X
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
    ; Grid-align to 8x8 tile boundary
    LDA.w SprX, X : AND.b #$F8 : STA.w SprX, X
    LDA.w SprY, X : AND.b #$F8 : STA.w SprY, X
    STZ.w SprMiscG, X
    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X
    STZ.w SprHeight, X

if !ENABLE_MINECART_LIFT_TOSS
    ; After toss landing, read the stop tile to set departure direction.
    ; Same pattern as Init: setup coords in $00-$03, call GetTileAttr.
    LDA.w SprY, X : AND.b #$F8 : STA.b $00
    LDA.w SprYH, X             : STA.b $01
    LDA.w SprX, X : AND.b #$F8 : STA.b $02
    LDA.w SprXH, X             : STA.b $03
    LDA.b #$00 : JSL Sprite_GetTileAttr

    LDA.w SPRTILE
    CMP.b #$B7 : BEQ .toss_goSouth
    CMP.b #$B8 : BEQ .toss_goNorth
    CMP.b #$B9 : BEQ .toss_goEast
    CMP.b #$BA : BEQ .toss_goWest
    ; Not on a stop tile — default to vert wait
    %GotoAction(1)
    RTS
  .toss_goSouth
    LDA.b #South : STA.w SprMiscB, X
    %GotoAction(1) : RTS
  .toss_goNorth
    LDA.b #North : STA.w SprMiscB, X
    %GotoAction(1) : RTS
  .toss_goEast
    LDA.b #East : STA.w SprMiscB, X
    %GotoAction(0) : RTS
  .toss_goWest
    LDA.b #West : STA.w SprMiscB, X
    %GotoAction(0) : RTS
endif

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
; Shutter door only opens if the player is in the cart.
;
; STATUS: UNTESTED — needs runtime verification before enabling.
;   - Confirm shutter stays closed without cart
;   - Confirm shutter opens when riding cart into tagged room
;   - Confirm no regression on Crumble Floor (tag 0x34) or other Holes tags
;   - Confirm JML $01CC5A return path is correct for tag 0x37 context
;
; Hook: Tag 0x38 at $01CC14 (vanilla Holes6 routine).
; The old hook at $01CC08 (Holes3/tag 0x35) conflicts with
; Dungeons/crumblefloor_tag.asm — do NOT use that address.
; Note: Tag 0x37 (Holes5) is already repurposed for Minish shutter doors
; (see Dungeons/custom_tag.asm: RoomTag_MinishShutterDoor).
;
; To enable: set !ENABLE_MINECART_CART_SHUTTERS = 1 in
; Config/feature_flags.asm, then assign tag 0x38 to the
; target room(s) in the yaze room header editor.

if !ENABLE_MINECART_CART_SHUTTERS
pushpc
org $01CC14 ; @hook module=Sprites name=RoomTag_ShutterDoorRequiresCart kind=jml target=RoomTag_ShutterDoorRequiresCart
  JML RoomTag_ShutterDoorRequiresCart
pullpc
endif

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

; =========================================================
