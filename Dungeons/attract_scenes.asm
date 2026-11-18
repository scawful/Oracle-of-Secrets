; Apart of Bank 0x0C
; Module14_Attract


; Attract_LoadNewScene
;   #_0CEEEC: dw AttractScene_PolkaDots    ; 0x00
;   #_0CEEEE: dw AttractScene_WorldMap     ; 0x01
;   #_0CEEF0: dw AttractScene_ThroneRoom   ; 0x02
;   #_0CEEF2: dw AttractScene_Prison       ; 0x03
;   #_0CEEF4: dw AttractScene_AgahnimAltar ; 0x04
;   #_0CEEF6: dw AttractScene_EndOfStory   ; 0x05

; ==========================================================

LoadCommonSprites_long = $00E384
Underworld_LoadAndDrawEntranceRoom = $02C533
Underworld_SaveAndLoadLoadAllPalettes = $02C546
AttractScene_AdvanceFromDungeon = $0CEFC0
Underworld_LoadAllPalettes = $02C55E
PuppetSoldier = $1DEB84
Attract_DrawPreloadedSprite = $0CF9B5
Attract_SetUpConclusionHDMA = $0ABC33
Attract_DoTextInDungeonScene = $0CF766
Attract_FadeInStep = $0CEEA6
Attract_DrawZelda = $0CF9E8
Attract_DrawKidnappedMaiden = $0CFA30
HandleScreenFlash = $1DE9B6
FadeMusicAndResetSRAMMirror = $0CC2F0

; Island-history narration and royal attract cards.
; The storybook and the three room scenes show the history narration in
; expanded messages $1C0-$1C3 instead of $112-$115. Text approved by scawful
; 2026-09-26 (Docs/Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md).
!AttractMsg_Throne    = $C1 ; message $01C1
!AttractMsg_Prison    = $C2 ; message $01C2
!AttractMsg_Altar     = $C3 ; message $01C3
; Scene lengths hold each last page about 3 seconds after its final line
; appears. The message then waits at its end; the scene timer ends the
; scene. (Measured in headless Mesen2 / yaze with the ORA flag fix.)
!AttractFrames_Throne = $0260
!AttractFrames_Prison = $02AC
!AttractFrames_Altar  = $0478

pushpc
; Attract_Initialize (vanilla code, not reassembled here).
org $0CEE58 : dw $01C0 ; @hook module=Dungeons name=AttractStorybookMessage kind=data
org $0CEE62 : dw $08C4 ; @hook module=Dungeons name=AttractStorybookFrames kind=data (tight 2-level/f swaps + ~2.5s Page 4 hold)
; AttractScene_WorldMap ($0CEF23-$0CEF38): whole-island establishing view
; panning to Kalyxo Castle (area $0B) via AttractMap_Pan ($0CFFB1 hook).
org $0CEF24 : dw $00F6 ; @hook module=Dungeons name=AttractMapZoomM7Y kind=data
org $0CEF2A : dw $0100 ; @hook module=Dungeons name=AttractMapZoomM7X kind=data
org $0CEF30 : dw $0080 ; @hook module=Dungeons name=AttractMapZoomHOFS kind=data
org $0CEF36 : dw $00C9 ; @hook module=Dungeons name=AttractMapZoomVOFS kind=data
pullpc

incsrc "Dungeons/attract_royal_scenes.asm"
