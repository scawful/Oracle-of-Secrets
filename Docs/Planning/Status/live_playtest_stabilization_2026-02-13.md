# Live Playtest Stabilization (2026-02-13)

Status: Active | Next Review: 2026-02-15

## Scope
- Octorok invisibility in OW grass
- Ocarina tint artifacts
- Save-data / Soaring debug setup
- Minecart room status vs ROM truth

## Completed Changes

1. **Octorok** (`Sprites/Enemies/octorok.asm`): Sprite flash `LDA.w SprFlash, X`; land Octorok `$2D/$6D` so they render above OW grass.
2. **Ocarina tint** (`!ENABLE_OCARINA_SONG_TINT`): Default OFF; gates Healing/Soaring/Time tint; Storms unchanged.
3. **Save persistence** (`scripts/mesen2_client_lib/`): Fixed slot decode (2/4/6 for slots 1/2/3). `save_data_transaction.py`; `profile-apply` does WRAM→SRAM flow with verify. Persistent/volatile classification.
4. **Save-state patch**: 28 `oos168x` states updated with `all_items_no_progress`; 28/28 verified.

## Minecart Accuracy Review
Command run:
- `../yaze/scripts/z3ed dungeon-minecart-audit --rom Roms/oos168x.sfc --rooms 0x98,0x88,0x87,0x77,0xA8,0xB8,0xB9,0x78,0x89,0xDA,0xD9,0xD7,0x79,0x97,0xD8 --only-issues`

Result:
- `10/15` rooms still report issues.
- Current ROM state does **not** support "all 17 tracks verified and ready".
- Confirmed blockers:
  - `0x78`, `0x79`: no custom collision data.
  - `0xB8`: no stop tiles.
  - `0xA8`, `0x89`, `0xDA`, `0xD8`: minecart sprites not on stop tiles.

## Test Plan
- Build: `./scripts/build_rom.sh 168` → `check_zscream_overlap.py` → rom-load → `save-data profile-apply soaring_debug`
- Accept: Octorok visible in OW grass; no tint when flag off; Soaring works; minecart audit after room edits

## Next Work
1. Visual pass for octorok fix in-game
2. Song tint: default-off vs profile toggle
3. Minecart: fix `0x78`/`0x79`/`0xB8` first, then sprite-on-stop rooms
4. `travel-profile` for cross-world routing; smoke test for slot mapping
