; Sparse native horse frames. All temporary work uses stack-preserved direct page.
; No new WRAM, global sheet ID, or P2/follower/shadow ownership.
; Dropable-safe Page 0 VRAM map ($4000-$43FF):
;   $4000-$407F/$4100-$417F ($00-$07): Horse parts 0..3 (Link Head/Body/Aux/Sword/Shield)
;   $4080-$409F/$4180-$419F ($08-$09): Rider Head
;   $40A0-$40AF/$41A0-$41AF ($0A/$1A): Narrow 8x16 Horse part 4 (8-part frames 8/9/16 only)
;   $40B0-$40BF/$41B0-$41BF ($0B/$1B): PRESERVED & ANIMATED Rupee dropable ($D9/$DA/$DB)
;   $40C0-$40DF/$41C0-$41DF ($0C-$0D): Rider Body (Link Push Block)
;   $40E0-$40FF/$41E0-$41FF ($0E-$0F): PRESERVED Swagduck / Item Receipt ($22)
;   $4200-$425F/$4300-$435F ($20-$25): PRESERVED Follower / Mounted Arrows / Heart Container / P2
;   $4260-$427F/$4360-$437F ($26-$27): Horse part (Boomerang ancilla, restored on dismount)
;   $4280-$429F/$4380-$439F ($28-$29): PRESERVED Small Shadow ($38) & Heart dropable ($29/$39)
;   $42A0-$42DF/$43A0-$43DF ($2A-$2D): Horse parts (Arrow ancillas remapped to $20-$23, restored)
;   $42E0-$42FF/$43E0-$43FF ($2E-$2F): PRESERVED Bombchu pickup ($DD)
HorseMounted_Chr:
  db $00,$02,$04,$06,$26,$2A,$2C,$0A

; C=1 means a live item, receipt, bird or cutscene owns situational graphics.
; Preserve every register/width; never remove an existing effect to mount.
Horse_SlotsBusy:
{
  PHP : PHB : REP #$30 : PHA : PHX
  SEP #$30
  LDA.b #0 : PHA : PLB
  ; No $0AF4 test: vanilla never clears it after a bird flight, and its stale
  ; NMI upload targets VRAM $40E0/$41E0, which no horse slot uses. The live
  ; bird is an ancilla and the scan below still reports it.
  LDA.l InCutScene : BNE .busy
  LDX.b #9
  .scan
    LDA.w $0C4A, X : BEQ .next_ancilla
    ; Ancilla $1D (dash tremor) is the long-jump landing shake: BG offsets
    ; only, no graphics, so it must not force a silent dismount.
    CMP.b #$1D : BEQ .next_ancilla
    ; A rider's own arrows ($09 in flight, $0A stuck in a wall) and item
    ; receipts ($22, VRAM $40E0/$41E0 disjoint from horse slots) must not
    ; unseat them (mounted bow / minigame reward). Unmounted, they still report busy.
    CMP.b #$09 : BEQ .arrow
    CMP.b #$22 : BEQ .arrow
    CMP.b #$0A : BNE .busy
    .arrow
    LDA.w !CurrentMask : CMP.b #!Horse_MaskId : BNE .busy
    .next_ancilla
    DEX : BPL .scan
  LDX.b #15
  .receipt_sprites
    LDA.w $0DD0, X : BEQ .next_sprite
    LDA.w $0E20, X : CMP.b #$EA : BEQ .busy
    CMP.b #$E7 : BEQ .busy
    .next_sprite
    DEX : BPL .receipt_sprites
  REP #$30 : PLX : PLA : PLB : PLP : CLC : RTL
  .busy
  REP #$30 : PLX : PLA : PLB : PLP : SEC : RTL
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
  PHP : PHB : REP #$30 : PHA : PHX
  SEP #$20 : LDA.b #0 : PHA : PLB
  LDX.w #15
  .scan
    LDA.w $0DD0, X : BEQ .next
    LDA.w $0E20, X
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
    LDA.w $0DC0, X : BNE .unsafe
    LDA.w $0F50, X : AND.b #$0F : CMP.b #$04 : BEQ .next
  .unsafe
    REP #$30 : PLX : PLA : PLB : PLP : CLC : RTL
  .next
    DEX : BPL .scan
  REP #$30 : PLX : PLA : PLB : PLP : SEC : RTL
}

