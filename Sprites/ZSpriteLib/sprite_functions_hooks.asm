SprAction    = $0D80
SprFrame     = $0D90 ; This is also used to do various things in different sprites
SprMiscA     = $0DA0 ; This can be used to do anything in sprite
SprMiscB     = $0DB0 ; This can be used to do anything in sprite
SprMiscC     = $0DE0 ; This can be used to do anything in sprite (Mainly used for sprite direction)
SprMiscD     = $0E90 ; This can be used to do anything in sprite
SprMiscE     = $0EB0 ; This can be used to do anything in sprite
SprMiscF     = $0EC0 ; This can be used to do anything in sprite
SprMiscG     = $0ED0 ; This can be used to do anything in sprite

SprStunTimer = $0B58

SprTimerA    = $0DF0 ; This address value is decreased by one every frames
SprTimerB    = $0E00 ; This address value is decreased by one every frames
SprTimerC    = $0E10 ; This address value is decreased by one every frames
SprTimerD    = $0EE0 ; This address value is decreased by one every frames
SprTimerE    = $0F10 ; This address value is decreased by one every frames
SprTimerF    = $0F80 ; This address value is decreased by 2 every frames is also used by the gravity routine

SprPause     = $0F00 ; Can probably be used for anything 
SprFloor     = $0F20
SprType      = $0E20 ; This contains the ID of the sprite 00 = raven, 01 = vulture, etc...
SprSubtype   = $0E30 ; This contains the Sub ID of the sprite
SprState     = $0DD0 ; This tells if the sprite is alive, dead, frozen, etc...

SprNbrOAM    = $0E40 ; Bits 0-4: define the number of OAM slots used by the sprite
SprHealth    = $0E50
SprGfxProps  = $0E60
SprCollision = $0E70 ; When a sprite hit a wall, this gets set to the direction in which the collision occurred.
SprDelay     = $0E80 ; Used in sprite state 0x03 (falling in water), used as delay in most of the sprites
SprRecoil    = $0EA0 ; Recoil Timer
SprDeath     = $0EF0

SprProps     = $0F50 ; DIWS UUUU - [D boss death][I Impervious to all attacks][W Water slash] [S Draw Shadow] [U Unused]
SprHitbox    = $0F60 ; ISPH HHHH - [I ignore collisions][S Statis (not alive eg beamos)][P Persist code still run outside of camera][H Hitbox] 
SprHeight    = $0F70 ; Distance from the shadow
SprHeightS   = $0F90 ; Distance from the shadow subpixel

SprYRecoil   = $0F30
SprXRecoil   = $0F40

SprGfx       = $0DC0 ; Determine the GFX used for the sprite
OAMPtr       = $90
OAMPtrH      = $92

SprY         = $0D00
SprX         = $0D10
SprYH        = $0D20
SprXH        = $0D30

SprYSpeed    = $0D40
SprXSpeed    = $0D50

SprYRound    = $0D60
SprXRound    = $0D70

SprCachedX   = $0FD8 ; This doesn't need to be indexed with X it contains the 16bit position of the sprite
SprCachedY   = $0FDA ; This doesn't need to be indexed with X it contains the 16bit position of the sprite



org $09AE64
Sprite_SetSpawnedCoords:

;=================================================================
;Sprite_PrepOamCoord LONG
;set the oam coordinate for the sprite draw
org $06E416
Sprite_PrepOamCoord:

;=================================================================
;Sprite_CheckDamageFromPlayer LONG
;check if the sprite is getting damage from player or items
org $06F2AA
Sprite_CheckDamageFromPlayer:

;=================================================================
;Sprite_CheckDamageToPlayer LONG
;check if the sprite is touching the player to damage
org $06F121
Sprite_CheckDamageToPlayer:

;=================================================================
;Sprite_AttemptDamageToPlayerPlusRecoil LONG
;damage the player everywhere on screen?
org $06F41F
Sprite_AttemptDamageToPlayerPlusRecoil:

;=================================================================
;Sprite_OAM_AllocateDeferToPlayer LONG
;Draw the sprite depending of the position of the player (if he has to be over or under link)
org $06F864
Sprite_OAM_AllocateDeferToPlayer:

org $0DBA80
OAM_AllocateFromRegionA:
org $0DBA84
OAM_AllocateFromRegionB:
org $0DBA88
OAM_AllocateFromRegionC:
org $0DBA8C
OAM_AllocateFromRegionD:
org $0DBA90
OAM_AllocateFromRegionE:
org $0DBA94
OAM_AllocateFromRegionF:

org $05DF70
Sprite_DrawMultiple_quantity_preset:
;=================================================================
;ApplyRumbleToSprites LONG
;makes all the sprites on screen shaking?
org $0680FA
ApplyRumbleToSprites:


;=================================================================
;CheckIfHitBoxesOverlap LONG
;args : 
;!pos1_low  = $00
;!pos1_size = $02
;!pos2_low  = $04
;!pos2_size = $06
;!pos1_high = $08
;!pos2_high = $0A
;!ans_low   = $0F
;!ans_high  = $0C
;returns carry clear if there was no overlap
org $0683E6
CheckIfHitBoxesOverlap:

;=================================================================
;Sprite_Get_16_bit_Coords LONG
;$0FD8 = sprite's X coordinate, $0FDA = sprite's Y coordinate
org $0684BD
Sprite_Get_16_bit_Coords:

;=================================================================
;Sprite_PrepAndDrawSingleLarge LONG
;load / draw a  16x16 sprite
org $06DBF0
Sprite_PrepAndDrawSingleLarge:

