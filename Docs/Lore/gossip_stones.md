# Oracle of Secrets - Gossip Stone Registry

**Last Updated:** 2026-01-22

The Gossip Stones are petrified Kalyxians who witnessed the original sealing of Kydrog during the Age of Secrets. They chose to become eternal watchers rather than flee the island. They speak in fragments—memories frozen in stone.

---

## Design Notes

- **Activation:** TBD (no Mask of Truth - consider progression-based or always active)
- **Dialogue Limit:** Keep messages short for SNES text constraints (~60-80 chars per line, 2-3 lines max)
- **Tone:** Cryptic, poetic, slightly mournful
- **Voice:** First person plural ("We saw...") or impersonal prophecy ("The one who seeks...")

---

## Lore Stones

These reveal the history of Kalyxo, the sealing, and the nature of the Eon Abyss.

### GS01 - Near Mushroom Grotto Entrance
**Location:** Forest path leading to D1
**Trigger:** Default (always active)

```
We remember when these woods
whispered only of growth...
before the shadow learned our names.
```

---

### GS03 - Zora Sanctuary
**Location:** Near the waterfall tablet
**Trigger:** After completing D4 (Zora Temple)

```
The Zora carved mirrors from crystal
to walk between worlds freely.
That freedom became our cage.
```

---

### GS06 - Outside Kalyxo Castle
**Location:** Bridge approach or courtyard
**Trigger:** After completing D3 (Kalyxo Castle)

```
The Hylians came bearing shields,
claiming protection. We traded
one king's shadow for another's.
```

---

### GS08 - Near Shrine of Wisdom
**Location:** S1 entrance area
**Trigger:** Default

```
She who guarded Wisdom
surrendered every memory to the seal.
Even now, she has forgotten why.
```

---

### GS09 - Near Shrine of Power
**Location:** S2 entrance area
**Trigger:** Default

```
He who guarded Power
gave his flesh to bind the dark.
Only stone remembers his face.
```

---

### GS10 - Near Shrine of Courage
**Location:** S3 entrance area
**Trigger:** Default

```
She who guarded Courage
sacrificed tomorrow for today.
The future she lost... is now yours.
```

---

### GS11 - Eon Abyss Beach
**Location:** First area after arriving in Abyss
**Trigger:** Default

```
This is the world that waits
when hope abandons the living.
Do not linger. Do not look back.
```

---

### GS12 - Hall of Secrets (Interior)
**Location:** Near the Maku Tree after Farore's rescue
**Trigger:** After completing D7

```
The Oracle's blood runs thin now.
One sealing nearly broke her line.
A second may end it forever.
```

---

## Hint Stones

These point toward side quests, collectibles, and secrets.

### GS02 - Wayward Village
**Location:** Village square or near elder's house
**Trigger:** Default

```
A girl lost her voice at the ranch.
Seek the forest's gift, the witch's craft,
and the spark that wakes the silent.
```
*Hints at: Lost Ranch Girl Quest (Mushroom → Powder → Ocarina)*

---

### GS04 - Mount Snowpeak
**Location:** Mountain trail before Glacia Estate
**Trigger:** Default

```
An old man waits where fire meets ice.
Show him the path he has forgotten.
The stars will remember your kindness.
```
*Hints at: Old Man Mountain Quest (Goldstar reward)*

---

### GS07 - Korok Cove
**Location:** Forested wetland area
**Trigger:** Default

```
The small ones play where roots drink deep.
Count them if you can, seeker.
They reward those with patient eyes.
```
*Hints at: Korok Hide and Seek minigame*

---

### GS13 - Near Ranch
**Location:** Outside ranch buildings
**Trigger:** After obtaining Ocarina

```
Plant what hungers in barren soil.
Call the rain. Summon the swarm.
Patience grows what haste cannot.
```
*Hints at: Magic Bean Quest (Song of Storms + Bee pollination)*

---

### GS14 - Desert/Goron Area
**Location:** Path to Goron Mines
**Trigger:** Default

```
The mountain dwellers feast in silence.
Five offerings open the stone door.
Seek the meat that feeds the earth.
```
*Hints at: Goron Rock Meat collection quest*

---

## Warning Stones

These foreshadow dangers, boss encounters, or plot revelations.

### GS05 - Forest of Dreams (Eon Abyss)
**Location:** Deep in the corrupted forest
**Trigger:** Default

```
The Pirate King was not always dead.
He came here as you did—sword drawn,
heart full of purpose. The Abyss remembers.
```
*Foreshadows: Kydrog was once a hero like Link*

---

### GS15 - Near Dragon Ship Dock
**Location:** Approach to D7
**Trigger:** After collecting 6 essences

```
His ship sails on stolen breath.
Strike true, but know this:
Killing the body frees the spirit.
```
*Warning: Defeating Kydrog's pirate form doesn't end him*

---

### GS16 - Temporal Pyramid Exterior
**Location:** Outside final dungeon area
**Trigger:** After completing D8

```
Three gave everything to cage him.
You carry their sacrifice now.
Do not let their ending be yours.
```
*Foreshadows: Final boss fight, importance of Master Sword*

