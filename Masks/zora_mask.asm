; =========================================================
; Zora Mask - by scawful
; Based on the Fairy Flippers item by Conn
; Special Thanks to Zarby89 for the PaletteArmorAndGloves hook
;
; Transforms Link into Zora Link
; Allows fast surface swimming, separate Y-button diving in the overworld
; and dungeons, and Overworld Strong Sea Currents (bypassed by King of Red Lions).
;
; How To Use:
;   Press R to transform into Zora Link. Press R again to transform back.
;   Hold D-pad (and B/A to stroke) in water for fast Zora surface swimming.
;   Press Y in deep water to dive. Press Y again to resurface.
;
; Overworld Strong Sea Current TileTypes (Overworld vector table $07DAFA-$07DB01):
;   $68 = Strong Sea Current North (pushes Up,    -Y)
;   $69 = Strong Sea Current South (pushes Down,  +Y)
;   $6A = Strong Sea Current West  (pushes Left,  -X)
;   $6B = Strong Sea Current East  (pushes Right, +X)
;   (Underworld conveyors $68-$6B at $07D8A8-$07D8AF remain untouched.)
;
; King of Red Lions Bypass WRAM Symbol:
;   !KORL_Mounted = $7FF3D4 (King of Red Lions mounted flag: 1=sailing, 0=not aboard).
;   Read via LDA.l $7FF3D4 so King of Red Lions sails straight through Strong Currents.
; =========================================================

; Swim speeds in 8.8 fixed-point ($0100 = 1.00 px/frame; Flippers = $00F0 = 0.9375 px/f).
; Leaves generous headroom for King of Red Lions at ~2.75-3.0 px/frame.
!ZoraSurfaceSwimMax     = $01B0  ; 1.6875 px/f (~1.80x Human Flippers)
!ZoraSurfaceStrokeMax   = $0230  ; 2.1875 px/f on B/A stroke burst (Human = $0180)
!ZoraDiveSwimMax        = $0120  ; 1.125 px/f distinct underwater speed
!VanillaSwimMax         = $00F0  ; 0.9375 px/f (exact vanilla Human Flippers / Ice)
!VanillaStrokeMax       = $0180  ; 1.50 px/f (exact vanilla Human Flippers stroke peak)

; Overworld Strong Sea Current pushback tuning (beats Human, Zora surface/stroke & dive).
!SeaCurrent_PushPx      = $0002  ; 2 px/frame directional current push
!SeaCurrent_UpstreamCap = $0080  ; 0.50 px/f max upstream thrust -> -1.50 px/f net pushback

; Volatile WRAM flags (zero SRAM delta).
if not(defined("KORL_Mounted"))
  !KORL_Mounted = $7FF3D4        ; King of Red Lions mounted flag (1=sailing, 0=not aboard)
endif
!SeaCurrentDir = $0AB9           ; $7E0AB9 (UNUSED_7E0AB9): 0=none, 1=N, 2=S, 3=W, 4=E

UpdateZoraPalette:
{
  REP #$30
  LDX #$001E

  .loop
  LDA.l zora_palette, X
  PHX
  STA.l TimeState.SubColor
  JSL ColorSubEffect
  PLX
  STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30
  INC $15
  RTL
}

; =========================================================

; TODO: Finish the Zora palette
zora_palette:
  dw $7BDE, $7FFF, $2F7D, $19B5, $3A9C, $14A5, $4E48, $3582
  dw $55BB, $6EF7, $7BDE, $55C7, $6ECD, $2E5A, $1970, $7616
; dw #$6565, #$7271, #$2AB7, #$477E, #$1997, #$14B5, #$459B, #$69F2
; dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, $2357

; zora_palette:
;   dw #$7BDE, $7FFF, $2F7D, $19B5, $3A9C, $14A5, $19FD, $14B6
;   dw #$55BB, $362A, $3F4E, $162B, $22D0, $2E5A, $1970, $7616
;   dw #$6565, $7271, $2AB7, $477E, $1997, $14B5, $459B, $69F2
;   dw #$7AB8, $2609, $19D8, $3D95, $567C, $1890, $52F6, $2357

