; Overworld.asm

; Random chance of hearts from bush instead of guards
org $1AFBBF : db $0B ; Heart Index
org $1AFBC7 : db $0B ; Heart Index
org $1AFBD7 : db $00

; Remove beginning rain inside rooms (UnderworldAdjustRainSFX).
; Also with !ENABLE_PART0_STORM: interiors stay silent (scawful, 2026-09-25).
org $02838C : LDA.l GameState : CMP.b #$00

; Phase-00 outdoor ambience still comes from LightWorldAmbiance, independently
; of Pool_EnableBeginningRain. Its high nibble is SFX1; preserve the base ROM's
; low music nibble and replace rain ($1) with explicit silence ($5), not $0.
; @source usdasm/bank_02.asm:LightWorldAmbiance, AdjustOverworldAmbiance
; Only the intro table changes; later phases, Mire, and Song of Storms remain.
org $02C316 : db (read1($02C316)&$0F)|$50 ; Area $13: Kalyxo Castle ; @hook module=Overworld kind=data name=IntroAmbience02C316
org $02C317 : db (read1($02C317)&$0F)|$50 ; Area $14: Kalyxo Castle ; @hook module=Overworld kind=data name=IntroAmbience02C317
org $02C31E : db (read1($02C31E)&$0F)|$50 ; Area $1B: Kalyxo Castle ; @hook module=Overworld kind=data name=IntroAmbience02C31E
org $02C31F : db (read1($02C31F)&$0F)|$50 ; Area $1C: Kalyxo Road ; @hook module=Overworld kind=data name=IntroAmbience02C31F
org $02C326 : db (read1($02C326)&$0F)|$50 ; Area $23: Wayward Village ; @hook module=Overworld kind=data name=IntroAmbience02C326
org $02C327 : db (read1($02C327)&$0F)|$50 ; Area $24: Wayward Village ; @hook module=Overworld kind=data name=IntroAmbience02C327
org $02C32E : db (read1($02C32E)&$0F)|$50 ; Area $2B: Wayward Village ; @hook module=Overworld kind=data name=IntroAmbience02C32E
org $02C32F : db (read1($02C32F)&$0F)|$50 ; Area $2C: Wayward Village ; @hook module=Overworld kind=data name=IntroAmbience02C32F

; RoomTag_GanonDoor
; Replace SprState == 04 -> .exit
org $01C769 : LDA.w SprState, X : CMP.b #$02

; Credits_LoadNextScene_Overworld
; Skip end cutscene until it's ready
org $0E9889 : LDA #$20 : STA $11 : RTS

; =========================================================
; Special Area Properties

org $0EDE29
{
  ; corresponding warp types that lead to special overworld areas
  dw $01EF, $01EF, $00AD, $00B9

  ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
  dw $002A, $0018, $000F, $0081

  ; Direction Link will face when he enters the special area
  dw $0008, $0008, $0008, $0008

  ; Exit value for the special area. In Hyrule Magic these are those White markers.
  dw $0180, $0181, $0182, $0189
}

; =========================================================

incsrc "Overworld/lost_woods.asm"
%log_end("Overworld/lost_woods.asm", !LOG_OVERWORLD)

org $348000 ; Free space
pushpc
incsrc "Overworld/time_system.asm"
%log_end("Overworld/time_system.asm", !LOG_OVERWORLD)

incsrc "Overworld/overlays.asm"
%log_end("Overworld/overlays.asm", !LOG_OVERWORLD)

incsrc "Overworld/entrances.asm"
%log_end("Overworld/entrances.asm", !LOG_OVERWORLD)

incsrc "Overworld/custom_gfx.asm"
%log_end("Overworld/custom_gfx.asm", !LOG_OVERWORLD)
pushpc

incsrc "Overworld/world_map.asm"
%log_end("Overworld/world_map.asm", !LOG_OVERWORLD)

; =========================================================
; Get Lv2 Sword from chest
; Get Lv4 Sword from pedestal

; At 04/87CA, change D0 into 80
org $0987CA : db $80

; Disable wind blowing sfx:
; At 04/45D4, change 09 into 00
org $08C5D4 : db $00

; MasterSword_HandleReceipt
org $0589AF : LDY.b #$03 ; ITEMGET 03

