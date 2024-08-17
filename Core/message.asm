; Expanded Message Bank
; Special thanks to Zarby89

!addr = $0EF3FF
!looprun = $00
while !looprun == $00
  if read1(!addr) == $7F
    !addr #= !addr+1
    print hex(!addr) ; DEBUG LINE
    !looprun = $01

  endif
  !addr #= !addr-1
endwhile

; Temporary fix for the message bank
; ZS does not clear message data when bank is changed
; So the end of the data bank is not as easily searchable.
org $0EEE75
  db #$80

org !addr+1
  db #$80

org $0ED436
  JML MessageExpand
  NOP #$06

org $2F8000
  MessageExpand:
  LDA.b $02 : AND.w #$00FF : CMP.w #$000E : BNE + ; are we already in expanded bank?
    LDA.w #MessageExpandedData : STA.b $00
    LDA.w #MessageExpandedData>>16 : STA.b $02
    JML $0ED3FC ; go back to original read message code pointers 
  +
  ; Restore vanilla code 
  LDA.w #$DF40 : STA.b $00
  LDA.w #$000E : STA.b $02
  JML $0ED3FC ; go back to original read message code pointers 

MessageExpandedData:
  Message_18D:
    db $13, $B0, $2C, $59, $B5, $59, $BE, $2C, $2C, $1A
    db $20, $1E, $59, $35, $3C, $03, $59, $A9, $26, $59 
    db $1B, $93, $24, $75, $37, $3A, $59, $3C, $34, $36 
    db $3A, $7F
    db $FF ; end of message pointers checks

print "End of expanded dialogue          ", pc

warnpc $3CA62A
