; Dungeon Object Handler

org $018262 ;object id 0x31
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

          LDA .ObjData, X : BEQ +
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
  dw .LeftRight-.ObjData      ; 00 
  dw .UpDown-.ObjData         ; 01 
  dw .TopLeft-.ObjData        ; 02 
  dw .TopRight-.ObjData       ; 03 
  dw .Bottomleft-.ObjData     ; 04 
  dw .BottomRight-.ObjData    ; 05
  dw .UpDownFloor-.ObjData    ; 06
  dw .LeftRightFloor-.ObjData ; 07
  dw .TopLeftFloor-.ObjData   ; 08
  dw .TopRightFloor-.ObjData  ; 09
  dw .BottomleftFloor-.ObjData; 10
  dw .BottomRightFloor-.ObjData;11
  dw .FloorAny-.ObjData       ; 12

.ObjData
  .LeftRight
    incbin track_LR.bin
  .UpDown
    incbin track_UD.bin
  .TopLeft
    incbin track_corner_TL.bin
  .TopRight
    incbin track_corner_TR.bin
  .Bottomleft
    incbin track_corner_BL.bin
  .BottomRight
    incbin track_corner_BR.bin
  .UpDownFloor
    incbin track_floor_UD.bin
  .LeftRightFloor
    incbin track_floor_LR.bin
  .TopLeftFloor
    incbin track_floor_corner_TL.bin
  .TopRightFloor
    incbin track_floor_corner_TR.bin
  .BottomleftFloor
    incbin track_floor_corner_BL.bin
  .BottomRightFloor
    incbin track_floor_corner_BR.bin
  .FloorAny
    incbin track_floor_any.bin

}

pushpc