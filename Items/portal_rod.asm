; =========================================================
; Portal Rod Item

; LinkState_UsingEther
org    $07A50F
RodAnimationTimer:
  db $03, $03, $05

LinkItem_PortalRod:
{
  BIT $3A : BVS .y_button_held
    LDA $6C : BNE .return
    JSR Link_CheckNewY_ButtonPress : BCC .return
      LDX.b #$00
      JSR LinkItem_EvaluateMagicCost : BCC .insufficient_mp
        LDA.b #$30 : JSR $802F    ; Sfx3
        JSL   LinkItem_FirePortal
        .y_button_held

        JSR $AE65 ; HaltLinkWhenUsingItems
        DEC $3D : BPL .return
        LDA $0300 : INC A : STA $0300 : TAX
        LDA RodAnimationTimer, X : STA $3D
        CPX.b #$03 : BNE .return
        STZ $0300
        STZ $5E
        STZ $3D
        LDA $0301 : AND.b #$FE : STA $0301

      .insufficient_mp
      LDA $3A : AND.b #$BF : STA $3A

  .return
  RTS
}

assert pc() <= $07A568

; Ancilla_CheckSpriteCollision
org $088DC3 ; @hook module=Items
JSL Ancilla_HandlePortalCollision : NOP

pullpc

Ancilla_HandlePortalCollision:
{
  LDA.w $0E20, Y : CMP.b #$03 : BNE .not_portal_arrow
    PHY
    ; Entering orange (subtype 1) exits 16 px right of blue ($0632); entering
    ; blue (subtype 2) exits 16 px below orange ($0633). Those indices keep the
    ; last slot after a portal is dismissed, rejected or never placed, so only
    ; move the arrow when the counterpart is a live portal of the other color.
    LDA.w SprSubtype, Y : CMP.b #$01 : BEQ .from_orange
                          CMP.b #$02 : BNE .done
      LDY.w $0633 : LDA.b #$01 : BRA .check_counterpart
    .from_orange
      LDY.w $0632 : LDA.b #$02
    .check_counterpart
    CPY.b #$10 : BCS .done
    CMP.w SprSubtype, Y : BNE .done
    LDA.w $0E20, Y : CMP.b #$03 : BNE .done
    LDA.w SprState, Y : CMP.b #$09 : BCC .done
    LDA.w SprSubtype, Y : CMP.b #$02 : BNE .exit_at_orange
      LDA.w SprX, Y : CLC : ADC.b #$10 : STA.w ANC0XL, X
      LDA.w SprXH, Y : ADC.b #$00 : STA.w ANC0XH, X
      LDA.w SprY, Y : STA.w ANC0YL, X
      LDA.w SprYH, Y : STA.w ANC0YH, X
      BRA .done
    .exit_at_orange
      LDA.w SprX, Y : STA.w ANC0XL, X
      LDA.w SprXH, Y : STA.w ANC0XH, X
      LDA.w SprY, Y : CLC : ADC.b #$10 : STA.w ANC0YL, X
      LDA.w SprYH, Y : ADC.b #$00 : STA.w ANC0YH, X
    .done
    PLY
    ; Z set: skip the deflection branch at $088DC8. The portal's bulletproof
    ; byte ($0BA0 = $FF) then makes vanilla report no collision: the arrow
    ; keeps flying, moved when a valid counterpart exists and unchanged
    ; otherwise (Discord 2025-01-10).
    LDA.b #$00
    RTL
  .not_portal_arrow
  ; Restore arrow deflection sprite code from $088DC3
  LDA.w SprTileDie,Y : AND.b #$08
  RTL
}

