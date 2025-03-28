; =========================================================
; Zora Mask - by scawful
; Based on the Fairy Flippers item by Conn
; Special Thanks to Zarby89 for the PaletteArmorAndGloves hook
;
; Transforms Link into Zora Link
; Allows Link to dive underwater in the overworld and dungeons as Zora Link.
;
; How To Use:
;   Press R to transform into Zora Link. Press R again to transform back.
;   Press Y in deep water to dive. Press Y again to resurface.
; =========================================================

UpdateZoraPalette:
{
  REP #$30
  LDX #$001E

  .loop
  LDA.l zora_palette, X
  PHX
  STA.l !SubPalColor
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
; dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, #$2357

; zora_palette:
;   dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$19FD, #$14B6
;   dw #$55BB, #$362A, #$3F4E, #$162B, #$22D0, #$2E5A, #$1970, #$7616
;   dw #$6565, #$7271, #$2AB7, #$477E, #$1997, #$14B5, #$459B, #$69F2
;   dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, #$2357

AddTransitionSplash = $0998FC

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

; =========================================================

; End of LinkState_Swimming
org $079781
  JSR LinkState_UsingZoraMask
  RTS

; =========================================================

pullpc ; Bank07 Free Space from Deku Mask
LinkState_UsingZoraMask:
{
  ; Check if the mask is equipped
  LDA $02B2 : CMP #$02 : BNE .normal
    ; Check if we are in water or not
    LDA $5D : CMP #$04 : BEQ .swimming

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
    ; Check the Y button and clear state if activated
    JSR Link_CheckNewY_ButtonPress : BCC .return
    LDA $3A : AND.b #$BF : STA $3A

    ; Check if already underwater
    LDA !ZoraDiving : BEQ .dive
      STZ $55            ; Reset cape flag
      STZ !ZoraDiving    ; Reset underwater flag
      STZ $0351          ; Reset ripple flag
      STZ $037B          ; Reset invincibility flag
      LDA #$04 : STA $5D ; Put Link in Swimming State
      JMP .return
    .dive


    ; Handle overworld underwater swimming
    LDA #$01 : STA $55   ; Set cape flag
    STA $037B            ; Set invincible flag
    LDA #$08 : STA $5E   ; Set underwater speed
    LDA #$01 : STA !ZoraDiving ; Set underwater flag
    STA $0351            ; Set ripple flag

    ; Splash visual effect
    LDA.b #$15 : LDY.b #$00
    JSL   AddTransitionSplash

    ; Stay in swimming mode
    LDA #$04 : STA $5D
    ; Splash sound effect
    ; LDA #$24 : STA $012E

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
org $0782D2
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
  STZ !ZoraDiving
  .return_default
  STZ $0302
  RTS
  .fall_into_pit
  LDA.b #$03 : STA $5B
  JSR $9427
  JMP .return_default
}

pushpc

; C2C3
; Link_HopInOrOutOfWater_Vertical
org $07C307
  JSR LinkState_UsingZoraMask_dungeon_stairs
  RTS

pullpc

.dungeon_stairs
{
  LDA $02B2 : CMP #$02 : BNE .return_hop
    STZ $5E                                ; Reset speed to normal
    STZ !ZoraDiving                        ; Reset underwater flag
    LDA #$62 : STA $9A                     ; Reset dungeon layer
  .return_hop
  LDA #$06 : STA $5D ; Set Link to Recoil State
  RTS
}

print "End of Masks/zora_mask.asm        ", pc
pushpc
