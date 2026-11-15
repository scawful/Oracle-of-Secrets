; =========================================================
; Horse Form (!CurrentMask = #$09) + Fence Jumping + NMI DMA
; Placed in bank $53 after HorseGraphics and HorsePalette
; under !ENABLE_HORSE_FORM == 1.
;
; Architecture:
;   - Native Link movement/hitbox remains unchanged. Sparse original-size horse
;     frames use up to8 horse parts, two ROM-exact rider parts and two shadows.
;   - Mounted OBJ uses00/02/04/06/0C + conditionally26/2A/2C, rider08/0A.
;     P2/follower and shared shadow28/38 are preserved. Live tools refuse mount;
;     native-source item cells are restored on loss of mounted ownership.
;   - Ranch NPC is bound to parent00 + loaded group06 (C2/BC/BD/C3). Its private
;     first32 C2 chars preserve runner lowerhalf and all kid/sweeper BD chars.
;     Unknown actors/tools suspend the composition and restore the native cells.
;   - Nineteen bounded frame IDs include all six original side run poses. No
;     modulo16 alias, new global graphics sheet, or new WRAM reservation.
;   - Fence jumping retains the existing sixteen-frame validated landing path.
; =========================================================

!Horse_MagicMarker   = $4852    ; 'HR' cold-init sentinel
!Horse_MaskId        = $09
!Horse_SpriteId      = $2D
!Horse_JumpFrames    = $10      ; 16-frame fence vault

!Horse_DefaultNpcX   = $01C0    ; Toto Ranch clear grass X (448px; avoids the adjacent east hay bale)
!Horse_DefaultNpcY   = $0294    ; Toto Ranch clear grass Y (660px; rider clears hay, feet remain north of fence)

; Vanilla routines referenced long
Horse_GetTileAttr    = $00882E  ; (DP $00=Ypx, $02=Xpx>>3) -> A=8x8 tiletype

; ---------------------------------------------------------
; Speed table indexed cleanly matching BunnySpeedTable ($00..$10)
; ---------------------------------------------------------
HorseSpeedTable:
  db $2C ; 0x00 - ground cardinal (Bunny = $20, vanilla = $18)
  db $1F ; 0x01 - ground diagonal (Bunny = $12, vanilla = $10)
  db $0E ; 0x02 - stairs
  db $18 ; 0x03 - stairs diagonal
  db $14 ; 0x04 - soft slipping
  db $0C ; 0x05 - soft slipping diagonal
  db $0A ; 0x06 - hard slipping
  db $06 ; 0x07 - hard slipping diagonal
  db $0E ; 0x08 - pushing
  db $12 ; 0x09 - pushing diagonal
  db $0C ; 0x0A - intraroom stairs
  db $1E ; 0x0B - slope / ledge run
  db $24 ; 0x0C - heavy grass / shallow water cardinal
  db $18 ; 0x0D - heavy grass / shallow water diagonal
  db $18 ; 0x0E
  db $12 ; 0x0F
  db $40 ; 0x10 - Pegasus cap

; Sparse frame offsets/pointers are generated in gfx/horse_sparse_tables.asm.

; Parabolic Z height across 16 jump frames (0..15)
HorseJump_ZTable:
  db  0,  4,  7, 10, 12, 13, 14, 15
  db 15, 14, 13, 11,  9,  6,  3,  1

; Walkable 8x8 tiletype table ($00..$57). 1 = safe landing ground.
; Matches Overworld TileBehavior ($07D452..$07D570).
HorseWalkableAttr:
  db 1,0,0,0,0,1,1,1, 0,0,0,0,0,0,0,0 ; $00-$0F (00=ground, 05..07=normal)
  db 0,0,0,0,1,1,1,1, 0,0,0,0,0,0,0,0 ; $10-$1F (14..17=normal)
  db 0,1,0,1,1,1,0,0, 0,0,0,0,0,0,0,0 ; $20-$2F (21,23..25=normal; 28..2F=ledges)
  db 0,0,0,0,0,0,0,0, 1,1,1,1,1,0,0,0 ; $30-$3F (38..3C=normal)
  db 1,1,1,0,0,1,0,1, 1,1,0,0,1,1,1,1 ; $40-$4F (40 grass, 48 dirt/grass, 45/47/49/4C..4F normal)
  db 0,0,0,0,0,0,0,0                  ; $50-$57 (liftable rocks/bushes, bonk)

; Wooden ranch fence Tile16 IDs on Toto Ranch (area 0x00)
; HorseFenceTile16s lives in Masks/horse_ground_clearance.asm (bank $53 slice $53E000-$53E7FF);
; it is read long (CMP.l), so placement is free.

; ---------------------------------------------------------
; NMI Upload Hook at $008B5C (replaces LDX #$0400 : STX $4305 : LDA #$01 : STA $420B)
; ---------------------------------------------------------
pushpc
org $008A0C ; @hook module=Masks name=Horse_LinkDmaPrefix kind=jml target=Horse_LinkDmaPrefix expected_m=8 expected_x=16
  assert read1($008A0C) == $A0 && read2($008A0D) == $4100 && read1($008A0F) == $8C && read2($008A10) == $2116, "Horse native Link prefix hook preimage changed"
  JML Horse_LinkDmaPrefix : NOP #2

org $008B5C ; @hook module=Masks name=Horse_NmiUploadHook kind=jsl target=Horse_NmiUpload expected_m=8 expected_x=16
  assert read3($008B5C) == $0400A2, "Expected animated tile DMA tail at $008B5C"
  JSL Horse_NmiUpload
  NOP #7
assert pc() == $008B67
pullpc

incsrc "Masks/horse_sparse_runtime.asm"

; ---------------------------------------------------------
; Palette Helpers (M/X=8 ABI)
; Writes Epona's 7 colors into unused Light World SP-3[9..15]
; ($7EC472/$7EC672) through TimeSystem's Day/Night tinting.
; ---------------------------------------------------------
UpdateHorsePalette:
Horse_LoadNpcPalette:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  REP #$30
  PHX : PHY
  LDY.w #$000C                        ; Y = 7 colors = 14 bytes (offsets 12,10,...,0)
  .loop
    PHY
    TYX : LDA.l HorsePalette, X : PHA
    TYA : CLC : ADC.w #$0172 : TAX    ; $7EC300 + $0172..$017E = $7EC472..$7EC47E
    PLA
    JSL LoadDayNightPaletteEffect
    REP #$30
    PLX
    STA.l $7EC672, X
    TXY
    DEY : DEY : BPL .loop
  PLY : PLX
  SEP #$20
  INC.b $15
  PLB : PLP
  RTL
}

Horse_RestoreSp3Palette:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  REP #$30
  PHX : PHY
  LDY.w #$000C
  .loop
    PHY
    TYA : CLC : ADC.w #$0172 : TAX
    LDA.w #$14A5                      ; MainSpr SP-3[9..15] uniform fill
    JSL LoadDayNightPaletteEffect
    REP #$30
    PLX
    STA.l $7EC672, X
    TXY
    DEY : DEY : BPL .loop
  PLY : PLX
  SEP #$20
  INC.b $15
  PLB : PLP
  RTL
}

; ---------------------------------------------------------
; Initialization & Lifecycle Helpers (M=8/any, restores flags)
; ---------------------------------------------------------
HorseForm_EnsureInit:
{
  PHP : REP #$30
  LDA.l Horse_Marker : CMP.w #!Horse_MagicMarker : BEQ .ok
    SEP #$20
    PHX
    LDX.w #$001F
    LDA.b #$00
    .clr
      STA.l Horse_Marker, X
      DEX : BPL .clr
    LDA.b #$FF
    STA.l Horse_UploadedFrame
    STA.l Horse_NpcUploadedFrame
    REP #$20
    LDA.w #!Horse_MagicMarker : STA.l Horse_Marker
    PLX
  .ok
  PLP
  RTL
}

HorseForm_ClearState:
{
  PHP : %m8()
  LDA.b #$00
  STA.l Horse_State
  STA.l Horse_JumpTimer
  STA.l Horse_JumpStep
  STA.l Horse_JumpZ
  STA.l Horse_PushTimer
  STA.l Horse_AnimTimer
  STA.l Horse_PalLoaded
  PLP
  RTL
}

; Enter Horse Form from Ranch NPC interaction. Preserves A/X/Y/DBR/P (safe for 8/16-bit callers).
HorseForm_Mount:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB              ; DBR=$00 mirrors WRAM $0000..$1FFF
  JSL HorseForm_EnsureInit
  JSL Horse_SlotsBusy
  BCC +
    PLB : REP #$30 : PLY : PLX : PLA : PLP
    RTL
  +
  JSL HorseForm_ClearState

  LDA.b #$14 : STA.w $0CF8
  JSL $0DBB67                         ; Link_CalculateSFXPan
  ORA.w $0CF8 : STA.w $012E

  LDA.b #!Horse_MaskId : STA.w !CurrentMask
  LDA.b #$10 : STA.b $BC
  LDA.b #$FF : STA.l Horse_UploadedFrame
  LDA.b #$06 : STA.l Horse_Frame
  LDA.b #$06 : STA.b $2F             ; Start facing Right to match NPC mount cleanly
  STZ.b $5D : STZ.b $3C : STZ.b $3A
  JSL Palette_ArmorAndGloves
  LDA.b #$01 : STA.l Horse_PalLoaded
  LDA.b #$0C : STA.l Horse_InteractDelay
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; User-initiated or water dismount (saves Ranch anchor; no mask transform puff). Preserves A/X/Y/DBR/P.
HorseForm_Dismount:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB
  LDA.b $8A : BNE .no_ranch_anchor
  LDA.b $1B : BNE .no_ranch_anchor
    REP #$20
    LDA.b $22 : STA.l Horse_AnchorX
    LDA.b $20 : STA.l Horse_AnchorY
    SEP #$20
    LDA.b #$01 : STA.l Horse_HasAnchor
    BRA .finish_dismount
  .no_ranch_anchor
  LDA.b #$00 : STA.l Horse_HasAnchor
  JSL Horse_RestoreSp3Palette

  .finish_dismount
  LDA.b #$14 : STA.w $0CF8
  JSL $0DBB67
  ORA.w $0CF8 : STA.w $012E

  JSL ResetToLinkGraphics
  JSL HorseForm_ClearState
  LDA.b #$18 : STA.l Horse_DismountCooldown
  LDA.b #$18 : STA.l Horse_InteractDelay
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; Quiet dismount for doorways / overworld entrances / module exit.
; Safe under 16-bit index callers (e.g., Overworld/entrances.asm M=8,X=16); preserves A/X/Y/DBR/P.
HorseForm_SilentDismount:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB
  LDA.b #$00 : STA.l Horse_HasAnchor
  JSL Horse_RestoreSp3Palette
  JSL ResetToLinkGraphics
  JSL HorseForm_ClearState
  LDA.b #$10 : STA.l Horse_DismountCooldown
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; ---------------------------------------------------------
; Per-Frame Hook from LinkMain_FrameHook (M=8, X/Y preserved by caller)
; ---------------------------------------------------------
HorseForm_FrameTick:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB              ; DBR=$00 mirrors WRAM & calls Sprite_SpawnDynamically safely
  JSL HorseForm_EnsureInit

  LDA.l Horse_DismountCooldown : BEQ +
    DEC : STA.l Horse_DismountCooldown
  +
  LDA.l Horse_InteractDelay : BEQ +
    DEC : STA.l Horse_InteractDelay
  +
  LDA.l Horse_JumpCooldown : BEQ +
    DEC : STA.l Horse_JumpCooldown
  +

  LDA.w !CurrentMask : CMP.b #!Horse_MaskId : BEQ .mounted
    ; Clear stale mount state and keep Ranch Epona NPC active on Toto Ranch.
    LDA.l Horse_State : BEQ +
      JSL HorseForm_ClearState
    +
    JSR HorseForm_MaintainRanchNpc
    PLB : PLP
    RTL

  .mounted
  ; Dismount automatically indoors, deep-water swimming, or falling in a pit.
  LDA.b $1B : BNE .force_silent_dismount
  LDA.b $10 : CMP.b #$09 : BEQ .outdoor_ok
  CMP.b #$0B : BEQ .outdoor_ok
  BRA .force_silent_dismount
  .outdoor_ok
  JSL Horse_SlotsBusy : BCC +
    BRL .force_silent_dismount
  +
  LDA.b $5D : CMP.b #$04 : BEQ .force_ranch_dismount
  LDA.b $4D : CMP.b #$04 : BEQ .force_ranch_dismount
  LDA.b $5B : CMP.b #$02 : BCS .force_ranch_dismount

  ; Suppress B-button sword swing and Y-button item press edges while mounted.
  LDA.b #$C0 : TRB.b $F4
  STZ.b $3C

  ; Refresh SP-3[9..15] + SP-7 if a palette reload reset SP-3 to uniform fill.
  REP #$20
  LDA.l $7EC67C : CMP.l $7EC67E : BNE +
    SEP #$20
    JSL Palette_ArmorAndGloves
  +
  SEP #$20

  ; Handle mid-jump physics or check ground triggers.
  LDA.l Horse_State : BEQ .grounded
    JSR HorseForm_JumpTick
    JSR HorseForm_UpdateAnimFrame
    PLB : PLP
    RTL

  .grounded
  LDA.b $10 : CMP.b #$09 : BNE .skip_triggers
  LDA.b $11 : BNE .skip_triggers
  LDA.b $5D : ORA.b $4D : ORA.b $6C : BNE .skip_triggers
  LDA.w $0FFC : ORA.w $02E4 : BNE .skip_triggers
    JSR HorseForm_CheckFenceJump
    JSR HorseForm_ConstrainGroundInput
    JSR HorseForm_PlayHoofBeat
  .skip_triggers
  JSR HorseForm_UpdateAnimFrame
  PLB : PLP
  RTL

  .force_silent_dismount
  JSL HorseForm_SilentDismount
  PLB : PLP
  RTL

  .force_ranch_dismount
  JSL HorseForm_Dismount
  PLB : PLP
  RTL
}

