; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_DekuLeaf
!NbrTiles           = 03  ; OAM slots - 1: 4 tiles (16 bytes)
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = $0D ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
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

%Set_Sprite_Properties(Sprite_DekuLeaf_Prep, Sprite_DekuLeaf_Long)

Sprite_DekuLeaf_Long:
{
  PHB : PHK : PLB
  LDA.b $8A : CMP.b #$3D : BEQ .whirlpool
    JSR Sprite_DekuLeaf_Draw
    BRA .run_main
  .whirlpool
    JSR Sprite_Whirlpool_Draw
  .run_main
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_DekuLeaf_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_DekuLeaf_Prep:
{
  PHB : PHK : PLB
  LDA.b $8A : CMP.b #$3D : BNE .not_whirlpool
    LDA.b #$01 : STA.w SprAction, X
  .not_whirlpool
  PLB
  RTL
}

Sprite_DekuLeaf_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForPlayer
  dw Whirlpool_Main

  WaitForPlayer:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 0, 10)

    ; Tick launch recoil & leaf-flutter burst countdown (24 -> 0 frames).
    LDA.w SprMiscD, X : BEQ +
      DEC A : STA.w SprMiscD, X
    +

    ; Re-arm per-launch burst once Link exits hover state $0A.
    LDA.b $5D : CMP.b #$0A : BEQ +
      STZ.w SprMiscB, X
    +

    ; 16-bit proximity check (40 px) while in Deku form -> approach breathing pulse.
    STZ.w SprMiscC, X
    LDA.w $02B2 : CMP.b #$01 : BNE .proximity_done
      REP #$20
      LDA.b $22 : SEC : SBC.w SprCachedX
      BPL + : EOR.w #$FFFF : INC A : +
      CMP.w #$0028 : BCS .prox_far
      LDA.b $20 : SEC : SBC.w SprCachedY
      BPL + : EOR.w #$FFFF : INC A : +
      CMP.w #$0028 : BCS .prox_far
      SEP #$20
      LDA.b #$01 : STA.w SprMiscC, X
      BRA .proximity_done
      .prox_far
      SEP #$20
    .proximity_done

    JSR CheckIfPlayerIsOn : BCC .not_on_flower
      LDA.b #$01 : STA.b $71
      LDA.w $02B2 : CMP.b #$01 : BNE .mark_on_only
        ; Detect burrow entry (0 -> 1) for a crisp sparkle cue (no white dust puff).
        LDA.w SprMiscA, X : BNE .already_burrowed
          LDA.b #$01 : STA.w SprMiscA, X
          JSL Sprite_SpawnSparkleGarnish
          RTS

        .already_burrowed
        ; Detect launch start ($5D == $0A) -> trigger recoil + leaf flutter burst once.
        LDA.b $5D : CMP.b #$0A : BNE .idle_burrow_rustle
          LDA.w SprMiscB, X : BNE .done_on
            JSR DekuLeaf_TriggerLaunchBurst
            RTS

        .idle_burrow_rustle
        ; Subtle periodic sparkle cue every 24 frames while standing/ready on the flower.
        LDA.b FrameCounter : AND.b #$1F : BNE .done_on
          JSL Sprite_SpawnSparkleGarnish
        .done_on
        RTS

      .mark_on_only
      LDA.b #$01 : STA.w SprMiscA, X
      RTS

    .not_on_flower
    ; Only clear $71 when leaving THIS flower so multiple flowers never clobber $71.
    LDA.w SprMiscA, X : BEQ .exit_wait
      STZ.w SprMiscA, X
      STZ.b $71
      ; Catch same-frame takeoff if Deku Link blasted out of the hitbox immediately.
      LDA.w $02B2 : CMP.b #$01 : BNE .exit_wait
      LDA.b $5D : CMP.b #$0A : BNE .exit_wait
      LDA.w SprMiscB, X : BNE .exit_wait
        JSR DekuLeaf_TriggerLaunchBurst
    .exit_wait
    RTS
  }

  DekuLeaf_TriggerLaunchBurst:
  {
    LDA.b #$01 : STA.w SprMiscB, X
    LDA.b #$18 : STA.w SprMiscD, X
    JSL Sprite_SpawnPoofGarnish
    JSL Sprite_SpawnSparkleGarnish
    RTS
  }

  Whirlpool_Main:
  {
    %PlayAnimation(0, 2, 10)
    JSR CheckIfPlayerIsOn : BCC .not_on

    LDA.w $0AAB : BEQ .not_on

      STZ.b $55    ; Reset cape flag
      STZ.w $0AAB  ; Reset underwater flag
      STZ.w $0351  ; Reset ripple flag
      STZ.w $037B  ; Reset invincibility flag
      ; Reset the mask with its sprite bank and palette. STZ $02B2 alone left
      ; the Zora Mask palette on Link's sprite (Discord 2025-01-01).
      LDA.w $02B2 : BEQ +
        PHX ; palette loaders clobber X (sprite slot)
        JSL ResetToLinkGraphics
        PLX
      +

      LDA.b $10 : CMP.b #$0B : BEQ .exit
        LDA.b $8A : AND.b #$40 : STA.b $7B : BEQ .no_mirror_portal
          LDA.b $20 : STA.w $1ADF
          LDA.b $21 : STA.w $1AEF
          LDA.b $22 : STA.w $1ABF
          LDA.b $23 : STA.w $1ACF
        .no_mirror_portal
        LDA.b #$23

        #SetGameModeLikeMirror:
        STA.b $11
        STZ.w $03F8
        LDA.b #$01 : STA.w $02DB
        STZ.b $B0
        STZ.b $27 : STZ.b $28
        LDA.b #$14 : STA.b $5D

    .not_on
    .exit
    RTS
  }
}

Sprite_DekuLeaf_Draw:
{
  ; Compute subtle breathing/bobbing/recoil offset ($08/$09) and frame (0=normal, 4=spring-crouch).
  STZ.b $08 : STZ.b $09
  LDA.w SprMiscD, X : BEQ .not_launching
    ; Launch recoil: age = $18 - timer (0..23)
    LDA.b #$18 : SEC : SBC.w SprMiscD, X
    CMP.b #$04 : BCS .recoil_rebound
      LDA.b #$02 : STA.b $08 ; compress +2px on blastoff
      LDA.b #$04 : BRA .draw_leaf
    .recoil_rebound
    CMP.b #$09 : BCS .draw_normal
      LDA.b #$FF : STA.b $08 : STA.b $09 ; pop rebound -1px
      BRA .draw_normal

  .not_launching
  ; Burrowed in flower: spring-loaded coiled breathing pulse every 8 frames.
  LDA.w SprMiscA, X : BEQ .check_approach
    LDA.b FrameCounter : AND.b #$08 : BEQ .draw_normal
      LDA.b #$01 : STA.b $08
      LDA.b #$04 : BRA .draw_leaf

  .check_approach
  ; Deku Link approaching within 40 px: lively welcoming breathing bob.
  LDA.w SprMiscC, X : BEQ .resting_breeze
    LDA.b FrameCounter : LSR #3 : AND.b #$03
    PHX : TAX
    LDA.w .approach_dy, X : STA.b $08
    BPL + : LDA.b #$FF : BRA ++ : + : LDA.b #$00 : ++
    STA.b $09
    LDA.w .approach_frame, X
    PLX
    BRA .draw_leaf

  .resting_breeze
  ; Serene idle swamp breeze: 1px upward lift for 16 of every 64 frames.
  LDA.b FrameCounter : AND.b #$30 : CMP.b #$20 : BNE .draw_normal
    LDA.b #$FF : STA.b $08 : STA.b $09

  .draw_normal
  LDA.b #$00
  .draw_leaf
  JSR DekuLeaf_DrawFrame : BCC .done
  LDA.w SprMiscD, X : BEQ .done
    JSR DekuLeaf_DrawLaunchBurst
  .done
  RTS

  .approach_dy
    db 0, -1, 0, 1
  .approach_frame
    db 0, 0, 0, 4
}

; 4 fluttering Page-0 green leaves ($72/$62, Pal 1 $32) bursting outward on launch.
; Uses Region C dynamically only while SprMiscD, X > 0 (24 frames); zero OAM leak.
DekuLeaf_DrawLaunchBurst:
{
  PHX
  ; age ($04) = $18 - SprMiscD, X (0..23)
  LDA.b #$18 : SEC : SBC.w SprMiscD, X : STA.b $04
  ; Allocate 4 x 8x8 OAM slots (16 bytes) above the flower.
  LDA.b #$10 : JSL OAM_AllocateFromRegionC

  STZ.b $05 ; particle index 0..3 (NW, NE, SW, SE)
  LDY.b #$00
  .next_leaf
    LDA.b $05 : CMP.b #$02 : BCS .lower_pair
      ; Upper pair (0=NW, 1=NE): fast outward & upward flutter
      LDA.b $04 : CLC : ADC.b #$04 : STA.b $06 ; |dx| = 4 + age
      LDA.b $04 : LSR A : CLC : ADC.b $04 : ADC.b #$02
      EOR.b #$FF : INC A : STA.b $07 ; dy = -(2 + 1.5*age)
      ; Gentle alternating horizontal/vertical flutter sway (+/-2 px)
      LDA.b $04 : LSR #2 : CLC : ADC.b $05 : AND.b #$01
      BEQ + : INC.b $07 : INC.b $07 : BRA .apply_x_sign : +
      DEC.b $07 : DEC.b $07
      BRA .apply_x_sign

    .lower_pair
      ; Lower pair (2=SW, 3=SE): wider base arc rising gently
      LDA.b $04 : LSR A : STA.b $06
      LDA.b $04 : LSR #2 : CLC : ADC.b $06 : ADC.b #$06 : STA.b $06 ; |dx| = 6 + 0.75*age
      LDA.b #$04 : SEC : SBC.b $04 : STA.b $07 ; dy = 4 - age

    .apply_x_sign
    ; Even index (0,2) -> left (-dx); odd index (1,3) -> right (+dx)
    LDA.b $05 : AND.b #$01 : BNE .x_pos_dir
      LDA.b $06 : EOR.b #$FF : INC A : STA.b $06
    .x_pos_dir

    ; Compute 16-bit screen X ($0A) = $00 + 4 + sext($06)
    LDA.b $06 : BPL + : LDA.b #$FF : BRA ++ : + : LDA.b #$00 : ++
    STA.b $0D : LDA.b $06 : STA.b $0C
    REP #$20
    LDA.b $00 : CLC : ADC.w #$0004 : CLC : ADC.b $0C : STA.b $0A
    SEP #$20

    ; Compute 16-bit screen Y ($0E) = $02 + 4 + sext($07)
    LDA.b $07 : BPL + : LDA.b #$FF : BRA ++ : + : LDA.b #$00 : ++
    STA.b $0D : LDA.b $07 : STA.b $0C
    REP #$20
    LDA.b $02 : CLC : ADC.w #$0004 : CLC : ADC.b $0C : STA.b $0E
    ; Clip cleanly to viewport [0..247] x [0..223]
    LDA.b $0A : CMP.w #$00F8 : BCS .hide_leaf
    LDA.b $0E : CMP.w #$00E0 : BCS .hide_leaf
    SEP #$20
    LDA.b $0A : STA.b ($90), Y : INY
    LDA.b $0E : STA.b ($90), Y : INY
    BRA .write_tile

    .hide_leaf
    SEP #$20
    LDA.b #$00 : STA.b ($90), Y : INY
    LDA.b #$F0 : STA.b ($90), Y : INY

    .write_tile
    ; Alternate resident Page-0 emerald bush-leaf tiles $E4 / $E5 (GID $CE at $C0-$FF)
    LDA.b $04 : LSR #2 : CLC : ADC.b $05 : AND.b #$01
    BEQ + : LDA.b #$E5 : BRA ++ : + : LDA.b #$E4 : ++
    STA.b ($90), Y : INY
    ; Tumbling H/V flip + prio 3 + Pal 1 emerald green + NT 0 ($32)
    LDA.b $04 : LSR #2 : CLC : ADC.b $05 : AND.b #$03
    CLC : ROR A : ROR A : ROR A : AND.b #$C0
    ORA.b #$32 : STA.b ($90), Y : INY

    ; High OAM slot = 8x8, X-msb=0
    PHY
    LDY.b $05
    LDA.b #$00 : STA.b ($92), Y
    PLY

    INC.b $05
    LDA.b $05 : CMP.b #$04 : BCS + : BRL .next_leaf : +

  PLX
  RTS
}

Sprite_Whirlpool_Draw:
{
  STZ.b $08 : STZ.b $09 ; Whirlpool never bobs vertically
  LDA.w SprFrame, X : CMP.b #$03 : BCC +
    LDA.b #$00
  +
  INC A
}

; Shared 4-tile Region B draw for Deku Leaf (frame 0 normal / frame 4 crouch)
; and Whirlpool (frames 1-3). Keeps flat water/surface sprites below Link and
; avoids !NbrTiles=0 OAM overflow by explicitly requesting $10 bytes (4 slots).
; Returns Carry set if drawn on-screen, Carry clear if clipped off-screen.
DekuLeaf_DrawFrame:
{
  PHA
  JSL Sprite_PrepOamCoord : BCC .check_viewport
    PLA
    CLC
    RTS
  .check_viewport
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0017 : CMP.w #$011F : BCS .clipped
  LDA.b $02 : CLC : ADC.w #$0017 : CMP.w #$00FF : BCC .draw_on_screen
  .clipped
    SEP #$20
    PLA
    CLC
    RTS
  .draw_on_screen
  LDA.b $02 : CLC : ADC.b $08 : STA.b $02
  SEP #$20
  LDA.b #$10
  JSL OAM_AllocateFromRegionB

  PLY
  LDA.w .start_index, Y : STA.b $06

  PHX
  LDX.w .nbr_of_tiles, Y ; amount of tiles - 1
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y ; Put the sprite out of the way
      STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA ($90), Y
    INY
    LDA.w .properties, X : STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY

    PLX : DEX : BPL .nextTile
  PLX
  SEC
  RTS

  ; Frame 0: Deku Leaf normal; Frames 1-3: Whirlpool; Frame 4: Deku Leaf crouch pulse
  .start_index
    db $00, $04, $08, $0C, $10
  .nbr_of_tiles
    db 3, 3, 3, 3, 3
  .x_offsets
    dw -8,  8,  8, -8
    dw -8,  8, -8,  8
    dw  8, -8,  8, -8
    dw -8,  8, -8,  8
    dw -7,  7,  7, -7
  .y_offsets
    dw  8,  8, -8, -8
    dw -8, -8,  8,  8
    dw -8, -8,  8,  8
    dw  8,  8, -8, -8
    dw  7,  7, -7, -7
  .chr
    db $A0, $A2, $82, $80
    db $C4, $C6, $E4, $E6
    db $C4, $C6, $E4, $E6
    db $C4, $C6, $E4, $E6
    db $A0, $A2, $82, $80
  .properties
    db $23, $23, $23, $23
    db $29, $29, $29, $29
    db $69, $69, $69, $69
    db $A9, $A9, $A9, $A9
    db $23, $23, $23, $23
}
