# Enemy Stats Inventory — Act I through D2 (2026-09-26)

Status: analysis only. No `.asm`/ROM/save file was edited to produce this document.

Source of truth: `Docs/Technical/Balance/enemy_stats_inventory.json`, produced
deterministically by `Scripts/Analysis/enemy_balance_inventory.py` from:

- ROM property tables read directly from the current playtest build
  `Roms/TestBuilds/rc-playtest-2026-09-25/oos168x.sfc` (HP/damage/prize/boss
  bytes, addressed exactly as `Core/sprite_macros.asm` `Set_Sprite_Properties`
  writes them: `$0DB080/$0DB173/$0DB266/$0DB359/$0DB44C/$0DB53F/$0DB632/$0DB725
  + SPRID`).
- Vanilla sprite-ID → name table parsed from `usdasm/bank_0D.asm`
  (`SpriteData_Health` comments, all 243 IDs).
- `Sprites/registry.csv` for Oracle's custom-sprite-ID → source-file overrides.
- `z3ed overworld-list-sprites --rom=Roms/oos168.sfc --format json` (818 total
  overworld placements, all screens) and `z3ed dungeon-list-sprites` for every
  room listed in `Docs/World/Dungeons/MushroomGrotto_Map.md` (D1, 21 rooms,
  158 placed instances) and `TailPalace_Map.md` (D2, 17 rooms, 123 instances).

Every number below is **VERIFIED** (read from ROM bytes or usdasm/source) unless
marked **INFERRED**. Re-run the script any time the playtest ROM or base ROM
changes: `python3 Scripts/Analysis/enemy_balance_inventory.py` (deterministic;
two consecutive runs produced byte-identical JSON).

## How to read "damage" and "HP" here

- **HP** = the raw ROM `health` byte. Fighter's Sword slash = 1 HP/hit, spin =
  2; Master Sword slash = 2, spin = 3 (`Sprite_CalculateSwordDamage`
  `.damage_class`, usdasm/bank_06.asm:21286-21291, ROM `$06ED33`). `hits_to_kill`
  in the JSON gives the exact swing count per sword.
- **Damage class** (0-9) = low nibble of the ROM `damage` byte, looked up in
  `Sprite_BumpDamageGroups` (usdasm/bank_06.asm:22774, ROM `$06F427`) to get
  eighths-of-a-heart dealt to Link on **[Green, Blue, Red]** mail
  (`$7EF35B`). Link's health counter (`$7EF36D`) is itself in eighths, so
  8/8 = 1 heart. **A hit is capped by the class value, not by Link's current
  HP** — a class that deals 32/8ths (4 hearts) can take a fresh 3-heart Link
  from full health to 0 in one hit.
- 255 HP generally means "not meant to be killed by melee" (statues, track
  hazards, Antifairy, Cucco) — not a real time-to-kill target.

## The "fast bird" — confirmed: Raven, sprite $00

Loom Beach's bird is the vanilla **Raven** (`$00`), unmodified AI, still
running vanilla `Sprite_00_Raven` (usdasm/bank_1D.asm:15550). Its actual stats
are **not** the generic property-table row — `SpritePrep_Raven`
(usdasm/bank_06.asm:1930-1956, ROM `$068963`) overrides HP/damage/prize at
spawn time from a 2-entry [Light World, Dark World] table selected by the
world flag (`$0FFF`):

| World | HP (actual) | Damage class (actual) | Hearts G/B/R | Prize pack |
|---|---|---|---|---|
| Light World (Loom Beach) | **4** | 1 | 0.5 / 0.5 / 0.5 | pack 6 (magic/rupee/heart mix) |
| Dark World | **8** | 4 *(patched from 8)* | 1.0 / 1.0 / 1.0 | pack 2 (all rupees) |

Oracle already reduced the Dark World damage class from 8 (was up to 24/8ths
= **3 hearts** on green mail) to 4 (flat 1 heart) — `Core/patches.asm:194-195`,
`org $068963 : db $81, $84`, comment "Raven Damage (LW/DW)". The generic
`SpriteData_Health`/`SpriteData_Bump` table row for ID `$00` (HP 12, damage
class 3 = 1 heart) is **dead data for this sprite** — Prep always overwrites
it — so don't hand-edit that table entry expecting it to change Raven.

