; King, Zelda-sprite visit, and matched empty Kalyxo hall.
; Uses the existing three room-card slots, narration and scene timers.
assert !ENABLE_CUSTOM_ATTRACT_SEQUENCE == 1, "Royal scenes require custom attract history"

org $0CEEF0 ; @hook module=Dungeons name=AttractRoyal_LoadVectors kind=data
  dw AttractRoyal_LoadCard, AttractRoyal_LoadCard, AttractRoyal_LoadCard
assert pc() == $0CEEF6

org $0CF120 ; @hook module=Dungeons name=AttractRoyal_DrawVectors kind=data
  dw AttractRoyal_DrawCard, AttractRoyal_DrawCard, AttractRoyal_DrawCard
assert pc() == $0CF126

org $0CF194 ; @hook module=Dungeons name=AttractMapZoomHook kind=hook
  JSR AttractMap_ZoomTrampoline
assert pc() == $0CF197

; Reuse only the three retired puppet routines and their data. Keep the
; map/conclusion, text helper, common graphics and preloaded-sprite helper.
org $0CF1AE
AttractRoyal_LoadCard:
{
  ; Entry is the bank $0C attract vector, M/X=8. The room loader borrows
  ; $20/$22, so preserve both 16-bit words as the original cards did.
  ; The nested $0090E3 tilemap uploader reads bank-$00 tables through DBR.
  ; Keep the original attract caller's DBR=$00; use long local-table reads.
  PHB
  LDA.b #$00 : PHA : PLB
  LDA.b #$80 : STA.b $13 : STA.w $2100
  STZ.w $420C : STZ.b $9B
  STZ.b $99
  LDA.b #$20 : STA.b $9A
  LDA.b #$0A : STA.w $0AA4
  JSL LoadCommonSprites_long
  REP #$20
  LDA.b $20 : PHA
  LDA.b $22 : PHA
  SEP #$20
  LDA.b $23 : SEC : SBC.b #$02 : TAX
  LDA.l .entrance, X
  JSL Underworld_LoadAndDrawEntranceRoom
  REP #$20
  PLA : STA.b $22
  PLA : STA.b $20
  SEP #$20

  ; Keep each room's sub-blockset and palette. Only card 4 ($23=$03, room $61,
  ; entrance $04) loads cave main group $04 and needs the castle main group $02
  ; override; both great-hall cards ($23=$02 and $23=$04, room $51, entrance $74)
  ; already load castle main group $02.
  LDA.b $23 : CMP.b #$03 : BNE .main_gfx_ready
    LDA.b #$02 : STA.w $0AA1
  .main_gfx_ready
  STZ.w $0AAC
  LDA.b #$0E : STA.w $0AAD
  LDA.b #$03 : STA.w $0AAE
  LDA.b #$0C : STA.w $0AA3 ; spriteset $0C = $51,$43,$55,$42: slot 3 = sheet $42 (Kydrog NPC)
  JSL $00E19B ; InitializeTilesets with the loaded room's BG groups
  LDA.b #$02 : STA.w $0AA9
  INC.b $15
  JSL Underworld_LoadAllPalettes
  LDA.b $23 : CMP.b #$04 : BNE .palettes_ready
    ; Card 4 ($1C3): OBJ palette 6 ($7EC6C2-$7EC6CE) is Kydrog's Abyss
    ; silhouette (shadow black with glowing crimson eye at index 2).
    REP #$20
    LDA.w #$0000
    STA.l $7EC6C2 : STA.l $7EC6C6 : STA.l $7EC6C8
    STA.l $7EC6CA : STA.l $7EC6CC : STA.l $7EC6CE
    LDA.w #$0016 : STA.l $7EC6C4
    SEP #$20
  .palettes_ready
  JSL AttractRoyal_UploadGfx

  ; Normal intro/dungeon BG bases, after the preceding Mode7 map card.
  LDA.b #$09 : STA.b $94 : STA.w $2105
  LDA.b #$13 : STA.w $2107
  LDA.b #$03 : STA.w $2108
  LDA.b #$63 : STA.w $2109
  LDA.b #$22 : STA.w $210B
  LDA.b #$07 : STA.w $210C

  ; Scroll values are room-local modulo $200, matching the renderer's
  ; accepted 256x224 crops.
  LDA.b $23 : SEC : SBC.b #$02 : ASL A : TAX
  REP #$20
  LDA.w #$0080 : STA.b $E0 : STA.b $E2 : STA.w $011E : STA.w $0120
  LDA.l .camera_y, X : STA.b $E6 : STA.b $E8 : STA.w $0122 : STA.w $0124
  LDA.l .frames, X : STA.b $64
  SEP #$20
  LDA.b $23 : SEC : SBC.b #$02 : TAX
  LDA.l .message, X : STA.w $1CF0
  LDA.b #$01 : STA.w $1CF1
  STZ.w $1CD8
  STZ.b $50 : STZ.b $51 : STZ.b $52
  STZ.b $5E : STZ.b $5F
  LDA.b #$FF : STA.b $25
  PLB
  JMP AttractScene_AdvanceFromDungeon

  .entrance
    db $74, $04, $74 ; room $51, room $61, room $51
  .message
    db !AttractMsg_Throne, !AttractMsg_Prison, !AttractMsg_Altar
  .camera_y
    dw $0040, $0050, $0040
  .frames
    dw !AttractFrames_Throne, !AttractFrames_Prison, !AttractFrames_Altar
}

