; Tail-only long-pointer version of the native09C50D..09C55D actor parser.
; Entry is JML from the current source loader, M16/X16, original phase in Y
; and pointer index in X. The original bank09 JSR return frame is untouched.
; DBR/D stay unchanged. Scratch00/01/02/05/06/07 matches native;08..0A are
; saved on the CPU stack and restored. No global WRAM or staging allocation.
assert !LYRA_CURRENT_MODE == 1 && !LYRA_CURRENT_ACTORS_ENABLED == 1
assert !LYRA_CURRENT_ACTORS_BOUND == 1, "Current actors require a reviewed source binding"
assert !LYRA_CURRENT_ACTOR_BANK != $7E && !LYRA_CURRENT_ACTOR_BANK != $7F
assert !LYRA_CURRENT_ACTOR_BANK >= 0 && !LYRA_CURRENT_ACTOR_BANK <= $FF
assert read3($09C55B) == $6010E2, "Native sprite parser return moved"

Lyra_LoadCurrentSprites:
{
  PHP
  LDA.w $040A : AND.w #$00FF
  CMP.w #$00A0 : BCS .check_upper
    BRL .legacy
  .check_upper
  CMP.w #$00C0 : BCC .selected
    BRL .legacy
  .selected
  PLP
  JSL Lyra_SpritePointer
  STA.b $00
  SEP #$20

  LDA.b $08 : PHA
  LDA.b $09 : PHA
  LDA.b $0A : PHA
  LDA.b $00 : STA.b $08
  LDA.b $01 : STA.b $09
  LDA.b #!LYRA_CURRENT_ACTOR_BANK : STA.b $0A
  LDY.w #$0000

  .next_sprite
  LDA.b [$08],Y
  CMP.b #$FF : BEQ .done
  INY : INY
  LDA.b [$08],Y
  DEY : DEY
  CMP.b #$F4 : BNE .not_boulder_spawner
    INC.w $0FFD
    INY : INY : INY
    BRA .next_sprite

  .not_boulder_spawner
  LDA.b [$08],Y : PHA
  LSR #4 : ASL #2 : STA.b $02
  INY
  LDA.b [$08],Y
  LSR #4 : CLC : ADC.b $02 : STA.b $06
  PLA
  ASL #4 : STA.b $07
  LDA.b [$08],Y
  AND.b #$0F : ORA.b $07 : STA.b $05
  INY
  LDA.b [$08],Y
  LDX.b $05
  INC : STA.l $7FDF80,X
  INY
  BRA .next_sprite

  .done
  PLA : STA.b $0A
  PLA : STA.b $09
  PLA : STA.b $08
  ; The native final LDA/CMP leaves A=FF, N=0,Z=1,C=1. PLA/STA preserve
  ; its V; reproduce A/N/Z/C after restoring scratch, including hidden B.
  LDA.b #$FF : CMP.b #$FF
  JML $09C55B ; SEP #$10 / RTS consumes the original bank09 JSR frame.

  .legacy
  PLP
  JSL Lyra_SpritePointer
  STA.b $00
  SEP #$20
  JML $09C50D ; Original parser, pointer bank and scratch lifetime unchanged.
}
