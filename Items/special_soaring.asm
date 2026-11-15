; Special-overworld Soaring uses the existing item-menu lifecycle and the
; native cached house-exit loader. No dialogue, teacher or map data is emitted.
; $1AF0 is the native flute cursor, borrowed only while this menu owns it:
; 80/81 = requested/current row; C0/C1 = selected pending close; 00 = idle.

SpecialSoaring_Open:
{
  ; Called by song03 after its indoor and Dark World checks, M8/X8.
  LDA.b $8A : CMP.b #$80 : BCC .done
  CMP.b #$C0 : BCS .done
  LDA.b #$80 : STA.w $1AF0
  STZ.w $0200
  STZ.w MenuScrollLevelV
  STZ.w MenuScrollLevelH
  STZ.b $E4 : STZ.b $E5
  LDA.b $10 : STA.w $010C
  LDA.b #$01 : STA.b $11
  LDA.b #$0E : STA.b $10
  .done
  RTL
}

SpecialSoaring_Complete:
{
  ; Normal Menu_Exit calls this after restoring the prior module. Do not
  ; consume the ordinary flute's numeric cursor, or another interface's state.
  PHP : SEP #$30
  LDA.b $10 : CMP.b #$0B : BNE .done
  LDA.w $1AF0 : AND.b #$FE : CMP.b #$C0 : BNE .done
  LDA.w $1AF0 : AND.b #$01 : PHA
  STZ.w $1AF0
  PLA : BEQ .garrison
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .done
  LDX.b #$32 : BRA .copy_start
  .garrison
  LDX.b #$00
  .copy_start
  PHB
  LDA.b #$7E : PHA : PLB
  REP #$20
  LDY.b #$00
  .copy
  LDA.l SpecialSoaring_Caches,X : STA.w $C140,Y
  INX #2 : INY #2 : CPY.b #$32 : BCC .copy
  ; The native cached-exit loader uses this full record, including camera,
  ; tilemap origin and fresh scroll modifiers. Reuse the existing synthetic
  ; cached-exit selector; it is not a room or an entrance allocation.
  STZ.w $0696 : STZ.w $0698
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  STZ.w $010A : STZ.w $04AA
  STZ.w $0FFF
  SEP #$20
  LDA.b #$00 : STA.l SavedWorld
  STZ.w $03F0 : STZ.b $3A
  STZ.w $0300 : STZ.w $0301 : STZ.w $037A
  STZ.b $5D : STZ.w $03EF : STZ.w $02E4
  STZ.b $B0 : STZ.b $11
  LDA.b #$80 : STA.b $13
  STZ.b $9B
  LDA.b #$08 : STA.b $10
  PLB
  PLP
  RTL
  .done
  PLP
  RTL
}

SpecialSoaring_Caches:
  ; Native $32-byte exit records; exact landing coordinates are previews.
  ; Garrison83: clear court tile(16,20), all four char collisions00.
  dw $0083,$0016,$00F0,$0688,$0140,$0700,$0083,$0790
  dw $015F,$0707,$0000,$011E,$0600,$0700,$FF20,$0200,$0500,$0800
  dw $2000,$0E1B,$0000,$0000,$0000,$0000,$0000
  ; Sky8C: existing S1 tile(14,11),37E; all four chars40 (walkable grass).
  dw $008C,$0016,$0260,$0868,$02B0,$08E0,$008C,$030C
  dw $02CF,$08E7,$0200,$031E,$0800,$0900,$0120,$0400,$0700,$0A00
  dw $2000,$1002,$0000,$0000,$0000,$0000,$0000
assert pc()-SpecialSoaring_Caches == $64

; The selected teaching action uses the native message lifecycle. No hooks or
; code are emitted until its approved message is explicitly bound in source.
incsrc "Items/sky_watch_log.asm"
