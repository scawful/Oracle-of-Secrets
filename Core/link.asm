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

CheckIfLinkIsBusy = $07F4D0
Refund_Magic = $07B0E9

Hookshot_CheckTileCollision = $07D576
