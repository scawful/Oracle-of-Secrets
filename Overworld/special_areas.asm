; =========================================================

org $0EDE49 ; @hook module=Overworld
JSL Overworld_CheckForSpecialOverworldTrigger
RTL

pullpc

Overworld_CheckForSpecialOverworldTrigger:
{
  PHB : PHK : PLB

  REP #$31

  JSR GetMap16Tile

  LDA.l Map16Definitions,X : AND.w #$01FF : STA.b $00

  LDX.w #$000C ; Size of table

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
  dw $01EF ; Maku Tree Entrance
  dw $01EF ; Tree House Entrance
  dw $00AD ; Zora Falls Entrance
  dw $00B9
  dw $01EF ; Tree House Entrance
  dw $00B7 ; Tiny House Entrance
  
  ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
  .screen_id
  dw $002A ; Maku Tree
  dw $0018 ; Mushroom Grotto
  dw $000F ; Graveyard
  dw $0081
  dw $0017 ; South of Graveyard
  dw $0033 ; Loom Beach
  
  ; Direction Link will face when he enters the special area
  .direction
  dw $0008, $0008, $0008, $0008, $0008, $0008
  
  ; Exit value for the special area. In Hyrule Magic these are those White markers.
  .special_id
  dw $0180, $0181, $0182, $0189, $0181, $0191
}


GetMap16Tile:
{
  LDA.b $20 : CLC : ADC.w #$000C : STA.b $00

  SEC
  SBC.w $0708

  AND.w $070A
  ASL A
  ASL A
  ASL A
  STA.b $06

  LDA.b $22 : CLC : ADC.w #$0008

  LSR A
  LSR A
  LSR A
  STA.b $02

  SEC : SBC.w $070C

  AND.w $070E
  CLC : ADC.b $06

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

  LDA.l Map16Definitions,X : AND.w #$01FF : STA.b $00

  LDX.w #$000C ; Size of table

  .check_next_screen
  LDA.b $00

  .check_next_tile
  DEX
  DEX
  BMI EXIT_0EDEE0

  CMP.l .tile_type, X : BNE .check_next_tile

  LDA.b $8A : CMP.l .screen_id, X : BNE .check_next_screen

  SEP #$30

  LDA.l .direction, X : STA.b $67

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

  LDA.b #$24 : STA.b $11
  STZ.b $B0 : STZ.b $A0

  RTL

  .tile_type
  dw $017C
  dw $01E4
  dw $00AD
  dw $00B9
  dw $01EF
  dw $00B7

  .screen_id
  dw $0080 ; OW 80
  dw $0080 ; OW 80
  dw $0081 ; OW 81
  dw $0081 ; OW 81
  dw $0080 ; OW 91
  dw $0091

  .direction
  dw $0004
  dw $0001
  dw $0004
  dw $0004
  dw $0004
  dw $0004
}

pushpc

OverworldPalettesLoader = $0ED5A8

org $02E90C ; LoadSpecialOverworld interrupt ; @hook module=Overworld
  JSL LoadSpecialOverworld
  RTS

pullpc

; Table of overworld transition points
OverworldTransitionPositionY = $02A8C4
OverworldTransitionPositionX = $02A944

; Interrupts the vanilla LoadSpecialOverworld function
; after LoadOverworldFromUnderworld is called.
; Adds additional data to the table for more special areas

; Overworld ID $A0 is set to the special area ID 
; To support 0x91, the special area ID will need to index to row 5 of the table

