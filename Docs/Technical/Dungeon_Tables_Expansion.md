# Dungeon Tables: Expansion Feasibility

Date: 2026-09-27. Base ROM `Roms/oos168.sfc` SHA-1 `1866b2977c2f7cb5389691cab36fa8bcce0f3152`.

Standing rule (scawful, 2026-09-27): "we should always research feasibility of
expanding the table and if not possible document the reason why with
justification. stuff like keys, maps, damage rooms can prob be ported to another
setup with some effort."

Evidence sources: vanilla disassembly `~/src/hobby/usdasm` (labels below), the base
ROM, z3ed v0.8.0-g356ca86b6, headless Mesen2 runs on b28 + `s3_dungeon_id` (logs
in the D7 big-key patch README), editor sources `~/src/hobby/yaze/src` and
`~/src/hobby/ZScreamDungeon/ZeldaFullEditor`.

## Verdicts

| # | Table | Capacity | In use / free | Verdict |
|---|---|---|---|---|
| 1 | Chest items `RoomData_ChestItems` | 168 records | 103 live, **65 dead** | Free space exists (dead records). Growth past 168: possible in ASM, breaks both editors |
| 2 | Per-room chest/key flags | 6 chests/locks + 2 keys per room | max used 5 (`$7C`) | Not expandable (room save word is full) |
| 3 | Room object streams, sprite lists | packed, 0 spare bytes per room | all D7 rooms full | Grows only through an editor that repacks |
| 4 | Dungeon IDs + SRAM bits/slots | 16 bit-masks; 14 IDs fully backed | after S3 -> `$00`: only `$04` left (reserved) | `$1C`/`$1E` usable with 5 fixes; a 2nd bank of bits is possible but costly |
| 5 | Pit-damage rooms `RoomsWithPitDamage` | 57 words | 53 rooms + 4 `$0123` fillers | Relocatable; yaze follows, ZScream does not |
| 6 | Key drops (sprite markers) | 2 keys per room | D7 uses 6 small + 1 big | In place: `$FE` -> `$FD` is 1 byte |

## 1. Chest item table

- **Location:** `$01:E96E-$01:EB65` (PC `0x0E96E-0x0EB65`).
- **Format:** 3 bytes per record: room word (bit 15 = big chest), then an item byte.
  `OpenItemChest` (`$01:EB72`) takes the Nth record whose room matches `$A0`,
  where N is the chest's slot in `$06E0` (object-stream order).
- **Readers:**
  - `CPX.w #$01F8` at `$01:EBF5`: the hardcoded byte length (operand at PC `0xEBF6`).
  - `LDA.l RoomData_ChestItems,X` at `$01:EBFA` (operand `0xEBFB`), `+2,X` at
    `$01:EC09` (operand `0xEC0A`), and `+0,X` at `$01:EC0F` (operand `0xEC10`).
  - Oracle `Dungeons/keyblock.asm` (`org $01EC1A : db $64`) makes big chests test
    the compass bits.
  - Oracle `Core/patches.asm` writes the pendants at fixed record addresses
    `$01:E9E8` and `$01:E9F7`, with asserts.
- **Editors:**
  - ZScream reads the pointer from `0xEBFB` (`Rooms/Room.cs:1111`). Its save
    (`Save.cs:832-866`) compacts the records in room order, drops records that
    have no chest object, errors above 168 records, and never writes `0xEBF6`.
  - yaze (`src/zelda3/dungeon/room.cc:2679-2717` load, `:3708-3830` save) follows
    `0xEBFB`. It caps at 168 records (`dungeon_rom_addresses.h:70-76`), rewrites
    `0xEBF6`, keeps the records of rooms that are not dirty, and refuses growth
    past 168 (`:3777`).
- **Census (static, confirmed at runtime from `$0496`):**
  - Records 0-102 match a chest object.
  - Records 103-167 (PC `0x0EAA3-0x0EB65`, 65 records) are all dead: each comes
    after its room's last chest and is never read. They look like the stale tail of
    a compacting editor save. Rooms `$124` x22, `$123` x17, `$11D` x5, `$11E` x4,
    `$03C` x4, `$011` x3, `$10D` x2, `$120` x2, and `$10A $10B $10C $113 $117 $11C`
    x1 each.
  - Room `$027` (D4 Water Gate Room) has a chest object at (53,25) with no record,
    so that chest cannot open.
  - Room `$11D` has 1 chest at runtime (`$0496 = 2`), not 6. The census count of
    6 came from table records.
- **Expand options:**
  1. **Reuse a dead record (recommended, zero code).**
     - As a JSON byte patch, rewrite a dead record's room word and item. The new
       record must be the Nth match for its room.
     - ZScream keeps it only if the room has the chest object.
     - A yaze save keeps it, and dirtying `$123` or `$124` in yaze drops their
       dead records.
  2. **Relocate and grow (ASM-owned).**
     - Copy the base table at build time (`read1()` loop, so yaze/ZScream edits to
       the base table still arrive), append Oracle records, and repoint
       `0xEBFB/0xEC0A/0xEC10`. Then raise `0xEBF6` (16-bit, so up to 21,845
       records) and add asserts.
     - Cost: about 20 lines. Risk: editors cannot see records past 168, and a
       ZScream save does not update `0xEBF6`.
     - yaze change needed: take the capacity from `0xEBF6` instead of 168, and
       show records past 168 read-only. Not done.
     - Not needed while 65 dead records exist.
- **Per-room cap:** 6 (see 2). Largest room today: `$07C`, with 5.

## 2. Per-room chest, lock and key flags

- **RoomFlagMask** (`$00:9900`, 6 words `$0100-$2000`) indexes `$0402` by chest or lock slot.
- **KeyRoomFlagMasks** (`$06:D030`, `db $40,$20`) are for key sprites (`$0403`).
  Keys are indexed by `$0B9B`, so a room can hold at most 2 key sprites (drops or
  placed). The second key mask (`$2000`) is the same bit as chest slot 5.
- **Save word** (`Underworld_SaveRoomData`, `$02:B947`):
  `$7EF000+2*room = ($0400 & $F000) | $0408 | ($0402 >> 4)`, which is `dddd bkut sehc qqqq`.
  Every bit is used.
- **Verdict:** not expandable without a new per-room save format. That means
  changing every `$7EF000` reader and all 296 room words. Keep to 6 chests/locks
  and 2 keys per room, and do not use chest slot 5 in a room with 2 keys.
- Oracle key blocks (object `$F98`, the old big-key lock; `Dungeons/keyblock.asm`)
  count as locks.

## 3. Room object streams and sprite lists

- **Test:** `z3ed dungeon-place-object --id 0xF99` (dry run) failed in every D7
  room checked (`$A2 $A3 $A4 $A5 $B3 $B4 $B7 $C0 $C4 $C5`). The error was
  "object data too large! Size N+3, Available N", with `allocator_capability: none`.
- **What that means:** each room stream ends where the next one starts. Sprite
  lists (`$09:D2B2` pointers, 3-byte entries, `$FF` end) are packed the same way.
- **Verdict:** adding an object or sprite needs a save through an editor that
  repacks the streams (ZScream does; yaze repacking was not tested here).
  In-place edits of the same size are safe, for example changing a key marker
  `$FE` to `$FD`.

## 4. Dungeon IDs and per-dungeon SRAM

`$040C` holds an even ID from `$00` to `$1A` (14 vanilla dungeons), or `$FF` for a cave.
The entrance loader reads ZScream's tables in bank `$0F` (`LDA $9800,X` at
`$02:DA96`, DBR from `JSL $0FF008`).

**yaze reads and writes the old table `$02:D48B` (`room_entrance.h:34`), which the
game no longer reads.** ZScream uses `$0F:9800`, detected through the `0x7F000` marker.
Both tables are identical today.

**Tables indexed by ID:**

