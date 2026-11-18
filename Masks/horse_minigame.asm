; Shared Horse Minigame Engine (!ENABLE_HORSE_FORM).
; Supports both contained courses with NPC unload + enemy sheet swap + exit
; route blocking (Course 0: Toto Ranch OW $00) and multi-area overlay hurdle
; routes (Course 1: Kalyxo OW $11 bridge route).
; Uses UNUSED_7F5000 ($7F5410-$7F545F) after Horse_OffOam ($7F5405-$7F5406).

HorseGame_State            = $7F5410 ; 0=idle, 1=enter blackout, 2=active, 3=exit blackout, 4=prompt wait
HorseGame_CourseId         = $7F5411 ; 0=Toto Ranch archery+hurdle, 1=Kalyxo route hurdles
HorseGame_Timer            = $7F5412 ; word: active frame countdown
HorseGame_TargetsLeft      = $7F5414 ; remaining live target count
HorseGame_ActiveArea       = $7F5415 ; $8A of current overlay tile saves
HorseGame_SavedAA3         = $7F5416 ; original $0AA3 before swap ($FF = unchanged)
HorseGame_SavedTileCount   = $7F5417 ; count of saved Tile16 cells (0..16)
HorseGame_TransStep        = $7F5418 ; blackout sub-step (0 = request blank, 1 = DMA/apply)
HorseGame_Score            = $7F5419 ; targets cleared so far
HorseGame_TargetCount      = $7F541A ; total targets spawned on active course
HorseGame_SavedTileOffsets = $7F5420 ; 16 words ($7E2000 byte offsets)
HorseGame_SavedTileValues  = $7F5440 ; 16 words (original Tile16 IDs)

!HorseGame_OverworldLoadSprites = $09C4AC
!HorseGame_LoadTransAuxSprite   = $00D6F9
!HorseGame_LoadNewSpriteGFXSet  = $00E031
!HorseGame_SpriteResetAll       = $09C44E
!HorseGame_SpriteOverworldReload = $09C499
!HorseGame_SpriteLoadProperties = $0DB818
!HorseGame_DrawMap16Persist     = $1BC97C
!HorseGame_CheckTouchLink       = $06F129 ; Sprite_CheckDamageToLink_same_layer_long
!HorseGame_ShowMessageUncond    = $05E219 ; Sprite_ShowMessageUnconditional
!HorseGame_ReceiveItem          = $0799AD ; Link_ReceiveItem (Y = item id)
!HorseGame_MsgKidOnFoot         = $0227
!HorseGame_MsgKidMountedPrompt  = $0228
!HorseGame_MsgKidMountedNoBow   = $0229
!HorseGame_RupeeReward          = $0032   ; 50 Rupees per course clear
!SideQuest2_RanchArchery        = $80     ; SideQuestProg2 ($7EF3D8) bit 7: first-clear Heart Piece won

pushpc
org $53E900

; Per-frame engine dispatcher called from HorseForm_FrameTick (M=8, X=8, DBR=$00).
; Preserves P/X/Y/DBR; A clobbered.
HorseGame_Tick:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  LDA.l HorseGame_State : BEQ .done
  CMP.b #$01 : BEQ .enter
  CMP.b #$02 : BEQ .active
  CMP.b #$03 : BEQ .exit
  CMP.b #$04 : BEQ .prompt
  LDA.b #$00 : STA.l HorseGame_State
  .done
  PLB : PLP
  RTL

  .enter
  JSR HorseGame_EnterTransition
  PLB : PLP
  RTL

  .active
  JSR HorseGame_ActiveTick
  PLB : PLP
  RTL

  .exit
  JSR HorseGame_ExitTransition
  PLB : PLP
  RTL

  .prompt
  JSR HorseGame_PromptWait
  PLB : PLP
  RTL
}