; Ensure Toto Ranch NPC Epona spawns whenever Link is outdoors on area $00.
HorseForm_MaintainRanchNpc:
{
  LDA.b $1B : ORA.b $8A : BEQ + : BRL .not_ranch : +
  LDA.b $10 : CMP.b #$09 : BEQ + : RTS : +
  LDA.b $11 : BEQ + : RTS : +
  LDA.w $0FFC : BEQ + : RTS : +
  JSL Horse_RanchProfileReady : BCS + : RTS : +
  JSL Horse_RanchActorsSafe : BCS + : RTS : +

  ; Check if an active $2D sprite already exists in $0DD0/$0E20 slots 0..15.
  PHX : PHY
  %m8()
  LDX.b #$0F
  .scan
    LDA.w $0DD0, X : BEQ .next_slot
    LDA.w $0E20, X : CMP.b #!Horse_SpriteId : BEQ .found
  .next_slot
    DEX : BPL .scan

  ; Spawn Epona NPC dynamically in a free sprite slot (X=0 template index).
  LDX.b #$00
  LDA.b #!Horse_SpriteId : JSL Sprite_SpawnDynamically : BMI .spawn_failed
  LDA.l Horse_HasAnchor : BEQ .use_default_pos
    REP #$20
    LDA.l Horse_AnchorX : STA.b $00
    LDA.l Horse_AnchorY : STA.b $02
    SEP #$20
    BRA .set_coords
  .use_default_pos
    REP #$20
    LDA.w #!Horse_DefaultNpcX : STA.b $00
    LDA.w #!Horse_DefaultNpcY : STA.b $02
    SEP #$20
  .set_coords
  LDA.b $00 : STA.w SprX, Y
  LDA.b $01 : STA.w SprXH, Y
  LDA.b $02 : STA.w SprY, Y
  LDA.b $03 : STA.w SprYH, Y
  LDA.b #$00
  STA.w $0F20, Y : STA.w $0F70, Y : STA.w $0DE0, Y
  STA.w $0E30, Y : STA.w $0E80, Y
  STA.w SprAction, Y : STA.w SprFrame, Y
  LDA.b #$01 : STA.l Horse_NpcActive : STA.w SprBulletproof, Y
  LDA.b #14  : STA.l Horse_NpcFrame
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  JSL Horse_LoadNpcPalette
  BRA .done_scan

  .found
  LDA.b #$01 : STA.l Horse_NpcActive
  BRA .done_scan

  .spawn_failed
  LDA.b #$00 : STA.l Horse_NpcActive

  .done_scan
  PLY : PLX
  .done
  RTS

  .not_ranch
  LDA.l Horse_NpcActive : BEQ +
    JSL Horse_RestoreSp3Palette
  +
  LDA.b #$00 : STA.l Horse_HasAnchor : STA.l Horse_NpcActive
  RTS
}

