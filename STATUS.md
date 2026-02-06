# Status

Stage: Alpha (per PROJECT.toml)

## Planning pointers
- Roadmap: `ROADMAP.md`
- Backlog + epics: `oracle.org`
- Release definition + guardrails: `Docs/Plans/release_2026_definition.md`
- Tooling references: `Docs/Tooling/` (esp. `AgentWorkflow.md`, `Z3DK_Analyzer_Findings.md`)
- Stability “stop-ship” notes: `Docs/STABILITY.md`
- Feature isolation flags: `Config/module_flags.asm` + `Config/feature_flags.asm`

## Current focus (2026-02-06)
- **Goron Mines (D6) minecart**: fix room-data invariants + expand to signature mechanic.
  - Use `z3ed dungeon-minecart-audit` to catch: missing stop tiles, carts not placed on stop tiles, track subtype mismatches.
  - Design plan: `Docs/Plans/goron_mines_minecart_design.md`
- **Progression consistency**: start converting NPCs to shared helpers (crystal count, MapIcon, reaction tables).
  - Spec + test plan: `Docs/Plans/progression_infrastructure.md`
- **Regression guardrails**: use feature/module flags plus the autonomous debugger to catch hardlocks early.
  - Smoke suite: `bash scripts/run_regression_tests.sh smoke --no-moe --fail-fast`
  - Manual play monitor: `python3 -m scripts.campaign.autonomous_debugger --monitor --fail-on-anomaly`

## Current focus (2026-01-24)
- **Follower Transition Fixes Applied** - Fixed black screen on building entry, stairs, room transitions
  - Two bugs fixed: 16-bit/8-bit mode mismatch + Data Bank addressing
  - ROM rebuilt and verified: `Roms/oos168x.sfc`
- **Testing Needed**: Building entry, dungeon transitions, staircases
- **Water Collision Fix Applied** - Hook re-enabled, needs testing
- Verify WaterGate persistence (rooms 0x27 / 0x25) after room re-entry and save/reload
- Use runtime reload hotkey (L+R+Select+Start) after loading older save states

## Follower Transition Fixes (2026-01-24)

### Problem
Black screen when using staircases, entering buildings, or transitioning between dungeon rooms. Screen would go black and stay black (game hang).

### Root Causes Discovered

**Bug 1: 16-bit/8-bit Mode Mismatch (Intraroom Hook)**

The `CheckForFollowerIntraroomTransition` hook at `$0289BF` was called with A in 16-bit mode but used 8-bit operations.

**Bug 2: Data Bank Addressing (Both Hooks)**

Both follower hooks used absolute addressing (`STA.w $7EF3CC`) instead of long addressing (`STA.l $7EF3CC`). When called from Module07 (bank $02), the Data Bank register is not $7E, causing writes to go to wrong memory locations (ROM mirrors instead of WRAM).

### Fixes Applied

**CheckForFollowerIntraroomTransition:**
```asm
CheckForFollowerIntraroomTransition:
{
  STA.l $7EC007           ; Store 16-bit A (vanilla behavior)
  SEP #$20                ; Switch to 8-bit A for our logic
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA #$0B : STA.l $7EF3CC  ; Long addressing - bank-agnostic
  .not_in_cart
  REP #$20                ; Restore 16-bit A mode before returning
  RTL
}
```

**CheckForFollowerInterroomTransition:**
```asm
CheckForFollowerInterroomTransition:
{
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA.l $7EF3CC     ; Long addressing
    PHX
    LDX.w !MinecartCurrent
    LDA.b #$01 : STA.l $7E0F00, X  ; Long indexed addressing
    PLX
  .not_in_cart
  JSL $01873A ; Underworld_LoadRoom
  RTL
}
```

**Key changes:**
- `STA.w $7EF3CC` → `STA.l $7EF3CC` (opcode $8F)
- `STA $0F00, X` → `STA.l $7E0F00, X` (opcode $9F)
- Added SEP #$20 / REP #$20 wrapper for intraroom hook

### ROM Verified
Assembled ROM (`Roms/oos168x.sfc`) confirmed to use correct opcodes:
- $8F = STA long (24-bit absolute)
- $9F = STA long,X (24-bit absolute indexed)

