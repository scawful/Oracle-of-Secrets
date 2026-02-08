# Minecart

## Overview
The Minecart sprite (`!SPRID = Sprite_Minecart`) is a highly complex and interactive object primarily used in the Goron Mines. It allows Link to ride it through a network of tracks, with its movement dictated by various track tile types, player input, and seamless dungeon transitions. The Minecart system features persistent state across rooms and intricate collision detection.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Minecart` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `08`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Impervious to all attacks)
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `14`
*   **`!Persist`**: `01` (Continues to live off-screen)
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Constants
*   **`!LinkInCart`**: `$35` (Flag indicating Link is currently riding the Minecart)
*   **`!MinecartSpeed`**: `20` (Normal movement speed)
*   **`!DoubleSpeed`**: `30` (Faster movement speed, possibly for boosts)
*   **Directions**: `North`, `East`, `South`, `West` (Used for `!MinecartDirection` and `SprMiscB`)
*   **Sprite Facing Directions**: `Up`, `Down`, `Left`, `Right` (Used for `!SpriteDirection`)
*   **`!MinecartDirection`**: `$0DE0` (Maps to `SprMiscC`, stores the current movement direction)
*   **`!SpriteDirection`**: `$0DE0` (Stores the sprite's visual facing direction)
*   **Track Persistence**: A system for saving and loading minecart state across rooms:
    *   **`!MinecartTrackRoom`**: `$0728` (Stores the room ID where a specific track was left)
    *   **`!MinecartTrackX`**: `$0768` (Stores the X position of a track)
    *   **`!MinecartTrackY`**: `$07A8` (Stores the Y position of a track)
*   **Active Cart Tracking**: Variables to manage the currently active minecart:
    *   **`!MinecartTrackCache`**: `$07E8` (Stores the ID of the track Link is currently on)
    *   **`!MinecartDirectionCache`**: `$07E9` (Stores the direction during room transitions)
    *   **`!MinecartCurrent`**: `$07EA` (Stores the sprite slot index of the current minecart)

## Collision Setup (Tile Types)
Defines various tile types that represent different parts of the minecart track, including straight sections, corners, intersections, stop tiles, and dynamic switch tiles. These are crucial for guiding the minecart's movement and interaction with the environment.

## Main Structure (`Sprite_Minecart_Long`)
This routine handles the Minecart's multi-layered drawing (top and bottom portions) and dispatches to its main logic if the sprite is active.

```asm
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
```

## Initialization (`Sprite_Minecart_Prep`)
This routine initializes the Minecart upon spawning. It updates cached coordinates, manages track persistence (initializing track data if not already set), and handles despawning if the cart is not in its designated room or its coordinates don't match. It sets various sprite properties and determines the initial movement direction based on the tile the minecart is placed on.

## Main Logic & State Machine (`Sprite_Minecart_Main`)
This routine manages the Minecart's complex behavior through a state machine:

*   **`Minecart_WaitHoriz` / `Minecart_WaitVert`**: The cart waits in a horizontal or vertical orientation. If Link is on the cart (`CheckIfPlayerIsOn`) and presses the B button, it saves the track ID, cancels Link's dash, sets `LinkSomaria` and `!LinkInCart`, adjusts Link's position, and transitions to a movement state (`Minecart_MoveEast`, `Minecart_MoveWest`, `Minecart_MoveNorth`, `Minecart_MoveSouth`).
*   **`Minecart_MoveNorth` / `MoveEast` / `MoveSouth` / `MoveWest`**: The cart moves in the specified direction. It plays animations, sets speed (`!MinecartSpeed` or `!DoubleSpeed`), moves the sprite, drags Link along (`JSL DragPlayer`), handles the player camera, and processes track tiles (`HandleTileDirections`).
*   **`Minecart_Release`**: Stops the cart, releases Link, and transitions back to a `Minecart_Wait` state.

## Helper Routines
*   **`HandlePlayerCameraAndMoveCart`**: Manages Link's animation, camera, and plays cart sound effects.
*   **`StopCart`**: Stops the cart, releases Link, rounds its coordinates, and saves its position to track variables for persistence.
*   **`InitMovement`**: Caches Link's coordinates for movement calculations.
*   **`Minecart_SetDirectionNorth` / `East` / `South` / `West`**: Set the cart's direction, animation, and update track caches.
*   **`HandleTileDirections`**: A crucial routine that checks the tile the minecart is currently on and determines its next action, handling out-of-bounds, stop tiles, player input at intersections, corner tiles, and dynamic switch tiles.
*   **`CheckForOutOfBounds`**: Determines if the cart is on an out-of-bounds tile.
*   **`CheckForStopTiles`**: Checks for stop tiles and sets the cart's next direction.
*   **`CheckForPlayerInput`**: Detects player input on intersection tiles to allow Link to choose the cart's direction.
*   **`CheckForCornerTiles`**: Handles direction changes when the cart encounters corner tiles.
*   **`HandleDynamicSwitchTileDirections`**: Manages movement on dynamic switch tiles, which can alter the cart's path.
*   **`CheckTrackSpritePresence`**: Checks for the presence and collision of a `Sprite $B0` (Switch Track) with the minecart.
*   **`CheckIfPlayerIsOn`**: Determines if Link is overlapping the minecart.
*   **`ResetTrackVars`**: Resets all minecart track-related variables.
*   **`Minecart_HandleToss` / `Minecart_HandleTossedCart` / `Minecart_HandleLiftAndToss`**: Routines for handling the minecart being tossed or lifted by Link.

## Drawing (`Sprite_Minecart_DrawTop` and `Sprite_Minecart_DrawBottom`)
These routines draw the Minecart in two separate portions (top and bottom) to create the illusion of Link riding inside it. They utilize `JSL Sprite_PrepOamCoord` and `OAM_AllocateFromRegionB`/`C` for OAM allocation, and explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

## Vanilla Overrides
*   **`RoomTag_ShutterDoorRequiresCart`**: Modifies a room tag to require Link to be in a cart to open a shutter door, integrating the Minecart into dungeon puzzles.
*   **`org $028260`**: Injects `JSL ResetTrackVars` to ensure minecart track variables are reset at specific points.

## Design Patterns
*   **Complex Interactive Object**: The Minecart is a highly interactive object with intricate movement, collision, and state management, providing a unique traversal mechanic.
*   **Track-Based Movement**: Movement is precisely governed by specific track tile types (stops, corners, intersections), requiring careful design of the minecart routes.
*   **Player Input for Direction**: Link can influence the minecart's direction at intersections, adding an element of player control to the ride.
*   **Persistent State**: Minecart position and direction are saved across room transitions, ensuring continuity and allowing for complex multi-room puzzles.
*   **Multi-Part Drawing**: The minecart is drawn in two separate parts to allow Link to appear "inside" it, enhancing visual immersion.
*   **Player State Manipulation**: The minecart directly controls Link's state (`!LinkInCart`, `LinkSomaria`, `LinkState`), seamlessly integrating the ride into Link's overall actions.
*   **Dynamic Room Transitions**: Handles seamless transitions between rooms while Link is in the minecart, maintaining the flow of gameplay.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.