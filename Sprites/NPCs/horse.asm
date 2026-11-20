; =========================================================
; Toto Ranch Epona NPC (Sprite ID $2D)
;
; Canon rules (decisions.org:4398-4414):
;   - Spawned outdoors on Toto Ranch (area $00) when unmounted.
;   - Uses native-size source Epona parts in the group06-bound C2 first32 chars
;     ($5000/$5100; page1 tiles00..0F). No globally free VRAM assumption.
;     and SP-3[9..15] ($7EC472/$7EC672) + SP-3[1,5,8] ($7FFF/$14A5/$0000).
;   - Pressing A nearby:
;       * Before curing Ranch Girl (SideQuestProg2 & !SideQuest2_RanchGirl == 0
;         or Ocarina $7EF34C == 0): gentle SFX2.3C + hop
;       * After early Ocarina visit cure: mounts Horse Form (#$09)
;   - Sprite tables are patched via %Set_Sprite_Properties; routine
;     bodies live in free bank $53 ($53D000..$53FFFF) to leave
;     crowded bank $2C, special-overworld bank $51, and prison bank $52 untouched.
; =========================================================

!SPRID              = $2D
!NbrTiles           = 07  ; native allocator adds1: eight sparse OAM entries
!Harmless           = 01
!HVelocity          = 00
!Health             = 00
!Damage             = 00
!DeathAnimation     = 01
!ImperviousAll      = 01
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 03  ; SP-3 (slots 9..15 unused by Light World sprites)
!Hitbox             = 03
!Persist            = 01
!Statis             = 00
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImpervSwordHammer  = 01
!ImperviousArrow    = 01
!Boss               = 00

%Set_Sprite_Properties(Sprite_HorseNPC_Prep, Sprite_HorseNPC_Long)

pushpc
org $53D000

Sprite_HorseNPC_Long:
{
  ; $2D is shared with Items/fishing_rod.asm's fishing floater (SprMiscA == $F1).
  ; Enter with M=8, X=8, DBR=$30; JML straight to FloaterBoySpriteCheck before horse gates run.
  LDA.w SprMiscA, X : CMP.b #$F1 : BNE .horse_npc
    JML FloaterBoySpriteCheck
  .horse_npc
  PHP : PHB : PHX : PHY
  SEP #$30
  LDA.b #$00 : PHA : PLB
  ; Reject ownership before drawing, including the same-frame mount transition.
  LDA.w $02B2 : CMP.b #9 : BEQ .despawn_before_draw
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  LDA.b $1B : BNE .despawn_before_draw
  LDA.l Horse_HasAnchor : BEQ .ranch_profile
  LDA.b $8A : CMP.l Horse_AnchorArea : BNE .despawn_before_draw
  JSL Horse_RanchProfileReady : BCC .off_ranch
    JSL Horse_SlotsBusy : BCS .SpriteIsNotActive
    BRA .draw_ok
  .off_ranch
  JSL Horse_ParkedBusy : BCS .SpriteIsNotActive
  ; Off the Ranch, draw only while her cells are in VRAM (hidden, not garbled).
  LDA.l Horse_OffState : CMP.b #$A2 : BNE .SpriteIsNotActive
  BRA .draw_ok
  .ranch_profile
endif
  JSL Horse_RanchProfileReady : BCC .despawn_before_draw
  JSL Horse_SlotsBusy : BCS .SpriteIsNotActive
  JSL Horse_RanchActorsSafe : BCC .SpriteIsNotActive
  .draw_ok
  JSR Sprite_HorseNPC_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_HorseNPC_Main
  .SpriteIsNotActive
  PLY : PLX : PLB : PLP
  RTL
  .despawn_before_draw
  STZ.w $0DD0, X
  LDA.b #0 : STA.l Horse_NpcActive
  BRA .SpriteIsNotActive
}

Sprite_HorseNPC_Prep:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  LDA.b #$00 : STA.w SprAction, X : STA.w SprFrame, X
  LDA.b #14  : STA.l Horse_NpcFrame
  PLB : PLP
  RTL
}

