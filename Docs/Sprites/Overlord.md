# Overlord Sprite Analysis

This document provides an analysis of the "Overlord" sprite system, which is a special type of sprite that acts as a controller for spawning other sprites or triggering events within a room. The main logic is found in `Sprites/overlord.asm`.

## Overview

Overlord sprites are invisible, non-interactive sprites that are placed in a room via a level editor. Their purpose is to run logic in the background, often tied to room-specific events or conditions. They are distinct from standard sprites and are processed by a separate loop.

In this project, the primary use of the Overlord system is to dynamically spawn soldiers in Hyrule Castle after the player acquires the Master Sword.

## `overlord.asm` Analysis

- **File:** `Sprites/overlord.asm`
- **Summary:** This file contains the logic for `Overlord04`, which is hooked into the game at `$09B7AE`. This specific overlord is responsible for continuously spawning soldiers in Hyrule Castle to create a sense of alarm and danger.

### Key Logic

- **`Overlord_KalyxoCastleGuards`:** This is the main entry point for the overlord's logic. It is a simple routine that calls `SummonGuards`.

- **`SummonGuards`:**
    - **Trigger Condition:** This routine first checks if Link has the Master Sword (`LDA.l Sword : CMP.b #$02`). It will only proceed if the sword level is 2 or greater.
    - **Spawning Logic:** If the condition is met, it calls `Overlord_SpawnSoldierPath`.

- **`Overlord_SpawnSoldierPath`:**
    - **Spawn Timer:** This routine uses `OverlordTimerB` as a countdown timer to manage the rate of spawning. It will not spawn a new soldier until the timer reaches zero.
    - **Sprite Limit:** It checks the number of active soldiers (`Sprite Type $41`) on screen. If there are already 5 or more, it will not spawn a new one.
    - **Spawning:** If the conditions are met, it calls `Sprite_SpawnDynamically_slot_limited` to create a new Blue Soldier (`$41`).
    - **Positioning:** The new soldier's position and initial direction are determined by data tables within the routine (`soldier_position_x`, `soldier_position_y`, `soldier_direction`), allowing for multiple spawn points.
