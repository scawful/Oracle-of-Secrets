; =========================================================
; Cloud Bridge Sprite
;
; Weather-conditional platform for Sky Islands.
; When Song of Storms is active ($7EE00E = 1), the cloud
; solidifies and acts as a walkable platform. When weather
; is clear, the cloud becomes translucent mist that the
; player passes through.
;
; Based on the Minecart platform_sprite.asm collision pattern.

!SPRID              = Sprite_CloudBridge
!NbrTiles           = 06    ; Number of tiles used in a frame
!Harmless           = 01    ; Sprite is Harmless
!HVelocity          = 00    ; Not fast
!Health             = 00    ; No health (indestructible)
!Damage             = 00    ; No damage
!DeathAnimation     = 01    ; No death animation
!ImperviousAll      = 01    ; Attacks clink off
!SmallShadow        = 00    ; No shadow
!Shadow             = 00    ; No shadow (floating cloud)
!Palette            = 00    ; Default palette
!Hitbox             = 14    ; Same as minecart platform
!Persist            = 01    ; Continue to live offscreen
!Statis             = 00    ; Normal sprite
!CollisionLayer     = 00    ; Single layer collision
!CanFall            = 00    ; Can't fall in holes
!DeflectArrow       = 00    ; Don't deflect arrows
!WaterSprite        = 00    ; Not water-only
!Blockable          = 00    ; Not blockable
!Prize              = 00    ; No prize
!Sound              = 00    ; Default damage sound
!Interaction        = 00    ; Default interaction
!Statue             = 00    ; Not a statue
!DeflectProjectiles = 00    ; Don't deflect projectiles
!ImperviousArrow    = 01    ; Impervious to arrows
!ImpervSwordHammer  = 01    ; Impervious to sword/hammer
!Boss               = 00    ; Not a boss

%Set_Sprite_Properties(Sprite_CloudBridge_Prep, Sprite_CloudBridge_Long)

; =========================================================

Sprite_CloudBridge_Prep:
{
  PHB : PHK : PLB

  LDA #$06 : STA.w SprNbrOAM, X
  LDA #$40 : STA.w SprGfxProps, X
  LDA #$E0 : STA.w SprHitbox, X
  LDA #$00 : STA.w SprBump, X
  LDA #$00 : STA.w SprTileDie, X
  LDA #$00 : STA.w SprAction, X

  PLB
  RTL
}

Sprite_CloudBridge_Long:
{
  PHB : PHK : PLB

  ; Don't run while paused
  LDA $10 : CMP #$0E : BEQ .return

  ; Check weather state: solid when storms, passable when clear
  LDA.l $7EE00E : BNE .solid_mode

  ; --- Passable mode (no storms): faded mist, no collision ---
  JSR CloudBridge_DrawFaded
  BRA .return

  .solid_mode
  ; --- Solid mode (storms active): opaque, blocks player ---
  JSR CloudBridge_DrawSolid
  JSL Sprite_PlayerCantPassThrough

  ; Check if player is standing on the cloud
  JSR CloudBridge_CheckPlayerOn : BCC .not_on
    LDA #$00 : STA $5D : STA $5B
  .not_on

  .return
  PLB
  RTL
}

; =========================================================
; Check if the player is standing on top of the cloud bridge.
; Returns: Carry set = on platform, Carry clear = not on
CloudBridge_CheckPlayerOn:
{
  REP #$20
  LDA $22 : CLC : ADC #$0008 : CMP.w SprCachedX : BCC .outside
  LDA $22 : SEC : SBC #$002C : CMP.w SprCachedX : BCS .outside
  LDA $20 : CLC : ADC #$0010 : CMP.w SprCachedY : BCC .outside
  LDA $20 : SEC : SBC #$0014 : CMP.w SprCachedY : BCS .outside
  SEP #$21  ; Set carry = on platform
  RTS

  .outside
  SEP #$20
  CLC
  RTS
}

; =========================================================
; Shared tile layout: 3 wide × 2 tall cloud (48×32 pixels)
CloudBridge_XOffsets:
  dw 0, 16, 32
  dw 0, 16, 32

CloudBridge_YOffsets:
  dw 0, 0, 0
  dw 16, 16, 16

; Tile characters (placeholder — shared with platform tiles)
CloudBridge_Chr:
  db $42, $4C, $42
  db $42, $4C, $42

; All 16×16 tiles
CloudBridge_Sizes:
  db $02, $02, $02
  db $02, $02, $02

; Solid mode: palette 1, priority 2, H-flip mirroring
CloudBridge_SolidProps:
  db $12, $12, $52
  db $92, $92, $D2

; Faded mode: palette 6 (lighter tint), lower visual weight
CloudBridge_FadedProps:
  db $1C, $1C, $5C
  db $9C, $9C, $DC

; =========================================================
; Draw solid cloud (opaque, storms active)
CloudBridge_DrawSolid:
{
  JSL Sprite_PrepOamCoord
  LDA #$18
  JSL OAM_AllocateFromRegionB

  PHX
  LDX #$05
  LDY.b #$00

  .nextTile
  PHX : TXA : PHA : ASL A : TAX

  REP #$20
  LDA $00 : CLC : ADC.w CloudBridge_XOffsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC.w CloudBridge_YOffsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen
  LDA.b #$F0 : STA ($90), Y : STA $0E
  .on_screen

  PLX ; tile index
  INY
  LDA.w CloudBridge_Chr, X : STA ($90), Y
  INY
  LDA.w CloudBridge_SolidProps, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.w CloudBridge_Sizes, X : ORA $0F : STA ($92), Y
  PLY : INY

  PLX : DEX : BPL .nextTile
  PLX
  RTS
}

; =========================================================
; Draw faded cloud (translucent mist, no storms)
CloudBridge_DrawFaded:
{
  JSL Sprite_PrepOamCoord
  LDA #$18
  JSL OAM_AllocateFromRegionB

  PHX
  LDX #$05
  LDY.b #$00

  .nextTile
  PHX : TXA : PHA : ASL A : TAX

  REP #$20
  LDA $00 : CLC : ADC.w CloudBridge_XOffsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC.w CloudBridge_YOffsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen
  LDA.b #$F0 : STA ($90), Y : STA $0E
  .on_screen

  PLX ; tile index
  INY
  LDA.w CloudBridge_Chr, X : STA ($90), Y
  INY
  LDA.w CloudBridge_FadedProps, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.w CloudBridge_Sizes, X : ORA $0F : STA ($92), Y
  PLY : INY

  PLX : DEX : BPL .nextTile
  PLX
  RTS
}