;=================================================================
;Sprite_PrepAndDrawSingleSmall LONG
;load / draw a  8x8 sprite
org $06DBF8
Sprite_PrepAndDrawSingleSmall:

;=================================================================
;Sprite_DrawShadow LONG
;draw shadow 
org $06DC54
Sprite_DrawShadow:

;=================================================================
;Sprite_CheckTileCollision LONG
;check if the sprite is colliding with a solid tile set $0E70, X
;----udlr , u = up, d = down, l = left, r = right
org $06E496
Sprite_CheckTileCollision:

;=================================================================
;Sprite_GetTileAttr LONG
; $00[0x02] - Entity Y coordinate
; $02[0x03?] - Entity X coordinate
;$0FA5
org $06E87B
Sprite_GetTileAttr:

;=================================================================
;Sprite_CheckSlopedTileCollision LONG
;check if the sprite is colliding with a solid sloped tile
org $06E8FD
Sprite_CheckSlopedTileCollision:

;=================================================================
;Sprite_ApplySpeedTowardsPlayer LONG
;set the velocity x,y towards the player (A = speed)
org $06EA12
Sprite_ApplySpeedTowardsPlayer:

;=================================================================
;Sprite_DirectionToFacePlayer LONG
; \return       $0E is low byte of player_y_pos - sprite_y_pos
; \return       $0F is low byte of player_x_pos - sprite_x_pos
org $06EAA0
Sprite_DirectionToFacePlayer:

;=================================================================
;Sprite_IsToRightOfPlayer LONG
;if Link is to the left of the sprite, Y = 1, otherwise Y = 0.
org $06EACD
Sprite_IsToRightOfPlayer:

;=================================================================
;Sprite_IsBelowPlayer LONG
;return Y=1 sprite is below player, otherwise Y = 0
org $06EAE4
Sprite_IsBelowPlayer:

;=================================================================
;Sprite_CheckDamageToPlayerSameLayer LONG
;check damage done to player if they collide and if they are on same layer
org $06F129
Sprite_CheckDamageToPlayerSameLayer:

;=================================================================
;Sprite_CheckDamageToPlayerIgnoreLayer LONG
;check damage done to player if they collide even if they are not on same layer
org $06F131
Sprite_CheckDamageToPlayerIgnoreLayer:

;=================================================================
;Sound_SetSfx2PanLong LONG
;play a sound loaded in A
org $0DBB6E
Sound_SetSfx1PanLong:

org $0DBB7C
Sound_SetSfx2PanLong:

org $0DBB8A
Sound_SetSfx3PanLong:

;=================================================================
;Sprite_SpawnDynamically LONG
;spawn a new sprite on screen, A = sprite id
;when using this function you have to set the position yourself
;these values belong to the sprite who used that function not the new one 
;$00 low x, $01 high x
;$02 low y, $03 high y
;$04 height, $05 low x (overlord)
;$06 high x (overlord), $07 low y (overlord)
;$08 high y (overlord)
org $1DF65D
Sprite_SpawnDynamically:

org $07F1A3
Player_ResetState:
;=================================================================
;Sprite_ApplyConveyorAdjustment LONG
;move the sprite if he stand on a conveyor belt
org $1D8010
Sprite_ApplyConveyorAdjustment:

;=================================================================
;SetupHitBox LONG
;set the hitbox of the player (i think)
;org $0683EA
;Sprite_SetupHitBoxLong:

;=================================================================
;Dungeon_SpriteInducedTilemapUpdate LONG
;set tile of dungeon
org $01E7A9
Dungeon_SpriteInducedTilemapUpdate:
;=================================================================
;Get random INT LONG
;GetRandomInt
org $0DBA71
GetRandomInt:

;=================================================================
;Sprite_PlayerCantPassThrough
;player can't pass through the sprite
org $1EF4F3
Sprite_PlayerCantPassThrough:

;=================================================================
;Sprite_NullifyHookshotDrag
;player can't hookshot to that sprite
org $0FF540
Sprite_NullifyHookshotDrag:

;=================================================================
;Player_HaltDashAttack
;stop the dash attack of the player
org $0791B9
Player_HaltDashAttack:

;=================================================================
;Sprite_ShowMessageUnconditional
;show a message box without any condition
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
org $05E219
Sprite_ShowMessageUnconditional:

;=================================================================
;Link_ReceiveItem
;Y = item id
org $0799AD
Link_ReceiveItem:

;=================================================================
;Sprite_ShowSolicitedMessageIfPlayerFacing
;show a message if we press A and face the sprite
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
org $05E1A7
Sprite_ShowSolicitedMessageIfPlayerFacing:

;=================================================================
;Sprite_ShowMessageFromPlayerContact
;show a message if we touch the sprite should be used with Sprite_PlayerCantPassThrough
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
org $05E1F0
Sprite_ShowMessageFromPlayerContact:

; Parameters: Stack, A
org $008781
UseImplicitRegIndexedLocalJumpTable:

org $00893D
EnableForceBlank:


;=================================================================
;Sprite_ProjectSpeedTowardsEntityLong
;04 = X
;05 = HighX
;06 = Y
;07 = HighY
;A = Speed

;Return $00 - Y Velocity
;Return $01 - X Velocity

org $06EA22
Sprite_ProjectSpeedTowardsEntityLong:

org $0DDA06
Sprite_SpawnFireball:

org $1D808C
Sprite_MoveLong:

org $1EFF8D
Sprite_DrawRippleIfInWater:

org $058008
Sprite_SpawnSparkleGarnish:


org $06EA1A
Sprite_ProjectSpeedTowardsPlayer:

org $06F2AA
Sprite_CheckDamageFromPlayerLong: