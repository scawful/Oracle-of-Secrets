; The approved cellmate uses the vanilla thief art, standing in the next cell.
; Only this staged C4 actor speaks the hint; ordinary thieves keep their AI.
; The paired room65 header selects group28 (runtime68), with thief sheet0E
; in slot0. No shared sheet data or palette loader is changed here.
if !ENABLE_D3_PRISON_SEQUENCE == 1 && !DISABLE_SPRITES == 0

!D3Prison_ThiefMarker = $D3
!D3Prison_ThiefMarker2 = $65
!D3Prison_ThiefX = $0B50 ; saved room65 tile42,43, inside the east cell
!D3Prison_ThiefY = $0D58

; End-of-list room loader, native M8/X8, DP0. Preserve full A/X/Y, DB and P,
; and the room-list allocator's next-free slot in $02. Highest free slot wins.
D3Prison_ThiefStage:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_ThiefStageEligible : BCS .stage
  JMP .done
  .stage
  LDX.b #$0F
  .duplicate
    LDA.w SprState, X : BEQ .next
    LDA.w SprType, X : CMP.b #$C4 : BNE .next
    LDA.w SprSubtype, X : CMP.b #!D3Prison_ThiefMarker : BNE .next
    LDA.w SprMiscA, X : CMP.b #!D3Prison_ThiefMarker2 : BNE .next
    JMP .done
    .next
    DEX : BPL .duplicate
  LDX.b #$0F
  .find_slot
    LDA.w SprState, X : BEQ .spawn
    DEX : BPL .find_slot
    JMP .done
  .spawn
  LDA.b #$C4 : STA.w SprType, X
  JSL $0DB818 ; SpritePrep_LoadProperties; do not run hostile thief Prep/AI
  LDA.b #$09 : STA.w SprState, X
  LDA.b #!D3Prison_ThiefMarker : STA.w SprSubtype, X
  LDA.b #!D3Prison_ThiefMarker2 : STA.w SprMiscA, X
  LDA.b #!D3Prison_ThiefX&$FF : STA.w SprX, X
  LDA.b #!D3Prison_ThiefX>>8 : STA.w SprXH, X
  LDA.b #!D3Prison_ThiefY&$FF : STA.w SprY, X
  LDA.b #!D3Prison_ThiefY>>8 : STA.w SprYH, X
  STZ.w SprFloor, X
  LDA.b #$40 : STA.w SprHitbox, X ; exclude from kill-all room tags
  LDA.b #$01 : STA.w SprBulletproof, X
  LDA.b #$FF : STA.w $0BC0, X     ; no room-list sprite-death bit
  STZ.w SprDrop, X
  LDA.b #$0F : STA.w $0F50, X    ; native friendly thief palette7/page1
  LDA.b #$02 : STA.w SprGfx, X   ; native standing body
  LDA.b #$01
  STA.w SprMiscE, X             ; head left, toward Link's cell
  STA.w SprMiscC, X
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  .done
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

; Public read-only predicates: native M8/X8, DP0; preserve X/Y/DB/SP and P
; except Carry. A is scratch. Stage uses loader room048E/F; live uses A0/A1.
D3Prison_ThiefStageEligible:
{
  PHP
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no
  LDA.l $7E048F : BNE .no
  LDA.l $7E048E : CMP.b #$65 : BNE .no
  JSL D3Prison_ThiefEscapeEligible : BCC .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

D3Prison_ThiefEligible:
{
  PHP
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no
  LDA.l $7E00A1 : BNE .no
  LDA.l $7E00A0 : CMP.b #$65 : BNE .no
  JSL D3Prison_ThiefEscapeEligible : BCC .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

D3Prison_ThiefEscapeEligible:
{
  PHP
  LDA.l Sword : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_BladeReclaimed
  BNE .no
  JSL D3Prison_ShouldResumeCell : BCC .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

; Native C4 entry originally JSLs its draw. Bank1D's sprite dispatcher has
; an RTS return beneath us. Restore its state before either return path.
D3Prison_ThiefDispatch:
{
  PHP : PHX : PHY : PHB
  PHK : PLB
  LDA.w SprSubtype, X : CMP.b #!D3Prison_ThiefMarker : BNE .native
  LDA.w SprMiscA, X : CMP.b #!D3Prison_ThiefMarker2 : BNE .native
  JSL D3Prison_ThiefMain
  PLB : PLY : PLX : PLP
  JML $1DC8CB ; native RTS, returns to SpriteModule_Active_Bank1D
  .native
  PLB : PLY : PLX : PLP
  JSL $1DCC9E ; original SpriteDraw_Thief
  JML $1DC8DC
}

D3Prison_ThiefMain:
{
  PHB : PHK : PLB
  JSL D3Prison_ThiefEligible : BCS .active
  STZ.w SprState, X
  BRA .done
  .active
  JSL $06F864 ; native player-deferred OAM allocator
  JSL $1DCC9E ; SpriteDraw_Thief: two pieces, native clipping and shadow
  JSL Sprite_CheckActive : BCC .done
  JSL D3Prison_ThiefCanTalk : BCC .done
  LDA.b $F6 : AND.b #$7F : STA.b $F6
  LDY.b #!Msg_CellmateHint1>>8
  LDA.b #!Msg_CellmateHint1&$FF
  JSL Sprite_ShowMessageUnconditional
  .done
  PLB
  RTL
}

; The separate cells prevent native contact solicitation. This scripted call
; reaches the thief 104..112px east of Link, only from the west cell's east
; floor0 strip while human Link faces right. Full coordinates prevent wrap.
; The rightward probes (X+15, Y+8/16/23) stay in floor tiles28..30,42..45;
; the south bars start at row46, so Link's Y must not exceed $0D58.
; Calls the real native busy predicate; no memory or sprite fields are written.
D3Prison_ThiefCanTalk:
{
  PHP : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_ThiefEligible : BCC .early_no
  LDA.b $10 : CMP.b #$07 : BNE .early_no
  LDA.b $11 : BNE .early_no
  LDA.w $02E4 : ORA.w $0FFC : ORA.w $0FC1 : BNE .early_no
  LDA.b $F6 : AND.b #$80 : BEQ .early_no
  LDA.b $EE : BNE .early_no
  LDA.b $2F : CMP.b #$06 : BNE .early_no
  LDA.b $5D : BNE .early_no
  LDA.w $02B2 : BNE .early_no
  JSL $07F4D0 : BCS .early_no ; native CheckIfLinkIsBusy, preserves X
  BRA .position
  .early_no
  PLB : PLP : CLC : RTL
  .position
  REP #$20
  LDA.b $22 : CMP.w #$0AE0 : BCC .no
  CMP.w #$0AE9 : BCS .no
  LDA.b $20 : CMP.w #$0D48 : BCC .no
  CMP.w #$0D59 : BCS .no
  SEP #$20
  PLB : PLP : SEC : RTL
  .no
  SEP #$20
  PLB : PLP : CLC : RTL
}

pushpc
org $1DC8D8 ; @hook module=Dungeons name=D3Prison_ThiefDispatch kind=jml target=D3Prison_ThiefDispatch expected_m=8 expected_x=8
  JML D3Prison_ThiefDispatch
assert pc() == $1DC8DC
pullpc
endif
