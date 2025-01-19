; =========================================================
; Goldstar ASM disassembly/restoration
; Originally from the all in patch by Conn
; Restored by scawful with help from Zarby
;
; $22XXXX - Denotes the source address from all in patch
; =========================================================

pullpc
TransferGFXinRAM:
{
  PHX
  PHP
  REP #$20

  LDX #$80
  --
    LDA.l .morningstargfx, X : STA.l $7EA180, X
    DEX : DEX : BPL --

  PLP
  PLX
  RTL

  .morningstargfx
    incbin morningstar.bin
}

pushpc
; OAM Draw Pattern for spikeball gfx
org $0085C4 : dw $0040

; =========================================================
; Zarby Code
; Handles the layout of OAM tile patterns for the hookshot

org $0DABA2 ; LinkOAM_SetWeaponVRAMOffsets
  JSL HookMaskCheck
  BRA LinkOAM_SetWeaponVRAMOffsets_not_rod_hook

org $0DABB0
  LinkOAM_SetWeaponVRAMOffsets_not_rod_hook:

; dw $A180, $A1A0, $A1C0, $A1E0
org $008542
  dw $A180, $A1A0, $A180, $A1A0
  dw $A1C0, $A1C0, $A1E0, $A1E0
pullpc

HookMaskCheck:
{
  LDA.w GoldstarOrHookshot : AND.w #$00FF :  CMP.w #$0002 : BNE .not_mask
    LDA $0202 : AND.w #$00FF : CMP.w #$0003 : BNE .not_mask
      ; morning star graphics oam tile pattern id
      LDA.w $0109 : AND #$FF00 : ORA.w #$004A
      RTL
  .not_mask
  ; return hookshot graphics oam tile pattern id
  TYA : AND.w #$00FF : STA.b $0A
  LDA.w $0109 : AND.w #$FF00 : ORA.b $0A
  RTL
}

; =========================================================
; $22D4A0 - Hooked into LinkItem_Hookshot @ _07AB5A
; Call this routine to start the gfx transfer of the handle
; based on the direction you are facing.

CheckForBallChain:
{
  LDA #$13 : STA $5D ; Set hookshot state
  LDA #$FF : STA $7A ; Start the rotation Timer
  JMP LinkItem_BallChain_GfxTransfer ; $D520
  RTL
}

; =========================================================

pushpc
org $08BF2D
  JSL BallChain_DrawOrReturn
  assert pc() <= $08BF32
pullpc

; $22D4C0 - Hooked into AncillaDraw_Hookshot @ _08BF2D
BallChain_DrawOrReturn:
{
  LDA.w GoldstarOrHookshot : CMP #$02 : BEQ +
    LDA #$00 : STA ($92),Y
    RTL
  + ; $22D4CD
  LDA #$02 : STA ($92),Y
  RTL
}

; =========================================================

pushpc
org $08BF0C
  JML BallChain_ExtraCollisionLogic
pullpc

; $22D4E0 - Hooked into Hookshot_ExtraCollisionLogic @ 08BF0C
BallChain_ExtraCollisionLogic:
{
  TAX
  LDA.w GoldstarOrHookshot : CMP #$02 : BNE + ; Check if using goldstar
    TXA : CMP #$0A : BNE ++
      LDA #$FF : BRA ++
  +  ; $22D4F2
  TXA
  ++ ; $22D4F3
  CMP #$FF : BEQ +++
    ; AncillaDraw_Hookshot - JSR Ancilla_SetOAM_XY, skips hookshot char
    JML $08BF10

  +++ ; $22D4FB
  JML $08BF32 ; AncillaDraw_Hookshot_skip
}