; Play soft boot-dust hoof thud periodically while galloping.
HorseForm_PlayHoofBeat:
{
  LDA.b $F0 : AND.b #$0F : BEQ .done
  LDA.l Horse_AnimTimer : AND.b #$0F : CMP.b #$04 : BNE .done
  LDA.w $012E : BNE .done
    LDA.b #$23 : STA.w $012E          ; SFX2.23 soft hoof beat
  .done
  RTS
}

; ---------------------------------------------------------
; Fence Jump Detection & Execution
; ---------------------------------------------------------
HorseForm_CheckFenceJump:
{
  LDA.l Horse_JumpCooldown : BNE .reset_push

  ; Convert facing $2F (0=U, 2=D, 4=L, 6=R) -> dir bit ($08,$04,$02,$01).
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  LDA.b $F0 : AND.l .dir_bits, X : BEQ .reset_push

  ; Require 2 consecutive frames pushing toward the fence for crisp response.
  LDA.l Horse_PushTimer : INC : STA.l Horse_PushTimer
  CMP.b #$02 : BCC .done

  PHX : PHY
  TXA : STA.l Horse_JumpDir           ; 0=U, 1=D, 2=L, 3=R

  ; Probe distance 1 then distance 2 ahead for wooden fence Tile16s.
  LDA.b #$00 : JSR HorseForm_ProbeFence : BCS .hit_fence
  LDA.b #$01 : JSR HorseForm_ProbeFence : BCC .no_fence

  .hit_fence
  ; Candidate landing stored in Horse_JumpEndX / Horse_JumpEndY (16-bit).
  JSR HorseForm_ComputeJumpEnd : BCC .no_fence
  JSR HorseForm_CheckLandingWalkable : BCC .no_fence

  ; Validated! Launch 16-frame fence jump.
  REP #$20
  LDA.b $22 : STA.l Horse_JumpStartX
  LDA.b $20 : STA.l Horse_JumpStartY
  SEP #$20
  LDA.b #$00 : STA.l Horse_JumpStep : STA.l Horse_JumpZ : STA.l Horse_PushTimer
  LDA.b #$01 : STA.l Horse_State
  LDA.b #$20 : STA.w $012E            ; SFX2.20 ledge/fence jump cue
  ; Suppress directional input starting this very frame so vanilla doesn't bump fence.
  LDA.b #$0F : TRB.b $F0 : TRB.b $F2
  PLY : PLX
  RTS

  .no_fence
  PLY : PLX
  .done
  RTS

  .reset_push
  LDA.b #$00 : STA.l Horse_PushTimer
  RTS

  .dir_bits
  db $08, $04, $02, $01               ; Up, Down, Left, Right
}

; Input: A = probe pass (0 = near, 1 = far). Uses Horse_JumpDir.
; Output: Carry set if fence Tile16 found; fence Tile16 origin left in $0A=FY, $0C=FX.
HorseForm_ProbeFence:
{
  PHA                                 ; 1,S = pass
  LDA.l Horse_JumpDir : ASL : ORA 1, S : ASL : TAX
  REP #$20
  LDA.l .dx_table, X : CLC : ADC.b $22 : STA.b $0C ; FX candidate X
  LDA.l .dy_table, X : CLC : ADC.b $20 : STA.b $0A ; FY candidate Y
  SEP #$20
  PLA                                 ; balance stack

  ; Query Map16 Tile16 + attribute at ($0A=Y, $0C=X)
  JSR Horse_QueryTileAt               ; outputs DP $04 = 16-bit Tile16, A = attr
  REP #$20
  LDA.b $04
  LDX.b #HorseFenceTile16s_End-HorseFenceTile16s-2
  .cmp_loop
    CMP.l HorseFenceTile16s, X : BEQ .matched
    DEX : DEX : BPL .cmp_loop
  SEP #$20
  CLC
  RTS

  .matched
  ; Align origin to 16x16 Tile16 corner.
  LDA.b $0C : AND.w #$FFF0 : STA.b $0C
  LDA.b $0A : AND.w #$FFF0 : STA.b $0A
  SEP #$20
  SEC
  RTS

  ; Offset pairs indexed by (dir*4 + pass*2): U0,U1, D0,D1, L0,L1, R0,R1
  .dx_table
  dw   8,   8,   8,   8,  -2,  -8,  18,  24
  .dy_table
  dw   2,  -6,  20,  26,  11,  11,  11,  11
}

; Uses DP $0A=FY, $0C=FX and Horse_JumpDir to write Horse_JumpEndX/Y.
; Validates the target doesn't cross a $400 world border or exceed jump reach.
HorseForm_ComputeJumpEnd:
{
  LDA.l Horse_JumpDir : ASL : TAX
  REP #$20
  JMP (.dir_table, X)

  .dir_table
  dw .up, .down, .left, .right

  .up
  LDA.b $22 : STA.l Horse_JumpEndX
  LDA.b $0A : SEC : SBC.w #$0010 : STA.l Horse_JumpEndY
  BRA .bounds_check

  .down
  LDA.b $22 : STA.l Horse_JumpEndX
  LDA.b $0A : CLC : ADC.w #$000C : STA.l Horse_JumpEndY
  BRA .bounds_check

  .left
  LDA.b $0C : SEC : SBC.w #$0010 : STA.l Horse_JumpEndX
  LDA.b $20 : STA.l Horse_JumpEndY
  BRA .bounds_check

  .right
  LDA.b $0C : CLC : ADC.w #$0010 : STA.l Horse_JumpEndX
  LDA.b $20 : STA.l Horse_JumpEndY

  .bounds_check
  ; Ensure EndX and EndY remain inside the same $400 overworld quadrant
  ; and strictly within [0x0010..0x0FF0] non-border margins.
  LDA.l Horse_JumpEndX : CMP.w #$0010 : BCC .invalid
  EOR.b $22 : AND.w #$FC00 : BNE .invalid
  LDA.l Horse_JumpEndY : CMP.w #$0010 : BCC .invalid
  EOR.b $20 : AND.w #$FC00 : BNE .invalid
  SEP #$20
  SEC
  RTS

  .invalid
  SEP #$20
  CLC
  RTS
}

