# Status

Stage: Alpha (per PROJECT.toml)

## Current focus (2026-01-22)
- **Water Collision Fix Applied** - Hook re-enabled, needs rebuild & testing
- Verify WaterGate persistence (rooms 0x27 / 0x25) after room re-entry and save/reload
- Use runtime reload hotkey (L+R+Select+Start) after loading older save states

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
- App bundle: `/Users/scawful/src/third_party/mesen2/bin/osx-arm64/Release/osx-arm64/publish/Mesen.app`

## What exists today
- Repo contains the Oracle-of-Secrets ASM source tree (see folders like `Core/`, `Dungeons/`, `Items/`).
- `build.bat` exists for Windows builds; manual Asar usage is documented in `Docs/General/AsarUsage.md`.
- `Docs/README.md` exists.

## What does NOT exist
- No LICENSE file at repo root.

## Priorities (next 1-3 weeks)
- Verify the build process (`build.bat` and manual Asar flow).
- Document required inputs and tools (Asar version, ROM input requirements).
- Add distribution policy (patch-only) and keep it current.

## Known issues
- Build process not verified in this status doc.

## Source of truth
- `README.md`
- `Docs/README.md`
