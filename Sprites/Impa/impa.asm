; ==============================================================================
; Impa - Sprite #76 Zelda  
; 
; Goals: Make the Impa sprite interact with the "Uncle/Priest/Mantle" object
;        in the forest. This will trigger the intro cutscene with Farore and the
;        antagonist of the story. 
;
; Ideas: Maybe make the "Mantle" the Maku Tree? 
; ==============================================================================

; from `sprites/npcs/sprite_uncle_and_priest.asm` 
; $2DD72-$2DD9E JUMP LOCATION
{
  LDA.b #$00 : STA $0EB0, X : STA $0DE0, X
  
  LDA $0DF0, X : BNE .alpha
  
  ; "Princess Zelda, you are safe! Is this your doing, [Name]?" message
  LDA.b #$17
  LDY.b #$00
  
  JSL Sprite_ShowMessageUnconditional
  
  INC $0D80, X
  
  LDA.b #$01 : STA $7FFE01
  
  JSR Zelda_TransitionFromTagalong
  
  LDA.b #$01 : STA $02E4
  
  LDA.b #$01 : STA $7EF3C7

.alpha

  RTS
}

; ==============================================================================
; from `sprites/npcs/sprite_zelda.asm`

; *$2EC4C-$2EC8D LOCAL
Zelda_TransitionFromTagalong:
{
  ; Transition princess Zelda back into a sprite from the tagalong
  ; state (the sage's sprite is doing this).
  
  LDA.b #$76 : JSL Sprite_SpawnDynamically
  
  PHX
  
  LDX $02CF
  
  LDA $1A64, X : AND.b #$03 : STA $0EB0, Y : STA $0DE0, Y
  
  LDA $20 : STA $0D00, Y
  LDA $21 : STA $0D20, Y
  
  LDA $22 : STA $0D10, Y
  LDA $23 : STA $0D30, Y
  
  LDA.b #$01 : STA $0E80, Y
  
  LDA.b #$00 : STA $7EF3CC
  
  LDA $0BA0, Y : INC A : STA $0BA0, Y
  
  LDA.b #$03 : STA $0F60, Y
  
  PLX
  
  RTS
}

; ==============================================================================

; *$2EC9E-$2ECBE LOCAL
Sprite_Zelda:
{
    JSL CrystalMaiden_Draw
    JSR Sprite2_CheckIfActive
    JSL Sprite_PlayerCantPassThrough
    
    JSL Sprite_MakeBodyTrackHeadDirection : BCC .cant_move
    
    JSR Sprite2_Move

.cant_move

    LDA $0E80, X
    
    JSL UseImplicitRegIndexedLocalJumpTable
    
    dw Zelda_InPrison           ; On the beach 
    dw Zelda_EnteringSanctuary  ; Approaching Maku Tree 
    dw Zelda_AtSanctuary        ; In the Maku Tree forest area 
}

; ==============================================================================

; *$2ED69-$2ED75 JUMP LOCATION
Zelda_EnteringSanctuary:
{
  LDA $0D80, X
  
  JSL UseImplicitRegIndexedLocalJumpTable
  
  dw Zelda_WalkTowardsPriest
  dw Zelda_RespondToPriest
  dw Zelda_BeCarefulOutThere
}

; ==============================================================================

; $2ED76-$2ED7D DATA
pool Zelda_WalkTowardsPriest:
{

.timers
  db $26, $1A, $2C, $01

.directions
  db $01, $03, $01, $02
}

; ==============================================================================

; *$2ED7E-$2EDC3 JUMP LOCATION
Zelda_WalkTowardsPriest:
{
  LDA $0DF0, X : BNE .walking
  
  LDY $0D90, X : CPY.b #$04 : BCC .beta
  
  INC $0D80, X
  
  STZ $0DE0, X
  STZ $0EB0, X
  
  STZ $0D50, X
  STZ $0D40, X
  
  RTS

.beta

  LDA .timers, Y : STA $0DF0, X
  
  LDA .directions, Y : STA $0EB0, X : STA $0DE0, X
  
  INC $0D90, X
  
  TAY
  
  LDA Sprite_Zelda.x_speeds, Y : STA $0D50, X
  
  LDA Sprite_Zelda.y_speeds, Y : STA $0D40, X

.walking

  LDA $1A : LSR #3 : AND.b #$01 : STA $0DC0, X
  
  RTS
}

; ==============================================================================

; *$2EDC4-$2EDEB JUMP LOCATION
Zelda_RespondToPriest:
{
  ; "Yes, it was [Name] who helped me escape from the dungeon! ..."
  LDA.b #$1D
  LDY.b #$00
  
  JSL Sprite_ShowMessageUnconditional
  
  INC $0D80, X
  
  LDA.b #$02 : STA $7FFE01
  
  LDA.b #$01 : STA $7EF3C8
  
  JSL SavePalaceDeaths
  
  LDA.b #$02 : STA $7EF3C5
  
  PHX
  
  JSL Sprite_LoadGfxProperties.justLightWorld
  
  PLX
  
  RTS
}

; ==============================================================================

; *$2EDEC-$2EE05 JUMP LOCATION
Zelda_BeCarefulOutThere:
{
  JSR Sprite2_DirectionToFacePlayer : TYA : EOR.b #$03 : STA $0EB0, X
  
  ; "[Name], be careful out there! I know you can save Hyrule!"
  LDA.b #$1E
  LDY.b #$00
  
  JSL Sprite_ShowSolicitedMessageIfPlayerFacing : BCC .didnt_speak
  
  STA $0DE0, X
  STA $0EB0, X

.didnt_speak

  RTS
}

; ==============================================================================
