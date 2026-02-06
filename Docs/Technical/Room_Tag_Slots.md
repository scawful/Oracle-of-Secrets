# ALTTP Room Tag Slots - Oracle of Secrets

## Room Tag Dispatch Table ($01CB00-$01CC5A)

The vanilla ALTTP room tag dispatch table runs from approximately $01CB00 to $01CC5A (return address).
Each tag slot is 4 bytes apart (JSL instruction space).

## "Holes" Tag Series ($01CC00-$01CC5A)

These tags are commonly called "Holes(N)" in the vanilla disassembly.

### Currently Used in Oracle of Secrets

| Address  | Tag ID | Name      | Purpose                     | File                     |
|----------|--------|-----------|----------------------------|--------------------------|
| $01CC00  | 0x33   | Holes(0)  | Floor Puzzle               | floor_puzzle.asm         |
| $01CC08  | 0x35   | Holes(3)  | Crumble Floor              | crumblefloor_tag.asm     |
| $01CC10  | 0x37   | Holes(5)  | Minish Shutter Door        | custom_tag.asm           |
| $01CC14  | 0x38   | Holes(6)  | Cart-Required Shutters     | minecart.asm (gated)     |
| $01CC18  | 0x39   | Holes(7)  | CustomTag (Intro House)    | custom_tag.asm           |
| $01CC1C  | 0x3A   | Holes(8)  | Together Warp Tag          | together_warp_tag.asm    |

### Available Slots (Confirmed)

| Address  | Tag ID | Name      | Status    |
|----------|--------|-----------|-----------|
| $01CC04  | 0x34   | Holes(1)  | AVAILABLE |
| $01CC0C  | 0x36   | Holes(4)  | AVAILABLE |

### Potentially Available Slots (After 0x3A)

| Address  | Tag ID | Name      | Status      |
|----------|--------|-----------|-------------|
| $01CC20  | 0x3B   | Holes(9)  | LIKELY FREE |
| $01CC24  | 0x3C   | Holes(10) | LIKELY FREE |
| ...      | ...    | ...       | ...         |

The table continues until $01CC5A, which is the return address all tag handlers JML to.

## Recommendation for Prison Escape Tag

**Use Tag 0x34 (Holes1) at $01CC04**

Reasons:
1. Confirmed unused in Oracle codebase (no grep hits)
2. First available slot chronologically
3. Clean gap between Floor Puzzle (0x33) and Crumble Floor (0x35)
4. No conflicts with any existing tags

### Implementation Pattern

```asm
; Dungeons/prison_escape_tag.asm

pushpc
org $01CC04 ; holes_1 tag routine ; @hook module=Dungeons
  JML PrisonEscapeTag
  RTS
pullpc

PrisonEscapeTag_Return = $01CC5A

PrisonEscapeTag:
{
  ; Your prison escape logic here
  ; ...
  JML PrisonEscapeTag_Return
}
```

### Alternative: Tag 0x36 (Holes4) at $01CC0C

If Tag 0x34 is needed for something else, Tag 0x36 is also confirmed available.

## Notes

- All tag handlers MUST return via `JML $01CC5A`
- Tags are processed during room initialization
- Tag IDs are set in room headers via yaze editor
- Feature-gated tags (like Cart-Required Shutters) use compile-time flags

## Additional Available Slots

If more room tags are needed beyond the "Holes" series, there are other tag types in the dispatch table before $01CC00. The complete table spans from approximately $01CB00 to $01CC5A, providing many potential hook points for custom dungeon behaviors.

To find other available slots, consult the vanilla ALTTP disassembly or use a ROM debugger to examine the dispatch table at bank $01.
