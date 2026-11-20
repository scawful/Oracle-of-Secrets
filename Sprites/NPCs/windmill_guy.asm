; =========================================================
; Eon Windmill NPC (Song of Storms)
;
; NARRATIVE ROLE: Eon Abyss windmill keeper who teaches Link the
;   Song of Storms after the Song of Healing.
;
; TERMINOLOGY: "Windmill Guy" = WindmillGuy
;   - Requires Ocarina ($7EF34C >= 1)
;   - Requires Song of Healing ($7EF34C >= 2)
;   - Teaches Song of Storms ($7EF34C = 3)
;
; MESSAGES:
;   0x1D5 - No Ocarina yet
;   0x1D6 - Need Song of Healing first
;   0x1D7 - Teach Song of Storms
;   0x1D8 - Already knows Song of Storms
;
; FLAGS READ:
;   $7EF34C - Ocarina/song progression
;
; FLAGS WRITTEN:
;   $7EF34C = 3 - Song of Storms learned
;
; GRAPHICS / PALETTES:
;   Room $00C9 header specifies spriteset $22 (34). Vanilla $01:B647 adds #$40
;   to dungeon header spritesets, which would load UW spriteset $62 (slot 3 =
;   Sheet $41 / global $B4, Great Fairy). WindmillGuy_HeaderSpriteset hooks
;   $01:B647 so Room $00C9 with header $22 keeps $0AA3 = $22 (slot 3 = Sheet
;   $38 / global $AB, VRAM $C0..$FF) without disturbing Room $0120 ($62).
;   Authentic GBC Oracle of Seasons spr_guruguru (frames 4d10d & 4d11e) occupies
;   the 12 blank tiles of Sheet $38 via Data/graphics/spr38.txt (OBJ5 $2B only):
;     Frame 0 (4d10d, 16x24, 3 tiles): $CF/$DF (horn 16x8), $E8 (body 16x16)
;     Frame 1 (4d11e, 16x25, 4 tiles): $CF backmost (+2,-9 horn cap),
;                                      $EF/$FF (horn 16x8), $EA (body 16x16)
; =========================================================

; Shared vanilla symbol referenced by Overworld/richard_quest.asm & Sprites/NPCs/ranch_girl.asm.
SpriteDraw_RaceGameLady =  $1AF92C

!SPRID              = Sprite_WindmillGuy
!NbrTiles           = 04 ; Max 4 body/horn tiles (Frame 1) + 1 shadow = 5 OAM slots (zero-based)
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 01  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 02  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 01  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

SpriteModule_Active_Bank1E = $1E8B11

%Set_Sprite_Properties(Sprite_WindmillGuy_Prep, Sprite_WindmillGuy_Long)

Sprite_WindmillGuy_Long:
{
  ; Safe sprite multiplexing: Sprite ID $B2 is shared between Sprite_WindmillGuy
  ; (NPC) and vanilla PlayerBee (spawned by Honeycomb swarm or player bottle bee).
  ; When spawned as a bee, $0D80,X is set to 1 (active player bee state).
  ; Windmill Guy has $0D80,X == 0.
  LDA.w $0D80, X : BEQ +
    JML SpriteModule_Active_Bank1E
  +
  PHB : PHK : PLB
  LDA.b #$01 : STA.w SprMiscC, X
  JSR Sprite_WindmillGuy_Draw
  BCS .skip_shadow
    JSL Sprite_DrawShadow
  .skip_shadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_WindmillGuy_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_WindmillGuy_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : AND.b #$01 : TAY
  LDA.w .start_index, Y : STA.b $06

  PHX
  LDA.w .nbr_of_tiles, Y : TAX
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA.b ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA.b ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA.b ($90), Y
      STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA.b ($90), Y
    INY
    LDA.w .properties, X : STA.b ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.w .sizes, X : ORA.b $0F : STA.b ($92), Y
    PLY : INY

    PLX : DEX : BPL .nextTile
  PLX
  CLC
  RTS

  .start_index
  db $00, $03
  .nbr_of_tiles
  db $02, $03 ; Frame 0: 3 tiles (4d10d); Frame 1: 4 tiles (4d11e, exact 16x25)

  ; Order per frame (highest index drawn to OAM slot 0 frontmost, index 0 backmost):
  ;   Frame 0 (3 tiles): 0=$CF horn L, 1=$DF horn R, 2=$E8 body 16x16
  ;   Frame 1 (4 tiles): 0=$CF backmost T07 cap (+2,-9), 1=$EF horn L, 2=$FF horn R, 3=$EA body 16x16
  .x_offsets
  dw 0, 8, 0            ; Frame 0 (OoS 4d10d)
  dw 2, 0, 8, 0         ; Frame 1 (OoS 4d11e)

  .y_offsets
  dw -8, -8, 0          ; Frame 0
  dw -9, -8, -8, 0      ; Frame 1

  .chr
  db $CF, $DF, $E8
  db $CF, $EF, $FF, $EA

  ; Priority 2 ($20) + OBJ5 ($0A) + OBJ page 1 ($01) = $2B (single GBC palette row)
  .properties
  db $2B, $2B, $2B
  db $2B, $2B, $2B, $2B

  .sizes
  db $00, $00, $02
  db $00, $00, $00, $02
}

Sprite_WindmillGuy_Prep:
{
  RTL
}

Sprite_WindmillGuy_Main:
{
  JSL Sprite_PlayerCantPassThrough
  %PlayAnimation(0, 1, 12)

  LDA.l $7EF34C : CMP.b #$01 : BCC .no_ocarina
                  CMP.b #$02 : BCC .need_healing
                  CMP.b #$03 : BCS .already

  %ShowSolicitedMessage($1D7) : BCC .done
    LDA.b #$03 : STA.l $7EF34C
    LDA.b #$2F : STA.w $0CF8
    JSL $0DBB67 ; Link_CalculateSFXPan
    ORA.w $0CF8
    STA $012E ; SFX2.$2F Song of Storms learned sound
    RTS

  .no_ocarina
  %ShowSolicitedMessage($1D5)
  RTS

  .need_healing
  %ShowSolicitedMessage($1D6)
  RTS

  .already
  %ShowSolicitedMessage($1D8)

  .done
  RTS
}

; =========================================================
; Room $00C9 header spriteset hook ($01:B647)
; Replaces INY : LDA [$0D],Y : CLC : ADC #$40 : STA.w $0AA3 (9 bytes).
; Entry/Exit: M=8, X=16, Y advanced by 1 (as vanilla), X/DBR preserved.
; Keeps $0AA3 = $22 for Room $00C9 when header byte == $22 so slot 3 loads
; Sheet $38 (global $AB, Data/graphics/spr38.txt) instead of UW $62 (Sheet $41).
; Room $0120 (shared header $22 for Fairies) and any future header change keep
; the standard +$40 dungeon offset.
; =========================================================
pushpc
assert read3($01B647) == $0DB7C8 && read3($01B64A) == $406918 && read3($01B64D) == $0AA38D, "Room header spriteset load at $01:B647 moved"
org $01B647 ; @hook module=Sprites name=WindmillGuy_HeaderSpriteset kind=jsl target=WindmillGuy_HeaderSpriteset expected_m=8 expected_x=16 expected_exit_m=8 expected_exit_x=16 protected_size=9
  JSL WindmillGuy_HeaderSpriteset
  NOP #5
assert pc() == $01B650
pullpc

WindmillGuy_HeaderSpriteset:
{
  INY
  LDA.b [$0D], Y
  CMP.b #$22 : BNE .add_uw_offset
  LDA.b $A0 : CMP.b #$C9 : BNE .restore_header
  LDA.b $A1 : BNE .restore_header
    LDA.b #$22
    BRA .store
.restore_header
  LDA.b #$22
.add_uw_offset
  CLC : ADC.b #$40
.store
  STA.l $7E0AA3
  RTL
}
