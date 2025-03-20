org $01C742
  JSL Ancilla_SpawnFallingPrize

org $06FA34
  JSL Ancilla_SpawnFallingPrize

org $098BC1
  AncillaAdd_FallingPrize:

pullpc

Ancilla_SpawnFallingPrize:
  PHX
  TAX
  LDY.b #$04
  LDA.b #$29 ; ANCILLA 29
  JSL AncillaAdd_FallingPrize
  PLX
  RTL

Lanmola_DrawDirtLONG:
{
  PHB : PHK : PLB
  JSR Lanmola_DrawDirt
  PLB
  RTL
}

Lanmola_DrawDirt:
{
  LDA.w SprTimerB, X : BNE .timerNotDone
    RTS
  .timerNotDone

  ; Determine weather the dirt should draw in front of or behind the body
  ; based on its y velocity.
  LDA.w SprYSpeed, X : ASL A : ROL A : ASL A : EOR $0D80, X : AND.b #$02 : BEQ .nu
    LDA.b #$08 : JSL OAM_AllocateFromRegionB
    BRA .xi

  .nu
    LDA.b #$08 : JSL OAM_AllocateFromRegionC

  .xi

  LDY.b #$00

  LDA.w SprTimerB, X : LSR #2 : AND.b #$03 : EOR.b #$03 : ASL A : STA $06
  LDA $0DC0, X : XBA
  LDA.w SprMiscC, X
  REP #$20 : SEC : SBC $E2 : STA $00 : SEP #$20
  STZ $37
  BPL .notNegative3
    INC $37

  .notNegative3

  LDA.w SprMiscE, X : XBA
  LDA $0E70, X
  REP #$20 : SEC : SBC $E8 : STA $02 : SEP #$20
  PHX
  LDX.b #$01

  .dirtLoop
    PHX

    TXA : CLC : ADC $06 : ASL : TAX

    REP #$20
    LDA $00 : CLC : ADC $7EEA64, X : STA ($90), Y ;dirt x ;.xDirt

    STZ $36
    BPL .notNegative4
        INC $36

    .notNegative4

    INY

    CLC : ADC.w #$0040 : CMP.w #$0140 : BCS .out_of_bounds3

    LDA $02 : CLC : ADC $7EEA74, X : STA ($90), Y ;dirt y ;.yDirt

    REP #$20
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20

    BCC .on_screen_y
      .out_of_bounds3
      SEP #$20
      LDA.b #$F0 : STA ($90), Y

    .on_screen_y

    TXA : LSR : TAX

    LDA $7EEA84, X : INY : STA ($90), Y ;dirt chr ;.chrDirt
    LDA $7EEA8C, X : INY : STA ($90), Y ;dirt properties ;.propertiesDirt

    PHY

    TYA : LSR #2 : TAY

    LDA $7EEA94, X : ORA $37 : ORA $36 : STA ($92), Y ;.sizesDirt

    PLY : INY

  PLX : DEX : BPL .dirtLoop

  PLX

  RTS
}

; =========================================================

Sprite_Lanmola_Init_DataLONG:
{
  PHB : PHK : PLB
  JSR Sprite_Lanmola_Init_Data
  PLB
  RTL
}

; =========================================================

