# Dialogue bundles

yaze-message-bundle JSON files for NPC dialogue. Source for Gemini/Codex import into ROM.

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
   - `python3 scripts/normalize_dialogue_bundles.py --glob 'Data/dialogue/*.json' --strict`

1. Validate bundle format/encoding:
   - `z3ed message-import-bundle --file Data/dialogue/<bundle>.json --strict`

2. Persist according to bank:
   - `expanded`: commit to `Core/message.asm` (durable source-of-truth for rebuilds)
   - `vanilla`: use `z3ed ... --apply` against the base ROM workflow when desired

`z3ed ... --apply` to patched outputs like `Roms/oos168x.sfc` is not durable across rebuilds by itself.
