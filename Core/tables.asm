
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


#_01B625: LDA.l UnderworldPaletteSets+0,X
#_01B629: STA.w $0AB6 ; PALBG

#_01B62C: LDA.l UnderworldPaletteSets+1,X
#_01B630: STA.w $0AAC ; PALSPR0

#_01B633: LDA.l UnderworldPaletteSets+2,X
#_01B637: STA.w $0AAD ; PALSPR1

#_01B63A: LDA.l UnderworldPaletteSets+3,X
#_01B63E: STA.w $0AAE ; PALSPR2

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
#_0ED460: db $00, $00, $03, $01 ; 0x00
#_0ED464: db $02, $00, $03, $01 ; 0x01
#_0ED468: db $04, $00, $0A, $01 ; 0x02 House
#_0ED46C: db $06, $00, $01, $07 ; 0x03 Fortress of Secrets
#_0ED470: db $0A, $02, $02, $07 ; 0x04 Zora Temple
#_0ED474: db $04, $04, $03, $0A ; 0x05 House
#_0ED478: db $0C, $05, $08, $14 ; 0x06 Tail Palace
#_0ED47C: db $0E, $00, $03, $0A ; 0x07 Goron Mines/Caves
#_0ED480: db $02, $00, $0F, $14 ; 0x08 Castle Basement
#_0ED484: db $0A, $02, $00, $07 ; 0x09 
#_0ED488: db $02, $00, $0F, $0C ; 0x0A
#_0ED48C: db $06, $00, $06, $07 ; 0x0B
#_0ED490: db $00, $00, $0E, $12 ; 0x0C Kalyxo Castle
#_0ED494: db $12, $05, $05, $0B ; 0x0D
#_0ED498: db $12, $00, $02, $0C ; 0x0E
#_0ED49C: db $10, $05, $0A, $07 ; 0x0F Mushroom Grotto
#_0ED4A0: db $10, $00, $10, $0C ; 0x10 Ranch?
#_0ED4A4: db $16, $07, $02, $07 ; 0x11 Hall of Secrets
#_0ED4A8: db $16, $00, $07, $0F ; 0x12
#_0ED4AC: db $08, $00, $04, $0C ; 0x13 Glacia Estate
#_0ED4B0: db $08, $00, $04, $09 ; 0x14
#_0ED4B4: db $04, $00, $03, $01 ; 0x15 House
#_0ED4B8: db $14, $00, $04, $04 ; 0x16
#_0ED4BC: db $14, $00, $14, $0C ; 0x17 
#_0ED4C0: db $18, $05, $07, $0B ; 0x18 Lava Lands Cave/Turtle Rock
#_0ED4C4: db $18, $06, $10, $0C ; 0x19
#_0ED4C8: db $1A, $05, $08, $14 ; 0x1A Dragon Ship
#_0ED4CC: db $1A, $02, $00, $07 ; 0x1B Dragon Ship
#_0ED4D0: db $06, $00, $03, $0A ; 0x1C
#_0ED4D4: db $1C, $00, $03, $01 ; 0x1D
#_0ED4D8: db $1E, $00, $0B, $11 ; 0x1E Swordsmith
#_0ED4DC: db $04, $00, $0B, $11 ; 0x1F
#_0ED4E0: db $0E, $00, $00, $02 ; 0x20 
#_0ED4E4: db $20, $08, $13, $0D ; 0x21 Ganondorf Boss
#_0ED4E8: db $0A, $00, $03, $0A ; 0x22 Zora Temple
#_0ED4EC: db $14, $00, $04, $04 ; 0x23
#_0ED4F0: db $1A, $02, $02, $07 ; 0x24 Dragon Ship
#_0ED4F4: db $1A, $0A, $00, $00 ; 0x25 Dragon Ship
#_0ED4F8: db $00, $00, $03, $02 ; 0x26
#_0ED4FC: db $0E, $00, $03, $07 ; 0x27
#_0ED500: db $1A, $05, $05, $0B ; 0x28 Dragon Ship


