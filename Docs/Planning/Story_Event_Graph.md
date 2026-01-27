# Story Event Graph

**Purpose:** Map story events to flags, rooms, scripts, and text IDs with explicit evidence.

**Last Verified:** 2026-01-24 (code + rom audit: Core/sram.asm + z3ed)
**Primary Sources:** Core/sram.asm (flag definitions), sprite scripts (setters), Docs/Sheets (room/entrance names)
**Confidence:** Partial (routine/room mappings still incomplete)

## Event Schema

| Event ID | Event Name | Flags Set/Cleared | Locations/Rooms | Scripts/Routines | Text IDs | Evidence | Last Verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Event Index (Seeded + Expanded)

| Event ID | Event Name | Flags Set/Cleared | Locations/Rooms | Scripts/Routines | Text IDs | Evidence | Last Verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | Intro begins (Link’s House / Loom Beach) | IntroState++ (StoryState); Story2_LegacyHouseFlag | Entrance 0/1: Link's House, OW 0x33 Loom Beach | HouseTag_TelepathicPlea | 0x1F | Dungeons/custom_tag.asm; Docs/Sheets/Rooms and Entrances.csv | 2026-01-23 (code) | GameState=1 setter not located; no uncle NPC in OOS (legacy vanilla flag only) |
| EV-002 | Maku Tree met | MakuTreeQuest=1; Story_HallOfSecrets (OOSPROG bit 1) | Hall of Secrets (Entrance ID 2, OW 0x0E) | MakuTree_MeetLink | 0x20, 0x22 | Sprites/NPCs/maku_tree.asm; Docs/Planning/world_map_diagram.md | 2026-01-24 (design) | Hall of Secrets is repurposed sanctuary interior |
| EV-003 | Hall of Secrets unlocked | Story_HallOfSecrets (OOSPROG bit 1) | Sanctuary / Hall of Secrets (Entrance ID 2, OW 0x0E) | MakuTree_MeetLink | 0x20 | Sprites/NPCs/maku_tree.asm; Docs/Sheets/Rooms and Entrances.csv | 2026-01-23 (code) | Location mapping via sheets |
| EV-004 | Pendant quest enabled (intro progress) | Story_PendantQuest (OOSPROG bit 2) | Sanctuary / Hall of Secrets | Impa_SetSpawnPointFlag | TBD | Sprites/NPCs/impa.asm | 2026-01-23 (code) | Hooked at Zelda_AtSanctuary |
| EV-005 | Kydrog encounter / banishment | Story2_KydrogEncounter (OOSPROG2 bit 2); GameState=2 | SW 0x80 Forest Glade | WarpPlayerAway (Kydrog); FaroreFollowPlayer | 0x21 | Sprites/Bosses/kydrog.asm; Sprites/NPCs/farore.asm | 2026-01-24 (design) | Canon: encounter happens on SW 0x80; LW 0x2A is a forest crossroads |
| EV-006 | Book of Secrets obtained | Story2_BookOfSecrets (OOSPROG2 bit 5) | TBD | TBD | TBD | Core/sram.asm | 2026-01-23 (code) | Setter not traced; check Items/book* |
| EV-007 | Fortress of Secrets complete | Story_FortressComplete (OOSPROG bit 7) | Fortress of Secrets (Entrance ID 0x0C/0x37) | TBD | TBD | Core/sram.asm; Docs/Sheets/Rooms and Entrances.csv | 2026-01-23 (code) | Completion routine not traced |
| EV-008 | Farore rescued / endgame | GameState=3 | TBD | TBD | TBD | Core/sram.asm | 2026-01-23 (code) | Setter not traced |
| EV-009 | Mask Salesman met | SideQuest_MetMaskSalesman (bit 0) | Tail Pond (OW 0x2D) | NoOcarina (Sprite_MaskSalesman) | 0xE9 | Sprites/NPCs/mask_salesman.asm; Docs/Planning/world_map_diagram.md | 2026-01-24 (design) | Shop always present; overworld access blocked by Stalfos guards during intro (clears after GameState moves to 2) |
| EV-010 | Song of Healing taught | SideQuest2_SongOfHealing (bit 2) | Tail Pond (OW 0x2D) | TeachLinkSong (Sprite_MaskSalesman) | 0x081 | Sprites/NPCs/mask_salesman.asm; Docs/Planning/world_map_diagram.md | 2026-01-24 (design) | Shop always present; overworld access blocked by Stalfos guards during intro (clears after GameState moves to 2) |
| EV-011 | Ranch Girl transformed back | SideQuest2_RanchGirl (bit 0) | Loom Ranch (OW 0x00) | RanchGirl_Message | 0x17D | Sprites/NPCs/ranch_girl.asm; Docs/Planning/world_map_diagram.md | 2026-01-23 (code) | Location mapped to OW 0x00 |
| EV-012 | Found withering Deku Scrub (main quest) | SideQuest_DekuScrubFound (bit 2) | Tail Pond (OW 0x2D) | EstadoInactivo (DekuScrub) | 0x140 | Sprites/NPCs/deku_scrub.asm; Docs/Planning/world_map_diagram.md | 2026-01-24 (design) | Main quest beat between D1 and D2; requires D1 mushroom → witches east of castle for magic powder/collectible bag; flags live in SideQuestProg |
| EV-013 | Deku Scrub soul freed (main quest) | SideQuest2_DekuSoulFreed (bit 4) | Tail Pond (OW 0x2D) | QuiereCuracion (DekuScrub) | 0x141 | Sprites/NPCs/deku_scrub.asm; Docs/Planning/world_map_diagram.md | 2026-01-24 (design) | Main quest beat between D1 and D2; Song of Healing required (Mask Salesman hints OK); flags live in SideQuestProg2 |
| EV-014 | Village Elder met | Story_VillageElderMet (bit 4) | Wayward Village (Entrance ID 0x97, Room 0x202) | Sprite_VillageElder_Main | 0x143 / 0x19 | Sprites/NPCs/village_elder.asm; Docs/Planning/npc_home_dialogue_audit.md | 2026-01-24 (rom) | Elder appears as subtype sprite in room 0x202; confirm subtype mapping |
| EV-015 | Impa intro / sanctuary visit | Story_PendantQuest (bit 2) | Sanctuary / Hall of Secrets | Impa_SetSpawnPointFlag | TBD | Sprites/NPCs/impa.asm | 2026-01-23 (code) | Duplicate of EV-004; keep until clarified |
| EV-016 | Mirror of Time obtained | Inventory: Mirror ($7EF353 = $02) | Hall of Secrets (Entrance ID 0x02, OW 0x0E) | Impa grants Mirror (planned) | 0x6E | Design decision (user confirmation) | 2026-01-24 (design) | Canonical: Impa grants Mirror in Hall of Secrets; setter not yet located |
| EV-017 | Tail Pond map marker set | MapIcon = Tail Pond; ElderGuideStage stage=1 | Wayward Village (Elder) | Sprite_VillageElder_Main (post-D1 hint) | 0x177 | Sprites/NPCs/village_elder.asm (draft) | 2026-01-24 (design) | Draft/untested: triggered after D1, before D2 |

## Relationship Types

- **Triggers:** Event -> script/routine
- **Persists:** Event -> flags/bitfields
- **Localizes:** Event -> room/area
- **Narrates:** Event -> text ID/message

## How to Update

1) Start from disassembly or ROM trace to identify event triggers.
2) Cross-check with runtime memory (flags/ram) and sheet data.
3) Add evidence and date, then link to Flag Ledger entries.
