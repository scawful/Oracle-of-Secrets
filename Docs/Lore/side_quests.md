# Oracle of Secrets - Side Quest Bible

**Last Updated:** 2026-01-23
**Status:** Active Development

This document catalogs all side quests, their narrative purpose, and implementation details.

---

## Overview

Side quests in Oracle of Secrets serve three purposes:
1. **World-building:** Reveal lore and character depth
2. **Reward progression:** Heart pieces, items, upgrades
3. **Thematic reinforcement:** Echo main story themes

Side quests are generally **not required** for main progression but enrich the experience.

---

## Trading Sequences

### The Lost Voice (Ranch Girl Quest)

**Gossip Stone Hint (GS02):**
> "A girl lost her voice at the ranch. Seek the forest's gift, the witch's craft, and the spark that wakes the silent."

#### Narrative Purpose
The Ranch Girl has lost her voice—a curse or trauma connected to Twinrova (revealed in Dream Sequence 2). Helping her restore her voice foreshadows the deeper connection and builds investment before the revelation.

#### Quest Flow

| Step | Location | Item Given | Item Received | Notes |
|------|----------|------------|---------------|-------|
| 1 | Mushroom Grotto (exterior) | — | Mushroom | Found near withered toadstool |
| 2 | Witch's Hut | Mushroom | Magic Powder | Syrup brews it for you |
| 3 | Ranch | Magic Powder | ??? | Use on silent Ranch Girl |
| 4 | Ranch (cont.) | ??? | Ocarina | She thanks you with song |

#### Trigger Conditions
- **Available after:** D1 (Mushroom Grotto cleared)
- **Completed by:** Playing Song of Healing with Ocarina (optional finale)

#### Story Significance
- Ranch Girl's silence hints at Twinrova's influence
- Dream Sequence 2 reveals the full truth
- Ocarina becomes key item for other quests

#### Rewards
- **Ocarina:** Required for Song of Storms, Song of Healing usage
- **Heart Piece:** Given after playing Song of Healing for her (optional)

#### Related Files
- `Sprites/NPCs/ranch_girl.asm`
- `Core/messages.org`: Message IDs for quest dialogue

---

### The Lonely Cartographer

**Gossip Stone Hint (GS18):**
> "The sea remembers what the land forgets. Gather its whispers, shell by shell. A cartographer trades in secrets."

#### Narrative Purpose
A reclusive map-maker lives on the coast, obsessed with documenting Kalyxo's hidden places. He trades map markers for seashells—the sea's memories of locations.

#### Quest Flow

| Seashells | Reward |
|-----------|--------|
| 5 | Secret #1 marked on map |
| 10 | Secret #2 marked on map |
| 15 | Secret #3 marked on map |
| 20 | Heart Piece |
| 30 | Item upgrade (TBD) |

#### Seashell Locations (20 total - TBD)
- Beach areas (obvious)
- Buried in sand (dig spots)
- Underwater (Zora Mask required)
- Enemy drops (rare)
- Bombable walls hiding caches

#### Story Significance
- Reinforces exploration theme
- Cartographer has lore dialogue about "old Kalyxo"
- Optional world-building

#### Related Files
- `Sprites/NPCs/cartographer.asm` (TBD)
- `Core/sram.asm`: Seashell counter

---

## Collection Quests

### Goron Rock Meat

**Gossip Stone Hint (GS14):**
> "The mountain dwellers feast in silence. Five offerings open the stone door. Seek the meat that feeds the earth."

#### Narrative Purpose
The Gorons have retreated from outside contact since the Hylian occupation disrupted their trade with the Zoras. To earn their trust, Link must provide a traditional offering of Rock Meat—proving he understands and respects their ways.

**Thematic parallel:** Like the Zora conflict, the Goron isolation was caused by outside forces. Link restores both relationships through action.

#### Quest Flow

