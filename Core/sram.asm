; =========================================================
; Oracle of Secrets - SRAM Definitions
; =========================================================
; Standardized naming convention: PascalCase for all variables
; Bit constants use !Prefix_Name format
;
; Organization:
;   1. Flag Management Macros
;   2. Bit Constants (for bitfields)
;   3. Story Progression ($7EF300-30F, $7EF3C5-D8)
;   4. Items ($7EF340-35F)
;   5. Player Stats ($7EF360-37B)
;   6. Dungeon Data ($7EF37C-389, $7EF364-369)
;   7. Collectibles ($7EF38A-39F)
;   8. Save File Metadata ($7EF3C8-E2, $7EF3E3-4FF)
;   9. Follower System ($7EF3CC-D3)
;  10. Free Blocks Reference (327 bytes available)
; =========================================================

; =========================================================
; 1. FLAG MANAGEMENT MACROS
; =========================================================
; SRAM-specific macros using long addressing and bit masks.
; For sprite/WRAM flags, use macros in sprite_macros.asm instead.
;
; Key difference from sprite_macros.asm:
;   - These use BIT MASKS ($01, $02, $04...) not bit positions (0, 1, 2...)
;   - These use LONG addressing (LDA.l) for SRAM access
;   - sprite_macros.asm uses short addressing for WRAM
;
; Usage examples:
;   %SRAMSetFlag(SideQuestProgress, !SideQuest_MetMaskSalesman)
;   %SRAMCheckFlag(StoryProgress, !Story_IntroComplete) : BNE .has_flag

; Set a bit in an SRAM progress flag (long addressing, bit mask)
macro SRAMSetFlag(address, bit)
    LDA.l <address> : ORA #<bit> : STA.l <address>
endmacro

; Clear a bit in an SRAM progress flag (long addressing, bit mask)
macro SRAMClearFlag(address, bit)
    LDA.l <address> : AND.b #<bit>^$FF : STA.l <address>
endmacro

; Check if bit is set in SRAM (Z=0 if set, Z=1 if not set)
macro SRAMCheckFlag(address, bit)
    LDA.l <address> : AND #<bit>
endmacro

; Check if bit is NOT set in SRAM (Z=1 if set, Z=0 if not set)
macro SRAMCheckFlagClear(address, bit)
    LDA.l <address> : AND #<bit> : EOR #<bit>
endmacro

; Set a full byte value in SRAM
macro SRAMSetValue(address, value)
    LDA #<value> : STA.l <address>
endmacro

; Increment a byte value in SRAM
macro SRAMIncValue(address)
    LDA.l <address> : INC : STA.l <address>
endmacro

; =========================================================
; 2. BIT CONSTANTS
; =========================================================

; ---------------------------------------------------------
; GameState Values ($7EF3C5)
; ---------------------------------------------------------
!GameState_Start           = $00  ; Cannot save yet
!GameState_LoomBeach       = $01  ; Intro sequence begun
!GameState_KydrogComplete  = $02  ; Sent to Eon Abyss
!GameState_FaroreRescued   = $03  ; D7 complete, endgame

; ---------------------------------------------------------
; StoryProgress Bits (OOSPROG @ $7EF3D6)
; ---------------------------------------------------------
; Bitfield: .fmp h.i.
!Story_IntroComplete       = $01  ; bit 0 - Met Maku Tree
!Story_HallOfSecrets       = $02  ; bit 1 - Hall of Secrets flag
!Story_PendantQuest        = $04  ; bit 2 - Shrine access
!Story_VillageElderMet     = $10  ; bit 4 - Elder met (no reader)
!Story_MasterSword         = $10  ; bit 4 - alias; not a Master Sword gate
!Story_FortressComplete    = $80  ; bit 7 - Final dungeon done

; ---------------------------------------------------------
; StoryProgress2 Bits (OOSPROG2 @ $7EF3C6)
; ---------------------------------------------------------
; Bitfield: sfbh .zsu (repurposed from ALTTP)
!Story2_ImpaIntro          = $01  ; bit 0 - Impa intro complete
!Story2_SanctuaryVisit     = $02  ; bit 1 - Sanctuary post-kidnap
!Story2_KydrogEncounter    = $04  ; bit 2 - Kydrog encounter done
!Story2_ImpaLeftHouse      = $08  ; bit 3 - Impa left Link's house
!Story2_LegacyHouseFlag    = $10  ; bit 4 - Legacy vanilla flag reused for intro house state
!Story2_BookOfSecrets      = $20  ; bit 5 - Book obtained
!Story2_FortuneTellerFlip  = $40  ; bit 6 - Fortune set toggle
; bit 7 - Part 0 storm active (rain overlay, rain sound, dim world map).
;   Unused by vanilla and by Oracle before 2026-09-25. Only read/written
;   when !ENABLE_PART0_STORM = 1 (Overworld/storm.asm).
;   Set: HouseTag_WakeUpPlayer (Dungeons/custom_tag.asm), same frame as
;        Story2_LegacyHouseFlag, so CustomTag's "$7EF3C6 != 0" check is unchanged.
;   Clear: Part0Storm_EndIfBackOnKalyxo (Overworld/storm.asm): back on Kalyxo
;          after the Abyss (Story2_KydrogEncounter set and SavedWorld = $00).
;   Do not read StoryProgress2 as a whole value; use AND with a bit mask.
!Story2_Part0Storm         = $80  ; bit 7 - Part 0 storm active

