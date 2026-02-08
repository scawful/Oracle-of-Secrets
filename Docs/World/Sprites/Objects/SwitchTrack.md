# Switch Track

## Overview
The Switch Track sprite (`!SPRID = Sprite_SwitchTrack`) is an interactive object designed to function as a rotating segment of a minecart track. Its visual appearance and implied path change dynamically based on its `SprAction` (which represents its mode of rotation) and the on/off state of a corresponding switch, stored in `SwitchRam`.

## Sprite Properties
*   **`!SPRID`**: `Sprite_SwitchTrack` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `00`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `01`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `00`
*   **`!Persist`**: `01` (Continues to live off-screen)
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

## Main Structure (`Sprite_RotatingTrack_Long`)
This routine handles the Switch Track's drawing and dispatches to its main logic if the sprite is active.

```asm
Sprite_RotatingTrack_Long:
{
  PHB : PHK : PLB
  JSR Sprite_RotatingTrack_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_RotatingTrack_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_RotatingTrack_Prep`)
This routine initializes the Switch Track upon spawning. It sets `SprDefl, X` to `$80`. It then calculates the tile attributes of the tile directly above the switch track and sets `SprAction, X` based on the `SPRTILE` value (normalized by subtracting `$D0`). This `SprAction, X` likely determines the initial mode or orientation of the track.

```asm
Sprite_RotatingTrack_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X

  ; Setup Minecart position to look for tile IDs
  ; We use AND #$F8 to clamp to a 8x8 grid.
  ; Subtract 8 from the Y position to get the tile right above instead.
  LDA.w SprY, X : AND #$F8 : SEC : SBC.b #$08 : STA.b $00
  LDA.w SprYH, X : STA.b $01

  LDA.w SprX, X : AND #$F8 : STA.b $02
  LDA.w SprXH, X : STA.b $03

  ; Fetch tile attributes based on current coordinates
  LDA.b #$00 : JSL Sprite_GetTileAttr

  LDA.w SPRTILE : SEC : SBC.b #$D0 : STA.w SprAction, X

  PLB
  RTL
}
```

## Constants
*   **`SwitchRam = $0230`**: A WRAM address that stores the state (on/off) of each individual switch, indexed by its `SprSubtype`. This allows for multiple independent switch tracks.

## Main Logic & State Machine (`Sprite_RotatingTrack_Main`)
This routine manages the visual state of the Switch Track based on its `SprAction` (mode of rotation) and the corresponding switch state in `SwitchRam`.

*   **Modes**: The `SprAction, X` determines the mode of rotation, with four defined modes:
    *   `0` = TopLeft -> TopRight
    *   `1` = BottomLeft -> TopLeft
    *   `2` = TopRight -> BottomRight
    *   `3` = BottomRight -> BottomLeft
*   **State-Based Animation**: For each mode, the `SprFrame, X` (animation frame) is set based on the on/off state of the switch (`SwitchRam, Y`). This visually changes the track's orientation.

```asm
Sprite_RotatingTrack_Main:
{
  ; Get the subtype of the track so that we can get its on/off state.
  LDA.w SprSubtype, X : TAY

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw TopLeftToTopRight
  dw BottomLeftToTopLeft
  dw TopRightToBottomRight
  dw BottomRightToBottomLeft

  ; 00 = TopLeft -> TopRight
  TopLeftToTopRight:
  {
    LDA.w SwitchRam, Y : BNE .part2
      LDA.b #$00 : STA.w SprFrame, X
      RTS
    .part2
    LDA.b #$01 : STA.w SprFrame, X
    RTS
  }

  ; 01 = BottomLeft -> TopLeft
  BottomLeftToTopLeft:
  {
    LDA.w SwitchRam, Y : BNE .part2_c
      LDA.b #$03 : STA.w SprFrame, X
      RTS
    .part2_c
    LDA.b #$00 : STA.w SprFrame, X
    RTS
  }

  ; 02 = TopRight -> BottomRight
  TopRightToBottomRight:
  {
    LDA.w SwitchRam, Y : BNE .part2_a
      LDA.b #$01 : STA.w SprFrame, X
      RTS
    .part2_a
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }

  ; 03 = BottomRight -> BottomLeft
  BottomRightToBottomLeft:
  {
    LDA.w SwitchRam, Y : BEQ .part2_b
      LDA.b #$03 : STA.w SprFrame, X
      RTS
    .part2_b
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }
}
```

## Drawing (`Sprite_RotatingTrack_Draw`)
This routine handles OAM allocation and animation for the Switch Track. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_RotatingTrack_Draw:
{
  JSL Sprite_PrepOamCoord
  LDA.b #$04 : JSL OAM_AllocateFromRegionB

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

  LDA $00 : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : STA ($90), Y
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

  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00, $01, $02, $03
  .nbr_of_tiles
    db 0, 0, 0, 0
  .chr
    db $44
    db $44
    db $44
    db $44
  .properties
    db $3D
    db $7D
    db $FD
    db $BD
}
```

## Design Patterns
*   **Interactive Puzzle Element**: The Switch Track is a key puzzle element that changes its orientation based on an external switch (likely the `mineswitch` sprite), directly influencing the path of minecarts.
*   **State-Based Animation**: The track's animation frame (`SprFrame, X`) is directly controlled by the on/off state of a corresponding switch in `SwitchRam`, providing clear visual feedback to the player about its current configuration.
*   **Subtype-Driven State**: The `SprSubtype` is used to index into `SwitchRam`, allowing each individual Switch Track to maintain its own independent state. This enables complex puzzle designs with multiple, distinct switch tracks.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
