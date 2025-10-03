# Zora Princess

## Overview
The Zora Princess sprite (`!SPRID = Sprite_ZoraPrincess`) is a key NPC involved in a quest that culminates in Link receiving the Zora Mask. Her interactions are conditional, primarily triggered by Link playing the "Song of Healing," and her presence is tied to whether Link has already obtained the Zora Mask.

## Sprite Properties
*   **`!SPRID`**: `Sprite_ZoraPrincess` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `9`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `02`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_ZoraPrincess_Long`)
This routine handles the Zora Princess's drawing and dispatches to her main logic if the sprite is active.

```asm
Sprite_ZoraPrincess_Long:
{
  PHB : PHK : PLB
  JSR Sprite_ZoraPrincess_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_ZoraPrincess_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_ZoraPrincess_Prep`)
This routine initializes the Zora Princess upon spawning. It checks the Zora Mask flag (`$7EF302`). If Link already possesses the Zora Mask, the sprite immediately despawns (`STZ.w SprState, X`), ensuring the quest is a one-time event. It also sets `SprDefl, X` and `SprTileDie, X` to `0`.

```asm
Sprite_ZoraPrincess_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF302 : BEQ .doesnt_have_mask
    STZ.w SprState, X ; Kill the sprite
  .doesnt_have_mask

  LDA #$00 : STA.w SprDefl, X
  LDA #$00 : STA.w SprTileDie, X
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_ZoraPrincess_Main`)
This routine manages the Zora Princess's interactions and the process of granting the Zora Mask.

*   **Player Collision**: Prevents Link from passing through the Zora Princess (`JSL Sprite_PlayerCantPassThrough`).
*   **`WaitForLink`**: Plays an animation and displays a solicited message (`%ShowSolicitedMessage($0C5)`). Upon message dismissal, it transitions to `CheckForSongOfHealing`.
*   **`CheckForSongOfHealing`**: Plays an animation and checks the `SongFlag`. If the "Song of Healing" has been played, it clears the `SongFlag`, sets a timer (`SprTimerD, X`), and transitions to `ThanksMessage`.
*   **`ThanksMessage`**: Plays an animation. After a timer (`SprTimerD, X`), it displays an unconditional message (`%ShowUnconditionalMessage($0C6)`) and transitions to `GiveZoraMask`.
*   **`GiveZoraMask`**: After a timer (`SprTimerD, X`), it grants Link the Zora Mask (`LDY #$0F`, `JSL Link_ReceiveItem`), sets the Zora Mask obtained flag (`$7EF302` to `$01`), and despawns the sprite (`STZ.w SprState, X`).

```asm
Sprite_ZoraPrincess_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForLink
  dw CheckForSongOfHealing
  dw ThanksMessage
  dw GiveZoraMask

  WaitForLink:
  {
    %PlayAnimation(0, 1, 10)
    %ShowSolicitedMessage($0C5) : BCC .no_hablaba
      %GotoAction(1)
    .no_hablaba
    RTS
  }

  CheckForSongOfHealing:
  {
    %PlayAnimation(0, 1, 10)
    LDA.b SongFlag : BEQ .ninguna_cancion
      STZ.b SongFlag
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(2)
    .ninguna_cancion
    RTS
  }

  ThanksMessage:
  {
    %PlayAnimation(0, 1, 10)
    LDA.w SprTimerD,              X : BNE +
      %ShowUnconditionalMessage($0C6)
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  GiveZoraMask:
  {
    LDA.w SprTimerD, X : BNE +
      LDY   #$0F : STZ $02E9     ; Give the Zora Mask
      JSL   Link_ReceiveItem
      LDA   #$01 : STA.l $7EF302
      LDA.b #$00 : STA.w SprState, X
    +
    RTS
  }
}
```

## Drawing (`Sprite_ZoraPrincess_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_ZoraPrincess_Draw:
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
  db $00, $04
  .nbr_of_tiles
  db 3, 11
  .x_offsets
  dw -4, 4, -4, 4
  dw 4, 4, 4, 4, -4, -4, -4, -4, 12, 12, 12, 12
  .y_offsets
  dw -8, -8, 8, 8
  dw -8, 0, 8, 16, -8, 0, 8, 16, -8, 0, 8, 16
  .chr
  db $C0, $C1, $E0, $E1
  db $C1, $D1, $E1, $F1, $C3, $D3, $E3, $F3, $C3, $D3, $E3, $F3
  .properties
  db $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $73, $73, $73, $73
  .sizes
  db $02, $02, $02, $02
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
}
```

## Design Patterns
*   **Quest Gating/Progression**: The Zora Princess's appearance and the granting of the Zora Mask are conditional on Link not already possessing the mask and playing the "Song of Healing," integrating her into a specific questline.
*   **NPC Interaction**: The Zora Princess interacts with the player through dialogue and grants a key item (the Zora Mask), which is essential for progression.
*   **Conditional Spawning/Despawning**: The sprite dynamically despawns if Link has already obtained the Zora Mask, ensuring that the quest is a one-time event and preventing redundant interactions.
*   **Item Granting**: The Zora Princess serves as the source for the Zora Mask, a significant item that likely grants new abilities or access to new areas.
*   **Player Collision**: Implements `JSL Sprite_PlayerCantPassThrough` to make the Zora Princess a solid object that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
