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

The special-overworld region (`0x80-0xBF`) shares one 64-map native container (`special_areas.asm` and `lyra_native_loaders.asm`; see [Terminology Glossary](../../Technical/terminology_glossary.md#special-overworld-domain-model)):

| OW Screen(s) | Parent / Size | Name / Region Role | Technical Features |
|---|---|---|---|
| `0x80` | `0x80` (32x32) | Maku Tree Area / Tree House | Maku Tree sprite spawns; variant tileset/overlay (`$0181`) |
| `0x81-0x82, 0x89-0x8A` | `0x81` (64x64) | Zora Falls | Waterfall effects/ripples, bridge causeways, water/cliff basins |
| `0x83` | `0x83` (32x32) | Cliff Terrace | Stepped cliff terrace/ramp north of `0x8B` (east of `0x82`) |
| `0x84-0x87, 0x8C-0x8F` | small pages (`0x94` overlay) | Sky Islands & Sky Tower (`0x87`) | `page_tile16` overrides on `0x87, 0x8C-0x8F`; cloud cover (`0x94`); Sky Tower exit `0x42` / ent `0x29` (`0x87`) |
| `0x90-0x92, 0x98-0x99` | small pages | Sea Zora Temple & Coast | `0x90` Sea Zora Temple; `0x91` Shrine of Wisdom (`0x33` door at `416,128`); `0x92` North Reef Gate; `0x98` shallow lagoon + sprite `0xB8` (`(15,12)`); `0x99` Zora Quay |
| `0x9C` | `0x9C` (32x32) | Reserved Fortress space | Reserved scawful space |
| `0xA0-0xBF` | `0xA0` (`64x32`), `0xA6`/`0xB0`/`0xB3` (`64x64`), `0xB5` (`32x64`), `0xBE` (`64x32`), others `32x32` | Lyra Sea & Coastal Tail Pages | `0xA0/0xA1` Zora Coast village; `0xA3/0xAC/0xAD` island/atoll waters (`0x387/0xC7C/0xC80` 2x2 corner reefs); `0xA6/0xA7/0xAE/0xAF` Great Island (Shrine of Courage `0x0C` on `0xA6`); `0xB0/0xB1/0xB8/0xB9` Goron coast / Shrine of Power (`0xB0`); `0xB3/0xB4/0xBB/0xBC` Crescent Atoll; `0xB5/0xBD` tall Lyra ship; `0xBE/0xBF` Snowy Island |

### Maku Tree Area (OW 0x80)

The Maku Tree sprite and Tree House variant live on `0x80`.

### Zora Falls (OW 0x81 parent: 0x81, 0x82, 0x89, 0x8A)

`0x81` is a 64x64 parent gameplay area spanning pages `0x81`, `0x82`, `0x89`, and `0x8A` with waterfall animations/SFX and connecting east into `0x83`.

---

## See Also

- [LocationRegistry.md](../LocationRegistry.md) - Master location index
- [Dungeons/](../Dungeons/) - Full dungeon documentation
- [Caves/](../Caves/) - Cave locations
