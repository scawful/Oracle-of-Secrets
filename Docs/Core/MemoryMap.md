# Memory Map

This document provides a detailed map of the WRAM and SRAM memory regions, serving as a central reference for understanding the game's state.

## 1. WRAM (Work RAM) - `$7E0000`

This section details the layout of the game's volatile memory.

### Key Vanilla WRAM Variables

*This section contains a table listing critical vanilla WRAM addresses, their labels (from `Core/ram.asm` and `Core/symbols.asm`), and their purpose.*

| Address  | Label      | Description                                       |
|----------|------------|---------------------------------------------------|
| `$7E0010` | `MODE`     | The main game state/module index.                 |
| `$7E0011` | `SUBMODE`  | The sub-state for the current game mode.          |
| `$7E001A` | `FRAME`    | A counter that increments each non-lagging frame. |
| `$7E001B` | `INDOORS`  | A flag indicating if Link is indoors (0x01) or outdoors (0x00). |
| `$7E002F` | `DIR`      | The direction Link is facing (0=U, 2=D, 4=L, 6=R). |
| `$7E005D` | `LINKDO`   | Link's personal state machine ID (walking, swimming, etc.). |
| `$7E008A` | `OWSCR`    | The current Overworld screen ID.                  |
| `$7E00A0` | `ROOM`     | The current Underworld room ID.                   |
| `$7E02E0` | `BUNNY`    | A flag indicating if Link is in his bunny form (0x01). |
| `$7E031F` | `IFRAMES`  | Link's invincibility frame timer after taking damage. |
| `$7E0DD0` | `SprState` | An array storing the state for each of the 16 sprites. |
| `$7E0E20` | `SprType`  | An array storing the ID for each of the 16 sprites. |
| `$7E0E50` | `SprHealth`| An array storing the health for each of the 16 sprites. |

### Custom WRAM Region - `$7E0730+`

*This section details the custom WRAM area defined in `Core/ram.asm` and `Core/symbols.asm`. It explains the purpose of each custom variable.*

| Address  | Label                  | Description                                                              |
|----------|------------------------|--------------------------------------------------------------------------|
| `$7E0730` | `MenuScrollLevelV`     | Vertical scroll position for the menu.                                   |
| `$7E0731` | `MenuScrollLevelH`     | Horizontal scroll position for the menu.                                 |
| `$7E0732` | `MenuScrollHDirection` | The direction of horizontal scrolling in the menu.                       |
| `$7E0734` | `MenuItemValueSpoof`   | Used to temporarily override the displayed value of a menu item.         |
| `$7E0736` | `ShortSpoof`           | A shorter version of the spoof value.                                    |
| `$7E0737` | `MusicNoteValue`       | The value of the current music note being played.                        |
| `$7E0739` | `GoldstarOrHookshot`   | Differentiates between the vanilla Hookshot and the custom Goldstar item.  |
| `$7E073A` | `Neck_Index`           | Used for multi-part sprites, like a centipede body.                      |
| `$7E0745` | `FishingOrPortalRod`   | Differentiates between the Fishing Rod and the Portal Rod.               |

---

## 2. SRAM (Save RAM) - `$7EF000`

This section details the layout of the save file memory.

### Key Vanilla SRAM Variables

*This section lists key vanilla save data locations, such as inventory, health, and progression flags, as defined in `Core/sram.asm`.*

| Address  | Label      | Description                               |
|----------|------------|-------------------------------------------|
| `$7EF340` | `Bow`      | The player's current bow type (0x00-0x04). |
| `$7EF343` | `Bombs`    | The number of bombs the player has.       |
| `$7EF359` | `Sword`    | The player's current sword type (0x00-0x04). |
| `$7EF35A` | `Shield`   | The player's current shield type (0x00-0x03). |
| `$7EF360` | `Rupees`   | The player's current rupee count.        |
| `$7EF36C` | `MAXHP`    | The player's maximum health (1 heart = 8 HP). |
| `$7EF36D` | `CURHP`    | The player's current health.             |
| `$7EF374` | `Pendants` | A bitfield for the collected pendants (Courage, Power, Wisdom). |
| `$7EF37A` | `Crystals` | A bitfield for the collected crystals from Dark World dungeons. |
| `$7EF3C5` | `GameState`| The main progression state of the game.   |

### Custom SRAM Region

*This is a critical section. It provides a comprehensive breakdown of all custom variables added to the SRAM, explaining what each flag or value represents. This information is primarily found in `Core/sram.asm`.*

