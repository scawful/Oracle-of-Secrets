; =========================================================
; Portal Rod Item

; LinkState_UsingEther
org    $07A50F
RodAnimationTimer:
  db $03, $03, $05

LinkItem_PortalRod:
{
  BIT $3A : BVS .y_button_held
    LDA $6C : BNE .return
    JSR Link_CheckNewY_ButtonPress : BCC .return
      LDX.b #$00
      JSR LinkItem_EvaluateMagicCost : BCC .insufficient_mp
        LDA.b #$30 : JSR $802F    ; Sfx3
        JSL   LinkItem_FirePortal
        .y_button_held

        JSR $AE65 ; HaltLinkWhenUsingItems
        DEC $3D : BPL .return
        LDA $0300 : INC A : STA $0300 : TAX
        LDA RodAnimationTimer, X : STA $3D
        CPX.b #$03 : BNE .return
        STZ $0300
        STZ $5E
        STZ $3D
        LDA $0301 : AND.b #$FE : STA $0301

      .insufficient_mp
      LDA $3A : AND.b #$BF : STA $3A

  .return
  RTS
}

assert pc() <= $07A568

; Ancilla_CheckSpriteCollision
org $088DC3
JSL Ancilla_HandlePortalCollision : NOP

pullpc

Ancilla_HandlePortalCollision:
{
  LDA.w $0E20, Y : CMP.b #$03 : BNE .not_portal_arrow
    ; Check if Y is the orange or blue portal
    LDA.w SprSubtype, Y : CMP.b #$02 : BEQ .blue_portal
                          CMP.b #$01 : BEQ .orange_portal
    .orange_portal
    PHY
      LDY.w $0632 ; Blue Sprite ID
      LDA.w SprX, Y : CLC : ADC.b #$10 : STA.w ANC0XL, X
      LDA.w SprY, Y : STA.w ANC0YL, X
      LDA.w SprXH, Y : STA.w ANC0XH, X
      LDA.w SprYH, Y : STA.w ANC0YH, X
    PLY
    JMP .continue

    .blue_portal
    PHY
      LDY.w $0633 ; Orange Sprite ID
      LDA.w SprX, Y : STA.w ANC0XL, X
      LDA.w SprY, Y : CLC : ADC.b #$10 : STA.w ANC0YL, X
      LDA.w SprXH, Y : STA.w ANC0XH, X
      LDA.w SprYH, Y : STA.w ANC0YH, X
    PLY
    .continue
    LDA.b #$08
    RTL
  .not_portal_arrow
  ; Restore arrow deflection sprite code from $088DC3
  LDA.w SprTileDie,Y : AND.b #$08
  RTL
}

macro  SpawnPortal(x_offset, y_offset)
  REP #$20
  LDA $22 : CLC : ADC.w #<x_offset>
  SEP #$20
  STA.w SprX,       Y                ; SprX
  XBA : STA.w SprXH, Y                ; SprXH

  REP #$20
  LDA $20 : CLC : ADC.w #<y_offset>
  SEP #$20
  STA.w SprY,       Y                ; SprY
  XBA : STA.w SprYH, Y                ; SprYH
endmacro

LinkItem_FirePortal:
{
  LDA.b #$03
  JSL   Sprite_SpawnDynamically : BPL .continue
    RTS
  .continue

  PHX
  LDA   $7E0FA6 : BEQ .spawn_blue
    STZ.w $0FA6
    JMP   .check_direction
  .spawn_blue
  LDA #$01 : STA $7E0FA6
  .check_direction

  LDA $2F : CMP.b #$00 : BEQ .facing_up
    LDA $2F : CMP.b #$02 : BEQ .facing_down
      LDA $2F : CMP.b #$04 : BEQ .facing_left
        LDA $2F : CMP.b #$06 : BEQ .facing_right
  ; Portal Spawn Location

  .facing_up
    %SpawnPortal($0000, -0020)
    JMP .finish
  .facing_down
    %SpawnPortal($0000, $001F)
    JMP .finish
  .facing_left
    %SpawnPortal(-0020, $0000)
    JMP .finish
  .facing_right
    %SpawnPortal(0020, $0000)

  .finish
  TYX
  STZ.w SprYRound, X : STZ.w SprXRound, X
  PLX

  .return
  ; Delay the spin attack for some amount of time?
  LDA RodAnimationTimer : STA $3D
  STZ $2E
  STZ $0300 : STZ $0301
  LDA.b #$01 : TSB $0301
  RTL
}

pushpc

org $02FF6E
Overworld_OperateCameraScroll_Long:
{
  PHB : PHK : PLB

  JSR $BB90

  PLB

  RTL
}

Overworld_ScrollMap_Long:
{
  PHB : PHK : PLB
  JSR $F273
  PLB

  RTL
}

pullpc

