; =========================================================
; Toadstool Woods Inhabitants & Archery Intro Redirects
; (Included from Sprites/all_sprites.asm, Bank $32)
;
; Keeps Bank $2B untouched. Hooks:
;   1. $05:F48A (MrsSahasrahla_Idle, Sprite $78):
;      - In Room $00F3 (NE Twin Cottage East), replaces the vanilla
;        $002B..$002E chain (hijacked by Oracle story messages) with
;        approved Woodland Forager Elder dialogue !ToadstoolForager_Msg ($022A).
;      - Outside $00F3, preserves vanilla $05F48A..$05F490 behavior verbatim.
;   2. $05:8292 (ArcheryGame_Host_Idle, Sprite $65):
;      - Replaces vanilla Dark World "Light Worlder" greeting ($0085) with
;        approved Toadstool Woods Archery intro !ToadstoolArchery_Msg ($022B),
;        preserving [CH2I] ($1CE8) Play / No way flow and SprTimerA clear.
; =========================================================

!ToadstoolForager_Msg = $022A
!ToadstoolArchery_Msg = $022B

pushpc

assert read1($05F48A) == $AF, "Unexpected byte at $05F48A (MrsSahasrahla_Idle)"
assert read1($05F48E) == $C9, "Unexpected byte at $05F48E (MrsSahasrahla_Idle)"
org $05F48A ; @hook module=Sprites name=ToadstoolForager_Idle kind=jml target=ToadstoolForager_Idle
  JML ToadstoolForager_Idle
  NOP #$02

assert read1($058292) == $A9, "Unexpected byte at $058292 (ArcheryGame_Host_Idle)"
assert read1($058293) == $85, "Unexpected byte at $058293 (ArcheryGame_Host_Idle)"
assert read1($058294) == $20, "Unexpected byte at $058294 (ArcheryGame_Host_Idle)"
org $058292 ; @hook module=Sprites name=ToadstoolArchery_ShowIntro kind=jsl target=ToadstoolArchery_ShowIntro
  JSL ToadstoolArchery_ShowIntro
  NOP

pullpc

ToadstoolForager_Idle:
{
  REP #$20
  LDA.b $A0
  CMP.w #$00F3
  SEP #$20
  BNE .vanilla

  LDA.b #!ToadstoolForager_Msg&$FF
  LDY.b #!ToadstoolForager_Msg>>8
  JSL Sprite_ShowSolicitedMessage
  JML $05F49F ; MrsSahasrahla_Animate (RTS returns to Sprite_78_MrsSahasrahla)

.vanilla
  LDA.l $7EF359
  CMP.b #$02
  JML $05F490
}

ToadstoolArchery_ShowIntro:
{
  LDA.b #!ToadstoolArchery_Msg&$FF
  STA.w $1CF0
  LDA.b #!ToadstoolArchery_Msg>>8
  STA.w $1CF1
  JSL $05FA8E ; Sprite_ShowMessageMinimal
  STZ.w SprTimerA, X
  RTL
}

print "End of toadstool_inhabitants.asm   ", pc
