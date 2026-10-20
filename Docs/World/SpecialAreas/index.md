# Special Areas

Oracle of Secrets contains several unique locations that do not fit standard categories.

**Narrative alignment (2026-10-20):** the Fortress follows required Sky D8 and
the Maku Tree/Seed return. The Seed clears its visible entrance obstruction.
The planned geography moves the Fortress to `$4B` and Lupo Mountain toward
`$5E`. The directory retains old recorded map IDs until implementation is
verified; it does not certify a completed relocation.

---

## Special Area Directory

| ID | Name | OW Screen | Purpose |
|----|------|-----------|---------|
| 0x02 | Hall of Secrets | 0x0E | Farore's Sanctuary |
| 0x12 | Hall of Secrets (Pyramid Route) | 0x02 | Secret path |
| 0x24 | Final Boss Route | 0x46 | Endgame path |
| 0x37 | Fortress of Secrets | 0x5E | Historical placement; planned post-Seed Fortress at $4B |
| 0x59 | Archery Minigame | 0x1A | Minigame |

---

## Key Locations

### Hall of Secrets (0x02)

**Location:** OW 0x0E
**Purpose:** Farore's Sanctuary - central hub for secrets and oracle guidance

The Hall of Secrets serves as the game's central narrative hub where Farore provides guidance and unlocks abilities. Players return here at key story milestones.

**Features:**
- Oracle Farore's throne room
- Secret passage to pyramid (entrance 0x12)
- Connected to Cave of Secrets (0x50)

**Related Locations:**
- [Cave of Secrets](../Caves/index.md) - Nearby cave entrance

---

### Fortress of Secrets (0x37)

**Recorded location:** OW `$5E`; planned move to `$4B`.
**Purpose:** Shorter post-Sky, post-Seed location with Dark Link in Kydrog's arc.

The Fortress leads toward the volcano finale. Exact interior changes and
the route to the prison remain design work; a final boss at the top of a
multi-floor fortress is not established. See [the Fortress guide](FortressOfSecrets.md).

**Current route:**
- Complete Sky D8 and obtain the eighth essence.
- Return to the Maku Tree for the Maku Seed.
- Use the Seed to clear the visible Fortress entrance obstruction.

---

### Final Boss Route (0x24)

**Location:** OW 0x46
**Purpose:** Endgame pathway

The route leading to the final boss area. Opens after completing all dungeons.

---

### Archery Minigame (0x59)

**Location:** OW 0x1A
**Purpose:** Minigame for prizes

**Prizes:**
- Rupees
- Heart Piece (high score)
- Quiver upgrades

---

## Special Overworlds

These are overworld screens with special behavior defined in `special_areas.asm`:

| OW Screen | Name | Special Feature |
|-----------|------|-----------------|
| 0x80 | Maku Tree Area | Maku Tree sprite spawns |
| 0x81 | Zora Falls West | Waterfall effects |
| 0x82 | Zora Falls East | Waterfall effects |
| 0x80 (variant) | Tree House | Different tileset |

### Maku Tree Area (OW 0x80)

The Maku Tree is a central story NPC. This special overworld spawns the Maku Tree sprite and handles its dialogue states.

### Zora Falls (OW 0x81, 0x82)

The Zora Falls area has special waterfall animations and sound effects. May connect to Zora Temple entrance.

---

## See Also

- [LocationRegistry.md](../LocationRegistry.md) - Master location index
- [Dungeons/](../Dungeons/) - Full dungeon documentation
- [Caves/](../Caves/) - Cave locations
