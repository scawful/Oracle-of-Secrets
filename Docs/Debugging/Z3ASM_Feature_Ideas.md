# Z3ASM Feature Ideas + Z3DK Doc Hygiene (Draft)

## Goals
- Provide z3asm-specific features that improve stability and tooling without breaking Asar compatibility.
- Keep new syntax comment-only or macro-based for a smooth Asar 2.0 migration path.
- Document deltas clearly and move legacy Asar docs out of the primary path.

## z3asm Feature Ideas (Asar-safe by default)

### 1) Hook directive (comment-based)
**Idea:** Support `@hook` comment tags as a first-class z3asm feature that emits `hooks.json`.

Example (Asar-safe today):
```
; @hook name=Overworld_SetCameraBounds kind=jsl target=NewOverworld_SetCameraBounds expected_m=16 expected_x=8
```
**Benefits:** Eliminates heuristic hook classification, reduces false positives, and provides explicit ABI expectations.

Practical extension:
- Feature-gated org blocks should be representable without heuristics (e.g., “this hook is only active when `!ENABLE_*` is on”), so tooling can align to the built ROM.
  - Example (Asar-safe):
    - `org $01CC14 ; @hook name=RoomTag_ShutterDoorRequiresCart kind=jml target=RoomTag_ShutterDoorRequiresCart feature=!ENABLE_MINECART_CART_SHUTTERS`

### 2) Annotation emit (`@watch`, `@assert`, `@abi`)
**Idea:** z3asm parses comment tags and emits `annotations.json` alongside other structured outputs.

**Benefits:** Removes the need for external scanners, enables live IDE feedback, improves Mesen2 watch presets.

### 3) Section/bank allocator
**Idea:** `section "Sprites", bank=$30, size<=...` or `segment` blocks that map to `org` internally.

**Benefits:** Prevents overlap, provides better diagnostics, and improves disassembler output.

### 4) ABI linting in assembler/lsp
**Idea:** Static checks for mixed-width exit paths, PHB/PLB imbalances, JumpTableLocal X=8 contract,
PHX/PLX imbalance across long routines, and `long_entry` normalization rules.

**Benefits:** Catches common softlock risks earlier than runtime.

### 5) Structured outputs + sourcemap extensions
**Idea:** Enrich sourcemaps with module, hook, and section metadata. Emit JSON diagnostics for IDEs.

**Benefits:** Better LSP diagnostics and debugger integration (Mesen2, yaze/z3ed).

### 6) Sprite registry integration
**Idea:** Read a registry manifest (CSV/TOML) and validate Sprite IDs/dupes while emitting a canonical ID file.

**Benefits:** Prevents sprite ID drift and keeps table constraints visible to tooling.

## Asar 2.0 Compatibility Strategy
- Prefer **comment-only tags** (`; @hook`, `; @watch`) or `%OOS_*` macros that expand to plain Asar.
- Avoid new directives unless they can be compiled away or feature-gated.
- Keep all z3asm-specific syntax optional and non-fatal in Asar mode.

## Documentation Hygiene Plan (z3dk)

### A) Establish a clean z3asm doc entry point
- New doc: `docs/manual/z3asm.md`
- Focus on z3asm-only behavior and structured output (hooks.json, annotations.json).

### B) Move legacy Asar docs out of the primary path
- Relocate legacy Asar docs into `docs/legacy/` (if not already).
- Add a short `docs/legacy/README.md` explaining scope and status.

### C) Add a "Differences vs Asar" page
- Enumerate behavior changes, new outputs, and any incompatible edge cases.

### D) Add "Asar 2.0 Compatibility" page
- Explain which z3asm features are safe in Asar 2.0 and which are z3asm-only.

### E) Update README to link to z3asm docs first
- Primary docs: z3asm reference + differences + compatibility.
- Legacy Asar docs as a secondary link.

## Suggested Rollout Plan
1) Phase 0: Use comment-only tags with existing tooling (hooks + annotations). No assembler changes required.
2) Phase 1: Add z3asm emit for hooks.json + annotations.json (optional flag).
3) Phase 2: Add linting in z3lsp; enforce only on opt-in CI.
4) Phase 3: Introduce section/bank allocator as optional syntax.

## Roadmap + Minimal Prototypes
- **Hook metadata**: continue comment-only `@hook` tags; prototype: normalize tags + emit hooks.json (done), add `module`/`note` where needed.
- **Annotations**: prototype: emit `annotations.json` from z3asm comments; add a simple watcher preset generator.
- **ABI linting**: prototype: z3lsp warning set for `@abi` + width imbalance + JumpTableLocal X=8 contract.
- **Allocator**: prototype: `section` macro in `Util/macros.asm` that expands to org + bounds checks (Asar-safe).
- **Diagnostics**: prototype: sourcemap enrichment with module + section + hook id; emit a `diagnostics.json`.
- **Sprite registry**: prototype: csv manifest → id include + validator (done); add “non-fatal on build” flag.
- **Cutscene scripting**: prototype: macro DSL that assembles to compact command streams (no new directives).

## Tracking Notes
- Keep all new features gated via flags in z3asm until Asar 2.0 feature set is stable.
- Ensure any new data formats are versioned.
