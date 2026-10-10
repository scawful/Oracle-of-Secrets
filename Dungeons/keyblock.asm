; =========================================================
; Key Block Object
;
; Purpose: A puzzle block that requires a small key to unlock, 
;          similar to Link's Awakening. Overwrites the Prison Door.
;
; Author: XaserLE
; Thanks: PuzzleDude, MathOnNapkins, wiiqwertyuiop
;
; Notes: The blocks can be opened from up or down only.
;        Must be placed on EVEN x and y coordinates.
; =========================================================

; Big chest key for compass
org $01EC1A
  db $64

; Replaces the big key lock check in OpenItemChest. Runs in 16-bit A/X/Y
; with OpenItemChest's PHB, PHA and PHY on the stack, so both paths must
; leave through vanilla code that pops them (never RTS here).
org $01EB8C
Object_KeyBlock:
{
  ; $7EF36F: Small key counter (Index into SRAM).
  LDA $7EF36F
  AND #$00FF              ; Mask high byte just in case.
  BNE .has_key

  ; No key: vanilla .cannot_open_big_key_lock (PLY, PLA, PLB, CLC, RTL).
  JMP.w $EBE1

.has_key
  ; Decrement the counter, then run vanilla .open_big_key_lock
  ; (set the room flag, play the SFX, redraw the tiles).
  LDA $7EF36F
  DEC A
  STA $7EF36F
  JMP.w $EBA6
}
assert pc() <= $01EBA6, "Object_KeyBlock overruns vanilla .open_big_key_lock"

; Fix draw bug from floor tile left by block after unlock.
org $01EBC8 : LDA.w $9B5A, Y

org $01EBD1 : LDA.w $9B54, Y

org $01EBDA : LDA.w $9B5C, Y

; Draw Values
; 50 - /
; 52 - normal
; 54 - x mirror
; 56 - normal
; 58 - x mirror
; 5A - y mirror
; 5C - xy mirror
; 5E - y mirror

org $00AFE6
  dw $4936
  ; 0100 1001 0011 0110
  dw $4937
  ; 0100 1001 0011 0111
  dw $0936
  ; 0000 1001 0011 0110
  dw $0937
  ; 0000 1001 0011 0111

