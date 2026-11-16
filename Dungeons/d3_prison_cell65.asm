; Private paired-data prototype. The build admission checks the accepted
; room64/65 payload before enabling this hook. A valid backed-up sword restarts
; unarmed on recovery; pending hall staging remains a separate content slice.
; Native common entrance join: M8/X16, DB02, DP0. Preserve X/Y/DBR/D/SP/P
; except the original LDA80 N/Z. Replay STA45; the native next STA44 remains.
; Only active captured entrance32 is rebound; ordinary32 still enters room55.
if !ENABLE_D3_PRISON_CELL65 == 1
assert !ENABLE_D3_PRISON_SEQUENCE == 1, "Cell65 requires the prison sequence"

D3Prison_ApplyCellProfile:
{
  PHP
  REP #$20 : PHA
  SEP #$20
  LDA.l $7E0010 : CMP.b #$05 : BNE .native
  LDA.l $7E010E : CMP.b #$32 : BNE .native
  LDA.l $7E010F : BNE .native
  LDA.l CastleAmbushFlags
  AND.b #(!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped)
  CMP.b #!CastleAmbush_HasBeenCaptured : BEQ .apply
  .native
  REP #$20 : PLA
  PLP
  LDA.b #$80 : STA.b $45
  RTL
  .apply
  ; A valid reclaimed transaction restarts unarmed after death/continue while
  ; retaining its backed-up sword. Legacy malformed state is not fabricated.
  JSL D3Prison_RestartEscape
  REP #$20
  LDA.w #$0032 : STA.l $7E010E ; runtime exit bookkeeping, not saved SpawnPoint
  LDA.w #$0065 : STA.l $7E00A0 : STA.l $7E048E
  LDA.w #$0CD0
  STA.l $7E00E8 : STA.l $7E00E6 : STA.l $7E0122 : STA.l $7E0124
  ; Keep Link at screenX120 while exposing the neighboring cell to the east.
  LDA.w #$0A58
  STA.l $7E00E2 : STA.l $7E00E0 : STA.l $7E011E : STA.l $7E0120
  LDA.w #$0A00 ; room bounds stay fixed while the current scroll moves
  STA.l $7E0608 : STA.l $7E060A : STA.l $7E060C
  ; Shifted room65 layout: tile26,35, inside the shared cell.
  LDA.w #$0D18 : STA.l $7E0020
  LDA.w #$0AD0 : STA.l $7E0022
  ; Native triggers are room-local, but track current scroll pixel-for-pixel.
  ; $0618/A are vertical: shift -0040 with Y scroll.
  ; $061C/E are horizontal: retain their values because X scroll is unchanged.
  LDA.w #$0147 : STA.l $7E0618
  LDA.w #$0149 : STA.l $7E061A
  LDA.w #$00D7 : STA.l $7E061C
  LDA.w #$00D9 : STA.l $7E061E
  LDA.w #$01F8 : STA.l $7E00EC
  LDA.w #$1DEE : STA.l $7E0696
  LDA.w #$0000
  STA.l $7E0698 : STA.l $7E0610 : STA.l $7E0614 : STA.l $7E04AA
  LDA.w #$0110 : STA.l $7E0612
  LDA.w #$0100 : STA.l $7E0616
  ; Entrance32's full camera bounds translated one room row (+0200 Y).
  LDA.w #$0D00 : STA.l $7E0600
  LDA.w #$0C00 : STA.l $7E0602
  LDA.w #$0D10 : STA.l $7E0604 : STA.l $7E0606
  LDA.w #$0B00 : STA.l $7E060E
  SEP #$20
  LDA.b #$00
  STA.l $7E002F : STA.l $7E00A4 : STA.l $7E006C
  STA.l $7E00EE : STA.l $7E0476
  STA.l $7E00A9
  ; Cell65 layout7 is wide and tall; Module05 does not recalculate this.
  LDA.b #$02 : STA.l $7E00A6 : STA.l $7E00A7 : STA.l $7E00AA
  ; Oracle main02 matches the vanilla Zelda cell sheets (vanilla main04).
  LDA.b #$02 : STA.l $7E0AA1
  LDA.b #$10 : STA.l $7E0132 : STA.l $7E040C
  REP #$20 : PLA
  PLP
  LDA.b #$80 : STA.b $45
  RTL
}

pushpc
assert read4($02DADB) == $458580A9, "Cell65 native entrance preimage changed"
org $02DADB ; @hook module=Dungeons name=D3Prison_ApplyCellProfile kind=jsl target=D3Prison_ApplyCellProfile expected_m=8 expected_x=16
  JSL D3Prison_ApplyCellProfile
assert pc() == $02DADF
pullpc
endif
