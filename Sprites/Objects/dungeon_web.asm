; ==============================================================================
; Sprites/Objects/dungeon_web.asm — Burnable Doorway Web (Sprite $B7)
; ==============================================================================
; Subtypes:
;   0 = Horizontal doorway web (32x16 px: two 16x16 solid cells side-by-side)
;   1 = Vertical doorway web   (16x32 px: two 16x16 solid cells stacked)
;
; Behavior:
;   - Solid barrier to Link across full 32x16 / 16x32 doorway span.
;   - Immune to sword (plays tink SFX + spark), arrows, bombs, boomerang,
;     Hookshot (no drag), Ice Rod, and unlit Deku Stick.
;   - Burns on contact with any of the three fire sources:
;       1. Lit Deku Stick (held State=2, or lit swipe State=3 with bit 7 set)
;       2. Fire Rod shot ancilla ($02)
;       3. Lamp flame ancilla ($2F)
;   - Persistence: 16-bit per-room bitmask in WRAM DungeonWeb_BurnedMask
;     ($7ECA00-$7ECC7F, 320 rooms). Cleared on Overworld load ($0283EA) and
;     file load ($02816C), so burned webs stay gone for the entire dungeon
;     visit and respawn after exiting the dungeon.
;
; Graphics:
;   - Uploads 4 8x8 4bpp tiles (128 bytes, adapted from Minish Cap
;     DeepwoodShrine1.png spiderweb) into Underworld common sprite sheet
;     GFX_7D ($0AA4 == $0A) unused X-placeholder slots:
;       OAM Table 0 tiles $4C, $4D (VRAM words $44C0-$44DF)
;       OAM Table 0 tiles $5C, $5D (VRAM words $45C0-$45DF)
;   - Uses OBJ Palette 1 ($22/$62/$A2/$E2), universal across all dungeons.
;   - Burn animation mixes singed web tile $5D with vanilla GFX_79 fire
;     tiles $8E, $9C, $A0, $A2 in OBJ Palette 4 ($38/$78).
; ==============================================================================

!SPRID              = Sprite_DungeonWeb
!NbrTiles           = 07  ; 8 8x8 OAM slots (32x16 or 16x32)
!Harmless           = 01  ; No contact damage to Link; skipped by Deku stun
!HVelocity          = 00
!Health             = 00
!Damage             = 00
!DeathAnimation     = 01  ; Suppress generic smoke; custom flame burn -> state 0
!ImperviousAll      = 01  ; Impervious / sword clink
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 01
!Hitbox             = 00  ; 16x16 per cell (checked across both doorway cells)
!Persist            = 00
!Statis             = 01  ; Not counted as killable enemy for shutter/clear tags
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 01  ; Disable tile collision checks
!Statue             = 00  ; Not pushable
!DeflectProjectiles = 00
!ImperviousArrow    = 00  ; Keep $0CAA bit 1 clear so Hookshot never drags Link
!ImpervSwordHammer  = 01  ; Sword swings tink without dealing damage
!Boss               = 00

%Set_Sprite_Properties(Sprite_DungeonWeb_Prep, Sprite_DungeonWeb_Long)

; ------------------------------------------------------------------------------
; Hooks (vanilla banks $00 and $02)
; ------------------------------------------------------------------------------
pushpc

; LoadCommonSprites ($00E726-$00E729): after GFX_7D ($0AA4) finishes streaming
; to VRAM $4400-$47FF during forced blank. Replaces `LDA.b $10 : CMP.b #$01`.
org $00E726 ; @hook module=Sprites name=DungeonWeb_CommonArtHook kind=jsl target=DungeonWeb_UploadCommonArt expected_m=8 expected_x=8
  JSL DungeonWeb_UploadCommonArt
assert pc() == $00E72A

