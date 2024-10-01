; ==========================================================
; Key Block Object like Link's Awakening
; Overwrites the Prison Door
;
; Author:   XaserLE
; Thanks: - PuzzleDude for finding a drawing bug and get rid of it
;			    - MathOnNapkins' Zelda Doc's
;			    - wiiqwertyuiop for his Zelda Disassembly
;
; The blocks can be opened from up- or downside only
; left and right will not work (will try to fix this in the future).
;
; The key block must always be placed on EVEN x and y.
; 00, 02, 04, 06, 08, 0A, 0C, 0E
; ==========================================================

; Big chest key for compass
org $01EC1A
  db $64

org $01EB8C
Object_KeyBlock:
{
  LDA $7EF36F			; load the small key counter
  AND #$00FF			; check if we have at least one small key (AND will not be zero)
  BEQ $4C				  ; if not (AND is zero), do nothing

  ; otherwise we will decrement the small key counter
  ; and branch to the code that opens the prison door

  LDA $7EF36F			; reload small key counter
  DEC A				    ; remove one key
  STA $7EF36F			; save the new value at small key counter position
  BRA $05				  ; branch to the code that opens the prison door
}

; Fix draw bug from floor tile left by block after unlock.
org $01EBC8
  LDA.w $9B5A, Y

org $01EBD1
  LDA.w $9B54, Y

org $01EBDA
  LDA.w $9B5C, Y

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

