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
  STZ.b $50
  .actor
    LDY.b $0A
    LDA.b ($00), Y : STA.b $51
    INY : LDA.b ($00), Y : STA.b $28
    INY : LDA.b ($00), Y : STA.b $29
    INY : STY.b $0A
    JSL AttractRoyal_AnimateActor
    BCS .skip_actor
    LDA.b $51 : CMP.b #$0B : BCS .kydrog_pose
      ASL A : TAX
      REP #$20
      LDA.w AttractRoyal_Pose_x, X : STA.b $02
      LDA.w AttractRoyal_Pose_y, X : STA.b $04
      LDA.w AttractRoyal_Pose_char, X : STA.b $06
      LDA.w AttractRoyal_Pose_prop, X : STA.b $08
      LDA.w AttractRoyal_Pose_size, X : STA.b $2D
      SEP #$20
      LDA.w AttractRoyal_PoseCounts, X : TAY : DEY
      BRA .draw_pose
    .kydrog_pose
      REP #$20
      LDA.w #AttractRoyal_kydrog_x : STA.b $02
      LDA.w #AttractRoyal_kydrog_y : STA.b $04
      LDA.w #AttractRoyal_kydrog_char : STA.b $06
      LDA.w #AttractRoyal_kydrog_sil_prop
      LDX.b $51 : CPX.b #$0B : BEQ .set_kydrog_prop
        LDA.w #AttractRoyal_kydrog_idle_prop
      .set_kydrog_prop
      STA.b $08
      LDA.w #AttractRoyal_kydrog_size : STA.b $2D
      SEP #$20
      LDY.b #$05 ; 6 pieces
    .draw_pose
    JSR Attract_DrawPreloadedSprite
    .skip_actor
    INC.b $50
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
    dw AttractRoyal_Cast_audience, AttractRoyal_Cast_visit, AttractRoyal_StoryCast_empty
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


incsrc "Data/attract_royal_poses.asm"

; Kydrog idle frame = Sprite_Kydrog_Draw frame 0 (Sprites/Bosses/kydrog.asm .chr/.x_offsets/
; .y_offsets: 6 x 16x16, chars $CC,$CE,$EE,$EC,$E8,$EA), in sprite slot 3 (VRAM $5C00-$5FFF,
; sheet $42 from $0AA3=$0C, as in Kydrog NPC rooms). Y is shifted -30 so the feet sit on the anchor.
; Review fix (coordinator, QUEUE252): the delivered 11-piece table used invented chars
; ($C0-$CE in sequence) on sheet $43 and drew a scrambled Kydrog natively.
AttractRoyal_kydrog_x:         db $F8,$08,$08,$F8,$F8,$08
AttractRoyal_kydrog_y:         db $D6,$D6,$E6,$E6,$F6,$F6
AttractRoyal_kydrog_char:      db $CC,$CE,$EE,$EC,$E8,$EA
AttractRoyal_kydrog_sil_prop:  db $3D,$3D,$3D,$3D,$3D,$3D
AttractRoyal_kydrog_idle_prop: db $39,$39,$39,$39,$39,$39
AttractRoyal_kydrog_size:      db $02,$02,$02,$02,$02,$02

; Card 4 cast: lone knight + two complacent guards + Kydrog + ground shadows.
AttractRoyal_StoryCast_empty:
  db $08,$04,$80,$B8,$04,$48,$88,$04,$B8,$88,$0B,$80,$70,$02,$80,$B8,$02,$48,$88,$02,$B8,$88,$02,$80,$70

AttractRoyal_CodeEnd:
assert pc() <= $0CF766 ; Attract_DoTextInDungeonScene remains untouched

