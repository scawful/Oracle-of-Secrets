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
  dw $7BDE, $7FFF, $2F7D, $19B5, $3A9C, $14A5, $19FD, $14B6
  dw $55BB, $362A, $3F4E, $162B, $22D0, $2E5A, $1970, $7616
  dw $6565, $7271, $2AB7, $477E, $1997, $14B5, $459B, $69F2
  dw $7AB8, $2609, $19D8, $3D95, $567C, $1890, $52F6, $2357, $0000

print "End of Bunny Hood GFX             ", pc

; =========================================================
; Bunny Hood Speed Modification

; Link_HandleVelocity_load_subvel
org $07E330
  JSR Link_CheckForBunnyRun
  CLC

pullpc
Link_CheckForBunnyRun:
  JSL LinkState_BunnyHoodRun
  RTS
pushpc

SubVelocityValues = $87E227

org $20AF20
LinkState_BunnyHoodRun:
{
  CPX.b #$11 : BCS .end    ; speed value upper bound check
  LDA.w $0202              ; check the current item
  CMP.b #$16 : BNE .end    ; is it the bunny hood?
  LDA.w !CurrentMask : CMP.b #$04 : BNE .end
        LDA.l BunnySpeedTable, X ; load new speed values
        CLC
        RTL

  .end
  LDA.l SubVelocityValues, X ; load native speed values
  CLC
  RTL
}

org $20AF70 ; this selects the new speed values
BunnySpeedTable:
{
  db $20 ; 0x00 - walking on ground
  db $12 ; 0x01 - walking diagonally
  db $0A ; 0x02 - walking on stairs
  db $18 ; 0x03 - walking on stairs diagonally, impossible to reach
  db $10 ; 0x04 - soft slipping
  db $08 ; 0x05 - soft slipping diagonally
  db $08 ; 0x06 - entering underworld/hard slipping
  db $04 ; 0x07 - hard slipping diagonally
  db $0C ; 0x08 - pushing statue
  db $10 ; 0x09 - pushing statue diagonally
  db $09 ; 0x0A - intraroom stairs
  db $19
  db $14 ; 0x0C - walking with sword out/carrying/sloshing
  db $0D ; 0x0D - walking with sword out/carrying/sloshing diagonally
  db $10 ; 0x0E - sword out/carry sloshing
  db $08 ; 0x0F - sword out/carry sloshing diagonally
  db $40 ; 0x10 - dashing
  db $2A ; 0x11 - dashing diagonally
  db $10 ; 0x12 - pushing block
  db $08 ; 0x13 - pushing block diagonally
  db $04 ; 0x14 - pulling statue/walking to triforce
  db $02 ; 0x15 - pulling statue diagonally
  db $30 ; 0x16 - slosh dashing
  db $18 ; 0x17 - slosh dashing diagonally
  db $20 ; 0x18 - dashing on ice
  db $15 ; 0x19 - dashing on ice diagonally
  db $F0 ; 0x1A -
  db $00 ; 0x1B -
  db $F0 ; 0x1C -
  db $01 ; 0x1D -
}

; =========================================================
; Press R to transform into bunny form and run faster.
; =========================================================

org $07A494
LinkItem_Ether:
{
  LDA #$04
  JSL Link_TransformMask
  LDA $0114 : CMP.b #$20 : BNE +
    LDA.b #$03 : STA $5B
    JSR $9427
  +
  RTS
}

assert pc() <= $07A4F6