; =========================================================
;; 22D520
LinkItem_BallChain_GfxTransfer:
{
    PHB
    ; Check link direction
    LDA $2F : CMP #$04 : BEQ .transfer_gfx_sideways
              CMP #$06 : BEQ .transfer_gfx_sideways
      REP #$30
      LDA #$0040 : LDX #GFX_D600 : LDY #$9AC0
      MVN $2B, $7E
      LDA #$0040 : LDX #GFX_D640 : LDY #$9B40
      MVN $2B, $7E
      PLB :        LDA #GFX_D6A0 : STA $4302
      JMP .transfer_handle_and_links ; D574

  .transfer_gfx_sideways ; $22D553
    REP #$30
    LDA #$0040 : LDX #GFX_D600 : LDY #$9B00
    MVN $2B, $7E
    LDA #$0040 : LDX #GFX_D640 : LDY #$9B80
    MVN $2B, $7E
    PLB :        LDA #GFX_D6C0 : STA $4302

  .transfer_handle_and_links ; $22D574
    LDA #$41E0 : STA $2116
    LDA #$1801 : STA $4300
    SEP #$30

    LDA #$80 : STA $2115
    .transfer_loop
      LDA $4212 : AND #$80
      BEQ .transfer_loop
    LDA #$2B : STA $4304
    LDA #$20 : STA $4305
    LDA #$01 : STA $420B

    REP #$30
    LDA #$40E0 : STA $2116
    LDA #GFX_D680 : STA $4302
    SEP #$30

    LDA #$20 : STA $4305
    LDA #$2B : STA $4304
    LDA #$01 : STA $420B
    RTL
}

; 22D5C0 ; Unreached
; LDA $8580,Y
; CMP #$02
; BEQ $22D5CA
; JMP $DA80

; Graphics data for transferring the handle oam slot
GoldstarHandleGfx:
{
  ; 22D600
  GFX_D600:
    db $00, $00, $00, $00, $21, $00, $7B, $00
    db $37, $0B, $3F, $14, $1D, $0A, $1F, $0B
    db $00, $00, $00, $00, $21, $00, $5B, $00
    db $2F, $0B, $3F, $14, $1E, $0A, $1F, $0B
  GFX_D620:
    db $00, $00, $80, $00, $40, $80, $F8, $00
    db $EC, $D0, $BC, $E8, $FC, $50, $D8, $60
    db $00, $00, $80, $00, $C0, $80, $F8, $00
    db $F4, $D0, $FC, $E8, $DC, $50, $F8, $60
  ; 22D640
  GFX_D640:
    db $1F, $04, $1F, $07, $2F, $19, $2F, $18
    db $7B, $01, $21, $00, $00, $00, $00, $00
    db $1F, $04, $1F, $07, $3F, $19, $3F, $18
    db $5B, $01, $21, $00, $00, $00, $00, $00
  ; 22D660
  GFX_D660:
    db $AC, $D0, $72, $DC, $FC, $C0, $F8, $10
    db $E8, $30, $34, $08, $08, $00, $00, $00
    db $FC, $D0, $FE, $DC, $FC, $C0, $F8, $10
    db $F8, $30, $3C, $08, $08, $00, $00, $00
  ; 22D680
  GFX_D680:
    db $00, $00, $18, $00, $24, $18, $5A, $24
    db $7E, $24, $3C, $18, $18, $00, $00, $00
    db $00, $00, $18, $00, $3C, $18, $7E, $24
    db $7E, $24, $3C, $18, $18, $00, $00, $00
  ; 22D6A0
  GFX_D6A0:
    db $18, $00, $3C, $18, $2C, $08, $34, $10
    db $34, $10, $34, $00, $24, $00, $18, $00
    db $18, $18, $24, $3C, $34, $3C, $2C, $18
    db $2C, $18, $2C, $08, $3C, $18, $18, $00
  ; 22D6C0
  GFX_D6C0:
    db $00, $00, $00, $00, $7E, $00, $BB, $1A
    db $87, $06, $7E, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $7E, $00, $C5, $5E
    db $F9, $7E, $7E, $00, $00, $00, $00, $00
}

; =========================================================

pushpc
org $07ABAF
  JSL BallChain_ResetTimer
pullpc

; 7F5F02

