; Main Modules
  Module00_Intro
  Module01_FileSelect
  Module02_CopyFile
  Module03_KILLFile
  Module04_NameFile
  Module05_LoadFile
  Module06_UnderworldLoad
  Module07_Underworld
  Module08_OverworldLoad
  Module09_Overworld
  Module0A_OverworldSpecialLoad
  Module0B_OverworldSpecial
  Module0C_Unused
  Module0D_Unused
  Module0E_Interface
  Module0F_SpotlightClose
  Module10_SpotlightOpen
  Module11_UnderworldFallingEntrance
  Module12_GameOver
  Module13_BossVictory_Pendant
  Module14_Attract
  Module15_MirrorWarpFromAga
  Module16_BossVictory_Crystal
  Module17_SaveAndQuit
  Module18_GanonEmerges
  Module19_TriforceRoom
  Module1A_Credits
  Module1B_SpawnSelect

; Garnish IDs
  Garnish01_FireSnakeTail
  Garnish02_MothulaBeamTrail
  Garnish03_FallingTile
  Garnish04_LaserTrail
  Garnish05_SimpleSparkle
  Garnish06_ZoroTrail
  Garnish07_BabasuFlash
  Garnish08_KholdstareTrail
  Garnish09_LightningTrail
  Garnish0A_CannonSmoke
  Garnish0B_WaterTrail
  Garnish0C_TrinexxIceBreath
  $0000
  Garnish0E_TrinexxFireBreath
  Garnish0F_BlindLaserTrail
  Garnish10_GanonBatFlame
  Garnish11_WitheringGanonBatFlame
  Garnish12_Sparkle
  Garnish13_PyramidDebris
  Garnish14_KakKidDashDust
  Garnish15_ArrghusSplash
  Garnish16_ThrownItemDebris


Module09_Overworld:
  Module09_00_PlayerControl              ; 0x00
  Module09_LoadAuxGFX                    ; 0x01
  Module09_TriggerTilemapUpdate          ; 0x02
  Module09_LoadNewMapAndGFX              ; 0x03
  Module09_LoadNewSprites                ; 0x04
  Overworld_StartScrollTransition        ; 0x05
  Overworld_RunScrollTransition          ; 0x06
  Overworld_EaseOffScrollTransition      ; 0x07
  Overworld_FinalizeEntryOntoScreen      ; 0x08
  Module09_09_OpenBigDoorFromExiting     ; 0x09
  Module09_0A_WalkFromExiting_FacingDown ; 0x0A
  Module09_0B_WalkFromExiting_FacingUp   ; 0x0B
  Module09_0C_OpenBigDoor                ; 0x0C
  Overworld_StartMosaicTransition        ; 0x0D
  Overworld_LoadSubscreenAndSilenceSFX1  ; 0x0E
  Module09_LoadAuxGFX                    ; 0x0F
  Module09_TriggerTilemapUpdate          ; 0x10
  Module09_LoadNewMapAndGFX              ; 0x11
  Module09_LoadNewSprites                ; 0x12
  Overworld_StartScrollTransition        ; 0x13
  Overworld_RunScrollTransition          ; 0x14
  Overworld_EaseOffScrollTransition      ; 0x15
  Module09_FadeBackInFromMosaic          ; 0x16
  Overworld_StartMosaicTransition        ; 0x17
  Module09_18                            ; 0x18
  Module09_19                            ; 0x19
  Module09_LoadAuxGFX                    ; 0x1A
  Module09_TriggerTilemapUpdate          ; 0x1B
  Module09_1C                            ; 0x1C
  Module09_1D                            ; 0x1D
  Module09_1E                            ; 0x1E
  Module09_1F                            ; 0x1F
  Overworld_ReloadSubscreenOverlay       ; 0x20
  Module09_21                            ; 0x21
  Module09_22                            ; 0x22
  Module09_MirrorWarp                    ; 0x23
  Overworld_StartMosaicTransition        ; 0x24
  Module09_25                            ; 0x25
  Module09_LoadAuxGFX                    ; 0x26
  Module09_TriggerTilemapUpdate          ; 0x27
  Overworld_LoadAndBuildScreen           ; 0x28
  Module09_FadeBackInFromMosaic          ; 0x29
  Module09_2A_RecoverFromDrowning        ; 0x2A
  Module09_2B                            ; 0x2B
  Module09_MirrorWarp                    ; 0x2C
  Module09_2D_WaitForBird                ; 0x2D
  Module09_2E_Whirlpool                  ; 0x2E
  Module09_2F


