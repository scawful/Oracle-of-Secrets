# Mask Salesman

## Overview
The Mask Salesman sprite (`!SPRID = Sprite_MaskSalesman`) is a complex NPC that functions as a vendor and a quest-giver, offering masks for sale and teaching Link songs. His interactions are highly conditional, branching based on Link's inventory (Ocarina, learned songs, owned masks) and current rupee count.

## Sprite Properties
*   **`!SPRID`**: `Sprite_MaskSalesman` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Impervious to all attacks)
*   **`!SmallShadow`**: `01`
*   **`!Shadow`**: `01`
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

## Main Structure (`Sprite_MaskSalesman_Long`)
This routine handles the Mask Salesman's drawing and dispatches to its main logic if the sprite is active.

```asm
Sprite_MaskSalesman_Long:
{
  PHB : PHK : PLB
  JSR Sprite_MaskSalesman_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_MaskSalesman_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_MaskSalesman_Prep`)
This routine is empty, indicating that the Mask Salesman requires no custom initialization upon spawning.

## Main Logic & State Machine (`Sprite_MaskSalesman_Main`)
The Mask Salesman's core behavior is managed by a complex state machine that facilitates a branching dialogue and transaction system.

*   **Player Collision**: Prevents Link from passing through the Mask Salesman (`JSL Sprite_PlayerCantPassThrough`).
*   **`InquiryHandler`**: Plays an animation, checks Link's Ocarina status (`$7EF34C`), and displays a solicited message asking if Link wants to buy a mask. Based on Link's response (`$1CE8`) and inventory, it transitions to various states like `NoOcarina`, `HasOcarina`, `OfferBunnyHood`, `OfferStoneMask`, or `PlayerSaidNoToMask`.
*   **`NoOcarina`**: Displays a message instructing Link to get the Ocarina first, then returns to `InquiryHandler`.
*   **`HasOcarina`**: Displays a message acknowledging Link has the Ocarina, then transitions to `TeachLinkSong`.
*   **`TeachLinkSong`**: Increments Link's learned songs count (`$7EF34C`), plays a song learned sound, and returns to `InquiryHandler`.
*   **`OfferBunnyHood`**: Displays a message offering the Bunny Hood for 100 rupees, then transitions to `BoughtBunnyHood`.
*   **`OfferStoneMask`**: Displays a message offering the Stone Mask for 650 rupees, then transitions to `BoughtStoneMask`.
*   **`PlayerSaidNoToMask`**: Displays a message and returns to `InquiryHandler`.
*   **`PlayerHasAllMasks`**: Displays a message indicating Link has all masks, then returns to `InquiryHandler`.
*   **`BoughtBunnyHood`**: Processes Link's decision to buy the Bunny Hood. Checks rupee count, grants the item (`LDY #$10`, `JSL Link_ReceiveItem`), deducts rupees, displays a confirmation message, and returns to `InquiryHandler`. If rupees are insufficient, it transitions to `NotEnoughMoney`.
*   **`BoughtStoneMask`**: Similar to `BoughtBunnyHood`, but for the Stone Mask (`LDY #$19`) and a higher rupee cost.
*   **`NotEnoughMoney`**: Displays a message indicating insufficient funds, then returns to `InquiryHandler`.