; 22D700
; Hooked into LinkState_Hookshotting @ _07ABAF
; Sets Link state to 0x00 and resets the hookshot timer
BallChain_ResetTimer:
{
  LDA.w GoldstarOrHookshot : CMP #$02 : BNE .dont_clear_timer
    STZ $7A ; Clear the timer
  .dont_clear_timer
  STZ $5D ; Return to LinkState_Default
  RTL
}

; =========================================================

pushpc
org $08BFDA
  JSL BallChain_DrawChainOrHookshot
  NOP #8
  NOP #5
pullpc

; 22D800
; Hooked into AncillaDraw_HookshotChain @ 08BFDA
; Natively NOPs out the bytes 08BFDA - 08BFEA
BallChain_DrawChainOrHookshot:
{
  LDA.w GoldstarOrHookshot : CMP #$02 : BEQ +
    LDA #$19 : STA ($90),Y
    JSR BallChainOrHookshot_Modifier ; $D820
    ORA.b #$02
    RTL
  + ; 22D812
  LDA #$0E : STA ($90),Y
  JSR BallChainOrHookshot_Modifier ; $D820
  ORA.b #$04 ; 02 is gray color
  RTL
}

; 22D820
BallChainOrHookshot_Modifier:
{
  INY : LDA.b $1A : AND.b #$02
  ASL #6 ; six times
  RTS
}

; =========================================================

struct HookshotSpriteData $08BD4C
  .char: skip 12
  .prop: skip 12
  .box_size_y: skip 8
  .box_size_x: skip 8
endstruct

pushpc
org $08BF1B ; AncillaDraw_HookshotChain
  JSL Goldstar_SetChainProperties
  NOP #3
pullpc

; $22D850 - Modify the palette
Goldstar_SetChainProperties:
{
  LDA.w GoldstarOrHookshot : CMP #$02 : BEQ .ball_chain
    LDA HookshotSpriteData.prop, X
    ORA.b #$02 : ORA.b $65
    RTL
  .ball_chain ; 22D860
  LDA HookshotSpriteData.prop, X
  ORA.b #$02
  ORA.b $65
  RTL
}

; =========================================================

pushpc
org $0DA6E3
  JSL LinkOAM_GoldstarWeaponTiles
  NOP
pullpc

LinkOAM_WeaponTiles = $0D839B

; 22D880
LinkOAM_GoldstarWeaponTiles:
{
  REP #$20
  LDA.w $0202 : AND.w #$00FF : CMP.w #$0003 : BEQ +
    LDA.w LinkOAM_WeaponTiles, Y
    RTL
  + ; $22D892
  LDA.w LinkOAM_WeaponTiles, Y : CMP.w #$221A : BEQ ++
    RTL
  ++ ; $22D89B
  LDA.w GoldstarOrHookshot : AND.w #$00FF : CMP.w #$0002 : BEQ +++
    LDA.w LinkOAM_WeaponTiles, Y
    RTL
  +++ ; $22D8AA
  LDA.w #$241E
  RTL
}

; =========================================================

pushpc
org $08BFB0
  JML HookshotChain_AncillaDraw

org $08BD64
  Hookshot_box_size_y:
pullpc

; 22D900 - AncillaDraw_HookshotChain_next_object @ 08BFB0
HookshotChain_AncillaDraw:
{
  REP #$20
  ; Ball Chain Timer
  LDA $7A  : AND #$00FF : CMP #$0001 : BNE + ; $22D914
    LDA Hookshot_box_size_y, X
    JML $08BFB5 ; AncillaDraw_HookshotChain
  + ; $22D914
  CMP #$0000 : BNE ++ ; $22D921
    LDA Hookshot_box_size_y, X
    JML $08BFB5 ; AncillaDraw_HookshotChain
  ++
  JSR CheckForSomariaBlock ; CheckAndClearAncillaId has set the timer in A

  SEP #$30
  ; Compare rotation progress
  CLC : CMP #$FB : BNE +++
    LDA #$06 : STA $2143

  +++ ; 22D930
  BCC ++++
    JMP StartChainRotation ; $D960

  ++++ ; 22D935
  ; Compare rotation progress
  CLC : CMP #$AB : BNE +++++
    LDA #$06 : STA $2143

  +++++ ;22D93F
  ; Compare rotation progress
  CLC : CMP #$5B : BNE ++++++
    LDA #$06 : STA $2143

  ++++++ ;22D949
  CLC : CMP #$E6 : BCC +++++++
    JMP Routine_22D9A0 ; $D9A0

  +++++++ ; 22D951
  CLC : CMP #$05 : BCC ++++++++
  LDA $F8 : CMP.b #$40 : BEQ +
    JMP Routine_22D9A0 ; $D9A0

  ++++++++ ; 22D959
  JMP Routine_22DBD0 ; $DBD0
}