OverworldPaletteSet:
#_0ED504: db $00, $FF, $07, $FF ; 0x00
#_0ED508: db $00, $01, $07, $FF ; 0x01
#_0ED50C: db $00, $02, $07, $FF ; 0x02
#_0ED510: db $00, $03, $07, $FF ; 0x03
#_0ED514: db $00, $04, $07, $FF ; 0x04
#_0ED518: db $00, $05, $07, $FF ; 0x05
#_0ED51C: db $00, $06, $07, $FF ; 0x06
#_0ED520: db $07, $06, $05, $FF ; 0x07
#_0ED524: db $00, $08, $07, $FF ; 0x08
#_0ED528: db $00, $09, $07, $FF ; 0x09
#_0ED52C: db $00, $0A, $07, $FF ; 0x0A
#_0ED530: db $00, $0B, $07, $FF ; 0x0B
#_0ED534: db $00, $FF, $07, $FF ; 0x0C
#_0ED538: db $00, $FF, $07, $FF ; 0x0D
#_0ED53C: db $03, $04, $07, $FF ; 0x0E
#_0ED540: db $04, $04, $03, $FF ; 0x0F
#_0ED544: db $10, $FF, $06, $FF ; 0x10
#_0ED548: db $10, $01, $06, $FF ; 0x11
#_0ED54C: db $10, $11, $06, $FF ; 0x12
#_0ED550: db $10, $03, $06, $FF ; 0x13
#_0ED554: db $10, $04, $06, $FF ; 0x14
#_0ED558: db $10, $05, $06, $FF ; 0x15
#_0ED55C: db $10, $06, $06, $FF ; 0x16
#_0ED560: db $12, $13, $04, $FF ; 0x17
#_0ED564: db $12, $05, $04, $FF ; 0x18
#_0ED568: db $10, $09, $06, $FF ; 0x19
#_0ED56C: db $10, $0B, $06, $FF ; 0x1A
#_0ED570: db $10, $0C, $06, $FF ; 0x1B
#_0ED574: db $10, $0D, $06, $FF ; 0x1C
#_0ED578: db $10, $0E, $06, $FF ; 0x1D
#_0ED57C: db $10, $0F, $06, $FF ; 0x1E


pool Module09_Overworld

