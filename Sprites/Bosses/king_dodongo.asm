; King Dodongo
;
; Health increased to 0x50 (80)

KingDodongo_NewHealthSystem:
{
  PHB : PHK : PLB
  LDA.w SprHealth,X
  LSR A
  LSR A
  TAY

  LDA.w .phase_table,Y
  STA.w SprMiscB,X
  PLB

  RTL

.phase_table
  db $03, $03, $03, $03, $03, $03, $03, $03
  db $03, $03, $03, $03, $02, $02, $02, $02
  db $02, $02, $01, $01, $01, $01, $01, $01
  db $00, $00, $00, $00, $00, $00, $00, $00
}

pushpc

; Adjust leg position to remove gap
org $1E87F5
.offset_x
#_1E87F5: db -22, -22,  22,  22

.offset_y
#_1E87F9: db -28,   8, -28,   8

.char
#_1E87FD: db $A2, $A6, $A2, $A6

.prop
#_1E8801: db $0B, $0B, $4B, $4B

org $1E8266
AND.b #$15

org $1E818C
.speed_x
#_1E818C: db -16, -16,  -8,   0,   8,  16,  16,   0

.speed_y
#_1E8194: db   0,   8,  16,  16,  16,   8,   0,  16

org $1E811A
JSL KingDodongo_NewHealthSystem
NOP #5

pullpc