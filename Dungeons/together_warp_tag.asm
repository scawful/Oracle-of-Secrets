; ==============================================================================
; Special Warp room tag
; Written by Jared_Brian_
; 11-19-2022
;
; Edit by scawful since I'm already using Holes(7) 
; ==============================================================================
; Replaces the "Holes(8)" tag in HM or ZS. Makes it so that what room the player
; will warp to when falling in a hole or using a warp pad will change depending
; on the player's position in the room. This uses the 4 "stairs" properties in 
; the room header.

; ==============================================================================

;relpaces the original tag.

; dw $CC1C ; = $CC1C* ; routine 0x3A "Holes(8)"

org $01CC1C
    JML WarpTag

org $01CC5A
    WarpTag_Return:

; ==============================================================================

pullpc ; Bank 0x2C
WarpTag:
{
    PHX

    ; Get a value 0-3 that represents where we are in the room
    ; -----------
    ; | 0  | 1  |
    ; |    |    |
    ; -----------
    ; | 2  | 3  |
    ; |    |    |
    ; -----------
    LDA $A9 : CLC : ADC $AA : TAX
    LDA $7EC001, X : STA $7EC000

    PLX
    JML WarpTag_Return
}
print  "End of together_warp_tag.asm      ", pc
pushpc

; ==============================================================================