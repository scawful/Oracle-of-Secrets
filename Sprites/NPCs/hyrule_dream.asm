Sprite_HyruleDream_Prep:
{
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    ; Wisdom scene actors (subtypes $D1/$D2, Sprites/NPCs/dream_wisdom.asm),
    ; Power scene actors ($D3/$D4, Sprites/NPCs/dream_power.asm)
    LDA.w SprSubtype, X : CMP.b #!DreamWisdom_SubCaptain : BCC .by_room
      if !ENABLE_DREAM_POWER_SCENE == 1
        CMP.b #!DreamPower_SubKing : BCC .wisdom
          JMP DreamPower_Prep
        .wisdom
      endif
      JMP DreamWisdom_Prep
    .by_room
  endif
  LDA.b ROOM : CMP.b #$51 : BEQ .king
               CMP.b #$60 : BEQ .soldier
               LDA.b #$00 : JMP .done
  .king
  LDA.b #$01 : JMP .done
  .soldier
  LDA.b #$02
  .done
  STA.w SprAction, X
  RTS
}

Sprite_HyruleDream_Main:
{
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    LDA.w SprSubtype, X : CMP.b #!DreamWisdom_SubCaptain : BCC .by_room
      if !ENABLE_DREAM_POWER_SCENE == 1
        CMP.b #!DreamPower_SubKing : BCC .wisdom
          JMP DreamPower_Main
        .wisdom
      endif
      JMP DreamWisdom_Main
    .by_room
  endif
  %SpriteJumpTable(Zelda_Idle,
                   King_Idle,
                   Soldier_Idle)

  Zelda_Idle:
  {
    STZ.w SprFrame, X
    RTS
  }

  King_Idle:
  {
    LDA.b #$01 : STA.w SprFrame, X
    RTS
  }

  Soldier_Idle:
  {
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }
}

Sprite_HyruleDream_Draw:
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

  ; Frames 0 Zelda, 1 King, 2 Soldier (room actors). Wisdom scene
  ; (dream_wisdom.asm): 3 Captain stand-in (the soldier, head lowered),
  ; 4 Farore standing, 5 her step, head facing left toward the Captain,
  ; 6 her hand on the Captain's shoulder: new body $CE + hand $F1
  ; (DreamWisdom_LoadReachGfx), head bowed 1 px; 3 pieces = the $73 OAM
  ; budget (sheet $55 in slot 3: her chars +$40; poses: wisdom_scene
  ; farore_poses, pose B).
  ; Power scene (dream_power.asm): the king is frame 1 (sheet $35 in slot 2);
  ; Farore 7 back to the camera, 8/9 her walk up, 10 facing the camera
  ; (farore.asm frames 5, 3, 4 and 0 with sheet $55 in slot 3: chars +$40).
  ; Wisdom fall (dream_power.asm): 11 empty (one piece pushed off screen:
  ; Farore gone, a man blinking out), 12 Kydrog's silhouette (his pirate
  ; frame, kydrog.asm, with sheet $42 in slot 1: chars -$80; OBJ palette 6).
  .start_index
  db $00, $03, $07
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db $0A, $0D, $0F, $11
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    db $14, $16, $18, $1A
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    db $1C, $1D
  endif
  .nbr_of_tiles
  db 2, 3, 2
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db 2, 1, 1, 2
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    db 1, 1, 1, 1
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    db 0, 5
  endif
  .x_offsets
  dw -8, 8, 0
  dw -8, 8, -8, 8
  dw -4, 4, 0
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    dw -4, 4, 0
    dw 0, 1
    dw 0, 1
    dw 0, -8, 0
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    dw 0
    dw -8, 8, 8, -8, -8, 8
  endif
  .y_offsets
  dw -4, -4, -14
  dw -16, -16, 0, 0
  dw -4, -4, -14
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    dw -2, -2, -10
    dw 4, -7
    dw 4, -7
    dw 4, 6, -6
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    dw -8, 4
    dw -8, 4
    dw 4, -7
    dw -8, 4
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    dw 240
    dw -12, -12, 4, 4, 20, 20
  endif
  .chr
  db $A8, $A8, $84
  db $8E, $8E, $AE, $AE
  db $A4, $A4, $A6
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db $A4, $A4, $A6
    db $EA, $C6
    db $C8, $C6
    db $CE, $F1, $C6
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    db $CA, $EC
    db $CA, $CC
    db $CC, $CA
    db $E8, $EA
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    db $00
    db $4C, $4E, $6E, $6C, $68, $6A
  endif
  .properties
  db $39, $79, $39
  db $39, $79, $39, $79
  db $39, $79, $39
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db $39, $79, $39
    db $3B, $3B
    db $7B, $3B
    db $3B, $3B, $3B
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    db $3B, $3B
    db $3B, $3B
    db $7B, $3B
    db $3B, $3B
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    db $3B
    db $3D, $3D, $3D, $3D, $3D, $3D
  endif
  .sizes
  db $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    db $02, $02, $02
    db $02, $02
    db $02, $02
    db $02, $00, $02
  endif
  if !ENABLE_DREAM_POWER_SCENE == 1
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
  endif
  if !ENABLE_DREAM_WISDOM_FALL == 1
    db $00
    db $02, $02, $02, $02, $02, $02
  endif
}
