# Gossip Stone Placement Plan

**Created:** 2026-02-12
**Status:** Design (blocked on graphics sheet constraint)
**Depends on:** Delivery method decision (see Open Question #1 in `lore_implementation.md`)

---

## Graphics Blocker

The Gossip Stone sprite currently exists on **one overworld map graphic sheet only**. It cannot be placed on arbitrary maps without either:
- Adding the sprite to the global sprite sheet (graphics work)
- Using an alternative delivery method (see below)

## Delivery Method Options

| Method | Effort | Coverage | Atmosphere |
|--------|--------|----------|------------|
| **A: Gossip Stone sprite (fix graphics)** | Medium — add to shared sheet | Full | Best — classic Zelda feel |
| **B: Telepathic signs/tablets** | Low — reuse existing sign system | Full | OK — less mystical |
| **C: Owl statues** | Medium — new sprite variant | Full | Good — Zelda tradition |
| **D: NPC dialogue variants** | Low — piggyback on existing NPCs | Limited | Natural but loses ambient feel |
| **E: Fortune Teller expansion** | Low — extend existing NPC | Single location | Worst — loses placement variety |

**Recommendation:** Method A is best if graphics work is feasible. Method C (owl statues) is a solid fallback — one new sprite gives full placement flexibility.

---

## Placement Map (21 Stones)

Organized by world region. Each stone's text is already written in `gossip_stones.md`.

### Kalyxo Overworld (11 stones)

| ID | Location | OW Screen | Near | Type | Gate |
|----|----------|-----------|------|------|------|
| GS01 | Mushroom Grotto entrance | 0x10 | D1 entry | Lore | Always |
| GS02 | Wayward Village outskirts | 0x23 | Village square | Hint | Always |
| GS04 | Mount Snowpeak trail | 0x0D | Path to Old Man | Hint | Snowpeak access |
| GS06 | Kalyxo Castle exterior | 0x0B | Castle gate | Lore | After D3 |
| GS07 | Korok Cove entrance | East Kalyxo | Korok area | Hint | Hammer (post-D6) |
| GS13 | Near Ranch | 0x00 | Ranch fence | Hint | Always |
| GS14 | Goron mountain path | 0x36 | Mine approach | Hint | Always |
| GS15 | Dragon Ship dock | TBD | D7 approach | Warning | 6 essences |
| GS18 | Seashell coast | 0x32-0x33 | Beach area | Hint | Always |
| GS19 | Glacia Estate approach | 0x0D area | D5 approach | Warning | D5 access |
| GS21 | Near Meadow Blade | TBD | Kalyxo Castle interior | Lore | D3 access |

### Eon Abyss / Dark World (6 stones)

| ID | Location | OW Screen | Near | Type | Gate |
|----|----------|-----------|------|------|------|
| GS05 | Forest of Dreams | Abyss forest | Eon Abyss entry | Warning | Abyss access |
| GS08 | Shrine of Wisdom approach | 0x63 area | S1 entrance | Lore | Always |
| GS09 | Shrine of Power approach | 0x4B area | S2 entrance | Lore | Always |
| GS10 | Shrine of Courage approach | 0x50 area | S3 entrance | Lore | Always |
| GS11 | Eon Abyss beach | 0x46 area | Abyss coast | Warning | Abyss access |
| GS16 | Temporal Pyramid exterior | Abyss | D8 approach | Warning | After D8 |

### Interior / Dungeon (4 stones)

| ID | Location | Room/Entrance | Near | Type | Gate |
|----|----------|---------------|------|------|------|
| GS03 | Zora Sanctuary | D4 area | Zora NPC area | Lore | After D4 |
| GS12 | Hall of Secrets | Entrance 2 / OW 0x0E | Maku Tree | Lore | After D7 |
| GS17 | Hidden Grotto | Secret cave | Bombable wall | Lore | Discovery |
| GS20 | Temporal Pyramid interior | D8 interior | Post-boss area | Lore | After D8 |

---

## Placement Design Principles

1. **Hint stones near quest start points** — GS02 near village (Ranch Girl hint), GS14 near Goron area (Rock Meat hint), GS18 near coast (seashell hint)
2. **Lore stones near thematic locations** — GS08-10 at shrine entrances (guardian sacrifice lore), GS06 at castle (occupation lore)
3. **Warning stones on approach paths** — GS15 before Dragon Ship, GS16 before Temporal Pyramid, GS19 before Glacia Estate
4. **Progression gating** — Late-game stones (GS12, GS16, GS20) require late dungeon completion. Early stones (GS01, GS02, GS13) always accessible.
5. **Eon Abyss cluster** — 6 stones in the dark world creates a "whispering stones" atmosphere for the corrupted realm

---

## Implementation Steps (Once Delivery Method Decided)

1. Choose delivery method (A, B, or C)
2. If A or C: graphics work to add sprite to shared/global sheet
3. Place sprite instances at locations above using yaze overworld editor
4. Wire each sprite to its message ID (0x1C0-0x1D4)
5. Implement progression gating (check SRAM flags before displaying)
6. Test all 21 with z3ed message-read + in-game verification
