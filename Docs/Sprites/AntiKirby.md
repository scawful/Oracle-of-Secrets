# Anti Kirby Sprite Analysis

## 1. Overview
The Anti Kirby sprite (`Sprite_AntiKirby`) is an enemy that exhibits unique behaviors, including a "suck" attack that can steal Link's items (bombs, arrows, rupees, or shield). It has distinct states for walking, sucking, being full (after stealing an item), and being "hatted" (presumably after Link gets his item back or a specific condition is met).

## 2. Sprite Properties
The sprite properties are defined at the beginning of `Sprites/Enemies/anti_kirby.asm`:

```asm
!SPRID              = Sprite_AntiKirby
!NbrTiles           = 02
!Harmless           = 00
!HVelocity          = 00
!Health             = $08
!Damage             = 04
!DeathAnimation     = 00
!ImperviousAll      = 00
!SmallShadow        = 00
!Shadow             = 01
!Palette            = 00
!Hitbox             = 03
!Persist            = 00
!Statis             = 00
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 00
!ImpervSwordHammer  = 00
!Boss               = 00
```

**Key Observations:**
*   `!SPRID = Sprite_AntiKirby`: This uses a named constant for the sprite ID, which is good practice.
*   `!Health = $08`: Anti Kirby has 8 health points.
*   `!Damage = 04`: Deals half a heart of damage to Link.
*   `!Hitbox = 03`: A relatively small hitbox.
*   `!Shadow = 01`: It draws a shadow.
*   `!Boss = 00`: It is not classified as a boss sprite, despite its complex behavior.

## 3. Main Structure (`Sprite_AntiKirby_Long`)
This routine follows the standard structure for sprites, calling the draw routine, shadow routine, and then the main logic if the sprite is active.

