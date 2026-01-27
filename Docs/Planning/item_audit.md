# Item Audit (oos168_test2.sfc)

Date: 2026-01-24 01:15:55

Sources:
- Chest inventory: `oracle-of-secrets/Docs/Planning/chest_inventory.json`
- Overworld items: `oracle-of-secrets/Docs/Planning/overworld_item_inventory.json`
- Scripted item gives (Link_ReceiveItem scans): `oracle-of-secrets/Docs/Planning/receiveitem_calls.json`

## Mirror checks (item id 0x1B per yaze labels)
- Chest placements:
  - room 0x74 (Desert Palace (Map Chest )), item 0x1B Mirror, big_chest=False
- Overworld items: none
- Scripted Link_ReceiveItem calls: none
Design note: Mirror is canonically intended for the Hall of Secrets (Impa grant); relocation pending.

## Specific locations checked
- Old Man cave: room `0x00D1` (from `Sprites/NPCs/followers.asm` trigger list) has **no chests** in oos168_test2.
- Grave Cave: room `0x113` has two chests (item ids `0x1A`, `0x19`), which are **Cape** / **Byrna** in vanilla labels.

## Mirror item ID confirmation (ROM table)
- Item receipt tables found in ROM at PC `0x484E8` (SRAM write table, 1-based index).
- Mirror item ID resolves to `0x1B` with value `0x02` written to `$7EF353`.

## Vanilla duplicate-item substitution (JP disassembly)
- Chest duplicate replacement uses `.overflow_replacement` in `alttp-gigaleak/DISASM/jpdasm/bank_07.asm` (lines 11011-11087).
  - Mirror row is `$FF` (no replacement), and no entry in the table maps *to* item id `0x1B`.
  - Only explicit replacements visible are Boomerang -> `0x44`, Lamp -> `0x35`, Red Boomerang -> `0x46`.
- Overworld secret substitution uses `Overworld_SubstituteAlternateSecret` in `alttp-gigaleak/DISASM/jpdasm/bank_1A.asm`; secret indices are rupees/guards/bee and never include Mirror.

## Scripted item-give call sites (LDY #imm; JSL Link_ReceiveItem)
| File | Line | Item ID | Item Name |
| --- | --- | --- | --- |
| `oracle-of-secrets/Sprites/NPCs/deku_scrub.asm` | 194 | 0x11 | Ether Medallion |
| `oracle-of-secrets/Sprites/NPCs/bug_net_kid.asm` | 51 | 0x4B | Arrow Refill (10) |
| `oracle-of-secrets/Sprites/NPCs/maku_tree.asm` | 137 | 0x3E | Fairy |
| `oracle-of-secrets/Sprites/NPCs/ranch_girl.asm` | 78 | 0x14 | Shovel |
| `oracle-of-secrets/Sprites/NPCs/mask_salesman.asm` | 248 | 0x10 | Bombos Medallion |
| `oracle-of-secrets/Sprites/NPCs/mask_salesman.asm` | 282 | 0x19 | Byrna Cane |
| `oracle-of-secrets/Sprites/NPCs/zora_princess.asm` | 139 | 0x0F | Bee Badge |
| `oracle-of-secrets/Sprites/Objects/collectible.asm` | 114 | 0x00 | None |

## Notes / caveats
- Item labels are from yaze default labels (vanilla ALTTP). Oracle-specific repurposes are not reflected in label names here.
- No custom ASM in this repo references `#$1B`, so there are no explicit custom substitutions to Mirror in Oracle code.
- Duplicate-item fallback behavior is handled by vanilla item receipt logic; needs a deeper disassembly pass to confirm there is no implicit substitution to Mirror.
