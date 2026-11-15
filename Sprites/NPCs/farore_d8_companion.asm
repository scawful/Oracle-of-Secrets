; Presence/recovery prototype, emitted after graphics inside its 2KiB extent.
; Only existing per-actor fields are used; A6 anchor still awaits native proof.
; Subtype $D8 identifies our actor. MiscB=placed, MiscD/E=full room stamp.
; No saved flags, dialogue, new frames, input ownership or inventory changes.
; A7 follow and A0 hold coordinates remain unselected and are not implemented.
D8Farore_Subtype = $D8
; c12 A6 authored BG1 floor left of the north Big Key door: local(56,64).
; Native $09C2A4/$09C2A9 room bases are X=$0C00,Y=$1400 for roomA6.
!D8Farore_A6WorldX = $0C38
!D8Farore_A6WorldY = $1440
!D8Farore_A6Layer = 0
D8Farore_CompanionStart:

; Input A=full room ID, M16; output A=0 absent,1 follows,2 waits, M8.
; X/Y/DBR untouched. DungeonID08 and existing crystal completion are required.
D8Farore_Presence:
{
  PHA
  SEP #$20
  LDA.l $7E001B : BEQ .none
  LDA.l $7E040C : CMP.b #$08 : BNE .none
  LDA.l $7EF37A : AND.b #$80 : BNE .none
  REP #$20 : PLA
  CMP.w #$0090 : BCC .absent
  CMP.w #$0096 : BCC .follow
  CMP.w #$00A0 : BEQ .follow
  CMP.w #$00A6 : BEQ .wait
.absent
  SEP #$20 : LDA.b #$00 : RTL
.none
  REP #$20 : PLA : BRA .absent
.follow
  SEP #$20 : LDA.b #$01 : RTL
.wait
  SEP #$20 : LDA.b #$02 : RTL
}

; Called only at native room sprite-list completion. $048E is loaded room,
; $02 next list slot. Do not overwrite an occupied slot or duplicate our actor.
; Preserve all registers/P and list pointer $00; only $02 advances on success.
D8Farore_Stage:
{
  PHP : REP #$30 : PHA : PHX : PHY : PHB
  PHK : PLB
  SEP #$30
  REP #$20 : LDA.w $048E : JSL D8Farore_Presence
  BEQ .done
  LDX.b #$0F
.find_existing
  LDA.w SprState,X : BEQ .next
  LDA.w SprType,X : CMP.b #Sprite_Farore : BNE .next
  LDA.w SprSubtype,X : CMP.b #D8Farore_Subtype : BNE .next
  LDA.w SprMiscD,X : CMP.w $048E : BNE .stale
  LDA.w SprMiscE,X : CMP.w $048F : BEQ .done
.stale
  STZ.w SprState,X
.next
  DEX : BPL .find_existing
  LDX.b $02
.find_free
  CPX.b #$10 : BCS .done
  LDA.w SprState,X : BEQ .create
  INX : BRA .find_free
.create
  LDA.b #$08 : STA.w SprState,X
  LDA.b #Sprite_Farore : STA.w SprType,X
  LDA.b #D8Farore_Subtype : STA.w SprSubtype,X
  LDA.w $048E : STA.w SprMiscD,X
  LDA.w $048F : STA.w SprMiscE,X
  STZ.w SprMiscB,X
  LDA.b #$FF : STA.w $0BC0,X ; no room kill/death bit
  STZ.w $0CBA,X             ; no key drop
  INX : STX.b $02
.done
  PLB : REP #$30 : PLY : PLX : PLA : PLP : RTL
}

; Farore's normal Prep must dispatch here only for our subtype. Frame0 is the
; existing front-facing pose. Placement waits until Link's room entry settles.
D8Farore_Prep:
{
  ; Native SpritePrep_ResetProperties clears MiscD/E before custom Prep.
  ; Re-establish the stamp from the room that is actually being loaded.
  LDA.w $048E : STA.w SprMiscD,X
  LDA.w $048F : STA.w SprMiscE,X
  STZ.w SprMiscB,X
  STZ.w SprGfx,X : STZ.w SprFrame,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  STZ.w SprHeight,X
  LDA.b #$80 : STA.w SprDefl,X
  LDA.b #$82 : STA.w SprNbrOAM,X ; harmless, two existing large OAM pieces
  RTL
}

