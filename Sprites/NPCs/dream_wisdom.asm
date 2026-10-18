; =========================================================
; Wisdom dream, shots 1-2 (Dream 1 "The Sealing War")
;
; Canon: Docs/Planning/Status/decisions.org, "Kydrog-was-the-guardian reveal
; is a dream" and "Dream structure: one dream per pendant, wake in the hut"
; (storyboard dream1_sealing_war_storyboard_2026-09-26.md). D1.01 ($204) and
; D1.02 ($205) are the words scawful approved on 2026-10-15
; (Data/dialogue/message_registry.json, owner dream-wisdom).
;
; !ENABLE_DREAM_WISDOM_SCENE (needs !ENABLE_DREAM_RETURN):
;   1. Hut (maple.asm): Maple shows D1.01 over the sleeping Link, then
;      Dream_Wisdom puts Farore's sheet $55 in sprite slot 3 and warps Link
;      to the great hall, room $51.
;   2. Room load (Core/part00.asm, Part00_RoomSprites end of list):
;      DreamWisdom_Stage adds the Captain ($D1) and Farore ($D2) as $73
;      actors, sets the camera, hides and freezes Link, hides any follower,
;      blanks the HUD and loads the hall's BG sheets (DreamRoom_LoadSheets,
;      dream_rooms.asm), all before the fade-in.
;   3. Farore (the director) holds, walks to the Captain, a white flash,
;      D1.02, then DreamReturn_Begin from DreamWisdom_End (the single exit;
;      shot 3 hooks in there later).
;   4. DreamReturn_Begin calls DreamWisdom_Release (input back, flash off).
;      Link stays hidden through the mirror fade; DreamWisdom_ReleaseLink
;      shows him again when the hut room loads.
;
; Fallbacks: no free sprite slots -> no staging, the dream return as before
; (Link visible at the landing in $51). A stalled director stops holding the
; dream timer after !DW_Watchdog frames, so the 8 s return still fires.
;
; Never write the camera ($E0-$E8) from sprite code: Module07_Underworld
; restores it after Sprite_Main. The Captain is a stand-in (the HyruleDream
; soldier, hyrule_dream.asm frame 3); swap the art through !DW_FrameCaptain.
; =========================================================

if !ENABLE_DREAM_WISDOM_SCENE == 1
assert !ENABLE_DREAM_RETURN == 1, "ENABLE_DREAM_WISDOM_SCENE requires ENABLE_DREAM_RETURN"

!DW_Room            = $51     ; the great hall (attract card 3, entrance $74)
!DW_CamX            = $0080   ; in-room BG2 camera: view x 128-383, y 72-295
!DW_CamY            = $0048
!DW_LinkX           = $0100   ; hidden Link at screen (128,48); 48 < $78, so
!DW_LinkY           = $0078   ; text boxes default to the bottom ($6244)
!DW_CaptainX        = $00F0   ; in-room actor spots
!DW_CaptainY        = $009C
!DW_FaroreX         = $010C
!DW_FaroreY         = $0096
!DW_Live            = $D1A5   ; DreamWisdom_Marker while the scene owns Link
!DW_Watchdog        = 1200    ; active frames the director holds the timer
!DW_FrameCaptain    = $03     ; Sprite_HyruleDream_Draw frames
!DW_FrameFarore     = $04
!DW_FrameFaroreStep = $05
!DW_FrameFaroreReach = $06   ; new tiles at dream $CE and $F1 (LoadReachGfx)
!DW_SprBufSlot3     = $7F1800 ; upload buffer, slot 3 = OBJ chars $1C0-$1FF
!DW_FaroreAux1      = $03     ; OBJ5 1-7: Farore's overworld colors (OW $2A/$80)
!DW_HoldFrames      = $28     ; 40 frames before Farore walks
!DW_WalkFrames      = $18     ; 24 frames x 0.5 px = 12 px west
!DW_WalkSpeed       = $F8
!DW_FlashFrames     = $0A
!DW_LineDelay       = $08     ; flash off -> D1.02
!DW_EndFrames       = $30     ; D1.02 closed -> dream return

