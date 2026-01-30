# Oracle Annotation Tags (Asar-compatible)

These are **comment-only** tags, so they do not affect Asar builds.
They are parsed by z3dk tooling to improve disassembly readability and
enable optional runtime checks.

## Supported tags

### Watch tags
```
; @watch
; @watch fmt=hex
```
Attach these to RAM/SRAM definitions (e.g., in `Core/ram.asm`, `Core/sram.asm`)
so tooling can auto-generate Mesen2 `.watch` files.

Example:
```
LinkX = $7E0022 ; @watch fmt=hex
```

### Assert tags
```
; @assert <freeform>
```
Used for future runtime validation. The raw comment is stored in
`annotations.json` for CLI scripts to interpret.

### ABI tags
```
; @abi long_entry
; @abi m8x8
; @no_return
```
These are already parsed into `hooks.json` for analysis and disassembly.

## Tooling pipeline
1) Generate annotations:
```
python3 z3dk/scripts/generate_annotations.py \
  --root oracle-of-secrets \
  --out oracle-of-secrets/.cache/annotations.json
```

2) Generate a watch file from annotations:
```
python3 z3dk/scripts/generate_watch.py \
  --mlb oracle-of-secrets/Roms/oos168x.mlb \
  --annotations oracle-of-secrets/.cache/annotations.json \
  --out oracle-of-secrets/scripts/oracle_symbols.watch --dedupe
```

3) Load in Mesen2:
```
python3 oracle-of-secrets/scripts/mesen2_client.py watch-load --preset symbols
```

4) Evaluate @assert expressions (optional):
```
python3 oracle-of-secrets/scripts/mesen2_client.py assert-run \
  --annotations oracle-of-secrets/.cache/annotations.json
```

5) Evaluate a single expression (optional):
```
python3 oracle-of-secrets/scripts/mesen2_client.py expr-eval "MODE == $07 && SUBMODE == $00"
```
