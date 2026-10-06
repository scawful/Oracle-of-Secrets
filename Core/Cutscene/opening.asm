; =========================================================
; Opening experiments (Docs/Planning/RC_MASTER_PLAN.md section 3)
;
; Included from Oracle_main.asm only when !ENABLE_CUTSCENE_FRAMEWORK is 1.
; Plan and evidence: Docs/Planning/Plans/intro_plan_2026-09-24.md
;
; Oracle arrival (!ENABLE_ORACLE_ARRIVAL_SEQUENCE)
;   New file, first load of Link's house (room $104) with Link tucked into
;   bed: before the iris opens, Link spins down over black while the
;   telepathic plea "Accept our quest" (message $1F) plays. Then the screen
;   fades out, the normal iris opens on the dark bedroom and the house tag
;   runs HouseTag_WakeUpPlayer.
;
;   Part00 (decisions.org "Arrival lines A/B/C approved"): after the fall-out,
;   a pause on black, then line A ($201, Impa's voice) over black, then more
;   black before the iris opens on Link already in bed.
;
;   One-shot: the arrival sets IntroState (StoryState, $7EF39E) to 1, which
;   is the value HouseTag_TelepathicPlea leaves behind. The house tag then
;   skips its own plea, so the message never shows twice.
;   Continue, death and save/quit loads never tuck Link into bed, so they
;   never reach the gate.
;
;   Keep in sync with HouseTag_TelepathicPlea (Dungeons/custom_tag.asm):
;   it sets the clock to 8:00 and plays song $03; the arrival does the same.
; =========================================================

Arrival_LinkOAM_Main      = $0DA18E ; RTL, draws Link from $20/$22 and pose vars
Arrival_RenderText        = $0EC440 ; RTL, message engine (state in $1CD8)
Arrival_IrisSpotlightOpen = $00F295 ; RTL, vanilla Module07_0F_00 call

; Transient state while module $0C runs. Vanilla free WRAM $7FF180-$7FF7FF
; (Core/ram.asm UNUSED_7FF180); no Oracle code uses $7FF300-$7FF31F.
Arrival_State  = $7FF300
Arrival_Save20 = $7FF302 ; 16-bit
Arrival_Save22 = $7FF304 ; 16-bit
Arrival_Save51 = $7FF306 ; 16-bit
Arrival_Save5D = $7FF308
Arrival_Save5B = $7FF309
Arrival_Save5A = $7FF30A
Arrival_Save4B = $7FF30B
Arrival_Save4D = $7FF30C
Arrival_Save1C = $7FF30D
Arrival_Save1D = $7FF30E
Arrival_Save1E = $7FF30F
Arrival_Save1F = $7FF310
Arrival_Timer  = $7FF312 ; $7FF311 was Arrival_Save9A (color math now forced off)
Arrival_Next   = $7FF313 ; state that follows Arrival_HoldBlack

; Part00 line A: Impa's voice on black after "Accept our quest" (message $201,
; Data/dialogue/expanded_messages.json). Frames of black before it, and after
; it before the iris opens on the bed (so Link never jumps from screen center
; to the bed; this replaces the old 60-frame hold).
!ArrivalVoiceMsg         = $0201
!ArrivalVoicePauseFrames = 50
!ArrivalVoiceAfterFrames = 40

; Experiment scene (experiment.asm): Exp_Done holds this value between the
; scene's reload and the arrival, so the gate starts the arrival that time.
!ExpDoneMarker = $5A

if !ENABLE_ORACLE_ARRIVAL_SEQUENCE == 1

pushpc
; Module $0C (vanilla Module0C_Unused, never selected) runs the arrival.
; Module_MainRouting tables: low $008061, mid $00807D, bank $008099.
org $00806D : db Arrival_Module>>0  ; @hook module=Cutscene name=Arrival_ModuleLow kind=data
org $008089 : db Arrival_Module>>8  ; @hook module=Cutscene name=Arrival_ModuleMid kind=data
org $0080A5 : db Arrival_Module>>16 ; @hook module=Cutscene name=Arrival_ModuleBank kind=data

if !ENABLE_EXPERIMENT_SCENE == 1
; Module $0D (vanilla Module0D_Unused, never selected) runs the experiment scene.
org $00806E : db Experiment_Module>>0  ; @hook module=Cutscene name=Experiment_ModuleLow kind=data
org $00808A : db Experiment_Module>>8  ; @hook module=Cutscene name=Experiment_ModuleMid kind=data
org $0080A6 : db Experiment_Module>>16 ; @hook module=Cutscene name=Experiment_ModuleBank kind=data
endif

; Module07_0F_00_InitSpotlight: JSL IrisSpotlight_open (same length).
org $02932D ; @hook module=Cutscene name=Arrival_SpotlightGate kind=jsl target=Arrival_SpotlightGate expected_m=8 expected_x=8
  JSL Arrival_SpotlightGate
assert pc() == $029331
pullpc

pushpc
org $3AC000
; Bank $3A: mask routines end at $3A:8AFC. This block must stay below $3AE000.

; ---------------------------------------------------------
; Gate. Called by Module07_0F_00 with M=8 X=8. DB is not assumed.
; Diverts to module $0C once; otherwise runs the vanilla iris.
Arrival_SpotlightGate:
{
  LDA.b $5D : CMP.b #$16 : BNE .vanilla   ; Link_TuckIntoBed ran on this load
  LDA.b $A1 : CMP.b #$01 : BNE .vanilla   ; room $104 = Link's house
  LDA.b $A0 : CMP.b #$04 : BNE .vanilla
  LDA.l IntroState : BNE .vanilla         ; plea not delivered yet
  if !ENABLE_EXPERIMENT_SCENE == 1
    LDA.l Exp_Done : CMP.b #!ExpDoneMarker : BEQ .after_scene
      LDA.b #$0D : STA.b $10              ; next frame: Experiment_Module; it
      LDA.b #$00 : STA.l Exp_State        ; reloads the house and comes back here
      RTL
    .after_scene
    LDA.b #$00 : STA.l Exp_Done
  endif
    LDA.b #$0C : STA.b $10                ; next frame: Arrival_Module
    LDA.b #$00 : STA.l Arrival_State
    RTL                                   ; caller INCs $B0; handoff clears it
  .vanilla
  JML Arrival_IrisSpotlightOpen           ; tail call, RTLs to $029331
}

; ---------------------------------------------------------
; Module $0C. Entered by JML from Module_MainRouting; must RTL.
Arrival_Module:
{
  PHB : PHK : PLB
  SEP #$30
  LDA.l Arrival_State : ASL A : TAX
  JSR (.states, X)
  PLB
  RTL

  .states
  dw Arrival_Init
  dw Arrival_FallIn
  dw Arrival_OpenText
  dw Arrival_Text
  dw Arrival_FallOut
  dw Arrival_HoldBlack
  dw Arrival_Handoff
  dw Arrival_OpenVoice
  dw Arrival_Voice
}

; State 0: save the bed scene, show only sprites, start the spin.
Arrival_Init:
{
  REP #$20
  LDA.b $20 : STA.l Arrival_Save20
  LDA.b $22 : STA.l Arrival_Save22
  LDA.b $51 : STA.l Arrival_Save51
  LDA.b $E2 : CLC : ADC.w #$0078 : STA.b $22 ; screen X $78
  LDA.b $E8 : SEC : SBC.w #$0020 : STA.b $20 ; start above the top edge
  LDA.b $E8 : CLC : ADC.w #$00D0 : STA.b $51 ; fall shadow below the screen
  SEP #$20

  LDA.b $5D : STA.l Arrival_Save5D
  LDA.b $5B : STA.l Arrival_Save5B
  LDA.b $5A : STA.l Arrival_Save5A
  LDA.b $4B : STA.l Arrival_Save4B
  LDA.b $4D : STA.l Arrival_Save4D
  LDA.b $1C : STA.l Arrival_Save1C
  LDA.b $1D : STA.l Arrival_Save1D
  LDA.b $1E : STA.l Arrival_Save1E
  LDA.b $1F : STA.l Arrival_Save1F

  LDA.b #$10 : STA.b $1C                  ; main screen: sprites only
  STZ.b $1D : STZ.b $1E : STZ.b $1F
  STZ.b $9A : STZ.b $9B                   ; no color math, no HDMA
  JSR Opening_HideHUD                     ; only Link and the text on screen

  STZ.b $5D : STZ.b $4D : STZ.b $4B       ; leave the bed pose
  LDA.b #$03 : STA.b $5B                  ; falling (LinkOAM fall pose)
  LDA.b #$06 : STA.b $5A                  ; spin frames 6-9

  LDA.b #$08 : STA.l TimeState.Hours      ; same as HouseTag_TelepathicPlea
  LDA.b #$03 : STA.w $012C                ; song $03, same as the plea
  STZ.b $13                               ; display on, brightness 0

  LDA.b #$01 : STA.l Arrival_State
  RTS
}

