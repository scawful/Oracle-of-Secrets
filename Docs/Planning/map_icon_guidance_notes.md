# Map Icon Guidance Notes (From Codex History)

Date: 2026-01-24
Source: ~/.codex/history.jsonl (session 019becb3-d97f-7073-a33c-304e1329a565)
Status: Draft notes, not canonical yet

## Extracted guidance (verbatim snippets)

- "Whenever we need to go to the Hall of Secrets to talk to Impa it should reappear, like a message indicator of sorts."
- "ElderGuideStage, so we can remove it with later states"
- "We should make like groupings of numbers I'm thinking so like when told about the Mushroom Grotto we'll see 1, when told about Kalyxo Castle we see 3, Tail Palace is 2, etc. Maybe midgame we learn about Zora Temple, Glacia Estate, Goron Mines all at once to reduce the amount of unique dialogues for map markers but still some combination of markings, the 7th marking will be obvious bc of the song of soaring pointing to the boat and the owls instructions im thinking"
- "the pyramid icon should likely not come until after the 3rd dungeon since you need to navigate through the hall of secrets to get to the pyramid"
- "MapIcon for D7 prob should be drawn anyway as a reminder it needs to be done"

## Working interpretation (draft)

- ImpaGuideStage controls Hall of Secrets icon; should be set when Impa expects a check-in.
- ElderGuideStage stages can loosely follow MapIcon groupings:
  - Stage 1: Tail Pond (post-D1 mask shop hint).
  - Stage 2: D2 (Tail Palace).
  - Stage 3: D3 (Kalyxo Castle).
  - Stage 4: Midgame group (D4/D5/D6).
  - Stage 5: D7 (Dragon Ship).
  - Stage 6: Fortress.
- Pyramid icon should only appear after D3 completion.

## Implementation hooks (draft)

- Tail Pond marker: set MapIcon to Tail Pond after a post-D1 NPC hint about the Mask Salesman.
- Hall of Secrets icon: set ImpaGuideStage bit 7 when Impa is waiting for the player.
- Pyramid icon: set ElderGuideStage bit 6 after D3.

