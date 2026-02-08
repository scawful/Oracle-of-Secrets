# Roadmap

## North Star
- Ship stable beta patches every 2-4 weeks (no new hardlocks on the golden path).
- Finish a full content release in 2026 (see `Docs/Planning/Plans/release_2026_definition.md`).

## Current Stage
- Alpha (per `PROJECT.toml`).

## Now (next 2-4 weeks)
- **Stability first**: close the loop on known regressions and stop-ship bug classes.
- **Goron Mines focus (D6)**: expand minecart usage from “present” to “signature dungeon mechanic”.
- **Progression consistency**: centralize crystal-based progression helpers so NPCs and MapIcon cannot drift.

### Workstreams
1. **Dungeon hooks and persistence**
   - D4 Water Gate end-to-end verification (fill, persistence on re-entry, save/load).
   - D3 Prison capture path: guard subtype gating, one-shot flags, escape flow, and placeholder dialogue cleanup.
   - Keep risky hooks feature-gated so you can regression test without blocking builds (see Feature Flags).
2. **Goron Mines (minecart) expansion**
   - Add at least 1 multi-room ride, 1 switch-corner puzzle, 1 “cart-required shutter” usage.
   - Prefer incremental track slots and room-by-room activation: see `Docs/Planning/Plans/goron_mines_minecart_design.md`.
   - Fix room-data invariants flagged by `z3ed dungeon-minecart-audit` (stop tiles present, minecart sprites placed on stop tiles, sprite track subtype matches the intended track objects).
3. **Progression infrastructure**
   - Implement shared helpers (`GetCrystalCount`, `UpdateMapIcon`, reaction tables) and convert the first consumers:
     - Maku Tree hint cascade.
     - Zora NPC post-D4 messaging.
   - Spec: `Docs/Planning/Plans/progression_infrastructure.md`.

## Next (1-2 months)
- Narrative/dialogue pass for the golden path (replace placeholder message IDs).
- Dungeon polish: tighten pacing and mechanical escalation (especially D6 and the endgame lead-in).
- Boss polish (telegraphs, fairness, crash-proofing) with targeted regression states.

## Later (post-beta hardening)
- Endgame sequence integration + credits.
- Optional regions and long arcs (Sky Islands, East Kalyxo expansion, etc.).

## Tooling and Guardrails
### Feature flags
- Canonical override file: `Config/feature_flags.asm` (generated via `scripts/set_feature_flags.py`).
- Use feature flags for risky `org` patches so hooks can be isolated without backing out commits.
- When flags change, `scripts/build_rom.sh` regenerates `hooks.json` automatically (so z3dk analysis matches the built ROM).

### z3dk (analysis signal improvements)
- Short term: ensure hooks/annotations reflect reality (feature-gated hooks, module isolation, skip non-assembled trees).
- Medium term: add analyzer diff mode (compare two ROM builds and show only new issues).
- Long term: migrate to structured outputs via comment-based tags (`@hook`, `@watch`, `@abi`) and z3asm/z3lsp linting.
See `Docs/Debugging/Z3DK_Analyzer_Findings.md` and `Docs/Debugging/Z3ASM_Feature_Ideas.md`.

### Debug + tests
- Treat `Docs/STABILITY.md` as “stop-ship gotchas” (color math, SPC timeouts, input hygiene).
- Grow the canon savestate library and keep transition tests deterministic (see `Docs/Debugging/Testing/SaveStateLibrary.md` and `RUNBOOK.md`).

## Sources of Truth
- Backlog + epics: `oracle.org`
- Release definition: `Docs/Planning/Plans/release_2026_definition.md`
- Dungeon plans: `Docs/Planning/Plans/`
- Tooling plans/findings: `Docs/Debugging/`
