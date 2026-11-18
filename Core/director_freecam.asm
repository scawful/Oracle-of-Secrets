; =========================================================
; Director freecam / camera hold (promo + host director)
;
; Included only when !ENABLE_DIRECTOR_FREECAM == 1 (default 0).
; Host/tools write DBG_CAM_* WRAM; this gate skips Link-follow camera
; and forces BG1/BG2 scrolls from the director targets each call.
;
; Modes ($7E0755):
;   0 = off (vanilla ApplyLinksMovementToCamera)
;   1 = hold (force scrolls from DBG_CAM_X/Y)
;   2 = freepan (hold + Select+D-pad pans 2px/frame)
; =========================================================

DBG_CAM_MODE   = $7E0755
DBG_CAM_X_LO   = $7E0756
DBG_CAM_X_HI   = $7E0757
DBG_CAM_Y_LO   = $7E0758
DBG_CAM_Y_HI   = $7E0759

BG1H_CAM       = $7E00E0
BG2H_CAM       = $7E00E2
BG1V_CAM       = $7E00E6
BG2V_CAM       = $7E00E8

pushpc

; ApplyLinksMovementToCamera entry ($07E9D3): gate to director or vanilla.
org $07E9D3 ; @hook module=Core name=DirectorCamera_Gate kind=jml target=DirectorCamera_Gate
  JML DirectorCamera_Gate

pullpc

org $3CBF00
DirectorCamera_Gate:
{
  LDA.l DBG_CAM_MODE
  BEQ .vanilla

  CMP.b #$02
  BNE .force
  JSR DirectorCamera_Freepan

.force
  JSR DirectorCamera_ForceScrolls
  RTL

.vanilla
  ; Reconstruct the four bytes overwritten by JML, then continue.
  PHB
  PHK
  PLB
  LDA.b $21
  JML $07E9D8
}

; ---------------------------------------------------------
DirectorCamera_ForceScrolls:
{
  PHP
  REP #$20
  LDA.l DBG_CAM_X_LO
  STA.l BG1H_CAM
  STA.l BG2H_CAM
  LDA.l DBG_CAM_Y_LO
  STA.l BG1V_CAM
  STA.l BG2V_CAM
  PLP
  RTS
}

; Select + D-pad pans the director camera (overworld play).
; $F0 = BYETUDLR (B,Y,Select,Start,Up,Down,Left,Right).
DirectorCamera_Freepan:
{
  PHP
  SEP #$20
  LDA.b $F0
  AND.b #$20                   ; Select
  BEQ .done

  REP #$20
  LDA.l DBG_CAM_X_LO
  STA.b $00
  LDA.l DBG_CAM_Y_LO
  STA.b $02

  SEP #$20
  LDA.b $F0
  BIT.b #$01 : BEQ .nright     ; Right
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0002 : STA.b $00
  SEP #$20
.nright
  LDA.b $F0
  BIT.b #$02 : BEQ .nleft      ; Left
  REP #$20
  LDA.b $00 : SEC : SBC.w #$0002 : STA.b $00
  SEP #$20
.nleft
  LDA.b $F0
  BIT.b #$04 : BEQ .ndown      ; Down
  REP #$20
  LDA.b $02 : CLC : ADC.w #$0002 : STA.b $02
  SEP #$20
.ndown
  LDA.b $F0
  BIT.b #$08 : BEQ .nup        ; Up
  REP #$20
  LDA.b $02 : SEC : SBC.w #$0002 : STA.b $02
  SEP #$20
.nup
  REP #$20
  LDA.b $00 : STA.l DBG_CAM_X_LO
  LDA.b $02 : STA.l DBG_CAM_Y_LO
  SEP #$20
.done
  PLP
  RTS
}