; Module05_LoadFile ($02816C-$02816F): clear burned-web WRAM mask on file load.
; Replaces `JSL Link_Initialize` ($07F13C).
org $02816C ; @hook module=Sprites name=DungeonWeb_FileLoadHook kind=jsl target=DungeonWeb_FileLoadInit expected_m=8 expected_x=8
  JSL DungeonWeb_FileLoadInit
assert pc() == $028170

; Module08_00_LoadProperties ($0283EA-$0283ED): clear burned-web WRAM mask when
; exiting any dungeon / special area to the Overworld.
; Replaces `JSL RefillLogic_long` ($0DDB75).
org $0283EA ; @hook module=Sprites name=DungeonWeb_OWLoadHook kind=jsl target=DungeonWeb_OWLoadReset expected_m=8 expected_x=8
  JSL DungeonWeb_OWLoadReset
assert pc() == $0283EE

; ------------------------------------------------------------------------------
; Fixed ROM Code & Tile Slot: Bank $36 ($36F200-$36F7FF, 1,536 bytes)
; Relocated off full Bank $2B; Bank $36 (< $40) mirrors low WRAM ($0000-$1FFF)
; when PHK : PLB sets DBR=$36, and Masks/zora_mask.asm ends at $36F030.
; ------------------------------------------------------------------------------
org $36F200
DungeonWeb_CodeStart:

; Entry: M=8, X=8, DBR=$00 (inside LoadCommonSprites during forced blank, VMAIN=$80).
; Preserves X, Y, DBR, DP, and VMADDR ($4800); exits with M=8, X=8 and flags
; set for `LDA.b $10 : CMP.b #$01` so $00E72A `BEQ .in_file_select` is unchanged.
DungeonWeb_UploadCommonArt:
{
  LDA.b $10 : CMP.b #$01 : BEQ .done
  LDA.w $0AA4 : CMP.b #$0A : BNE .done

  PHX
  REP #$30

  ; Upload tiles $4C and $4D (64 bytes) to VRAM word $44C0..$44DF
  LDA.w #$44C0 : STA.w $2116
  LDX.w #$0000
.loop_row0
  LDA.l DungeonWeb_Tile4C, X : STA.w $2118
  INX : INX
  CPX.w #$0040 : BCC .loop_row0

  ; Upload tiles $5C and $5D (64 bytes) to VRAM word $45C0..$45DF
  LDA.w #$45C0 : STA.w $2116
  LDX.w #$0000
.loop_row1
  LDA.l DungeonWeb_Tile5C, X : STA.w $2118
  INX : INX
  CPX.w #$0040 : BCC .loop_row1

  ; Restore VMADDR = $4800 for the following GFX_79/GFX_7A upload at $00E72C
  LDA.w #$4800 : STA.w $2116

  SEP #$30
  PLX

.done
  LDA.b $10 : CMP.b #$01
  RTL
}

; Entry: M=8, X=8 from Module05_LoadFile ($02816C)
DungeonWeb_FileLoadInit:
{
  JSL $07F13C ; Link_Initialize
  JSL DungeonWeb_ClearAll
  RTL
}

; Entry: M=8, X=8 from Module08_00_LoadProperties ($0283EA)
DungeonWeb_OWLoadReset:
{
  JSL $0DDB75 ; RefillLogic_long
  JSL DungeonWeb_ClearAll
  RTL
}

; Clears all 640 bytes ($0280) of DungeonWeb_BurnedMask ($7ECA00-$7ECC7F).
; Entry: any M/X/DBR; preserves A, X, Y, DBR, P.
DungeonWeb_ClearAll:
{
  PHP
  REP #$30
  PHA : PHX
  LDA.w #$0000
  LDX.w #$027E
.clear_loop
  STA.l DungeonWeb_BurnedMask, X
  DEX : DEX : BPL .clear_loop
  PLX : PLA
  PLP
  RTL
}

; ==============================================================================
; Sprite Prep & Main Dispatch
; ==============================================================================