Sprite_HorseNPC_Main:
{
  ; Despawn cleanly if mounted, indoors, or off the parked/Ranch area.
  LDA.w $02B2 : CMP.b #$09 : BNE +
    BRL .despawn
  +
  LDA.b $1B : BNE .do_despawn
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  LDA.l Horse_HasAnchor : BEQ .ranch_only_area
  LDA.b $8A : CMP.l Horse_AnchorArea : BEQ .area_ok
  BRA .do_despawn
  .ranch_only_area
endif
  LDA.b $8A : BEQ .area_ok
  .do_despawn
  BRL .despawn
  .area_ok

  ; Keep SP-3[9..15] palette crisp if area palette reload overwrote it with uniform fill.
  REP #$20
  LDA.l $7EC67C : CMP.l $7EC67E : BNE +
    SEP #$20
    JSL Horse_LoadNpcPalette
  +
  SEP #$20

  ; Uses SprMiscF (not SprTimerB, which the sprite engine auto-decrements every frame).
  ; In-place idle + subtle graze/head-bob cycle (0..191); never modifies SprX/SprY.
  LDA.w SprMiscF, X : INC
  CMP.b #192 : BCC +
    LDA.b #$00
  +
  STA.w SprMiscF, X
  JSR HorseNPC_SelectNpcFrame
  STA.l Horse_NpcFrame
  .anim_done

  ; Decay optional pre-unlock head-shake hop timer.
  LDA.w SprTimerA, X : BEQ +
    DEC : STA.w SprTimerA, X
  +

  ; Solid barrier ONLY once player walks clear of dismount overlap (|dx|>=14 || |dy|>=14).
  JSR Sprite_HorseNPC_CheckPlayerDistance ; returns DP $00=dx(abs), $02=dy(abs)
  REP #$20
  LDA.b $00 : CMP.w #14 : BCS .barrier
  LDA.b $02 : CMP.w #14 : BCC .no_barrier
  .barrier
  SEP #$20
  JSL Sprite_PlayerCantPassThrough
  BRA .check_interact
  .no_barrier
  SEP #$20

  .check_interact
  LDA.l Horse_InteractDelay : BNE .done
  LDA.l Horse_DismountCooldown : BNE .done
  ; Allow $5D=$00 (normal) or $5D=$11 (set earlier on the same frame by Player_Main on A-press).
  LDA.b $5D : BEQ + : CMP.b #$11 : BNE .done : +
  LDA.b $4D : ORA.b $11 : ORA.b $5B : BNE .done
  LDA.b $F6 : BPL .done               ; Wait for new A-button press ($80)

  ; Recompute |dx| and |dy| because Sprite_PlayerCantPassThrough clobbers DP $00/$02.
  JSR Sprite_HorseNPC_CheckPlayerDistance
  REP #$20
  LDA.b $00 : CMP.w #26 : BCS .done_sep
  LDA.b $02 : CMP.w #26 : BCS .done_sep
  SEP #$20

  STZ.b $5D                           ; Clear A-press grab/pull pose
  LDA.b #$80 : TRB.b $F6              ; Consume A press cleanly
  ; Unlocked once Ranch Girl is permanently cured and gives the Ocarina.
  LDA.l SideQuestProg2 : AND.b #!SideQuest2_RanchGirl : BEQ .locked
  LDA.l $7EF34C : BEQ .locked
  BRA .mount_now
  .locked
    ; Pre-cure: gentle refusal SFX + brief hop.
    LDA.b #$3C : STA.w $012E          ; SFX2.3C error beep
    LDA.b #$10 : STA.w SprTimerA, X
    RTS

  .mount_now
  JSL Horse_SlotsBusy : BCC + : RTS : +
  ; Snap Link to Epona's saddle coordinates and mount Horse Form!
  LDA.w SprX, X  : STA.b $22
  LDA.w SprXH, X : STA.b $23
  LDA.w SprY, X  : STA.b $20
  LDA.w SprYH, X : STA.b $21
  STZ.w $0DD0, X
  LDA.b #$00 : STA.l Horse_NpcActive : STA.l Horse_HasAnchor
  JSL HorseForm_Mount
  RTS

  .done_sep
  SEP #$20
  .done
  RTS

  .despawn
  STZ.w $0DD0, X
  LDA.b #$00 : STA.l Horse_NpcActive
  RTS
}

; Computes |LinkX - SprX| -> DP $00 (16-bit), |LinkY - SprY| -> DP $02 (16-bit).
Sprite_HorseNPC_CheckPlayerDistance:
{
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.b $22
  BPL + : EOR.w #$FFFF : INC : +
  STA.b $00

  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.b $20
  BPL + : EOR.w #$FFFF : INC : +
  STA.b $02
  SEP #$20
  RTS
}

; Draws the Ranch/group06-bound sparse horse in C2 first32 chars, page1/SP3.
; ---------------------------------------------------------
; Returns A = valid parked NPC facing (0=N, 2=S, 4=W, 6=E; defaults to 6=E).
; M8 in/out, preserves X/Y.
HorseNPC_GetFacing:
{
  LDA.l Horse_AnchorDir
  CMP.b #$08 : BCC +
    LDA.b #$06
  +
  AND.b #$06
  RTS
}

; Returns A = NPC VRAM pose ID for current facing (12=N, 13=S, 14=Side E/W).
HorseNPC_SelectNpcFrame:
{
  JSR HorseNPC_GetFacing
  BEQ .north
  CMP.b #$02 : BEQ .south
    LDA.b #14
    RTS
  .north
  LDA.b #12
  RTS
  .south
  LDA.b #13
  RTS
}

; =========================================================
; Draw Routine (respects Horse_AnchorDir, 16-bit X/Y clip, in-place graze bob)
; =========================================================
Sprite_HorseNPC_Draw:
{
  ; Keep persistent offscreen bit set so horizontal/vertical scroll never runs Sprite_KillSelf.
  LDA.w $0CAA, X : ORA.b #$80 : STA.w $0CAA, X
  JSL Sprite_PrepOamCoord             ; $00=X, $02=Y (relative to camera); C=1 if off-screen
  BCC .coord_ok
    BRL .offscreen_no_oam
  .coord_ok

  ; Optional vertical hop feedback on pre-unlock gentle refusal.
  LDA.w SprTimerA, X : BEQ .no_hop
    LSR #2 : CLC : ADC.b #$01
    REP #$20
    AND.w #$00FF : STA.b $06
    LDA.b $02 : SEC : SBC.b $06 : STA.b $02
    SEP #$20
  .no_hop

  ; Coarse 16-bit bounds check before reserving 8 OAM slots.
  ; Even with !Persist = 01 (C=0), walking >256 px wraps 8-bit X; skip early if fully outside.
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0030 : CMP.w #$0150 : BCC + : BRL .offscreen_m16 : +
  LDA.b $02 : CLC : ADC.w #$0030 : CMP.w #$0130 : BCC + : BRL .offscreen_m16 : +
  SEP #$20

  JSL Sprite_OAM_AllocateDeferToPlayer
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  REP #$20
  LDA.b $90 : STA.l Horse_OffOam      ; exact 8-slot OAM base [$90..$90+$1F] for HorseScanOam
  SEP #$20
endif

  ; Compute graze/head-bob offsets from SprMiscF,X (0..191) without moving SprX/SprY:
  ;   $06 = 16-bit head Y bob (0, 1, or 3; 2 for N/S)
  ;   $08 = 16-bit head X nod (side graze only: +1 right / -1 left)
  ;   $0A = 16-bit tail Y sway (side only: 0 or +1)
  ;   $0C = facing (0=N, 2=S, 4=W, 6=E)
  ;   $0D = visible tile counter (if 0, clear Horse_OffOam)
  ;   $04 = tile props ($27 right/N/S, $67 left H-flip)
  STZ.b $06 : STZ.b $07
  STZ.b $08 : STZ.b $09
  STZ.b $0A : STZ.b $0B
  STZ.b $0D

  JSR HorseNPC_GetFacing
  STA.b $0C
  LDA.w SprMiscF, X
  CMP.b #32 : BCC .phase_done
  CMP.b #64 : BCC .phase_breath
  CMP.b #96 : BCC .phase_done
  CMP.b #168 : BCC .phase_graze
    LDA.b #$01 : STA.b $06            ; 168..191: gentle lift back up
    BRA .phase_done
  .phase_breath
    LDA.b #$01 : STA.b $06            ; 32..63: +1px subtle breathing nod & tail sway
    STA.b $0A
    BRA .phase_done
  .phase_graze
    LDA.b #$03 : STA.b $06            ; 96..167: graze head dip
    LDA.b #$01 : STA.b $08
    LDA.w SprMiscF, X
    CMP.b #112 : BCC .phase_done
    CMP.b #144 : BCS .phase_done
      LDA.b #$01 : STA.b $0A
  .phase_done

  LDA.b #$27 : STA.b $04              ; Pal 3, priority 2, page 1, no flip
  LDA.b $0C
  BEQ .setup_ns
  CMP.b #$02 : BEQ .setup_ns
  CMP.b #$04 : BNE .setup_loop        ; $06 Right keeps dx_head = +1, props = $27
    LDA.b #$67 : STA.b $04            ; Left: H-flip bit $40
    LDA.b $08 : BEQ .setup_loop
      LDA.b #$FF : STA.b $08 : STA.b $09
    BRA .setup_loop
  .setup_ns
    STZ.b $08 : STZ.b $09
    STZ.b $0A
    LDA.b $06 : CMP.b #$03 : BCC .setup_loop
      LDA.b #$02 : STA.b $06

  .setup_loop
  PHX                                 ; save sprite slot X across OAM loop
  LDX.b #$07                          ; eight reserved OAM entries
  LDY.b #$00
  .nextTile
    PHX
    LDA.b $0C
    BEQ .check_ns_limit
    CMP.b #$02 : BNE .tile_coords
    .check_ns_limit
      TXA : CMP.b #$06 : BCC .tile_coords
      JMP .hide_tile                  ; N/S only uses 6 tiles (0..5); hide 6..7

    .tile_coords
    TXA : ASL : TAX                   ; word index X*2

    REP #$20
    LDA.b $0C : AND.w #$00FF
    BEQ .load_x_ns
    CMP.w #$0002 : BEQ .load_x_ns
    CMP.w #$0004 : BEQ .load_x_left
      LDA.l .x_offsets, X
      BRA .add_x_nod
    .load_x_left
      LDA.l .x_offsets_left, X
    .add_x_nod
      CPX.b #$02 : BEQ .apply_x_nod
      CPX.b #$08 : BNE .got_x_off
      .apply_x_nod
        CLC : ADC.b $08
      BRA .got_x_off
    .load_x_ns
      LDA.l .x_offsets_ns, X
    .got_x_off
    CLC : ADC.b $00                   ; 16-bit screen X
    PHA
    CLC : ADC.w #$0010 : CMP.w #$0110
    BCC .x_in_bounds
      PLA
      JMP .hide_tile
    .x_in_bounds
    PLA
    STA ($90), Y
    AND.w #$0100 : STA.b $0E          ; $0F = bit 8 of screen X

    LDA.b $0C : AND.w #$00FF
    BEQ .load_y_north
    CMP.w #$0002 : BEQ .load_y_south
      LDA.l .y_offsets, X
      CPX.b #$00 : BEQ .add_y_head
      CPX.b #$02 : BEQ .add_y_head
      CPX.b #$08 : BEQ .add_y_head
      CPX.b #$0E : BNE .no_y_mod
        CLC : ADC.b $0A
        BRA .no_y_mod
      .add_y_head
        CLC : ADC.b $06
        BRA .no_y_mod
    .load_y_north
      LDA.l .y_offsets_n, X
      CPX.b #$04 : BCS .no_y_mod
        CLC : ADC.b $06
        BRA .no_y_mod
    .load_y_south
      LDA.l .y_offsets_s, X
      CPX.b #$04 : BCS .no_y_mod
        CLC : ADC.b $06
    .no_y_mod
    CLC : ADC.b $02                   ; 16-bit screen Y
    PHA
    CLC : ADC.w #$0010 : CMP.w #$0100
    BCC .y_in_bounds
      PLA
      BRA .hide_tile
    .y_in_bounds
    PLA
    INY
    SEP #$20
    STA ($90), Y

    PLX                               ; 0..7 tile index
    INY
    LDA.b $0C
    BEQ .chr_load_ns
    CMP.b #$02 : BEQ .chr_load_ns
      LDA.l .chr, X
      BRA .store_chr
    .chr_load_ns
      LDA.l .chr_ns, X
    .store_chr
    STA ($90), Y
    INY
    LDA.b $04
    STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y
    PLY : INY
    INC.b $0D
    BRA .tile_done

    .hide_tile
    SEP #$20
    PLX
    INY
    LDA.b #$F0 : STA ($90), Y
    INY #2
    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : STA ($92), Y
    PLY : INY

    .tile_done
    DEX : BMI +
      BRL .nextTile
    +

  PLX
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  LDA.b $0D : BNE +
    LDA.b #$00 : STA.l Horse_OffOam : STA.l Horse_OffOam+1
  +
endif
  RTS

  .offscreen_m16
  SEP #$20
  .offscreen_no_oam
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  LDA.b #$00 : STA.l Horse_OffOam : STA.l Horse_OffOam+1
endif
  RTS

  ; Native source standing footprint; part7 is transparent padding.
  .x_offsets
  dw -3,13,-14,2,18,-11,5,-14
  .x_offsets_left
  dw 3,-13,14,-2,-18,11,-5,14
  .y_offsets
  dw -28,-28,-12,-12,-12,4,4,-21
  .x_offsets_ns
  dw -4,12,-4,12,-4,12,0,0
  .y_offsets_n
  dw -26,-26,-10,-10,6,6,0,0
  .y_offsets_s
  dw -20,-20,-4,-4,12,12,0,0
  .chr
  db $00,$02,$04,$06,$08,$0A,$0C,$0E
  .chr_ns
  db $00,$02,$04,$06,$08,$0A,$00,$00
  .props
  db $27,$27,$27,$27,$27,$27,$27,$27  ; OBJ priority 2: respects BG1 high tiles (arches/roofs)
}

HorseNpc_End:
if !ENABLE_HORSE_PARK_ANYWHERE == 1
  incsrc "Masks/horse_park_anywhere.asm"
  assert pc() <= $53E000, "horse_park_anywhere overlapped mounted clearance allocation"
endif
if !ENABLE_HORSE_CROWD_CHARGE == 1
  incsrc "Masks/horse_charge.asm"
  assert pc() <= $53E000, "horse_charge overlapped mounted clearance allocation"
endif
incsrc "Masks/horse_mounted_helpers.asm"
assert pc() <= $53E000, "Sprite_HorseNPC overlapped mounted clearance allocation"
pullpc
