# Oracle of Secrets - World Map Diagram

**Last Updated:** 2026-01-22
**Purpose:** Document all overworld screens, dungeon locations, and entrances for lore hint placement

---

## World Structure Overview

| World | Screen Range | Name | Description |
|-------|--------------|------|-------------|
| **Light World (LW)** | `0x00-0x3F` | Kalyxo Island | Main overworld, present day |
| **Dark World (DW)** | `0x40-0x7F` | Eon Abyss | Mirror dimension, corrupted reflection |
| **Special World (SW)** | `0x80+` | Expanded Areas | Forest Glade, Korok Cove, Sky Islands, etc. |

---

## Kalyxo Island (Light World: 0x00-0x3F)

### Grid Layout (8x8 = 64 screens)

```
          0              1              2              3              4              5              6              7
   ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
   │     00       │     01       │     02       │     03       │     04       │     05       │     06       │     07       │
 0 │    Ranch     │    Ranch     │  Pyramid     │              │  Snow Mtn    │  Snow Mtn    │   Glacia     │  Snow Peak   │
   │              │              │    Route     │              │  West Peak   │  East Peak   │   Estate     │              │
   │              │              │              │              │              │              │     D5       │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     08       │     09       │     0A       │     0B       │     0C       │     0D       │     0E       │     0F       │
 1 │    Ranch     │    Ranch     │  West Hotel  │   Kalyxo     │   Kalyxo     │  Witch Shop  │   Hall of    │  Graveyard   │
   │              │              │              │   Castle     │   Castle     │    Area      │   Secrets    │              │
   │              │              │              │     D3       │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     10       │     11       │     12       │     13       │     14       │     15       │     16       │     17       │
 2 │   Mushroom   │              │              │   Kalyxo     │   Kalyxo     │    Fairy     │              │  S of Grave  │
   │    Grotto    │              │              │   Castle     │   Castle     │  Fount East  │              │              │
   │     D1       │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     18       │     19       │     1A       │     1B       │     1C       │     1D       │     1E       │     1F       │
 3 │  Toadstool   │              │   Archery    │              │              │    Fairy     │    Zora      │              │
   │    Woods     │              │  Minigame    │              │              │ Fount South  │  Sanctuary   │              │
   │              │              │              │              │              │              │     D4       │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     20       │     21       │     22       │     23       │     24       │     25       │     26       │     27       │
 4 │              │              │   Smith's    │   Wayward    │              │   Kalyxo     │              │              │
   │              │              │    House     │   Village    │              │    Field     │              │              │
   │              │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     28       │     29       │     2A       │     2B       │     2C       │     2D       │     2E       │     2F       │
 5 │              │  Lost Woods  │   Forest     │              │              │   Tail Pond   │  Tail Cave   │    Tail      │
   │              │              │  Crossroads  │              │              │  Mask Area   │    Route     │   Palace     │
   │              │              │              │              │              │              │              │     D2       │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     30       │     31       │     32       │     33       │     34       │     35       │     36       │     37       │
 6 │   Dragon     │              │  Beach Cave  │    Loom      │    Loom      │              │    Goron     │              │
   │    Ship      │              │              │    Beach     │    Beach     │              │    Mines     │              │
   │     D7       │              │              │              │              │              │     D6       │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     38       │     39       │     3A       │     3B       │     3C       │     3D       │     3E       │     3F       │
 7 │              │              │              │   Loom       │    Loom      │              │              │              │
   │              │              │              │   Beach      │    Beach     │              │              │              │
   │              │              │              │              │              │              │              │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### Named Locations (Light World)

| Screen | Hex | Name | Size | Notable Features |
|--------|-----|------|------|------------------|
| 0x00 | `00` | Ranch Area | Large | Ranch Shed, Ocarina Girl's House, Chicken House |
| 0x02 | `02` | Hall of Secrets Pyramid Route | Small | Cave to Hall of Secrets |
| 0x04 | `04` | Snow Mountain West Peak | Small | Cave to East Peak |
| 0x05 | `05` | Snow Mountain East Peak | Small | Portal cave, Cave to West Peak |
| 0x06 | `06` | Glacia Estate Approach | Small | **D5 Entrance** |
| 0x07 | `07` | Snow Mountain Peak | Small | Old Man Mountain Quest |
| 0x0A | `0A` | West Hotel Area | Small | West Hotel entrance |
| 0x0B | `0B` | Kalyxo Castle | Large | **D3**, Multiple entrances (Main, West, Basement, Prison, Secret Courtyard) |
| 0x0D | `0D` | Witch Shop Area | Small | Witch Shop, Mountain caves |
| 0x0E | `0E` | Hall of Secrets | Small | Repurposed vanilla sanctuary interior; main story hub |
| 0x0F | `0F` | Graveyard | Small | Hidden Grave, Waterfall cave |
| 0x10 | `10` | Mushroom Grotto | Large | **D1 Entrance** |
| 0x15 | `15` | Fairy Fountain East | Small | Deluxe Fairy, Rock Heart Piece Cave |
| 0x17 | `17` | South of Graveyard | Small | Tree House entrance |
| 0x18 | `18` | Toadstool Woods | Small | Mushroom House, Old Woman House, Log Cave, Chest/Bonzai Games |
| 0x1A | `1A` | Archery Area | Small | Archery Minigame |
| 0x1D | `1D` | Fairy Fountain South | Small | Deluxe Fairy (East/South entrances) |
| 0x1E | `1E` | Zora Sanctuary | Large | **D4 (Zora Temple)**, Zora Princess House, Waterfall entrance |
| 0x22 | `22` | Smith's House Area | Small | Smith's House |
| 0x23 | `23` | Wayward Village | Large | Village center: Tavern, Shop, Library, Mayor's House, Sick Boy's House |
| 0x25 | `25` | Kalyxo Field | Small | Cave system (Start/River/End) |
| 0x29 | `29` | Lost Woods | Small | Maze puzzle area |
| 0x2A | `2A` | Forest Crossroads | Small | Wayward Village / Lost Woods / Loom Beach West junction; tree entrance to SW 0x80 (Forest Glade) |
| 0x2D | `2D` | Tail Pond | Small | Pond area; Happy Mask Salesman Shop; withered Deku Scrub (main quest) outside; Tail Palace Cave Start |
| 0x2E | `2E` | Tail Palace Cave | Small | Cave route end |
| 0x2F | `2F` | Tail Palace | Large | **D2 Entrance** |
| 0x30 | `30` | Dragon Ship Dock | Large | **D7 (Dragon Ship)** |
| 0x32 | `32` | Beach Cave | Small | Beach Cave (Intro/Route) |
| 0x33 | `33` | Loom Beach | Small | Tiny House entrance |
| 0x36 | `36` | Goron Area | Large | **D6 (Goron Mines)**, Mines Shed |

---

## Eon Abyss (Dark World: 0x40-0x7F)

The Eon Abyss is the mirror dimension of Kalyxo Island. It represents a corrupted, twisted version of the Light World where Kydrog was sealed.

### Grid Layout (8x8 = 64 screens)

```
          0              1              2              3              4              5              6              7
   ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
   │     40       │     41       │     42       │     43       │     44       │     45       │     46       │     47       │
 0 │   Temporal   │   Temporal   │              │  Lava Lands  │  Lava Lands  │  Lava Lands  │  Lava Lands  │  Lava Lands  │
   │   Pyramid    │   Pyramid    │              │              │              │              │              │              │
   │  (MS hidden) │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     48       │     49       │     4A       │     4B       │     4C       │     4D       │     4E       │     4F       │
 1 │              │              │              │    Lupo      │    Lupo      │  Lava Lands  │  Lava Lands  │  Lava Lands  │
   │              │              │              │   Mountain   │   Mountain   │              │              │              │
   │              │              │              │     S2       │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     50       │     51       │     52       │     53       │     54       │     55       │     56       │     57       │
 2 │  Shrine of   │  Connector   │              │    Lupo      │    Lupo      │  Lava Lands  │  Lava Lands  │  Lava Lands  │
   │   Courage    │  to Pyramid  │              │   Mountain   │   Mountain   │              │              │  Final Boss  │
   │     S3       │              │              │              │              │              │              │   (Ganon)    │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     58       │     59       │     5A       │     5B       │     5C       │     5D       │     5E       │     5F       │
 3 │  Forest of   │  Forest of   │              │              │              │              │ Fortress of  │              │
   │   Dreams     │   Dreams     │              │              │              │              │   Secrets    │              │
   │   (Intro)    │              │              │              │              │              │     D8       │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     60       │     61       │     62       │     63       │     64       │     65       │     66       │     67       │
 4 │  Forest of   │  Forest of   │              │    Swamp     │    Swamp     │              │              │              │
   │   Dreams     │   Dreams     │              │  Shrine of   │              │              │              │              │
   │              │              │              │  Wisdom S1   │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     68       │     69       │     6A       │     6B       │     6C       │     6D       │     6E       │     6F       │
 5 │  Forest of   │  Forest of   │  Forest of   │    Swamp     │    Swamp     │              │              │              │
   │   Dreams     │   Dreams     │   Dreams     │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     70       │     71       │     72       │     73       │     74       │     75       │     76       │     77       │
 6 │  Underwater  │  Underwater  │  Underwater  │  Underwater  │  Underwater  │   Octobos    │    Beach     │    Beach     │
   │    Area      │    Area      │    Area      │    Area      │    Area      │    Area      │   Desert     │   Desert     │
   │   (Zora)     │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     78       │     79       │     7A       │     7B       │     7C       │     7D       │     7E       │     7F       │
 7 │  Underwater  │  Underwater  │  Underwater  │  Underwater  │  Underwater  │  Underwater  │    Beach     │    Beach     │
   │    Area      │    Area      │    Area      │    Area      │    Area      │    Area      │   Desert     │   Desert     │
   │              │              │              │              │              │              │              │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### Named Locations (Eon Abyss)

