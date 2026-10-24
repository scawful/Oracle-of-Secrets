; Dream return (!ENABLE_DREAM_RETURN): see DreamReturn_PlayerControl below.
!DreamReturn_Entrance = $0068 ; Dream Hut door on DW $5D; lands in room $0F
!DreamReturn_HutRoom  = $000F ; the hut room itself
!DreamReturn_Ticks    = 120   ; x4 frames = 8 s of player control in the dream
; Wisdom dream (!ENABLE_DREAM_WISDOM_SCENE): D1.01 in the hut, D1.02 in the
; great hall (Sprites/NPCs/dream_wisdom.asm).
!DreamMsg_WisdomNarration = $0204
!DreamMsg_WisdomFarore    = $0205
; Power dream (!ENABLE_DREAM_POWER_SCENE): D2.06, Maple once Link is back in
; the hut after the scene (Sprites/NPCs/dream_power.asm).
!DreamMsg_PowerWake       = $020B
; Wisdom fall (!ENABLE_DREAM_WISDOM_FALL): D1.05, Maple after shots 3-5.
!DreamMsg_WisdomWake      = $020E
if !ENABLE_DREAM_WISDOM_FALL == 1
  assert !ENABLE_DREAM_POWER_SCENE == 1, "ENABLE_DREAM_WISDOM_FALL runs on the Power scene's script engine (ENABLE_DREAM_POWER_SCENE)"
endif
if !ENABLE_DREAM_BED_WAKE == 1
  assert !ENABLE_DREAM_POWER_SCENE == 1, "ENABLE_DREAM_BED_WAKE needs the wake word (ENABLE_DREAM_POWER_SCENE)"
endif

