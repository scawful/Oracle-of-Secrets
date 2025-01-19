
; Game state
;   0x00 - Very start; progress cannot be saved in this state
;   0x01 - Uncle reached
;   0x02 - Zelda rescued
;   0x03 - Agahnim defeated
GameState       = $7EF3C5

; Red X on Hall of Secrets
; Red X on Kalyxo Pyramid

; .fmp h.i.
;  f - fortress of secrets
;  m - master sword
;  p - pendant quest
;  h - hall of secrets
;  i - intro over, maku tree
OOSPROG         = $7EF3D6

; Bitfield of less important progression
; .fbh .zsu
;   u - Uncle
;   s - Priest visited in sanc after Zelda is kidnapped again
;   z - Zelda brought to sanc
;   h - Uncle left Link's house (0: spawn | 1: gone)
;   b - Book of Mudora obtained/mentioned; controls Aginah dialog
;   f - Flipped by fortune tellers to decide fortune set to give
OOSPROG2       = $7EF3C6

; .... ...m
;   m - maku tree has met link (0: no | 1: yes)
MakuTreeQuest  = $7EF3D4

; Map icon
;   0x00 - Red X on Maku Tree/Maku Warp
;   0x01 - Toadstool Woods Crystal
;   0x02 - Kalyxo All Crystals
;   0x03 -
;   0x04 -
;   0x05 -
;   0x06 -
;   0x07 -
;   0x08 - Skull on GT        | Climb Ganon's Tower
MapIcon        = $7EF3C7

; 01 - Fishing Rod
; 02 - Portal Rod
CustomRods = $7EF351

; Free SRAM Block 38A-3C4
FishingRod = $7EF38A

; Collectibles
Bananas    = $7EF38B
Pineapples = $7EF38D
RockMeat   = $7EF38F
Seashells  = $7EF391
Honeycomb  = $7EF393
DekuSticks = $7EF395

TingleMaps = $7EF396
TingleId   = $7EF397

; .dgi zktm
;   m - Mushroom Grotto
;   t - Tail Palace
;   k - Kalyxo Castle
;   z - Zora Temple
;   i - Glacia Estate
;   g - Goron Mines
;   d - Dragon Ship
Scrolls    = $7EF398

; Keep track of the previous scroll
; For re-reading old hints.
PrevScroll = $7EF39A

; .dts fwpb
;   b - bean planted
;   w - plant watered
;   p - pollinated by bee
;   f - first day
;   s - second day
;   t - third day
;   d - done
MagicBeanProg = $7EF39B

; .... .cpw
;   c - courage
;   p - power
;   w - wisdom
Dreams        = $7EF410

; =========================================================
; Items
; =========================================================
; 0x00 - Nothing
; 0x01 - Bow
; 0x02 - Bow and arrows
; 0x03 - Silver bow
; 0x04 - Silver bow and arrows
; Picking the arrow and nonarrow versions is done by the HUD draw routines
BOW             = $7EF340

; 0x00 - Nothing
; 0x01 - Blue boomerang
; 0x02 - Red boomerang
BOOMER          = $7EF341

; 0x00 - Nothing
; 0x01 - Hookshot
; 0x02 - Goldstar (L/R)
HOOKSHOT        = $7EF342

; Number of bombs
BOMBS           = $7EF343

; 0x00 - Nothing
; 0x01 - Mushroom
; 0x02 - Powder
SHROOM          = $7EF344

; 0x00 - Nothing
; 0x01 - Fire rod
FIREROD         = $7EF345

; 0x00 - Nothing
; 0x01 - Ice rod
ICEROD          = $7EF346

; 0x00 - Nothing
; 0x01 - Zora Mask
ZoraMask        = $7EF347

; 0x00 - Nothing
; 0x01 - Bunny Hood
BunnyHood       = $7EF348

; 0x00 - Nothing
; 0x01 - Deku Mask
DekuMask        = $7EF349

; 0x00 - Nothing
; 0x01 - Lamp
LAMP            = $7EF34A

; 0x00 - Nothing
; 0x01 - Magic hammer
HAMMER          = $7EF34B

; 0x00 - Nothing
; 0x01 - Shovel
; 0x02 - Inactive flute
; 0x03 - Active flute
FLUTE           = $7EF34C

; 0x00 - Nothing
; 0x01 - Roc's Feather
RocsFeather     = $7EF34D

; 0x00 - Nothing
; 0x01 - Book of Mudora
BOOK            = $7EF34E

; 0x00 - Nothing
; Other values indicate the index of the currently selected bottle
BottleIndex     = $7EF34F

; 0x00 - Nothing
; 0x01 - Cane of Somaria
SOMARIA         = $7EF350

; 0x00 - Nothing
; 0x01 - Cane of Byrna
BYRNA           = $7EF351

; 0x00 - Nothing
; 0x01 - Magic cape
CAPE            = $7EF352

; 0x00 - Nothing
; 0x01 - Letter (works like mirror)
; 0x02 - Mirror
; 0x03 - Deleted triforce item
MIRROR          = $7EF353

