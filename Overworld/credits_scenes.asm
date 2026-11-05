; =========================================================
; Ending credits: Oracle overworld scenes before the staff roll.
;
; Vanilla Module1A plays 16 scenes (subs $00-$1F) and then the staff roll
; (sub $20). Each scene loads its camera from an UnderworldExitData record,
; but Oracle reused those records, so the vanilla scan never matches and hangs.
; This file:
;   1. Hooks LoadOverworldFromUnderworld's record scan: during credits ($10 =
;      $1A) the camera comes from OracleCredits_* tables below instead.
;   2. Plays !OracleCredits_SceneCount scenes, all overworld, with a blank
;      caption, then jumps to the staff roll. Only scene 7 has an actor.
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
;   7 Abyss grass patch area $46  pan down; a sapling grows on the grass
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

; Scene 7 actor: a sapling grows from a magic bean on the grass patch.
; Reuses the bean vendor's frames (Sprites/NPCs/bean_vendor.asm), no new tiles.
; Called through OracleCredits_SaplingVector in bank $0E. M=8, X=8, DBR=$0E.
!OracleCredits_SaplingX = $0CF8 ; area $46 map px (248,260)
!OracleCredits_SaplingY = $0104

OracleCredits_SaplingDraw:
{
  PHB : PHK : PLB
  LDX.b #$00                                        ; sprite slot 0 (cleared at scene load)
  LDA.b #!OracleCredits_SaplingX : STA.w $0D10, X
  LDA.b #!OracleCredits_SaplingX>>8 : STA.w $0D30, X
  LDA.b #!OracleCredits_SaplingY : STA.w $0D00, X
  LDA.b #!OracleCredits_SaplingY>>8 : STA.w $0D20, X

  ; Growth stage by scene time ($C8): the bean, then the vine swaying
  ; between its two frames every 32 frames.
  REP #$20
  LDY.b #$00 : LDA.b $C8 : CMP.w #$0170 : BCC .frame
  INY : AND.w #$0020 : BEQ .frame
  INY
  .frame
  SEP #$20
  STY.b $07

  LDA.b #$18 : JSL OAM_AllocateFromRegionA ; up to 6 tiles
  JSL Sprite_Get_16_bit_Coords
  JSL Sprite_PrepOamCoord : BCS .done

  LDX.b $07
  LDA.w .stage_start, X : STA.b $06
  LDA.w .stage_last, X : TAX
  LDY.b #$00
  .next_tile
  PHX
  TXA : CLC : ADC.b $06 : PHA
  ASL A : TAX
  REP #$20
  LDA.b $00 : CLC : ADC.l Sprite_BeanVendor_Draw_x_offsets, X : STA.b ($90), Y
  AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : CLC : ADC.l Sprite_BeanVendor_Draw_y_offsets, X : STA.b ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y
    LDA.b #$F0 : STA.b ($90), Y
  .on_screen_y
  PLX
  INY
  LDA.l Sprite_BeanVendor_Draw_chr, X : STA.b ($90), Y
  INY
  LDA.l Sprite_BeanVendor_Draw_properties, X : STA.b ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.l Sprite_BeanVendor_Draw_sizes, X : ORA.b $0F : STA.b ($92), Y
  PLY : INY
  PLX : DEX : BPL .next_tile

  .done
  PLB
  RTL

  ; First tile and tile count-1 in the bean vendor tables for each stage:
  ; bean (frame 1), vine A (frame 2), vine B (frame 3). The sprout frames
  ; (5/6) use sprite page 0 chars, which hold other art in this scene.
  .stage_start : db $04, $05, $0B
  .stage_last  : db 0, 5, 5
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
; Scene 7 uses the Ranch sprite set and palette (set $06, palette $01), which
; hold the bean vendor's tiles.
org $0285E9 ; @hook module=Overworld kind=data name=OracleCreditsSaplingGfx
  db $06
org $0285FA ; @hook module=Overworld kind=data name=OracleCreditsSaplingPalette
  db $01

; Credits_LoadNextScene_Underworld ($0E9891) only ran for vanilla subs $02,
; $14 and $16; $02 is an overworld scene here and $14/$16 come after the last
; scene, so its 8 bytes hold the scene 7 draw vector.
org $0E9891 ; @hook module=Overworld name=OracleCredits_SaplingVector kind=jsl target=OracleCredits_SaplingDraw expected_m=8 expected_x=8
OracleCredits_SaplingVector:
  JSL OracleCredits_SaplingDraw
  RTS
  assert pc() <= $0E9899

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

; Credits_SpriteDraw_vectors: only scene 7 draws (the sapling).
org $0E99A5 ; @hook module=Overworld kind=data name=OracleCreditsSpriteDraw
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor
  dw OracleCredits_SaplingVector

; Credits_HandleSceneFade .timer: frames before the fade-out starts.
org $0E9A0A ; @hook module=Overworld kind=data name=OracleCreditsTimer
  dw $02C0, $02C0, $02C0, $02C0, $02C0, $02C0, $02C0, $02C0

pullpc
