# Mask System

This document provides a detailed analysis of the Mask System in Oracle of Secrets, based on the code in the `Masks/` directory. The system allows Link to transform into various forms, each with unique graphics, palettes, and abilities.

## 1. System Architecture

The Mask System is built around a central WRAM variable and a set of core routines that handle transformations, graphics, and palettes.

-   **`!CurrentMask` (`$02B2`):** A WRAM variable that stores the ID of the currently active mask. A value of `0x00` represents Link's normal human form.
-   **`!LinkGraphics` (`$BC`):** A WRAM variable that holds the bank number for Link's current graphics sheet. The Mask System changes this value to load the appropriate sprite graphics for each form.

### Mask IDs

| ID   | Mask / Form   |
|------|---------------|
| `00` | Human (Default) |
| `01` | Deku Mask     |
| `02` | Zora Mask     |
| `03` | Wolf Mask     |
| `04` | Bunny Hood    |
| `05` | Minish Form   |
| `06` | GBC Form      |
| `07` | Moosh Form    |

## 2. Core Routines & Hooks (`Masks/mask_routines.asm`)

A set of shared routines and hooks form the backbone of the system.

-   **`Link_TransformMask`:** This is the primary function for changing forms. It is typically called when the player uses a mask item.
    -   **Trigger:** It requires a new R-button press (`CheckNewRButtonPress`) to prevent rapid toggling.
    -   **Logic:** It takes a mask ID in the A register. If the requested mask is already active, it reverts Link to his human form. Otherwise, it sets `!CurrentMask`, updates the graphics bank in `$BC` from a lookup table, and calls `Palette_ArmorAndGloves` to apply the new look.
    -   **Effect:** It spawns a "poof" of smoke (`AddTransformationCloud`) and plays a sound effect.

-   **`Palette_ArmorAndGloves` (Hook):** This routine hooks the vanilla palette loading function (`$1BEDF9`). It checks `!CurrentMask` and jumps to the appropriate `Update...Palette` routine for the active form, ensuring the correct colors are loaded. If no mask is active, it proceeds with the vanilla logic for loading Link's tunic color.

-   **`LinkItem_CheckForSwordSwing_Masks` (Hook):** This routine hooks the vanilla sword swing check (`$079CD9`). It prevents certain forms (Deku, Wolf, Minish, Moosh) from using the sword, while allowing others (Zora, GBC Link) to use it freely.

-   **Reset Routines:**
    -   `ResetToLinkGraphics`: Reverts Link to his default graphics and `!CurrentMask = 0`.
    -   `ForceResetMask_GameOver` / `ForceResetMask_SaveAndQuit`: Hooks into the game over and save/quit routines to ensure Link's form is reset before the game saves or restarts.

## 3. Transformation Masks

These masks grant Link new forms with significant new abilities.

### Deku Mask

-   **File:** `Masks/deku_mask.asm`
-   **Transformation:** Replaces the Quake Medallion. Pressing 'Y' with the item selected transforms Link.
-   **Abilities:**
    -   **Spin Attack:** Pressing 'Y' performs a spinning attack.
    -   **Deku Bubble:** If not on a Deku Flower, the spin attack also shoots a bubble projectile (`Ancilla0E_MagicBubble`).
    -   **Hover:** If standing on a Deku Flower (tile property check sets WRAM `$71`), the spin attack launches Link into the air, allowing him to hover for a short time.
    -   **Bomb Drop:** While hovering, pressing 'Y' drops a bomb.
    -   **Cancel Hover:** Pressing 'B' or letting the timer expire cancels the hover.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x01`
    -   `DekuFloating` (`$70`): Flag set when Link is hovering.
    -   `DekuHover` (`$71`): Flag set when Link is standing on a Deku Flower, enabling the hover ability.
-   **Code Interactions:**
    -   Hooks `LinkItem_Quake` (`$07A64B`).
    -   Repurposes Link's "Using Quake Medallion" state (`$5D = 0x0A`) for the hover ability.
    -   Hooks `LinkOAM_DrawShield` (`$0DA780`) to prevent the shield from being drawn.

### Zora Mask

-   **File:** `Masks/zora_mask.asm`
-   **Transformation:** Replaces the Bombos Medallion. Pressing 'Y' with the item selected transforms Link.
-   **Abilities:**
    -   **Diving:** Allows Link to dive in deep water by pressing 'Y'. Pressing 'Y' again resurfaces.
    -   **Overworld Diving:** When diving in the overworld, Link becomes invincible, moves faster, and is hidden beneath a ripple effect.
    -   **Dungeon Diving:** When diving in a dungeon, Link moves to the lower layer (`$EE=0`), allowing him to swim under floors and obstacles.
    -   **Sword:** The Zora form can use the sword.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x02`
    -   `!ZoraDiving` (`$0AAB`): Flag set when Link is currently underwater.
