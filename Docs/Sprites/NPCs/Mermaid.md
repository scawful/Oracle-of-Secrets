# Mermaid / Maple / Librarian

## Overview
The `mermaid.asm` file is a highly versatile sprite definition that implements three distinct NPC characters: the "Mermaid," "Maple," and "Librarian." This multi-purpose sprite leverages `SprSubtype` and `SprMiscE, X` to dispatch to different behaviors and drawing routines, allowing for efficient resource reuse and complex, context-sensitive interactions within the game world.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Mermaid` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `00`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_Mermaid_Long`)
This routine acts as a central dispatcher, selecting the appropriate drawing routine based on `SprMiscE, X` (0 for Mermaid, 1 for Maple, 2 for Librarian). It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_Mermaid_Long:
{
  PHB : PHK : PLB
  LDA.w SprMiscE, X : BEQ .MermaidDraw
         CMP.b #$02 : BEQ .LibrarianDraw
    JSR Sprite_Maple_Draw
    JMP .Continue
  .LibrarianDraw
  JSR Sprite_Librarian_Draw
  JMP .Continue
  .MermaidDraw
  JSR Sprite_Mermaid_Draw
  .Continue
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Mermaid_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Mermaid_Prep`)
This routine initializes the sprite upon spawning. It sets `SprDefl, X`, `SprTimerA, X`, and `SprHitbox, X`. Crucially, it sets `SprMiscE, X` based on `SprSubtype, X` to determine which character the sprite will represent (0 for Mermaid, 1 for Maple, 2 for Librarian).

```asm
Sprite_Mermaid_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$40 : STA.w SprTimerA, X
  LDA.b #$07 : STA.w SprHitbox, X

  ; Mermaid Sprite
  STZ.w SprMiscE, X

  ; Maple Sprite
  LDA.w SprSubtype, X : CMP.b #$01 : BNE +
    LDA.b #$01 : STA.w SprMiscE, X
  +

  ; Librarian Sprite
  CMP.b #$02 : BNE ++
    LDA.b #$02 : STA.w SprMiscE, X
  ++
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Mermaid_Main`)
This routine acts as a dispatcher for the main logic, calling the appropriate handler (`MermaidHandler`, `MapleHandler`, or `LibrarianHandler`) based on `SprMiscE, X`.

### `MermaidHandler`
Manages the Mermaid's behavior through a state machine:

*   **`MermaidWait`**: Plays an idle animation, prevents player passage, and displays a message on contact. Upon message dismissal, it transitions to `MermaidDive`.
*   **`MermaidDive`**: Plays a diving animation, moves horizontally, and transitions to `MermaidSwim` after a timer.
*   **`MermaidSwim`**: Plays a swimming animation, moves, sets `SprXSpeed, X`, spawns a splash effect, and can despawn or change direction after a timer.

### `LibrarianHandler`
Manages the Librarian's behavior, primarily focused on a map and scroll translation quest:

*   **`LibrarianIdle`**: Plays an animation, prevents player passage, and displays messages based on whether Link has no maps, all maps, or new scrolls. Transitions to `Librarian_CheckResponse` if new scrolls are available.
*   **`Librarian_CheckResponse`**: Processes Link's response to the translation offer, transitioning to `Librarian_OfferTranslation` or back to `LibrarianIdle`.
*   **`Librarian_OfferTranslation`**: Displays a message, prevents player passage, and checks `Scrolls` and `DNGMAP1`/`DNGMAP2` to identify new scrolls. If found, it updates `Scrolls`, sets `SprMiscG, X` to the scroll ID, and transitions to `Librarian_TranslateScroll`.
*   **`Librarian_TranslateScroll`**: Displays a message based on the scroll ID and transitions to `Librarian_FinishTranslation`.
*   **`Librarian_FinishTranslation`**: Displays a final message and returns to `LibrarianIdle`.

### Librarian Message IDs

| Message ID | Purpose | Status |
| --- | --- | --- |
| `0x012E` | No maps / no scrolls | Present |
| `0x01A0` | Offer translation | Present |
| `0x01A1` | Translation start | Present |
| `0x01A2` | Translation complete | Present |
| `0x01A3` | All scrolls collected | Present |

**Message 0x012E (current):**
```
In your quest you may find
secret scrolls, bring them all
to me for translation.
```

**Message 0x01A0 (Offer Translation):**
```
Ah, another secret scroll!
These ancient writings hold
mysteries long lost to time.
Shall I translate its forgotten
words for you?

> Translate the scroll
  Read previous scroll
  Don't touch my stuff
```

**Message 0x01A1 (Translation Start):**
```
Very well. Let us unveil the
secrets hidden within this
ancient text.
Listen closely, for these
words carry great weight.
```

**Message 0x01A2 (Translation Done):**
```
The scroll has been translated.
Another piece of Kalyxo's
history revealed.
These words may serve you
well, if you heed them.
```

**Message 0x01A3 (All Scrolls):**
```
It seems you've collected all
the scrolls in the land of
Kalyxo! You truly are the hero.
```

## `Librarian_CheckForAllMaps` and `Librarian_CheckForNoMaps`
These helper routines check `DNGMAP1` and `DNGMAP2` (SRAM flags for dungeon maps) to determine Link's map collection status.

## Drawing (`Sprite_Mermaid_Draw`, `Sprite_Maple_Draw`, `Sprite_Librarian_Draw`)
Each character has its own dedicated drawing routine. These routines handle OAM allocation and animation, and explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the respective character.

## Design Patterns
*   **Multi-Character Sprite (Conditional Drawing/Logic)**: A single sprite definition (`Sprite_Mermaid`) is used to represent three distinct NPCs (Mermaid, Maple, Librarian) based on `SprSubtype` and `SprMiscE`, showcasing efficient resource utilization and context-sensitive character representation.
*   **Quest Progression Integration**: The Librarian's dialogue and actions are tied to collected dungeon maps and scrolls, indicating its role in a translation quest, driving narrative progression.
*   **Context-Sensitive Dialogue**: The Librarian's messages dynamically change based on whether Link has maps, all maps, or new scrolls, providing a personalized and evolving interaction.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make NPCs solid objects that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
