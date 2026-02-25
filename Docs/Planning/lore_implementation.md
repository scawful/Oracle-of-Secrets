# Oracle of Secrets - Lore Implementation Tracker

**Last Updated:** 2026-02-12
**Reference:** `Docs/World/Lore/story_bible.md`, `Docs/World/Lore/gossip_stones.md`

---

## Dialogue Catalogue Summary

**Source:** `Core/messages.org` (1876 lines, ~190 messages)

### Existing Lore-Aligned Dialogue

These messages already support our story bible:

| ID | NPC/Context | Key Lore | Status |
|----|-------------|----------|--------|
| `1AD` | Sea Zora | Kydrog as fallen hero, Meadow Blade, Ganondorf | ✅ Aligned |
| `136` | Maiden (Glacia) | Twinrova's failed Ganon revival → joined Kydrog | ✅ Aligned |
| `9C` | Old Man Mountain | "Sent to this place by evil witch Twinrova" | ✅ Aligned |
| `70` | Meadow Blade | Farore's spirit bound within | ✅ Aligned |
| `21` | Kydrog Intro | "Cast away to the Eon Abyss, just as I was" | ✅ Aligned |
| `E6` | Eon Abyss Owl | "This realm is a mirror, a reflection" | ✅ Aligned |
| `112-115` | Attract Scene | Backstory, Kydrog sealed ages ago | ✅ Aligned |
| `10E` | Ranch Girl | Cursed into Cucoo by (implied Twinrova) | ✅ Aligned |
| `123` | Twinrova Boss | "Foolish boy! You've stumbled into my trap!" | ⚠️ Basic |

### Dialogue Needing Updates/Expansion

| ID | Current | Proposed Change | Priority |
|----|---------|-----------------|----------|
| `1AD` | "ambition clouded his heart" | Consider: died heroically, THEN corrupted | Low |
| `123` | Generic Twinrova taunt | Add references to "our new master" / failed Ganon revival | Medium |
| `70` | Meadow Blade text | Could hint at original owner | Low |
| NEW | Gossip Stones (21) | Need message IDs assigned | High |

---

## Implementation Tasks

### Tier 1: Critical Path

| Task | Description | Files | Est. Messages |
|------|-------------|-------|---------------|
| **Dream Sequences** | 6 scripted dream cutscenes | `attract_scenes.asm`, `messages.org` | 6-12 |
| **Twinrova D5 Dialogue** | Pre/post boss text with lore hints | `messages.org` | 3-5 |

### Tier 2: High Value

| Task | Description | Files | Est. Messages |
|------|-------------|-------|---------------|
| **Gossip Stones** | 21 stone texts (already written) | `messages.org`, sprite placement | 21 |
| **Reactive NPCs** | Mayor/Witch/Library post-D3/D6 variants | `messages.org` | 6-10 |

### Tier 3: Polish

| Task | Description | Files | Est. Messages |
|------|-------------|-------|---------------|
| **Kydrog Boss Dialogue** | D7 pre-fight, reference fallen hero past | `messages.org` | 2-3 |
| **Kydreeok Final** | Death scene, possible redemption moment | `messages.org` | 1-2 |
| **Item Descriptions** | Enhance Meadow Blade, essence texts | `messages.org` | 7 |

---

## Message ID Allocation

### Current Usage (Observed)
- `0F-15`: Tutorial Skeleton Guards
- `19-2F`: Main NPCs (Elder, Impa, Maku Tree, Kydrog)
- `30-6F`: Items, hints, misc
- `70-9F`: Meadow Blade, masks, Old Man Mountain
- `A0-CF`: Village NPCs, Zora Temple signs
- `D0-FF`: Swordsmith, Happy Mask Salesman, hints
- `100-13F`: Zora Baby, Ranch Girl, attract scenes, maidens
- `190-1AF`: Tingle, Librarian, Sea Zora lore

### Proposed Reservations (Updated 2026-02-12)

**Expanded bank currently ends at 0x1BB.** Ranges below require bank extension. Verify capacity before committing.

| Range | Purpose | Count | Status |
|-------|---------|-------|--------|
| `1BC-1D4` | *(gap — available)* | 25 | Unassigned |
| `1D5-1D8` | Windmill Guy (Song of Storms chain) | 4 | Assigned to Gemini Task 1 |
| `1D9-1DF` | *(gap — available)* | 7 | Unassigned |
| `1E0-1E4` | Goron Elder (Rock Meat quest) | 5 | Assigned to Gemini Task 1 |
| `1E5-1E7` | River Zora Elder (Reconciliation) | 3 | Assigned to Gemini Task 1 |
| `1E8-1EA` | Bean Vendor (Magic Bean quest) | 3 | Assigned to Gemini Task 1 |
| `1EB-1EF` | Cartographer (Seashell quest) | 5 | Assigned to Gemini Task 1 |
| `1F0-1F9` | Koroks (10 unique lore fragments) | 10 | Assigned to Gemini Task 1 |
| `1FA-1FF` | *(gap — available)* | 6 | Unassigned |
| `200-214` | Gossip Stones (GS01-GS21) | 21 | Text written, placement blocked |
| `220-224` | Dream Sequences (3 core) | 5 | Designed, not implemented |
| `225-229` | Dream Sequences (2 bonus) | 5 | Designed, lower priority |
| `230-23F` | Reactive NPC variants | 16 | Planned |
| `240-24F` | Twinrova expanded dialogue | 16 | Draft exists (0x240-0x241) |