AttractRoyal_DrawCard:
{
  ; Entry/exit M/X=8.
  PHB : PHK : PLB
  STZ.b $2A
  LDA.b $52 : BNE .text
    LDA.b $13 : CMP.b #$0F : BEQ .lit
      INC.b $13
      BRA .text
    .lit
      INC.b $52
  .text
  JSR Attract_DoTextInDungeonScene
  JSL AttractRoyal_DrawCastLong

  REP #$20
  LDA.b $64
  SEP #$20
  BNE .exit
    LDA.b $13 : BEQ .advance
    LDA.b $1A : AND.b #$01 : BNE .exit
      DEC.b $13
      BRA .exit
    .advance
      INC.b $23
      DEC.b $22 : DEC.b $22 : DEC.b $22
  .exit
  PLB
  RTL
}

AttractRoyal_UploadGfx:
{
  ; Called only after the room/palette loader, under forced blank.
  ; M=8, X=8; DBR is preserved. DMA channel 0 matches InitializeTilesets.
  ; Card 4 ($23 == $04) uploads $1800 bytes (slots 0-2, VRAM $5000-$5BFF)
  ; so slot 3 (VRAM $5C00-$5FFF) keeps Kydrog's sheet $42 from $0AA3=$0C.
  PHB
  LDA.b #$00 : PHA : PLB
  LDA.b #$80 : STA.b $13 : STA.w $2100
  LDA.b #$80 : STA.w $2115
  LDX.b #$20
  LDA.b $23 : CMP.b #$04 : BNE .full_window
    LDX.b #$18
  .full_window
  STZ.w $4305
  STX.w $4306
  REP #$20
  LDA.w #$5000 : STA.w $2116
  LDA.w #$1801 : STA.w $4300
  LDA.w #AttractRoyal_Gfx : STA.w $4302
  SEP #$20
  LDA.b #AttractRoyal_Gfx>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  PLB
  RTL
}

AttractRoyal_CodeEnd:
; Vanilla Attract_SkipToFileSelect ($0CF700, Start press) and Attract_BuildNextImageTilemap
; ($0CF72E-$0CF765, storybook) stay live with royal scenes on, so the ceiling is $0CF700.
assert read1($0CF700) == $C6, "Vanilla Attract_SkipToFileSelect entry at $0CF700 was overwritten"
assert pc() <= $0CF700 ; Start-skip, storybook and Attract_DoTextInDungeonScene remain untouched

; 7-byte tail trampoline in unused $0CFFB1-$0CFFFF for Scene 1 Mode 7 pan.
pushpc
org $0CFFB1 ; @hook module=Dungeons name=AttractMapZoomTrampoline kind=hook
AttractMap_ZoomTrampoline:
  JSL AttractMap_Pan
  JMP $F783 ; Attract_ControlMapZoom (returns via RTS to $0CF197)
assert pc() <= $0D0000
pullpc

; Bank $58 attract engine + generated pose/cast/track tables ($58F000-$58FFFF).
pushpc
org $58F000

; Draw all cast actors for the current royal card ($23 = 2..4).
; Entry/exit M=8, X=8; DBR preserved.
AttractRoyal_DrawCastLong:
{
  PHB : PHK : PLB
  LDA.b $23 : SEC : SBC.b #$02 : ASL A : TAX
  REP #$20
  LDA.w AttractRoyal_CastPointers,X : STA.b $00
  SEP #$20
  LDY.b #$00
  LDA.b ($00),Y : BEQ .done
  STA.b $0B
  INY : STY.b $0A
  STZ.b $50
  .actor
    LDY.b $0A
    LDA.b ($00),Y : STA.b $51
    INY : LDA.b ($00),Y : STA.b $28
    INY : LDA.b ($00),Y : STA.b $29
    INY : STY.b $0A
    STZ.b $0D
    JSL AttractRoyal_RunTracks
    BCS .skip_actor
      JSL AttractRoyal_DrawPoseLong
    .skip_actor
    INC.b $50
    DEC.b $0B : BNE .actor
  .done
  PLB
  RTL
}

