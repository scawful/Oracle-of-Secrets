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


; The shared Link frame hook calls this with M/X=8 and saves A/X/Y/DBR.
; Own only the BG2 bit we actually hid, scoped to this loaded room. Never
; force BG2 on in a room where the loader intentionally disabled it.
Dungeon_RevealSecrets:
{
  LDA.b $1B : BEQ .forget
  LDA.l BookRevealState : BEQ .check
    LDA.b $A0 : CMP.l BookRevealRoom : BNE .new_room
    LDA.b $A1 : CMP.l BookRevealRoomH : BEQ .check
    .new_room
    LDA.b #$00 : STA.l BookRevealState
  .check
  LDA.b $10 : CMP.b #$07 : BNE .restore
  LDA.b $11 : BNE .restore
  LDA.l Book : CMP.b #$01 : BNE .restore
  LDA.b $F2 : AND.b #$20 : BEQ .restore
  LDA.l BookRevealState : BNE .hide
    LDA.b $1C : AND.b #$02 : BEQ .done
    LDA.b $A0 : STA.l BookRevealRoom
    LDA.b $A1 : STA.l BookRevealRoomH
    LDA.b #$01 : STA.l BookRevealState
  .hide
  LDA.b #$02 : TRB.b $1C
  RTL

  .restore
  LDA.l BookRevealState : BEQ .done
    LDA.b #$02 : TSB.b $1C
  .forget
  LDA.b #$00 : STA.l BookRevealState
  .done
  RTL
}

Book_RevealReset:
{
  LDA.b #$00 : STA.l BookRevealState
  RTL
}

%log_end("Items/book_of_secrets.asm", !LOG_ITEMS)
pushpc
