; ==============================================================================
; Items/deku_stick.asm — Deku Stick consumable handler
; ==============================================================================
; State:
;   DekuStick_State      ($7E046D): 0 = none, 1 = held unlit, 2 = held lit, 3 = swiping
;   DekuStick_BurnTimer  ($7E046E): Active burn countdown ticks (1 tick = 16 frames; 75 = 20s)
;   DekuStick_SwipeTimer ($7E046F): Swipe animation / hit window frames (0 = idle; bit 7 = lit, bit 6 = enemy hit latch)
;   DekuStickWear        ($7EF39F): Stored burn ticks of stowed worn stick (1-74, 0 = none)
; ==============================================================================

Entity_GetTileAttr  = $06E87B
Dungeon_LightTorch  = $01F3EC

; ------------------------------------------------------------------------------
; Tables for Torch Probe Coordinates (indexed by DIR: 0=Up, 2=Down, 4=Left, 6=Right)
; ------------------------------------------------------------------------------
Deku_TorchProbeX:
  dw 8, 8, -4, 20
Deku_TorchProbeY:
  dw -4, 24, 8, 8

; ------------------------------------------------------------------------------
; Tables for Enemy Hit Probe Coordinates (indexed by DIR: 0=Up, 2=Down, 4=Left, 6=Right)
; ------------------------------------------------------------------------------
Deku_HitProbeOffX:
  dw 0, 0, -10, 16
Deku_HitProbeOffY:
  dw -10, 16, 4, 4

; Width / Height indexed by DIR/2 (0=Up, 1=Down, 2=Left, 3=Right)
Deku_HitProbeWidth:
  db 16, 16, 12, 12
Deku_HitProbeHeight:
  db 12, 12, 16, 16

; ------------------------------------------------------------------------------
; Tables for OAM Rendering (indexed by DIR/2: 0=Up, 1=Down, 2=Left, 3=Right)
; ------------------------------------------------------------------------------
; Held Poses:
Deku_HeldStickX:
  db 10, 2, -6, 14
Deku_HeldStickY:
  db -4, 12, 8, 8
Deku_HeldStickTile:
  db $09, $09, $19, $19
Deku_HeldFlameX:
  db 10, 2, -12, 20
Deku_HeldFlameY:
  db -10, 18, 8, 8

; Active Swipe Poses (extended thrust):
Deku_ActiveStickX:
  db 8, 4, -10, 18
Deku_ActiveStickY:
  db -8, 16, 8, 8
Deku_ActiveStickTile:
  db $09, $09, $19, $19
Deku_ActiveFlameX:
  db 8, 4, -16, 24
Deku_ActiveFlameY:
  db -14, 22, 8, 8

; Angled Swipe Poses (startup & recovery):
Deku_AngledStickX:
  db 10, 4, -4, 12
Deku_AngledStickY:
  db -2, 10, 6, 6
Deku_AngledStickAttr:
  db $72, $32, $B2, $32
Deku_AngledFlameX:
  db 10, 4, -10, 18
Deku_AngledFlameY:
  db -8, 16, 6, 6

; ==============================================================================
; DekuStick_CheckYPress: Intercepts Y press while Deku Stick is held
; ==============================================================================
DekuStick_CheckYPress:
{
  PHP
  SEP #$30
  PHA : PHX : PHY

  LDA.l DekuStick_State : BEQ .done

  ; Check if Y was newly pressed ($F4 bit 6)
  LDA.b $F4 : AND.b #$40 : BEQ .done

  ; Suppress assigned Y item from activating
  LDA.b #$40 : TRB.b $F4

  ; Can we start a swipe? Must be in held unlit (1) or held lit (2) state
  LDA.l DekuStick_State
  CMP.b #$01 : BEQ .start_unlit
  CMP.b #$02 : BEQ .start_lit
  BRA .done

.start_lit
  ; 14-frame swipe (4 startup, 4 active, 6 recovery) with bit 7 set (lit)
  LDA.b #$8E : STA.l DekuStick_SwipeTimer
  LDA.b #$03 : STA.l DekuStick_State
  LDA.b #$0A : STA.w $012E ; Swipe SFX
  BRA .done

.start_unlit
  ; 14-frame swipe (unlit)
  LDA.b #$0E : STA.l DekuStick_SwipeTimer
  LDA.b #$03 : STA.l DekuStick_State
  LDA.b #$0A : STA.w $012E ; Swipe SFX

.done
  PLY : PLX : PLA
  PLP
  RTL
}

