# Ice Block (Pushable)

## Overview
The Ice Block sprite (`!SPRID = $D5`) is an interactive object designed as a puzzle element that Link can push. It features complex logic for detecting Link's push, applying movement with momentum, and interacting with switch tiles. This sprite is impervious to most attacks and behaves like a solid statue.

## Sprite Properties
*   **`!SPRID`**: `$D5` (Vanilla sprite ID, likely for a pushable block)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Impervious to all attacks)
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `09`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `01` (Behaves like a solid statue)
*   **`!DeflectProjectiles`**: `01` (Deflects all projectiles)
*   **`!ImperviousArrow`**: `01` (Impervious to arrows)
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Constants
*   **`!ICE_BLOCK_SPEED`**: `16` (Speed at which the ice block moves when pushed)
*   **`!PUSH_CONFIRM_FRAMES`**: `10` (Number of frames Link must maintain a push for it to be confirmed)
*   **`!ALIGN_TOLERANCE`**: `4` (Pixel tolerance for Link's alignment with the block)
*   **`!WRAM_FLAG_0642`**: `$0642` (WRAM address for a flag related to switch activation)
*   **`!WRAM_TILE_ATTR`**: `$0FA5` (WRAM address for tile attributes)
*   **`!SPRITE_LOOP_MAX`**: `$0F` (Max index for sprite loops)
*   **`!SPRITE_TYPE_STATUE`**: `$1C` (Sprite ID for a generic statue)
*   **`!SPRITE_STATE_ACTIVE`**: `$09` (Sprite state for active sprites)
*   **`!TILE_ATTR_ICE`**: `$0E` (Tile attribute for ice, currently unused)
*   **`!SWITCH_TILE_ID_1` to `!SWITCH_TILE_ID_4`**: IDs for various switch tiles.
*   **`!SWITCH_TILE_COUNT_MINUS_1`**: `$03`

## Main Structure (`Sprite_IceBlock_Long`)
This routine handles the Ice Block's drawing and dispatches to its main logic if active. It also manages Link's interaction with the block, setting Link's speed and actions when pushing.

```asm
Sprite_IceBlock_Long:
{
  PHB : PHK : PLB

  LDA.w SprMiscC, X : BEQ .not_being_pushed
    STZ.w SprMiscC, X
    STZ.b LinkSpeedTbl
    STZ.b $48 ; Clear push actions bitfield
  .not_being_pushed

  LDA.w SprTimerA, X : BEQ .retain_momentum
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #$84 : STA.b $48 ; Set statue and push block actions
    LDA.b #$04 : STA.b LinkSpeedTbl ; Slipping into pit speed
  .retain_momentum

  JSR Sprite_IceBlock_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_IceBlock_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_IceBlock_Prep`)
This routine initializes the Ice Block upon spawning. It caches the sprite's initial position in `SprMiscD, X` through `SprMiscG, X`. It sets `SprDefl, X` to `$04` (designating it as a pushable statue) and initializes `SprMiscB, X` to `0` (movement state).

```asm
Sprite_IceBlock_Prep:
{
  PHB : PHK : PLB
  ; Cache Sprite position
  LDA.w SprX, X : STA.w SprMiscD, X
  LDA.w SprY, X : STA.w SprMiscE, X
  LDA.w SprXH, X : STA.w SprMiscF, X
  LDA.w SprYH, X : STA.w SprMiscG, X

  LDA.b #$04 : STA.w SprDefl, X ; Set as pushable statue

  LDA.w SprHitbox, X : ORA.b #$09 : STA.w SprHitbox, X
  ; Initialize movement state tracking
  STZ.w SprMiscB, X ; Clear movement state
  PLB
  RTL
}
```

## Main Logic (`Sprite_IceBlock_Main`)
This routine manages the Ice Block's behavior, including push detection, movement, and interaction with switches.

*   **Animation**: Plays a static animation (`%PlayAnimation(0, 0, 1)`).
*   **Sprite-to-Sprite Collision**: Calls `IceBlock_HandleSpriteToSpriteCollision` to manage interactions with other sprites.
*   **Damage Reaction**: If the block takes damage, its position, speed, and movement state are reset.
*   **Switch Detection**: Calls `Sprite_IceBlock_CheckForSwitch`. If the block is on a switch, it stops movement, sets `!WRAM_FLAG_0642` to `01`, and resets its movement state.
*   **Push Logic**: This is a core part of the routine. If the block is not moving, it checks if Link is in contact and correctly aligned (`IceBlock_CheckLinkPushAlignment`). If so, a push timer (`SprTimerA, X`) is initiated. If the timer expires while Link is still pushing, the block snaps to the grid, applies push speed (`Sprite_ApplyPush`), and begins moving. If the block is already moving, it continues to move (`JSL Sprite_Move`) and checks for tile collisions, stopping if an obstacle is encountered.

