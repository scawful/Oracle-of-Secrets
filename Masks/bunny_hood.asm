;===========================================================
; Bunny Hood Item
; Makes Link run quicker when holding
; Written by Conn (I think)
; $7EF349 bunny hood RAM slot
; 
; Adjustable speed table at the end
;   db (0) $18: - Horizontal and vertical walking speed 
;                 (Default = 18) 
;   db (1) $10 - Diagonal walking speed 
;                 (Default = 10) 
;   db (2) $0a - Stairs walking speed 
;                 (Default = 0A) 
;   db (0c) $14 - walking through heavy grass speed (also shallow water) 
;                 (Default = 14) 
;   db (0d) $0d - walking diagonally through heavy grass speed (also shallow water) 
;                 (Default = 0D) 
;   db (10) $40 - Pegasus boots speed (Default = 40)
;
; TODO: draw sprite on link
;===========================================================

org $07A494
LinkItem_Ether:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2
  
  LDA $02B2 : CMP #$04 : BEQ .unequip ; is the hood already on?
  LDA #$37 : STA $BC                   ; change link's sprite 
  LDA #$04 : STA $02B2
  BRA .return
.unequip
  LDA #$10 : STA $BC : STZ $02B2        ; take the hood off

.return
  CLC
  RTS
}

org $378000
incbin bunny_link.4bpp


org $87E330
JSR $FD66
CLC

org $87FD66
JSL $20AF20
RTS

org $20AF20
CPX.b #$11 : BCS end  ; speed value upper bound check
LDA.w $0202           ; check the current item
CMP.b #$16 : BNE end  ; is it the bunny hood?
LDA.w $02B2           ; did you put it on?
BEQ end
LDA $20AF70,X         ; load new speed values
CLC
RTL

end: {
  LDA $87E227,X       ; load native speed values
  CLC
  RTL
}

org $20AF70           ; this selects the new speed values
db $20, $12, $0a, $18, $10, $08, $08, $04, $0c, $10, $09, $19, $14, $0d, $10, $08, $40