; Verifies 3 footprint points around (Horse_JumpEndX, Horse_JumpEndY) are walkable.
HorseForm_CheckLandingWalkable:
{
  LDX.b #$02                          ; check 3 points: 2, 1, 0
  .pt_loop
    PHX
    TXA : ASL : TAX
    REP #$20
    LDA.l Horse_JumpEndX : CLC : ADC.l .off_x, X : STA.b $0C
    LDA.l Horse_JumpEndY : CLC : ADC.l .off_y, X : STA.b $0A
    SEP #$20
    JSR Horse_QueryTileAt             ; A = 8x8 tiletype
    CMP.b #$58 : BCS .blocked_pop
    TAX
    LDA.l HorseWalkableAttr, X : BEQ .blocked_pop
    PLX
    DEX : BPL .pt_loop
  SEC
  RTS

  .blocked_pop
  PLX
  CLC
  RTS

  .off_x
  dw 4, 11, 8
  .off_y
  dw 12, 12, 8
}

; Queries Overworld_GetTileAttrAtLocation ($00882E) safely from any DBR.
; Inputs: DP $0A = 16-bit world Y px, DP $0C = 16-bit world X px (M/X=8).
; Outputs: A = 8-bit TileType (M=8, X=8), DP $04 = 16-bit Tile16 ID.
Horse_QueryTileAt:
{
  PHB : PHX : PHY
  %a16()
  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $06 : PHA
  LDA.b $0A : STA.b $00               ; $00 = world Y pixels
  LDA.b $0C : LSR #3 : STA.b $02      ; $02 = world X / 8

  SEP #$20
  LDA.b #$00 : PHA : PLB              ; $00882E reads $0708..$070E with w-addr
  REP #$30
  LDA.b $00 : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $06
  LDA.b $02 : SEC : SBC.w $070C : AND.w $070E : ORA.b $06 : TAX
  LDA.l $7E2000, X : PHA              ; Preserve Tile16 ID across $00882E

  JSL Horse_GetTileAttr               ; returns SEP #$30, A = TileType
  TAX                                 ; hold TileType across stack restores
  REP #$20
  PLA : STA.b $04
  PLA : STA.b $06 : PLA : STA.b $02 : PLA : STA.b $00
  SEP #$30
  TXA
  PLY : PLX : PLB
  RTS
}

; Advance 16-frame jump interpolation and freeze vanilla d-pad movement.
HorseForm_JumpTick:
{
  LDA.b #$0F : TRB.b $F0 : TRB.b $F2  ; mask directional buttons mid-flight

  LDA.l Horse_JumpStep : CMP.b #!Horse_JumpFrames : BCS .land
    TAX
    LDA.l HorseJump_ZTable, X : STA.l Horse_JumpZ

    ; Linearly interpolate X and Y using t = Horse_JumpStep + 1 (1..16 / 16)
    INX                               ; X = 1..16
    STX.b $0E                         ; scratch byte $0E = t
    REP #$20
    LDA.l Horse_JumpStartX : STA.b $00
    LDA.l Horse_JumpEndX   : STA.b $02
    JSR Horse_Lerp16
    STA.b $22

    LDA.l Horse_JumpStartY : STA.b $00
    LDA.l Horse_JumpEndY   : STA.b $02
    JSR Horse_Lerp16
    STA.b $20
    SEP #$20

    LDA.l Horse_JumpStep : INC : STA.l Horse_JumpStep
    CMP.b #!Horse_JumpFrames : BCC .done

  .land
  REP #$20
  LDA.l Horse_JumpEndX : STA.b $22
  LDA.l Horse_JumpEndY : STA.b $20
  SEP #$20
  LDA.b #$00 : STA.l Horse_State : STA.l Horse_JumpZ : STA.l Horse_JumpStep
  LDA.b #$10 : STA.l Horse_JumpCooldown
  LDA.b #$21 : STA.w $012E            ; SFX2.21 hoof landing thud
  .done
  RTS
}

; Input (M=16, X=8): DP $00=Start, DP $02=End, DP $0E=t (1..16).
; Output (M=16): A = Start + ((End - Start) * t) / 16.
Horse_Lerp16:
{
  LDA.b $02 : SEC : SBC.b $00
  BEQ .done_same
  PHP                                 ; save N flag for sign
  BPL .pos
    EOR.w #$FFFF : INC
  .pos
  ; Unsigned |delta| <= 64. Multiply by 8-bit DP $0E (1..16) in 5 shifts.
  STA.b $06                           ; multiplicand (shifted left)
  LDA.b $0E : AND.w #$001F : STA.b $08 ; multiplier
  LDA.w #$0000
  LDX.b #$05
  .mul_loop
    LSR.b $08 : BCC .no_add
      CLC : ADC.b $06
    .no_add
    ASL.b $06
    DEX : BNE .mul_loop
  LSR #4                              ; divide by 16
  PLP : BPL .add_start
    EOR.w #$FFFF : INC
  .add_start
  CLC : ADC.b $00
  RTS

  .done_same
  LDA.b $00
  RTS
}

