# Fortress of Secrets

**Role:** Shorter late-game location after Sky D8 and the Maku Seed return.
**Narrative alignment:** 2026-10-29; source receipt/gate present, full scenes and relocation remain unqualified.
**Recorded entrance:** `0x37`, at OW `$5E` in the older location reference.
**Planned geography:** Fortress at `$4B`, mirroring Kalyxo Castle; Lupo Mountain
moves toward `$5E`. This document does not report a completed ROM relocation.

## Story and access

The current route is **Dragon Ship D7 -> late Courage / Dream 3 -> Master
Sword -> Sky D8 -> Maku Tree -> Maku Seed -> Fortress**. Sky supplies the
eighth main-dungeon essence. Returning all eight essences to the Tree gives
the Seed, which clears a visible obstruction at the Fortress entrance.
The Seed replaces the former Master Sword-only entrance barrier.
The main checkout has a once-only eight-essence Seed grant in
`Sprites/NPCs/maku_tree.asm`, receipt text `$1BC` in the canonical expanded
source, and `Fortress_CheckSeedGate` in `Overworld/overlays.asm` at the
existing `$5E` entrance. This is source evidence, not a claim that the
planned `$4B` relocation or ordinary route/save acceptance is complete.

Dark Link belongs to Kydrog's arc inside the Fortress. The Fortress is not
an additional numbered main dungeon and is not automatically the arena for
Kydreeok and Ganon. Its exit route to the volcano prison remains design work.
No multi-floor layout, boss-floor placement, or extra gate is established here.

## Farore and the Meadow Blade

Farore helps Link during D7, exposing the blade's hidden power to Kydrog;
her rescue begins a partnership through selected NPC encounters. At the
Master Sword pedestal, she reclaims her power and keeps the Meadow Blade
while Link draws the Master Sword. Exact Fortress appearances and useful
interactions remain open. This does not require continuous following.

Kydrog's human appearance after Healing is established; biological life
versus a spirit's form stays deliberately ambiguous (2026-10-29). His
revised post-D7 plan, voluntary post-healing choice, Farore's final binding
action, and the transition to Ganon require design. Do not treat taking the
blade, rescuing Farore, or playing the Song of Healing as automatic unsealing.

## Location reference and implementation limits

The older reference lists entrance `0x37` at `$5E`. Retain that as a snapshot
until the planned `$4B` entrance, terrain, obstruction, and return routes are
implemented and verified. Moving Lupo also needs its own route and collision
review. Narrative placement alone does not change the ROM entrance records.

The October 28 decision removes the nine island rooms
`$7B/$7C/$7D/$8B/$8C/$8D/$9B/$9C/$9D` from the Fortress plan. They are
unclaimed, not automatically assigned to Sky D8. The retained 13-room set
is `$0C/$0D/$1C/$1D/$2D/$3D/$4C/$4D/$5C/$5D/$6B/$6C/$6D`; the exact
treatment of `$4D` remains open. This is a planning ruling, not proof of
changed room data.

The earlier diagram of a final boss at the top of a multi-floor fortress
was an unverified placeholder. Use the room census and current editor data
for actual layout work rather than that diagram.

## See also

- [Current beat sheet](../../Planning/story_canon_beat_sheet.md)
- [Quest flow](../Guides/QuestFlow.md)
- [Special-area directory](index.md)
- [Location snapshot](../LocationRegistry.md)