; Data-driven choreography interpreter keyed to $64 countdown timer.
; Entry: M=8, X=8, $23 = scene (2..4), $50 = actor record index,
;        $51 = pose_id, $28/$29 = screen X/Y, $0D = prop XOR mask ($00/$40),
;        $64 = 16-bit card countdown timer.
; Exit: M=8, X=8, DBR preserved. CLC = draw ($51/$28/$29/$0D updated), SEC = skip actor.
AttractRoyal_RunTracks:
{
  PHB : PHK : PLB
  STZ.b $0C ; hidden flag
  LDA.b $23 : SEC : SBC.b #$02 : ASL A : TAX
  REP #$20
  LDA.w AttractRoyal_TrackPointers,X : STA.b $0E
  SEP #$20

.record_loop
  LDY.b #$00
  LDA.b ($0E),Y
  CMP.b #$FF : BNE +
    JMP .finish
  +
  CMP.b $50 : BEQ +
    JMP .next_record
  +
  LDY.b #$08 : LDA.b ($0E),Y : STA.b $40 ; flags

  LDY.b #$01
  REP #$20
  LDA.b ($0E),Y ; t_start
  CMP.b $64
  BCS .started
    ; $64 > t_start: track has not started yet.
    SEP #$20
    LDA.b $40 : AND.b #$04 ; BLINK_IN
    BNE +
      JMP .next_record
    +
    INC.b $0C
    JMP .next_record

  .started
  LDY.b #$03
  LDA.b ($0E),Y ; t_end
  CMP.b $64
  BCC .in_progress

  ; --- Finished ($64 <= t_end) ---
  SEP #$20
  LDA.b $40
  BIT.b #$0A ; BLINK_OUT ($02) or HIDE ($08)
  BEQ +
    INC.b $0C
    JMP .next_record
  +
  BIT.b #$10 ; FLIP_H
  BEQ +
    LDA.b $0D : EOR.b #$40 : STA.b $0D
  +
  LDY.b #$07 : LDA.b ($0E),Y ; pose
  CMP.b #$FF : BEQ +
    STA.b $51
  +
  LDY.b #$05 : LDA.b ($0E),Y ; dx
  CLC : ADC.b $28 : STA.b $28
  INY : LDA.b ($0E),Y ; dy
  CLC : ADC.b $29 : STA.b $29
  JMP .next_record

  ; --- In progress (t_end < $64 <= t_start) ---
  .in_progress
  LDY.b #$01
  LDA.b ($0E),Y ; t_start
  SEC : SBC.b $64
  STA.b $42 ; 16-bit elapsed
  SEP #$20

  LDA.b $40
  BIT.b #$08 ; HIDE
  BEQ +
    INC.b $0C
    JMP .next_record
  +
  BIT.b #$02 ; BLINK_OUT
  BEQ .chk_blink_in
    LDA.b $64 : AND.b #$02 : BNE .chk_pose_start
      INC.b $0C
      JMP .next_record
  .chk_blink_in
  LDA.b $40 : BIT.b #$04 ; BLINK_IN
  BEQ .chk_pose_start
    LDA.b $64 : AND.b #$02 : BEQ .chk_pose_start
      INC.b $0C
      JMP .next_record

  .chk_pose_start
  LDA.b $40 : BIT.b #$01 ; POSE_ON_START
  BEQ .chk_motion
    LDY.b #$07 : LDA.b ($0E),Y
    CMP.b #$FF : BEQ +
      STA.b $51
    +
    LDA.b $40 : BIT.b #$10 ; FLIP_H
    BEQ .chk_motion
      LDA.b $0D : EOR.b #$40 : STA.b $0D

  .chk_motion
  LDY.b #$05 : LDA.b ($0E),Y
  INY : ORA.b ($0E),Y
  BEQ .next_record

  LDY.b #$09 : LDA.b ($0E),Y ; shift
  CMP.b #$FF : BEQ .linear_motion
  TAX
  REP #$20
  LDA.b $42
  CPX.b #$00 : BEQ .shift_done
  - : LSR A : DEX : BNE -
  .shift_done
  CMP.w #$0080 : BCC +
    LDA.w #$007F
  +
  SEP #$20
  STA.b $44 ; step

  LDY.b #$05 : LDA.b ($0E),Y : BEQ .apply_dy
  BPL .dx_pos
    EOR.b #$FF : INC A
    CMP.b $44 : BCC + : LDA.b $44 : +
    STA.b $45
    LDA.b $28 : SEC : SBC.b $45 : STA.b $28
    BRA .apply_dy
  .dx_pos
    CMP.b $44 : BCC + : LDA.b $44 : +
    CLC : ADC.b $28 : STA.b $28

  .apply_dy
  LDY.b #$06 : LDA.b ($0E),Y : BEQ .next_record
  BPL .dy_pos
    EOR.b #$FF : INC A
    CMP.b $44 : BCC + : LDA.b $44 : +
    STA.b $45
    LDA.b $29 : SEC : SBC.b $45 : STA.b $29
    BRA .next_record
  .dy_pos
    CMP.b $44 : BCC + : LDA.b $44 : +
    CLC : ADC.b $29 : STA.b $29

  .next_record
  REP #$20
  LDA.b $0E : CLC : ADC.w #$000A : STA.b $0E
  SEP #$20
  JMP .record_loop

  .linear_motion
  REP #$20
  LDY.b #$01 : LDA.b ($0E),Y
  LDY.b #$03 : SEC : SBC.b ($0E),Y
  STA.b $46 ; 16-bit duration
  SEP #$20

  LDY.b #$05 : LDA.b ($0E),Y : BEQ .lin_dy
  JSR .scale_axis
  CLC : ADC.b $28 : STA.b $28

  .lin_dy
  LDY.b #$06 : LDA.b ($0E),Y : BEQ .next_record
  JSR .scale_axis
  CLC : ADC.b $29 : STA.b $29
  BRA .next_record

  .scale_axis
  {
    STZ.b $45
    BPL +
      EOR.b #$FF : INC A
      INC.b $45
    +
    STA.l $004202
    LDA.b $42 : STA.l $004203
    NOP #4
    REP #$20
    LDA.l $004216 : STA.b $48
    SEP #$20
    STZ.b $4A
    LDA.b $43 : BEQ .div_start
      STA.l $004203
      NOP #4
      REP #$20
      LDA.l $004216
      CLC : ADC.b $49 : STA.b $49
      SEP #$20
    .div_start
    STZ.b $4B : STZ.b $4C
    LDX.b #$18
    .div_loop
      ASL.b $48 : ROL.b $49 : ROL.b $4A
      ROL.b $4B : ROL.b $4C
      BCS .div_sub
      REP #$20
      LDA.b $4B
      CMP.b $46
      BCC .div_no_sub
      .div_sub
        REP #$20
        LDA.b $4B
        SEC : SBC.b $46
        STA.b $4B
        SEP #$20
        INC.b $48
        BRA .div_next
      .div_no_sub
      SEP #$20
    .div_next
      DEX : BNE .div_loop
    LDA.b $48
    LDX.b $45 : BEQ +
      EOR.b #$FF : INC A
    +
    RTS
  }

.finish
  LDA.b $0C : BNE .skip
    CLC
    PLB
    RTL
  .skip
    SEC
    PLB
    RTL
}

