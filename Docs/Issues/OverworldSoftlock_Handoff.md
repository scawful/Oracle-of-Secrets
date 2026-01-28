# Overworld / Dungeon Black Screen Softlock — Handoff
Date: 2026-01-28  
Owner (next): whoever picks up with mesen2-oos agent tooling

## Status (short)
- Bug still repros on Save State 1 (pyramid overworld) and Save State 2 (menu hovered “New File”).
- Evidence points to stack/return corruption (invalid PC in bank $11; main loop not hit).
- Recent bitness/return patches did **not** resolve the issue.

## Required setup
- Build from `Roms/oos168_test2.sfc` → load `Roms/oos168x.sfc` in Mesen2.
- Use isolated Mesen2 home + socket; do **not** attach to other agents’ instances.
- Prefer `scripts/export_symbols.py` for labels (avoid `labels-sync` until it filters non-ROM labels).

## Where to pick up
- Action plan: `Docs/Issues/OverworldSoftlock_ActionPlan.md`
- Evidence ledger (dense logs): `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`

## Likely suspects (still unproven)
- Stack corruption before `SpritePrep_LoadPalette` returns.
- Hook bitness/DBR leakage in `time_system` or palette hooks.
- Overlay pointer corruption in `ZSCustomOverworld`.