**Why it's fast:** `Raven_Rise` (`$1DDDF6`) and `Raven_Attack` (`$1DDE21`,
usdasm/bank_1D.asm) both launch the dive with a flat `#$20` (32) speed
constant via `Sprite_ApplySpeedTowardsLink`/`Sprite_ProjectSpeedTowardsLink`.
For comparison: Octorok's rock-throw approach uses a ±24 table
(`$06D367-D36B`), and Buzzblob's crawl uses ±2/±3 (`$06D8EE-D8F6`). The
Raven's dive is ~33% faster than an Octorok's shot and ~10-16x a Buzzblob's
crawl — it is objectively the fastest common Act I enemy movement in the ROM.
Confirmed placement: 4 Ravens on Loom Beach (`OW $33`, Light World); the
higher-damage DW variant appears elsewhere on the Dark World overworld
(`$52,$5A,$62,$63`), not on the Act I beat-sheet screens.

## Act I - D2 early-game table (sorted by stage)

| Stage | ID | Name | HP | Dmg class | Hearts G/B/R | Hits (Fighter slash / spin) | Placements | Notes |
|---|---|---|---|---|---|---|---|---|
| Loom Beach (pre-sword) | `$00` | Raven | **4** (LW, see above) | 1 | 0.5/0.5/0.5 | 4 / 2 | 4 on $33 | generic table (12 HP/1 heart) is overridden, ignore it |
| Loom Beach | `$08` | Octorok | **0** | 0 | 0.25/0.125/0.125 | n/a (0 HP) | 34 total | **see outlier #1** |
| Loom Beach | `$0D` | Buzzblob | 3 | 1 | 0.5/0.5/0.5 | 3 / 2 | 41 total | reasonable; slow (±2/±3 crawl) |
| Loom Beach | `$55` | Zora/Fireball | 8 | 3 | **1.0**/0.5/0.25 | 8 / 4 | 45 total | outlier candidate |
| Loom Beach | `$58` | Crab | 2 | 3 | **1.0**/0.5/0.25 | 2 / 1 | 30 total | low HP but full-heart "gotcha" hit on green mail |
| Loom Beach | `$AE` | Sea Urchin | 6 | 4 | **1.0/1.0/1.0** | 6 / 3 | 39 total | **outlier #2**: full heart on *any* mail |
| Wayward Village | `$41` (West Forest) | Blue Guard | 6 | 1 | 0.5/0.5/0.5 | 6 / 3 | 36 total | fine |
| West Forest / Forest Glade | `$59`/`$5A` | Lost Woods Bird/Squirrel | 0 | 0 | harmless | n/a | 14/11 | ambient, harmless |
| Abyss tutorial (DW $40) | — | *(no hostile sprites placed on this screen — Master Sword pedestal, plaque, Zora Princess, ambient critters only)* | | | | | | screen is a cutscene/pickup area, not combat |
| "Shrine of Origins" `$05` (**INFERRED** id) | `$C9` | Tektite/Firebat | 8 | 5 | **2.0/1.0/0.5** | — | 3 | **outlier #3**: 2 full hearts, green mail |
| "Shrine of Origins" `$05` (**INFERRED**) | `$D0` | Lynel | 24 | 6 | **4.0/2.0/1.0** | 24 / 12 | 2 | **outlier #4 — most severe**: 4 hearts = can 1-shot a fresh 3-heart Link |
| D1 Mushroom Grotto | `$9B` | Wizzrobe | 2 | 6 | **4.0/2.0/1.0** | 2 / 1 | 15 | **outlier #5 — most severe in D1**: same 1-shot-capable hit, but dies in 1-2 hits |
| D1 | `$20` | Sluggula | 8 | 6 | **4.0/2.0/1.0** | 8 / 4 | 4 | outlier #6 |
| D1/D2 | `$91` | Stalfos Knight | **64** | 4 | 1.0/1.0/1.0 | **64 / 32** | 10 | outlier #7: 64 Fighter-Sword hits in the *first* dungeon |
| D1/D2 | `$83`/`$84` | Green/Red Eyegore | 16/8 | 4 | 1.0/1.0/1.0 | impervious to sword/hammer | 11/5 | expected-tanky by design (ranged-only weakness), still 1 heart/hit |
| D1/D2 | `$A7` | Stalfos | 4 | 1 | 0.5/0.5/0.5 | 4 / 2 | 37 | baseline, fine — most common D1/D2 enemy |
| D1/D2 | `$23`/`$24` | Red/Blue Bari | 2 | 3 / 1 | 1.0.../0.5 | 2 / 1 | 27/36 | Red Bari full heart on green mail, low HP |
| D1 | `$14` | Business Scrub | 8 | 4 | 1.0/1.0/1.0 | 8 / 4 | 14 | full heart, tanky for D1 |
| D2 | `$09` | Moldorm (boss) | 12 | 3 | 1.0/0.5/0.25 | boss=true | 1 | expected |
| D1 | `$BD` | Vitreous (mini-boss) | 128 | 7 | 4.0/3.0/2.0 | boss=true | 1 (room `$07`) | expected boss-tier damage; not a "fodder" outlier |

