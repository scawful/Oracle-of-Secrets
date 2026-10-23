; =========================================================
; Kaepora Gaebora and Eon Owl

!SPRID              = Sprite_EonOwl
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
!DeflectProjectiles = 01  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 01  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_EonOwl_Prep, Sprite_EonOwl_Long)

; Eon Owl talk distance (!ENABLE_EON_OWL_NEAR_TRIGGER): the Owl talks when
; Link is within this many pixels on both axes (16-bit positions).
; scawful 2026-09-26: about 5 tiles. Tune by feel.
!EonOwl_TalkDistance = 80
!EonOwl_ArrivalTalkDistance = $20 ; two tiles; let Link take in the landing
; Arrival map $40 landing spot (scawful 2026-10-23: spot B, tile (44,34)).
!EonOwl_SpotB_X = $02C0 ; pixel 704
!EonOwl_SpotB_Y = $0220 ; pixel 544

Sprite_EonOwl_Long:
{
  PHB : PHK : PLB
  ; If it is not the Hall of Secrets map
  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    ; If the map doesn't have the 6 crystals
     LDA.l $7EF37A : AND.b #$7F : CMP.b #$77 : BNE .Despawn
        ; If the player has the Song of Soaring, despawn
        LDA.l $7EF34C : CMP.b #$04 : BCS .Despawn
          LDA.b #$01 : STA.w SprSubtype, X
          JSR Sprite_KaeporaGaebora_Draw
          JMP .HandleSprite
  .NotGaebora
if !ENABLE_EON_OWL_ONE_SHOT == 1
  ; Arrival owl is not drawn until it flies in.
  LDA.w SprAction, X : CMP.b #$06 : BEQ .HandleSprite
endif
  JSR Sprite_EonOwl_Draw
  .HandleSprite
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_EonOwl_Main
  .SpriteIsNotActive
  PLB
  RTL
  .Despawn
  STZ.w SprState, X
  PLB
  RTL
}

if !ENABLE_EON_OWL_ONE_SHOT == 1
; Arrival graphics: preserve the Zora/Master Sword sheets in slots 1-3.
; Area $40 places no Eon Scrub, so replace only slot 0's sheet $16 with the
; existing Eon Owl sheet $42. Area $7A shares spriteset $18 and is untouched.
; All vanilla sprite load paths reach this decompressor, including room exits
; and mosaic transitions. Do not write VRAM from the per-frame sprite draw.
pushpc
org $00E772 ; @hook module=Sprites name=EonOwl_ArrivalSheet kind=jml target=EonOwl_ArrivalSheet expected_m=8
  JML EonOwl_ArrivalSheet
  NOP
assert pc() == $00E777
pullpc

; Original entry: M=8, Y=sheet, DB=$00, DP destination=$00-$02.
; X and DB are preserved. Decompress resets Y before consuming its stream.
; Displaced: LDA.w $CFF3,Y : STA.b $CA. Return to the original high/low
; pointer loads, retaining the bank-$00 JSR/RTS return path.
EonOwl_ArrivalSheet:
{
  TYA : CMP.b #$16 : BNE .original
  LDA.w $0AA3 : CMP.b #$18 : BNE .original
  LDA.b $8A : CMP.b #$40 : BNE .original
  LDA.b $00 : BNE .original
  LDA.b $02 : CMP.b #$7E : BEQ .area_buffer
  CMP.b #$7F : BNE .original
  ; Mirror warp converts its temporary $7F4000 buffer directly into VRAM.
  LDA.b $01 : CMP.b #$40 : BNE .original
  BRA .replace
  .area_buffer
  ; Ordinary loads and the post-warp cache reload use $7E7800.
  LDA.b $01 : CMP.b #$78 : BNE .original
  .replace
    LDY.b #$42
    LDA.b #$42 : STA.l $7EC2FC
  .original
  LDA.w $CFF3,Y : STA.b $CA
  JML $00E777
}
endif

; =========================================================

Sprite_EonOwl_Prep:
{
  PHB : PHK : PLB

  STZ.w SprHitbox, X

  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    LDA.b #$20 : STA.w SprTimerA, X
    LDA.b #$03 : STA.w SprAction, X
  .NotGaebora
  LDA.w AreaIndex : CMP.b #$50 : BNE .not_intro
    ; If Map 0x50, don't spawn after getting sword
    LDA.l Sword : CMP.b #$01 : BCC .continue
       STZ.w SprState, X
    .continue
if !ENABLE_EON_OWL_ONE_SHOT == 1
    ; Second Abyss appearance ($E6): once per save, no respawn after the
    ; talk and fly-away (EonOwlFlags, Core/sram.asm).
    LDA.l EonOwlFlags : AND.b #!EonOwl_SwordTalked : BEQ .not_talked
      STZ.w SprState, X
    .not_talked
endif
  .not_intro
if !ENABLE_EON_OWL_ONE_SHOT == 1
  ; First Abyss appearance: arrival map $40 (sprite $0A placed in the base
  ; ROM; decisions.org "Abyss segment: fix direction"). Before the Pearl
  ; only, and once per save (EonOwl_ArrivalTalked).
  LDA.w AreaIndex : CMP.b #$40 : BNE .not_arrival
    LDA.l MoonPearl : BNE .no_arrival_owl
    LDA.l EonOwlFlags : AND.b #!EonOwl_ArrivalTalked : BNE .no_arrival_owl
      ; Hidden until Impa's arrival text ends, then flies in to spot B.
      LDA.b #$06 : STA.w SprAction, X
      BRA .not_arrival
    .no_arrival_owl
      STZ.w SprState, X
  .not_arrival
endif
  PLB
  RTL
}

