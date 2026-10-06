# Dialogue sources and bundles

This directory contains the durable expanded source, generated audit data, the
human-owned ID registry, and staging bundles. A staging bundle is not proof
that its text was published.

| Path | Role |
|---|---|
| `expanded_messages.json` | Canonical expanded-bank source used by the build |
| `message_registry.json` | Human-owned ID allocation and reservation policy |
| `message_inventory.json` | Generated evidence across ROM, source, bundles, ASM, and plans |
| `*_dialogue.json` | Staging/import bundles; compare with the inventory before use |

Regenerate or verify the inventory from the repository root:

```bash
python3 Scripts/Analysis/analyze_dialogue_inventory.py --root . --write
python3 Scripts/Analysis/analyze_dialogue_inventory.py --root . --check
```

## Staging bundles

| File | NPC |
|------|-----|
| bean_vendor_dialogue.json | Magic Bean vendor |
| cartographer_dialogue.json | Secret Shell side quest |
| goron_elder_dialogue.json | Goron Mines unlock |
| korok_dialogue.json | Korok lore (10 msgs) |
| maiden_upgrades_dialogue.json | Crystal maiden upgrades |
| river_zora_elder_dialogue.json | Zora reconciliation |
| windmill_guy_dialogue.json | Song of Storms |

## Import Contract (Required)

- `id` in `yaze-message-bundle` is the index **within its bank**.
- `bank` must be correct (`vanilla` or `expanded`).
- Absolute Oracle message IDs (example: `0x1D5` / `469`) must be converted for expanded import:
  - `expanded_index = absolute_id - 0x18D`

### Safe workflow

0. Normalize/validate bundle IDs:
   - `python3 Scripts/Generate/normalize_dialogue_bundles.py --glob 'Data/dialogue/*_dialogue.json' --strict`

1. Validate bundle format/encoding:
   - `z3ed message-import-bundle --file Data/dialogue/<bundle>.json --strict`

2. Persist according to bank:
   - `expanded`: preview and publish through `z3ed message-source-sync`; commit
     `Data/dialogue/expanded_messages.json` and
     `Core/Generated/expanded_messages.asm` together
   - `vanilla`: use `z3ed ... --apply` against the base ROM workflow when desired

`z3ed ... --apply` to patched outputs like `Roms/oos168x.sfc` is not durable across rebuilds by itself.

Expanded source publication is dry-run-first and requires the previewed source
SHA in write mode:

```bash
z3ed message-source-sync \
  --project Oracle-of-Secrets.yaze \
  --file Data/dialogue/<bundle>.json \
  --format json

z3ed message-source-sync \
  --project Oracle-of-Secrets.yaze \
  --file Data/dialogue/<bundle>.json \
  --expected-source-sha256 <sha256-from-preview> \
  --write --format json
```

Native write mode serializes publication with a persistent
`.yaze-message-source-sync.lock` in each distinct source-artifact directory;
the lock files are intentionally persistent and ignored by git.
