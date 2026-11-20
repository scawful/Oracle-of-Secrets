; =========================================================
; Epona crowd check + mounted charge (!ENABLE_HORSE_CROWD_CHARGE).
; Included from Sprites/NPCs/horse.asm in bank $53 after park-anywhere.
;
; Crowd check: Epona's Song refuses (existing $3C refusal chime, no new
; text) while !HORSE_CROWD_LIMIT or more enemies are active, so the tall
; Epona sprite does not compete with a crowded screen for OAM slots.
; Charge: while mounted and moving on the ground, an enemy touching the
; front of Epona takes level-1 sword damage with knockback away from Link.
; =========================================================

!HORSE_CROWD_LIMIT = 5              ; refuse the call at this many enemies

; In: M/X 8-bit, DBR $00-$3F. Out: C=1 crowded. A/X/Y preserved.
HorseCrowd_Check:
{
  PHA : PHX : PHY
  LDY.b #$00
  LDX.b #$0F
  .slot
    JSR HorseCharge_IsEnemy : BCC .next
    INY
  .next
  DEX : BPL .slot
  CPY.b #!HORSE_CROWD_LIMIT         ; C=1 when count >= limit
  PLY : PLX : PLA
  RTL
}

; In: X = slot, M 8-bit, DBR $00-$3F. Out: C=1 when slot X holds a live
; enemy: active ($0DD0 >= $09), not harmless ($0E40 bit 7), not Epona, not a
; pickup (ID >= $D8). A clobbered.
HorseCharge_IsEnemy:
{
  LDA.w $0DD0,X : CMP.b #$09 : BCC .no
  LDA.w $0E40,X : BMI .no
  LDA.w $0E20,X : CMP.b #!HorsePark_SpriteId : BEQ .no
  CMP.b #$D8 : BCS .no
  SEC
  RTS
  .no
  CLC
  RTS
}

; Called from HorseForm_FrameTick .grounded (mounted, overworld play,
; DBR=$00, M/X 8-bit). Hits each touching enemy once per damage flash.
; A/X/Y and DP $00-$0B clobbered (frame-local scratch).
HorseCharge_Tick_Long:
{
  LDA.b $F0 : AND.b #$0F : BNE +      ; d-pad held = charging
    RTL
  +
  REP #$20
  LDA.b $0C : PHA : LDA.b $0E : PHA
  LDA.b $22 : SEC : SBC.w #48 : STA.b $0C
  LDA.b $20 : SEC : SBC.w #48 : STA.b $0E
  SEP #$20
  JSR HorseCharge_SetBox
  LDX.b #$0F
  .slot
    LDA.w $0DD0,X : CMP.b #$09 : BCC .next_near
    LDA.w $0E40,X : BMI .next_near
    LDA.w $0E20,X : CMP.b #!HorsePark_SpriteId : BEQ .next_near
    CMP.b #$D8 : BCS .next_near
    LDA.w $0D10,X : SEC : SBC.b $0C : TAY
    LDA.w $0D30,X : SBC.b $0D : BNE .next_near
    CPY.b #$80 : BCS .next_near
    LDA.w $0D00,X : SEC : SBC.b $0E : TAY
    LDA.w $0D20,X : SBC.b $0F : BNE .next_near
    CPY.b #$80 : BCS .next_near
    LDA.w $0EF0,X : BNE .next       ; already flashing from a hit
    LDA.w $0BA0,X : BNE .next       ; bulletproof
    LDA.w $0E60,X : AND.b #$40 : BNE .next  ; impervious
    LDA.w $0B6B,X : AND.b #$02 : BNE .next  ; !Boss property
    LDA.w $0F70,X : CMP.b #$10 : BCC +      ; airborne above the horse
    .next_near
      BRA .next
    +
    LDA.w $0E20,X
    PHX
    LDX.b #(HorseCharge_ImmuneIds_end-HorseCharge_ImmuneIds)-1
    .immune
      CMP.l HorseCharge_ImmuneIds,X : BEQ .immune_hit
    DEX : BPL .immune
    PLX
    JSL $0683EA                     ; Sprite_SetupHitbox_long: X -> box B
    JSL $0683E6                     ; CheckIfHitBoxesOverlap_long
    BCC .next
    LDA.b $2F : LSR : TAY
    PHX : TYX : LDA.l .recoil_y,X : PLX : STA.w $0F30,X
    PHX : TYX : LDA.l .recoil_x,X : PLX : STA.w $0F40,X
    PHX
    LDA.b #$01                      ; class 1 = level-1 sword slash
    JSL $06ED25                     ; Ancilla_CheckDamageToSprite_preset.apply
    PLX
    REP #$20
    LDA.b $22 : SEC : SBC.w #48 : STA.b $0C
    LDA.b $20 : SEC : SBC.w #48 : STA.b $0E
    SEP #$20
    JSR HorseCharge_SetBox
    BRA .next
    .immune_hit
    PLX
  .next
  DEX : BMI + : JMP .slot : +
  REP #$20
  PLA : STA.b $0E : PLA : STA.b $0C
  SEP #$20
  .done
  RTL

  ; Knockback away from Link by facing ($2F/2: up, down, left, right).
  .recoil_y : db $C0, $40, $00, $00
  .recoil_x : db $00, $00, $C0, $40
}

; Box A ($00/$08 x, $01/$09 y, $02 w, $03 h) = Epona's front by facing $2F.
; Epona's body spans about x -8..24, y -28..16 from Link's $22/$20.
; X preserved; A/Y clobbered.
HorseCharge_SetBox:
{
  PHX
  LDA.b $2F : AND.b #$06 : TAX
  REP #$20
  LDA.b $22 : CLC : ADC.l .dx,X : SEP #$20 : STA.b $00 : XBA : STA.b $08
  REP #$20
  LDA.b $20 : CLC : ADC.l .dy,X : SEP #$20 : STA.b $01 : XBA : STA.b $09
  TXA : LSR : TAX
  LDA.l .wid,X : STA.b $02
  LDA.l .hgt,X : STA.b $03
  PLX
  RTS

  ;     up    down  left  right
  .dx : dw -8,   -8,   -14,  8
  .dy : dw -32,  0,    -16,  -16
  .wid : db 32,  32,   22,   22
  .hgt : db 26,  22,   30,   30
}

; Sprite IDs Epona's charge never damages: armored enemies. Bosses are
; skipped by the !Boss property ($0B6B bit 1) above, vanilla and custom.
HorseCharge_ImmuneIds:
  db $51                            ; Armos
  db $6A                            ; Ball and Chain trooper
  db $8E                            ; Terrorpin
  db $91                            ; Stalfos Knight
  db $CA                            ; Chain Chomp
.end