```asm
Sprite_MaskSalesman_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw InquiryHandler
  dw NoOcarina
  dw HasOcarina
  dw TeachLinkSong
  dw OfferBunnyHood
  dw OfferStoneMask
  dw PlayerSaidNoToMask
  dw PlayerHasAllMasks
  dw BoughtBunnyHood
  dw BoughtStoneMask
  dw NotEnoughMoney

  ; 0x00
  InquiryHandler:
  {
    %PlayAnimation(0, 1, 16)
    ; Player has a Lv1 Ocarina, skip to the you got it message
    LDA.l $7EF34C : CMP.b #$01 : BEQ .has_ocarina
      ; Player has no Ocarina or Lv2 Ocarina
      ; Do you want to buy a mask?
      %ShowSolicitedMessage($E5) : BCC .didnt_converse
        LDA $1CE8 : BNE .player_said_no

        ; Player wants to buy a mask
        LDA.l $7EF34C : CMP.b #$02 : BCS .has_song_healing

          ; No Ocarina yet
          %GotoAction(1)
          RTS

    .has_ocarina
    %GotoAction(2)
    RTS

    .has_song_healing
      LDA.l $7EF348 : CMP.b #$01 : BCS .has_bunny_mask
      %GotoAction(4)
      RTS
    .has_bunny_mask
      LDA.l $7EF352 : CMP.b #$01 : BCS .has_stone_mask
      %GotoAction(5)
      RTS
    .has_stone_mask
      %GotoAction(7)
      RTS

    .player_said_no
      %GotoAction(6)
    .didnt_converse
    RTS
  }

  ; 0x01 - Link has not yet gotten the Ocarina
  NoOcarina:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($E9) ; Go get the Ocarina first!
    %GotoAction(0)
    RTS
  }

  ; 0x02 - Link has the Ocarina, but not all the songs
  HasOcarina:
  {
    %PlayAnimation(0, 1, 16)
    %ShowSolicitedMessage($081) ; Oh! You got it!
    %GotoAction(3)
    RTS
  }

  ; 0x03
  TeachLinkSong:
  {
    LDA #$02 : STA $7EF34C ; Increment the number of songs Link has
    LDA.b #$13
    STA.w $0CF8
    JSL $0DBB67 ;  Link_CalculateSFXPan
    ORA.w $0CF8
    STA $012E ; Play the song learned sound
    %GotoAction(0)
    RTS
  }

  ; 0x04 - Offer Bunny Hood
  OfferBunnyHood:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($07F) ; Bunny Hood for 100 rupees?
    %GotoAction(8)
    RTS
  }

  ; 0x05 - Offer Stone Mask
  OfferStoneMask:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($082) ; Stone Mask for 650 rupees?
    %GotoAction(9)
    RTS
  }

  ; 0x06 - Player said no to buying a mask
  PlayerSaidNoToMask:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($E8)
    %GotoAction(0)
    RTS
  }

  ; 0x07 - Player has all the masks
  PlayerHasAllMasks:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($028)
    %GotoAction(0)
    RTS
  }

  BoughtBunnyHood:
  {
    %PlayAnimation(0, 1, 16)
    LDA $1CE8 : BNE .player_said_no
      REP #$20
      LDA.l $7EF360 : CMP.w #$64 ; 100 rupees
      SEP #$30
      BCC .not_enough_rupees

        LDY.b #$10 ; Bunny Hood
        STZ.w $02E9
        PHX
        JSL Link_ReceiveItem
        PLX

        REP #$20
        LDA.l $7EF360
        SEC : SBC.w #$64 ; Subtract 100 rupees
        STA.l $7EF360
        SEP #$30

        %ShowUnconditionalMessage($063)

        %GotoAction(0)
        RTS

      .not_enough_rupees
      %GotoAction($0A)
      RTS
    .player_said_no
    %GotoAction(6)
    RTS
  }

  BoughtStoneMask:
  {
    %PlayAnimation(0, 1, 16)
    LDA $1CE8 : BNE .player_said_no
      REP #$20
      LDA.l $7EF360 : CMP.w #$352 ; 850 rupees
      SEP #$30
      BCC .not_enough_rupees

        LDY #$19 ; Stone Mask
        STZ.w $02E9
        PHX
        JSL Link_ReceiveItem
        PLX

        REP #$20
        LDA.l $7EF360
        SEC : SBC.w #$352 ; Subtract 850 rupees
        STA.l $7EF360
        SEP #$30

        %ShowUnconditionalMessage($055)
        %GotoAction(0)
        RTS

      .not_enough_rupees
      %GotoAction($0A)
      RTS
    .player_said_no
    %GotoAction(6)
    RTS
  }

  NotEnoughMoney:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($029)
    %GotoAction(0)
    RTS
  }
}
```

## Drawing (`Sprite_MaskSalesman_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_MaskSalesman_Draw:
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
  db 3, 3
.x_offsets
  dw -4, 12, 0, 0
  dw 4, -12, 0, 0
.y_offsets
  dw -8, -8, 0, -11
  dw -8, -8, 0, -10
.chr
  db $82, $84, $A0, $80
  db $82, $84, $A0, $80
.properties
  db $39, $39, $39, $39
  db $79, $79, $79, $39
.sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02

}
```

## Design Patterns
*   **Complex Dialogue and Shop System**: The Mask Salesman implements a sophisticated dialogue tree that functions as a shop, offering items (masks) and services (teaching songs) based on player choices and inventory. This creates a dynamic and interactive vendor experience.
*   **Quest Gating/Progression**: Interactions with the Mask Salesman are gated by Link's possession of the Ocarina and the number of songs he has learned, integrating the NPC into the game's progression system.
*   **Conditional Transactions**: The process of buying masks involves checking Link's current rupee count and deducting the cost upon a successful purchase, simulating a real in-game economy.
*   **Player Choice and Branching Dialogue**: Link's responses to the Mask Salesman's inquiries directly influence the flow of conversation and the available options, leading to a personalized interaction.
*   **Item Granting**: The Mask Salesman grants masks to Link and teaches him new songs, providing valuable rewards and abilities.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
