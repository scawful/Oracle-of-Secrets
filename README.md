# The Legend of Zelda: Oracle of Secrets

Source code for all assembly-level hacks in the game. Learn more about the project at [halext.org](https://halext.org/labs/Oracle)

Build using [Asar](https://github.com/RPGHacker/asar). See `Docs/Debugging/Guides/AsarUsage.md` for the ROM naming scheme.

## Quick Build

```bash
Scripts/Build/oos-quick.sh          # fast build + Mesen2 reload
Scripts/Build/oos-verify.sh         # build + reload + full validation
Scripts/Build/build_rom.sh 168      # direct build with options
Scripts/Build/z3dk_safe_smoke.sh    # safe z3asm smoke build in a temp workspace
```

## Runbook (Start Here)
- `Docs/RUNBOOK.md` (build, debug, test, save-data profiles, blackout capture)
- `Docs/README.md` (documentation index)

## Hook tagging (optional)
Use `Scripts/Generate/tag_org_hooks.py` to tag org blocks with `@hook` comments and normalize metadata.

Examples:
- `python3 Scripts/Generate/tag_org_hooks.py --root . --dry-run`
- `python3 Scripts/Generate/tag_org_hooks.py --root . --apply --normalize --module-from-path`

Supported `@hook` fields: `name`, `kind`, `target`, `module`, `note`, `expected_m`, `expected_x`, `skip_abi`, `abi`.

## Z3DK config
- `z3dk.toml`: Oracle of Secrets main entry (`Oracle_main.asm`).

---
