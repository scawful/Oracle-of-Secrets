# Oracle of Secrets Release Roadmap

**Created**: December 2025
**Status**: Active Development
**Target**: Full Release with complete narrative content

---

## Project Status Summary

**Current State**: ~75% complete for full release
- Core game loop functional: 7 dungeons + 3 shrines playable
- 60+ custom sprites implemented
- Dialogue system with ~190 messages
- Menu system recently refactored and stable
- Time system recently refactored and stable

**Major Gaps for Full Release**:
- 0/11 dungeon maps
- 0/6 dream sequences (CRITICAL for narrative)
- Journal system stubbed but not functional
- Kydrog boss incomplete (1/3)
- Kydreeok boss needs polish (0/9)
- Several ZSOW integration bugs
- Prison escape sequence not started (0/4)
- 4/6 consumable items incomplete

---

## Phase 1: System Stability & Blockers

*Priority: HIGH - These tasks unblock other work*

### 1.1 ZSOW Integration Fixes

- [ ] **Fix ZSOW vs. Lost Woods Conflict** (Priority A)
  - File: `Overworld/lost_woods.asm`, `ZSCustomOverworld.asm`
  - Task: Refactor into JSL-callable `LostWoods_PuzzleHandler`
  - Implementation: Modify `OverworldHandleTransitions` to check if area is Lost Woods (`#$29`) and call handler

- [ ] **Complete ZSOW vs. Song of Storms** (Priority A, Active)
  - File: `Items/ocarina.asm`, `Overworld/overlays.asm`
  - Blocks: Zora Sanctuary waterfall event

### 1.2 Document Dialogue System

- [ ] **Create dialogue system documentation** (Priority C)
  - File: `Core/message.asm`, `Core/messages.org`
  - Blocks: Garo NPC, reactive dialogue system
  - Critical for Phase 3 narrative implementation
  - Document: Message ID format, control codes, branching dialogue

### 1.3 Verify Active Work

- [ ] **Emulator verify Ice Block collision fixes** (Active)
- [ ] **Emulator verify Ice Block sprite refactor** (Active)

---

## Phase 2: Core Content Completion

*Priority: HIGH - Delivers visible progress on main quests*

### 2.1 Quest Completion

**Zora Sanctuary Questline** (2/3 complete)
- [ ] Implement waterfall opening with Song of Storms
  - Files: `Items/ocarina.asm`, `Overworld/overlays.asm`
  - Depends on: Phase 1.1 ZSOW fixes

**Goron Mines Quest** (2/4 complete)
- [ ] Implement Garo NPC (depends on dialogue docs from Phase 1.2)
- [ ] Add Gossip Stones with shrine/lore hints

**Tail Palace Kiki Quest** (1/2 complete)
- [ ] Modify Kiki follower logic to require Bananas instead of Rupees
  - File: `Sprites/NPCs/` (Kiki follower logic)

**Zora Temple Tasks** (0/2 complete)
- [ ] Fix Zora Baby follower sprite transitions to standard sprite
- [ ] Fix water gate collision issues

### 2.2 Consumable Items (2/6 complete)

- File: `Items/all_items.asm` (Magic Bag jump table)
- [X] Banana (restores health)
- [X] Rock Meat
- [ ] Pineapple effect
- [ ] Seashells effect
- [ ] Honeycombs effect
- [ ] Deku Sticks effect

---

## Phase 3: Narrative Implementation

*Priority: CRITICAL - User specified this makes the game special*

### 3.1 Dream Sequences (0/6)

- Existing infrastructure: `Dungeons/attract_scenes.asm`
- Use Maple Dream Hut system (`Core/messages.org:1769-1844`)
- Dreams flag location: `$7EF410`

| Dream | Trigger | Purpose | Status |
|-------|---------|---------|--------|
| Deku Business Scrub | Post-pendant | Deku lore | [ ] |
| Twinrova Ranch Girl | Post-D5 Glacia | Ranch Girl lineage reveal | [ ] |
| Hyrule Castle | Song of Time | Historical context | [ ] |
| River Zora King | Zora progression | Zora conflict backstory | [ ] |
| Kydrog Sealing | Major milestone | Antagonist origin | [ ] |
| Mine Collapse | Goron Mines | Mining disaster lore | [ ] |

### 3.2 Kalyxo Castle Prison Sequence (0/4)

- Triggers after obtaining Meadow Blade
- [ ] Implement Overlord logic to swarm player with guards, trigger prison warp
- [ ] Implement guard AI using `probe_ref.asm`
  - Some guards: "reset on sight" behavior
  - Other guards: give chase
- [ ] Design prison escape path (requires Minish form)
- [ ] Create custom Minish-only pathway dungeon objects

### 3.3 Reactive NPC Dialogue

Per `Docs/World/Features/Narrative_Improvements.md`:
- Goal: 3-5 NPCs checking OOSPROG flags
- Key NPCs: Mayor, Potion Shop Witch, Library NPC
- Triggers: After D3 (Kalyxo Castle) and D6 (Goron Mines)

**Example Implementation**:
- Mayor comments on "strange lights vanishing from the castle" after D3
- Use existing OOSPROG ($7EF3D6) bitfield system

### 3.4 Gossip Stone Network

- Requires Mask of Truth to activate
- Provides hints for side-quests and heart pieces
- Lore: Petrified observers from "Age of Secrets"

---

## Phase 4: Boss Enhancement

### 4.1 Kydrog Boss (1/3) - PRIMARY FOCUS