LinkItem_FirePortal:
{
  LDA.b #$03
  JSL   Sprite_SpawnDynamically : BPL .continue
    ; No free slot: the cast already paid, so give the magic back.
    JSL PortalRod_RefundCast
    RTL
  .continue

  ; Bit 1 of the bolt's SprMiscA keeps the pre-cast selector, so a fizzle can
  ; restore it exactly (the empty-pair reset below may also change it).
  LDA.w $0FA6 : AND.b #$01 : ASL A : STA.w SprMiscA, Y

  PHX
  ; A room change can leave the last color selected after every portal is gone.
  ; Start an empty pair with blue; only accepted live portals and bolts still
  ; in flight preserve the turn. The allocator clears the new slot's subtype
  ; and action, so this scan excludes it.
  LDX.b #$0F
  .find_live_portal
    LDA.w SprState, X : CMP.b #$09 : BNE .next_portal
    LDA.w SprType, X : CMP.b #$03 : BNE .next_portal
    LDA.w SprSubtype, X : CMP.b #$01 : BEQ .toggle_color
                         CMP.b #$02 : BEQ .toggle_color
    LDA.w SprAction, X : CMP.b #!PortalShotAction : BEQ .toggle_color
  .next_portal
    DEX : BPL .find_live_portal
  STZ.w $0FA6
  .toggle_color
  LDA   $7E0FA6 : BEQ .spawn_blue
    STZ.w $0FA6
    BRA .spawn_bolt
  .spawn_blue
  LDA #$01 : STA $7E0FA6
  .spawn_bolt

  TYX
  ; The bolt starts on Link and flies in his facing direction (sprite action
  ; PortalShot). The portal opens where it lands.
  LDA.b $22 : STA.w SprX, X
  LDA.b $23 : STA.w SprXH, X
  LDA.b $20 : STA.w SprY, X
  LDA.b $21 : STA.w SprYH, X
  LDA.b $2F : LSR A : AND.b #$03 : STA.w SprMiscC, X
  LDA.w $0FA6 : ORA.w SprMiscA, X : STA.w SprMiscA, X
  LDA.w $0FA6 : BNE .blue_frame
    LDA.b #$02
  .blue_frame
  AND.b #$02 : STA.w SprFrame, X ; blue (1) -> frame 0, orange (0) -> frame 2
  STZ.w SprGfx, X
  STZ.w PortalShot_Dist, X
  LDA.b #!PortalShotAction : STA.w SprAction, X
  ; This is Link's cast, not a child of the allocator's source sprite slot.
  LDA.b $EE : STA.w SprFloor, X
  STZ.w SprYRound, X : STZ.w SprXRound, X
  ; Dynamic spawning skips Prep; keep this portal active off camera too.
  LDA.w SprDefl, X : ORA.b #$80 : STA.w SprDefl, X
  ; Sprite_SpawnDynamically does not run Sprite_Portal_Prep, so set its
  ; bulletproof byte here: ancillae then pass over the portal instead of
  ; hitting it (runtime: $0BA0 was $00 on Portal Rod portals).
  LDA.b #$FF : STA.w SprBulletproof, X
  PLX

  .return
  ; Delay the spin attack for some amount of time?
  LDA RodAnimationTimer : STA $3D
  STZ $2E
  STZ $0300 : STZ $0301
  LDA.b #$01 : TSB $0301
  RTL
}

; Return one Portal Rod cast (magic cost index $00) to the meter.
; Preserves X/Y. Clobbers A and $00. Caps at a full meter ($80) in case a
; magic jar was picked up while the bolt was in flight.
PortalRod_RefundCast:
{
  PHX
  LDX.b #$00
  JSL Refund_Magic
  LDA.l $7EF36E : CMP.b #$81 : BCC .in_range
    LDA.b #$80 : STA.l $7EF36E
  .in_range
  PLX
  RTL
}

pushpc

org $02FF6E
Overworld_OperateCameraScroll_Long:
{
  PHB : PHK : PLB

  JSR $BB90

  PLB

  RTL
}

Overworld_ScrollMap_Long:
{
  PHB : PHK : PLB
  JSR $F273
  PLB

  RTL
}

pullpc

