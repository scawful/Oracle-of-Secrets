# Oracle of Secrets - Dream Sequences

**Last Updated:** 2026-09-02
**Status:** Proposed (Implementation TBD)

This document details the planned dream sequences—playable narrative interludes that bridge major story arcs and reveal lore without exposition dumps.

---

## Overview

Dream sequences serve three purposes:
1. **Pacing:** Break up "dungeon fatigue" with atmospheric storytelling
2. **Lore delivery:** Show rather than tell key backstory
3. **Foreshadowing:** Plant seeds for later revelations

Dreams are triggered by "camping" or "rest" scenes after specific dungeons. Link sleeps and experiences a playable vision.

---

## Dream 1: The Sealing War

**Trigger:** After completing D2 (Tail Palace)
**Duration:** 3-5 minutes of gameplay
**Tone:** Epic, tragic, foreboding

### Narrative Purpose

This dream establishes the historical stakes. Players witness the original sealing of Kydrog (when he was still human) and understand:
- The magnitude of the ancient conflict
- That Kydrog was once a hero who fell
- The sacrifices made to create the seal
- Why the current threat is so serious

### Dream Flow

#### Scene 1: The Battlefield (Playable)

**Setting:** A twilight version of Kalyxo—recognizable but ancient
**Sprite:** Link appears as an "Ancient Soldier" (helmet, different armor palette)

```
[Screen fades in from white]

VOICE (Maku Tree?):
"Before the Pirate King...
before the corruption...
there was only a knight with a sword."

[Player gains control]
```

**Gameplay:**
- Walk through a battlefield strewn with fallen soldiers
- Enemies are shadowy, half-visible (can be fought or avoided)
- Path is mostly linear, guiding toward the mountain

**Environmental Details:**
- Burning structures in background
- Fallen Zora and Goron warriors (showing the alliance)
- The three Shrines visible, glowing with power
- Sky is blood-red, transitioning to black

#### Scene 2: The Mountain Approach (Playable)

