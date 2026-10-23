; Preserved $97: tag1=$17 owns the original one-sided shutter. Tag2=$37
; owns only the appended P faces (indices 2/10). Included only by the
; default-off cart-shutter feature. No save bits or selector reset are used.
if !ENABLE_MINECART_CART_SHUTTERS
!CartShutter97PreservedCode = $2CF000

pushpc
; @source usdasm/bank_01.asm:Underworld_LoadHeader, M16/X16, D=0.
assert read4($01B6DF) == $8D0F0009 && read2($01B6E3) == $068C, "Initial door flags moved"
org $01B6DF ; @hook module=Sprites name=CartShutter97_InitDoors kind=jsl target=CartShutter97_InitDoors expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL CartShutter97_InitDoors
  NOP #2
assert pc() == $01B6E5

; @source usdasm/bank_01.asm:OperateShutterDoors. Long entry establishes
; M16/X16; the original body returns M8/X8. DBR/D remain the caller's.
assert read4($01D38F) == $0C6430C2, "Shutter animator entry moved"
org $01D38F ; @hook module=Sprites name=CartShutter97_Animate kind=jml target=CartShutter97_Animate expected_exit_m=8 expected_exit_x=8
  JML CartShutter97_Animate
assert pc() == $01D393

; @source usdasm/bank_01.asm:OperateShutterDoors.next_door, M16/X16.
assert read4($01D3C7) == $291980B9 && read2($01D3CB) == $00FE, "Shutter face selection moved"
org $01D3C7 ; @hook module=Sprites name=CartShutter97_FilterDoor kind=jsl target=CartShutter97_FilterDoor expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL CartShutter97_FilterDoor
  NOP #2
assert pc() == $01D3CD

; @source usdasm/bank_01.asm:RoomDraw_FlagDoorsAndGetFinalType. An open
; P uses its own mask even when the original $17 shutter is closed.
assert read4($01B10B) == $D00468AD && read1($01B10F) == $31, "Open shutter graphic branch moved"
org $01B10B ; @hook module=Sprites name=CartShutter97_DrawState kind=jml target=CartShutter97_DrawState expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JML CartShutter97_DrawState
  NOP
assert pc() == $01B110
pullpc

pushpc
org !CartShutter97PreservedCode

; Predicate helpers preserve P except carry, and X/Y/DBR/D. A clobbered.
CartShutter97_PreservedProfile:
{
  PHP
  REP #$20
  LDA.b $A0 : CMP.w #$0097 : BNE .no
  LDA.b $AE : CMP.w #$3717 : BNE .no
  PLP
  SEC
  RTS
  .no
  PLP
  CLC
  RTS
}

; Called before door drawing on every room load. Clear both private bytes
; even outside $97; only the exact preserved header gets a valid seal.
; P starts closed without changing the original $0400 or $0468 state.
CartShutter97_InitDoors:
{
  ORA.w #$0F00
  PHA
  LDA.w #$0000 : STA.l CartShutter97Job
  JSR.w CartShutter97_PreservedProfile
  BCC .ordinary
  LDA.w #$A500 : STA.l CartShutter97Job
  PLA
  AND.w #$DFDF
  STA.w $068C
  RTL
  .ordinary
  PLA
  STA.w $068C
  RTL
}

; Carry set only for a validated P transaction; arbitrary/old WRAM cannot
; select a job. Room load always resets it before either tag can execute.
CartShutter97_PJob:
{
  PHP
  REP #$20
  LDA.l CartShutter97Job
  CMP.w #$A580 : BEQ .yes
  CMP.w #$A581 : BEQ .yes
  PLP
  CLC
  RTS
  .yes
  PLP
  SEC
  RTS
}

; Use the vanilla timer/draw/collision body as a serialized P transaction.
; The original $0468 word lives on the stack only during this call. It is
; restored before returning to the module loop, including the final frame.
CartShutter97_Animate:
{
  REP #$30
  JSR.w CartShutter97_PreservedProfile : BCC .ordinary
  JSR.w CartShutter97_PJob : BCC .ordinary
  LDA.w $0468 : PHA
  LDA.l CartShutter97Job : AND.w #$0001 : STA.w $0468
  JSL CartShutter97_AnimateBody
  REP #$20
  PLA : STA.w $0468
  SEP #$30
  LDA.b $11 : BNE .exit
  LDA.b #$00 : STA.l CartShutter97Job
  .exit
  RTL
  .ordinary
  REP #$30
  STZ.b $0C
  JML $01D393
}

CartShutter97_AnimateBody:
{
  REP #$30
  STZ.b $0C
  JML $01D393
}

; Replacement for LDA1980,Y / AND00FE. X/Y and C/V/D/I are preserved;
; N/Z match the returned type. It never changes the actual door table.
CartShutter97_FilterDoor:
{
  PHP
  JSR.w CartShutter97_PreservedProfile : BCC .original
  CPY.w #$0004 : BEQ .p_face
  CPY.w #$0014 : BEQ .p_face
  JSR.w CartShutter97_PJob : BCS .excluded
  BRA .original
  .p_face
  JSR.w CartShutter97_PJob : BCC .excluded
  .original
  PLP
  LDA.w $1980, Y : AND.w #$00FE
  RTL
  .excluded
  PLP
  LDA.w #$0000
  RTL
}

; Original loader reaches this branch only for an already-open face.
; Preserve X/Y and select open graphics for P independently of $0468.
CartShutter97_DrawState:
{
  JSR.w CartShutter97_PreservedProfile : BCC .ordinary
  CPX.w #$0004 : BEQ .p_face
  CPX.w #$0014 : BNE .ordinary
  .p_face
  LDA.w $068C : AND.w #$2020 : CMP.w #$2020 : BNE .closed
  JML $01B110
  .ordinary
  LDA.w $0468 : BNE .closed
  JML $01B110
  .closed
  JML $01B141
}

; Fail closed if the expected appended P pair is absent or malformed.
CartShutter97_PLayout:
{
  REP #$20
  LDA.w $1984 : AND.w #$00FE : CMP.w #$0018 : BNE .no
  LDA.w $1994 : AND.w #$00FE : CMP.w #$0018 : BNE .no
  LDA.w $1982 : AND.w #$00FE : CMP.w #$0018 : BNE .no
  LDA.w $1992 : AND.w #$00FE : BNE .no
  SEP #$20
  SEC
  RTS
  .no
  SEP #$20
  CLC
  RTS
}

RoomTag_CartShutter97_Preserved:
{
  SEP #$30
  ; Tag1 may already have requested 05 or its pressure-plate effect17.
  LDA.b $11 : BNE .exit
  LDA.l CartShutter97Seal : CMP.b #$A5 : BNE .invalid
  JSR.w CartShutter97_PLayout : BCC .exit
  LDA.b #$00 : STA.l CartShutter97Job
  REP #$20
  LDA.w $068C : AND.w #$2020 : CMP.w #$2020 : BEQ .open
  CMP.w #$0000 : BNE .close
  SEP #$20
  JSR.w CartShutter97_Approach : BCC .exit
  LDA.b #$80
  BRA .start
  .open
  SEP #$20
  JSR.w CartShutter97_Hold : BCS .exit
  .close
  SEP #$20
  LDA.b #$81
  .start
  STA.l CartShutter97Job
  REP #$20
  STZ.w $068E : STZ.w $0690
  SEP #$20
  LDA.b #$05 : STA.b $11
  BRA .exit
  .invalid
  LDA.b #$00 : STA.l CartShutter97Job
  .exit
  SEP #$30
  JML $01CC5A
}

; Same geometric admission as the qualified local gate; no key-bit or
; selector dependency. The new narrow branch must retain this P aperture.
CartShutter97_Approach:
{
  LDA.b $1B : BEQ .no
  LDA.b $EE : BNE .no
  LDA.b !LinkInCart : BEQ .no
  LDX.w !MinecartCurrent : CPX.b #$10 : BCS .no
  LDA.w SprState, X : CMP.b #$09 : BNE .no
  LDA.w SprType, X : CMP.b #Sprite_Minecart : BNE .no
  LDA.w SprFloor, X : BNE .no
  LDA.w SprAction, X : CMP.b #$02 : BEQ .north
  CMP.b #$04 : BEQ .south
  .no
  CLC
  RTS
  .south
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CMP.w #$1328 : BCS .no_wide
  BRA .y_range
  .north
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CMP.w #$1328 : BCC .no_wide
  .y_range
  CMP.w #$12B8 : BCC .no_wide
  CMP.w #$1351 : BCS .no_wide
  SEP #$20
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CMP.w #$0F78 : BCC .no_wide
  CMP.w #$0F89 : BCS .no_wide
  LDA.b $22 : CMP.w #$0F68 : BCC .no_wide
  CMP.w #$0F99 : BCS .no_wide
  LDA.b $20 : CMP.w #$12B0 : BCC .no_wide
  CMP.w #$1359 : BCS .no_wide
  SEP #$20
  SEC
  RTS
  .no_wide
  SEP #$20
  CLC
  RTS
}
CartShutter97_PreservedEnd:
assert pc() <= $2CF800, "Preserved cart shutter exceeds its reserved block"
pullpc
endif