| Screen | Hex | Name | Notable Features |
|--------|-----|------|------------------|
| 0x40-41 | `40-41` | Temporal Pyramid | Large area, Master Sword hidden in 0x41 corner |
| 0x43-47, 4D-4F, 55-57 | | Lava Lands | Volcanic region, 0x57 has final boss hole |
| 0x4B-4C, 53-54 | | Lupo Mountain | Mountain area with **S2 (Shrine of Power)** |
| 0x50 | `50` | Shrine of Courage | **S3 Entrance** - Mirror Shield |
| 0x51 | `51` | Connector | Links Shrine of Courage to Pyramid |
| 0x57 | `57` | Final Boss Chamber | Hole to Ganon/Kydreeok fight |
| 0x58-59, 60-61, 68-6A | | Forest of Dreams | Intro area, connects to S3 later |
| 0x5E | `5E` | Fortress of Secrets | **D8 Entrance** - Portal Rod |
| 0x63-64, 6B-6C | | Swamp | Swampy area with **S1 (Shrine of Wisdom)** |
| 0x70-74, 78-7D | | Underwater Area | Access via Mermaid NPC whirlpool on LW 0x3C (Zora Mask required) |
| 0x75 | `75` | Octobos Area | Octobos enemy location |
| 0x76-77, 7E-7F | | Beach/Desert | Coastal desert region |

