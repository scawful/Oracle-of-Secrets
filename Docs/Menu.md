# Custom Menu & HUD System

This document provides a detailed analysis of the custom menu and Heads-Up Display (HUD) systems in Oracle of Secrets, based on the code in the `Menu/` directory.

## 1. Overview

The project features a completely custom menu and HUD, replacing the vanilla systems. The menu is a robust, multi-screen system, while the HUD provides a clean, modern interface for in-game stats.

-   **Menu System**: A two-page design that separates selectable items from quest status and equipment. It is accessible by pressing the Start button.
-   **HUD System**: A persistent on-screen display for health, magic, rupees, and the currently equipped item.

## 2. Menu System Architecture

The entire menu operates as a large state machine, with the main entry point being `Menu_Entry` in `Menu/menu.asm`. The flow is controlled by the value in WRAM `$0200`.

### 2.1. Main State Machine

The `Menu_Entry` routine uses a jump table (`.vectors`) to execute different subroutines based on the state in `$0200`. This modular approach allows for a clean separation of tasks like initialization, drawing, input handling, and screen transitions.

**Key States in `$0200`:**

| State ID | Label                      | Purpose                                                                 |
|----------|----------------------------|-------------------------------------------------------------------------|
| `0x00`   | `Menu_InitGraphics`        | Initializes the menu, clears player state, and prepares for drawing.    |
| `0x01`   | `Menu_UploadRight`         | Draws the entire right-hand screen (Quest Status).                      |
| `0x02`   | `Menu_UploadLeft`          | Draws the entire left-hand screen (Item Selection).                     |
| `0x04`   | `Menu_ItemScreen`          | The main interactive state for the Item screen. Handles cursor movement.  |
| `0x05`   | `Menu_ScrollTo`            | Handles the smooth scrolling animation when moving from Items to Quest.   |
| `0x06`   | `Menu_StatsScreen`         | The main interactive state for the Quest Status screen.                 |
| `0x0A`   | `Menu_Exit`                | Exits the menu, restores the game state, and updates the equipped item. |
| `0x0C`   | `Menu_MagicBag`            | A sub-menu for viewing collectible items.                               |
| `0x0D`   | `Menu_SongMenu`            | A sub-menu for selecting Ocarina songs.                                 |
| `0x0E`   | `Menu_Journal`             | A sub-menu for reading the player's journal.                            |
| `0x09`   | `Menu_RingBox`             | A sub-menu for managing magic rings.                                    |

### 2.2. Item Selection Screen (Left Page)

This is the primary interactive screen where the player selects their Y-button item.

-   **Drawing (`DrawYItems`):** This routine is responsible for rendering all 24 item slots. It reads the SRAM address for each slot from `Menu_AddressIndex` (`menu_select_item.asm`), checks if the player owns the item, and then calls `DrawMenuItem`.
-   **`DrawMenuItem`:** This generic function is the core of the drawing system. It takes an item's SRAM value (e.g., Sword level 0-4) and uses it to look up the correct 16x16 tile data from a large graphics table in `Menu/menu_gfx_table.asm`. This makes the menu highly data-driven.
-   **Selection (`menu_select_item.asm`):** Cursor movement is handled by `Menu_FindNextItem`, `Menu_FindPrevItem`, etc. These routines intelligently skip over empty slots, ensuring the cursor always lands on a valid item. The currently selected slot index is stored in `$0202`.

### 2.3. Quest Status Screen (Right Page)

This screen is a static display of the player's overall progress.

-   **Drawing:** It is rendered by a series of functions in `menu_draw.asm`, including:
    -   `Menu_DrawQuestItems`: Draws equipped sword, shield, tunic, etc.
    -   `Menu_DrawPendantIcons` & `Menu_DrawTriforceIcons`: Reads SRAM flags to draw collected pendants and crystals.
    -   `Menu_DrawCharacterName`: Reads the player's name from SRAM and renders it.
    -   `DrawLocationName`: Reads the current overworld area (`$008A`) or underworld room (`$00A0`) and looks up the corresponding name from the tables in `menu_map_names.asm`.

## 3. HUD System Architecture

The HUD is a separate system that hooks the vanilla game's NMI rendering routines. Its main entry point is `HUD_Update` in `Menu/menu_hud.asm`.

-   **Functionality:** The `HUD_Update` routine runs every frame during gameplay. It reads player stats directly from SRAM and WRAM and draws them to the VRAM buffer for the top of the screen.
-   **Key Drawing Logic:**
    -   **Hearts:** `HUD_UpdateHearts` is a loop that draws empty hearts based on `MAXHP` (`$7EF36C`) and then overlays full/partial hearts based on `CURHP` (`$7EF36D`).
    -   **Magic Meter:** It reads `MagicPower` (`$7EF36E`) and uses the `MagicTilemap` lookup table to find the correct tiles to display the green bar.
    -   **Counters:** It uses a `HexToDecimal` routine to convert the values for Rupees, Bombs, and Arrows into drawable digits.
    -   **Equipped Item:** `HUD_UpdateItemBox` reads the currently equipped item index (`$0202`), finds its graphics data in the `HudItems` table, and draws the icon in the top-left box.

## 4. Data-Driven Design & Areas for Improvement

The entire menu and HUD are heavily data-driven, which is a major strength.

-   **Graphics:** All item icons for both the menu and HUD are defined in data tables in `menu_gfx_table.asm` and `menu_hud.asm`, not hardcoded.
-   **Item Layout:** The position and SRAM address of every item in the menu are defined in the `Menu_ItemCursorPositions` and `Menu_AddressIndex` tables, allowing the layout to be easily changed.
-   **Text:** Item names, location names, and other text are all stored in data tables in `menu_text.asm` and `menu_map_names.asm`.

This analysis confirms the suggestions in the placeholder `Menu.md` file:

1.  **Refactor Redundant Code:** The input handling logic for the Magic Bag, Song Menu, and Ring Box is nearly identical and is a prime candidate for being refactored into a single, reusable subroutine.
2.  **Use `table` for Jump Tables:** The main `Menu_Entry` jump table is created with manual `dw` directives and would be cleaner and safer if generated with asar's `table` directive.
3.  **Replace Hardcoded Values:** Hardcoded state values (e.g., `LDA.b #$0C : STA.w $0200`) should be replaced with named constants (`!MENU_STATE_MAGIC_BAG = $0C`) for readability and maintainability.