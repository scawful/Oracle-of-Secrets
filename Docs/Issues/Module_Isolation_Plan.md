# Module Isolation Plan (2026-01-30)

Purpose: isolate regressions behind overworld/dungeon softlocks and mirror-warp failure
by toggling major modules and running targeted transition tests.

## Infra Review (ready for isolation)

- **Module disable flags**: `!DISABLE_*` in `Util/macros.asm`, used by `Oracle_main.asm`.
- **Module override file**: `Config/module_flags.asm` (generated or edited for isolation).
- **Debug warp system**: ROM code at `$3CB400` exposed via `OracleDebugClient.warp_to()`.
- **Socket test runner**: `scripts/test_runner.py` (Mesen2 socket backend) can load
  states, press inputs, and run scripted checks.
- **P/stack tracing**: `scripts/repro_stack_corruption.py`, `scripts/p_watch.py`,
  and `mesen2_client_lib` watch/breakpoint helpers.

## How to Toggle Modules

Preferred: use the generator script and rebuild.

```bash
python3 scripts/set_module_flags.py --disable menu
./scripts/build_rom.sh 168
```

**Optional: cycle through modules in FixPlan order.** Run `./scripts/run_module_isolation.sh` to disable modules one at a time (Masks → Music → Menu → Items → Patches → Sprites → Dungeon → Overworld), build after each, and be prompted to test. Use `--next N` to run only step N (1–8); use `--next 9` to reset all.

Reset to defaults:
```bash
python3 scripts/set_module_flags.py --profile all
```

## Isolation Runbook (recommended order)

Run from repo root. After each build, load save state 1 (overworld) or 2 (file-load dungeon) and test; if crash disappears, the disabled module is implicated.

| Step | Command | If crash gone |
|------|---------|----------------|
| 1 | `python3 scripts/set_module_flags.py --disable menu` then `./scripts/build_rom.sh 168` | Focus on menu (and file-load path for State 2) |
| 2 | `python3 scripts/set_module_flags.py --disable overworld` then build | Focus on time system and LoadOverworldSprites_Interupt |
| 3 | `python3 scripts/set_module_flags.py --disable sprites,masks,items` then build | Focus on sprite/ancilla width imbalances and JumpTableLocal callers |
| Reset | `python3 scripts/set_module_flags.py --profile all` then build | Restore all modules |

## Isolation Profiles (recommended order)

1) **No menu/HUD** (fast signal on P-register/stack issues triggered by HUD code)
- `--disable menu`
- Tests: overworld transitions, dungeon entry, mirror warp

2) **No overworld system** (disables ZSOW + time system overlays)
- `--disable overworld`
- Tests: dungeon-only flows and menu navigation (if still enabled)

3) **No sprites + masks + items** (reduces width-imbalance exposure)
- `--disable sprites,masks,items`
- Tests: basic movement + transitions (expect visual oddities)

4) **No patches** (sanity baseline for ROM hooks)
- `--disable patches`
- Tests: if debug warp fails here, use direct RAM teleports or vanilla play

5) **Core-only** (last-resort, likely to fail fast but confirms if infra or hooks
   are the crash source)
- `--profile core-only`

## Targeted Test Sequence

Use the debug warp system (ROM-side) to avoid manual travel:

- **Overworld transitions**: warp to several OW areas (same-area, cross-area)
- **Dungeon entry/exit**: warp to dungeon entrance → enter → exit
- **Mirror warp**: trigger mirror item or use debug warp error codes (see client logs)

Suggested warp loop (socket backend):
```bash
python3 scripts/mesen2_client.py warp --location "Kakariko Village" --wait 60
python3 scripts/mesen2_client.py warp --location "Lost Woods" --wait 60
python3 scripts/mesen2_client.py warp --location "Eastern Palace Entrance" --wait 60
```

Capture on failure:
```bash
python3 scripts/repro_stack_corruption.py --strategy auto --output /tmp/blame_report.json
```

## Likely Modules to Isolate First

- **Overworld/ZSCustomOverworld + time system**
  - Recent changes in `Overworld/ZSCustomOverworld.asm` and `Overworld/time_system.asm`.
  - Known interaction with overlays, palette loads, and transitions.

- **Sprites (bank $06/30)**
  - Width-dependent stack imbalances concentrated in sprite routines.
  - Softlock chain involves P/X mode corruption.

- **Menu/HUD**
  - Prior fixes added SEP/REP + stack changes; HUD clock display is in P-chain.

## Notes

- Disabling a module may introduce missing symbol errors. If that happens,
  disable dependent modules (see `Oracle_main.asm` dependency notes).
- Overworld disable also disables ZSCustomOverworld, which is outside the Oracle
  namespace but gated by the same flag.

