# Oracle of Secrets — Deep Analysis (Oct 2025 - Mar 2026)

**Generated:** 2026-03-21
**Purpose:** Comprehensive documentation of the full system architecture, AI-generated feature lineage, and organized regression testing task list.

---

## Document Index

| # | Document | Scope |
|---|----------|-------|
| [00](00_system_architecture.md) | **System Architecture** | ROM bank allocation, game state machine, module dependencies, namespace organization, build pipeline, feature flags, module isolation |
| [01](01_asm_hooks_patches.md) | **ASM Hooks & Patches** | Hook architecture, 65816 ABI standard, hook categories (overworld, follower, dungeon, dream), patch safety patterns, known risk areas |
| [02](02_sprites_subsystem.md) | **Sprites** | Sprite entry pattern, state machine, memory map, catalog status (bosses/enemies/NPCs/objects), Yaze requirements, known issues |
| [03](03_overworld_subsystem.md) | **Overworld** | ZSCustomOverworld data-driven engine, world map layout (Kalyxo/Eon Abyss/Special), time system, region access progression |
| [04](04_dialogue_messages.md) | **Dialogue & Messages** | Message format, control codes, NPC dialogue states, foreshadowing layers, content status (written vs implemented) |
| [05](05_progression_flags.md) | **Progression & Flags** | SRAM layout, GameState machine, MapIcon values, crystal bitfield, NPC conversion status, progression gating chain |
| [06](06_plot_characters.md) | **Plot & Characters** | Three-act structure, character arcs (Kydrog, Ganondorf, Farore, Princess, Ranch Girl), dream sequences, boss roster, mask system, sprites needed |
| [07](07_ai_lineage_regression.md) | **AI Lineage & Regression Tasks** | All 21 AI-generated commits, risk assessment, feature-gate status, prioritized regression test task list, testing infrastructure, recommended test order |
| [08](08_dungeon_menu_subsystems.md) | **Dungeon & Menu** | Dungeon roster, water gate system, minecart mechanics, menu state machine, HUD system, item system, Yaze workflow |

---

## Key Findings

### AI-Generated Code (21 commits, 6.8% of total)

14 commits from `ai-infra-architect` (Feb 5-6, 2026 burst) and 6 from Claude Code (Nov-Dec 2025). 6 feature-gated features are disabled and untested. The highest-risk AI-generated code touches progression helpers, dungeon hooks, and menu stability.

### Critical Untested Changes

1. **Stack corruption fix** (ebb03d3) — Orphaned PHX removed from overworld reload
2. **14-file gameplay update** (4394bad) — Dungeon collision, messages, runtime scripts
3. **Register-width safety** (d30fb96) — 8 files touching hooks/sprites/transitions
4. **L/R button swap** (32129a8) — Explicitly marked UNTESTED in commit message

### Documentation Gaps

- Dream sequences: Scripts written, no ASM implementation
- D8 Fortress: "Skeleton" status, no room layout
- Ganondorf boss: Design only, no code
- Vaati boss: Not implemented
- Gossip Stones: 21 written, no message IDs assigned
- Post-game sequence: No design doc

### System Strengths

- Data-driven architecture (overworld tables, sprite registry, menu lookups)
- Feature flag system allows safe isolation of risky code
- Module isolation enables binary-search debugging
- Build pipeline is well-automated with overlap checks and hooks generation
- Extensive knowledge base documentation

---

## Recommended Next Steps

1. **Run Priority 1 critical tests** (stack, gameplay, registers, followers)
2. **Full golden path playthrough** D1→D7 with all active (ON) features
3. **Enable gated features one at a time** and test each in isolation
4. **Assign Gossip Stone message IDs** and implement foreshadowing Layer 1
5. **Implement Dream 1** (most critical narrative beat, after D2)
6. **Design D8 room layout** (currently skeleton)
7. **Create Vaati boss file** for Shrine S3
