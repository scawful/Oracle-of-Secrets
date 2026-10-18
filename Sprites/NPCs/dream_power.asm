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
;
; The script engine (DreamPower_Main) also runs the Wisdom fall
; (!ENABLE_DREAM_WISDOM_FALL, shots 3-5 in the great hall; decisions.org
; "Wisdom dream shots 3-5 stay in the great hall"): at the end of shot 2
; DreamWisdom_End turns Farore into this director ($D4) at
; DreamPower_Script_wisdom. Its actors: the Captain's men ($D5-$D7) and
; Kydrog's black silhouette ($D8, his own sheet $42 in slot 1).
;
; !ENABLE_DREAM_BED_WAKE: the script's end leaves the wake word, and the hut
; reload tucks Link into Maple's bed (DreamWake_TuckIntoBed); Maple sits him
; up and says the dream's line (maple.asm). Off, the line plays at the door.
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
if !ENABLE_DREAM_WISDOM_FALL == 1
assert !ENABLE_DREAM_WISDOM_SCENE == 1, "ENABLE_DREAM_WISDOM_FALL requires ENABLE_DREAM_WISDOM_SCENE"
!DP_OpFadeOut       = $05     ; brightness ($13) to 0 over argument frames
!DP_OpFadeIn        = $06     ; brightness back to $0F over argument frames
!DP_OpSpawnMen      = $07     ; the Captain's three men appear
!DP_OpVanish        = $08     ; man <argument> blinks out
!DP_OpSfx           = $09     ; sound <argument> on SFX2 ($012E)
!DP_OpFlash         = $0A     ; white flash on (1) or off (0)
!DP_OpFall          = $0B     ; the Captain becomes Kydrog's silhouette

!DP_FrameEmpty      = $0B     ; Sprite_HyruleDream_Draw frames (hyrule_dream.asm)
!DP_FrameSilhouette = $0C
!DP_FrameMan        = $02     ; the HyruleDream soldier, standing
!DP_VanishFrames    = $18     ; 24 frames of blinking, then gone
!DP_SilhouettePal   = $7EC6C2 ; OBJ palette 6 colors 1-15 (current; target at -$200)
; In-room spots of his men (room $51, around the Captain at $F0,$9C)
!DP_ManX0           = $00D0   ; left of him
!DP_ManY0           = $00A8
!DP_ManX1           = $0110   ; right of him (Farore's spot in shot 2)
!DP_ManY1           = $00A8
!DP_ManX2           = $00F0   ; in front of him
!DP_ManY2           = $00C4
endif
if !ENABLE_DREAM_BED_WAKE == 1
; Maple's bed in the hut (room $0F, base $1E00,$0000): Sprite_PutLinkToSleep
; puts Link 24 px right of where he stands to talk to Maple.
!DreamWake_BedX     = $1F78
!DreamWake_BedY     = $0140
endif

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
if !ENABLE_DREAM_WISDOM_FALL == 1
; Wisdom shots 3-5 in the great hall. DreamWisdom_End starts it after D1.02
; (and its 48-frame hold). Lines: !DreamMsg_PowerFirst + 6 = $20C, + 7 = $20D.
.wisdom
  db !DP_OpWait, $10
  db !DP_OpFadeOut, $20                   ; years pass: to black
  db !DP_OpFrame, !DP_FrameEmpty          ; Farore leaves (the director stays)
  db !DP_OpSpawnMen, $00                  ; his men stand with him
  db !DP_OpWait, $04                      ; their Prep runs while it is black
  db !DP_OpFadeIn, $20
  db !DP_OpWait, $30
  db !DP_OpVanish, $01                    ; the men fade one by one
  db !DP_OpWait, $28
  db !DP_OpVanish, $00
  db !DP_OpWait, $28
  db !DP_OpVanish, $02
  db !DP_OpWait, $30                      ; the Captain alone
  db !DP_OpLine, $06                      ; D1.03 the prison
  db !DP_OpWait, $10
  db !DP_OpLine, $07                      ; D1.04 the prison
  db !DP_OpWait, $20
  db !DP_OpSfx, $05                       ; his sword hits the floor
  db !DP_OpFlash, $01
  db !DP_OpFall, $00                      ; Kydrog's silhouette in his place
  db !DP_OpWait, $0A
  db !DP_OpFlash, $00
  db !DP_OpWait, $40
  db !DP_OpEnd, $00
endif
.end
assert DreamPower_Script_end-DreamPower_Script < $FF, "dream scripts must fit an 8-bit index"

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
; Sprite init (SpritePrep_ResetProperties) has cleared the timers, SprAction,
; SprMiscA/B/D and SprFrame; only the subtype tells the actors apart.
DreamPower_Prep:
{
  STZ.w SprTimerB, X
  STZ.w SprAction, X                      ; script position
  STZ.w SprMiscB, X                       ; continuous-op frames left
  LDA.w SprSubtype, X : CMP.b #!DreamPower_SubFarore : BEQ .farore
  if !ENABLE_DREAM_WISDOM_FALL == 1
    CMP.b #!DreamPower_SubSilhouette : BEQ .silhouette
    CMP.b #!DreamPower_SubMan0 : BCS .man
  endif
    LDA.b #!DP_FrameKing : STA.w SprFrame, X
    ; Frame 1 is four 16x16 pieces; $73 reserves ($0E40 & $1F) + 1 = 3.
    LDA.w $0E40, X : AND.b #$E0 : ORA.b #$03 : STA.w $0E40, X
    RTS
  .farore
  LDA.b #!DP_FrameBack : STA.w SprFrame, X
  RTS
  if !ENABLE_DREAM_WISDOM_FALL == 1
    .man
    LDA.b #!DP_FrameMan : STA.w SprFrame, X
    RTS
    .silhouette
    LDA.b #!DP_FrameSilhouette : STA.w SprFrame, X
    LDA.w $0E40, X : AND.b #$E0 : ORA.b #$05 : STA.w $0E40, X ; 6 pieces
    RTS
  endif
}

; JMP from Sprite_HyruleDream_Main (subtype >= $D3); active frames only.
DreamPower_Main:
{
  JSL DreamReturn_IsDreaming : BCS .dreaming
    STZ.w SprState, X                     ; never outside the dream
    RTS
  .dreaming
  LDA.w SprSubtype, X : CMP.b #!DreamPower_SubFarore : BEQ .director
  if !ENABLE_DREAM_WISDOM_FALL == 1
    CMP.b #!DreamPower_SubSilhouette : BCS .drawn_only
    CMP.b #!DreamPower_SubMan0 : BCS .man
  endif
  .drawn_only
  RTS                                     ; the king, the silhouette

  if !ENABLE_DREAM_WISDOM_FALL == 1
    ; One of the Captain's men. DreamPower_OpVanish sets SprMiscB: blink
    ; (2 frames on, 2 off), then gone.
    .man
    LDA.w SprMiscB, X : BEQ .drawn_only
      DEC.w SprMiscB, X : BEQ .gone
      LDA.w SprMiscB, X : AND.b #$02 : BEQ .hide
        LDA.b #!DP_FrameMan : STA.w SprFrame, X
        RTS
      .hide
      LDA.b #!DP_FrameEmpty : STA.w SprFrame, X
      RTS
    .gone
    STZ.w SprState, X
    RTS
  endif

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

  ; Continuous ops run for SprMiscB frames: walk up (SprMiscD 0) or, in the
  ; Wisdom fall, a brightness fade out (1) or in (2), one step per 2 frames.
  LDA.w SprMiscB, X : BEQ .script
  if !ENABLE_DREAM_WISDOM_FALL == 1
    LDA.w SprMiscD, X : BEQ .walk
    CMP.b #$01 : BEQ .fade_out
      LDA.w SprMiscB, X : LSR A : BCS .tick
      LDA.b $13 : CMP.b #$0F : BCS .tick
      INC.b $13
      BRA .tick
    .fade_out
      LDA.w SprMiscB, X : LSR A : BCS .tick
      LDA.b $13 : BEQ .tick
      DEC.b $13
    .tick
    DEC.w SprMiscB, X
    RTS
    .walk
  endif
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
  LDA.w DreamPower_Script+1, Y : STA.b $05 ; argument (JumpTableLocal uses $00-$03)
  LDA.w DreamPower_Script, Y              ; op
  JSL JumpTableLocal

  dw DreamPower_OpWait                    ; 0
  dw DreamPower_OpWalk                    ; 1
  dw DreamPower_OpLine                    ; 2
  dw DreamPower_OpFrame                   ; 3
  dw DreamPower_OpEnd                     ; 4
  if !ENABLE_DREAM_WISDOM_FALL == 1
    dw DreamPower_OpFadeOut               ; 5
    dw DreamPower_OpFadeIn                ; 6
    dw DreamPower_OpSpawnMen              ; 7
    dw DreamPower_OpVanish                ; 8
    dw DreamPower_OpSfx                   ; 9
    dw DreamPower_OpFlash                 ; A
    dw DreamPower_OpFall                  ; B
  endif

  .done
  RTS
}

; Script ops: X = director slot, $05 = argument, M = 8, X = 8, DB = $30.
DreamPower_OpWait:
{
  LDA.b $05 : STA.w SprTimerA, X
  RTS
}

DreamPower_OpWalk:
{
  LDA.b $05 : STA.w SprMiscB, X
  STZ.w SprMiscD, X
  RTS
}

; The next op runs on the first frame after the box closes (text pauses sprites).
DreamPower_OpLine:
{
  LDA.b $05 : CLC : ADC.b #!DreamMsg_PowerFirst&$FF
  LDY.b #!DreamMsg_PowerFirst>>8
  JSL Sprite_ShowMessageUnconditional
  RTS
}

DreamPower_OpFrame:
{
  LDA.b $05 : STA.w SprFrame, X
  JMP DreamPower_Main_next_op
}

; The single exit. $10 = $07 and $11 = 0 here, as DreamReturn_Begin needs.
DreamPower_OpEnd:
{
  LDA.b #$FF : STA.w SprAction, X         ; past every script
  STZ.w DreamReturnTimer                  ; as when the timer fires
  REP #$20
  LDA.w #!DreamPower_WakeLive : STA.l DreamPower_WakeLine
  SEP #$20
  PHX : JSR DreamReturn_Begin : PLX       ; Begin clobbers X
  RTS
}

if !ENABLE_DREAM_WISDOM_FALL == 1
DreamPower_OpFadeOut:
{
  LDA.b $05 : STA.w SprMiscB, X
  LDA.b #$01 : STA.w SprMiscD, X
  RTS
}

DreamPower_OpFadeIn:
{
  LDA.b $05 : STA.w SprMiscB, X
  LDA.b #$02 : STA.w SprMiscD, X
  RTS
}

; The three men in free slots (Prep runs in the next Sprite_Main).
DreamPower_OpSpawnMen:
{
  PHX
  LDY.b #$00                              ; man
  LDX.b #$00                              ; slot
  .find
    LDA.w SprState, X : BNE .busy
      LDA.b #$08 : STA.w SprState, X
      LDA.b #Sprite_Farore : STA.w SprType, X
      TYA : CLC : ADC.b #!DreamPower_SubMan0 : STA.w SprSubtype, X
      STZ.w SprFloor, X
      LDA.w .x_lo, Y : STA.w SprX, X
      LDA.w .x_hi, Y : CLC : ADC.w $0FB0 : STA.w SprXH, X
      LDA.w .y_lo, Y : STA.w SprY, X
      LDA.w .y_hi, Y : CLC : ADC.w $0FB1 : STA.w SprYH, X
      LDA.b #$FF : STA.w $0BC0, X         ; no room death bit
      STZ.w $0CBA, X                      ; no key drop
      INY : CPY.b #$03 : BCS .out
    .busy
    INX : CPX.b #$10 : BCC .find
  .out
  PLX
  RTS

  .x_lo
  db !DP_ManX0&$FF, !DP_ManX1&$FF, !DP_ManX2&$FF
  .x_hi
  db !DP_ManX0>>8, !DP_ManX1>>8, !DP_ManX2>>8
  .y_lo
  db !DP_ManY0&$FF, !DP_ManY1&$FF, !DP_ManY2&$FF
  .y_hi
  db !DP_ManY0>>8, !DP_ManY1>>8, !DP_ManY2>>8
}

DreamPower_OpVanish:
{
  LDA.b $05 : CLC : ADC.b #!DreamPower_SubMan0 : STA.b $06
  LDY.b #$0F
  .find
    LDA.w SprState, Y : BEQ .next
    LDA.w SprType, Y : CMP.b #Sprite_Farore : BNE .next
    LDA.w SprSubtype, Y : CMP.b $06 : BNE .next
      LDA.b #!DP_VanishFrames : STA.w SprMiscB, Y
      RTS
    .next
    DEY : BPL .find
  RTS
}

DreamPower_OpSfx:
{
  LDA.b $05 : STA.w $012E
  RTS
}

DreamPower_OpFlash:
{
  LDA.b $05 : BEQ .off
    JSR DreamWisdom_FlashOn
    RTS
  .off
  JSR DreamWisdom_FlashOff
  RTS
}

; The Captain ($D1) becomes Kydrog's silhouette: his pirate frame from sheet
; $42 (slot 1, Dream_Wisdom) drawn in OBJ palette 6, set to black here. The
; hut reload loads every palette again.
DreamPower_OpFall:
{
  LDY.b #$0F
  .find
    LDA.w SprState, Y : BEQ .next
    LDA.w SprType, Y : CMP.b #Sprite_Farore : BNE .next
    LDA.w SprSubtype, Y : CMP.b #!DreamWisdom_SubCaptain : BNE .next
      LDA.b #!DreamPower_SubSilhouette : STA.w SprSubtype, Y
      LDA.b #!DP_FrameSilhouette : STA.w SprFrame, Y
      LDA.w $0E40, Y : AND.b #$E0 : ORA.b #$05 : STA.w $0E40, Y ; 6 pieces
      BRA .palette
    .next
    DEY : BPL .find
  .palette
  PHX
  REP #$20
  LDX.b #$1C
  LDA.w #$0000
  .black
    STA.l !DP_SilhouettePal, X
    STA.l !DP_SilhouettePal-$200, X       ; fade target ($7EC300 copy)
    DEX : DEX : BPL .black
  SEP #$20
  PLX
  LDA.b #$01 : STA.b $15                  ; upload the palettes in NMI
  RTS
}
endif

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

if !ENABLE_DREAM_BED_WAKE == 1
; ---------------------------------------------------------
; JSR from DreamWisdom_ReleaseLink: the hut reload after a finished scene,
; at the end of the room's sprite list (Underworld_ResetSprites), where the
; vanilla intro calls Link_TuckIntoBed ($07:9A2C, after $02834C). Same state
; at the hut's bed: sleeping ($5D = $16), snoring ($037C = 0), the blanket.
; Maple sits him up later (maple.asm, Maple_WakeLink). M = 8, X = 8, DB = $30.
DreamWake_TuckIntoBed:
{
  REP #$20
  LDA.w #!DreamWake_BedY : STA.b $20 : STA.w $0FC4
  LDA.w #!DreamWake_BedX : STA.b $22 : STA.w $0FC2
  SEP #$20
  LDA.b #$16 : STA.b LinkState            ; asleep in bed
  STZ.w $037C : STZ.w $037D
  LDA.b #$03 : STA.w $0374
  LDA.b #$20 : JSL AncillaAdd_Blanket     ; ancilla slot 0, at the vanilla bed
  ; Move it onto Link, as Sprite_PutLinkToSleep (maple.asm) does.
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0004
  SEP #$20
  STA.w $0BFA : XBA : STA.w $0C0E
  REP #$20
  LDA.b $22 : SEC : SBC.w #$0008
  SEP #$20
  STA.w $0C04 : XBA : STA.w $0C18
  RTS
}
endif
endif