; =========================================================

Sprite_EonOwl_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw EonOwl_Idle
  dw EonOwl_IntroDialogue
  dw EonOwl_FlyingAway

  dw KaeporaGaebora
  dw KaeporaGaebora_Respond
  dw KaeporaGaebora_FlyAway

if !ENABLE_EON_OWL_ONE_SHOT == 1
  dw EonOwl_ArrivalWait
  dw EonOwl_ArrivalFlyIn
  dw EonOwl_ArrivalLanded
endif

  EonOwl_Idle:
  {
    %PlayAnimation(0,1,16)
if !ENABLE_EON_OWL_NEAR_TRIGGER == 1
    JSR EonOwl_CarrySetIfLinkNear : BCC .not_too_close
else
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
endif
      %GotoAction(1)
    .not_too_close
    RTS
  }

  EonOwl_IntroDialogue:
  {
    %PlayAnimation(0,1,16)
if !ENABLE_EON_OWL_ONE_SHOT == 1
    ; First appearance (arrival map $40): message $1FA points to the Shrine
    ; of Origins. Marked done now, so the Owl does not come back.
    LDA.w AreaIndex : CMP.b #$40 : BNE .not_arrival_owl
      LDA.l EonOwlFlags : ORA.b #!EonOwl_ArrivalTalked : STA.l EonOwlFlags
      %ShowUnconditionalMessage($01FA)
      BRA .message_shown
    .not_arrival_owl
    ; Mark the map $50 appearance as done now, so leaving during the
    ; fly-away does not bring the Owl back.
    LDA.w AreaIndex : CMP.b #$50 : BNE .not_sword_owl
      LDA.l EonOwlFlags : ORA.b #!EonOwl_SwordTalked : STA.l EonOwlFlags
    .not_sword_owl
endif
    %ShowUnconditionalMessage($00E6)
if !ENABLE_EON_OWL_ONE_SHOT == 1
    .message_shown
endif
    LDA.b #$C0 : STA.w SprTimerA, X
    %GotoAction(2)
    RTS
  }

  EonOwl_FlyingAway:
  {
    %PlayAnimation(2,3,10)
    LDA.b #$F8 : STA.w SprYSpeed, X
    JSL   Sprite_Move

    LDA.w SprTimerA, X : CMP.b #$80 : BNE +
      LDA.b #$40 : STA.w SprXSpeed, X
    +

    LDA.w SprTimerA, X : BNE .not_done
      STZ.w SprState, X
    .not_done

    RTS
  }

  ; 0x03 - Kaepora Gaebora
  KaeporaGaebora:
  {
    %PlayAnimation(0,0,1)
    JSL GetDistance8bit_Long : CMP.b #$50 : BCC .not_ready
      LDA.w SprTimerA, X : BNE .not_ready
        %ShowUnconditionalMessage($146)
        %GotoAction(4)
    .not_ready
    RTS
  }

  KaeporaGaebora_Respond:
  {
    LDA $1CE8 : BNE .player_said_no
      %GotoAction(3)
      RTS
    .player_said_no
    %GotoAction(5)
    LDA.b #$60 : STA.w SprTimerA, X
    LDA.b #$04 : STA.l $7EF34C
    RTS
  }

  FlyAwaySpeed = 10
  KaeporaGaebora_FlyAway:
  {
    LDA.b #-FlyAwaySpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerA, X : BNE .not_ready
      STZ.w SprState, X
    .not_ready
    RTS
  }