; ---------------------------------------------------------
; JSL from Part00_RoomSprites .end_of_list, every underworld room load.
; M = 8, X = 8, DB = $09, $00 = list pointer, $02 = next free slot.
DreamWisdom_Stage:
{
  PHB : PHK : PLB
  LDA.b $10 : CMP.b #$07 : BNE .release
  JSL DreamReturn_IsDreaming : BCC .release
  LDA.w CurrentDream : BNE .release       ; Wisdom only
  LDA.w $048F : BNE .release              ; room being loaded
  LDA.w $048E : CMP.b #!DW_Room : BNE .release
  LDX.b $02 : CPX.b #$0F : BCC .stage     ; needs slots X and X+1
  .release
  JSR DreamWisdom_ReleaseLink
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
  STX.b $02

  ; Room base = $0FB0/$0FB1 << 8 (kept on the stack: $00 is the list
  ; pointer). Module07_15 step 4 copies $E2/$E8 to BG1.
  REP #$20
  LDA.w $0FB0 : AND.w #$00FF : XBA : PHA
  CLC : ADC.w #!DW_CamX : STA.b $E2
  PLA : CLC : ADC.w #!DW_LinkX : STA.b $22
  LDA.w $0FB1 : AND.w #$00FF : XBA : PHA
  CLC : ADC.w #!DW_CamY : STA.b $E8
  PLA : CLC : ADC.w #!DW_LinkY : STA.b $20
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
  ; Room $51's header loads aux1 $0E (magenta hair, olive dress).
  ; Palettes_Load_SpriteAux1 reads $0AAD later in this Module07_15 step
  ; ($02A276), so OBJ5 fades in with her colors; the hut header resets it.
  LDA.b #!DW_FaroreAux1 : STA.w $0AAD
  LDA.b #$00 : STA.l SongTintTimer        ; a running tint rewrites $9A
  STA.l DreamWisdom_Flash
  JSR DreamWisdom_BlankHUD
  JSR DreamWisdom_LoadReachGfx
  ; Room $51 would keep the hut's BG sheets (slot 5 $23 draws the thrones
  ; as stoves). Today $0AA2 = $02 = entrance $74: 00 01 10 06 0E 1F 18 0F.
  ; The blank HUD above is what DreamRoom_ClearPPU uploads.
  JSL DreamRoom_LoadSheets                ; dream_rooms.asm
  PLB
  RTL

  .subtype
  db !DreamWisdom_SubCaptain, !DreamWisdom_SubFarore
  .x_lo
  db !DW_CaptainX&$FF, !DW_FaroreX&$FF
  .x_hi
  db !DW_CaptainX>>8, !DW_FaroreX>>8
  .y_lo
  db !DW_CaptainY&$FF, !DW_FaroreY&$FF
  .y_hi
  db !DW_CaptainY>>8, !DW_FaroreY>>8
}

; Farore's reach pose (frame !DW_FrameFaroreReach) uses sheet $55's empty
; cells: dream chars $CE,$CF,$DE,$DF (16x16 body) and $F1 (8x8 arm).
; Module07_15 step 3 ran LoadNewSpriteGFXSet earlier in this frame: it fills
; the upload buffer $7F0000-$7F1FFF (sheet $55 in slot 3: low 3bpp->4bpp,
; plane 3 = 0). Graphics_IncrementalVRAMUpload then sends one $200-byte
; chunk per frame ($0412 = 0-15) to VRAM words $5000-$5FFF; slot 3 is
; chunks 12-15, during the fade-in. So the tiles go into the buffer, not
; VRAM: a direct VRAM write would be overwritten by those chunks. Nothing in
; the scene reloads sprite sheets; the hut reload rebuilds the buffer.
; M = 8, X = 8 on entry and exit. A, X clobbered (InitializeTilesets follows).
DreamWisdom_LoadReachGfx:
{
  LDA.l LASTSPRSET3 : CMP.b #$55 : BNE .done ; only over Farore's sheet
  REP #$30
  LDX.w #$003E
  .row
    ; asar math is left to right: keep the parentheses
    LDA.l DreamWisdom_ReachGfx+$00, X : STA.l !DW_SprBufSlot3+($0E*$20), X ; $CE,$CF
    LDA.l DreamWisdom_ReachGfx+$40, X : STA.l !DW_SprBufSlot3+($1E*$20), X ; $DE,$DF
    CPX.w #$0020 : BCS .next
      LDA.l DreamWisdom_ReachGfx+$80, X : STA.l !DW_SprBufSlot3+($31*$20), X ; $F1
    .next
    DEX : DEX : BPL .row
  SEP #$30
  .done
  RTS
}

; 4bpp, plane 3 = 0. Built from gfx/farore_reach.txt by
; Scripts/Generate/pixels_to_4bpp.py (run it with --check in tests).
; Order: $CE,$CF | $DE,$DF | $F1.
DreamWisdom_ReachGfx:
  incbin "gfx/farore_reach.bin"
.end
assert DreamWisdom_ReachGfx_end-DreamWisdom_ReachGfx == $A0, "farore_reach.bin: $CE/$CF, $DE/$DF, $F1 = 160 bytes"

; Any room load the scene does not stage: give Link back after the scene.
; This is also the seam for D1.05's "just woke" marker.
DreamWisdom_ReleaseLink:
{
  REP #$20
  LDA.l DreamWisdom_Marker : CMP.w #!DW_Live
  SEP #$20                                ; SEP keeps Z
  BNE .done
    STZ.b $4B
    STZ.w $02E4 : STZ.w $0FFC : STZ.w $037B : STZ.w $02F9
    LDA.b #$00 : STA.l DreamWisdom_Marker : STA.l DreamWisdom_Marker+1
    ; Sprite_CancelHookshot (message boxes, barrier sprites) puts Link back
    ; at $0FC2/$0FC4. They still hold the dream spot until Link_Main runs
    ; again, so Maple's first-frame wake line put him there, outside the
    ; hut (Mesen2 write trace on $20-$23, 2026-10-18; same fix as
    ; HouseVillager_Say, Core/part00.asm). The entrance load has already
    ; set $20/$22 to the hut door.
    REP #$20
    LDA.b $22 : STA.w $0FC2
    LDA.b $20 : STA.w $0FC4
    SEP #$20
  .done
  RTS
}

; First thing in DreamReturn_Begin, on every path (scene end, watchdog,
; stale timer). $4B and the marker stay set, so Link stays hidden through
; Module07_19 and DreamWisdom_ReleaseLink shows him on the hut reload.
DreamWisdom_Release:
{
  REP #$20
  LDA.l DreamWisdom_Marker : CMP.w #!DW_Live
  SEP #$20                                ; SEP keeps Z
  BNE .done
    STZ.w $02E4 : STZ.w $0FFC : STZ.w $037B
    JSR DreamWisdom_FlashOff
  .done
  RTS
}

; ---------------------------------------------------------
; JMP from Sprite_HyruleDream_Prep (subtype >= $D1). X = slot, DB = $30.
DreamWisdom_Prep:
{
  STZ.w SprTimerB, X
  LDA.w SprSubtype, X : CMP.b #!DreamWisdom_SubFarore : BEQ .farore
    LDA.b #!DW_FrameCaptain : STA.w SprFrame, X
    STZ.w SprAction, X
    RTS
  .farore
  LDA.b #!DW_FrameFarore : STA.w SprFrame, X
  LDA.b #$01 : STA.w SprAction, X
  LDA.b #!DW_HoldFrames : STA.w SprTimerA, X ; ticks only while $11 = 0
  LDA.b #!DW_WalkFrames : STA.w SprMiscA, X
  RTS
}

