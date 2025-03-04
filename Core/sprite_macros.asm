; Write Sprite Properties in the rom MACRO
macro Set_Sprite_Properties(SprPrep, SprMain)
{
  pushpc ; Save writing Position for the sprite
  org $0DB080+!SPRID ; Oam Harmless ($0E40)
  db ((!Harmless<<7)|(!HVelocity<<6)|!NbrTiles)

  org $0DB173+!SPRID ; Sprite HP ($0E50)
  db !Health

  org $0DB266+!SPRID ; Sprite Damage ($0CD2)
  db !Damage

  org $0DB359+!SPRID ; Sprite Data ($0E60 / $0F50)
  db ((!DeathAnimation<<7)|(!ImperviousAll<<6)|(!SmallShadow<<5)|(!Shadow<<4)|(!Palette<<1))

  org $0DB44C+!SPRID ; Sprite Hitbox ($0F60)
  db ((!CollisionLayer<<7)|(!Statis<<6)|(!Persist<<5)|(!Hitbox))

  org $0DB53F+!SPRID ; Sprite Fall ($0B6B)
  db ((!DeflectArrow<<3)|(!Boss<<1)|!CanFall)

  org $0DB632+!SPRID ; Sprite Prize ($0BE0)
  db ((!Interaction<<7)|(!WaterSprite<<6)|(!Blockable<<5)|(!Sound<<4)|!Prize)

  org $0DB725+!SPRID ; Sprite ($0CAA)
  db ($40|(!Statue<<5)|(!DeflectProjectiles<<4)|(!ImpervSwordHammer<<2)|(!ImperviousArrow<<1))

  org $069283+(!SPRID*2) ; Vanilla Sprite Main Pointer
  dw NewMainSprFunction

  org $06865B+(!SPRID*2) ; Vanilla Sprite Prep Pointer
  dw NewSprPrepFunction

  org NewSprRoutinesLong+(!SPRID*3) ; New Long Sprite Pointer
  dl <SprMain>

  org NewSprPrepRoutinesLong+(!SPRID*3) ; New Long Sprite Pointer
  dl <SprPrep>
  pullpc ; Get back the writing position for the sprite
}
endmacro

macro sta(...)
  !a #= 0
  while !a < sizeof(...)
    STA <...>
    !a #= !a+1
  endwhile
endmacro

macro m16()
  REP #$30
endmacro

macro m8()
  SEP #$30
endmacro

macro a16()
  REP #$20
endmacro

macro a8()
  SEP #$20
endmacro

macro index16()
  REP #$10
endmacro

macro index8()
  SEP #$10
endmacro

macro GotoAction(action)
  LDA.b #<action> : STA.w SprAction, X
endmacro

macro SetFrame(frame)
  LDA.b #<frame> : STA.w SprFrame, X
endmacro

macro JumpTable(index, ...)
  LDA.w <index>
  JSL JumpTableLocal

  !a #= 0
  while !a < sizeof(...)
    dw <...[!a]>
    !a #= !a+1
  endwhile
endmacro

macro SpriteJumpTable(...)
  LDA.w SprAction, X
  JSL JumpTableLocal

  !a #= 0
  while !a < sizeof(...)
    dw <...[!a]>
    !a #= !a+1
  endwhile
endmacro

macro SetFlag(flag_addr, bit_pos)
  LDA.b flag_addr : ORA.b #(1 << bit_pos) : STA.b flag_addr
endmacro

macro ClearFlag(flag_addr, bit_pos)
  LDA.b flag_addr : AND.b #~(1 << bit_pos) : STA.b flag_addr
endmacro

macro ToggleFlag(flag_addr, bit_pos)
  LDA.b flag_addr : EOR.b #(1 << bit_pos) : STA.b flag_addr
endmacro

macro CheckFlag(flag_addr, bit_pos, set_label, clear_label)
  LDA.b flag_addr : AND.b #(1 << bit_pos) : BEQ clear_label
    BRA set_label
endmacro

macro CheckFlagLong(flag_addr, bit_pos, set_label, clear_label)
  LDA.l flag_addr : AND.b #(1 << bit_pos) : BEQ clear_label
    BRA set_label
endmacro

; Increase the sprite frame every (frames_wait) frames
; reset to (frame_start) when reaching (frame_end)
; This is using SprTimerB
macro PlayAnimation(frame_start, frame_end, frame_wait)
{
  LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : INC : STA.w SprFrame, X
                        CMP.b #<frame_end>+1 : BCC ++
      LDA.b #<frame_start> : STA.w SprFrame, X
    ++
    LDA.b #<frame_wait> : STA.w SprTimerB, X
  +
}
endmacro

macro PlayAnimBackwards(frame_start, frame_end, frame_wait)
  LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : DEC : STA.w SprFrame, X
                        CMP.b #<frame_end> : BCS ++
      LDA.b #<frame_start> : STA.w SprFrame, X
    ++
    LDA.b #<frame_wait> : STA.w SprTimerB, X
  +
