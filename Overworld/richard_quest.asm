; =========================================================
; Richard quest (!ENABLE_RICHARD_QUEST)
;
; scawful 2026-11-15: the Wayward Village lady paces back and forth but does
; not call the guards; she wants her dog Richard. Richard is a night-only
; palette swap of the village dog. Once Link finds him she runs inside,
; excited, with the dog, and afterwards she is inside the house with a
; reward. The house is the storage shed: entrance $4A on map $23, room $107.
;
; Pieces (all gated by this file's include, so flag-off bytes are master):
; 1. Old Snitch $3D subtype 0 (vanilla bank $05):
;    - prep  $06886E JSL SpritePrep_Snitch     -> RichardLady_Prep
;    - main  $06C053 JSL Sprite_3D_OldSnitch   -> RichardLady_Main
;    - meander contact $05E776 JSL Sprite_ShowMessageOnContact
;                                              -> RichardLady_Talk
;      Only map !RichardLadyMap is changed. Elsewhere every path JMLs to the
;      vanilla routine, so other snitches still call the guards.
;    Talk is solicited (face + A) and never reaches Snitch_SpawnGuard.
; 2. Village dog $25 (Sprites/NPCs/village_dog.asm, bank $31) subtypes:
;      1 home Richard beside the lady, 2 field Richard (night), 3 indoor.
;    Any nonzero subtype XORs the OAM palette bits (!RichardPaletteXor).
; 3. RichardQuest_Tick (JSL from HUD_ClockDisplay, every frame) spawns the
;    field Richard from RichardFieldSpawn at night, and the indoor lady and
;    Richard in room !RichardShedRoom after delivery.
;
; Save state: RichardQuestFlags ($7EF3C4, Core/sram.asm). Old saves read 00:
; quest not started.
; Dialogue: placeholders only (existing IDs). Story text needs scawful's
; approval; the draft lives in AFS, not in the ROM.
; Included from Overworld/overworld.asm (bank $34 free space).
; =========================================================

!RichardLadyMap      = $23     ; Wayward Village (large area parent)
!RichardShedRoom     = $0107   ; storage shed interior (entrance $4A)
!RichardRewardItem   = $17     ; Piece of Heart (receipt ID)
!RichardPaletteXor   = $04     ; OAM vhoopppc: $37 (pal 3) -> $33 (pal 1)
!RichardLadySpeed    = $18     ; 1.5 px/frame
!RichardDogSpeed     = $1A
!RichardRunAction    = $04     ; past the vanilla Snitch jump table (0-3)

; Placeholder message IDs (existing messages). Replace after the dialogue
; draft is approved and authored.
!RichardMsg_Pacing   = $00AD
!RichardMsg_Delivery = $00AD
!RichardMsg_Reward   = $00AD
!RichardMsg_Thanks   = $00AD
!RichardMsg_Found    = $001B

; Indoor placement, room-local pixels (0-511) in !RichardShedRoom.
!RichardIndoorLadyX  = $0180
!RichardIndoorLadyY  = $0190
!RichardIndoorDogX   = $0198
!RichardIndoorDogY   = $01A8

; ---------------------------------------------------------
; Data. Field spawn site: open design question (the village study may move
; it). Placeholder = scawful's 2026-11-15 suggestion: map $24, tile16 (25,7).
RichardFieldSpawn:
  db $24               ; overworld area ($8A)
  dw $0800+(25*16)     ; world X (map $24 column 4 -> $0800)
  dw $0800+(7*16)      ; world Y (map $24 row 4 -> $0800)

; Run path from the lady's pacing row to the shed door (door faces south).
; dw X, dw Y, db facing (0 up, 1 down, 2 left, 3 right); $FF ends.
RichardShedPath:
  dw 1644, 2464 : db $02
  dw 1644, 2604 : db $01
  dw 1680, 2604 : db $03
  dw 1680, 2584 : db $00
  dw $0000, $0000 : db $FF

; ---------------------------------------------------------
; Carry set at night (18:00-05:59). Plain clock read: no GameState rules.
RichardQuest_IsNight:
{
  LDA.l TimeState.Hours : CMP.b #$12 : BCS .night
  CMP.b #$06 : BCC .night
  CLC
  RTS
.night
  SEC
  RTS
}

; In: $00 = sprite ID, $01 = subtype. Carry set if a live sprite matches.
; Clobbers A, Y.
RichardQuest_FindSprite:
{
  LDY.b #$0F
.next
  LDA.w SprState, Y : BEQ .skip
  LDA.w SprType, Y : CMP.b $00 : BNE .skip
  LDA.w SprSubtype, Y : CMP.b $01 : BNE .skip
  SEC
  RTS
.skip
  DEY : BPL .next
  CLC
  RTS
}

; In: A = sprite ID, $01 = subtype. Out: N clear and Y = new slot on
; success. Copies Link's layer. X is preserved.
RichardQuest_Spawn:
{
  JSL Sprite_SpawnDynamically : BMI .fail
  LDA.b $01 : STA.w SprSubtype, Y
  LDA.b $EE : STA.w SprFloor, Y
  LDA.b #$00
.fail
  RTS
}

; ---------------------------------------------------------
; Walk sprite X along RichardShedPath. SprMiscB = waypoint index.
; In: A = speed, DB = this bank. Out: carry set when the path is done.
RichardQuest_RunPath:
{
  STA.b $0D
  STZ.b $0C
  LDA.w SprMiscB, X : ASL #2 : CLC : ADC.w SprMiscB, X : TAY
  LDA.w RichardShedPath+4, Y : CMP.b #$FF : BNE .walk
    SEC
    RTS
.walk
  STA.w SprMiscC, X : STA.w SprMiscE, X

  ; ---- X axis
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.w RichardShedPath, Y
  BPL .x_right_of
    CMP.w #$FFFE : BCS .x_there
    SEP #$20
    LDA.b $0D : BRA .x_set
.x_right_of
  CMP.w #$0002 : BCC .x_there
    SEP #$20
    LDA.b $0D : EOR.b #$FF : INC A : BRA .x_set
.x_there
  LDA.w RichardShedPath, Y
  SEP #$20
  STA.w SprX, X : XBA : STA.w SprXH, X
  INC.b $0C
  LDA.b #$00
.x_set
  STA.w SprXSpeed, X

  ; ---- Y axis
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.w RichardShedPath+2, Y
  BPL .y_below
    CMP.w #$FFFE : BCS .y_there
    SEP #$20
    LDA.b $0D : BRA .y_set
.y_below
  CMP.w #$0002 : BCC .y_there
    SEP #$20
    LDA.b $0D : EOR.b #$FF : INC A : BRA .y_set
.y_there
  LDA.w RichardShedPath+2, Y
  SEP #$20
  STA.w SprY, X : XBA : STA.w SprYH, X
  INC.b $0C
  LDA.b #$00
.y_set
  STA.w SprYSpeed, X

  LDA.b $0C : CMP.b #$02 : BNE .move
    INC.w SprMiscB, X
.move
  JSL Sprite_Move
  CLC
  RTS
}

; ---------------------------------------------------------
; Old Snitch prep. Vanilla first; then the quest-state outdoor changes.
RichardLady_Prep:
{
  JSL $05E675 ; SpritePrep_Snitch
  LDA.w SprSubtype, X : BNE .done
  LDA.b $1B : BNE .done
  LDA.b $8A : CMP.b #!RichardLadyMap : BNE .done
  LDA.l RichardQuestFlags : AND.b #!Richard_Delivered : BEQ .not_delivered
    STZ.w SprState, X ; she lives indoors now
    RTL
.not_delivered
  LDA.l RichardQuestFlags : AND.b #!Richard_Found : BEQ .done
  LDA.b #$25 : STA.b $00
  LDA.b #$01 : STA.b $01
  JSR RichardQuest_FindSprite : BCS .done
  LDA.b #$25 : JSR RichardQuest_Spawn : BMI .done
  LDA.w SprX, X : CLC : ADC.b #$14 : STA.w SprX, Y
  LDA.w SprXH, X : ADC.b #$00 : STA.w SprXH, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprYH, X : STA.w SprYH, Y
.done
  RTL
}

; Old Snitch main. Only subtype 0 on the quest map or in the shed changes.
RichardLady_Main:
{
  LDA.w SprSubtype, X : BNE .vanilla
  LDA.b $1B : BNE .indoors
  LDA.b $8A : CMP.b #!RichardLadyMap : BNE .vanilla
  LDA.w SprAction, X : CMP.b #!RichardRunAction : BCC .vanilla
  JMP RichardLady_Run
.indoors
  REP #$20
  LDA.b $A0 : CMP.w #!RichardShedRoom
  SEP #$20
  BNE .vanilla
  JMP RichardLady_Indoor
.vanilla
  JML $05E69A ; Sprite_3D_OldSnitch
}

; Snitch_Meander contact message site. In: A/Y = vanilla message $002F.
; Quest map: solicited talk instead, and always carry clear so the vanilla
; caller never reaches Snitch_SpawnGuard / INC SprAction.
RichardLady_Talk:
{
  PHA
  LDA.b $8A : CMP.b #!RichardLadyMap : BEQ .quest
    PLA
    JML $05E1F0 ; Sprite_ShowMessageOnContact (vanilla guard call path)
.quest
  PLA
  LDA.l RichardQuestFlags : AND.b #!Richard_Found : BNE .delivery
    LDY.b #!RichardMsg_Pacing>>8 : LDA.b #!RichardMsg_Pacing : JSL Sprite_ShowSolicitedMessageIfPlayerFacing : BCC .none
    LDA.l RichardQuestFlags : ORA.b #!Richard_Asked : STA.l RichardQuestFlags
    BRA .none
.delivery
  LDY.b #!RichardMsg_Delivery>>8 : LDA.b #!RichardMsg_Delivery : JSL Sprite_ShowSolicitedMessageIfPlayerFacing : BCC .none
  LDA.l RichardQuestFlags : ORA.b #!Richard_Delivered : STA.l RichardQuestFlags
  LDA.b #!RichardRunAction : STA.w SprAction, X
  STZ.w SprMiscB, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$F0 : STA.w SprTimerA, X ; safety: arrive after 240 frames anyway
  LDA.b #$01 : STA.w $02E4         ; hold Link while she runs
.none
  CLC
  RTL
}

; Run to the shed door, then go inside.
RichardLady_Run:
{
  PHB : PHK : PLB
  JSL SpriteDraw_RaceGameLady
  JSL Sprite_CheckActive : BCC .out
  LDA.b $1A : LSR #2 : AND.b #$01 : STA.w SprGfx, X
  LDA.w SprTimerA, X : BEQ .inside
  LDA.b #!RichardLadySpeed : JSR RichardQuest_RunPath : BCC .out
.inside
  STZ.w SprState, X
  STZ.w $02E4
.out
  PLB
  RTL
}

; Indoors in the shed: face Link; reward once, then thanks.
RichardLady_Indoor:
{
  PHB : PHK : PLB
  JSL SpriteDraw_RaceGameLady
  JSL Sprite_CheckActive : BCC .out
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DirectionToFacePlayer
  TYA : EOR.b #$03 : STA.w SprMiscE, X : STA.w SprMiscC, X
  LDA.b $1A : LSR #4 : AND.b #$01 : STA.w SprGfx, X

  LDA.w SprMiscD, X : BEQ .talk
    LDA.b $10 : CMP.b #$0E : BEQ .out
    STZ.w SprMiscD, X
    LDA.l RichardQuestFlags : AND.b #!Richard_Rewarded : BNE .out
    ORA.l RichardQuestFlags : ORA.b #!Richard_Rewarded : STA.l RichardQuestFlags
    LDY.b #!RichardRewardItem
    STZ.w $02E9
    PHX
    JSL Link_ReceiveItem
    PLX
    BRA .out
.talk
  LDA.l RichardQuestFlags : AND.b #!Richard_Rewarded : BNE .thanks
    LDY.b #!RichardMsg_Reward>>8 : LDA.b #!RichardMsg_Reward : JSL Sprite_ShowSolicitedMessageIfPlayerFacing : BCC .out
    LDA.b #$01 : STA.w SprMiscD, X
    BRA .out
.thanks
  LDY.b #!RichardMsg_Thanks>>8 : LDA.b #!RichardMsg_Thanks : JSL Sprite_ShowSolicitedMessageIfPlayerFacing
.out
  PLB
  RTL
}

; ---------------------------------------------------------
; Village dog hook (bank $31). Carry set = handled, skip the vanilla AI.
RichardDog_Main:
{
  LDA.w SprSubtype, X : BEQ .vanilla
  CMP.b #$01 : BEQ .home
  CMP.b #$02 : BEQ .field
.vanilla
  CLC
  RTL

.home
  LDA.l RichardQuestFlags : AND.b #!Richard_Delivered : BEQ .vanilla
  PHB : PHK : PLB
  LDA.b #!RichardDogSpeed : JSR RichardQuest_RunPath : BCC +
    STZ.w SprState, X
  +
  ; Walk frames: 2-3 face left, 5-6 face right (vanilla dog sheet).
  LDA.b #$05 : STA.b $0E
  LDA.w SprMiscC, X : CMP.b #$02 : BNE +
    LDA.b #$02 : STA.b $0E
  +
  LDA.b $1A : LSR #2 : AND.b #$01 : CLC : ADC.b $0E : STA.w SprFrame, X
  PLB
  SEC
  RTL

.field
  PHB : PHK : PLB
  JSR RichardQuest_IsNight : BCS .night
    STZ.w SprState, X ; night only: gone at daybreak
    BRA .handled
.night
  LDA.l RichardQuestFlags : AND.b #!Richard_Found : BNE .leaving
  ; |Link - dog| < 24 px on both axes
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.b $22 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0018
  SEP #$20
  BCS .unhandled
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.b $20 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0018
  SEP #$20
  BCS .unhandled
    LDA.l RichardQuestFlags : ORA.b #!Richard_Found : STA.l RichardQuestFlags
    LDY.b #!RichardMsg_Found>>8 : LDA.b #!RichardMsg_Found : JSL Sprite_ShowMessageUnconditional
    LDA.b #$40 : STA.w SprTimerA, X
    LDA.b #$20 : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    BRA .handled
.leaving
  ; Runs off home, then despawns (he reappears beside the lady).
  LDA.w SprTimerA, X : BNE +
    STZ.w SprState, X
    BRA .handled
  +
  LDA.b $1A : LSR #2 : AND.b #$01 : CLC : ADC.b #$05 : STA.w SprFrame, X
  JSL Sprite_Move
.handled
  PLB
  SEC
  RTL
.unhandled
  PLB
  CLC
  RTL
}

; Village dog draw: $0C = OAM property XOR for this dog (0 = vanilla).
RichardDog_PaletteMask:
{
  STZ.b $0C
  LDA.w SprSubtype, X : BEQ +
    LDA.b #!RichardPaletteXor : STA.b $0C
  +
  RTL
}

; ---------------------------------------------------------
; Every frame (HUD_ClockDisplay, M/X 8-bit). Spawns quest actors.
RichardQuest_Tick:
{
  PHB : PHK : PLB
  LDA.b $11 : BNE .done
  LDA.b $10 : CMP.b #$09 : BEQ .overworld
  CMP.b #$07 : BEQ .underworld
.done
  PLB
  RTL

.overworld
  LDA.l RichardQuestFlags : AND.b #(!Richard_Asked|!Richard_Found)
  CMP.b #!Richard_Asked : BNE .done
  LDA.b $8A : CMP.w RichardFieldSpawn : BNE .done
  JSR RichardQuest_IsNight : BCC .done
  LDA.b #$25 : STA.b $00
  LDA.b #$02 : STA.b $01
  JSR RichardQuest_FindSprite : BCS .done
  LDX.b #$00
  LDA.b #$25 : JSR RichardQuest_Spawn : BMI .done
  REP #$20
  LDA.w RichardFieldSpawn+1 : SEP #$20 : STA.w SprX, Y : XBA : STA.w SprXH, Y
  REP #$20
  LDA.w RichardFieldSpawn+3 : SEP #$20 : STA.w SprY, Y : XBA : STA.w SprYH, Y
  BRA .done

.underworld
  REP #$20
  LDA.b $A0 : CMP.w #!RichardShedRoom
  SEP #$20
  BNE .done
  LDA.l RichardQuestFlags : AND.b #!Richard_Delivered : BEQ .done
  ; Room base: X hi = (room & $0F) * 2, Y hi = (room & $F0) / 8.
  LDA.b $A0 : AND.b #$0F : ASL A : STA.b $02
  LDA.b $A0 : AND.b #$F0 : LSR #3 : STA.b $03
  LDX.b #$00

  LDA.b #$3D : STA.b $00
  STZ.b $01
  JSR RichardQuest_FindSprite : BCS .dog
  LDA.b #$3D : JSR RichardQuest_Spawn : BMI .dog
  LDA.b #!RichardIndoorLadyX&$FF : STA.w SprX, Y
  LDA.b #!RichardIndoorLadyX>>8 : CLC : ADC.b $02 : STA.w SprXH, Y
  LDA.b #!RichardIndoorLadyY&$FF : STA.w SprY, Y
  LDA.b #!RichardIndoorLadyY>>8 : CLC : ADC.b $03 : STA.w SprYH, Y
  LDA.b #$01 : STA.w SprMiscC, Y : STA.w SprMiscE, Y
.dog
  LDA.b #$25 : STA.b $00
  LDA.b #$03 : STA.b $01
  JSR RichardQuest_FindSprite : BCS .tail
  LDA.b #$25 : JSR RichardQuest_Spawn : BMI .tail
  LDA.b #!RichardIndoorDogX&$FF : STA.w SprX, Y
  LDA.b #!RichardIndoorDogX>>8 : CLC : ADC.b $02 : STA.w SprXH, Y
  LDA.b #!RichardIndoorDogY&$FF : STA.w SprY, Y
  LDA.b #!RichardIndoorDogY>>8 : CLC : ADC.b $03 : STA.w SprYH, Y
.tail
  JMP .done
}

; ---------------------------------------------------------
pushpc

; SpritePrep $3D bounce: JSL SpritePrep_Snitch : RTS (only $3D uses it).
org $06886E ; @hook module=Sprites name=RichardLadyPrep kind=jsl target=RichardLady_Prep expected_m=8 expected_x=8
  JSL RichardLady_Prep

; Sprite main $3D bounce: JSL Sprite_3D_OldSnitch : RTS (only $3D uses it).
org $06C053 ; @hook module=Sprites name=RichardLadyMain kind=jsl target=RichardLady_Main expected_m=8 expected_x=8
  JSL RichardLady_Main

; Snitch_Meander: LDA #$2F : LDY #$00 : JSL Sprite_ShowMessageOnContact.
org $05E776 ; @hook module=Sprites name=RichardLadyTalk kind=jsl target=RichardLady_Talk expected_m=8 expected_x=8
  JSL RichardLady_Talk

pullpc