; JMP from Sprite_HyruleDream_Main (subtype >= $D1); active frames only.
DreamWisdom_Main:
{
  JSL DreamReturn_IsDreaming : BCS .dreaming
    STZ.w SprState, X                     ; never outside the dream
    RTS
  .dreaming
  LDA.w SprSubtype, X : CMP.b #!DreamWisdom_SubFarore : BEQ .director
    RTS                                   ; Captain: drawn only
  .director
  ; Hold the 8 s dream timer, for the first !DW_Watchdog frames only: a
  ; stalled state must not keep a frozen Link in the dream.
  REP #$20
  LDA.l DreamWisdom_Watchdog : CMP.w #!DW_Watchdog : BCS .watchdog_out
    INC A : STA.l DreamWisdom_Watchdog
    SEP #$20
    LDA.b #!DreamReturn_Ticks : STA.w DreamReturnTimer
  .watchdog_out
  SEP #$20
  LDA.b #$01 : STA.w $037B                ; Ancilla_TerminateSelectInteractives
                                          ; clears it after Stage

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw DreamWisdom_Idle                     ; 0
  dw DreamWisdom_Hold                     ; 1
  dw DreamWisdom_Approach                 ; 2
  dw DreamWisdom_Flashing                 ; 3
  dw DreamWisdom_Line                     ; 4
  dw DreamWisdom_AfterLine                ; 5
  dw DreamWisdom_End                      ; 6

  DreamWisdom_Idle:
  {
    RTS
  }

  DreamWisdom_Hold:
  {
    LDA.w SprTimerA, X : BNE .wait
      INC.w SprAction, X
    .wait
    RTS
  }

  ; Farore walks west to the Captain and touches the blade.
  DreamWisdom_Approach:
  {
    %PlayAnimation(!DW_FrameFarore, !DW_FrameFaroreStep, 8)
    LDA.b #!DW_WalkSpeed : STA.w SprXSpeed, X
    JSL Sprite_MoveHoriz
    DEC.w SprMiscA, X : BNE .walk
      STZ.w SprXSpeed, X
      LDA.b #!DW_FrameFaroreReach : STA.w SprFrame, X ; hand on his shoulder
      JSR DreamWisdom_FlashOn
      LDA.b #!DW_FlashFrames : STA.w SprTimerA, X
      INC.w SprAction, X
    .walk
    RTS
  }

  DreamWisdom_Flashing:
  {
    LDA.w SprTimerA, X : BNE .wait
      JSR DreamWisdom_FlashOff
      LDA.b #!DW_LineDelay : STA.w SprTimerA, X
      INC.w SprAction, X
    .wait
    RTS
  }

  ; The next state runs on the first frame after the box closes.
  DreamWisdom_Line:
  {
    LDA.w SprTimerA, X : BNE .wait
      %ShowUnconditionalMessage(!DreamMsg_WisdomFarore)
      INC.w SprAction, X
    .wait
    RTS
  }

  DreamWisdom_AfterLine:
  {
    LDA.b #!DW_EndFrames : STA.w SprTimerA, X
    INC.w SprAction, X
    RTS
  }

  ; The single exit. $10 = $07 and $11 = 0 here, as DreamReturn_Begin needs.
  DreamWisdom_End:
  {
    LDA.w SprTimerA, X : BNE .wait
      STZ.w SprAction, X
      STZ.w DreamReturnTimer              ; as when the timer fires
      PHX : JSR DreamReturn_Begin : PLX   ; Begin clobbers X
    .wait
    RTS
  }
}

; JSL from HUD_Update (menu_hud.asm) and HUD_ClockDisplay (time_system.asm):
; carry set while the scene owns Link, so they leave the blanked HUD alone.
; HUD_Update runs every frame after Sprite_Main (RefillLogic, $028856).
; A, X, Y and P (except carry) are preserved.
DreamWisdom_HUDHidden:
{
  PHP : REP #$20 : PHA
  LDA.l DreamWisdom_Marker : CMP.w #!DW_Live : BEQ .hidden
    PLA : PLP : CLC
    RTL
  .hidden
  PLA : PLP : SEC
  RTL
}

; ---------------------------------------------------------
; White flash: fixed-colour add on BG1/BG2/backdrop (experiment.asm .flash
; values). OBJ and BG3 are not in the math, so the actors stay visible.
; Rooms load $99 = $02 (subscreen source), so $99 = 0 here.
DreamWisdom_FlashOn:
{
  LDA.b $99 : STA.l DreamWisdom_Save99
  LDA.b $9A : STA.l DreamWisdom_Save99+1
  LDA.b $9C : STA.l DreamWisdom_Save99+2
  LDA.b $9D : STA.l DreamWisdom_Save99+3
  LDA.b $9E : STA.l DreamWisdom_Save99+4
  STZ.b $99
  LDA.b #$23 : STA.b $9A
  LDA.b #$3F : STA.b $9C
  LDA.b #$5F : STA.b $9D
  LDA.b #$9F : STA.b $9E
  LDA.b #$01 : STA.l DreamWisdom_Flash
  RTS
}

DreamWisdom_FlashOff:
{
  LDA.l DreamWisdom_Flash : BEQ .done
    LDA.l DreamWisdom_Save99   : STA.b $99
    LDA.l DreamWisdom_Save99+1 : STA.b $9A
    LDA.l DreamWisdom_Save99+2 : STA.b $9C
    LDA.l DreamWisdom_Save99+3 : STA.b $9D
    LDA.l DreamWisdom_Save99+4 : STA.b $9E
    LDA.b #$00 : STA.l DreamWisdom_Flash
  .done
  RTS
}

; Body of Opening_HideHUD (opening.asm; bank $3A, RTS only). The HUD buffer
; ($7EC700, $14A bytes) gets the blank tile; NMI uploads it while $16 != 0.
; M = 8, X = 8 on entry and exit; X preserved.
DreamWisdom_BlankHUD:
{
  PHX
  REP #$30
  LDX.w #$0148
  LDA.w #$207F
  .loop
    STA.l $7EC700, X
    DEX : DEX : BPL .loop
  SEP #$30
  PLX
  LDA.b #$01 : STA.b $16
  RTS
}
endif
