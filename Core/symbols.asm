; =========================================================
; WRAM in Use
org $008000
base $7E0730 ; MAP16OVERFLOW free ram region

MenuScrollLevelV:         skip 1
MenuScrollLevelH:         skip 1
MenuScrollHDirection:     skip 2
MenuItemValueSpoof:       skip 2
ShortSpoof:               skip 1
MusicNoteValue:           skip 2
OverworldLocationPointer: skip 2
HasGoldstar:              skip 1
GoldstarOrHookshot:       skip 1
Neck_Index:               skip 1
Neck1_OffsetX:            skip 1
Neck1_OffsetY:            skip 1
Neck2_OffsetX:            skip 1
Neck2_OffsetY:            skip 1
Neck3_OffsetX:            skip 1
Neck3_OffsetY:            skip 1
Offspring1_Id:            skip 1
Offspring2_Id:            skip 1
Offspring3_Id:            skip 1
Kydreeok_Id:              skip 1
FishingOrPortalRod:       skip 1

base off

; =========================================================

function RGBto555(R,G,B) = ((R/8)<<10)|((G/8)<<5)|(B/8) ; zarby
function hexto555(h) = ((((h&$FF)/8)<<10)|(((h>>8&$FF)/8)<<5)|(((h>>16&$FF)/8)<<0)) ; kan
function menu_offset(y,x) = (y*64)+(x*2)

; =========================================================
; SRAM in Use

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
OOSPROG3       = $7EF3D4

; Current Dream ID (0x00-0x07)
CurrentDream   = $0426

CurrentSong    = $030F

; .dgi zktm
;   m - Mushroom Grotto
;   t - Tail Palace
;   k - Kalyxo Castle
;   z - Zora Temple
;   i - Glacia Estate
;   g - Goron Mines
;   d - Dragon Ship
DREAMS         = $7EF410

; Collectibles
Bananas    = $7EF38B
Pineapples = $7EF38D
RockMeat   = $7EF38F
Seashells  = $7EF391
Honeycomb  = $7EF393
DekuSticks = $7EF395

; 01 - Fishing Rod
; 02 - Portal Rod
CUSTOMRODS     = $7EF351

FishingRod = $7EF38A

; =========================================================
; Sprite RAM and Functions

SprY         = $0D00
SprX         = $0D10
SprYH        = $0D20
SprXH        = $0D30

SprYSpeed    = $0D40
SprXSpeed    = $0D50

SprYRound    = $0D60
SprXRound    = $0D70

SprCachedX   = $0FD8
SprCachedY   = $0FDA

SprAction    = $0D80 ; Indexes the action jump table
SprFrame     = $0D90 ; Indexes the SprGfx for drawing
SprGfx       = $0DC0 ; Determine the GFX used for the sprite

SprMiscA     = $0DA0 ; Direction, position, or other misc usage
SprMiscB     = $0DB0 ; Various usages, truly auxiliary
SprMiscC     = $0DE0 ; Cardinal direction the sprite is facing
SprMiscD     = $0E90 ; Pikit stolen item, misc usage
SprMiscE     = $0EB0 ; Head direction 0123 -> udlr
SprMiscF     = $0EC0 ;
SprMiscG     = $0ED0 ;

; Used in sprite state 0x03 (falling in water)
; used as delay in most of the sprites
SprDelay     = $0E80

; Enemy color flash buffer
SprFlash     = $0B89

SprTimerA    = $0DF0 ; Action,    decreased by 1 each frame
SprTimerB    = $0E00 ; Animation, decreased by 1 each frame
SprTimerC    = $0E10 ;            decreased by 1 each frame
SprTimerD    = $0EE0 ;            decreased by 1 each frame
SprTimerE    = $0F10 ;            decreased by 1 each frame
SprTimerF    = $0F80 ; Gravity,   decreased by 2 each frame

SprSlot      = $0FA0 ; Current sprite slot being executed

SprStunTimer = $0B58 ; counts down from 0xFF

SprPause     = $0F00 ; Inactive if nonzero
SprFloor     = $0F20 ; 0 (top layer), 1 (bottom layer)
SprType      = $0E20 ; Sprite ID
SprSubtype   = $0E30 ; Sprite subtype

; hmwo oooo
;   o - define the number of OAM slots used by the sprite
;   w - Causes enemies to go towards the walls
;   m - Master sword ceremony sprite flag
;   h - If set, harmless. Unset you take damage from contact.
SprNbrOAM    = $0E40
SprHealth    = $0E50

