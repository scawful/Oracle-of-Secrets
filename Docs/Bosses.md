# Bosses Analysis

This document provides an analysis of the boss sprites found in the `Sprites/Bosses/` directory. These sprites are typically complex, with multiple phases and unique behaviors.

## File Overview

| Filename | Sprite ID(s) | Description |
|---|---|---|
| `arrghus.asm` | (Hooks `$1EB593`) | A custom version of Arrghus that spawns fireballs. |
| `dark_link.asm` | `Sprite_DarkLink` (`$C1`) | A multi-phase boss fight against a shadow version of Link. |
| `king_dodongo.asm`| (Hooks `$1E811A`) | A custom version of King Dodongo with a new health system. |
| `kydreeok.asm` | `Sprite_Kydreeok` | A multi-headed sea monster boss. Parent sprite for `kydreeok_head.asm`. |
| `kydreeok_head.asm`| `Sprite_KydreeokHead` | The individual head of the Kydreeok boss, which can be attacked. |
| `kydrog.asm` | `Sprite_KydrogNPC` | A cutscene version of Kydrog that appears before the boss fight. |
| `kydrog_boss.asm` | `Sprite_KydrogBoss` | The main Kydrog boss fight, a large amphibious creature. |
| `lanmola.asm` | (Hooks `$05A377`) | A custom version of the Lanmola boss. |
| `lanmola_expanded.asm`| (Expansion) | Contains additional data and drawing logic for the custom Lanmola. |
| `manhandla.asm` | `Sprite_Manhandla` | A two-phase boss fight against Manhandla, which later becomes a Big Chuchu. |
| `octoboss.asm` | (Hooks `Sprite_A2_Kholdstare`) | A custom boss fight against two octopuses, replacing Kholdstare. |
| `twinrova.asm` | `Sprite_Twinrova` (`$CE`) | A custom boss fight replacing Blind the Thief with the twin witches, Koume and Kotake. |
| `vampire_bat.asm` | (Subtype of Keese) | A vampire bat mini-boss. |
| `wolfos.asm` | `Sprite_Wolfos` | A Wolfos mini-boss that guards the Wolf Mask. |

## Detailed Boss Analysis

### `dark_link.asm`
- **Sprite ID:** `Sprite_DarkLink` (`$C1`)
- **Summary:** A complex, multi-action boss that mimics Link's abilities. The fight has multiple stages, including a Ganon-like form.
- **Key Logic:**
    - The main routine is a large state machine driven by `SprAction, X`.
    - **Actions:** Includes standard walking, sword slashes, jump attacks, dodging, and using items like bombs and the Magic Cape.
    - **AI:** The AI in the `Handler` routine decides which action to take based on the distance to the player. It can choose to slash, dodge, or use a special attack.
    - **Enrage Mechanic:** At a certain health threshold (`SprHealth < $20`), the boss can enter an "enraged" state (`Enraging` action), which refills its health and makes its attacks faster.
    - **Ganon Subtype:** If `SprSubtype` is 5, it uses Ganon's draw and main logic, acting as a final phase.

### `kydreeok.asm` / `kydreeok_head.asm`
- **Sprite IDs:** `Sprite_Kydreeok` (body), `Sprite_KydreeokHead` (head, ID `$CF`)
- **Summary:** A large, stationary sea monster boss with multiple heads that act as its weak points. The main body sprite (`Kydreeok`) is a controller that spawns and manages the head sprites.
- **Key Logic:**
    - **`Kydreeok_Prep`:** Spawns two `KydreeokHead` sprites (`SpawnLeftHead`, `SpawnRightHead`).
    - **`Kydreeok_Main`:** The body moves around the arena, and the heads follow its position, controlled via shared RAM addresses (`LeftNeck1_X`, etc.).
    - **`KydreeokHead_Main`:** The heads have their own AI. They move in a rotational pattern and randomly shoot fireballs at the player.
    - **Damage:** Only the head sprites can be damaged. When both heads are defeated, the main body sprite is killed.

### `manhandla.asm`
- **Sprite ID:** `Sprite_Manhandla` (`$88`)
- **Summary:** A two-phase boss. The first phase is a plant-like creature with three heads. The second phase is a large Big Chuchu.
- **Key Logic:**
    - **Phase 1 (Manhandla):** The main body (`Manhandla_Body`) moves around the room, and three head sprites are spawned as offspring. The boss is only vulnerable when the heads are defeated.
    - **Phase Transition:** When all three heads are killed, `Sprite_Manhandla_CheckForNextPhaseOrDeath` sets `SprMiscD` to 1, refills the boss's health, and transitions to the `BigChuchu_Emerge` action.
    - **Phase 2 (Big Chuchu):** The sprite changes its appearance and behavior to that of a large slime. It moves around, spawns smaller slime projectiles (`Chuchu_SpawnBlast`), and has a central flower weak point.

### `octoboss.asm`
- **Sprite ID:** (Replaces `Sprite_A2_Kholdstare`)
- **Summary:** A custom boss fight featuring two octopus brothers who replace the vanilla Kholdstare boss.
- **Key Logic:**
    - The fight begins when the player approaches, triggering the `Emerge` sequence.
    - The first octopus spawns its brother (`SpawnAndAwakeHisBrother`), and they both don hats (`SpawnPirateHats`).
    - The two sprites then move independently, attacking the player. Their total health is tracked via `ReturnTotalHealth`.
    - When their combined health is low enough, they surrender (`WaitMessageBeforeSurrender`), remove their hats, and one submerges to give the player the Quake Medallion.

### `twinrova.asm`
- **Sprite ID:** `Sprite_Twinrova` (`$CE`, replaces Blind the Thief)
- **Summary:** A custom, multi-phase boss fight against the twin witches Koume (fire) and Kotake (ice). This sprite completely replaces the vanilla Blind the Thief boss, including the cutscene leading up to it.
- **Key Logic:**
    - **Trigger:** The fight begins when the Blind Maiden follower is brought into the boss room. `Follower_CheckBlindTrigger` detects this, and `Blind_SpawnFromMaiden` despawns the maiden and spawns the Twinrova sprite.
    - **Phase 1:** The combined Twinrova form moves around the room, alternating between fire (`Twinrova_FireAttack`) and ice (`Twinrova_IceAttack`) attacks.
    - **Phase 2:** When health is low, the boss splits. The `Twinrova_MoveState` action will randomly choose between `KoumeMode` (fire) and `KotakeMode` (ice). In these modes, the boss has different attack patterns, including spawning Keese and changing the floor tiles.

### `wolfos.asm`
- **Sprite ID:** `Sprite_Wolfos`
- **Summary:** A mini-boss that guards the Wolf Mask. It is designed to be subdued rather than killed.
- **Key Logic:**
    - The Wolfos attacks Link with lunges and swipes.
    - When its health is depleted, `Sprite_Wolfos_CheckIfDefeated` transitions it to the `Wolfos_Subdued` action instead of killing it.
    - In the subdued state, it waits for the player to play the Song of Healing (`SongFlag`).
    - Once the song is played, it grants the Wolf Mask (`ITEMGET` ID `$10F`) and then despawns.
