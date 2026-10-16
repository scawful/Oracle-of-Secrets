; Dream return (!ENABLE_DREAM_RETURN): see DreamReturn_PlayerControl below.
!DreamReturn_Entrance = $0068 ; Dream Hut door on DW $5D; lands in room $0F
!DreamReturn_HutRoom  = $000F ; the hut room itself
!DreamReturn_Ticks    = 120   ; x4 frames = 8 s of player control in the dream

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


  Maple_Idle:
  {
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
      JSR Link_HandleDreams
    +
    RTS
  }
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
  JSL PaletteFilter_StartBlindingWhite
  JSL ApplyPaletteFilter
  PLX
  RTS
}

Link_HandleDreams:
{
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_Wisdom
  dw Dream_Power
  dw Dream_Courage

  ; The dream's Dreams bit is set when it ends (DreamReturn_Begin).
  Dream_Wisdom:
  {
    LDX.b #$00
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Power:
  {
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
  endif
  RTS

  .room  ; Wisdom, Power, Courage
  db $61, $00, $31
  .x     ; in-room X low byte, SE quadrant
  db $38, $48, $78
  .y     ; in-room Y low byte, SE quadrant
  db $70, $44, $70
  .layer ; $EE: lower layer in all three rooms
  db $00, $00, $00
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
  ; The dream counts as seen only now (decisions.org: pendant dreams):
  ; dying or quitting mid-dream leaves it offerable again.
  LDX.w CurrentDream
  LDA.l Dreams : ORA.l .bit, X : STA.l Dreams
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
}

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

pushpc
; RoomTag_GanonDoor (room $00 tag $3D): LDA.b $5D : CMP.b #$01 : BEQ .exit
org $01C77F ; @hook module=Sprites name=DreamReturn_GanonDoorGate kind=jsl target=DreamReturn_GanonDoorGate expected_m=8 expected_x=8
  JSL DreamReturn_GanonDoorGate
  BCS $01C7A1 ; RoomTag_GanonDoor .exit (RTS)
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
