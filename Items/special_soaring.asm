; Special-overworld Soaring uses the existing item-menu lifecycle and the
; native cached house-exit loader. No dialogue, teacher or map data is emitted.
; $1AF0 is the native flute cursor, borrowed only while this menu owns it:
; $80..$85 = requested/current row; $C0..$C5 = selected pending close; $00 = idle.

!SpecialSoaring_Count    = 6
!SpecialSoaring_SkyIndex = 5

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
  LDA.b #$0B : STA.w $010C
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
  LDA.b $10 : CMP.b #$0B : BNE .early_done
  LDA.w $1AF0 : AND.b #$F8 : CMP.b #$C0 : BNE .early_done
  LDA.w $1AF0 : AND.b #$07
  STZ.w $1AF0
  CMP.b #!SpecialSoaring_Count : BCS .early_done
  CMP.b #!SpecialSoaring_SkyIndex : BNE .allowed
    PHA
    LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BEQ .sky_ok
      PLA
    .early_done
      PLP : RTL
    .sky_ok
    PLA
  .allowed
  ; Dismiss active ferry/horse/swimming state before landing on dry ground.
  PHA
if !ENABLE_KALYXO_BOAT == 1
  JSL Boat_ResetSession
endif
if !ENABLE_HORSE_FORM == 1
  LDA.w $02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
  STZ.w $0345 : STZ.w $0351
  JSL Link_ResetSwimmingState
  PLA
  PHB
  REP #$30
  AND.w #$00FF : ASL : TAX
  LDA.l SpecialSoaring_CacheOffsets,X : TAX
  SEP #$20
  LDA.b #$7E : PHA : PLB
  REP #$20
  LDY.w #$0000
  .copy
  LDA.l SpecialSoaring_Caches,X : STA.w $C140,Y
  INX #2 : INY #2 : CPY.w #$0032 : BCC .copy
  ; The native cached-exit loader uses this full record, including camera,
  ; tilemap origin and fresh scroll modifiers. Reuse the existing synthetic
  ; cached-exit selector; it is not a room or an entrance allocation.
  STZ.w $0696 : STZ.w $0698
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  STZ.w $010A : STZ.w $04AA
  STZ.w $0FFF
  SEP #$30
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
}

SpecialSoaring_CacheOffsets:
  dw $0000, $0032, $0064, $0096, $00C8, $00FA

SpecialSoaring_Caches:
  ; Native $32-byte exit records consumed by LoadCachedEntranceProperties ($02E5D4).
  ; 0: Garrison ($83, 32x64 Tall): bounds $0000..$031E / $0600..$0700, court tile (16,20) walkable 00.
  dw $0083,$0016,$00F0,$0688,$0140,$0700,$0083,$0790
  dw $015F,$0707,$0000,$031E,$0600,$0700,$FF20,$0400,$0500,$0800
  dw $2000,$0E24,$0000,$0000,$0000,$0000,$0000
  ; 1: Zora Coast ($A0, 64x32 Wide): origin ($0000,$0800), cache (40,17) -> lands (40,18) 3x3 walkable 48.
  dw $00A0,$0016,$08C0,$0208,$0910,$0280,$00A0,$0640
  dw $092F,$0287,$0800,$091E,$0000,$0300,$0720,$0A00,$FF00,$0400
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 2: Deku Grove ($A8, 64x32 Wide): origin ($0000,$0A00), cache (19,16) -> lands (19,17) 3x3 walkable 00.
  dw $00A8,$0016,$0AB0,$00B8,$0B00,$0130,$00A8,$0596
  dw $0B1F,$0137,$0A00,$0B1E,$0000,$0300,$0920,$0C00,$FF00,$0400
  dw $2000,$0B30,$0000,$0000,$0000,$0000,$0000
  ; 3: Goron Coast ($B0, 64x64 Large): origin ($0000,$0C00), cache (31,8) -> lands (31,9) 7x6 flat plateau 00.
  dw $00B0,$0016,$0C30,$0178,$0C80,$01F0,$00B0,$01AE
  dw $0C9F,$01F7,$0C00,$0F1E,$0000,$0300,$0B20,$1000,$FF00,$0400
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 4: Courage Isle ($A6, 64x64 Large): origin ($0C00,$0800), cache (35,28) -> lands (35,29) 3x3 walkable 00.
  dw $00A6,$0016,$0970,$0DB8,$09C0,$0E30,$00A6,$0BB6
  dw $09DF,$0E37,$0800,$0B1E,$0C00,$0F00,$0720,$0C00,$0B00,$1000
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 5: Sky ($8C, 32x32 Small): S1 tile (14,11), all four chars 40 (walkable grass); gated on SkySoaringLearned.
  dw $008C,$0016,$0260,$0868,$02B0,$08E0,$008C,$030C
  dw $02CF,$08E7,$0200,$031E,$0800,$0900,$0120,$0400,$0700,$0A00
  dw $2000,$1002,$0000,$0000,$0000,$0000,$0000
assert pc()-SpecialSoaring_Caches == $012C

; The selected teaching action uses the native message lifecycle. No hooks or
; code are emitted until its approved message is explicitly bound in source.
incsrc "Items/sky_watch_log.asm"