; 0x00 - Sprite is dead, totally inactive
; 0x01 - Sprite falling into a pit with generic animation.
; 0x02 - Sprite transforms into a puff of smoke, often producing an item
; 0x03 - Sprite falling into deep water (optionally making a fish jump up?)
; 0x04 - Death mode for bosses
; 0x05 - Sprite falling into a pit that has a special animation
; 0x06 - Death Mode for normal creatures.
; 0x08 - Sprite is being spawned at load time.
;      An initialization routine will be run for one frame,
;      and then move on to the active state (0x09) next frame.
; 0x09 - Sprite is in the normal, active mode.
; 0x0A - Sprite is being carried by the player.
; 0x0B - Sprite is frozen and / or stunned.
SprState     = $0DD0

; nios pppt
;   n - if set, don't draw extra death anim
;   i - impervious to attacks and collision? TODO
;   o - shadow size (0: normal | 1: small)
;   s - shadow (0: no shadow | 1: shadow)
;   p - palette used for OAM props
;   t - name table used for OAM props
SprGfxProps  = $0E60

; Direction of sprite collision with wall
SprCollision = $0E70

; Definitely closely tied to the process of a sprite taking damage.
; Seems to serve as a palette cycling index, or a state variable.
; When this value is positive
; 0x80 -  Signal that the recoil process has finished
;         and will terminate during this frame.
SprRecoil    = $0EA0 ; Recoil Timer

; abbbbbbb:
;   a - start death timer
;   b - death timer
SprDeath     = $0EF0

SprYRecoil   = $0F30
SprXRecoil   = $0F40

; DIWS UUUU
;   D - boss death
;   I - Impervious to all attacks
;   W - Water slash
;   S - Draw Shadow
;   U - Unused
SprProps     = $0F50

; ISPH HHHH
;   I - ignore collisions
;   S - Statis (not alive eg beamos)
;   P - Persist code still run outside of camera
;   H - Hitbox
SprHitbox    = $0F60
SprHeight    = $0F70 ; Distance from the shadow
SprHeightS   = $0F90 ; Distance from the shadow subpixel
SprFreeze    = $0FC1 ; Seems to freeze sprites

; Primarily deals with bump damage
; tzpd bbbb
;   t - TODO
;   z - High priority target for bees to give hints
;   p - Powder interaction (0: normal | 1: ignore)
;   d - Behavior when a boss spawns (0: die | 1: live)
;   b - bump damage class
;   Bump damage classes are read from a table at $06F42D
;   Each table entry has 3 values, for green, blue, and red mails
;   class   g    b    r
;   0x00    2    1    1
;   0x01    4    4    4
;   0x02    0    0    0
;   0x03    8    4    2
;   0x04    8    8    8
;   0x05   16    8    4
;   0x06   32   16    8
;   0x07   32   24   16
;   0x08   24   16    8
;   0x09   64   48   24
;
; Higher values are invalid, but here's what they are:
;   0x0A  169   48   32
;   0x0B  142  246  169
;   0x0C  144  133   71
;   0x0D  169   16  133
;   0x0E   70  169   33
;   0x0F   34  124  187
SprBump      = $0CD2

; Damage sprite is enduring
SprDmgTaken       = $0CE2

; Sprite Deflection Properties
;   abcdefgh
;   a - If set, sprite is active
;   b - Same as bit 'a' for Zora.
;   c - Never queried, pushable interaction flag
;   d - If hit from front, deflect Ice Rod, Somarian missile,
;       boomerang, hookshot, and sword beam, and arrows stick in
;       it harmlessly.  If bit 1 is also set, frontal arrows will
;       instead disappear harmlessly.  No monsters have bit 4 set
;       in the ROM data, but it was functional and interesting
;       enough to include.
;   e - If set, sprite collides with less tiles than usual
;   f - If set, impervious to sword and hammer type attacks
;   g - If set, impervious to arrows, but may have other additional meanings.
;   h - Handles behavior with previous deaths flagged in $7FDF80 (0: default | 1: ignore)
SprDefl      = $0CAA

; iwbs pppp
;   i - disable tile interaction
;   w - something water
;   b - sprite is blocked by shield
;   s - taking damage sfx to use TODO name
;   p - prize pack
SprPrize     = $0BE0

; tttt a.bp
;   t - tile interaction hitbox
;   a - deflect arrows TODO VERIFY
;   b - boss death
;   p - Sprite ignores falling into a pit when frozen?
SprTileDie   = $0B6B