ScrollToPortal:
{
  REP #$20

  STZ $00
  STZ $02

  LDA $22 : CMP $7EC186 : BEQ .set_x : BCC .x_low
    DEC $02
    DEC A : CMP $7EC186 : BEQ .set_x
    DEC $02
    DEC A
    BRA .set_x
  .x_low

  INC $02
  INC A : CMP $7EC186 : BEQ .set_x
  INC $02
  INC A

  .set_x

  STA $22

  LDA $20 : CMP $7EC184 : BEQ .set_y : BCC .y_low
    DEC $00
    DEC A : CMP $7EC184 : BEQ .set_y
    DEC $00
    DEC A
    BRA .set_y
  .y_low

  INC $00
  INC A : CMP $7EC184 : BEQ .set_y
  INC $00
  INC A

  .set_y

  STA $20
  CMP $7EC184 : BNE .delay_advance
    LDA $22 : CMP $7EC186 : BNE .delay_advance
      INC $B0
      STZ $46
  .delay_advance

  SEP #$20

  LDA $00 : STA $30
  LDA $02 : STA $31

  JSL Overworld_OperateCameraScroll_Long ; $13B90 IN ROM

  LDA $0416 : BEQ .exit
    JSL Overworld_ScrollMap_Long ; $17273 IN ROM
  .exit

  RTL
}

