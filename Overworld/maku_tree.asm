org $0EDE29
; $75E29-$75E48 DATA
{
  ; corresponding warp types that lead to special overworld areas
  dw $01EF, $01EF, $00AD, $00B9

  ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
  dw $002A, $0018, $000F, $0081

  ; Direction Link will face when he enters the special area
  dw $0008, $0008, $0008, $0008

  ; Exit value for the special area. In Hyrule Magic these are those White markers.
  dw $0180, $0181, $0182, $0189
}


; =========================================================
; Special Area Properties
; =========================================================

pushpc

; =========================================================
; Exit 180 to Master Sword Area
; =========================================================

; Sprite GFX
org $02E811 : db $0C ; PC Address $016811

; Background GFX
org $02E821 : db $2F ; PC Address $016821

; Palette
org $02E831 : db $0A ; PC Address $016831

; Sprite Palette
org $02E841 : db $01 ; PC Address $016841

; =========================================================
; Exit 181 to Bridge Area
; =========================================================

; Sprite GFX
org $02E812 : db $25 ; PC Address $016812

; Background GFX
org $02E822 : db $2F ; PC Address $016822

; Palette
org $02E832 : db $0A ; PC Address $016832

; Sprite Palette
org $02E842 : db $08 ; PC Address $016842

; =========================================================
; Exit 182 to Zora's Waterfall
; =========================================================

; Sprite GFX
org $02E813 : db $0E ; PC Address $016813

; Background GFX
org $02E823 : db $2F ; PC Address $016823

; Palette
org $02E833 : db $0A ; PC Address $016833

; Sprite Palette
org $02E843 : db $03 ; PC Address $016843

; Disable Zora's Waterfall SFX
org $02C444 : db $55 ; PC Address $014444

pullpc

; =========================================================