ScrollToPortal:
{
  REP #$20

  STZ $00
  STZ $02

  LDA $22 : CMP $7EC186 : BEQ .set_x : BCC .x_low
    DEC $02
    DEC A : CMP $7EC186 : BEQ .set_x
    DEC $02
    DEC A
    BRA .set_x
  .x_low

  INC $02
  INC A : CMP $7EC186 : BEQ .set_x
  INC $02
  INC A

  .set_x

  STA $22

  LDA $20 : CMP $7EC184 : BEQ .set_y : BCC .y_low
    DEC $00
    DEC A : CMP $7EC184 : BEQ .set_y
    DEC $00
    DEC A
    BRA .set_y
  .y_low

  INC $00
  INC A : CMP $7EC184 : BEQ .set_y
  INC $00
  INC A

  .set_y

  STA $20
  CMP $7EC184 : BNE .delay_advance
    LDA $22 : CMP $7EC186 : BNE .delay_advance
      INC $B0
      STZ $46
  .delay_advance

  SEP #$20

  LDA $00 : STA $30
  LDA $02 : STA $31

  JSL Overworld_OperateCameraScroll_Long ; $13B90 IN ROM

  LDA $0416 : BEQ .exit
    JSL Overworld_ScrollMap_Long ; $17273 IN ROM
  .exit

  RTL
}

print "End of Items/portal_rod.asm       ", pc
pushpc

; ; Portal Rod logic based on Fire Rod
; Ancilla_PortalShot:
; {
;     LDA $0C54, X : BEQ .traveling_shot
;     JMP Ancilla_ConsumingFire
; .traveling_shot
;     LDA $11 : BNE .just_draw
;     STZ $0385, X
;     JSR Ancilla_MoveHoriz
;     JSR Ancilla_MoveVert
;     JSR Ancilla_CheckSpriteCollision : BCS .collided

;     LDA $0C72, X : ORA.b #$08 : STA $0C72, X
;     JSR Ancilla_CheckTileCollision
;     PHP
;     LDA $03E4, X : STA $0385, X
;     PLP : BCS .collided
;     LDA $0C72, X : ORA.b #$0C : STA $0C72, X
;     LDA $028A, X : STA $74
;     JSR Ancilla_CheckTileCollision
;     PHP
;     LDA $74 : STA $028A, X
;     PLP : BCC .no_collision
; .collided
;     INC $0C54, X
;     ; Check if it's blue or orange portal
;     LDA   $0C68, X
;     CMP.b #$1F
;     BEQ   .blue_portal
;     JMP   .orange_portal
; .blue_portal
;     LDA.b #$20 : STA $0C68, X
;     LDA.b #$08 : STA $0C90, X
;     LDA.b #$2B : JSR Ancilla_DoSfx2 ; Different sound effect for blue portal
;     JMP   .portal_created
; .orange_portal
;     LDA.b #$21 : STA $0C68, X
;     LDA.b #$08 : STA $0C90, X
;     LDA.b #$2C : JSR Ancilla_DoSfx2 ; Different sound effect for orange portal
; .portal_created
;     ; CLC : ADC portal creation logic here if necessary
; .no_collision
;     INC $0C5E, X
;     LDA $0C72, X : AND.b #$F3 : STA $0C72, X
;     LDA $0385, X : STA $0333
;     AND.b #$F0 : CMP.b #$C0 : BNE .just_draw
;     LDA $03E4, X : STA $0333
;     AND.b #$F0 : CMP.b #$C0 : BNE .just_draw
; .just_draw
;     JSR PortalShot_Draw
;     RTS
; }

; ; *$4077C-$407CA LOCAL
; PortalShot_Draw:
; {
;   JSR Ancilla_BoundsCheck
;   LDA $0280, X : BEQ .default_priority
;   LDA.b #$30 : TSB $04
; .default_priority
;   LDA $0C5E, X : AND.b #$0C : STA $02
;   PHX
;   LDX.b #$02
;   LDY.b #$00
; .next_oam_entry
;   STX $03
;   TXA : ORA $02 : TAX
;   LDA $00 : CLC : ADC .x_offsets, X       : STA ($90), Y
;   LDA $01 : CLC : ADC .y_offsets, X : INY : STA ($90), Y
;   LDX $03
;   LDA .chr, X          : INY : STA ($90), Y
;   LDA $04 : ORA.b #$02 : INY : STA ($90), Y
;   PHY
;   TYA : LSR #2 : TAY
;   LDA.b #$00 : STA ($92), Y
;   PLY : INY
;   DEX : BPL .next_oam_entry
;   PLX
;   RTS
; .x_offsets
; db 7, 0, 8, 0, 8, 4, 0, 0
; db 2, 8, 0, 0, 1, 4, 9, 0
; .y_offsets
; db 1, 4, 9, 0, 7, 0, 8, 0
; db 8, 4, 0, 0, 2, 8, 0, 0
; .chr
; db $8D, $9D, $9C
; }
