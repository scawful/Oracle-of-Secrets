; Sparse native horse frames. All temporary work uses stack-preserved direct page.
; No new WRAM, global sheet ID, or P2/follower/shadow ownership.
HorseMounted_Chr:
  db $00,$02,$04,$06,$0C,$26,$2A,$2C
HorseMounted_Vram:
  dw $4000,$4080,$40C0,$4260,$42A0,$42C0
HorseMounted_RowBytes:
  dw $0100,$0080,$0040,$0040,$0040,$0040
HorseNpc_Vram:
  dw $5000,$5020,$5040,$5060,$5080,$50A0,$50C0,$50E0
HorseRestore_Vram:
  dw $4260,$42A0,$42C0,$4360,$43A0,$43C0

; C=1 means a live item, receipt, bird or cutscene owns situational graphics.
; Preserve every register/width; never remove an existing effect to mount.
Horse_SlotsBusy:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$20
  LDA.l $7E0AF4 : BNE .busy
  LDA.l InCutScene : BNE .busy
  LDX.w #9
  .scan
    LDA.l $7E0C4A, X : BEQ .next_ancilla
if !ENABLE_HORSE_LONG_JUMP == 1
    ; Ancilla $1D (dash tremor) is the long-jump landing shake: BG offsets
    ; only, no graphics, so it must not force a silent dismount.
    CMP.b #$1D : BEQ .next_ancilla
endif
    ; A rider's own arrows ($09 in flight, $0A stuck in a wall) must not
    ; unseat them (mounted bow). Unmounted, an arrow still reports busy.
    CMP.b #$09 : BEQ .arrow
    CMP.b #$0A : BNE .busy
    .arrow
    LDA.l $7E02B2 : CMP.b #$09 : BNE .busy ; CurrentMask != horse
    .next_ancilla
    DEX : BPL .scan
  LDX.w #15
  .receipt_sprites
    LDA.l $7E0DD0, X : BEQ .next_sprite
    LDA.l $7E0E20, X : CMP.b #$EA : BEQ .busy
    CMP.b #$E7 : BEQ .busy
    .next_sprite
    DEX : BPL .receipt_sprites
  REP #$30 : PLX : PLA : PLP : CLC : RTL
  .busy
  REP #$30 : PLX : PLA : PLP : SEC : RTL
}

; Actual loaded Ranch group, not phase0 describe-map defaults or generic free VRAM.
Horse_RanchProfileReady:
{
  PHP : REP #$30 : PHA
  SEP #$20
  LDA.l $7E001B : ORA.l $7E008A : BNE .no
  LDA.l $7E0AA3 : CMP.b #6 : BNE .no
  LDA.l $7EC2FC : CMP.b #$4F : BNE .no
  LDA.l $7EC2FD : CMP.b #$49 : BNE .no
  LDA.l $7EC2FE : CMP.b #$4A : BNE .no
  LDA.l $7EC2FF : CMP.b #$50 : BNE .no
  REP #$30 : PLA : PLP : SEC : RTL
  .no
  REP #$30 : PLA : PLP : CLC : RTL
}

; Current Ranch residents have measured non-overlapping CHR usage. Unknown
; dynamically spawned actors suspend the NPC composition, not the actor itself.
Horse_RanchActorsSafe:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$20 : LDX.w #15
  .scan
    LDA.l $7E0DD0, X : BEQ .next
    LDA.l $7E0E20, X
    CMP.b #$2D : BEQ .next ; horse
    CMP.b #$2A : BEQ .next ; sweeper, BD
    CMP.b #$3C : BEQ .next ; kid, BD
    CMP.b #$74 : BEQ .next ; runner, C2 second half
    CMP.b #$0B : BEQ .next ; cucco
    CMP.b #$07 : BEQ .next ; pull switch
    CMP.b #$EB : BEQ .next ; heart piece
    CMP.b #$AC : BEQ .next ; apple
    ; Ordinary Light World entry always initializes the native mirror portal,
    ; even at an unset (0,8) anchor. Its native frame0 uses page0 CHR4C/4D/5C/5D
    ; and palette2, disjoint from the private C2 first32 chars and SP3 colors.
    ; Refuse altered frame/page/palette rather than admitting arbitrary 6C art.
    CMP.b #$6C : BNE .unsafe
    LDA.l $7E0DC0, X : BNE .unsafe
    LDA.l $7E0F50, X : AND.b #$0F : CMP.b #$04 : BEQ .next
  .unsafe
    REP #$30 : PLX : PLA : PLP : CLC : RTL
  .next
    DEX : BPL .scan
  REP #$30 : PLX : PLA : PLP : SEC : RTL
}