; For sprites that interact with speical objects (arrows in particular)
; the special object will identify its type to the sprite via this location.
SprSpecial   = $0BB0

; If nonzero, ancillae do not interact with the sprite
; Bulletproof
SprBulletproof = $0BA0

SprRoom      = $0C9A ;X W Contains the area or room id the sprite has been loaded in
SprDrop      = $0CBA ;X W 00: Drop nothing, 01: drop normal key, 03: Drop green rupee, OtherValues: Drop big key

; =========================================================

; The record format for the low table is 4 bytes:
;   byte OBJ*4+0: xxxxxxxx
;   byte OBJ*4+1: yyyyyyyy
;   byte OBJ*4+2: cccccccc
;   byte OBJ*4+3: vhoopppN

; The record format for the high table is 2 bits:
;   bit 0/2/4/6 of byte OBJ/4: X
;   bit 1/3/5/7 of byte OBJ/4: s

; Xxxxxxxxx = X position of the sprite. signed but see below.
; yyyyyyyy  = Y position of the sprite.
; cccccccc  = First tile of the sprite.
; N         = Name table of the sprite. See below for VRAM address calculation
; ppp       = Palette of the sprite. The first palette index is 128+ppp*16.
; oo        = Sprite priority. See below for details.
; h/v       = Horizontal/Vertical flip flags.
; s         = Sprite size flag. See below for details.

OAMPtr       = $90
OAMPtrH      = $92

OamBackup   = $0FEC

SpriteData_OAMProp = $0DB359

; Clear all properties for sprites
SpritePrep_ResetProperties = $0DB871

; =========================================================
; set the oam coordinate for the sprite draw
Sprite_PrepOamCoord =  $06E416

; =========================================================
; Draw the sprite depending of the position of the player
; (if he has to be over or under link)
Sprite_OAM_AllocateDeferToPlayer = $06F864

OAM_AllocateFromRegionA = $0DBA80 ; Above
OAM_AllocateFromRegionB = $0DBA84 ; Below
OAM_AllocateFromRegionC = $0DBA88 ; Above
OAM_AllocateFromRegionD = $0DBA8C ; Above
OAM_AllocateFromRegionE = $0DBA90 ; Above
OAM_AllocateFromRegionF = $0DBA94 ; Above

Sprite_DrawMultiple_quantity_preset = $05DF70

; =========================================================
; check if the sprite is getting damage from player or items
Sprite_CheckDamageFromPlayer = $06F2AA

; =========================================================
; check if the sprite is touching the player to damage
Sprite_CheckDamageToPlayer = $06F121

; =========================================================
; damage the player everywhere on screen?
Sprite_AttemptDamageToPlayerPlusRecoil = $06F41F

; =========================================================
; makes all the sprites on screen shaking
ApplyRumbleToSprites = $0680FA

; =========================================================

Sprite_MoveLong = $1D808C

Sprite_ProjectSpeedTowardsPlayer = $06EA1A

Sprite_Decelerate_X = $05E657
Sprite_Decelerate_Y = $05E666

; =========================================================
; args:
; pos1_low  = $00
; pos1_size = $02
; pos2_low  = $04
; pos2_size = $06
; pos1_high = $08
; pos2_high = $0A
; ans_low   = $0F
; ans_high  = $0C
; returns carry clear if there was no overlap
CheckIfHitBoxesOverlap = $0683E6

; =========================================================
; $0FD8 = sprite's X coordinate
; $0FDA = sprite's Y coordinate
Sprite_Get16BitCoords_Local = $0684C1
Sprite_Get_16_bit_Coords = $0684BD

; =========================================================
; load / draw a 16x16 sprite
Sprite_PrepAndDrawSingleLarge = $06DBF0

; =========================================================
; load / draw a 8x8 sprite
Sprite_PrepAndDrawSingleSmall = $06DBF8

; =========================================================
; draw shadow (requires additional oam allocation)
Sprite_DrawShadow = $06DC54

Sprite_DrawWaterRipple = $059FFA
Sprite_DrawRippleIfInWater = $1EFF8D

; =========================================================
; check if the sprite is colliding with a solid tile set $0E70, X
; ----udlr , u = up, d = down, l = left, r = right
Sprite_CheckTileCollision = $06E496
Sprite_CheckTileCollision_long = $06E496