**Gemini dialogue bundles (2026-02-12):** ~50 messages across 7 JSON files. Codex building batch import to load them. See `scratchpad/gemini_prompts_2026-02-12.md`.

**Maiden identity upgrades** reuse existing IDs: 0x132 (D1), 0x133 (D2), 0x137 (D6). Gemini drafting replacement text.

---

## NPC → Message ID Map

### Main Story NPCs
| NPC | Message IDs | Location |
|-----|-------------|----------|
| Maku Tree | `20`, `22` | Hall of Secrets |
| Impa | `1E`, `25`, `26`, `27`, `35`, `36` | Hall of Secrets, Telepathic |
| Kydrog | `21`, `3A` | Intro, Bounty Sign |
| Farore | `BF`, `70`, `138` | Ship, Meadow Blade, Post-rescue |
| Twinrova | `122`, `123` | Maiden disguise, Boss |
| Village Elder | `19` | Village |

### Side Quest NPCs
| NPC | Message IDs | Quest |
|-----|-------------|-------|
| Old Man Mountain | `99`-`A0` | Goldstar escort |
| Ranch Girl | `10E` | Cucoo curse |
| Happy Mask Salesman | `E5`, `E9`, `7F`, `81`, `82` | Masks, Ocarina hint |
| Vasu | `A9`-`AD` | Ring Shop |
| Zora Baby | `108`-`10C` | Temple follower |
| Sea Zora | `1AD`-`1AF` | Kydrog lore, ring, quest hint |

### Fortune Teller
Uses `[P:01]` format, located around lines 742-818 in messages.org.

---

## Gossip Stone Implementation

### Status: BLOCKED - Graphics Constraints
**Issue:** Gossip Stone sprite only exists on one map graphic sheet and is not in global graphics. Cannot place stones across different areas without major graphics work.

### Alternative Delivery Methods

| Method | Pros | Cons | Effort |
|--------|------|------|--------|
| **Telepathic Signs/Tablets** | Reuse existing sign system | Less atmospheric | Low |
| **NPC Dialogue Variants** | Natural, progression-based | Limited placement | Medium |
| **Owl Statues** | Zelda tradition, can place anywhere | Need new sprite | Medium |
| **Fortune Teller Expansion** | Already exists, cryptic style fits | Single location | Low |

### Recommended Approach
1. Use **existing NPCs** (Sea Zora, Fortune Teller) for major lore
2. Add **sign/tablet hints** near dungeon entrances
3. Consider **owl statue sprite** for Eon Abyss (fits corrupted theme)

### Original Sprite Requirements (if unblocked)
- Need Gossip Stone sprite placed in overworld/dungeon
- Activation: Always active or progression-gated (TBD)
- Interaction: Standard NPC talk trigger

### Message Format
```
** 200 - Gossip Stone (Mushroom Grotto)
We remember when these woods
[2]whispered only of growth...
[3]before the shadow learned our names.
```

### Locations Checklist
| ID | Location | Overworld/Dungeon | Placed |
|----|----------|-------------------|--------|
| GS01 | Near D1 entrance | Overworld | [ ] |
| GS02 | Wayward Village | Overworld | [ ] |
| GS03 | Zora Sanctuary | Overworld | [ ] |
| GS04 | Mount Snowpeak | Overworld | [ ] |
| GS05 | Forest of Dreams | Abyss | [ ] |
| GS06 | Kalyxo Castle exterior | Overworld | [ ] |
| GS07 | Korok Cove | Overworld | [ ] |
| GS08 | Near S1 | Abyss | [ ] |
| GS09 | Near S2 | Abyss | [ ] |
| GS10 | Near S3 | Abyss | [ ] |
| GS11 | Eon Abyss beach | Abyss | [ ] |
| GS12 | Hall of Secrets | Interior | [ ] |
| GS13 | Near Ranch | Overworld | [ ] |
| GS14 | Goron area | Overworld | [ ] |
| GS15 | Dragon Ship approach | Overworld | [ ] |
| GS16 | Temporal Pyramid ext | Abyss | [ ] |
| GS17 | Hidden Grotto | Secret | [ ] |
| GS18 | Seashell Coast | Overworld | [ ] |
| GS19 | Glacia Estate approach | Overworld | [ ] |
| GS20 | Temporal Pyramid int | Dungeon | [ ] |
| GS21 | Kalyxo Castle int | Dungeon | [ ] |

