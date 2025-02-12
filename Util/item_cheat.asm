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

; Overwrite JSL executed every frame
org $068365 : JSL $3CA62A 

Follower_Main = $099F91

org $3CA62A ; Expanded space for our routine
{
  ;LDA.l $7EF3C5 : CMP.b #$02 : BCS .continue ; Check if in main game
  ;JSL Follower_Main
  ;RTL
  ;.continue
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
