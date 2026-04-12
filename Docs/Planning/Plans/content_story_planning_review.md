# Oracle of Secrets — Content & Story Planning Review

**Created:** 2026-03-01
**Status:** Active Planning Document
**Purpose:** Identify what's done, what needs work, and priority order for content authoring.

---

## Design Decisions (Resolved 2026-03-01)

1. **D3 Boss** — Eyegore Knights (vanilla Armos reskin via spriteset swap, no custom code)
2. **D1/D2 Bosses** — Manhandla and Moldorm are vanilla bosses with spriteset/hook tweaks. Do NOT attempt major custom boss ASM for these — agent ASM capability is not reliable enough for complex boss rewrites yet.
3. **Ganondorf Name** — Gradual revelation via Gossip Stones, scholar NPCs, libraries before D8
4. **Dream Sequences** — Full cutscene production (sprites, palettes, transitions via `attract_scenes.asm`)
5. **Existing Bosses** — D1-D6 bosses work via vanilla code + hooks/reskins. Leave as-is. No standalone Ganondorf boss file exists — `dark_link.asm` subtype 05 has reused Ganon cutscene functions, NOT the designed 3-phase fight.
6. **Boss Priority** — Focus on unfinished: Kydreeok v2 (D8), Ganondorf (final, needs new file), Vaati (S3, needs new file), D7 Kydrog rescue pipeline (combat works, post-fight gated OFF)
7. **Agent Trust Boundary** — Text authoring and design docs are safe for agents. ASM implementation of new features (bosses, cutscenes, complex hooks) requires human review + Mesen2 validation before merging. Feature-gate all new runtime code.

---

## Current State Summary

### Dungeons (from `Docs/Technical/Sheets/Oracle of Secrets Data Sheet - Dungeons.csv`)

| # | Name | Boss | Item | Status |
|---|------|------|------|--------|
| D1 | Mushroom Grotto | Manhandla | Bow | Rooms exist |
| D2 | Tail Palace | Moldorm | Roc's Feather | Rooms exist |
| D3 | Kalyxo Castle | Eyegore Knights | King's Sword | Phase A code (gated OFF) |
| D4 | Zora Temple | Advanced Arrghus | Hookshot, Blue Tunic | 16 rooms, water gate in progress |
| D5 | Glacia Estate | Twinrova | Fire Rod | 19 rooms exist |
| D6 | Goron Mines | King Dodongo | Hammer, Fire Shield | Minecart in progress |
| D7 | Dragon Ship | Kydrog | Cane of Somaria | Combat functional, post-fight rescue gated OFF |
| D8 | Fortress of Secrets | Dark Link, Kydreeok | Portal Rod | Skeleton (Ganon subtype in dark_link.asm is cutscene only, NOT 3-phase fight) |

| Shrine | Challenge | Item | Status |
|--------|-----------|------|--------|
| S1 Wisdom | — | Flippers | Beta (pendant mismatch) |
| S2 Power | — | Power Glove | Beta (pendant mismatch) |
| S3 Courage | Vaati | Mirror Shield | Stub |
| S4? Unnamed Bonus | — | Red Tunic | Unknown |

**End-to-end testing: ZERO dungeons fully playtested.**

### NPCs — 27 implementations in `Sprites/NPCs/`

- **Done (code + dialogue):** Fortune Teller, Mermaid, Tingle, Mask Salesman, Zora Princess, Deku Scrub, Ranch Girl, Bug Net Kid, Village Elder, Maku Tree
- **Partial (code done, dialogue imported 2026-02-22):** Windmill Guy, Bean Vendor, Goron Elder, River Zora Elder, Cartographer, Koroks
- **Functional but incomplete:** Impa (spawn point tracking works, follows Zelda hooks), Farore (7 states through Imprisoned, NO post-rescue states 8+), Followers (20-step cache works, Zora Baby detection wired)
- **Functional:** Maple, Zora, Eon variants, Korok variants (Makar/Hollo/Rown all separate files)

