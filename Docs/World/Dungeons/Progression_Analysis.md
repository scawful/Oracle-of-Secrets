# Oracle of Secrets - Progression Analysis

**Narrative alignment:** 2026-10-20. The design has eight main dungeons;
Sky is D8 and the Fortress follows the Maku Seed return. The room/floor
figures below remain the 2026-09-26 census, not a fresh ROM measurement.
See [the beat sheet](../../Planning/story_canon_beat_sheet.md) for current intent.

## Dungeon Progression

| # | Dungeon | Theme | Rooms | Floors | Enemy | Puzzles | Required Items |
|---|---------|-------|-------|--------|-------|---------|----------------|
| 1 | Mushroom Grotto | forest | 15 | 1 | low | simple | - |
| 2 | Tail Palace | palace | 16 | 1 | low | moderate | - |
| 3 | Kalyxo Castle | castle | 22 | 2 | moderate | moderate | - |
| 4 | Zora Temple | water | 16 | 1 | moderate | high | Sea Zora Flippers gift + Shrine of Wisdom |
| 5 | Glacia Estate | ice | 19 | 1 | high | high | - |
| 6 | Goron Mines | fire/mine | 19 | 3 | high | moderate | Shrine of Power + Goron/Rock Meat route |
| 7 | Dragon Ship | naval/ship | 22 | 1 | very_high | high | Earlier Song of Soaring route |
| 8 | Sky tower and islands | sky / Watcher structures | TBD | TBD | TBD | TBD | Ship Somaria; late Courage / Dream 3 / Master Sword first |

Rooms: from `Docs/Dev/Planning/dungeons.json`, census 2026-09-26. The D8
row is planned progression and is excluded from that measured total. Item
and gate descriptions follow the current beat sheet; exact island access
and lifting-item routes still need level review.

## Bosses and Dungeon Items

| Dungeon | Boss | Miniboss | Dungeon Item |
|---------|------|----------|--------------|
| Mushroom Grotto | TBD | Vampire Bat (Sprites/Bosses/vampire_bat.asm) | TBD |
| Tail Palace | TBD | - | TBD |
| Kalyxo Castle | TBD | - | TBD |
| Zora Temple | Arrghus (advanced variant) | - | TBD |
| Glacia Estate | Twinrova (Sprites/Bosses/twinrova.asm) | - | TBD |
| Goron Mines | King Dodongo | Lanmolas | Hammer, Fire Shield |
| Dragon Ship | Kydrog, pirate form (`Sprites/Bosses/kydrog_boss.asm`; rescue/reveal staging to build) | - | Somaria Rod |
| Sky D8 | Open | Open | Open |

## Shrines

The three pendant shrines reuse their guest interiors in the **sea/east
region**: dry-connected Wisdom near Sea Zora homes; volcanic-shelf Power
near Goron Mines; jungle-island Courage. Docks boat -> Wisdom pendant proof
-> Sea Zora trust/Flippers -> D4. Power precedes D6, with a separate post-D5
gate still to choose; Courage requires Ship Somaria after D7. Each dream
wakes Link in Maple's Abyss hut; Wisdom's reachable visit/timing remains open.
These are design changes, not proof that entrance/exit records have moved.

| Shrine | Rooms | Theme |
|--------|-------|-------|
| Shrine of Courage | 7 | ancient |
| Shrine of Power | 8 | ancient |
| Shrine of Wisdom | 7 | ancient |

## Late route and geography

Farore's D7 intervention reveals the blade's hidden power to Kydrog before
her rescue. At the pedestal, Farore reclaims her power and keeps the Meadow
Blade; Link draws the Master Sword. Their partnership uses selected NPC
placements, not continuous following. After Sky's eighth essence, the Maku
Seed clears the Fortress entrance. The planned Fortress `$4B` / Lupo `$5E`
swap remains separate from verified ROM placement.

## Counts and evidence

- **Current design:** 8 main dungeons, 3 pendant shrines, and a separate shorter Fortress.
- **Historical dungeon-room census:** 129 rooms across D1-D7 (`Docs/Dev/Planning/dungeons.json`, 2026-09-26); Sky is not counted.
- **Historical location categories:** 6 shrine entries and 33 caves in the older directories. Those categories do not establish three additional required essence shrines.