| Address  | Label             | Description                                                              |
|----------|-------------------|--------------------------------------------------------------------------|
| `$7EF3D6` | `OOSPROG`         | A primary bitfield for major quest milestones unique to Oracle of Secrets. |
| `$7EF3C6` | `OOSPROG2`        | A secondary bitfield for less critical progression flags.                |
| `$7EF3D4` | `MakuTreeQuest`   | A flag indicating if the Maku Tree has met Link.                         |
| `$7EF3C7` | `MapIcon`         | Controls the position of the guiding 'X' on the world map.               |
| `$7EF351` | `CustomRods`      | A flag to differentiate between the Fishing Rod (1) and Portal Rod (2).    |
| `$7EF38A` | `FishingRod`      | Flag indicating if the player has the Fishing Rod.                       |
| `$7EF38B` | `Bananas`         | The number of bananas collected for a side-quest.                        |
| `$7EF391` | `Seashells`       | The number of secret seashells collected.                                |
| `$7EF398` | `Scrolls`         | A bitfield tracking which of the lore scrolls have been found.           |
| `$7EF39B` | `MagicBeanProg`   | Tracks the multi-day growth cycle of the magic bean side-quest.          |
| `$7EF39C` | `JournalState`    | The current state of the player's journal.                              |
| `$7EF39D` | `SRAM_StormsActive`| A flag indicating if the Song of Storms effect is active.                |
| `$7EF410` | `Dreams`          | A bitfield tracking the collection of the three "Dreams" (Courage, Power, Wisdom). |
| `$7EF347` | `ZoraMask`        | Flag indicating if the player has obtained the Zora Mask.                |
| `$7EF348` | `BunnyHood`       | Flag indicating if the player has obtained the Bunny Hood.               |
| `$7EF349` | `DekuMask`        | Flag indicating if the player has obtained the Deku Mask.                |
| `$7EF34D` | `RocsFeather`     | Flag indicating if the player has obtained Roc's Feather.                 |
| `$7EF352` | `StoneMask`       | Flag indicating if the player has obtained the Stone Mask.               |
| `$7EF358` | `WolfMask`        | Flag indicating if the player has obtained the Wolf Mask.                |

## 3. Custom Code and Data Layout (ROM Banks)

This section details the allocation of custom code and data within the ROM banks, as defined by `org` directives in the project's assembly files. The order of `incsrc` directives in `Oracle_main.asm` is crucial for the final ROM layout.

| Bank (Hex) | Address Range (PC)    | Purpose / Contents                                     |
|------------|-----------------------|--------------------------------------------------------|
| $20        | `$208000` - `$20FFFF` | Expanded Music                                         |
| $21-$27    |                       | ZScream Reserved                                       |
| $28        | `$288000` - `$28FFFF` | ZSCustomOverworld data and code                        |
| $29-$2A    |                       | ZScream Reserved                                       |
| $2B        | `$2B8000` - `$2BFFFF` | Items                                                  |
| $2C        | `$2C8000` - `$2CFFFF` | Underworld/Dungeons                                    |
| $2D        | `$2D8000` - `$2DFFFF` | Menu                                                   |
| $2E        | `$2E8000` - `$2EFFFF` | HUD                                                    |
| $2F        | `$2F8000` - `$2FFFFF` | Expanded Message Bank                                  |
| $30        | `$308000` - `$30FFFF` | Sprites                                                |
| $31        | `$318000` - `$31FFFF` | Sprites                                                |
| $32        | `$328000` - `$32FFFF` | Sprites                                                |
| $33        | `$338000` - `$33FFFF` | Moosh Form Gfx and Palette                             |
| $34        | `$348000` - `$34FFFF` | Time System, Custom Overworld Overlays, Gfx            |
| $35        | `$358000` - `$35FFFF` | Deku Link Gfx and Palette                              |
| $36        | `$368000` - `$36FFFF` | Zora Link Gfx and Palette                              |
| $37        | `$378000` - `$37FFFF` | Bunny Link Gfx and Palette                             |
| $38        | `$388000` - `$38FFFF` | Wolf Link Gfx and Palette                              |
| $39        | `$398000` - `$39FFFF` | Minish Link Gfx                                        |
| $3A        | `$3A8000` - `$3AFFFF` | Mask Routines, Custom Ancillae (Deku Bubble)           |
| $3B        | `$3B8000` - `$3BFFFF` | GBC Link Gfx                                           |
| $3C        |                       | Unused                                                 |
| $3D        |                       | ZS Tile16                                              |
| $3E        |                       | LW ZS Tile32                                           |
| $3F        |                       | DW ZS Tile32                                           |
| $40        | `$408000` - `$40FFFF` | LW World Map                                           |
| $41        | `$418000` - `$41FFFF` | DW World Map                                           |
| Patches    | Various               | Targeted modifications within vanilla ROM addresses    | `Core/patches.asm`, `Util/item_cheat.asm` |