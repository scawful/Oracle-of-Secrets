# Roadmap: Guardrails + z3dk Alignment + Model Integration
Date: 2026-01-31
Status: Active (Phase 0)
Owner: scawful + agents

## Scope
This roadmap covers three lanes executed in parallel, with shared gating:
1) Oracle-of-Secrets guardrails (debugging + regression safety).
2) z3dk alignment (config + linting + editor feedback).
3) Model integration (router + gating + registry) for the afs-scawful Qwen2.5 Coder stack.

## Dependencies (Critical Path)
- Phase 0 baseline must complete before wide feature work.
- Lane 3 (models) gating depends on Lane 1 tests + Lane 2 lint.
- Guardrails and lint are mandatory before accepting model-generated patches.

## Phase 0 - Baseline + Alignment (Complete)
- [x] Document softlock root-cause resolution (archived to `Docs/Issues/archive/`).
- [x] Update softlock root-cause status (resolved, investigation artifacts archived).
- [ ] Lock a known-good savestate (capture + manifest entry) for regression.
- [x] Define DoD for lanes 1–3 (below) and link to scratchpad checklist.
- [x] Ensure static analysis runs during build (`scripts/build_rom.sh` already calls `oracle_analyzer.py`).

## Tooling Sprint (168 Beta) — Added 2026-02-05
- [x] Archive ~25 resolved Docs/Issues/ files to `Docs/Issues/archive/`
- [x] Update CLAUDE.md: remove black screen bug status, add JumpTableLocal gotcha
- [x] Create `z3dk.toml` project config for Oracle of Secrets
- [ ] Expand `oracle_analyzer.py`: PHB/PLB pairing, JSL validation, `--strict`/`--diff` modes
- [ ] Wire lint `--strict` into `build_rom.sh` pipeline
- [ ] Create `.githooks/pre-commit` hook for staged ASM lint
- [ ] Build `z3dk scaffold` generator (sprite, npc, routine, hook templates)
- [ ] Add transition matrix test definitions (OW→cave, OW→D6, D6 inter-room)
- [ ] Add lint-pass smoke test (Tier 1 static analysis without emulator)

## Lane 1 - Oracle Guardrails (Debugging + Regression)
- [ ] Add pause detection + action logging in `scripts/mesen2_client_lib/client.py`.
- [ ] Add SP/DBR watchdog (debug flag) and optional HUD overlay.
- [ ] Expand regression tests: transition matrix + Lost Woods + ZSCustomOverworld.
- [ ] Wire black-screen detection via `scripts/campaign/transition_tester.py`.
- [ ] Update `Docs/Issues/TieredTestingPlan.md` with new tests + state requirements.

## Lane 2 - z3dk Alignment
- [ ] Implement `z3dk.toml` support (schema + parser + config-relative paths).
- [ ] Add Oracle lint command (hooks + M/X + width imbalance + ABI checks).
- [ ] Integrate lint into OOS build pipeline (blocking on errors).
- [ ] Surface lint findings in `z3lsp` diagnostics.

## Lane 3 - Model Integration (afs-scawful)
- [ ] Map router roles (Nayru/Din/Farore/Veran/Ralph) to workflow tasks.
- [ ] Require ASAR pass + regression tests before accepting model patches.
- [ ] Register model versions + eval scores in AFS registry.
- [ ] Integrate routing + gating into Oracle agent gateway and log decisions to AFS scratchpad.

## Definition of Done (DoD)

### Lane 1 DoD
- Repro tests pass for transition matrix + Lost Woods + ZSCustomOverworld.
- Black-screen detection script can flag and report issues in <60s.
- SP/DBR watchdog produces actionable state on failure (debug flag only).

### Lane 2 DoD
- `z3dk.toml` drives default emits + symbol paths with CLI override support.
- Oracle lint runs in build and fails on new ABI/MX/width errors.
- z3lsp displays lint results inline.

### Lane 3 DoD
- Router chooses model role and logs decision per task.
- Gating requires ASAR pass + regression test run before patch acceptance.
- Registry records model metadata + eval scores for each deployed variant.

## Tracking
- Checklist: `.context/scratchpad/roadmap_phase0_checklist_2026-01-31.md`
- Status updates: append to this doc or scratchpad notes.
