# Pendant Reward Alignment — Task Description

**Created:** 2026-02-13
**Last Reviewed:** 2026-07-24
**Priority:** HIGH (blocks shrine progression integrity)
**Owner:** User/Codex (data + runtime verification)
**Status:** S1/S2 source-patched and statically read back; runtime pickup
pending. S3 unimplemented.

---

## Problem

S1/S2 source data is aligned by `Core/patches.asm`, but pickup/progression
behavior has not been verified in the emulator. S3 Courage still lacks its
Vaati boss-drop path.

- S1 and S2 need runtime pickup and pendant-state verification.
- S3 Courage should come from Vaati's (Vitreous reskin) boss-drop flow, not a
  chest placement.

## Current State

| Shrine | Current Reward Path | Current Result | Target |
|--------|---------------------|----------------|--------|
| S1 Wisdom | Chest in room `0x7A` | `0x39` source-patched; z3ed readback confirmed; runtime pickup unverified | `0x39` (Wisdom) |
| S2 Power | Chest in room `0x73` | `0x3A` source-patched; z3ed readback confirmed; runtime pickup unverified | `0x3A` (Power) |
| S3 Courage | Boss-drop path (Vaati) not implemented | No Courage reward flow | Vaati awards Courage (`0x38`) |

Current patched-ROM readback shows Pendant of Power (`0x3A`) in room `0x73`.

## Required Fixes

| Shrine | Action | Type |
|--------|--------|------|
| S1 Wisdom | Run runtime pickup and pendant SRAM/progression validation | Runtime |
| S2 Power | Run runtime pickup and pendant SRAM/progression validation | Runtime |
| S3 Courage | Implement Vaati victory reward path to grant Courage pendant (`0x38`) and set progression bits | ASM/runtime |

## Pendant Item IDs

| Item ID | Pendant |
|---------|---------|
| `0x38` | Courage |
| `0x39` | Wisdom |
| `0x3A` | Power |

---

## Source Fix (Implemented)

`Core/patches.asm` asserts the chest-record identities and writes:

- `$01E9F7 = $39` for room `0x7A` (Wisdom)
- `$01E9E8 = $3A` for room `0x73` (Power)

Rebuild the patched ROM from the recorded base. Do not treat a direct edit to a
gitignored ROM as the durable fix.

### S3 reward path (separate implementation)
1. Confirm Vaati boss room + defeat flow entrypoint.
2. Add Courage pendant award logic to the boss clear path.
3. Ensure SRAM progression bits and item grant are consistent with shrine completion.

---

## Verification

```bash
# Static chest readback (S1/S2)
../yaze/scripts/z3ed dungeon-list-chests \
  --rom Roms/oos168x.sfc --room 0x7A --format json
../yaze/scripts/z3ed dungeon-list-chests \
  --rom Roms/oos168x.sfc --room 0x73 --format json

# Runtime checks
python3 Scripts/Mesen2/mesen2_client.py warp-entrance 0x33  # S1
python3 Scripts/Mesen2/mesen2_client.py warp-entrance 0x09  # S2
# S3: run Vaati defeat path and verify Courage reward + SRAM progression
```

Static readback currently confirms:
- S1 chest data is Wisdom (`0x39`).
- S2 chest data is Power (`0x3A`).

Runtime acceptance (pending):
- S1 pickup grants Wisdom and updates the intended pendant/progression state.
- S2 pickup grants Power and updates the intended pendant/progression state.
- S3 Vaati clear grants Courage (no chest dependency).

---

## Dependencies

- S3 depends on Vaati boss implementation and clear-event wiring.
- Runtime verification depends on Mesen2 tooling for SRAM observation.