; ---------------------------------------------------------
; Frame Animation Selector -> Horse_Frame (0..13)
; ---------------------------------------------------------
HorseForm_UpdateAnimFrame:
{
  ; Preserve one already-visible pose while its hidden NPC graphics restore.
  ; No movement, facing, health, input or inventory writes. Transition paths
  ; never use this hold; they force a fresh mounted upload instead.
  LDA.b $10 : CMP.b #9 : BNE .select_frame
  LDA.b $11 : BNE .select_frame
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BEQ .select_frame
  LDA.l Horse_UploadedFrame : CMP.b #!Horse_FrameCount : BCS .select_frame
  STA.l Horse_Frame
  RTS
  .select_frame
  ; Check airborne jump state first (custom fence jump OR vanilla ledge hop $24/$25).
  LDA.l Horse_State : BEQ + : BRL .in_jump : +
  LDA.b $25 : BMI .chk_neg_z
    LDA.b $24 : BEQ .check_walk
    BRL .in_jump
  .chk_neg_z
  LDA.b $24 : CMP.b #$F0 : BCS .check_walk
    BRL .in_jump

  .check_walk
  ; Moving if any D-pad held and Link isn't locked ($2E or $F0&$0F)
  LDA.b $F0 : AND.b #$0F : BEQ .idle
  LDA.l Horse_AnimTimer : INC : STA.l Horse_AnimTimer
  LDA.b $2F : AND.b #$06 : TAX        ; 0=U, 2=D, 4=L, 6=R -> dw table index
  JMP (.walk_dir, X)

  .walk_dir
  dw .walk_up, .walk_down, .walk_left_right, .walk_left_right

  .walk_up
  LDA.l Horse_AnimTimer : LSR #3 : AND.b #$01 : CLC : ADC.b #$04 ; frames 4, 5
  STA.l Horse_Frame
  RTS

  .walk_down
  LDA.l Horse_AnimTimer : LSR #3 : AND.b #$01 : CLC : ADC.b #$01 ; frames 1, 2
  STA.l Horse_Frame
  RTS

  .walk_left_right
  LDA.l Horse_AnimTimer : CMP.b #24 : BCC +
    LDA.b #$00 : STA.l Horse_AnimTimer
  +
  LSR #2 : TAX
  LDA.l .gallop_cycle, X : STA.l Horse_Frame
  RTS
  .gallop_cycle
  db 7, 8, 9, 16, 17, 18              ; all six original source run poses

  .idle
  LDA.b #$00 : STA.l Horse_AnimTimer
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  LDA.l .idle_frames, X : STA.l Horse_Frame
  RTS
  .idle_frames
  db 3, 0, 6, 6                       ; N Idle, S Idle, L/R Idle

  .in_jump
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  CPX.b #$00 : BEQ .jump_n
  CPX.b #$01 : BEQ .jump_s
    ; Side jump: ascending step < 8 -> 10, descending >= 8 -> 11
    LDA.l Horse_State : BEQ .jump_side_dn
    LDA.l Horse_JumpStep : CMP.b #$08 : BCS .jump_side_dn
      LDA.b #$0A : STA.l Horse_Frame
      RTS
    .jump_side_dn
    LDA.b #$0B : STA.l Horse_Frame
    RTS
  .jump_s
  LDA.b #$0C : STA.l Horse_Frame
  RTS
  .jump_n
  LDA.b #$0D : STA.l Horse_Frame
  RTS
}

; ---------------------------------------------------------
; Player OAM Override ($0DA191)
; Entry: M=8, X=8, DBR=$0D, caller DBR stacked above JSL return.
; Displaces LDY #$00 : LDA $11 at $0DA191..$0DA194.
; ---------------------------------------------------------
pushpc
org $0DA191 ; @hook module=Masks name=Horse_PlayerOamHook kind=jsl target=Horse_PlayerOamHook expected_m=8 expected_x=8
  assert read4($0DA191) == $11A500A0, "Expected PlayerOam_Main entry instructions at $0DA191"
  JSL Horse_PlayerOamHook
assert pc() == $0DA195
pullpc

Horse_PlayerOamHook:
{
  LDA.w !CurrentMask : CMP.b #!Horse_MaskId : BEQ .draw_horse
    LDY.b #$00 : LDA.b $11
    RTL

  .draw_horse
  JSL Horse_DrawPlayerOam_Long
  PLA : PLA : PLA                     ; drop JSL return inside PlayerOam_Main
  PLB                                 ; pop PlayerOam_Main's entry PHB
  RTL
}

