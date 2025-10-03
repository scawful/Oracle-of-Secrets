# Overlord Sprite System Analysis

This document provides a comprehensive analysis of the "Overlord" sprite system, a special class of sprite used for room-level event scripting and control.

## 1. What is an Overlord?

An Overlord is an invisible, non-interactive sprite placed in a room via a level editor. Unlike normal sprites (enemies, NPCs), their purpose is not to interact directly with Link, but to execute logic in the background. They function as "room controllers" or "event triggers."

Common uses for Overlords include:
- Spawning other sprites under specific conditions.
- Modifying the environment (e.g., creating falling tiles, moving floors).
- Coordinating the behavior of multiple other sprites.
- Setting up room-specific traps or puzzles.

In `Oracle of Secrets`, the most prominent example is `Overlord04`, which is used to continuously spawn soldier sprites in Hyrule Castle after Link acquires the Master Sword, creating a sense of alarm.

## 2. How Overlords Work: The Engine Loop

The core logic for the Overlord system resides in **Bank $09** of the vanilla ROM.

1.  **Main Entry Point:** The standard sprite processing loop (`bank_06`) calls `JSL Overlord_Main` (at `$068398`), which jumps to the main overlord handler at **`$09B770`**.

2.  **Execution Loop (`Overlord_ExecuteAll`):** At `$09B781`, the routine `Overlord_ExecuteAll` begins. It loops five times, once for each of the five available overlord "slots" in RAM. In each iteration, it calls `Overlord_ExecuteSingle`.

3.  **Single Overlord Execution (`Overlord_ExecuteSingle`):** This routine, starting at `$09B791`, is the heart of the system. For a given overlord slot, it performs these steps:
    a. It calls `Overlord_CheckIfActive` (`$09C08A`) to see if the slot contains an active overlord.
    b. It reads the **Overlord Type** from WRAM address `$0F90,X` (where X is the overlord slot 0-4).
    c. It uses this Type ID as an index into a jump table located at **`$09B7A8`**.
    d. It executes the routine pointed to by the jump table entry, running the specific logic for that overlord type.

## 3. Overlord Jump Table

The jump table at `$09B7A8` is the key to customizing overlords. It contains pointers to the code for each of the 26 (1A) possible overlord types.

| Address | Vanilla Label | Oracle of Secrets Usage |
|---|---|---|
| `$09B7A8` | `Overlord01_PositionTarget` | Unused |
| `$09B7AA` | `Overlord02_FullRoomCannons` | Unused |
| `$09B7AC` | `Overlord03_VerticalCannon` | Unused |
| **`$09B7AE`** | `Overlord04_Unused` | **Hooked for `Overlord_KalyxoCastleGuards`** |
| `$09B7B0` | `Overlord05_FallingStalfos` | Unused |
| ... | ... | ... |

`Oracle of Secrets` replaces the pointer at `$09B7AE` to point to its own custom logic for the castle guard spawner.

## 4. Overlord RAM Data Structure

Each of the five active overlords has its data stored in a series of arrays in WRAM, indexed by the overlord slot (0-4).

| Address | Description |
|---|---|
| `$0F90,X` | **Overlord Type:** The ID (1-26) that determines which logic to run via the jump table.
| `$0FA0,X` | **Overlord State/Action:** The current state of the overlord's internal state machine, similar to `SprAction` for normal sprites.
| `$0FB0,X` | **Overlord Timer A:** A general-purpose timer.
| `$0FC0,X` | **Overlord Timer B:** A second general-purpose timer.
| `$0FD0,X` | **Overlord Timer C:** A third general-purpose timer.
| `$0B08,X` | X-Coordinate (and other properties, loaded from room data).
| `$0B10,X` | Y-Coordinate (and other properties, loaded from room data).

When a room is loaded, the `Underworld_LoadSingleOverlord` (`$09C35A`) or `Overworld_LoadSingleOverlord` (`$09C779`) routines read the overlord data defined in the level editor and populate these WRAM slots.

## 5. Creating a Custom Overlord

To create your own custom overlord, follow these steps:

1.  **Choose an Overlord Slot:** Find an unused overlord type in the jump table at `$09B7A8`. `Overlord04` is already taken, but others may be available. For this example, let's assume you choose to replace `Overlord05_FallingStalfos` at `$09B7B0`.

2.  **Write Your Logic:** Create a new `.asm` file (e.g., `Sprites/Overlords/my_custom_overlord.asm`) or add to the existing `Sprites/overlord.asm`. Your code should define the main routine for your overlord.

    ```asm
    ; In my_custom_overlord.asm
    MyCustomOverlord_Main:
    {
      ; Your logic here.
      ; You can use the Overlord Timers and State registers.
      ; For example, let's use the state register to create a simple two-state machine.
      LDA.w $0FA0,X  ; Load the current state
      JSL JumpTableLocal

      dw .State0_Wait
      dw .State1_DoSomething

    .State0_Wait
      ; Decrement Timer A. When it hits zero, switch to state 1.
      LDA.w $0FB0,X : BNE .keep_waiting
        INC.w $0FA0,X ; Go to state 1
        LDA.b #$80 : STA.w $0FB0,X ; Reset timer
      .keep_waiting
      RTS

    .State1_DoSomething
      ; Do something, like spawn a sprite.
      ; Then go back to state 0.
      LDA.b #<Sprite_ID>
      JSL Sprite_SpawnDynamically
      STZ.w $0FA0,X ; Go back to state 0
      RTS
    }
    ```

3.  **Hook into the Jump Table:** In a file that is included in your main build file (like `Core/patches.asm`), add an `org` directive to overwrite the vanilla pointer in the jump table.

    ```asm
    ; In Core/patches.asm
    incsrc ../Sprites/Overlords/my_custom_overlord.asm

    pushpc
    org $09B7B0 ; Address for Overlord05
    dw MyCustomOverlord_Main ; Replace pointer with your routine
    pullpc
    ```

4.  **Place in a Room:** Use your level editor to place an "Overlord" object in a room. Set its **Type** to the one you chose (e.g., `05`). When the room is loaded, the game will load your overlord into an active slot, and the main loop will execute your custom code.
