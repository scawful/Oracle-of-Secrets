; Private D4 prototype. Existing IDs only: $11 subtype 3, $B8 subtype 2/3.
; No dialogue or new SRAM allocation. Accepted native art; gameplay unqualified.
; Room $46 tag $0A opens the two shutters after the warden's normal death.
; Leaving before healing resets the encounter; the existing Mask flag prevents
; both a repeat reward and a warden respawn after the rescue is completed.

D4Zora_CodeStart:
incsrc "Data/graphics/d4_zora/frames.asm"

D4Zora_IsRescueActor:
{
  LDA.w ROOM : CMP.b #$46 : BNE .no
  LDA.w ROOM+1 : BNE .no
  LDA.w SprSubtype, X : CMP.b #$02 : BEQ .yes
  CMP.b #$03 : BNE .no
  .yes
  SEC : RTL
  .no
  CLC : RTL
}

D4Zora_Prep:
{
  PHB : PHK : PLB
  JSR D4Zora_LoadPalettes
  LDA.b #$83 : STA.w SprNbrOAM, X ; harmless, four Princess OAM cells
  LDA.b #$42 : STA.w SprHitbox, X ; NPC excluded from kill-room check
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w $0DC0, X
  LDA.w SprSubtype, X : CMP.b #$02 : BNE .done
  LDA.b #$81 : STA.w SprNbrOAM, X ; two protector cells (count minus one)
  LDA.l $7EF302 : BEQ .done
  STZ.w SprState, X ; protector spirit departs, Princess remains
  .done
  PLB : RTL
}

D4Zora_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$03 : BNE .protector
  JSR Sprite_ZoraPrincess_Draw
  JSL Sprite_CheckActive : BCC .done
  JSL Sprite_PlayerCantPassThrough
  BRA .done
  .protector
  LDA.b #!D4Zora_Frame_protector_rest : STA.w SprFrame, X
  LDA.w SprAction, X : BEQ .draw
  LDA.b #!D4Zora_Frame_protector_healing : STA.w SprFrame, X
  .draw
  JSR D4Zora_Draw
  JSL Sprite_CheckActive : BCC .done
  JSR D4Zora_ProtectorMain
  .done
  PLB : RTL
}

D4Zora_ProtectorMain:
{
  JSL Sprite_PlayerCantPassThrough
  LDA.l $7EF302 : BEQ .not_owned
  STZ.w SprState, X
  RTS
  .not_owned
  LDA.w SprAction, X : BNE .healing
  ; Do not consume Healing while the warden (including its death poof) lives.
  PHX
  LDX.b #$0F
  .scan
  LDA.w SprState, X : BEQ .next
  LDA.w SprType, X : CMP.b #$11 : BNE .next
  LDA.w SprSubtype, X : CMP.b #$03 : BEQ .blocked
  .next
  DEX : BPL .scan
  PLX
  JSL GetDistance8bit_Long : CMP.b #$30 : BCS .done
  LDA.w SprFloor, X : CMP.b $EE : BNE .done
  LDA.b SongFlag : CMP.b #$01 : BNE .done
  STZ.b SongFlag
  LDA.b #$60 : STA.w SprTimerD, X
  INC.w SprAction, X
  RTS
  .blocked
  PLX
  .done
  RTS
  .healing
  LDA.w SprTimerD, X : BNE .done
  ; Set the existing acquisition flag before calling the modal item receive.
  LDA.b #$01 : STA.l $7EF302
  PHX
  LDY.b #$0F : STZ.w $02E9
  JSL Link_ReceiveItem
  PLX
  STZ.w SprState, X
  RTS
}

D4Warden_Prep:
{
  PHB : PHK : PLB
  JSR D4Zora_LoadPalettes
  LDA.b #$0B : STA.w SprNbrOAM, X ; maximum twelve cells, count minus one
  LDA.b #$18 : STA.w SprHealth, X ; provisional 24 HP
  LDA.b #$03 : STA.w SprBump, X   ; one heart in Green Mail
  LDA.b #$02 : STA.w SprHitbox, X
  LDA.b #$40 : STA.w SprGfxProps, X ; armored outside recovery
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprPrize, X
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$30 : STA.w SprTimerA, X
  LDA.l $7EF302 : BEQ .done
  STZ.w SprState, X
  .done
  PLB : RTL
}