### Eon Abyss Lore Context

The Eon Abyss is described as "the world that waits when hope abandons the living." Key lore points:

- Mirror reflection of Kalyxo created during Kydrog's sealing
- Contains the three Shrines (Wisdom, Power, Courage) where the original sealers sacrificed themselves
- Underwater area only accessible via Zora Mask transformation at Mermaid NPC whirlpool (LW 0x3C)

### Game Intro Flow (Eon Abyss Section)

1. **Kydrog Encounter** - After sneaking through Wayward Village with Impa, Link enters SW 0x80 (Forest Glade) via the special tree entrance from 0x2A
2. **Banishment** - Kydrog casts Link away (Agahnim-style) → Link appears on **Temporal Pyramid (0x40)** as Bunny Link
3. **Moon Pearl** - Find Moon Pearl in pyramid area
4. **Shrine of Origins** - Use Minish Cap ability on 0x40 to regain human form
5. **Owl Encounter** - Meet the Owl on 0x50 who gives advice
6. **Sword & Shield** - Found on 0x60 (large map area)
7. **Portal Home** - Portal on 0x6A takes Link back to 0x2A (Forest Crossroads)
8. **Maku Tree** - Hall of Secrets is on OW 0x0E (repurposed sanctuary). It is not connected to SW 0x80.

---

## Special World / Expanded Areas (0x80+)

These are special expanded maps accessed via triggers on the main overworld. They allow for larger or more detailed areas than a single overworld screen.

### Grid Layout (8x4 = 32 screens)