---

## Dream Sequence Implementation

### Infrastructure
- Existing: `Dungeons/attract_scenes.asm`
- Existing: `Core/messages.org` attract format (`[SPD:00][C:07][S:03][W:02][IMG]`)

### Dream Scripts Needed (Aligned with narrative_design_master_plan.md)

**3 Core Dreams (narrative-critical, no skip):**

| Dream | Trigger | Content | Message IDs | Complexity |
|-------|---------|---------|-------------|------------|
| **Dream 1: The Sealing War** | Post-D2 | Ancient Soldier witnesses Kydrog's fall | `220`-`222` | HIGH — custom sprite |
| **Dream 2: Ranch Girl's Secret** | Post-D5 | Twinrova's curse on Ranch Girl revealed | `223`-`225` | MEDIUM — HDMA effects |
| **Dream 3: Observatory Vision** | Sky Islands | Ganondorf's imprisonment, 3-phase weakness | `226`-`228` | **LOW — implement first** |

**2 Bonus Dreams (optional, lower priority):**

| Dream | Trigger | Content | Message IDs | Complexity |
|-------|---------|---------|-------------|------------|
| **Dream 4: The Reflection** | Post-D3 | Mirror shows Kydrog as knight → skeleton | `229`-`22A` | MEDIUM |
| **Dream 5: The Giant's Message** | Post-D6 | Shadowed silhouette warns of seal breaking | `22B`-`22C` | LOW |

**Implementation order:** Dream 3 first (static images + text, highest narrative payoff), then Dream 1 and 2. Bonus dreams are post-RC polish.

**SRAM tracking:** `$7EF410` bitfield (bits 0-4, one per dream).

---

## Twinrova Dialogue Expansion

### Current (ID 123)
```
Hohoho! Foolish boy!
You've stumbled right into my
trap! Prepare to die!
```

### Proposed Pre-Fight (ID 240)
```
Hohoho! Another hero falls into
our web! Do you know how many
we've broken, little boy?[K]
Our first master... failed us.
The beast we raised was incomplete.
But this one... this Kydrog...[K]
He doesn't even know he serves
a greater power! And neither
will you, when we're done![K]
```

### Proposed Post-Fight (ID 241)
```
Grrr... You haven't won, boy!
We've failed before, and we
rose again! We always do![K]
The King of Thieves waits below,
patient as stone. When Kydrog
breaks the final seal...[K]
...you'll wish you'd never
set foot on this island!
```

---

## Open Questions

1. **Gossip Stone delivery method** — Sprite only on one map sheet (graphics blocker). Options: telepathic signs, owl statues, fortune teller expansion. See "Alternative Delivery Methods" above.
2. **Kydrog's living name** — Finalized as unnamed ("lost to time") per narrative_design_master_plan.md
3. **Expanded message bank capacity** — Current bank ends at 0x1BB. Ranges 0x1BC-0x24F proposed but **capacity not verified**. Need to check how many expanded messages the bank can hold before committing IDs.
4. **Windmill Guy blocker** — Messages 0x1D5-0x1D8 referenced in `windmill_guy.asm` but don't exist. Bank extension needed.

---

## Next Actions (Updated 2026-02-12)

### In Progress (Agent Work)
- [x] Write Gossip Stone messages — text complete in `gossip_stones.md`
- [ ] **Codex:** Message batch import/export in yaze — enables bulk dialogue loading
- [ ] **Codex:** Object dimension wiring in dungeon editor — unblocks room editing
- [ ] **Gemini:** Draft 50+ NPC dialogue messages in `yaze-message-bundle` v1 JSON
- [ ] **Gemini:** 32-char wrap validation on all drafted dialogue

### Ready to Do (Unblocked)
- [ ] Verify expanded message bank capacity (how far past 0x1BB can we go?)
- [ ] Expand Twinrova dialogue (pre/post D5 boss) — draft exists at 0x240-0x241
- [ ] Update `messages.org` with reserved ID ranges

### Blocked
- [ ] Place Gossip Stone sprites — blocked on graphics sheet constraint
- [ ] Dream sequence ASM — blocked on attract_scenes.asm format research
- [ ] NPC dialogue loading — blocked on Codex batch import feature
- [ ] Runtime test Maku Tree — blocked on Mesen2 SRAM tooling

---

## Reference Commands

```bash
# Search messages
/Users/scawful/src/hobby/yaze/build/bin/z3ed message-search --rom=Roms/oos168x.sfc --query="Kydrog"

# Read specific message (if implemented)
/Users/scawful/src/hobby/yaze/build/bin/z3ed message-read --rom=Roms/oos168x.sfc --id=0x1AD

# Grep messages.org
grep -n "Twinrova\|Kydrog\|Ganon" Core/messages.org
```
