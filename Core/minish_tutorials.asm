; Source-built replacements for the three Minish walk-on tutorials.
; Included after the expanded bank's $FF, so the sequential walker ignores
; this helper/data and all existing expanded message IDs remain unchanged.
; Core/messages.org and Core/messages_es.org retain the readable references.

pushpc
; Replace only the original CreateMessagePointers epilogue. The routine has
; already built every three-byte pointer, with M/X=16 and the caller DBR saved.
assert read4($0ED447) == $6BAB30E2, "CreateMessagePointers epilogue moved"
org $0ED447 ; @hook module=Core name=MinishTutorialPointers kind=jml target=MinishTutorialPointers expected_m=16 expected_x=16 expected_exit_m=8 expected_exit_x=8
  JML MinishTutorialPointers
assert pc() == $0ED44B, "Minish tutorial hook exceeded vanilla epilogue"
pullpc

MinishTutorialPointers:
{
  ; Preserve the accumulator; X/Y and the direct-page scratch stay untouched.
  ; RenderText_ParseMessage reads the offset at +0 and bank at +2, then uses
  ; LDA [$04],Y ($0EC50B), so each override must replace all three bytes.
  PHA
  LDA.w #MinishTutorial_038 : STA.l $7F71C0+($038*3)
  LDA.w #MinishTutorial_15B : STA.l $7F71C0+($15B*3)
  LDA.w #MinishTutorial_15C : STA.l $7F71C0+($15C*3)
  SEP #$20
  LDA.b #MinishTutorial_038>>16 : STA.l $7F71C2+($038*3)
  LDA.b #MinishTutorial_15B>>16 : STA.l $7F71C2+($15B*3)
  LDA.b #MinishTutorial_15C>>16 : STA.l $7F71C2+($15C*3)
  REP #$20
  PLA
  ; Replay SEP #$30 / PLB / RTL; PLB consumes the original routine's PHB.
  SEP #$30
  PLB
  RTL
}

MinishTutorial_038:
; Shrine of Origins[2][3][K][V]The True Hero will reveal the[V]path forward by stepping onto[V]the magical pot.
  db $12, $21, $2B, $22, $27, $1E, $59, $28, $1F, $59, $0E, $2B, $22, $20, $22, $27
  db $2C, $75, $76, $7E, $73, $13, $21, $1E, $59, $13, $2B, $2E, $1E, $59, $07, $1E
  db $2B, $28, $59, $30, $22, $25, $25, $59, $2B, $1E, $2F, $1E, $1A, $25, $59, $2D
  db $21, $1E, $73, $29, $1A, $2D, $21, $59, $1F, $28, $2B, $30, $1A, $2B, $1D, $59
  db $1B, $32, $59, $2C, $2D, $1E, $29, $29, $22, $27, $20, $59, $28, $27, $2D, $28
  db $73, $2D, $21, $1E, $59, $26, $1A, $20, $22, $1C, $1A, $25, $59, $29, $28, $2D
  db $41, $7F