; ---------------------------------------------------------
; Crystals Bits - Dungeon Completion ($7EF37A)
; ---------------------------------------------------------
; Uses ALTTP bit positions for compatibility. The bit comes from the dungeon
; ID: crystal award $08CC3B ORs RoomTagPrizeChecks[$040C/2] ($02A1A4).
; D1 = dungeon $0C (PoD slot, bit 1); D6 = dungeon $0E (Mire slot, bit 0).
; Fixed 2026-09-26: D1 and D6 were swapped here
; (Docs/Debugging/Issues/world_map_icons_2026-09-26.md section 5.0).
!Crystal_D6_GoronMines     = $01  ; bit 0 - Misery Mire slot
!Crystal_D1_MushroomGrotto = $02  ; bit 1 - Palace of Darkness slot
!Crystal_D5_GlaciaEstate   = $04  ; bit 2 - Ice Palace slot
!Crystal_D7_DragonShip     = $08  ; bit 3 - Turtle Rock slot
!Crystal_D2_TailPalace     = $10  ; bit 4 - Swamp Palace slot
!Crystal_D4_ZoraTemple     = $20  ; bit 5 - Thieves' Town slot
!Crystal_D3_KalyxoCastle   = $40  ; bit 6 - Skull Woods slot

; ---------------------------------------------------------
; SideQuestProgress Bits ($7EF3D7)
; ---------------------------------------------------------
; Bitfield: .dgo mwcn
!SideQuest_MetMaskSalesman = $01  ; bit 0 - Shown "need Ocarina"
!SideQuest_CursedCucco     = $02  ; bit 1 - Ranch quest started
!SideQuest_DekuScrubFound  = $04  ; bit 2 - Withering Deku found
!SideQuest_GotMushroom     = $08  ; bit 3 - Toadstool Woods
!SideQuest_OldManMountain  = $10  ; bit 4 - (TBD)
!SideQuest_GoronQuest      = $20  ; bit 5 - Rock Meat collecting

; ---------------------------------------------------------
; SideQuestProgress2 Bits ($7EF3D8)
; ---------------------------------------------------------
; Bitfield: .bts fsmr
!SideQuest2_RanchGirl      = $01  ; bit 0 - Revealed by powder, Ocarina given
!SideQuest2_SongOfHealing  = $04  ; bit 2 - Mask Salesman taught
!SideQuest2_FortuneTeller  = $08  ; bit 3 - Any fortune shown
!SideQuest2_DekuSoulFreed  = $10  ; bit 4 - Before mask given
!SideQuest2_TingleMet      = $20  ; bit 5 - Any map purchased
!SideQuest2_BeanstalkGrown = $40  ; bit 6 - Final bean stage

; ---------------------------------------------------------
; Pendants Bits ($7EF374)
; ---------------------------------------------------------
!Pendant_Wisdom            = $01  ; bit 0 - Red pendant
!Pendant_Power             = $02  ; bit 1 - Blue pendant
!Pendant_Courage           = $04  ; bit 2 - Green pendant

; ---------------------------------------------------------
; Dreams Bits ($7EF410)
; ---------------------------------------------------------
!Dream_Wisdom              = $01  ; bit 0 - Dream 1 "The Sealing War"
!Dream_Power               = $02  ; bit 1 - Dream 2 "The Oracle's Choice"
!Dream_Courage             = $04  ; bit 2 - Dream 3 "The Healing Revelation"

; ---------------------------------------------------------
; MagicBeanProgress Bits ($7EF39B)
; ---------------------------------------------------------
!Bean_Planted              = $01  ; bit 0
!Bean_Watered              = $02  ; bit 1
!Bean_Pollinated           = $04  ; bit 2
!Bean_Day1                 = $08  ; bit 3
!Bean_Day2                 = $10  ; bit 4
!Bean_Day3                 = $20  ; bit 5
!Bean_Complete             = $40  ; bit 6