```asm
Sprite_IceBlock_Main:
{
  %PlayAnimation(0, 0, 1)

  JSR IceBlock_HandleSpriteToSpriteCollision ; Renamed from Statue_BlockSprites
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.w SprMiscD, X : STA.w SprX, X
    LDA.w SprY, X : STA.w SprY, X
    LDA.w SprXH, X : STA.w SprXH, X
    LDA.w SprYH, X : STA.w SprYH, X
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    STZ.w SprTimerA, X : STZ.w SprMiscA, X
    STZ.w SprMiscB, X ; Reset movement state when hit
  .no_damage

  STZ.w !WRAM_FLAG_0642
  JSR Sprite_IceBlock_CheckForSwitch : BCC .no_switch
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$01 : STA.w !WRAM_FLAG_0642
    STZ.w SprMiscB, X ; Reset movement state when hitting switch
  .no_switch

  ; If the block is currently moving, apply movement and check for collisions
  LDA.w SprMiscB, X
  BNE .block_is_moving

  ; --- Block is NOT moving, check for push initiation ---
  JSL Sprite_CheckDamageToPlayerSameLayer : BCC .NotInContact
    ; Link is in contact. Now check if he's properly aligned and facing the block.
    JSR IceBlock_CheckLinkPushAlignment
    BCC .NotInContact ; Link is not aligned or facing correctly.

    ; Link is aligned and facing the block. Start or continue the push timer.
    LDA.w SprTimerA, X
    BNE .timer_is_running ; Timer already started, let it count down.

    ; Start the timer for the first time.
    LDA.b #!PUSH_CONFIRM_FRAMES
    STA.w SprTimerA, X
    RTS ; Wait for next frame

  .timer_is_running
    ; Timer is running. Has it reached zero? (SprTimerA is decremented by engine)
    LDA.w SprTimerA, X
    BNE .NotInContact ; Not zero yet, keep waiting.

    ; --- PUSH CONFIRMED ---
    ; Timer reached zero while still in contact and aligned.
    ; Snap to grid before setting speed for clean movement.
    LDA.w SprX, X : AND.b #$F8 : STA.w SprX, X
    LDA.w SprY, X : AND.b #$F8 : STA.w SprY, X

    JSR Sprite_ApplyPush ; Set speed based on Link's direction.
    LDA.b #$01 : STA.w SprMiscB, X ; Set "is moving" flag.
    RTS

.NotInContact
  ; No contact or improper alignment, reset push timer.
  STZ.w SprTimerA, X
  RTS

.block_is_moving
  JSL Sprite_Move
  JSL Sprite_Get_16_bit_Coords
  JSL Sprite_CheckTileCollision
  ; ----udlr , u = up, d = down, l = left, r = right
  LDA.w SprCollision, X : AND.b #$0F : BEQ + ; If no collision, continue moving
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X ; Stop movement
    STZ.w SprMiscB, X ; Reset movement state
  +
  RTS
}
```

## `IceBlock_CheckLinkPushAlignment`
This complex routine precisely determines if Link is correctly aligned and facing the ice block to initiate a push. It calculates the relative positions of Link and the block, considers Link's facing direction, and uses `!ALIGN_TOLERANCE` to allow for slight pixel variations. It returns with the carry flag set for success or clear for failure.

## `Sprite_ApplyPush`
This routine sets the Ice Block's `SprXSpeed, X` or `SprYSpeed, X` based on Link's facing direction (`SprMiscA, X`) and the predefined `!ICE_BLOCK_SPEED`.

## `IceBlock_CheckForGround`
This routine is currently unused but was intended to check if the tile beneath the sprite was a sliding ice tile.

## `Sprite_IceBlock_CheckForSwitch`
This routine checks if any of the four corners of the Ice Block are currently positioned on a switch tile (identified by `!SWITCH_TILE_ID_1` to `!SWITCH_TILE_ID_4`). It returns with the carry flag set if any corner is on a switch tile.

## `IceBlock_HandleSpriteToSpriteCollision`
This routine (renamed from `Statue_BlockSprites`) manages collisions between the Ice Block and other active sprites. It iterates through other sprites, checks for collision, and applies recoil or other effects to them.

## Drawing (`Sprite_IceBlock_Draw`)
This routine handles OAM allocation and animation for the Ice Block. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

## Design Patterns
*   **Interactive Puzzle Element**: The Ice Block is a core interactive puzzle element that Link can manipulate by pushing, requiring precise player input and environmental interaction.
*   **Precise Collision and Alignment Detection**: Implements detailed logic to ensure Link is correctly positioned and facing the block before a push is registered, providing a robust and fair interaction mechanism.
*   **Movement with Momentum**: The block retains momentum after being pushed, sliding across the terrain until it encounters an obstacle, adding a realistic physics element.
*   **Switch Activation**: The block can activate switch tiles upon contact, integrating it into environmental puzzles and triggering game events.
*   **Sprite-to-Sprite Collision**: Handles interactions with other sprites, applying recoil effects to them, demonstrating complex inter-sprite dynamics.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.