# The Legend of Zelda: Oracle of Secrets

Source code for all assembly-level hacks in the game. Learn more about the project at [halext.org](https://halext.org/labs/Oracle)

Build using [Asar](https://github.com/RPGHacker/asar). Recommended: `mesen-agent build`. Legacy: `./scripts/build_rom.sh <version>` on macOS/Linux, and `build.bat` on Windows. See `Docs/Debugging/Guides/AsarUsage.md` for the ROM naming scheme and `python3 scripts/check_zscream_overlap.py` for post-build overlap verification.

## Runbook (Start Here)
- `RUNBOOK.md` (build, debug, test, save-data profiles, blackout capture)
- `Docs/README.md` (documentation index)

## Dev loop
Quick build + sync helper:
- `scripts/dev_loop.sh 168 --z3asm --mesen-sync --reload --validate`

## Hook tagging (optional)
Use `scripts/tag_org_hooks.py` to tag org blocks with `@hook` comments and normalize metadata.

Examples:
- `python3 scripts/tag_org_hooks.py --root . --dry-run`
- `python3 scripts/tag_org_hooks.py --root . --apply --normalize --module-from-path`

Supported `@hook` fields: `name`, `kind`, `target`, `module`, `note`, `expected_m`, `expected_x`, `skip_abi`, `abi`.

## Z3DK configs
- `z3dk.toml`: Oracle of Secrets main entry (`Oracle_main.asm`).
- `z3dk.meadow.toml`: Meadow of Shadows template (copy to `z3dk.toml` when working on Meadow).

---