; ==============================================================================
; DekuStick_Main: Per-frame service from LinkMain_FrameHook
; ==============================================================================
DekuStick_Main:
{
  LDA.l DekuStick_State : BNE +
    RTL
  +

  PHP : SEP #$30

  ; Guard 0: Active gameplay mode (0x07 = Underworld, 0x09 = Overworld)
  LDA.b $10
  CMP.b #$07 : BEQ .check_underworld_submodules
  CMP.b #$09 : BEQ .check_overworld_submodules
  BRA .interrupted

.check_underworld_submodules
  ; Destructive Underworld submodules (inter-room stairs, falling, warps, mirror):
  ; 0x06 (Fat stairs), 0x07 (Fall), 0x0E (Spiral stairs), 0x11..0x13 (Straight stairs),
  ; 0x14 (Fall recovery), 0x15 (Warp pad), 0x19 (Mirror fade)
  LDA.b $11
  CMP.b #$06 : BEQ .interrupted
  CMP.b #$07 : BEQ .interrupted
  CMP.b #$0E : BEQ .interrupted
  CMP.b #$11 : BEQ .interrupted
  CMP.b #$12 : BEQ .interrupted
  CMP.b #$13 : BEQ .interrupted
  CMP.b #$14 : BEQ .interrupted
  CMP.b #$15 : BEQ .interrupted
  CMP.b #$19 : BEQ .interrupted
  BRA .submodule_ok

.check_overworld_submodules
  ; Destructive Overworld submodules (mosaic entrance fades, warps, drowning, whirlpool):
  LDA.b $11
  CMP.b #$0D : BEQ .interrupted
  CMP.b #$17 : BEQ .interrupted
  CMP.b #$23 : BEQ .interrupted
  CMP.b #$24 : BEQ .interrupted
  CMP.b #$2A : BEQ .interrupted
  CMP.b #$2C : BEQ .interrupted
  CMP.b #$2E : BEQ .interrupted

.submodule_ok

  ; Guard 1: LinkState must be default ($5D == 0)
  LDA.l $7E005D : BNE .interrupted

  ; Guard 2: Not carrying an object ($0308 == 0)
  LDA.l $7E0308 : BNE .interrupted

  ; Guard 3: Not dashing ($0372 == 0)
  LDA.l $7E0372 : BNE .interrupted

  ; Guard 4: Not transformed by a mask (0 and 6 are normal Link)
  LDA.l $7E02B2 : BEQ .guards_ok
  CMP.b #$06 : BEQ .guards_ok

.interrupted
  JSL DekuStick_Drop
  PLP : RTL

.guards_ok
  ; During room transitions / submodules / pauses ($11 != 0):
  ; Freeze burn timer and swipe, preserve fire and stick, and draw
  LDA.b $11 : BEQ +
    JSR DekuStick_DrawOAM
    PLP : RTL
  +

  ; If swiping (State == 3): service swipe logic
  LDA.l DekuStick_State : CMP.b #$03 : BNE .check_held_torch

  ; Freeze Link directional movement during swipe (clear d-pad bits from $F0)
  LDA.b #$0F : TRB.b $F0

  ; Check hit window: frames 10 down to 7 (active phase)
  LDA.l DekuStick_SwipeTimer : AND.b #$1F : CMP.b #$07 : BCC .after_hit
  CMP.b #$0B : BCS .after_hit

  ; Within active window (7..10): check hit if not already latched (bit 6)
  LDA.l DekuStick_SwipeTimer : AND.b #$40 : BNE .torch_check
    JSR DekuStick_CheckHit

.torch_check
  JSR DekuStick_CheckTorch

.after_hit
  ; Decrement swipe timer
  LDA.l DekuStick_SwipeTimer : DEC A : STA.l DekuStick_SwipeTimer
  AND.b #$1F : BNE .burn_check

  ; Swipe complete! Revert state to lit (2) or unlit (1) based on bit 7
  LDA.l DekuStick_SwipeTimer : BMI .revert_lit
    LDA.b #$01 : STA.l DekuStick_State
    LDA.b #$00 : STA.l DekuStick_SwipeTimer
    BRA .burn_check

.revert_lit
  LDA.b #$02 : STA.l DekuStick_State
  LDA.b #$00 : STA.l DekuStick_SwipeTimer
  BRA .burn_check

.check_held_torch
  ; Held contact with dungeon torches
  JSR DekuStick_CheckTorch

.burn_check
  ; Active burn countdown:
  ; Lit if State == 2, OR State == 3 with bit 7 set
  LDA.l DekuStick_State
  CMP.b #$02 : BEQ .is_lit
  CMP.b #$03 : BNE .draw_and_exit
  LDA.l DekuStick_SwipeTimer : BPL .draw_and_exit

.is_lit
  ; Tick once every 16 frames ($1A & $0F == 0)
  LDA.l $7E001A : AND.b #$0F : BNE .draw_and_exit

  LDA.l DekuStick_BurnTimer : DEC A : STA.l DekuStick_BurnTimer
  BNE .draw_and_exit

  ; Burn timer reached 0: stick burned out!
  JSL DekuStick_Drop
  LDA.b #$3C : STA.w $012E ; Extinguish sound
  PLP : RTL

.draw_and_exit
  JSR DekuStick_DrawOAM
  PLP : RTL
}

; ==============================================================================
; DekuStick_CheckTorch: Probes tile in front of Link for underworld torches
; ==============================================================================
DekuStick_CheckTorch:
{
  ; Torch interaction only applies indoors in underworld ($1B != 0)
  LDA.b $1B : BNE +
    RTS
  +

  ; Setup probe coordinates using table indexed by DIR ($2F)
  LDX.b $2F
  REP #$20
  LDA.l Deku_TorchProbeX, X : CLC : ADC.b $22 : STA.b $02
  LDA.l Deku_TorchProbeY, X : CLC : ADC.b $20 : STA.b $00
  SEP #$20

  LDA.b $EE ; Current layer
  JSL Entity_GetTileAttr ; $06E87B
  STA.w $0333 ; Set FIRETILE ($0333)

  ; Check if tile is a torch (attribute $C0..$CF)
  AND.b #$F0 : CMP.b #$C0 : BEQ +
    RTS
  +

  ; Valid torch tile! Extract torch index (0..15)
  LDA.w $0333 : AND.b #$0F : TAX

  ; Check if torch is lit ($04F0,X != 0)
  LDA.w $04F0, X : BNE .torch_is_lit

.torch_is_unlit
  ; Torch is unlit: if stick is lit, light the torch!
  LDA.l DekuStick_State
  CMP.b #$02 : BEQ .do_light_torch
  CMP.b #$03 : BNE .done
  LDA.l DekuStick_SwipeTimer : BPL .done ; unlit swipe -> harmless

.do_light_torch
  TXA : ORA.b #$C0 : STA.w $0333
  JSL Dungeon_LightTorch ; $01F3EC
  BRA .done

.torch_is_lit
  ; Torch is lit: if stick is unlit, ignite stick!
  LDA.l DekuStick_State
  CMP.b #$01 : BEQ .do_ignite_stick
  CMP.b #$03 : BNE .done
  LDA.l DekuStick_SwipeTimer : BMI .done ; already lit swipe -> harmless

  ; Swipe was unlit -> ignite it!
  ORA.b #$80 : STA.l DekuStick_SwipeTimer
  LDA.b #$2D : STA.w $012F ; Ignition SFX
  BRA .done

.do_ignite_stick
  JSL DekuStick_Ignite

.done
  SEP #$20
  RTS
}

; ==============================================================================
; DekuStick_CheckHit: Detects enemy stun overlap and wall contact
; ==============================================================================
DekuStick_CheckHit:
{
  ; Setup probe box coordinates using table indexed by DIR ($2F)
  LDA.b $2F : TAX
  REP #$20
  LDA.l Deku_HitProbeOffX, X : CLC : ADC.b $22 : STA.b $00
  LDA.l Deku_HitProbeOffY, X : CLC : ADC.b $20 : STA.b $08
  SEP #$20

  LDA.b $2F : LSR A : TAX
  LDA.l Deku_HitProbeWidth, X : STA.b $02
  LDA.l Deku_HitProbeHeight, X : STA.b $03

  LDX.b #$0F
.loop
  JSR DekuStick_CheckSingleSprite
  BCS .hit
  DEX : BPL .loop

  ; No enemy hit: check for wall contact to play tink SFX
  JSR DekuStick_CheckWallContact
.hit
  RTS
}

