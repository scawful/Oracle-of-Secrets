# Progression Infrastructure — Centralized Helpers

## Summary

Design centralized progression routines to replace scattered, ad-hoc crystal checks and MapIcon logic across multiple NPCs. Introduces three shared systems: a **MapIcon advancement table**, a **crystal count helper**, and an **NPC reaction framework** for threshold-based alternate messages.

## Current State

### The Problem: Scattered Progression Logic

Multiple files independently check crystal flags and story progression, each with its own implementation:

**Maku Tree** (`Sprites/NPCs/maku_tree.asm:147–176`):
- Waterfall checks D5 → D3 → D1 (missing D2, D4, D6)
- Sets MapIcon only on first meeting

**Zora NPC** (`Sprites/NPCs/zora.asm:154–167`):
- Checks `!Crystal_D4_ZoraTemple` ($20) for post-D4 dialogue
- Hardcoded message IDs ($1A4, $1A5, $1A6)

**Village Elder, Deku Scrub, other NPCs:**
- Each has its own flag-check pattern
- No shared infrastructure

**Crystal flags** (`Core/sram.asm`):
```
$7EF37A — Crystal bitfield
  D1 Mushroom Grotto  = $01
  D6 Goron Mines      = $02
  D5 Glacia Estate    = $04
  D7 Dragon Ship      = $08
  D2 Tail Palace      = $10
  D4 Zora Temple      = $20
  D3 Kalyxo Castle    = $40
```

**MapIcon values** (`Core/sram.asm:171–182`):
```
$7EF3C7 — MapIcon
  $00 = Maku Tree
  $01 = D1 Mushroom Grotto
  $02 = D2 Tail Palace
  $03 = D3 Kalyxo Castle
  $04 = D4 Zora Temple
  $05 = D5 Glacia Estate
  $06 = D6 Goron Mines
  $07 = D7 Dragon Ship
  $08 = Fortress
  $09 = Tail Pond
```

### What Centralization Solves

1. **Consistency:** All NPCs use the same crystal-count logic — no more mismatched checks
2. **Maintainability:** Adding a new dungeon means updating one table, not 8 NPCs
3. **MapIcon correctness:** MapIcon advances reliably regardless of which NPC the player visits
4. **NPC reactions:** Easy to add "the world reacts to your progress" flavor without per-NPC custom code

## Proposed Changes

### 1. Crystal Count Helper

A shared routine that counts set bits in the crystal bitfield and returns the count in A.

```asm
; Returns crystal count in A (0-7)
; Clobbers: A (8-bit on exit)
GetCrystalCount:
{
  PHX
  SEP #$20        ; 8-bit A
  LDA.l Crystals
  LDX.w #$0000    ; counter
  .loop
    LSR A : BCC .no_bit
    INX
  .no_bit
    CMP.b #$00 : BNE .loop
  TXA
  PLX
  RTL
}
```

**Usage anywhere in codebase:**
```asm
JSL GetCrystalCount
CMP.b #$03 : BCS .has_three_or_more
```

### 2. MapIcon Advancement Table

A lookup table indexed by crystal count that returns the correct next MapIcon:

```asm
; Indexed by crystal count (0-7)
MapIconAdvanceTable:
  db !MapIcon_D1_MushroomGrotto  ; 0 crystals → go to D1
  db !MapIcon_D2_TailPalace      ; 1 crystal  → go to D2
  db !MapIcon_D3_KalyxoCastle    ; 2 crystals → go to D3
  db !MapIcon_D4_ZoraTemple      ; 3 crystals → go to D4
  db !MapIcon_D5_GlaciaEstate    ; 4 crystals → go to D5
  db !MapIcon_D6_GoronMines      ; 5 crystals → go to D6
  db !MapIcon_D7_DragonShip      ; 6 crystals → go to D7
  db !MapIcon_Fortress           ; 7 crystals → go to Fortress
```

**Helper routine:**
```asm
; Sets MapIcon based on current crystal count
; Clobbers: A
UpdateMapIcon:
{
  PHB : PHK : PLB
  JSL GetCrystalCount
  TAX
  LDA.w MapIconAdvanceTable, X
  STA.l MapIcon
  PLB
  RTL
}
```

**Note:** This table assumes a fixed dungeon order (D1→D2→D3→...). If the game supports non-linear dungeon order, the table needs to be replaced with a bitmask-to-next-dungeon mapping.

### 3. NPC Reaction Framework

A threshold-based system where NPCs check the crystal count against a threshold and select an alternate message if met.

**Data structure (per NPC):**
```asm
; NPC reaction entry: 3 bytes each
;   byte 0: crystal threshold (show alternate if count >= this)
;   byte 1-2: alternate message ID (16-bit)
NPCReaction_Zora:
  db $04 : dw $01A6   ; after 4+ crystals, show post-D4 message
  db $00 : dw $01A4   ; default message (threshold 0 = always)

NPCReaction_RanchGirl:
  db $05 : dw $xxxx   ; after 5+ crystals, Twinrova-cursed silence
  db $00 : dw $yyyy   ; default message
```