```asm
Sprite_AntiKirby_Long:
{
  PHB : PHK : PLB
  JSR Sprite_AntiKirby_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_AntiKirby_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## 4. Initialization (`Sprite_AntiKirby_Prep`)
The `_Prep` routine initializes several sprite-specific variables and sets its `SprBump`, `SprHealth`, and `SprPrize` based on Link's current sword level (or a similar progression metric, inferred from `LDA.l Sword : DEC : TAY`). This is an interesting way to scale enemy difficulty.

```asm
Sprite_AntiKirby_Prep:
{
  PHB : PHK : PLB
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprMiscB, X
  LDA.l Sword : DEC : TAY
  LDA .bump_damage, Y : STA.w SprBump, X
  LDA .health, Y : STA.w SprHealth, X
  LDA .prize_pack, Y : STA.w SprPrize, X
  PLB
  RTL

  .bump_damage
    db $81, $88, $88, $88
  .health
    db 06, 10, 20, 20
  .prize_pack
    db 6, 3, 3, 3
}
```
**Insight:** The use of `LDA.l Sword : DEC : TAY` to index into `.bump_damage`, `.health`, and `.prize_pack` tables demonstrates a dynamic difficulty scaling mechanism based on player progression (likely sword upgrades). This is a valuable pattern for making enemies adapt to the player's power level.

## 5. Main Logic & State Machine (`Sprite_AntiKirby_Main`)
The `_Main` routine implements a complex state machine using `JSL JumpTableLocal` and a series of `dw` (define word) entries pointing to different states.

```asm
Sprite_AntiKirby_Main:
{
  JSL Sprite_IsToRightOfPlayer
  TYA : CMP #$01 : BNE .WalkRight
    .WalkLeft
    LDA.b #$40 : STA.w SprMiscC, X
    JMP +
  .WalkRight
  STZ.w SprMiscC, X
  +

  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw AntiKirby_Main       ; State 0: Normal movement/attack
  dw AntiKirby_Hurt       ; State 1: Recoiling from damage
  dw AntiKirby_BeginSuck  ; State 2: Initiating suck attack
  dw AntiKirby_Sucking    ; State 3: Actively sucking Link
  dw AntiKirby_Full       ; State 4: Full after stealing item
  dw AntiKirby_Hatted     ; State 5: Hatted (after Link gets item back?)
  dw AntiKirby_HattedHurt ; State 6: Hatted and hurt
  dw AntiKirby_Death      ; State 7: Death animation

  ; ... (State implementations below) ...
}
```

**State Breakdown:**
*   **`AntiKirby_Main` (State 0):**
    *   Checks health and transitions to `AntiKirby_Full` if health is low (this seems like a bug, should probably be `AntiKirby_Death`).
    *   Randomly initiates the `AntiKirby_BeginSuck` state.
    *   Plays walking animation (`%PlayAnimation(0, 2, 10)`).
    *   Handles damage from player and transitions to `AntiKirby_Hurt`.
    *   Deals damage to Link on contact (`%DoDamageToPlayerSameLayerOnContact()`).
    *   Moves toward Link (`%MoveTowardPlayer(8)`) and bounces from tile collisions.
*   **`AntiKirby_Hurt` (State 1):** Plays a hurt animation and waits for a timer (`SprTimerA`) to expire before returning to `AntiKirby_Main`.
*   **`AntiKirby_BeginSuck` (State 2):**
    *   Plays a "suck" animation (`%PlayAnimation(4, 5, 10)`).
    *   Checks for damage from player.
    *   Checks Link's proximity (`$0E`, `$0F` are likely relative X/Y coordinates to Link). If Link is close enough, it transitions to `AntiKirby_Sucking` and sets up a projectile speed towards Link.
*   **`AntiKirby_Sucking` (State 3):**
    *   Plays a "sucking" animation (`%PlayAnimation(5, 5, 10)`).
    *   Uses `JSL Sprite_DirectionToFacePlayer` and `JSL DragPlayer` to pull Link towards it if he's close enough.
    *   If Link is very close, it "consumes" Link, storing Link's position in `SprMiscB` and `SprMiscA`, sets a timer, and transitions to `AntiKirby_Full`.
*   **`AntiKirby_Full` (State 4):**
    *   Plays a "full" animation (`%PlayAnimation(10, 10, 10)`).
    *   Sets Link's position to the stored `SprMiscA`/`SprMiscB` (effectively "spitting" Link out).
    *   Transitions to `AntiKirby_Hatted` after a timer.
*   **`AntiKirby_Hatted` (State 5):**
    *   Plays a "hatted" animation (`%PlayAnimation(6, 8, 10)`).
    *   Moves toward Link, deals damage, and handles damage from player (transitions to `AntiKirby_HattedHurt`).
*   **`AntiKirby_HattedHurt` (State 6):** Plays a hurt animation for the "hatted" state and returns to `AntiKirby_Hatted`.
*   **`AntiKirby_Death` (State 7):** Sets `SprState` to `$06` (likely a death state) and plays a sound effect.

**Insight:** The `AntiKirby_Main` state's health check `LDA.w SprHealth, X : CMP.b #$01 : BCS .NotDead : %GotoAction(4)` seems to incorrectly transition to `AntiKirby_Full` (State 4) instead of `AntiKirby_Death` (State 7) when health is 0. This might be a bug or an intentional design choice for a specific game mechanic.

## 6. Item Stealing Logic (`AntiKirby_StealItem`)
This is a separate routine that is likely called when Anti Kirby successfully "sucks" Link. It checks Link's inventory and steals a random item (bomb, arrow, rupee, or shield).

