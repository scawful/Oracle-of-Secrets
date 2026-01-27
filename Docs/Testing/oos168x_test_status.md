# OOS168x Testing Status

**Date:** 2026-01-22
**Tester:** scawful + Codex
**Build:** oos168x.sfc (patched from oos168.sfc)

---

## ROM Information

| Property | Value |
|----------|-------|
| Source ROM | `Roms/oos168.sfc` |
| Source MD5 | `2eb02125e1f72e773aaf04e048c2d097` |
| Patched ROM | `Roms/oos168x.sfc` |
| Patched MD5 | `6211297eeabb2f4b99040ba8cf2cce5a` |
| Git Commit | `32a9a3d` (Fix water debug overlay position) |
| Build Script | `./scripts/build_rom.sh 168` |
| Assembler | Asar (from `third_party/asar-repo/`) |

## Changes from oos168.sfc

### Water Collision System (NEW)
- **File:** `Dungeons/Collision/water_collision.asm`
- **Hook 1:** `$01F3D2` - `WaterGate_FillComplete_Hook` (ENABLED)
  - Triggers when water fill animation completes
  - Writes collision data to `$7F2000` (COLMAPA) and `$7F3000` (COLMAPB)
  - Sets SRAM persistence flag at `$7EF411`
- **Hook 2:** `$0188DF` - `Underworld_LoadRoom_ExitHook` (ENABLED in source)
  - Recomputes torch table end condition (no stale Z flag reliance)
  - Re-enabled in `Dungeons/dungeons.asm` (needs rebuild + retest)
  - **Expected Effect:** Water collision should persist on room re-entry

### Collision Data (Room 0x27 - Zora Temple Water Gate)
Y-offsets shifted +3 tiles to account for game's +20px Y check offset:
- Vertical channel: Y=15 (was Y=12), Y=31 (was Y=28)
- Horizontal swim area: Y=41-43 (was Y=38-40), X=5-57
- Total tiles: 174

---

## Test Results

### WORKING ✅

| Feature | Status | Notes |
|---------|--------|-------|
| Dungeon exit/re-entry | ✅ Fixed | Crashes stopped after disabling room load hook |
| Overworld transitions | ✅ Fixed | Walking between areas works correctly |
| Water fill animation | ✅ Working | Room 0x27 water fills visually |
| Partial swim collision | ✅ Working | Horizontal strip in Room 0x27 allows swimming |
| Dungeon corner graphics | ✅ OK | Was stale save state artifact |

### ISSUES ⚠️

| Issue | Severity | Description |
|-------|----------|-------------|
| Incomplete water collision | Medium | Only horizontal strip works; full water mask shape not covered |
| Water persistence | Medium | Hook re-enabled in source; needs retest after rebuild |
| Fishing Rod GFX | Low | Graphics missing in menu |
| Ring Box GFX | Low | Icons offset, frame messed up |
| Magic Bag GFX | Low | Graphics messed up |
| Ocarina Song Frame | Low | Frame corrupted, song icons OK |

### Menu Graphics Issues (Pre-existing?)

These may predate the water collision work. Relevant commits:
- `740571c` (Dec 8, 2025) - "upgrade submenus with hints, indicators"
- `f508f9a` (Dec 8, 2025) - "menu scroll fixes"

Files involved:
- `Menu/menu_draw.asm` - Drawing functions
- `Menu/menu_gfx_table.asm` - Item graphics data
- `Menu/tilemaps/*.tilemap` - Tilemap binary data

---

## Debug Infrastructure Created

| Script | Purpose | Location |
|--------|---------|----------|
| `debug_transitions.lua` | Module/room change tracking, stuck detection | `scripts/` |
| `debug_crash_detector.lua` | Hook monitoring, invalid state detection | `scripts/` |
| `debug_overworld.lua` | Overworld area transitions, edge detection | `scripts/` |
| `mesen_water_debug.lua` | Water collision overlay (existing) | `scripts/` |
| `verify_water_gate.lua` | Automated water gate test (existing) | `scripts/` |

`verify_water_gate.lua` supports `MESEN_LOADSTATE=/path/to/state.mss` for deterministic headless runs.

### Runtime Reload Hotkey (Save-State Safety)
- **Combo:** `L + R + Select + Start`
- **Effect:** Rebuilds message pointer table (dialog dictionaries) + reloads sprite graphics properties + reloads overworld/underworld sprite list based on `INDOORS`
- **Use:** After loading older save states following ROM rebuilds

---

## Next Steps

### Priority 1: Fix Water Collision Coverage
- [ ] Map the actual water mask shape in Room 0x27
- [ ] Add collision data for missing areas (vertical sections, edges)
- [ ] Test with `mesen_water_debug.lua` to visualize collision values

### Priority 2: Fix Room Load Hook
- [ ] Retest `Underworld_LoadRoom_ExitHook` after rebuild
- [ ] Verify persistence on room re-entry and save/load

### Priority 3: Investigate Menu Bugs
- [ ] Determine if pre-existing or new regression
- [ ] Check tilemap loading in `Menu_Draw*` functions
- [ ] Verify `SEP`/`REP` state consistency

---

## Reproduction Steps

### Build patched ROM:
```bash
cd /Users/scawful/src/hobby/oracle-of-secrets
./scripts/build_rom.sh 168
```

### Launch with debugger:
```bash
open /Applications/Mesen2\ OOS.app \
  --args /Users/scawful/src/hobby/oracle-of-secrets/Roms/oos168x.sfc
```

### Load debug script:
In Mesen2: Tools → Run Script → `scripts/debug_transitions.lua`

---

## Files Modified (Uncommitted)

```
M Dungeons/Collision/water_collision.asm
M Dungeons/dungeons.asm  (room load hook re-enabled)
M Util/item_cheat.asm    (runtime reload hotkey)
M Docs/...
M scripts/sync_mesen_saves.sh
```

## Archive Location

Previous builds archived to:
`~/Documents/OracleOfSecrets/Roms/`