Module07_Underworld:
  Module07_00_PlayerControl                    ; 0x00
  Module07_01_IntraroomTransition              ; 0x01
  Module07_02_InterroomTransition              ; 0x02
  Module07_03_OverlayChange                    ; 0x03
  Module07_04_UnlockDoor                       ; 0x04
  Module07_05_ControlShutters                  ; 0x05
  Module07_06_FatInterRoomStairs               ; 0x06
  Module07_07_FallingTransition                ; 0x07
  Module07_08_NorthIntraRoomStairs             ; 0x08
  Module07_09_OpenCrackedDoor                  ; 0x09
  Module07_0A_ChangeBrightness                 ; 0x0A
  Module07_0B_DrainSwampPool                   ; 0x0B
  Module07_0C_FloodSwampWater                  ; 0x0C
  Module07_0D_FloodDam                         ; 0x0D
  Module07_0E_SpiralStairs                     ; 0x0E
  Module07_0F_LandingWipe                      ; 0x0F
  Module07_10_SouthIntraRoomStairs             ; 0x10
  Module07_11_StraightInterroomStairs          ; 0x11
  Module07_11_StraightInterroomStairs          ; 0x12
  Module07_11_StraightInterroomStairs          ; 0x13
  Module07_14_RecoverFromFall                  ; 0x14
  Module07_15_WarpPad                          ; 0x15
  Module07_16_UpdatePegs                       ; 0x16
  Module07_17_PressurePlate                    ; 0x17
  Module07_18_RescuedMaiden                    ; 0x18
  Module07_19_MirrorFade                       ; 0x19
  Module07_1A_RoomDraw_OpenTriforceDoor_bounce ; 0x1A


Link_ControlHandler:
  LinkState_Default                  ; 0x00
  LinkState_Pits                     ; 0x01
  LinkState_Recoil                   ; 0x02
  LinkState_SpinAttack               ; 0x03
  LinkState_Swimming                 ; 0x04
  LinkState_OnIce                    ; 0x05
  LinkState_Recoil                   ; 0x06
  LinkState_Zapped                   ; 0x07
  LinkState_UsingEther               ; 0x08
  LinkState_UsingBombos              ; 0x09
  LinkState_UsingQuake               ; 0x0A - DekuHover
  LinkState_HoppingSouthOW           ; 0x0B
  LinkState_HoppingHorizontallyOW    ; 0x0C
  LinkState_HoppingDiagonallyUpOW    ; 0x0D
  LinkState_HoppingDiagonallyDownOW  ; 0x0E
  LinkState_0F                       ; 0x0F
  LinkState_0F                       ; 0x10
  LinkState_Dashing                  ; 0x11
  LinkState_ExitingDash              ; 0x12
  LinkState_Hookshotting             ; 0x13
  LinkState_CrossingWorlds           ; 0x14
  LinkState_ShowingOffItem           ; 0x15
  LinkState_Sleeping                 ; 0x16
  LinkState_Bunny                    ; 0x17
  LinkState_HoldingBigRock           ; 0x18
  LinkState_ReceivingEther           ; 0x19
  LinkState_ReceivingBombos          ; 0x1A
  LinkState_ReadingDesertTablet      ; 0x1B
  LinkState_TemporaryBunny           ; 0x1C
  LinkState_TreePull                 ; 0x1D
  LinkState_SpinAttack               ; 0x1E


Link_HandleYItem:
  LinkItem_Bombs
  LinkItem_Boomerang
  LinkItem_Bow
  LinkItem_Hammer

  LinkItem_Rod
  LinkItem_Rod
  LinkItem_Net
  LinkItem_ShovelAndFlute

  LinkItem_Lamp
  LinkItem_Powder
  LinkItem_Bottle
  LinkItem_Book

  LinkItem_CaneOfByrna
  LinkItem_Hookshot
  LinkItem_Bombos
  LinkItem_Ether

  LinkItem_Quake
  LinkItem_CaneOfSomaria
  LinkItem_Cape
  LinkItem_Mirror


; Liftable object palettes
; Sprites Aux 2 #8 for DW
; Sprites Aux 2 #6 for LW
; #7 and #9 are the yellow bush palettes


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
