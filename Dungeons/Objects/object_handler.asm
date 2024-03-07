; Dungeon Object Handler

incsrc Collision/CollisionTablesExpanded.asm

org    $018262            ;object id 0x31
  dw ExpandedObject


org $01B53C
  ExpandedObject:
  JSL NewObjectsCode
  RTS


org $2C8000
NewObjectsCode:
{
  PHB : PHK : PLB
  PHX

  STZ $03 ; 03 will be used to store the object ID for custom config
  LDA $00 : PHA
  LDA $02 : PHA
  ; $00 Will be used for tile count and tile to skip 
  LDA $B2 : ASL #2 : ORA $B4

  ;get the offset for the object data based on the object height 
  ASL : TAX
  LDA .ObjOffset, X
  TAX

  .lineLoop
      LDA .ObjData, X : BNE .continue
          ;break
          BRA .Done
      .continue
      PHY ; Keep current position in the buffer

      STA $00 ; we save the tile count + tile to skip

      -- ;Tiles Loop
          INX : INX
          ;  Vhopppcc cccccccc
          print "Object Handler", pc
          LDA .ObjData, X : BEQ +
              JSR CustomDrawConfig
              STA [$BF], Y
          +

          INY : INY
          LDA $00 : DEC : STA $00 : AND #$001F : BNE +
              LDA $00 : XBA : AND #$00FF : STA $00
              PLA                                  ;Pull back position
              CLC : ADC $00 : TAY
              INX : INX
              BRA .lineLoop
          +

      BRA --

  .Done

  PLA : STA $02
  PLA : STA $00 ;Not sure if needed

  PLX
  PLB
  RTL

.ObjOffset
  dw .LeftRight-.ObjData        ; 00 
  dw .UpDown-.ObjData           ; 01 
  dw .TopLeft-.ObjData          ; 02 
  dw .TopRight-.ObjData         ; 03 
  dw .Bottomleft-.ObjData       ; 04 
  dw .BottomRight-.ObjData      ; 05
  dw .UpDownFloor-.ObjData      ; 06
  dw .LeftRightFloor-.ObjData   ; 07
  dw .TopLeftFloor-.ObjData     ; 08
  dw .TopRightFloor-.ObjData    ; 09
  dw .BottomleftFloor-.ObjData  ; 10
  dw .BottomRightFloor-.ObjData ; 11
  dw .FloorAny-.ObjData         ; 12
  dw .WallSwordHouse-.ObjData   ; 13
  dw .KydreeokBody-.ObjData     ; 14
  dw .HeavyPot-.ObjData         ; 15

.ObjData
  .LeftRight
    incbin Data/track_LR.bin
  .UpDown
    incbin Data/track_UD.bin
  .TopLeft
    incbin Data/track_corner_TL.bin
  .TopRight
    incbin Data/track_corner_TR.bin
  .Bottomleft
    incbin Data/track_corner_BL.bin
  .BottomRight
    incbin Data/track_corner_BR.bin
  .UpDownFloor
    incbin Data/track_floor_UD.bin
  .LeftRightFloor
    incbin Data/track_floor_LR.bin
  .TopLeftFloor
    incbin Data/track_floor_corner_TL.bin
  .TopRightFloor
    incbin Data/track_floor_corner_TR.bin
  .BottomleftFloor
    incbin Data/track_floor_corner_BL.bin
  .BottomRightFloor
    incbin Data/track_floor_corner_BR.bin
  .FloorAny
    incbin Data/track_floor_any.bin
  .WallSwordHouse
    incbin Data/wall_sword_house.bin
  .KydreeokBody
    incbin Data/kydreeok_body.bin
  .HeavyPot
    incbin Data/heavy_pot.bin

}


; May need to make this a table 
; This modifies object 0xOE to use the spritesheets for the object
CustomDrawConfig:
{
  PHA
  LDA $03 : AND #$00FF : CMP.w #$000E : BEQ .custom_config

  TYA : LSR : AND #$00FF

  CMP #$000E : BNE .no_spriteset
    LDA #$000E : STA $03
  .custom_config
    PLA
    ORA.w #$0300 : JMP .return
.no_spriteset   
    PLA
.return
  RTS
}

pushpc

; Item ID 22B 
org $00A9AC
  dw $0D28, $0D38, $4D28, $4D38

org $01B306 ; RoomDraw_WeirdGloveRequiredPot
  LDA.w #$1010
