# File Select Link GFX Regression (2026-01-30)

## Symptom
- Link sprite on the file select screen appears incorrect after recent fixes.

## Capture
- Screenshot: `/tmp/file_select_20260130.png` (headless Mesen2 run, 600 frames after reset).
  - Note: `/tmp` is ephemeral; capture a persistent screenshot if needed.

## What was checked
- File select loads sprite sheets via `LoadFileSelectGraphics`:
  - `Decompress_sprite_low` indices `0x5E`, `0x5F`, `0x6B`.
- Pointer tables (ROM) are identical in base vs patched ROM:
  - Index `0x5E` → `$988AAA`
  - Index `0x5F` → `$988E5C`
  - Index `0x6B` → `$98B3F8`
- Compressed data at those pointers is identical between:
  - `Roms/oos168_test2.sfc`
  - `Roms/oos168x.sfc`

## Hypotheses
- Runtime VRAM base (OBSEL) or sprite VRAM region is being altered after
  `LoadFileSelectGraphics` runs.
- Palette load for file select may be corrupted (equipment values or palette
  RAM overwritten), causing the Link sprite to look incorrect even if tiles are correct.

## Next steps (concrete)

1) **Confirm OBSEL after LoadFileSelectGraphics**
   - Break on `LoadFileSelectGraphics` (or its return). Read PPU mirror: `$7E0021` (OBSEL). Expected `0x02` for sprite tiles at VRAM $6000. If non-02, find which code writes to $2121.
   - Mesen2: set exec breakpoint at the routine, run to hit, then read memory at $7E0021 (size 1).

2) **Dump VRAM at sprite region**
   - After reaching file select (e.g. 600 frames after reset), dump VRAM at `$A000` (sprite tile region; size e.g. 2KB) and compare against a known-good dump or expected file-select sprite tiles. Mesen2: READ_MEMORY or debugger memory view for VRAM.

3) **Capture file-select save state**
   - Load ROM, advance to file select screen, save state to a slot (e.g. slot 3). Document slot and ROM version so tests are repeatable.

4) **Compare palette/equipment state**
   - At file select, read CGRAM (palette) and any equipment/display RAM that affects Link’s colors. Compare against vanilla or last-known-good to see if palette or equipment values are corrupted.