### Dialogue — ~506 messages total (397 vanilla + ~109 expanded $18D-$1F9)

- 34 expanded messages have real encoded text; 28 are placeholder slots
- Imported 2026-02-22: Windmill (4), Goron Elder (5), River Zora Elder (3), Bean Vendor (3), Cartographer (5), Koroks (10) — all NOT runtime-tested
- Maku hints: 4/7 have real text ($1C5-$1C7, $1CA); 3 still placeholder ($1C8, $1C9, $1CB)
- Placeholder slots: D3 Prison ($1CC-$1D1, all 6), Gossip ($1D2-$1D4, all 3), gap fillers ($1D9-$1DF, all 7)
- Maiden Upgrades (vanilla IDs 306/307/311): applied to test ROM via z3ed, NOT in ASM source, will revert on rebuild

### Bosses — 14 files in `Sprites/Bosses/`

Existing: arrghus, vampire_bat, kydrog, kydrog_boss, king_dodongo, kydreeok, kydreeok_head, lanmola, lanmola_expanded, octoboss, twinrova, manhandla, dark_link, wolfos

**Boss-to-Dungeon (from Data Sheet):**
D1=Manhandla, D2=Moldorm, D3=Eyegore Knights, D4=Advanced Arrghus, D5=Twinrova, D6=King Dodongo, D7=Kydrog, D8=Dark Link+Kydreeok, S3=Vaati

**Unfinished bosses:** Kydreeok v2 (spec only), Ganondorf (design only, NO standalone file — needs new `ganondorf.asm`), Vaati S3 (NO file exists — needs new `vaati.asm`), D7 Kydrog post-fight rescue (combat works, rescue pipeline gated OFF)

**Note on vanilla bosses:** D1 Manhandla, D2 Moldorm, D3 Eyegore Knights use vanilla boss code with spriteset/hook tweaks. No custom boss ASM for these — intentional to reduce risk.

### Progression System

- Crystal bitfield ($7EF37A), pendant tracking ($7EF374)
- `Core/progression.asm`: GetCrystalCount, UpdateMapIcon, SelectReactionMessage — UNTESTED
- Maku Tree hint cascade: code complete, UNTESTED

### Story Documents (complete, locked)

- `Docs/Planning/narrative_design_master_plan.md`
- `Docs/Planning/Plans/endgame_narrative_arc.md`
- `Docs/Planning/Story_Event_Graph.md` (17 events, 11 traced to code)
- `Docs/Planning/world_map_diagram.md` (78 areas)
- `Docs/Planning/Plans/dream_sequences.md` (infrastructure hooks + data structure, NO dream content in code — narrative scripts exist in master plan only)
- `Docs/World/Bosses/kydreeok_v2_spec.md`

---

## Critical Path Narrative Flow

```
INTRO --> D1 --> D2 --> DREAM 1 (Kydrog's origin)
--> D3 --> D4 --> SONG OF HEALING (Zora schism revealed)
--> D5 --> TWINROVA DEFEATED --> DREAM 2 (Ranch Girl)
--> D6 --> East Kalyxo (reconciliation)
--> SHRINES --> Master Sword forged
--> SKY ISLANDS --> DREAM 3 (Ganondorf vision)
--> D7 --> FARORE RESCUED
--> D8 --> VOICE ENCOUNTERS --> TEMPORAL PYRAMID --> KYDREEOK
--> LAVA LANDS --> GANONDORF --> ENDING
```

---

## Session Plans

This work should NOT be coded in a single session. Each item below is a discrete planning session with its own validation gate. No implementation begins until the design is reviewed.

### SP-01: Critical Path Dialogue Script (TEXT ONLY)

- **Scope:** Author ~43 critical path messages as plain text dialogue
- **Content:** Ganondorf speeches, Zora Princess Song of Healing, Dreams 1-3 narration, Maku Tree guidance, boss encounter dialogue, Farore rescue
- **Deliverable:** Dialogue script doc with message ID assignments
- **Validation:** Human review of tone, pacing, character voice
- **No ASM changes.** Text authoring only.