; =========================================================
; $00[0x02] - Entity Y coordinate
; $02[0x03?] - Entity X coordinate
; $0FA5
Sprite_GetTileAttr = $06E87B

; =========================================================
; check if the sprite is colliding with a solid sloped tile
Sprite_CheckSlopedTileCollision = $06E8FD

; =========================================================
; set the velocity x,y towards the player (A = speed)
Sprite_ApplySpeedTowardsPlayer = $06EA12

; =========================================================
; \return $0E is low byte of player_y_pos - sprite_y_pos
; \return $0F is low byte of player_x_pos - sprite_x_pos
Sprite_DirectionToFacePlayer = $06EAA0

; =========================================================
; if Link is to the left of the sprite, Y = 1, otherwise Y = 0.
Sprite_IsToRightOfPlayer = $06EACD

; =========================================================
; return Y=1 sprite is below player, otherwise Y = 0
Sprite_IsBelowPlayer = $06EAE4

; =========================================================
; $06 = sprite's Y coordinate
; $07 = sprite's X coordinate
Sprite_IsBelowLocation = $06EB1D

; =========================================================
; check damage done to player if they collide on same layer
Sprite_CheckDamageToPlayerSameLayer = $06F129

; =========================================================
; check damage done to player if they collide even if they are not on same layer
Sprite_CheckDamageToPlayerIgnoreLayer = $06F131

; =========================================================
; play a sound loaded in A
Sound_SetSfx1PanLong = $0DBB6E
Sound_SetSfx2PanLong = $0DBB7C
Sound_SetSfx3PanLong = $0DBB8A

; =========================================================
; spawn a new sprite on screen, A = sprite id
; when using this function you have to set the position yourself
; these values belong to the sprite who used that function not the new one
; $00 low x, $01 high x
; $02 low y, $03 high y
; $04 height, $05 low x (overlord)
; $06 high x (overlord), $07 low y (overlord)
; $08 high y (overlord)
Sprite_SpawnDynamically = $1DF65D

Sprite_SetSpawnedCoords = $09AE64
Sprite_SetSpawnedCoordinates = $09AE64

; =========================================================
; move the sprite if he stand on a conveyor belt
Sprite_ApplyConveyorAdjustment = $1D8010

; =========================================================
; Setup sprite hitbox for comparison with scrap ram
Sprite_SetupHitBoxLong = $0683EA

; =========================================================
; set tile of dungeon
Dungeon_SpriteInducedTilemapUpdate = $01E7A9

; =========================================================
; player can't pass through the sprite
Sprite_BehaveAsBarrier = $1EF4F3
Sprite_PlayerCantPassThrough = $1EF4F3

; =========================================================
; player can't hookshot to that sprite
Sprite_NullifyHookshotDrag = $0FF540

; =========================================================
; show a message box without any condition
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowMessageUnconditional = $05E219

; =========================================================
; show a message if we press A and face the sprite
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowSolicitedMessage = $05E1A7
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7

; =========================================================
; show a message if we touch the sprite
; should be used with Sprite_PlayerCantPassThrough
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowMessageOnContact = $05E1F0
Sprite_ShowMessageFromPlayerContact = $05E1F0

; Parameters: Stack, A
JumpTableLocal = $008781
UseImplicitRegIndexedLocalJumpTable = $008781

EnableForceBlank = $00893D

Snitch_SpawnGuard = $09C02F

Sprite_KillFriends = $09EF56

Sprite_KillSelf = $09F1F8

; =========================================================
; $04 = X
; $05 = HighX
; $06 = Y
; $07 = HighY
;   A = Speed
; \return $00 - Y Velocity
; \return $01 - X Velocity

Sprite_ProjectSpeedTowardsEntityLong = $06EA22

; =========================================================
; Guard and Prober functions

Guard_ChaseLinkOnOneAxis = $05C542
Guard_ParrySwordAttacks = $06EB5E
Probe_CheckTileSolidity = $0DC26E

Sprite_SpawnProbeAlways_long = $05C66E

Sprite_TrackBodyToHead = $05DCA2

; =========================================================
; Misc long functions

GetRandomInt = $0DBA71

Sprite_SpawnFireball = $0DDA06

Sprite_SpawnSmallSplash = $1EA820

Sprite_SpawnSparkleGarnish = $058008

Sprite_CheckIfLifted = $06AA0C

Sprite_TransmuteToBomb = $06AD50

Sprite_RepelDash = $079291

Sprite_SpawnPoofGarnish = $05AB9C

