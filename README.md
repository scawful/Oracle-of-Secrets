# The Legend of Zelda: Oracle of Secrets

Source code for all assembly-level hacks in the game. Learn more about the project at [halext.org](https://halext.org/labs/Oracle)

## Start here

| I want to... | Go to |
|---|---|
| Build the ROM | `Scripts/Build/build_rom.sh 168` (base `Roms/oos168.sfc` -> patched `Roms/oos168x.sfc`) |
| Edit rooms, maps, graphics, text | open `Oracle-of-Secrets.yaze` in yaze (it pins the base ROM SHA-1) |
| See what's left to do | `Docs/oracle.org` (task tracker) |
| Check a story or design ruling | `Docs/Planning/Status/decisions.org`, `Docs/Planning/story_canon_beat_sheet.md` |
| Look up RAM/SRAM, flags, tables | `Docs/Technical/` (`Flag_Ledger.md`, `MemoryMap.md`) |
| Read dungeon/world/lore references | `Docs/World/` |

What lives where:

- **Game source**: `Oracle_main.asm`, `Config/`, `Core/`, `Dungeons/`, `Items/`, `Masks/`, `Menu/`,
  `Music/`, `Overworld/`, `Sprites/`, `Util/`. Feature flags: `Util/macros.asm` (generated
  `Config/feature_flags.asm` via `Scripts/Build/set_feature_flags.py`).
- **Build data**: `Data/` (dialogue, custom collision, ROM byte patches, debug checkpoints),
  `Docs/Dev/Planning/*.json` (yaze project registry).
- **Scripts**: only build, generate, validate, emulator and debug helpers (`Scripts/README.md`).
- **Not in git**: agent plans, reviews, evidence, old debugging guides and session notes live in the
  private AFS context `~/.context/projects/oracle-of-secrets/` (the repo's `.context` symlink).
  Docs moved out on 2026-10-06 keep their old relative paths under
  `scratchpad/archive/repo-slim-2026-10-06/repo/` (e.g. the old `Docs/RUNBOOK.md`).

## Quick Build

```bash
Scripts/Build/build_rom.sh 168      # direct build with options
Scripts/Build/oos-quick.sh          # fast build + Mesen2 reload
Scripts/Build/oos-verify.sh         # build + reload + full validation
Scripts/Build/z3dk_safe_smoke.sh    # safe z3asm smoke build in a temp workspace
```

ROM naming: `Roms/oos<VERSION>.sfc` is the unpatched base (the edit target); `Roms/oos<VERSION>x.sfc` is
the Asar-patched ROM for testing only. Never edit the `x` ROM.

## Hook tagging (optional)
z3asm infers each hook's kind, target, and name from the assembled code (`Scripts/Build/build_rom.sh 168 --asar=z3asm` writes `Roms/hooks.json`).
Add an `@hook` comment on the `org` line only to override those values or to record ABI widths, for example:
`org $02C0C3 ; @hook name=Overworld_SetCameraBounds expected_m=16 expected_x=8`

Supported `@hook` fields: `name`, `kind`, `target`, `module`, `note`, `expected_m`, `expected_x`, `expected_exit_m`, `expected_exit_x`, `skip_abi`, `abi`. Rules: `../z3dk/docs/Z3DK_HOOKS.md`.

## Z3DK config
- `z3dk.toml`: Oracle of Secrets main entry (`Oracle_main.asm`).

---