; Entry from native8A0C, M8/X16/DB00; mask-bank8A01 remains intact.
; Native4000..40DF/4100..41DF are entirely replaced by the mounted frame.
; Skip only those896 bytes. Preserve4200/4300, shadows, items, P2 and BG DMA.
Horse_LinkDmaPrefix:
{
  ; Bit7 is a same-NMI grant only. Preserve preexisting palette bit0.
  LDA.l Horse_PalLoaded : AND.b #$7F : STA.l Horse_PalLoaded
  REP #$20 : LDA.l Horse_Marker : CMP.w #!Horse_MagicMarker : SEP #$20
  BNE .native
  LDA.l !CurrentMask : CMP.b #!Horse_MaskId : BNE .native
  LDA.b $1B : BNE .native
  LDA.b $10 : CMP.b #9 : BEQ .eligible
  CMP.b #$0B : BNE .native
  .eligible
  JSL Horse_SlotsBusy : BCS .native
  LDA.l Horse_PalLoaded : ORA.b #$80 : STA.l Horse_PalLoaded
  ; Required post-prefix DMA channel banks and X size for original8ADB body.
  LDA.b #$7E
  STA.w $4304 : STA.w $4314 : STA.w $4324 : STA.w $4334 : STA.w $4344
  LDX.w #$0040
  JML $008ADB
  .native
  LDY.w #$4100 : STY.w $2116
  JML $008A12
}

; Entry M8/X16, DBR any. Preserve Y/DBR/DP and displaced native DMA0 tail.
; Horse_UploadedFrame FF=no mounted ownership, 0..18=restore required on exit.
Horse_NmiUpload:
{
  PHB : PHY
  REP #$20
  ; Packed groups use only DP04,06,0A; all other DP words stay untouched.
  LDA.b $0A : PHA : LDA.b $06 : PHA : LDA.b $04 : PHA
  SEP #$20 : LDA.b #0 : PHA : PLB
  REP #$20 : LDA.l Horse_Marker : CMP.w #!Horse_MagicMarker : SEP #$20
  BEQ + : BRL .replay : +
  ; Prefix grant covers the same straight-line NMI path; no main/actor code
  ; runs between8A0C and8B5C. Consume it once and preserve palette bit0.
  LDA.l Horse_PalLoaded : AND.b #$80 : BNE + : BRL .not_mounted : +
  LDA.l Horse_PalLoaded : AND.b #$7F : STA.l Horse_PalLoaded
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BEQ .upload_mounted
  JSL Horse_RanchProfileReady : BCC .profile_changed
  LDA.l Horse_UploadedFrame : CMP.b #$FF : BEQ .first_mounted
  ; One ordinary-frame hold restores the now-hidden NPC before any consumer
  ; can reuse its C2 cells. Native prefix skips every mounted destination.
  LDA.b $10 : CMP.b #9 : BNE .restore_and_upload
  LDA.b $11 : BNE .restore_and_upload
  JSR Horse_RestoreNpcCells
  LDA.l Horse_Frame : CMP.l Horse_UploadedFrame : BNE .upload_mounted
  BRL .replay
  .first_mounted
  ; Only the measured known Ranch residents permit one-frame retained NPC
  ; cells. Unknown actors retain the conservative original immediate restore.
  JSL Horse_RanchActorsSafe : BCC .restore_and_upload
  LDA.b $10 : CMP.b #9 : BNE .restore_and_upload
  LDA.b $11 : BNE .restore_and_upload
  BRA .upload_mounted
  .profile_changed
  ; Existing native profile loader owns C2 restoration outside the Ranch.
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  BRA .upload_mounted
  .restore_and_upload
  JSR Horse_RestoreNpcCells
  .upload_mounted
  LDA.l Horse_Frame : JSR Horse_FramePointerBase
  ; Six fixed groups; no per-piece loop or destination-table walk.
  REP #$20
  LDA.w #$0100 : STA.b $0A
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+0, X : TAX
  LDY.w #$4000 : SEP #$20 : JSR Horse_DmaGroup
  REP #$20
  LDA.w #$0080 : STA.b $0A
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+2, X : TAX
  LDY.w #$4080 : SEP #$20 : JSR Horse_DmaGroup
  REP #$20
  LDA.w #$0040 : STA.b $0A
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+4, X : TAX
  LDY.w #$40C0 : SEP #$20 : JSR Horse_DmaGroup
  REP #$20
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+6, X : TAX
  LDY.w #$4260 : SEP #$20 : JSR Horse_DmaGroup
  REP #$20
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+8, X : TAX
  LDY.w #$42A0 : SEP #$20 : JSR Horse_DmaGroup
  REP #$20
  LDX.b $04
  LDA.l HorseFrame_GroupPointers+10, X : TAX
  LDY.w #$42C0 : SEP #$20 : JSR Horse_DmaGroup
  LDA.l Horse_Frame : CMP.b #!Horse_FrameCount : BCC + : LDA.b #6 : +
  STA.l Horse_UploadedFrame
  BRL .replay ; mounted and NPC uploads are mutually exclusive

  .not_mounted
  LDA.l Horse_UploadedFrame : CMP.b #$FF : BEQ .npc
    JSR Horse_RestoreItemCells
    LDA.b #$FF : STA.l Horse_UploadedFrame
  .npc
  JSL Horse_RanchProfileReady : BCS +
    LDA.b #$FF : STA.l Horse_NpcUploadedFrame
    BRL .replay ; native profile loader owns restoration outside Ranch
  +
  LDA.b $10 : CMP.b #9 : BEQ +
    CMP.b #$0B : BNE .restore_npc
  +
  JSL Horse_SlotsBusy : BCS .restore_npc
  JSL Horse_RanchActorsSafe : BCC .restore_npc
  LDA.l Horse_NpcActive : BEQ .restore_npc
  LDA.l !CurrentMask : CMP.b #!Horse_MaskId : BEQ .restore_npc
  ; NPC frames14/15 share exact pixels. Reuse the packed first-four group
  ; and a512-byte final-four stream. Four transfers preserve unconditional
  ; reload behavior without an extra full NPC frame or a new cache/state.
  LDA.l Horse_NpcFrame : CMP.b #14 : BEQ .npc_rows
  CMP.b #15 : BNE .restore_npc
  .npc_rows
  ; Native DMA0/1 are already mode1→VRAM. Two channels concatenate the
  ; first-four and last-four256-byte rows; a second burst emits their bottoms.
  ; Hardware increments both source addresses and VRAM between bursts.
  LDA.b #HorseGraphics>>16 : STA.w $4304 : STA.w $4314
  LDX.w #HorseGraphics+!Horse_NpcHeadOffset : STX.w $4302
  LDX.w #HorseNpcTail : STX.w $4312
  LDX.w #$0100 : STX.w $4305 : STX.w $4315
  LDX.w #$5000 : STX.w $2116
  LDA.b #3 : STA.w $420B
  LDX.w #$0100 : STX.w $4305 : STX.w $4315
  LDA.b #3 : STA.w $420B
  ; Native prefix set DMA1 bank7E; preserve it for subsequent native consumers.
  LDA.b #$7E : STA.w $4314
  LDA.l Horse_NpcFrame : STA.l Horse_NpcUploadedFrame
  BRA .replay
  .restore_npc
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BEQ .replay
    JSR Horse_RestoreNpcCells
  .replay
  REP #$20
  PLA : STA.b $04 : PLA : STA.b $06 : PLA : STA.b $0A
  SEP #$20
  LDA.b #$7E : STA.w $4304
  LDX.w $0ADC : STX.w $4302
  LDX.w $0134 : STX.w $2116
  LDX.w #$0400 : STX.w $4305
  LDA.b #1 : STA.w $420B
  PLY : PLB : RTL
}