| Data | Address | Entries | ID `$1C` / `$1E` |
|---|---|---|---|
| Compass / big key / map bits | SRAM `$7EF364/366/368` (16-bit each) | 16 bits | ok |
| `DungeonMask` | `$00:98C0` | 16 words | `$0002` / `$0001` |
| Item-receipt masks (`$25/$32/$33`) | `$09:85CC` (`LDA $85CC,X` at `$09:86B0`) | **14** | garbage `$4B8B` / `$20AB` (the code after the table): sets 8 / 6 other dungeons' bits |
| Small-key slot `$7EF37C + ID/2` | load `$02:825C`, `$02:9B36`; save `$02:A1DA`, `$09:F584` | 14 bytes | **`$7EF38A` FishingRod / `$7EF38B` Bananas** |
| Death counter `$7EF3E7 + ID` | `SaveDeathCount` `$00:F9E0` | 14 words | `$1C` writes `$7EF403` (the running counter) |
| Pause map: floors, rooms, boss | `$0A:F5D9`, `$0A:F605`, `$0A:E807` | 14 | read past the table (the X-button map is not blocked: Oracle's `CheckForTingleMaps` returns "map allowed" for any ID other than `$FF`) |
| `.dungeon_level` | `$0A:E196` | 14 | past the table |
| `RoomTagPrizeChecks` (crystal bits) | `$02:A1A4` | 13 | past the table |
| `CheckPalaceItemPossession` | Oracle `Menu/menu_draw.asm` jump table | 14 | jumps past the table if the big key is owned |

Hardcoded IDs:
- Vanilla: `$02` shares `$00`'s key slot (4 sites), `$08` keeps the death count,
  `$12` firebar, `$14` falling prize, `$18` maiden is Zelda (`$1E:CD8B`), `$1A`
  heart container.
- Oracle: `CheckForTingleMaps` (`Dungeons/dungeons.asm`) and the disabled prison
  guard (`$0A`).

**Odd IDs** (S3 used `$09`): word tables read across two entries
(`DungeonMask[$09] = $0008` = D7), and byte tables alias `ID-1`. Never use odd IDs.

**IDs in use** (bank `$0F` entrance table, 2026-09-27):

| ID | Used by |
|---|---|
| `$00` | S3 after `s3_dungeon_id` (entrance `$81` is unplaced) |
| `$02` | Spawn points 2 and 4; entrance `$04` (unplaced) |
| `$04` | Reserved for the Sky tower (decisions.org, room budget step 1) |
| `$06` | S2 Shrine of Power |
| `$08` | Final Boss Route (`$24`) |
| `$0A` | D2 |
| `$0C` | D1 |
| `$0E` | D6 |
| `$10` | D3 |
| `$12` | D5 |
| `$14` | S1 Shrine of Wisdom |
| `$16` | D4, plus Master Sword Cave `$2D` |
| `$18` | D7, plus Master Sword Cave `$18`/`$19` |
| `$1A` | D8 Fortress of Secrets |
| `$1C` | Planned keyless underwater shrine |

The Master Sword Cave rooms have no key doors or dungeon items. Their only key,
the room `$04` chest, lands in D4's, D7's or `$08`'s slot depending on the entrance.
That does no harm today.

**Verdicts:**
- **16 keyed dungeons are the ceiling** of the three 16-bit fields. Only 14 IDs are
  fully backed by ROM tables.
- **Making `$1C`/`$1E` fully usable** (about 30 lines ASM, low risk; needed before
  `$1C` holds any key, compass, big key or map):
  1. Relocate the item-receipt mask table to 16 entries (1 operand).
  2. Move their key slots to free SRAM through a key-slot hook at the 4 load/save
     sites.
  3. Block the X-button map for IDs of `$1C` or more in `CheckForTingleMaps`.
  4. Extend `RoomTagPrizeChecks`/`.dungeon_level` if they get a prize.
  5. Pad the Oracle jump table.

  The keyless, itemless `$1C` shrine only needs fix 3. Adding fix 2 would protect
  `$7EF38A` if a key is ever placed there.
- **A second bank of bits** (IDs `$20+`): new 16-bit fields fit in free SRAM
  (`Core/sram.asm`: `$7EF3A8-$3C4` 29 B, `$7EF412-$4FD` about 236 B). The work:
  - Hook every reader: big-key doors `$01:CF22`, big chests `$01:EC19`, receipt
    `$09:86B0`, 8 pause-map sites `$0A:E676-$E7C5`, boss icon `$0A:EDFE`, 3 Oracle
    menu sites, the Librarian map check (`mermaid.asm`), plus key slots and death
    counters.
  - Relocate the 14-entry pause-map tables, which yaze owns (`dungeon_map.h:47`,
    `kNumDungeons = 14`).

  Estimate: about 20 hooks, a yaze change, high regression risk. Not
  recommended until 17+ keyed dungeons are really needed.

## 5. Pit-damage rooms

- **Location:** `RoomsWithPitDamage` `$00:990C`, 57 words (PC `0x190C-0x197D`).
- **Reader:** `LDX.w #$0070` at `$07:94A5` (count operand PC `0x394A6`) and
  `CMP.l $00990C,X` at `$07:94AA` (pointer PC `0x394AB`). A room found in the table
  takes 1 heart and respawns Link instead of using the holewarp.
- **Oracle:** the table is rewritten with 53 rooms and 4 `$0123` fillers.
  `Core/patches.asm` writes `$B8` in the last slot. The `$81` hunk in the room
  census patch takes one filler.
- **Editors:**
  - yaze follows `0x394AB`, reads the count from the low byte of `0x394A6` (up to
    128 entries), and allows replace-only edits of the same count
    (`pit_damage_table.cc:34-110`).
  - ZScream computes 56 entries (misses the last slot, `$B8`), errors above 56, and
    never writes the count (`Rooms/Room.cs:256-270`, `Save.cs:517-540`).
- **Expand options:**
  - Relocate the table and raise `LDX` (16-bit). yaze would follow; ZScream breaks.
  - Better: after the vanilla loop misses, a `JSL` at `$07:94B2` checks an
    Oracle-owned list. About 15 bytes, editors untouched.
- **Verdict:** expandable at low cost. Not needed while fillers remain (4 today,
  3 after `$81`).

## 6. Keys and big keys from sprites

- **Format:** a room's sprite list marks a key drop with an entry `$FE,xx,$E4`
  (small) or `$FD,xx,$E4` (big) right after the sprite that carries it.
- **Path:** `Underworld_LoadSingleSprite` (`$09:C327`) sets `SprDrop` (`$0CBA`)
  to 1 or 2. `Sprite_DoTheDeath` (`$06:F970`) spawns `$E4` or `$E5`, and
  `Absorb_BigKey` (`$06:D178`) gives item `$32`.
- **Blind spot:** chest audits and `z3ed dungeon-list-chests` do not see these drops.
- **Where they are:**
  - Big-key drops in the whole ROM: only D7 room `$A2`. Vanilla had one, in room `$80`.
  - Small-key drops: rooms `$6F $72 $77 $80 $97 $A1 $A5 $B1 $B2 $B6 $C5`.

## Applied: D7 big key (2026-09-27)

**D7 already has a Big Key.** The Stalfos Knight in room `$A2` (the NE alcove
with the statues, behind the interior small-key door `N@46,36`) drops it. The
marker is sprite entry 1 of `$A2`: `FD 00 E4` at `$09:E0C6` (PC `0x4E0C6`).

It was missed because the audit read only the chest table. On b28 the only
`$0008` big key seemed to be S3's, but S3's odd ID `$09` merely wrote D7's bit.

**Runtime-verified** on b28 + `s3_dungeon_id`, and on a scratch build of the tree with this change:
- The knight dies (standard death state) and drops sprite `$E5`.
- Pickup sets `$7EF366 = $0008` with message `$6C`.
- The `$C4` big-key door opens into `$B4`.
- The room word keeps the key bit (`$7EF144 = $2407`). A respawned knight's key
  deletes itself, so there is no second key.

**Route:** D6 -> C6 -> B6 (small-key stairs) -> lower hold (A1/B1/B2) -> A2 hall
-> key door -> knight. This is the same room as the compass (NW, "Big Chest Key").

**Small keys:** 7 sources (drops in A1, A5, B1, B2, B6, C5, plus the B5 pot).
Up to 6 locks: B6 stairs, A2 interior door, B3 interior door (Somaria), 3 key
blocks in C4.

No table change was needed. S3 goes to ID `$00`, so S3's big key is now `$8000` and
no longer D7's. `Core/patches.asm` fails the build if `$A2` loses the `$FD/$E4` marker.