Horse_DrawPlayerOam_Long:
{
  PHB : PHP
  SEP #$20 : LDA.b #$00 : PHA : PLB   ; DBR=$00 mirrors WRAM $0000..$1FFF

  ; Setup $64 priority and $0352 OAM offset matching PlayerOam_Main ($0DA120/$0DA126).
  REP #$30
  LDA.b $EE : AND.w #$0003 : ASL : TAX
  LDA.l $0DA126, X : STA.b $64
  LDA.w $0FB3 : AND.w #$00FF : CMP.w #$0003 : BCC +
    LDA.w #$0002
  +
  ASL : TAX
  LDA.l $0DA120, X : STA.w $0352

  ; Base screen origin: SX16 = $22 - $E2, SY16 = $20 - $E8
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8 : STA.b $02

  ; Air Z height = max(Horse_JumpZ, vanilla $24/$25).
  SEP #$20
  LDA.b $25 : BMI .chk_van_z
    LDA.b $24 : BRA .have_van_z
  .chk_van_z
  LDA.b $24 : CMP.b #$F0 : BCC .have_van_z
    LDA.b #$00
  .have_van_z
  CMP.l Horse_JumpZ : BCS +
    LDA.l Horse_JumpZ
  +
  STA.b $0E : STZ.b $0F               ; temp 16-bit AirZ in $0E/$0F
  ; OBJ priority 3 only mid-jump or beside wooden fences (high-priority rails).
  ; Elsewhere native $65 stays, so gates, arches and banisters cover horse and rider.
  LDA.l Horse_State : BEQ +
    LDA.b $65 : ORA.b #$30 : STA.b $65
    BRA ++
  +
  JSR Horse_ApplyFencePriority
  ++

  ; Handle invincibility blink ($031F) & invisible state ($4B == $0C).
  LDA.b $11 : BNE .chk_vis_flags
  LDA.w $031F : BEQ .chk_vis_flags
    DEC : STA.w $031F
    CMP.b #$04 : BCC .chk_vis_flags
    AND.b #$01 : BEQ .hide_all
  .chk_vis_flags
  LDA.b $4B : CMP.b #$0C : BEQ .hide_all
  LDA.b $55 : BNE .hide_all
  BRA .draw_visible

  .hide_all
  REP #$30
  JSR HorseOam_HideAll
  BRL .exit

  .draw_visible
  REP #$30
  SEP #$20
  ; Overworld scroll-row frames ($17=3) already fill vblank: hold the resident
  ; pose one frame so NMI skips the ~1.3KB horse DMA (no black top scanline).
  LDA.b $17 : CMP.b #$03 : BNE .frame_ok
  LDA.b $11 : BNE .frame_ok
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BNE .frame_ok
  LDA.l Horse_UploadedFrame : CMP.b #!Horse_FrameCount : BCS .frame_ok
  STA.l Horse_Frame
  .frame_ok
  ; Latch validated frame before indexing metadata; never alias an expanded ID.
  LDA.l Horse_Frame : CMP.b #!Horse_FrameCount : BCC +
    LDA.b #6
  +
  STA.b $0D
  REP #$20 : AND.w #$00FF : TAX
  LDA.l HorseFrame_Width, X : AND.w #$00FF : LSR : STA.b $08
  LDA.b $00 : CLC : ADC.w #8 : SEC : SBC.b $08 : STA.b $04
  LDA.l HorseFrame_Height, X : AND.w #$00FF : STA.b $08
  LDA.b $02 : CLC : ADC.w #16 : SEC : SBC.b $08 : SEC : SBC.b $0E : STA.b $06
  LDY.w $0352

  ; Slot 0: Rider Head ($08, SP-7, highest priority).
  JSR Horse_EmitRiderHead

  ; South ($2F=2) places Epona head/forelock in front of rider lap while shoulders
  ; frame behind Epona's ears; other directions place Rider Body in front of Epona.
  SEP #$20
  LDA.b $2F : CMP.b #$02 : BEQ .south_oam_order
    JSR Horse_EmitRiderBody
    JSR Horse_EmitEponaBody
    BRA .draw_shadow
  .south_oam_order
    JSR Horse_EmitEponaBody
    JSR Horse_EmitRiderBody

  .draw_shadow
  SEP #$20
  ; Shadow only while airborne (same test as frame select): on the ground it read as Link's own.
  LDA.l Horse_State : BNE .shadow_on
  LDA.b $25 : BMI .shadow_neg_z
    LDA.b $24 : BNE .shadow_on
    BRL .shadow_done
  .shadow_neg_z
  LDA.b $24 : CMP.b #$F0 : BCC .shadow_on
    BRL .shadow_done
  .shadow_on
  ; Slots 6..7: Ground hoof shadow (two 8x8 tiles $6C at SX16, SY16+12)
  LDA.b #$6C : STA.b $0B
  LDA.b #$08 : ORA.b $65 : STA.b $0A
  LDA.b #$00 : STA.b $0C
  REP #$20
  LDA.b $00 : STA.b $08
  LDA.b $02 : CLC : ADC.w #$000C : STA.b $0E
  JSR HorseOam_WriteSlot
  INY #4

  SEP #$20
  LDA.b #$48 : ORA.b $65 : STA.b $0A
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0008 : STA.b $08
  JSR HorseOam_WriteSlot
  INY #4
  .shadow_done

  ; Clear only unused entries; an eight-part horse consumes all twelve slots.
  REP #$30
  TYA : SEC : SBC.w $0352 : CMP.w #48 : BCS .exit
  .clear_rest
    LDA.w #$F000 : STA.w $0800, Y
    TYA : LSR #2 : TAX
    SEP #$20 : LDA.b #$01 : STA.w $0A20, X : REP #$20
    INY #4
    TYA : SEC : SBC.w $0352 : CMP.w #48 : BCC .clear_rest

  .exit
  PLP : PLB
  RTL
}

; Sets OBJ priority 3 in $65 when a wooden fence Tile16 lies under the
; horse/rider footprint (6 samples). Preserves DP $04-$0F, P and registers.
Horse_ApplyFencePriority:
{
  PHP
  REP #$30
  PHX : PHY
  LDA.b $04 : PHA : LDA.b $08 : PHA : LDA.b $0A : PHA
  LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$30
  LDY.b #$00
  LDX.b #10
  .sample
    PHX
    REP #$20
    LDA.l .dx, X : CLC : ADC.b $22 : STA.b $0C
    LDA.l .dy, X : CLC : ADC.b $20 : STA.b $0A
    SEP #$20
    JSR Horse_QueryTileAt               ; M/X=8; X/Y preserved, DP $04 = Tile16
    REP #$20
    LDA.b $04
    LDX.b #HorseFenceTile16s_End-HorseFenceTile16s-2
    .cmp
      CMP.l HorseFenceTile16s, X : BEQ .hit
      DEX : DEX : BPL .cmp
    SEP #$20
    PLX
    DEX : DEX : BPL .sample
  BRA .restore
  .hit
  SEP #$20
  PLX
  LDY.b #$30
  .restore
  REP #$20
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A
  PLA : STA.b $08 : PLA : STA.b $04
  SEP #$20
  TYA : ORA.b $65 : STA.b $65
  REP #$30
  PLY : PLX : PLP
  RTS

  ; Offsets from Link ($22,$20): three columns across the body, rider and hooves rows.
  .dx
  dw -6, 8, 22, -6, 8, 22
  .dy
  dw  6, 6,  6, 22, 22, 22
}