- File: `Sprites/Bosses/kydrog_boss.asm`
- Current: Tracks offspring sprites for dynamic spawns
- Hardcoded activation trigger at Y-position $08C8

Tasks:
- [ ] Improve movement AI
- [ ] Add Phase 2 to the fight
- [ ] Create cinematic opening cutscene
  - Should recognize "Scent of Farore" (connects to intro)
- [ ] Create ending cutscene
  - HDMA wave transformation sequence to Kydreeok form

### 4.2 Kydreeok Boss (0/9) - SECONDARY

- Files: `Sprites/Bosses/kydreeok.asm`, `kydreeok_v2.asm`, `kydreeok_head.asm`
- Note: v2 refactor in progress with dynamic chain physics

Prioritize AFTER Kydrog complete:
- [ ] Improved fireball attack patterns (targeted shots, spreads)
- [ ] Neck stretch lunge attack (Chain Chomp style)
- [ ] Spin attack with stretched necks shooting fire
- [ ] Bone-throwing attack for second phase
- [ ] Head detachment/float behavior (instead of popping back)
- [ ] "Bullet hell" phase with retracted heads
- [ ] Modify damage check to prevent electrocution frustration
- [ ] Pre-fight transformation cutscene (ties to Kydrog ending)
- [ ] Improve head/neck rotation visuals

### 4.3 Vaati/Shrine of Courage Boss (Lower Priority)

- Goal: Move beyond simple Vitreous reskin
- Reference: "Advanced Arrghus" custom boss logic

---

## Phase 5: Polish & Presentation

### 5.1 Dungeon Maps (0/11)

- Tool: yaze dungeon map editor

| Dungeon | Status |
|---------|--------|
| D1: Mushroom Grotto | [ ] |
| D2: Tail Palace | [ ] |
| D3: Kalyxo Castle | [ ] |
| D4: Zora Temple | [ ] |
| D5: Glacia Estate | [ ] |
| D6: Goron Mines | [ ] |
| D7: Dragon Ship | [ ] |
| D8: Fortress of Secrets | [ ] |
| S1: Shrine of Wisdom | [ ] |
| S2: Shrine of Power | [ ] |
| S3: Shrine of Courage | [ ] |

### 5.2 Journal System

- File: `Menu/menu_journal.asm` (stub exists)
- [ ] Design journal UI
- [ ] SRAM flag tracking for quests/events
- [ ] Write text entries for each major event

### 5.3 Glacia Estate Polish (0/4)

- [ ] Ice block collision improvements (ties to Phase 1 verification)
- [ ] Enemy positioning/tuning for better challenge flow
- [ ] Exterior GFX improvements
- [ ] Visual indicator (crack) for pushable block in ice puzzle

### 5.4 Sprite Quality Pass

- [ ] Goriya: Add chase and head detection animation (`goriya.asm:163`)
- [ ] Darknut: Setup parrying sword gfx (`darknut.asm:70`)
- [ ] General AI/behavior polish pass

### 5.5 Additional Polish

- [ ] Shrine of Power: Fix lava pit corner tile collision
- [ ] Dragon Ship: Flesh out extended section ideas
- [ ] Shrine of Wisdom: Add warp zones, magic drops, hints, treasures
- [ ] Custom End Credits (via yaze C++ editor)

---

## Phase 6: Final Integration & Testing

### 6.1 System Verification

- [ ] Full playthrough test
- [ ] SRAM flag progression verification
- [ ] All quest paths functional
- [ ] All dungeons completable with maps

### 6.2 Optional Refactoring (Opportunistic)

These can be done alongside other work when touching related code:
- Minecart system cleanup
- Patch centralization to `Core/patches.asm`
- Struct directive adoption
- Table directive conversions

---

## Critical Files Reference

| System | Key Files |
|--------|-----------|
| Dialogue | `Core/message.asm`, `Core/messages.org` |
| Cutscenes | `Dungeons/attract_scenes.asm` |
| Story Flags | OOSPROG ($7EF3D6), OOSPROG2 ($7EF3C6) |
| Dreams | Dreams flag ($7EF410) |
| Game State | GameState ($7EF3C5) |
| Bosses | `Sprites/Bosses/kydrog_boss.asm`, `kydreeok.asm` |
| ZSOW | `ZSCustomOverworld.asm` |
| Ocarina | `Items/ocarina.asm` |
| Journal | `Menu/menu_journal.asm` |
| Overlays | `Overworld/overlays.asm` |
| Task Tracker | `oracle.org` |

---

## SRAM Flag Reference

### OOSPROG ($7EF3D6)
Bitfield: `.fmp h.i.`
- `f` = Fortress of Secrets
- `m` = Master Sword acquired
- `p` = Pendant quest progress
- `h` = Hall of Secrets visited
- `i` = Intro complete, Maku Tree met

### OOSPROG2 ($7EF3C6)
Bitfield: `.fbh .zsu`
- `u` = Uncle visited
- `s` = Priest visited in sanctuary
- `z` = Zelda brought to sanctuary
- `h` = Uncle left house
- `b` = Book of Mudora obtained
- `f` = Fortune teller flag

### Dreams ($7EF410)
Bitfield: `.dts fwpb`
- Tracks dream sequence completion

---

## Notes

- **Stub bosses** (King Dodongo, Arrghus): Keep as-is - they're vanilla address modifications
- **Technical debt**: Handle opportunistically alongside feature work
- **Music system**: Low priority, existing system is functional
- See `oracle.org` for detailed task tracking and priority levels
