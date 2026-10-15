# ALTTP Room Tag Slots - Oracle of Secrets

## Room Tag Dispatch Table ($01CB00-$01CC5A)

The vanilla ALTTP room tag dispatch table runs from approximately $01CB00 to $01CC5A (return address).
Each tag slot is 4 bytes apart (JSL instruction space).

## "Holes" Tag Series ($01CC00-$01CC5A)

These tags are commonly called "Holes(N)" in the vanilla disassembly. Tag IDs and slot addresses are per usdasm bank_01.asm:12275-12300 (tag table) and bank_01.asm:14179-14221 (vanilla handlers), and per the hook files in this repo. Runtime unverified.

Each vanilla Holes slot is 4 bytes: `LDA.b #n` then `BRA RoomTag_TriggerHoles` (Holes8 at $01CC1C falls through instead).

### Currently Used in Oracle of Secrets

| Address  | Tag ID | Name      | Purpose                     | File                     |
|----------|--------|-----------|----------------------------|--------------------------|
| $01CC00  | 0x21   | Holes(0)  | Floor Puzzle               | floor_puzzle.asm:5       |
| $01CC04  | 0x23   | Holes(1)  | Minish Switch (only if !ENABLE_D3_PRISON_SEQUENCE=1, default 0) | custom_tag.asm:16 |
| $01CC08  | 0x34   | Holes(3)  | Crumble Floor              | crumblefloor_tag.asm:4   |
| $01CC10  | 0x36   | Holes(5)  | Minish Shutter Door        | custom_tag.asm:12        |
| $01CC14  | 0x37   | Holes(6)  | Cart-Required Shutters (gated by !ENABLE_MINECART_CART_SHUTTERS, default 0) | minecart.asm:1541 |
| $01CC18  | 0x39   | Holes(7)  | CustomTag (Intro House)    | custom_tag.asm:9         |
| $01CC1C  | 0x3A   | Holes(8)  | Together Warp Tag          | together_warp_tag.asm:11 |

Tag 0x38 is vanilla Agahnim (`RoomTag_Agahnim`, bank_01.asm tag table). Do not use it for a Holes hook.

### Available Slots (Confirmed)

| Address  | Tag ID | Name      | Status    |
|----------|--------|-----------|-----------|
| $01CC0C  | 0x35   | Holes(4)  | AVAILABLE in code (no hook at $01CC0C); room headers not checked |

The table continues until $01CC5A, which is the return address all tag handlers JML to. $01CC20 onward is the shared `RoomTag_TriggerHoles` body, not Holes(9) or Holes(10).

## Next Free Slot

Next free slot: $01CC0C (tag 0x35). Prison escape logic already lives in RoomTag_MinishSwitch (custom_tag.asm:135,170); do not reuse $01CC04.

## Notes

- All tag handlers MUST return via `JML $01CC5A`
- Tags are processed during room initialization
- Tag IDs are set in room headers via yaze editor
- Feature-gated tags (like Cart-Required Shutters) use compile-time flags
- Each slot is 4 bytes (`LDA.b #n` : `BRA`). A JSL+RTS patch spills its RTS into the next slot (floor_puzzle.asm:6-7 into $01CC04; crumblefloor_tag.asm:5-6 into $01CC0C). The JML at $01CC1C overwrites the shared RoomTag_TriggerHoles entry at $01CC1E, so do not put an unhooked Holes tag in a room header. Static reading of asar write order; runtime unverified.
- Tag 0x35 ($01CC0C) is free in code only. Vanilla room headers live in ROM and were not checked; run yaze `dungeon_room_header` on candidate rooms before assigning.

## Additional Available Slots

If more room tags are needed beyond the "Holes" series, there are other tag types in the dispatch table before $01CC00. The complete table spans from approximately $01CB00 to $01CC5A, providing many potential hook points for custom dungeon behaviors.

To find other available slots, consult the vanilla ALTTP disassembly or use a ROM debugger to examine the dispatch table at bank $01.
