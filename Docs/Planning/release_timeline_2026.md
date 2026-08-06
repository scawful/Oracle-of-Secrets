# Oracle of Secrets — Release Timeline 2026

**Updated:** 2026-06-11 (re-baselined after spring pause; RC/release targets unchanged)
**Current state:** Playable start-to-credits, shipping beta patches to Discord testers
**Target:** Public v1.0 patch (RHDN-quality release)
**Target RC:** October 2026
**Target Release:** November 2026
**Estimated remaining work:** ~160-240 hours (polish + new content) at variable pace

---

## Re-baseline (2026-06-11)

Work paused early May; phases 1-2 are partially done and Phase 3 has not
started. Rather than slip the RC, the remaining Phase 1-2 work is compressed
into a June **stabilization beta** and the dream sequences move to July.
Already landed since the original plan:

- D6 minecart room invariants fixed (carts on stop tiles in 0xA8/0xB8/0xD8/0xDA,
  full 0xB8 track collision) — runtime validation still pending
- Mesen2 socket harness + `dungeon_navigator.py` smoke-test tooling

Cut-line rule: **Phase 4 (Sky Islands + East Kalyxo + Koroks) is the first
thing to move to v1.1 if August slips.** Phases 5-7 dates are protected.

---

## Calendar Milestones

Use this table for calendar sync and milestone review. These are the formal
phase checkpoints from this document.

| Date | Milestone |
|------|-----------|
| June 30, 2026 | Phase 1+2 (compressed): Stabilization Beta — regression confidence, D6 minecart runtime validation, pendant fixes, critical-path dialogue, D7 Farore rescue, boss polish |
| July 31, 2026 | Phase 3: Dream Sequences |
| August 31, 2026 | Phase 4: Sky Islands + East Kalyxo + Koroks (cut-line content) |
| September 30, 2026 | Phase 5: Dialogue & Narrative Polish |
| October 31, 2026 | Phase 6: RC Build + Tester Feedback |
| November 30, 2026 | Phase 7: Release |

Notes:
- One-off playtest sessions are useful calendar events, but they are not part
  of the numbered phase milestone list.
- The June stabilization beta ships first (minecarts + progression validation +
  pendant fixes + placeholder dialogue); D7 rescue and boss polish follow
  within the same checkpoint window.

---

## What v1.0 Includes

The game is already playable start-to-credits. v1.0 adds polish and the remaining content that makes it the complete vision:

### Polish (the game you have now, but better)
1. **Regression confidence** — verify 21 AI-generated commits haven't broken anything
2. **D6 Goron Mines quality** — dungeon works but needs to feel finished
3. **Boss fight polish** — Kydreeok AI, Octoboss camera, telegraphs/fairness
4. **Dialogue & narrative** — NPC progression awareness, placeholder cleanup

### New Content (designed but not yet implemented)
5. **Dream sequences (6)** — scripts written, hooks scaffolded, need full ASM implementation
6. **Sky Islands** — weather mechanics, Observatory vision, Cumuli NPCs
7. **East Kalyxo + Zora reconciliation** — River Zora Village, reconciliation scene
8. **Korok minigame** — sprites exist, need tracking logic and rewards

### Explicitly NOT in v1.0
- Post-game Abyss healing (post-release content update)
- Gossip stone implementation (atmosphere, not progression)
- D8 Voice / Ganondorf name-drop sequence (post-release)
- Trading sequence (already cut)

---

## How This Works (ADHD-Optimized)

No weekly schedule. Instead:

- **Monthly milestones** with yes/no checkpoints
- **Task menus** sorted by energy level — pick what fits your brain today
- **Playtest sessions** framed as play, not work
- **If you miss a month**, tasks roll forward. No guilt.
- **Novelty rotation** — alternate between polish and new content to stay fresh

### Energy Levels

| Energy | Task Type | Time per task |
|--------|-----------|--------------|
| 🟢 **Low focus** | Dialogue writing, Yaze screen edits, doc updates | 15-45 min |
| 🟡 **Medium focus** | Boss tuning, NPC state wiring, Korok tracking, testing | 1-2 hrs |
| 🔴 **High focus** | Dream sequence ASM, Kydreeok AI, weather mechanics, new sprites | 2-4 hrs |

---

## Phase 1: Regression Confidence (re-baselined: June 2026)

**Goal:** Verify every AI-generated commit. Know exactly what's broken vs what's fine.
**Estimated hours:** 20-30

### Task Menu

🟢 **Low Focus**
- [ ] Read through AI commit diff list in `Docs/Analysis/07_ai_lineage_regression.md` (30 min)
- [ ] Document which AI changes testers have already exercised via gameplay (1 hr)
- [ ] Cross-reference Discord bug reports with AI commit dates (1 hr)

