; Moon Pearl dream: a playable visit to the existing Hyrule Castle hall.
; The hut remains entrance $68 throughout the room swap and normal return.
; The existing revive gate restores the hut on death; Save & Quit follows
; the normal saved spawn. Only a completed Zelda lesson earns the dream bit
; and Song of Time; leaving the hall wakes Link without either.

if !ENABLE_MOON_PEARL_DREAM == 1
assert !ENABLE_DREAM_RETURN == 1, "Moon Pearl dream needs DREAM_RETURN"
assert !ENABLE_DREAM_ROOM_SHEETS == 1, "Moon Pearl dream needs DREAM_ROOM_SHEETS"
assert !ENABLE_DREAM_POWER_SCENE == 1, "Moon Pearl dream needs the hut wake marker"
assert !ENABLE_DREAM_BED_WAKE == 1, "Moon Pearl dream needs DREAM_BED_WAKE"

!DreamZelda_Id       = $03
!DreamZelda_Subtype  = $D9
!DreamZelda_Room     = $61
!DreamZelda_Live     = $D9A3
!DreamZelda_Lesson   = $0211
!DreamZelda_Learned  = $0212
!DreamZelda_Offer    = $0213
!DreamZelda_Returned = $02
!DreamZelda_Aborted  = $03

pushpc
org $42D400

; This existing Maple state lives here to keep bank $30 within its allocation.
; Same sprite-state contract as Maple_CheckForPendant: M/X=8, X=sprite slot.
DreamZelda_SelectDream:
{
  PHB
  LDA.b #$00 : PHA : PLB
  JSL DreamZelda_CheckOffer : BCC .pendants
  LDA.b #!DreamZelda_Id : STA.w CurrentDream
  %ShowUnconditionalMessage(!DreamZelda_Offer)
  BRA .sleep
  .pendants
  LDA.l Pendants : AND.b #$04 : BEQ .no_courage
  LDA.l Dreams : AND.b #$04 : BNE .no_courage
  LDA.b #$02 : STA.w CurrentDream : BRA .offer
  .no_courage
  LDA.l Pendants : AND.b #$02 : BEQ .no_power
  LDA.l Dreams : AND.b #$02 : BNE .no_power
  LDA.b #$01 : STA.w CurrentDream : BRA .offer
  .no_power
  LDA.l Pendants : AND.b #$01 : BEQ .none
  LDA.l Dreams : AND.b #$01 : BNE .none
  STZ.w CurrentDream
  .offer
  %ShowUnconditionalMessage($01B6)
  .sleep
  LDA.b #$06 : STA.w SprAction, X
  LDA.b #$40 : STA.w SprTimerA, X
  BRA .done
  .none
  INC.w SprAction, X
  .done
  PLB
  RTL
}

; Maple's eligibility check. M/X=8, preserves X/Y/DB, carry = offerable.
DreamZelda_CheckOffer:
{
  LDA.l MoonPearl : BEQ .no
  LDA.l Dreams : AND.b #!Dream_Zelda : BNE .no
  JSL Ocarina_ValidateSong_Long
  LDA.l SongBits : AND.b #!Song_Healing : BEQ .no
  SEC
  RTL
  .no
  CLC
  RTL
}

; Called immediately before the hut-to-hall room swap. M/X=8, DB preserved.
DreamZelda_Start:
{
  PHB
  LDA.b #$00 : PHA : PLB
  LDA.w $02F9 : STA.l DreamZelda_SaveFollower
  LDA.b #$01 : STA.w $02F9
  LDA.b #$00 : STA.l DreamZelda_Progress
  REP #$20
  LDA.w #!DreamZelda_Live : STA.l DreamZelda_Marker
  SEP #$20
  PLB
  RTL
}

; Carry = this fourth dream owns the hut entrance context. M/X=8; X/Y kept.
DreamZelda_IsActive:
{
  LDA.w CurrentDream : CMP.b #!DreamZelda_Id : BNE .no
  LDA.w $010F : BNE .no
  LDA.w $010E : CMP.b #$68 : BNE .no
  REP #$20
  LDA.l DreamZelda_Marker : CMP.w #!DreamZelda_Live
  SEP #$20
  BNE .no
  SEC
  RTL
  .no
  CLC
  RTL
}

