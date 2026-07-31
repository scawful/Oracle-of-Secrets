# Message-Bridge Integration State — 2026-07-31

Purpose: exact reconciliation map for syncing the local checkout with
origin/master (11 commits: PR #114 manifest reachability, PR #115 message
source contract). Written for the clean integration pass; verified against
`origin/master` by direct inspection, not from PR descriptions.

## Upstream facts (verified)

1. Expanded messages are source-owned: `Data/dialogue/expanded_messages.json`
   (109 expanded / 0 vanilla, format `yaze-message-bundle`) generates
   `Core/Generated/expanded_messages.asm`. Do not hand-edit the generated file.
2. Bank $2F allocation, enforced by build-failing asserts:
   - `$2F8000-$2F8025` — MessageExpand loader (`Core/message.asm`)
   - `$2F8026-$2FFDFF` — expanded message data (32,218 bytes; bundle currently
     13,676 bytes ≈ 42% used)
   - `$2FFE00-$2FFFFF` — progression helpers tail (`Core/progression.asm`,
     est. 100–200 bytes used of 512)
   Overflow anywhere fails the build. This is the "detect when full" guarantee.
3. `build_rom.sh` now runs `validate_expanded_message_source.py --root` before
   assembling and regenerates `Roms/hack_manifest.json` after. Both fail closed.
4. CI: `.github/workflows/manifest-tests.yml` runs
   `Scripts/Generate/tests/` (unittest discover) on ASM/bundle/script changes.
5. `.gitignore` adds `.yaze-message-source-sync.lock`; `.gitattributes` pins LF
   on the bundle and generated ASM.

## Conflict surface: 4 files dirty locally AND changed upstream

| File | Disposition |
|---|---|
| `Docs/Planning/Plans/essence_maiden_presentation.md` | Take upstream. Local edit is a path fix upstream already includes. |
| `Oracle-of-Secrets.yaze` | Keep local. Upstream's two changes (`hack_manifest_file=Roms/hack_manifest.json`, `expected_hash=eaf2ce3d...`) are already in the local copy with identical values. Local-only lines are deliberate safety state: `labels_filename=` cleared, `save_dungeon_maps=false`, `save_graphics_sheet=false`, `autosave_enabled=false`. It also points `[build] build_script` at the tracked `./Scripts/Build/build_rom.sh 168`; upstream's `./run.sh` does not exist. |
| `Scripts/Build/build_rom.sh` | Take upstream, then re-apply 3 local-only deltas (below). Do NOT re-apply `--dev-rom`. |
| `Scripts/Generate/generate_hack_manifest.py` | Take upstream wholesale. Local copy is an intermediate draft of the same work; upstream version is covered by 552 lines of tests + CI. |

## Local-only build_rom.sh deltas worth preserving

1. Base-ROM preference swap: prefer `Roms/oos168.sfc` over legacy
   `oos168_test2.sfc` (upstream still picks legacy first).
2. Legacy-ROM message downgraded from WARNING to
   `NOTE: Ignoring legacy base ROM ...`.
3. z3dk analyzer paths lowercased: `../z3dk/scripts/` (upstream has
   `../z3dk/Scripts/`, wrong on case-sensitive filesystems).

Dropped integration delta: the local manifest call passed
`--dev-rom "$base_rom"`, but the upstream generator at integration time had no
such flag. Carrying that call-only hunk forward would have broken the build.

Follow-up resolution: the old call-only draft remains intentionally dropped.
The manifest provenance follow-up implements `--dev-rom` as a validated
generator option, passes the exact base selected by `build_rom.sh`, and covers
canonical, legacy, external, and missing-ROM cases with tests. Only that paired
generator + build-script contract is safe to use.

## Other verified upstream details

- `Sprites/all_sprites.asm`: include case fix
  `lanmola_Expanded.asm` → `lanmola_expanded.asm` (fallout of case-exact
  manifest reachability; required on case-sensitive filesystems).
- `Docs/Planning/Plans/essence_maiden_presentation.md` upstream rewrite is
  workflow-only. No story-canon content added; no Ganondorf-origin or
  two-villain material.
- Vanilla message slots (e.g. Farore intro at $0E) are NOT in the bundle
  (`vanilla: 0`); they go through the yaze/z3ed vanilla message path
  (yaze PR #178 preflight/readback).

## yaze side (as of 2026-07-31 ~18:20Z)

- Merged: #166–#181 (message bridge #176–178, palette guards #179–180,
  BG render routing report #181).
- Open: #182 (Object Tile Editor write guards, retargeted to master, awaiting
  CI), #183 (provenance for dungeon object tile writes).

## Open items

1. Integration pass itself (Codex owns; no stash/pull/pop on this checkout).
2. OoS PR #107 still open — scawful decides.
3. Dialogue text-debt batch can move to `expanded_messages.json` once synced.
4. Watch progression tail headroom if reaction tables grow (512-byte cap,
   assert-protected).