Sprite_Lanmola_Init_Data:
{
    PHX

    LDX.b #$00
    .loop
      LDA .sprite_regions, X : STA $7EEA00, X

    INX : CPX.b #$B8 : BCC .loop

    PLX

    RTS

    ;$7EEA00
    .sprite_regions
    db $00, $40, $80, $C0

    ;$7EEA04
    .data1
    db $00, $1C

    ;$7EEA06
    .data2
    db $01, $F9

    ;$7EEA08
    .chrHead
    db $C4, $E2, $C2, $E0, $C0, $E0, $C2, $E2, $C4, $E2, $C2, $E0, $C0, $E0, $C2, $E2

    ;$7EEA18
    .chrTail
    db $CC, $E4, $CA, $E6, $C8, $E6, $CA, $E4, $CC, $E4, $CA, $E6, $C8, $E6, $CA, $E4

    ;$7EEA28
    .propertiesBody
    ;db $F3, $F3, $F3, $F3, $B3, $B3, $B3, $B3, $33, $33, $33, $33, $73, $73, $73, $73
    ; 1 yellow, green, pink
    ;db $F1, $F1, $F1, $F1, $B1, $B1, $B1, $B1, $31, $31, $31, $31, $71, $71, $71, $71
    ; 3 metroid colors
    ; 5 ice blue
    ; db $F5, $F5, $F5, $F5, $B5, $B5, $B5, $B5, $35, $35, $35, $35, $75, $75, $75, $75
    ; 7 red and yellow
    ; db $F7, $F7, $F7, $F7, $B7, $B7, $B7, $B7, $37, $37, $37, $37, $77, $77, $77, $77
    ; 9 blue and red
    ; db $F9, $F9, $F9, $F9, $B9, $B9, $B9, $B9, $39, $39, $39, $39, $79, $79, $79, $79
    ; B neon green and yellow
    ; D silver and yellow
    db $FD, $FD, $FD, $FD, $BD, $BD, $BD, $BD, $3D, $3D, $3D, $3D, $7D, $7D, $7D, $7D
    ; F yellow and red
    ; db $FF, $FF, $FF, $FF, $BF, $BF, $BF, $BF, $3F, $3F, $3F, $3F, $7F, $7F, $7F, $7F

    ;$7EEA38
    .oamCoord90
    dw $0930, $08F0, $08B0, $0870

    ;$7EEA40
    .oamCoord92
    dw $0A6C, $0A5C, $0A4C, $0A3C

    ;$7EEA48
    .chrMound
    db $EE, $EE, $EC, $EC, $CE, $CE
    ;db $EE, $EE, $EC, $EC, $CE, $CE

    ;$7EEA4E
    .propertiesMound
    ; db $39, $79, $39, $79, $39, $79
    db $3D, $7D, $3D, $7D, $3D, $7D
    ;db $31, $71, $31, $71, $31, $71

    ;$7EEA54
    .frameMound
    db $04, $05, $04, $05, $04, $05, $04, $05
    db $04, $03, $02, $01, $01, $01, $00, $00

    ;$7EEA64
    .xDirt
    dw $FFF8, $0008, $FFF6, $000A, $FFF0, $0010, $FFE8, $0020
    ;db $F8, $08, $F6, $0A, $F0, $10, $E8, $20

    ;$7EEA74
    .yDirt
    dw $0000, $0000, $FFFF, $FFFF, $FFFF, $FFFF, $0003, $0003
    ;db $00, $00, $FF, $FF, $FF, $FF, $03, $03

    ;$7EEA84
    .chrDirt
    db $E8, $E8, $E8, $E8, $EA, $EA, $EA, $EA

    ;$7EEA8C
    .propertiesDirt
    db $39, $79, $39, $79, $39, $79, $39, $79
    ;db $00, $40, $00, $40, $00, $40, $00, $40

    ;$7EEA94
    .sizesDirt
    db $02, $02, $02, $02, $02, $02, $00, $00

    ;$7EEA9C
    .y_speed_slope
    db 2, -2

    ;$7EEA9E
    .y_speeds
    db $10, $F0

    ;$7EEAA0
    .dataDeath
    db 0,  8, 16, 24, 32, 40, 48, 56

    ;$7EEAA8
    .randXPos
    db $58, $50, $60, $70, $80, $90, $A0, $98

    ;$7EEAB0
    .randYPos
    db $68, $60, $70, $80, $90, $A0, $A8, $B0

    ;$7EEAB8
    .lanmoalKilledState

    ;7EEACA
}

; =========================================================

Lanmola_MoveSegment:
{
  PHX
  TXA : ASL A : TAX

  REP #$20
  LDA $7EEA38, X : STA $90 ;.oamCoord90
  LDA $7EEA40, X : STA $92 ;.oamCoord92
  SEP #$20

  PLX

  LDA.w SprYSpeed, X : SEC : SBC $0F80, X : STA $00
  LDA.w SprXSpeed, X                      : STA $01
  JSL Sprite_ConvertVelocityToAngle : STA $0F

  LDA $7EEA00, X : STA $04 ;.sprite_regions

  PHX

  ; Store the current position, angle, and hieght of the sprite
  ; so that we can set the other segments to them later.
  LDA.w SprXH, X : PHA ;high x
  LDA.w SprYH, X : PHA ;high y
  LDA.w SprX, X : PHA ;lower x
  LDA.w SprY, X : PHA ;lower y

  LDA.w SprHeight, X : PHA ;height
  LDA $0F      : PHA ;angle

  LDA $0E80, X : STA $02 : STA $05

  CLC : ADC $04 : TAX

  PLA : STA $7FFF00, X ;angle
  PLA : STA $7FFE00, X ;height

  PLA : STA $7FFD00, X ;lower y
  PLA : STA $7FFC00, X ;lower x
  PLA : STA $7EE900, X ;high y
  PLA : STA $7EE800, X ;high x

  PLX

  LDA.w SprState, X : CMP.b #$09 : BNE .notActive
    LDA $11 : ORA.w SprFreeze : BNE .notActive
      LDA $10 : CMP #$0E : BEQ .notActive
      LDA $5D : CMP #$08 : BEQ .notActive ;in medallion cut scene
                CMP #$09 : BEQ .notActive ;in medallion cut scene
                CMP #$0A : BEQ .notActive ;in medallion cut scene
                  LDA $05 : INC A : AND.b #$3F : STA $0E80, X
  .notActive
  RTL
}

; =========================================================

SetShrapnelTimer:
{
  LDA.b #$40 : STA.w SprTimerA, Y
  JSL GetRandomInt ; replaced code
  RTL
}

; =========================================================

CheckIfActive:
{
  SEC

  ;Check if sprite is active (pause menu, etc...)
  LDA $10 : CMP #$0E : BEQ .inMenu
  LDA $5D : CMP #$08 : BEQ .inMenu ;in medallion cut scene
            CMP #$09 : BEQ .inMenu ;in medallion cut scene
            CMP #$0A : BEQ .inMenu ;in medallion cut scene

      CLC
  .inMenu

  RTL
}