AddTransitionSplash = $0998FC

; =========================================================
; Bank $36 Helpers ($36F040-$36F1FF, bounded strictly below DungeonWeb $36F200)
; =========================================================

; Returns 16-bit cruise max speed in A.
; Entry: M=16 (X=8 or X=16), any DBR. Preserves X, Y, DBR.
ZoraSwim_GetCruiseMax:
{
  LDA.l $7E005D : AND.w #$00FF : CMP.w #$0004 : BNE .vanilla
  LDA.l $7E034A : AND.w #$00FF : BNE .vanilla
  LDA.l $7E02B2 : AND.w #$00FF : CMP.w #$0002 : BNE .vanilla
  LDA.l $7E0000+!ZoraDiving : AND.w #$00FF : BNE .diving
    LDA.w #!ZoraSurfaceSwimMax
    RTL
  .diving
  LDA.w #!ZoraDiveSwimMax
  RTL
  .vanilla
  LDA.w #!VanillaSwimMax
  RTL
}

; Replaces LDA.w MaxSwimAcceleration : STA.w $0334,X at $079825 and $07E478.
; Entry: M=16 (X=8 or X=16), DBR=$07. Preserves X, Y, DBR.
ZoraSwim_LoadCruiseMaxTo0334:
{
  JSL ZoraSwim_GetCruiseMax
  STA.w $0334, X
  RTL
}

; Shared loop init for Link_HandleSwimAccels ($0798A8) & Link_SetTheMaxAccel ($079903).
; Entry: M=16, X=16, DBR=$07.
; Exit:  $04 = cruise max, $06 = stroke peak, $02 = $0003, X = $0002.
ZoraSwim_LoadLimits:
{
  JSL ZoraSwim_GetCruiseMax : STA.b $04
  LDA.w #!VanillaStrokeMax
  CMP.b $04 : BCS .got_peak        ; Only Zora surface ($01B0 > $0180) gets $0230 peak
    LDA.w #!ZoraSurfaceStrokeMax
  .got_peak
  STA.b $06
  LDA.w #$0003 : STA.b $02
  LDX.w #$0002
  RTL
}

