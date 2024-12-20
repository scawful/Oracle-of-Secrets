; ==========================================================
; Special Warp room tag
; Written by Jared_Brian_
; 11-19-2022
;
; Makes it so that what room the player will warp to when
; falling in a hole or using a warp pad will change
; depending on the player's position in the room. This uses
; the 4 "stairs" properties in the room header.

org $01CC1C : JML WarpTag

WarpTag_Return = $01CC5A

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