MapleHandler:
{
  %PlayAnimation(0,1,16)
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Maple_Idle
  dw Maple_HandleFirstResponse
  dw Maple_DreamOrExplain
  dw Maple_ExplainHut
  dw Maple_CheckForPendant
  dw Maple_NoNewPendant
  dw Maple_PutLinkToSleep
  dw Maple_HandleDreams
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    dw Maple_DreamNarrationDone ; 08
  endif
  if !ENABLE_DREAM_BED_WAKE == 1
    dw Maple_WakeLink           ; 09
  endif


  Maple_Idle:
  {
    if !ENABLE_DREAM_POWER_SCENE == 1
      ; A finished dream scene left the wake word (DreamPower_OpEnd). With
      ; the bed wake-up Link snores a moment first (action 9); otherwise
      ; Maple says the dream's line now, at the hut door.
      REP #$20
      LDA.l DreamPower_WakeLine : CMP.w #!DreamPower_WakeLive
      SEP #$20                            ; SEP keeps Z
      BNE .no_wake_line
      if !ENABLE_DREAM_BED_WAKE == 1
        LDA.b #$40 : STA.w SprTimerA, X
        %GotoAction(9)
        RTS
      else
        JMP Maple_SayWakeLine
      endif
      .no_wake_line
    endif
    %ShowSolicitedMessage($01B3) : BCC +
      INC.w SprAction, X
    +
    ; Fishing Rod (1) -> Portal Rod (2), once. It used to queue SFX $1B on
    ; every idle frame while Link had either rod.
    LDA.l $7EF351 : CMP.b #$01 : BNE +
      LDA.b #$02 : STA.l $7EF351
      LDA.b #$1B : STA.w $012F
    +
    RTS
  }

  Maple_HandleFirstResponse:
  {
    LDA.w $1CE8 : CMP.b #$02 : BNE +
      STZ.w SprAction, X
      RTS
    +
    CMP.b #$01 : BNE .next_response
      LDA.b #$03 : STA.w SprAction, X
      RTS
    .next_response
    INC.w SprAction, X
    RTS
  }

  Maple_DreamOrExplain:
  {
    ; Every $1B4 answer goes to the pendant check (decisions.org: pendant
    ; dreams). The removed $1CE8 test read the $1B3 answer, always 0 here.
    %ShowUnconditionalMessage($01B4)
    LDA.b #$04 : STA.w SprAction, X
    RTS
  }

  Maple_ExplainHut:
  {
    %ShowUnconditionalMessage($01B5)
    STZ.w SprAction, X
    RTS
  }

  Maple_CheckForPendant:
  {
    if !ENABLE_MOON_PEARL_DREAM == 1
      JSL DreamZelda_SelectDream
      RTS
    else
    ; Offer the first pendant dream that is owned and not yet dreamed (Courage, Power, Wisdom)
    LDA.l Pendants : AND.b #$04 : BEQ .no_courage
    LDA.l Dreams   : AND.b #$04 : BNE .no_courage
      LDA.b #$02 : STA.w CurrentDream : BRA .offer
    .no_courage
    LDA.l Pendants : AND.b #$02 : BEQ .no_power
    LDA.l Dreams   : AND.b #$02 : BNE .no_power
      LDA.b #$01 : STA.w CurrentDream : BRA .offer
    .no_power
    LDA.l Pendants : AND.b #$01 : BEQ .none
    LDA.l Dreams   : AND.b #$01 : BNE .none
      STZ.w CurrentDream
    .offer
    %ShowUnconditionalMessage($01B6)
    LDA.b #$06 : STA.w SprAction, X
    LDA.b #$40 : STA.w SprTimerA, X
    RTS
    .none
    INC.w SprAction, X
    RTS
    endif
  }

  Maple_NoNewPendant:
  {
    %ShowUnconditionalMessage($01B7)
    STZ.w SprAction, X
    RTS
  }

  Maple_PutLinkToSleep:
  {
    JSR Sprite_PutLinkToSleep
    INC.w SprAction, X
    RTS
  }

  Maple_HandleDreams:
  {
    LDA.w SprTimerA, X : BNE +
      if !ENABLE_DREAM_WISDOM_SCENE == 1
        ; D1.01 over the sleeping Link, before the Wisdom dream only.
        LDA.w CurrentDream : BNE .warp
          %ShowUnconditionalMessage(!DreamMsg_WisdomNarration)
          %GotoAction(8)
          RTS
        .warp
      endif
      JSR Maple_DreamEntry
    +
    RTS
  }

  if !ENABLE_DREAM_WISDOM_SCENE == 1
    ; Every frame after D1.01 closes.
    Maple_DreamNarrationDone:
    {
      JSR Maple_DreamEntry
      RTS
    }
  endif

  ; Every frame until the entry effect is done (dream_entry_fx.asm), then
  ; the warp.
  Maple_DreamEntry:
  {
    if !ENABLE_DREAM_ENTRY_FX == 1
      JSL DreamFX_Run : BCC .wait
    endif
    JSR Link_HandleDreams
    .wait
    RTS
  }

  if !ENABLE_DREAM_BED_WAKE == 1
    ; Link was tucked into the bed on the hut reload (DreamWake_TuckIntoBed)
    ; and snores. Then he sits up, as Uncle_AwakenLink wakes him in the
    ; vanilla intro ($05DE86), and Maple says the line; a button press gets
    ; him out of bed (Link_SittingUpInBed).
    Maple_WakeLink:
    {
      LDA.w SprTimerA, X : BNE .wait
        INC.w $037D : INC.w $037C
        STZ.w SprAction, X
        JMP Maple_SayWakeLine
      .wait
      RTS
    }
  endif

  if !ENABLE_DREAM_POWER_SCENE == 1
    ; Clears the wake word and shows the line of the dream that just ended.
    Maple_SayWakeLine:
    {
      LDA.b #$00 : STA.l DreamPower_WakeLine : STA.l DreamPower_WakeLine+1
      LDY.w CurrentDream
      LDA.w .lo, Y : BEQ .none            ; no line for this dream
        PHA : LDA.w .hi, Y : TAY : PLA
        JSL Sprite_ShowMessageUnconditional
      .none
      RTS

      .lo ; by CurrentDream: Wisdom, Power, Courage
      if !ENABLE_DREAM_WISDOM_FALL == 1
        db !DreamMsg_WisdomWake&$FF
      else
        db $00
      endif
      db !DreamMsg_PowerWake&$FF, $00
      if !ENABLE_MOON_PEARL_DREAM == 1
        db $00 ; fourth dream wakes in bed without a new Maple caption
      endif
      .hi
      db !DreamMsg_WisdomWake>>8, !DreamMsg_PowerWake>>8, $00
      if !ENABLE_MOON_PEARL_DREAM == 1
        db $00
      endif
    }
  endif
}

