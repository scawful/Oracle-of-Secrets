# BG Color / Overlay Handoff — March 2026

## Current Symptom
- Exiting a dungeon into a non-overlay overworld area (e.g., $8A=$1D) yields a black screen. Palette viewer shows correct palettes loaded; BG still black.
- Runtime snapshot during failure: $8C=$FF, $8A=$33 (later $1D), $1C=$17 (BG1/2/3+OBJ on main), $1D=$00 (subscreen off), $9A=$00 (CGADSUB off), $9D=$40. $15 observed stuck at $01 despite attempts to bump it.

## Recent Attempts (now reverted)
- Added no-overlay early exits in `Overworld_ReloadSubscreenOverlay_Interupt` to clear $1D/$9A, set $1C=#17, bump $15, and skip the overlay loader.
- Added no-overlay branch in `Overworld_LoadBGColorAndSubscreenOverlay` to clear subscreen/color math and bump $15.
- Tried calling `Overworld_SetScreenBGColorCacheOnly` in the no-overlay branch; removed due to bank size assertion or no effect.
- Net result: black screen persisted; palette appeared loaded; BG still not rendering.

## Likely Next Steps
1) Instrument $15 changes: force an `INC $15` and a lightweight palette write (e.g., `JSL Overworld_SetScreenBGColorCacheOnly`) in the no-overlay path *without* skipping `LoadSubscreenOverlay`—or move the overlay=$FF handling earlier where there’s more slack.
2) Check whether map32/CHR loads are skipped when $8C=$FF: verify `LoadSubscreenOverlay`/`LoadOverworldOverlay` aren’t early-exiting and that BG1 tilemap/CHR are valid after dungeon exit.
3) Confirm screen enable at PPU, not just mirrors: read $212C/$212D during the black screen to ensure BG1 isn’t actually disabled despite $1C mirror being $17.
4) If the overlay loader path is required for palette/tile uploads, avoid early returns; instead zero $1D/$9A/$99 just before palette DMA, then let the original path run.

## Files to Revisit
- `Overworld/ZSCustomOverworld.asm`: `Overworld_ReloadSubscreenOverlay_Interupt`, `Overworld_LoadBGColorAndSubscreenOverlay`.
- `Overworld/time_system.asm`: interaction with $15/palette tints.
- Any overlay loader hooks that might skip map loads when $8C=$FF.