; Checks whether Module $0E submodule ($11) keeps Overworld OAM on screen and
; leaves sprite VRAM untouched (matching vanilla Module0E_Interface $00F81B).
; Entry: M=8, DBR any. Out: C=1 if safe overlay ($01 ItemMenu, $02 Dialogue,
; $04/$08/$09 Potions, $0B SaveMenu, or $07/$0A Map/Flute while $0200==0
; fade-out); C=0 otherwise. Preserves X, Y, P widths, DBR; clobbers A.
Horse_IsSafeOverlay:
{
  LDA.b $11
  CMP.b #$01 : BEQ .safe
  CMP.b #$02 : BEQ .safe
  CMP.b #$0B : BEQ .safe
  CMP.b #$04 : BEQ .safe
  CMP.b #$08 : BEQ .safe
  CMP.b #$09 : BEQ .safe
  CMP.b #$07 : BEQ .chk_fade
  CMP.b #$0A : BNE .unsafe
  .chk_fade
  LDA.l $7E0200 : BNE .unsafe
  .safe
  SEC : RTL
  .unsafe
  CLC : RTL
}

; Entry from native8A0C, M8/X16/DB00; mask-bank8A01 remains intact.
; Native4000..40DF/4100..41DF are entirely replaced by the mounted frame.
; Skip only those896 bytes. Preserve4200/4300, shadows, items, P2 and BG DMA.
Horse_LinkDmaPrefix:
{
  ; Bit7 is a same-NMI grant only. Preserve preexisting palette bit0.
  LDA.w Horse_PalLoaded&$FFFF : AND.b #$7F : STA.w Horse_PalLoaded&$FFFF
  REP #$20 : LDA.w Horse_Marker&$FFFF : CMP.w #!Horse_MagicMarker : SEP #$20
  BNE .native
  LDA.w !CurrentMask : CMP.b #!Horse_MaskId : BNE .native
  LDA.b $1B : BNE .native
  LDA.b $10 : CMP.b #9 : BEQ .eligible
  CMP.b #$0B : BEQ .eligible
  ; Overworld-overlay $0E submodules keep mounted OAM on screen, so her cells
  ; must stay intact (Item menu, Dialogue, Potions, Save menu, Map/Flute fade).
  CMP.b #$0E : BNE .native
  JSL Horse_IsSafeOverlay : BCS .eligible
  .native
if defined("KORL_MOUNT_DEFINED")
  JML KORL_LinkDmaPrefix
else
  LDY.w #$4100 : STY.w $2116
  JML $008A12
endif

  .eligible
  ; Single-pass DBR=$00 slot check (replaces JSL Horse_SlotsBusy + second
  ; ancilla scan). Y counts live rider arrows ($09/$0A) for .arrow_check.
  LDA.l InCutScene : BNE .native
  LDY.w #0
  LDX.w #9
  .ancilla_scan
    LDA.w $0C4A, X : BEQ .next_ancilla
    CMP.b #$1D : BEQ .next_ancilla
    CMP.b #$22 : BEQ .next_ancilla
    CMP.b #$09 : BEQ .seen_arrow
    CMP.b #$0A : BNE .native
    .seen_arrow
    INY
    .next_ancilla
    DEX : BPL .ancilla_scan
  LDX.w #15
  .receipt_scan
    LDA.w $0DD0, X : BEQ .next_sprite
    LDA.w $0E20, X : CMP.b #$EA : BEQ .native
    CMP.b #$E7 : BEQ .native
    .next_sprite
    DEX : BPL .receipt_scan

  LDA.w Horse_PalLoaded&$FFFF : ORA.b #$80 : STA.w Horse_PalLoaded&$FFFF
  ; Required post-prefix DMA channel banks for original $008ADB body.
  LDA.b #$7E
  STA.w $4304 : STA.w $4314 : STA.w $4324 : STA.w $4334 : STA.w $4344
  ; Keep animated Rupee dropables ($D9/$DA/$DB -> CHR $0B/$1B, VRAM $40B0/$41B0)
  ; live every frame while mounted; Rider Body moved to $0C/$1C so $0B/$1B stays clean.
  LDX.w #$0020
  LDA.b #$01
  PHY                                       ; preserve live-arrow count across Rupee DMA
  LDY.w #$40B0 : STY.w $2116
  LDY.w $0AE0  : STY.w $4302 : STX.w $4305
  STA.w $420B
  LDY.w #$41B0 : STY.w $2116
  LDY.w $0AE2  : STY.w $4302 : STX.w $4305
  STA.w $420B
  PLY
  LDX.w #$0040
  ; Mounted frames own the native arrow cells ($2A-$2D/$3A-$3D). While a
  ; rider's arrow is alive (Y != 0), load that arrow art into Link's aux A/B
  ; cells ($20-$23/$30-$33, never drawn by the rider) in place of native aux.
  CPY.w #0 : BEQ .no_arrow_cells
  LDA.l $7EF3CC : BNE .no_arrow_cells       ; follower owns $4200/$4220
  LDA.b #HorseItemRestore>>16 : STA.w $4304 : STA.w $4314
  LDY.w #$4200 : STY.w $2116
  LDY.w #HorseItemRestore+64 : STY.w $4302 : STX.w $4305  ; $2A,$2B -> $20,$21
  LDY.w #HorseItemRestore+128 : STY.w $4312 : STX.w $4315 ; $2C,$2D -> $22,$23
  LDY.w #$BD40 : STY.w $4322 : STX.w $4325
  LDA.b #$07 : STA.w $420B
  LDY.w #$4300 : STY.w $2116
  LDY.w #HorseItemRestore+256 : STY.w $4302 : STX.w $4305 ; $3A,$3B -> $30,$31
  LDY.w #HorseItemRestore+320 : STY.w $4312 : STX.w $4315 ; $3C,$3D -> $32,$33
  LDY.w #$BD80 : STY.w $4322 : STX.w $4325
  STA.w $420B
  LDA.b #$7E : STA.w $4304 : STA.w $4314
  JML $008B25
  .no_arrow_cells
  JML $008ADB
}