; State $04: Wait for $0228 mounted Yes/No prompt ($10 == $0E) to return to
; overworld play ($10 == $09, $11 == $00), then read $1CE8 (0 = Let's ride!).
HorseGame_PromptWait:
{
  LDA.b $10 : CMP.b #$09 : BNE .wait
  LDA.b $11 : BNE .wait
  LDA.w $1CE8 : BNE .declined
    LDA.b #$00 : STA.l HorseGame_CourseId : STA.l HorseGame_TransStep
    LDA.b #$01 : STA.l HorseGame_State
    JSR HorseGame_EnterTransition
    RTS
  .declined
  LDA.b #$00 : STA.l HorseGame_State
  .wait
  RTS
}

; State $01: Two-step forced-blank loading screen transition.
; Sub-step 0 sets INIDISP=$80 ($13) and purges resident NPCs/spatial memory.
; Sub-step 1 (now in forced blank) swaps enemy VRAM sheet $5000, injects
; course barriers/hurdles, spawns archery targets, and reveals the course.
HorseGame_EnterTransition:
{
  LDA.l HorseGame_TransStep : BNE .step1
    LDA.b #$80 : STA.b $13            ; NMI writes $80 -> INIDISP ($2100) for next frame
    STZ.b $30 : STZ.b $31
    STZ.b $14 : STZ.b $17
    LDA.b #$FF : STA.l Horse_NpcUploadedFrame
    STA.l HorseGame_SavedAA3
    LDA.b #$00 : STA.l Horse_NpcActive : STA.l Horse_OffState
    STA.l HorseGame_SavedTileCount
    STA.l HorseGame_Score
    STA.l HorseGame_TargetCount
    STA.l HorseGame_TargetsLeft
    JSL !HorseGame_SpriteResetAll     ; clear $0DD0 and spatial tables ($7FDF80+)
    SEP #$30
    LDA.b #$00 : PHA : PLB
    LDA.b #$01 : STA.l HorseGame_TransStep
    RTS

  .step1
  LDA.b #$80 : STA.w $2100            ; keep PPU forced blank latched during 8KB DMA
  STZ.b $14 : STZ.b $17
  STZ.b $30 : STZ.b $31

  ; Check course enemy $0AA3 sprite graphics set ($FF = keep resident sheets).
  LDA.l HorseGame_CourseId : AND.b #$01 : TAX
  LDA.l HorseGame_CourseEnemyAA3, X
  CMP.b #$FF : BEQ .no_gfx_swap
    PHA
    LDA.w $0AA3 : STA.l HorseGame_SavedAA3
    PLA : STA.w $0AA3
    JSR HorseGame_ReloadSpriteVram
    SEP #$30
    LDA.b #$00 : PHA : PLB
  .no_gfx_swap

  LDA.b $8A : STA.l HorseGame_ActiveArea
  JSR HorseGame_ApplyOverlaysForArea
  JSR HorseGame_SpawnTargetsForArea

  LDA.l HorseGame_CourseId : AND.b #$01 : ASL : TAX
  REP #$20
  LDA.l HorseGame_CourseInitTimers, X : STA.l HorseGame_Timer
  SEP #$20

  LDA.b #$00 : STA.l HorseGame_TransStep
  LDA.b #$02 : STA.l HorseGame_State
  LDA.b #$0F : STA.b $13              ; reveal loaded minigame course
  RTS
}

; State $02: Active minigame frame tick (M=8, X=8, DBR=$00).
HorseGame_ActiveTick:
{
  LDA.b $10 : CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .ret
  +
  LDA.b $11 : BNE .ret

  ; Inject area overlays if rider crossed into another course area cleanly.
  LDA.b $8A : CMP.l HorseGame_ActiveArea : BEQ .same_area
    STA.l HorseGame_ActiveArea
    LDA.b #$00 : STA.l HorseGame_SavedTileCount
    JSR HorseGame_ApplyOverlaysForArea
    JSR HorseGame_SpawnTargetsForArea
  .same_area

  ; Hold spawned archery targets anchored on post & count remaining targets.
  LDA.l HorseGame_TargetCount : BEQ .tick_timer
  JSR HorseGame_UpdateTargets
  LDA.l HorseGame_TargetsLeft : BNE .tick_timer
    ; All targets defeated: wait until death poofs ($0DD0 != 0) clear cleanly.
    JSR HorseGame_AnyTargetSlotBusy : BCS .tick_timer
      LDA.b #$00 : STA.l HorseGame_TransStep
      LDA.b #$03 : STA.l HorseGame_State
      RTS

  .tick_timer
  REP #$20
  LDA.l HorseGame_Timer : BEQ .timeout
    DEC : STA.l HorseGame_Timer
    SEP #$20
    RTS
  .timeout
  SEP #$20
  LDA.b #$00 : STA.l HorseGame_TransStep
  LDA.b #$03 : STA.l HorseGame_State
  .ret
  RTS
}

; State $03: Two-step forced-blank teardown restoring tiles, NPC sheet & NPCs.
HorseGame_ExitTransition:
{
  LDA.l HorseGame_TransStep : BNE .step1
    LDA.b #$80 : STA.b $13
    STZ.b $30 : STZ.b $31
    STZ.b $14 : STZ.b $17
    JSL !HorseGame_SpriteResetAll
    SEP #$30
    LDA.b #$00 : PHA : PLB
    LDA.b #$01 : STA.l HorseGame_TransStep
    RTS

  .step1
  LDA.b #$80 : STA.w $2100
  STZ.b $14 : STZ.b $17
  STZ.b $30 : STZ.b $31

  ; Restore temporary Tile16 barriers/hurdles if still in the modified area.
  LDA.b $8A : CMP.l HorseGame_ActiveArea : BNE .skip_tiles
    JSR HorseGame_RestoreAreaTiles
  .skip_tiles

  ; Restore native $0AA3 sprite graphics set & VRAM $5000 if swapped.
  LDA.l HorseGame_SavedAA3 : CMP.b #$FF : BEQ .skip_gfx_restore
    STA.w $0AA3
    JSR HorseGame_ReloadSpriteVram
    SEP #$30
    LDA.b #$00 : PHA : PLB
    LDA.b #$FF : STA.l HorseGame_SavedAA3
  .skip_gfx_restore

  ; Reload area residents ($0DD0 + spatial table) and allow normal NMI NPC state.
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  JSL !HorseGame_SpriteOverworldReload
  SEP #$30
  LDA.b #$00 : PHA : PLB

  ; Clear state and reveal course before granting rewards.
  LDA.b #$00 : STA.l HorseGame_TransStep
  STA.l HorseGame_State
  LDA.b #$0F : STA.b $13

  ; Award +50 Rupees + first-clear Piece of Heart ($17) when course targets were cleared.
  LDA.l HorseGame_TargetCount : BEQ .clear_done
  LDA.l HorseGame_TargetsLeft : BNE .clear_done
    LDA.b #$0F : STA.w $012F
    REP #$20
    LDA.l $7EF360 : CLC : ADC.w #!HorseGame_RupeeReward
    CMP.w #$03E7 : BCC +
      LDA.w #$03E7
    +
    STA.l $7EF360
    SEP #$20
    LDA.l SideQuestProg2 : AND.b #!SideQuest2_RanchArchery : BNE .clear_done
      LDA.l SideQuestProg2 : ORA.b #!SideQuest2_RanchArchery : STA.l SideQuestProg2
      LDA.l $7EF280 : ORA.b #$40 : STA.l $7EF280
      STZ.w $02E9
      LDY.b #$17
      JSL !HorseGame_ReceiveItem
      SEP #$30
      LDA.b #$00 : PHA : PLB
  .clear_done
  RTS
}

; Re-decompress $0AA3 4 sprite sub-sheets -> convert 3bpp->4bpp -> DMA $2000 bytes
; into OBJ VRAM $5000-$5FFF (Page 1 tiles $00..$FF). Requires forced blank ($2100=$80).
; Enters M=8, X=8, DP=$0000, DBR=$00. Restores DMA0 bank=$7E.
HorseGame_ReloadSpriteVram:
{
  SEP #$30
  LDA.b #$00 : PHA : PLB
  JSL !HorseGame_LoadTransAuxSprite
  SEP #$30
  LDA.b #$00 : PHA : PLB
  JSL !HorseGame_LoadNewSpriteGFXSet

  SEP #$30
  LDA.b #$00 : PHA : PLB
  LDA.b #$80 : STA.w $2100
  STA.w $2115                         ; VMAIN = $80 (word increment)
  LDA.b #$01 : STA.w $4300            ; DMA0 mode 1 (2 regs write-twice: $2118/$2119)
  LDA.b #$18 : STA.w $4301
  REP #$10
  LDX.w #$5000 : STX.w $2116          ; VRAM $5000 word = $A000 byte (OBJ Page 1)
  LDX.w #$0000 : STX.w $4302
  LDA.b #$7F   : STA.w $4304          ; $7F:0000 4bpp conversion buffer
  LDX.w #$2000 : STX.w $4305          ; full 8 KB (all 4 sprite sheets)
  LDA.b #$01   : STA.w $420B
  LDA.b #$7E   : STA.w $4304          ; restore native bank $7E for subsequent NMI DMA
  SEP #$30
  RTS
}

; Apply course Tile16 overlays matching ($8A == HorseGame_ActiveArea).
; Table entries: db course_id, area_id; dw wx, wy, tile16 (terminated by db $FF).
HorseGame_ApplyOverlaysForArea:
{
  LDX.b #$00
  .loop
    LDA.l HorseGame_OverlayTable, X : CMP.b #$FF : BEQ .done
    CMP.l HorseGame_CourseId : BNE .next6
    LDA.l HorseGame_OverlayTable+1, X : CMP.b $8A : BNE .next6
      PHX
      REP #$20
      LDA.l HorseGame_OverlayTable+2, X : STA.b $0C ; wx
      LDA.l HorseGame_OverlayTable+4, X : STA.b $0A ; wy
      LDA.l HorseGame_OverlayTable+6, X : STA.b $08 ; new Tile16
      JSR HorseGame_ApplyTile16At
      SEP #$30
      PLX
    .next6
    TXA : CLC : ADC.b #$08 : TAX
    BRA .loop
  .done
  RTS
}

; Writes DP $08 (16-bit Tile16) at world px (DP $0C, DP $0A), saving original
; $7E2000 offset & Tile16 for teardown. Enters DBR=$00, returns M=8/X=8.
HorseGame_ApplyTile16At:
{
  REP #$30
  LDA.b $0A : SEC : SBC.l $7E0708 : AND.l $7E070A : ASL #3 : STA.b $06
  LDA.b $0C : LSR #3 : SEC : SBC.l $7E070C : AND.l $7E070E : ORA.b $06 : TAY ; Y = $7E2000 offset

  SEP #$20
  LDA.l HorseGame_SavedTileCount : CMP.b #$10 : BCS .skip_save
    INC : STA.l HorseGame_SavedTileCount
    DEC
    REP #$20
    AND.w #$00FF : ASL : TAX
    TYA : STA.l HorseGame_SavedTileOffsets, X
    PHX
    TYX
    LDA.l $7E2000, X
    PLX
    STA.l HorseGame_SavedTileValues, X
  .skip_save
  REP #$30
  TYX
  LDA.b $08
  JSL !HorseGame_DrawMap16Persist
  SEP #$30
  LDA.b #$01 : STA.b $14
  RTS
}

; Restores all Tile16 cells saved in HorseGame_SavedTileOffsets/Values.
HorseGame_RestoreAreaTiles:
{
  LDA.l HorseGame_SavedTileCount : BEQ .done
  REP #$30
  AND.w #$00FF : DEC : ASL : TAX
  .loop
    PHX
    LDA.l HorseGame_SavedTileValues, X : PHA
    LDA.l HorseGame_SavedTileOffsets, X : TAX
    PLA
    JSL !HorseGame_DrawMap16Persist
    PLX
    DEX : DEX : BPL .loop
  SEP #$30
  LDA.b #$01 : STA.b $14
  LDA.b #$00 : STA.l HorseGame_SavedTileCount
  .done
  RTS
}

; Spawns stationary archery enemy targets matching CourseId & $8A into sprite slots 0..3.
HorseGame_SpawnTargetsForArea:
{
  LDA.b #$00 : STA.l HorseGame_TargetCount : STA.l HorseGame_TargetsLeft
  STZ.b $00                           ; DP $00 = table byte offset (stride 8)
  .loop
    LDX.b $00
    LDA.l HorseGame_TargetTable, X : CMP.b #$FF : BNE + : JMP .done : +
    CMP.l HorseGame_CourseId : BEQ + : JMP .next : +
    LDA.l HorseGame_TargetTable+1, X : CMP.b $8A : BEQ + : JMP .next : +
      LDA.l HorseGame_TargetCount : CMP.b #$04 : BCC + : JMP .next : +
      STA.b $01                       ; hold target slot in DP $01
      LDA.l HorseGame_TargetTable+2, X : PHA
      LDA.b $01 : TAX                 ; X = sprite slot 0..3
      LDA.b #$09 : STA.w $0DD0, X     ; active sprite state
      PLA : STA.w $0E20, X            ; sprite ID ($08 Octorok)
      JSL !HorseGame_SpriteLoadProperties
      SEP #$30
      LDY.b $01                       ; Y = sprite slot 0..3
      LDX.b $00                       ; X = table byte offset
      LDA.l HorseGame_TargetTable+4, X : STA.w $0D10, Y
      LDA.l HorseGame_TargetTable+5, X : STA.w $0D30, Y
      LDA.l HorseGame_TargetTable+6, X : STA.w $0D00, Y
      LDA.l HorseGame_TargetTable+7, X : STA.w $0D20, Y
      LDA.b #$01 : STA.w $0E50, Y     ; 1 HP -> single mounted arrow kills cleanly
      LDA.b #$03 : STA.w $0F50, Y     ; palette 1 (SP-1 red) + page 1
      LDA.w $0CAA, Y : ORA.b #$80 : STA.w $0CAA, Y ; persist off-camera across 1024x1024 OW $00
      LDA.b #$00
      STA.w $0BE0, Y                  ; zero prize drop so hearts/fairies don't spawn
      STA.w $0D40, Y : STA.w $0D50, Y
      STA.w $0D80, Y : STA.w $0E00, Y
      STA.w $0E30, Y : STA.w $0EF0, Y
      STA.w $0F00, Y : STA.w $0F20, Y : STA.w $0F70, Y
      PHX : TYX : LDA.b #$00 : STA.l $7FF9C2, X : PLX ; clear water-tile subtype flag
      LDA.b #$02 : STA.w $0DE0, Y     ; face south
      LDA.b #$01 : STA.w $0EC0, Y     ; Octorok .wait state (skip Move/CheckTileCollision)
      LDA.b #$40 : STA.w $0DF0, Y     ; hold timer nonzero (no movement/rock throw)
      LDA.l HorseGame_TargetCount : INC : STA.l HorseGame_TargetCount
      STA.l HorseGame_TargetsLeft
    .next
    LDA.b $00 : CLC : ADC.b #$08 : STA.b $00
    JMP .loop
  .done
  RTS
}

; Re-anchors live targets (state $09) on their course coordinates, prevents
; wander/rock-spit AI, and updates HorseGame_TargetsLeft + HorseGame_Score.
HorseGame_UpdateTargets:
{
  STZ.b $00                           ; alive count accumulator
  LDX.b #$00                          ; table offset
  LDY.b #$00                          ; target slot index 0..3
  .loop
    LDA.l HorseGame_TargetTable, X : CMP.b #$FF : BEQ .done
    CMP.l HorseGame_CourseId : BNE .next
    LDA.l HorseGame_TargetTable+1, X : CMP.l HorseGame_ActiveArea : BNE .next
      CPY.b #$04 : BCS .done
      LDA.w $0DD0, Y : CMP.b #$09 : BNE .not_alive
        INC.b $00
        LDA.w $0EF0, Y : BNE .next_slot ; allow hit flash/recoil frame cleanly
        LDA.l HorseGame_TargetTable+4, X : STA.w $0D10, Y
        LDA.l HorseGame_TargetTable+5, X : STA.w $0D30, Y
        LDA.l HorseGame_TargetTable+6, X : STA.w $0D00, Y
        LDA.l HorseGame_TargetTable+7, X : STA.w $0D20, Y
        LDA.b #$00
        STA.w $0D40, Y : STA.w $0D50, Y
        STA.w $0D80, Y : STA.w $0E00, Y
        STA.w $0E30, Y : STA.w $0F00, Y
        LDA.b #$01 : STA.w $0EC0, Y
        LDA.b #$40 : STA.w $0DF0, Y
      .not_alive
      .next_slot
      INY
    .next
    TXA : CLC : ADC.b #$08 : TAX
    BRA .loop
  .done
  LDA.b $00 : STA.l HorseGame_TargetsLeft
  LDA.l HorseGame_TargetCount : SEC : SBC.l HorseGame_TargetsLeft
  STA.l HorseGame_Score
  RTS
}

; Carry set if any target slot 0..TargetCount-1 still has nonzero $0DD0 (dying poof).
HorseGame_AnyTargetSlotBusy:
{
  LDA.l HorseGame_TargetCount : BEQ .clear
  DEC : TAX
  .scan
    LDA.w $0DD0, X : BNE .busy
    DEX : BPL .scan
  .clear
  CLC
  RTS
  .busy
  SEC
  RTS
}

; Per-course configuration tables.
HorseGame_CourseEnemyAA3:
  db $04                              ; Course 0: swap $0AA3 to $04 (Octorok sheet)
  db $FF                              ; Course 1: keep current area's sprite sheet

HorseGame_CourseInitTimers:
  dw $0E10                            ; Course 0: 3600 frames (~60 s)
  dw $0E10                            ; Course 1: 3600 frames (~60 s)

; Overlay Tile16 entries: db course_id, area_id; dw wx, wy, tile16_id
HorseGame_OverlayTable:
  ; Course 0 (Toto Ranch OW $00): solid exit corridor barrier ($00CB) + hurdle ($007B)
  db $00, $00 : dw 608,  704, $00CB
  db $00, $00 : dw 624,  704, $00CB
  db $00, $00 : dw 640,  704, $00CB
  db $00, $00 : dw 656,  704, $00CB
  db $00, $00 : dw 480,  672, $007B
  ; Course 1 (Kalyxo Multi-Area Route): bridge hurdle ($007B) on OW $11
  db $01, $11 : dw 912, 1376, $007B
  db $FF

; Target entries (stride 8): db course_id, area_id, sprite_id, flags; dw wx, wy
HorseGame_TargetTable:
  db $00, $00, $08, $00 : dw 416, 656
  db $00, $00, $08, $00 : dw 464, 640
  db $00, $00, $08, $00 : dw 512, 656
  db $00, $00, $08, $00 : dw 544, 656
  db $FF

; Toto Ranch Kid ($3C) start trigger, called from HorseForm_FrameTick after
; HorseForm_SuppressMountedButtons (before Link reads A). M=8, X=8, DBR=$00.
; Mounted on OW $00 + new A while touching the Kid starts Course 0. A is
; consumed so it neither opens the Kid's message nor starts a Pegasus dash.
; Preserves X/Y. A and scratch $00-$0F clobbered.
HorseGame_KidStartCheck:
{
  LDA.b $F6 : BPL .done
  LDA.b $1B : ORA.b $8A : BNE .done
  LDA.l HorseGame_State : BNE .done
  LDA.l Horse_State : BNE .done
  PHX : PHY
  LDX.b #$0F
  .scan
    LDA.w $0DD0, X : CMP.b #$09 : BNE .next
    LDA.w $0E20, X : CMP.b #$3C : BNE .next
    JSL !HorseGame_CheckTouchLink : BCS .start
  .next
    DEX : BPL .scan
  PLY : PLX
  .done
  RTL

  .start
  LDA.b #$80 : TRB.b $F6
  LDA.b #$40 : STA.w $0F10, X
  LDA.l $7EF340 : BEQ .no_bow
  LDA.l $7EF377 : BEQ .no_bow
    LDA.b #$04 : STA.l HorseGame_State
    STZ.w $1CE8
    LDA.b #!HorseGame_MsgKidMountedPrompt&$FF
    LDY.b #!HorseGame_MsgKidMountedPrompt>>8
    JSL !HorseGame_ShowMessageUncond
    PLY : PLX
    RTL
  .no_bow
  LDA.b #!HorseGame_MsgKidMountedNoBow&$FF
  LDY.b #!HorseGame_MsgKidMountedNoBow>>8
  JSL !HorseGame_ShowMessageUncond
  PLY : PLX
  RTL
}

HorseGame_End:
assert pc() <= $53EFF0, "Horse minigame engine exceeded bank53 allocation ($53E900-$53EFF0)"
pullpc

pushpc
; USDASM Sprite_3C_KidInKak .dont_discuss_quest ($05FF96): after the Ocarina
; ($7EF34C >= 1), replace vanilla $0148 hotel hint with $0227 (sister cured +
; Epona's Song mounted target practice invitation).
org $05FF96 ; @hook module=Masks name=HorseGame_KidPostOcarinaMsg kind=data
  LDA.b #!HorseGame_MsgKidOnFoot&$FF
  LDY.b #!HorseGame_MsgKidOnFoot>>8
assert pc() == $05FF9A
pullpc