; =========================================================

!RotationState = $7F5803

; 22D960
StartChainRotation:
{
  REP #$20
  LDA #$0000 : EOR #$FFFF : INC : CLC
  JSR Goldstar_GetPlayerPosY : STA $7F5810 ; en center y-pos
  JSR Goldstar_GetPlayerPosX : STA $7F580E ; en center x-pos
  SEP #$30
  JSR Routine_22DAD0 : STA $7F5803 ; Set rotation state
  DEC $7A ; Ball Chain Timer
  SEP #$20
  JML $08BFD0 ; AncillaDraw_HookshotChain before Hookshot_CheckProximityToLink
}

; =========================================================

struct Ancilla_GetRadialProjection $0FFBC2
  .multiplier_x : skip 64
  .multiplier_y : skip 64
  .meta_sign_y  : skip 64
  .meta_sign_x  : skip 64
endstruct

; $22D9A0
Routine_22D9A0:
{
  LDA $7F5803 : CLC : ADC #$02 : AND #$3F : CPY #$04 : BNE +
    STA $7F5803 : CLC : ADC #$02
  + ; 22D9B6
  AND #$3F : PHX : TAX

  LDA Ancilla_GetRadialProjection.multiplier_y, X
  STA $4202 : JSR Routine_22DAA0 : STA $4203

  ; Sign of the projected distance.
  LDA Ancilla_GetRadialProjection.meta_sign_y, X
  STA $02 : STZ $03

  ; Get Y of projected distance
  LDA $4216 : ASL
  LDA $4217 : ADC #$00 : STA $00 : STZ $01

  LDA Ancilla_GetRadialProjection.multiplier_x, X
  STA $4202 : JSR Routine_22DAA0 : STA $4203

  ; Sign of the projected distance.
  LDA Ancilla_GetRadialProjection.meta_sign_x, X
  STA $06 : STZ $07

  ; Get X of projected distance
  LDA $4216 : ASL
  LDA $4217 : ADC #$00 : STA $04 : STZ $05

  PHY
  JSL $08DA17 ; Sparkle_PrepOAMFromRadial
  PLY : PLX
  CPY #$04 : BNE ++ ; $22DA14
    JSR Routine_22DA70 ; $DA70
    NOP #7
    JSR BallChain_SpinAncilla ; $22DB90

  ++ ;22DA14
  NOP #3
  LDA #$F0 : CPY #$1C : BNE +++ ; $22DA1F
    STA $00
  +++ ; 22DA1F
  DEC $7A ; Ball Chain Timer
  SEP #$20
  JML $08BFD0 ; AncillaDraw_HookshotChain before Hookshot_CheckProximityToLink
}

; =========================================================
; 22DA30

Goldstar_GetPlayerPosY:
{
  ADC $20 : CLC : ADC #$000C
  CPX #$00 : BNE +
    SEC : SBC #$000C
    RTS
  + ; $22DA3F
  CPX #$02 : BNE ++
    CLC : ADC #$000C
  ++ ; $22DA47
  RTS
}

; =========================================================
; 22DA50

Goldstar_GetPlayerPosX:
{
  LDA $22 : CLC : ADC #$0008
  CPX #$04 : BNE + ; $22DA5F
    SEC : SBC #$000C
    RTS
  + ; $22DA5F
  CPX #$06 : BNE ++ ; $22DA67
    CLC : ADC #$000C
  ++ ;$22DA67
  RTS
}