; Review fix (coordinator, QUEUE252): AnimateActor does not fit in $0CF1AE-$0CF766,
; and the Bank $2C dungeon stream has no room for it (Somaria landing assert at $2CF700).
; It uses only DP and $64 (no tables, no calls), so it lives in Bank $58 after the
; Oracle title code (title code ends near $58D58D) and is called with JSL.
pushpc
org $58F000
; ---------------------------------------------------------
; Per-card narration choreography. Entry/exit M=8, X=8, DBR=$0C.
; Input: $50 = actor record index, $51 = pose_id, $28/$29 = screen X/Y,
;        $64 = 16-bit card countdown timer.
; Output: CLC = draw ($51, $28, $29 updated), SEC = skip actor this frame.
AttractRoyal_AnimateActor:
{
  LDA.b $23 : CMP.b #$02 : BEQ .audience
              CMP.b #$03 : BNE +
              JMP .visit
            +
              JMP .empty

  ; Card 2 ($23 == $02, room $51, $1C1, $64 = $0220 -> $0000):
  ; - Records 2, 7 (Farore + shadow): step up to the dais ($6C -> $64) during
  ;   "Word reached Hyrule..." ($64 = $0220..$01E0).
  ; - Records 3, 8 (Commander + shadow): face north ($03) toward the King while
  ;   listening ($64 > $0160), then turn south ($00) and step forward ($64 -> $68)
  ;   on "Its king sent" ($64 <= $0160).
  ; - Records 0, 1, 5, 6 (two Hylian soldiers + shadows): stand at Y=$90 facing
  ;   north ($03), then turn south ($04) at $64 <= $0140 and march down the
  ;   aisle ($90 -> $C8) on "soldiers to guard it."
  .audience
  LDA.b $50
  CMP.b #$02 : BEQ .aud_farore
  CMP.b #$07 : BEQ .aud_farore
  CMP.b #$03 : BEQ .aud_commander
  CMP.b #$08 : BEQ .aud_commander
  CMP.b #$04 : BEQ .aud_draw
    ; Soldiers + shadows (0, 1, 5, 6): start at Y=$90 ($A8 - $18).
    LDA.b $29 : SEC : SBC.b #$18 : STA.b $29
    REP #$20
    LDA.b $64 : CMP.w #$0141 : BCS .aud_draw
    LDA.w #$0140 : SEC : SBC.b $64
    LSR #2
    CMP.w #$0038 : BCC +
      LDA.w #$0038
    +
    SEP #$20
    CLC : ADC.b $29 : STA.b $29
    LDA.b $50 : CMP.b #$02 : BCS .aud_draw
      LDA.b #$04 : STA.b $51
    BRA .aud_draw

  .aud_farore
    REP #$20
    LDA.b $64 : SEC : SBC.w #$01E0 : BCC .aud_draw
    LSR #3
    SEP #$20
    CLC : ADC.b $29 : STA.b $29
    BRA .aud_draw

  .aud_commander
    REP #$20
    LDA.b $64 : CMP.w #$0161 : BCC .aud_cmd_sent
      SEP #$20
      LDA.b $50 : CMP.b #$03 : BNE .aud_draw
        LDA.b #$03 : STA.b $51
      BRA .aud_draw
    .aud_cmd_sent
    LDA.w #$0160 : SEC : SBC.b $64
    LSR #3
    CMP.w #$0004 : BCC +
      LDA.w #$0004
    +
    SEP #$20
    CLC : ADC.b $29 : STA.b $29

  .aud_draw
  SEP #$20
  CLC
  RTL

  ; Card 3 ($23 == $03, room $61, $1C2, $64 = $0260 -> $0000):
  ; - Records 0, 7 (Red Mage + shadow): shift west to X=$28 (clear of text).
  ; - Records 1, 8 (Youth + shadow): shift east to X=$D8 (clear of text).
  ; - Records 4, 11 (Kalyxo villager + shadow): stand in center court at Y=$84,
  ;   then marched south ($84 -> $9C) at $64 <= $0100 on "Many called it an invasion."
  ; - Records 2, 3, 9, 10 (two Hylian guards + shadows): close in diagonally
  ;   from ($60,$94)/($A0,$94) to ($6E,$86)/($92,$86) during $64 = $0260..$01F0
  ;   ("and new laws"), then turn south ($04) at $64 <= $0100 and escort the
  ;   arrested villager down the aisle ($86 -> $9E).
  .visit
  LDA.b $50
  BEQ .vis_left_bystander
  CMP.b #$07 : BEQ .vis_left_bystander
  CMP.b #$01 : BEQ .vis_right_bystander
  CMP.b #$08 : BEQ .vis_right_bystander
  CMP.b #$04 : BEQ .vis_villager
  CMP.b #$0B : BEQ .vis_villager
  CMP.b #$02 : BEQ .vis_guard
  CMP.b #$03 : BEQ .vis_guard
  CMP.b #$09 : BEQ .vis_guard
  CMP.b #$0A : BEQ .vis_guard
  BRA .aud_draw

  .vis_left_bystander
    LDA.b #$28 : STA.b $28
    BRA .aud_draw

  .vis_right_bystander
    LDA.b #$D8 : STA.b $28
    BRA .aud_draw

  .vis_villager
    LDA.b #$84 : STA.b $29
    BRA .vis_escort_check

  .vis_guard
    LDA.b #$94 : STA.b $29
    REP #$20
    LDA.w #$0260 : SEC : SBC.b $64
    LSR #3
    CMP.w #$000E : BCC +
      LDA.w #$000E
    +
    SEP #$20
    STA.b $0C
    LDA.b $29 : SEC : SBC.b $0C : STA.b $29
    LDA.b $50 : CMP.b #$03 : BEQ .vis_guard_right
                CMP.b #$0A : BEQ .vis_guard_right
      LDA.b $28 : CLC : ADC.b $0C : STA.b $28
      BRA .vis_escort_check
    .vis_guard_right
      LDA.b $28 : SEC : SBC.b $0C : STA.b $28

  .vis_escort_check
    REP #$20
    LDA.b $64 : CMP.w #$0101 : BCC +
      JMP .aud_draw
    +
    LDA.w #$0100 : SEC : SBC.b $64
    LSR #2
    CMP.w #$0018 : BCC +
      LDA.w #$0018
    +
    SEP #$20
    CLC : ADC.b $29 : STA.b $29
    LDA.b $50 : CMP.b #$02 : BEQ .vis_turn_south
                CMP.b #$03 : BEQ .vis_turn_south
                JMP .aud_draw
    .vis_turn_south
      LDA.b #$04 : STA.b $51
    JMP .aud_draw

  ; Card 4 ($23 == $04, room $61, $1C3, $64 = $0460 -> $0000):
  ; - Records 1, 5 (Left guard + shadow at $48,$88): blink out at $64 = $0360..$0330.
  ; - Records 2, 6 (Right guard + shadow at $B8,$88): blink out at $64 = $02F0..$02C0.
  ; - Records 0, 4 (Lone knight + shadow at $80,$B8): step forward ($B8 -> $BC)
  ;   on "One knight kept watch alone." ($64 <= $029E).
  ; - Records 3, 7 (Kydrog + shadow at $80,$70): hidden while $64 > $016E;
  ;   flicker in ($64 = $016E..$0150) and hold as dark Abyss silhouette ($0B,
  ;   OBJ6) on "Now dark forces stir in the Abyss", then resolve into full
  ;   Pirate King / Fallen Knight colors ($0C, OBJ4) at $64 <= $00D0 on
  ;   "and the destiny of the Oracle of Secrets draws near."
  .empty
  LDA.b $50
  BEQ .emp_knight
  CMP.b #$04 : BEQ .emp_knight
  CMP.b #$01 : BEQ .emp_left_guard
  CMP.b #$05 : BEQ .emp_left_guard
  CMP.b #$02 : BEQ .emp_right_guard
  CMP.b #$06 : BEQ .emp_right_guard
    ; Kydrog + shadow (3, 7)
    REP #$20
    LDA.b $64 : CMP.w #$016F : BCS .emp_skip
    CMP.w #$0150 : BCC .emp_kydrog_solid
      AND.w #$0002 : BNE .emp_skip
    .emp_kydrog_solid
    LDA.b $64 : CMP.w #$00D1 : BCS .emp_draw
      SEP #$20
      LDA.b $50 : CMP.b #$03 : BNE .emp_draw
        LDA.b #$0C : STA.b $51
      BRA .emp_draw

  .emp_knight
    REP #$20
    LDA.b $64 : CMP.w #$029F : BCS .emp_draw
    LDA.w #$029E : SEC : SBC.b $64
    LSR #3
    CMP.w #$0004 : BCC +
      LDA.w #$0004
    +
    SEP #$20
    CLC : ADC.b $29 : STA.b $29
    BRA .emp_draw

  .emp_left_guard
    REP #$20
    LDA.b $64 : CMP.w #$0361 : BCS .emp_draw
    CMP.w #$0331 : BCC .emp_skip
    AND.w #$0002 : BEQ .emp_skip
    BRA .emp_draw

  .emp_right_guard
    REP #$20
    LDA.b $64 : CMP.w #$02F1 : BCS .emp_draw
    CMP.w #$02C1 : BCC .emp_skip
    AND.w #$0002 : BEQ .emp_skip

  .emp_draw
  SEP #$20
  CLC
  RTL

  .emp_skip
  SEP #$20
  SEC
  RTL
}
assert pc() <= $590000 ; stays in Bank $58
pullpc