if !ENABLE_EON_OWL_ONE_SHOT == 1
  ; 0x06 - Arrival (map $40), hidden. Module15 shows Impa's text ($35/$36)
  ; and then hands control to module $09, so the first active frame in
  ; module $09 is after the text. Start 32 px left of the camera.
  EonOwl_ArrivalWait:
  {
    LDA.b $10 : CMP.b #$09 : BNE .wait
      REP #$20
      LDA.b $E2 : SEC : SBC.w #$0020
      CMP.w #!EonOwl_SpotB_X-$20 : BCC +
        ; Camera is right of spot B (re-entry): start 112 px left of it.
        LDA.w #!EonOwl_SpotB_X-$70
      +
      SEP #$20
      STA.w SprX, X : XBA : STA.w SprXH, X
      REP #$20
      LDA.w #!EonOwl_SpotB_Y-$18
      SEP #$20
      STA.w SprY, X : XBA : STA.w SprYH, X
      LDA.b #$18 : STA.w SprXSpeed, X
      LDA.b #$05 : STA.w SprYSpeed, X
      LDA.b #$02 : STA.w SprFrame, X
      %GotoAction(7)
    .wait
    RTS
  }

  ; 0x07 - Fly right and down to spot B, then land.
  EonOwl_ArrivalFlyIn:
  {
    %PlayAnimation(2,3,10)
    JSL Sprite_Move

    LDA.w SprY, X : STA.b $00
    LDA.w SprYH, X : STA.b $01
    REP #$20
    LDA.b $00 : CMP.w #!EonOwl_SpotB_Y
    SEP #$20
    BCC .y_above
      STZ.w SprYSpeed, X
      LDA.b #!EonOwl_SpotB_Y&$FF : STA.w SprY, X
      LDA.b #!EonOwl_SpotB_Y>>8 : STA.w SprYH, X
    .y_above

    LDA.w SprX, X : STA.b $00
    LDA.w SprXH, X : STA.b $01
    REP #$20
    LDA.b $00 : CMP.w #!EonOwl_SpotB_X
    SEP #$20
    BCC .flying
      LDA.b #!EonOwl_SpotB_X&$FF : STA.w SprX, X
      LDA.b #!EonOwl_SpotB_X>>8 : STA.w SprXH, X
      LDA.b #!EonOwl_SpotB_Y&$FF : STA.w SprY, X
      LDA.b #!EonOwl_SpotB_Y>>8 : STA.w SprYH, X
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      STZ.w SprFrame, X
      LDA.b #$20 : STA.w SprTimerA, X
      %GotoAction(8)
    .flying
    RTS
  }

  ; 0x08 - Landed: a short pause, then $1FA by itself (no near trigger).
  EonOwl_ArrivalLanded:
  {
    %PlayAnimation(0,1,16)
    LDA.w SprTimerA, X : BNE .wait
      %GotoAction(1)
    .wait
    RTS
  }
endif
}

if !ENABLE_EON_OWL_NEAR_TRIGGER == 1
; Carry set when Link is within !EonOwl_TalkDistance px of the Owl on both
; axes. GetDistance8bit_Long uses only the low position bytes, so it fired
; from 248 px away (playtest: the Owl talked on area entry).
; M=8, X=8 (sprite index), keeps X. Uses $00-$03.
EonOwl_CarrySetIfLinkNear:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.w #!EonOwl_TalkDistance : STA.b $04
  LDA.b $8A : AND.w #$00FF : CMP.w #$0040 : BNE .distance_ready
    LDA.w #!EonOwl_ArrivalTalkDistance : STA.b $04
  .distance_ready
  LDA.b $22 : SEC : SBC.b $00 : BPL +
    EOR.w #$FFFF : INC A
  +
  CMP.b $04 : BCS .far
  LDA.b $20 : SEC : SBC.b $02 : BPL +
    EOR.w #$FFFF : INC A
  +
  CMP.b $04 : BCS .far
    SEP #$20
    SEC
    RTS
  .far
  SEP #$20
  CLC
  RTS
}

endif
; =========================================================

Sprite_EonOwl_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame,     X : TAY     ;Animation Frame
  LDA   .start_index, Y : STA $06

  PHX
  LDX   .nbr_of_tiles, Y ;amount of tiles -1
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
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
if !ENABLE_EON_OWL_ONE_SHOT == 1
  LDA.w AreaIndex : CMP.b #$40 : BNE .usual_sheet
  LDA.w $0AA3 : CMP.b #$18 : BNE .usual_sheet
    LDA .chr, X : AND.b #$3F ; arrival sheet $42 is in slot 0, not slot 3
    BRA .store_chr
  .usual_sheet
endif
  LDA .chr, X
if !ENABLE_EON_OWL_ONE_SHOT == 1
  .store_chr
endif
  STA ($90), Y
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
  db $00, $04, $06, $08
  .nbr_of_tiles
  db 3, 1, 1, 1
  .x_offsets
  dw 0, 0, 8, 8
  dw 8, -8
  dw -8, 8
  dw 8, -8
  .y_offsets
  dw 0, 8, 0, 8
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .chr
  db $C2, $D2, $C2, $D2
  db $C3, $C3
  db $C7, $C7
  db $C9, $C9
  .properties
  db $37, $37, $77, $77
  db $37, $77
  db $37, $77
  db $37, $77
  .sizes
  db $00, $00, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
}

Sprite_KaeporaGaebora_Draw:
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
  db 3
  .x_offsets
  dw -8, -8, 8, 8
  .y_offsets
  dw 0, -16, 0, -16
  .chr
  db $AE, $8E, $AE, $8E
  .properties
  db $3B, $3B, $7B, $7B
  .sizes
  db $02, $02, $02, $02
}