D4Warden_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BEQ .done
  JSR D4Zora_Draw
  JSL Sprite_CheckActive : BCC .done
  JSR D4Warden_Main
  .done
  PLB : RTL
}

D4Warden_Main:
{
  LDA.w SprAction, X : CMP.b #$03 : BEQ .vulnerable
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  BRA .damage
  .vulnerable
  LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X
  .damage
  JSL Sprite_CheckDamageFromPlayer
  LDA.w SprState, X : CMP.b #$09 : BEQ .active
  RTS
  .active
  LDA.w SprAction, X
  JSL JumpTableLocal
  dw .idle, .brace, .charge, .vent
  .idle
  STZ.w SprFrame, X
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprTimerA, X : BNE .done
  LDA.b #$01 : STA.w SprAction, X
  LDA.b #$28 : STA.w SprTimerA, X
  RTS
  .brace
  LDA.b #!D4Zora_Frame_warden_brace : STA.w SprFrame, X
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprTimerA, X : BNE .done
  ; Aim once. There is no pursuit or re-aim during the committed charge.
  LDA.b #$20 : JSL Sprite_ApplySpeedTowardsPlayer
  LDA.b #$02 : STA.w SprAction, X
  LDA.b #$18 : STA.w SprTimerA, X
  RTS
  .charge
  LDA.b #!D4Zora_Frame_warden_charge : STA.w SprFrame, X
  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckTileCollision : BNE .recover
  JSL Sprite_Move
  LDA.w SprTimerA, X : BNE .done
  .recover
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$03 : STA.w SprAction, X
  LDA.b #$38 : STA.w SprTimerA, X
  RTS
  .vent
  LDA.b #!D4Zora_Frame_warden_vent : STA.w SprFrame, X
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprTimerA, X : BNE .done
  STZ.w SprAction, X
  LDA.b #$30 : STA.w SprTimerA, X
  .done
  RTS
}

; Private room $46 lower OBJ halves, colours 1..7 only. Globals $DF..$E2
; (relative $6C..$6F) take LoadSpriteGraphics' Do3To4Low path. Hardware
; rows 3=head, 4=body, 5=bronze, 6=iron. Preserve Link row 7, Princess/Baby
; row 1, every upper half, and both halves' transparent colour entries.
D4Zora_LoadPalettes:
{
  PHX
  REP #$20
  LDX.b #$0C
  .next
  LDA.l D4Zora_Palette_protector_head, X
  STA.l $7EC462, X : STA.l $7EC662, X
  LDA.l D4Zora_Palette_protector_body, X
  STA.l $7EC482, X : STA.l $7EC682, X
  LDA.l D4Zora_Palette_warden_armor, X
  STA.l $7EC4A2, X : STA.l $7EC6A2, X
  LDA.l D4Zora_Palette_warden_iron, X
  STA.l $7EC4C2, X : STA.l $7EC6C2, X
  DEX : DEX : BPL .next
  SEP #$20
  INC.b $15
  PLX
  RTS
}

; SprFrame indexes generated start/count tables. Each piece owns its palette.
; The coordinate/9-bit-X handling follows Oracle's existing Zora draw loop.
D4Zora_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  LDA.w SprFrame, X : TAY
  LDA.w D4Zora_FrameStarts, Y : STA $06
  LDA.w D4Zora_FrameCounts, Y : STA $0D
  PHX
  LDX.b #$00
  LDY.b #$00
  .next
  PHX
  TXA : CLC : ADC $06 : PHA
  ; Use the same generated per-frame index for chars, properties and offsets.
  PLA : PHA
  ASL : TAX
  REP #$20
  LDA $00 : CLC : ADC.l D4Zora_XOffsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC.l D4Zora_YOffsets, X : STA ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .visible
  LDA.b #$F0 : STA ($90), Y : STA $0E
  .visible
  PLX
  INY
  LDA.l D4Zora_Chars, X : STA ($90), Y
  INY
  LDA.l D4Zora_Props, X : STA ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y
  PLY : INY
  PLX : INX : CPX $0D : BCC .next
  PLX
  RTS
}

D4Zora_CodeEnd:
