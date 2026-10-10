# Data/debug: checkpoints and warps

Test data for the Mesen2-OOS **Cheats & Warps** panel (Oracle tools pane) and
the client commands `checkpoint`, `warp-entrance`, `warp-area`. Not built into
the ROM.

| File | What | Source of truth |
|------|------|-----------------|
| `warps.json` | 80 named entrances (dungeon, shrine, town, cave) and 38 overworld areas | Generated from the ROM and `Overworld/entrances.asm` |
| `checkpoints.json` | 15 story checkpoints in beat-sheet order, plus one TODO row | Hand-written; every write cites a file:line or beat row |

## Use

```bash
C="python3 Scripts/Mesen2/mesen2_client.py --socket /tmp/mesen2-<instance>.sock"
$C checkpoint --list
$C checkpoint d4-entrance          # writes WRAM + active SRAM slot, then warps
$C warp-entrance d1                # id (0x26, 26) or name ("village shop")
$C warp-entrance --list shrine
$C warp-area 0x40                  # area id or name
```

In Mesen2-OOS: Oracle tools pane (Cmd/Ctrl+Shift+O) → Warp (search box),
Checkpoints (Jump asks for confirmation), Items, Flags.

## Checkpoint rules

- `after` chains checkpoints: a checkpoint applies every write of its
  ancestors first, oldest first. `intro-bed` resets the story bytes, so every
  chain is deterministic for the bytes it touches. Bytes no checkpoint names
  (bombs, rupees, bottles, keys) keep their current values.
- Write ops: `value` (store), `set_bits` (OR), `clear_bits` (AND out).
- `inferred: true` marks a guess; its `why` says what it rests on (mostly
  heart counts and the Meadow Blade sword level).
- Save-slot safety: the writes go to WRAM `$7EF000-$7EF4FF`, then that block is
  copied to the **active** SRAM slot (main + mirror, new checksum). Other slots
  are untouched. The panel asks before it writes.
- Crystal bits follow the 2026-09-26 fix: D1 = `$02`, D6 = `$01`
  (`Docs/Debugging/Issues/world_map_icons_2026-09-26.md` section 5.0).
- The storm bit (`OOSPROG2` `$80`) stays set in the Abyss and is cleared at
  `kalyxo-return`, as in the current `Overworld/storm.asm`. On b17 and older
  builds the Abyss checkpoints therefore show rain.
- `abyss-owl` uses `EonOwlFlags` (`$7EF3A7`, read only with
  `!ENABLE_EON_OWL_ONE_SHOT = 1`). The arrival Owl is a `todo` row until it is
  placed in the ROM.

## Warp mechanisms (verified on `oos-v0.9.0-b17`, headless Mesen2)

| Target | Path | Leaving again |
|--------|------|---------------|
| Entrance, from overworld play | Vanilla door entry: `$010E` = entrance, `$10` = `$0F`, `$010C` = `$06` | Houses return to where Link stood |
| Entrance, from indoors | Death-continue reload: `$010E`, `$010A` = 1, `$1B` = 1, `$10` = `$05` | Dungeons/caves use the exit table |
| House entrance (rooms `$0100-$017F`), from indoors | Area warp to the door's area first, then the door entry | Back to that area |
| Overworld area | Dungeon-exit load: `$A0` = an `UnderworldExitData` room, `$10` = `$08` | n/a |

Checkpoints at an area reload through an entrance first, so the HUD hearts and
follower graphics (Impa) are rebuilt.

## Limits

- Areas without a dungeon/cave exit room are not warpable (for example `$2A`,
  the western forest where Farore stands). `warp-area --list` shows the 38
  that are.
- Special areas `$80+` (Maku Tree Area / Forest Glade, Zora falls) are excluded:
  loading them through `$10` = `$08` skips their setup, and walking to the edge
  ran into area `$90` with garbage tiles. `village-impa` (also the
  Farore-meeting state) and `kalyxo-return` therefore land in the village and
  outside the Hall of Secrets.
- Warps need normal play (module `$07/$09/$0B`, submodule 0): close text boxes
  first. Follower `$02` makes the game load the spawn point; the warp refuses.
- Mesen2 builds without the SPC state-load fix (`Spc::AfterStateLoad`) hang in
  the song upload on the first warp that changes song bank after loading a
  save state. Boot the ROM fresh, or use a build with the fix.
- `entrances.asm` area comments disagree with the ROM door table for 15
  entrances (for example Link's House: comment `OW 32`, ROM area `$33`). Each
  such entry has a `note`; the ROM value is used.

## Regenerate `warps.json`

After entrance or exit edits, from the mesen2-oos checkout:

```bash
python3 tools/oracle_cheats/gen_warps.py --oracle ~/src/hobby/oracle-of-secrets \
  --rom Roms/Playtest/oos-v0.9.0-b17.sfc
```

Headless check (copied ROM + copied .srm; every checkpoint rewrites the active
slot):

```bash
python3 tools/oracle_cheats/test_cheats_headless.py --socket /tmp/mesen2-<instance>.sock --boot
```