; AncillaDraw_Arrow char store ($08A41B), M8/X8. Mounted: draw from the aux
; cells Horse_LinkDmaPrefix fills (arrow char - $0A). On foot: native char.
HorseArrow_StoreChar:
{
  LDA.l !CurrentMask : CMP.b #!Horse_MaskId : BNE .native
  LDA.l $7EF3CC : BNE .native               ; follower owns aux cells
  LDA.b $72 : SEC : SBC.b #$0A
  STA.b ($90), Y : INY
  RTL
  .native
  LDA.b $72
  STA.b ($90), Y : INY
  RTL
}

pushpc
org $08A41B ; @hook module=Masks name=HorseArrow_StoreChar kind=jsl target=HorseArrow_StoreChar expected_m=8 expected_x=8
  assert read2($08A41B) == $72A5 && read2($08A41D) == $9091 && read1($08A41F) == $C8, "Expected arrow char store at $08A41B"
  JSL HorseArrow_StoreChar : NOP
assert pc() == $08A420
pullpc

; Entry M8/X16, DBR any. Preserve Y/DBR/DP and displaced native DMA0 tail.
; Horse_UploadedFrame FF=no mounted ownership, 0..18=restore required on exit.
; VBlank-safe design:
;   - Zero-REP/SEP multi-channel (CH0+CH1) mounted uploads with hardware $43x2 auto-inc.
;   - Deduplicates Rider 256B upload whenever old & new frames share the same Rider pointer
;     (all gallop frames share +$1680, N walk shares +$0C80, S walk shares +$0200).
;   - Overworld border transitions ($11 != 0) never touch $4000..$43FF -> keep steady path.
;   - Skips the 1,024B animated-tile replay on any NMI that already performed a Horse/NPC/
;     restore DMA (and on ultra-crowded mounted scroll+palette/stripe steady frames), while
;     always restoring $4304=#$7E & $4302=$0ADC and chaining DekuWings_NmiUpload cleanly.
Horse_NmiUpload:
{
  PHB : PHY
  REP #$20
  ; Only DP $04 and $06 are used as scratch; all other DP words stay untouched.
  LDA.b $06 : PHA : LDA.b $04 : PHA
  SEP #$20 : LDA.b #0 : PHA : PLB
  REP #$20 : LDA.w Horse_Marker&$FFFF : CMP.w #!Horse_MagicMarker : SEP #$20
  BEQ + : BRL .replay : +
  ; Prefix grant covers the same straight-line NMI path; no main/actor code
  ; runs between $008A0C and $008B5C. Consume bit 7 and preserve palette bit 0.
  LDA.w Horse_PalLoaded&$FFFF : BPL .not_mounted_near
  AND.b #$7F : STA.w Horse_PalLoaded&$FFFF
  BRA .mounted
  .not_mounted_near
  BRL .not_mounted

  .mounted
  LDA.w Horse_NpcUploadedFrame&$FFFF : CMP.b #$FF : BEQ .steady
  JSL Horse_RanchProfileReady : BCC .profile_changed
  LDA.w Horse_UploadedFrame&$FFFF : CMP.b #$FF : BEQ .first_mounted
  ; One ordinary-frame hold restores the now-hidden NPC before any consumer
  ; can reuse its C2 cells. Native prefix skips every mounted destination.
  LDA.b $10 : CMP.b #9 : BNE .restore_and_upload
  LDA.b $11 : BNE .restore_and_upload
  JSR Horse_RestoreNpcCells
  LDA.w Horse_Frame&$FFFF : CMP.w Horse_UploadedFrame&$FFFF : BNE .upload_mounted
  BRL .replay_skip_anim
  .first_mounted
  ; Only the measured known Ranch residents permit one-frame retained NPC
  ; cells. Unknown actors retain the conservative original immediate restore.
  JSL Horse_RanchActorsSafe : BCC .restore_and_upload
  LDA.b $10 : CMP.b #9 : BNE .restore_and_upload
  LDA.b $11 : BNE .restore_and_upload
  BRA .upload_mounted
  .profile_changed
  ; Existing native profile loader owns C2 restoration outside the Ranch.
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  JSL Horse_OffRestore ; parked off-Ranch NPC cells -> saved native copy
endif
  LDA.b #$FF : STA.w Horse_NpcUploadedFrame&$FFFF
  BRA .upload_mounted
  .restore_and_upload
  JSR Horse_RestoreNpcCells
  BRA .upload_mounted

  .steady
  ; Native 8A0C/8ADB and Overworld border transitions ($11 != 0) never write
  ; mounted cells ($4000-40DF/4100-41DF, $4260-42DF/4360-43DF); any lost grant
  ; resets UploadedFrame to $FF. Skip DMA whenever the current pose is resident.
  LDA.w Horse_Frame&$FFFF : CMP.b #!Horse_FrameCount : BCC + : LDA.b #6 : +
  CMP.w Horse_UploadedFrame&$FFFF : BNE .upload_mounted
  ; On crowded steady frames (scroll+palette/stripes or stripes+palette), skip
  ; the 1KB animated-tile replay for 1 frame to guarantee VBlank headroom.
  LDA.b $17 : BNE .steady_heavy
  LDA.b $14 : BEQ .steady_replay
  LDA.b $15 : BNE .steady_skip
  BRA .steady_replay
  .steady_heavy
  LDA.b $14 : ORA.b $15 : BEQ .steady_replay
  .steady_skip
  BRL .replay_skip_anim
  .steady_replay
  BRL .replay

  .upload_mounted
  ; Clamp frame -> $06 (16-bit, hi=0) and compute $04 = frame * 12 (word table offset).
  LDA.w Horse_Frame&$FFFF : CMP.b #!Horse_FrameCount : BCC + : LDA.b #6 : +
  REP #$20 : AND.w #$00FF : STA.b $06
  ASL : CLC : ADC.b $06 : ASL #2 : STA.b $04
  SEP #$20

  ; Set DMA0 & DMA1 source bank once for every mounted burst.
  LDA.b #HorseGraphics>>16 : STA.w $4304 : STA.w $4314

  ; Group 0: Horse parts 0..3 -> $4000/$4100 (256B top + 256B bot via hardware auto-inc).
  LDX.b $04
  REP #$20
  LDA.l HorseFrame_GroupPointers+0, X : STA.w $4302
  SEP #$20
  LDY.w #$4000 : STY.w $2116
  LDX.w #$0100 : STX.w $4305
  LDA.b #$01   : STA.w $420B
  LDY.w #$4100 : STY.w $2116
  STX.w $4305
  STA.w $420B

  ; Group 1: Rider Head ($4080/$4180) + Rider Body ($40C0/$41C0), 4x64B sequential.
  ; Skip all 256B whenever the resident Horse_UploadedFrame uses the same Rider pointer.
  LDA.w Horse_UploadedFrame&$FFFF : CMP.b #!Horse_FrameCount : BCS .do_rider
    REP #$20
    AND.w #$00FF : PHA
    ASL : CLC : ADC 1, S : ASL #2 : TAX        ; X = old_frame * 12
    LDA.l HorseFrame_GroupPointers+2, X : STA 1, S
    LDX.b $04
    LDA.l HorseFrame_GroupPointers+2, X
    CMP 1, S : BEQ .skip_rider_pop
    STA.w $4302
    PLA
    SEP #$20
    BRA .dma_rider_go
  .skip_rider_pop
    PLA
    SEP #$20
    BRA .after_rider
  .do_rider
    LDX.b $04
    REP #$20
    LDA.l HorseFrame_GroupPointers+2, X : STA.w $4302
    SEP #$20
  .dma_rider_go
  LDX.w #$0040 : LDA.b #$01
  LDY.w #$4080 : STY.w $2116 : STX.w $4305 : STA.w $420B ; Head Top (+$00)
  LDY.w #$40C0 : STY.w $2116 : STX.w $4305 : STA.w $420B ; Body Top (+$40)
  LDY.w #$4180 : STY.w $2116 : STX.w $4305 : STA.w $420B ; Head Bot (+$80)
  LDY.w #$41C0 : STY.w $2116 : STX.w $4305 : STA.w $420B ; Body Bot (+$C0)
  .after_rider

  ; 8-part frames (8, 9, 16) first upload narrow 8x16 part 4 -> $40A0 (TL +$00)
  ; & $41A0 (BL +$40), keeping Rupee dropable $0B/$1B ($40B0/$41B0) untouched,
  ; then advance $04 by +2 so +4/+6/+8 align with $4260/$42A0/$42C0 identically
  ; to 6/7-part frames!
  LDX.b $06
  LDA.l HorseFrame_Count, X : PHA           ; preserve part count (6, 7, or 8)
  CMP.b #8 : BNE .upload_p4260
    LDX.b $04
    REP #$20
    LDA.l HorseFrame_GroupPointers+4, X : STA.w $4302
    CLC : ADC.w #$0040 : STA.w $4312
    SEP #$20
    LDX.w #$0020
    LDY.w #$40A0 : STY.w $2116 : STX.w $4305 : LDA.b #$01 : STA.w $420B
    LDY.w #$41A0 : STY.w $2116 : STX.w $4315 : LDA.b #$02 : STA.w $420B
    INC.b $04 : INC.b $04

  .upload_p4260
  ; Shared across 6-, 7-, and 8-part frames: 16x16 part -> $4260/$4360 (2x64B).
  LDX.b $04
  REP #$20 : LDA.l HorseFrame_GroupPointers+4, X : STA.w $4302 : SEP #$20
  LDY.w #$4260 : JSR Horse_Dma64Pair

  ; Remaining parts: 6-part uses CH0 ($42A0/$43A0); 7/8-part concatenates
  ; CH0+CH1 ($42A0+$42C0 and $43A0+$43C0) in 2 bursts!
  LDX.b $04
  PLA : CMP.b #7 : BCS .upload_78_tail
    REP #$20 : LDA.l HorseFrame_GroupPointers+6, X : STA.w $4302 : SEP #$20
    LDY.w #$42A0 : JSR Horse_Dma64Pair
    BRA .upload_done
  .upload_78_tail
  REP #$20
  LDA.l HorseFrame_GroupPointers+6, X : STA.w $4302
  LDA.l HorseFrame_GroupPointers+8, X : STA.w $4312
  SEP #$20
  LDX.w #$0040 : LDA.b #$03
  LDY.w #$42A0 : STY.w $2116 : STX.w $4305 : STX.w $4315 : STA.w $420B
  LDY.w #$43A0 : STY.w $2116 : STX.w $4305 : STX.w $4315 : STA.w $420B

  .upload_done
  ; Restore DMA1 bank to $7E (native $008A5C invariant) and commit frame ID.
  LDA.b #$7E : STA.w $4314
  LDA.b $06  : STA.w Horse_UploadedFrame&$FFFF
  BRL .replay_skip_anim ; skip 1KB animated tiles on horse upload frame

  .not_mounted
  ; DP $04 low byte tracks whether any Horse/NPC/restore DMA ran this NMI.
  STZ.b $04
  LDA.w Horse_UploadedFrame&$FFFF : CMP.b #$FF : BEQ .npc
    JSR Horse_RestoreItemCells
    LDA.b #$FF : STA.w Horse_UploadedFrame&$FFFF
    INC.b $04
  .npc
  JSL Horse_RanchProfileReady : BCS .on_ranch
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  LDA.b #$00
  JSL Horse_OffRanchNpc : BCS .npc_rows_budget
  ORA.b $04 : STA.b $04
  BRL .not_mounted_exit
else
  LDA.b #$FF : STA.w Horse_NpcUploadedFrame&$FFFF
  BRL .not_mounted_exit
endif

  .on_ranch
  ; Check cheap scalar gates before scanning ancillas/sprites.
  LDA.w Horse_NpcActive&$FFFF : BEQ .restore_npc
  LDA.w !CurrentMask : CMP.b #!Horse_MaskId : BEQ .restore_npc
  LDA.b $10 : CMP.b #9 : BEQ .ranch_mod_ok
  CMP.b #$0B : BEQ .ranch_mod_ok
  CMP.b #$0E : BNE .restore_npc
  JSL Horse_IsSafeOverlay : BCC .restore_npc
  .ranch_mod_ok
  LDA.w Horse_NpcFrame&$FFFF
  CMP.b #12 : BCC .restore_npc
  CMP.b #16 : BCS .restore_npc

  .ranch_scan
  ; Tight DBR=$00 ancilla check + DBR=$00 Horse_RanchActorsSafe (eliminates
  ; duplicate 16-sprite scan from Horse_SlotsBusy).
  LDA.l InCutScene : BNE .restore_npc
  LDX.w #9
  .ranch_anc
    LDA.w $0C4A, X : BEQ .ranch_anc_next
    CMP.b #$1D : BNE .restore_npc
    .ranch_anc_next
    DEX : BPL .ranch_anc
  JSL Horse_RanchActorsSafe : BCC .restore_npc
  LDA.w Horse_NpcFrame&$FFFF : CMP.w Horse_NpcUploadedFrame&$FFFF : BNE .npc_rows_budget
  BRA .not_mounted_exit

  .restore_npc
  LDA.w Horse_NpcUploadedFrame&$FFFF : CMP.b #$FF : BEQ .not_mounted_exit
    JSR Horse_RestoreNpcCells
    BRA .replay_skip_anim

  .npc_rows_budget
  ; Never stack 1KB NPC upload on the same NMI as Horse_RestoreItemCells.
  LDA.b $04 : BNE .replay_skip_anim
  ; Native DMA0/1 are already mode1->VRAM. Two channels concatenate the
  ; first-four and last-four 256-byte rows; a second burst emits their bottoms.
  ; Hardware increments both source addresses and VRAM between bursts.
  LDA.b #HorseGraphics>>16 : STA.w $4304 : STA.w $4314
if defined("HorseNpcNorthTail")
  LDA.w Horse_NpcFrame&$FFFF
  CMP.b #12 : BEQ .npc_north
  CMP.b #13 : BEQ .npc_south
    LDX.w #HorseGraphics+!Horse_NpcHeadOffset : STX.w $4302
    LDX.w #HorseNpcTail : STX.w $4312
    BRA .npc_dma
  .npc_north
    LDX.w #HorseGraphics : STX.w $4302
    LDX.w #HorseNpcNorthTail : STX.w $4312
    BRA .npc_dma
  .npc_south
    LDX.w #HorseGraphics+$0A80 : STX.w $4302
    LDX.w #HorseNpcSouthTail : STX.w $4312
  .npc_dma
else
  LDX.w #HorseGraphics+!Horse_NpcHeadOffset : STX.w $4302
  LDX.w #HorseNpcTail : STX.w $4312
endif
  LDX.w #$0100 : STX.w $4305 : STX.w $4315
  LDY.w #$5000 : STY.w $2116
  LDA.b #3 : STA.w $420B
  STX.w $4305 : STX.w $4315
  STA.w $420B
  ; Native prefix set DMA1 bank $7E; preserve it for subsequent native consumers.
  LDA.b #$7E : STA.w $4314
  LDA.w Horse_NpcFrame&$FFFF : STA.w Horse_NpcUploadedFrame&$FFFF
  BRA .replay_skip_anim

  .not_mounted_exit
  LDA.b $04 : BNE .replay_skip_anim

  .replay
if defined("KORL_MOUNT_DEFINED")
  JSL KORL_NmiUpload
  BCS .replay_skip_anim
endif
  LDA.w Horse_DismountCooldown&$FFFF : BNE .replay_skip_anim
  CLC : BRA .replay_epilogue
  .replay_skip_anim
  SEC
  .replay_epilogue
  REP #$20 : PLA : STA.b $04 : PLA : STA.b $06 : SEP #$20
  LDA.b #$7E : STA.w $4304
  LDX.w $0ADC : STX.w $4302
  BCS .replay_done
  LDX.w $0134 : STX.w $2116
  LDX.w #$0400 : STX.w $4305
  LDA.b #1 : STA.w $420B
  .replay_done
  if defined("DEKU_WINGS_NMI_DEFINED")
    JSL DekuWings_NmiUpload
  endif
  PLY : PLB : RTL
}

