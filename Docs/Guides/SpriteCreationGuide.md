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
!NbrTiles           = 02  ; Number of 8x8 tiles used in the largest frame (e.g., Darknut uses 03 for its multi-tile body)
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
*   **Damage Handling for Bosses:** For boss sprites, `!Damage = 0` is acceptable if damage is applied through other means, such as spawned projectiles or direct contact logic within the main routine.
*   **Fixed vs. Dynamic Health:** While many sprites (like Booki) have dynamic health based on Link's sword level, some sprites (like Pols Voice) may have a fixed `!Health` value, simplifying their damage model.
*   **Custom Boss Logic:** Setting `!Boss = 00` for a boss sprite indicates that custom boss logic is being used, rather than relying on vanilla boss flags. This is important for understanding how boss-specific behaviors are implemented.

; This macro MUST be called after the properties
%Set_Sprite_Properties(Sprite_MyNewEnemy_Prep, Sprite_MyNewEnemy_Long)
```

## 3. Main Structure (`_Long` routine)

This is the main entry point for your sprite, called by the game engine every frame. Its primary job is to call the drawing and logic routines. Sometimes, shadow drawing might be conditional based on the sprite's current action or state, as seen in the Thunder Ghost sprite (`Sprites/Enemies/thunder_ghost.asm`).

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
; For improved readability and maintainability, always prefer using named constants for hardcoded values (e.g., timers, speeds, health, magic numbers) and named labels for `JSL` calls to project-specific functions instead of direct numerical addresses. Additionally, be mindful of the Processor Status Register (P) flags (M and X) and use `REP #$20`/`SEP #$20` to explicitly set the accumulator/index register size when necessary, especially when interacting with memory or calling routines that expect a specific state.
```

## 6. Drawing (`_Draw` routine)

This routine renders your sprite's graphics. The easiest method is to use the `%DrawSprite()` macro, which reads from a set of data tables you define. However, for highly customized drawing logic, such as dynamic tile selection, complex animation sequences, or precise OAM manipulation (as demonstrated in the Booki sprite's `Sprite_Booki_Draw` routine, which uses `REP`/`SEP` for 16-bit coordinate calculations), you may need to implement a custom drawing routine.

**Important Note on 16-bit OAM Calculations:** When performing OAM (Object Attribute Memory) calculations, especially for sprite positioning and offsets, it is crucial to explicitly manage the Processor Status Register (P) flags. Use `REP #$20` to set the accumulator to 16-bit mode before performing 16-bit arithmetic operations (e.g., adding `x_offsets` or `y_offsets` to sprite coordinates), and `SEP #$20` to restore it to 8-bit mode afterward if necessary. This ensures accurate positioning and prevents unexpected graphical glitches or crashes.

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
; For improved readability and maintainability, always prefer using named constants for hardcoded values (e.g., OAM properties, tile numbers) and named labels for `JSL` calls to project-specific functions instead of direct numerical addresses. Additionally, be mindful of the Processor Status Register (P) flags (M and X) and use `REP #$20`/`SEP #$20` to explicitly set the accumulator/index register size when necessary, especially when interacting with memory or calling routines that expect a specific state.
```

## 7. Final Integration

The %Set_Sprite_Properties() macro you added in Step 2 handles the final integration. It automatically adds your sprite's _Prep and _Long routines to the game's sprite tables in Core/sprite_new_table.asm. Your sprite is now ready to be placed in the game world!

## 8. Advanced Sprite Design Patterns

### 8.1. Multi-Part Sprites and Child Sprites
For complex bosses or entities, you can break them down into a main parent sprite and multiple child sprites.

*   **Parent Sprite Responsibilities:**
    *   Spawns and manages its child sprites (e.g., Kydreeok spawning `kydreeok_head` instances, Darknut spawning probes, Goriya spawning its boomerang, Helmet Chuchu detaching its helmet/mask, Thunder Ghost spawning lightning attacks with directional logic, or Puffstool transforming into a bomb).
    *   Monitors the state/health of its child sprites to determine its own phases, actions, or defeat conditions.
    *   Often handles overall movement, phase transitions, and global effects.
    *   Uses global variables (e.g., `Offspring1_Id`, `Offspring2_Id`) to store the sprite IDs of its children for easy referencing.
*   **Child Sprite Responsibilities:**
    *   Handles its own independent logic, movement, and attacks.
    *   May be positioned relative to the parent sprite.
    *   Can use `SprSubtype` to differentiate between multiple instances of the same child sprite ID (e.g., left head vs. right head, Goriya vs. its Boomerang, or Helmet Chuchu's detached helmet/mask).
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

*   **Shared Logic:** If multiple sprites perform similar actions (e.g., spawning stalfos, specific movement patterns, or tile collision handling like `Goriya_HandleTileCollision` used by Darknut), consider creating common functions or macros that can be called by different sprites. This reduces code duplication and improves maintainability.
*   **Refactoring:** Regularly refactor duplicated code into reusable components. This makes it easier to apply changes consistently across related sprites.

### 8.4. Configurability and Avoiding Hardcoded Values
To improve sprite reusability and ease of placement in different maps, avoid hardcoding values that might change.

*   **Activation Triggers:** Instead of hardcoding specific screen coordinates or camera values for activation (e.g., Octoboss's Y-coordinate trigger), consider using:
    *   Sprite properties (`SprMiscA`, `SprMiscB`, etc.) to store configurable trigger values.
    *   Room-specific flags or events that can be set externally.
    *   Relative positioning or distance checks to Link.
*   **Timers, Speeds, Offsets:** Always prefer using named constants (`!CONSTANT_NAME = value`) for numerical values that control behavior (timers, speeds, offsets, health thresholds). This significantly improves readability and makes it easier to adjust parameters without searching through code.
*   **Function Calls:** Use named labels for `JSL` calls to project-specific functions instead of direct numerical addresses.
*   **Conditional Drawing/Flipping:** When drawing, use sprite-specific variables (e.g., `SprMiscC` in the Booki sprite) to store directional information and conditionally adjust OAM offsets or flip bits to achieve horizontal or vertical flipping without hardcoding.
*   **State Machine Implementation:** For complex AI, utilize `JumpTableLocal` with `SprAction` to create robust state machines, as seen in the Booki sprite's `_Main` routine.
*   **Randomness:** Incorporate `JSL GetRandomInt` to introduce variability into sprite behaviors, such as movement patterns or state transitions, making enemies less predictable.

### 8.5. Overriding Vanilla Behavior
When creating new boss sequences or modifying existing enemies, it's common to override vanilla sprite behavior.

*   **Hooking Entry Points:** Identify the entry points of vanilla sprites (e.g., `Sprite_Blind_Long`, `Sprite_Blind_Prep`) and use `org` directives to redirect execution to your custom routines.
*   **Contextual Checks:** Within your custom routines, perform checks (e.g., `LDA.l $7EF3CC : CMP.b #$06`) to determine if the vanilla behavior should be executed or if your custom logic should take over.
*   **SRAM Flags:** Utilize SRAM flags (`$7EF3XX`) to track quest progression or conditions that dictate whether vanilla or custom behavior is active.