🟡 **Medium Focus**
- [ ] Test menu system stability: navigate all pages, open/close rapidly (1 hr)
- [ ] Test Song of Storms persistence across screen transitions (45 min)
- [ ] Test L/R button swap for Hookshot/Goldstar (the explicitly UNTESTED commit) (30 min)
- [ ] Test ice block push direction in all 4 directions (30 min)
- [ ] Test Maku Tree hint cascade at 0, 1, 3, 5, 7 crystals (1 hr)
- [ ] Test water gate: fill, exit room, re-enter, save/reload (1 hr)
- [ ] Run full regression suite: `bash Scripts/Validate/run_regression_tests.sh` (30 min + fix time)

🔴 **High Focus**
- [ ] Verify stack integrity fix (orphaned PHX removal) — 20+ OW transitions (1 hr)
- [ ] Test the 14-file gameplay update (4394bad) — full D1-D4 run (2 hrs)
- [ ] Verify register-width safety fixes (d30fb96) — exercise all 8 modified hooks (2 hrs)
- [ ] Enable each gated feature one at a time, test in isolation (3-4 hrs total)

### Checkpoint (June 30, was April 30)
- Do you have a confident "working" vs "broken" list for all 21 AI commits?
- Is the regression suite green?

---

## Phase 2: D6 + Boss Polish (re-baselined: June 2026)

**Goal:** Goron Mines feels like a real dungeon. Boss fights are fair and fun.
**Estimated hours:** 25-40

### Task Menu

🟢 **Low Focus**
- [ ] Play D6 as a tester — write down every moment that feels off (1 hr)
- [ ] Sketch D6 pacing improvements on paper (30 min)
- [ ] Write improved Goron NPC dialogue for mine entrance/interior (1 hr)
- [ ] Document Octoboss camera offset bug precisely (30 min)

🟡 **Medium Focus**
- [ ] Fix Octoboss camera offset (change hardcoded value) (1-2 hrs)
- [ ] Decide: Lanmola stays or gets cut from D6 (1 hr)
- [ ] Place remaining minecart tracks for D6 (B1/B2 floors) in Yaze (2-3 hrs)
- [ ] Enable minecart feature flags, test track-by-track (2 hrs)
- [ ] Tune boss health/damage values based on tester feedback (1 hr per boss)
- [ ] Add telegraphs to any boss that feels unfair (2 hrs)

🔴 **High Focus**
- [ ] Kydreeok AI overhaul: new attack patterns, phase transitions, visual tells (8-12 hrs)
- [ ] D6 room flow redesign in Yaze if needed (4-8 hrs)
- [ ] Playtest D6 fresh after changes (1 hr)

### Checkpoint (June 30, was May 31)
- Would you be embarrassed if a stranger played D6?
- Is every boss fight fair (clear telegraph before every attack)?

---

## Phase 3: Dream Sequences (re-baselined: July 2026)

**Goal:** Implement the 3 critical dreams + scaffold the 3 polish dreams.
**Estimated hours:** 30-50

Dreams are the biggest new content block. The infrastructure (hooks, SRAM bitfield at `$7EF410`, macros) is scaffolded. The scripts are written. What's missing is the actual scene implementations.

### Task Menu

🟢 **Low Focus**
- [ ] Review all 6 dream scripts in `Docs/Planning/Plans/dream_sequences.md` (30 min)
- [ ] Write any missing dream dialogue for messages.org (2 hrs)
- [ ] Sketch Ancient Soldier sprite design on paper (for Dream 1) (30 min)

🟡 **Medium Focus**
- [ ] Create `Core/dream_sequences.asm` — scene dispatcher framework (2-3 hrs)
- [ ] Create `Core/dream_triggers.asm` — hook sleep events to dream checks (2 hrs)
- [ ] Wire dream SRAM bitfield ($7EF410) to trigger logic (1 hr)
- [ ] Test dream trigger: sleep after D2, verify Dream 1 fires (1 hr)
- [ ] Test dream trigger: sleep after D5, verify Dream 2 fires (1 hr)

🔴 **High Focus**
- [ ] **Dream 1: The Sealing War** — Kydrog's origin, Ancient Soldier sprite (8-12 hrs)
  - [ ] Create Ancient Soldier sprite (Hylian Knight with helmet, silver/blue palette)
  - [ ] Implement scene: battlefield, knight vs shadow, transformation
  - [ ] Wire to post-D2 trigger
- [ ] **Dream 2: Ranch Girl / Twinrova** — surreal ranch, curse scene (6-8 hrs)
  - [ ] Implement scene: distorted ranch, Twinrova silhouettes, voice torn away
  - [ ] Wire to post-D5 trigger