; ---------------------------------------------------------
; Scroll Bits ($7EF398) - Dungeon Hints Collected
; ---------------------------------------------------------
!Scroll_D1_MushroomGrotto  = $01  ; bit 0
!Scroll_D2_TailPalace      = $02  ; bit 1
!Scroll_D3_KalyxoCastle    = $04  ; bit 2
!Scroll_D4_ZoraTemple      = $08  ; bit 3
!Scroll_D5_GlaciaEstate    = $10  ; bit 4
!Scroll_D6_GoronMines      = $20  ; bit 5
!Scroll_D7_DragonShip      = $40  ; bit 6

; ---------------------------------------------------------
; MapIcon Values ($7EF3C7) - Dungeon Guidance
; ---------------------------------------------------------
!MapIcon_MakuTree          = $00
!MapIcon_D1_MushroomGrotto = $01
!MapIcon_D2_TailPalace     = $02
!MapIcon_D3_KalyxoCastle   = $03
!MapIcon_D4_ZoraTemple     = $04
!MapIcon_D5_GlaciaEstate   = $05
!MapIcon_D6_GoronMines     = $06
!MapIcon_D7_DragonShip     = $07
!MapIcon_Fortress          = $08
!MapIcon_TailPond          = $09  ; Tail Pond guidance marker

; ---------------------------------------------------------
; SpawnPoint Values ($7EF3C8)
; ---------------------------------------------------------
!Spawn_LinksHouse          = $00
!Spawn_Sanctuary           = $01
!Spawn_Prison              = $02
!Spawn_Uncle               = $03
!Spawn_Throne              = $04
!Spawn_OldManCave          = $05
!Spawn_OldManHome          = $06

; =========================================================
; 3. STORY PROGRESSION FLAGS
; =========================================================

; ---------------------------------------------------------
; Oracle of Secrets Flags ($7EF300-30F)
; ---------------------------------------------------------
; Added for Oracle of Secrets (not in vanilla ALTTP).

; Kydrog/Farore removed from Maku Tree intro area
;   Set by: kydrog.asm | Read by: farore.asm, kydrog.asm
KydrogFaroreRemoved     = $7EF300

; Deku Mask quest complete (separate from inventory slot)
;   Set by: deku_scrub.asm
DekuMaskQuestDone       = $7EF301

; Zora Mask quest complete (separate from inventory slot)
;   Set by: zora_princess.asm
ZoraMaskQuestDone       = $7EF302

; In cutscene flag (controls player movement)
;   Also defined in patches.asm as InCutScene
InCutSceneFlag          = $7EF303

; Village Elder guidance stage (map marker progression)
;   Low nibble used for post-D1 guidance to Tail Pond
ElderGuideStage         = $7EF304

; Zora waterfall hint shown flag (first-time hint at waterfall dismiss)
;   Set by: ocarina.asm OcarinaEffect_SummonStorms
ZoraWaterfallHint       = $7EF305

; Castle Ambush System ($7EF306) - D3 prison capture sequence
;   Set by: custom_guard.asm | Read by: custom_guard.asm
CastleAmbushFlags       = $7EF306
!CastleAmbush_HasBeenCaptured = $01  ; bit 0 - Player captured (one-shot)
!CastleAmbush_HasEscaped      = $02  ; bit 1 - Player escaped prison

; Reserved: $7EF307-30F available for future use

; ---------------------------------------------------------
; Main Story State ($7EF3C5)
; ---------------------------------------------------------
; Use !GameState_* constants for values
GameState               = $7EF3C5

; ---------------------------------------------------------
; Story Progress Bitfields
; ---------------------------------------------------------
; Primary story flags - use !Story_* bit constants
StoryProgress           = $7EF3D6

; Secondary story flags - use !Story2_* bit constants
StoryProgress2          = $7EF3C6

; Maku Tree meeting flag
;   bit 0: Has met Link (0=no, 1=yes)
MakuTreeQuest           = $7EF3D4

; Reserved for future story flags
ReservedStory           = $7EF3D5

; ---------------------------------------------------------
; Map Guidance ($7EF3C7)
; ---------------------------------------------------------
; Use !MapIcon_* constants for values
; Set by: maku_tree.asm, deku_scrub.asm
MapIcon                 = $7EF3C7

; ---------------------------------------------------------
; Side Quest Progress ($7EF3D7-D8)
; ---------------------------------------------------------
; Use !SideQuest_* and !SideQuest2_* bit constants
; Legacy bug: with !ENABLE_RING_SRAM_RELOCATE = 0, FOUNDRINGS/MAGICRINGS
; (Items/magic_rings.asm) alias these two bytes. See RingSaveBlock.
SideQuestProgress       = $7EF3D7
SideQuestProgress2      = $7EF3D8

; =========================================================
; 4. ITEMS ($7EF340-35F)
; =========================================================

; ---------------------------------------------------------
; Y-Button Items ($7EF340-350)
; ---------------------------------------------------------
; 0x00 = Nothing, other values indicate level/type

