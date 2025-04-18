; Dungeon Object Handler

; Tile types
TileBehavior_Nothing = $07DC54
TileBehavior_Pit = $07DC8B
TileBehavior_Door = $07DD0A

org $018262 ; Object ID 0x31
  dw ExpandedObject

org $018264 ; Object ID 0x32
  dw ExpandedObject2

org $0182A8 ; Object ID 0x54
  dw SpriteBodyObjects

; RoomDraw_WeirdUglyPot
org $018650 ; Object ID 230
  dw HeavyPot

; Heavy rock object draw code
DrawBigGraySegment_hook = $01B350

; Bank01 Free Space
org $01B53C
  ExpandedObject:
    JSL CustomObjectHandler
    RTS

  ExpandedObject2:
    JSL CustomObjectHandler2
    RTS

  SpriteBodyObjects:
    JSL SpriteObjectsDraw
    RTS

  HeavyPot:
    JSL InitHeavyPot
    JMP DrawBigGraySegment_hook

assert pc() <= $01B560

org $2C8000
; TODO: Fix the graphics used for the heavy pot in game
InitHeavyPot:
{
  LDA.w #$1010
  PHX
  LDX.w $042C ; MANIPINDEX
  LDA.w #$1111 : STA $0500, X ; M16BUFF500

  ; Store this object's position in the object buffer to $0520, X
  LDA $BA : STA $0520, X

  ; Store it's tilemap position.
  TYA : STA $0540, X
  RTL
}

CustomObjectHandler:
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
    dw .TrackAny-.ObjData         ; 14
    dw .SmallStatue-.ObjData      ; 15

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
    .TrackAny
      incbin Data/track_any.bin
    .SmallStatue
      incbin Data/small_statue.bin
}

SpriteObjectsDraw:
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
          LDA .ObjData, X : BEQ +
              ORA.w #$0300
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
  dw .KydreeokBody-.ObjData     ; 00
  dw .ManhandlaBody1-.ObjData   ; 01

.ObjData
  .KydreeokBody
    incbin Data/kydreeok_body.bin
  .ManhandlaBody1
    incbin Data/manhandla_body_1a.bin
}


CustomObjectHandler2:
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
    dw .IceFurnace-.ObjData       ; 00
    dw .Firewood-.ObjData         ; 01
    dw .IceChair-.ObjData         ; 02

  .ObjData
    .IceFurnace
      incbin Data/furnace.bin
    .Firewood
      incbin Data/firewood.bin
    .IceChair
      incbin Data/ice_chair.bin
}

pushpc

; Item ID 22B
org $00A9AC
  dw $0D28, $0D38, $4D28, $4D38

; org $01B306 ; RoomDraw_WeirdGloveRequiredPot
;   LDA.w #$1010

; Normal Door
; #obj2716:
;   dw $2888, $0808, $0818, $2889
;   dw $09EF, $0878, $6889, $09EF
;   dw $4878, $6888, $4808, $4818

; Unused door 3A
; #obj2866:
org $00C3B8
  dw $2888, $0808, $0818, $2889
;             09
  dw $282C, $082D, $6889, $682C
;      10
  dw $482D, $6888, $4808, $4818

; 282D
; 682D
; $682C

; #obj2866:
;   dw $282C, $0808, $080D, $282D
;   dw $09EF, $0878, $682D, $09EF
;   dw $4878, $682C, $4808, $480D