; Long pose OAM writer (24-bit [dp],Y reads from Bank $58, DBR=$00 for WRAM OAM).
; Entry: M=8, X=8, $51 = pose_id, $28/$29 = screen X/Y, $2A = OAM slot, $0D = prop XOR.
; Exit:  M=8, X=8, DBR preserved, $2A updated.
AttractRoyal_DrawPoseLong:
{
  PHB
  LDA.b #$00 : PHA : PLB
  LDA.b $51 : STA.b $2F : ASL A : CLC : ADC.b $2F : TAX ; X = pose_id * 3
  REP #$20
  LDA.l AttractRoyal_Pose_size,X : STA.b $2D
  LDA.l AttractRoyal_Pose_x,X    : STA.b $30
  LDA.l AttractRoyal_Pose_y,X    : STA.b $33
  LDA.l AttractRoyal_Pose_char,X : STA.b $36
  LDA.l AttractRoyal_Pose_prop,X : STA.b $39
  SEP #$20
  LDA.l AttractRoyal_Pose_size+2,X : STA.b $2F
  LDA.l AttractRoyal_Pose_x+2,X    : STA.b $32
  LDA.l AttractRoyal_Pose_y+2,X    : STA.b $35
  LDA.l AttractRoyal_Pose_char+2,X : STA.b $38
  LDA.l AttractRoyal_Pose_prop+2,X : STA.b $3B
  LDX.b $51
  LDA.l AttractRoyal_PoseCounts,X : BEQ .done
  TAY : DEY
  .next_object
    LDX.b $2A
    CPX.b #$40 : BCS .done
    LDA.b [$2D],Y
    STA.w $0A60,X
    TXA
    ASL A
    ASL A
    TAX
    LDA.b [$30],Y
    CLC
    ADC.b $28
    STA.w $0900,X
    LDA.b [$33],Y
    CLC
    ADC.b $29
    STA.w $0901,X
    LDA.b [$36],Y
    STA.w $0902,X
    LDA.b [$39],Y
    EOR.b $0D
    STA.w $0903,X
    INC.b $2A
    DEY
    BPL .next_object
  .done
  PLB
  RTL
}

