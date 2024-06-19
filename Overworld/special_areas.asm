; =========================================================

org $0EDE49
JSL Overworld_CheckForSpecialOverworldTrigger
RTL

pullpc

Overworld_CheckForSpecialOverworldTrigger:
{
  PHB : PHK : PLB

  REP #$31

  JSR GetMap16Tile

  LDA.l Map16Definitions,X : AND.w #$01FF : STA.b $00

  LDX.w #$000A

  .check_next_screen
  LDA.b $00

  .check_next_tile
  DEX
  DEX
  BMI .exit

  CMP.l .tile_type,X : BNE .check_next_tile

  LDA.b $8A : CMP.l .screen_id, X : BNE .check_next_screen

  ;--------------------------------------------------------

  LDA.l .special_id,X
  STA.b $A0

  SEP #$20

  LDA.l .direction,X
  STA.b $67

  STA.w $0410
  STA.w $0416

  LDX.w #$0004

  .continue_shifting
  DEX

  LSR A
  BCC .continue_shifting

  STX.w $0418
  STX.w $069C

  LDA.b #$17
  STA.b $11

  LDA.b #$0B
  STA.b $10

  .exit
  SEP #$30

  PLB

  RTL

  ; .tile_type
  ; dw $0105
  ; dw $01E4
  ; dw $00AD
  ; dw $00B9

  ; .screen_id
  ; dw $0000 ; OW 00
  ; dw $002D ; OW 2D
  ; dw $000F ; OW 0F
  ; dw $0081 ; OW 81

  ; .direction
  ; dw $0008
  ; dw $0002
  ; dw $0008
  ; dw $0008

  ; .special_id
  ; dw $0180 ; OW 80
  ; dw $0181 ; OW 81
  ; dw $0182 ; OW 82
  ; dw $0189 ; OW 89

  ; corresponding warp types that lead to special overworld areas
  .tile_type
  dw $01EF, $01EF, $00AD, $00B9, $01EF
  
  ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
  .screen_id
  dw $002A, $0018, $000F, $0081, $0017
  
  ; Direction Link will face when he enters the special area
  .direction
  dw $0008, $0008, $0008, $0008, $0008
  
  ; Exit value for the special area. In Hyrule Magic these are those White markers.
  .special_id
  dw $0180, $0181, $0182, $0189, $0181
}


GetMap16Tile:
{
  LDA.b $20
  CLC
  ADC.w #$000C
  STA.b $00

  SEC
  SBC.w $0708

  AND.w $070A
  ASL A
  ASL A
  ASL A
  STA.b $06

  LDA.b $22
  CLC
  ADC.w #$0008

  LSR A
  LSR A
  LSR A
  STA.b $02

  SEC
  SBC.w $070C

  AND.w $070E
  CLC
  ADC.b $06

  TAY
  TAX

  LDA.l $7E2000,X
  ASL A
  ASL A
  ASL A
  TAX

  RTS
}

#EXIT_0EDEE0:
SEP #$30

RTL

; =========================================================

SpecialOverworld_CheckForReturnTrigger:
{
  REP #$31

  JSR GetMap16Tile

  LDA.l Map16Definitions,X
  AND.w #$01FF
  STA.b $00

  LDX.w #$0006

  .check_next_screen
  LDA.b $00

  .check_next_tile
  DEX
  DEX
  BMI EXIT_0EDEE0

  CMP.l .tile_type,X
  BNE .check_next_tile

  LDA.b $8A
  CMP.l .screen_id,X
  BNE .check_next_screen

  SEP #$30

  LDA.l .direction,X
  STA.b $67

  LDX.b #$04

  .keep_shifting
  DEX

  LSR A
  BCC .keep_shifting

  TXA
  STA.w $0418

  LDA.b $67

  LDX.b #$04

  .just_keep_shifting
  DEX

  LSR A
  BCC .just_keep_shifting

  TXA
  STA.w $069C

  LDA.b #$24
  STA.b $11

  STZ.b $B0
  STZ.b $A0

  RTL

  .tile_type
  dw $017C
  dw $01E4
  dw $00AD

  .screen_id
  dw $0080 ; OW 80
  dw $0080 ; OW 80
  dw $0081 ; OW 81

  .direction
  dw $0004
  dw $0001
  dw $0004
}

LoadExpandedSpecialArea:
{
  LDA.b $A0 : CMP.w #$0191 : BNE .not_minish_woods
    LDA.w #$0180 : STA.b $A0
  .not_minish_woods
  RTL
}

org $02E90E
JSL LoadExpandedSpecialArea : NOP