; Entry: M=8, X=16, DBR=$00, Y=VRAM top word, $4302/$4304 set.
; Emits 64B top row to Y and 64B bottom row to Y+$0100 via hardware $4302 auto-inc.
Horse_Dma64Pair:
{
  LDX.w #$0040 : LDA.b #$01
  STY.w $2116 : STX.w $4305 : STA.w $420B
  REP #$20 : TYA : CLC : ADC.w #$0100 : STA.w $2116 : SEP #$20
  LDA.b #$01 : STX.w $4305 : STA.w $420B
  RTS
}

; Unrolled native-default item cell restore (384B in 4 contiguous bursts:
; $4260 64B, $42A0-$42DF 128B, $4360 64B, $43A0-$43DF 128B).
; Shadow $28/$38, Heart $29/$39, and P2 are never touched.
Horse_RestoreItemCells:
{
  LDA.b #HorseItemRestore>>16 : STA.w $4304
  LDX.w #HorseItemRestore : STX.w $4302
  LDX.w #$4260 : JSR .half
  LDX.w #$4360
  .half
  STX.w $2116 : LDY.w #$0040 : STY.w $4305 : LDA.b #$01 : STA.w $420B
  REP #$20 : TXA : CLC : ADC.w #$0040 : STA.w $2116 : SEP #$20
  LDY.w #$0080 : STY.w $4305 : LDA.b #$01 : STA.w $420B
  RTS
}

; Single contiguous 1,024B restore of Ranch C2 first 32 chars ($5000-$51FF).
Horse_RestoreNpcCells:
{
  LDA.b #HorseRanchRestore>>16 : STA.w $4304
  LDX.w #HorseRanchRestore : STX.w $4302
  LDX.w #$5000 : STX.w $2116
  LDX.w #$0400 : STX.w $4305
  LDA.b #1 : STA.w $420B
  LDA.b #$FF : STA.w Horse_NpcUploadedFrame&$FFFF
  RTS
}