DekuStick_CheckSingleSprite:
{
  ; Check if sprite slot is active ($0DD0 == 9)
  LDA.w $0DD0, X : CMP.b #$09 : BEQ +
    CLC : RTS
  +

  ; Layer check (only in underworld; $0F20 must match $EE)
  LDA.b $1B : BEQ +
    LDA.w $0F20, X : CMP.b $EE : BEQ +
      CLC : RTS
  +

  ; Boss / immune check (bit 7 of $0E40)
  LDA.w $0E40, X : BPL +
    CLC : RTS
  +

  ; Already stunned check ($0EA0 != 0)
  LDA.w $0EA0, X : BEQ +
    CLC : RTS
  +

  ; AABB overlap check between Probe Box and Sprite Box
  ; Sprite X: $0D10,X (low) + $0D30,X (high)
  ; Sprite Y: $0D00,X (low) + $0D20,X (high)
  REP #$20
  LDA.w $0D10, X : AND.w #$00FF : STA.b $04
  LDA.w $0D30, X : AND.w #$00FF : XBA : ORA.b $04 : STA.b $04 ; $04 = Sprite X

  ; Check: Sprite X < Probe X + Width ($00 + $02)
  LDA.b $02 : AND.w #$00FF : CLC : ADC.b $00 : CMP.b $04 : BCC .miss : BEQ .miss

  ; Check: Probe X < Sprite X + 16 ($04 + 16)
  LDA.b $04 : CLC : ADC.w #$0010 : CMP.b $00 : BCC .miss : BEQ .miss

  ; Vertical: Sprite Y < Probe Y + Height && Probe Y < Sprite Y + 16
  LDA.w $0D00, X : AND.w #$00FF : STA.b $06
  LDA.w $0D20, X : AND.w #$00FF : XBA : ORA.b $06 : STA.b $06 ; $06 = Sprite Y

  ; Check: Sprite Y < Probe Y + Height ($08 + $03)
  LDA.b $03 : AND.w #$00FF : CLC : ADC.b $08 : CMP.b $06 : BCC .miss : BEQ .miss

  ; Check: Probe Y < Sprite Y + 16 ($06 + 16)
  LDA.b $06 : CLC : ADC.w #$0010 : CMP.b $08 : BCC .miss : BEQ .miss

  ; Enemy hit! Apply brief nonlethal stun without HP damage or stick breakage
  SEP #$20
  LDA.b #$20 : STA.w $0EA0, X ; Stun timer = 32 frames
  LDA.b #$20 : STA.w $012E ; Stun hit SFX

  ; Latch enemy hit bit 6 in swipe timer so max 1 enemy is hit per swipe
  LDA.l DekuStick_SwipeTimer : ORA.b #$40 : STA.l DekuStick_SwipeTimer
  SEC
  RTS

.miss
  SEP #$20
  CLC
  RTS
}

DekuStick_CheckWallContact:
{
  REP #$20
  LDA.b $00 : STA.b $02
  LDA.b $08 : STA.b $00
  SEP #$20
  LDA.b $EE
  JSL Entity_GetTileAttr ; $06E87B
  CMP.b #$00 : BEQ .no_wall
  CMP.b #$C0 : BCS .no_wall ; torches are handled separately
  ; Wall contact: play tink SFX
  LDA.b #$09 : STA.w $012E
  ; Latch bit 6 so tink plays once per swipe
  LDA.l DekuStick_SwipeTimer : ORA.b #$40 : STA.l DekuStick_SwipeTimer
.no_wall
  RTS
}