; =========================================================
; 22DA70

Routine_22DA70:
{
  LDY #$00 : LDA $02 ; set sign of projected distance X
  STA ($90),Y

  LDY #$01 : LDA $00 ; set sign of projected distance y
  STA ($90),Y

  LDY #$04
  RTS
}

; =========================================================
; 22DA80 Possibly unused

Routine_22DA80:
{
  LDA $7EF34A : CMP #$02 : BNE + ; $22DA89
    RTL
  +
  CMP #$01 : BEQ ++ ; $22DA93
    LDA $8580,Y : STA [$00]
    RTL
  ++
  LDA #$8F01 : TSC : SBC ($7E,S),Y
  RTL
}

; =========================================================
; 22DAA0

Routine_22DAA0:
{
  CPY #$04 : BNE .alpha
    JMP Routine_22DB50 ; $DB50
  .alpha ; 22DAA7
  CPY #$08 : BNE +
    LDA #$00
    RTS
  + ; 22DAAE
  CPY #$0C : BNE ++
    LDA #$04
    RTS
  ++ ; 22DAB5
  CPY #$10 : BNE +++
    LDA #$08
    RTS
  +++ ; 22DABC
  CPY #$14 : BNE ++++
    LDA #$0C
    RTS
  ++++ ; 22DAC3
  CPY #$18 : BNE +++++ ; $22DACA
    LDA #$10
    RTS
  +++++ ; 22DACA
  LDA #$02
  RTS
}

; =========================================================
; 22DAD0

Routine_22DAD0:
{
  CPX #$00 : BNE + ; $22DAD7
    LDA #$2E
    RTS
  + ; 22DAD7
  CPX #$02 : BNE ++ ; $22DADE
    LDA #$13
    RTS
  ++ ; 22DADE
  CPX #$04 : BNE +++ ; $22DAE5
    LDA #$2B
    RTS
  +++ ; 22DAE5
  LDA #$09
  RTS
}

; =========================================================

pushpc
org $08BF94
  JML BallChain_TryAncillaDraw
  NOP
pullpc

; 22DB00
; Hooks into AncillaDraw_HookshotChain @ 08BF94
; Hookshot box size
BallChain_TryAncillaDraw:
{
  ; Ball Chain timer should be $FF here on first run
  LDA $7A : AND #$00FF : CMP #$0000 : BEQ +
    CMP #$0001 : BEQ +
      SEP #$20
      JML HookshotChain_AncillaDraw ; $22D900

  + ; $22DB15
  LDA Hookshot_box_size_y,X : BNE ++
    JML $08BF99 ; AncillaDraw_HookshotChain

  ++ ; $22DB1F
  JML $08BFA1 ; Resume AncillaDraw_HookshotChain
}

; =========================================================

pushpc
org $08F7DC
  JML BallChain_CheckProximityToLink
pullpc

; 22DB30
; Hooks into Hookshot_CheckProximityToLink @ 08F7DC
BallChain_CheckProximityToLink:
{
  REP #$20
  ; Ball Chain Timer
  LDA $7A  : AND #$00FF : CMP #$0000 : BNE + ; $22DB44
    LDA.b $00
    JML $08F7E0 ; Hookshot_CheckProximityToLink continue
  + ; 22DB44
  JML $08F820 ; Hookshot_CheckProximityToLink too_far
}

; =========================================================
; 22DB50

Routine_22DB50:
{
  ; Ball Chain Timer
  LDA $7A : CLC : CMP #$EA : BCC +
    LDA #$08
    RTS
  + ; 22DB5A
  CLC : CMP #$16 : BCC ++
    LDA #$14
    RTS
  ++ ; 22DB62
  CLC
  LDA #$08
  RTS
}

; =========================================================
; $22DB90