; Part00_RoomSprites, after DreamFX_RoomLoaded. M/X=8, DB=$09; A/X/Y free.
; The list pointer and next-free-slot byte are no longer needed by this path.
DreamZelda_RoomLoaded:
{
  PHB
  LDA.b #$00 : PHA : PLB
  REP #$20
  LDA.l DreamZelda_Marker : CMP.w #!DreamZelda_Live
  SEP #$20
  BNE .done
  LDA.w CurrentDream : CMP.b #!DreamZelda_Id : BNE .forget
  JSL DreamZelda_IsActive : BCC .release
  LDA.w $048F : BNE .done
  LDA.w $048E : CMP.b #$0F : BEQ .hut
  CMP.b #!DreamZelda_Room : BNE .done
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : CMP.b #$15 : BNE .done
  JSR DreamZelda_Stage
  BRA .done

  .hut
  LDA.l DreamZelda_Progress : CMP.b #!DreamZelda_Returned : BNE .release
  ; No Wisdom marker is borrowed: the ordinary pendant scene remains separate.
  JSL DreamZelda_TuckIntoBed_Long
  .release
  STZ.b $4B
  STZ.w DreamReturnTimer
  LDA.l DreamZelda_SaveFollower : STA.w $02F9
  .forget
  LDA.b #$00
  STA.l DreamZelda_Marker : STA.l DreamZelda_Marker+1
  STA.l DreamZelda_Progress
  .done
  PLB
  RTL
}

; Stage one temporary Zelda and remove the normal Impa only in this dream.
DreamZelda_Stage:
{
  LDX.b #$0F
  .remove_impa
  LDA.w SprType, X : CMP.b #$76 : BNE .next
  STZ.w SprState, X
  .next
  DEX : BPL .remove_impa
  LDX.b #$0F
  .find_slot
  LDA.w SprState, X : BEQ .slot
  DEX : BPL .find_slot
  RTS                                      ; boundary wake still works
  .slot
  LDA.b #$08 : STA.w SprState, X
  LDA.b #Sprite_Farore : STA.w SprType, X
  LDA.b #!DreamZelda_Subtype : STA.w SprSubtype, X
  STZ.w SprFloor, X
  LDA.b #$00 : STA.w SprX, X
  LDA.b #$03 : STA.w SprXH, X               ; room $61 + local X $0100
  LDA.b #$A0 : STA.w SprY, X
  LDA.b #$0C : STA.w SprYH, X               ; local Y $00A0
  LDA.b #$FF : STA.w $0BC0, X
  STZ.w $0CBA, X
  JSR DreamZelda_Landing
  STZ.b LinkState : STZ.b $5C : STZ.b $4B
  JSL DreamRoom_LoadSheets                   ; authored header set $00
  RTS
}

; Entrance $04's camera, without replacing entrance $68. Land 64 px north
; of its dormant doorway: the authored south wall covers local Y $01B8-$01D7.
DreamZelda_Landing:
{
  REP #$20
  LDA.w #$02F8 : STA.b $22
  LDA.w #$0D80 : STA.b $20
  LDA.w #$0280 : STA.b $E2
  LDA.w #$0D10 : STA.b $E8
  LDA.w #$0D00 : STA.w $0600
  LDA.w #$0C00 : STA.w $0602
  LDA.w #$0D10 : STA.w $0604 : STA.w $0606
  LDA.w #$0200 : STA.w $0608 : STA.w $060A : STA.w $060C
  LDA.w #$0300 : STA.w $060E
  LDA.w #$0187 : STA.w $0618
  LDA.w #$0189 : STA.w $061A
  LDA.w #$00FF : STA.w $061C
  LDA.w #$0101 : STA.w $061E
  SEP #$20
  STZ.b $A9
  LDA.b #$02 : STA.b $AA
  STZ.b $EE : STZ.w $0476
  RTS
}

; Farore's indoor prep/main call these only for subtype $D9. DB preserved.
DreamZelda_Prep:
{
  %SetHarmless(1)                         ; contact must not recoil before talking
  LDA.b #$07 : STA.w SprHitbox, X         ; talk reaches past the solid NPC boundary
  STZ.w SprAction, X
  STZ.w SprFrame, X
  RTL
}