**Setting:** Mountain path leading to a cave
**Objective:** Follow the knight ahead (Kydrog's living form, seen at distance)

```
VOICE:
"He sought the source of darkness.
He believed he could end it alone."

[A knight figure is visible ahead, climbing]
```

**Gameplay:**
- Platforming section (simple jumps)
- Shadow enemies block the path
- Reach the cave entrance

#### Scene 3: The Fall (Cutscene)

**Setting:** Inside the mountain, a vast cavern
**Transition:** Becomes non-playable, cinematic

```
[The knight enters the cavern]
[A massive shadowy form is visible—Ganondorf's silhouette]

KNIGHT:
"By the Goddesses, I will—"

GANONDORF (voice only):
"...Fail."

[The knight is engulfed in shadow]
[Scream, darkness, transformation implied]

VOICE:
"He did not return.
But something wearing his face did."
```

#### Scene 4: The Sealing (Cutscene)

**Setting:** The three Shrines, guardians performing the ritual

```
[Three figures stand at the shrine points]
[Light connects them, forms a triangle]

VOICE:
"Three gave everything to cage the evil.
Wisdom surrendered memory.
Power surrendered flesh.
Courage surrendered tomorrow."

[The triangle descends into the earth]
[The shadow is pulled down with it]

VOICE:
"The seal held.
For a time."

[Fade to black]
```

#### Wake Up

```
[Link awakens at a campfire]
[The Maku Tree's voice in his mind]

MAKU TREE:
"You saw the truth, hero.
The one you hunt was once like you.
Do not share his fate."
```

### Technical Requirements

| Element | Requirement | Notes |
|---------|-------------|-------|
| Sprite swap | Ancient Soldier palette | Link's sprite with different colors/helmet |
| Tileset | Twilight Kalyxo | Modified overworld palette, darker |
| Music | Unique dream track | Haunting, orchestral |
| NPCs | Shadowy enemies | Use existing enemy sprites, modified |
| Cutscene | HDMA effects | For Ganondorf reveal, seal formation |
| SRAM flag | Dream 1 complete | `Dreams` bitfield at $7EF410 |

### Message IDs Needed

| ID | Content | Speaker |
|----|---------|---------|
| TBD | "Before the Pirate King..." | Voice (Maku Tree) |
| TBD | "He sought the source..." | Voice |
| TBD | "By the Goddesses, I will—" | Knight |
| TBD | "...Fail." | Ganondorf |
| TBD | "He did not return..." | Voice |
| TBD | "Three gave everything..." | Voice |
| TBD | "The seal held..." | Voice |
| TBD | "You saw the truth, hero..." | Maku Tree |

---

## Dream 2: The Ranch Girl's Secret — CUT

**Canon status:** `[CUT 2026-09-02]`. Do not implement this dream, a sleep
trigger, or a Song-of-Healing return quest.

The old proposal duplicated the already-dense D1-to-D2 Ocarina chain, relied on
an unexplained return to Loom Ranch after D5, and described the Ranch Girl as
silent even though implemented message `0x17D` has her speak before giving Link
the Ocarina.

Canonical replacement:

- The required early quest explains that Twinrova transformed a witness and
  gives Link a real reason to investigate Loom Ranch.
- Magic Powder reveals the Ranch Girl temporarily so she can give Link the
  Ocarina and direct him to the Mask Salesman.
- Defeating Twinrova in D5 breaks the curse permanently and automatically.
- A short post-D5 reaction may appear if the player revisits naturally, but no
  objective, reward, song, or dream sends the player back.

The fire-and-ice witness imagery may be reused in concise D5 dialogue. It does
not require a separate scene or progression flag.

---

## Dream 3: The Observatory Vision

**Trigger:** After completing D7 (Dragon Ship), visiting Sky Islands Observatory
**Duration:** 2-3 minutes (mostly cutscene)
**Tone:** Cosmic, ominous, clarifying

### Narrative Purpose

The Sky Islands contain an ancient observatory built by Zora scholars. Looking through the crystal lens triggers a vision of Ganondorf's imprisonment—showing the player what they're truly fighting.

**Note:** This is not a sleep dream but a waking vision triggered by the Observatory lens.

### Vision Flow

#### Vision 1: The Past Age

**What Link sees:**
- A hero from long ago confronting Ganondorf
- The wizard-king in full power (humanoid Ganondorf, not Pig Ganon)
- A battle that shook the island

```
[Image: A green-clad figure facing a tall, robed figure]

VOICE:
"Long before your time...
a hero challenged the King of Evil."
```

#### Vision 2: The Sealing Ritual

**What Link sees:**
- Three guardians performing the original seal
- The sacrifice: Wisdom gave memories, Power gave flesh, Courage gave future
- The Lava Lands forming as Ganondorf's prison

```
[Image: Three figures channeling light into the earth]

VOICE:
"Three gave everything to cage him.
Not to destroy—to contain.
They believed death too merciful."
```

#### Vision 3: The Present

**What Link sees:**
- Ganondorf conscious, waiting, whispering in the dark
- The seal cracking (visualized as light breaking through cracks)
- Kydrog (as Stalfos) listening to the whispers

```
[Image: A dark figure in chains, one eye open, smiling]

VOICE:
"He is not dead. He is not sleeping.
He has been waiting.
And now, through his puppet...
he is almost free."

[Image: The seal cracking further]

VOICE:
"The Master Sword alone can end him.
Gather the pendants.
Forge the blade.
Or all is lost."
```

### Post-Vision

```
[Link pulls back from the crystal lens]
[He now understands the full stakes]
[Map marker appears for the Shrines if not already completed]
```

### Narrative Implications

After this vision:
- Link knows Ganondorf is the true enemy (not just Kydrog)
- The urgency of completing the Shrines is clear
- The Master Sword's necessity is established
- Lava Lands is identified as the final destination

### Technical Requirements

| Element | Requirement | Notes |
|---------|-------------|-------|
| Trigger | Observatory interaction | Specific tile/object in Sky Islands |
| Images | Static images with text | Simpler than full cutscene |
| Music | Ominous, revelatory | Orchestral swell |
| SRAM flag | Vision complete | `Dreams` bitfield at $7EF410 |

---

## Dreams Bitfield ($7EF410)

| Bit | Flag | Dream |
|-----|------|-------|
| 0 | `d1` | Dream 1: The Sealing War |
| 1 | — | Reserved; former Ranch Girl dream was cut 2026-09-02 |
| 2 | `d3` | Dream 3: Observatory Vision |
| 3-7 | — | Reserved for future dreams |

---

## Implementation Priority

| Dream | Priority | Complexity | Story Impact |
|-------|----------|------------|--------------|
| Dream 1 | High | High (sprite swap, custom tileset) | Major (establishes Kydrog's origin) |
| Ranch Girl dream | Cut | None | Replaced by early quest clues and automatic D5 resolution |
| Dream 3 | High | Low (static images, text) | Major (reveals true enemy) |

**Recommendation:** Implement Dream 3 first (lowest complexity, highest impact), then Dream 1. Do not implement the cut Ranch Girl dream.

---

## Open Questions

1. **Sprite swap for Dream 1:** Use existing sprite with palette swap, or create new Ancient Soldier sprite?

2. **Dream skip option:** Should players be able to skip dreams on repeat playthroughs?

3. **Observatory access:** When exactly do Sky Islands unlock? (Currently documented as post-D7)

The Ranch Girl connection is resolved: she is Twinrova's transformed witness,
and the curse ends automatically when Twinrova is defeated.

---

## Related Documents

- `dungeon_narratives.md`: D2, D5, D7 context
- `story_bible.md`: Character backgrounds
- `side_quests.md`: Ranch Girl quest
- `sram_flag_analysis.md`: Dreams flag documentation

---

## Technical Notes

### Attract Scene System

Dreams likely use the existing attract scene system in `Dungeons/attract_scenes.asm`. This system supports:
- Custom tilesets per scene
- Text overlays
- Palette manipulation
- Scene transitions

### Sprite Swapping

For Dream 1's Ancient Soldier:
- Option A: Palette swap on Link's sprite (simplest)
- Option B: Separate sprite sheet loaded for dream (more work, better result)
- Option C: Use existing NPC sprite as stand-in (quick but breaks immersion)

### HDMA Effects

For transformation/seal sequences:
- Wave distortion (screen warping)
- Color cycling (fire/ice effects)
- Mosaic transition (pixelation fade)

These are already used in other ALTTP hacks and should be portable.
