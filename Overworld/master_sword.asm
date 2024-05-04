; TODO: Make the pedestal sword the lv4 sword
;       Change the dialogue for the sword pull

; =========================================================
; Get Lv2 Sword from chest
; =========================================================

; At 04/87CA, change D0 into 80
org $0987CA
db $80

; Disable wind blowing sfx:
; At 04/45D4, change 09 into 00
org $08C5D4
db $00

org $0589AF
LDY.b #$03 ; ITEMGET 03
