# Width-Dependent Stack Imbalance — Fix Spec

**Purpose:** Document the four highest-impact PHA/PLA (and PHX/PLX, PHY/PLY) width mismatches that can leave SP wrong and feed the overworld/dungeon softlock chain. NMI saves SP to `$7E1F0A` and restores via TCS; a shifted stack corrupts that save.

**Status:** Pull sites are in vanilla ROM (bank 06/03/05/1B). Oracle does not assemble these routines; fixes require either (1) ROM patches at the listed addresses, or (2) ensuring callers use consistent width before calling. The sprite dispatch PHP/PLP wrapper reduces exposure but does not fix cross-call pairs.

---

## 1. Oracle_Ancilla_CheckDamageToSprite ↔ Oracle_Sprite_CheckIfLifted

| Role   | Address   | Width   | Effect        |
|--------|-----------|---------|---------------|
| Push   | `$06ECC8` | M=16 (2B) | PHA pushes 2 bytes |
| Pull   | `$06ACF1` | M=8 (1B)  | PLA pulls 1 byte → stack shift 1B |

**Fix pattern (at pull site):** Ensure M=16 before PLA so 2 bytes are pulled:
```asm
REP #$20   ; M=16-bit
PLA
SEP #$20   ; restore 8-bit if needed
```
Requires patching vanilla at `$06ACF1` (e.g. replace PLA with JSL to a stub that does REP #$20 : PLA : SEP #$20 : RTL).

**Scope:** 14 occurrences across 8 sprite routines (see OverworldSoftlock_RootCause.md).

---

## 2. Overworld_Entrance ↔ Oracle_ApplyRumbleToSprites

| Role   | Address   | Width   | Effect        |
|--------|-----------|---------|---------------|
| Push   | `$1BC1C3` | M=16 (2B) | PHA in Overworld_Entrance |
| Pull   | `$068142` / `$068189` | M=8 (1B) | PLA in ApplyRumbleToSprites |

**Fix pattern:** At `$068142` and `$068189`, pull with M=16 (REP #$20 : PLA : SEP #$20) or patch caller at `$1BC1C3` to push with M=8 (SEP #$20 : PHA) if semantics allow.

---

## 3. Oracle_Sprite_DrawMultiple_quantity_preset

| Role   | Address   | Width   | Effect        |
|--------|-----------|---------|---------------|
| Push   | `$05DF7A` | X=16 (2B) | PHX pushes 2 bytes |
| Pull   | `$05DFE3` | X=8 (1B)  | PLX pulls 1 byte → stack shift 1B |

**Fix pattern:** At pull site, REP #$10 before PLX then SEP #$10; or at push site SEP #$10 before PHX.

---

## 4. Oracle_Link_Initialize

| Role   | Address   | Width   | Effect        |
|--------|-----------|---------|---------------|
| Push   | `$030CC8` | X=16 (2B) | PHY pushes 2 bytes |
| Pull   | `$038B2F` / `$038B42` | X=8 (1B) | PLY pulls 1 byte → stack shift 1B |

**Fix pattern:** At pull site(s), REP #$10 before PLY then SEP #$10; or at push site SEP #$10 before PHY.

---

## References

- [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) — mechanism, TCS sites, width analysis
- [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) — Fix 1.3–1.6, Option A/B patterns
- `width_imbalance_report_20260130.json` — full static analysis output

## Additional Oracle-Side Guard (Not A Vanilla Patch)

The static report also flagged a width-dependent `PHX/PLX` mismatch risk in `ApplyManhandlaGraphics` (`Sprites/Bosses/manhandla.asm`) when invoked from transition code.

Practical hazard:
- `STX` to PPU regs (`$2100`, etc.) is only safe when X is **8-bit**.

Fix applied in Oracle ASM (no vanilla patch required):
- `ApplyManhandlaGraphics`: `PHP : SEP #$10` before `PHX`/`STX`, and `PLP` on exit.
