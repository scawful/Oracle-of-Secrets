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

org $01EB8C
Object_KeyBlock:
{
  ; $7EF36F: Small key counter (Index into SRAM).
  LDA $7EF36F
  AND #$00FF              ; Mask high byte just in case.
  BEQ .no_keys            ; If zero, Link cannot unlock the block.

  ; Link has at least one key. 
  ; Decrement the counter and proceed to the vanilla prison door unlock routine.
  LDA $7EF36F
  DEC A
  STA $7EF36F

  BRA .vanilla_unlock     ; Hook into vanilla unlock logic.

.no_keys
  RTS

.vanilla_unlock
  ; This branch logic targets the prison door opening code at $01EB8C's offset.
  BRA $05
}

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

