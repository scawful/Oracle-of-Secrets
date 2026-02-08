;Custom dungeon collision code
;mostly written by kan
;put together by Jared_Brian_
;meant to be used with the ZScream collision editor
;12-18-2021

; Format:
; dw <offset> : db width, height
; dw <tile data>, ...
;
; if <offset> == $F0F0, start doing single tiles
; format:
; dw <offset> : db <data>
;
; if <offset> == $FFFF, stop

RoomPointer = $258090

org $01B95B ; @hook module=Dungeons name=CustomRoomCollision kind=jsl target=CustomRoomCollision expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
if !ENABLE_CUSTOM_ROOM_COLLISION
  JSL CustomRoomCollision
  NOP #6
else
  ; Vanilla (USDASM #_01B95B):
  ;   LDA.b $B4 : CMP.w #$2000 : BNE .more_to_go : INC.w $0200
  LDA.b $B4
  CMP.w #$2000
  BNE +            ; +3 bytes to INC
  INC.w $0200
+
endif

org $258000
CustomRoomCollision_easyout:
{
  RTL
}

CustomRoomCollision:
{
  LDA $B4 : CMP.w #$2000 : BNE .notEndOfTable
    INC $0200
  .notEndOfTable

  ; This hook runs during room load. Preserve P (including M/X width)
  ; so we don't leak 16-bit width back into vanilla transition code.
  PHP
  ; Do not assume Direct Page is $0000. This routine uses DP mirrors ($A0) and
  ; DP scratch ($00-$0F); preserve D and set D=$0000 while we run.
  PHD
  REP #$20
  LDA.w #$0000
  TCD

  REP #$30
  LDA.b $A0 : ASL : ADC.b $A0 : TAX
  LDA.l RoomPointer, X : BEQ .plp_rtl

  STA.b $08

  LDA.l RoomPointer+1, X : STA.b $09

  PHB

  PEA.w $7F7F
  PLB
  PLB

  LDY.w #$0000

  .read_next
  LDA.b [$08],Y
  INY
  INY
  CMP.w #$F0F0
  BCC .new_rectangle

  .single_tiles
  CMP.w #$FFFF
  BEQ .done

  TAX

  SEP #$20
  LDA.b [$08],Y
  STA.w $2000,X
  REP #$20
  INY
  LDA.b [$08],Y
  INY
  INY
  BRA .single_tiles

  .done
  ; Water gate persistence restore (room-entry collision reapply).
  ;
  ; This runs at the end of the collision map streaming pass (when $B4 reaches
  ; $2000). Doing it here avoids the old global torch-loop hook at $0188DF,
  ; which was implicated in deterministic dungeon transition corruption.
  if !ENABLE_WATER_GATE_HOOKS == 1 && !ENABLE_WATER_GATE_ROOMENTRY_RESTORE == 1
    LDA $B4 : CMP.w #$2000 : BNE +
      JSL WaterGate_CheckRoomEntry
    +
  endif

  PLB
  PLD
  PLP
  RTL

  .plp_rtl
  PLD
  PLP
  RTL

  .new_rectangle
  STA.b $02 ; beginning of row

  LDA.b [$08],Y ; number of rows and columns
  STA.b $06

  INY
  INY

  .next_row
  REP #$21
  LDA.b $02
  TAX
  ADC.w #64
  STA.b $02

  SEP #$20
  LDA.b $06 : STA $0C; save number of columns

  .next_column
  LDA.b [$08],Y
  STA.w $2000,X
  INY
  INX
  DEC.b $0C
  BNE .next_column

  DEC.b $07
  BNE .next_row

  REP #$21
  JMP .read_next
}
