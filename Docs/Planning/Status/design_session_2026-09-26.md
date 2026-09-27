# Design session summary — 2026-09-26

One chat ("Yaze and Oracle of Secrets design discussion") spent the day on story,
design and cleanup. No gameplay code was written here; build work went to the RC
leader. Every ruling below is recorded in `Docs/Planning/Status/decisions.org`
with scawful's own words.

## In one line

The old AI-written story "rules" were audited and replaced by your own rulings;
the intro, title screen, Abyss and Sky Islands now have approved designs; the
build side (RC leader) has applied part of it and holds the rest.

## What you asked for, and where it ended up

| # | You asked for | Result |
|---|---|---|
| 1 | Audit AI-generated rules, one source of truth | **Done.** No story "ruling" had evidence from you. `decisions.org` is now the canon; about 35 rulings recorded with quotes. Canon files are in git. |
| 2 | Talk through the plot | **Done.** Villain chain decided (below). |
| 3 | Dialogue: "people of Kalyxo", not race names | **Done** as a rule; first rewrites approved. |
| 4 | Intro direction (wake-up, beach, Impa) | **Designed and approved.** Build: RC leader. |
| 5 | New title-screen (attract) scenes | **Designed and approved.** Build: RC leader. |
| 6 | Eon Abyss: vibe, signs, NPCs, Dream Hut | **Mostly designed.** Dream Hut layout not started. |
| 7 | Remove wrong agent comments in code | **Done** in 13 files. 4 files wait for other sessions' commits; Impa files are with the RC leader. |
| 8 | Sky Islands in the story | **Designed.** |
| 9 | Room for new dungeons | **Analysis done.** Room budget **not decided** yet. |

## Story decisions made today (plain version)

1. **Kydrog** was a Hylian knight chosen by Farore to guard the prison. The prison
   corrupted him decades ago. His pirates are his dead men; the jokes are how he
   copes. He wants his men back. The Song of Healing frees the knight.
2. **The prison** holds the half-revived beast Ganon from the Oracle games.
   Twinrova try to finish the revival and die in D5; Kydrog carries it on.
   Final fight: Ganondorf and the beast, switching back and forth.
3. **Farore** sealed the prison and put her power in Kydrog's sword (the Meadow
   Blade = the key). She knew him.
4. **Seal places:** the Temporal Pyramid (with the Master Sword pedestal) is the
   lock; the volcano is the prison's mouth, where Ganon's chamber is.
5. **Impa** rescues Link after the fall, guides him, and is spared by Kydrog as a
   messenger to Zelda. She stays at the Hall of Secrets.
6. **Dreams** are in the RC. One per pendant: Kydrog's fall, Farore's choice,
   the cure. Link wakes in Maple's Dream Hut each time.
7. **Yesterwind** is the Abyss's true name and its village (on the swamp map).
8. **Sky Islands:** optional, open after D6. Reached only by climbing a tall tower
   dungeon in East Kalyxo. Built by the **Watchers**, an ancient race who shaped
   the Abyss; Hyrule's garrison later used the tower and abandoned it.
9. **Names:** Toto Ranch, Rock Meat, Pegasus Shoes. Garrison came decades ago.

## What is already in the game vs. waiting to be built

Reported applied to the base ROM by the RC leader today (test in the latest
playtest build): Kydrog's line to Impa, Impa's telepathy line, the dialogue
audit batch, the arrival Owl, Abyss text fixes, the text-box shade fix (b28).

Prepared as patches, not yet confirmed applied: Abyss signs, the accidental warp
corners, the Dream Hut door, the intro Stalfos patrol, room-census fixes.

Designed, not built yet:
- Intro: rescue voice on black + villager wake-up lines; checkpoint after the
  village hole.
- Abyss: sword warp home (no warp tile); return portal where you arrived; respawn
  in the Abyss until you escape.
- Title screen: new narration and scenes (great hall, villager arrest, zoom to
  Tail Pond).
- Experiment scene: sprites still don't show.
- Dreams, Dream Hut, Yesterwind village map, Sky tower and islands.

## What to test

In the game (latest build, `oos-play`):
1. New file: arrival, Impa's hints in the village, the ambush (Kydrog now talks
   to Impa).
2. In the Abyss: Impa's telepathy line, the Owl, the signs, the Dream Hut door.
3. Text boxes indoors, outdoors and in the storm (b28 fix).

In yaze:
1. The Sky maps: remove the test bridge from Korok Cove when you redesign them.
2. The swamp map: rework it into the Yesterwind village.
3. The room matrix (`Reviews/room_census_2026-09-26/room_matrix.png`) when
   planning new dungeons.

## Decisions still waiting on you

Ask for these one at a time:
1. **Room budget:** which rooms the Sky tower and the underwater shrine get. First
   step: decide whether to trim D7/D8.
2. **Two empty D3 rooms:** planned prison rooms, or spare?
3. **Room census follow-ups** (OPEN in `decisions.org`, from the RC leader).
4. **Swamp sign riddle** (Ice Rod vs. Flippers).
5. **Old text still wrong:** Kydrog "fell to Ganondorf" line, "Rock Sirloin",
   the journal's Ranch Girl entry.
6. Postponed on purpose: Dream 2 and 3 storyboards, the finale, the ending text.

## Corrections from you today (so agents don't repeat them)

- The volcano is in the Abyss, not Kalyxo.
- "Observatory" was not your idea; dropped.
- Glacia Estate (D5) is on the Light World snow peak, not in the sky.
- The Korok Cove bridge to the sky was a test.
- The D7 room with 3 empty quadrants is Kydrog's boss room; keep it.
- Keep chat replies short, plain, one question at a time.

## Where the details are

- Rulings: `Docs/Planning/Status/decisions.org`
- Approved text: `Docs/Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md`
- Dream 1 storyboard: `Docs/Planning/Plans/dream1_sealing_war_storyboard_2026-09-26.md`
- Audits and scans: `Docs/Planning/Reviews/audit_2026-09-26/`
- Rooms and capacity: `Docs/Planning/Reviews/room_census_2026-09-26/`