DreamZelda_Main:
{
  PHB
  LDA.b #$00 : PHA : PLB
  JSL DreamZelda_IsActive : BCS +
    JMP .inactive
  +
  STZ.w SprFrame, X
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprAction, X : BEQ .greet
  CMP.b #$01 : BEQ .lesson
  CMP.b #$02 : BNE .done
  ; Sprite_CheckActive resumes this handler only after the message closes.
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : BNE .done
  LDA.w $1CD8 : BNE .done
  LDA.b #!Song_Time : JSL Ocarina_LearnSong_Long
  LDA.b #$04 : STA.w CurrentSong : STA.l SavedOcarinaSong
  LDA.b #!DreamZelda_Returned : STA.l DreamZelda_Progress
  LDA.b #$03 : STA.w SprAction, X
  REP #$20
  LDA.w #!DreamPower_WakeLive : STA.l DreamPower_WakeLine
  SEP #$20
  PHX : JSR DreamZelda_Return : PLX
  BRA .done
  .greet
  %ShowSolicitedMessage(!DreamZelda_Lesson) : BCC .done
  LDA.b #$01 : STA.w SprAction, X
  BRA .done
  .lesson
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : BNE .done
  LDA.w $1CD8 : BNE .done
  %ShowUnconditionalMessage(!DreamZelda_Learned)
  LDA.b #$27 : STA.w $012F                  ; existing Song of Time notes
  LDA.b #$02 : STA.w SprAction, X
  BRA .done
  .inactive
  STZ.w SprState, X
  .done
  PLB
  RTL
}

; Before Link_Main, only in Module07_00. Carry = return started, skip Link_Main.
; The hall's edges wake Link before doors/stairs can replace the hut context.
DreamZelda_PlayerControl:
{
  PHB
  LDA.b #$00 : PHA : PLB
  JSL DreamZelda_IsActive : BCC .ordinary
  LDA.b $10 : CMP.b #$07 : BNE .ordinary
  LDA.b $11 : BNE .ordinary
  LDA.b $A1 : BNE .abort
  LDA.b $A0 : CMP.b #!DreamZelda_Room : BNE .abort
  REP #$20
  LDA.b $22 : AND.w #$01FF
  CMP.w #$0018 : BCC .outside
  CMP.w #$01E8 : BCS .outside
  LDA.b $20 : AND.w #$01FF
  CMP.w #$0048 : BCC .outside
  CMP.w #$01D0 : BCS .outside
  SEP #$20
  .ordinary
  PLB
  CLC
  RTL
  .outside
  SEP #$20
  .abort
  LDA.b #!DreamZelda_Aborted : STA.l DreamZelda_Progress
  JSR DreamZelda_Return
  PLB
  SEC
  RTL
}

; Existing Part00_ReviveGate, after vanilla's cave-death path cleared $1B.
; M/X=8, DP=0; X/Y/DB preserved. Carry set means the hut reload is prepared.
DreamZelda_ReviveGate:
{
  PHB
  LDA.b #$00 : PHA : PLB
  JSL DreamZelda_IsActive : BCC .ordinary
  LDA.l DreamZelda_Progress : CMP.b #!DreamZelda_Returned : BEQ .reload
  LDA.b #!DreamZelda_Aborted : STA.l DreamZelda_Progress
  .reload
  LDA.b #$68 : STA.w $010E
  STZ.w $010F
  LDA.b #$01 : STA.w $010A : STA.b $1B
  STZ.w $04AA : STZ.w $04AB
  STZ.w DreamReturnTimer
  STZ.b $4B
  STZ.w $02E4 : STZ.w $0FFC : STZ.w $037B
  LDA.l DreamZelda_SaveFollower : STA.w $02F9
  PLB
  SEC
  RTL
  .ordinary
  PLB
  CLC
  RTL
}

; M/X=8, DB=$00. Completion is decided by DreamZelda_Progress in the shared
; return helper. Aborting has no wake caption, reward or seen bit.
DreamZelda_Return:
{
  STZ.w DreamReturnTimer
  LDA.b #$0C : STA.b $4B
  LDA.b #$0F : STA.b $13                   ; MirrorFade decrements brightness
  JSL DreamReturn_Begin_Long
  RTS
}

print "End of Moon Pearl Zelda dream     ", pc
assert pc() <= $430000, "Moon Pearl Zelda dream crossed bank $42"
pullpc
endif
