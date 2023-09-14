; =============================================================================
; Book of Secrets (Reveal Secrets with Book of Mudora)
; Makes BG2 Disappear when pressing X+R
; Based on the Parallel Worlds feature
;
; Bank 0x3C used for whole code
; Layer Flags: xxxsabcd (i count BG from 1 to 4 - MathOnNapkins RAM-Map counts from 0 to 3)
; s - Sprite layer enabled 
; a - BG4 enabled
; b - BG3 enabled
; c - BG2 enabled
; d - (BG1 disabled) --> only works properly if the room uses the feature "BG2 on Top"
;
; Written by XaserLE
; Edited by scawful
; =============================================================================

; =============================================================================
; code that branches behind the dungeon map load if player didn't press X
org $0288FD			  
BRA $1C				    ; make it always branch, so map isn't loaded anymore

; =============================================================================
; long subroutine that is executed every frame
org $068365			  
JSL LinkItem_SecretsBook			  ; overwrite it (originally JSL $099F91)

; =============================================================================

pullpc

LinkItem_SecretsBook:
{
  LDA $1B				    ; load data that tells us whether we are in a building or not
  AND #$01			    ; are we in a building?
  BEQ .end				    ; if not, don't use the x-button-secret

    ; ----------
    LDA $7EF34D			; load book of mudora slot
    CMP #$01			  ; do we have the moon pearl?
    BNE $0F				  ; if not, go to enable BG2
    LDA $F2				  ; load unfiltered joypad 1 register (AXLR|????)
    AND #$50 			  ; delete all bits except those for X and R
    SEC 				    ; set carry for the following subtraction
    SBC #$50			  ; X+R button pressed? (if yes, zero flag is set)
    BNE $06				  ; if not, go to enable BG2
      LDA $1C				; load layer flags
      AND #$FD			; disable BG2 (0xFD = 11111101)
      BRA $04				; go to store layer flags
    LDA $1C				  ; load layer flags
    ORA #$02			  ; enable BG2 (0x02 = 00000010)
    STA $1C				  ; store layer flags
    ; ----------

.end
  JSL $099F91			  ; at least execute original code
  RTL
}

print  "End of Items/book_of_secrets.asm  ", pc
pushpc


; =============================================================================