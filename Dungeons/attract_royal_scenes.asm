; King, Zelda-sprite visit, and matched empty Kalyxo hall.
; Uses the existing three room-card slots, narration and scene timers.
assert !ENABLE_CUSTOM_ATTRACT_SEQUENCE == 1, "Royal scenes require custom attract history"

org $0CEEF0 ; @hook module=Dungeons name=AttractRoyal_LoadVectors kind=data
  dw AttractRoyal_LoadCard, AttractRoyal_LoadCard, AttractRoyal_LoadCard
assert pc() == $0CEEF6

org $0CF120 ; @hook module=Dungeons name=AttractRoyal_DrawVectors kind=data
  dw AttractRoyal_DrawCard, AttractRoyal_DrawCard, AttractRoyal_DrawCard
assert pc() == $0CF126

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

  ; Keep each room's sub-blockset and palette. Entrance $04 uses cave main
  ; group $04 (sheets $02/$03/$12); the royal/empty hall needs the audience
  ; hall's castle main group $02 ($00/$01/$10), with identical room geometry.
  LDA.b $23 : CMP.b #$02 : BEQ .main_gfx_ready
    LDA.b #$02 : STA.w $0AA1
  .main_gfx_ready
  STZ.w $0AAC
  LDA.b #$0E : STA.w $0AAD
  LDA.b #$03 : STA.w $0AAE
  LDA.b #$7E : STA.w $0AA3
  JSL $00E19B ; InitializeTilesets with the loaded room's BG groups
  LDA.b #$02 : STA.w $0AA9
  INC.b $15
  JSL Underworld_LoadAllPalettes
  JSL AttractRoyal_UploadGfx

  ; Normal intro/dungeon BG bases, after the preceding Mode7 map card.
  LDA.b #$09 : STA.b $94 : STA.w $2105
  LDA.b #$13 : STA.w $2107
  LDA.b #$03 : STA.w $2108
  LDA.b #$63 : STA.w $2109
  LDA.b #$22 : STA.w $210B
  LDA.b #$07 : STA.w $210C

  ; Scroll values are room-local modulo $200, matching the renderer's
  ; accepted 256x224 crops. The visit and empty card use identical values.
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
    db $74, $04, $04 ; existing entrances to room $51 and room $61
  .message
    db !AttractMsg_Throne, !AttractMsg_Prison, !AttractMsg_Altar
  .camera_y
    dw $0040, $0050, $0050
  .frames
    dw !AttractFrames_Throne, !AttractFrames_Prison, !AttractFrames_Altar
}

AttractRoyal_DrawCard:
{
  ; Entry/exit M/X=8. $00-$0B and $2D are the existing attract draw scratch.
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
  LDA.b $23 : SEC : SBC.b #$02 : ASL A : TAX
  REP #$20
  LDA.w .cast, X : STA.b $00
  SEP #$20
  LDY.b #$00
  LDA.b ($00), Y : STA.b $0B
  INY : STY.b $0A
  .actor
    LDY.b $0A
    LDA.b ($00), Y : ASL A : TAX
    REP #$20
    LDA.w AttractRoyal_Pose_x, X : STA.b $02
    LDA.w AttractRoyal_Pose_y, X : STA.b $04
    LDA.w AttractRoyal_Pose_char, X : STA.b $06
    LDA.w AttractRoyal_Pose_prop, X : STA.b $08
    LDA.w AttractRoyal_Pose_size, X : STA.b $2D
    SEP #$20
    INY : LDA.b ($00), Y : STA.b $28
    INY : LDA.b ($00), Y : STA.b $29
    INY : STY.b $0A
    LDA.w AttractRoyal_PoseCounts, X : TAY : DEY
    JSR Attract_DrawPreloadedSprite
    DEC.b $0B : BNE .actor

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

  .cast
    dw AttractRoyal_Cast_audience, AttractRoyal_Cast_visit, AttractRoyal_Cast_empty
}

AttractRoyal_UploadGfx:
{
  ; Called only after the room/palette loader, under forced blank.
  ; M=8, X=8; DBR is preserved. DMA channel 0 matches InitializeTilesets.
  PHB
  LDA.b #$00 : PHA : PLB
  LDA.b #$80 : STA.b $13 : STA.w $2100
  LDA.b #$80 : STA.w $2115
  REP #$20
  LDA.w #$5000 : STA.w $2116
  LDA.w #$1801 : STA.w $4300
  LDA.w #AttractRoyal_Gfx : STA.w $4302
  LDA.w #$2000 : STA.w $4305
  SEP #$20
  LDA.b #AttractRoyal_Gfx>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  PLB
  RTL
}


incsrc "Data/attract_royal_poses.asm"
AttractRoyal_CodeEnd:
assert pc() <= $0CF766 ; Attract_DoTextInDungeonScene remains untouched
