# Oracle of Secrets & z3dk Architecture Maps

This document contains conceptual diagrams of the project architecture and the `z3dk` toolchain workflow. Use these as a reference for understanding system dependencies and memory management.

---

## 1. z3dk "Safety Net" Workflow
*How the tools interact to prevent ROM corruption and crashes.*

```text
       YOUR WORKSTATION                        THE VALIDATION LOOP
   +----------------------+                 +-----------------------+
   |                      |                 |                       |
   |   VS Code / Neovim   | <-------------> |      z3lsp (IDE)      |
   |  (The Text Editor)   |    (Intellisense|   (The Smart Brain)   |
   |                      |     & Hover)    |                       |
   +----------+-----------+                 +-----------+-----------+
              |                                         ^
              | (Save File)                             | (Reads Config)
              v                                         |
   +----------+-----------+                 +-----------+-----------+
              |                                         |
              |     Source Code      | <-------------- |       z3dk.toml       |
              |  (HOOK directives)   |                 |    (Project Config)   |
              |                      |                 |                       |
              +----------+-----------+                 +-----------------------+
              |
              | (Run Build)
              v
   +----------+-----------+                 +-----------------------+
   |                      |  Generates      |                       |
   |        z3asm         | --------------> |      hooks.json       |
   |     (Assembler)      |                 |    (The Manifest)     |
   |                      |                 |                       |
   +----+-----+-----------+                 +-----------+-----------+
        |     |                                         |
        |     | Generates                               | (Reads)
        |     v                                         v
        |  +--------------+                 +-----------+-----------+
        |  | symbols.mlb  |                 |                       |
        |  | (Debug Info) |                 |    Static Analyzer    |
        |  +------+-------+                 |   (The Safety Check)  |
        |         |                         |                       |
        v         v                         +-----------+-----------+
   +----+---------+-------+                             |
   |                      |                             | (Verifies)
   |     Mesen2 (Emu)     | <---------------------------+
   |                      |      "Did you break the registers?"
   +----------------------+           (Pass / Fail)
```

---

## 2. Oracle of Secrets: Module Organization
*How the code is organized into modules and namespaces.*

```text
          THE BRAIN                                THE BODY (Modules)
   +---------------------+                  +---------------------------+
   |                     | include          |                           |
   |   Oracle_main.asm   | <---------------+   Config/module_flags.asm  |
   |                     |                  |   (Toggle Features On/Off)|
   |  - Memory Banking   |                  |                           |
   |  - Global Constants |                  +-------------+-------------+
   |  - Namespaces       |                                |
   |                     |                  +-------------+-------------+
   +----------+----------+                  |                           |
              ^                             |   Modules/Masks/          |
              | include                     |   (Banks $33-$3B)         |
              |                             |                           |
   +----------+----------+                  +-------------+-------------+
   |                     |                                |
   |  ZSCustomOverworld  |                  +-------------+-------------+
   |  (Global Namespace) |                  |                           |
   |                     |                  |   Modules/Dungeons/       |
   | - World Layout      |                  |   (Level Data)            |
   | - Map Logic         |                  |                           |
   +---------------------+                  +-------------+-------------+
                                                          |
                                            +-------------+-------------+
                                            |                           |
                                            |   Modules/Music/          |
                                            |   (MSU-1 & SPC)           |
                                            |                           |
                                            +---------------------------+
```

---

## 3. Memory Map & Banking Strategy
*Where things live in the SNES memory space (LoROM).*

```text
  SNES MEMORY MAP (LoROM Layout)
  +-----------------------------------------+
  | BANK $00 - $1F (Vanilla Code/Data)      |
  |  - $00-$0F: Core Logic (Hooked by z3asm)|
  |  - $10-$1F: Vanilla Graphics/Data       |
  +-----------------------------------------+
  | BANK $20 - $2F (Expanded Systems)       |
  |  $20: Music (MSU-1 / SPC Data)          |
  |  $21-$27: [RESERVED]                    |
  |  $28: ZSCustomOverworld (The Tables)    | <--- HUGE TABLE LOOKUPS
  |  $2B: Items (New Hookshots, etc.)       |
  |  $2C: Dungeons (Level Data)             |
  |  $2D: Menu & HUD                        |
  |  $2F: Expanded Dialog (Messages)        |
  +-----------------------------------------+
  | BANK $30 - $3F (Graphics & Forms)       |
  |  $30-$32: Sprite Data                   |
  |  $33: Moosh Form                        |
  |  $35: Deku Form                         |
  |  $36: Zora Form                         |
  |  $37: Bunny Form                        |
  |  $38: Wolf Form                         |
  |  $39: Minish Form                       |
  |  $3A: Mask Logic (State Machine)        | <--- THE BRAIN
  |  $3B: GBC Form                          |
  +-----------------------------------------+
  | BANK $40+ (Overworld Maps)              |
  |  $40: Light World Tilemaps              |
  |  $41: Dark World Tilemaps               |
  +-----------------------------------------+
```

---

## 4. The Mask Transformation System
*The logic behind Link changing forms via state swaps and DMA.*

```text
      THE TRANSFORMATION PIPELINE
      (Triggered by Button/Menu)

            [ INPUT ]
                |
                v
      +---------------------+
      | Bank $3A: Logic     |
      | "Check Requirements"| (Do we have the mask? Magic?)
      +---------+-----------+
                |
                v
      +---------------------+      +------------------------+
      | State Machine ($02B2)| ---> | Memory Bank Swap       |
      | ID: 00 -> 02 (Zora) |      | (!LinkGraphics = $BC)  |
      +---------+-----------+      +-----------+------------+
                |                              |
                v                              v
      +---------+-----------+      +------------------------+
      | Hook: Player Logic  |      | DMA Transfer (Bank $36)|
      | ($078028 DoSFX)     |      | Load "zora_link.4bpp"  |
      | ($09912C Cloud)     |      | into VRAM              |
      +---------------------+      +------------------------+
                |
                v
      +---------------------+
      |   NEW ABILITIES     |
      | (!ZoraDiving = 1)   |
      | (Swim Logic Active) |
      +---------------------+
```

---

## 5. The "Data-Driven" Overworld
*Replacing hardcoded branch logic with ZSCustomOverworld table lookups.*

```text
       VANILLA ALTTP OVERWORLD                ZSCREAM CUSTOM OVERWORLD
      +-----------------------+              +------------------------+
      |                       |              |                        |
      |  "If Area == 0x03"    |   REPLACED   |  Lookup Table (Bank $28)|
      |     Load Rain();      |      BY      |  Address: $288340      |
      |  "If Area == 0x5B"    |  --------->  |                        |
      |     Load Pyramid();   |              |  Index | Overlay ID    |
      |                       |              |  --------------------  |
      +-----------------------+              |  $03   | $009D (Fog)   |
                                             |  $5B   | $0096 (Pyr)   |
      (Slow, Fragile, Hardcoded)             |  $70   | $00FF (None)  |
                                             |                        |
                                             +-----------+------------+
                                                         |
                                                         v
                                              +-----------------------+
                                              |   Generic Loader      |
                                              | "Read ID -> Load GFX" |
                                              +-----------------------+
                                              (Fast, Flexible, Safe)
```