; Emits 16x16 Rider Head ($08) or Body ($0A) on SP-7 using DP $0D=frame. Returns M=16, X=16.
Horse_EmitRiderHead:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : TAX
  SEP #$20
  LDA.l HorseRider_HeadX, X : STA.b $08
  LDA.l HorseRider_HeadY, X : STA.b $09
  LDA.b #$08 : STA.b $0B
  BRA Horse_EmitRiderCommon
}

Horse_EmitRiderBody:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : TAX
  SEP #$20
  LDA.l HorseRider_BodyX, X : STA.b $08
  LDA.l HorseRider_BodyY, X : STA.b $09
  LDA.b #$0A : STA.b $0B
}

Horse_EmitRiderCommon:
{
  LDA.b $2F : CMP.b #$04 : BNE .rider_no_flip
    LDA.l HorseFrame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08 ; mirror actual width
    LDA.b #$4E : BRA .set_rider_attr        ; H-flip + SP-7
  .rider_no_flip
  LDA.b #$0E                                ; SP-7, no flip
  .set_rider_attr
  ORA.b $65 : STA.b $0A                     ; DP $0A = rider OAM attr
  LDA.b #$02 : STA.b $0C                    ; DP $0C = 16x16 size

  ; Compute signed Y ($0E/$0F) before overwriting $08/$09 with Screen X.
  LDA.b $09 : PHA
  REP #$20
  LDA.b $08 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $04 : STA.b $08
  SEP #$20 : PLA : REP #$20 : AND.w #$00FF
  BIT.w #$0080 : BEQ +
    ORA.w #$FF00
  +
  CLC : ADC.b $06 : STA.b $0E
  JSR HorseOam_WriteSlot
  INY #4
  RTS
}

; Sparse horse parts, signed source offsets and width-aware horizontal mirroring.
Horse_EmitEponaBody:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : ASL #3 : TAX
  .loop
    PHX
    SEP #$20
    LDA.l HorsePiece_X, X : STA.b $08
    LDA.l HorsePiece_Y, X : STA.b $09
    REP #$20 : TXA : AND.w #7 : TAX : SEP #$20
    LDA.l HorseMounted_Chr, X : STA.b $0B
    LDA.b #$06 : STA.b $0A
    LDA.b $2F : CMP.b #4 : BNE .not_flip
      REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
      LDA.l HorseFrame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
      LDA.b #$46 : STA.b $0A
    .not_flip
    LDA.b $0A : ORA.b $65 : STA.b $0A
    LDA.b #2 : STA.b $0C
    LDA.b $09 : PHA
    REP #$20
    LDA.b $08 : AND.w #$00FF
    BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
    CLC : ADC.b $04 : STA.b $08
    SEP #$20 : PLA : REP #$20 : AND.w #$00FF
    BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
    CLC : ADC.b $06 : STA.b $0E
    JSR HorseOam_WriteSlot
    INY #4
    PLX : INX : PHX
    TXA : AND.w #7 : STA.b $08
    LDA.b $0D : AND.w #$00FF : TAX
    LDA.l HorseFrame_Count, X : AND.w #$00FF : CMP.b $08
    PLX
    ; An eight-part frame wraps the index to zero after its final part.
    LDA.b $08 : BEQ .done
    ; Compare the next part index against this frame count.
    PHX
    LDA.b $0D : AND.w #$00FF : TAX
    LDA.b $08 : SEP #$20 : CMP.l HorseFrame_Count, X : REP #$20
    PLX : BCS .done
    BRL .loop
    .done
  RTS
}

; Writes one OAM entry at Y ($0800+Y) and $0A20+(Y>>2). Requires DBR=$00. Keeps Y.
; Inputs (M=16): $08=screen X (signed), $0E=screen Y (signed), $0B=tile, $0A=attr, $0C=size (0 or 2).
HorseOam_WriteSlot:
{
  ; Clip Y if completely offscreen vertically (224..65519)
  LDA.b $0E : CLC : ADC.w #$0010 : CMP.w #$0100 : BCS .offscreen
  ; Clip X if outside [-16..255]
  LDA.b $08 : CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .offscreen

  ; On screen: write OAM $0800..$0803 via DBR=$00 WRAM mirror
  SEP #$20
  LDA.b $08 : STA.w $0800, Y        ; X low
  LDA.b $0E : STA.w $0801, Y        ; Y
  LDA.b $0B : STA.w $0802, Y        ; tile
  LDA.b $0A : STA.w $0803, Y        ; attr

  ; Compute $0A20 index and high X bit
  LDA.b $09 : AND.b #$01              ; high bit of Screen X ($08/$09)
  ORA.b $0C                           ; size bit ($02 or $00)
  PHA
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
  PLA : STA.w $0A20, X
  REP #$20
  RTS

  .offscreen
  SEP #$20
  LDA.b #$F0 : STA.w $0801, Y
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
  LDA.b #$01 : STA.w $0A20, X
  REP #$20
  RTS
}

HorseOam_HideAll:
{
  ; Compacted to free bank $53 bytes for post-dismount NMI cache (queue125).
  LDA.w $0352 : LSR #2 : TAX
  LDA.w #$0101
  LDY.b #5
- STA.w $0A20, X
  INX : INX
  DEY : BPL -
  RTS
}

incsrc "Masks/horse_ground_clearance.asm"
