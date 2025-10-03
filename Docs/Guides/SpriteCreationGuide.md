# Sprite Creation Guide

This guide provides a step-by-step walkthrough for creating a new custom sprite in Oracle of Secrets using the project's modern sprite system.

## 1. File Setup

1.  **Create the Sprite File:** Create a new `.asm` file for your sprite in the appropriate subdirectory of `Sprites/`:
    *   `Sprites/Enemies/` - For enemy sprites
    *   `Sprites/Bosses/` - For boss sprites
    *   `Sprites/NPCs/` - For non-playable character sprites
    *   `Sprites/Objects/` - For interactive objects and items

2.  **Include the File:** Open `Sprites/all_sprites.asm` and add an `incsrc` directive to include your new file. The file must be placed in the correct bank section:
    *   **Bank 30** (`$308000`) - First bank, includes `sprite_new_table.asm` and some core sprites
    *   **Bank 31** (`$318000`) - Second bank, includes `sprite_functions.asm` and more sprites
    *   **Bank 32** (`$328000`) - Third bank for additional sprites
    *   **Bank 2C** (Dungeon bank) - For sprites that are part of dungeon-specific content

    Example:
    ```asm
    ; In Sprites/all_sprites.asm
    org    $318000 ; Bank 31
    %log_start("my_new_enemy", !LOG_SPRITES)
    incsrc "Sprites/Enemies/MyNewEnemy.asm"
    %log_end("my_new_enemy", !LOG_SPRITES)
    ```

3.  **Assign a Sprite ID:** Choose an unused sprite ID for your sprite. You can either:
    *   Use a completely new ID (e.g., `$A0` through `$FF` range)
    *   Override a vanilla sprite ID (for replacing existing sprites)
    *   Share an ID with another sprite and use `SprSubtype` to differentiate behaviors

## 2. Sprite Properties

At the top of your new sprite file, define its core properties using the provided template. These `!` constants are used by the `%Set_Sprite_Properties` macro to automatically configure the sprite's behavior and integrate it into the game.

```asm
; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $XX ; CHOOSE AN UNUSED SPRITE ID or use a constant like Sprite_MyNewEnemy
!NbrTiles           = 02  ; Number of 8x8 tiles used in the largest frame
!Harmless           = 00  ; 00 = Harmful, 01 = Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 10  ; Number of Health the sprite has
!Damage             = 04  ; Damage dealt to Link on contact (08 = whole heart, 04 = half heart)
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attacked, 01 = all attacks clink harmlessly
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 08  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = sprite continues to live offscreen
!Statis             = 00  ; 00 = sprite is alive? (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layers for collision
!CanFall            = 00  ; 01 = sprite can fall in holes, 00 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk in shallow water
!Blockable          = 00  ; 01 = can be blocked by Link's shield
!Prize              = 01  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is a statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

; This macro MUST be called after the properties
%Set_Sprite_Properties(Sprite_MyNewEnemy_Prep, Sprite_MyNewEnemy_Long)
```

### Property Details

**Memory Mapping:** The `%Set_Sprite_Properties` macro writes these properties to specific ROM addresses:
*   `$0DB080+!SPRID` - OAM/Harmless/HVelocity/NbrTiles
*   `$0DB173+!SPRID` - Sprite HP
*   `$0DB266+!SPRID` - Sprite Damage
*   `$0DB359+!SPRID` - Death Animation/Impervious/Shadow/Palette flags
*   `$0DB44C+!SPRID` - Collision Layer/Statis/Persist/Hitbox
*   `$0DB53F+!SPRID` - DeflectArrow/Boss/CanFall flags
*   `$0DB632+!SPRID` - Interaction/WaterSprite/Blockable/Sound/Prize
*   `$0DB725+!SPRID` - Statue/DeflectProjectiles/Impervious flags

The macro also sets up the jump table entries at:
*   `$069283+(!SPRID*2)` - Vanilla Sprite Main Pointer
*   `$06865B+(!SPRID*2)` - Vanilla Sprite Prep Pointer
*   `NewSprRoutinesLong+(!SPRID*3)` - New Long Sprite Pointer
*   `NewSprPrepRoutinesLong+(!SPRID*3)` - New Long Sprite Prep Pointer

