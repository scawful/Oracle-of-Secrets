# Flag Ledger

**Purpose:** Single source of truth for story/system flags, their addresses, and evidence.

**Last Verified:** 2026-01-24 (code audit: Core/sram.asm + targeted call sites)
**Primary Sources:** Core/sram.asm (bit/value definitions), sprite scripts (setters), water_collision.asm (water gate bits)
**Confidence:** Partial (runtime snapshot captured, semantics still unverified)

**Runtime Snapshot:** Docs/Planning/Status/runtime_verification_20260123_180426.json
**Runtime Notes:** Mesen2 socket connected; screenshot captured successfully.

## Source Tiering (for evidence column)

1) ROM + disassembly (authoritative)
2) Runtime memory observation (watch/screenshot/state)
3) Docs/Sheets
4) Notes/assumptions

## Ledger Schema

| Flag Name | Address | Bit/Value | Set By | Cleared By | Story/System Event | Evidence | Last Verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Flag Ledger

| Flag Name | Address | Bit/Value | Set By | Cleared By | Story/System Event | Evidence | Last Verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GameState_Start | $7EF3C5 | $00 | HouseTag_WakeUpPlayer (custom_tag.asm) | TBD | Intro start | Dungeons/custom_tag.asm | 2026-01-23 (code) | Value 0 set in house intro |
| GameState_LoomBeach | $7EF3C5 | $01 | TBD | TBD | Intro sequence begun | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| GameState_KydrogComplete | $7EF3C5 | $02 | FaroreFollowPlayer (Sprite_Farore); Meadow_main hook | TBD | Sent to Eon Abyss | Sprites/NPCs/farore.asm; Meadow_main.asm | 2026-01-23 (code) | Runtime snapshot shows GameState=2 |
| GameState_FaroreRescued | $7EF3C5 | $03 | KydrogBoss_ApplyFaroreRescueProgression (feature-gated) | TBD | D7 complete, endgame | Core/sram.asm; Sprites/Bosses/kydrog_boss.asm | 2026-02-13 (code) | Guarded by !ENABLE_D7_FARORE_RESCUE_SEQUENCE; staged in Kydrog death via SprMiscF (message first, commit second) |
| Story_IntroComplete | $7EF3D6 | $01 | TBD | TBD | Met Maku Tree (per sram.asm) | Core/sram.asm | 2026-01-23 (code) | Setter not located; Maku Tree sets bit 1, not bit 0 |
| Story_HallOfSecrets | $7EF3D6 | $02 | MakuTree_MeetLink (Sprite_MakuTree) | TBD | Hall of Secrets unlocked | Sprites/NPCs/maku_tree.asm | 2026-01-23 (code) | Bit 1 |
| Story_PendantQuest | $7EF3D6 | $04 | Impa_SetSpawnPointFlag | TBD | Intro progress / sanctuary | Sprites/NPCs/impa.asm | 2026-01-23 (code) | Bit 2 |
| Story_VillageElderMet | $7EF3D6 | $10 | Sprite_VillageElder_Main | TBD | Elder met flag | Sprites/NPCs/village_elder.asm | 2026-01-23 (code) | Bit 4 |
| Story_MasterSword | $7EF3D6 | $10 | Sprite_VillageElder_Main | TBD | Master Sword (alias) | Sprites/NPCs/village_elder.asm | 2026-01-23 (code) | Alias of bit 4 |
| Story_FortressComplete | $7EF3D6 | $80 | TBD | TBD | Final dungeon done | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Story2_ImpaIntro | $7EF3C6 | $01 | TBD | TBD | Impa intro complete | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Story2_SanctuaryVisit | $7EF3C6 | $02 | TBD | TBD | Sanctuary post-kidnap | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Story2_KydrogEncounter | $7EF3C6 | $04 | WarpPlayerAway (Sprite_KydrogNPC) | TBD | Kydrog encounter done | Sprites/Bosses/kydrog.asm | 2026-01-23 (code) | Bit 2 |
| Story2_ImpaLeftHouse | $7EF3C6 | $08 | TBD | TBD | Impa left house | Core/sram.asm | 2026-01-23 (code) | Setter not located; check intro scripts |
| Story2_LegacyHouseFlag | $7EF3C6 | $10 | HouseTag_WakeUpPlayer (custom_tag.asm) | TBD | Legacy vanilla house flag (no uncle NPC; room has only Link) | Dungeons/custom_tag.asm | 2026-01-23 (code) | Runtime snapshot shows OOSPROG2=0x10 |
| Story2_BookOfSecrets | $7EF3C6 | $20 | TBD | TBD | Book obtained | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Story2_FortuneTellerFlip | $7EF3C6 | $40 | TBD | TBD | Fortune set toggle | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Story2_Part0Storm | $7EF3C6 | $80 | HouseTag_WakeUpPlayer (Dungeons/custom_tag.asm:94) | Part0Storm_EndIfBackOnKalyxo (Overworld/storm.asm), run by every storm reader: bit set + Story2_KydrogEncounter + SavedWorld $7EF3CA = $00 (back on Kalyxo after the Abyss) | Part 0 storm: rain overlay, rain sound, dim world map; light world ($8A bit 6 = 0) only | Core/sram.asm; Overworld/storm.asm; Overworld/ZSCustomOverworld.asm:1566,2324 | 2026-09-26 (Mesen2 watch: clear at $34F64F after $02B23C set $7EF3CA = $00; Roms/TestBuilds/storm-owl-oneshot-2026-09-26/evidence.txt) | Only read/written when !ENABLE_PART0_STORM = 1 (default 0). Unused by vanilla and by Oracle before 2026-09-25. Read with AND mask, never as a whole byte. Until 2026-09-26 cleared at the Farore beat (FaroreFollowPlayer) |
| Crystal_D6_GoronMines | $7EF37A | $01 | Dungeon completion (vanilla $08CC3B: ORA RoomTagPrizeChecks[$040C/2]; D6 = dungeon $0E, Mire slot) | TBD | Dungeon complete (D6) | Core/sram.asm; usdasm bank_08.asm:15044-15050, bank_02.asm:6617 | 2026-09-26 (ROM bytes) | Was listed as $02 (swapped with D1) until 2026-09-26. Entrance $27 -> dungeon $0E in ROM table $02D48B; runtime $040C = $0E in D6 (rc_status_and_test_session_2026-09-24.md:103) |
| Crystal_D1_MushroomGrotto | $7EF37A | $02 | Dungeon completion (vanilla $08CC3B; D1 = dungeon $0C, PoD slot) | TBD | Dungeon complete (D1) | Core/sram.asm; usdasm bank_08.asm:15044-15050, bank_02.asm:6616 | 2026-09-26 (ROM bytes) | Was listed as $01 (swapped with D6) until 2026-09-26. Entrance $26 -> dungeon $0C in ROM table $02D48B. Not yet confirmed by clearing D1 at runtime |
| Crystal_D5_GlaciaEstate | $7EF37A | $04 | Dungeon completion (vanilla) | TBD | Dungeon complete (D5) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Crystal_D7_DragonShip | $7EF37A | $08 | KydrogBoss_ApplyFaroreRescueProgression (feature-gated); Dungeon completion (vanilla path TBD) | TBD | Dungeon complete (D7) | Core/sram.asm; Sprites/Bosses/kydrog_boss.asm | 2026-02-13 (code) | Feature-gated staged death path sets bit once after one-shot dialogue; final maiden flow still pending |
| Crystal_D2_TailPalace | $7EF37A | $10 | Dungeon completion (vanilla) | TBD | Dungeon complete (D2) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Crystal_D4_ZoraTemple | $7EF37A | $20 | Dungeon completion (vanilla) | TBD | Dungeon complete (D4) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Crystal_D3_KalyxoCastle | $7EF37A | $40 | Dungeon completion (vanilla) | TBD | Dungeon complete (D3) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Pendant_Wisdom | $7EF374 | $01 | Shrine completion (vanilla) | TBD | Pendant obtained (Wisdom) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Pendant_Power | $7EF374 | $02 | Shrine completion (vanilla) | TBD | Pendant obtained (Power) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| Pendant_Courage | $7EF374 | $04 | Shrine completion (vanilla) | TBD | Pendant obtained (Courage) | Core/sram.asm | 2026-01-23 (code) | Routine not traced in repo |
| SideQuest_MetMaskSalesman | $7EF3D7 | $01 | NoOcarina (Sprite_MaskSalesman) | TBD | Met Mask Salesman | Sprites/NPCs/mask_salesman.asm | 2026-01-23 (code) | Bit 0 |
| SideQuest_CursedCucco | $7EF3D7 | $02 | TBD | TBD | Ranch quest started | Core/sram.asm; Menu/menu_journal.asm; Sprites/NPCs/ranch_girl.asm | 2026-01-23 (code) | No setter found; journal expects bit 1; Ranch Girl uses Ocarina ($7EF34C) instead; check cucco/chicken trigger |
| SideQuest_DekuScrubFound | $7EF3D7 | $04 | EstadoInactivo (DekuScrub) | TBD | Main quest: withered Deku Scrub found | Sprites/NPCs/deku_scrub.asm | 2026-01-24 (design) | Bit 2; Tail Pond (OW 0x2D); between D1 and D2; magic powder from witches east of castle |
| SideQuest_GotMushroom | $7EF3D7 | $08 | TBD | TBD | Toadstool Woods | Core/sram.asm; Menu/menu_journal.asm | 2026-01-23 (code) | No setter found; journal expects bit 3; Mushroom tracked via MagicPowder ($7EF344) instead |
| SideQuest_OldManMountain | $7EF3D7 | $10 | TBD | TBD | Old man mountain quest | Core/sram.asm; Menu/menu_journal.asm; Sprites/NPCs/followers.asm | 2026-01-23 (code) | No setter found; only journal entry uses bit 4; Old Man uses follower system ($7EF3CC) |
| SideQuest_GoronQuest | $7EF3D7 | $20 | TBD | TBD | Rock Meat collecting | Core/sram.asm; Sprites/NPCs/goron.asm; Sprites/Objects/collectible.asm | 2026-01-23 (code) | No setter found; Goron quest uses RockMeat counter ($7EF38F) |
| SideQuest2_RanchGirl | $7EF3D8 | $01 | RanchGirl_Message | TBD | Ranch Girl transformed back | Sprites/NPCs/ranch_girl.asm | 2026-01-23 (code) | Bit 0 |
| SideQuest2_SongOfHealing | $7EF3D8 | $04 | TeachLinkSong (Sprite_MaskSalesman) | TBD | Song of Healing taught | Sprites/NPCs/mask_salesman.asm | 2026-01-23 (code) | Bit 2 |
| SideQuest2_FortuneTeller | $7EF3D8 | $08 | TBD | TBD | Any fortune shown | Core/sram.asm; Sprites/NPCs/fortune_teller.asm | 2026-01-23 (code) | No setter found; fortune_teller.asm has no SideQuestProg2 writes |
| SideQuest2_DekuSoulFreed | $7EF3D8 | $10 | QuiereCuracion (DekuScrub) | TBD | Main quest: Deku Scrub soul freed | Sprites/NPCs/deku_scrub.asm | 2026-01-24 (design) | Bit 4; Tail Pond (OW 0x2D); between D1 and D2; Song of Healing required |
| SideQuest2_TingleMet | $7EF3D8 | $20 | TBD | TBD | Any map purchased | Core/sram.asm; Sprites/NPCs/tingle.asm | 2026-01-23 (code) | No setter found; Tingle uses TingleMaps bitfield instead |
| SideQuest2_BeanstalkGrown | $7EF3D8 | $40 | TBD | TBD | Final bean stage | Core/sram.asm; Sprites/NPCs/bean_vendor.asm; Menu/menu_journal.asm | 2026-01-23 (code) | No setter found; bean quest uses MagicBeanProg ($7EF39B) |
| Dream_Wisdom | $7EF410 | $01 | TBD | TBD | Dream progress (Wisdom) | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Dream_Power | $7EF410 | $02 | TBD | TBD | Dream progress (Power) | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| Dream_Courage | $7EF410 | $04 | TBD | TBD | Dream progress (Courage) | Core/sram.asm | 2026-01-23 (code) | Setter not located |
| WaterGateStates_Room27 | $7EF411 | $01 | WaterGate_SetPersistenceFlag | TBD | Zora Temple water gate room | Dungeons/Collision/water_collision.asm | 2026-01-23 (code) | Bit 0 (room 0x27) |
| WaterGateStates_Room25 | $7EF411 | $02 | WaterGate_SetPersistenceFlag | TBD | Zora Temple water grate room | Dungeons/Collision/water_collision.asm | 2026-01-23 (code) | Bit 1 (room 0x25) |
| IntroState | $7EF39E | Value | TBD | TBD | Link's House intro sequence | Core/sram.asm | 2026-01-23 (code) | Value semantics TBD |
| JournalState | $7EF39C | Value | TBD | TBD | Journal / story state | Core/sram.asm | 2026-01-23 (code) | Value semantics TBD |
| ElderGuideStage | $7EF304 | Value | TBD | TBD | Village Elder map guidance stage | Core/sram.asm | 2026-01-24 (code) | Bits 0-3 stage; bit 6 pyramid icon |
| ZoraWaterfallHint | $7EF305 | $01 | OcarinaEffect_SummonStorms | TBD | Zora waterfall hint shown | Core/sram.asm; Items/ocarina.asm | 2026-02-06 (code) | 1 = hint shown |
| CastleAmbushFlags | $7EF306 | $03 | Oracle_CaptureAndWarp | TBD | D3 prison capture state | Core/sram.asm; Sprites/Enemies/custom_guard.asm | 2026-02-06 (code) | Bit 0 captured; bit 1 escaped |
| ImpaGuideStage | TBD | Value | TBD | TBD | Impa guidance stage / Hall of Secrets indicator | Docs/Planning/map_icon_guidance_notes.md | 2026-01-24 (design) | Planned; previously noted at $7EF305 |
| FOUNDRINGS | $7EF3A1 | ..pa hlbs | Sprite_EonZora_Main (msg $1AE), Vasu Error_Idle (msg $0121): STA random AND $06 | Not cleared | Rings found, not yet appraised | Items/magic_rings.asm; Core/sram.asm (RingSaveBlock); Sprites/NPCs/eon_zora.asm; Sprites/NPCs/vasu.asm | 2026-09-25 (Mesen2 watch, ring-sram-overlap) | Only with !ENABLE_RING_SRAM_RELOCATE = 1. Flag 0 = legacy $7EF3D7 (aliases SideQuestProgress; Eon Zora overwrites the whole side-quest byte). Bits follow the ring menu: $20 Power, $10 Armor, $08 Heart, $04 Light, $02 Blast, $01 Steadfast (the old magic_rings.asm comment said ..pa slbh) |
| MAGICRINGS | $7EF3A2 | ..pa hlbs | Vasu_AppraiseRing (ORA FOUNDRINGS) | Not cleared | Rings owned; Ring Box unlock (Menu_CheckRingsUnlocked, bits 0-5) | Items/magic_rings.asm; Sprites/NPCs/vasu.asm; Menu/menu.asm; Menu/menu_draw.asm; Menu/menu_text.asm | 2026-09-25 (Mesen2, ring-sram-overlap) | Only with !ENABLE_RING_SRAM_RELOCATE = 1. Flag 0 = legacy $7EF3D8 (aliases SideQuestProgress2: side-quest bits read as owned rings) |
| RingSlot1-3 | $7EF3A3-3A5 | Value 0, 2-7 (2 Power, 3 Armor, 4 Heart, 5 Light, 6 Blast, 7 Steadfast) | RingMenu_StoreRingToSlotStack (Menu/menu.asm) | Not cleared (stack shifts) | Equipped rings (ring menu index + 2) | Items/magic_rings.asm; Menu/menu.asm; Menu/menu_draw.asm | 2026-09-25 (Mesen2 watch: writes at $2DB8BE/$2DB8C4) | Only with !ENABLE_RING_SRAM_RELOCATE = 1. Flag 0 = legacy $7EF38C/$7EF38D/$7EF38E ($7EF38D = Pineapples). With !ENABLE_ONE_RING = 1 (M2, 2026-09-28) only RingSlot1 is worn and read: Menu_Page3_ToggleRing / RingMenu_StoreRingToSlotStack write slot 1; OneRing_MigrateSlots (file load, SearchForEquippedItem_Override) moves an old slot 2/3 ring into an empty slot 1 and zeroes $7EF3A4-3A5 (Mesen2 2026-09-28: save 00 03 05 -> 03 00 00) |
| PortalRodOwned | $7EF3A6 | Value 0/1 | Menu_PortalRod_SyncOwned (menu open: 1 when CustomRods $7EF351 >= 2) | Not cleared | Portal Rod Items cell owned ($0202 = $19, Menu_AddressLong) | Core/sram.asm; Menu/menu_page3.asm; Menu/menu_select_item.asm; Menu/menu_draw.asm | 2026-09-28 (Mesen2: 00 at load, 01 after menu open) | Only with !ENABLE_PORTAL_ROD_CELL = 1. Was RingSlotsNum (relocated ring slot count): never read or written in the repo, its git history or usdasm, retired by the one-ring rule. Zero on console saves checked 2026-09-26. The legacy RingSlotsNum alias (flag 0) stays $7EF38F (= RockMeatCount) |
| EonOwlFlags (EonOwl_SwordTalked) | $7EF3A7 | $02 | EonOwl_IntroDialogue (Sprites/NPCs/eon_owl.asm), map $50 Owl, message $E6 | Not cleared | Second Abyss Owl appearance done: the map $50 Owl does not respawn (Sprite_EonOwl_Prep) | Core/sram.asm; Sprites/NPCs/eon_owl.asm | 2026-09-26 (Mesen2 watch: write $02 at $2CD19B; Roms/TestBuilds/storm-owl-oneshot-2026-09-26/evidence.txt) | Only with !ENABLE_EON_OWL_ONE_SHOT = 1 (default 0). Byte allocated from FreeBlock_Large (now $7EF3A8-3C4). Zero on console saves checked 2026-09-26 |
| EonOwlFlags (EonOwl_ArrivalTalked) | $7EF3A7 | $01 | EonOwl_IntroDialogue (Sprites/NPCs/eon_owl.asm), map $40 Owl, message $1FA | Not cleared | First Abyss Owl appearance done (arrival map $40, before the Pearl); Sprite_EonOwl_Prep despawns it when set or when the Pearl is owned | Core/sram.asm; Sprites/NPCs/eon_owl.asm | 2026-09-26 (code, patch storm_owl_round2.diff) | Only with !ENABLE_EON_OWL_ONE_SHOT = 1. Needs the base-ROM Owl placement on map $40 |

## Update Workflow

1) Identify flag usage in disassembly (primary).
2) Verify with runtime watch or save-state evidence.
3) Update this ledger with evidence + date.
4) Link related story events in `Docs/Planning/Story_Event_Graph.md`.
