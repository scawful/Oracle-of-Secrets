# Oracle of Secrets - Intro Flow Analysis

**Last Updated:** 2026-01-22
**Purpose:** Document the intro sequence, analyze dialogue, and suggest improvements

---

## Current Intro Sequence

### Phase 1: Loom Beach Awakening (LW 0x33)

1. **Wake Up** - Link awakens in a bed on Loom Beach
   - Current: Generic Oracle-style "Accept our quest hero!" prompt
   - **Suggestion:** Could use a dream sequence or Farore vision here to set up the story

2. **Exit House** - Player explores the beach area

3. **Meet Impa** - Find Impa who explains her mission
   - "Sent by the princess to meet with Farore"
   - **Note:** This connects to Zelda (post-linked ending), establishing Oracle timeline

### Phase 2: Wayward Village Infiltration (LW 0x23)

1. **Enter Village** - Impa becomes follower
2. **Stalfos Guards** - Block path to Forest Glade / Farore (tree entrance to SW 0x80); cleared after GameState moves to 2 (return from Eon Abyss)
   - **Lore Implication:** Kydrog's forces already control parts of Kalyxo
3. **Sneak Around** - Player navigates around guards to reach Farore

### Phase 3: Kydrog Encounter (LW 0x2A → SW 0x80)

1. **Enter Forest Glade (SW 0x80)** - Reach via the special tree entrance from LW 0x2A (Forest Crossroads); Kydrog is already there waiting
   - `kydrog.asm` (Sprite_KydrogNPC) handles this cutscene

2. **Kydrog's Dialogue (Message 0x21):**
```
Well, well, what a surprise!
Look who walked into me trap,
and with Farore, no less.

The lass I've been seekin'.

I'm Kydrog, the Pirate King,
and I've been waitin' for ye
to show up. Hehehe!

Prepare yourself, lad! Ye're
about to be cast away to the
Eon Abyss, just as I was.

A fitting end for a pesky hero,
don't ye think? Hehehe!

Oh, and before I forget, let me...
[continues]
```

**Key Lore Point:** "Cast away to the Eon Abyss, **just as I was**"
- Confirms Kydrog was also banished to the Abyss
- Suggests shared fate/connection between Link and Kydrog
- Supports "fallen hero" backstory

3. **Banishment** - Kydrog warps Link away (Agahnim-style)
   - Code sets `$7EF3CA` to Dark World flag
   - Sets map to `$A0 = #$20` (Room 0x20 in pyramid area?)
   - Removes Impa follower
   - Sets progress flag `$7EF3C6 |= #$04`

### Phase 4: Temporal Pyramid (DW 0x40)

1. **Bunny Link** - Link arrives as bunny (no Moon Pearl yet)
2. **Find Moon Pearl** - Located somewhere in pyramid
3. **Shrine of Origins** - Use Minish Cap ability to regain human form
   - **Question:** What is the "Minish Cap ability"? Shrinking mechanic?

### Phase 5: Eon Abyss Exploration (DW 0x50-0x6A)

1. **Owl Encounter (DW 0x50)** - Eon Owl gives advice

**Owl's Dialogue (Message 0xE6):**
```
Hoo hoo! [L], lost in
this dark abyss, are you?

This realm is a mirror,
a reflection of forgotten
dreams and shadowed paths.

Though you hold the Moon
Pearl, beware, for not all
is as it seems in the Abyss.

Deep in the Forest of Dreams,
where echoes of the old...
[continues]
```

**Key Lore Points:**
- "This realm is a mirror" - confirms mirror dimension concept
- "Reflection of forgotten dreams and shadowed paths" - poetic, fits tone
- Acknowledges Moon Pearl possession
- References "Forest of Dreams" by name

**Code Note:** Owl despawns after player gets sword (`Sword >= 1`)

2. **Sword & Shield (DW 0x60)** - Found on large map area
   - This is the Lv1 Sword (not Meadow Blade)

3. **Portal Home (DW 0x6A)** - Returns to LW 0x2A (Forest Crossroads)

### Phase 6: Maku Tree Guidance (Hall of Secrets, OW 0x0E)

1. **First Meeting (Message 0x20):**
```
Ah, [L]!
Thank the Goddesses you are
alright. I feared the worst.

A dark shadow has befallen us.
Kydrog, the Pirate King, has
seized Farore and threatens
our great island of Kalyxo.

[...] [...] [...]

Long ago, the island of Kalyxo
was chosen by the Goddess
Farore as her resting place.

The Triforce's essences were
hidden here to protect them...
[continues]
```

**Key Lore Points:**
- "Kydrog has seized Farore" - establishes stakes
- "Island of Kalyxo" - names the Light World
- "Goddess Farore as her resting place" - explains Farore's presence
- "Triforce's essences" - the MacGuffins

**Code Actions:**
- Sets `MakuTreeQuest = 1`
- Sets `MapIcon = 1` (Mushroom Grotto marker)
- Sets `OOSPROG |= #$02`
- Gives Heart Container

2. **Revisit (Message 0x22):**
```
Ah, [L]!
How fares your journey?
Remember, you must seek out
the Triforce's essences from
across Kalyxo and the Abyss
to thwart Kydrog's plans.

Impa in the Hall of Secrets
will guide you when in doubt.
I have faith in you, [L]...
```

---

## Analysis & Suggestions

### Strengths

1. **Kydrog's characterization** - Pirate speech pattern is distinctive ("ye," "lad," "me trap")
2. **Mirror world concept** - Owl's dialogue establishes it poetically
3. **Shared fate theme** - "Just as I was" creates link between hero and villain
4. **Clear objectives** - Maku Tree gives explicit guidance

