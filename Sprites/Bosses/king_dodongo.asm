; King Dodongo
;
; Health increased to 0x50 (80)

KingDodongo_NewHealthSystem:
{
  PHB : PHK : PLB
  LDA.w $0E50,X
  LSR A
  LSR A
  TAY

  LDA.w .phase_table,Y
  STA.w $0DB0,X
  PLB 

  RTL

.phase_table
  db $03, $03, $03, $03, $03, $03, $03, $03
  db $03, $03, $03, $03, $03, $03, $03, $03
  db $02, $02, $01, $01, $00
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

org $1E811A
JSL KingDodongo_NewHealthSystem
NOP #7

org $1E86E5
KingHelmasaur_CheckBombDamage:

org $1E8385
HelmasaurKing_CheckMaskDamageFromHammer:
#_1E8385: LDA.w $0DB0,X
#_1E8388: CMP.b #$03
#_1E838A: BCS .exit

JSR KingHelmasaur_CheckBombDamage
.exit
RTS

pullpc