; Entry: M=8, X=8, X = sprite slot (via NewSprPrepTable)
Sprite_DungeonWeb_Prep:
{
  PHB : PHK : PLB

  ; Keep doorway webs alive when >64px off camera in 2x2 rooms (clear bit 6)
  LDA.w SprDefl, X : AND.b #$BF : STA.w SprDefl, X

  ; Ignore arrows, Hookshot, bombs, boomerang, Ice Rod, Somaria, and Byrna
  LDA.b #$01 : STA.w SprBulletproof, X

  ; Cache subtype (0 = 32x16 horiz, 1 = 16x32 vert) in transition-safe SprMiscC
  LDA.w SprSubtype, X : AND.b #$01 : STA.w SprMiscC, X

  ; Cache per-room persistence bit index (0..15) in transition-safe SprMiscA:
  ; Placed room sprites have $0BC0,X = 0..15; dynamic spawns fall back to 14|sub.
  LDA.w $0BC0, X : BPL .have_bit
    LDA.w SprMiscC, X : ORA.b #$0E
.have_bit
  AND.b #$0F : STA.w SprMiscA, X

  ; If in Underworld ($1B != 0) and already burned this dungeon visit, despawn
  LDA.b $1B : BEQ .done
  JSR DungeonWeb_GetMaskAndRoomOffset : BCC .done
  REP #$20
  PHX
  TYX
  LDA.l DungeonWeb_BurnedMask, X
  PLX
  BIT.b $00
  SEP #$30
  BEQ .done
    STZ.w SprState, X

.done
  PLB
  RTL
}