Sprite_LoadGfxProperties = $00FC41

ThrownSprite_TileAndSpriteInteraction_long = $06DFF2

; =========================================================
; Local functions which may be useful for sprites
; Sprite_AttemptZapDamage - 06EC02

; =========================================================
; Misc RAM

FrameCounter = $1A ; value that is increasing every frame
Indoor       = $1B ; 0: outside, 1: indoor
UpdPalFlag   = $15 ; Update all palettes $7EC500-$7EC700 if non-zero

RoomIndex    = $A0 ; Return the current room ID
AreaIndex    = $8A ; Return the current overworld area ID

MsgChoice    = $1CE8 ; Choice made in a message box

; set the mosaic setting ($2106) XXXXDCBA
;   [ABCD BG1/BG2/BG3/BG4][X size of the mosaic pixels 0-16]
Mosaic       = $95

DungeonMainCheck = $021B
SpriteRanCheck = $8E

; Underworld:
;    Flags sprite deaths in underworld based on slot.
;    Indexed by 2 * room ID.
; Overworld:
;    Holds ID+1 of sprite with each position being assigned a unique byte
;    0x00 indicates no sprite in this slot
UWDEATH         = $7FDF80

; =========================================================

RebuildHUD_long = $0DFA58

; =========================================================
; Controllers

; BYSTUDLR
;   [B BButton][Y YButton]
;   [SSelect Button][TStart Button]
;   [UDLR dpad buttons Up, Down, Left, Right]
RawJoypad1L  = $F0
; AXLRIIII
;   [A AButton][X Xbutton][L LButton][R RButton][I = controller ID]
RawJoypad1H  = $F2

; BYSTUDLR
;  [B BButton][Y YButton]
;  [SSelect Button][TStart Button]
;  [UDLR dpad buttons Up, Down, Left, Right]
PressPad1L   = $F4

; AXLRIIII
;  [A AButton][X Xbutton]
;  [L LButton][R RButton][I = controller ID]
PressPad1H   = $F6

ButtonAFlag  = $3B ; bit7: Button A is down (A-------)

; Timer for B button
; ssss tttt
;   s - spin attack in action; set to 0x9
;   t - sword swing timer
;       0x00 - No swing
;      —0x08 - Sword swing
;       0x09 - Sword primed
;      —0x0C - Poking wall
;
; Also used as a 16-bit countdown for various cutscenes:
;   Ether tablet:  0x00C0
;   Bombos tablet: 0x00E0
;   Desert tablet: 0x0001
BFLAG           = $3C

; =========================================================
; Link RAM and Functions

LinkY        = $20 ; Position Y of link
LinkYH       = $21 ; High position Y of link
LinkX        = $22 ; Position X of link
LinkXH       = $23 ; High position X of link
LinkZ        = $24 ; Position Z of link

; ----UDLR
;  [U Up][D Down][L Left][R Right]
;  Direction link is pushing against
LinkPushDir   = $26

; Link's recoiling speed
; By themselves, these do not do much
; They will be reset every frame Link is not in recoil state
LinkRecoilY   = $27
LinkRecoilX   = $28
LinkRecoilZ   = $29

; Link's subpixel velocity
; when this value overflows, Link's main velocity gains an extra pixel
; reset on direction change, so not really a positional subpixel
LinkSubVelY  = $2A
LinkSubVelX  = $2B

; Direction link is facing
; 00:Up, 02:Down, 04:Left, 06:Right
LinkFaceDir  = $2F

; Last direction link moved towards
; 00:Up, 01:Down, 02:Left, 03:Right
LinkLastDir  = $66

; ----UDLR
;  [U Up][D Down][L Left][R Right]
;  direction link is "walking towards"
LinkMoveDir  = $67

; 0: Not moving, 1: Moving cardinal, 2: Moving diagonally
LinkMoveInfo = $6A

LinkVisible  = $4B ; if set to 0x0C link will be invisible
LinkBunnyGfx = $56 ; if set to 1 link will be bunny, otherwise link

; 0x00: normal speed, 0x01-0x0F: slow,�> 0x10:fast
LinkSpeed    = $57

; 0x00: normal speed, 0x02: walking on stair speed, 0x10: dashing speed
LinkSpeedTbl = $5E

; if is set to 0x02 or 0x03 link is falling
LinkFalling  = $5B
FallTimer    = $5C