; M/X8, actor slot X, DBR low mirror. C=1 requests normal Farore drawing.
; Stable gameplay only may place/move. A6 remains at its proven anchor.
D8Farore_Frame:
{
  PHB : PHK : PLB
  ; During room loading the loaded-room stamp and current-room byte can differ.
  ; Defer removal and placement until ordinary gameplay owns a settled room.
  LDA.b $10 : CMP.b #$07 : BNE .wait
  LDA.b $11 : ORA.w $0FC1 : ORA.l InCutScene : BNE .wait
  REP #$20 : LDA.b $A0 : JSL D8Farore_Presence
  BEQ .remove
  PHA
  LDA.w SprMiscD,X : CMP.b $A0 : BNE .stale
  LDA.w SprMiscE,X : CMP.b $A1 : BNE .stale
  ; Preserve caller scratch: floor probing owns $00-$07; candidates use08/0A.
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  LDA.b $06 : PHA
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  SEP #$20
  LDA.w SprMiscB,X : BNE .placed
  JSR D8Farore_TryPlace
  BRA .restore
.placed
  ; All accepted non-wait rooms follow; A6 remains at its admitted anchor.
  LDA.b $A0 : CMP.b #$A6 : BEQ .restore
  JSL D8Farore_Follow
.restore
  REP #$20
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$20
  PLA
.wait
  LDA.w SprMiscB,X : BEQ .hidden
  PLB : SEC : RTL
.stale
  PLA
.remove
  STZ.w SprState,X
.hidden
  PLB : CLC : RTL
}

; Try one bounded set of adjacent footprints; no repair/warp of Link. An
; unavailable footprint leaves the actor hidden and pending, never on a pit.
D8Farore_TryPlace:
{
  LDA.b $A0 : CMP.b #$A6 : BEQ .wait_anchor
  LDY.b #$00
.try
  PHY
  REP #$20
  TYA : AND.w #$00FF : ASL : TAY
  LDA.b $22 : CLC : ADC.w .dx,Y : STA.b $08
  LDA.b $20 : CLC : ADC.w .dy,Y : STA.b $0A
  SEP #$20
  LDA.b $EE : STA.w SprFloor,X
  JSR D8Farore_CheckFootprint
  PLY : BCC .place
  INY : CPY.b #$05 : BCC .try
  RTS
.wait_anchor
  REP #$20
  LDA.w #!D8Farore_A6WorldX : STA.b $08
  LDA.w #!D8Farore_A6WorldY : STA.b $0A
  SEP #$20
  LDA.b #!D8Farore_A6Layer : STA.w SprFloor,X
  JSR D8Farore_CheckFootprint : BCS .done
.place
  LDA.b $08 : STA.w SprX,X
  LDA.b $09 : STA.w SprXH,X
  LDA.b $0A : STA.w SprY,X
  LDA.b $0B : STA.w SprYH,X
  LDA.b #$01 : STA.w SprMiscB,X
.done
  RTS
.dx dw -24,24,0,0,0
.dy dw 0,0,24,-24,0
}

; Four corners, same floor/plate set as the current Stone placement contract.
; C=blocked. Existing Sprite_GetTileAttr exits M/X8 and clobbers scratch00..07.
D8Farore_CheckFootprint:
{
  PHY : LDY.b #$03
.corner
  PHX : PHY
  REP #$20
  TYA : AND.w #$00FF : ASL : TAY
  LDA.b $08 : CLC : ADC.w .dx,Y : STA.b $02
  LDA.b $0A : CLC : ADC.w .dy,Y : STA.b $00
  SEP #$20
  LDA.w SprFloor,X : JSL Sprite_GetTileAttr
  PLY : PLX
  LDA.w $0FA5 : BEQ .allowed
  CMP.b #$23 : BEQ .allowed
  CMP.b #$24 : BEQ .allowed
  CMP.b #$25 : BEQ .allowed
  CMP.b #$3B : BNE .blocked
.allowed
  DEY : BPL .corner
  PLY : CLC : RTS
.blocked
  PLY : SEC : RTS
.dx dw 0,15,0,15
.dy dw 4,4,19,19
}
; Follow code is in bank30; local footprint tables belong to this bank.
D8Farore_CheckFootprintLong:
  PHB : PHK : PLB
  JSR D8Farore_CheckFootprint
  PLB : RTL
D8Farore_CompanionEnd:
