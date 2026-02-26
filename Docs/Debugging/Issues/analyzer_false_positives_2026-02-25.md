# Oracle Analyzer False Positives — Feb 25 2026

**Status:** IDENTIFIED — no ROM fix required; analyzer fix needed in z3dk
**Triggered by:** `bash run.sh 168` smoke test step 4 failing with 27 sprite table overflow errors
**Investigated commits:** `4394bad` (gameplay/collision/sprites), `0342300` (minecart room fixes)
**Related:** `Docs/Debugging/Issues/SpriteID_Overflow_Resolution.md` (the REAL overflow from Jan 2026)

---

## TL;DR for next agent

The 27 `--check-sprite-tables` errors reported by `oracle_analyzer.py` are **all false positives**. No sprite table overflow exists in the current ROM. The analyzer has two stale assumptions that produce noise:

1. **$0DB818 sentinel is wrong for this ROM** — the base ROM already patches `SpritePrep_LoadProperties` with a `JSL SpritePrep_ResetProperties` hook; the analyzer still expects the vanilla `PHB:PHK:PLB` bytes there.
2. **Twinrova's `NewMantlePrep` hook bytes are misread as sprite prep pointer overflow** — `twinrova.asm:1063` writes `JSL NewMantlePrep : RTS` at `org $068841`, which the analyzer interprets as prep pointer entries for sprite IDs $F3/$F4/$F5.

Neither the `4394bad` commit nor `0342300` introduced a sprite table overflow. The crash that prompted this investigation is attributed to stale save states (confirmed by codex analysis), with a contributing stack leak that has already been fixed.

---

## What the analyzer reports vs. what is actually there

### Error 1: Table 8 sentinel mismatch at $0DB818

**Analyzer says:** `SpritePrep_LoadProperties at $0DB818 has been overwritten — sprite property Table 8 (Deflect) overflowed past ID $F2`

**Reality:** The sentinel bytes the analyzer expects (`8B 4B AB BD 20 0E C9 00` = `PHB:PHK:PLB:LDA.w $0E20,X...`) have not been present in `oos168.sfc` or `oos168_test2.sfc` for some time. Both base ROMs already have `22 71 B8 0D 5A 8B 4B AB` at PC `$6B818`, which decodes as `JSL $0DB871 : PHY : PHB : PHK : PLB` — an intentional hook prepending `JSL SpritePrep_ResetProperties` before the original body. OOS does not write to `$0DB818`; the base ROM contains this.

**To verify:**
```python
rom = open('Roms/oos168.sfc', 'rb').read()
pc = 0x0D * 0x8000 + (0xB818 - 0x8000)  # = 0x6B818
print(rom[pc:pc+8].hex())  # should be: 2271b80d5a8b4bab
```

### Errors 2–14: Sprite Main Pointer table "overflow" at IDs $F3–$FF

**Analyzer says:** 13 entries from `$069469` to `$069481` have non-null values for sprite IDs $F3–$FF.

**Reality:** OOS writes NOTHING to those addresses. The bytes are vanilla ROM data that happen to live past the end of the sprite pointer table. Base ROM and patched ROM are byte-for-byte identical at all 13 of those addresses.

### Errors 15–27: Sprite Prep Pointer table "overflow" at IDs $F3–$F5

**Analyzer says:** `$068841`, `$068843`, `$068845` contain non-null values for sprite IDs $F3–$F5.

**Reality:** `Sprites/Bosses/twinrova.asm:1063` has:
```asm
org $068841 ; @hook module=Sprites
  JSL NewMantlePrep
  RTS
```
`NewMantlePrep` assembles to bank $32 (all_sprites.asm puts Twinrova there). The 5-byte sequence `JSL $32A86D : RTS` = `22 6D A8 32 60` is written at $068841 as a code hook, not a sprite prep pointer. The analyzer doesn't know the hook is intentional and flags those 3 words as "overflow."

---

## What the `4394bad` / `0342300` commits actually changed (ROM-level)

All changes were validated static; none introduce new crash paths.

| Area | What changed | Verdict |
|------|-------------|---------|
| `minecart_tracks.asm` | Spawn X/Y coordinates for tracks 0–16 corrected to actual stop tile positions | Data only — no logic |
| `dungeons.asm` | Replaced hardcoded `NewWaterOverlayData` address with `JSL WaterGate_SelectOverlayPointer`; org from `$2CFB00` area | Hook resolves by label; correctly assembled |
| `custom_collision.asm` | Moved `CustomRoomCollision` from `org $258000` → `org $2CFE00`; added water-fill marker tile skip ($F5) | JSL hook at `$01B95B` uses label, now resolves to `$2CFE01` ✓; `$258000` reverts to harmless vanilla bytes |
| `kydrog_boss.asm` | New boss sprite at SPRID `$CB` (well within $F2 limit) | Structurally clean; prep runs in 8-bit mode via `SEP #$30` in `NewSprPrepTable` |
| `followers.asm` | ZoraBaby: added water gate switch trigger logic | New code path, no table writes, no ID changes |