### 8.6. Dynamic Enemy Behavior
For more engaging and adaptive enemies, consider implementing dynamic behaviors:

*   **Dynamic Difficulty Scaling:** Adjust enemy properties (health, damage, prize drops) based on player progression (e.g., Link's sword level, number of collected items). This can be done in the `_Prep` routine by indexing into data tables. For example, the Booki sprite (`Sprites/Enemies/booki.asm`) sets its health based on Link's current sword level.
*   **Dynamic State Management:** Utilize `SprMisc` variables (e.g., `SprMiscB` for sub-states) and timers (e.g., `SprTimerA` for timed transitions) to create complex and adaptive behaviors. The Booki sprite demonstrates this with its `SlowFloat` and `FloatAway` sub-states and timed transitions.
*   **Advanced Interaction/Guard Mechanics:** Implement behaviors like parrying (`Guard_ParrySwordAttacks` in Darknut) or chasing Link along a single axis (`Guard_ChaseLinkOnOneAxis` in Darknut) to create more sophisticated enemy encounters.
*   **Random Movement with Collision Response:** Implement enemies that move in random directions and change their behavior upon collision with tiles, as demonstrated by the Goriya sprite's `Goriya_HandleTileCollision` routine.
*   **Dynamic Appearance and Conditional Vulnerability:** Sprites can dynamically change their appearance and vulnerability based on internal states or player actions. For instance, the Helmet Chuchu (`Sprites/Enemies/helmet_chuchu.asm`) changes its graphics and becomes vulnerable only after its helmet/mask is removed, often by a specific item like the Hookshot.
*   **Stunned State and Counter-Attack:** Some sprites react to damage by entering a stunned state, then performing a counter-attack (e.g., Puffstool spawning spores or transforming into a bomb).
*   **Interaction with Thrown Objects:** Sprites can be designed to interact with objects thrown by Link (e.g., `ThrownSprite_TileAndSpriteInteraction_long` used by Puffstool), allowing for environmental puzzles or unique combat strategies.
*   **Interaction with Non-Combat Player Actions:** Sprites can react to specific player actions beyond direct attacks, suchs as playing a musical instrument. The Pols Voice (`Sprites/Enemies/pols_voice.asm`) despawns and drops a prize if Link plays the flute.
*   **Specific Movement Routines for Attacks:** During attack animations, sprites may utilize specialized movement routines like `Sprite_MoveLong` (seen in Thunder Ghost) to control their position and trajectory precisely.
*   **Damage Reaction (Invert Speed):** A common dynamic behavior is for a sprite to invert its speed or change its movement pattern upon taking damage, as seen in Pols Voice.
*   **Global State-Dependent Behavior:** Sprite properties and behaviors can be dynamically altered based on global game state variables (e.g., `WORLDFLAG` in the Sea Urchin sprite), allowing for different enemy characteristics in various areas or game progression points.
*   **Simple Movement/Idle:** Not all sprites require complex movement. Some may have simple idle animations and primarily interact through contact damage or being pushable, as exemplified by the Sea Urchin.
*   **Timed Attack and Stun States:** Sprites can have distinct attack and stunned states that are governed by timers, allowing for predictable attack patterns and temporary incapacitation (e.g., Poltergeist's `Poltergeist_Attack` and `Poltergeist_Stunned` states).
*   **Conditional Invulnerability:** Invulnerability can be dynamic, changing based on the sprite's state. For example, a sprite might be impervious to certain attacks only when in a specific state, or its `SprDefl` flags might be manipulated to reflect temporary invulnerability (as suggested by the Poltergeist's properties).
*   **Direct SRAM Interaction:** Implement mechanics that directly interact with Link's inventory or status in SRAM (e.g., stealing items, modifying rupee count). Remember to explicitly manage processor status flags (`REP`/`SEP`) when performing mixed 8-bit/16-bit operations on SRAM addresses to prevent unexpected behavior or crashes.

### 8.7. Subtype-based Behavior and Dynamic Transformations
Leverage `SprSubtype` to create diverse enemy variations from a single sprite ID and enable dynamic transformations based on in-game conditions.

*   **Multiple Variations per `!SPRID`**: A single `!SPRID` can represent several distinct enemy types (e.g., Ice Keese, Fire Keese, Vampire Bat) by assigning unique `SprSubtype` values. This allows for efficient reuse of sprite slots and base logic while providing varied challenges.
*   **Dynamic Environmental Transformation**: Sprites can change their `SprSubtype` (and thus their behavior/appearance) in response to environmental factors. For example, an Octorok might transform from a land-based to a water-based variant upon entering water tiles. This adds depth and realism to enemy interactions with the environment.

### 8.8. Vanilla Sprite Overrides and Conditional Logic
When modifying existing enemies or creating new boss sequences, it's common to override vanilla sprite behavior. This allows for custom implementations while retaining the original sprite ID.

*   **Hooking Entry Points**: Use `pushpc`/`pullpc` and `org` directives to redirect execution from vanilla sprite routines to your custom code. This is crucial for replacing or extending existing behaviors.
*   **Contextual Checks**: Implement checks (e.g., using custom flags or game state variables) within your custom routines to determine whether to execute your custom logic or fall back to the original vanilla behavior. This provides flexibility and allows for conditional modifications.