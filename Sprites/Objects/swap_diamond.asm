; =========================================================
; Swap Diamond (Oracle of Ages Switch Hook target)
; =========================================================
; A fixed crystal that only the Switch Hook moves. It never moves on its
; own, takes no damage, is solid to Link like a statue, and cannot be pushed
; or lifted. A swap writes its new position (Items/switch_hook.asm), and the
; diamond stays there, so it can be swapped again (Ages: re-placed, never
; breaks).
;
; Art (placeholder until the art pass): the ice block tile, char $E9 drawn
; four times with H/V flips (as Sprites/Objects/ice_block.asm), in palette 4
; ($28/$68/$A8/$E8) instead of the ice block's palette 2. Palette 4 is the
; vanilla crystal switch's orange state (CrystalSwitch_Palette toggles 2/4),
; so the diamond reads as a crystal and stays distinct from blue ice.
; The crystal switch char $E4 was tried first; room $59's sprite sheets do
; not hold it, so it drew garbage.
; =========================================================

!SPRID              = Sprite_SwapDiamond
!NbrTiles           = 03  ; OAM slots - 1: four 8x8 tiles
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 01  ; 01 = not counted as an enemy
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 01  ; 01 = Sprite is statue
!DeflectProjectiles = 01  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_SwapDiamond_Prep, Sprite_SwapDiamond_Long)

Sprite_SwapDiamond_Long:
{
  PHB : PHK : PLB
  JSR Sprite_SwapDiamond_Draw
  JSL Sprite_CheckActive : BCC .inactive
    ; Solid to Link; no push, lift, damage or movement path.
    JSL Sprite_PlayerCantPassThrough
  .inactive
  PLB
  RTL
}

Sprite_SwapDiamond_Prep:
{
  PHB : PHK : PLB
  ; The property macro sets SprDefl bit 6 (delete 64px off camera). Clear it:
  ; the diamond is room furniture and must stay where the last swap put it.
  LDA.w SprDefl, X : AND.b #$BF : STA.w SprDefl, X
  PLB
  RTL
}

Sprite_SwapDiamond_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  PHX
  LDX.b #$03
  LDY.b #$00
  .next
  PHX
  TXA : ASL A : TAX
  REP #$20
  LDA.b $00 : CLC : ADC.w .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : CLC : ADC.w .y_offsets, X : STA ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y
    LDA.b #$F0 : STA ($90), Y             ; off screen: hide
    STA.b $0E
  .on_screen_y
  PLX
  INY : LDA.w .chr, X : STA ($90), Y
  INY : LDA.w .properties, X : STA ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b $0F : STA ($92), Y                ; X bit 8, 8x8 size
  PLY : INY
  DEX : BPL .next
  PLX
  RTS

  .x_offsets
  dw 0, 8, 0, 8
  .y_offsets
  dw 0, 0, 8, 8
  .chr
  db $E9, $E9, $E9, $E9                   ; ice block tile
  .properties
  db $28, $68, $A8, $E8                   ; priority 2, palette 4, flips
}
