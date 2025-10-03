# RAM Analysis: The Engine's State

This document provides a high-level analysis of how Work RAM (WRAM) and Save RAM (SRAM) are used to manage the game's state. For a raw list of addresses, see `Core/ram.asm` and `Core/sram.asm`.

## 1. The Core Game Loop: WRAM in Motion

The entire game is driven by a master state machine whose state is stored in a single WRAM variable:

-   **`MODE` (`$7E0010`):** This is the game's primary state index. The main loop in `bank_00.asm` reads this value every frame and jumps to the corresponding module in the `Module_MainRouting` table.
-   **`SUBMODE` (`$7E0011`):** Many modules have their own internal state machines. This variable holds the sub-state for the current `MODE`.

This `MODE`/`SUBMODE` pattern is the fundamental driver of the game's flow. For example:
-   When Link opens the menu, the game sets `MODE` to `0x0E` (Interface), which gives control to the menu engine.
-   When Link talks to a character, `Interface_PrepAndDisplayMessage` is called, which saves the current game state to `MODECACHE` (`$7E010C`) and then sets `MODE` to `0x0E` to display the text box. When the dialogue is finished, the previous state is restored from the cache.
-   Transitioning between the overworld and underworld involves setting `MODE` to `0x08` (Overworld Load) or `0x06` (Underworld Load), respectively.

## 2. Defining the World: Location and Environment

The player's location and the properties of their environment are controlled by a handful of key WRAM variables.

-   **`INDOORS` (`$7E001B`):** A simple but powerful flag (`0x01` for indoors, `0x00` for outdoors). This variable is checked by numerous systems to alter their behavior. For instance, the `ZSCustomOverworld` system reads this flag to determine whether to apply day/night palettes, and the audio engine uses it to select the appropriate music track.

-   **`OWSCR` (`$7E008A`) and `ROOM` (`$7E00A0`):** These variables store the player's current location. `OWSCR` holds the Overworld screen ID, while `ROOM` holds the Underworld room ID.

The interaction between these variables is central to world traversal. When Link enters a cave on `OWSCR` 0x35, the following happens:
1.  The game looks up the entrance data for that tile in `Overworld/entrances.asm`.
2.  This data specifies the destination `ROOM` ID (e.g., 0x0104).
3.  The `INDOORS` flag is set to `0x01`.
4.  The main game `MODE` is set to `0x06` (Underworld Load).
5.  The dungeon engine in `bank_01.asm` takes over. It reads the `ROOM` ID and uses it to look up the room's header in `ALTTP/rooms.asm`. This header contains pointers to all the data needed to draw the room, including its layout, objects, and sprites.

## 3. Room-Specific Behavior

Once a room is loaded, its specific behavior is governed by tags and flags.

-   **`TAG1`/`TAG2` (`$7E00AE`/`$AF`):** These are "Room Effect" tags loaded from the room's header. They trigger special behaviors like kill rooms, shutter doors, or custom events defined in `Dungeons/custom_tag.asm`. For example, a kill room tag will cause the `Underworld_HandleRoomTags` routine to check if all sprites in the room (`$7E0E20+`) have been defeated.

-   **`UWDEATH` (`$7FDF80`) and `OWDEATH` (`$7FEF80`):** These are large bitfields in SRAM that track the state of every overworld screen and underworld room. When a kill room is cleared or a key is taken from a chest, a bit is set in this array. This ensures that the state persists permanently in the save file, preventing enemies from respawning or chests from reappearing.

## 4. The Player and Entities

-   **Link:** The player's state is managed by its own state machine in `bank_07.asm`, with the current state held in `LINKDO` (`$7E005D`). This is covered in detail in `Docs/Link.md`.

-   **Sprites and Ancillae:** The WRAM regions from `$7E0D00` onwards are large arrays that hold the state of all active entities in the game (16 sprites, ~40 ancillae). These are defined as `structs` in `Core/structs.asm`. While there are dozens of variables for each sprite, the most important for general game logic are:
    -   `SprState` (`$7E0DD0,X`): The sprite's main state (e.g., `0x09` for active, `0x0B` for stunned).
    -   `SprType` (`$7E0E20,X`): The sprite's ID number.
    -   `SprX`/`SprY` (`$0D10,X`/`$0D00,X`): The sprite's coordinates.

    The sprite engine in `bank_06.asm` iterates through these arrays each frame, executing the logic for each active sprite.

## 4.5. Custom WRAM Region (`$7E0730+`)

Oracle of Secrets adds a custom WRAM region starting at `$7E0730`, utilizing the MAP16OVERFLOW free RAM space. All custom variables documented here have been verified against `Core/ram.asm` and are actively used by the project's custom systems.

### Verified Custom WRAM Variables

