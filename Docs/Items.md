# Custom Items System

This document details the functionality of new and modified items in Oracle of Secrets, based on analysis of the `Items/` directory.

## 1. Overview

The item roster has been significantly expanded with new mechanics, and many vanilla items have been reworked to provide new functionality. The system is managed through a combination of hooks into the main player state machine and custom routines for each item.

## 2. Vanilla Item Modifications

Several items from the original game have been altered.

### Hookshot / Goldstar

-   **Files:** `goldstar.asm`
-   **Functionality:** The Hookshot can be upgraded to the **Goldstar**, a powerful morning star weapon. The two items share an inventory slot.
-   **Switching:** When the Goldstar is obtained, the player can switch between the Hookshot and Goldstar by pressing the L/R shoulder buttons while it is selected in the menu. The current mode is tracked by the `GoldstarOrHookshot` WRAM variable.
-   **Goldstar Mechanics:** When active, the item functions as a short-range, powerful melee weapon with its own collision and damage properties, distinct from the Hookshot's grappling mechanic.

### Ice Rod

-   **File:** `ice_rod.asm`
-   **Functionality:** The Ice Rod's projectile now freezes water tiles it hits, creating temporary 16x16 ice platforms. This allows the player to cross water gaps.
-   **Implementation:** The `LinkItem_IceRod` routine hooks into the ancilla tile collision logic. When the projectile hits a water tile, it dynamically modifies the tilemap properties in RAM and DMAs new ice graphics to VRAM.

### Bug-Catching Net -> Roc's Feather

-   **File:** `jump_feather.asm`
-   **Functionality:** The vanilla Bug-Catching Net has been completely replaced by **Roc's Feather**. This item allows Link to perform a short hop.
-   **Implementation:** `LinkItem_JumpFeather` initiates the jump by setting Link's state to a recoil/ledge hop state and applying a burst of vertical velocity.

### Bottles

-   **File:** `bottle_net.asm`
-   **Functionality:** The Bug-Catching Net is no longer required to catch bees, fairies, etc. The Bottle item now has a dual function:
    1.  If the bottle is **empty**, using it initiates the `LinkItem_CatchBottle` routine, which performs a net-catching swing.
    2.  If the bottle is **full**, using it calls `LinkItem_Bottles`, which consumes the contents (e.g., drinks a potion, releases a fairy).

### Book of Mudora -> Book of Secrets

-   **File:** `book_of_secrets.asm`
-   **Functionality:** The Book of Mudora is now the **Book of Secrets**. While its vanilla function of translating Hylian text remains, it has a new secret-revealing capability.
-   **Implementation:** The `Dungeon_RevealSecrets` routine checks if the L button is held while inside a building. If it is, it disables the `BG2` layer, which can be used to hide secret passages or objects behind walls that are part of that background layer.

## 3. New Active Items

### Ocarina

-   **File:** `ocarina.asm`
-   **Functionality:** A multi-song instrument. When selected, the player can cycle through learned songs using the L/R shoulder buttons. Pressing 'Y' plays the selected song, triggering its unique effect.
-   **Songs & Effects:**
    -   **Song of Healing:** Heals certain NPCs or triggers quest events.
    -   **Song of Storms:** Toggles a rain overlay on the overworld, which can affect the environment (e.g., watering the Magic Bean).
    -   **Song of Soaring:** Warps the player to pre-defined locations (the vanilla flute's bird travel).
    -   **Song of Time:** Toggles the in-game time between day and night.

### Shared Slot: Portal Rod & Fishing Rod

-   **Files:** `portal_rod.asm`, `fishing_rod.asm`
-   **Functionality:** These two distinct items share a single inventory slot. If the player has the upgrade (`$7EF351 >= 2`), they can swap between the two by pressing L/R in the menu.
-   **Portal Rod:** Fires a projectile that creates a portal sprite (blue or orange). The `Ancilla_HandlePortalCollision` logic detects when another projectile (like an arrow) hits a portal and teleports it to the other portal's location.
-   **Fishing Rod:** Initiates a fishing minigame. `LinkItem_FishingRod` spawns a "floater" sprite, and the player can reel it in to catch fish or other items from a prize table.

## 4. New Passive Items

### Magic Rings

-   **File:** `magic_rings.asm`
-   **Functionality:** Passive items that grant buffs when equipped in one of the three ring slots in the Quest Status menu. The effects are applied by hooking into various game logic routines.
-   **Implemented Rings:**
    -   **Power Ring:** Increases sword damage.
    -   **Armor Ring:** Reduces damage taken by half.
    -   **Heart Ring:** Slowly regenerates health over time.
    -   **Light Ring:** Allows the sword to shoot beams even when Link is not at full health (down to -2 hearts from max).
    -   **Blast Ring:** Increases the damage of bombs.
    -   **Steadfast Ring:** Prevents or reduces knockback from enemy hits.

## 5. Consumable Items (Magic Bag)

-   **File:** `all_items.asm`
-   **Functionality:** The Magic Bag is a sub-menu that holds new consumable items. The `Link_ConsumeMagicBagItem` routine is a jump table that executes the effect for the selected item.
-   **Consumables:**
    -   **Banana:** Implemented. Restores a small amount of health (`#$10`).
    -   **Pineapple, Rock Meat, Seashells, Honeycombs, Deku Sticks:** Placeholder entries exist in the jump table, but their effects are not yet implemented (the routines just contain `RTS`).