.submodules
#_02A40D: dw Module09_00_PlayerControl              ; 0x00
#_02A40F: dw Module09_LoadAuxGFX                    ; 0x01
#_02A411: dw Module09_TriggerTilemapUpdate          ; 0x02
#_02A413: dw Module09_LoadNewMapAndGFX              ; 0x03
#_02A415: dw Module09_LoadNewSprites                ; 0x04
#_02A417: dw Overworld_StartScrollTransition        ; 0x05
#_02A419: dw Overworld_RunScrollTransition          ; 0x06
#_02A41B: dw Overworld_EaseOffScrollTransition      ; 0x07
#_02A41D: dw Overworld_FinalizeEntryOntoScreen      ; 0x08
#_02A41F: dw Module09_09_OpenBigDoorFromExiting     ; 0x09
#_02A421: dw Module09_0A_WalkFromExiting_FacingDown ; 0x0A
#_02A423: dw Module09_0B_WalkFromExiting_FacingUp   ; 0x0B
#_02A425: dw Module09_0C_OpenBigDoor                ; 0x0C
#_02A427: dw Overworld_StartMosaicTransition        ; 0x0D
#_02A429: dw Overworld_LoadSubscreenAndSilenceSFX1  ; 0x0E
#_02A42B: dw Module09_LoadAuxGFX                    ; 0x0F
#_02A42D: dw Module09_TriggerTilemapUpdate          ; 0x10
#_02A42F: dw Module09_LoadNewMapAndGFX              ; 0x11
#_02A431: dw Module09_LoadNewSprites                ; 0x12
#_02A433: dw Overworld_StartScrollTransition        ; 0x13
#_02A435: dw Overworld_RunScrollTransition          ; 0x14
#_02A437: dw Overworld_EaseOffScrollTransition      ; 0x15
#_02A439: dw Module09_FadeBackInFromMosaic          ; 0x16
#_02A43B: dw Overworld_StartMosaicTransition        ; 0x17
#_02A43D: dw Module09_18                            ; 0x18
#_02A43F: dw Module09_19                            ; 0x19
#_02A441: dw Module09_LoadAuxGFX                    ; 0x1A
#_02A443: dw Module09_TriggerTilemapUpdate          ; 0x1B
#_02A445: dw Module09_1C                            ; 0x1C
#_02A447: dw Module09_1D                            ; 0x1D
#_02A449: dw Module09_1E                            ; 0x1E
#_02A44B: dw Module09_1F                            ; 0x1F
#_02A44D: dw Overworld_ReloadSubscreenOverlay       ; 0x20
#_02A44F: dw Module09_21                            ; 0x21
#_02A451: dw Module09_22                            ; 0x22
#_02A453: dw Module09_MirrorWarp                    ; 0x23
#_02A455: dw Overworld_StartMosaicTransition        ; 0x24
#_02A457: dw Module09_25                            ; 0x25
#_02A459: dw Module09_LoadAuxGFX                    ; 0x26
#_02A45B: dw Module09_TriggerTilemapUpdate          ; 0x27
#_02A45D: dw Overworld_LoadAndBuildScreen           ; 0x28
#_02A45F: dw Module09_FadeBackInFromMosaic          ; 0x29
#_02A461: dw Module09_2A_RecoverFromDrowning        ; 0x2A
#_02A463: dw Module09_2B                            ; 0x2B
#_02A465: dw Module09_MirrorWarp                    ; 0x2C
#_02A467: dw Module09_2D_WaitForBird                ; 0x2D
#_02A469: dw Module09_2E_Whirlpool                  ; 0x2E
#_02A46B: dw Module09_2F   


pool Module07_Underworld

.submodules
#_02876C: dw Module07_00_PlayerControl                    ; 0x00
#_02876E: dw Module07_01_IntraroomTransition              ; 0x01
#_028770: dw Module07_02_InterroomTransition              ; 0x02
#_028772: dw Module07_03_OverlayChange                    ; 0x03
#_028774: dw Module07_04_UnlockDoor                       ; 0x04
#_028776: dw Module07_05_ControlShutters                  ; 0x05
#_028778: dw Module07_06_FatInterRoomStairs               ; 0x06
#_02877A: dw Module07_07_FallingTransition                ; 0x07
#_02877C: dw Module07_08_NorthIntraRoomStairs             ; 0x08
#_02877E: dw Module07_09_OpenCrackedDoor                  ; 0x09
#_028780: dw Module07_0A_ChangeBrightness                 ; 0x0A
#_028782: dw Module07_0B_DrainSwampPool                   ; 0x0B
#_028784: dw Module07_0C_FloodSwampWater                  ; 0x0C
#_028786: dw Module07_0D_FloodDam                         ; 0x0D
#_028788: dw Module07_0E_SpiralStairs                     ; 0x0E
#_02878A: dw Module07_0F_LandingWipe                      ; 0x0F
#_02878C: dw Module07_10_SouthIntraRoomStairs             ; 0x10
#_02878E: dw Module07_11_StraightInterroomStairs          ; 0x11
#_028790: dw Module07_11_StraightInterroomStairs          ; 0x12
#_028792: dw Module07_11_StraightInterroomStairs          ; 0x13
#_028794: dw Module07_14_RecoverFromFall                  ; 0x14
#_028796: dw Module07_15_WarpPad                          ; 0x15
#_028798: dw Module07_16_UpdatePegs                       ; 0x16
#_02879A: dw Module07_17_PressurePlate                    ; 0x17
#_02879C: dw Module07_18_RescuedMaiden                    ; 0x18
#_02879E: dw Module07_19_MirrorFade                       ; 0x19
#_0287A0: dw Module07_1A_RoomDraw_OpenTriforceDoor_bounce ; 0x1A