; Module15_0C
; Prevent the game from setting $7EF3C7 to 06
org $029E58 : NOP #6

pullpc
LoadDarkWorldIntro:
{
  ; If we have the old man, set us indoors and dark world
  LDA.l $7EF3C8 : CMP.b #$05 : BNE .not_dw_spawn
    LDA.b #$01 : STA.b $1B
    LDA.b #$40 : STA.l $7EF3CA
    RTL
  .not_dw_spawn
  ; Dungeon/cave death continues must rebuild the current underworld room.
  ; Apply story-specific overworld routing only to outdoor loads.
  LDA.b $1B : BNE .indoors
if !ENABLE_ABYSS_RESPAWN_UNTIL_ESCAPE == 1
  ; Abyss respawn lock (decisions.org, scawful 2026-09-26): from Kydrog's
  ; banishment until the escape, outdoor deaths and continues load the Abyss.
  ; The saved world is the lock: Kydrog_WarpPlayerAway sets $7EF3CA = $40 with
  ; Story2_KydrogEncounter; the first light world arrival after that sets it
  ; to $00 (today the DW $6A warp tile, $02B236; later the sword warp home,
  ; decisions.org). The same condition ends the Part 0 storm (storm.asm).
  ; GameOver keeps $7EF3CA while GameState >= 2 ($09F520 patch below). The
  ; old OOSPROG < 2 force is not used: it ended at the Maku Tree and sent a
  ; death or continue after the escape back to the Abyss.
else
  LDA.l GameState : CMP.b #$02 : BNE .intro_sequence
    ; Check for maku tree progress flag
    LDA.l OOSPROG : CMP.b #$02 : BCS .has_pearl
      STZ.w $1B
      LDA.b #$40 : STA.l $7EF3CA
      RTL
    .has_pearl
endif
  .intro_sequence
  LDA.l $7EF3CA
  .indoors
  RTL
}
pushpc

; Module05_LoadFile
org $028192 : JSL LoadDarkWorldIntro ; @hook module=Overworld name=LoadDarkWorldIntro kind=jsl target=LoadDarkWorldIntro

; Module05_LoadFile
; Check for goldstar instead of mirror for mountain spawn option
org $0281E2 : LDA.l $7EF342 : CMP.b #$02

; Check for hall of secrets spawn pt flag
org $0281CD : LDA.l $7EF3D6 : CMP.b #$04

; GameOver_FadeAndRevive
org $09F520 : LDA.l GameState : CMP.b #$02

pullpc
if !ENABLE_PART0_STORM == 1
  incsrc "Overworld/storm.asm"
endif

LoadOverworldPitAreas:
{
  LDA $8A : CMP.b #$0F : BEQ .allow_transition
            CMP.b #$11 : BEQ .allow_transition
            CMP.b #$23 : BEQ .allow_transition
            CMP.b #$57 : BEQ .allow_transition
    SEC ; fall in the pit
    RTL
  .allow_transition
  CLC ; allow transition
  RTL
}

Overworld_GetPitDestination = $1BB860

; DetermineConsequencesOfFalling
org $0794D9 ; @hook module=Overworld
  JSL LoadOverworldPitAreas : BCC .overworld_pit_transition
    JSL $01FFD9 ; TakeDamageFromPit
    RTS
  .overworld_pit_transition

org $1AF5C3 : CMP.b #$5E

org $0EF581
EXIT_0EF581:

; FlashGanonTowerPalette
org $0EF587
  LDA.b $8A : CMP.b #$73 : BEQ .on_dark_dm
              CMP.b #$75 : BEQ .on_dark_dm
              CMP.b #$7D : BNE EXIT_0EF581
  .on_dark_dm

org $0EF531
Palettes_GanonTowerFlash:
  dw  $7FFF,  $0884,  $1CC8,  $1DCE,  $3694,  $4718,  $1D4A,  $18AC
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $34CD,  $5971,  $5635,  $7F1B,  $7FFF,  $1D4A,  $3D54
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $0884,  $052A,  $21EF,  $3AB5,  $4B39,  $1D4C,  $18AC
; dw  $7FFF,  $0C63,  $40A5,  $5D67, $7EAE, $7F18, $7A6B, $7B5C