- [ ] **Dream 3: Observatory Vision** — Ganondorf imprisonment (6-8 hrs)
  - [ ] Implement 3 visions (past age, sealing ritual, present)
  - [ ] Wire to Sky Islands access
- [ ] **Dreams 4-6** (polish, lower priority) — scaffold Init/Main/Cleanup (4-6 hrs)
  - [ ] Dream 4: The Reflection (post-D3)
  - [ ] Dream 5: The Giant's Message (post-D6)
  - [ ] Dream 6: Hyrule Castle Memory (polish)

### Checkpoint (July 31, was June 30)
- Do Dreams 1, 2, and 3 trigger at the right times and play through?
- Does the dream SRAM bitfield track which dreams you've seen?

---

## Phase 4: Sky Islands + East Kalyxo + Koroks (July-August 2026)

**Goal:** The optional regions exist and feel like real places.
**Estimated hours:** 40-65

These three areas share the special overworld map (0x80-0x9B) and can be built incrementally.

### Task Menu — Sky Islands

🟢 **Low Focus**
- [ ] Design screen layouts for maps 0x84-87, 0x8C-8F on paper (1 hr)
- [ ] Write Cumuli NPC dialogue (shy cloud creatures, cryptic hints) (1 hr)
- [ ] Write Observatory discovery dialogue (Maku Tree telepathy) (30 min)

🟡 **Medium Focus**
- [ ] Build Sky Islands overworld screens in Yaze (4-6 hrs)
- [ ] Set ZSOW data tables for Sky Islands screens (palette, GFX, sprites) (2 hrs)
- [ ] Create Cumuli NPC sprite (simple fluffy design, 3 behaviors) (3-4 hrs)
- [ ] Wire Flute bird bonus destination for Sky Islands access (1 hr)
- [ ] Gate access behind D6 + Shrines completion (1 hr)

🔴 **High Focus**
- [ ] Implement weather mechanics: rain solidifies clouds, sun vaporizes (6-8 hrs)
  - [ ] Song of Storms → clouds become walkable platforms
  - [ ] Default/wait → clouds become passthrough
  - [ ] Wind shrine mechanism → platforms move
- [ ] Wire Observatory dream (Dream 3) to Sky Islands location (2 hrs)

### Task Menu — East Kalyxo + Reconciliation

