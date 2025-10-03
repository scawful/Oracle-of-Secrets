# Eon Scrub

## Overview
The Eon Scrub is a custom enemy sprite, likely a variation of the Business Scrub, that overrides a vanilla sprite ID. It shares similar characteristics with the Business Scrub, including low health and harmless contact damage, implying its primary threat comes from projectiles or other interactions defined within its main logic.

## Sprite Properties
*   **`!SPRID`**: `$00` (Vanilla sprite ID, likely overridden)
*   **`!NbrTiles`**: `$02`
*   **`!Health`**: `$01`
*   **`!Damage`**: `$00` (Harmless contact)
*   **`!Harmless`**: `$00`
*   **`!Hitbox`**: `$08`
*   **`!ImperviousAll`**: `$00`
*   **`!Statue`**: `$00`
*   **`!Prize`**: `$00`
*   **`!Boss`**: `$00`
*   **Collision Properties**: All collision-related properties (`!Defl`, `!SprColl`, etc.) are set to `$00`, indicating that direct contact damage and knockback are not handled by these properties. Interaction and damage are likely managed within the sprite's main logic.

## Main Structure (`Sprite_EonScrub_Long`)
This routine is the main entry point for the Eon Scrub, executed every frame. It sets up bank registers, calls the drawing routine, and then executes the main logic if the sprite is active.

```asm
Sprite_EonScrub_Long:
{
  PHB : PHK : PLB
  JSR Sprite_EonScrub_Draw
  JSL Sprite_DrawShadow

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_EonScrub_Main
  .SpriteIsNotActive

  PLB
  RTL
}
```

## Initialization (`Sprite_EonScrub_Prep`)
This routine runs once when the Eon Scrub is spawned. It initializes the sprite's action state to `0` and sets a general-purpose timer (`SprTimerA`) to `120` frames (2 seconds).

```asm
Sprite_EonScrub_Prep:
{
  PHB : PHK : PLB
  %GotoAction(0)
  %SetTimerA(120)
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_EonScrub_Main`)
The core behavior of the Eon Scrub is managed by a state machine using `%SpriteJumpTable`. The current states are:

*   **`State_Idle`**: The initial state where the scrub is idle. It plays an animation and checks for player proximity. If Link is within 80 pixels, it transitions to `State_Attacking`.
*   **`State_Attacking`**: In this state, the scrub plays an attack animation, moves towards the player, and deals damage on contact. It also checks if it has been hit by the player and transitions to `State_Hurt` if so.
*   **`State_Hurt`**: This state handles the sprite being hit, causing it to flash and be knocked back.

```asm
Sprite_EonScrub_Main:
{
  %SpriteJumpTable(State_Idle, State_Attacking, State_Hurt)

  State_Idle:
  {
    %PlayAnimation(0, 1, 15)

    JSL GetDistance8bit_Long : CMP.b #$50 : BCS .player_is_far
      %GotoAction(1)
    .player_is_far
    RTS
  }

  State_Attacking:
  {
    %PlayAnimation(2, 3, 8)
    %MoveTowardPlayer(12)
    %DoDamageToPlayerSameLayerOnContact()

    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      %GotoAction(2)
    .no_damage
    RTS
  }

  State_Hurt:
  {
    JSL Sprite_DamageFlash_Long
    RTS
  }
}
```

## Drawing (`Sprite_EonScrub_Draw`)
The drawing routine uses the `%DrawSprite()` macro to render the sprite's graphics based on defined OAM data tables.

```asm
Sprite_EonScrub_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $02, $04, $06
  .nbr_of_tiles
    db 1, 1, 1, 1

  .x_offsets
    dw -8, 8, -8, 8, -8, 8, -8, 8
  .y_offsets
    dw -8, -8, -8, -8, -8, -8, -8, -8
  .chr
    db $C0, $C2, $C4, $C6, $C8, $CA, $CC, $CE
  .properties
    db $3B, $7B, $3B, $7B, $3B, $7B, $3B, $7B
}
```

## Design Patterns
*   **State Machine**: Utilizes a clear state machine (`%SpriteJumpTable`) for managing different behaviors (Idle, Attacking, Hurt).
*   **Player Interaction**: Incorporates distance checks (`GetDistance8bit_Long`) to trigger state changes and direct damage on contact (`DoDamageToPlayerSameLayerOnContact`).
*   **Damage Handling**: Includes a basic damage reaction (`Sprite_CheckDamageFromPlayer`, `Sprite_DamageFlash_Long`).
*   **Vanilla ID Override**: The use of `!SPRID = $00` suggests this sprite is intended to replace or modify the behavior of a vanilla sprite with ID $00.
