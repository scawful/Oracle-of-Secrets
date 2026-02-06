; =========================================================
; Maku Tree
;
; NARRATIVE ROLE: Central quest hub NPC who guides Link through the main
;   story. The Maku Tree is the guardian of Kalyxo Island and provides
;   dungeon guidance after the intro sequence. Serves as the "oracle"
;   figure who points Link toward the next objective.
;
; TERMINOLOGY: "Maku Tree" = MakuTree
;   - Guardian spirit of Kalyxo Island
;   - Provides dungeon map hints (MapIcon system)
;   - First major NPC after Kydrog encounter
;
; TRIGGER: Spawns at Maku Tree area (LW 0x2A) after intro sequence
;   - Plays Maku Song on entry if OOSPROG2 bit 2 is set
;
; STATES:
;   0: Handler - Check if met before, branch accordingly
;   1: MeetLink - First meeting, show message 0x20, give heart container
;   2: SpawnHeartContainer - Award heart container item
;   3: HasMetLink - Subsequent visits, show message 0x22
;
; MESSAGES:
;   0x20  - First meeting (introduces quest, dungeon guidance)
;   0x22  - Subsequent visits (generic, before any dungeon completion)
;   0x1C5 - Post-D1: hint toward Tail Palace (D2)
;   0x1C6 - Post-D3: hint toward Zora Temple (D4)
;   0x1C7 - Post-D5: hint toward Goron Mines (D6)
;   0x1C8 - Post-D2: hint toward Kalyxo Castle (D3)
;   0x1C9 - Post-D4: hint toward Glacia Estate (D5)
;   0x1CA - Post-D7: reserved (endgame)
;   0x1CB - Post-D6: hint toward Dragon Ship (D7)
;
; FLAGS WRITTEN:
;   MakuTreeQuest = 1 - Met Maku Tree
;   MapIcon = varies - Set to next dungeon based on progression
;   $7EF3D6 |= 0x02 - OOSPROG bit 1 (Hall of Secrets flag)
;
; FLAGS READ:
;   MakuTreeQuest - Check if already met
;   OOSPROG2 bit 2 - Check if Kydrog encounter done (for music)
;
; RELATED:
;   - farore.asm (leads Link to Maku area)
;   - kydrog.asm (sets OOSPROG2 bit 2)
;   - narrative_lockdown.md (story structure)
;
; ITEMS GIVEN:
;   0x3E - Heart Container (first meeting only)
; =========================================================

!SPRID              = Sprite_MakuTree
!NbrTiles           = 00  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = $0D ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0   ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_MakuTree_Prep, Sprite_MakuTree_Long)

Sprite_MakuTree_Long:
{
  PHB : PHK : PLB
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_MakuTree_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_MakuTree_Prep:
{
  PHB : PHK : PLB
  ; Play the Maku Song
  LDA.l OOSPROG2 : AND.b #$04 : BEQ +
    LDA.b #$03 : STA.w $012C
  +
  PLB
  RTL
}

PaletteFilter_StartBlindingWhite = $00EEF1
ApplyPaletteFilter = $00E914

Sprite_MakuTree_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw MakuTree_Handler
  dw MakuTree_MeetLink
  dw MakuTree_SpawnHeartContainer
  dw MakuTree_HasMetLink

  MakuTree_Handler:
  {
    ; Check the progress flags
    LDA.l MakuTreeQuest : AND.b #$01 : BNE .has_met_link
      %GotoAction(1)
      RTS
    .has_met_link
    %GotoAction(3)
    RTS
  }

  MakuTree_MeetLink:
  {
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %ShowUnconditionalMessage($20)
      LDA.b #$01 : STA.l MakuTreeQuest
      LDA.b #$01 : STA.l MapIcon ; Mushroom Grotto
      LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
      %GotoAction(2)
    .not_too_close
    RTS
  }

  MakuTree_SpawnHeartContainer:
  {
    ; Give Link a heart container
    LDY #$3E : JSL Link_ReceiveItem
    %GotoAction(3)
    RTS
  }

  MakuTree_HasMetLink:
  {
    ; Progressive hints based on dungeon completion.
    ; Check from latest progression to earliest so the
    ; most relevant hint is shown. Each hit advances MapIcon
    ; (world-map marker reveal threshold; see Overworld/world_map.asm)
    ; so more dungeon markers become visible.
    ;
    ; Uses JMP instead of BRA/BCC for long-distance branches
    ; (cascade exceeds ±127 byte BRA range).

    ; After D7 (Dragon Ship) → endgame / no further dungeon
    LDA.l Crystals
    AND.b #!Crystal_D7_DragonShip : BEQ .check_d6
      %ShowSolicitedMessage($1CA) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder endgame hint text
      JMP .talked

    .check_d6
    ; After D6 (Goron Mines) → hint toward Dragon Ship (D7)
    LDA.l Crystals
    AND.b #!Crystal_D6_GoronMines : BEQ .check_d5
      %ShowSolicitedMessage($1CB) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D7_DragonShip : STA.l MapIcon
      JMP .talked

    .check_d5
    ; After D5 (Glacia Estate) → hint toward Goron Mines (D6)
    LDA.l Crystals
    AND.b #!Crystal_D5_GlaciaEstate : BEQ .check_d4
      %ShowSolicitedMessage($1C7) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D6_GoronMines : STA.l MapIcon
      JMP .talked

    .check_d4
    ; After D4 (Zora Temple) → hint toward Glacia Estate (D5)
    LDA.l Crystals
    AND.b #!Crystal_D4_ZoraTemple : BEQ .check_d3
      %ShowSolicitedMessage($1C9) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D5_GlaciaEstate : STA.l MapIcon
      JMP .talked

    .check_d3
    ; After D3 (Kalyxo Castle) → hint toward Zora Temple (D4)
    LDA.l Crystals
    AND.b #!Crystal_D3_KalyxoCastle : BEQ .check_d2
      %ShowSolicitedMessage($1C6) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D4_ZoraTemple : STA.l MapIcon
      JMP .talked

    .check_d2
    ; After D2 (Tail Palace) → hint toward Kalyxo Castle (D3)
    LDA.l Crystals
    AND.b #!Crystal_D2_TailPalace : BEQ .check_d1
      %ShowSolicitedMessage($1C8) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D3_KalyxoCastle : STA.l MapIcon
      JMP .talked

    .check_d1
    ; After D1 (Mushroom Grotto) → hint toward Tail Palace (D2)
    LDA.l Crystals
    AND.b #!Crystal_D1_MushroomGrotto : BEQ .default
      %ShowSolicitedMessage($1C5) : BCS + : JMP .no_talk : + ; TODO(dialogue): placeholder hint text
      LDA.b #!MapIcon_D2_TailPalace : STA.l MapIcon
      JMP .talked

    .default
    ; Before any dungeon completion, show generic guidance
    %ShowSolicitedMessage($22) : BCS + : JMP .no_talk : +

    .talked
    LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
    .no_talk
    RTS
  }
}
