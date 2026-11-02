; =========================================================
; GBC Link
; =========================================================

UpdateGbcPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  LDA $7EF35B : AND.w #$00FF : CMP #$0001 : BEQ .blue_mail
  LDA $7EF35B : AND.w #$00FF : CMP #$0002 : BEQ .red_mail

  .loop
  LDA.l GameboyLinkPalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop
  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
  .blue_mail
  LDX #$001E
    .loop2
    LDA.l GameboyLinkBlueMail, X : STA $7EC6E0, X
    DEX : DEX : BPL .loop2
  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
  .red_mail
  LDX #$001E
    .loop3
    LDA.l GameboyLinkRedMail, X : STA $7EC6E0, X
    DEX : DEX : BPL .loop3
  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

GameboyLinkPalette:
  dw $0000, $7FFF, $237E, $B711, $369E, $14A5, $01FF, $1078
  dw $46FF, $22A2, $3B68, $0A4A, $12EF, $2A5C, $1571, $7A18

GameboyLinkBlueMail:
  dw $0000, $7FFF, $237E, $B711, $369E, $14A5, $01FF, $1078
  dw $46FF, $4D25, $3B68, $0A4A, $12EF, $2A5C, $1571, $7A18

GameboyLinkRedMail:
  dw $0000, $7FFF, $237E, $B711, $369E, $14A5, $01FF, $1078
  dw $46FF, $081D, $3B68, $0A4A, $12EF, $2A5C, $1571, $7A18

LinkState_GameboyInDungeonEntrance:
{
if !ENABLE_MASK_R_BINDING == 1
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .return
  CMP.b #$05 : BCC .return
  +
endif
  print pc
  ; if link is in the dark world, change his sprite to the gbc one
  LDA $0FFF : CMP #$00 : BEQ .return
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
        JSL UpdateGbcPalette
        LDA #$3B : STA $BC ; change link's sprite
  .return
  JSL $0AFE80 ; Underworld_HandleLayerEffect
  RTL
}

; Retain GBC sprite when exiting DW dungeons
LoadOverworld_CheckForGbcLink:
{
if !ENABLE_MASK_R_BINDING == 1
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .return
  CMP.b #$05 : BCC .return
  +
endif
  LDA $0FFF : BEQ .return_lw
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
        LDA.b #$06 : STA $02B2
        LDA.b #$3B : STA $BC   ; change link's sprite
        JSL UpdateGbcPalette
        JMP .return
  .return_lw
  STZ.w $02B2
  .return
  JSL Palette_ArmorAndGloves
  STZ.b $B0
  STZ.b $11
  RTL
}

OverworldTransition_CheckForGbcLink:
{
if !ENABLE_MASK_R_BINDING == 1
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .return
  CMP.b #$05 : BCC .return
  +
endif
  LDA $0FFF : BEQ .return
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
      LDA #$3B : STA $BC   ; change link's sprite
      LDA #$06 : STA $02B2
      JSL Palette_ArmorAndGloves
  .return
  JSL Link_HandleMovingAnimation_FullLongEntry
  RTL
}

; Module15 queues the pearl-less poof (ancilla $23) in s03, but ancillae only
; run once Sprite_Main resumes in s06, after message $35. Until then Link is
; drawn with $02E0=0 and $BC=$10, and LinkState_GameboyForm poofs again in
; module 09. On the warp into the Abyss, set the arrival form directly.
MirrorWarp_PearllessArrival:
{
  LDA.b $10 : CMP.b #$15 : BNE .vanilla
  LDA.l $7EF3CA : BEQ .vanilla
    LDA.b #$01 : STA.w $02E0 : STA.b $56
    LDA.b #$3B : STA.b $BC
    LDA.b #$06 : STA.w $02B2
    JSL UpdateGbcPalette
    ; The warp's white filter fades toward the aux palette; keep it in step.
    REP #$30
    LDX.w #$001E
    .copy
    LDA.l $7EC6E0, X : STA.l $7EC4E0, X
    DEX : DEX : BPL .copy
    SEP #$30
    RTL
  .vanilla
  LDY.b #$04 : LDA.b #$23
  JSL $099102 ; AncillaAdd_BunnyPoof
  RTL
}

; Module08_02_LoadAndAdvance
org $02EDC0 : JSL LoadOverworld_CheckForGbcLink ; @hook module=Masks name=LoadOverworld_CheckForGbcLink kind=jsl target=LoadOverworld_CheckForGbcLink

; Overworld_RunScrollTransition
org $02ABDA : JSL OverworldTransition_CheckForGbcLink ; @hook module=Masks name=OverworldTransition_CheckForGbcLink kind=jsl target=OverworldTransition_CheckForGbcLink

; LinkState_CrossingWorlds
org $07A9B1 : JSL LinkState_GameboyForm ; @hook module=Masks name=LinkState_GameboyForm kind=jsl target=LinkState_GameboyForm

; HandleFollowersAfterMirroring (.check_for_pearl, no pearl)
org $07AB09 : JSL MirrorWarp_PearllessArrival : NOP #4 ; @hook module=Masks name=MirrorWarp_PearllessArrival kind=jsl target=MirrorWarp_PearllessArrival expected_m=8 expected_x=8

; Module07_Underworld
org $0287A4 : JSL LinkState_GameboyInDungeonEntrance ; @hook module=Masks name=LinkState_GameboyInDungeonEntrance kind=jsl target=LinkState_GameboyInDungeonEntrance

pullpc
LinkState_GameboyForm:
{
  SEP #$30
if !ENABLE_MASK_R_BINDING == 1
  ; A cosmetic world transition must not replace the active Garo form.
  LDA.w !CurrentMask : CMP.b #$08 : BEQ .return
endif
  LDA $02B2 : CMP.b #$06 : BEQ .already_gbc
    LDA $0FFF : BEQ .return ; not in dark world
      .transform
      JSL PlayerTransform
      LDA #$3B : STA $BC   ; change link's sprite
      LDA #$06 : STA $02B2
      JSL UpdateGbcPalette
      BRA .return

  .already_gbc
  LDA $0FFF : BNE .return ; still in the Abyss (MirrorWarp_PearllessArrival set the form)
  JSL PlayerTransform
  LDA #$10 : STA $BC
  STZ $02B2
  JSL Palette_ArmorAndGloves
  .return
  JSL $07F1E6
  RTL
}
pushpc
