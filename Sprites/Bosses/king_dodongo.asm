; King Dodongo
;
; Health reduced to 0x28 (40) for v168 beta balance.
; Phase table shortened to 10 entries ($28 >> 2 = 10).
; Phases transition faster so the fight feels more dynamic.

KingDodongo_NewHealthSystem:
{
  PHB : PHK : PLB
  LDA.w SprHealth,X
  LSR A
  LSR A
  TAY
  ; The table has 10 entries (HP 0-39). Clamp higher HP to the last entry;
  ; reading past the table picked negative phases, and the boss deleted
  ; itself as mask debris (softlock in room $C8).
  CPY.b #$0A : BCC .in_table
    LDY.b #$09
  .in_table

  LDA.w .phase_table,Y
  STA.w SprMiscB,X
  PLB

  RTL

  .phase_table
  db $03, $03, $02, $02, $01, $01, $01, $00
  db $00, $00
}

pushpc

; Sprite health table entry for King Dodongo (sprite $92). The ROM held 96;
; 40 matches the phase table above (see header note).
assert read1($0DB173+$92) == $28 || read1($0DB173+$92) == $60, "Unexpected King Dodongo health"
org $0DB173+$92 ; @hook module=Sprites kind=data
db $28

; Adjust leg position to remove gap
org $1E87F5
.offset_x
db -22, -22,  22,  22
.offset_y
db -28,   8, -28,   8
.char
db $A2, $A6, $A2, $A6
.prop
db $0B, $0B, $4B, $4B

org $1E8266
AND.b #$15

org $1E818C ; @hook module=Sprites
.speed_x
db -16, -16,  -8,   0,   8,  16,  16,   0
.speed_y
db   0,   8,  16,  16,  16,   8,   0,  16

org $1E811A ; @hook module=Sprites
JSL KingDodongo_NewHealthSystem
NOP #5

pullpc
