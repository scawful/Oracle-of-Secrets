# Bottle Vendor

## Overview
`Sprites/NPCs/bottle_vendor.asm` is not a standalone sprite. It hooks the vanilla sprite routine at `$05EAC2` (`org $05EAC2 : JSL BottleVendor_MilkHandler`, lines 2-5) and sells milk for an empty bottle. The file has no `!SPRID`, `!NbrTiles`, property block, `_Long` routine, or `_Prep` routine. Its labels are `BottleVendor_*`.

## Hook Entry (`BottleVendor_MilkHandler`)
Source: `bottle_vendor.asm:7-16`.

```asm
BottleVendor_MilkHandler:
{
  LDA.l $7EF34C : BNE +
    LDA.b #$D4
    JSL Sprite_ShowSolicitedMessage
    RTL
  +
  JSR BottleVendor_SellMilk
  RTL
}
```

*   If the Ocarina byte `$7EF34C` is zero, the hook shows solicited message `$D4` and returns.
*   Otherwise it calls `BottleVendor_SellMilk`.

## State Machine (`BottleVendor_SellMilk`)
The state is `SprMiscA, X`, dispatched by `JumpTableLocal` (`bottle_vendor.asm:20-28`). Per code, runtime unverified.

| SprMiscA | Routine | Behaviour (`bottle_vendor.asm`) |
| --- | --- | --- |
| 0 | `BottleVendor_Idle` (`:30-39`) | Plays animation `(0,1,16)`, blocks passage, and shows solicited `$0187` (the offer). If Link talks, sets SprMiscA to 3. |
| 1 | `BottleVendor_BoughtMilkBottle` (`:41-76`) | If rupees `$7EF360` are at least 30 (`CMP.w #$1E`, `:44`): finds the first bottle slot `$7EF35C`-`$7EF35F` that holds `2` and sets it to `$0A` (`:48-62`), subtracts 30 rupees (`:64-68`), shows `$0188` (`:70`), and sets SprMiscA to 0. If no slot holds `2`, sets SprMiscA to 5 (`:52`). If rupees are short, sets SprMiscA to 2 (`:73-75`). |
| 2 | `BottleVendor_NotEnoughRupees` (`:78-83`) | Shows `$0189`; sets SprMiscA to 0. |
| 3 | `BottleVendor_HandlePlayerResponse` (`:85-93`) | Player response `$1CE8` = 0 (yes) sets SprMiscA to 1. Any other value sets SprMiscA to 4. |
| 4 | `BottleVendor_ComeBackAgain` (`:95-100`) | Shows `$018B`; sets SprMiscA to 0. |
| 5 | `BottleVendor_NoAvailableBottles` (`:102-108`) | Shows `$033`; sets SprMiscA to 0; sets carry. |

## Messages

| ID | Use |
| --- | --- |
| `$D4` | Hook message when `$7EF34C` is zero (no Ocarina yet) |
| `$0187` | Offer (Idle) |
| `$0188` | Bottle of milk sold (BoughtMilkBottle) |
| `$0189` | Not enough rupees |
| `$018B` | Come back again |
| `$033` | No empty bottle slot available |

## Notes
*   Price: 30 rupees (`bottle_vendor.asm:44`, `:66`).
*   Bottle slots: `$7EF35C`-`$7EF35F`. A slot holding `2` is empty and is filled with `$0A`.
*   Response byte: `$1CE8` (0 = yes).