**Shared dispatch algorithm (pseudocode):**
```text
count = GetCrystalCount()
for (threshold, message_id) in reaction_table:
  if threshold == 0 or count >= threshold:
    return message_id
```

Implementation notes:
- Keep reaction tables in each NPC ASM file (locality), but keep the iterator/selection routine in shared code (`Core/progression.asm`).
- Prefer returning a 16-bit message ID and let the caller use existing message display macros (so you don't duplicate message plumbing).

### NPCs That Should Use the Shared System

| NPC | File | Current Behavior | Proposed Threshold |
|---|---|---|---|
| Maku Tree | `Sprites/NPCs/maku_tree.asm` | Waterfall check (D1/D3/D5 only) | Crystal count → message table |
| Zora (Sea) | `Sprites/NPCs/zora.asm` | Checks D4 crystal | 4+ crystals → post-D4 |
| Ranch Girl | `Sprites/NPCs/ranch_girl.asm` | Unknown | 5+ crystals → cursed silence (Twinrova foreshadow) |
| Bug Net Kid | `Sprites/NPCs/bug_net_kid.asm` | Unknown | 3+ crystals → new dialogue |
| Bottle Vendor | `Sprites/NPCs/bottle_vendor.asm` | Unknown | 6+ crystals → endgame stock |
| Impa | `Sprites/NPCs/impa.asm` | Hall of Secrets presence | Story flags (not crystal-based) |
| Village Elder | Referenced in codebase | Basic dialogue | 2+ crystals → lore hints |
| Followers | `Sprites/NPCs/followers.asm` | Follow behavior | Crystal-gated commentary |

### Story Flag Reactions (Non-Crystal)

Some NPCs react to story flags rather than crystal count:

| Flag | Source | NPCs Affected |
|---|---|---|
| `!Story_AbyssSevered` | Post-Kydreeok | Abyss NPCs, Gossip Stones |
| `!Story_IntroComplete` | After prologue | Maku Tree first meeting |
| `MakuTreeQuest` | Met Maku Tree | Multiple town NPCs |

These use the same framework but check `StoryProgress` / `StoryProgress2` instead of `Crystals`.

## Affected Files

| File | Change |
|---|---|
| **New:** `Core/progression.asm` (or section in `Core/patches.asm`) | `GetCrystalCount`, `UpdateMapIcon`, `ShowReactionMessage` |
| `Core/sram.asm` | No changes (uses existing definitions) |
| `Sprites/NPCs/maku_tree.asm` | Refactor waterfall to use shared helpers |
| `Sprites/NPCs/zora.asm` | Refactor D4 check to use reaction framework |
| `Sprites/NPCs/ranch_girl.asm` | Add reaction table |
| `Sprites/NPCs/bottle_vendor.asm` | Add reaction table |
| `Sprites/NPCs/bug_net_kid.asm` | Add reaction table |
| `Sprites/NPCs/followers.asm` | Add crystal-gated commentary |

## Open Questions

1. **Non-linear dungeon order:** The MapIcon table assumes D1→D2→D3→... in order. If the player can do dungeons out of order, the "next dungeon" isn't predictable by crystal count alone. Do we need a bitmask-based "first uncompleted dungeon" lookup instead?
2. **Reaction table location:** Should NPC reaction tables live in each NPC's ASM file (locality) or in a central `progression.asm` (discoverability)? Recommend: tables in NPC files, shared routines in `Core/progression.asm`.
3. **Story flag reactions:** Should story-flag checks use the same framework as crystal checks, or a separate system? The threshold model maps cleanly to crystal counts but less cleanly to bitfield flags.
4. **Performance:** `GetCrystalCount` loops through 7 bits. This is negligible (~30 cycles) but could be replaced with a lookup table if called frequently per frame. Not a concern for NPC dialogue triggers.

## Dependencies

- `maku_tree_hint_cascade.md` — The Maku Tree's refactored hint dispatch is the first consumer of this infrastructure.
- `gossip_stone_additions.md` — Gossip Stones may use the reaction framework for progression-gated messages.
- `kydrog_mask_stalfos_form.md` — `!Story_AbyssSevered` flag is defined here and consumed by the reaction framework.

## Dev Checklist (Guardrails + Validation)

Guardrails:
- Keep the first implementation scoped: add shared helpers first, then convert one NPC at a time (avoid multi-NPC refactors in one commit).
- If a converted NPC becomes unstable, prefer feature-gating its new path (so you can keep shared helpers without blocking builds).

Validation:
```bash
./scripts/build_rom.sh 168
python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x.sfc --hooks hooks.json --check-hooks --find-mx --find-width-imbalance --check-abi --check-phb-plb --check-jsl-targets --check-rtl-rts --strict
```

Runtime spot-checks (minimum):
- MapIcon advances correctly after each crystal (verify `MapIcon` at `$7EF3C7` changes as expected).
- Zora NPC switches to the post-threshold message without breaking existing dialogue flow.
- Maku Tree waterfall guidance uses the centralized mapping and does not regress to a partial dungeon set.
