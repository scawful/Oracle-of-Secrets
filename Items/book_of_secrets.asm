; =========================================================
; Book of Secrets (Reveal Secrets with Book of Mudora)
; Makes BG2 Disappear when holding L in a building
; Based on the Parallel Worlds feature
;
; Layer Flags: xxxsabcd
; (i count BG from 1 to 4 - MathOnNapkins RAM-Map counts from 0 to 3)
; s - Sprite layer enabled
; a - BG4 enabled
; b - BG3 enabled
; c - BG2 enabled
; d - (BG1 disabled) --> only works properly if the room uses the feature "BG2 on Top"
;
; Originally by XaserLE, updated by scawful

; =========================================================
; long subroutine that is executed every frame

org $068365
JSL LinkItem_SecretsBook ; overwrite it (originally JSL $099F91)

; =========================================================

pullpc

LinkItem_SecretsBook:
{
  ; Check if we are in a building
  LDA $1B : AND #$01 : BEQ .end

    ; ----------
    ; Check if we have the book of secrets
    LDA $7EF34D : CMP #$01 : BNE $0F ; if not, go to enable BG2

    ; load unfiltered joypad 1 register (AXLR|????)
    ; delete all bits except those for L
    LDA $F2	: AND #$20

    ; L button pressed? (if yes, zero flag is set)
    SEC : SBC #$20	: BNE $06	; if not, go to enable BG2

      ; load layer flags and disable BG2 (0xFD = 11111101)
      LDA $1C	: AND #$FD : BRA $04 ; go to store layer flags

    ; enable BG2 (0x02 = 00000010)
    LDA $1C	: ORA #$02 : STA $1C
    ; ----------

  .end
  JSL $099F91
  RTL
}

print  "End of Items/book_of_secrets.asm  ", pc
pushpc
