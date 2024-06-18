
; Ancilla IDs
db $00 ; 0x00 - NOTHING
db $08 ; 0x01 - SOMARIA BULLET
db $0C ; 0x02 - FIRE ROD SHOT
db $10 ; 0x03 - UNUSED
db $10 ; 0x04 - BEAM HIT
db $04 ; 0x05 - BOOMERANG
db $10 ; 0x06 - WALL HIT
db $18 ; 0x07 - BOMB
db $08 ; 0x08 - DOOR DEBRIS
db $08 ; 0x09 - ARROW
db $08 ; 0x0A - ARROW IN THE WALL
db $00 ; 0x0B - ICE ROD SHOT
db $14 ; 0x0C - SWORD BEAM_BOUNCE
db $00 ; 0x0D - SPIN ATTACK FULL CHARGE SPARK
db $10 ; 0x0E - BLAST WALL EXPLOSION
db $28 ; 0x0F - BLAST WALL EXPLOSION
db $18 ; 0x10 - BLAST WALL EXPLOSION
db $10 ; 0x11 - ICE ROD WALL HIT
db $10 ; 0x12 - BLAST WALL EXPLOSION
db $10 ; 0x13 - ICE ROD SPARKLE
db $10 ; 0x14 - BAD POINTER
db $0C ; 0x15 - SPLASH
db $08 ; 0x16 - HIT STARS
db $08 ; 0x17 - SHOVEL DIRT
db $50 ; 0x18 - ETHER SPELL
db $00 ; 0x19 - BOMBOS SPELL
db $10 ; 0x1A - POWDER DUST
db $08 ; 0x1B - SWORD WALL HIT
db $40 ; 0x1C - QUAKE SPELL
db $00 ; 0x1D - SCREEN SHAKE
db $0C ; 0x1E - DASH DUST
db $24 ; 0x1F - HOOKSHOT
db $10 ; 0x20 - BLANKET
db $0C ; 0x21 - SNORE
db $08 ; 0x22 - ITEM GET
db $10 ; 0x23 - LINK POOF
db $10 ; 0x24 - GRAVESTONE
db $04 ; 0x25 - BAD POINTER
db $0C ; 0x26 - SWORD SWING SPARKLE
db $1C ; 0x27 - DUCK
db $00 ; 0x28 - WISH POND ITEM
db $10 ; 0x29 - MILESTONE ITEM GET
db $14 ; 0x2A - SPIN ATTACK SPARKLE A
db $14 ; 0x2B - SPIN ATTACK SPARKLE B
db $10 ; 0x2C - SOMARIA BLOCK
db $08 ; 0x2D - SOMARIA BLOCK FIZZ
db $20 ; 0x2E - SOMARIA BLOCK FISSION
db $10 ; 0x2F - LAMP FLAME
db $10 ; 0x30 - BYRNA WINDUP SPARK
db $10 ; 0x31 - BYRNA SPARK
db $04 ; 0x32 - BLAST WALL FIREBALL
db $00 ; 0x33 - BLAST WALL EXPLOSION
db $80 ; 0x34 - SKULL WOODS FIRE
db $10 ; 0x35 - MASTER SWORD GET
db $04 ; 0x36 - FLUTE
db $30 ; 0x37 - WEATHERVANE EXPLOSION
db $14 ; 0x38 - CUTSCENE DUCK
db $10 ; 0x39 - SOMARIA PLATFORM POOF
db $00 ; 0x3A - BIG BOMB EXPLOSION
db $10 ; 0x3B - SWORD UP SPARKLE
db $00 ; 0x3C - SPIN ATTACK CHARGE SPARKLE
db $00 ; 0x3D - ITEM SPLASH
db $08 ; 0x3E - RISING CRYSTAL
db $00 ; 0x3F - BUSH POOF
db $10 ; 0x40 - DWARF POOF
db $08 ; 0x41 - WATERFALL SPLASH
db $78 ; 0x42 - HAPPINESS POND RUPEES
db $80 ; 0x43 - GANONS TOWER CUTSCENE