Bow                     = $7EF340   ; 1=Bow, 2=+Arrows, 3=Silver, 4=Silver+Arrows
Boomerang               = $7EF341   ; 1=Blue, 2=Red
Hookshot                = $7EF342   ; legacy 1=Hookshot, 2=both; split flag: 0/1 Hookshot only
Bombs                   = $7EF343   ; Count
MagicPowder             = $7EF344   ; 1=Mushroom, 2=Powder
FireRod                 = $7EF345   ; 1=Have
IceRod                  = $7EF346   ; 1=Have
ZoraMask                = $7EF347   ; 1=Have (inventory slot)
BunnyHood               = $7EF348   ; 1=Have
DekuMask                = $7EF349   ; 1=Have (inventory slot)
Lamp                    = $7EF34A   ; 1=Have
Hammer                  = $7EF34B   ; 1=Have
Flute                   = $7EF34C   ; 1=Shovel, 2=Inactive, 3=Active (also Ocarina)
RocsFeather             = $7EF34D   ; 1=Have
Book                    = $7EF34E   ; 1=Have (Book of Secrets)
BottleIndex             = $7EF34F   ; Currently selected bottle (1-4)
Somaria                 = $7EF350   ; 1=Have
CustomRods              = $7EF351   ; 1=Fishing Rod, 2=Portal Rod
StoneMask               = $7EF352   ; 1=Have
Mirror                  = $7EF353   ; 1=Letter, 2=Mirror

; ---------------------------------------------------------
; Equipment ($7EF354-35B)
; ---------------------------------------------------------
Gloves                  = $7EF354   ; 0=None, 1=Power Glove, 2=Titan's Mitt
Boots                   = $7EF355   ; 1=Pegasus Shoes (also needs Ability bit)
Flippers                = $7EF356   ; 1=Have
MoonPearl               = $7EF357   ; 1=Have
WolfMask                = $7EF358   ; 1=Have
Sword                   = $7EF359   ; 1=Fighter, 2=Master, 3=Tempered, 4=Golden
Shield                  = $7EF35A   ; 1=Fighter, 2=Fire, 3=Mirror
Armor                   = $7EF35B   ; 0=Green, 1=Blue, 2=Red

; ---------------------------------------------------------
; Bottles ($7EF35C-35F)
; ---------------------------------------------------------
; 0=Empty slot, 2=Empty bottle, 3-10=Contents
Bottle1                 = $7EF35C
Bottle2                 = $7EF35D
Bottle3                 = $7EF35E
Bottle4                 = $7EF35F

; =========================================================
; 5. PLAYER STATS ($7EF360-37B)
; =========================================================

; ---------------------------------------------------------
; Currency
; ---------------------------------------------------------
Rupees                  = $7EF360   ; Actual count
RupeesGoal              = $7EF361   ; Target (for drain/fill animation)
RupeesDisplay           = $7EF362   ; HUD display value

; ---------------------------------------------------------
; Health & Magic
; ---------------------------------------------------------
MaxHealth               = $7EF36C   ; Max HP (8 per heart container)
CurrentHealth           = $7EF36D   ; Current HP (0 = death)
MagicPower              = $7EF36E   ; Current magic (max 128)
MagicUsage              = $7EF37B   ; 0=Normal, 1=Half, 2=Quarter
HeartRefill             = $7EF372   ; Pending HP refill (multiples of 8)
MagicRefill             = $7EF373   ; Pending magic refill

; ---------------------------------------------------------
; Ammo & Capacity
; ---------------------------------------------------------
Arrows                  = $7EF377   ; Arrow count
BombCapacity            = $7EF370   ; Bomb capacity upgrades
ArrowCapacity           = $7EF371   ; Arrow capacity upgrades
BombRefill              = $7EF375   ; Pending bomb refill
ArrowRefill             = $7EF376   ; Pending arrow refill

; ---------------------------------------------------------
; Progress Collectibles
; ---------------------------------------------------------
HeartPieces             = $7EF36B   ; Pieces toward next container (0-3)
Pendants                = $7EF374   ; Use !Pendant_* bits
Crystals                = $7EF37A   ; Use !Crystal_* bits
WishRupees              = $7EF36A   ; Rupees donated to fairies

; ---------------------------------------------------------
; Ability Display ($7EF379)
; ---------------------------------------------------------
; Bitfield: lrtu pbsh
;   h=Pray, s=Swim, b=Run, p=Pull, t=Talk, r=Read, l=Lift
AbilityFlags            = $7EF379

; ---------------------------------------------------------
; Dreams ($7EF410)
; ---------------------------------------------------------
; Use !Dream_* bits
Dreams                  = $7EF410

; =========================================================
; 6. DUNGEON DATA
; =========================================================

; ---------------------------------------------------------
; Current Dungeon Keys ($7EF36F)
; ---------------------------------------------------------
CurrentKeys             = $7EF36F

