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
assert GameboyLinkBlueMail == GameboyLinkPalette+$20, "GBC Blue Mail table offset drifted"
assert GameboyLinkRedMail == GameboyLinkPalette+$40, "GBC Red Mail table offset drifted"

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
  ; Note: Module07_Underworld ($0287A4) calls this every frame indoors. Guard
  ; against re-applying palette/shield sync once GBC form is already active;
  ; LW/DW dungeon loads already sync shield tiles & palette via $02C64B
  ; (Palettes_Load_Shield -> MirrorShield_LoadColor8).
  LDA.l SavedWorld : BNE .dark_world
    ; Light World (including Start From Kalyxo): clear stale GBC form once,
    ; otherwise perform zero per-frame palette/VRAM work.
    LDA.w !CurrentMask : CMP.b #$06 : BEQ .restore_lw
    LDA.b $BC : CMP.b #$3B : BNE .return
  .restore_lw
    STZ.w $02B2
    LDA.b #$10 : STA.b $BC
    JSL $1BEDF9                         ; Palette_ArmorAndGloves (mask-aware)
    JSL ShieldWorld_SyncBoth
    BRA .return
  .dark_world
    LDA.w !CurrentMask : CMP.b #$05 : BEQ .return
    CMP.b #$06 : BNE .apply_gbc
    LDA.b $BC : CMP.b #$3B : BEQ .return
  .apply_gbc
    LDA.b #$06 : STA.w $02B2
    LDA.b #$3B : STA.b $BC ; change link's sprite
    JSL UpdateGbcPalette
    JSL ShieldWorld_SyncBoth
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
  JSL ShieldWorld_SyncBoth
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
    JSL ShieldWorld_SyncBoth
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
  JSL ShieldWorld_SyncBoth
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
    JSL ShieldWorld_SyncBoth
  .done
  LDA.l $7EF357
  RTL
}

; =========================================================
; File Select: clean Link reset + per-slot Abyss-locked GBC preview
; =========================================================

; Carry Set if SRAM slot X ($0000/$0500/$0A00) is valid and Abyss-locked
; (SavedWorld != 0 and GameState < !GameState_FaroreRescued).
; Entry: M=8, X=16, X=slot SRAM offset. Preserves X, Y, M/X; clobbers A.
FileSelect_IsSlotGbcEligible:
{
  LDA.l $7003E5, X : CMP.b #$AA : BNE .normal
  LDA.l $7003E6, X : CMP.b #$55 : BNE .normal
  LDA.l $7003CA, X : BEQ .normal
  LDA.l $7003C5, X : CMP.b #!GameState_FaroreRescued : BCS .normal
  SEC
  RTL
.normal
  CLC
  RTL
}

