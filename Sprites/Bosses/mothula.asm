;----------------------------------------------------------
; Mothula Spike Removal
;----------------------------------------------------------

pushpc

org $1EBE84
NOP #3

pullpc

;----------------------------------------------------------
; Change Mothula Damage
;----------------------------------------------------------

pushpc

org $0DB266+$88 ; Mothula Damage 1 heart 
db $14

org $0DB266+$89 ; Mothula Beam Damage 1 heart
db $14

pullpc