BallChain_SpinAncilla:
{
  REP #$20
  LDA $00 : CLC : ADC $E8 : CPX #$02 : BNE .alpha
    CLC : ADC #$0010
  .alpha
  STA $04
  LDA $02 : CLC : ADC $E2 : STA $06
  SEP #$20
  LDA $04 : STA $0BFE : LDA $05 : STA $0C12 ; Ancilla4 Y
  LDA $06 : STA $0C08 : LDA $07 : STA $0C1C ; Ancilla4 X
  STZ $0C76 ; Ancilla4 direction
  SEP #$30
  RTS
}

; =========================================================

struct AncillaAdd_HookshotData $099AF8
  .speed_y: skip 4
  .speed_x: skip 4
  .offset_y: skip 8
  .offset_x: skip 8
endstruct

; 22DBD0
Routine_22DBD0:
{
  STZ $7A ; Ball Chain Timer
  JSR ClearAncillaVariables ; $DC70
  ; Check Link direction
  LDA $2F  : CMP #$00 : BNE .not_up
    LDA #$C0 : STA $0C26 ; Ancilla4 Y Axis Velocity
  .not_up
  CMP #$02 : BNE .not_down
    LDA #$40 : STA $0C26 ; Ancilla4 Y Axis Velocity
  .not_down
  CMP #$04 : BNE .not_left
    LDA #$C0 : STA $0C30 ; Ancilla4 X Axis Velocity
  .not_left
  CMP #$06 : BNE .not_right
    LDA #$40 : STA $0C30 ; Ancilla4 X Axis Velocity
  .not_right
  SEP #$20
  STZ $0C58 ; Ancilla4 Misc
  STZ $0C62 ; Ancilla4 hookshoot extension
  STZ $0C54 ; Ancilla0 Misc
  REP #$20

  LDA $2F : LSR : STA $0C76
  ASL : TAX

  LDA $20 : CLC : ADC AncillaAdd_HookshotData.offset_y, X
  STA $00 : STA $04

  LDA $22 : CLC : ADC AncillaAdd_HookshotData.offset_x, X
  STA $02 : STA $06

  SEP #$30
  LDA $00 : STA $0BFE : LDA $01 : STA $0C12 ; Ancilla4 Y
  LDA $02 : STA $0C08 : LDA $03 : STA $0C1C ; Ancilla4 X
  LDX #$06 : LDA Hookshot_box_size_y,X ; hookshot box size y table
  SEP #$20
  JML $08BFD0 ; AncillaDraw_HookshotChain before Hookshot_CheckProximityToLink
}

; =========================================================

pushpc
org $08BDFD
  JML HookshotOrBallChain_Extending_ignore_collision
pullpc

; 22DC50
HookshotOrBallChain_Extending_ignore_collision:
{
  ; Ball Chain Timer
  LDA $7A  : CMP #$00 : BNE +
    JSL Hookshot_CheckTileCollision ; $07D576
    JML $08BE01 ; Hookshot_Extending_ignore_collision continue
  + ; 22DC5E
  JML $08BEDC ; AncillaDraw_Hookshot
}

; =========================================================
; 22DC70

ClearAncillaVariables:
{
  REP #$30
  LDA #$0000
  STA $7F580E ; en center x-pos
  STA $7F5810 ; en center y-pos
  STA $7F5803 ; rotation state
  SEP #$30
  RTS
}

; =========================================================

pushpc
org $08BD7F
  JSL BallChain_SFX_Control
  NOP #1
pullpc

;; 22DC90
; Hooked into Ancilla1F_Hookshot @ 08BD7F before Ancilla_SFX2_Pan
BallChain_SFX_Control:
{
  STA $0C68,X
  ; Ball Chain Timer
  LDA $7A : CMP #$00 : BNE + ; $22DC9C
    LDA.b #$0A ; SFX2.0A
    RTL
  + ;; 22DC9C
  LDA.b #$07 ; Clear SFX2
  RTL
}

; =========================================================
; 22DCA0
; SFX Pan flags?

