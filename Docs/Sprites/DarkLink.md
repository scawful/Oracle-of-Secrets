# Dark Link Sprite Analysis

## Overview
Dark Link (Sprite ID: `$C1`) is a boss sprite known for its dynamic and challenging combat. It features a variety of attacks, including sword slashes, jump attacks, and projectile spawning. A notable aspect of this sprite is its ability to transform into a Ganon-like entity via a subtype, suggesting a multi-phase boss encounter.

## Key Properties:
*   **Sprite ID:** `$C1`
*   **Number of Tiles:** 4
*   **Health:** 34 (decimal)
*   **Damage:** 0 (Damage is handled by spawned attacks or direct contact logic, not directly by the sprite's `!Damage` property.)
*   **Special Properties:**
    *   `!DeflectProjectiles = 01` (Deflects all projectiles)
    *   `!ImperviousArrow = 01` (Impervious to arrows)
    *   `!Boss = 00` (Despite being a boss, this flag is not set, indicating custom boss logic rather than reliance on vanilla boss flags.)

## Subtypes:
*   **Subtype `$05` (Ganon):** This subtype completely alters Dark Link's behavior to that of a Ganon boss, executing `Sprite_Ganon_Main` and `Sprite_Ganon_Draw`. This mechanism allows for a multi-stage boss fight or an entirely different boss using the same sprite slot.
*   **Subtype `$01` (Sword Damage):** This subtype is used for a temporary sprite spawned during Dark Link's sword attacks to handle collision and damage detection.

## In-Game Behavior:
Dark Link is an active and engaging boss. It moves strategically towards Link, performs various sword attacks (including a jump attack with screen shake), can utilize a cape for evasion, and throws bombs. It reacts to damage with visual recoil and flashing, and enters an "enraging" state (indicated by a red palette change) which likely alters its attack patterns or aggression. The Ganon subtype suggests a significant shift in combat during the fight.

## Original Sprite Replaced:
The code does not explicitly state which vanilla sprite `dark_link` replaces. However, the integration of `GanonInit` and Ganon-related logic strongly suggests it either heavily modifies an existing Ganon boss fight or is a completely new boss utilizing a custom sprite ID.

## Development Goals for Oracle of Secrets:
*   **Variety in Attacks:** Introduce more diverse attack patterns and abilities to enhance the fight's complexity and challenge.
*   **Unique Oracle of Secrets Attacks:** Implement attacks that are thematic and unique to the Oracle of Secrets project, moving beyond standard ALTTP boss mechanics.

## Code Quality Notes:
The code, while functional and effective in creating a competent boss, is noted to be somewhat "messy" due to its origin from Zarby89's ZScream project. This implies that while it works, future modifications might require careful navigation through its structure.