; LinkState_Default                  : 0x00
; LinkState_Pits                     : 0x01
; LinkState_Recoil                   : 0x02
; LinkState_SpinAttack               : 0x03
; LinkState_Swimming                 : 0x04 (ZoraDive)
; LinkState_OnIce                    : 0x05
; LinkState_Recoil                   : 0x06
; LinkState_Zapped                   : 0x07
; LinkState_UsingEther               : 0x08
; LinkState_UsingBombos              : 0x09
; LinkState_UsingQuake               : 0x0A (DekuHover)
; LinkState_HoppingSouthOW           : 0x0B
; LinkState_HoppingHorizontallyOW    : 0x0C
; LinkState_HoppingDiagonallyUpOW    : 0x0D
; LinkState_HoppingDiagonallyDownOW  : 0x0E
; LinkState_0F                       : 0x0F
; LinkState_0F                       : 0x10
; LinkState_Dashing                  : 0x11
; LinkState_ExitingDash              : 0x12
; LinkState_Hookshotting             : 0x13
; LinkState_CrossingWorlds           : 0x14
; LinkState_ShowingOffItem           : 0x15
; LinkState_Sleeping                 : 0x16
; LinkState_Bunny                    : 0x17
; LinkState_HoldingBigRock           : 0x18
; LinkState_ReceivingEther           : 0x19
; LinkState_ReceivingBombos          : 0x1A
; LinkState_ReadingDesertTablet      : 0x1B
; LinkState_TemporaryBunny           : 0x1C
; LinkState_TreePull                 : 0x1D
; LinkState_SpinAttack               : 0x1E
LinkState    = $5D

; 0: Link is not in a doorway
; 1: is in a vertical doorway
; 2: is in horizontal doorway
LinkDoorway  = $6C

; 0: Nothing
; 1: a hand in the air
; 2: 2 hands in the air (like getting triforce)
LinkGrabGfx  = $02DA

; if not 0 add a poof gfx on link
LinkPoofGfx  = $02E1

; Bunny timer for link before transforming back
LinkBunTimer = $02E2

; if not 0 prevent link from moving and opening the menu
LinkMenuMove = $02E4

; if not 0 prevent link from getting any damages from sprites
LinkDamage   = $037B

; ----CCCC
;  [C Touching chest id]
LinkColChest = $02E5

; 0: Not on somaria platform, 2: On somaria platform
LinkSomaria  = $02F5

; BP-AETHR
;   [B Boomerang][P Powder]
;   [A Bow&Arrows][E UnusedItem]
;   [T UnusedItem][H Hammer][R Rods]
LinkItemUse  = $0301

LinkItemY    = $0303 ; Currently equipped item on the Y button

; 0: Nothing, 1:Picking up something, 2: Throwing something
LinkCarrying = $0308

; .... ..tl
;   t - tossing object
;   l - lifting object
LinkCarryOrToss = $0309

; 0: Normal
; 1: Shovel
; 2: Praying
; 4: Hookshot
; 8: Somaria
; 10: Bug net
; 20: Read book
; 40: Tree pull
LinkAnim     = $037A

LinkWallCheat = $037F ; If non zero can walk through walls

; Animation step/graphics for spin attack animations; including medallions.
LinkSpinGfx   = $031C
LinkSpinStep  = $031D

; =========================================================

Link_ReceiveItem = $0799AD ; Y = item id

Link_CancelDash = $0791B9

Link_Initialize = $07F13C
Link_ResetProperties_A = $07F1A3
Link_ResetProperties_B = $07F1E6
Link_ResetProperties_C = $07F1FA
Link_ResetSwimmingState = $07983A
Link_ResetStateAfterDamagingPit = $07984B
Link_ItemReset_FromOverworldThings = $07B107

Link_CalculateSFXPan = $0DBB67

; Used by Agahnim2 fight
CallForDuckIndoors = $07A45F

ApplyLinksMovementToCamera = $07E9D3

HandleIndoorCameraAndDoors = $07F42F

Link_HandleVelocityAndSandDrag = $07E3DD

Link_HandleMovingAnimation_FullLongEntry = $07E6A6
Link_HandleMovingAnimation_General = $07E765
Link_HandleMovingAnimationSwimming = $07E7FA

LinkHop_FindArbitraryLandingSpot = $07E370

HandleFollowersAfterMirroring = $07AAA2

TileDetect_BigArea_long = $07CF0A

Hookshot_CheckTileCollision = $07D576

Refund_Magic = $07B0E9

CheckIfLinkIsBusy = $07F4D0