; ---------------------------------------------------------
; Keys Per Dungeon ($7EF37C-389)
; ---------------------------------------------------------
KeysSewer               = $7EF37C
KeysHyruleCastle        = $7EF37D
KeysEastern             = $7EF37E
KeysDesert              = $7EF37F
KeysAgahnim             = $7EF380
KeysSwamp               = $7EF381
KeysPalaceOfDarkness    = $7EF382
KeysMiseryMire          = $7EF383
KeysSkullWoods          = $7EF384
KeysIcePalace           = $7EF385
KeysTowerOfHera         = $7EF386
KeysThievesTown         = $7EF387
KeysTurtleRock          = $7EF388
KeysGanonsTower         = $7EF389

; ---------------------------------------------------------
; Dungeon Item Ownership ($7EF364-369)
; ---------------------------------------------------------
; Bitfields - see vanilla ALTTP documentation for bit mapping
CompassSet1             = $7EF364
CompassSet2             = $7EF365
BigKeySet1              = $7EF366
BigKeySet2              = $7EF367
DungeonMapSet1          = $7EF368
DungeonMapSet2          = $7EF369

; =========================================================
; 7. COLLECTIBLES ($7EF38A-39F)
; =========================================================

; ---------------------------------------------------------
; Trade Items / Resources
; ---------------------------------------------------------
FishingRod              = $7EF38A
Bananas                 = $7EF38B
; $7EF38C/$7EF38E: legacy RingSlot1/RingSlot3 (flag off); keep unallocated.
Pineapples              = $7EF38D   ; Pineapple count (legacy RingSlot2 alias, flag off)
RockMeatCount           = $7EF38F   ; For Goron quest (legacy RingSlotsNum alias, flag off)
Seashells               = $7EF391
Honeycomb               = $7EF393
DekuSticks              = $7EF395

; ---------------------------------------------------------
; Tingle Maps ($7EF396-397)
; ---------------------------------------------------------
TingleMaps              = $7EF396   ; Bitfield of purchased maps
TingleId                = $7EF397   ; Next map index (0-7)

; ---------------------------------------------------------
; Dungeon Scrolls ($7EF398-39A)
; ---------------------------------------------------------
; Use !Scroll_* bit constants
DungeonScrolls          = $7EF398
PreviousScroll          = $7EF39A   ; For re-reading hints

; ---------------------------------------------------------
; Magic Bean Progress ($7EF39B)
; ---------------------------------------------------------
; Use !Bean_* bit constants
MagicBeanProgress       = $7EF39B

; ---------------------------------------------------------
; Journal & Story State ($7EF39C-39E)
; ---------------------------------------------------------
JournalState            = $7EF39C
; Reserved              = $7EF39D
IntroState              = $7EF39E   ; Link's House intro sequence

; ---------------------------------------------------------
; Part00 flags ($7EF30F)
; ---------------------------------------------------------
; Allocated 2026-09-27 from FreeBlock_Story (its last byte). Read/written only
; when !ENABLE_PART00_ARRIVAL_LINES or !ENABLE_PART00_CHECKPOINT = 1
; (Core/part00.asm), and only while GameState = 0. Vanilla unused; zero on
; new files. Read with AND masks.
Part00Flags             = $7EF30F
!Part00_VillagerB          = $01  ; villager line B ($202) shown (first wake)
!Part00_Checkpoint         = $02  ; Link went down the village hole (route checkpoint)
!Part00_DeathPending       = $04  ; respawned in the house after a death: say B2 ($203)
!Part00_Revisit            = $08  ; house entered again after B: talking gives B2

; ---------------------------------------------------------
; Magic Ring Save Block ($7EF3A1-3A6)
; ---------------------------------------------------------
; Reserved 2026-09-25 (ring-sram-overlap). Vanilla unused block, inside the
; saved and checksummed range. Read/written only when
; !ENABLE_RING_SRAM_RELOCATE = 1; symbols live in Items/magic_rings.asm:
;   +0 $7EF3A1 FOUNDRINGS   rings found, not appraised (..pa hlbs)
;   +1 $7EF3A2 MAGICRINGS   rings owned (..pa hlbs, bit order of the ring menu)
;   +2 $7EF3A3 RingSlot1    equipped ring ID (0 = empty; 2 Power, 3 Armor,
;                            4 Heart, 5 Light, 6 Blast, 7 Steadfast)
;   +3 $7EF3A4 RingSlot2    (0 with !ENABLE_ONE_RING: file load clears it)
;   +4 $7EF3A5 RingSlot3    (0 with !ENABLE_ONE_RING: file load clears it)
;   +5 $7EF3A6 PortalRodOwned (below). Was RingSlotsNum, a ring slot count
;                            that nothing read or wrote; the one-ring rule
;                            (decisions.org 2026-09-28) retired it.
; With the flag at 0 the ring symbols use the legacy addresses $7EF3D7/D8
; (= SideQuestProgress/2) and $7EF38C-38F (RingSlot2 = Pineapples,
; RingSlotsNum = RockMeatCount). Do not allocate $7EF38C or $7EF38E:
; saves made with the flag at 0 can hold ring IDs there.
RingSaveBlock           = $7EF3A1   ; 6 bytes ($7EF3A1-3A6)