### Custom collision org move — spot check

```
$01B95B hook: 22 01 FE 2C  →  JSL $2CFE01  (= CustomRoomCollision)
$2CFE00: 6B                →  RTL  (= CustomRoomCollision_easyout)
$2CFE01: A5 B4 C9 00 20 D0 03 EE 00 02 ...  →  matches CustomRoomCollision source
$258000: 6B A5 B4 C9 00 20 D0 03  →  unchanged vanilla bytes (not touched by OOS)
```

---

## What was actually fixed this session

**`ebb03d3` — Remove orphaned PHX in `Overworld_ReloadSubscreenOverlay_Interupt`**

`Overworld/ZSCustomOverworld.asm` previously had an unbalanced `PHX` left over from a refactor in `4394bad` that switched from `PHX/PLX` to `STX.b $8C / LDX.b $8C`. The push was removed but not the corresponding PHX, leaking 2 bytes per call. Removed at line 2314.

This is a real but low-frequency bug — it causes slow SP drift during overworld subscreen reloads, not a deterministic file-load crash.

---

## Probable crash cause (from codex analysis)

The file-load crash reported around `4394bad` is attributed to **stale save states**: save states captured from a pre-`4394bad` ROM were loaded against a post-`4394bad` ROM. SRAM layout or sprite table positions differed enough to corrupt game state on load.

The PHX leak above may have contributed to SP drift that made a crash more likely with certain game states, but is not the deterministic trigger.

---

## What needs fixing in z3dk (oracle_analyzer)

The `find_sprite_table_overflow()` function in `z3dk/scripts/oracle_analyzer.py` needs two updates:

### 1. Update the sentinel at $0DB818 (line ~1166)

```python
# Current (stale):
LOAD_PROPERTIES_SENTINEL = bytes([0x8B, 0x4B, 0xAB, 0xBD, 0x20, 0x0E, 0xC9, 0x00])

# Correct for this ROM (JSL SpritePrep_ResetProperties : PHY : PHB : PHK : PLB ...):
LOAD_PROPERTIES_SENTINEL = bytes([0x22, 0x71, 0xB8, 0x0D, 0x5A, 0x8B, 0x4B, 0xAB])
```

Or better: teach the checker to recognize that `JSL $0DB871` at $0DB818 is itself a valid hook pattern and not an overflow indicator.

### 2. Cross-reference hooks.json before flagging pointer table overflow (line ~1227)

Before reporting a byte at `$06865B + ID*2` or `$069283 + ID*2` as overflow, verify it is NOT already covered by a hook in `hooks.json`. If a hook is registered for that address range, the bytes are code — not overflow. The Twinrova hook at `$068841` would be excluded this way.

**File:** `~/src/hobby/z3dk/scripts/oracle_analyzer.py`, function `find_sprite_table_overflow`, lines 1132–1260.

---

## Key addresses for this investigation

| Address | What it is |
|---------|-----------|
| `$0DB818` | `SpritePrep_LoadProperties` — already hooked in base ROM with `JSL $0DB871` |
| `$0DB871` | `SpritePrep_ResetProperties` — vanilla symbol, called by the hook above |
| `$068841` | Twinrova `NewMantlePrep` hook (`org $068841 ; @hook`) — 5 bytes of code |
| `$2CFE00` | `CustomRoomCollision_easyout` (RTL) — moved here from $258000 in `4394bad` |
| `$2CFE01` | `CustomRoomCollision` entry point — called via JSL from `$01B95B` |
| `$01B95B` | Custom room collision hook site |

---

## Valid sprite ID ceiling

The maximum valid sprite ID remains **$F2** (IDs $00–$F2 = 243 entries). The Asar assertion in `Core/sprite_macros.asm:4` enforces this at build time:
```asm
assert !SPRID <= $F2, "Sprite ID !SPRID exceeds vanilla table limit ($F2 max)."
```
Current high-water sprites: Goron `$F2`, Korok `$F1`, Mermaid/Maple/Librarian `$F0`.

The real overflow event (WindmillGuy `$F8`) is documented in `SpriteID_Overflow_Resolution.md`.