; Hook at $0CCDEA (FileSelect_InitializeGFX, replaces JSL Intro_InitializeSRAMWRAM).
; Resets active mask/Link bank ($02B2=0, $BC=$10) and uploads static standing-down
; GBC tiles to OBJ Page 1 ($5800/$5900, tiles $80-$83/$90-$93) for Abyss-locked slots.
; Entry/Exit: M=8, X=8, DB preserved. Force blank is active ($13=$80).
FileSelect_InitGbcAssets:
{
  JSL $028054                         ; Intro_InitializeSRAMWRAM (exits SEP #$30)
  STZ.w $02B2
  LDA.b #$10 : STA.b $BC

  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB              ; DB=$00 for PPU/DMA registers
  - : LDA.w $4212 : BPL -             ; wait for vblank, then end of vblank
  - : LDA.w $4212 : BMI -             ; so NMI cannot race VMADDR/VMDATA
  LDA.b #$80 : STA.w $2100            ; force blank
  STA.w $2115                         ; VMAIN: word increment

  LDX.b #$00
.slice
  REP #$20
  LDA.l FileSelect_GbcTileSlices+0, X : STA.w $2116 ; VMADDR
  LDA.l FileSelect_GbcTileSlices+2, X : STA.w $4302 ; DMA0ADDRL/H
  LDA.w #$0040 : STA.w $4305          ; 64 bytes (2 4BPP tiles)
  LDA.w #$1801 : STA.w $4300          ; A->B, 2 regs ($2118/$2119)
  SEP #$20
  LDA.b #GbcLinkGraphics>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B            ; MDMAEN ch0
  INX : INX : INX : INX
  CPX.b #(FileSelect_GbcTileSlices_End-FileSelect_GbcTileSlices) : BNE .slice

  PLB : PLP
  RTL
}

FileSelect_GbcTileSlices:
  dw $5800, GbcLinkGraphics+$00C0     ; GBC Head top (tiles $80,$81 Page 1)
  dw $5900, GbcLinkGraphics+$02C0     ; GBC Head bot (tiles $90,$91 Page 1)
  dw $5820, GbcLinkGraphics+$3D00     ; GBC Body top (tiles $82,$83 Page 1)
  dw $5920, GbcLinkGraphics+$3F00     ; GBC Body bot (tiles $92,$93 Page 1)
FileSelect_GbcTileSlices_End:

; Hook at $0CCE06 (FileSelect_EraseTriforce, replaces JSL Palettes_LoadForFileSelect).
; Runs vanilla/tunic-aware slot palettes, then replaces Abyss-locked slots' Link OBJ
; palettes (0/2/4 -> $7EC602/$7EC642/$7EC682 + aux) with GameboyLinkPalette*.
; Entry/Exit: M=8, X=8, DB preserved.
FileSelect_LoadPalettes:
{
  JSL $1BEF96                         ; Palettes_LoadForFileSelect (exits SEP #$30)
  PHP : PHB
  SEP #$20
  PHK : PLB                           ; DB=$3B for bank-$3B tables (LoROM mirrors $7E:0000-$1FFF)
  REP #$30
  LDY.w #$0000                        ; slot word index: 0, 2, 4
.slot_loop
  LDA.w FileSelect_SlotSramOffsets, Y
  TAX
  SEP #$20
  JSL FileSelect_IsSlotGbcEligible
  REP #$20
  BCC .next_slot

  PHY
  TYA : JSR FileSelect_GetSlotTunic   ; A = 0, 1, or 2 (green/blue/red worn tunic)
  ASL #5                              ; *$20 -> palette offset
  PHA
  LDA $03, S                          ; saved slot word index (0, 2, 4)
  TAX
  LDA.w FileSelect_SlotCgramOffsets, X
  TAX                                 ; dest CGRAM offset ($0000/$0040/$0080)
  PLY                                 ; src offset ($00/$20/$40)
  LDA.w #$000F                        ; 15 colors (indices 1..15)
.copy_color
  PHA
  LDA.w GameboyLinkPalette+2, Y
  STA.l $7EC402, X
  STA.l $7EC602, X
  INY #2 : INX #2
  PLA
  DEC A : BNE .copy_color
  PLY

.next_slot
  INY #2
  CPY.w #$0006 : BNE .slot_loop
  PLB : PLP
  RTL
}

; Entry: A = slot word index (0, 2, 4), M=16, X=16.
; Exit:  A = worn tunic (0=green, 1=blue, 2=red), X/Y preserved.
FileSelect_GetSlotTunic:
{
  CMP.w #$0002 : BEQ .slot2
  CMP.w #$0004 : BEQ .slot3
  JSL Tunic_FileSelectSlot1
  RTS
.slot2
  JSL Tunic_FileSelectSlot2
  RTS
.slot3
  JSL Tunic_FileSelectSlot3
  RTS
}

FileSelect_SlotSramOffsets:
  dw $0000, $0500, $0A00

FileSelect_SlotCgramOffsets:
  dw $0000, $0040, $0080

; Hook at $0CD774 (FileSelect_DrawLink, replaces 21 bytes $0CD774..$0CD788).
; Draws normal Link ($00/$02, N=0) or isolated GBC Link ($80/$82, N=1) per slot.
; Entry: M=8, X=8, X=OAM offset, Y=slot index (0..2), $0E/$0F=SRAM slot offset.
; Exit:  M=8, X=8, X/Y/DB preserved.
FileSelect_SelectSlotLinkSprite:
{
  PHX
  REP #$10
  LDX.b $0E
  JSL FileSelect_IsSlotGbcEligible
  SEP #$10
  PLX
  BCS .gbc
    LDA.b #$00 : STA.w $0802, X
    LDA.b #$02 : STA.w $0806, X
    TYA : ASL #2 : ORA.b #$30 : STA.w $0803, X
    ORA.b #$40 : STA.w $0807, X
    RTL
.gbc
  LDA.b #$80 : STA.w $0802, X
  LDA.b #$82 : STA.w $0806, X
  TYA : ASL #2 : ORA.b #$31 : STA.w $0803, X
  ORA.b #$40 : STA.w $0807, X
  RTL
}
assert pc() <= $3BF400, "GBC form exceeded Bank $3B limit before $3BF400"

; FileSelect_InitializeGFX (Intro_InitializeSRAMWRAM call)
assert read4($0CCDEA) == $02805422 || read1($0CCDEA) == $22, "Unexpected Intro_InitializeSRAMWRAM call in FileSelect_InitializeGFX"
org $0CCDEA : JSL FileSelect_InitGbcAssets ; @hook module=Masks name=FileSelect_InitGbcAssets kind=jsl target=FileSelect_InitGbcAssets expected_m=8 expected_x=8 protected_size=4
assert pc() == $0CCDEE

; FileSelect_EraseTriforce (Palettes_LoadForFileSelect call)
assert read4($0CCE06) == $1BEF9622 || read1($0CCE06) == $22, "Unexpected Palettes_LoadForFileSelect call in FileSelect_EraseTriforce"
org $0CCE06 : JSL FileSelect_LoadPalettes ; @hook module=Masks name=FileSelect_LoadPalettes kind=jsl target=FileSelect_LoadPalettes expected_m=8 expected_x=8 protected_size=4
assert pc() == $0CCE0A

; FileSelect_DrawLink (Link tile + OAM attr selection per slot)
assert read4($0CD774) == $029D00A9 || read1($0CD774) == $22, "Unexpected FileSelect_DrawLink tile store"
org $0CD774 : JSL FileSelect_SelectSlotLinkSprite : NOP #17 ; @hook module=Masks name=FileSelect_SelectSlotLinkSprite kind=jsl target=FileSelect_SelectSlotLinkSprite expected_m=8 expected_x=8 protected_size=21
assert pc() == $0CD789

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
  JSL ShieldWorld_SyncBoth
  JSL $07F1E6
  RTL
}
pushpc
