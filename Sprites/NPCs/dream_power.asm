; =========================================================
; Power dream (Dream 2 "The Oracle's Choice")
;
; Canon: Docs/Planning/Status/decisions.org, "Dream structure: one dream per
; pendant, wake in the hut" (Power: Farore goes to Hyrule's king and
; discloses the prison), "Pendant dreams: bit on return, quiet room $00,
; fixed landing, no $1B8" and "Pendant dream arrivals: Power in room $00's
; NE arena". D2.01-D2.06 ($206-$20B) are the words scawful approved on
; 2026-10-15 (Data/dialogue/message_registry.json, owner dream-power).
;
; !ENABLE_DREAM_POWER_SCENE (needs !ENABLE_DREAM_ROOM_SHEETS for the landing
; and !ENABLE_DREAM_WISDOM_SCENE for the scene locks and their release):
;   1. Hut (maple.asm): Dream_Power puts Farore's sheet $55 in sprite slot 3
;      and warps Link to room $00.
;   2. Room load: DreamPower_KingSheet swaps the king's sheet $35 into slot
;      2 (two cache-store hooks below). DreamRoom_Stage (dream_rooms.asm)
;      sets the north-east arena landing, then calls DreamPower_Stage: the
;      king ($D3) and Farore ($D4) as $73 actors, Link hidden and frozen,
;      blank HUD, Farore's colors, BG1 off (Kydreeok's bone body is room
;      $00's only BG1 object), the Wisdom marker.
;   3. Farore (the director) runs DreamPower_Script: she walks up to the
;      king, D2.01-D2.04, turns to the camera, D2.05, then DreamReturn_Begin.
;   4. Hut reload: DreamWisdom_ReleaseLink shows Link; Maple says D2.06 once
;      (maple.asm, Maple_Idle), only after a finished scene.
;
; Fallbacks: as the Wisdom scene. No two free sprite slots -> no staging
; (the landing and the 8 s return as before). A stalled director stops
; holding the dream timer after !DP_Watchdog frames, so the 8 s return still
; fires; that return has no wake line.
; =========================================================

if !ENABLE_DREAM_POWER_SCENE == 1
assert !ENABLE_DREAM_ROOM_SHEETS == 1, "ENABLE_DREAM_POWER_SCENE requires ENABLE_DREAM_ROOM_SHEETS"
assert !ENABLE_DREAM_WISDOM_SCENE == 1, "ENABLE_DREAM_POWER_SCENE requires ENABLE_DREAM_WISDOM_SCENE (scene locks)"

!DP_KingSheet       = $35     ; vanilla king: HyruleDream frame 1, chars $8E/$AE
; In-room spots (room $00, base 0; camera $0100,$0010 from the landing).
; Screen x = X - $100, y = Y - $10. The Triforce floor is screen x 88-167,
; y 88-151; text boxes open at y 144.
!DP_KingX           = $0178   ; frame 1 spans x-8..x+23: centred on x 128
!DP_KingY           = $0060   ; spans y-16..y+15: screen 64-95, above the Triforce
!DP_FaroreX         = $0178
!DP_FaroreY         = $00A0   ; spans y-8..y+19: screen 136-163, below the floor
!DP_LinkScreenY     = $0030   ; hidden Link at screen y 48 (< $78): boxes at the bottom
!DP_FrameKing       = $01     ; Sprite_HyruleDream_Draw frames
!DP_FrameBack       = $07     ; Farore, back to the camera
!DP_FrameBackStepA  = $08
!DP_FrameBackStepB  = $09
!DP_FrameFront      = $0A     ; Farore facing the camera
!DP_WalkSpeed       = $F8     ; 0.5 px per frame up
!DP_Watchdog        = 1200    ; active frames the director holds the timer (scene ~264)
!DreamMsg_PowerFirst = $0206  ; D2.01; D2.02-D2.05 follow

; Script ops: two bytes each (op, argument).
!DP_OpWait          = $00     ; hold for argument frames
!DP_OpWalk          = $01     ; walk up for argument frames
!DP_OpLine          = $02     ; show !DreamMsg_PowerFirst + argument
!DP_OpFrame         = $03     ; set the frame, then the next op at once
!DP_OpEnd           = $04     ; the single exit: dream return

; Text pauses sprites, so each op after a line runs on the first frame
; after its box closes.
DreamPower_Script:
  db !DP_OpWait, $28                      ; 40: the tableau after the fade-in
  db !DP_OpWalk, $30                      ; 48 x 0.5 px: Farore walks 24 px up
  db !DP_OpWait, $10
  db !DP_OpLine, $00                      ; D2.01 Farore
  db !DP_OpWait, $08
  db !DP_OpLine, $01                      ; D2.02 Farore
  db !DP_OpWait, $18                      ; a beat before the king answers
  db !DP_OpLine, $02                      ; D2.03 the king
  db !DP_OpWait, $10
  db !DP_OpLine, $03                      ; D2.04 Farore
  db !DP_OpWait, $20
  db !DP_OpFrame, !DP_FrameFront          ; she turns from the king to us
  db !DP_OpWait, $20
  db !DP_OpLine, $04                      ; D2.05 her own thought
  db !DP_OpWait, $30
  db !DP_OpEnd, $00
.end

; ---------------------------------------------------------
; JSL from DreamRoom_Stage (dream_rooms.asm), Power only, after
; DreamRoom_PowerLanding and before DreamRoom_LoadSheets (so ClearPPU uploads
; the blank HUD). M = 8, X = 8, DB = $09 on entry; M = 8, X = 8 on exit.
DreamPower_Stage:
{
  PHB : PHK : PLB
  ; Two free slots X and X+1 (Kydreeok's slot is freed by its own Prep).
  LDX.b #$00
  .find
    LDA.w SprState, X : ORA.w SprState+1, X : BEQ .stage
    INX : CPX.b #$0F : BCC .find
  PLB
  RTL

  .stage
  LDY.b #$00
  .next_actor
    LDA.b #$08 : STA.w SprState, X        ; init: Prep runs in Sprite_Main
    LDA.b #Sprite_Farore : STA.w SprType, X
    LDA.w .subtype, Y : STA.w SprSubtype, X
    STZ.w SprFloor, X
    LDA.w .x_lo, Y : STA.w SprX, X
    LDA.w .x_hi, Y : CLC : ADC.w $0FB0 : STA.w SprXH, X
    LDA.w .y_lo, Y : STA.w SprY, X
    LDA.w .y_hi, Y : CLC : ADC.w $0FB1 : STA.w SprYH, X
    LDA.b #$FF : STA.w $0BC0, X           ; no room death bit
    STZ.w $0CBA, X                        ; no key drop
    INX : INY : CPY.b #$02 : BCC .next_actor

  REP #$20
  LDA.b $E8 : CLC : ADC.w #!DP_LinkScreenY : STA.b $20 ; X stays the landing's
  LDA.w #!DW_Live : STA.l DreamWisdom_Marker
  LDA.w #$0000 : STA.l DreamWisdom_Watchdog
  SEP #$20

  STZ.b $30 : STZ.b $31                   ; no movement: the camera holds
  STZ.b LinkState : STZ.b $5C             ; drop Link_WarpToRoom's pit state
  LDA.b #$0C : STA.b $4B                  ; Link invisible
  LDA.b #$01
  STA.w $02E4                             ; frozen
  STA.w $0FFC                             ; no menu
  STA.w $037B                             ; no damage
  STA.w $02F9                             ; follower not drawn
  STZ.w $04A0                             ; no floor indicator
  ; Step 4 (Module07_15_04) sets $1C/$1D from Underworld_SubscreenEnable
  ; by $0414: room $00's 3 puts BG1 on the main screen, 0 turns BG1 off.
  ; The translucency setup reads $0414 too: 0 and 3 give the same $9A. The
  ; hut header sets $0414 again.
  STZ.w $0414
  LDA.b #!DW_FaroreAux1 : STA.w $0AAD     ; Farore's overworld colors (OBJ5)
  LDA.b #$00 : STA.l SongTintTimer        ; a running tint rewrites $9A
  STA.l DreamWisdom_Flash
  JSR DreamWisdom_BlankHUD
  PLB
  RTL

  .subtype
  db !DreamPower_SubKing, !DreamPower_SubFarore
  .x_lo
  db !DP_KingX&$FF, !DP_FaroreX&$FF
  .x_hi
  db !DP_KingX>>8, !DP_FaroreX>>8
  .y_lo
  db !DP_KingY&$FF, !DP_FaroreY&$FF
  .y_hi
  db !DP_KingY>>8, !DP_FaroreY>>8
}

; ---------------------------------------------------------
; JMP from Sprite_HyruleDream_Prep (subtype >= $D3). X = slot, DB = $30.
DreamPower_Prep:
{
  STZ.w SprTimerB, X
  STZ.w SprAction, X                      ; script position
  STZ.w SprMiscB, X                       ; walk frames left
  LDA.w SprSubtype, X : CMP.b #!DreamPower_SubFarore : BEQ .farore
    LDA.b #!DP_FrameKing : STA.w SprFrame, X
    ; Frame 1 is four 16x16 pieces; $73 reserves ($0E40 & $1F) + 1 = 3.
    LDA.w $0E40, X : AND.b #$E0 : ORA.b #$03 : STA.w $0E40, X
    RTS
  .farore
  LDA.b #!DP_FrameBack : STA.w SprFrame, X
  RTS
}

; JMP from Sprite_HyruleDream_Main (subtype >= $D3); active frames only.
DreamPower_Main:
{
  JSL DreamReturn_IsDreaming : BCS .dreaming
    STZ.w SprState, X                     ; never outside the dream
    RTS
  .dreaming
  LDA.w SprSubtype, X : CMP.b #!DreamPower_SubFarore : BEQ .director
    RTS                                   ; the king: drawn only
  .director
  ; Hold the 8 s dream timer, for the first !DP_Watchdog frames only.
  REP #$20
  LDA.l DreamWisdom_Watchdog : CMP.w #!DP_Watchdog : BCS .watchdog_out
    INC A : STA.l DreamWisdom_Watchdog
    SEP #$20
    LDA.b #!DreamReturn_Ticks : STA.w DreamReturnTimer
  .watchdog_out
  SEP #$20
  LDA.b #$01 : STA.w $037B                ; Ancilla_TerminateSelectInteractives
                                          ; clears it after Stage

  LDA.w SprMiscB, X : BEQ .script
    %PlayAnimation(!DP_FrameBackStepA, !DP_FrameBackStepB, 8)
    LDA.b #!DP_WalkSpeed : STA.w SprYSpeed, X
    JSL Sprite_MoveVert
    DEC.w SprMiscB, X : BNE .done
      STZ.w SprYSpeed, X
      LDA.b #!DP_FrameBack : STA.w SprFrame, X
    RTS

  .script
  LDA.w SprTimerA, X : BNE .done
  .next_op
  LDY.w SprAction, X
  CPY.b #DreamPower_Script_end-DreamPower_Script : BCS .done ; after the end
  INC.w SprAction, X : INC.w SprAction, X
  LDA.w DreamPower_Script, Y : STA.b $00  ; op
  LDA.w DreamPower_Script+1, Y            ; argument
  LDY.b $00
  CPY.b #!DP_OpWait : BNE +
    STA.w SprTimerA, X
    RTS
  +
  CPY.b #!DP_OpWalk : BNE +
    STA.w SprMiscB, X
    RTS
  +
  CPY.b #!DP_OpLine : BNE +
    CLC : ADC.b #!DreamMsg_PowerFirst&$FF
    LDY.b #!DreamMsg_PowerFirst>>8
    JSL Sprite_ShowMessageUnconditional
    RTS
  +
  CPY.b #!DP_OpFrame : BNE .end
    STA.w SprFrame, X
    BRA .next_op

  ; The single exit. $10 = $07 and $11 = 0 here, as DreamReturn_Begin needs.
  .end
  STZ.w DreamReturnTimer                  ; as when the timer fires
  REP #$20
  LDA.w #!DreamPower_WakeLive : STA.l DreamPower_WakeLine
  SEP #$20
  PHX : JSR DreamReturn_Begin : PLX       ; Begin clobbers X
  .done
  RTS
}

; ---------------------------------------------------------
; The king's sheet in sprite slot 2. Group $57 (room $00) loads $27 there,
; so the slot-2 cache store takes the king's sheet instead while the Power
; dream loads room $00: LoadTransAuxGFX in Module07_15 step 2 (the upload
; buffer) and InitializeTilesets in DreamRoom_LoadSheets (VRAM). Pattern:
; HouseVillager_LoadSheet (Core/part00.asm, slot 1). The hut's group sets
; all four slots, so the swap ends with the dream.
pushpc
; LoadTransAuxGFX .skip_spr2 store: STA.l $7EC2FE (M = 8, X = 16, DB = $00)
org $00D757 ; @hook module=Sprites name=DreamPower_KingSheetTransition kind=jsl target=DreamPower_KingSheet expected_m=8
  JSL DreamPower_KingSheet
assert pc() == $00D75B
; InitializeTilesets .dont_change_c store: STA.l $7EC2FE (M = 8, X = 16, DB = $00)
org $00E1DE ; @hook module=Sprites name=DreamPower_KingSheetInitial kind=jsl target=DreamPower_KingSheet expected_m=8
  JSL DreamPower_KingSheet
assert pc() == $00E1E2
pullpc

; A = the group's slot-2 sheet. M = 8; X and Y (16-bit here) preserved.
DreamPower_KingSheet:
{
  PHA
  JSL DreamReturn_IsDreaming : BCC .keep  ; A only
  LDA.w CurrentDream : CMP.b #$01 : BNE .keep
  LDA.b $A0 : ORA.b $A1 : BNE .keep       ; room $00 being loaded
    PLA
    LDA.b #!DP_KingSheet
    BRA .store
  .keep
  PLA
  .store
  STA.l $7EC2FE
  RTL
}
endif