; ==============================================================================
; DekuStick_DrawOAM: Renders Stick and Flame into OAM Sprite 4 and 5
; ==============================================================================
DekuStick_DrawOAM:
{
  ; Calculate screen coordinates:
  ; Screen X ($04) = POSX ($22) - BG2H ($E2)
  ; Screen Y ($06) = POSY ($20) - BG2V ($E8)
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $04
  LDA.b $20 : SEC : SBC.b $E8 : STA.b $06
  SEP #$20

  ; Screen bounds check: off-screen if high byte is not 0 and not $FF
  LDA.b $05 : BEQ +
  CMP.b #$FF : BEQ +
  .hide
    LDA.b #$E0 : STA.w $0811 : STA.w $0815
    RTS
+ LDA.b $07 : BEQ +
  CMP.b #$FF : BNE .hide
+

  ; Direction index for table lookups (DIR/2: 0..3)
  LDA.b $2F : LSR A : TAX

  ; Default attribute: Priority 3, Palette 1
  LDA.b #$32 : STA.b $09

  ; Check if currently swiping
  LDA.l DekuStick_State : CMP.b #$03 : BNE .held_pose

  ; Swipe pose: check active window (frames 10..7)
  LDA.l DekuStick_SwipeTimer : AND.b #$1F : CMP.b #$07 : BCC .angled_pose
  CMP.b #$0B : BCS .angled_pose

  ; Active forward thrust pose:
  LDA.l Deku_ActiveStickX, X : STA.b $00
  LDA.l Deku_ActiveStickY, X : STA.b $01
  LDA.l Deku_ActiveStickTile, X : STA.b $08
  LDA.l Deku_ActiveFlameX, X : STA.b $02
  LDA.l Deku_ActiveFlameY, X : STA.b $03
  BRA .write_sprites

.angled_pose
  ; Angled startup/recovery pose (diagonal tile $1A):
  LDA.l Deku_AngledStickX, X : STA.b $00
  LDA.l Deku_AngledStickY, X : STA.b $01
  LDA.b #$1A : STA.b $08
  LDA.l Deku_AngledStickAttr, X : STA.b $09
  LDA.l Deku_AngledFlameX, X : STA.b $02
  LDA.l Deku_AngledFlameY, X : STA.b $03
  BRA .write_sprites

.held_pose
  ; Normal held pose:
  LDA.l Deku_HeldStickX, X : STA.b $00
  LDA.l Deku_HeldStickY, X : STA.b $01
  LDA.l Deku_HeldStickTile, X : STA.b $08
  LDA.l Deku_HeldFlameX, X : STA.b $02
  LDA.l Deku_HeldFlameY, X : STA.b $03

.write_sprites
  ; Write Sprite 4 (Deku Stick):
  LDA.b $04 : CLC : ADC.b $00 : STA.w $0810 ; Stick X
  LDA.b $06 : CLC : ADC.b $01 : STA.w $0811 ; Stick Y
  LDA.b $08 : STA.w $0812 ; Stick Tile
  LDA.b $09 : STA.w $0813 ; Stick Attr

  ; Write Sprite 5 (Flame, if lit):
  ; Lit if State == 2 OR (State == 3 AND bit 7 set)
  LDA.l DekuStick_State
  CMP.b #$02 : BEQ .draw_flame
  CMP.b #$03 : BNE .hide_flame
  LDA.l DekuStick_SwipeTimer : BPL .hide_flame

.draw_flame
  LDA.b $04 : CLC : ADC.b $02 : STA.w $0814 ; Flame X
  LDA.b $06 : CLC : ADC.b $03 : STA.w $0815 ; Flame Y
  LDA.b #$9C : STA.w $0816 ; Flame Tile $9C
  ; Flame attribute: Palette 4, priority 3 ($38), flicker H-flip with frame counter bit 2
  LDA.b $1A : AND.b #$04 : BEQ +
    LDA.b #$78 : BRA ++
  + LDA.b #$38
  ++ STA.w $0817
  BRA .set_high_table

.hide_flame
  LDA.b #$E0 : STA.w $0815

.set_high_table
  ; Clear high table bits 0-3 in $0A21 (small 8x8 size for both sprites)
  LDA.w $0A21 : AND.b #$F0 : STA.w $0A21
  RTS
}

; ==============================================================================
; DekuStick_Stow: Stows intact stick, extinguishes fire, refunds 1 stick, saves wear
; ==============================================================================
DekuStick_Stow:
{
  ; Refund exactly one intact stick to inventory
  LDA.l DekuSticks : INC A : STA.l DekuSticks

  ; Determine retained wear:
  ; If BurnTimer == 75 ($4B), stick was unlit/fresh -> store 0 (no worn stick).
  ; If BurnTimer is between 1 and 74, stick is worn -> retain BurnTimer in SRAM.
  LDA.l DekuStick_BurnTimer
  CMP.b #$4B : BEQ .unlit
  CMP.b #$00 : BEQ .unlit
  CMP.b #$4C : BCS .unlit ; Out-of-range safety guard -> do not store invalid wear
    STA.l DekuStickWear
    BRA .clear_active

.unlit
  LDA.b #$00 : STA.l DekuStickWear

.clear_active
  LDA.b #$00
  STA.l DekuStick_State
  STA.l DekuStick_BurnTimer
  STA.l DekuStick_SwipeTimer

  ; Move OAM sprites off-screen
  LDA.b #$E0
  STA.w $0811
  STA.w $0815

  ; Play equip / stow sound
  LDA.b #$20 : STA.w $012F
  RTL
}

