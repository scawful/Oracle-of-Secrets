; =========================================================
; Ending credits: Oracle overworld scenes before the staff roll.
;
; Vanilla Module1A plays 16 scenes (subs $00-$1F) and then the staff roll
; (sub $20). Each scene loads its camera from an UnderworldExitData record,
; but Oracle reused those records, so the vanilla scan never matches and hangs.
; This file:
;   1. Hooks LoadOverworldFromUnderworld's record scan: during credits ($10 =
;      $1A) the camera comes from OracleCredits_* tables below instead.
;   2. Plays !OracleCredits_SceneCount scenes, all overworld, with no actors and
;      a blank caption, then jumps to the staff roll.
;   3. Patches the vanilla per-scene tables for those scenes (pan, timer).
;
; Scenes (camera pans 96 px and ends on the chosen view):
;   0 Ranch            area $00  pan right
;   1 Wayward Village  area $23  pan down
;   2 Hall of Secrets  area $0E  pan right
;   3 Kalyxo Castle    area $0B  pan up to the gate
;   4 Loom Beach       area $33  pan left
;   5 Zora island house area $1E  pan down
;   6 Goron mine door  area $36  pan up
;   7 Abyss grass patch area $46  pan down (sapling spot)
; Included from Overworld/overworld.asm (bank $34 free space).

!OracleCredits_SceneCount = 8

; Camera values as Oracle's ZScream exits compute them from the scroll position.
function credits_map_x(area) = (area&$07)<<9
function credits_map_y(area) = (area&$38)<<6
function credits_vram(area, sy, sx) = (((sy-credits_map_y(area))&$FFF0)<<3)|(((sx-credits_map_x(area))&$FFF0)>>3)

; Start scroll (top-left of the camera), per scene.
OracleCredits_Area:
  db $00, $23, $0E, $0B, $33, $1E, $36, $46
OracleCredits_ScrollY:
  dw $00C0, $08E0, $0220, $0380, $0EA0, $0630, $0E00, $0030
OracleCredits_ScrollX:
  dw $01A0, $0700, $0C20, $0740, $0760, $0C30, $0C80, $0C70
OracleCredits_Vram:
  dw credits_vram($00, $00C0, $01A0)
  dw credits_vram($23, $08E0, $0700)
  dw credits_vram($0E, $0220, $0C20)
  dw credits_vram($0B, $0380, $0740)
  dw credits_vram($33, $0EA0, $0760)
  dw credits_vram($1E, $0630, $0C30)
  dw credits_vram($36, $0E00, $0C80)
  dw credits_vram($46, $0030, $0C70)

; Replaces `LDX.b #$9E : DEX : DEX` at LoadOverworldFromUnderworld_custom_exit.
; M=16, X=8, DBR=$02, A = $A0 (exit room id).
OracleCredits_ExitHook:
{
  LDX.b $10 : CPX.b #$1A : BEQ .credits
    LDX.b #$9C
    JML $02E4D8 ; vanilla record scan (CMP UnderworldExitData_room_id,X)

  .credits
  LDA.b $11 : AND.w #$00FE : TAX
  LDA.l OracleCredits_ScrollY, X
  STA.b $E6 : STA.b $E8 : STA.w $0122 : STA.w $0124
  CLC : ADC.w #$0050 : STA.b $20                    ; Link Y = scroll + 80
  CLC : ADC.w #$001F : STA.w $0618                  ; camera Y = Link Y + 31
  DEC A : DEC A : STA.w $061A
  LDA.l OracleCredits_ScrollX, X
  STA.b $E0 : STA.b $E2 : STA.w $011E : STA.w $0120
  CLC : ADC.w #$0078 : STA.b $22                    ; Link X = scroll + 120
  CLC : ADC.w #$0007 : STA.w $061C                  ; camera X = Link X + 7
  DEC A : DEC A : STA.w $061E

  LDA.l OracleCredits_Vram, X : STA.b $84
  SEC : SBC.w #$0400 : AND.w #$0F80 : ASL A : XBA : STA.b $88
  LDA.b $84 : SEC : SBC.w #$0010 : AND.w #$003E : LSR A : STA.b $86

  LDA.w #$0002 : STA.b $2F
  STZ.w $0696 : STZ.w $0698                         ; no door to redraw
  STZ.w $0624 : STZ.w $0626 : STZ.w $0628 : STZ.w $062A ; scroll aligned to 16 px

  TXA : LSR A : TAX
  SEP #$20
  LDA.l OracleCredits_Area, X : STA.b $8A : STA.w $040A
  STZ.b $8B : STZ.w $040B
  REP #$20
  JML $02E58A ; Overworld_LoadNewScreenProperties_pre (PLB, then M=16 code)
}

