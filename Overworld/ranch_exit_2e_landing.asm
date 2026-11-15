; QUEUE152 private: Ranch UnderworldExitData index $2E landing (room $0003 -> OW $00)
; Matches vG near DefaultNpc (448,660). Never write shared Roms/ without scawful OK.
; Absolute orgs (asar left-to-right math would mis-eval +$2E*2).

pushpc

; exit_vram_addr[$2E] @ $02DE77 + $5C
org $02DED3
dw $11AA

; vertical_scroll[$2E] @ $02DF15 + $5C
org $02DF71
dw $0239

; horizontal_scroll[$2E] @ $02DFB3 + $5C
org $02E00F
dw $0150

; y_coordinate[$2E] @ $02E051 + $5C
org $02E0AD
dw $0289

; x_coordinate[$2E] @ $02E0EF + $5C
org $02E14B
dw $01C8

pullpc