endmacro

macro StartOnFrame(frame)
  LDA.w SprFrame, x : CMP.b #<frame> : BCS +
    LDA.b #<frame> : STA.w SprFrame, x
  +
endmacro

; Show message if the player is facing toward sprite and pressing A
; Return Carry Set if message is displayed
; can use BCC .label <> .label to see if message have been displayed
macro ShowSolicitedMessage(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL Sprite_ShowSolicitedMessageIfPlayerFacing
endmacro

macro ShowMessageOnContact(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL $05E1F0 ; Sprite_ShowMessageOnContact
endmacro

; Show message no matter what (should not be used without code condition)
macro ShowUnconditionalMessage(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL Sprite_ShowMessageUnconditional
endmacro

; Make the sprite move towards the player at a speed of (speed)
macro MoveTowardPlayer(speed)
  LDA.b #<speed>
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_MoveLong
endmacro

; Prevent the player from passing through sprite hitbox
macro PlayerCantPassThrough()
  JSL Sprite_PlayerCantPassThrough
endmacro

; Do damage to player on contact if sprite is on same layer as player
macro DoDamageToPlayerSameLayerOnContact()
  JSL Sprite_CheckDamageToPlayerSameLayer
endmacro

; Set harmless flag, 0 = harmful, 1 = harmless
macro SetHarmless(value)
  LDA.w SprNbrOAM, X
  AND #$7F
  if <value> != 0
      ORA.b #(<value>)<<7
  endif
  STA.w SprNbrOAM, X
endmacro

; Set Room Flag (Chest 6)
; Do not use if you have more than 5 chests or a small key under a pot
; in that room unless you want it to be already opened/taken
macro SetRoomFlag(value)
  if <value> != 0
    LDA $0403 : ORA #$20 : STA $0403
  else
    LDA $0403 : AND #$DF : STA $0403
  endif
endmacro

; Will prevent the player from moving or opening his menu
macro PreventPlayerMovement()
  LDA #$01 : STA $02E4
endmacro

; Will allow the player to move or open his menu
macro AllowPlayerMovement()
  STZ.w $02E4
endmacro

; This is a 16 bit will load A with current rupee count
; to use with instructions CMP and BCC/BCS
macro GetPlayerRupees()
  LDA $7EF360
endmacro

; Set the velocity Y of the sprite at (speed) value
; this require the use of the function JSL Sprite_MoveLong
macro SetSpriteSpeedY(speed)
  LDA.b #<speed> : STA.w SprYSpeed, x
endmacro

; Set the velocity X of the sprite at (speed) value
; this require the use of the function JSL Sprite_MoveLong
macro SetSpriteSpeedX(speed)
  LDA.b #<speed> : STA.w SprXSpeed, x
endmacro

macro PlaySFX1(sfxid)
  LDA.b #<sfxid> : STA $012E
endmacro

macro PlaySFX2(sfxid)
  LDA.b #<sfxid> : STA $012F
endmacro

macro PlayMusic(musicid)
  LDA.b #<musicid> : STA $012C
endmacro

macro SetTimerA(length)
  LDA.b #<length> : STA.w SprTimerA, X
endmacro

macro SetTimerB(length)
  LDA.b #<length> : STA.w SprTimerB, X
endmacro

macro SetTimerC(length)
  LDA.b #<length> : STA.w SprTimerC, X
endmacro

macro SetTimerD(length)
  LDA.b #<length> : STA.w SprTimerD, X
endmacro

macro SetTimerE(length)
  LDA.b #<length> : STA.w SprTimerE, X
endmacro

macro SetTimerF(length)
  LDA.b #<length> : STA.w SprTimerF, X
endmacro

macro ErrorBeep()
  LDA.b #$3C : STA.w $012E ; Error beep
endmacro

macro NextAction()
  INC $0D80, X
endmacro

macro GetTilePos(x, y)
  LDX.w #((<y>*$80)+(<x>*$02))
endmacro

macro SetupDistanceFromSprite()
  LDA.w POSX : STA $02
  LDA.w POSY : STA $03
  LDA.w SprX, X : STA $04
  LDA.w SprY, X : STA $05
endmacro

macro ProbCheck(mask, label)
  JSL GetRandomInt
  AND.b #<mask>
  BNE <label>
endmacro

macro ProbCheck2(mask, label)
  JSL GetRandomInt
  AND.b #<mask>
  BEQ <label>
endmacro

macro DrawSprite()
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY
  LDA.w .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08
  PHX
  LDX .nbr_of_tiles, Y ; amount of tiles -1
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
      ; Put the sprite out of the way
      LDA.b #$F0 : STA ($90), Y : STA $0E
    .on_screen_y
    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y
    INY
    LDA .properties, X : ORA $08 : STA ($90), Y
    PHY
    TYA : LSR #2 : TAY
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY
    PLX : DEX : BPL .nextTile
  PLX
  RTS
}
endmacro