-   **Code Interactions:**
    -   Hooks `LinkItem_Bombos` (`$07A569`).
    -   Hooks the end of `LinkState_Swimming` (`$079781`) to handle the dive input.
    -   Hooks the end of `LinkState_Default` (`$0782D2`) to handle resurfacing in dungeons.
    -   Hooks `Link_HopInOrOutOfWater_Vertical` (`$07C307`) to reset the dive state when using water stairs.

### Wolf Mask

-   **File:** `Masks/wolf_mask.asm`
-   **Transformation:** Shares an item slot with the Flute. When selected, it replaces the Shovel. Pressing 'Y' transforms Link.
-   **Abilities:**
    -   **Dig:** When transformed, pressing 'Y' executes the vanilla `LinkItem_Shovel` routine, allowing Wolf Link to dig for items without needing the shovel.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x03`
-   **Code Interactions:**
    -   Hooks the `LinkItem_Shovel` vector (`$07A313`) to a new `LinkItem_ShovelAndFlute` routine that dispatches between the Flute and Wolf Mask logic based on the selected item (`$0202`).

### Minish Form

-   **File:** `Masks/minish_form.asm`
-   **Transformation:** Context-sensitive. When standing on a special portal tile (`ID 64`), pressing 'R' transforms Link into Minish form. Pressing 'R' on the portal again reverts him.
-   **Abilities:**
    -   **Access Minish Areas:** Allows Link to pass through special small openings (`Tile ID 65`).
    -   **Restricted Actions:** Cannot lift objects.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x05`
-   **Code Interactions:**
    -   Hooks the overworld (`$07DAF2`) and underworld (`$07D8A0`) tile collision tables to add handlers for the portal and passage tiles.
    -   Hooks the lift check (`$079C32`) to disable lifting while in Minish form.

### Moosh Form

-   **File:** `Masks/moosh.asm`
-   **Transformation:** The trigger for transforming into Moosh is not defined within the mask's own file, but is handled by `Link_TransformMoosh`.
-   **Abilities:**
    -   **Hover Dash:** Attempting to use the Pegasus Boots (dash) while in Moosh form will instead trigger a short hover, similar to the Deku Mask's ability.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x07`
-   **Code Interactions:**
    -   Hooks the dash initiation logic (`$079093`) to intercept the dash and call `PrepareQuakeSpell`, which sets Link's state to `0x0A` (hover).
    -   Shares the hover/recoil animation logic with the Deku Mask.

## 4. Passive & Cosmetic Forms

### Bunny Hood

-   **File:** `Masks/bunny_hood.asm`
-   **Transformation:** Replaces the Ether Medallion. Pressing 'Y' activates the Bunny Hood state. This is a state change, not a visual transformation.
-   **Abilities:**
    -   **Increased Speed:** While the Bunny Hood is the active mask (`!CurrentMask = 0x04`), Link's movement speed is increased across various actions (walking, carrying, etc.). The specific speed values are defined in `BunnySpeedTable`.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x04`
-   **Code Interactions:**
    -   Hooks `LinkItem_Ether` (`$07A494`) to trigger the state change.
    -   Hooks the velocity calculation in the player engine (`$07E330`) to load custom speed values from a table.

### GBC Form

-   **File:** `Masks/gbc_form.asm`
-   **Transformation:** An automatic, cosmetic transformation that occurs whenever Link is in the Dark World.
-   **Abilities:**
    -   Changes Link's graphics to a Game Boy Color-inspired sprite.
    -   Applies a unique, limited-color palette. The palette correctly reflects Link's current tunic (Green, Blue, or Red).
    -   This form can still use the sword.
-   **Key Flags & Variables:**
    -   `!CurrentMask`: `0x06`
    -   `$0FFF`: The vanilla Dark World flag.
-   **Code Interactions:**
    -   Hooks numerous overworld, underworld, and transition routines to consistently apply the effect when in the Dark World and remove it when in the Light World.