; ==============================================================================
; DekuStick_Drop: Clears active stick without refund or wear restoration
; ==============================================================================
DekuStick_Drop:
{
  ; Clear active state without refunding inventory (spent on draw)
  ; DekuStickWear was already zeroed on draw, so no wear is restored
  LDA.b #$00
  STA.l DekuStick_State
  STA.l DekuStick_BurnTimer
  STA.l DekuStick_SwipeTimer

  ; Move OAM sprites off-screen
  LDA.b #$E0
  STA.w $0811
  STA.w $0815
  RTL
}

; ==============================================================================
; DekuStick_Ignite: Sets stick lit (State = 2) and preserves remaining wear budget
; ==============================================================================
DekuStick_Ignite:
{
  ; Only an unlit stick (state 1) can ignite
  LDA.l DekuStick_State : CMP.b #$01 : BNE .exit
    LDA.b #$02 : STA.l DekuStick_State
    ; Preserves active BurnTimer! (Relighting preserves remaining wear budget)
    ; Play flame ignition sound
    LDA.b #$2D : STA.w $012F
  .exit
  RTL
}

; ==============================================================================
; DekuStick_SubmoduleCheck: Per-frame transition drop check in Module07 / Module09
; ==============================================================================
DekuStick_SubmoduleCheck:
{
  PHP : SEP #$30
  PHA : PHX : PHY : PHB
  PHK : PLB

  LDA.l DekuStick_State : BEQ .done

  ; Check active mode: 0x07 = Underworld, 0x09 = Overworld
  LDA.b $10
  CMP.b #$07 : BEQ .check_uw
  CMP.b #$09 : BEQ .check_ow
  BRA .drop

.check_uw
  ; Destructive Underworld submodules (inter-room stairs, falling, warps, mirror):
  ; 0x06 (Fat stairs), 0x07 (Fall), 0x0E (Spiral stairs), 0x11..0x13 (Straight stairs),
  ; 0x14 (Fall recovery), 0x15 (Warp pad), 0x19 (Mirror fade)
  LDA.b $11
  CMP.b #$06 : BEQ .drop
  CMP.b #$07 : BEQ .drop
  CMP.b #$0E : BEQ .drop
  CMP.b #$11 : BEQ .drop
  CMP.b #$12 : BEQ .drop
  CMP.b #$13 : BEQ .drop
  CMP.b #$14 : BEQ .drop
  CMP.b #$15 : BEQ .drop
  CMP.b #$19 : BEQ .drop
  BRA .done

.check_ow
  ; Destructive Overworld submodules (mosaic entrance fades, warps, drowning, whirlpool):
  ; 0x0D, 0x17, 0x23, 0x24, 0x2A, 0x2C, 0x2E
  LDA.b $11
  CMP.b #$0D : BEQ .drop
  CMP.b #$17 : BEQ .drop
  CMP.b #$23 : BEQ .drop
  CMP.b #$24 : BEQ .drop
  CMP.b #$2A : BEQ .drop
  CMP.b #$2C : BEQ .drop
  CMP.b #$2E : BEQ .drop
  BRA .done

.drop
  JSL DekuStick_Drop

.done
  PLB : PLY : PLX : PLA
  PLP
  ; Replay displaced instructions: LDA $11 : ASL A : TAX
  LDA.b $11
  ASL A
  TAX
  RTL
}

pushpc
; Module07_Underworld ($0287A8-$0287AB): replaces LDA $11 : ASL A : TAX (replayed by helper)
org $0287A8 ; @hook module=Items name=DekuStick_UWSubmoduleHook kind=jsl target=DekuStick_SubmoduleCheck expected_m=8 expected_x=8
  JSL DekuStick_SubmoduleCheck
assert pc() == $0287AC

; Module09_Overworld ($0283BF-$0283C2): replaces LDA $11 : ASL A : TAX (replayed by helper)
org $0283BF ; @hook module=Items name=DekuStick_OWSubmoduleHook kind=jsl target=DekuStick_SubmoduleCheck expected_m=8 expected_x=8
  JSL DekuStick_SubmoduleCheck
assert pc() == $0283C3
pullpc

