; =========================================================
; Bunny Hood Item
; Makes Link run quicker when holding
; Written by Conn (I think)
; $7EF349 bunny hood RAM slot
; 
; Adjustable speed table at the end
; db (0) $18: - Horizontal and vertical walking speed
;                 (Default = 18) 
; db (1) $10 - Diagonal walking speed
;                 (Default = 10) 
; db (2) $0a - Stairs walking speed
;                 (Default = 0A) 
; db (0c) $14 - walking through heavy grass speed (also shallow water)
;                 (Default = 14) 
; db (0d) $0d - walking diagonally through heavy grass speed (also shallow water)
;                 (Default = 0D) 
; db (10) $40 - Pegasus boots speed (Default = 40)
;
; =========================================================

UpdateBunnyPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l bunny_palette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

; =========================================================

bunny_palette:
  dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$19FD, #$14B6
  dw #$55BB, #$362A, #$3F4E, #$162B, #$22D0, #$2E5A, #$1970, #$7616
  dw #$6565, #$7271, #$2AB7, #$477E, #$1997, #$14B5, #$459B, #$69F2
  dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, #$2357, #$0000

print "End of Bunny Hood GFX             ", pc

; =========================================================
; Bunny Hood Speed Modification

org $07E330
JSR Link_CheckForBunnyRun
CLC

; org $87FD66
pullpc
Link_CheckForBunnyRun:
JSL LinkState_BunnyHoodRun
RTS
pushpc

org $20AF20
LinkState_BunnyHoodRun:
{
  CPX.b #$11 : BCS .end    ; speed value upper bound check
  LDA.w $0202              ; check the current item
  CMP.b #$16 : BNE .end    ; is it the bunny hood?
  LDA.w !CurrentMask       ; did you put it on?
  BEQ   .end
  LDA.l BunnySpeedTable, X ; load new speed values
  CLC
  RTL

.end
  LDA $87E227, X ; load native speed values
  CLC
  RTL
}

org $20AF70 ; this selects the new speed values
BunnySpeedTable:
{
  db $20, $12, $0a, $18, $10, $08, $08, $04, $0c, $10, $09, $19, $14, $0d, $10, $08, $40
}

; =========================================================
; Press R to transform into bunny form and run faster.
; =========================================================

org $07A494
LinkItem_Ether:
{
  LDA #$04 
  JSL Link_TransformMask
  RTS
}

warnpc $07A4F6