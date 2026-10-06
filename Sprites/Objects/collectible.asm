; =========================================================
; Collectible Sprites 
; (Pineapple, Seashell, Sword/Shield, Rock Meat)

!SPRID              = $52
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
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
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Collectible_Prep, Sprite_Collectible_Long)

if !ENABLE_SWORD_WARP_HOME == 1
; Sword warp home (Forest of Dreams sword, DW $58 -> LW $2A).
SwordWarp_VictorySpinLong       = $07A7B0 ; Link_AnimateVictorySpin_long
SwordWarp_TerminateInteractives = $09AC6B ; Ancilla_TerminateSelectInteractives
!SwordWarp_CacheRoom = $0150              ; any room $0128-$017F (not an entrance)
endif

Sprite_Collectible_Long:
{
  PHB : PHK : PLB

if !ENABLE_SWORD_WARP_HOME == 1
  ; The sword is taken: the scene actions (4+) draw nothing.
  LDA.w SprAction, X : CMP.b #$04 : BCS .skip_draw
endif
  LDA.b $8A : CMP.b #$58 : BNE .not_intro_sword
    JSR Sprite_SwordShield_Draw
    BRA +
  .not_intro_sword
  LDA.b $8A : CMP.b #$4B : BNE .not_lupo_mountain
    JSR Sprite_RockSirloin_Draw
    BRA +
  .not_lupo_mountain
  JSR Sprite_Pineapple_Draw
  +
  JSL Sprite_DrawShadow
if !ENABLE_SWORD_WARP_HOME == 1
  .skip_draw
endif
  JSL Sprite_CheckActive
  BCC .SpriteIsNotActive

  JSR Sprite_Collectible_Main

  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Collectible_Prep:
{
  PHB : PHK : PLB

  ; Don't spawn the sword if we have it.
  LDA.b $8A : CMP.b #$58 : BNE .not_intro_sword
    LDA.l $7EF359 : BEQ +
      STZ.w SprState, X
    +
    LDA.b #$02 : STA.w SprAction, X
  .not_intro_sword
  LDA.b $8A : CMP.b #$4B : BNE .not_lupo_mountain
    LDA.b #$03 : STA.w SprAction, X
  .not_lupo_mountain

  PLB
  RTL
}

Sprite_Collectible_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw Pineapple
  dw Seashell
  dw SwordShield
  dw RockSirloin
if !ENABLE_SWORD_WARP_HOME == 1
  dw SwordWarp_Spin       ; 4
  dw SwordWarp_SwordUp    ; 5
  dw SwordWarp_Hold       ; 6
  dw SwordWarp_Flash      ; 7
  dw SwordWarp_Go         ; 8
endif

  Pineapple:
  {
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDA.l Pineapples : INC A : STA.l Pineapples
      STZ.w SprState, X
    +
    RTS
  }

  Seashell:
  {
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDA.l Seashells : INC A : STA.l Seashells
      STZ.w SprState, X
    +
    RTS
  }

  SwordShield:
  {
    %PlayAnimation(0,0,1)
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDY.b #$00 : STZ $02E9
      JSL Link_ReceiveItem
if !ENABLE_SWORD_WARP_HOME == 1
      ; Keep the slot: the sword-warp scene runs once the receipt ends
      ; (Sprite_CheckActive skips this sprite while SprFreeze is set).
      LDA.b #$04 : STA.w SprAction, X
else
      STZ.w SprState, X
endif
    +
    RTS
  }

if !ENABLE_SWORD_WARP_HOME == 1
  ; -------------------------------------------------------
  ; Sword warp home (decisions.org "Intro Abyss exit: the sword cuts Link
  ; home"): spin, sword up, white flash, then an overworld reload onto the
  ; Maku Tree area ($2A) through the house-exit cache path. No vanilla bytes.

  ; 4: Link spins the new sword (Underworld_StartVictorySpin $029C93,
  ; without its module).
  SwordWarp_Spin:
  {
    LDA.b $10 : CMP.b #$09 : BNE .wait
    LDA.b $5D : ORA.b $4D : BNE .wait ; default state, no recoil
      LDA.b #$01 : STA.w $0FFC        ; no menu during the scene
      STZ.w $02E4
      LDA.b #$02 : STA.b $2F          ; face the camera
      PHX
      JSL SwordWarp_VictorySpinLong
      JSL SwordWarp_TerminateInteractives
      JSL AncillaAdd_VictorySpin
      PLX
      INC.w SprAction, X
    .wait
    RTS
  }

  ; 5: spin over: hold the sword up (Underworld_RunVictorySpin $029CAD).
  SwordWarp_SwordUp:
  {
    LDA.b $5D : BNE .wait
      LDA.b #$01 : STA.w $02E4        ; Link stays put from here
      STA.w $03EF                     ; sword-up pose
      STA.w $037B                     ; no damage while he cannot move
      LDA.b #$2C : STA.w $012E        ; SFX2 sword up
      LDA.b #$20 : STA.w SprTimerA, X
      INC.w SprAction, X
    .wait
    RTS
  }

  ; 6: hold, then the slash and the flash start.
  SwordWarp_Hold:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b $9A : STA.w SprMiscA, X   ; color math to restore before the load
      LDA.b #$01 : STA.w $012E        ; SFX2 slash
      LDA.b #$20 : STA.w SprTimerA, X
      INC.w SprAction, X
    .wait
    RTS
  }

  ; 7: white ramp: add fixed color 0 -> 31 to every layer and the backdrop.
  SwordWarp_Flash:
  {
    LDA.b #$20 : SEC : SBC.w SprTimerA, X : CMP.b #$20 : BCC +
      LDA.b #$1F
    +
    STA.b $00
    LDA.b #$3F : STA.b $9A
    LDA.b $00 : ORA.b #$20 : STA.b $9C
    LDA.b $00 : ORA.b #$40 : STA.b $9D
    LDA.b $00 : ORA.b #$80 : STA.b $9E
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$08 : STA.w SprTimerA, X ; hold the white a moment
      INC.w SprAction, X
    .wait
    RTS
  }

  ; 8: warp. Module $08 with a cache room ($0128-$017F, no entrance uses
  ; them) runs LoadCachedEntranceProperties, which reads the overworld
  ; position from $7EC140-$7EC171 (every house exit uses this path).
  SwordWarp_Go:
  {
    LDA.w SprTimerA, X : BEQ .go
      RTS
    .go
    PHX
    REP #$20
    LDX.b #$30
    .copy
      LDA.l SwordWarp_Cache, X : STA.l $7EC140, X
    DEX #2 : BPL .copy
    STZ.w $0696                       ; no door tile, arrival faces down
    STZ.w $0698
    LDA.w #!SwordWarp_CacheRoom : STA.b $A0
    SEP #$20
    PLX

    ; Back on Kalyxo: SavedWorld = $00 is the escape that the respawn lock
    ; (LoadDarkWorldIntro, Overworld/overworld.asm) and the Part 0 storm
    ; (Part0Storm_EndIfBackOnKalyxo, Overworld/storm.asm) key on.
    LDA.b #$00 : STA.l SavedWorld
    STZ.w $0FFF                       ; world flag (sprites and GBC hooks)
    LDA.w $02B2 : CMP.b #$06 : BNE .not_gbc
      LDA.b #$10 : STA.b $BC          ; normal Link graphics (gbc_form.asm)
      STZ.w $02B2
    .not_gbc

    STZ.w $03EF
    STZ.w $02E4
    STZ.w $037B
    STZ.w $0FFC
    LDA.w SprMiscA, X : STA.b $9A
    LDA.b #$20 : STA.b $9C
    LDA.b #$40 : STA.b $9D
    LDA.b #$80 : STA.b $9E

    STZ.w $010A                       ; not a continue
    STZ.w $04AA                       ; not a respawn
    LDA.b #$80 : STA.b $13            ; forced blank for the load
    STZ.b $9B                         ; HDMA off
    STZ.b $11
    STZ.b $B0
    LDA.b #$08 : STA.b $10            ; Module $08: overworld load
    STZ.w SprState, X
    RTS
  }
endif

  RockSirloin:
  {
    JSL Sprite_Move
    LDA.l $7EF354 : BEQ .do_you_even_lift_bro
      JSL Sprite_CheckDamageToPlayer : BCC +
        JSL ThrownSprite_TileAndSpriteInteraction_long
        LDA.l RockMeat : INC A : STA.l RockMeat
        STZ.w SprState, X
    +
    .do_you_even_lift_bro
    RTS
  }

}

if !ENABLE_SWORD_WARP_HOME == 1
; Overworld cache image ($7EC140-$7EC171, LoadCachedEntranceProperties
; $02E5D4) for the arrival on LW $2A: Link at X $0530, Y $0AB0 (the old DW
; $6A pad spot); the house-exit walk then steps him ~19 px down the path.
; Scroll/trigger/VRAM words follow the ZScream exit formula
; (scroll = pos - 120/80, trigger = pos + 7/31); camera bounds and $0AA0-3
; as read in play on $2A (b29 flags, 2026-09-27). Recapture if $2A's size,
; graphics or palette change.
SwordWarp_Cache:
  dw $002A, $0016               ; $040A area, $1C main screen
  dw $0A60, $04B8               ; $E8/$E6 Y scroll, $E2/$E0 X scroll
  dw $0AB0, $0530               ; $20 Y, $22 X
  dw $002A, $0316               ; $8A area, $84 tilemap position
  dw $0ACF, $0537               ; $0618 / $061C camera triggers
  dw $0A00, $0B1E, $0400, $0500 ; $0600-$0606 camera bounds
  dw $0920, $0C00, $0300, $0600 ; $0610-$0616
  dw $2000, $0A3F               ; $0AA0-$0AA3 graphics bytes
  dw $0000                      ; $7EC168 (unused)
  dw $0000, $0000, $0000, $0000 ; $0624-$062A scroll offsets
endif

Sprite_Pineapple_Draw:
{
  JSL   Sprite_PrepOamCoord
  JSL   Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame,         X : TAY        ;Animation Frame
  LDA   .start_index,     Y : STA $06

  PHX
  LDX   .nbr_of_tiles,    Y              ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX                                    ; Save current Tile Index?

  TXA   : CLC : ADC $06                  ; Add Animation Index Offset

  PHA                                    ; Keep the value with animation index offset?

  ASL   A : TAX

  REP   #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y              ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX                                    ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY

  TYA   : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY   : INY

  PLX   : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00
  .nbr_of_tiles
  db 0
  .x_offsets
  dw 0
  .y_offsets
  dw 0
  .chr
  db $EE
  .properties
  db $33
  .sizes
  db $02
}

Sprite_SwordShield_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06


  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?

  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00
  .nbr_of_tiles
  db 2
  .x_offsets
  dw 0, 8, 8
  .y_offsets
  dw 0, 0, 8
  .chr
  db $C0, $EC, $FC
  .properties
  db $B5, $35, $35
  .sizes
  db $02, $00, $00
}

Sprite_RockSirloin_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06


  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?

  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00
  .nbr_of_tiles
  db 0
  .x_offsets
  dw 0
  .y_offsets
  dw 0
  .chr
  db $86
  .properties
  db $37
  .sizes
  db $02
}