; A8 frame -> DP04 word table offset; invalid IDs use standing, never AND0F.
Horse_FramePointerBase:
{
  CMP.b #!Horse_FrameCount : BCC + : LDA.b #6 : +
  REP #$20 : AND.w #$00FF : STA.b $04
  ASL : CLC : ADC.b $04 : ASL #2 : STA.b $04
  SEP #$20 : RTS
}

; Source53:X, destination VRAMwordY; DP0A is top-row byte length.
; Emit the identical bottom row at VRAM+0100. Sizes are64/128/256 from table.
Horse_DmaGroup:
{
  LDA.b #HorseGraphics>>16 : STA.w $4304
  STX.w $4302 : STY.w $2116
  REP #$20 : LDA.b $0A : STA.w $4305 : SEP #$20
  LDA.b #1 : STA.w $420B
  REP #$20
  TXA : CLC : ADC.b $0A : STA.w $4302
  TYA : CLC : ADC.w #$0100 : STA.w $2116
  LDA.b $0A : STA.w $4305
  SEP #$20 : LDA.b #1 : STA.w $420B
  RTS
}

; Six disjoint64B transfers from exact native-default conversion. Assertions in
; generated tables reject any source drift; shadow28/38 and P2 are never touched.
Horse_RestoreItemCells:
{
  LDA.b #HorseItemRestore>>16 : STA.w $4304
  STZ.b $06
  .loop
    REP #$20
    LDA.b $06 : AND.w #$00FF : ASL : TAX
    LDA.l HorseRestore_Vram, X : STA.w $2116
    LDA.b $06 : AND.w #$00FF : ASL #6 : CLC : ADC.w #HorseItemRestore : STA.w $4302
    LDA.w #64 : STA.w $4305
    SEP #$20 : LDA.b #1 : STA.w $420B
    INC.b $06 : LDA.b $06 : CMP.b #6 : BCC .loop
  RTS
}

Horse_RestoreNpcCells:
{
  LDA.b #HorseRanchRestore>>16 : STA.w $4304
  LDX.w #HorseRanchRestore : STX.w $4302
  LDX.w #$5000 : STX.w $2116
  LDX.w #$0200 : STX.w $4305
  LDA.b #1 : STA.w $420B
  LDX.w #HorseRanchRestore+$0200 : STX.w $4302
  LDX.w #$5100 : STX.w $2116
  LDX.w #$0200 : STX.w $4305
  LDA.b #1 : STA.w $420B
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  RTS
}
