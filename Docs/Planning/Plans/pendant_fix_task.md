# Pendant Reward Alignment — Task Description

**Created:** 2026-02-13
**Last Reviewed:** 2026-02-13
**Priority:** HIGH (blocks shrine progression integrity)
**Owner:** User/Codex (data + runtime verification)

---

## Problem

Shrine pendant rewards are not aligned with Oracle design intent.

- S1 and S2 currently use wrong chest items.
- S3 Courage reward should come from Vaati (Vitreous reskin) boss-drop flow, not a chest placement.

## Current State

| Shrine | Current Reward Path | Current Result | Target |
|--------|---------------------|----------------|--------|
| S1 Wisdom | Chest in room `0x7A` | `0x38` (Courage) | `0x39` (Wisdom) |
| S2 Power | Chest in room `0x73` | `0x39` (Wisdom) | `0x3A` (Power) |
| S3 Courage | Boss-drop path (Vaati) not implemented | No Courage reward flow | Vaati awards Courage (`0x38`) |

**Pendant of Power (`0x3A`) does not appear in any chest in the current ROM.**

## Required Fixes

| Shrine | Action | Type |
|--------|--------|------|
| S1 Wisdom | Change chest item in room `0x7A` from `0x38` -> `0x39` | Data (yaze dungeon editor) |
| S2 Power | Change chest item in room `0x73` from `0x39` -> `0x3A` | Data (yaze dungeon editor) |
| S3 Courage | Implement Vaati victory reward path to grant Courage pendant (`0x38`) and set progression bits | ASM/runtime |

## Pendant Item IDs

| Item ID | Pendant |
|---------|---------|
| `0x38` | Courage |
| `0x39` | Wisdom |
| `0x3A` | Power |

---

## How to Fix (Now)

### S1/S2 chest swaps (yaze)
1. Open ROM in yaze.
2. Room `0x7A`: set big chest item to `0x39`.
3. Room `0x73`: set big chest item to `0x3A`.
4. Save ROM.

### S3 reward path (separate implementation)
1. Confirm Vaati boss room + defeat flow entrypoint.
2. Add Courage pendant award logic to the boss clear path.
3. Ensure SRAM progression bits and item grant are consistent with shrine completion.

---

## Verification

```bash
# Chest sanity (S1/S2)
~/src/hobby/yaze/build/bin/z3ed chest-inventory --rom Roms/oos168x.sfc | grep -i pendant

# Runtime checks
python3 scripts/mesen2_client.py warp-entrance 0x33  # S1
python3 scripts/mesen2_client.py warp-entrance 0x09  # S2
# S3: run Vaati defeat path and verify Courage reward + SRAM progression
```

Expected outcome:
- S1 chest grants Wisdom.
- S2 chest grants Power.
- S3 Vaati clear grants Courage (no chest dependency).

---

## Dependencies

- S3 depends on Vaati boss implementation and clear-event wiring.
- Runtime verification depends on Mesen2 tooling for SRAM observation.
