# Oracle of Secrets: item progression audit

Date: 2026-09-27. Read-only. No repo file or ROM edited, no build, no emulator.
ROMs read (copies in this scratch dir): `Roms/oos168.sfc` (base, `base.sfc`), `Roms/Playtest/oos-play.sfc`
(b28 patched, `play.sfc`), vanilla US 1.0 (`vanilla.sfc`). Nothing here was runtime-tested.

Status tags: **V-ROM** = read from ROM bytes or z3ed on a copy. **V-CODE** = read in ASM source.
**INF** = inferred from vanilla engine rules plus V-ROM data. **DOC** = planning docs only.

## 0. Headline

1. The "Red Mail in 21 chests" is a label bug, not a data bug. The Feb-2026 docs used yaze labels that
   are shifted by one ID. Byte `0x24` is a Small Key. Real Red Mail (`0x23`) is in one chest: D8 room
   `0x5C` (big chest). Current `z3ed dungeon-list-chests` uses correct (0-based) names.
2. Two static soft-locks block the whole late game: **D7 has no big key** (its big-key bit is shared with
   S3, whose big key sits behind S3's own big-key door). **D8's big key is inside a big chest.**
3. The Titan's Mitt exists only in orphan room `0x92` (no entrance). It is unobtainable.
4. The Magic Mirror ("Mirror of Time") is in the Hidden Grave (room `0x113`, graveyard LW `0x0F`),
   not in room `0x74`. Room `0x74` holds the Power Glove.
5. A second Ocarina source (chest in room `0x11E`) writes song level 3, which skips the Ranch Girl /
   Mask Salesman chain or deletes the Song of Soaring (4 -> 3).

## 1. Method (evidence sources)

- Receipt tables (usdasm `bank_09.asm` pool `AncillaAdd_ItemReceipt`): SRAM target `$09:84E8`
  (2 bytes/item), value `$09:8580`, gfx `$09:8404`; message table `$08:C2DD`. Diffed all 0x4C
  entries, vanilla vs base vs play (`receipt_dump.py`).
- Chest table `$01:E96E` (PC `0xE96E`), 168 x 3 bytes; the lookup loop is hard-capped at
  `CPX #$01F8` (`$01:EBF5`). The Nth chest object in a room opens the Nth table entry for that room.
  A big chest is decided by bit 15 of the **table entry** plus `$7EF366 & DungeonMask[$040C]`
  (`$01:EC13-EC21`).
- `z3ed dungeon-list-chests`, `dungeon-describe-room --include-objects` (counted chest objects
  `0xF99`/`0xFB1`), `dungeon-list-pot-items`, `overworld-find-tile`, `message-read` (item texts).
- The prior room census in this dir (`room_census.csv`) for room -> dungeon ownership and entrances.
- Oracle ASM: every `Link_ReceiveItem` call, every direct item SRAM write, every item SRAM read used as a gate.

## 2. What each repurposed ID really gives (V-ROM receipt table + item message)

| ID | Vanilla name | Oracle item | SRAM write | Msg | Changed vs vanilla |
|---|---|---|---|---|---|
| 0x00 | Sword+Shield | Small sword + shield (L1) | `$7EF359=1` | 0x48 | msg only |
| 0x01 | Master Sword | **Meadow Blade (L2)** | `$7EF359=2` | 0x70 | chest-safe patch `$0987CA` |
| 0x03 | Golden Sword | **Master Sword (L4)**, pedestal | `$7EF359=4` | 0x6F | pedestal gives 0x03 (`$0589AF`) |
| 0x0F/10/11 | Bombos/Ether/Quake | Zora Mask / Bunny Hood / Deku Mask | `$347/$348/$349=1` | 0x64/63/65 | slots reused |
| 0x13 | Shovel | **Goldstar** (Hookshot=2) | `$7EF342=2` | 0x54 | table edited |
| 0x14 | Flute | **Ocarina, song level 3** | `$7EF34C=3` | 0x67 | table edited (was 2) |
| 0x18 | Byrna | **Fishing Rod** | `$7EF351=1` | 0x79 | slot reused |
| 0x19 | Cape | **Stone Mask** | `$7EF352=1` | 0x55 | slot reused |
| 0x1A | Magic Mirror | **Mirror of Time** (Abyss recall) | `$7EF353=2` | 0x6E | text only |
| 0x1B / 0x1C | Glove / Mitt | Power Glove / Titan's Mitt | `$7EF354=1/2` | 0x58/0x6D | none |
| 0x1D | Book of Mudora | Book of Secrets | `$7EF34E=1` | 0x5D | text |
| 0x21 | Bug Net | **Roc's Feather** | `$7EF34D=1` | 0x74 | slot reused |
| 0x22 / 0x23 | Blue / Red Mail | Blue / Red Mail (real armor) | `$7EF35B` | 0x75/0x76 | none |
| 0x37/38/39 | Green/Blue/Red pendant | Courage `$04` / Wisdom `$01` / Power `$02` | `$7EF374` | - | none |
| 0x3A | Bow & Arrows | **Wolf Mask** | `$7EF358=1` | 0x10F | table edited |
| 0x4B | Pegasus Boots | Pegasus Shoes | `$7EF355=1` | 0x7C | none |

Portal Rod has no receipt ID: `Sprites/NPCs/maple.asm:30-32` sets `$7EF351=2` if Link owns the rod.

## 3. Item placement (reachable chest = chest object exists for that table slot)

Beat numbers are from `story_canon_beat_sheet.md`.

| Item | Source | How | Beat | Status |
|---|---|---|---|---|
| L1 sword + shield | Abyss `0x60` collectible (`collectible.asm:109-118`, Y=0x00) | pickup | 7 | V-CODE; map DOC |
| Moon Pearl 0x1F | Shrine of Origins room `0x05` | chest | 7 | V-ROM |
| Heart Container 0x3E | Maku Tree (`maku_tree.asm:145`) | NPC | 8 | V-CODE |
| Lamp 0x12 | Link's House room `0x104` (entr. 0x01, LW 0x33) | chest | 4-8 | V-ROM |
| Mushroom 0x29 | D1 room `0x0B` chest **and** sprite `0xE7` on LW 0x18 | chest / pickup | 9 | V-ROM (duplicate) |
| Bow 0x0B | D1 room `0x2A` | big chest | 9 | V-ROM |
| Magic Powder 0x0D | Witch Shop room `0x109` (vanilla assistant `0xE9`) | trade | 10 | INF (vanilla code intact) |
| Ocarina 0x14 | Ranch Girl (`ranch_girl.asm:70-86`, then forces `$7EF34C=1`) | NPC | 10 | V-CODE |
| Ocarina 0x14 (dup) | room `0x11E` chest (entr. 0x55 LW 0x15, 0x3D DW 0x75) | chest | any | V-ROM; OW access UNVERIFIED |
| Song of Healing | Mask Salesman room `0x11F` (`$7EF34C=2`) | NPC | 10 | V-CODE |
| Deku Mask 0x11 | Deku Scrub (Healing) | NPC | 10 | V-CODE |
| Roc's Feather 0x21 | D2 room `0x7F` | big chest | 11 | V-ROM |
| Pegasus Shoes 0x4B | Sick Kid room `0x102` (Healing; `bug_net_kid.asm`) | NPC | 12 | V-CODE |
| Book of Secrets 0x1D | Library (entr. 0x49 LW 0x23), vanilla book sprite `$05FD3F` | dash | 12 | INF; setter `Story2_BookOfSecrets` not wired (beat 12) |
| Meadow Blade 0x01 | D3 room `0x56` | big chest | 13 | V-ROM |
| Flippers 0x1E | S1 room `0x9A` | big chest | 14 | V-ROM |
| Pendant of Wisdom 0x38 | S1 room `0x7A` | big chest | 14 | V-ROM (correct bit `$01`) |
| Portal Rod | Maple, Dream Hut room `0x0F` (needs Fishing Rod) | NPC upgrade | >=14 | V-CODE; DOC says D8 |
| Hookshot 0x0A | D4 room `0x36` | big chest | 15 | V-ROM |
| Zora Mask 0x0F | Zora Princess in D4 (Healing) | NPC | 15 | V-CODE |
| Song of Storms | Windmill Guy `0xB2` in room `0x120` (Snowpeak caves) | NPC, needs >=2 | 16 | V-ROM sprite + V-CODE |
| Ice Rod 0x08 | room `0x120` (entr. 0x84 LW 0x03 / 0x56 LW 0x07), same room as Windmill Guy | chest | ~16 | V-ROM |
| Blue Mail 0x22 | room `0x10B` ("Zora Temple Waterfall", entr. 0x4E LW 0x1E); opened by Song of Storms at the Zora pedestal (`pedestal.asm`, SongFlag 3) | chest | 16 | V-ROM + V-CODE |
| Fire Rod 0x07 | D5 room `0xCC` | big chest | 17 | V-ROM |
| Goldstar 0x13 | Old Man escort (`followers.asm:607`, Lava Lands per DOC) | NPC | ~17 | V-CODE; location DOC |
| Power Glove 0x1B | S2 room `0x74` | chest | 19 | V-ROM |
| Pendant of Power 0x39 | S2 room `0x73` | big chest | 19 | V-ROM (correct bit `$02`) |
| Fire Shield 0x05 | Mines Shed room `0x10D` (entr. 0x5F LW 0x36) | chest | ~19 | V-ROM |
| Hammer 0x09 | D6 room `0x88` | big chest | 20 | V-ROM |
| Song of Soaring | Kaepora on LW 0x0E when `Crystals==$77` (`eon_owl.asm:40-48`) | NPC | 22 | V-CODE |
| Cane of Somaria 0x15 | D7 room `0xB3` | big chest | 23 | V-ROM, **BLOCKED (no D7 big key)** |
| Mirror Shield 0x06 | S3 room `0x53` | big chest | 24 | V-ROM, **BLOCKED** |
| Pendant of Courage 0x37 | S3 room `0x07` | big chest | 24 | V-ROM, **BLOCKED** |
| Master Sword L4 0x03 | pedestal (needs pendants, vanilla check not traced) | pedestal | 25 | V-CODE patch; blocked via S3 |
| Silver Arrows 0x3B | D8 room `0x3D` | big chest | 27 | V-ROM, **BLOCKED (D8 big key)** |
| Red Mail 0x23 | D8 room `0x5C` | big chest | 27 | V-ROM, **BLOCKED** |
| Titan's Mitt 0x1C | room `0x92` (orphan block 0x90-0x92, no entrance) | chest | never | V-ROM, **UNOBTAINABLE** |
| Magic Mirror 0x1A | Hidden Grave room `0x113` (entr. 0x5B at LW 0x0F px 3776,672) | chest | 8+? | V-ROM; OW gate UNVERIFIED |
| Boomerang 0x0C | room `0xE8` (Deluxe Fairy Fountain cave, LW 0x15/0x16) | chest | early? | V-ROM |
| Fishing Rod 0x18 | room `0x117` (entr. 0x41, Abyss DW 0x76) | chest | chunk? | V-ROM |
| Bottle 0x16 | room `0xEC` (Snow Mountain Cave) | chest | early | V-ROM |
| Bottles (more) | vanilla Bottle Merchant `0x75` LW 0x23, Hobo `0x2B` SW 0x80 | buy / NPC | early | INF (vanilla `LDY #$16` intact) |
| Bunny Hood 0x10 / Stone Mask 0x19 | Mask Salesman, 100 / 850 rupees | purchase | 10+ | V-CODE |
| Wolf Mask | Wolfos `$A9`, direct `WolfMask=1` (`wolfos.asm:241`) | mini-boss + Healing | ? | V-CODE; place DOC |
| L3 Tempered sword 0x02 | only vanilla Smithy code `$06B553`; smithy sprites in room `0x121` and DW 0x76 | NPC quest | none | INF; no Oracle beat |
| 1/2 magic | Mad Batter `0x3A` in room `0xE3` (entr. 0x11 LW 0x0B) | powder | ? | INF (vanilla) |
| Bomb/arrow capacity | fairy `0x72` in room `0x115` (entr. 0x5E LW 0x36) | rupees | ? | INF (vanilla) |
| Magic rings | Eon Zora (random `AND #$06`), Vasu appraisal | NPC | ? | V-CODE; SRAM alias bug (`!ENABLE_RING_SRAM_RELOCATE=0`) |
| Heart pieces | 16 OW sprites, 4 room sprites (0x11B x2, 0x75, 0xEE), 12 reachable chests (+1 in `0x11D`, room unconfirmed) | mixed | - | V-ROM; about 8 containers |
| Heart containers | OW sprite `0xEA` LW 0x30 (px 352,3376); boss drops | pickup | - | V-ROM sprite; boss drops UNVERIFIED |

Pots and OW secret tables cannot hold major items (secret ID space). D7 pot `0xB5` and S3 pot `0x33` hold small keys only.

## 4. Direct answers

1. **Red Mail (0x23)**: one chest, D8 Fortress room `0x5C`, big chest. It really is Red Mail (armor 2,
   msg 0x76). The 21 "Red Mail" in `chest_item_counts.tsv` are Small Keys (0x24). It is unobtainable now
   (issue 2).
2. **Blue Mail (0x22)**: room `0x10B`, the Zora Temple Waterfall room behind the pedestal on LW 0x1E.
   Play the Song of Storms at the pedestal (`pedestal.asm:52-57`) to open it. Beat 16. Good placement.
3. **Titan's Mitt (0x1C)**: room `0x92` only. The room has no entrance and is the DECIDED Sky tower block
   (`$90-$96`). Unobtainable. `item_audit.md` called it "Power Glove" (shifted label).
4. **Pegasus Shoes (0x4B)**: Sick Kid in room `0x102` (village), after the Song of Healing. Beat 12.
   Vanilla Sahasrahla code still gives 0x4B at `$05F1FB`, but no Sahasrahla sprite was found.
5. **Magic Mirror (0x1A)**: Hidden Grave room `0x113` (first table slot; the second slot, Stone Mask 0x19,
   is parked). The old claim "Mirror only in Desert Palace room 0x74" is wrong: 0x74 holds the Power Glove.
   The Old Man no longer gives the Mirror; he gives the Goldstar.
6. **Lamp (0x12)**: Link's House room `0x104`, vanilla spot.
7. **Missing**: Tempered sword (L3) has no Oracle source. Song of Time (`$7EF34C=5`) has no setter.
   No quarter magic. No Kydrog Mask yet (post-game, DOC).
8. **Duplicated**: Ocarina (Ranch Girl + chest `0x11E`), Mushroom (D1 chest + Toadstool sprite, harmless:
   the receipt code will not overwrite Powder).
9. **Unobtainable**: Titan's Mitt; Somaria, Mirror Shield, Pendant of Courage, Master Sword L4 (D7/S3 key
   loop); Silver Arrows, Red Mail (D8). 65 of 168 chest slots are parked (no chest object).

