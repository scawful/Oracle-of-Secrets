; portal_rod.asm by scawful
; TODO: Make the item an alternative to the FishingRod

; Replace LinkState_UsingEther
org    $07A50F
RodAnimationTimer:
  db $03, $03, $05

LinkItem_PortalRod:
{
  BIT $3A : BVS .y_button_held
  LDA $6C : BNE .return

  JSR   Link_CheckNewY_ButtonPress : BCC .return
  LDX.b #$00
  JSR   LinkItem_EvaluateMagicCost : BCC .insufficient_mp
  
  LDA.b #$30 : JSR $802F    ; Sfx3
  JSL   LinkItem_FirePortal
  
.y_button_held

  JSR $AE65 ; HaltLinkWhenUsingItems
  
  ; What's the point of this?
  ; LDA $67 : AND.b #$F0 : STA $67
  
  DEC $3D : BPL .return
  
  LDA $0300 : INC A : STA $0300 : TAX
  
  LDA RodAnimationTimer, X : STA $3D
  
  CPX.b #$03 : BNE .return
  
  STZ $5E
  STZ $0300
  STZ $3D
  
  LDA $0301 : AND.b #$FE : STA $0301

.insufficient_mp
  LDA $3A : AND.b #$BF : STA $3A

.return
  RTS
}

warnpc $07A568

pullpc

macro  SpawnPortal(x_offset, y_offset)
  REP #$20
  LDA $22 : CLC : ADC.w #<x_offset>
  SEP #$20
  STA $0D10,       Y                ; SprX
  XBA : STA $0D30, Y                ; SprXH

  REP #$20
  LDA $20 : CLC : ADC.w #<y_offset>
  SEP #$20
  STA $0D00,       Y                ; SprY
  XBA : STA $0D20, Y                ; SprYH
endmacro

LinkItem_FirePortal:
{
  LDA.b #$B8
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
  JMP .finish

.finish
  TYX

  STZ $0D60, X
  STZ $0D70, X
  LDA #$09 : STA $0DD0, X
      
  PLX

.return
  ; Delay the spin attack for some amount of time?
  LDA RodAnimationTimer : STA $3D
  
  STZ $2E
  STZ $0300
  STZ $0301
  
  LDA.b #$01 : TSB $0301

  RTL

}

; =========================================================

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


Ancilla_MoveXYWithPortal:
{
  ; Increments X_reg by 0x0A so that X coordinates will be handled next
  TXA : CLC : ADC.b #$0A : TAX
  
; MoveVertical
  LDA $0C22, X : ASL #4 : CLC : ADC $0C36, X : STA $0C36, X
  
  LDY.b #$00
  
  ; upper 4 bits are pixels per frame. lower 4 bits are 1/16ths of a pixel per frame.
  ; store the carry result of adding to $0C36, X
  ; check if the y pixel change per frame is negative
  LDA $0C22, X : PHP : LSR #4 : PLP : BPL .moving_down
  
  ; sign extend from 4-bits to 8-bits
  ORA.b #$F0
  
  DEY

.moving_down

  ; modifies the y coordinates of the special object
        ADC $0BFA, X : STA $0BFA, X
  TYA : ADC $0C0E, X : STA $0C0E, X

  LDX.w $0FA0


  RTL
}

; #_088087: db $50 ; 0x18 - ETHER SPELL
; #_088088: db $00 ; 0x19 - BOMBOS SPELL  
; LDA.b #$18               ; Ether Spell
; LDY.b #$01
; JSL   Ancilla_PortalShot

print "End of Items/portal_rod.asm       ", pc
pushpc


; org $0997DE
;   AddSilverArrowSparkle:

; org $088D68
;   Ancilla_CheckSpriteCollision:

; org $088981
;   Ancilla_CheckTileCollision:

; org $088027
;   Ancilla_DoSfx2:

; org $08A121
; Ancilla_Arrow:
; {
; .y_offsets
; dw -4,  2,  0,  0

; .x_offsets
; dw 0,  0, -4,  4

;   LDA.b $11 : BEQ .normal_submode
  
;   BRL .draw

; .normal_submode

;   DEC.w $0C5E, X : LDA.w $0C5E, X : BMI .timer_elapsed
;                    CMP.b #$04     : BCC .begin_moving
  
;   ; The object doesn't even start being drawn until this timer counts
;   ; down.
;   BRL .do_nothing

; .timer_elapsed

;   LDA.b #$FF : STA.w $0C5E, X

; .begin_moving

;   ; JSL Ancilla_MoveXYWithPortal
;   JSR $908B
;   JSR $9080
  
;   LDA.l $7EF340 : AND.b #$04 : BEQ .dont_spawn_sparkle
  
;   LDA.b $1A : AND.b #$01 : BNE .dont_spawn_sparkle
  
;   PHX
  
;   JSL AddSilverArrowSparkle
  
;   PLX

; .dont_spawn_sparkle

;   LDA.b #$FF : STA $03A9, X
  
;   JSR Ancilla_CheckSpriteCollision : BCS .sprite_collision
  
;   JSR Ancilla_CheckTileCollision : BCS .tile_collision
  
;   BRL .draw

; .tile_collision

;   TYA : STA $03C5, X
  
;   LDA $0C72, X : AND.b #$03 : ASL A : TAY
  
;   LDA.w .y_offsets+0, Y : CLC : ADC.w $0BFA, X : STA.w $0BFA, X
;   LDA.w .y_offsets+1, Y : ADC.w $0C0E, X : STA.w $0C0E, X
  
;   LDA.w .x_offsets+0, Y : CLC : ADC.w $0C04, X : STA.w $0C04, X
;   LDA.w .x_offsets+1, Y : ADC.w $0C18, X : STA.w $0C18, X
  
;   STZ.w $0B88
  
;   BRA .transmute_to_halted_arrow

; .sprite_collision

;   LDA $0C04, X : SEC : SBC $0D10, Y : STA $0C2C, X
  
;   LDA $0BFA, X : SEC : SBC $0D00, Y : CLC : ADC $0F70, Y : STA $0C22, X
  
;   TYA : STA $03A9, X
  
;   LDA $0E20, Y : CMP.b #$65 : BNE .not_archery_game_sprite
  
;   LDA $0D90, Y : CMP.b #$01 : BNE .not_archery_target_mop
  
;   LDA.b #$2D : STA $012F
  
;   ; Set a delay for the archery game proprietor and set a timer for the 
;   ; target that was hit (indicating it was hit)
;   LDA.b #$80 : STA $0E10, Y : STA $0F10
  
;   ; \tcrf In conjunction with the ArcheryGameGuy sprite code, this is
;   ; another lead the suggested that there were 9 game prize values
;   ; instead of just the normal 5.
;   LDA $0B88 : CMP.b #$09 : BCS .prize_index_maxed_out
  
;   INC $0B88

; .prize_index_maxed_out

;   LDA $0B88 : STA $0DA0, Y
  
;   LDA $0ED0, Y : INC A : STA $0ED0, Y
  
;   BRA .transmute_to_halted_arrow

; .not_archery_target_mop

;   LDA.b #$04 : STA $0EE0, Y

; .not_archery_game_sprite

;   STZ $0B88

; .transmute_to_halted_arrow

;   LDA $0E20, Y : CMP.b #$1B : BEQ .hit_enemy_arrow_no_sfx
  
;   LDA.b #$08 : JSR Ancilla_DoSfx2

; .hit_enemy_arrow_no_sfx

;   STZ $0C5E, X
  
;   LDA.b #$0A : STA $0C4A, X
;   LDA.b #$01 : STA $03B1, X
  
;   LDA $03C5, X : BEQ .draw
  
;   REP #$20
  
;   LDA $E0 : SEC : SBC  $E2 : CLC : ADC $0C04, X : STA $00
;   LDA $E6 : SEC : SBC  $E8 : CLC : ADC $0BFA, X : STA $02
  
;   SEP #$20
  
;   LDA $00 : STA $0C04, X
;   LDA $02 : STA $0BFA, X
  
;   BRA .draw

; .do_nothing

;   RTS

; .draw

;   BRL $09236E ; Arrow_Draw
; }
; warnpc $08A24E

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