Routine_22DCA0:
{
  LDA $7A : CMP #$00 : BNE + ;$A2DCAB
    LDA $0DBB5B, X
    RTL
  +
  LDA #$00
  RTL
}

; =========================================================
; 22DD90

CheckAndClearAncillaId:
{
  SEP #$30
  ; Check if hookshot ancillae in this slot
  LDA $0C4A : CMP #$1F : BEQ + ; $22DDC9
    LDA $0C4C : CMP #$1F : BEQ ++ ; $22DDB1
      LDA $0C4D : CMP #$1F : BEQ +++ ; $22DDB9
        LDA $0C4B : CMP #$1F : BEQ ++++ ; $22DDC1
          LDA $7A ; Ball Chain Timer
          RTS
    ++ ; 22DDB1
      STZ $0C4C : LDA $7A
      RTS
      +++ ; 22DDB9
        STZ $0C4D : LDA $7A
        RTS
        ++++ ; 22DDC1
          STZ $0C4B : LDA $7A
          RTS
  + ; 22DDC9
  STZ $0C4A : LDA $7A
  RTS
}

; =========================================================
; 22E5A0
; Checks for the Somaria block before moving on
; TODO: Replace the JMP $E5DB with the proper code
; to handle the somaria block case.

CheckForSomariaBlock:
{
    SEP #$30
    JMP CheckForSomariaBlast ; $EE80
  .22E5A5 ; 22E5A5
    LDA $0C4C : CMP #$2C : BNE + ; $22E5B2
      INC $0C4C
      ;JMP $E5DB

  + ; 22E5B2
    LDA $0C4D : CMP #$2C : BNE ++ ; $22E5BF
      INC $0C4D
      ;JMP $E5DB

  ++ ; 22E5BF
    LDA $0C4E : CMP #$2C : BNE +++ ; $22E5CC
      INC $0C4E
      ;JMP $E5DB

  +++ ; 22E5CC
    LDA $0C4F : CMP #$2C : BNE ++++ ; $22E5D9
      INC $0C4F
      ;JMP $E5DB

  ++++ ; 22E5D9
    BRA +++++ ; $22E5E0

  +++++ ; 22E5E0
    JSR CheckAndClearAncillaId ; $DD90
    RTS
}

; =========================================================
;22EE80
; TODO: Handle the somaria blast case, these JMPs are invalid.

CheckForSomariaBlast:
{
    LDA $0300 : BEQ + ; $22EE88
      ;JMP $E5DB

  + ; 22EE88
    LDA $0C4A : CMP #$01 : BNE ++ ; $22EE92
      ;JMP $EEC0

  ++ ; 22EE92
    LDA $0C4B : CMP #$01 : BNE +++ ; $22EE9C
      ;JMP $EEC0

  +++ ; 22EE9C
    LDA $0C4C : CMP #$01 : BNE ++++ ; $22EEA6
      ;JMP $EEC0

  ++++ ; 22EEA6
    LDA $0C4D : CMP #$01 : BNE +++++ ; $22EEB0
      ;JMP $EEC0

  +++++ ; 22EEB0
    LDA $0C4E : CMP #$01 : BNE ++++++ ; $22EEBA
      ;JMP $EEC0

  ++++++ ; 22EEBA
    JMP CheckForSomariaBlock_22E5A5 ; $E5A5
}

; =========================================================
; 22EF00
; Hooked inside LinkItem_Hookshot @ 07AB5E

BallChain_StartAnimationFlag:
{
  ; Restore vanilla code
  LDA #$01 : STA $037B
  ; Check if we are rotating the goldstar
  LDA $037A : CMP #$04 : BNE +
    ; Animation flag, prevent menu from opening
    LDA #$01 : STA $0112
  +
  RTL
}

; =========================================================

pushpc
org $07AB95
  JSL BallChain_Finish
  NOP #2
pullpc

; 22EF12
; Hooked inside LinkState_Hookshotting @ 07AB95
BallChain_Finish:
{
  STZ.w $0300 : STZ.w $037B ; Restore vanilla
  LDA $037A : CMP #$04 : BNE .not_done ; We are hookshotting
    STZ $0112 ; Clear animation flag
  .not_done
  RTL
}