Follower_Initialize = $099EFC

; =========================================================
; Ancilla

AnciOAMPrior = $0280 ; Ancilla oam priority if non zero use highest priority for draw
AnciColTimer = $028A ; Ancilla collision timer to prevent doing collision code too often set to 06 after a collision
AnciZSpeed   = $0294 ; Ancilla Z Speed
AnciHeight   = $029E ; Ancilla Height how far it is from its shadow
AnciHeightH  = $02A8 ; Ancilla Height hight byte how far it is from its shadow

AnciMiscA    = $0BF0 ; This can be used to do anything in ancilla
AnciMiscB    = $0C54 ; This can be used to do anything in ancilla
AnciMiscC    = $0C5E ; This can be used to do anything in ancilla (often used to track item received)
AnciMiscD    = $0C72 ; This can be used to do anything in ancilla (often used to track direction)

; General use variable for ancillae. Only intended for front slots.
; LENGTH: 0x05
AnciMiscJ    = $03CA

; General use variable for ancillae.
; LENGTH: 0x0A
ANC0MISCB    = $0385

AnciTimerA   = $0C68 ; This is a timer, value is decreased by 1 every frame

AnciY        = $0BFA ; Position Y of the ancilla (Up to Down)
AnciX        = $0C04 ; Position X of the ancilla (Left to Right)
AnciYH       = $0C0E ; High (often determine the room) Position Y of the ancilla (Up to Down)
AnciXH       = $0C18 ; High (often determine the room) Position X of the ancilla (Left to Right)
AnciXSpeed   = $0C22 ; Y Speed of the ancilla can go negative to go up
AnciYSpeed   = $0C2C ; X Speed of the ancilla can go negative to go left
AnciLayer    = $0C7C ; return the floor where the ancilla is
AnciOamBuf   = $0C86 ; Oam buffer?
AnciOAMNbr   = $0C90 ; Number of OAM slots used

AnciYsub     = $0C36 ; sub pixel for Y position for ancilla
AnciXsub     = $0C40 ; sub pixel for X position for ancilla

; Ancilla IDs
; db $00 ; 0x00 - NOTHING
; db $08 ; 0x01 - SOMARIA BULLET
; db $0C ; 0x02 - FIRE ROD SHOT
; db $10 ; 0x03 - UNUSED
; db $10 ; 0x04 - BEAM HIT
; db $04 ; 0x05 - BOOMERANG
; db $10 ; 0x06 - WALL HIT
; db $18 ; 0x07 - BOMB
; db $08 ; 0x08 - DOOR DEBRIS
; db $08 ; 0x09 - ARROW
; db $08 ; 0x0A - ARROW IN THE WALL
; db $00 ; 0x0B - ICE ROD SHOT
; db $14 ; 0x0C - SWORD BEAM_BOUNCE
; db $00 ; 0x0D - SPIN ATTACK FULL CHARGE SPARK
; db $10 ; 0x0E - BLAST WALL EXPLOSION
; db $28 ; 0x0F - BLAST WALL EXPLOSION
; db $18 ; 0x10 - BLAST WALL EXPLOSION
; db $10 ; 0x11 - ICE ROD WALL HIT
; db $10 ; 0x12 - BLAST WALL EXPLOSION
; db $10 ; 0x13 - ICE ROD SPARKLE
; db $10 ; 0x14 - BAD POINTER
; db $0C ; 0x15 - SPLASH
; db $08 ; 0x16 - HIT STARS
; db $08 ; 0x17 - SHOVEL DIRT
; db $50 ; 0x18 - ETHER SPELL
; db $00 ; 0x19 - BOMBOS SPELL
; db $10 ; 0x1A - POWDER DUST
; db $08 ; 0x1B - SWORD WALL HIT
; db $40 ; 0x1C - QUAKE SPELL
; db $00 ; 0x1D - SCREEN SHAKE
; db $0C ; 0x1E - DASH DUST
; db $24 ; 0x1F - HOOKSHOT
; db $10 ; 0x20 - BLANKET
; db $0C ; 0x21 - SNORE
; db $08 ; 0x22 - ITEM GET
; db $10 ; 0x23 - LINK POOF
; db $10 ; 0x24 - GRAVESTONE
; db $04 ; 0x25 - BAD POINTER
; db $0C ; 0x26 - SWORD SWING SPARKLE
; db $1C ; 0x27 - DUCK
; db $00 ; 0x28 - WISH POND ITEM
; db $10 ; 0x29 - MILESTONE ITEM GET
; db $14 ; 0x2A - SPIN ATTACK SPARKLE A
; db $14 ; 0x2B - SPIN ATTACK SPARKLE B
; db $10 ; 0x2C - SOMARIA BLOCK
; db $08 ; 0x2D - SOMARIA BLOCK FIZZ
; db $20 ; 0x2E - SOMARIA BLOCK FISSION
; db $10 ; 0x2F - LAMP FLAME
; db $10 ; 0x30 - BYRNA WINDUP SPARK
; db $10 ; 0x31 - BYRNA SPARK
; db $04 ; 0x32 - BLAST WALL FIREBALL
; db $00 ; 0x33 - BLAST WALL EXPLOSION
; db $80 ; 0x34 - SKULL WOODS FIRE
; db $10 ; 0x35 - MASTER SWORD GET
; db $04 ; 0x36 - FLUTE
; db $30 ; 0x37 - WEATHERVANE EXPLOSION
; db $14 ; 0x38 - CUTSCENE DUCK
; db $10 ; 0x39 - SOMARIA PLATFORM POOF
; db $00 ; 0x3A - BIG BOMB EXPLOSION
; db $10 ; 0x3B - SWORD UP SPARKLE
; db $00 ; 0x3C - SPIN ATTACK CHARGE SPARKLE
; db $00 ; 0x3D - ITEM SPLASH
; db $08 ; 0x3E - RISING CRYSTAL
; db $00 ; 0x3F - BUSH POOF
; db $10 ; 0x40 - DWARF POOF
; db $08 ; 0x41 - WATERFALL SPLASH
; db $78 ; 0x42 - HAPPINESS POND RUPEES
; db $80 ; 0x43 - GANONS TOWER CUTSCENE
AnciType     = $0C4A