; Portal Rod bolt flight (portal sprite action 7), one frame. Entry X = slot,
; M/X 8-bit. Returns carry set when the bolt landed and the caller must run
; StateHandler; carry clear while flying or after a fizzle. Pits and water pass under it; any other tile
; at its leading edge stops it. It then opens the portal on the last position
; where Link's whole body (and the portal's own tile) is on safe floor. With
; no such position on the path it fizzles and refunds the cast.
PortalShot_Fly:
{
  PHB : PHK : PLB
  LDA.w SprMiscC, X : BEQ .move_up
    DEC A : BEQ .move_down
    DEC A : BEQ .move_left
  ; .move_right
    LDA.w SprX, X : CLC : ADC.b #!PortalShotSpeed : STA.w SprX, X
    LDA.w SprXH, X : ADC.b #$00 : STA.w SprXH, X
    BRA .moved
  .move_up
    LDA.w SprY, X : SEC : SBC.b #!PortalShotSpeed : STA.w SprY, X
    LDA.w SprYH, X : SBC.b #$00 : STA.w SprYH, X
    BRA .moved
  .move_down
    LDA.w SprY, X : CLC : ADC.b #!PortalShotSpeed : STA.w SprY, X
    LDA.w SprYH, X : ADC.b #$00 : STA.w SprYH, X
    BRA .moved
  .move_left
    LDA.w SprX, X : SEC : SBC.b #!PortalShotSpeed : STA.w SprX, X
    LDA.w SprXH, X : SBC.b #$00 : STA.w SprXH, X
  .moved
  LDA.w PortalShot_Dist, X : CLC : ADC.b #!PortalShotSpeed : STA.w PortalShot_Dist, X

  ; Leading edge of Link's body box in the flight direction.
  LDY.w SprMiscC, X
  LDA.w .lead_x, Y : STA.b $06
  LDA.w .lead_y, Y : STA.b $07
  JSR PortalShot_ProbeTile
  CMP.b #$00 : BEQ .passable
  CMP.b #$08 : BEQ .passable ; deep water
  CMP.b #$09 : BEQ .passable ; shallow water
  CMP.b #$20 : BEQ .passable ; pit
  CMP.b #$40 : BEQ .passable ; grass
  CMP.b #$48 : BEQ .passable
    JMP .stop
  .passable

  ; Second shot (orange, with a live blue): keep the pair where
  ; Portal_CheckWarpContext can warp both ways. SprMiscA bit 2 = the bolt has
  ; been inside that window. Before it gets there the flight is unchanged; on
  ; the first step inside, spots recorded outside are dropped; once it leaves,
  ; it stops and opens on the last safe spot that was inside.
  LDA.w SprMiscA, X : AND.b #$01 : BNE .window_ok
  LDY.w BlueSpriteIndex : CPY.b #$10 : BCS .window_ok
  LDA.w SprType, Y : CMP.b #$03 : BNE .window_ok
  LDA.w SprState, Y : CMP.b #$09 : BNE .window_ok
  LDA.w SprSubtype, Y : CMP.b #$02 : BNE .window_ok
  JSR PortalShot_InPairWindow : BCS .in_window
    LDA.w SprMiscA, X : AND.b #$04 : BEQ .window_ok
    JMP .stop
  .in_window
  LDA.w SprMiscA, X : AND.b #$04 : BNE .window_ok
    LDA.w SprMiscA, X : ORA.b #$04 : STA.w SprMiscA, X
    LDA.w PortalShot_Dist, X : AND.b #$7F : STA.w PortalShot_Dist, X
  .window_ok

  ; Too close to Link would overlap and warp at once (old fixed offsets).
  LDY.w SprMiscC, X
  LDA.w PortalShot_Dist, X : AND.b #$7F : CMP.w .min_distance, Y : BCC .check_range
  LDY.b #9 ; .safe_x/.safe_y entries - 1
  .next_safe_probe
    PHY
    LDA.w .safe_x, Y : STA.b $06
    LDA.w .safe_y, Y : STA.b $07
    JSR PortalShot_ProbeTile
    PLY
    CMP.b #$00 : BEQ .probe_safe
    CMP.b #$48 : BNE .check_range
    .probe_safe
    DEY : BPL .next_safe_probe
  LDA.w SprX, X  : STA.w PortalShot_SafeX, X
  LDA.w SprXH, X : STA.w PortalShot_SafeXH, X
  LDA.w SprY, X  : STA.w PortalShot_SafeY, X
  LDA.w SprYH, X : STA.w PortalShot_SafeYH, X
  LDA.w PortalShot_Dist, X : ORA.b #$80 : STA.w PortalShot_Dist, X

  .check_range
  LDA.w PortalShot_Dist, X : AND.b #$7F : CMP.b #!PortalShotRange : BCS .stop
    PLB
    CLC
    RTL

  .stop
  LDA.w PortalShot_Dist, X : BMI .land
    ; Fizzle: no safe floor on the path. Give back this cast's turn and magic.
    LDA.b #$3C : STA.w $012E ; SFX2.3C error beep
    STZ.w SprState, X
    LDA.w SprMiscA, X : LSR A : AND.b #$01 : STA.w $0FA6
    JSL PortalRod_RefundCast
    PLB
    CLC
    RTL
  .land
  LDA.w PortalShot_SafeX, X  : STA.w SprX, X
  LDA.w PortalShot_SafeXH, X : STA.w SprXH, X
  LDA.w PortalShot_SafeY, X  : STA.w SprY, X
  LDA.w PortalShot_SafeYH, X : STA.w SprYH, X
  ; Accept with this bolt's own color: later casts may have toggled $0FA6.
  LDA.w SprMiscA, X : AND.b #$01 : STA.w $0FA6 : BEQ .orange_frame
    STZ.w SprFrame, X
    BRA .landed
  .orange_frame
  LDA.b #$02 : STA.w SprFrame, X
  .landed
  PLB
  SEC ; caller runs StateHandler
  RTL

  ; Indexed by direction: up, down, left, right.
  .lead_x
    db 8, 8, 1, 14
  .lead_y
    db 9, 22, 16, 16
  .min_distance
    db 20, 32, 20, 20
  ; Portal tile (as RejectOnTileCollision checks it) plus Link's body box.
  .safe_x
    db 0, 1, 8, 14, 1, 8, 14, 1, 8, 14
  .safe_y
    db 0, 9, 9, 9, 16, 16, 16, 22, 22, 22
}

