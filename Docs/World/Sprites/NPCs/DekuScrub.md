# Deku Scrub

## Overview
The Deku Scrub sprite is a highly versatile NPC implementation capable of representing multiple distinct characters, including a Withered Deku Scrub, Deku Butler, and Deku Princess. Its behavior is intricately tied to game progression, player actions, and specific in-game locations.

## Sprite Properties
*   **`!SPRID`**: `Sprite_DekuScrubNPCs` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `06`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `03`
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

## Main Structure (`Sprite_DekuScrub_Long`)
This routine is the main entry point for the Deku Scrub, executed every frame. It handles drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_DekuScrub_Long:
{
  PHB : PHK : PLB
  JSR Sprite_DekuScrub_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_DekuScrub_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_DekuScrub_Prep`)
This routine runs once when the Deku Scrub is spawned. It sets `SprDefl, X` and then determines the initial `SprAction, X` based on the current `AreaIndex`, `SprSubtype, X`, and whether the Deku Mask has been obtained (`$7EF301`). It also checks if Tail Palace is cleared (`Crystals`) to potentially set `SprState, X` to `0`.

```asm
Sprite_DekuScrub_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X

  ; Peacetime Deku Scrub NPCs
  LDA.b AreaIndex : CMP.b #$2E : BNE .check_next
    ; Deku Butler
    LDA.b #$07 : STA.w SprAction, X
    JMP +
  .check_next
  CMP.b #$2F : BNE .continue
    LDA.b #$08 : STA.w SprAction, X
    JMP +
  .continue

  LDA.w SprSubtype, X : CMP.b #$01 : BEQ .DekuButler
                        CMP.b #$02 : BEQ .DekuPrincess
  LDA.l $7EF301 : BEQ +
    LDA.b #$04 : STA.w SprAction, X
    JMP +
  .DekuButler
    LDA.b #$05 : STA.w SprAction, X
    JMP ++
  .DekuPrincess
    LDA.b #$06 : STA.w SprAction, X
    ++
    ; Check if tail palace is cleared
    LDA.l Crystals : AND #$10 : BEQ +
      STZ.w SprState, X
  +
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_DekuScrub_Main`)
The Deku Scrub's core behavior is managed by a complex state machine with several states, many of which are named in Spanish:

*   **`EstadoInactivo` (Inactive State)**: The scrub plays an idle animation, prevents player passage, and transitions to `QuiereCuracion` upon player interaction.
*   **`QuiereCuracion` (Wants Healing)**: Plays an animation and checks if the "Song of Healing" (`SongFlag`) has been played. If so, it clears the flag, sets a timer, and transitions to `DarMascara`.
*   **`DarMascara` (Give Mask)**: Plays an animation, displays a message after a timer, and then transitions to `Regalo`.
*   **`Regalo` (Gift)**: After a timer, grants Link the Deku Mask (`$11`) and updates the Deku Mask flag (`$7EF301`), then transitions to `Withered`.
*   **`Withered`**: Plays a withered animation.
*   **`DekuButler`**: Plays a specific animation, prevents player passage, and displays a message.
*   **`DekuPrincess`**: Plays a specific animation, prevents player passage, and displays a message.
*   **`DekuButler_Peacetime`**: Plays a specific animation, prevents player passage, and displays a message. If the message is dismissed, it sets `MapIcon` to `$02`.
*   **`DekuPrinces_Peacetime`**: Plays a specific animation, prevents player passage, and displays a message. If the message is dismissed, it sets `MapIcon` to `$02`.

```asm
Sprite_DekuScrub_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw EstadoInactivo
  dw QuiereCuracion
  dw DarMascara
  dw Regalo
  dw Withered
  dw DekuButler
  dw DekuPrincess

  dw DekuButler_Peacetime
  dw DekuPrinces_Peacetime

  EstadoInactivo:
  {
    %PlayAnimation(0, 1, 16)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($140) : BCC .no_hablaba
      %GotoAction(1)
    .no_hablaba
    RTS
  }

  QuiereCuracion:
  {
    %PlayAnimation(0, 1, 16)
    LDA.b SongFlag : CMP.b #$01 : BNE .ninguna_cancion
      STZ.b SongFlag
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(2)
    .ninguna_cancion
    RTS
  }

  DarMascara:
  {
    %PlayAnimation(0, 1, 16)
    LDA.w SprTimerD, X : BNE +
      %ShowUnconditionalMessage($141)
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  Regalo:
  {
    LDA.w SprTimerD, X : BNE +
      LDY   #$11 : STZ $02E9     ; Give the Deku Mask
      JSL   Link_ReceiveItem
      LDA.b #$01 : STA.l $7EF301
      %GotoAction(4)
    +
    RTS
  }

  Withered:
  {
    %PlayAnimation(2, 2, 10)
    RTS
  }

  DekuButler:
  {
    %PlayAnimation(3, 3, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($080)
    RTS
  }

  DekuPrincess:
  {
    %PlayAnimation(4, 4, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($0C3)
    RTS
  }

  DekuButler_Peacetime:
  {
    %StartOnFrame(3)
    %PlayAnimation(3, 3, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($1B9) : BCC +
      LDA.b #$02 : STA.l MapIcon
    +
    RTS
  }

  DekuPrinces_Peacetime:
  {
    %StartOnFrame(4)
    %PlayAnimation(4, 4, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($1BA) : BCC +
      LDA.b #$02 : STA.l MapIcon
    +
    RTS
  }
}
```

## Drawing (`Sprite_DekuScrub_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_DekuScrub_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

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
    db $00, $04, $08, $0C, $10
  .nbr_of_tiles
    db 3, 3, 3, 3, 3
  .x_offsets
    dw 4, 4, -4, -4
    dw 4, -4, -4, 4
    dw -8, -8, 8, 8
    dw -4, 4, -4, 4
    dw -4, -4, 4, 4
  .y_offsets
    dw 4, -4, -4, 4
    dw 4, 4, -4, -4
    dw 4, -12, -12, 4
    dw -12, -12, 4, 4
    dw 4, -12, 4, -12
  .chr
    db $2E, $0E, $0E, $2E
    db $2C, $2C, $0C, $0C
    db $20, $00, $02, $22
    db $04, $05, $24, $25
    db $27, $07, $27, $07
  .properties
    db $3B, $7B, $3B, $7B
    db $3B, $7B, $3B, $7B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $7B, $7B
  .sizes
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
}
```

## Design Patterns
*   **Multi-Character NPC**: A single sprite definition is used to represent multiple distinct NPC characters (Withered Deku Scrub, Deku Butler, Deku Princess), with their specific roles determined by `SprSubtype` and `AreaIndex`.
*   **Quest Progression Integration**: The sprite's behavior is deeply integrated with various quest elements, checking for specific items (Deku Mask), songs (Song of Healing), and cleared dungeons (Tail Palace) to determine its current state and interactions.
*   **Conditional Behavior**: Extensive use of conditional logic based on `AreaIndex`, `SprSubtype`, and global game state flags allows for dynamic changes in the NPC's role, dialogue, and actions.
*   **NPC Interaction**: Provides rich interaction with the player through dialogue (`%ShowSolicitedMessage`, `%ShowUnconditionalMessage`) and the granting of key items (`Link_ReceiveItem`).
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the NPC a solid object that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, essential for accurate sprite rendering.