; Replaces $0796D9 (LDA $F4 : ORA $00 : AND #$C0) in LinkState_Swimming.
; Keeps Y dedicated to diving/resurfacing in Zora form; B/A still stroke on surface.
; Entry: M=8, X=8, DBR=$07, $00 = ($F6 & #$80). Exit: A + Z flag for BEQ.
ZoraSwim_CheckStrokeInput:
{
  LDA.w $02B2 : CMP.b #$02 : BNE .vanilla
    LDA.w !ZoraDiving : BNE .suppress
      LDA.b $F4 : ORA.b $00 : AND.b #$80
      RTL
    .suppress
    LDA.b #$00
    RTL
  .vanilla
  LDA.b $F4 : ORA.b $00 : AND.b #$C0
  RTL
}

; Snappier thrust acceleration tables for Zora surface & diving (vanilla = 8,-12,-8,-16).
ZoraSwim_AccelSurface:
  dw 16, -16, -16, -24
ZoraSwim_AccelDive:
  dw 10, -14, -12, -18

; Replaces $07E459 (LDA $E406,Y : CLC : ADC $033C,X) in HandleSwimStrokeAndSubpixels.
; Entry: M=16, X=8, Y=8, DBR=$07. Exit: A = new thrust with N/Z flags; preserves X, Y, DBR.
ZoraSwim_StepThrust:
{
  CPY.b #$08 : BCS .vanilla       ; Ice table ($034A != 0) untouched
  LDA.w $005D : AND.w #$00FF : CMP.w #$0004 : BNE .vanilla
  LDA.w $02B2 : AND.w #$00FF : CMP.w #$0002 : BNE .vanilla
  LDA.w !ZoraDiving : AND.w #$00FF : BNE .dive
    PHX : TYX : LDA.l ZoraSwim_AccelSurface, X : PLX
    BRA .apply
  .dive
  PHX : TYX : LDA.l ZoraSwim_AccelDive, X : PLX
  BRA .apply
  .vanilla
  LDA.w $E406, Y
  .apply
  CLC : ADC.w $033C, X
  RTL
}

; Replaces $07E53A (STZ $68 : STZ $69) right before Link_HandleVelocityAndSandDrag.
; Applies Overworld Strong Sea Current pushback unless !KORL_Mounted != 0.
; Entry/Exit: M=8, X=8, DBR=$07. Preserves X, Y, DBR.
ZoraSwim_ApplySeaCurrent:
{
  STZ.b $68 : STZ.b $69
  LDA.b $1B : BNE .done
  LDA.b $5D : CMP.b #$04 : BNE .done
  LDA.w $034A : BNE .done
  LDA.l !KORL_Mounted : BNE .done
  LDA.w !SeaCurrentDir : BEQ .done
  CMP.b #$05 : BCS .done

  PHX
  DEC A                           ; 0=N(-Y), 1=S(+Y), 2=W(-X), 3=E(+X)
  LDX.b #$00
  CMP.b #$02 : BCC .axis_ready
    LDX.b #$02
  .axis_ready
  AND.b #$01 : BNE .push_pos

  ; Negative push (North -Y or West -X)
  REP #$20
  LDA.b $20, X : SEC : SBC.w #!SeaCurrent_PushPx : STA.b $20, X
  LDA.w $0338, X : AND.w #$00FF : BEQ .pop_done
  BRA .clamp_upstream

  .push_pos
  ; Positive push (South +Y or East +X)
  REP #$20
  LDA.b $20, X : CLC : ADC.w #!SeaCurrent_PushPx : STA.b $20, X
  LDA.w $0338, X : AND.w #$00FF : BNE .pop_done

  .clamp_upstream
  LDA.w $033C, X : CMP.w #!SeaCurrent_UpstreamCap : BCC .pop_done
    LDA.w #!SeaCurrent_UpstreamCap : STA.w $033C, X

  .pop_done
  SEP #$20
  PLX
  .done
  RTL
}

; Latch Overworld Strong Sea Current direction from $03F1/$03F2 (set by TileDetect_MainHandler Y=0)
; into !SeaCurrentDir for BOTH Human & Zora swimmers, with periodic rushing-water splash feedback.
; Entry/Exit: M=8, X=8, DBR=$07.
ZoraSwim_LatchSeaCurrent:
{
  LDA.b $1B : BNE .clear
  LDA.b $5D : CMP.b #$04 : BNE .clear
  LDA.w $034A : BNE .clear
  LDA.l !KORL_Mounted : BNE .clear

  LDA.w $03F1 : AND.b #$0F : BEQ +
    LDA.b #$01 : BRA .store
  +
  LDA.w $03F1 : AND.b #$F0 : BEQ +
    LDA.b #$02 : BRA .store
  +
  LDA.w $03F2 : AND.b #$0F : BEQ +
    LDA.b #$03 : BRA .store
  +
  LDA.w $03F2 : AND.b #$F0 : BEQ .clear
    LDA.b #$04

  .store
  PHA
  LDA.w !SeaCurrentDir : BEQ .do_splash
  LDA.b $1A : AND.b #$1F : BNE .save
  .do_splash
  LDA.b #$15 : LDY.b #$00
  JSL AddTransitionSplash
  .save
  PLA
  STA.w !SeaCurrentDir
  RTL

  .clear
  STZ.w !SeaCurrentDir
  RTL
}

print "End of Masks/zora_mask.asm Bank36 ", pc
assert pc() <= $36F200, "Masks/zora_mask.asm Bank $36 helpers reached DungeonWeb ($36F200)"

; =========================================================
; Bank $07 Hooks
; =========================================================

; Replaces Bombos medallion
org $07A569
LinkItem_ZoraMask:
{
  ; No removing the mask whilst diving.
  LDA !ZoraDiving : BNE .return
    LDA.b #$02
    JSL Link_TransformMask
  .return
  RTS
}

assert pc() <= $07A5CE

; LinkState_Swimming stroke input filter (separate Y dive from B/A stroke in Zora form)
org $0796D9 ; @hook module=Masks name=ZoraSwim_CheckStrokeInput kind=jsl target=ZoraSwim_CheckStrokeInput expected_m=8 expected_x=8 protected_size=6
  assert read4($0796D9) == $0005F4A5 && read2($0796DD) == $C029, "ZoraSwim: $0796D9 stroke check moved"
  JSL ZoraSwim_CheckStrokeInput
  NOP #2
assert pc() == $0796DF

; End of LinkState_Swimming
org $079781 ; @hook module=Masks
  JSR LinkState_UsingZoraMask
  RTS

; Link_SetMomentum cruise max load
org $079825 ; @hook module=Masks name=ZoraSwim_SetMomentumMax kind=jsl target=ZoraSwim_LoadCruiseMaxTo0334 expected_m=16 expected_x=16 protected_size=6
  assert read4($079825) == $9D9639AD && read2($079829) == $0334, "ZoraSwim: $079825 MaxSwimAcceleration moved"
  JSL ZoraSwim_LoadCruiseMaxTo0334
  NOP #2
assert pc() == $07982B

; Link_HandleSwimAccels ($0798A8..$079902, 91 bytes in-place): dynamic cruise & stroke peak.
org $0798A8 ; @hook module=Masks name=ZoraSwim_HandleStrokeAccels kind=patch protected_size=91 skip_abi=true
  assert read4($0798A8) == $02A230C2 && read1($0798AC) == $00, "ZoraSwim: $0798A8 Link_HandleSwimAccels moved"
ZoraSwim_HandleStrokeAccels:
{
  REP #$30
  JSL ZoraSwim_LoadLimits
  .next
  LDA.b $F0 : AND.b $02 : BEQ .next_axis
  LDA.w $033C, X : BEQ .check_max
  LDA.w $0334, X : CMP.b $06 : BCC .check_max
    LDA.b $06 : CMP.w #!VanillaStrokeMax : BNE .set
      LDY.w #$0000
      .check_next
      LDA.w $9896, Y : CMP.w $033C, X : BCS .set
      INY : INY : CPY.w #$0012 : BNE .check_next
      BRA .set
  .check_max
  LDA.w $0334, X : BEQ .no_max
    CLC : ADC.w #$00A0
    CMP.b $06 : BCC .set
      LDA.b $06 : BRA .set
  .no_max
  LDA.w #$0001 : STA.w $033C, X
  LDA.b $04
  .set
  STA.w $0334, X
  .next_axis
  ASL.b $02 : ASL.b $02
  DEX : DEX : BPL .next
  SEP #$30
  RTS
}
assert pc() <= $079903, "ZoraSwim: HandleStrokeAccels overflowed Link_SetTheMaxAccel ($079903)"

; Link_SetTheMaxAccel ($079903..$07996B, 105 bytes in-place): dynamic cruise target + resurface recovery.
org $079903 ; @hook module=Masks name=ZoraSwim_SetTheMaxAccel kind=patch protected_size=105 skip_abi=true
  assert read4($079903) == $4AAD30C2 && read1($079907) == $03, "ZoraSwim: $079903 Link_SetTheMaxAccel moved"
ZoraSwim_SetTheMaxAccel:
{
  LDA.w $034A : ORA.w $034F : BNE .exit8
  REP #$30
  JSL ZoraSwim_LoadLimits
  .next
  LDA.b $F0 : AND.b $02 : BEQ .set
  LDA.w $032B, X : CMP.w #$0002 : BEQ .set
  LDA.w $032F, X : BNE .reset
  ; If target max < current cruise max (e.g. surfaced from Dive), raise target immediately.
  LDA.w $0334, X : CMP.b $04 : BCC .set
  LDA.w $033C, X : CMP.b $04 : BCC .to_next
  CMP.w $0334, X : BEQ .reset
  BCC .to_next
  .reset
  STZ.w $032B, X
  LDA.w $033C, X : CMP.b $04 : BCC .set
    LDA.w #$0001 : STA.w $032B, X : STA.w $032F, X
    BRA .to_next
  .set
  LDA.b $04 : STA.w $0334, X
  STZ.w $032F, X
  .to_next
  ASL.b $02 : ASL.b $02
  DEX : DEX : BPL .next
  SEP #$30
  .exit8
  RTS
}
assert pc() <= $07996C, "ZoraSwim: SetTheMaxAccel overflowed LinkState_Zapped ($07996C)"

; HandleSwimStrokeAndSubpixels acceleration step
org $07E459 ; @hook module=Masks name=ZoraSwim_StepThrust kind=jsl target=ZoraSwim_StepThrust expected_m=16 expected_x=8 protected_size=7
  assert read4($07E459) == $18E406B9 && read2($07E45D) == $3C7D && read1($07E45F) == $03, "ZoraSwim: $07E459 thrust step moved"
  JSL ZoraSwim_StepThrust
  NOP #3
assert pc() == $07E460

; HandleSwimStrokeAndSubpixels post-reverse cruise max load
org $07E478 ; @hook module=Masks name=ZoraSwim_ReverseMax kind=jsl target=ZoraSwim_LoadCruiseMaxTo0334 expected_m=16 expected_x=8 protected_size=6
  assert read4($07E478) == $9D9639AD && read2($07E47C) == $0334, "ZoraSwim: $07E478 MaxSwimAcceleration moved"
  JSL ZoraSwim_LoadCruiseMaxTo0334
  NOP #2
assert pc() == $07E47E

; HandleSwimStrokeAndSubpixels Strong Sea Current pushback before Link_HandleVelocityAndSandDrag
org $07E53A ; @hook module=Masks name=ZoraSwim_ApplySeaCurrent kind=jsl target=ZoraSwim_ApplySeaCurrent expected_m=8 expected_x=8 protected_size=4
  assert read4($07E53A) == $69646864, "ZoraSwim: $07E53A STZ $68 / STZ $69 moved"
  JSL ZoraSwim_ApplySeaCurrent
assert pc() == $07E53E

; Overworld TileBehavior vectors for TileTypes $68-$6B (Strong Sea Currents N/S/W/E).
; Underworld vectors at $07D8A8-$07D8AF remain vanilla conveyors.
org $07DAFA ; @hook module=Masks name=SeaCurrent_OverworldTileVectors kind=data protected_size=8
  assert read4($07DAFA) == $DE2DDE29 && read4($07DAFE) == $DE3ADE35, "ZoraSwim: $07DAFA OW conveyor vectors moved"
  dw TileBehavior_SeaCurrent_Up     ; $68 = Strong Sea Current North (-Y)
  dw TileBehavior_SeaCurrent_Down   ; $69 = Strong Sea Current South (+Y)
  dw TileBehavior_SeaCurrent_Left   ; $6A = Strong Sea Current West  (-X)
  dw TileBehavior_SeaCurrent_Right  ; $6B = Strong Sea Current East  (+X)
assert pc() == $07DB02

; =========================================================

pullpc ; Bank07 Free Space from Deku Mask

; Overworld Strong Sea Current tile behaviors (entered with M=16, X=16, DBR=$07).
; Flag Deep Water ($0341) AND bit0/bit4 of $03F1/$03F2 only (mask $22 stays 0 so
; vanilla TileDetect_Vertical/Horizontal never set $03F3 / Link_ApplyConveyor,
; ensuring !KORL_Mounted != 0 feels zero conveyor drag on real $68-$6B tiles).
TileBehavior_SeaCurrent_Up:
  LDA.w #$0001 : BRA TileBehavior_SeaCurrent_Common

TileBehavior_SeaCurrent_Down:
  LDA.w #$0010 : BRA TileBehavior_SeaCurrent_Common

TileBehavior_SeaCurrent_Left:
  LDA.w #$0100 : BRA TileBehavior_SeaCurrent_Common

TileBehavior_SeaCurrent_Right:
  LDA.w #$1000

TileBehavior_SeaCurrent_Common:
  TSB.w $03F1
  LDA.b $0A : TSB.w $0341
  RTS

LinkState_UsingZoraMask:
{
  ; Latch Overworld Strong Sea Current for ALL swimmers (Human & Zora; KORL bypasses)
  JSL ZoraSwim_LatchSeaCurrent

  ; Check if the Zora Mask is equipped
  LDA $02B2 : CMP #$02 : BNE .not_zora
    ; Check if we are in water or not
    LDA $5D : CMP #$04 : BEQ .swimming
    BRA .normal

  .not_zora
  STZ !ZoraDiving
  .normal
  ; Return to normal state
  STZ $55
  STZ $5E     ; Reset speed to normal
  STZ $037B
  STZ $0351
  JMP .return

  .swimming
  ; Check if we are indoors or outdoors
  LDA $1B : BNE .dungeon ; z flag is 1

  ; OVERWORLD ---------------------------------------------
  .overworld
  {
    ; Maintain continuous underwater ripple ($0351) every frame while diving
    ; (vanilla tile detection clears $0351 each frame on deep water $08).
    LDA !ZoraDiving : BEQ +
      LDA #$01 : STA $0351
    +

    ; Check the Y button and toggle diving cleanly on deep water
    JSR Link_CheckNewY_ButtonPress : BCC .return
    LDA $3A : AND.b #$BF : STA $3A

    ; Check if already underwater
    LDA !ZoraDiving : BEQ .dive
      ; Resurface cleanly back into fast Zora surface swim
      STZ $55            ; Reset cape/underwater look
      STZ !ZoraDiving    ; Reset underwater flag
      STZ $0351          ; Reset ripple flag
      STZ $037B          ; Reset invincibility flag
      STZ $5E            ; Keep land speed clean
      LDA.b #$15 : LDY.b #$00
      JSL AddTransitionSplash
      LDA #$04 : STA $5D ; Stay in Swimming State (restores fast surface swim)
      JMP .return
    .dive

    ; Handle overworld underwater diving (distinct underwater speed in ZoraSwim_GetCruiseMax)
    LDA #$01 : STA $55   ; Set cape/underwater look
    STA $037B            ; Set invincible flag
    STA !ZoraDiving      ; Set underwater flag
    STA $0351            ; Set ripple flag
    STZ $5E              ; Never set slow ground $5E on Overworld
    STZ $034F            ; End any active surface stroke burst immediately
    STZ $032A            ; Reset stroke anim phase

    ; Splash visual + SFX2.$24 sound effect
    LDA.b #$15 : LDY.b #$00
    JSL AddTransitionSplash

    ; Stay in swimming mode
    LDA #$04 : STA $5D

  .return
    JSR $E8F0 ; HandleIndoorCameraAndDoors
    RTS
  }

  ; DUNGEON DIVE ------------------------------------------
  .dungeon
  {
    ; Check if we are in water or not
    LDA $5D : CMP #$04 : BNE .return_dungeon
      ; Check if already underwater
      LDA !ZoraDiving : BNE .return_dungeon
        ; Check the Y button and clear state if activated
        JSR Link_CheckNewY_ButtonPress : BCC .return_dungeon
          LDA $3A : AND.b #$BF : STA $3A

          .dive_dungeon
          ; Splash effect
          LDA.b #$15 : LDY.b #$00
          JSL   AddTransitionSplash

          STZ $5D ; reset player to ground state
          STZ $EE ; move link to lower level
          LDA #$72 : STA $9A  ; Set layer
          LDA #$08 : STA $5E  ; Set the player speed
          STZ $0345           ; Reset deep water flag
          LDA #$01 : STA !ZoraDiving ; Set the player underwater flag

    .return_dungeon
    JSR $E8F0 ; HandleIndoorCameraAndDoors
    RTS
  }
}

pushpc

; End of LinkState_Default
org $0782D2 ; @hook module=Masks
  JSR LinkState_UsingZoraMask_dungeon_resurface
  JSR $E8F0  ; HandleIndoorCameraAndDoors
  CLC
  RTS

assert pc() <= $0782DA

pullpc

.dungeon_resurface
{
  LDA $1B : BEQ .return_overworld ; We are in overworld actually

  ; Check if the player is actually diving
  LDA !ZoraDiving : BEQ .return_default

  ; Check precise tile types for interaction
  LDA $0114 : CMP #$85 : BEQ .player_is_falling
              CMP #$09 : BEQ .player_is_falling
              CMP #$20 : BEQ .fall_into_pit
              CMP #$23 : BEQ .return_default

  ; Check if the ground level is safe
  ; Otherwise, eject the player back to the surface
  LDA $0114 : BNE .remove_dive

  ; Dive gate rooms: Y surfaces only over deep water on map b
  JSL DiveGate_CanSurface : BCC .return_default

  ; Check the Y button and clear state if activated
  JSR Link_CheckNewY_ButtonPress : BCC .return_default
  LDA $3A : AND.b #$BF : STA $3A
  {
    ; Restore Swimming Effects
    LDA.b #$15 : LDY.b #$00 : JSL AddTransitionSplash
    .remove_dive
    LDA #$04 : STA $5D ; Set Link to Swimming State

    LDA #$01 : STA $EE ; Set Link to upper level
    STA $0345          ; Set deep water flag

    ; Remove Diving Effects
    .player_is_falling
    LDA $67 : AND #$01 : STA $2F
    STZ $5E                      ; Reset speed to normal
    STZ !ZoraDiving              ; Reset underwater flag
    STZ $0351                    ; Reset ripple flag
    STZ $24                      ; Reset z coordinate for link
    STZ $0372                    ; Reset link bounce flag
    LDA #$62 : STA $9A           ; Reset dungeon layer
    JMP .return_default
  }

  .return_overworld
  STZ !SeaCurrentDir
  LDA !ZoraDiving : BEQ .return_default
    STZ !ZoraDiving
    STZ $55
    STZ $5E
    STZ $037B
    STZ $0351
  .return_default
  STZ $0302
  RTS
  .fall_into_pit
  LDA.b #$03 : STA $5B
  JSR $9427
  JMP .return_default
}

pushpc

; LinkState_Pits entry: STZ $67 : LDA $0302
org $0792D3 ; @hook module=Masks
  JSR LinkState_UsingZoraMask_pit_stall_guard
  NOP : NOP

pullpc

; A dive beside a pit can leave Link in LinkState_Pits with the pull blocked
; by map-A walls; no input moves him there. Y resurfaces, as it does in water.
.pit_stall_guard
{
  LDA !ZoraDiving : BEQ .run_pits
    LDA $5B : CMP #$02 : BEQ .run_pits ; already falling
      JSR Link_CheckNewY_ButtonPress : BCC .run_pits
        LDA $3A : AND.b #$BF : STA $3A
        PLA : PLA ; leave LinkState_Pits directly
        STZ $5B
        STZ $037B
        LDA.b #$15 : LDY.b #$00 : JSL AddTransitionSplash
        JMP .remove_dive
  .run_pits
  STZ $67
  LDA $0302 ; flags consumed by the BEQ after the hook
  RTS
}

pushpc

; C2C3
; Link_HopInOrOutOfWater_Vertical
org $07C307 ; @hook module=Masks
  JSR LinkState_UsingZoraMask_dungeon_stairs
  RTS

pullpc

.dungeon_stairs
{
  STZ !SeaCurrentDir
  LDA $02B2 : CMP #$02 : BNE .return_hop
    STZ $5E                                ; Reset speed to normal
    LDA !ZoraDiving : BEQ .not_diving_hop
      STZ !ZoraDiving                      ; Reset underwater flag
      STZ $55                              ; Clear underwater invisibility
      STZ $0351                            ; Clear ripple flag
    .not_diving_hop
    LDA $1B : BEQ .return_hop
      LDA #$62 : STA $9A                   ; Reset dungeon layer
  .return_hop
  LDA #$06 : STA $5D ; Set Link to Recoil State
  RTS
}

print "End of Masks/zora_mask.asm        ", pc
pushpc