### Files Modified
- `Sprites/NPCs/followers.asm` - Fixed both transition hooks

### Verification Needed
1. ✅ ROM built: `./scripts/build_rom.sh 168`
2. Load in Mesen2 (optional: use `scripts/debug_building_entry.lua`)
3. Test intra-room transitions (stairs, layer changes)
4. Test inter-room transitions (doors between rooms)
5. Test building entry (houses, shops, dungeons)
6. Test dungeon exit back to overworld

## Water Collision Fix (2026-01-21)

### Problem
Link could only swim in a thin strip of the water area in Room 0x27. Collision values weren't being applied to the correct tiles.

### Root Cause Discovered
The vanilla `TileDetect_MainHandler` routine at `$07D077` adds **direction-based pixel offsets** to Link's position before checking collision tiles. For deep water checks, this is typically:
- **+20 pixels Y** (checks at Link's feet, not center)
- **+8 pixels X** (depending on direction)

This means when Link is visually standing at tile Y=39, the game actually checks collision at tile Y=41-42 (20 pixels ÷ 8 pixels/tile ≈ 2.5 tiles).

### Fix Applied
Shifted all collision data in `Dungeons/Collision/water_collision.asm` down by 3 tiles:

| Original | Fixed | Purpose |
|----------|-------|---------|
| Y=12 | Y=15 | Vertical channel |
| Y=28 | Y=31 | Vertical channel |
| Y=38 | Y=41 | Main water area |
| Y=39 | Y=42 | Main water area |
| Y=40 | Y=43 | Main water area |

### Files Modified
- `Dungeons/Collision/water_collision.asm` - Corrected collision offsets
- `Docs/Issues/WaterCollision_Handoff.md` - Added root cause analysis

### Verification Needed
1. Build ROM with Asar
2. Load in Mesen2 with `mesen_water_debug.lua`
3. Navigate to Room 0x27
4. Walk into water from all directions
5. Verify swim state triggers at visual water boundary
6. Test persistence on room re-entry and save/reload
7. If using old save states, press L+R+Select+Start to reload caches

## Mesen2 build + WaterGate verification plan
### Claude tasks
- Find the latest macOS build steps for Mesen2 (deps, CMake flags, SDL2/Qt requirements).
- Confirm if Mesen2 has a CLI flag to auto-load a ROM + Lua script (for `scripts/mesen_water_debug.lua`).
- Note the best place to install the built app and any codesigning quirks.

### Local tasks (Codex)
- Build patched ROM and run `scripts/mesen_water_debug.lua` during water gate testing.
- Verify persistence on room re-entry and after save/reload; log results here.
- Archive oos91x saves/states alongside the ROMs for quick regression checks.

### Build status
- Built Mesen2 with: `SDKROOT=$(xcrun --sdk macosx --show-sdk-path) make`
- App bundle (preferred): `/Applications/Mesen2 OOS.app`

## What exists today
- Repo contains the Oracle-of-Secrets ASM source tree (see folders like `Core/`, `Dungeons/`, `Items/`).
- `build.bat` exists for Windows builds; manual Asar usage is documented in `Docs/General/AsarUsage.md`.
- `Docs/README.md` exists.

## What does NOT exist
- No LICENSE file at repo root.

## Priorities (next 1-3 weeks)
- Verify the build process (`scripts/build_rom.sh` and manual Asar flow).
- Document required inputs and tools (Asar version, ROM input requirements).
- Add distribution policy (patch-only) and keep it current.
- [ ] Add LICENSE file to repository root.

## Build Process (Verified)

To build the Oracle of Secrets ROM:
1. Ensure `asar` is in your PATH.
2. Provide a base ROM at `Roms/oos168x.sfc`.
3. Run the build script:
   ```bash
   ./scripts/build_rom.sh 168
   ```
4. Output will be generated at `Roms/oos168x.sfc` (patched).

For specific sprite or dungeon work, use the corresponding ASM files in `Sprites/` or `Dungeons/` with `asar` directly as documented in `Docs/General/AsarUsage.md`.

## Source of truth
- `README.md`
- `Docs/README.md`