---

## Optional/Bonus Stones

Additional stones for hidden areas or post-game.

### GS17 - Hidden Grotto (Overworld Secret)
**Location:** Bombable cave or hidden area
**Trigger:** Default

```
Something older than the Pirate King
waits in the deepest dark.
A king of thieves. A lord of malice.
```
*Hints at: Ganondorf's presence in the Abyss*

---

### GS19 - Near Glacia Estate
**Location:** Mountain approach to D5
**Trigger:** Default

```
The twin flames serve another master.
Ice and fire are merely tools.
Beware what they prepare for.
```
*Foreshadows: Twinrova's true loyalty to Ganon*

---

### GS20 - Temporal Pyramid Interior
**Location:** Deep in the pyramid, near the seal
**Trigger:** After D8

```
He whispered to the fallen knight
for a hundred years. Patience
is the weapon of the imprisoned.
```
*Reveals: Ganon's corruption of Kydrog*

---

### GS21 - Near Meadow Blade Location (Kalyxo Castle)
**Location:** Near where Link finds the Lv2 sword
**Trigger:** Default

```
This blade knew another hand.
A hero carried it into shadow
and never returned. Until now.
```
*Connects: The Meadow Blade to its original owner*

---

### GS18 - Seashell Location
**Location:** Coastal hidden area
**Trigger:** Default

```
The sea remembers what the land forgets.
Gather its whispers, shell by shell.
A cartographer trades in secrets.
```
*Hints at: Seashell collection / Cartographer NPC*

---

## Implementation Checklist

| ID | Location | Category | Chars/Line | Implemented |
|----|----------|----------|------------|-------------|
| GS01 | Mushroom Grotto | Lore | ~35 | [ ] |
| GS02 | Wayward Village | Hint | ~40 | [ ] |
| GS03 | Zora Sanctuary | Lore | ~40 | [ ] |
| GS04 | Mount Snowpeak | Hint | ~40 | [ ] |
| GS05 | Forest of Dreams | Warning | ~40 | [ ] |
| GS06 | Kalyxo Castle Exterior | Lore | ~40 | [ ] |
| GS07 | Korok Cove | Hint | ~40 | [ ] |
| GS08 | Shrine of Wisdom | Lore | ~45 | [ ] |
| GS09 | Shrine of Power | Lore | ~40 | [ ] |
| GS10 | Shrine of Courage | Lore | ~40 | [ ] |
| GS11 | Eon Abyss Beach | Warning | ~40 | [ ] |
| GS12 | Hall of Secrets | Lore | ~40 | [ ] |
| GS13 | Ranch | Hint | ~35 | [ ] |
| GS14 | Goron Area | Hint | ~40 | [ ] |
| GS15 | Dragon Ship | Warning | ~40 | [ ] |
| GS16 | Temporal Pyramid Ext | Warning | ~40 | [ ] |
| GS17 | Hidden Grotto | Lore (Ganondorf) | ~40 | [ ] |
| GS18 | Seashell Coast | Hint | ~40 | [ ] |
| GS19 | Glacia Estate | Warning (Twinrova) | ~35 | [ ] |
| GS20 | Temporal Pyramid Int | Lore (Ganondorf) | ~35 | [ ] |
| GS21 | Kalyxo Castle Interior | Lore (Blade) | ~35 | [ ] |

**Total: 21 stones**

---

## Message ID Assignment

Gossip Stones use message IDs 0x1C0-0x1D4 in `Core/messages.org`:

| Stone | Message ID | Location |
|-------|------------|----------|
| GS01 | 0x1C0 | Mushroom Grotto Entrance |
| GS02 | 0x1C1 | Wayward Village |
| GS03 | 0x1C2 | Zora Sanctuary |
| GS04 | 0x1C3 | Mount Snowpeak |
| GS05 | 0x1C4 | Forest of Dreams |
| GS06 | 0x1C5 | Kalyxo Castle Exterior |
| GS07 | 0x1C6 | Korok Cove |
| GS08 | 0x1C7 | Shrine of Wisdom |
| GS09 | 0x1C8 | Shrine of Power |
| GS10 | 0x1C9 | Shrine of Courage |
| GS11 | 0x1CA | Eon Abyss Beach |
| GS12 | 0x1CB | Hall of Secrets Interior |
| GS13 | 0x1CC | Near Ranch |
| GS14 | 0x1CD | Goron Area Path |
| GS15 | 0x1CE | Dragon Ship Dock |
| GS16 | 0x1CF | Temporal Pyramid Exterior |
| GS17 | 0x1D0 | Hidden Grotto |
| GS18 | 0x1D1 | Seashell Coast |
| GS19 | 0x1D2 | Glacia Estate Approach |
| GS20 | 0x1D3 | Temporal Pyramid Interior |
| GS21 | 0x1D4 | Meadow Blade Location |

---

## Notes

- Stones use first-person plural ("We") to emphasize they are collective witnesses
- Past tense for lore, present/future for hints and warnings
- Avoid directly naming characters when possible (adds mystery)
- Each stone should feel like a fragment, not a complete explanation
- Players piece together the full story by finding all stones
