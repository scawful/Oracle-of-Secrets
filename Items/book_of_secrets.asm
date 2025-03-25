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
; d - (BG1 disabled) --> only works if the room uses the feature "BG2 on Top"
;
; Originally by XaserLE, updated by scawful

; LinkItem_Book
; Desert Book activation trigger
org $07A484 ; LDA $02ED : BNE BRANCH_BETA
  NOP #01
  JML LinkItem_BookOfSecrets
  return_pos:


pullpc
LinkItem_BookOfSecrets:
{
  ; set link in praying mode
  ; LDA.b #$02 : STA.w $037A
  ; LDA #$FF : STA $8C
  ; LDA #$00 : STA $7EE00E
  ; STZ $1D : STZ $9A
  ; STZ.w $012D

  ; Are we on the castle map?
  LDA $8A : CMP.b #$1B : BNE +
    ; Is there an overlay playing?
    LDA $04C6 : BNE +
      ; If not, start the castle entrance animation
      LDA.b #$02 : STA.w $04C6 ; Set the overlay
      STZ.b $B0 : STZ.b $C8
      ; Cache the camera
      REP #$20
      LDA.w $0618 : STA.w CameraCache
      SEP #$20
  +
  JML $07A493 ; return do not !
}


Dungeon_RevealSecrets:
{
  ; Check if we are in a building
  LDA $1B : AND #$01 : BEQ .end

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

  .end
  ; @ $068365, JSL $099F91 old hook
  RTL
}

print  "End of Items/book_of_secrets.asm  ", pc
pushpc