| Step | Action | Location |
|------|--------|----------|
| 1 | Speak to Goron Elder | Goron Mine entrance |
| 2 | Learn about Rock Meat tradition | — |
| 3 | Collect Rock Meat #1 | Cave near Wayward Village |
| 4 | Collect Rock Meat #2 | Mountain trail (bombable wall) |
| 5 | Collect Rock Meat #3 | Korok Cove underground |
| 6 | Collect Rock Meat #4 | Eon Abyss rocky area |
| 7 | Return to Elder with 4 | Mine entrance opens |
| 8 | Complete D6 (Goron Mines) | Obtain Hammer |
| 9 | Collect Rock Meat #5 | Hidden grotto (Hammer required) |
| 10 | Return to Elder with 5 | Full alliance restored |

#### Pre-Dungeon vs Post-Dungeon
- **4 Rock Meat** = Access to D6
- **5 Rock Meat** = Full rewards (requires Hammer from D6, creates backtrack)

#### Rewards
- **D6 Access:** Primary reward
- **Goron Tunic:** Heat resistance (given with 5th meat)
- **Goron Dialogue:** Updates across the island

#### Story Significance
- Restores Goron-Kalyxian relations
- Parallels Zora reconciliation arc
- Demonstrates Link proves himself through deeds

#### Related Files
- `Sprites/NPCs/goron.asm`
- `Core/sram.asm`: `RockMeat` counter at $7EF350

---

### Korok Hide and Seek

**Gossip Stone Hint (GS07):**
> "The small ones play where roots drink deep. Count them if you can, seeker. They reward those with patient eyes."

#### Narrative Purpose
The Koroks are ancient forest spirits who remember the Age of Secrets. They've hidden throughout East Kalyxo and Korok Cove, playing a game that tests observation and patience. Finding them all reveals fragments of forgotten lore.

#### Quest Flow

| Koroks Found | Reward |
|--------------|--------|
| 1-4 | 5-20 rupees each |
| 5 | Heart Piece |
| 10 | Heart Piece |

#### Korok Hiding Spots (10 total)

| # | Location | Method to Find |
|---|----------|----------------|
| 1 | Korok Cove tree | Roll into tree |
| 2 | Korok Cove pond | Dive underwater |
| 3 | East Kalyxo rock | Hammer smash |
| 4 | East Kalyxo tree | Roll into tree |
| 5 | Behind waterfall | Walk through |
| 6 | Buried in clearing | Dig spot |
| 7 | Under hammer rock | Hammer smash |
| 8 | Underwater passage | Zora Mask dive |
| 9 | Environmental puzzle | Solve it |
| 10 | Hidden cave | Bomb wall |

#### Korok Dialogue
Each Korok shares a fragment when found:
- Korok 1: "Yahaha! The trees remember when pirates wore scales..."
- Korok 5: "The old king sleeps beneath the mountain of fire..."
- Korok 10: "We watched the hero fall. We watched the knight rise. Same soul, different shadow..."

#### Access Requirements
- **Korok Cove:** Always accessible
- **East Kalyxo:** Hammer required (post-D6)

#### Related Files
- `Sprites/NPCs/korok.asm`
- `Core/sram.asm`: Korok found bitfield (TBD)

---

## Mask Quests

### The Withered Deku Scrub (Main Quest Beat)

#### Canonical Notes
- This is a **main quest beat**, not a side quest.
- Location: OW 0x2D (Tail Pond), outside the Mask Salesman shop.
- Timing: between **D1** and **D2**.
- After D1, the mushroom can be traded to the witches east of the castle for Magic Powder / collectible bag.
- Requires Song of Healing; reward is the **Deku Mask**.
- Hints may come from the Mask Salesman or nearby NPCs (design).
- Flags: `SideQuestProg` bit 2, `SideQuestProg2` bit 4; `DekuMaskQuestDone` at $7EF301 (verify in code).

#### Quest Flow (Minimal)

| Step | Action | Result |
|------|--------|--------|
| 1 | Find withered Deku Scrub | Outside the Mask Salesman shop (OW 0x2D Tail Pond) |
| 2 | Play Song of Healing | Spirit freed |
| 3 | Receive Deku Mask | Progression item |

