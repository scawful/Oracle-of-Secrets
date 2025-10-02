# Sprite Creation Guide

This guide provides a step-by-step walkthrough for creating a new custom sprite in Oracle of Secrets using the project's modern sprite system.

## 1. File Setup

1.  **Create the Sprite File:** Create a new `.asm` file for your sprite in the appropriate subdirectory of `Sprites/` (e.g., `Sprites/Enemies/MyNewEnemy.asm`).
2.  **Include the File:** Open `Sprites/all_sprites.asm` and add an `incsrc` directive to include your new file. Make sure to place it in the correct bank section (e.g., Bank 30, 31, or 32) to ensure it gets compiled into the ROM.

    ```asm
    ; In Sprites/all_sprites.asm
    org    $318000 ; Bank 31
    ...
    incsrc "Sprites/Enemies/MyNewEnemy.asm"
    ```

## 2. Sprite Properties

At the top of your new sprite file, define its core properties using the provided template. These `!` constants are used by the `%Set_Sprite_Properties` macro to automatically configure the sprite's behavior and integrate it into the game.

```asm
; Properties for MyNewEnemy
!SPRID              = $XX ; CHOOSE AN UNUSED SPRITE ID!
!NbrTiles           = 02  ; Number of 8x8 tiles used in the largest frame
!Health             = 10  ; Health points
!Damage             = 04  ; Damage dealt to Link on contact (04 = half a heart)
!Harmless           = 00  ; 00 = Harmful, 01 = Harmless
!Hitbox             = 08  ; Hitbox size (0-31)
!ImperviousAll      = 00  ; 01 = All attacks clink harmlessly
!Statue             = 00  ; 01 = Behaves like a solid statue
!Prize              = 01  ; Prize pack dropped on death (0-15)
; ... and so on for all properties ...

; This macro MUST be called after the properties
%Set_Sprite_Properties(Sprite_MyNewEnemy_Prep, Sprite_MyNewEnemy_Long)
```

## 3. Main Structure (`_Long` routine)

This is the main entry point for your sprite, called by the game engine every frame. Its primary job is to call the drawing and logic routines.

```asm
Sprite_MyNewEnemy_Long:
{
  PHB : PHK : PLB      ; Set up bank registers
  JSR Sprite_MyNewEnemy_Draw
  JSL Sprite_DrawShadow  ; Optional: Draw a shadow

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive ; Only run logic if active
    JSR Sprite_MyNewEnemy_Main
  .SpriteIsNotActive

  PLB                  ; Restore bank register
  RTL                  ; Return from long routine
}
```

## 4. Initialization (`_Prep` routine)

This routine runs *once* when the sprite is first spawned. Use it to set initial values for timers, its action state, and any other properties.

```asm
Sprite_MyNewEnemy_Prep:
{
  PHB : PHK : PLB
  %GotoAction(0)      ; Set the initial state to the first one in the jump table
  %SetTimerA(120)     ; Set a general-purpose timer to 120 frames (2 seconds)
  PLB
  RTL
}
```

## 5. Main Logic & State Machine (`_Main` routine)

This is the heart of your sprite. Use the `%SpriteJumpTable` macro to create a state machine. The sprite's current state is stored in `SprAction, X`.

```asm
Sprite_MyNewEnemy_Main:
{
  %SpriteJumpTable(State_Idle, State_Attacking, State_Hurt)

  State_Idle:
  {
    %PlayAnimation(0, 1, 15) ; Animate between frames 0 and 1 every 15 game frames

    ; Check distance to player. If less than 80 pixels, switch to attacking state.
    JSL GetDistance8bit_Long : CMP.b #$50 : BCS .player_is_far
      %GotoAction(1) ; Switch to State_Attacking
    .player_is_far
    RTS
  }

  State_Attacking:
  {
    %PlayAnimation(2, 3, 8)
    %MoveTowardPlayer(12) ; Move toward the player with speed 12
    %DoDamageToPlayerSameLayerOnContact()

    ; Check if the player has hit the sprite
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      %GotoAction(2) ; Switch to State_Hurt
    .no_damage
    RTS
  }

  State_Hurt:
  {
    ; Sprite was hit, flash and get knocked back
    JSL Sprite_DamageFlash_Long
    RTS
  }
}
```

## 6. Drawing (`_Draw` routine)

This routine renders your sprite's graphics. The easiest method is to use the `%DrawSprite()` macro, which reads from a set of data tables you define.

```asm
Sprite_MyNewEnemy_Draw:
{
  %DrawSprite()

  ; --- OAM Data Tables ---
  .start_index  ; Starting index in the tables for each animation frame
    db $00, $02, $04, $06
  .nbr_of_tiles ; Number of tiles to draw for each frame (minus 1)
    db 1, 1, 1, 1

  .x_offsets    ; X-position offset for each tile
    dw -8, 8, -8, 8, -8, 8, -8, 8
  .y_offsets    ; Y-position offset for each tile
    dw -8, -8, -8, -8, -8, -8, -8, -8
  .chr          ; The character (tile) number from the graphics sheet
    db $C0, $C2, $C4, $C6, $C8, $CA, $CC, $CE
  .properties   ; OAM properties (palette, priority, flips)
    db $3B, $7B, $3B, $7B, $3B, $7B, $3B, $7B
  .sizes        ; Size of each tile (e.g., $02 for 16x16)
    db $02, $02, $02, $02, $02, $02, $02, $02
}
```

## 7. Final Integration

The `%Set_Sprite_Properties()` macro you added in Step 2 handles the final integration. It automatically adds your sprite's `_Prep` and `_Long` routines to the game's sprite tables in `Core/sprite_new_table.asm`. Your sprite is now ready to be placed in the game world!