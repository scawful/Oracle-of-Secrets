; =========================================================
; Book of Secrets (Reveal Secrets with Book of Mudora)
; Interacts with SpecialObject ID 0x32 
; Makes objects disappear when using the book

org $07A45E
EXIT_07A45E:

org $07AA6C
Link_PerformDesertPrayer:

; Restored vanilla book of mudora code
; TODO: Update to work with special object
org $07A471
LinkItem_Book:
{
    BIT.b $3A : BVS .exit
    LDA.b $6C : BNE EXIT_07A45E
    JSR Link_CheckNewY_ButtonPress : BCC .exit

    LDA.b $3A : AND.b #$BF : STA.b $3A
    LDA.w $02ED : BNE .do_prayer
    LDA.b #$3C : JSR PlaySFX_Set2 ; SFX2.3C

    BRA .exit

  .do_prayer
    BRL Link_PerformDesertPrayer

  .exit
    RTS
}
warnpc $07A494

; =========================================================
; Makes BG2 Disappear when holding L in a building
; Based on the Parallel Worlds feature
;
; Layer Flags: xxxsabcd 
; (i count BG from 1 to 4 
;   - MathOnNapkins RAM-Map counts from 0 to 3)
; s - Sprite layer enabled 
; a - BG4 enabled
; b - BG3 enabled
; c - BG2 enabled
; d - (BG1 disabled) --> only works properly if the room 
;                         uses the feature "BG2 on Top"
;
; Originally by XaserLE, updated by scawful
; Note: No longer used as part of Book of Secrets globally
; Likely will be reused for specific events where we can
; ensure the BG2 will have something secret to show,
; rather than allowing the ability to be used anywhere.

; =========================================================
; long subroutine that is executed every frame

org $068365			  
JSL LinkItem_SecretsBook ; hook JSL $099F91

; =========================================================

pullpc

LinkItem_SecretsBook:
{
  ; Check if we are in a building
  LDA $1B : AND #$01 : BEQ .end

    ; ----------
    ; TODO: Add a new condition, such as a RoomTag check

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
  JSL $099F91			  ; restore original code
  RTL
}

print  "End of Items/book_of_secrets.asm  ", pc
pushpc