### SP-02: Maku Tree Hint Encoding

- **Scope:** Replace 3 remaining placeholder slots ($1C8, $1C9, $1CB) with real hint text. Review existing 4 messages ($1C5-$1C7, $1CA) for tone consistency.
- **Prerequisite:** SP-01 (Maku hints portion)
- **Deliverable:** Encoded messages in `Core/message.asm`
- **Validation:** `build_rom.sh 168` + ROM byte inspection + Mesen2 text display test

### SP-03: Dream 1 Cutscene Design

- **Scope:** Full cutscene spec for Dream 1 (The Sealing War)
- **Content:** Sprite positions, palette data, transitions, text boxes, trigger conditions
- **Prerequisite:** SP-01 (Dream 1 narration text)
- **Assess:** What `attract_scenes.asm` provides vs what's needed
- **Deliverable:** Frame-by-frame storyboard with technical notes
- **Validation:** Design review only — no code

### SP-04: Dreams 2 + 3 Cutscene Design

- **Scope:** Full cutscene specs for Dreams 2-3
- **Prerequisite:** SP-03 (reuses infrastructure decisions)
- **Deliverable:** Storyboards with technical notes
- **Validation:** Design review only

### SP-05: Ganondorf Foreshadowing Layer

- **Scope:** Author 3-4 Gossip Stone "King in darkness" messages, scholar NPC hints, D8 Voice Encounters (4 escalating), Temporal Pyramid visions
- **Prerequisite:** SP-01 (character voice established)
- **Deliverable:** Message text + NPC assignment table
- **Validation:** Human review of lore consistency

### SP-06: D7 Kydrog Boss Pipeline Design

- **Scope:** Design crystal drop, flag setter, cutscene, Farore rescue sequence
- **Assess:** `kydrog_boss.asm` staged death flow, `!ENABLE_D7_FARORE_RESCUE_SEQUENCE`
- **Deliverable:** Implementation spec (SRAM flags, message IDs, feature flag plan)
- **Validation:** Design review before any code
- **Reference:** `Docs/Planning/Plans/d7_farore_rescue_spec.md`

### SP-07: Kydreeok v2 Implementation Plan

- **Scope:** Design chain physics, parent-child architecture, phase transitions
- **Assess:** `kydreeok_v2_spec.md`, existing `kydreeok.asm` v1
- **Deliverable:** ASM implementation plan with sprite state machine diagram
- **Validation:** Design review

### SP-08: Ganondorf Final Boss Design

- **Scope:** 3-phase fight pattern, seal flicker vulnerability, health thresholds
- **Assess:** `endgame_narrative_arc.md` fight design, `narrative_design_master_plan.md` boss spec
- **Current state:** NO standalone `ganondorf.asm` exists. `dark_link.asm` subtype 05 has reused Ganon cutscene functions (5-state: Wait/ShowMessage/Fall/FellWait/FadingAwait) — this is NOT the designed 3-phase combat fight. A new file is needed.
- **Deliverable:** Boss state machine doc, sprite requirements, message IDs
- **Validation:** Design review

### SP-09: Vaati S3 Boss Design

- **Scope:** Vaati encounter for Shrine of Courage
- **Content:** Mechanics, Mirror Shield integration, pendant reward
- **Deliverable:** Boss design doc
- **Validation:** Design review

### SP-10: Supporting NPC Dialogue Script

- **Scope:** Zora Baby (D4), Impa, Goron Elder, Ranch Girl post-curse
- **Prerequisite:** SP-01 (voice consistency)
- **Deliverable:** Text script with message IDs
- **Validation:** Human review

### SP-11: World Building Dialogue