#### Related Files
- `Sprites/NPCs/deku_scrub.asm`
- `Core/sram.asm`: `DekuMaskQuestDone` at $7EF301

---

### The Zora Princess's Gift

#### Narrative Purpose
The Zora Princess in D4 is a trapped spirit—the victim of Kydrog's conspiracy. Playing the Song of Healing frees her and reveals the truth about the Sea Zora/River Zora conflict.

**This is both a main quest beat AND a mask quest.**

#### Quest Flow

| Step | Action | Result |
|------|--------|--------|
| 1 | Complete D4 to boss room | Reach the Princess |
| 2 | Play Song of Healing | Spirit freed, truth revealed |
| 3 | Receive Zora Mask | Transformation ability |

#### Zora Mask Abilities
- Underwater diving
- Fast swimming
- Access underwater areas

#### Story Significance
- Major lore revelation (Kydrog framed River Zoras)
- Unlocks reconciliation path
- Enables exploration of underwater areas

#### Related Files
- `Sprites/NPCs/zora_princess.asm`
- `Core/sram.asm`: `ZoraMaskQuestDone` at $7EF302

---

### The Mask Salesman's Collection

#### Narrative Purpose
The Happy Mask Salesman appears on Kalyxo, seeking masks with "interesting histories." He teaches the Song of Healing and offers masks in trade.

#### Available Masks

| Mask | Source | Effect |
|------|--------|--------|
| Deku Mask | Deku Scrub quest | Small form, hover |
| Zora Mask | D4 Zora Princess | Underwater diving |
| Wolf Mask | Wolfos mini-boss + Song | Dig ability |
| Stone Mask | Purchase (200 rupees) | Enemies ignore you |
| Bunny Hood | Purchase (100 rupees) | Speed boost |