; Garnish IDs
dw Garnish01_FireSnakeTail
dw Garnish02_MothulaBeamTrail
dw Garnish03_FallingTile
dw Garnish04_LaserTrail
dw Garnish05_SimpleSparkle
dw Garnish06_ZoroTrail
dw Garnish07_BabasuFlash
dw Garnish08_KholdstareTrail
dw Garnish09_LightningTrail
dw Garnish0A_CannonSmoke
dw Garnish0B_WaterTrail
dw Garnish0C_TrinexxIceBreath
dw $0000
dw Garnish0E_TrinexxFireBreath
dw Garnish0F_BlindLaserTrail
dw Garnish10_GanonBatFlame
dw Garnish11_WitheringGanonBatFlame
dw Garnish12_Sparkle
dw Garnish13_PyramidDebris
dw Garnish14_KakKidDashDust
dw Garnish15_ArrghusSplash
dw Garnish16_ThrownItemDebris


; Liftable object palettes
; Sprites Aux 2 #8 for DW
; Sprites Aux 2 #6 for LW
; #7 and #9 are the yellow bush palettes

LDA.l UnderworldPaletteSets+0,X
STA.w $0AB6 ; PALBG

LDA.l UnderworldPaletteSets+1,X
STA.w $0AAC ; PALSPR0

LDA.l UnderworldPaletteSets+2,X
STA.w $0AAD ; PALSPR1

LDA.l UnderworldPaletteSets+3,X
STA.w $0AAE ; PALSPR2

; PALBG
; 0x00 - Kalyxo Castle
; 0x01 - Blue 
; 0x02 - House
; 0x03 - Green 
; 0x04 - Glacia Estate Ice
; 0x05 - Zora Temple
; 0x06 - Tail Palace Pink
; 0x07 - Goron Mines Cave Red
; 0x08 - Mushroom Grotto Gray
; 0x09 
; 0x0A (10) - Ranch Pink
; 0x0B (11) - Another green
; 0x0C - Goron Mines Cave Red
; 0x0D
; 0x0E
; 0x0F
; 0x10 - 
; 0x (19) - 

UnderworldPaletteSets:
db $00, $00, $03, $01 ; 0x00
db $02, $00, $03, $01 ; 0x01
db $04, $00, $0A, $01 ; 0x02 House
db $06, $00, $01, $07 ; 0x03 Fortress of Secrets
db $0A, $02, $02, $07 ; 0x04 Zora Temple
db $04, $04, $03, $0A ; 0x05 House
db $0C, $05, $08, $14 ; 0x06 Tail Palace
db $0E, $00, $03, $0A ; 0x07 Goron Mines/Caves
db $02, $00, $0F, $14 ; 0x08 Castle Basement
db $0A, $02, $00, $07 ; 0x09 
db $02, $00, $0F, $0C ; 0x0A
db $06, $00, $06, $07 ; 0x0B
db $00, $00, $0E, $12 ; 0x0C Kalyxo Castle
db $12, $05, $05, $0B ; 0x0D
db $12, $00, $02, $0C ; 0x0E
db $10, $05, $0A, $07 ; 0x0F Mushroom Grotto
db $10, $00, $10, $0C ; 0x10 Ranch?
db $16, $07, $02, $07 ; 0x11 Hall of Secrets
db $16, $00, $07, $0F ; 0x12
db $08, $00, $04, $0C ; 0x13 Glacia Estate
db $08, $00, $04, $09 ; 0x14
db $04, $00, $03, $01 ; 0x15 House
db $14, $00, $04, $04 ; 0x16
db $14, $00, $14, $0C ; 0x17 
db $18, $05, $07, $0B ; 0x18 Lava Lands Cave/Turtle Rock
db $18, $06, $10, $0C ; 0x19
db $1A, $05, $08, $14 ; 0x1A Dragon Ship
db $1A, $02, $00, $07 ; 0x1B Dragon Ship
db $06, $00, $03, $0A ; 0x1C
db $1C, $00, $03, $01 ; 0x1D
db $1E, $00, $0B, $11 ; 0x1E Swordsmith
db $04, $00, $0B, $11 ; 0x1F
db $0E, $00, $00, $02 ; 0x20 
db $20, $08, $13, $0D ; 0x21 Ganondorf Boss
db $0A, $00, $03, $0A ; 0x22 Zora Temple
db $14, $00, $04, $04 ; 0x23
db $1A, $02, $02, $07 ; 0x24 Dragon Ship
db $1A, $0A, $00, $00 ; 0x25 Dragon Ship
db $00, $00, $03, $02 ; 0x26
db $0E, $00, $03, $07 ; 0x27
db $1A, $05, $05, $0B ; 0x28 Dragon Ship


