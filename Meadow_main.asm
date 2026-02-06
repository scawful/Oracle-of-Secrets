; =========================================================
; Meadow of Shadows


; =========================================================
; game will switch to part 1 after your uncle lEFt the house
lorom

org $05DF12 ; @hook module=Meadow_main.asm
  JSL $04ECA0
  NOP
  NOP

org $04ECA0
  STZ.w SprState,x
  STZ $02E4     ; repeat native code overwritten by hook
  LDA #$02
  STA $7EF3C5   ; store "part 2"
  LDA #$00
  STA $7EF3CC   ; disable telepathic message
  JSL $00FC41   ; fix monsters
  RTL

; =========================================================

lorom

org $0cdc5a ; @hook module=Meadow_main.asm
JSR $ffb1

org $0cffb1

LDA #$0000     
STA $7003C5,x

LDA #$0000 
STA $7003C7,x

LDA #$00
STA $7003C8

LDA #$0101      ; 01=sword,  02 = shield to start with        
STA $700359,x   ; sword/shield save

LDY #$0000              
RTS

; =========================================================
;Start Textbox Removed
; =========================================================

org $0281F2
NOP #4

; =========================================================
;Forest Fog for Log Woods
; =========================================================

; norom $12FC3

org $02AFC3
LDX.w #$0097
LDA.b $8A
CMP.w #$0010
; skip 2
; CMP.w #$0023 ; Another foggy area if needed.
; skip 2
; CMP.w #$0024 ; Another foggy area if needed.


; =========================================================
; no glove color 
org $0DEE24
 db $80