; State 1: fade in and spin down to screen Y $48.
Arrival_FallIn:
{
  JSR Arrival_FadeInStep
  JSR Arrival_SpinStep
  REP #$20
  INC.b $20
  LDA.b $20 : SEC : SBC.b $E8
  BMI .above
  CMP.w #$0048 : BCC .above
    SEP #$20
    LDA.b #$02 : STA.l Arrival_State
    BRA .draw
  .above
  SEP #$20
  .draw
  JSL Arrival_LinkOAM_Main
  RTS
}

; State 2: open message $1F. Keep the pose still while text is open:
; the text engine blocks Link graphics uploads on its busy frames.
Arrival_OpenText:
{
  LDA.b #$14 : STA.b $1C                  ; BG3 (text) + sprites
  REP #$20
  LDA.w #$001F : STA.w $1CF0              ; "Accept our quest, Link!"
  SEP #$20
  STZ.w $1CD8
  LDA.b #$0C : STA.w $010C                ; text end returns to module $0C
  JSL Arrival_RenderText
  JSL Arrival_LinkOAM_Main
  LDA.b #$03 : STA.l Arrival_State
  RTS
}

; State 3: run the message until it closes ($1CD8 back to 0).
Arrival_Text:
{
  JSL Arrival_RenderText
  JSL Arrival_LinkOAM_Main
  LDA.w $1CD8 : BNE .wait
    LDA.b #$10 : STA.b $1C                ; sprites only again
    LDA.b #$04 : STA.l Arrival_State
  .wait
  RTS
}

; State 4: spin on down while the screen fades out.
Arrival_FallOut:
{
  JSR Arrival_SpinStep
  REP #$20 : INC.b $20 : INC.b $20 : SEP #$20
  JSL Arrival_LinkOAM_Main
  LDA.b $1A : AND.b #$01 : BNE .hold
  LDA.b $13 : BEQ .dark
    DEC.b $13
  .hold
  RTS
  .dark
  STZ.b $1C                               ; nothing on screen while black
  LDA.b #!ArrivalVoicePauseFrames : STA.l Arrival_Timer
  LDA.b #$07 : STA.l Arrival_Next         ; then line A over black
  LDA.b #$05 : STA.l Arrival_State
  RTS
}

; State 5: hold on black for Arrival_Timer frames, then go to Arrival_Next
; (line A after the fall, the bed scene after line A).
Arrival_HoldBlack:
{
  LDA.l Arrival_Timer : DEC A : STA.l Arrival_Timer
  BNE .wait
    LDA.l Arrival_Next : STA.l Arrival_State
  .wait
  RTS
}

; State 7: open line A ($201, Impa) over black: text layer only, no Link.
; Link's bed position is restored first so the text engine puts the box
; low on the screen, like message $1F.
Arrival_OpenVoice:
{
  REP #$20
  LDA.l Arrival_Save20 : STA.b $20
  LDA.l Arrival_Save22 : STA.b $22
  LDA.w #!ArrivalVoiceMsg : STA.w $1CF0
  SEP #$20
  LDA.b #$04 : STA.b $1C                  ; BG3 (text) only
  LDA.b #$0F : STA.b $13                  ; backdrop stays black
  STZ.w $1CD8
  LDA.b #$0C : STA.w $010C                ; text end returns to module $0C
  JSL Arrival_RenderText
  LDA.b #$08 : STA.l Arrival_State
  RTS
}

