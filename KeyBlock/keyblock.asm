;===========================================================
; Key Block Object like Link's Awakening
; Overwrites the Prison Door
;
;
; WRITTEN: 	by XaserLE
; THANKS TO: -PuzzleDude for finding a drawing bug and get rid of it
;			-MathOnNapkins' Zelda Doc's
;			-wiiqwertyuiop for his Zelda Disassembly
;
; The blocks can be opened from up- or downside only, left and right will not work (will try to fix this in the future).
; The patch is "in place" so it doesn't overwrite other data or patches you added.  
;
; PuzzleDudes Note:
; The key block must always be placed on EVEN x and y.
; The even x or y is: 00, 02, 04, 06, 08, 0A, 0C, 0E, 10, 12 etc.
; HM x and y value of the position of the key block must end with: 0, 2, 4, 6, 8, A, C, E.
;===========================================================

lorom

ORG $01EB8C			; go to the code that loads the big key holding variable
LDA $7EF36F			; load the small key counter
AND #$00FF			; check if we have at least one small key (AND will not be zero)
BEQ $4C				  ; if not (AND is zero), don't do anything and especially don't give this "Eh? It's locked..." - message
                ; otherwise we will decrement the small key counter and branch to the code that opens the prison door
LDA $7EF36F			; reload small key counter
DEC A				    ; remove one key
STA $7EF36F			; save the new value at small key counter position
BRA $05				  ; branch to the code that opens the prison door

; now correct a drawing bug in the original game that causes the floor tile under the door drawed odd
ORG $01EBC8
LDA.w $9B5A,y
ORG $01EBD1
LDA.w $9B54,y
ORG $01EBDA
LDA.w $9B5C,y
; draw values representation
; 50- /
; 52- normal
; 54- x mirror
; 56- normal
; 58- x mirror
; 5A- y mirror
; 5C- xy mirror
; 5E- y mirror