### Design Considerations

*   **Multi-purpose Sprite IDs:** A single `!SPRID` can be used for multiple distinct behaviors (e.g., Keese, Fire Keese, Ice Keese, Vampire Bat all share sprite IDs) through the use of `SprSubtype`. This is a powerful technique for reusing sprite slots and creating variations of enemies.
*   **Damage Handling for Bosses:** For boss sprites, `!Damage = 00` is common if damage is applied through other means, such as spawned projectiles or direct contact logic within the main routine.
*   **Dynamic Health:** Many sprites set health dynamically in their `_Prep` routine based on game progression (e.g., Booki sets health based on Link's sword level, Darknut based on sword upgrades).
*   **Custom Boss Logic:** Setting `!Boss = 00` for a boss sprite indicates that custom boss logic is being used, rather than relying on vanilla boss flags.
*   **Shared Sprite IDs:** Multiple distinct NPCs or objects can share a single `!SPRID` by using `SprSubtype` for differentiation (e.g., `Sprite_Mermaid = $F0` is used for Mermaid, Maple, and Librarian with different subtypes).

## 3. Main Structure (`_Long` routine)

This is the main entry point for your sprite, called by the game engine every frame. Its primary job is to call the drawing and logic routines.

```asm
Sprite_MyNewEnemy_Long:
{
  PHB : PHK : PLB      ; Set up bank registers (Push Bank, Push K, Pull Bank)
  JSR Sprite_MyNewEnemy_Draw
  JSL Sprite_DrawShadow  ; Optional: Draw a shadow (use appropriate shadow function)

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive ; Only run logic if active
    JSR Sprite_MyNewEnemy_Main
  .SpriteIsNotActive

  PLB                  ; Restore bank register
  RTL                  ; Return from long routine
}
```

### Important Notes

*   **Bank Register Management:** Always use `PHB : PHK : PLB` at the start and `PLB` before `RTL` to ensure proper bank context.
*   **Sprite_CheckActive:** This critical function checks if the sprite should execute logic based on its state, freeze status, and pause flags. Returns carry set if active.
*   **Drawing Order:** Drawing is typically done before the main logic, though the order can vary based on sprite needs.
*   **Conditional Drawing:** Shadow drawing might be conditional based on the sprite's current action or state (e.g., Thunder Ghost only draws shadow when grounded).

## 4. Initialization (`_Prep` routine)

This routine runs *once* when the sprite is first spawned. Use it to set initial values for timers, its action state, and any other properties. For dynamic difficulty scaling, you can adjust properties based on game progression here.

```asm
Sprite_MyNewEnemy_Prep:
{
  PHB : PHK : PLB
  
  ; Set dynamic health based on sword level (optional)
  LDA.l Sword : DEC A : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  
  %GotoAction(0)      ; Set the initial state to the first one in the jump table
  %SetTimerA(120)     ; Set a general-purpose timer to 120 frames (2 seconds)
  
  PLB
  RTL
  
  ; Optional: Dynamic health table
  .health
    db $04, $08, $10, $18  ; Health values for sword levels 1-4
}
```

### Available Sprite RAM Variables

The following WRAM addresses are available for sprite-specific data (all indexed by X):

**Position & Movement:**
*   `SprY, SprX` ($0D00, $0D10) - 8-bit position coordinates (low byte)
*   `SprYH, SprXH` ($0D20, $0D30) - High bytes of position
*   `SprYSpeed, SprXSpeed` ($0D40, $0D50) - Movement velocities
*   `SprYRound, SprXRound` ($0D60, $0D70) - Sub-pixel precision
*   `SprCachedX, SprCachedY` ($0FD8, $0FDA) - Cached coordinates

**Animation & Graphics:**
*   `SprAction` ($0D80) - Current state in state machine
*   `SprFrame` ($0D90) - Current animation frame index
*   `SprGfx` ($0DC0) - Graphics offset for drawing
*   `SprFlash` ($0B89) - Flash color for damage indication

**Timers:**
*   `SprTimerA-F` ($0DF0, $0E00, $0E10, $0EE0, $0F10, $0F80) - Six general-purpose timers
*   Note: `SprTimerF` decreases by 2 each frame (used for gravity)

**Miscellaneous Data:**
*   `SprMiscA-G` ($0DA0, $0DB0, $0DE0, $0E90, $0EB0, $0EC0, $0ED0) - Seven general-purpose variables
*   `SprCustom` ($1CC0) - Additional custom data storage

**State & Properties:**
*   `SprState` ($0DD0) - Sprite state (0x00=dead, 0x08=spawning, 0x09=active, etc.)
*   `SprType` ($0E20) - Sprite ID
*   `SprSubtype` ($0E30) - Sprite subtype for variations
*   `SprHealth` ($0E50) - Current health
*   `SprNbrOAM` ($0E40) - Number of OAM slots + flags
*   `SprFloor` ($0F20) - Layer (0=top, 1=bottom)
*   `SprHeight` ($0F80) - Z-position for altitude/jumping

### Common Initialization Patterns

```asm
; Set sprite to be impervious initially (e.g., for a boss with phases)
LDA.b #$80 : STA.w SprDefl, X

; Configure tile collision behavior
LDA.b #%01100000 : STA.w SprTileDie, X

; Set bump damage type
LDA.b #$09 : STA.w SprBump, X

; Initialize custom variables
STZ.w SprMiscA, X
STZ.w SprMiscB, X
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
    JSL Sprite_CheckIfRecoiling
    
    ; Return to attacking after recoil
    LDA.w SprRecoil, X : BNE .still_recoiling
      %GotoAction(1)
    .still_recoiling
    RTS
  }
}
```

### Available Macros

**State Management:**
*   `%GotoAction(action)` - Set `SprAction` to switch states
*   `%SpriteJumpTable(state1, state2, ...)` - Create state machine jump table
*   `%JumpTable(index, state1, state2, ...)` - Jump table with custom index

**Animation:**
*   `%PlayAnimation(start, end, speed)` - Animate frames (uses `SprTimerB`)
*   `%PlayAnimBackwards(start, end, speed)` - Animate in reverse
*   `%StartOnFrame(frame)` - Ensure animation starts at a minimum frame
*   `%SetFrame(frame)` - Directly set animation frame

**Movement:**
*   `%MoveTowardPlayer(speed)` - Apply speed toward player and move
*   `%SetSpriteSpeedX(speed)` - Set horizontal velocity
*   `%SetSpriteSpeedY(speed)` - Set vertical velocity

**Timers:**
*   `%SetTimerA-F(length)` - Set timer values

**Player Interaction:**
*   `%DoDamageToPlayerSameLayerOnContact()` - Damage on contact (same layer only)
*   `%PlayerCantPassThrough()` - Prevent Link from passing through sprite
*   `%ShowSolicitedMessage(id)` - Show message when player presses A
*   `%ShowMessageOnContact(id)` - Show message on contact
*   `%ShowUnconditionalMessage(id)` - Show message immediately

**Sprite Properties:**
*   `%SetHarmless(value)` - 0=harmful, 1=harmless
*   `%SetImpervious(value)` - Toggle invulnerability
*   `%SetRoomFlag(value)` - Set room completion flag

**Audio:**
*   `%PlaySFX1(id)`, `%PlaySFX2(id)` - Play sound effect
*   `%PlayMusic(id)` - Change background music
*   `%ErrorBeep()` - Play error sound

**Utility:**
*   `%ProbCheck(mask, label)` - Random check, branch if result is non-zero
*   `%ProbCheck2(mask, label)` - Random check, branch if result is zero
*   `%SetupDistanceFromSprite()` - Setup distance calculation

### Common Functions

**Movement & Physics:**
*   `Sprite_Move` / `Sprite_MoveLong` - Apply velocity to position
*   `Sprite_MoveHoriz` / `Sprite_MoveVert` - Move in one axis
*   `Sprite_BounceFromTileCollision` - Bounce off walls
*   `Sprite_CheckTileCollision` - Check for tile collision
*   `Sprite_ApplySpeedTowardsPlayer` - Calculate speed toward player
*   `Sprite_FloatTowardPlayer` - Float toward player with altitude
*   `Sprite_FloatAwayFromPlayer` - Float away from player
*   `Sprite_InvertSpeed_X` / `Sprite_InvertSpeed_Y` - Reverse velocity

**Combat:**
*   `Sprite_CheckDamageFromPlayer` - Check if player attacked sprite
*   `Sprite_CheckDamageToPlayer` - Check if sprite damaged player
*   `Sprite_DamageFlash_Long` - Flash sprite when damaged
*   `Sprite_CheckIfRecoiling` - Handle knockback after being hit
*   `Guard_ParrySwordAttacks` - Parry sword attacks (like Darknut)

**Spawning:**
*   `Sprite_SpawnDynamically` - Spawn a new sprite
*   `Sprite_SpawnProbeAlways_long` - Spawn probe projectile
*   `Sprite_SpawnSparkleGarnish` - Spawn sparkle effect

**Distance & Direction:**
*   `GetDistance8bit_Long` - Get 8-bit distance to player
*   `Sprite_DirectionToFacePlayer` - Get direction to face player
*   `Sprite_IsToRightOfPlayer` - Check if sprite is to right of player

**Randomness:**
*   `GetRandomInt` - Get random 8-bit value

### Code Style Guidelines

*   **Named Constants:** Always use named constants for magic numbers:
    ```asm
    GoriyaMovementSpeed = 10
    LDA.b #GoriyaMovementSpeed : STA.w SprXSpeed, X
    ```
*   **Processor Status Flags:** Explicitly manage 8-bit/16-bit mode with `REP #$20` (16-bit) and `SEP #$20` (8-bit), especially during OAM calculations
*   **State Machine Pattern:** Use `SprAction` with `%SpriteJumpTable` for clear state management
*   **Timer Usage:** Use dedicated timers for different purposes (e.g., `SprTimerA` for state changes, `SprTimerB` for animation, `SprTimerC` for cooldowns)

## 6. Drawing (`_Draw` routine)

This routine renders your sprite's graphics. The project provides the `%DrawSprite()` macro for standard drawing, which reads from data tables you define.

### Standard Drawing with %DrawSprite()

```asm
Sprite_MyNewEnemy_Draw:
{
  JSL Sprite_PrepOamCoord              ; Prepare OAM coordinates
  JSL Sprite_OAM_AllocateDeferToPlayer ; Allocate OAM slots
  
  %DrawSprite()

  ; --- OAM Data Tables ---
  .start_index  ; Starting index in the tables for each animation frame
    db $00, $02, $04, $06
  .nbr_of_tiles ; Number of tiles to draw for each frame (actual count minus 1)
    db 1, 1, 1, 1

  .x_offsets    ; X-position offset for each tile (16-bit values)
    dw -8, 8, -8, 8, -8, 8, -8, 8
  .y_offsets    ; Y-position offset for each tile (16-bit values)
    dw -8, -8, -8, -8, -8, -8, -8, -8
  .chr          ; The character (tile) number from the graphics sheet
    db $C0, $C2, $C4, $C6, $C8, $CA, $CC, $CE
  .properties   ; OAM properties (palette, priority, flips)
    db $3B, $7B, $3B, $7B, $3B, $7B, $3B, $7B
  .sizes        ; Size of each tile (e.g., $02 for 16x16)
    db $02, $02, $02, $02, $02, $02, $02, $02
}
```

### OAM Property Byte Format

The `.properties` byte contains flags for each tile:
*   Bits 0-2: Palette (0-7)
*   Bit 3: Priority (0=front, 1=behind BG)
*   Bit 4: Unused
*   Bit 5: Horizontal flip
*   Bit 6: Vertical flip
*   Bit 7: Unused

Example values:
*   `$39` = Palette 1, no flip, front priority
*   `$79` = Palette 1, horizontal flip, front priority
*   `$B9` = Palette 1, vertical flip, front priority

### Custom Drawing Logic

For complex drawing needs (multi-part sprites, dynamic flipping, etc.), implement custom drawing:

```asm
Sprite_MyNewEnemy_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY ; Get animation frame
  LDA.w .start_index, Y : STA $06                  ; Get starting index
  LDA.w SprFlash, X : STA $08                      ; Store flash value
  LDA.w SprMiscC, X : STA $09                      ; Store direction for flipping

  PHX
  LDX .nbr_of_tiles, Y ; Load number of tiles minus 1
  LDY.b #$00           ; OAM buffer index
  
  .nextTile
    PHX                                ; Save tile index
    TXA : CLC : ADC $06 : PHA          ; Calculate absolute tile index
    ASL A : TAX                        ; Multiply by 2 for 16-bit offsets
    
    REP #$20                           ; 16-bit accumulator
    LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y  ; Write X position
    AND.w #$0100 : STA $0E                             ; Store X high bit
    INY
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y  ; Write Y position
    CLC : ADC #$0010 : CMP.w #$0100                    ; Check if on screen
    SEP #$20                           ; Back to 8-bit
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y : STA $0E  ; Move offscreen
    .on_screen_y
    
    PLX              ; Restore absolute tile index
    INY
    LDA .chr, X : STA ($90), Y         ; Write character
    INY
    
    ; Apply horizontal flip based on direction
    LDA.b $09 : BEQ .no_flip
      LDA.b #$79 : JMP .write_prop
    .no_flip
    LDA .properties, X
    .write_prop
    ORA $08 : STA ($90), Y             ; Write properties with flash
    
    PHY
    TYA : LSR #2 : TAY
    LDA .sizes, X : ORA $0F : STA ($92), Y  ; Write size
    PLY : INY
    
    PLX : DEX : BPL .nextTile

  PLX
  RTS

  ; Data tables follow...
}
```

### Important Drawing Notes

*   **16-bit Calculations:** Always use `REP #$20` before 16-bit position calculations and `SEP #$20` afterward
*   **OAM Allocation:** Different allocation functions for different scenarios:
    *   `Sprite_OAM_AllocateDeferToPlayer` - Standard allocation
    *   `OAM_AllocateFromRegionE` - For large sprites (bosses)
    *   `Sprite_OAM_AllocateDeferToPlayerLong` - Long version
*   **Shadow Drawing:** Call `Sprite_DrawShadow` in the `_Long` routine, not in `_Draw`
*   **Multi-Layer Drawing:** For objects like minecarts that Link can be "inside", draw in multiple parts from different OAM regions to create depth
*   **Conditional Drawing:** Some sprites (like followers or bosses) dispatch to different draw routines based on `SprSubtype` or current state

## 7. Final Integration

The `%Set_Sprite_Properties()` macro you added in Step 2 handles the final integration automatically. It:

1.  Writes your sprite properties to the appropriate ROM addresses
2.  Sets up pointers in the vanilla sprite jump tables
3.  Adds your `_Prep` and `_Long` routines to the new sprite table in `Core/sprite_new_table.asm`

Your sprite is now ready to be placed in the game world using your level editor!

## 8. Testing Your Sprite

1.  **Build the ROM:** Run your build script (`build.sh` or `build.bat`)
2.  **Place in Editor:** Use your level editor to place the sprite in a room
3.  **Test Behavior:** Load the room and verify:
    *   Sprite spawns correctly
    *   Animation plays as expected
    *   Movement works properly
    *   Collision detection functions
    *   Damage and health mechanics work
    *   State transitions occur correctly

## 9. Common Issues and Solutions

### Sprite Doesn't Appear
*   Check that the sprite ID is not already in use
*   Verify the `incsrc` directive is in the correct bank
*   Ensure `%Set_Sprite_Properties` is called after property definitions
*   Check that the sprite is being placed in a compatible room type

### Graphics are Corrupted
*   Verify 16-bit mode (`REP #$20`) is used for OAM calculations
*   Check that `.start_index`, `.nbr_of_tiles`, and data tables are correctly sized
*   Ensure `.sizes` table uses correct values ($00=8x8, $02=16x16)
*   Verify character numbers (`.chr`) match your graphics sheet

### Sprite Behaves Incorrectly
*   Check that timers are being set and checked correctly
*   Verify state transitions in the jump table
*   Ensure `Sprite_CheckActive` is called before main logic
*   Check that collision functions are being called in the right order

### Performance Issues
*   Reduce `!NbrTiles` if using too many tiles
*   Optimize drawing routine (avoid redundant calculations)
*   Use simpler collision detection where possible
*   Consider using `!Persist = 00` for non-critical sprites

## 10. Advanced Sprite Design Patterns

## 10. Advanced Sprite Design Patterns

### 10.1. Multi-Part Sprites and Child Sprites

For complex bosses or entities, break them down into a main parent sprite and multiple child sprites. Examples include Kydreeok (body + heads), Darknut (knight + probes), Goriya (enemy + boomerang), and Helmet Chuchu (body + detachable helmet).

**Parent Sprite Responsibilities:**
*   Spawns and manages child sprites using `Sprite_SpawnDynamically`
*   Stores child sprite IDs in global variables or `SprMisc` slots
*   Monitors child sprite states to determine phases or defeat conditions
*   Handles overall movement, phase transitions, and global effects

**Child Sprite Responsibilities:**
*   Handles independent logic, movement, and attacks
*   May be positioned relative to parent sprite
*   Uses `SprSubtype` to differentiate between multiple instances

**Example: Kydreeok Boss**
```asm
; In Kydreeok body sprite
SpawnLeftHead:
{
  LDA #$CF  ; Kydreeok Head sprite ID
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA.w Offspring1_Id        ; Store child ID globally
    LDA.b #$00 : STA.w SprSubtype, Y ; Subtype 0 = left head
    ; Position relative to parent
    REP #$20
    LDA.w SprCachedX : SEC : SBC.w #$0010
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y
    ; ... more initialization
  .return
  RTS
}

; Check if all heads are defeated
Sprite_Kydreeok_CheckIfDead:
{
  LDA.w Offspring1_Id : TAY
  LDA.w SprState, Y : BNE .not_dead  ; Check if left head alive
  LDA.w Offspring2_Id : TAY
  LDA.w SprState, Y : BNE .not_dead  ; Check if right head alive
  ; All heads defeated - trigger death sequence
  .not_dead
  RTS
}
```

**Shared Sprite IDs for Variations:**
A single sprite ID can represent different enemy types using `SprSubtype`:
*   Keese sprite ID shared by: Regular Keese, Fire Keese, Ice Keese, Vampire Bat
*   Mermaid sprite ID ($F0) shared by: Mermaid, Maple, Librarian (all using different subtypes)
*   This efficiently reuses sprite slots and base logic

### 10.2. Quest Integration and Dynamic Progression

Boss fights and NPC interactions can be deeply integrated with quest progression using SRAM flags, dynamic health management, and multi-phase battles.

**Phase Transitions:**
Trigger new phases based on health thresholds, timers, or child sprite states:
```asm
; Check health threshold for phase change
LDA.w SprHealth, X : CMP.b #$10 : BCS .phase_one
  LDA.w SprMiscD, X : CMP.b #$02 : BEQ .already_phase_two
    LDA.b #$02 : STA.w SprMiscD, X  ; Switch to phase 2
    JSR LoadPhase2Graphics
    JSR SpawnPhase2Adds
  .already_phase_two
.phase_one
```

**Health Management:**
*   **Direct Health:** Use `SprHealth` for straightforward health tracking
*   **Indirect Health:** Base defeat on child sprite states (e.g., Kydreeok defeated when all heads are killed)
*   **Phase-Based Health:** Refill health between phases for extended boss fights
*   **Dynamic Scaling:** Adjust health based on Link's sword level or progression

**Quest Integration Examples:**
*   **Wolfos:** After being subdued, plays Song of Healing animation and grants Wolf Mask
*   **Bug Net Kid:** Dialogue changes based on whether Link has the Bug Net
*   **Maple:** Spawns items and interacts with Link differently based on quest flags
*   **Mask Salesman:** Complex shop system with inventory checks and rupee deduction
*   **Zora Princess:** Quest rewards and dialogue conditional on SRAM flags

**SRAM Flag Usage:**
```asm
; Check if quest item has been obtained
LDA.l $7EF3XX : CMP.b #$XX : BNE .not_obtained
  ; Quest item obtained - change behavior
  %ShowUnconditionalMessage(MessageID)
  JMP .quest_complete
.not_obtained
```

### 10.4. Code Reusability and Best Practices

**Shared Logic Functions:**
Create reusable functions for common behaviors across multiple sprites:
```asm
; Shared by Goriya and Darknut
Goriya_HandleTileCollision:
{
  JSL Sprite_CheckTileCollision
  LDA.w SprCollision, X : BEQ .no_collision
    JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    STA.w SprMiscE, X
    %SetTimerC(60)
  .no_collision
  RTS
}
```

**Named Constants:**
Always use named constants instead of magic numbers:
```asm
; Good
GoriyaMovementSpeed = 10
MinecartSpeed = 20
DoubleSpeed = 30

LDA.b #GoriyaMovementSpeed : STA.w SprXSpeed, X

; Bad
LDA.b #10 : STA.w SprXSpeed, X  ; What does 10 mean?
```

**Processor Status Management:**
Explicitly manage 8-bit/16-bit modes:
```asm
REP #$20  ; 16-bit accumulator
LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
SEP #$20  ; Back to 8-bit
```

**State Machine Pattern:**
Use `SprAction` with jump tables for clear state management:
```asm
Sprite_Enemy_Main:
{
  %SpriteJumpTable(State_Idle, State_Chase, State_Attack, State_Retreat)
  
  State_Idle: { /* ... */ RTS }
  State_Chase: { /* ... */ RTS }
  State_Attack: { /* ... */ RTS }
  State_Retreat: { /* ... */ RTS }
}
```

**Timer Management:**
Use different timers for different purposes:
*   `SprTimerA` - State transitions, cooldowns
*   `SprTimerB` - Animation (automatically used by `%PlayAnimation`)
*   `SprTimerC` - Movement changes, direction changes
*   `SprTimerD` - Attack cooldowns
*   `SprTimerE` - Special effects
*   `SprTimerF` - Gravity/altitude (decrements by 2)

### 10.5. Centralized Handlers and Multi-Purpose Sprites

Many sprite files serve as central handlers for multiple distinct entities, using conditional logic to dispatch behaviors.

**Examples:**
*   **Followers** (`followers.asm`) - Zora Baby, Old Man, Kiki
*   **Mermaid** (`mermaid.asm`) - Mermaid (subtype 0), Maple (subtype 1), Librarian (subtype 2)
*   **Zora** (`zora.asm`) - Various Zora NPCs with different roles
*   **Collectible** (`collectible.asm`) - Different collectible items
*   **Deku Leaf** (`deku_leaf.asm`) - Deku Leaf and Beach Whirlpool

**Implementation Pattern:**
```asm
Sprite_MultiPurpose_Long:
{
  PHB : PHK : PLB
  
  ; Dispatch based on subtype
  LDA.w SprSubtype, X
  JSL JumpTableLocal
  dw Type0_Routine
  dw Type1_Routine
  dw Type2_Routine
  
  Type0_Routine:
    JSR Type0_Draw
    JSR Type0_Main
    PLB : RTL
    
  Type1_Routine:
    JSR Type1_Draw
    JSR Type1_Main
    PLB : RTL
}
```

### 10.6. Overriding Vanilla Sprites

To replace vanilla sprite behavior while keeping the original sprite ID:

```asm
; In a patch file or at the start of your sprite file
pushpc
org $069283+($XX*2)  ; Replace vanilla main pointer
dw NewCustomBehavior_Main
org $06865B+($XX*2)  ; Replace vanilla prep pointer
dw NewCustomBehavior_Prep
pullpc

NewCustomBehavior_Main:
{
  ; Check if custom behavior should activate
  LDA.l $7EF3XX : CMP.b #$YY : BNE .use_vanilla
    JSL CustomImplementation_Long
    RTS
  .use_vanilla
  JML $OriginalVanillaAddress
}
```

### 10.7. Interactive Objects and Environmental Triggers

**Player-Manipulated Objects:**
Objects like Ice Block and Minecart require precise collision and alignment:
```asm
; Round position to 8-pixel grid for proper alignment
RoundCoords:
{
  LDA.b $00 : CLC : ADC.b #$04 : AND.b #$F8 : STA.b $00 : STA.w SprY, X
  LDA.b $02 : CLC : ADC.b #$04 : AND.b #$F8 : STA.b $02 : STA.w SprX, X
  JSR UpdateCachedCoords
  RTS
}
```

**Environmental Triggers:**
Switch objects respond to player actions and modify game state:
```asm
; Mine switch changes track configuration
Sprite_Mineswitch_OnActivate:
{
  LDA.w SprMiscA, X : BEQ .currently_off
    ; Switch is on, turn it off
    STZ.w SprMiscA, X
    JSR UpdateTrackTiles_Off
    JMP .done
  .currently_off
    ; Switch is off, turn it on
    LDA.b #$01 : STA.w SprMiscA, X
    JSR UpdateTrackTiles_On
  .done
  %PlaySFX2($14)  ; Switch sound
  RTS
}
```

### 10.8. Shop and Item Management

**Transaction System:**
```asm
Shopkeeper_SellItem:
{
  ; Check if player has enough rupees
  REP #$20
  LDA.l $7EF360 : CMP.w #ItemCost : BCC .not_enough
    ; Deduct rupees
    SEC : SBC.w #ItemCost : STA.l $7EF360
    SEP #$20
    ; Grant item
    LDA.b #ItemID : STA.l $7EF3XX
    %ShowUnconditionalMessage(ThankYouMessage)
    RTS
  .not_enough
  SEP #$20
  %ErrorBeep()
  %ShowUnconditionalMessage(NotEnoughRupeesMessage)
  RTS
}
```

**Item Granting with Quest Tracking:**
```asm
NPC_GrantQuestItem:
{
  ; Check if already received
  LDA.l $7EF3XX : BNE .already_obtained
    ; Grant item
    LDA.b #$01 : STA.l $7EF3XX
    LDA.b #ItemID
    JSL Link_ReceiveItem
    %ShowUnconditionalMessage(ItemReceivedMessage)
    RTS
  .already_obtained
  %ShowUnconditionalMessage(AlreadyHaveMessage)
  RTS
}
```

### 10.9. Player State Manipulation

For cinematic sequences and special interactions:
```asm
Cutscene_LinkSleep:
{
  ; Prevent player input
  %PreventPlayerMovement()
  
  ; Set Link's animation
  LDA.b #$XX : STA.w LinkAction
  
  ; Play sleep animation
  LDA.b #$XX : STA.w LinkGraphics
  
  ; Wait for timer
  LDA.w SprTimerA, X : BNE .still_waiting
    %AllowPlayerMovement()
    %GotoAction(NextState)
  .still_waiting
  RTS
}
```

### 10.10. Error Handling and Player Feedback

**Robust Error Prevention:**
```asm
; Portal sprite checks for valid placement
Sprite_Portal_CheckValidTile:
{
  LDA.w CurrentTileType : CMP.b #ValidTileMin : BCC .invalid
  CMP.b #ValidTileMax : BCS .invalid
  CMP.b #$XX : BEQ .invalid  ; Check specific invalid tiles
    ; Valid placement
    SEC
    RTS
  .invalid
    %ErrorBeep()
    STZ.w SprState, X  ; Despawn sprite
    CLC
    RTS
}
```

**Clear Player Feedback:**
```asm
; Provide audio/visual feedback
%ErrorBeep()                      ; Sound for errors
%PlaySFX1($14)                    ; Sound for success
JSL Sprite_ShowMessageUnconditional ; Text feedback
```

## 11. Additional Resources

**Core Files:**
*   `Core/sprite_macros.asm` - All available macros and their implementations
*   `Core/sprite_functions.asm` - Reusable sprite functions
*   `Core/sprite_new_table.asm` - Sprite table initialization
*   `Core/symbols.asm` - RAM address definitions
*   `Core/structs.asm` - Sprite structure definitions

**Documentation:**
*   `Docs/Sprites/` - Detailed documentation for existing sprites
*   `Docs/Sprites/Overlords.md` - Overlord system documentation
*   `Sprites/all_sprites.asm` - See how sprites are organized and included

**Example Sprites:**
*   **Simple Enemy:** `Sprites/Enemies/sea_urchin.asm` - Basic enemy with minimal logic
*   **Advanced Enemy:** `Sprites/Enemies/booki.asm` - Dynamic AI with state management
*   **Boss:** `Sprites/Bosses/kydreeok.asm` - Multi-part boss with child sprites
*   **Interactive Object:** `Sprites/Objects/minecart.asm` - Complex player interaction
*   **NPC:** `Sprites/NPCs/mask_salesman.asm` - Shop system and dialogue