Sprite_PutLinkToSleep:
{
  PHX
  LDA.b $20 : SEC : SBC.b #$14 : STA.b $20
  LDA.b $22 : CLC : ADC.b #$18 : STA.b $22

  LDA.b #$16 : STA.b $5D ; Set Link to sleeping
  LDA.b #$20 : JSL AncillaAdd_Blanket
  LDA.b $20 : CLC : ADC.b #$04 : STA.w $0BFA,X
  LDA.b $21 : STA.w $0C0E,X
  LDA.b $22 : SEC : SBC.b #$08 : STA.w $0C04,X
  LDA.b $23 : STA.w $0C18,X
  ; No palette filter here: one PaletteFilter_BlindingWhite step runs
  ; RestoreAdditive with a stale $7EC009 = 2, which adds +1 to each colour
  ; field with no clamp. Full fields wrapped: the bed's $7F51 became green
  ; $0371 and white $7FFF became $0420 until the warp reset the filter
  ; (DREAM-PAL, 2026-10-18).
  JSR Blanket_UseBedColors
  PLX
  RTS
}

; The blanket ancilla always draws with OBJ palette 6 ($08C052: ORA #$0D).
; In Maple's hut, row E colours 6-7 are green ($036F/$026B), so the blanket
; covered the white bed in lime green (DREAM-PAL, 2026-10-18). Only the
; blanket uses palette 6 there: set those two colours to the bed sheet's
; greys (BG $739C/$56B5) in both buffers. The next room load restores them.
; Also called by DreamWake_TuckIntoBed (dream_power.asm).
Blanket_UseBedColors:
{
  REP #$20
  LDA.w #$739C : STA.l PAL_SPR6A+$0C : STA.l PALB_SPR6A+$0C
  LDA.w #$56B5 : STA.l PAL_SPR6A+$0E : STA.l PALB_SPR6A+$0E
  SEP #$20
  INC.b UpdPalFlag
  RTS
}

Link_HandleDreams:
{
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_Wisdom
  dw Dream_Power
  dw Dream_Courage
  if !ENABLE_MOON_PEARL_DREAM == 1
    dw Dream_Zelda
  endif

  ; The dream's Dreams bit is set when it ends (DreamReturn_Begin).
  Dream_Wisdom:
  {
    if !ENABLE_DREAM_WISDOM_SCENE == 1
      ; Farore's sheet for the great hall. Group $6A keeps slot 3 (entry 0),
      ; so LoadTransAuxGFX decodes LASTSPRSET3 there ($00D77B).
      LDA.b #$55 : STA.l LASTSPRSET3
    endif
    if !ENABLE_DREAM_WISDOM_FALL == 1
      ; Kydrog's own sheet (kydrog.asm: chars $CC-$EE in slot 3 of overworld
      ; set $0C) for his silhouette in shot 5. Group $6A keeps slot 1 too.
      LDA.b #$42 : STA.l LASTSPRSET1
    endif
    LDX.b #$00
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Power:
  {
    if !ENABLE_DREAM_POWER_SCENE == 1
      ; Farore's sheet for room $00, as Dream_Wisdom: group $57 keeps slot 3.
      ; The king's sheet comes in through DreamPower_KingSheet (slot 2).
      LDA.b #$55 : STA.l LASTSPRSET3
    endif
    LDX.b #$01
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Courage:
  {
    LDX.b #$02
    JSR Link_WarpToRoom
    RTS
  }

  if !ENABLE_MOON_PEARL_DREAM == 1
    Dream_Zelda:
    {
      JSL DreamZelda_Start
      LDX.b #!DreamZelda_Id
      JSR Link_WarpToRoom
      RTS
    }
  endif
}

Link_WarpToRoom:
{
  LDA.b #$20 : STA.b $5C
  LDA.b #$01 : STA.b LinkState

  LDA.b #$15 : STA.b $11
  LDA.b $A0  : STA.b $A2
  STZ.b $A1
  LDA.w .room, X : STA.b $A0
  ; Fixed landing spot and layer per dream (decisions.org: pendant dreams).
  ; Module07_15 adds the room delta to Link and the camera, so only the
  ; in-room offset inside the hut's SE quadrant (+$100,+$100) is set here.
  LDA.w .x, X : STA.b $22
  LDA.w .y, X : STA.b $20
  LDA.w .layer, X : STA.b $EE
  if !ENABLE_DREAM_RETURN == 1
    ; Arm the wake-up timer; it only counts in Module07_00 after the warp lands.
    LDA.b #!DreamReturn_Ticks : STA.w DreamReturnTimer
    ; Hide Link for the fade-out: LinkOAM_Main draws him every Module07_15
    ; frame, at the landing offset above against the hut camera (DREAM-LINK,
    ; 2026-10-18). Part00_RoomSprites shows him again when the room loads.
    LDA.b #$0C : STA.b $4B
  endif
  RTS

  .room  ; Wisdom, Power, Courage
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db $51, $00, $31 ; Wisdom: the great hall (attract card 3, entrance $74)
  else
    db $61, $00, $31
  endif
  if !ENABLE_MOON_PEARL_DREAM == 1
    db !DreamZelda_Room
  endif
  .x     ; in-room X low byte, SE quadrant
  db $38, $48, $78
  if !ENABLE_MOON_PEARL_DREAM == 1
    db $F8 ; DreamZelda_Landing installs the full entrance-$04 coordinates
  endif
  .y     ; in-room Y low byte, SE quadrant
  db $70, $44, $70
  if !ENABLE_MOON_PEARL_DREAM == 1
    db $C0
  endif
  .layer ; $EE: lower layer in all three rooms
  db $00, $00, $00
  if !ENABLE_MOON_PEARL_DREAM == 1
    db $00
  endif
}

; Takes X as argument for the entrance ID
Link_FallIntoDungeon:
{
  LDA.w .entrance, X
  STA.w $010E
  STZ.w $010F

  LDA.b #$20 : STA.b $5C
  LDA.b #$01 : STA.b LinkState
  LDA.b #$11 : STA.b $10
  STZ.b $11 : STZ.b $B0

  RTS

  .entrance
  db $78 ; 0x00 - Wisdom: Dream 1 "The Sealing War" (placeholder room)
  db $79 ; 0x01 - Power: Dream 2 "The Oracle's Choice" (placeholder room)
  db $7A ; 0x02 - Courage: Dream 3 "The Healing Revelation" (placeholder)
  db $81 ; 0x03
}

if !ENABLE_DREAM_RETURN == 1
; =========================================================
; Dream return, option (c) (decisions.org "DECIDED Abyss fixes follow-ups",
; item 3): a dream must not strand the player.
;
; Link_WarpToRoom arms DreamReturnTimer. It counts down only while Link has
; control in the underworld (Module07_00), so it starts when the dream room
; has loaded and pauses in menus and text boxes. At zero, DreamReturn_Begin
; reloads the Dream Hut entrance ($68). Link comes back inside room $0F at
; the entrance position (the hut door), not in bed.
;
; The timer is a hard stop that needs no room geometry: dream room $31 has no
; objects and room $00 has no doors, so a door or exit trigger could strand
; Link there. Walking out of the dream room ($61 -> $60/$62) does not stop it.
;
; Stale timer (death or Save and Quit during a dream): the tick clears it
; without firing when the current entrance is not $68 (every underworld load
; sets $010E) or when Link is in the hut room $0F again.
;
; Option (a) later (wake up in bed): replace DreamReturn_Begin with a scene
; that reloads $68 and then puts Link in the bed like Sprite_PutLinkToSleep
; ($5D=$16 + blanket) before Maple's wake line. The tick can stay as is.

pushpc
; Module07_00_PlayerControl: JSL Link_Main
org $028947 ; @hook module=Sprites name=DreamReturn_PlayerControl kind=jsl target=DreamReturn_PlayerControl expected_m=8 expected_x=8
  JSL DreamReturn_PlayerControl
pullpc

DreamReturn_PlayerControl:
{
  if !ENABLE_MOON_PEARL_DREAM == 1
    JSL DreamZelda_PlayerControl : BCC +
      RTL ; the boundary wake selected MirrorFade before Link_Main
    +
  endif
  JSL $078000 ; Link_Main (replaced instruction)
  PHP
  SEP #$30
  LDA.w DreamReturnTimer : BEQ .done
    REP #$20
    ; Not in the Dream Hut's entrance context: stale timer.
    LDA.w $010E : CMP.w #!DreamReturn_Entrance : BNE .cancel
    ; Back in the hut room (continue, or re-entered through the door).
    LDA.b $A0 : CMP.w #!DreamReturn_HutRoom : BEQ .cancel
    SEP #$20
    ; Only from plain player control (Link_Main can start a transition).
    LDA.b $10 : CMP.b #$07 : BNE .done
    LDA.b $11 : BNE .done
    if !ENABLE_MOON_PEARL_DREAM == 1
      ; This playable dream ends with Zelda or the hall boundary, not after 8 s.
      LDA.w CurrentDream : CMP.b #!DreamZelda_Id : BEQ .done
    endif
    LDA.b $1A : AND.b #$03 : BNE .done
    DEC.w DreamReturnTimer : BNE .done
      JSR DreamReturn_Begin
      BRA .done
  .cancel
  SEP #$20
  STZ.w DreamReturnTimer
  .done
  PLP
  RTL
}

; (c) Reload entrance $68 through the vanilla dungeon-mirror fade:
; Module07_19_MirrorFade (mosaic + fade out) -> Module05 -> Module06 loads
; $010E. $11 != 0 also skips the rest of this Module07 frame (tags, doors,
; edge transitions), so nothing else can change the submodule.
DreamReturn_Begin:
{
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    JSR DreamWisdom_Release ; scene locks end with every dream return
  endif
  ; The dream counts as seen only now (decisions.org: pendant dreams):
  ; dying or quitting mid-dream leaves it offerable again.
  if !ENABLE_MOON_PEARL_DREAM == 1
    LDA.w CurrentDream : CMP.b #!DreamZelda_Id : BNE .mark_seen
    LDA.l DreamZelda_Progress : CMP.b #!DreamZelda_Returned : BNE .not_seen
    .mark_seen
  endif
  LDX.w CurrentDream
  LDA.l Dreams : ORA.l .bit, X : STA.l Dreams
  .not_seen
  ; Disarm the dream room's tags: room $00's Ganon-door tag would otherwise
  ; fire on the last fade frame, once DreamReturn_IsDreaming no longer gates it.
  STZ.b $AE : STZ.b $AF
  REP #$20
  LDA.w #!DreamReturn_Entrance : STA.w $010E
  SEP #$20
  ; Continue-style load ($010A): Underworld_LoadEntrance keeps the overworld
  ; cache written when Link came in through the hut door, and Module05
  ; always takes the underworld reload path.
  LDA.b #$01 : STA.w $010A
  STZ.w $04AA ; not a spawn-point load
  LDA.b #$19 : STA.b $11 ; Module07_19_MirrorFade
  STZ.b $B0
  LDA.b #$33 : STA.w $012E ; SFX2.33, the vanilla warp sound
  RTS

  .bit ; by CurrentDream: Wisdom, Power, Courage
  db !Dream_Wisdom, !Dream_Power, !Dream_Courage
  if !ENABLE_MOON_PEARL_DREAM == 1
    db !Dream_Zelda
  endif
}

if !ENABLE_MOON_PEARL_DREAM == 1
; Cross-bank entries for the bank-$42 scene; each balances its own JSR frame.
DreamReturn_Begin_Long:
  JSR DreamReturn_Begin
  RTL

DreamZelda_TuckIntoBed_Long:
  JSR DreamWake_TuckIntoBed
  RTL
endif

; Carry set while a pendant dream runs: the wake-up timer is armed and the
; current entrance is still the Dream Hut's. Room $00 is reached in that
; state only by the Power dream. 8-bit A; X/Y untouched.
DreamReturn_IsDreaming:
{
  LDA.w DreamReturnTimer : BEQ .no
  LDA.w $010F : BNE .no
  LDA.w $010E : CMP.b #!DreamReturn_Entrance&$FF : BNE .no
    SEC
    RTL
  .no
  CLC
  RTL
}

RoomTag_GanonDoor_Exit = $01C7A1 ; vanilla .exit (RTS)

pushpc
; RoomTag_GanonDoor (room $00 tag $3D): LDA.b $5D : CMP.b #$01 : BEQ .exit
org $01C77F ; @hook module=Sprites name=DreamReturn_GanonDoorGate kind=jsl target=DreamReturn_GanonDoorGate expected_m=8 expected_x=8
  JSL DreamReturn_GanonDoorGate
  BCS RoomTag_GanonDoor_Exit
  assert pc() == $01C785
pullpc

; Carry set: do not open the Triforce door this frame (Link is falling, as
; vanilla checks, or the Power dream is running in room $00).
DreamReturn_GanonDoorGate:
{
  JSL DreamReturn_IsDreaming : BCS .skip
  LDA.b $5D : CMP.b #$01 : BEQ .skip
    CLC
    RTL
  .skip
  SEC
  RTL
}
endif

pushpc
org $068C9C
db $0F
pullpc
