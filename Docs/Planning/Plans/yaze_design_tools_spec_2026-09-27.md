# yaze design tools spec: progression checker + overworld gate view

Date: 2026-09-27. Requested by scawful (design chat). Status: spec for the yaze
session; nothing built. Priority order: (1) progression checker, (2) overworld
render + gate overlay.

Why: on 2026-09-26/27 each of these questions took a 15-30 minute agent run with
custom scripts (reports in `Docs/Planning/Reviews/audit_2026-09-26/` and
`room_census_2026-09-26/`). They found real bugs (two late-game big-key
soft-locks, an unobtainable Titan's Mitt, an ungated Abyss). yaze should answer
them in seconds, reproducibly, after every edit.

Both tools are **read-only checks/views** first. Editing comes later.

---

## 1. Progression checker (soft-lock finder)

### Command

```
z3ed progression-check --rom <rom> --logic <project>/logic.yaml
                       [--start <state>] [--format text|json] [--output <path>]
```

MCP wrapper: `progression_check` (same arguments).

### Inputs

1. **ROM data** (read by yaze, no hand entry):
   - chests per room (`dungeon-list-chests`), big chests, pot items, overworld
     items (`overworld-list-items`);
   - room connections: doors (incl. key doors, big-key doors, shutters), stairs,
     holes, warps (room headers; note the stair high-byte bug below);
   - dungeon ID per room and per entrance (`$040C` values), small-key counter
     slot = ID/2, big-key/map/compass bit per ID;
   - overworld entrances/exits, warp pads (tile behavior `$4B`), whirlpools,
     special-area triggers, and the overworld gate graph from tool 2.
2. **`logic.yaml`** (per project, hand-written, small). Declares what the ROM
   cannot say:
   - item meanings (Oracle item IDs are repurposed: e.g. `0x23` = Red Mail,
     `0x24` = Small Key; names must come from here, not vanilla tables);
   - what each item opens: `glove: [rock_light]`, `mitt: [rock_light, rock_heavy]`,
     `hammer: [peg]`, `flippers: [deep_water]`, `hookshot: [...]`,
     `minish: [minish_passage]`, songs, masks;
   - story flags and scripted gates (e.g. `fortress_barrier: requires
     master_sword`, `volcano: requires event.master_sword_pulled`);
   - NPC gifts and their conditions (e.g. Pegasus Shoes: Sick Kid after
     `song_of_healing`);
   - one-way links (e.g. Kydrog banishment, sword warp home).

### Algorithm

Sphere search (as randomizer logic checkers do):
1. Start from the start state (new file, or a named checkpoint).
2. Repeat: collect every reachable location given current items/flags; add the
   items/flags found; stop when nothing new.
3. Small keys: count keys reachable per dungeon ID vs key doors that must be
   opened, including worst-case order (a key spent on the wrong door).
4. Big keys: a big key that is only reachable through its own big-key door (or
   inside a big chest of the same dungeon ID) is a soft-lock.
5. Shared IDs: flag dungeons that share a small-key slot or big-key/map/compass
   bit (e.g. an odd dungeon ID `0x09` sharing slot 4 with `0x08`).

### Output

- Spheres: which items become available in which order.
- **Errors:** unreachable items/locations; big-key soft-locks; key starvation;
  shared key/big-key slots; items that open nothing (dead items); gates with no
  item.
- **Warnings:** items reachable earlier than the story intends (e.g. a second
  Ocarina chest), overwrites (Hookshot chest overwriting Goldstar).
- JSON for agents, a short text table for humans.

### Acceptance (regression cases from 2026-09-27 audit, against the ROM before fixes)

1. Reports D7 has no reachable big key (shared flag with the Shrine of Courage).
2. Reports D8's big key inside a big chest (room `0x7C`).
3. Reports the Titan's Mitt unreachable (only in room `0x92`, no entrance).
4. Warns on the second Ocarina chest (room `0x11E`).
5. Reports pad `$25`->`$65` reaching most of the Abyss with no items (with
   tool 2's gate graph).
Source: `Docs/Planning/Reviews/audit_2026-09-26/item_progression.md`.

---

## 2. Overworld render + gate overlay

### Commands

```
z3ed overworld-render --rom <rom> --screen <id|parent|world:lw|dw|sw>
                      --out <png> [--overlays sprites,entrances,exits,holes,items,
                                   gates,edges,pads,regions,grid]
                      [--phase 0|1|2] [--scale <f>]
z3ed overworld-connectivity --rom <rom> [--format json|csv] [--output <path>]
```

MCP wrappers: `overworld_render`, `overworld_connectivity`.

### What `overworld-connectivity` computes (method proven by the 2026-09-27 agent run)

1. Full 32x32 tile16 grid per screen (ZSCustomOverworld tile16 table at
   `$BD8000`; tile types `$0E9459`; behaviors per `usdasm/bank_07.asm` ~`#_07DAC0`).
2. Flood fill walkable cells per screen by tile type; mark edges between
   neighboring screens as `open`, `blocked`, `swim`, `special`.
3. Gate tiles by type: light rocks (Glove), heavy rocks (Mitt), hammer pegs,
   deep water (Flippers), bombable walls, ledges, boots-only; classify each as
   ROUTE (blocks a link), POCKET (guards a dead end), DECOR.
4. Links: entrances/exits, warp pads (behavior `$4B`) and their targets, holes,
   whirlpools, special-area triggers.
5. Output: per-screen rows (`map_id, world, parent, size, region, name,
   neighbors, entrances, gates`) - same schema as
   `Docs/Planning/Reviews/audit_2026-09-26/overworld_regions.csv` - plus a region
   graph (regions, links, the item each link needs).
Known ROM quirk to report, not hide: tile graphics that index into rock/sign
types by accident (dock shoreline on `$30/$31`, warp corners on `$31`).

### GUI

- Overworld editor toggle **"Progression view"**: draws region tint, gate icons,
  edge markers and pad links on the live map (the layout of
  `overworld_grid.png`: Kalyxo, special world beside the graveyard, Abyss under
  Kalyxo; sky and overlay slots in their own block).
- Hover a gate: shows which item opens it and what it blocks.
- Region names come from a project `regions.yaml` (editable), defaulting to the
  2026-09-27 CSV.

### Acceptance

1. `overworld-render --screen world:sw` shows the current Sky drafts (`$84-$8F`),
   not the 2024 ZScream export.
2. `overworld-connectivity` reproduces the 2026-09-27 CSV's edges/gates for at
   least the Abyss (`$40-$7F`) and flags the ungated pad `$25`->`$65`.
3. Sprite overlay respects `--phase` (the current merged list misled an audit).

---

## Known z3ed bugs to fix alongside (blocking accurate results)

1. `overworld-get-tile`: reads x/y as hex, rejects >63, indexes the wrong array.
2. Room stair destinations above `0x100` lose the high byte (room `0x119` stairs
   read as `0x1D`; real target `0x11D`).
3. yaze-editor MCP server points at a missing ROM (`build/oracle.sfc`).
4. `overworld-list-sprites` merges story-phase lists; add `--phase`.
5. `overworld-find-tile --tile` parses its value as hex silently; document or
   accept `0x` prefix explicitly.

## Later (not in this spec)

Chunk validator (every entry to a region gated), project item names in all
tools, overlay manager, dialogue preview in the game font, glossary lint over
messages and ASM comments.
