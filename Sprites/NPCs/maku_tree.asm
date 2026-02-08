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
;   3: HasMetLink - Threshold-based reaction table via SelectReactionMessage
;
; MESSAGES:
;   0x20  - First meeting (introduces quest, dungeon guidance)
;   0x22  - Subsequent visits (0 crystals, vanilla revisit)
;   0x1C5 - 1+ crystals: calm encouragement
;   0x1C6 - 3+ crystals: senses deeper threat
;   0x1C7 - 5+ crystals: urgency rising
;   0x1CA - 7 crystals: endgame, seek Shrines
;   0x1C8 - RESERVED
;   0x1C9 - RESERVED
;   0x1CB - RESERVED
;
; FLAGS WRITTEN:
;   MakuTreeQuest = 1 - Met Maku Tree
;   MapIcon = count+1 - Progressive marker reveal (via UpdateMapIcon)
;   $7EF3D6 |= 0x02 - OOSPROG bit 1 (Hall of Secrets flag)
;
; FLAGS READ:
;   MakuTreeQuest - Check if already met
;   OOSPROG2 bit 2 - Check if Kydrog encounter done (for music)
;
; DEPENDS ON:
;   - Core/progression.asm (SelectReactionMessage, UpdateMapIcon)
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
    ; Threshold-based reaction using crystal count.
    ; SelectReactionMessage walks MakuTreeReactionTable (descending
    ; thresholds) and returns A/Y pre-loaded for the message JSL.
    ; UpdateMapIcon sets MapIcon = crystal_count + 1 (progressive
    ; marker reveal, not "go here next").
    ; Clobbers $00-$02 (table pointer), $04 (temp) — safe in sprite context.

    ; Set up 24-bit pointer to reaction table
    REP #$20
    LDA.w #MakuTreeReactionTable : STA $00
    SEP #$20
    LDA.b #MakuTreeReactionTable>>16 : STA $02

    ; Select message by crystal count threshold
    JSL SelectReactionMessage
    ; A = msg low, Y = msg high
    JSL Sprite_ShowSolicitedMessageIfPlayerFacing
    BCC .no_talk

    .talked
    JSL UpdateMapIcon
    LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6

    .no_talk
    RTS
  }

  ; Descending thresholds, sentinel-terminated.
  ; Format: db threshold : dw message_id
  ; First entry where crystal_count >= threshold wins.
  MakuTreeReactionTable:
    db $07 : dw $01CA  ; 7 crystals → endgame
    db $05 : dw $01C7  ; 5+ → urgency
    db $03 : dw $01C6  ; 3+ → mid-game
    db $01 : dw $01C5  ; 1+ → early
    db $00 : dw $0022  ; 0  → vanilla revisit
}