## 5. Gate map

### 5.1 Gates found in ASM (V-CODE)

| Item / state | Gates | Evidence |
|---|---|---|
| Ocarina (`$7EF34C>=1`) | Mask Salesman teaches Healing | `mask_salesman.asm:134-141` |
| Song of Healing | Sick Kid -> Boots; Deku Scrub -> Deku Mask (D2 marker); Zora Princess -> Zora Mask; Wolfos -> Wolf Mask | `bug_net_kid.asm:4-12`, NPC files |
| `$7EF34C>=2` | Windmill Guy -> Song of Storms | `windmill_guy.asm:85-90` |
| Pegasus Shoes | Library book knock-down -> Book | vanilla sprite; DOC beat 12 |
| Book of Secrets | Kalyxo Castle entrance overlay on area `$1B` -> D3 | `book_of_secrets.asm` `LinkItem_BookOfSecrets` |
| Power Glove (`$7EF354!=0`) | Rock Meat pickup -> Goron -> D6 | `collectible.asm:124` |
| Song of Storms at pedestal | Zora waterfall -> Blue Mail room | `pedestal.asm:52-57` |
| 6 crystals (`$77`) | Kaepora -> Song of Soaring -> D7 | `eon_owl.asm:40-48`, `world_map.asm:187` |
| Flippers | whirlpool/teleport check | `all_sprites.asm:117` |
| Fishing Rod | Maple upgrades to Portal Rod | `maple.asm:30-32` |
| Goldstar | Old Man stops spawning; file-select mountain spawn | `followers.asm:633`, `overworld.asm:136` |