LoadSpecialOverworld:
{
  STZ.w $0AA5 ; Clear the custom gfx flag for koroks

  REP #$20
  LDA.b $A0 : CMP.w #$1010 : BNE .not_zora
    LDA.w #$0182 ; OW 82
    STA.b $A0
  .not_zora
  SEP #$20

  PHB : PHK : PLB

  LDA.b $A0
  PHA

  SEC : SBC.b #$80 : STA.b $A0

  ; Check if the special area is 0x91
  LDA.b $A0 : CMP.b #$11 : BNE .not_tiny_house
    ; Subtract by 5 to index to row 5 of the table
    SEC : SBC.b #$05 : STA.b $A0
  .not_tiny_house

  TAX

  LDA.l .direction, X : STA.b $2F
  STZ.w $0412

  LDA.l .gfx_AA3, X : STA.w $0AA3
  LDA.l .gfx_AA2, X : STA.w $0AA2

  PHX
  LDA.l .palette_prop_b, X : STA.b $00
  LDA.l .palette_prop_a, X : JSL OverworldPalettesLoader
  PLX

  REP #$30

  ; Store the size of a big screen in $00 if ID < 5
  LDA.b $A0 : AND.w #$00FF : CMP.w #$0005 : BCC .large_map
    LDA.w #$01F0 : STA.b $00 ; Small map size
    JMP +
  .large_map
  LDA.w #$03F0 : STA.b $00
  +

  ; Load overworld ID 
  LDA.b $A0 : AND.w #$003F : ASL A : TAX

  ; Overworld camera boundaries Y edge
  LDA.l .camera600, X : STA.w $0708

  ; X edge
  LDA.l .camera70C, X
  LSR A : LSR A : LSR A
  STA.w $070C

  ; Y BG size
  ; 0x01F0 on small screens, 0x03F0 on big screens
  LDA.b $00 : STA.w $070A

  ; X BG size
  ; 0x003E on small screens , 0x007E on big screens
  LDA.b $00
  LSR A : LSR A : LSR A
  STA.w $070E

  ; ---------------------------------------------------------

  LDA.b $A0 : ASL A : TAY

  SEP #$10
  LDA.w .camera600, Y : STA.w $0600
  LDA.w .camera602, Y : STA.w $0602
  LDA.w .camera604, Y : STA.w $0604
  LDA.w .camera606, Y : STA.w $0606
  LDA.w .camera610, Y : STA.w $0610
  LDA.w .camera612, Y : STA.w $0612
  LDA.w .camera614, Y : STA.w $0614
  LDA.w .camera616, Y : STA.w $0616
  SEP #$20

  PLA
  STA.b $A0

  PLB

  JSL $0ED61D ; Overworld_SetScreenBGColorCacheOnly

  RTL

  ; row 0 - maku tree, left half of small map 80
  ; row 1 - tree house, top right quarter of small map 80
  ; row 2 - zora falls, large map 81
  ; row 3 - also zora falls?
  ; row 4 - tree house, top right quarter of small map 80 (mirror)
  ; row 5 - tiny house, small map 91 (512x512)

  ; Affects $0600 and $0708
  .camera600 ; Camera Scroll Boundary Small North
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0200, $0200, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0400, $0400, $0400, $0400 ; OW 91

  .camera602 ; Camera Scroll Boundary Large North
  dw $0120, $0020, $0320, $0020 ; OW 80
  dw $0000, $0000, $0320, $0320 ; OW 81
  dw $0320, $0220, $0000, $0000 ; OW 82
  dw $0000, $0000, $0320, $0320 
  dw $0320, $0220, $0000, $0000 ; OW 81
  dw $051E, $0000, $051E, $051E ; OW 91

  .camera604 ; Camera Scroll Boundary South
  dw $0000, $0100, $0200, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0100, $0200, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0100, $0200, $0600
  dw $0600, $0A00, $0C00, $0C00

  .camera606 ; Camera Scroll Boundary Large South
  dw $0000, $0100, $0500, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0100, $0400, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0100, $0500, $0600
  dw $0300, $0A00, $0C00, $0C00

  .camera610 ; Overworld target position for transition north
  dw $FF20, $FF20, $FF20, $FF20
  dw $FF20, $FF20, $FF20, $FF20
  dw $FF20, $FF20, $0120, $FF20
  dw $FF20, $FF20, $FF20, $0120
  dw $FF20, $FF20, $FF20, $FF20
  dw $0320, $0320, $0320, $0320

  .camera614 ; Overworld target position for transition west
  dw $FFFC, $0100, $0300, $0100
  dw $0500, $0900, $0B00, $0B00
  dw $FFFC, $0100, $0300, $0500
  dw $0500, $0900, $0B00, $0B00
  dw $FFFC, $0100, $0300, $0100
  dw $0100, $0900, $0B00, $0B00

  .camera612 ; Overworld target position for transition south
  dw $FF20, $FF20, $FF20, $FF20
  dw $FF20, $FF20, $0400, $0400
  dw $FF20, $FF20, $0120, $FF20
  dw $FF20, $FF20, $0400, $0400
  dw $FF20, $FF20, $FF20, $FF20
  dw $FF20, $FF20, $0400, $0400

  .camera616 ; Overworld target position for transition east
  dw $0004, $0104, $0300, $0100
  dw $0500, $0900, $0B00, $0B00
  dw $0004, $0104, $0300, $0100
  dw $0500, $0900, $0B00, $0B00
  dw $0004, $0104, $0300, $0100
  dw $0400, $0900, $0B00, $0B00

  .camera70C ; Overworld X Edge 
  dw $0000, $0000, $0200, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0000, $0200, $0600
  dw $0600, $0A00, $0C00, $0C00
  dw $0000, $0000, $0200, $0600
  dw $0000, $0000, $0000, $0000

  ; ---------------------------------------------------------

  .direction
  db $00, $04, $00, $00
  db $00, $00, $00, $00
  db $00, $00, $00, $00
  db $00, $00, $00, $00
  db $00, $00, $00, $00
  db $00, $00, $00, $00

  .gfx_AA3
  db $0C, $0C, $0E, $0E
  db $0E, $10, $10, $10
  db $0E, $0E, $0E, $0E
  db $10, $10, $10, $10
  db $0E, $0E, $0E, $0E
  db $10, $10, $10, $10

  .gfx_AA2
  db $2F, $2F, $2F, $2F
  db $2F, $2F, $2F, $2F
  db $2F, $2F, $2F, $2F
  db $2F, $2F, $2F, $2F
  db $2F, $2F, $2F, $2F
  db $2F, $2F, $2F, $2F

  .palette_prop_a
  db $0A, $0A, $0A, $0A ; 0x00 - Maku Tree
  db $02, $02, $02, $0A ; 0x01 - Tree House
  db $01, $01, $04, $01 ; 0x02 - Zora Falls
  db $02, $02, $02, $0A ; 0x03 - Zora Falls
  db $02, $02, $02, $0A ; 0x04 - Tree House
  db $02, $02, $02, $0A ; 0x05 - Tiny House

  .palette_prop_b
  db $01, $08, $08, $08
  db $00, $00, $00, $00
  db $00, $00, $00, $00
  db $00, $00, $00, $02
  db $00, $00, $00, $00
  db $00, $00, $00, $00
}
