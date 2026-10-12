; =========================================================
; Lupo pad gate (!ENABLE_LUPO_PAD_GATE)
;
; scawful 2026-10-12: "Sure pad the gate, so long as you can access the portal
; to yesterwind/swamp area for shrine of wisdom".
;
; The Hall of Secrets courtyard warp pad (LW $02) lands on Abyss $42 (Lupo
; Mountain). Until the D5 crystal is set (Crystals $7EF37A bit $04,
; !Crystal_D5_GlaciaEstate) it refuses: no warp, one error beep (SFX2 $3C,
; the failed Magic Mirror sound), no text. The check is on the current area
; only, so every other pad stays vanilla, in particular LW $25 -> DW $65
; (Yesterwind, Shrine of Wisdom). The Magic Mirror item is not gated.
;
; Pads are tiles (tile type $4B), not a table; the destination is area ^ $40
; at the same X/Y (MirrorWarp_Initialize, $02B236).
;
; Hook: TileDetect_MainHandler outdoor warp attempt, $07D151, reached only
; after the vanilla position window and the $031F/$4D checks:
;   vanilla  LDA.w $02DB : BNE $07D159 : JSR Mirror_TryToWarp
;   patched  JSL LupoPadGate_Check : NOP : JSR Mirror_TryToWarp
; Latch: NOWARP ($7E02DB) is the vanilla warp-tile latch. The refusal sets
; it; the vanilla STZ.w $02DB at $07D15C clears it on the first frame Link is
; off the pad, so the beep plays once per step onto the pad.
;
; Included from Overworld/overworld.asm (bank $34 free space) only when the
; flag is on.
; =========================================================

; ---------------------------------------------------------
; RTL = vanilla warp attempt (falls into JSR Mirror_TryToWarp).
; Latched or refused: drops the JSL return and JMLs to $07D159, the old BNE
; target (BRL .clear_tall_grass_flag).
; Entry M=8, X=8, DB=$07. Clobbers A. Keeps X, Y and the M/X widths.
LupoPadGate_Check:
{
  LDA.l NOWARP : BNE .no_warp                         ; vanilla: latched
  LDA.b $8A : CMP.b #$02 : BNE .warp                  ; only the LW $02 pad
  LDA.l Crystals : AND.b #!Crystal_D5_GlaciaEstate : BNE .warp
    LDA.b #$01 : STA.l NOWARP                         ; hold until Link steps off
    LDA.b #$3C : STA.l SFX2                           ; SFX2.3C error beep
  .no_warp
  PLA : PLA : PLA                                     ; drop the JSL return
  JML $07D159
  .warp
  RTL
}

pushpc

; TileDetect_MainHandler: LDA.w $02DB : BNE $07D159 (5 bytes).
org $07D151 ; @hook module=Overworld name=LupoPadGate kind=jsl target=LupoPadGate_Check expected_m=8 expected_x=8
  JSL LupoPadGate_Check : NOP
assert pc() == $07D156

pullpc
