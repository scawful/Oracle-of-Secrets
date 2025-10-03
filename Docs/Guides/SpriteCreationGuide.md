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

; --- Design Considerations ---
; *   **Multi-purpose Sprite IDs:** A single `!SPRID` can be used for multiple distinct behaviors (e.g., Dark Link and Ganon) through the use of `SprSubtype`. This is a powerful technique for reusing sprite slots and creating multi-phase bosses or variations of enemies.
; *   **Damage Handling for Bosses:** For boss sprites, `!Damage = 0` is acceptable if damage is applied through other means, such as spawned projectiles or direct contact logic within the main routine.
; *   **Custom Boss Logic:** Setting `!Boss = 00` for a boss sprite indicates that custom boss logic is being used, rather than relying on vanilla boss flags. This is important for understanding how boss-specific behaviors are implemented.

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

;   State_Hurt:
;   {
;     ; Sprite was hit, flash and get knocked back
;     JSL Sprite_DamageFlash_Long
;     RTS
;   }
; }
;
; --- Code Readability Note ---
; For improved readability and maintainability, always prefer using named constants for hardcoded values (e.g., timers, speeds, health, magic numbers) and named labels for `JSL` calls to project-specific functions instead of direct numerical addresses.
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
;   .sizes        ; Size of each tile (e.g., $02 for 16x16)
;     db $02, $02, $02, $02, $02, $02, $02, $02
; }
;
; --- Code Readability Note ---
; For improved readability and maintainability, always prefer using named constants for hardcoded values (e.g., OAM properties, tile numbers) and named labels for `JSL` calls to project-specific functions instead of direct numerical addresses.
```

## 7. Final Integration

The %Set_Sprite_Properties() macro you added in Step 2 handles the final integration. It automatically adds your sprite's _Prep and _Long routines to the game's sprite tables in Core/sprite_new_table.asm. Your sprite is now ready to be placed in the game world!

## 8. Advanced Sprite Design Patterns

### 8.1. Multi-Part Sprites and Child Sprites
For complex bosses or entities, you can break them down into a main parent sprite and multiple child sprites.

*   **Parent Sprite Responsibilities:**
    *   Spawns and manages its child sprites (e.g., Kydreeok spawning `kydreeok_head` instances).
    *   Monitors the state/health of its child sprites to determine its own phases, actions, or defeat conditions.
    *   Often handles overall movement, phase transitions, and global effects.
    *   Uses global variables (e.g., `Offspring1_Id`, `Offspring2_Id`) to store the sprite IDs of its children for easy referencing.
*   **Child Sprite Responsibilities:**
    *   Handles its own independent logic, movement, and attacks.
    *   May be positioned relative to the parent sprite.
    *   Can use `SprSubtype` to differentiate between multiple instances of the same child sprite ID (e.g., left head vs. right head).
*   **Shared Sprite IDs for Variations:** A single `!SPRID` can also be used for different enemy variations (e.g., Keese, Fire Keese, Ice Keese, Vampire Bat) by assigning unique `SprSubtype` values. This is an efficient way to reuse sprite slots and base logic.

### 8.2. Multi-Phase Bosses and Dynamic Health Management
Boss fights can be made more engaging by implementing multiple phases and dynamic health management.

*   **Phase Transitions:** Trigger new phases based on health thresholds, timers, or the defeat of child sprites. Phases can involve:
    *   Changing the boss's graphics or palette.
    *   Altering movement patterns and attack routines.
    *   Spawning new entities or environmental hazards.
*   **Health Management:** Boss health can be managed in various ways:
    *   Directly via the parent sprite's `SprHealth`.
    *   Indirectly by monitoring the health or state of child sprites (e.g., Kydreeok's main body health is tied to its heads).
    *   Using custom variables (e.g., `!KydrogPhase`) to track overall boss progression.
*   **Quest Integration and Pacification:** Sprites can be integrated into quests where "defeat" might mean pacification rather than outright killing. This can involve refilling health and changing the sprite's state to a subdued or quest-complete action (e.g., Wolfos granting a mask after being subdued by the Song of Healing).

### 8.3. Code Reusability and Modularity
When designing multiple sprites, especially bosses, look for opportunities to reuse code and create modular components.

*   **Shared Logic:** If multiple sprites perform similar actions (e.g., spawning stalfos, specific movement patterns), consider creating common functions or macros that can be called by different sprites. This reduces code duplication and improves maintainability.
*   **Refactoring:** Regularly refactor duplicated code into reusable components. This makes it easier to apply changes consistently across related sprites.

### 8.4. Configurability and Avoiding Hardcoded Values
To improve sprite reusability and ease of placement in different maps, avoid hardcoding values that might change.

*   **Activation Triggers:** Instead of hardcoding specific screen coordinates or camera values for activation (e.g., Octoboss's Y-coordinate trigger), consider using:
    *   Sprite properties (`SprMiscA`, `SprMiscB`, etc.) to store configurable trigger values.
    *   Room-specific flags or events that can be set externally.
    *   Relative positioning or distance checks to Link.
*   **Timers, Speeds, Offsets:** Always prefer using named constants (`!CONSTANT_NAME = value`) for numerical values that control behavior (timers, speeds, offsets, health thresholds). This significantly improves readability and makes it easier to adjust parameters without searching through code.
*   **Function Calls:** Use named labels for `JSL` calls to project-specific functions instead of direct numerical addresses.

### 8.5. Overriding Vanilla Behavior
When creating new boss sequences or modifying existing enemies, it's common to override vanilla sprite behavior.

*   **Hooking Entry Points:** Identify the entry points of vanilla sprites (e.g., `Sprite_Blind_Long`, `Sprite_Blind_Prep`) and use `org` directives to redirect execution to your custom routines.
*   **Contextual Checks:** Within your custom routines, perform checks (e.g., `LDA.l $7EF3CC : CMP.b #$06`) to determine if the vanilla behavior should be executed or if your custom logic should take over.
*   **SRAM Flags:** Utilize SRAM flags (`$7EF3XX`) to track quest progression or conditions that dictate whether vanilla or custom behavior is active.