; State 8: run line A until it closes, then black before the bed scene.
Arrival_Voice:
{
  JSL Arrival_RenderText
  LDA.w $1CD8 : BNE .wait
    STZ.b $1C
    STZ.b $13
    LDA.b #!ArrivalVoiceAfterFrames : STA.l Arrival_Timer
    LDA.b #$06 : STA.l Arrival_Next         ; then Arrival_Handoff (iris on the bed)
    LDA.b #$05 : STA.l Arrival_State
  .wait
  RTS
}

; State 6: restore the bed scene and resume Module07_0F. The iris opens next
; frame, and the house tag goes straight to HouseTag_WakeUpPlayer.
Arrival_Handoff:
{
  LDA.l Arrival_Save1C : STA.b $1C
  LDA.l Arrival_Save1D : STA.b $1D
  LDA.l Arrival_Save1E : STA.b $1E
  LDA.l Arrival_Save1F : STA.b $1F
  ; Color math stays off for the iris. The bedroom loads with CGADSUB=$20 and a
  ; yellow fixed color ($9C/$9D = $30/$50), and the indoor iris
  ; (IrisSpotlight_open, $00F2DC) does not reset the fixed color, so the
  ; masked area outside the circle turned olive instead of black.
  ; HouseTag_WakeUpPlayer still times the wake-up from $9C.
  STZ.b $9A
  LDA.l Arrival_Save5D : STA.b $5D
  LDA.l Arrival_Save5B : STA.b $5B
  LDA.l Arrival_Save5A : STA.b $5A
  LDA.l Arrival_Save4B : STA.b $4B
  LDA.l Arrival_Save4D : STA.b $4D
  REP #$20
  LDA.l Arrival_Save20 : STA.b $20
  LDA.l Arrival_Save22 : STA.b $22
  LDA.l Arrival_Save51 : STA.b $51
  SEP #$20
  JSR Opening_ShowHUD

  LDA.b #$01 : STA.l IntroState           ; plea delivered
  LDA.b #$07 : STA.b $10 : STA.w $010C
  LDA.b #$0F : STA.b $11                  ; Module07_0F landing wipe
  STZ.b $B0                               ; rerun InitSpotlight: iris opens
  LDA.b #$00 : STA.l Arrival_State
  RTS
}

; The HUD shares BG3 with the text box. Blank the HUD buffer ($7EC700, $14A
; bytes; NMI uploads it while $16 != 0) with the empty HUD tile. The clock
; redraw runs from Sprite_Main (modules $07/$09), so it stays blank here.
Opening_HideHUD:
{
  REP #$30
  LDX.w #$0148
  LDA.w #$207F                            ; HUD_TilemapTemplate blank tile
  .loop
    STA.l $7EC700, X
    DEX : DEX : BPL .loop
  SEP #$30
  LDA.b #$01 : STA.b $16
  RTS
}

; Rebuild the HUD from the save (same calls as the menu close path).
Opening_ShowHUD:
{
  JSL RebuildHUD_long
  SEP #$30
  JSL DrawClockToHudLong
  SEP #$30
  LDA.b #$01 : STA.b $16
  RTS
}

Arrival_FadeInStep:
{
  LDA.b $13 : CMP.b #$0F : BCS .done
  LDA.b $1A : AND.b #$01 : BNE .done
    INC.b $13
  .done
  RTS
}

; Same cadence as HandleUnderworldLandingFromPit ($07953D): frames 6-9,
; one step every 4 frames.
Arrival_SpinStep:
{
  LDA.b $1A : AND.b #$03 : BNE .done
  INC.b $5A
  LDA.b $5A : CMP.b #$0A : BCC .done
    LDA.b #$06 : STA.b $5A
  .done
  RTS
}

print "End of opening arrival            ", pc

if !ENABLE_EXPERIMENT_SCENE == 1
  incsrc "experiment.asm"
  print "End of experiment scene           ", pc
endif

assert pc() <= $3AE000, "Opening arrival code crossed $3AE000"
pullpc

endif