```
          0              1              2              3              4              5              6              7
   ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
   │     80       │     81       │     82       │     83       │     84       │     85       │     86       │     87       │
 0 │  Forest Glade│              │   Korok      │              │              │              │              │              │
   │   (Kydrog)   │              │    Cove      │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     88       │     89       │     8A       │     8B       │     8C       │     8D       │     8E       │     8F       │
 1 │              │              │              │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     90       │     91       │     92       │     93       │     94       │     95       │     96       │     97       │
 2 │              │   Loom       │              │              │              │              │              │              │
   │              │   Beach      │              │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
   │     98       │     99       │     9A       │     9B       │     9C       │     9D       │     9E       │     9F       │
 3 │              │              │              │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   │              │              │              │              │              │              │              │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### Special Area Registry

| ID | Hex | Name | Trigger Screen | Entry Tile | Description |
|----|-----|------|----------------|------------|-------------|
| 0x080 | `80` | Forest Glade (Kydrog encounter) | 0x2A | TBD | Left half used for Kydrog encounter; top-right trigger leads to Tree Interior (0x181) |
| 0x180 | `180` | Forest Glade Entrance (Exit ID) | 0x2A | `$01EF` | Special overworld entrance into SW 0x80 (exit ID, not a map) |
| 0x181 | `181` | Tree Interior (Under the Bridge) | SW 0x80 (top-right trigger) | TBD | Vanilla bottle-guy area; Oracle name tentative |
| 0x182 | `182` | Korok Cove (Zora Falls in vanilla) | 0x0F | `$00AD` | Waterfall area behind graveyard; leads to East Kalyxo via expanded maps |
| 0x189 | `189` | | 0x81 | `$00B9` | DW expansion |
| 0x191 | `191` | Loom Beach | 0x33 | `$00B7` | Tiny house / coastal area |
| | | Sea Zora Area | | | East Kalyxo, Kydrog lore NPC |
| | | Sky Islands | | | Beanstalk destination |

### Expanded Area Notes

| Area | NPCs | Access | Purpose |
|------|------|--------|---------|
| **Forest Glade (SW 0x80)** | Kydrog encounter | Tree entrance on 0x2A (exit ID 0x180) | Main quest beat; repurposed from vanilla master sword screen |
| **Tree Interior (SW 0x181)** | Bottle guy (vanilla under-bridge) | Trigger from SW 0x80 (top-right) | Flavor / item |
| **Korok Cove (SW 0x182)** | Koroks | Waterfall on 0x0F (Graveyard) | Hide & Seek; leads to East Kalyxo via expanded maps |
| **Sea Zora Area** | Sea Zora | TBD | Major lore NPC (Kydrog history) |
| **Sky Islands** | TBD | Beanstalk from Ranch? | Heart Container reward |

### Overlays

| Name | Purpose | Trigger |
|------|---------|---------|
| Canopy Overlay | Forest canopy visual layer | Forest areas |
| Rain Overlay | Storm visual layer | Song of Storms |
| | | |

---

## Dungeon Registry

### Main Dungeons (D1-D8)

| ID | Name | OW Screen | World | Boss | Reward |
|----|------|-----------|-------|------|--------|
| **D1** | Mushroom Grotto | 0x10 | LW | Mothra | Bow |
| **D2** | Tail Palace | 0x2F | LW | Big Moldorm | Roc's Feather |
| **D3** | Kalyxo Castle | 0x0B | LW | Armos Knights | Meadow Blade |
| **D4** | Zora Temple | 0x1E | LW | Arrghus | Hookshot |
| **D5** | Glacia Estate | 0x06 | LW | Twinrova | Fire Rod |
| **D6** | Goron Mines | 0x36 | LW | King Dodongo | Hammer |
| **D7** | Dragon Ship | 0x30 | LW | Kydrog (Pirate) | Somaria Rod |
| **D8** | Fortress of Secrets | 0x5E | DW | Dark Link | Portal Rod |

### Shrines (S1-S3)

| ID | Name | OW Screen | World | Boss | Reward |
|----|------|-----------|-------|------|--------|
| **S1** | Shrine of Wisdom | 0x63 | DW | (none) | Zora Flippers |
| **S2** | Shrine of Power | 0x4B | DW | (none) | Power Glove |
| **S3** | Shrine of Courage | 0x50 | DW | Vaati | Mirror Shield |

### Final Areas

| Name | OW Screen | World | Boss | Notes |
|------|-----------|-------|------|-------|
| Temporal Pyramid | 0x02/0x46 | LW/DW | — | Links both worlds |
| Eon Core | (interior) | — | Kydreeok, Ganon | Final dungeon |

---

## Entrance ID → Location Map

Extracted from `Overworld/entrances.asm`:

### Dungeon Entrances

| Ent ID | OW | Location |
|--------|-----|----------|
| 0x15 | 0x2F | Tail Palace (D2) |
| 0x25 | 0x1E | Zora Temple (D4) |
| 0x26 | 0x10 | Mushroom Grotto (D1) |
| 0x27 | 0x36 | Goron Mines (D6) |
| 0x28 | 0x0B | Kalyxo Castle West (D3) |
| 0x2B | 0x0B | Kalyxo Castle Main (D3) |
| 0x34 | 0x06 | Glacia Estate (D5) |
| 0x35 | 0x30 | Dragon Ship (D7) |
| 0x37 | 0x5E | Fortress of Secrets (D8) |

### Shrine Entrances

| Ent ID | OW | Location |
|--------|-----|----------|
| 0x33 | 0x63 | Shrine of Wisdom (S1) |
| 0x03/05/09/0B | 0x4B | Shrine of Power (S2) |
| 0x0C | 0x50 | Shrine of Courage (S3) |

### Key Interior Entrances

| Ent ID | OW | Location |
|--------|-----|----------|
| 0x02 | 0x0E | Hall of Secrets |
| 0x18/19/2D | 0x40 | Master Sword Cave |
| 0x3E | 0x00 | Ranch Shed |
| 0x3F | 0x00 | Ocarina Girl's House |
| 0x42 | 0x23 | Village Tavern |
| 0x46 | 0x23 | Village Shop |
| 0x49 | 0x23 | Village Library |
| 0x4C | 0x0D | Witch Shop |
| 0x61 | 0x23 | Village Mayor's House |
| 0x6B | 0x2D | Happy Mask Salesman Shop |

---

## NPC Placement by Screen

### Light World NPCs

| Screen | NPCs Present | Lore Relevance |
|--------|--------------|----------------|
| 0x00 Ranch | Ranch Girl (Cucoo), Ocarina Girl | Lost Ranch Girl quest |
| 0x0E Hall of Secrets | Maku Tree, Impa (telepathic) | Main story hub |
| 0x1E Zora Sanctuary | Zora Princess, Sea Zora, Zora Baby | Zora Mask quest, Kydrog lore |
| 0x23 Village | Elder, Mayor, Sick Boy, Librarian | Song of Healing quest |
| 0x2D Tail Pond | Happy Mask Salesman, withered Deku Scrub | Mask quests / main quest beat |
| 0x36 Goron Area | Kalyxian Goron | Goron Mines quest |

### Eon Abyss NPCs

| Screen | NPCs Present | Lore Relevance |
|--------|--------------|----------------|
| 0x40 Master Sword | (forest spirits?) | Meadow Blade connection |
| Various | Eon Scrubs, Stalfos | Corrupted enemies |

---

## Lore Hint Placement Candidates

Since Gossip Stones may not be viable (graphics constraints), alternative hint delivery methods:

### Option 1: Telepathic Stones/Signs

Existing sign/tablet system could display hints on interaction.

### Option 2: NPC Dialogue Variants

Add hint dialogue to existing NPCs based on progression flags.

### Option 3: Owl Statues

Kaepora Gaebora-style owl statues with cryptic messages.

### Recommended Hint Locations by Category

**Lore Hints (Story/History):**

| Screen | Location | Method | Hint Topic |
|--------|----------|--------|------------|
| 0x10 | D1 Entrance | Sign/NPC | Woods before shadow |
| 0x0B | Castle approach | Guard NPC | Hylian occupation |
| 0x1E | Zora Sanctuary | Sea Zora | Kydrog fallen hero (exists!) |
| 0x40 | Master Sword | Stone/Sign | Original blade owner |

**Quest Hints (Sidequests):**

| Screen | Location | Method | Hint Topic |
|--------|----------|--------|------------|
| 0x23 | Village | Elder NPC | Ranch Girl quest |
| 0x07 | Mountain | Sign | Old Man quest |
| 0x00 | Ranch | Sign | Magic Bean quest |
| 0x36 | Goron area | Goron NPC | Rock Meat quest |

**Warning Hints (Foreshadowing):**

| Screen | Location | Method | Hint Topic |
|--------|----------|--------|------------|
| 0x06 | Glacia approach | Sign | Twinrova warning |
| 0x30 | Dragon Ship | Sign | Kydrog warning |
| 0x5E | Fortress approach | Stone | Three sealers |

---

## Open Questions

1. **Sky Islands implementation?** - Via beanstalk or bird travel?
2. **Eon Abyss screen names?** - Many DW screens unnamed
3. **Sign/tablet sprite availability?** - Can reuse existing assets?

---

## Reference Commands

```bash
# List overworld entrances
grep -n "OW 0x" Overworld/entrances.asm

# Find dungeon references
grep -rn "D[1-8]\|Dungeon" Docs/

# Check sprite loading by screen
grep -n "SpritePointers" Overworld/ZSCustomOverworld.asm
```
