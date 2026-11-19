; =========================================================
; GBC Link
; =========================================================

UpdateGbcPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  JSL Tunic_GetWorn                  ; worn colour (Menu/menu_tunic.asm)
  CMP #$0001 : BEQ .blue_mail
  CMP #$0002 : BEQ .red_mail

  .loop
  ; Write both live CGRAM ($7EC6E0) and aux/fade target ($7EC4E0) so fades,
  ; spotlights, and menu/map exits never revert GBC Link to normal Link colors.
  LDA.l GameboyLinkPalette, X : STA.l $7EC6E0, X : STA.l $7EC4E0, X
  DEX : DEX : BPL .loop
  SEP #$30 ; go back to 8 bit mode
  INC.b $15 ; update the palette
  RTL
  .blue_mail
  LDX #$001E
    .loop2
    LDA.l GameboyLinkBlueMail, X : STA.l $7EC6E0, X : STA.l $7EC4E0, X
    DEX : DEX : BPL .loop2
  SEP #$30 ; go back to 8 bit mode
  INC.b $15 ; update the palette
  RTL
  .red_mail
  LDX #$001E
    .loop3
    LDA.l GameboyLinkRedMail, X : STA.l $7EC6E0, X : STA.l $7EC4E0, X
    DEX : DEX : BPL .loop3
  SEP #$30 ; go back to 8 bit mode
  INC.b $15 ; update the palette
  RTL
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
  ; Preserve the actual entrance's world, but never choose GBC base art in D8.
  JSL LinkGraphics_ApplyD8Base : BCS .return
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .return
  CMP.b #$05 : BCC .return
  +
  ; if link is in the dark world, change his sprite to the gbc one
  ; SavedWorld, not $0FFF: Sprite_Main copies it to $0FFF only once sprites
  ; run, which is after the load fade on file load and continue.
  LDA.l SavedWorld : BEQ .return
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
        LDA.b #$06 : STA.w $02B2
        LDA.b #$3B : STA.b $BC ; change link's sprite
        JSL UpdateGbcPalette
  .return
  JSL $0AFE80 ; Underworld_HandleLayerEffect
  RTL
}

; Retain GBC sprite when exiting DW dungeons or loading into the Eon Abyss
LoadOverworld_CheckForGbcLink:
{
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .refresh
  CMP.b #$05 : BCC .refresh
  +
  ; SavedWorld, not $0FFF: on file load and continue Sprite_Main has not run
  ; yet, so $0FFF is still 0 here and the spotlight showed normal Link.
  LDA.l SavedWorld : BEQ .return_lw
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .refresh
        LDA.b #$06 : STA.w $02B2
        LDA.b #$3B : STA.b $BC   ; change link's sprite
        JSL UpdateGbcPalette
        BRA .done
  .return_lw
  STZ.w $02B2
  .refresh
  JSL Palette_ArmorAndGloves
  .done
  STZ.b $B0
  STZ.b $11
  RTL
}

OverworldTransition_CheckForGbcLink:
{
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .return
  CMP.b #$05 : BCC .return
  +
  LDA.l SavedWorld : BEQ .return
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
      LDA.b #$3B : STA.b $BC   ; change link's sprite
      LDA.b #$06 : STA.w $02B2
      JSL UpdateGbcPalette
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
    ; UpdateGbcPalette updates both live ($7EC6E0) and aux ($7EC4E0) buffers.
    JSL UpdateGbcPalette
    RTL
  .vanilla
  LDY.b #$04 : LDA.b #$23
  JSL $099102 ; AncillaAdd_BunnyPoof
  RTL
}

; Kydrog's warp (Module15) with the Moon Pearl takes the .have_pearl branch, so
; MirrorWarp_PearllessArrival never runs. Module15 does not run Link_Main, so
; LinkState_GameboyForm only fires in module 09, after the white fade and
; message $35: Link arrived in the Abyss as normal Link. Set the GBC form here,
; before Module15_05 first draws Link. Replaces LDA.l $7EF357 and returns with
; that load last, so vanilla's BNE .have_pearl still reads the pearl.
MirrorWarp_PearlArrival:
{
  LDA.b $10 : CMP.b #$15 : BNE .done
  LDA.l SavedWorld : BEQ .done
  ; Without the pearl, MirrorWarp_PearllessArrival sets the form.
  LDA.l $7EF357 : BEQ .done
  ; Cosmetic GBC transitions must not replace an active mask form.
  LDA.w !CurrentMask : BEQ +
  CMP.b #$08 : BEQ .done
  CMP.b #$05 : BCC .done
  +
  LDA.w !CurrentMask : CMP.b #$05 : BEQ .done
    LDA.b #$3B : STA.b $BC
    LDA.b #$06 : STA.w $02B2
    ; UpdateGbcPalette updates both live ($7EC6E0) and aux ($7EC4E0) buffers.
    JSL UpdateGbcPalette
  .done
  LDA.l $7EF357
  RTL
}

; Module08_02_LoadAndAdvance
org $02EDC0 : JSL LoadOverworld_CheckForGbcLink ; @hook module=Masks name=LoadOverworld_CheckForGbcLink kind=jsl target=LoadOverworld_CheckForGbcLink

; Overworld_RunScrollTransition
org $02ABDA : JSL OverworldTransition_CheckForGbcLink ; @hook module=Masks name=OverworldTransition_CheckForGbcLink kind=jsl target=OverworldTransition_CheckForGbcLink

; LinkState_CrossingWorlds
org $07A9B1 : JSL LinkState_GameboyForm ; @hook module=Masks name=LinkState_GameboyForm kind=jsl target=LinkState_GameboyForm

; HandleFollowersAfterMirroring (.check_for_pearl, pearl read)
assert read4($07AB03) == $7EF357AF || read1($07AB03) == $22, "Unexpected pearl check in HandleFollowersAfterMirroring"
org $07AB03 : JSL MirrorWarp_PearlArrival ; @hook module=Masks name=MirrorWarp_PearlArrival kind=jsl target=MirrorWarp_PearlArrival expected_m=8 expected_x=8
assert pc() == $07AB07

; HandleFollowersAfterMirroring (.check_for_pearl, no pearl)
org $07AB09 : JSL MirrorWarp_PearllessArrival : NOP #4 ; @hook module=Masks name=MirrorWarp_PearllessArrival kind=jsl target=MirrorWarp_PearllessArrival expected_m=8 expected_x=8

; Module07_Underworld
org $0287A4 : JSL LinkState_GameboyInDungeonEntrance ; @hook module=Masks name=LinkState_GameboyInDungeonEntrance kind=jsl target=LinkState_GameboyInDungeonEntrance

pullpc
LinkState_GameboyForm:
{
  SEP #$30
  ; A cosmetic world transition must not replace the active Garo form.
  LDA.w !CurrentMask : CMP.b #$08 : BEQ .return
  LDA $02B2 : CMP.b #$06 : BEQ .already_gbc
    LDA.l SavedWorld : BEQ .return ; not in dark world
      .transform
      JSL PlayerTransform
      LDA #$3B : STA $BC   ; change link's sprite
      LDA #$06 : STA $02B2
      JSL UpdateGbcPalette
      BRA .return

  .already_gbc
  LDA.l SavedWorld : BNE .return ; still in the Abyss (MirrorWarp_PearllessArrival set the form)
  JSL PlayerTransform
  LDA #$10 : STA $BC
  STZ $02B2
  JSL Palette_ArmorAndGloves
  .return
  JSL $07F1E6
  RTL
}
pushpc