## Outliers (ranked by severity for the "hits too hard early" complaint)

1. **Lynel (`$D0`) on `$05`** — INFERRED stage id, but the sprite data is
   VERIFIED: 24 HP, damage class 6 = **4 hearts on green mail**, i.e. capable
   of dropping a fresh save from full health to 0 in a single hit. If `$05`
   is genuinely a pre-D1 area per the beat sheet, this is the single most
   dangerous placement found in this pass.
2. **Wizzrobe (`$9B`) in D1** — same damage class 6 (4/2/1 hearts), 15
   placements in the very first dungeon. Dies in 1-2 Fighter's Sword hits, so
   it's a glass cannon: low risk to the *enemy*, high risk to the *player*.
3. **Sluggula (`$20`) in D1** — same class 6, 8 HP, 4 placements.
4. **Sea Urchin (`$AE`) on Loom Beach** — full heart (class 4) on *every* mail
   level, pre-sword tutorial area, 39 total placements.
5. **Stalfos Knight (`$91`) in D1/D2** — 64 HP is 64 Fighter's-Sword swings
   (32 with a Spin Attack); a 4-hit vanilla-tier sponge landing in the first
   dungeon is a pacing outlier even though its per-hit damage (1 heart) is
   not the worst on this list.
6. **Octorok (`$08`)** — 0 HP and prize pack 0 (no drop) confirmed from the
   ROM. `Sprites/Enemies/octorok.asm` declares `!Health=00 !Damage=00 !Prize=00`
   and its Prep routine never sets `SprHealth`/`$0CD2` at runtime, so nothing
   restores the vanilla value (2 HP). **Needs a Mesen2 check**: 0 HP could
   mean "dies in one hit" (harmless, just odd) or "never dies" if the death
   check treats 0 as already-dead — the two have opposite gameplay effects
   and only a runtime trace can tell them apart. Flagged as a bug, not a
   balance call.
7. **Red Bari (`$23`)** — full heart on green mail with only 2 HP; a
   "gotcha" enemy in D1/D2 that punishes a single mistake disproportionately
   to how easy it is to kill.

## Does Link's own damage output matter for time-to-kill? Yes.

`Sprite_CalculateSwordDamage` (usdasm/bank_06.asm:21286-21344, ROM `$06ED3F`)
scales melee damage by sword level (`$7EF359`, 1-4) and swing type:

| Sword level | Slash/dash | Spin attack | Poke |
|---|---|---|---|
| Fighter's Sword (1) | 1 | 2 | 1 |
| Master Sword (2) | 2 | 3 | 1 |
| Tempered Sword (3) | 3 | 4 | 2 |
| Golden/Butter Sword (4) | 4 | 5 | 3 |

This directly halves (or better) hits-to-kill once the player has the Master
Sword — e.g. Stalfos Knight goes from 64 hits (Fighter slash) to 32 (Master
slash) to 22 (Master spin). Any HP tuning proposal must state which sword
level it assumes; see the proposal doc.

## Scope notes / what was NOT covered in this pass

- Dungeon placement enumeration was scoped to **D1 and D2 only**, per the
  task's explicit room lists. D3+ were not queried; a follow-up pass should
  extend `D1_ROOMS`/`D2_ROOMS` in the script to cover them.
- Indoor shop rooms (Village Shop, Bomb Shop, Magic Shop) do **not** appear in
  `overworld-list-sprites` output at all (indoor maps are stored as
  underworld/room data, not overworld screens) — see the proposal doc's
  economy section for what was verified about shop contents from source
  instead of placement data.
- `$05`/`$80` stage identity is **INFERRED** — confirmed only that `$05` is a
  Light World overworld screen and `$80` is a "Special" world overworld
  screen (and that Farore/Maku Tree are on `$80`, consistent with "Forest
  Glade"), not that `$05` is specifically "Shrine of Origins". Recommend
  confirming both against `Docs/Planning/story_canon_beat_sheet.md` cross-refs
  or a live playtest waypoint.