; Tile attribute at (SprX + $06, SprY + $07) on this sprite's floor.
; Returns A = attribute. Preserves X/Y; clobbers $00-$05.
PortalShot_ProbeTile:
{
  PHY
  LDA.w SprY, X : CLC : ADC.b $07 : STA.b $00
  LDA.w SprYH, X : ADC.b #$00 : STA.b $01
  LDA.w SprX, X : CLC : ADC.b $06 : STA.b $02
  LDA.w SprXH, X : ADC.b #$00 : STA.b $03
  LDA.w SprFloor, X : JSL Sprite_GetTileAttr
  PLY
  LDA.w $0FA5
  RTS
}

; Carry set when bolt X and live portal Y pass Portal_CheckWarpContext in both
; directions, with Link standing on the source portal: same 256px pages, and
; target - camera inside [0,$F1) on X and [0,$D1) on Y. The camera for Link at
; p is the native scroll's resting point: E + (p & mask) + off - trigger - 1,
; clamped to the room/area bounds (Underworld_HandleCamera,
; Overworld_OperateCameraScroll). Floor is not checked: the flight cannot
; change it. Entry M=8/X=8; preserves X/Y; clobbers A and $00-$0F.
PortalShot_InPairWindow:
{
  LDA.w SprXH, X : CMP.w SprXH, Y : BNE .other_page
  LDA.w SprYH, X : CMP.w SprYH, Y : BEQ .same_page
  .other_page
    CLC
    RTS
  .same_page
  PHX
  LDA.b $1B : BEQ .overworld
    LDX.b $A6
    REP #$20
    LDA.w $0608, X : STA.b $02
    LDA.w $060C, X : STA.b $04
    SEP #$20
    LDX.b $A7
    REP #$20
    LDA.w $0600, X : STA.b $06
    LDA.w $0604, X : STA.b $08
    LDA.w #$01FF : STA.b $00
    BRA .bounds_set
  .overworld
    REP #$20
    LDA.w $0604 : STA.b $02
    LDA.w $0606 : STA.b $04
    LDA.w $0600 : STA.b $06
    LDA.w $0602 : STA.b $08
    LDA.w #$FFFF : STA.b $00
  .bounds_set
  SEP #$20
  PLX

  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20 : STA.b $0A : SEP #$20
  LDA.w SprXH, Y : XBA : LDA.w SprX, Y
  REP #$20 : STA.b $0C
  LDA.b $0A : JSR .cam_x : STA.b $0E
  LDA.b $0C : SEC : SBC.b $0E : CMP.w #$00F1 : BCS .out16
  LDA.b $0C : JSR .cam_x : STA.b $0E
  LDA.b $0A : SEC : SBC.b $0E : CMP.w #$00F1 : BCS .out16
  SEP #$20

  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20 : STA.b $0A : SEP #$20
  LDA.w SprYH, Y : XBA : LDA.w SprY, Y
  REP #$20 : STA.b $0C
  LDA.b $0A : JSR .cam_y : STA.b $0E
  LDA.b $0C : SEC : SBC.b $0E : CMP.w #$00D1 : BCS .out16
  LDA.b $0C : JSR .cam_y : STA.b $0E
  LDA.b $0A : SEC : SBC.b $0E : CMP.w #$00D1 : BCS .out16
  SEP #$20
  SEC
  RTS
  .out16
  SEP #$20
  .out
  CLC
  RTS

  ; M=16. In: A = portal X. Out: A = $E2 with Link resting there.
  .cam_x
  AND.b $00 : CLC : ADC.w #$0008 : SEC : SBC.w $061C : DEC A : CLC : ADC.b $E2
  CMP.b $02 : BCS .x_above_min
    LDA.b $02
  .x_above_min
  CMP.b $04 : BCC .x_below_max
    LDA.b $04
  .x_below_max
  RTS

  ; M=16. In: A = portal Y. Out: A = $E8 with Link resting there.
  .cam_y
  AND.b $00 : CLC : ADC.w #$000C : SEC : SBC.w $0618 : DEC A : CLC : ADC.b $E8
  CMP.b $06 : BCS .y_above_min
    LDA.b $06
  .y_above_min
  CMP.b $08 : BCC .y_below_max
    LDA.b $08
  .y_below_max
  RTS
}