🟢 **Low Focus**
- [ ] Design screen layouts for maps 0x90-9B, 0x83, 0x8B on paper (1 hr)
- [ ] Write River Zora Village NPC dialogue (Elder, Warriors, Children, Researcher) (2 hrs)
- [ ] Write reconciliation scene dialogue (Elder's response to evidence) (1 hr)

🟡 **Medium Focus**
- [ ] Build East Kalyxo overworld screens in Yaze (4-6 hrs)
- [ ] Build Korok Cove screens (0x81, 82, 89, 8A) in Yaze (2-3 hrs)
- [ ] Set ZSOW data tables for all new screens (2 hrs)
- [ ] Create River Zora NPC variant sprites (if distinct from Sea Zora) (2-3 hrs)
- [ ] Wire Hammer barrier at Korok Cove entrance (post-D6 gate) (1 hr)

🔴 **High Focus**
- [ ] Implement reconciliation scene: Link delivers Princess's words (4-6 hrs)
  - [ ] Elder listens → tense moment → understanding
  - [ ] Sea Zora dialogue updates post-reconciliation
  - [ ] Side content unlocks
- [ ] Wire River Zora Village NPC states to progression flags (2-3 hrs)

### Task Menu — Korok Minigame

🟡 **Medium Focus**
- [ ] Place 10 Korok sprites across Korok Cove + East Kalyxo maps in Yaze (2 hrs)
- [ ] Implement Korok tracking counter in SRAM (1 hr)
- [ ] Wire find rewards: 5-20 rupees per Korok (1 hr)
- [ ] Wire milestone rewards: heart piece at 5 and 10 found (1 hr)
- [ ] Implement hide behavior (Koroks appear when approached from correct direction) (3-4 hrs)
- [ ] Test full minigame: find all 10, collect both heart pieces (1 hr)

### Checkpoint (August 31)
- Can you reach Sky Islands after forging Master Sword?
- Does the weather mechanic work (rain = solid clouds, sun = fall through)?
- Can you reach East Kalyxo via Korok Cove after getting Hammer?
- Does the reconciliation scene play? Do Sea Zora react afterward?
- Can you find all 10 Koroks and get both heart pieces?

---

## Phase 5: Dialogue & Narrative Polish (September 2026)

**Goal:** No placeholder text. Every NPC reacts to your progress. Story beats land.
**Estimated hours:** 20-30

### Task Menu

🟢 **Low Focus**
- [ ] Audit every NPC: does their dialogue change after key events? List gaps (2 hrs)
- [ ] Write progression-aware dialogue for static NPCs (3-4 hrs)
- [ ] Review Maku Tree hint cascade — are hints helpful at each stage? (1 hr)
- [ ] Review all boss dialogue — pre-fight and defeat text (1 hr)
- [ ] Write any missing intermediate dialogue (post-D4 Sea Zora, etc.) (2 hrs)
- [ ] Final tone pass: read all dialogue aloud, fix what sounds wrong (2 hrs)

🟡 **Medium Focus**
- [ ] Wire new dialogue to NPC sprite code (SelectReactionMessage tables) (3-4 hrs)
- [ ] Test each NPC at different progression points via savestates (2-3 hrs)
- [ ] Playtest dialogue flow: new game, talk to everyone at start, D3, D6, credits (2 hrs)

🔴 **High Focus**
- [ ] Full golden path dialogue pass including new content areas (3-4 hrs)
- [ ] Fix any story beats that feel flat based on tester feedback (varies)

### Checkpoint (September 30)
- Start a new game and talk to every NPC at: start, after D3, after D6, after credits.
- Visit Sky Islands, East Kalyxo, Korok Cove — does dialogue make sense in each?
- Does the world feel alive?

---

## Phase 6: RC Build + Tester Feedback (October 2026)

**Goal:** Build the RC. Ship to Discord testers with "this is the release candidate" framing.
**Estimated hours:** 15-25

### Task Menu

🟢 **Low Focus**
- [ ] Update all docs to match final state (2 hrs)
- [ ] Write release notes for v1.0 (1 hr)
- [ ] Prepare patch file for distribution (1 hr)

🟡 **Medium Focus**
- [ ] Full regression suite — must pass clean (2-4 hrs fixing)
- [ ] Test save/load at every dungeon midpoint + new areas (2 hrs)
- [ ] Final boss fairness check (play each boss 3 times) (2 hrs)
- [ ] Ship RC ROM to Discord: "please break this" (1 hr)
- [ ] Triage tester feedback: critical vs nice-to-have (ongoing)

🔴 **High Focus**
- [ ] Fix critical bugs from RC tester reports (varies)
- [ ] Address analyzer warnings in strict mode (2-3 hrs)

### RC Gate (October 31)
- [ ] Full regression suite passes
- [ ] No hardlocks on golden path (including new areas)
- [ ] All dialogue in final form
- [ ] Dreams trigger correctly
- [ ] Sky Islands + East Kalyxo accessible and complete
- [ ] YOU played it start-to-credits and felt good about it

---

## Phase 7: Release (November 2026)

**Goal:** Ship it.
**Estimated hours:** 5-10

- [ ] Final build from RC + bug fixes
- [ ] Tag release in git
- [ ] Create RHDN page / distribution post
- [ ] Write a "how to play" readme
- [ ] Post it and celebrate

---

## Post-Release Content (v1.1+)

These are great reasons to keep working on the game after v1.0:

| Feature | Notes |
|---------|-------|
| Post-game Abyss healing | Visual changes after credits, enemy density, hopeful NPC dialogue |
| Gossip stones (21 written) | Atmosphere and foreshadowing |
| D8 Voice encounters | Ganondorf name-drop layering |
| Temporal Pyramid visions | Ties to dream system |
| Dream polish (Dreams 4-6) | If only scaffolded in v1.0 |

---

## Progress Tracker

```
Phase 1: Regression Confidence   [___________] 0/14 tasks
Phase 2: D6 + Boss Polish        [___________] 0/13 tasks
Phase 3: Dream Sequences          [___________] 0/14 tasks
Phase 4: Sky/Kalyxo/Koroks       [___________] 0/20 tasks
Phase 5: Dialogue & Narrative     [___________] 0/11 tasks
Phase 6: RC Build                 [___________] 0/8 tasks
Phase 7: Release                  [___________] 0/5 tasks
                                                -------
                                                0/85 total
```

---

## Discord Beta Context

Beta patches have been shipping to Discord testers throughout development. Tester feedback is an active input to this plan. When testers report issues:

1. Check if it maps to a known AI-generated commit (see `Docs/Analysis/07_ai_lineage_regression.md`)
2. If it's a crash: check register width first (65816 M/X flags, #1 cause)
3. If it's a softlock: check SUBMODE ($7E0011) and SPC timeout ($B010)
4. If it's "this feels bad": add to the relevant phase's task menu

Tester feedback > this document. If testers say something is fine, trust them.