; Interpolate Scene 1 Mode 7 center ($0638/$063A) and BG1 scroll ($0120/$0124)
; along AttractMap_Keyframes as $0637 steps from $FF down to $00.
; Entry/exit: M=8, X=8; preserves DBR and $0637. Clobbers A, X, Y, $00-$07.
AttractMap_Pan:
{
  PHB
  LDA.b #$00 : PHA : PLB ; DBR=$00 for WRAM ($0637..$063B, $0120..$0125) and MMIO ($4202..$4217)
  LDX.b #$00
  .find_seg
    LDA.w $0637
    CMP.l AttractMap_Keyframes+0,X ; $0637 >= t_end?
    BCS .found
    TXA : CLC : ADC.b #$0A : TAX
    BRA .find_seg
  .found
  LDA.l AttractMap_Keyframes+1,X ; t_start
  SEC : SBC.w $0637
  STA.b $00 ; elapsed = t_start - t
  LDA.l AttractMap_Keyframes+1,X
  SEC : SBC.l AttractMap_Keyframes+0,X
  STA.b $01 ; span = t_start - t_end
  STX.b $02 ; save segment offset across 16-bit sections

  ; X axis: M7X ($0638) and BG1HOFS ($0120 = M7X - $0080)
  REP #$20
  LDA.l AttractMap_Keyframes+6,X : STA.b $04 ; dx (signed 16-bit)
  LDA.l AttractMap_Keyframes+2,X             ; x0
  JSR .interp_axis
  STA.w $0638
  SEC : SBC.w #$0080 : STA.w $0120

  ; Y axis: M7Y ($063A) and BG1VOFS ($0124 = M7Y - $002D)
  SEP #$20
  LDX.b $02
  REP #$20
  LDA.l AttractMap_Keyframes+8,X : STA.b $04 ; dy (signed 16-bit)
  LDA.l AttractMap_Keyframes+4,X             ; y0
  JSR .interp_axis
  STA.w $063A
  SEC : SBC.w #$002D : STA.w $0124

  SEP #$30
  PLB
  RTL

; Compute A = base (entry A, 16-bit) + (elapsed * signed $04) / span.
; Entry: M=16, X=8, DBR=$00, $00=elapsed, $01=span, $04=signed 16-bit delta.
; Exit:  M=16, A=result.
.interp_axis
  STA.b $06
  LDY.b #$00
  LDA.b $04
  BEQ .axis_done
  BPL .delta_pos
    EOR.w #$FFFF : INC A
    INY
  .delta_pos
  SEP #$20
  PHA
  LDA.b $00 : STA.w WRMPYA
  PLA       : STA.w WRMPYB
  NOP : NOP : NOP : NOP
  REP #$20
  LDA.w RDMPYL
  STA.w WRDIVL
  SEP #$20
  LDA.b $01 : STA.w WRDIVB
  NOP : NOP : NOP : NOP
  NOP : NOP : NOP : NOP
  REP #$20
  LDA.w RDDIVL
  CPY.b #$00 : BEQ .apply_off
    EOR.w #$FFFF : INC A
  .apply_off
  CLC : ADC.b $06
  RTS
.axis_done
  LDA.b $06
  RTS
}

; Keyframe segments (10 bytes each):
;   db t_end, t_start
;   dw x0, y0
;   dw dx, dy (signed 16-bit)
; Whole-island overview ($0100, $00F6) -> ($0100, $00EE) -> Castle $0B ($00FE, $00AE) hold.
AttractMap_Keyframes:
  db $C0, $FF : dw $0100, $00F6, $0000, $FFF8 ; t=$FF..$C0: dy=-8
  db $30, $C0 : dw $0100, $00EE, $FFFE, $FFC0 ; t=$C0..$30: dx=-2, dy=-64
  db $00, $30 : dw $00FE, $00AE, $0000, $0000 ; t=$30..$00: hold Castle $0B

incsrc "Data/attract_royal_poses.asm"

assert pc() <= $590000 ; stays in Bank $58
pullpc