; =========================================================
; 22EF30
; Hooked at $07AC98

Hookshot_Init:
{
  ; ResetAllAcceleration:
  REP #$20
  STZ.w $032F : STZ.w $0331
  STZ.w $0326 : STZ.w $0328
  STZ.w $032B : STZ.w $032D
  STZ.w $033C : STZ.w $033E
  STZ.w $0334 : STZ.w $0336
  SEP #$20

  ; Initialize hookshot variables
  STZ.w $0300
  LDA.b #$01 : TSB.b $50
  LDA.b #$07 : STA.b $3D
  STZ.b $2E

  LDA.b $67 : AND.b #$F0 : STA.b $67
  LDA.w $037A : AND.b #$00 : ORA.b #$04
  STA.w $037A

  RTL
}

; =========================================================

BeginGoldstarOrHookshot:
{
  LDA.w GoldstarOrHookshot : CMP #$02 : BEQ .begin_goldstar
    JMP .begin_hookshot

  .begin_goldstar:
  JSL CheckForBallChain
  JSL Hookshot_Init
  JSL BallChain_StartAnimationFlag
  LDY.b #$03 : LDA.b #$1F ; ANCILLA 1F
  JSL AncillaAdd_Hookshot
  JSL TransferGFXinRAM
  RTL

  .begin_hookshot
  JSL Hookshot_Init
  LDA.b #$13 : STA $5D ; Set hookshot state
  LDA.b #$01 : STA.w $037B
  LDY.b #$03 : LDA.b #$1F ; ANCILLA 1F
  JSL AncillaAdd_Hookshot
  RTL
}

; =========================================================

MaybeUploadBirdGraphicsToOam:
{
  LDY $037A : CPY #$0104 : BEQ .here
    LDY #$40E0 : STY $2116
    JML $008B30 ; NMI_DoUpdates
  .here
  JML $008B50 ; NMI_DoUpdates.no_update_swagduck
}

ApplyGoldstarDamageClass:
{
  PHA
  ; If the hookshot is active
  LDA.w $0202 : CMP.b #$03 : BNE .return
    ; If the goldstar is active, swap in the damage class
    LDA.w GoldstarOrHookshot : CMP.b #$02 : BNE .return
      PLA
      LDA #$02
      JMP .apply
  .return
  PLA
  .apply
  JSL $06ED25 ; Ancilla_CheckDamageToSprite_preset.apply
  RTL
}

; =========================================================

CheckForSwitchToGoldstar:
{
  JSL CheckNewRButtonPress : BEQ .continue
  LDA.l $7EF342 : CMP.b #$02 : BNE .continue
    LDA.w GoldstarOrHookshot : CMP.b #$01 : BEQ .set_hookshot
      LDA.b #$01 : STA.w GoldstarOrHookshot
      JMP .continue
    .set_hookshot:
    LDA.b #$02 : STA.w GoldstarOrHookshot
  .continue:
  LDA.b $3A : AND.b #$40 ; Restore vanilla code
  RTL
}

Goldstar_GetDragged:
{
  LDA.w GoldstarOrHookshot : CMP.b #$02 : BNE +
    STZ.w $0112
    STZ.w $037E
    RTL
  +
  JSL LinkHop_FindArbitraryLandingSpot
  RTL
}

pushpc

; =========================================================
; Main Hookshot/Goldstar hooks

; LinkItem_Hookshot
org $07AB25
  JSL CheckForSwitchToGoldstar

; Ancilla_CheckDamageToSprite.not_airborne
org $06ECF2
  JSL ApplyGoldstarDamageClass

; LinkItem_Hookshot
org $07AB3A ;$07AB40
  JSL BeginGoldstarOrHookshot
  RTS

org $008B2A
  JML MaybeUploadBirdGraphicsToOam

org $07AD49
LinkHookshot_GetDragged:
  JSL Goldstar_GetDragged

