# Dream 1 "The Sealing War": storyboard (DRAFT, 2026-09-26)

Status: storyboard accepted in direction by scawful (2026-09-26); text is draft;
seal location decided (pyramid pedestal). No ASM, ROM or message changes.
Canon: `Docs/Planning/Status/decisions.org` entries "Villain chain",
"Kydrog-was-the-guardian reveal is a dream", "Dreams are in RC scope",
"Attract scene direction".

## Placement and trigger

- After the Shrine of Wisdom, before D4 (beat 14). The player already has the
  Meadow Blade (D3 reward, maiden msg 0x134), so the dream shows the sword they
  carry.
- Trigger: sleep in the bed at Maple's Dream Hut (bed-interaction trigger
  planned in `Plans/dream_sequences.md`). One-shot; seen flag per
  `dream_sequences.md` (`$7EF410`, unverified).

## Shots

| # | Scene | Picture | Text (draft, <=26 chars/line) |
|---|---|---|---|
| 1 | Black | Fade out from the hut bed | ...a dream of long ago... |
| 2 | Great hall (same room as attract cards 3/5) | Young knight kneels; Farore touches his sword; flash | Farore: Keep the seal, / Captain. This blade / is its key. |
| 3 | Temporal Pyramid, Master Sword pedestal ($41 grove) | Knight and his men on guard; the men fade out one by one (years pass) | none |
| 4 | Seal site | Knight alone; the seal glows | The prison: Your king forgot you. / We have not. |
| 5 | Seal site | He drops the sword; flash; a Stalfos pirate silhouette stands in his place | none |
| 6 | Dream Hut | Link wakes | Maple: Bad dream? You / were talking in your / sleep... about a sword. |

## Rulings (scawful, 2026-09-26)

1. Farore calls him "Captain", not "Kydrog"; the Stalfos silhouette lets the
   player connect it ("sure yes").
2. Maple's closing line stays light and funny for now ("light and funny for
   now").
3. Seal site: the knight guards the Master Sword pedestal at the Temporal
   Pyramid (the lock). The volcano is the prison mouth. See decisions.org
   "Seal geography" ("yes split that works for me").

## Reuse and cost notes

- The great hall reuses the attract room and load path (attract host in
  `Dungeons/attract_scenes.asm`); the knight uses the same actor as attract
  card 5.
- Shot 3 needs multi-actor fades; shot 5 needs a Stalfos pirate sprite in the
  scene (village sheet `$0D` look).
- Technique shared with the attract and the experiment scene (which currently
  shows no sprites): fixing actor drawing once serves all three.