; 0x00 - Lift 1 (nothing)
; 0x01 - Lift 2 (power glove)
; 0x02 - Lift 3 (titan's mitt)
GLOVES          = $7EF354

; 0x00 - Nothing
; 0x01 - Pegasus boots
; bit 2 of $7E:F379 also needs to be set to actually dash
BOOTS           = $7EF355

; 0x00 - Nothing
; 0x01 - Zora's flippers
FLIPPERS        = $7EF356

; 0x00 - Nothing
; 0x01 - Moon pearl
PEARL           = $7EF357

; 0x00 - Nothing
; 0x01 - Wolf Mask
WolfMask        = $7EF358

; 0x00 - Nothing
; 0x01 - Fighter sword
; 0x02 - Master sword
; 0x03 - Tempered sword
; 0x04 - Golden sword
; 0xFF - Set when sword is handed in to smithy
SWORD           = $7EF359

; 0x00 - Nothing
; 0x01 - Fighter shield
; 0x02 - Fire shield
; 0x03 - Mirror shield
SHIELD          = $7EF35A

; 0x00 - Green mail
; 0x01 - Blue mail
; 0x02 - Red mail
ARMOR           = $7EF35B

; 0x00 - Nothing
; 0x01 - Mushroom (unused)
; 0x02 - Empty bottle
; 0x03 - Red potion
; 0x04 - Green potion
; 0x05 - Blue potion
; 0x06 - Fairy
; 0x07 - Bee
; 0x08 - Good bee
; 0x09 - Magic Bean
; 0x0A - Milk Bottle
Bottle1         = $7EF35C
Bottle2         = $7EF35D
Bottle3         = $7EF35E
Bottle4         = $7EF35F

; Number of rupees you have
; RUPEEDISP will be incremented or decremented until it reaches this value
RUPEES          = $7EF360

; Rupee count displayed on the HUD
RUPEEDISP       = $7EF362

; Bitfields for ownership of various dungeon items
;   SET 2        SET 1
; xced aspm    wihb tg..
;   c - Hyrule Castle
;   x - Sewers
;   a - Agahnim's Tower
;
;   e - Eastern Palace
;   d - Desert Palace
;   h - Tower of Hera
;
;   p - Palace of Darkness
;   s - Swamp Palace
;   w - Skull Woods
;   b - Thieves' Town
;   i - Ice Palace
;   m - Misery Mire
;   t - Turtle Rock
;   g - Ganon's Tower
COMPASS1        = $7EF364
COMPASS2        = $7EF365

BIGKEY1         = $7EF366
BIGKEY2         = $7EF367

DNGMAP1         = $7EF368
DNGMAP2         = $7EF369

; Number of rupees donated to fairies
WISHRUP         = $7EF36A

; Number of heart pieces towards next container
; Intended to be a value from 0-3
HEARTPC         = $7EF36B

; Maximum health; 1 heart container = 0x08 HP
MAXHP           = $7EF36C

; Current health
; You die at 0x00
; You also die at ≥0xA8
CURHP           = $7EF36D

; Magic power, capped at 128
MAGPOW          = $7EF36E

; Current number of keys for whatever dungeon is loaded
KEYS            = $7EF36F

; Number of capacity upgrades received
BOMBCAP         = $7EF370
ARROWCAP        = $7EF371

; Refills health
; Expects multiples of 8
HEALME          = $7EF372

; Refills magic
ZAPME           = $7EF373

; ... ..gbr
;   r - Wisdom  (red)
;   b - Power   (blue)
;   g - Courage (green)
PENDANTS        = $7EF374

; Refills bombs
BOMBME          = $7EF375

; Refills arrows
SHOOTME         = $7EF376

; Arrow count
ARROWS          = $7EF377

; Unused
UNUSED_7EF378   = $7EF378

; Displays ability flags
; lrtu pbsh
;  h - Pray (unused and mostly cut off by HUD borders)
;  s - Swim
;  b - Run
;  u - unused but set by default
;  p - Pull
;  t - Talk
;  r - Read
;  l - Lift
;      This only controls the display of "LIFT.1"
;      If this bit is unset but LIFT is set then the proper lift text is displayed
ABILITY         = $7EF379

; Dungeon ID Legend
; Mushroom Grotto ID 0x0C (Palace of Darkness)
; Tail Palace ID 0x0A (Swamp Palace)
; Kalyxo Castle ID 0x10 (Skull Woods)
; Zora Temple ID 0x16 (Thieves Town)
; Glacia Estate 0x12 (Ice Palace)
; Goron Mines 0x0E (Misery Mire)
; Dragon Ship 0x18 (Turtle Rock)

; .wbs tipm
;   p - Palace of Darkness
;   s - Swamp Palace
;   w - Skull Woods
;   b - Thieves' Town
;   i - Ice Palace
;   m - Misery Mire
;   t - Turtle Rock
Crystals        = $7EF37A

; 0x00 - Normal magic
; 0x01 - Half magic
; 0x02 - Quarter magic
; Quarter magic has no special HUD graphic, unlike half magic
; Also, not everything is necessarily quarter magic
MAGCON          = $7EF37B

; Keys earned per dungeon
; Sewers and Castle are kept in sync
KEYSSEWER       = $7EF37C
KEYSHYRULE      = $7EF37D
KEYSEAST        = $7EF37E
KEYSDESERT      = $7EF37F
KEYSAGA         = $7EF380
KEYSSWAMP       = $7EF381
KEYSPOD         = $7EF382
KEYSMIRE        = $7EF383
KEYSWOODS       = $7EF384
KEYSICE         = $7EF385
KEYSHERA        = $7EF386
KEYSTHIEF       = $7EF387
KEYSTROCK       = $7EF388
KEYSGANON       = $7EF389

; Unused block of SRAM
UNUSED_7EF38A   = $7EF38A

; Game state
;   0x00 - Very start; progress cannot be saved in this state
;   0x01 - Uncle reached
;   0x02 - Zelda rescued
;   0x03 - Agahnim defeated
GAMESTATE       = $7EF3C5

; Bitfield of less important progression
; .fbh .zsu
;   u - Uncle visited in secret passage; controls spawn (0: spawn | 1: gone)
;   s - Priest visited in sanc after Zelda is kidnapped again
;   z - Zelda brought to sanc
;   h - Uncle has left Link's house; controls spawn (0: spawn | 1: gone)
;   b - Book of Mudora obtained/mentioned; controls Aginah dialog
;   f - Flipped by fortune tellers to decide which fortune set to give
PROGLITE        = $7EF3C6

; Map icon to guide noob players
;   0x00 - Red X on castle    | Save zelda
;   0x01 - Red X on Kakariko  | Talk to villagers about elders
;   0x02 - Red X on Eastern   | Talk to Sahasrahla
;   0x03 - Pendants and MS    | Obtain the master sword
;   0x04 - Master sword on LW | Grab the master sword
;   0x05 - Skull on castle    | Kill Agahnim
;   0x06 - Crystal on POD     | Get the first crystal
;   0x07 - Crystals           | Get all 7 crystals
;   0x08 - Skull on GT        | Climb Ganon's Tower
MAPICON         = $7EF3C7

; 0x00 - Link's house
; 0x01 - Sanctuary
; 0x02 - Prison
; 0x03 - Uncle
; 0x04 - Throne
; 0x05 - Old man cave
; 0x06 - Old man home
SPAWNPT         = $7EF3C8

; Another bitfield for progress
; t.dp s.bh
;   t - smiths are currently tempering sword
;   d - swordsmith rescued
;   p - purple chest has been opened
;   s - stumpy has been stumped
;   b - bottle purchased from vendor
;   h - bottle received from hobo
PROGLITE2       = $7EF3C9

; .d.. ....
;   d - World (0: Light World | 1: Dark World)
SAVEWORLD       = $7EF3CA

; Not used
UNUSED_7EF3CB   = $7EF3CB

; Current follower ID
FOLLOWER        = $7EF3CC

; Cache of follower properties
FOLLOWCYL       = $7EF3CD
FOLLOWCYH       = $7EF3CE
FOLLOWCXL       = $7EF3CF
FOLLOWCXH       = $7EF3D0

; Copies INDOORS
FOLLOWERINOUT   = $7EF3D1

; Copies LAYER
FOLLOWERCLAYER  = $7EF3D2

; Indicates the follower is currently following
;   0x00 - Following
;   0x80 - Not following
FOLLOWERING     = $7EF3D3

; Unused
UNUSED_7EF3D4   = $7EF3D4
UNUSED_7EF3D5   = $7EF3D5
UNUSED_7EF3D6   = $7EF3D6
UNUSED_7EF3D7   = $7EF3D7
UNUSED_7EF3D8   = $7EF3D8

; Player name
NAME1L          = $7EF3D9
NAME1H          = $7EF3DA
NAME2L          = $7EF3DB
NAME2H          = $7EF3DC
NAME3L          = $7EF3DD
NAME3H          = $7EF3DE
NAME4L          = $7EF3DF
NAME4H          = $7EF3E0

; Save file checksum; expected to be $55AA
SCHKSML         = $7EF3E1
SCHKSMH         = $7EF3E2

; Games played in each dungeon
GPSEWER         = $7EF3E3
GPHYRULE        = $7EF3E5
GPEAST          = $7EF3E7
GPDESERT        = $7EF3E9
GPAGA           = $7EF3EB
GPSWAMP         = $7EF3ED
GPPOD           = $7EF3EF
GPMIRE          = $7EF3F1
GPWOODS         = $7EF3F3
GPICE           = $7EF3F5
GPHERA          = $7EF3F7
GPTHIEF         = $7EF3F9
GPTROCK         = $7EF3FB
GPGANON         = $7EF3FD

; Games played for current segment
GPNOW           = $7EF3FF

; Total games played
; No display on file select if 0xFFFF
GAMESPLAYED     = $7EF401

; Big unused block
UNUSED_7EF403   = $7EF403
DEATHS_MAXED    = $7EF405

; Inverse checksum for save file
SAVEICKSML      = $7EF4FE
SAVEICKSMH      = $7EF4FF