### 5.2 Gates in docs only (DOC)

Flippers + S1 -> D4; S2 (Eon Gorons) -> D6; Somaria -> S3; Hammer -> East Kalyxo and the Sky tower
(post-D6); Zora Mask -> underwater Abyss (Mermaid whirlpool LW 0x3C); Silver Arrows -> Kydrog/Ganon
(fortune 0xFD); three pendants -> pedestal. ROM-data gates (rocks, pegs, gaps, dark rooms) were only
sampled for rocks (5.4).

### 5.3 Dead items and gates without items

- **No gate use found**: Magic Mirror, Titan's Mitt, Ice Rod (only the OPEN `$63` sign riddle), Boomerang,
  Portal Rod, Fishing Rod, Goldstar (combat only), Lamp (dark-room use not audited), Red Mail,
  Bunny Hood, Stone Mask.
- **Gate without an item**: Sky access (tower is the only route; no entry item, OPEN #4); Watchers'
  temple item (TBD); underwater Abyss shrine (keyless, no reward chosen); Song of Time (no setter or use);
  `$63` Ice Rod riddle vs Flippers (OPEN in `decisions.org`).

### 5.4 Rock scan (V-ROM tile types, `LiftableGloveLevels` `$07:D375` unchanged from vanilla)

Tile16s with rock tile types (`$52/$55` need Glove, `$53/$56` need Mitt), placements from
`overworld-find-tile`:
- Glove rocks: 85 small + 11 big-rock tile16s on LW 0x04 0x0B 0x0C 0x0F 0x11 0x13 0x15 0x16 0x17 0x1A
  0x20 0x22 0x24 0x26 0x30 0x31 0x36 and DW 0x4D 0x50 0x51 0x53 0x58 0x5B 0x5C 0x60 0x61.
  D6 approach LW 0x36: one big gray rock (tiles 0x36D/0x36E/0x374/0x375, px 3168-3184, 3232-3248) plus
  small gray tiles.
- Mitt rocks: LW 0x1A tile 0x239 at px 1088-1104,1616, next to the OW heart piece at (1120,1664); DW 0x48
  (7), DW 0x67 (4). LW 0x30/0x31 hits are custom tiles 0xB4C-0xBC5 around the D7 entrance (384,3488).
  They are probably chars that alias through `AND #$01FF`. Check them in yaze.

## 6. Issues (ranked)

1. **BLOCKER, D7/S3 big-key loop (V-ROM + INF).** D7 (dungeon ID 0x18, mask `$0008`) has a big chest
   (`0xB3` Somaria) and a big-key door (`0xC4` N), but no big-key chest (D7 chests: `0xA2` compass,
   `0xB3`, `0xB7` map). S3 (odd ID 0x09) reads the same mask `$0008`. Its big key (`0x32`) is behind its
   entrance room's big-key door (`0x53` N). No ASM writes `$7EF366`. Nothing can obtain the first
   `$0008` bit, so Somaria, S3, Courage and the L4 sword are all unobtainable.
2. **BLOCKER (D8 WIP), big key inside a big chest (V-ROM + INF).** Room `0x7C` has 4 small chests, then
   the big chest (object 20). Its 5th table entry is the Big Key with the big flag. Silver Arrows (`0x3D`),
   Red Mail (`0x5C`) and door `0x1D` all need that key.
3. **HIGH, duplicate Ocarina writes song level 3 (V-ROM).** The 0x14 table value was changed from 2 to 3.
   If chest `0x11E` is opened first, Link gets Healing + Storms and skips the Ranch Girl and Mask Salesman,
   and the Tail Pond marker is never set. If it is opened after Kaepora, it drops the Song of Soaring
   (4 -> 3). Its text is "She gave you the Ocarina!".
4. **HIGH, Titan's Mitt unobtainable (V-ROM).** The docs say "post-D6 desert" or "Shrine of Power (OPEN)".
   The only Mitt uses in data are a few heavy rocks (5.4).
5. **HIGH, stale shifted labels invite wrong "fixes".** `pendant_fix_task.md` says S1=0x39 and S2=0x3A.
   Applying that gives S1 the Power pendant and S2 the **Wolf Mask**. The current ROM is correct and
   `Core/patches.asm:4-13` enforces it. Other stale files: `ShrineofCourage.md` ("Courage 0x38",
   "misassigned to S1"), `item_audit.md`, `chest_inventory.json/.txt`, `chest_item_counts.tsv`,
   `mirror_item_ids.json`, `receiveitem_calls.json` names, `item_flow_balance_check.md:94-98`, and the
   MEMORY "Pendant misalignment / no 0x3A pendant" blocker.
6. **MEDIUM, receipts overwrite with a lower level (V-ROM values).** Hookshot 0x0A writes `$7EF342=1`.
   If the Old Man (Goldstar=2) comes before D4, the D4 chest deletes the Goldstar. Power Glove 0x1B
   writes 1, which deletes a Mitt if the order is ever reversed (relevant to the Glove/Mitt swap).
   Fire Shield 0x05 writes 2 over a Mirror Shield. Blue Mail and Mushroom are protected.
7. **MEDIUM, Mirror role and early access.** The Hidden Grave is next to the Hall of Secrets, so the
   Mirror may be available from beat 8 (entrance gate not checked). The vanilla Mirror moves Link to the
   same X/Y in Kalyxo from anywhere in the Abyss. That can bypass the "return portal" and "chunk" design,
   and it can drop Link inside gated Kalyxo areas (the classic mirror sequence break). No Oracle code uses
   it. QuestFlow's "Mirror needed for the Old Man" is not implemented: the code checks Goldstar.
8. **MEDIUM, Portal Rod.** `Maple_Idle` writes `$7EF351=2` and SFX `$1B` to `$012F` on **every idle
   frame** while Link has any rod. This is probably a looping sound (not runtime-checked). The upgrade
   shows no message. It is available from the Dream Hut chunk (about beat 14), but the docs say D8 reward.
9. **MEDIUM, Fire Shield text.** Item 0x05 uses msg 0x78 ("You found the Mirror Shield!"). This is a
   vanilla bug that now shows in the Mines Shed.
10. **MEDIUM, L3 sword gap.** The beat sheet says "Meadow Blade caps at L3", but the only L3 source is the
    vanilla Smithy frog quest. In vanilla that quest uses the Mirror to carry the frog to the other world.
11. **LOW, dead chest data.** 65 parked entries: `0x124` 22, `0x123` 17, `0x11D` 5, `0x11E` 4, `0x3C` 4
    (0 chests), `0x11` 3 (Hall of Secrets, 0 chests), others. D4 room `0x27` has a chest object with no
    table entry. `decisions.org` says "`$11D` basement (2 heart pieces)", but the room has 1 chest object.
12. **Pacing.**
    - D1-D3 is dense: Mushroom, Powder, Ocarina, Healing, Deku Mask, Feather, Boots, Book and Blade
      (9 pickups).
    - D4-D6 has one tool per step: Flippers, Hookshot, Storms, Fire Rod, Glove, Hammer.
    - After D6 the only new tools are Soaring and Somaria; Somaria and the Mirror Shield are blocked.
    - Red Mail and Silver Arrows arrive in the last dungeon, where they barely matter.
    - Six optional tools (Mirror, Ice Rod, Boomerang, Goldstar, Fishing Rod, Portal Rod) open nothing,
      so exploring does not pay off.
    - Boss heart containers are not verified: the vanilla `Explode_VerifyPrizing` spawns them, but
      custom boss death code may skip it.

## 7. Suggestions (respecting DECIDED rulings)

1. **Break the D7/S3 loop (smallest change).** Change D7 map chest `0xB7` (table index 66, PC `0x0EA34`)
   from `0x33` to `0x32` (Big Key). Add it to `Core/patches.asm` with the same assert + org pattern as the
   pendants, or move a parked slot into a D7 room. Then give S3 its own even ID, as the census recommends
   (`$00`; `$04` is taken by the tower) so S3 stops sharing keys and big keys with D7.
2. **Fix D8.** In room `0x7C`, put the Big Key in a small-chest slot (index 0-3) and put loot in slot 4.
   D8 room `0x5C` loses the Red Mail (suggestion 5). Use it for Silver Arrows or a D8-only item.
3. **Remove the duplicate Ocarina.** Room `0x11E` slot (PC `0x0EA8E`): change 0x14 to 0x17 (heart piece) or
   rupees. Optionally set the 0x14 value `$09:8594` back to `$01`. `ranch_girl.asm` already writes 1,
   so no path needs 3.
4. **Glove/Mitt swap (input for the OPEN decision).**
   1. Early Glove: D2 room `0x4E` slot 2 (currently 50 Rupees, PC `0x0E9C5`) -> 0x1B, beat 11.
      Alternative: Hall of Secrets `0x41` (10 bombs, PC `0x0E9B3`) at beat 8, zero ASM, but it opens more
      of the world earlier.
   2. S2 room `0x74` -> 0x1C (Mitt). The Glove must always come first, because 0x1B writes 1.
   3. Rock Meat must then need the Mitt: `collectible.asm:124` becomes
      `LDA.l $7EF354 : CMP.b #$02 : BCC .do_you_even_lift_bro`. Otherwise the early Glove opens D6.
   4. Turn the LW 0x36 D6-approach rocks into black rocks (`$56`). Audit the glove rocks listed in 5.4
      for early breaks.
   5. Mitt uses after S2: D6 approach, LW 0x1A heart piece, DW 0x48 pyramid rocks, Sky tower lifting
      puzzles.
   6. Room `0x92`'s Mitt slot is freed when the tower redecorates `$90-$92`.
5. **Armor.** Keep Blue Mail (post-D4, Storms waterfall). Move Red Mail to the **Sky tower big chest**.
   The tower is optional, opens after D6, and uses keyed ID `$04` with its own big key; this matches the
   "items, e.g. upgrades" ruling. Put it in a parked chest slot.
6. **Mirror.** It fits the canon "Mirror breakthrough (Zora research)" and the story_bible
   "crystal-mirror" / Sea Shrine "First Mirror" lore.
   1. Primary: make the Mirror the reward of the keyless underwater Abyss shrine (post-D4, Zora Mask /
      whirlpool chunk). Frame it as the islanders' recent research, so there is no ancient portal
      industry (Sep 23 ruling). Alternative: Impa gives it in the Hall of Secrets (existing plan).
   2. Replace the Hidden Grave slot with a heart piece.
   3. Role: Abyss recall ("Mirror of Time" text), plus the vanilla Smithy frog escort for L3. That fills
      the L3 gap.
   4. Block Mirror use in areas where the Kalyxo copy is gated, or accept those breaks deliberately.
      Keep the Portal Rod local (same-area portals), so the two items never overlap.
7. **Portal Rod.** Make the Maple upgrade one-shot, with a message, and play the SFX only when the value
   changes. Then pick one home: the Watchers' sky temple item (Watcher portal tech, post-D6, optional)
   if D8 does not require it; otherwise D8.
8. **Hookshot overwrite.** Spawn the Old Man only when `$7EF342>=1` (`followers.asm` `PutRollerBeneathLink`),
   or make receipt 0x0A keep the higher value.
9. **Text.** Give 0x05 its own Fire Shield message (table `$08:C2E7`). Flippers msg 0x57 says "You bought".
10. **Docs.** Regenerate `chest_inventory.*`, `chest_item_counts.tsv` and `item_audit.md` with current
    z3ed. Close `pendant_fix_task.md` (S1/S2 are correct). Fix `ShrineofCourage.md`, the reward tables in
    `world_map_diagram.md:261-278` (D8 is Silver Arrows + Red Mail, not Portal Rod), and the MEMORY
    pendant blocker.
11. **Chest capacity.** 65 parked slots cover the tower (10 rooms), the underwater shrine (5) and the
    temple (1-2) without breaking the 168-entry cap (`CPX #$01F8`).

## 8. Not verified (next checks)

1. Runtime: D7 or S3 big key available at all (Mesen, b28); `0x11E` and Hidden Grave entrances reachable
   and when; Maple SFX loop; boss heart containers; the D4 room `0x27` empty chest.
2. OW gating for Mirror, Ice Rod, Boomerang, Fishing Rod, Ocarina chest (only rock tiles were scanned).
3. Chest-object-to-slot order is from the vanilla rule (Nth object = Nth slot); the object order came from
   z3ed stream order.