; Replaces Credits_LoadNextScene_Overworld. M=8, X=8.
OracleCredits_LoadNextScene:
{
  LDA.b $11 : CMP.b #!OracleCredits_SceneCount*2 : BCC .scene
    LDA.b #$20 : STA.b $11                          ; staff roll
    RTL

  .scene
  JSL $0285BA ; Credits_LoadScene_Overworld

  ; Blank caption: the vanilla clear stripe for the caption rows, no text.
  REP #$20
  LDA.w #$0060 : STA.l $7E1002                      ; VRAM $C000
  LDA.w #$FE47 : STA.l $7E1004
  LDA.l $0EB176 : STA.l $7E1006                     ; CreditsBlankFillTile
  LDA.w #$0006 : STA.l $7E1000
  SEP #$20
  LDA.b #$FF : STA.l $7E1008
  LDA.b #$01 : STA.b $14
  RTL
}

; Tile sheets: ZS InitTilesetsLongCalls also treats module $1A as outdoors, so
; each scene loads its area's own sheets (see ZSCustomOverworld.asm).

pushpc

org $02E4D4 ; @hook module=Overworld name=OracleCredits_ExitHook kind=jml target=OracleCredits_ExitHook expected_m=16 expected_x=8
  JML OracleCredits_ExitHook
  assert pc() == $02E4D8

; $0E988D (the old JSR Credits_AddEndingSequenceText) becomes a bare RTS; the
; no-actor sprite vectors below point at it.
org $0E9889 ; @hook module=Overworld name=OracleCredits_LoadNextScene kind=jsl target=OracleCredits_LoadNextScene expected_m=8 expected_x=8
  JSL OracleCredits_LoadNextScene
  RTS
  assert pc() == $0E988E
!OracleCredits_NoActor = $988D

; Module1A sub vectors: scene 1 (vanilla Sanctuary) is an overworld scene here.
org $0E9824 ; @hook module=Overworld kind=data name=OracleCreditsSubVectors
  dw $9889, $9958

; Credits_LoadScene_Overworld_PrepGFX sends subs $0C and $1E (vanilla Zora's
; Domain / Master Sword) to LoadSpecialOverworld, which overwrites the area's
; tile sheets and palette after the camera hook. All Oracle scenes are normal
; overworld areas, so compare against $FF (load subs are even; never matches).
org $02861D ; @hook module=Overworld kind=data name=OracleCreditsNoSpecialA
  db $FF
org $028621 ; @hook module=Overworld kind=data name=OracleCreditsNoSpecialB
  db $FF

; Credits_LoadScene_Overworld .sprite_gfx / .sprite_palette for scene 1.
org $0285E3 ; @hook module=Overworld kind=data name=OracleCreditsSpriteGfx
  db $28
org $0285F4 ; @hook module=Overworld kind=data name=OracleCreditsSpritePalette
  db $01

; Credits_PrepAndLoadSprites .vectors: no actors.
org $0E9899 ; @hook module=Overworld kind=data name=OracleCreditsLoadSprites
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor

; Credits_ScrollScene .target_y / .target_x / .movement_y / .movement_x.
org $0E98D8 ; @hook module=Overworld kind=data name=OracleCreditsTargetY
  dw $00C0, $0940, $0220, $0320, $0EA0, $0690, $0DA0, $0090
org $0E98F8 ; @hook module=Overworld kind=data name=OracleCreditsTargetX
  dw $0200, $0700, $0C80, $0740, $0700, $0C30, $0C80, $0C70
org $0E9918 ; @hook module=Overworld kind=data name=OracleCreditsMoveY
  dw 0, 1, 0, -1, 0, 1, -1, 1
org $0E9938 ; @hook module=Overworld kind=data name=OracleCreditsMoveX
  dw 1, 0, 1, 0, -1, 0, 0, 0

; Credits_SpriteDraw_vectors: nothing to draw.
org $0E99A5 ; @hook module=Overworld kind=data name=OracleCreditsSpriteDraw
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor

; Credits_HandleSceneFade .timer: frames before the fade-out starts.
org $0E9A0A ; @hook module=Overworld kind=data name=OracleCreditsTimer
  dw $02C0, $02C0, $02C0, $02C0, $02C0, $02C0, $02C0, $02C0

pullpc