MinishTutorial_15B:
; Oh? Who are you, stranger?[2]This place is the Eon Abyss,[3]a dark reflection of Kalyxo.[K][V]Evil magic has twisted it[V]into something sinister and[V]dangerous.[K][V]The Golden Power here can[V]change your form to match[V]your heart and mind.[K][V]I am always changing my mind,[V]so I turned into a ball.[...][V]But if you find a magic stump,[K][V]step onto it to shrink[V]and navigate through small[V]spaces in this dark world.[K]
  db $0E, $21, $3F, $59, $16, $21, $28, $59, $1A, $2B, $1E, $59, $32, $28, $2E, $42
  db $59, $2C, $2D, $2B, $1A, $27, $20, $1E, $2B, $3F, $75, $13, $21, $22, $2C, $59
  db $29, $25, $1A, $1C, $1E, $59, $22, $2C, $59, $2D, $21, $1E, $59, $04, $28, $27
  db $59, $00, $1B, $32, $2C, $2C, $42, $76, $1A, $59, $1D, $1A, $2B, $24, $59, $2B
  db $1E, $1F, $25, $1E, $1C, $2D, $22, $28, $27, $59, $28, $1F, $59, $0A, $1A, $25
  db $32, $31, $28, $41, $7E, $73, $04, $2F, $22, $25, $59, $26, $1A, $20, $22, $1C
  db $59, $21, $1A, $2C, $59, $2D, $30, $22, $2C, $2D, $1E, $1D, $59, $22, $2D, $73
  db $22, $27, $2D, $28, $59, $2C, $28, $26, $1E, $2D, $21, $22, $27, $20, $59, $2C
  db $22, $27, $22, $2C, $2D, $1E, $2B, $59, $1A, $27, $1D, $73, $1D, $1A, $27, $20
  db $1E, $2B, $28, $2E, $2C, $41, $7E, $73, $13, $21, $1E, $59, $06, $28, $25, $1D
  db $1E, $27, $59, $0F, $28, $30, $1E, $2B, $59, $21, $1E, $2B, $1E, $59, $1C, $1A
  db $27, $73, $1C, $21, $1A, $27, $20, $1E, $59, $32, $28, $2E, $2B, $59, $1F, $28
  db $2B, $26, $59, $2D, $28, $59, $26, $1A, $2D, $1C, $21, $73, $32, $28, $2E, $2B
  db $59, $21, $1E, $1A, $2B, $2D, $59, $1A, $27, $1D, $59, $26, $22, $27, $1D, $41
  db $7E, $73, $08, $59, $1A, $26, $59, $1A, $25, $30, $1A, $32, $2C, $59, $1C, $21
  db $1A, $27, $20, $22, $27, $20, $59, $26, $32, $59, $26, $22, $27, $1D, $42, $73
  db $2C, $28, $59, $08, $59, $2D, $2E, $2B, $27, $1E, $1D, $59, $22, $27, $2D, $28
  db $59, $1A, $59, $1B, $1A, $25, $25, $41, $43, $73, $01, $2E, $2D, $59, $22, $1F
  db $59, $32, $28, $2E, $59, $1F, $22, $27, $1D, $59, $1A, $59, $26, $1A, $20, $22
  db $1C, $59, $2C, $2D, $2E, $26, $29, $42, $7E, $73, $2C, $2D, $1E, $29, $59, $28
  db $27, $2D, $28, $59, $22, $2D, $59, $2D, $28, $59, $2C, $21, $2B, $22, $27, $24
  db $73, $1A, $27, $1D, $59, $27, $1A, $2F, $22, $20, $1A, $2D, $1E, $59, $2D, $21
  db $2B, $28, $2E, $20, $21, $59, $2C, $26, $1A, $25, $25, $73, $2C, $29, $1A, $1C
  db $1E, $2C, $59, $22, $27, $59, $2D, $21, $22, $2C, $59, $1D, $1A, $2B, $24, $59
  db $30, $28, $2B, $25, $1D, $41, $7E, $7F

MinishTutorial_15C:
; You didn't change your shape?[2]Well, don't forget, if you want[3]to get through tight spaces, [K][V]step onto a magic stump![V]Step off and back on to grow.
  db $18, $28, $2E, $59, $1D, $22, $1D, $27, $51, $2D, $59, $1C, $21, $1A, $27, $20
  db $1E, $59, $32, $28, $2E, $2B, $59, $2C, $21, $1A, $29, $1E, $3F, $75, $16, $1E
  db $25, $25, $42, $59, $1D, $28, $27, $51, $2D, $59, $1F, $28, $2B, $20, $1E, $2D
  db $42, $59, $22, $1F, $59, $32, $28, $2E, $59, $30, $1A, $27, $2D, $76, $2D, $28
  db $59, $20, $1E, $2D, $59, $2D, $21, $2B, $28, $2E, $20, $21, $59, $2D, $22, $20
  db $21, $2D, $59, $2C, $29, $1A, $1C, $1E, $2C, $42, $59, $7E, $73, $2C, $2D, $1E
  db $29, $59, $28, $27, $2D, $28, $59, $1A, $59, $26, $1A, $20, $22, $1C, $59, $2C
  db $2D, $2E, $26, $29, $3E, $73, $12, $2D, $1E, $29, $59, $28, $1F, $1F, $59, $1A
  db $27, $1D, $59, $1B, $1A, $1C, $24, $59, $28, $27, $59, $2D, $28, $59, $20, $2B
  db $28, $30, $41, $7F

; Share the existing dialogue allocation; progression owns $2FFE00 onward.
assert pc() <= $2FFE00, "Minish tutorials crossed dialogue allocation"