| Address    | Label                   | Description                                               | Verified |
|------------|-------------------------|-----------------------------------------------------------|----------|
| `$7E0730`  | `MenuScrollLevelV`      | Vertical scroll position for the custom menu system       | ✓        |
| `$7E0731`  | `MenuScrollLevelH`      | Horizontal scroll position for the custom menu system     | ✓        |
| `$7E0732`  | `MenuScrollHDirection`  | Direction flag for horizontal menu scrolling (2 bytes)    | ✓        |
| `$7E0734`  | `MenuItemValueSpoof`    | Temporary override for displayed menu item values (2 bytes)| ✓       |
| `$7E0736`  | `ShortSpoof`            | Shorter version of the spoof value (1 byte)               | ✓        |
| `$7E0737`  | `MusicNoteValue`        | Current music note value for Ocarina system (2 bytes)     | ✓        |
| `$7E0739`  | `GoldstarOrHookshot`    | Differentiates Hookshot (0) from Goldstar (1) mode        | ✓        |
| `$7E073A`  | `Neck_Index`            | Index for multi-part sprite body tracking (e.g., bosses)  | ✓        |
| `$7E073B`  | `Neck1_OffsetX`         | X-offset for first neck/body segment                      | ✓        |
| `$7E073C`  | `Neck1_OffsetY`         | Y-offset for first neck/body segment                      | ✓        |
| `$7E073D`  | `Neck2_OffsetX`         | X-offset for second neck/body segment                     | ✓        |
| `$7E073E`  | `Neck2_OffsetY`         | Y-offset for second neck/body segment                     | ✓        |
| `$7E073F`  | `Neck3_OffsetX`         | X-offset for third neck/body segment                      | ✓        |
| `$7E0740`  | `Neck3_OffsetY`         | Y-offset for third neck/body segment                      | ✓        |
| `$7E0741`  | `Offspring1_Id`         | Sprite ID of first child sprite (for boss mechanics)      | ✓        |
| `$7E0742`  | `Offspring2_Id`         | Sprite ID of second child sprite (for boss mechanics)     | ✓        |
| `$7E0743`  | `Offspring3_Id`         | Sprite ID of third child sprite (for boss mechanics)      | ✓        |
| `$7E0744`  | `Kydreeok_Id`           | Sprite ID for Kydreeok boss entity                        | ✓        |
| `$7E0745`  | `FishingOrPortalRod`    | Differentiates Fishing Rod (1) from Portal Rod (2)        | ✓        |

### Usage Notes

-   **Menu System**: Variables `$7E0730-$7E0736` are exclusively used by the custom menu system (`Menu/menu.asm`) to manage smooth scrolling between the Items and Quest Status pages.

-   **Item Differentiation**: `GoldstarOrHookshot` and `FishingOrPortalRod` are critical for shared inventory slots. These allow two distinct items to occupy a single menu slot, with the player able to switch between them using the L/R shoulder buttons.

-   **Boss Mechanics**: The `Neck_*` and `Offspring_*` variables enable complex multi-part boss sprites (e.g., Kydreeok with multiple heads, Manhandla with independent parts). The parent sprite uses these to track and coordinate its child sprite components.

-   **Memory Safety**: All variables in this region are placed within the MAP16OVERFLOW free RAM area, which is guaranteed to be unused by the vanilla game engine. This prevents conflicts with vanilla systems.

## 5. Long-Term Progression: SRAM and Custom Flags

SRAM (`$7EF000+`) stores the player's save file and is the key to managing long-term quest progression. Oracle of Secrets heavily expands the vanilla save format to support its new data-driven systems.

-   **`OOSPROG` (`$7EF3D6`) and `OOSPROG2` (`$7EF3C6`):** These are the primary bitfields for tracking major and minor quest milestones. They are the heart of the game's custom progression.
    -   **Example Flow:**
        1.  The player talks to the `village_elder` NPC for the first time.
        2.  The NPC's code in `Sprites/NPCs/village_elder.asm` sets a specific bit in `OOSPROG` (e.g., `ORA.b #$10 : STA.l OOSPROG`).
        3.  Later, the world map code in `Overworld/world_map.asm` checks this bit (`LDA.l OOSPROG : AND.b #$10`). If it's set, a new icon is displayed on the map.

-   **Other Custom SRAM:** The project adds many other custom variables to SRAM to track new systems, such as:
    -   **New Inventory:** `ZoraMask` (`$7EF347`), `RocsFeather` (`$7EF34D`), etc.
    -   **Side-Quests:** `MagicBeanProg` (`$7EF39B`) tracks the growth of a magic bean over time.
    -   **New Collectibles:** A block starting at `$7EF38B` tracks items like `Bananas` and `Seashells`.

This data-driven approach, centered on modifying and checking flags in SRAM, allows for complex, stateful quest design that persists across play sessions.