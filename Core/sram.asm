; =========================================================
; Oracle of Secrets - SRAM Definitions
; =========================================================
; Standardized naming convention: PascalCase for all variables
; Bit constants use !Prefix_Name format
; @doc Docs/Technical/Flag_Ledger.md
; @source Primary flag definitions live here
; @verified 2026-01-23 (code audit)
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
;  10. Free Blocks Reference (334 bytes available)
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
!Story_IntroComplete       = $01  ; bit 0 - Intro complete (setter unknown; Maku Tree sets bit 1)
!Story_HallOfSecrets       = $02  ; bit 1 - Hall of Secrets flag
!Story_PendantQuest        = $04  ; bit 2 - Shrine access
!Story_VillageElderMet     = $10  ; bit 4 - Elder met (Master Sword?)
!Story_MasterSword         = $10  ; bit 4 - (alias, same as above)
!Story_FortressComplete    = $80  ; bit 7 - Final dungeon done

; ---------------------------------------------------------
; StoryProgress2 Bits (OOSPROG2 @ $7EF3C6)
; ---------------------------------------------------------
; Bitfield: .fbh .zsu (repurposed from ALTTP)
!Story2_ImpaIntro          = $01  ; bit 0 - Impa intro complete
!Story2_SanctuaryVisit     = $02  ; bit 1 - Sanctuary post-kidnap
!Story2_KydrogEncounter    = $04  ; bit 2 - Kydrog encounter done
!Story2_ImpaLeftHouse      = $08  ; bit 3 - Impa left Link's house
!Story2_LegacyHouseFlag    = $10  ; bit 4 - Legacy vanilla flag reused for intro house state
!Story2_BookOfSecrets      = $20  ; bit 5 - Book obtained
!Story2_FortuneTellerFlip  = $40  ; bit 6 - Fortune set toggle

; ---------------------------------------------------------
; Crystals Bits - Dungeon Completion ($7EF37A)
; ---------------------------------------------------------
; Uses ALTTP bit positions for compatibility
!Crystal_D1_MushroomGrotto = $01  ; bit 0 - Palace of Darkness slot
!Crystal_D6_GoronMines     = $02  ; bit 1 - Misery Mire slot
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
!SideQuest2_RanchGirl      = $01  ; bit 0 - Transformed back
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
!Dream_Wisdom              = $01  ; bit 0
!Dream_Power               = $02  ; bit 1
!Dream_Courage             = $04  ; bit 2

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
!MapIcon_Group_Midgame     = $04  ; Draws D4/D5/D6 markers together
!MapIcon_D7_DragonShip     = $05  ; Canonical value (legacy: $07)
!MapIcon_Fortress          = $06  ; Canonical value (legacy: $08)
!MapIcon_D7_DragonShip_Legacy = $07
!MapIcon_Fortress_Legacy      = $08
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
;   bits 0-3: stage id (0-15)
;   bit 6: show Pyramid icon (post-D3 guidance)
ElderGuideStage         = $7EF304

; Impa guidance stage (Hall of Secrets check-in)
;   bits 0-3: stage id (0-15)
;   bit 7: show Hall of Secrets icon
ImpaGuideStage          = $7EF305

; Reserved: $7EF306-30F available for future use

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
Hookshot                = $7EF342   ; 1=Hookshot, 2=Goldstar
Bombs                   = $7EF343   ; Count
MagicPowder             = $7EF344   ; 1=Mushroom, 2=Powder
FireRod                 = $7EF345   ; 1=Have
IceRod                  = $7EF346   ; 1=Have
ZoraMask                = $7EF347   ; 1=Have (inventory slot)
BunnyHood               = $7EF348   ; 1=Have
DekuMask                = $7EF349   ; 1=Have (inventory slot)
Lamp                    = $7EF34A   ; 1=Have
Hammer                  = $7EF34B   ; 1=Have
Flute                   = $7EF34C   ; 0=None, 1=Ocarina, 2=Healing, 3=Storms, 4=Soaring, 5=Time
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
Boots                   = $7EF355   ; 1=Pegasus Boots (also needs Ability bit)
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
Pineapples              = $7EF38D
RockMeatCount           = $7EF38F   ; For Goron quest
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
; Story Extension Block ($7EF304-30F) - 12 bytes
; ---------------------------------------------------------
; Purpose: Reserved for additional story/quest flags
; Suggested uses:
;   - Additional NPC encounter flags
;   - Extended side quest progress
;   - World event triggers
;
FreeBlock_Story    = $7EF304  ; 12 bytes ($7EF304-30F)

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
; Reserved Block ($7EF3A1-3C4) - 36 bytes
; ---------------------------------------------------------
; Purpose: Large block for complex features
; Suggested uses:
;   - Achievement system
;   - Extended map data
;   - NPC relationship tracking
;
FreeBlock_Large    = $7EF3A1  ; 36 bytes ($7EF3A1-3C4)

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
; | $7EF304  | $7EF30F  | 12    | Story extension    |
; | $7EF310  | $7EF33F  | 48    | Item extension     |
; | $7EF39F  | $7EF3A0  | 2     | Collectibles ext   |
; | $7EF3A1  | $7EF3C4  | 36    | Large reserved     |
; | $7EF412  | $7EF4FD  | 236   | Dreams extension   |
; |----------|----------|-------|--------------------|
; | TOTAL AVAILABLE:    | 334   | bytes              |
; ---------------------------------------------------------

; =========================================================
; END OF SRAM DEFINITIONS
; =========================================================