; ---------------------------------------------------------
; Portal Rod ownership ($7EF3A6)
; ---------------------------------------------------------
; Allocated 2026-09-28 (M2 pause menu). Read/written only when
; !ENABLE_PORTAL_ROD_CELL = 1: it is the Items-grid ownership byte of the
; Portal Rod cell ($0202 = $19, Menu_AddressLong). Menu open sets it to 1
; when CustomRods $7EF351 >= 2 (Maple's upgrade), so older saves show the
; cell too. Free before: no reader or writer in the repo, its git history or
; usdasm; not indexed by any $7EF3xx,X write; zero on the SNES Classic saves
; checked 2026-09-26 (Docs/oracle.org). Inside the saved, checksummed range.
PortalRodOwned          = $7EF3A6   ; 0 = no, 1 = owned

; ---------------------------------------------------------
; Eon Owl appearances ($7EF3A7)
; ---------------------------------------------------------
; Allocated 2026-09-26 from FreeBlock_Large. Read/written only when
; !ENABLE_EON_OWL_ONE_SHOT = 1 (Sprites/NPCs/eon_owl.asm). The Owl appears
; twice in the Abyss (decisions.org "Abyss segment: fix direction"); each
; appearance happens once, then that Owl does not respawn.
;   bit 0: arrival Owl talked (map $40, message $1FA, before the Pearl;
;          needs the base-ROM placement, see Sprites/NPCs/eon_owl.asm)
;   bit 1: sword Owl talked (map $50, message $E6, after the Pearl)
; Vanilla unused; zero on the SNES Classic saves checked 2026-09-26. Read
; with AND masks.
EonOwlFlags             = $7EF3A7
!EonOwl_ArrivalTalked      = $01  ; bit 0 - first Abyss appearance done
!EonOwl_SwordTalked        = $02  ; bit 1 - second Abyss appearance ($E6) done

; ---------------------------------------------------------
; Water Gate States ($7EF411)
; ---------------------------------------------------------
WaterGateStates         = $7EF411

; =========================================================
; 8. SAVE FILE METADATA
; =========================================================

; ---------------------------------------------------------
; Spawn & World State ($7EF3C8-CA)
; ---------------------------------------------------------
; Use !Spawn_* constants for SpawnPoint
SpawnPoint              = $7EF3C8

; Miscellaneous progress (mostly vanilla ALTTP)
; Bitfield: t.dp s.bh
MiscProgress            = $7EF3C9

; World flag: bit 6 = Dark World
SavedWorld              = $7EF3CA

; Reserved
ReservedSave            = $7EF3CB

; ---------------------------------------------------------
; Player Name ($7EF3D9-E0)
; ---------------------------------------------------------
PlayerName1L            = $7EF3D9
PlayerName1H            = $7EF3DA
PlayerName2L            = $7EF3DB
PlayerName2H            = $7EF3DC
PlayerName3L            = $7EF3DD
PlayerName3H            = $7EF3DE
PlayerName4L            = $7EF3DF
PlayerName4H            = $7EF3E0

; ---------------------------------------------------------
; Checksum ($7EF3E1-E2)
; ---------------------------------------------------------
SaveChecksumL           = $7EF3E1
SaveChecksumH           = $7EF3E2

; ---------------------------------------------------------
; Games Played Per Dungeon ($7EF3E3-3FD)
; ---------------------------------------------------------
GamesSewer              = $7EF3E3
GamesHyruleCastle       = $7EF3E5
GamesEastern            = $7EF3E7
GamesDesert             = $7EF3E9
GamesAgahnim            = $7EF3EB
GamesSwamp              = $7EF3ED
GamesPalaceOfDarkness   = $7EF3EF
GamesMiseryMire         = $7EF3F1
GamesSkullWoods         = $7EF3F3
GamesIcePalace          = $7EF3F5
GamesTowerOfHera        = $7EF3F7
GamesThievesTown        = $7EF3F9
GamesTurtleRock         = $7EF3FB
GamesGanonsTower        = $7EF3FD

; ---------------------------------------------------------
; Total Games Played ($7EF3FF-401)
; ---------------------------------------------------------
GamesCurrentSegment     = $7EF3FF
TotalGamesPlayed        = $7EF401

; ---------------------------------------------------------
; Misc Save Data ($7EF403-4FF)
; ---------------------------------------------------------
ReservedBlock           = $7EF403
DeathsMaxed             = $7EF405

; Inverse checksum
SaveInverseChecksumL    = $7EF4FE
SaveInverseChecksumH    = $7EF4FF

; =========================================================
; 9. FOLLOWER SYSTEM ($7EF3CC-D3)
; =========================================================

; Current follower ID (0 = none)
FollowerId              = $7EF3CC

; Follower position cache
FollowerCoordYL         = $7EF3CD
FollowerCoordYH         = $7EF3CE
FollowerCoordXL         = $7EF3CF
FollowerCoordXH         = $7EF3D0

; Follower state
FollowerIndoors         = $7EF3D1   ; Copies INDOORS
SavedFollowerLayer      = $7EF3D2   ; Copies LAYER (SRAM cache)
FollowerActive          = $7EF3D3   ; 0x00=Following, 0x80=Not following

; =========================================================
; LEGACY ALIASES (for backward compatibility)
; =========================================================
; These aliases maintain compatibility with existing code.
; New code should use the standardized names above.

OOSPROG                 = StoryProgress
OOSPROG2                = StoryProgress2
CURHP                   = CurrentHealth
MAXHP                   = MaxHealth
KEYS                    = CurrentKeys
RUPEEDISP               = RupeesDisplay
HEARTPC                 = HeartPieces
ZAPME                   = MagicRefill
BOMBME                  = BombRefill
SHOOTME                 = ArrowRefill
BOMBCAP                 = BombCapacity
ARROWCAP                = ArrowCapacity
WISHRUP                 = WishRupees
COMPASS1                = CompassSet1
COMPASS2                = CompassSet2
BIGKEY1                 = BigKeySet1
BIGKEY2                 = BigKeySet2
DNGMAP1                 = DungeonMapSet1
DNGMAP2                 = DungeonMapSet2
KEYSSEWER               = KeysSewer
KEYSHYRULE              = KeysHyruleCastle
KEYSEAST                = KeysEastern
KEYSDESERT              = KeysDesert
KEYSAGA                 = KeysAgahnim
KEYSSWAMP               = KeysSwamp
KEYSPOD                 = KeysPalaceOfDarkness
KEYSMIRE                = KeysMiseryMire
KEYSWOODS               = KeysSkullWoods
KEYSICE                 = KeysIcePalace
KEYSHERA                = KeysTowerOfHera
KEYSTHIEF               = KeysThievesTown
KEYSTROCK               = KeysTurtleRock
KEYSGANON               = KeysGanonsTower
PROGLITE2               = MiscProgress
SAVEWORLD               = SavedWorld
FOLLOWER                = FollowerId
FOLLOWCYL               = FollowerCoordYL
FOLLOWCYH               = FollowerCoordYH
FOLLOWCXL               = FollowerCoordXL
FOLLOWCXH               = FollowerCoordXH
FOLLOWERINOUT           = FollowerIndoors
FOLLOWERCLAYER          = SavedFollowerLayer
FOLLOWERING             = FollowerActive
GPSEWER                 = GamesSewer
GPHYRULE                = GamesHyruleCastle
GPEAST                  = GamesEastern
GPDESERT                = GamesDesert
GPAGA                   = GamesAgahnim
GPSWAMP                 = GamesSwamp
GPPOD                   = GamesPalaceOfDarkness
GPMIRE                  = GamesMiseryMire
GPWOODS                 = GamesSkullWoods
GPICE                   = GamesIcePalace
GPHERA                  = GamesTowerOfHera
GPTHIEF                 = GamesThievesTown
GPTROCK                 = GamesTurtleRock
GPGANON                 = GamesGanonsTower
GPNOW                   = GamesCurrentSegment
GAMESPLAYED             = TotalGamesPlayed
SCHKSML                 = SaveChecksumL
SCHKSMH                 = SaveChecksumH
SAVEICKSML              = SaveInverseChecksumL
SAVEICKSMH              = SaveInverseChecksumH
NAME1L                  = PlayerName1L
NAME1H                  = PlayerName1H
NAME2L                  = PlayerName2L
NAME2H                  = PlayerName2H
NAME3L                  = PlayerName3L
NAME3H                  = PlayerName3H
NAME4L                  = PlayerName4L
NAME4H                  = PlayerName4H
RockMeat                = RockMeatCount
Scrolls                 = DungeonScrolls
PrevScroll              = PreviousScroll
MagicBeanProg           = MagicBeanProgress
StoryState              = IntroState
Pearl                   = MoonPearl
Ability                 = AbilityFlags
Byrna                   = CustomRods        ; Note: Address conflict with CustomRods
SideQuestProg           = SideQuestProgress
SideQuestProg2          = SideQuestProgress2

; =========================================================
; 10. FREE SRAM BLOCKS (Available for Future Use)
; =========================================================
; This section documents all unused SRAM addresses.
; When adding new features, allocate from these blocks.
;
; IMPORTANT: Update this section when claiming addresses!
;
; ---------------------------------------------------------
; Story Extension Block ($7EF307-30F) - 9 bytes
; ---------------------------------------------------------
; Purpose: Reserved for additional story/quest flags
; Suggested uses:
;   - Additional NPC encounter flags
;   - Extended side quest progress
;   - World event triggers
; Allocated: $7EF304 = ElderGuideStage
;            $7EF305 = ZoraWaterfallHint
;            $7EF306 = CastleAmbushFlags
;            $7EF30F = Part00Flags (2026-09-27)
;
FreeBlock_Story    = $7EF307  ; 8 bytes ($7EF307-30E)

; ---------------------------------------------------------
; Item Extension Block ($7EF310-33F) - 48 bytes
; ---------------------------------------------------------
; Purpose: Reserved for new items or item metadata
; Suggested uses:
;   - New Y-button items
;   - Item upgrade levels
;   - Quest item tracking
;
FreeBlock_Items    = $7EF310  ; 48 bytes ($7EF310-33F)

; ---------------------------------------------------------
; Collectibles Extension ($7EF39F-3A0) - 2 bytes
; ---------------------------------------------------------
; Purpose: Reserved for additional collectible tracking
; Note: Small block, use for single-byte counters
;
FreeBlock_Collect  = $7EF39F  ; 2 bytes ($7EF39F-3A0)

; ---------------------------------------------------------
; Reserved Block ($7EF3AB-3C4) - 26 bytes
; ---------------------------------------------------------
; Purpose: Large block for complex features
; Suggested uses:
;   - Achievement system
;   - Extended map data
;   - NPC relationship tracking
; Allocated: $7EF3A1-3A6 = RingSaveBlock (magic rings)
;            $7EF3A7     = EonOwlFlags (Eon Owl appearances)
;            $7EF3A8     = BoundMask (independent R binding)
;            $7EF3A9-AA  = Goldstar ownership / migration version
;
; Independent mask selection, saved with the vanilla $500-byte save block.
; Proposed allocation for integrator: $7EF3A8; 0 none, 1-4 forms, 5 Stone.
; Validate range AND ownership before use; old saves may contain garbage.
BoundMask = $7EF3A8
; Proposed allocations: reconcile with integrator before applying.
GoldstarOwned = $7EF3A9       ; 0/1, independent of Hookshot $7EF342
GoldstarInventoryVersion = $7EF3AA ; $A5 = legacy upgrade migrated

; Saved Ocarina song ($7EF3AB). Allocated 2026-09-29 by the RC integrator.
; Read/written only when !ENABLE_EQUIPMENT_MENU = 1 (Items/ocarina.asm
; UpdateFluteSong_Long, Menu/menu_equipment.asm). 0 = unset, 1-4 = song.
; CurrentSong ($030F) is volatile WRAM; this byte keeps the Equipment
; choice across save/reload. Validated against learned songs ($7EF34C) on
; every use; out-of-range or garbage values become song 1.
; Free before: no reader/writer in the full candidate chain or main; no
; indexed $7EF3xx,X write reaches it (only bottles $7EF35C,X); none of the
; 76 item-receipt destinations ($0984E8) is in $7EF3A0-3C4; vanilla new-file
; init clears it ($0CC315-$0CC325); 00 in every stored save checked.
SavedOcarinaSong   = $7EF3AB
FreeBlock_Large    = $7EF3AC  ; 25 bytes ($7EF3AC-3C4)

; ---------------------------------------------------------
; Dreams Extension ($7EF411-4FD) - 237 bytes
; ---------------------------------------------------------
; Purpose: Large block after dreams/water gates
; Note: $7EF4FE-4FF are checksum (do not use)
;
FreeBlock_Dreams   = $7EF412  ; ~236 bytes ($7EF412-4FD)

; ---------------------------------------------------------
; FREE BLOCK SUMMARY
; ---------------------------------------------------------
; | Start    | End      | Size  | Purpose            |
; |----------|----------|-------|--------------------|
; | $7EF307  | $7EF30E  | 8     | Story extension    |
; | $7EF310  | $7EF33F  | 48    | Item extension     |
; | $7EF39F  | $7EF3A0  | 2     | Collectibles ext   |
; | $7EF3AB  | $7EF3C4  | 26    | Large reserved     |
; | $7EF412  | $7EF4FD  | 236   | Dreams extension   |
; |----------|----------|-------|--------------------|
; | TOTAL AVAILABLE:    | 320   | bytes              |
; ---------------------------------------------------------

; =========================================================
; END OF SRAM DEFINITIONS
; =========================================================