AncillaInit_SetCoordsAndExit = $0980C3
Ancilla_PrepOAMCoord_long = $08F6D9
Ancilla_SetOAM_XY_long = $08F6FE
Ancilla_GetRadialProjection_long = $08FB23

Ancilla_CheckForAvailableSlot = $0FF577
Ancilla_CheckInitialTile_A = $099DD3

Ancilla_CheckSpriteCollision_long = $088DA2

Ancilla_CheckTileCollision_long = $08923B
Ancilla_CheckTileCollision_Class2_long = $089243

Ancilla_CalculateSFXPan = $0DBB5E

Ancilla_CheckDamageToSprite = $06ECB7

; Table of ancilla properties
AncillaObjectAllocation = $08806F

AncillaAdd_BombosSpell = $08AF66
AncillaAdd_FireRodShot = $0880B3
AncillaAdd_Snoring = $0980C8
AncillaAdd_Bomb = $09811F
AncillaAdd_Boomerang = $09820F
AncillaAdd_BoomerangAsClink = $098345
AncillaAdd_DugUpFlute = $098C73
AncillaAdd_ChargedSpinAttackSparkle = $098CB1
AncillaAdd_ExplodingWeatherVane = $098D11
AncillaAdd_CutsceneDuck = $098D90
AncillaAdd_SomariaPlatformPoof = $098DD2
AncillaAdd_SuperBombExplosion = $098DF9

ConfigureRevivalAncillae = $098E4E

AncillaAdd_CaneOfByrnaInitSpark = $098EE0
AncillaAdd_LampFlame = $098F1C
AncillaAdd_ShovelDirt = $098F5B
AncillaAdd_BlastWallFireball = $099031
AncillaAdd_Arrow = $0990A4
AncillaAdd_CapePoof = $09912C
AncillaAdd_BushPoof = $0991C3
AncillaAdd_EtherSpell = $0991FC
AncillaAdd_VictorySpin = $0992AC
AncillaAdd_MagicPowder = $0992F0
AncillaAdd_WallTapSpark = $099395
AncillaAdd_SwordSwingSparkle = $0993C2
AncillaAdd_QuakeSpell = $099589
AncillaAdd_IceRodShot = $099863
AncillaAdd_Splash = $0998FC
AncillaAdd_Hookshot = $099B10
AncillaAdd_Blanket = $098091

AddHappinessPondRupees = $098AE0

DeleteBoomAndByrnaSparks = $0FFD86

Sparkle_PrepOAMFromRadial = $08DA17

Fireball_SpawnTrailGarnish = $09B020

SpriteSFX_QueueSFX2WithPan = $0DBB7C
