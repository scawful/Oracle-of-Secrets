# Item Flow and Hint Coverage Check

Date: 2026-01-24
Status: Draft for Q and A (not canonical yet)

Scope: Early to midgame item progression, song gating, map icon guidance, and hint coverage.
Sources: Docs/Guides/QuestFlow.md, Docs/Planning/Story_Event_Graph.md, Core/messages.org,
Docs/Sprites/NPCs/*.md, Overworld/world_map.asm, Core/sram.asm, Docs/Planning/item_audit.md.

## Current flow snapshot (from docs + code)

- Maku Tree sets MapIcon to D1 (Mushroom Grotto).
- D1 completion yields Bow + Mushroom; Mushroom -> Witches -> Magic Powder.
- Ocarina from Ranch Girl (message 0x17D).
- Mask Salesman teaches Song of Healing (message 0x81). Used to heal Deku Scrub (main quest).
- Ocarina chain currently gates the Book of Secrets path (sick child -> boots -> library).
- D4 requires Flippers (from Shrine of Wisdom).
- D6 reward is Hammer; planned post-D6 reward is Titan's Mitt (desert area).
- Song of Soaring is required to reach the Dragon Ship (D7).

## Ocarina songs (planned + code intent)

- Ocarina (Ranch Girl).
- Song of Healing (Mask Salesman).
- Song of Storms (planned: Windmill NPC in Eon Abyss, needs placement).
- Song of Soaring (post-D6 Owl).
- Song of Time (undecided; likely tied to dream or late-game gate).

## Map icon guidance (world map)

- MapIcon values: D1=0x01, D2=0x02, D3=0x03, midgame group (D4-D6)=0x04,
  D7=0x05, Fortress=0x06, Tail Pond=0x09.
- Tail Pond marker is intended to be set after a post-D1 NPC hint about the Mask Salesman (draft).
- Tail Pond marker coordinates should be tuned manually (visual pass).
- Hall of Secrets icon is controlled by ImpaGuideStage bit 7.
- Pyramid icon is controlled by ElderGuideStage bit 6.
- Known setters: Maku Tree sets D1; Deku Scrub sets D2.

## Hint inventory (existing in ROM)

Primary guidance:
- Fortune Teller messages 0xEA-0xFD:
  - 0xEB: magic mushroom in Toadstool Woods.
  - 0xEC: magic shop / mushroom lover.
  - 0xF0: heal sick child -> access to forbidden knowledge.
  - 0xF1: strength in the Eon Abyss mountains.
  - 0xF9: treasure in the graveyard.
  - 0xFA: take the form of the Zora.
  - 0xFB: pendants.
  - 0xFC: Fortress barrier.
  - 0xFD: Silver Arrows for Kydrog.
- Mask Salesman:
  - 0xE9: get the Ocarina first.
  - 0x81: Song of Healing explanation.
- Village Elder (0x143): mentions the mountain gate and marks the map.

Secondary hints:
- Old woman near Mushroom Grotto (0x2D) points to D1.
- Mayor's son (0x172) mentions old texts in the basement (Book of Secrets lead).
- Bush Yard Guy (0x182/0x183) points to swamp temple and Goron Mines.
- Ranch Girl (0x17D) gives the Ocarina and flavor text about melodies.

## Pressure points and balance risks

- Early chain density: Ocarina -> Song of Healing -> sick child -> boots -> Book of Secrets -> D3.
  - Needs clear hints and map icons so players do not miss the chain.
- Song of Storms is optional (Blue Mail waterfall post-D4). Needs light hinting but not required gating.
  - Windmill NPC: Ocarina-only; player will likely already have Song of Healing by then.
- Titan's Mitt is intended as immediate post-D6 reward (confirmed).
- Mirror placement vs Old Man quest:
  - Current audit shows Mirror only in Desert Palace chest (room 0x74).
  - Canonical plan: Impa grants Mirror in Hall of Secrets (setter TBD).
  - Relocation is a design change only; do not move ROM data yet.

## Open questions for Q and A

1. Windmill NPC (Storms):
   - Requirement: Ocarina only (resolved).
   - Placement + Eon Abyss access timing still TBD.
2. ElderGuideStage and ImpaGuideStage mapping:
   - Tail Pond marker: after D1 via Village Elder (draft).
   - When to show D1-D3 and midgame group markers?
   - Should D7 icon appear as soon as Song of Soaring is learned?
3. Mirror placement:
   - Prefer Hall of Secrets (confirmed).
4. (Resolved) Titan's Mitt is immediate post-D6 reward.
