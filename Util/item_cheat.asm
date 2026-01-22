;===========================================================
; Debug Hacks
;
; Gives player all items when pressing L (not for main game)
; Bank 0x3C used for code
; WRITTEN: by XaserLE, refactored by scawful
; THANKS TO: -MathOnNapkins' Zelda Doc's
; -wiiqwertyuiop for his Zelda Disassembly
;===========================================================

!BetaRelease = $00
!DebugReloadLatch = $00FE ; Uses UNUSED_FE (free RAM) for hotkey debounce

; Overwrite JSL executed every frame
org $068365 : JSL $3CA62A 

Follower_Main = $099F91
CreateMessagePointers          = $0ED3EB
Sprite_LoadGraphicsProperties  = $00FC41
Sprite_ReloadAll_Overworld     = $09C499

org $3CA62A ; Expanded space for our routine
{
  ;LDA.l $7EF3C5 : CMP.b #$02 : BCS .continue ; Check if in main game
  ;JSL Follower_Main
  ;RTL
  ;.continue
  ; Hotkey: L+R+Select+Start -> reload message pointers + sprite properties
  PHP
  SEP #$20
  LDA RawJoypad1H : AND.b #$F0 : CMP.b #$30 : BNE .reset_reload
  LDA RawJoypad1L : AND.b #$30 : CMP.b #$30 : BNE .reset_reload
  LDA !DebugReloadLatch : BNE .skip_reload
  INC !DebugReloadLatch
  JSL Debug_ReloadRuntimeCaches
  BRA .skip_reload
  .reset_reload
  STZ !DebugReloadLatch
  .skip_reload
  PLP

  LDA $F2 : CMP #$70 : BEQ $03 : JMP END ; Check L, R and X button

if !BetaRelease == 0
  ; How many bombs you have. Can exceed 0x50, up to 0xff.
  LDA #$50 : STA Bombs

  LDA #$02 : STA MagicPowder
             STA Gloves

  LDA #$01 : STA FireRod
             STA IceRod

  LDA #$01 : STA BunnyHood

  LDA #$01 : STA DekuMask
  LDA #$01 : STA ZoraMask
  LDA #$01 : STA WolfMask
  LDA #$01 : STA StoneMask

  LDA #$01 : STA Book
  LDA #$01 : STA Somaria
  LDA #$01 : STA Boots
             STA Flippers
             STA WolfMask

  LDA #$04 : STA Sword

  LDA #$03 : STA Shield

  LDA #$02 : STA Armor

  LDA #$01 : STA BottleIndex ; has bottles
  LDA #$03 : STA Bottle1
  LDA #$05 : STA Bottle2
  LDA #$04 : STA Bottle3
  LDA #$06 : STA Bottle4

  ; How many arrows you have. Can exceed 0x70.
  LDA #$32 : STA Arrows

  ; 2 bytes for rupees (goal, for counting up)
  LDA #$E7 : STA Rupees
  LDA #$03 : STA RupeesGoal
  LDA #$07 : STA Pendants
  LDA #$6E : STA Ability
  LDA #$00 : STA Crystals
  LDA #$01 : STA Hookshot
  LDA #$02 : STA MagicUsage

  LDA #$A0 : STA MAXHP

endif
  LDA #$04 : STA Flute
  LDA #$01 : STA RocsFeather
  LDA #$03 : STA Bow
  LDA #$02 : STA Boomerang
             STA Mirror
             STA Byrna

  LDA #$01 : STA Lamp
             ; STA MagicHammer
             STA Pearl

  LDA #$A0 : STA HeartRefill
  LDA #$80 : STA MagicPower

  ; Skip story events, test goron mines
  LDX.b #$36
  LDA.l $7EF280,X
  ORA.b #$20
  STA.l $7EF280,X

  LDA.b #$02 : STA $7EF3C5
  LDA.b #$01 : STA MakuTreeQuest
  LDA.b #%00001010 : STA OOSPROG

END:

  JSL Follower_Main
  RTL
}

org $3CB000
Debug_ReloadRuntimeCaches:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB

  SEP #$20
  LDA.b #$7E : PHA : PLB

  REP #$30
  JSL CreateMessagePointers
  JSL Sprite_LoadGraphicsProperties

  SEP #$20
  LDA.w INDOORS : BNE .done
    REP #$30
    JSL Sprite_ReloadAll_Overworld

  .done
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}
