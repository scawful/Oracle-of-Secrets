; Expanded Message Bank
; Special thanks to Zarby89

!addr = $0EF3FF
!looprun = $00
while !looprun == $00
  if read1(!addr) == $7F
    !addr #= !addr+1
    ;print hex(!addr) ; DEBUG LINE
    !looprun = $01

  endif
  !addr #= !addr-1
endwhile

; Temporary fix for the message bank
; ZS does not clear message data when bank is changed
; So the end of the data bank is not as easily searchable.
org $0EEE75 : db $80

org !addr+1 : db $80

org $0ED436
  JML MessageExpand
  NOP #$06

org $2F8000
MessageExpand:
{
  ; are we already in expanded bank?
  LDA.b $02 : AND.w #$00FF : CMP.w #$000E : BNE +
    LDA.w #MessageExpandedData : STA.b $00
    LDA.w #MessageExpandedData>>16 : STA.b $02
    JML $0ED3FC ; go back to original read message code pointers
  +
  ; Restore vanilla code
  LDA.w #$DF40 : STA.b $00
  LDA.w #$000E : STA.b $02
  JML $0ED3FC ; go back to original read message code pointers
}

; Keep the loader below the source-sync boundary. This fails the build if a
; future loader change would overwrite the fixed expanded-message data start.
assert pc() <= $2F8026, "MessageExpand loader crossed fixed data start $2F8026"
org $2F8026
MessageExpandedData:
  ; Allocation notes retained from the former inline message table:
  ; $1BC-$1C4, $1C8-$1C9, $1CB: sequential-walker/reserved padding
  ; $1C5/$1C6/$1C7/$1CA: Maku Tree hints at 1+/3+/5+/7 crystals
  ; $1CC-$1D1: D3 prison sequence placeholders
  ; $1D2-$1D4: Gossip Stone placeholders
  ; $1D5-$1D8: Windmill Guy / Song of Storms quest
  ; $1D9-$1DF: reserved for future use
  ; $1E0-$1E4: Goron Elder; $1E5-$1E7: River Zora Elder
  ; $1E8-$1EA: Magic Bean Vendor; $1EB-$1EF: Cartographer
  ; $1F0-$1F9: Korok lore
  incsrc "Core/Generated/expanded_messages.asm"

print "End of expanded dialogue          ", pc

; Keep message source-sync inside its fixed allocation. Core/progression.asm
; owns the reserved tail beginning at $2FFE00.
assert pc() <= $2FFE00, "Expanded messages crossed fixed allocation end $2FFDFF"
