# SRAM Reorg Conflicts (Oracle vs USDASM/ZS)

## Summary
Oracle’s story flags still live in `$7EF300–$7EF304`, which overlap the vanilla `OWFLG80–OWFLG84` map. This is a **real semantic conflict** between Oracle and USDASM/ZS logic that can clobber flags during transitions or file loads.

## Verified overlaps (active)
| Address | USDASM label (Core/ram.asm) | Oracle label (Core/sram.asm) |
| --- | --- | --- |
| `$7EF300` | `OWFLG80` | `KydrogFaroreRemoved` |
| `$7EF301` | `OWFLG81` | `DekuMaskQuestDone` |
| `$7EF302` | `OWFLG82` | `ZoraMaskQuestDone` |
| `$7EF303` | `OWFLG83` | `InCutSceneFlag` |
| `$7EF304` | `OWFLG84` | `ElderGuideStage` (also marked `FreeBlock_Story`) |
| `$7EF310` | `OWFLG90` | `FreeBlock_Items` |

Sources:
- `Core/sram.asm` defines Oracle story flags at `$7EF300–$7EF304`.  
- `Core/ram.asm` defines `OWFLG80–OWFLG90` at `$7EF300–$7EF310` (vanilla map).

## Concrete Oracle↔ZS conflict in live code
`Overworld/ZSCustomOverworld.asm` treats `$7EF300` as a **bitfield** and checks bit `$40` for the Master Sword:
- `Overworld/ZSCustomOverworld.asm:1540–1544`  
- `Overworld/ZSCustomOverworld.asm:2221–2224`  
- `Overworld/ZSCustomOverworld.asm:2274–2277`

Oracle code writes `$7EF300` as a **full-byte flag**:
- `Sprites/Bosses/kydrog.asm:95` (read as “Kydrog/Farore removed”)  
- `Sprites/Bosses/kydrog.asm:178` (`LDA #$01 : STA.l KydrogFaroreRemoved`)

This means a single Oracle write can **clear bit `$40`**, causing ZS/vanilla logic to misinterpret Master Sword state.

## Why this matters for the current softlocks
Even if the immediate crash looks like stack/NMI, this SRAM overlap is a **real, reproducible** mismatch between Oracle and USDASM semantics. During file load / transition logic, any vanilla or ZS routine that touches `OWFLG80–OWFLG9F` can clobber Oracle story flags or vice‑versa, causing incorrect flow or state transitions.

## Status
Decision: keep flags at `$7EF300–$7EF304` for now. The overlap remains a known risk until we choose a long‑term fix.

## Action items
- Audit literal `$7EF3xx` constants outside `Core/sram.asm` and replace with labels.
- Decide whether to move story flags or update OWFLG usage to avoid clobbering.