### Areas for Improvement

#### 1. Opening Scene (High Priority)

**Current:** Generic Oracle wake-up
**Suggestion:** Dream sequence showing:
- Farore calling for help
- Brief flash of Kydrog's silhouette
- Glimpse of the Eon Abyss

This would:
- Hook player immediately
- Establish Farore connection before meeting her
- Foreshadow the Abyss

#### 2. Kydrog's Backstory (Medium Priority)

**Current:** "Cast away to the Eon Abyss, just as I was" - only hint
**Suggestion:** Add a line revealing he was once a hero:

```
Prepare yourself, lad! Ye're
about to be cast away to the
Eon Abyss, just as I was.

I was a hero once, ye know.
The Abyss... it changes ye.
Hehehe!
```

Or save this for later revelation via Sea Zora / Gossip Stones.

#### 3. Owl Dialogue Expansion (Low Priority)

**Current:** Good atmospheric setup
**Suggestion:** Add hint about the Shrines:

```
Deep in the Forest of Dreams,
where echoes of the old
guardians still linger...

Three Shrines mark the spots
where brave souls gave all
to seal away the darkness.
```

#### 4. Maku Tree First Meeting (Medium Priority)

**Current:** Jumps straight to exposition
**Suggestion:** Add acknowledgment of what just happened:

```
Ah, [L]!
Thank the Goddesses you are
alright. I feared the worst.

Kydrog's power grows. He cast
you into the Abyss itself...
yet you returned. Remarkable.
```

---

## Code Reference

### Key Sprites
| Sprite | File | Role |
|--------|------|------|
| `Sprite_KydrogNPC` | `Sprites/Bosses/kydrog.asm` | Intro cutscene Kydrog |
| `Sprite_EonOwl` | `Sprites/NPCs/eon_owl.asm` | Eon Abyss guide + Kaepora |
| `Sprite_MakuTree` | `Sprites/NPCs/maku_tree.asm` | Quest hub NPC |
| `Impa` | `Sprites/NPCs/impa.asm` | Follower/guide |

### Key Messages
| ID | NPC | Purpose |
|----|-----|---------|
| `0x20` | Maku Tree | First meeting, main exposition |
| `0x21` | Kydrog | Intro encounter, banishment |
| `0x22` | Maku Tree | Revisit guidance |
| `0xE6` | Eon Owl | Abyss introduction, Moon Pearl |

### Key Flags
| Address | Flag | Meaning |
|---------|------|---------|
| `$7EF300` | `#$01` | Kydrog/Farore removed from Maku area |
| `$7EF3C6` | `#$04` | Post-Kydrog encounter |
| `$7EF3D4` | `MakuTreeQuest` | Met Maku Tree |
| `$7EF3D6` | `OOSPROG` | Main story progress |

---

## Connection to Lore Documents

### Aligns With Story Bible:
- ✅ Kydrog as Pirate King
- ✅ Eon Abyss as mirror dimension
- ✅ Farore's connection to Kalyxo
- ✅ Triforce essences as quest items
- ✅ "Cast away" supporting fallen hero backstory

### Needs Story Bible Update:
- [ ] Document "Shrine of Origins" and Minish Cap ability
- [ ] Clarify Moon Pearl location in pyramid
- [ ] Document exact route: 0x40 → 0x50 → 0x60 → 0x6A → 0x2A

### Gossip Stone Integration:
Many of the Gossip Stone texts align with this intro:
- GS05 (Forest of Dreams): "The Pirate King was not always dead. He came here as you did—sword drawn, heart full of purpose."
- GS11 (Eon Abyss Beach): "This is the world that waits when hope abandons the living."

---

## User Feedback (2026-01-22)

### Confirmed Directions:
1. **Opening dream sequence** - Approved for implementation
2. **Kydrog hero dialogue** - Save for late-game reveal (via Sea Zora, etc.)
3. **Shrine introduction** - Should come LATER, after Kalyxo Castle prison escape and Meadow Blade retrieval
4. **Maku acknowledgment** - Should recognize Link's escape from Abyss

### Game Structure - Two Acts

**Act 1: Traditional Zelda (D1-D3)**
- First 3 dungeons in classic style
- Meadow Blade obtained around D3 (Kalyxo Castle)
- Eon Abyss is meant to be escaped quickly
- Focus on establishing Kalyxo Island

**Act 2: Elevated Stakes (D4-D8 + Shrines)**
- Story elements elevate importance of Eon Abyss
- Shrine of Wisdom → Flippers
- Zora Temple conflict plot
- Deeper exploration of the Abyss
- Final 4 dungeons with more complex narrative

### Minish Cap Mechanic (Shrine of Origins)

**Current Implementation:**
- Link can shrink into Minish form
- R button on stumps to transform
- Special collision tiles only passable in Minish form
- Cannot lift objects while in Minish form

**Planned Expansion:**
- Dungeon objects with Minish collision type
- More gameplay integration

---

## Next Steps

1. [x] Opening dream sequence - APPROVED
2. [x] Review attract scene code - **RESOLVED: Build errors in `Util/item_cheat.asm` fixed (2026-01-22)**
   - Fixed missing space in `!REINIT_ROOMCACHE` define
   - Fixed PEA syntax (removed parentheses)
   - Fixed branch out of bounds (BRA→JMP)
   - Fixed STZ.l (doesn't support long addressing mode)
3. [x] Kydrog hero hint - Keep for late-game reveal
4. [x] Document Minish Cap ability - Basic doc above, expand later