%log_end("Items/portal_rod.asm", !LOG_ITEMS)
pushpc

; ; Portal Rod logic based on Fire Rod
; Ancilla_PortalShot:
; {
;     LDA $0C54, X : BEQ .traveling_shot
;     JMP Ancilla_ConsumingFire
; .traveling_shot
;     LDA $11 : BNE .just_draw
;     STZ $0385, X
;     JSR Ancilla_MoveHoriz
;     JSR Ancilla_MoveVert
;     JSR Ancilla_CheckSpriteCollision : BCS .collided

;     LDA $0C72, X : ORA.b #$08 : STA $0C72, X
;     JSR Ancilla_CheckTileCollision
;     PHP
;     LDA $03E4, X : STA $0385, X
;     PLP : BCS .collided
;     LDA $0C72, X : ORA.b #$0C : STA $0C72, X
;     LDA $028A, X : STA $74
;     JSR Ancilla_CheckTileCollision
;     PHP
;     LDA $74 : STA $028A, X
;     PLP : BCC .no_collision
; .collided
;     INC $0C54, X
;     ; Check if it's blue or orange portal
;     LDA   $0C68, X
;     CMP.b #$1F
;     BEQ   .blue_portal
;     JMP   .orange_portal
; .blue_portal
;     LDA.b #$20 : STA $0C68, X
;     LDA.b #$08 : STA $0C90, X
;     LDA.b #$2B : JSR Ancilla_DoSfx2 ; Different sound effect for blue portal
;     JMP   .portal_created
; .orange_portal
;     LDA.b #$21 : STA $0C68, X
;     LDA.b #$08 : STA $0C90, X
;     LDA.b #$2C : JSR Ancilla_DoSfx2 ; Different sound effect for orange portal
; .portal_created
;     ; CLC : ADC portal creation logic here if necessary
; .no_collision
;     INC $0C5E, X
;     LDA $0C72, X : AND.b #$F3 : STA $0C72, X
;     LDA $0385, X : STA $0333
;     AND.b #$F0 : CMP.b #$C0 : BNE .just_draw
;     LDA $03E4, X : STA $0333
;     AND.b #$F0 : CMP.b #$C0 : BNE .just_draw
; .just_draw
;     JSR PortalShot_Draw
;     RTS
; }

; ; *$4077C-$407CA LOCAL
; PortalShot_Draw:
; {
;   JSR Ancilla_BoundsCheck
;   LDA $0280, X : BEQ .default_priority
;   LDA.b #$30 : TSB $04
; .default_priority
;   LDA $0C5E, X : AND.b #$0C : STA $02
;   PHX
;   LDX.b #$02
;   LDY.b #$00
; .next_oam_entry
;   STX $03
;   TXA : ORA $02 : TAX
;   LDA $00 : CLC : ADC .x_offsets, X       : STA ($90), Y
;   LDA $01 : CLC : ADC .y_offsets, X : INY : STA ($90), Y
;   LDX $03
;   LDA .chr, X          : INY : STA ($90), Y
;   LDA $04 : ORA.b #$02 : INY : STA ($90), Y
;   PHY
;   TYA : LSR #2 : TAY
;   LDA.b #$00 : STA ($92), Y
;   PLY : INY
;   DEX : BPL .next_oam_entry
;   PLX
;   RTS
; .x_offsets
; db 7, 0, 8, 0, 8, 4, 0, 0
; db 2, 8, 0, 0, 1, 4, 9, 0
; .y_offsets
; db 1, 4, 9, 0, 7, 0, 8, 0
; db 8, 4, 0, 0, 2, 8, 0, 0
; .chr
; db $8D, $9D, $9C
; }