- **Scope:** Gossip Stones (12), D5 journals, D7 captain's log, side NPC flavor
- **Priority:** Last — polish layer
- **Deliverable:** Text script with message IDs
- **Validation:** Human review

---

## Dependency Graph

```
SP-01 (dialogue text) -------- no deps, START HERE
SP-02 (Maku hints) ----------- can parallel SP-01
SP-05 (foreshadowing) -------- after SP-01
SP-03 (Dream 1) -------------- after SP-01
SP-04 (Dreams 2+3) ----------- after SP-03
SP-06 (D7 Kydrog) ------------ independent
SP-07 (Kydreeok v2) ---------- independent
SP-08 (Ganondorf) ------------- independent
SP-09 (Vaati S3) -------------- independent
SP-10 (NPC dialogue) ---------- after SP-01
SP-11 (world building) -------- last
```

## Validation Gates

**Gate 1** (after SP-01+02): All critical text authored. Maku hints encoded + runtime tested.
**Gate 2** (after SP-03+04): Dream cutscene designs reviewed and approved.
**Gate 3** (after SP-05): Foreshadowing text approved. Ready for encoding.
**Gate 4** (after SP-06+07+08+09): All boss designs reviewed. No implementation until all approved.
**Gate 5** (after SP-10+11): Full dialogue script complete. Ready for batch encoding session.

---

## Pacing Notes

**Strengths:**
- Gradual escalation (Kydrog as visible threat, Ganondorf as cosmic evil behind the scenes)
- Dreams space revelations well between dungeon blocks
- Each dungeon adds a narrative layer (Zora schism, Twinrova's portal, Goron trust)
- D1-D6 use vanilla bosses with spriteset/hook tweaks; truly custom bosses (Kydreeok, Ganondorf, Vaati) reserved for climax — reduces ASM risk

**Risks:**
- D5-D7 compresses multiple major revelations (Twinrova portal, Ranch Girl cure, Goron reconciliation, East Kalyxo)
- Ganondorf needs earlier foreshadowing (resolved: Gossip/NPC hints decided this session)
- Ranch Girl arc may feel disconnected without earlier NPC hints about her silence
- Dream sequences are "narrative pressure valves" — if cut for time, pacing suffers

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| `story_framework.md` | Companion doc: narrative structure and character arcs |
| `rc_content_checklist.md` | What must be done for Release Candidate |
| `narrative_design_master_plan.md` | Locked story decisions |
| `endgame_narrative_arc.md` | D8 through Ganondorf detailed design |
| `d7_farore_rescue_spec.md` | SP-06 reference |
| `dream_sequences.md` | SP-03/SP-04 reference |
| `kydreeok_v2_spec.md` | SP-07 reference |
| `Story_Event_Graph.md` | 17 events, flag tracing status |

---

## Agent Capability Boundaries

**What agents CAN do reliably:**
- Text authoring (dialogue scripts, design docs, narrative planning)
- Message encoding (byte-level encoding for `Core/message.asm`)
- Code audits and static analysis
- Build verification (`build_rom.sh`, overlap checks)
- ROM byte inspection and diffing

**What agents CANNOT do reliably yet:**
- Complex boss ASM (state machines, sprite choreography, phase transitions)
- Cutscene implementation (dream sequences, attract scenes)
- Custom hook code that touches P register, stack, or DBR
- Any feature that requires runtime validation to confirm correctness

**Rule:** All new runtime ASM must be feature-gated OFF by default. Human reviews code, enables flag, and validates in Mesen2 before merging. This is why `mesen2-oos`, `z3dk`, and `oracle-agent-manager` exist — they provide the validation infrastructure that agents alone cannot.

**Safe SP plans for agents:** SP-01, SP-02, SP-05, SP-10, SP-11 (all text/encoding work)
**Design-only SP plans:** SP-03, SP-04, SP-06, SP-07, SP-08, SP-09 (produce specs, not code)

---

## Next Action

Pick SP-01 or any independent session plan (SP-06/07/08/09) to start in the next session.