OverworldPaletteSet:
db $00, $FF, $07, $FF ; 0x00
db $00, $01, $07, $FF ; 0x01
db $00, $02, $07, $FF ; 0x02
db $00, $03, $07, $FF ; 0x03
db $00, $04, $07, $FF ; 0x04
db $00, $05, $07, $FF ; 0x05
db $00, $06, $07, $FF ; 0x06
db $07, $06, $05, $FF ; 0x07
db $00, $08, $07, $FF ; 0x08
db $00, $09, $07, $FF ; 0x09
db $00, $0A, $07, $FF ; 0x0A
db $00, $0B, $07, $FF ; 0x0B
db $00, $FF, $07, $FF ; 0x0C
db $00, $FF, $07, $FF ; 0x0D
db $03, $04, $07, $FF ; 0x0E
db $04, $04, $03, $FF ; 0x0F
db $10, $FF, $06, $FF ; 0x10
db $10, $01, $06, $FF ; 0x11
db $10, $11, $06, $FF ; 0x12
db $10, $03, $06, $FF ; 0x13
db $10, $04, $06, $FF ; 0x14
db $10, $05, $06, $FF ; 0x15
db $10, $06, $06, $FF ; 0x16
db $12, $13, $04, $FF ; 0x17
db $12, $05, $04, $FF ; 0x18
db $10, $09, $06, $FF ; 0x19
db $10, $0B, $06, $FF ; 0x1A
db $10, $0C, $06, $FF ; 0x1B
db $10, $0D, $06, $FF ; 0x1C
db $10, $0E, $06, $FF ; 0x1D
db $10, $0F, $06, $FF ; 0x1E


Module09_Overworld
dw Module09_00_PlayerControl              ; 0x00
dw Module09_LoadAuxGFX                    ; 0x01
dw Module09_TriggerTilemapUpdate          ; 0x02
dw Module09_LoadNewMapAndGFX              ; 0x03
dw Module09_LoadNewSprites                ; 0x04
dw Overworld_StartScrollTransition        ; 0x05
dw Overworld_RunScrollTransition          ; 0x06
dw Overworld_EaseOffScrollTransition      ; 0x07
dw Overworld_FinalizeEntryOntoScreen      ; 0x08
dw Module09_09_OpenBigDoorFromExiting     ; 0x09
dw Module09_0A_WalkFromExiting_FacingDown ; 0x0A
dw Module09_0B_WalkFromExiting_FacingUp   ; 0x0B
dw Module09_0C_OpenBigDoor                ; 0x0C
dw Overworld_StartMosaicTransition        ; 0x0D
dw Overworld_LoadSubscreenAndSilenceSFX1  ; 0x0E
dw Module09_LoadAuxGFX                    ; 0x0F
dw Module09_TriggerTilemapUpdate          ; 0x10
dw Module09_LoadNewMapAndGFX              ; 0x11
dw Module09_LoadNewSprites                ; 0x12
dw Overworld_StartScrollTransition        ; 0x13
dw Overworld_RunScrollTransition          ; 0x14
dw Overworld_EaseOffScrollTransition      ; 0x15
dw Module09_FadeBackInFromMosaic          ; 0x16
dw Overworld_StartMosaicTransition        ; 0x17
dw Module09_18                            ; 0x18
dw Module09_19                            ; 0x19
dw Module09_LoadAuxGFX                    ; 0x1A
dw Module09_TriggerTilemapUpdate          ; 0x1B
dw Module09_1C                            ; 0x1C
dw Module09_1D                            ; 0x1D
dw Module09_1E                            ; 0x1E
dw Module09_1F                            ; 0x1F
dw Overworld_ReloadSubscreenOverlay       ; 0x20
dw Module09_21                            ; 0x21
dw Module09_22                            ; 0x22
dw Module09_MirrorWarp                    ; 0x23
dw Overworld_StartMosaicTransition        ; 0x24
dw Module09_25                            ; 0x25
dw Module09_LoadAuxGFX                    ; 0x26
dw Module09_TriggerTilemapUpdate          ; 0x27
dw Overworld_LoadAndBuildScreen           ; 0x28
dw Module09_FadeBackInFromMosaic          ; 0x29
dw Module09_2A_RecoverFromDrowning        ; 0x2A
dw Module09_2B                            ; 0x2B
dw Module09_MirrorWarp                    ; 0x2C
dw Module09_2D_WaitForBird                ; 0x2D
dw Module09_2E_Whirlpool                  ; 0x2E
dw Module09_2F   