#### Song of Healing Acquisition
- **Location:** Mask Salesman's shop (Tail Pond, OW 0x2D)
- **Trigger:** After obtaining Ocarina
- **Cost:** Free (he's eager to teach it)

#### Story Significance
- Central to transformation mechanics
- Mask Salesman has cryptic dialogue about "souls trapped in forms"
- May hint at Kydrog's own transformation

#### Related Files
- `Sprites/NPCs/mask_salesman.asm`
- `Core/sram.asm`: `SideQuestProg` bit 0 (met salesman), `SideQuestProg2` bit 2 (taught song)

---

## Exploration Quests

### The Old Man's Return

**Gossip Stone Hint (GS04):**
> "An old man waits where fire meets ice. Show him the path he has forgotten. The stars will remember your kindness."

#### Narrative Purpose
An elderly traveler is lost on Mount Snowpeak, unable to find his way home. Guiding him back rewards Link with a Goldstar—a rare collectible.

#### Quest Flow

| Step | Action |
|------|--------|
| 1 | Find Old Man on mountain trail |
| 2 | Lead him through the maze |
| 3 | Avoid enemies (he can't fight) |
| 4 | Reach his cabin |
| 5 | Receive Goldstar |

#### Requirements
- **Available after:** Access to Mount Snowpeak
- **Difficulty:** Escort mission (protect NPC)

#### Rewards
- **Goldstar:** Rare collectible (currency for special items?)
- **Old Man's Gratitude:** Dialogue updates, hints about Glacia Estate

#### Related Files
- `Sprites/NPCs/old_man.asm`
- `Core/sram.asm`: `SideQuestProg` bit 4 (quest active)

---

### The Magic Bean Garden

**Gossip Stone Hint (GS13):**
> "Plant what hungers in barren soil. Call the rain. Summon the swarm. Patience grows what haste cannot."

#### Narrative Purpose
Magic Beans can be planted in special soil patches. With the Song of Storms and bee pollination, they grow into platforms or reveal secrets.

#### Quest Flow

| Step | Action | Result |
|------|--------|--------|
| 1 | Purchase Magic Beans | From Bean Vendor |
| 2 | Find soft soil patch | Various locations |
| 3 | Plant bean | Bean sprout appears |
| 4 | Play Song of Storms | Sprout grows slightly |
| 5 | Use Honeycomb | Attracts bees |
| 6 | Bean fully grows | Platform or secret access |

#### Bean Locations (TBD)
- Near Ranch (leads to heart piece)
- Korok Cove (leads to secret grotto)
- Mountain trail (shortcut to Glacia Estate)
- Eon Abyss (leads to hidden area)

#### Song of Storms Acquisition
- **Location:** Zora Falls (after D4)
- **Trigger:** Use Zora Mask to dive, find tablet
- **Reward:** Song of Storms + Blue Tunic

#### Honeycomb Mechanic
- Find honeycombs in trees (roll into them)
- Using honeycomb on bean sprout = instant growth
- Bypasses waiting mechanic

#### Related Files
- `Sprites/NPCs/bean_vendor.asm`

---

## Alliance Quests

### Zora Reconciliation

**Reference:** Plan file (`jiggly-spinning-newt.md`)

#### Narrative Purpose
After the D4 revelation, Link carries the Princess's truth to the River Zoras in East Kalyxo. This reconciles the two Zora factions and unlocks side content.

#### Quest Flow

| Step | Trigger | Location |
|------|---------|----------|
| 1 | Complete D4 | Zora Temple |
| 2 | Sea Zora dialogue updates | Throughout Kalyxo |
| 3 | Complete D6, get Hammer | Goron Mines |
| 4 | Access East Kalyxo | Via Korok Cove |
| 5 | Reach River Zora Village | East Kalyxo |
| 6 | Deliver Princess's message | Elder's hut |
| 7 | Reconciliation scene | Village center |

#### Intermediate Dialogue (After D4, Before Reconciliation)
Sea Zora NPCs update:
```
The princess... she spoke to you?
We have heard whispers of what
she revealed. Can it be true?

The River Zoras claim they've
been waiting for this proof.
Perhaps we should... listen.
```

#### River Zora Elder's Response
```
So... you carry the Princess's
final words. And her mask...
Show me this evidence, outsider.

[After seeing proof]

...All these years. We mourned
our dead and cursed our kin.
And it was HIM. The Pirate King.

You have given us something
more precious than treasure.
You have given us our names back.
```

#### Rewards
- **River Zora Alliance:** New dialogue, hints
- **Side Content Access:** River Zora quests unlock
- **Heart Piece:** Given by Elder

#### Related Files
- `Sprites/NPCs/zora.asm`
- `Core/sram.asm`: Reconciliation flag (TBD)

---

## Quest Status Summary

| Quest | Giver | Reward | Priority |
|-------|-------|--------|----------|
| Lost Voice | Ranch Girl | Ocarina | High |
| Lonely Cartographer | Cartographer | Map markers | Medium |
| Goron Rock Meat | Goron Elder | D6 access | High |
| Korok Hide and Seek | Koroks | Heart pieces | Medium |
| Deku Scrub's Sorrow | Deku Scrub | Deku Mask | High |
| Zora Princess's Gift | Zora Princess | Zora Mask | High |
| Mask Salesman | Mask Salesman | Masks, Song | High |
| Old Man's Return | Old Man | Goldstar | Low |
| Magic Bean Garden | Bean Vendor | Platforms | Medium |
| Zora Reconciliation | — | Alliance | Medium |

---

## Implementation Checklist

### Dialogue Needed
- [ ] Ranch Girl (silent state, restored state)
- [ ] Cartographer (shell trades)
- [ ] Goron Elder (5 stages of trust)
- [ ] Koroks (10 unique fragments)
- [ ] River Zora Elder (reconciliation)
- [ ] Old Man (escort dialogue)

### SRAM Flags Needed
- [ ] Seashell counter
- [ ] Korok found bitfield
- [ ] Bean planted bitfield
- [ ] Reconciliation flag

### Related Documents
- `dungeon_narratives.md`: Dungeon quest connections
- `gossip_stones.md`: Hint stone text
- `dream_sequences.md`: Story revelations
- `sram_flag_analysis.md`: Flag documentation