```asm
AntiKirby_StealItem:
{
  REP #$20
  ; ... (collision checks) ...
  SEP #$20
  LDA.w SprTimerA, X : CMP.b #$2E : BCS .exit ; Timer check
    JSL GetRandomInt
    AND.b #$03
    INC A
    STA.w SprMiscG, X
    STA.w SprMiscE, X

    CMP.b #$01 : BNE .dont_steal_bomb
      LDA.l $7EF343 : BEQ .dont_steal_anything ; Check bombs
        DEC A
        STA.l $7EF343
        RTS
      .dont_steal_anything
      SEP #$20
      STZ.w SprMiscG,X
      RTS
    .dont_steal_bomb

    CMP.b #$02 : BNE .dont_steal_arrow
      LDA.l $7EF377 : BEQ .dont_steal_anything ; Check arrows
        DEC A
        STA.l $7EF377
        RTS
    .dont_steal_arrow

    CMP.b #$03 : BNE .dont_steal_rupee
      REP #$20
      LDA.l $7EF360 : BEQ .dont_steal_anything ; Check rupees
        DEC A
        STA.l $7EF360
    .exit
    SEP #$20
    RTS
  ; -----------------------------------------------------

  .dont_steal_rupee
  LDA.l $7EF35A : STA.w SprSubtype, X : BEQ .dont_steal_anything ; Check shield
    CMP.b #$03 : BEQ .dont_steal_anything
      LDA.b #$00
      STA.l $7EF35A
      RTS
}
```
**Key Observations:**
*   Uses `REP #$20` and `SEP #$20` to explicitly control the accumulator size (16-bit for address calculations, 8-bit for item counts). This is crucial for correct memory access.
*   Randomly selects an item to steal using `JSL GetRandomInt : AND.b #$03 : INC A`.
*   Directly modifies SRAM addresses (`$7EF343` for bombs, `$7EF377` for arrows, `$7EF360` for rupees, `$7EF35A` for shield) to decrement item counts or remove the shield.
*   The shield stealing logic (`LDA.l $7EF35A : STA.w SprSubtype, X : BEQ .dont_steal_anything : CMP.b #$03 : BEQ .dont_steal_anything : LDA.b #$00 : STA.l $7EF35A`) is a bit convoluted. It seems to check the shield type and only steals if it's not a specific type (possibly the Mirror Shield, which is type 3).

**Insight:** The `AntiKirby_StealItem` routine is a good example of how to interact directly with Link's inventory in SRAM. It also highlights the importance of explicitly managing the processor status flags (`REP`/`SEP`) when dealing with mixed 8-bit and 16-bit operations, especially when accessing memory.

## 7. Drawing (`Sprite_AntiKirby_Draw`)
The drawing routine uses `JSL Sprite_PrepOamCoord` and `JSL Sprite_OAM_AllocateDeferToPlayer` for OAM management. It then uses a series of tables (`.start_index`, `.nbr_of_tiles`, `.x_offsets`, `.y_offsets`, `.chr`, `.properties`, `.sizes`) to define the sprite's animation frames and tile data.

```asm
Sprite_AntiKirby_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprFlash, X : STA $08
  LDA.w SprMiscC, X : STA $09

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  ; ... (OAM manipulation logic) ...

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $08, $0A, $0C, $0E, $10
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1
  ; ... (other OAM tables) ...
}
```
**Key Observations:**
*   The drawing logic includes a check for `SprMiscC, X` to determine if the sprite is facing left or right, and uses different `.x_offsets` tables (`.x_offsets` vs `.x_offsets_2`) accordingly. This is a common pattern for horizontal flipping.
*   The `.properties` table defines the palette, priority, and flip bits for each tile.
*   The `.sizes` table defines the size of each tile (e.g., `$02` for 16x16).

## 8. Advanced Design Patterns Demonstrated

*   **Dynamic Difficulty Scaling:** The `_Prep` routine adjusts health, bump damage, and prize based on `Link's Sword` level.
*   **Complex State Machine:** The `_Main` routine uses a jump table to manage multiple distinct behaviors (walking, sucking, full, hatted, hurt, death).
*   **Direct SRAM Interaction:** The `AntiKirby_StealItem` routine directly modifies Link's inventory in SRAM, demonstrating how to implement item-related mechanics.
*   **Explicit Processor Status Management:** The `AntiKirby_StealItem` routine explicitly uses `REP #$20` and `SEP #$20` to ensure correct 8-bit/16-bit operations when accessing SRAM.
*   **Conditional Drawing/Flipping:** The `_Draw` routine uses `SprMiscC, X` to conditionally flip the sprite horizontally.