Module07_Underworld
dw Module07_00_PlayerControl                    ; 0x00
dw Module07_01_IntraroomTransition              ; 0x01
dw Module07_02_InterroomTransition              ; 0x02
dw Module07_03_OverlayChange                    ; 0x03
dw Module07_04_UnlockDoor                       ; 0x04
dw Module07_05_ControlShutters                  ; 0x05
dw Module07_06_FatInterRoomStairs               ; 0x06
dw Module07_07_FallingTransition                ; 0x07
dw Module07_08_NorthIntraRoomStairs             ; 0x08
dw Module07_09_OpenCrackedDoor                  ; 0x09
dw Module07_0A_ChangeBrightness                 ; 0x0A
dw Module07_0B_DrainSwampPool                   ; 0x0B
dw Module07_0C_FloodSwampWater                  ; 0x0C
dw Module07_0D_FloodDam                         ; 0x0D
dw Module07_0E_SpiralStairs                     ; 0x0E
dw Module07_0F_LandingWipe                      ; 0x0F
dw Module07_10_SouthIntraRoomStairs             ; 0x10
dw Module07_11_StraightInterroomStairs          ; 0x11
dw Module07_11_StraightInterroomStairs          ; 0x12
dw Module07_11_StraightInterroomStairs          ; 0x13
dw Module07_14_RecoverFromFall                  ; 0x14
dw Module07_15_WarpPad                          ; 0x15
dw Module07_16_UpdatePegs                       ; 0x16
dw Module07_17_PressurePlate                    ; 0x17
dw Module07_18_RescuedMaiden                    ; 0x18
dw Module07_19_MirrorFade                       ; 0x19
dw Module07_1A_RoomDraw_OpenTriforceDoor_bounce ; 0x1A


Link_ControlHandler

  dw LinkState_Default                  ; 0x00
  dw LinkState_Pits                     ; 0x01
  dw LinkState_Recoil                   ; 0x02
  dw LinkState_SpinAttack               ; 0x03
  dw LinkState_Swimming                 ; 0x04
  dw LinkState_OnIce                    ; 0x05
  dw LinkState_Recoil                   ; 0x06
  dw LinkState_Zapped                   ; 0x07
  dw LinkState_UsingEther               ; 0x08
  dw LinkState_UsingBombos              ; 0x09
  dw LinkState_UsingQuake               ; 0x0A
  dw LinkState_HoppingSouthOW           ; 0x0B
  dw LinkState_HoppingHorizontallyOW    ; 0x0C
  dw LinkState_HoppingDiagonallyUpOW    ; 0x0D
  dw LinkState_HoppingDiagonallyDownOW  ; 0x0E
  dw LinkState_0F                       ; 0x0F
  dw LinkState_0F                       ; 0x10
  dw LinkState_Dashing                  ; 0x11
  dw LinkState_ExitingDash              ; 0x12
  dw LinkState_Hookshotting             ; 0x13
  dw LinkState_CrossingWorlds           ; 0x14
  dw LinkState_ShowingOffItem           ; 0x15
  dw LinkState_Sleeping                 ; 0x16
  dw LinkState_Bunny                    ; 0x17
  dw LinkState_HoldingBigRock           ; 0x18
  dw LinkState_ReceivingEther           ; 0x19
  dw LinkState_ReceivingBombos          ; 0x1A
  dw LinkState_ReadingDesertTablet      ; 0x1B
  dw LinkState_TemporaryBunny           ; 0x1C
  dw LinkState_TreePull                 ; 0x1D
  dw LinkState_SpinAttack               ; 0x1E

Link_HandleYItem

  dw LinkItem_Bombs
  dw LinkItem_Boomerang
  dw LinkItem_Bow
  dw LinkItem_Hammer

  dw LinkItem_Rod
  dw LinkItem_Rod
  dw LinkItem_Net
  dw LinkItem_ShovelAndFlute

  dw LinkItem_Lamp
  dw LinkItem_Powder
  dw LinkItem_Bottle
  dw LinkItem_Book

  dw LinkItem_CaneOfByrna
  dw LinkItem_Hookshot
  dw LinkItem_Bombos
  dw LinkItem_Ether

  dw LinkItem_Quake
  dw LinkItem_CaneOfSomaria
  dw LinkItem_Cape
  dw LinkItem_Mirror