; Computes $00..$01 = (1 << SprMiscA,X) and 16-bit Y = ($A0 * 2) if $A0 < $0140.
; Entry: M=8, X=8. Returns SEC if valid underworld room (< $0140), CLC otherwise.
; Preserves X; leaves M=8, X=16 on SEC (caller restores SEP #$30) or M=8, X=8 on CLC.
DungeonWeb_GetMaskAndRoomOffset:
{
  LDA.w SprMiscA, X : TAY
  REP #$20
  LDA.w #$0001
  CPY.b #$00 : BEQ .mask_ready
.shift_loop
  ASL A
  DEY : BNE .shift_loop
.mask_ready
  STA.b $00

  REP #$10
  LDA.b $A0 : CMP.w #$0140 : BCS .out_of_range
  ASL A : TAY
  SEP #$20
  SEC
  RTS

.out_of_range
  SEP #$30
  CLC
  RTS
}

; Marks this web's room bit in DungeonWeb_BurnedMask ($7ECA00).
; Entry/Exit: M=8, X=8; preserves X.
DungeonWeb_MarkBurned:
{
  LDA.b $1B : BEQ .exit
  JSR DungeonWeb_GetMaskAndRoomOffset : BCC .exit
  REP #$20
  PHX
  TYX
  LDA.l DungeonWeb_BurnedMask, X : ORA.b $00 : STA.l DungeonWeb_BurnedMask, X
  PLX
  SEP #$30
.exit
  RTS
}

; Entry: M=8, X=8, X = sprite slot (via NewSprTable)
Sprite_DungeonWeb_Long:
{
  PHB : PHK : PLB
  JSR Sprite_DungeonWeb_Draw
  JSL Sprite_CheckActive : BCC .return
    JSR Sprite_DungeonWeb_Main
.return
  PLB
  RTL
}

Sprite_DungeonWeb_Main:
{
  LDA.w SprAction, X : BEQ .intact

  ; SprAction == 1: short flame burn (SprTimerA counts 20 -> 0), then doorway opens
  JSR DungeonWeb_SolidBarrier
  LDA.w SprTimerA, X : BNE .done
    STZ.w SprState, X
.done
  RTS

.intact
  JSR DungeonWeb_SolidBarrier
  JSR DungeonWeb_CheckSwordTink
  JSR DungeonWeb_CheckFireSources
  RTS
}

; Enforces solid collision across both 16x16 halves of the 32x16 / 16x32 doorway.
DungeonWeb_SolidBarrier:
{
  JSL Sprite_Get_16_bit_Coords
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprMiscC, X : BNE .vertical

  REP #$20
  LDA.w SprCachedX : PHA
  CLC : ADC.w #$0010 : STA.w SprCachedX
  SEP #$20
  JSL Sprite_PlayerCantPassThrough
  REP #$20
  PLA : STA.w SprCachedX
  SEP #$20
  RTS

.vertical
  REP #$20
  LDA.w SprCachedY : PHA
  CLC : ADC.w #$0010 : STA.w SprCachedY
  SEP #$20
  JSL Sprite_PlayerCantPassThrough
  REP #$20
  PLA : STA.w SprCachedY
  SEP #$20
  RTS
}

; Produces vanilla sword tink SFX + spark across both 16x16 cells without damage.
; Fast-exits in 5 cycles whenever Link is not actively swinging the sword ($3C == 0).
DungeonWeb_CheckSwordTink:
{
  LDA.b $3C : BEQ .exit
  LDA.b $46 : BNE .exit
  LDA.w $0301 : AND.b #$02 : BNE .exit ; Ignore Hammer

  JSL Sprite_CheckDamageFromPlayer
  LDA.b $46 : BNE .exit ; Cell 0 already triggered tink recoil

  LDA.w SprMiscC, X : BNE .vertical
  LDA.w SprX, X : PHA
  LDA.w SprXH, X : PHA
  LDA.w SprX, X : CLC : ADC.b #$10 : STA.w SprX, X
  LDA.w SprXH, X : ADC.b #$00 : STA.w SprXH, X
  JSL Sprite_CheckDamageFromPlayer
  PLA : STA.w SprXH, X
  PLA : STA.w SprX, X
  RTS

.vertical
  LDA.w SprY, X : PHA
  LDA.w SprYH, X : PHA
  LDA.w SprY, X : CLC : ADC.b #$10 : STA.w SprY, X
  LDA.w SprYH, X : ADC.b #$00 : STA.w SprYH, X
  JSL Sprite_CheckDamageFromPlayer
  PLA : STA.w SprYH, X
  PLA : STA.w SprY, X
.exit
  RTS
}

; Checks all 3 fire sources against the full 32x16 / 16x32 web bounds:
;   1. Fire Rod shot ($02) and Lamp flame ($2F) in front ancilla slots 0..4
;   2. Lit Deku Stick (State == 2, or State == 3 with SwipeTimer bit 7 set)
DungeonWeb_CheckFireSources:
{
  ; Precompute 16-bit web AABB: [$04..$08) x [$06..$0A)
  LDA.w SprX, X : STA.b $04
  LDA.w SprXH, X : STA.b $05
  LDA.w SprY, X : STA.b $06
  LDA.w SprYH, X : STA.b $07

  LDA.w SprMiscC, X : BNE .bounds_vert
  REP #$20
  LDA.b $04 : CLC : ADC.w #$0020 : STA.b $08
  LDA.b $06 : CLC : ADC.w #$0010 : STA.b $0A
  SEP #$20
  BRA .scan_ancillae

.bounds_vert
  REP #$20
  LDA.b $04 : CLC : ADC.w #$0010 : STA.b $08
  LDA.b $06 : CLC : ADC.w #$0020 : STA.b $0A
  SEP #$20

.scan_ancillae
  LDY.b #$04
.anc_loop
  LDA.w $0C4A, Y : BEQ .next_anc
  CMP.b #$02 : BEQ .check_anc_layer
  CMP.b #$2F : BNE .next_anc

.check_anc_layer
  LDA.b $1B : BEQ .anc_box
    LDA.w $0C7C, Y : CMP.w SprFloor, X : BNE .next_anc

.anc_box
  LDA.w $0C04, Y : STA.b $00
  LDA.w $0C18, Y : STA.b $01
  LDA.w $0BFA, Y : STA.b $02
  LDA.w $0C0E, Y : STA.b $03

  REP #$20
  ; Horizontal overlap: AncX < WebX1 && AncX + 16 > WebX0
  LDA.b $00 : CMP.b $08 : BCS .anc_miss_16
  CLC : ADC.w #$0010 : CMP.b $04 : BCC .anc_miss_16 : BEQ .anc_miss_16
  ; Vertical overlap: AncY < WebY1 && AncY + 16 > WebY0
  LDA.b $02 : CMP.b $0A : BCS .anc_miss_16
  CLC : ADC.w #$0010 : CMP.b $06 : BCC .anc_miss_16 : BEQ .anc_miss_16
  SEP #$20

  ; If Fire Rod shot ($02) is still moving ($0C54,Y == 0), halt it on the web
  LDA.w $0C4A, Y : CMP.b #$02 : BNE .ignite_web
  LDA.w $0C54, Y : BNE .ignite_web
    LDA.b #$01 : STA.w $0C54, Y
    LDA.b #$1F : STA.w $0C68, Y
    LDA.b #$08 : STA.w $0C90, Y
  BRA .ignite_web

.anc_miss_16
  SEP #$20
.next_anc
  DEY : BPL .anc_loop

  if !DISABLE_ITEMS == 0
    JSR DungeonWeb_CheckStickFire
    BCS .ignite_web
  endif
  RTS

.ignite_web
  LDA.b #$01 : STA.w SprAction, X
  LDA.b #$14 : STA.w SprTimerA, X ; 20-frame flame burn (~0.33s)
  LDA.b #$2A : STA.w $012E        ; Vanilla flame SFX
  LDA.b #$2D : STA.w $012F        ; Fire ignition crackle SFX
  JSR DungeonWeb_MarkBurned
  RTS
}

if !DISABLE_ITEMS == 0
; Helper: checks Lit Deku Stick (held State=2 or lit swipe State=3) against [$04..$08) x [$06..$0A).
; Entry/Exit: M=8, X=8, preserves X (sprite slot); returns SEC if web ignited, CLC otherwise.
DungeonWeb_CheckStickFire:
{
  ; Fast-reject when no Deku Stick is active (6 cycles) or when unlit
  LDA.l DekuStick_State : BEQ .early_no_fire
  CMP.b #$02 : BEQ .stick_lit
  CMP.b #$03 : BNE .early_no_fire
  LDA.l DekuStick_SwipeTimer : BPL .early_no_fire

.stick_lit
  LDA.b $1B : BEQ .check_stick_torch_probe
    LDA.b $EE : CMP.w SprFloor, X : BNE .early_no_fire
  BRA .check_stick_torch_probe

.early_no_fire
  CLC
  RTS

.check_stick_torch_probe
  ; Probe 1: 8x8 flame box centered on Deku_TorchProbeX/Y[DIR]
  PHX
  LDX.b $2F
  REP #$20
  LDA.l Deku_TorchProbeX, X : CLC : ADC.b $22 : SEC : SBC.w #$0004 : STA.b $00
  CMP.b $08 : BCS .try_swipe_box
  CLC : ADC.w #$0008 : CMP.b $04 : BCC .try_swipe_box : BEQ .try_swipe_box

  LDA.l Deku_TorchProbeY, X : CLC : ADC.b $20 : SEC : SBC.w #$0004 : STA.b $02
  CMP.b $0A : BCS .try_swipe_box
  CLC : ADC.w #$0008 : CMP.b $06 : BCC .try_swipe_box : BEQ .try_swipe_box
  SEP #$20
  PLX
  BRA .latch_stick_and_ignite

.try_swipe_box
  SEP #$20
  PLX
  LDA.l DekuStick_State : CMP.b #$03 : BNE .no_fire
  LDA.l DekuStick_SwipeTimer : AND.b #$1F
  CMP.b #$07 : BCC .no_fire
  CMP.b #$0B : BCS .no_fire

  ; Probe 2: Active swipe hitbox Deku_HitProbeOffX/Y + Width/Height
  PHX
  LDA.b $2F : LSR A : TAX
  LDA.l Deku_HitProbeWidth, X : STA.b $0C
  STZ.b $0D
  LDA.l Deku_HitProbeHeight, X : STA.b $0E
  STZ.b $0F
  LDX.b $2F
  REP #$20
  LDA.l Deku_HitProbeOffX, X : CLC : ADC.b $22 : STA.b $00
  CMP.b $08 : BCS .stick_miss_16
  CLC : ADC.b $0C : CMP.b $04 : BCC .stick_miss_16 : BEQ .stick_miss_16

  LDA.l Deku_HitProbeOffY, X : CLC : ADC.b $20 : STA.b $02
  CMP.b $0A : BCS .stick_miss_16
  CLC : ADC.b $0E : CMP.b $06 : BCC .stick_miss_16 : BEQ .stick_miss_16
  SEP #$20
  PLX

.latch_stick_and_ignite
  LDA.l DekuStick_State : CMP.b #$03 : BNE .hit
    LDA.l DekuStick_SwipeTimer : ORA.b #$40 : STA.l DekuStick_SwipeTimer
.hit
  SEC
  RTS

.stick_miss_16
  SEP #$20
  PLX
.no_fire
  CLC
  RTS
}
endif

; ==============================================================================
; Draw Routine (8 8x8 OAM slots: indices 0..7 = 32x16 horiz, 8..15 = 16x32 vert)
; ==============================================================================
Sprite_DungeonWeb_Draw:
{
  JSL Sprite_PrepOamCoord
  LDA.w SprPause, X : BEQ +
    RTS
  +
  JSL Sprite_OAM_AllocateDeferToPlayer

  ; $06 = table base (0 for subtype 0, 8 for subtype 1)
  ; $07 = burn stage (0 = intact, 1 = early burn >= $0A, 2 = late sparks < $0A)
  LDA.w SprMiscC, X : ASL #3 : STA.b $06
  STZ.b $07
  LDA.w SprAction, X : BEQ .draw_loop_init
    INC.b $07
    LDA.w SprTimerA, X : CMP.b #$0A : BCS .draw_loop_init
      INC.b $07

.draw_loop_init
  PHX
  LDX.b #$07
  LDY.b #$00

.next_tile
  PHX
  TXA : CLC : ADC.b $06 : TAX

  LDA.w .x_offsets, X : STA.b $08 : STZ.b $09
  LDA.w .y_offsets, X : STA.b $0A : STZ.b $0B

  REP #$20
  LDA.b $00 : CLC : ADC.b $08 : STA.b ($90), Y
  AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : CLC : ADC.b $0A : STA.b ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y
    LDA.b #$F0 : STA.b ($90), Y
    STA.b $0E
.on_screen_y
  INY
  LDA.b $07 : BNE .burn_tile

  LDA.w .chr_intact, X : STA.b ($90), Y
  INY
  LDA.w .prop_intact, X : STA.b ($90), Y
  BRA .finish_tile

.burn_tile
  PLX : PHX
  CMP.b #$01 : BNE .late_sparks
  LDA.w .chr_burn_early, X : STA.b ($90), Y
  INY
  LDA.b $1A : AND.b #$04 : ASL #4 ; Flicker H-flip ($00 / $40) every 4 frames
  EOR.w .prop_burn_early, X : STA.b ($90), Y
  BRA .finish_tile

.late_sparks
  LDA.w .chr_burn_late, X : STA.b ($90), Y
  INY
  LDA.b $1A : AND.b #$02 : ASL #5
  EOR.w .prop_burn_late, X : STA.b ($90), Y

.finish_tile
  PLX
  PHY
  TYA : LSR #2 : TAY
  LDA.b $0F : STA.b ($92), Y ; 8x8 size (bit 1 = 0), X9 high bit
  PLY : INY
  DEX : BMI .done_tiles
  BRL .next_tile

.done_tiles
  PLX
  RTS

.x_offsets
  db  0,  8, 16, 24,  0,  8, 16, 24 ; Subtype 0: 32x16 horizontal
  db  0,  8,  0,  8,  0,  8,  0,  8 ; Subtype 1: 16x32 vertical

.y_offsets
  db  0,  0,  0,  0,  8,  8,  8,  8 ; Subtype 0: 32x16 horizontal
  db  0,  0,  8,  8, 16, 16, 24, 24 ; Subtype 1: 16x32 vertical

.chr_intact
  db $4C, $4D, $4D, $4C, $4C, $4D, $4D, $4C ; Subtype 0
  db $5C, $5C, $4D, $4D, $4D, $4D, $5C, $5C ; Subtype 1

.prop_intact
  db $22, $22, $62, $62, $A2, $A2, $E2, $E2 ; Priority 2, OBJ Pal 1, H/V flips
  db $22, $62, $22, $62, $A2, $E2, $A2, $E2

.chr_burn_early
  db $5D, $9C, $8E, $5D, $9C, $5D, $8E, $5D ; Singed web ($5D) + GFX_79 flames

.prop_burn_early
  db $22, $38, $38, $62, $78, $A2, $78, $E2

.chr_burn_late
  db $9C, $A0, $9C, $A2, $A2, $9C, $A0, $9C ; GFX_79 shrinking flame sparks

.prop_burn_late
  db $38, $38, $78, $38, $78, $38, $78, $78
}

; ==============================================================================
; 4bpp Common Sprite Web Tiles (128 bytes total: $4C, $4D, $5C, $5D)
; Adapted from Minish Cap DeepwoodShrine1.png spiderweb, mapped to ALTTP
; OBJ Palette 1 (1=#F8F8F8 silk, 13=#B8B8C8 mid, 14=#787888 rib, 5=#282828 dark)
; ==============================================================================
DungeonWeb_Tile4C:
  ; Tile $4C: Horizontal doorway jamb anchor + radial strands
  db $F3,$00, $FF,$00, $DF,$20, $96,$08, $0A,$05, $2F,$10, $BB,$44, $EE,$11
  db $33,$20, $4E,$4A, $F3,$B2, $9E,$0C, $0F,$07, $3B,$1B, $FF,$74, $3D,$3D

DungeonWeb_Tile4D:
  ; Tile $4D: Central octant-symmetric cobweb hub + concentric rings
  db $E6,$09, $FD,$00, $FB,$00, $76,$09, $6F,$90, $DD,$02, $BB,$04, $6F,$90
  db $AF,$0D, $3D,$29, $DA,$50, $6F,$2B, $F7,$D5, $DB,$8A, $BC,$14, $DC,$D8

DungeonWeb_Tile5C:
  ; Tile $5C: Vertical lintel/threshold anchor (transpose of Tile $4C)
  db $F3,$00, $E1,$02, $C7,$20, $F2,$05, $6F,$10, $75,$0A, $FF,$00, $E6,$09
  db $32,$20, $62,$42, $A7,$A3, $B7,$27, $5F,$55, $5B,$1B, $FE,$6C, $AF,$0D

DungeonWeb_Tile5D:
  ; Tile $5D: Singed snapping web strands (burn transition frame)
  db $42,$20, $E4,$02, $4E,$00, $04,$00, $20,$10, $72,$01, $27,$00, $02,$00
  db $62,$20, $A6,$02, $4A,$00, $04,$00, $30,$10, $53,$01, $25,$00, $02,$00

DungeonWeb_CodeEnd:
print "End of Sprites/Objects/dungeon_web.asm ", pc
assert pc() <= $36F800, "DungeonWeb overflowed $36F200-$36F7FF slot into $36F800"
pullpc
