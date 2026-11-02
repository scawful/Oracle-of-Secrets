; Song of Secrets / Elegy of Stone, source-owned first playable integration.
;
; Secrets room-authoring contract (tag $35, previously unused in this base):
; - reserve native room flag $0403 bit $10 for the reveal (SRAM room bit $0100);
; - at most FOUR ordinary chests; no fifth chest, rupee floor, bombable floor,
;   moving-wall or drain object that also consumes bit $10;
; - authored ordinary chests are hidden until the song; authored shutters open;
; - no implicit target in untagged rooms, no overworld secrets or hint dialogue.
; The room flag uses the normal save/checksum path, not a new SRAM allocation.
;
; Stone is a temporary subtype of native sprite $1C, marker $0D90=$E6.
; Ordinary statues retain every native path. Only room-local plain floor and
; pressure-plate tiles permit creation. Rooms unload the echo; no save flag.
; No new art slot: the native C0/C2 statue art must be present in the room's
; sprite sheet. Teaching locations and Link-shaped replacement art are separate.

!Secrets_Tag = $35
!Stone_Marker = $E6

OcarinaEffect_Secrets:
{
  STZ.b SongFlag
  LDA.b #$19 : STA.w $012D
  LDA.b $1B : BEQ .no_target
  LDA.b $AE : CMP.b #!Secrets_Tag : BEQ .tagged
  LDA.b $AF : CMP.b #!Secrets_Tag : BNE .no_target
.tagged
  LDA.w $0403 : AND.b #$10 : BNE .no_target
  LDA.b #$04 : STA.b SongFlag
if !ENABLE_OCARINA_SONG_TINT == 1
  LDA.b #$20 : STA.l SongTintTimer
  LDA.b #$3A : STA.l SongTintColor : STA.b $9A
endif
  RTL
.no_target
  LDA.b #$20 : STA.w $012F ; short cursor chime; no false puzzle-success fanfare
  RTL
}

; Native room-tag dispatcher called us with an RTS return on the stack.
RoomTag_SongOfSecrets:
{
  LDA.w $0403 : AND.b #$10 : BNE .revealed
  LDA.b SongFlag : CMP.b #$04 : BNE .done
  STZ.b SongFlag
  ; Reject a violated chest-count contract before consuming the saved bit.
  LDA.w $0496 : CMP.b #$09 : BCC +
    LDA.b #$3C : STA.w $012E
    JML $01CC5A
  +
  LDA.w $0403 : ORA.b #$10 : STA.w $0403
.revealed
  ; The flag is also read on re-entry, so a saved reveal restores shutters.
  REP #$20
  LDA.w $0468 : BEQ .doors_open
  STZ.w $0468 : STZ.w $068E : STZ.w $0690
  SEP #$20
  LDA.b #$05 : STA.b $11
  LDA.b #$1B : STA.w $012F
  REP #$20
.doors_open
  LDA.w $0496 : BEQ .no_chests
  ; The stock reveal writes at least one chest. Never call it with count zero,
  ; a big chest or a missing/opened pointer: native $0496 includes those too.
  CMP.w #$0009 : BCS .no_chests
  TAX
.check_chest
  DEX : DEX
  LDA.w $06E0,X : BEQ .no_chests
  BMI .no_chests
  CPX.b #$00 : BNE .check_chest
  SEP #$30
  JML $01C7D8 ; RoomTag_OperateChestReveal, clears current tag and returns RTS
.no_chests
  SEP #$30
.done
  JML $01CC5A
}

; Six room-load sites normalize the custom tag for the existing hidden-chest
; classification. Saved reveals become ordinary chest rendering immediately.
; Entry/exit M/X=16, preserve X/Y and leave A/Z equivalent to LDA tag / AND FF.
Secrets_ChestTagA:
  LDA.b $AE : BRA Secrets_ChestTag
Secrets_ChestTagB:
  LDA.b $AF
Secrets_ChestTag:
{
  AND.w #$00FF
  CMP.w #!Secrets_Tag : BNE .done
  LDA.w $0402 : AND.w #$1000 : BNE .revealed
  LDA.w #$0027
  RTL
.revealed
  LDA.w #$0000
.done
  RTL
}

OcarinaEffect_Stone:
{
  STZ.b SongFlag
  PHB : PHK : PLB
  PHX : PHY
  ; M/X=8 on entry/exit. Tile probing uses $00..$07; the allocator also
  ; overwrites $08. Preserve caller scratch and keep the candidate in $08/$0A.
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  LDA.b $06 : PHA
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  SEP #$20
  ; Keep the v1 floor/switch contract restricted to dungeon collision maps.
  LDA.b $1B : BNE +
    JMP .error
  +
  LDA.b $10 : CMP.b #$07 : BEQ +
    JMP .error
  +
  LDA.b $11 : BEQ +
    JMP .error
  +
  LDA.b $5D : BEQ +
    JMP .error
  +
  JSR Stone_SelectSpawnPoint
  JSR Stone_CheckSpawnFloor : BCS +
    JMP .error
  +

  ; Reuse the old echo's slot, even when the ordinary sprite table is full.
  LDY.b #$0F
.find_previous
  LDA.w SprState,Y : CMP.b #$09 : BNE .next_previous
  LDA.w SprType,Y : CMP.b #$1C : BNE .next_previous
  LDA.w SprFrame,Y : CMP.b #!Stone_Marker : BEQ .initialize
.next_previous
  DEY : BPL .find_previous
  ; The allocator clobbers $08; preserve both candidate words across it.
  REP #$20
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  SEP #$20
  LDX.b #$00 ; native allocator copies harmless parent scratch from a valid slot
  LDA.b #$1C : JSL Sprite_SpawnDynamically
  REP #$20
  PLA : STA.b $0A
  PLA : STA.b $08
  SEP #$20
  TYA : BPL .initialize ; allocator returns Y=$FF on failure
  JMP .error
.initialize
  TYX
  ; The allocator loads native properties. Replacements keep these constants.
  LDA.b #$09 : STA.w SprState,X
  LDA.b #!Stone_Marker : STA.w SprFrame,X
  LDA.b #$01 : STA.w SprMiscC,X ; let Link leave the creation footprint once
  LDA.b $A0 : STA.w SprMiscA,X
  LDA.b $A1 : STA.w SprMiscB,X
  LDA.b $EE : STA.w SprFloor,X
  LDA.b $2F : STA.w SprMiscE,X ; retain Link's facing for future Link-statue art
  LDA.b $08 : STA.w SprX,X
  LDA.b $09 : STA.w SprXH,X
  LDA.b $0A : STA.w SprY,X
  LDA.b $0B : STA.w SprYH,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  STZ.w SprHeight,X
  STZ.w SprTimerA,X : STZ.w SprTimerB,X
  STZ.w SprTimerC,X : STZ.w SprTimerD,X
  LDA.b #$B6 : STA.w SprDefl,X ; active offscreen, statue + projectile deflection
  LDA.b #$82 : STA.w SprNbrOAM,X ; harmless, three OAM entries
  LDA.b #$43 : STA.w SprHitbox,X ; stationary, 16x16 contract
  LDA.b #$4D : STA.w SprGfxProps,X ; native statue: invulnerable, palette/sheet
  LDA.b #$0D : STA.w SprProps,X ; native palette6 + OBJ page1, no global flips
  LDA.b #$1B : STA.w $012D
if !ENABLE_OCARINA_SONG_TINT == 1
  LDA.b #$10 : STA.l SongTintTimer
  LDA.b #$31 : STA.l SongTintColor : STA.b $9A
endif
  BRA .done
.error
  LDA.b #$3C : STA.w $012E
.done
  REP #$20
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$20
  PLY : PLX : PLB
  RTL
}

; Plain floor retains Link X/Y+8. If the foot center is on a pressure plate,
; select its 16px origin so a wall-clamped Link can leave a centered echo.
; Validate the whole selected footprint afterward; never snap onto a wall.
; Output $08=X/$0A=Y; Sprite_GetTileAttr clobbers $00..$07, exits M/X=8.
Stone_SelectSpawnPoint:
{
  REP #$20
  LDA.b $22 : STA.b $08
  CLC : ADC.w #$0008 : STA.b $02
  LDA.b $20 : CLC : ADC.w #$0008 : STA.b $0A
  CLC : ADC.w #$0008 : STA.b $00
  SEP #$20
  LDA.b $EE : JSL Sprite_GetTileAttr
  LDA.w $0FA5
  CMP.b #$23 : BEQ .plate
  CMP.b #$24 : BEQ .plate
  CMP.b #$25 : BEQ .plate
  CMP.b #$3B : BNE .done
.plate
  REP #$20
  LDA.b $22 : CLC : ADC.w #$0008 : AND.w #$FFF0 : STA.b $08
  LDA.b $20 : CLC : ADC.w #$0010 : AND.w #$FFF0 : STA.b $0A
  SEP #$20
.done
  RTS
}

; Four corners of the 16x16 base. Floor $00 is deliberately the sole ordinary
; floor; pressure plates $23/$24/$25/$3B are the useful intentional exception.
Stone_CheckSpawnFloor:
{
  LDY.b #$03
.loop
  REP #$20
  TYA : AND.w #$00FF : ASL : TAX
  LDA.b $08 : CLC : ADC.l Stone_CornerX,X : STA.b $02
  LDA.b $0A : CLC : ADC.l Stone_CornerY,X : STA.b $00
  SEP #$20
  PHY
  LDA.b $EE : JSL Sprite_GetTileAttr
  PLY
  LDA.w $0FA5 : BEQ .allowed
  CMP.b #$23 : BEQ .allowed
  CMP.b #$24 : BEQ .allowed
  CMP.b #$25 : BEQ .allowed
  CMP.b #$3B : BNE .bad
.allowed
  DEY : BPL .loop
  SEC : RTS
.bad
  CLC : RTS
}
Stone_CornerX: dw 0, 15, 0, 15
Stone_CornerY: dw 0, 0, 15, 15
; Native statue switch coverage has three-pixel tolerance at each edge.
Stone_SwitchX: dw 3, 12, 3, 12
Stone_SwitchY: dw 3, 3, 12, 12

; Native sprite dispatcher supplied an RTS return address. The untouched
; path exactly replays LDA $0DE0,X / BEQ $C0F4 before continuing in bank06.
Stone_StatueDispatch:
{
  LDA.w SprFrame,X : CMP.b #!Stone_Marker : BEQ .echo
  LDA.w $0DE0,X : BEQ .ordinary_idle
  JML $06C0ED
.ordinary_idle
  JML $06C0F4
.echo
  PHB : PHK : PLB
  LDA.b $1B : BEQ .remove
  LDA.b $A0 : CMP.w SprMiscA,X : BNE .remove
  LDA.b $A1 : CMP.w SprMiscB,X : BNE .remove
  ; Room changes unload normally; the stamp additionally rejects retained or
  ; slot-carried actors before they can draw or contribute switch pressure.
  JSR Stone_Draw
  JSL Sprite_CheckActive : BCC .done
  JSL Sprite_Get_16_bit_Coords
  JSR Stone_BlockSprites
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  LDA.w SprMiscC,X : BEQ .barrier
  REP #$20
  LDA.w SprCachedX : SEC : SBC.b $22 : CLC : ADC.w #$0010
  CMP.w #$0021 : BCS .left_footprint
  LDA.w SprCachedY : SEC : SBC.b $20 : CLC : ADC.w #$0010
  CMP.w #$0021 : BCC .grace
.left_footprint
  SEP #$20
  STZ.w SprMiscC,X
.barrier
  JSL Sprite_BehaveAsBarrier
.grace
  SEP #$30
.done
  PLB
  JML $06C1F6 ; native RTS
.remove
  STZ.w SprState,X
  BRA .done
}

Stone_Draw:
{
  REP #$20
  LDA.w #.oam_groups : STA.b $08
  LDA.w #$0003 : STA.b $06
  SEP #$30
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred, uses current DBR
  RTS
.oam_groups
  dw 0,-8 : db $C2,$00,$00,$00
  dw 8,-8 : db $C2,$40,$00,$00
  dw 0, 0 : db $C0,$00,$00,$02
}

; Native Statue_BlockSprites equivalent, with same-layer guard. Enemy
; projectile sprites use this same recoil path; player ancillae see $0CAA's
; native deflection flags. Never move the echo itself or another statue.
Stone_BlockSprites:
{
  LDY.b #$0F
.next
  LDA.w SprType,Y : CMP.b #$1C : BEQ .skip
  CPY.w SprSlot : BEQ .skip
  LDA.w SprState,Y : CMP.b #$09 : BCC .skip
  LDA.w SprFloor,Y : CMP.w SprFloor,X : BNE .skip
  TYA : EOR.b $1A : AND.b #$01 : BNE .skip
  LDA.w SprX,Y : STA.b $04
  LDA.w SprXH,Y : STA.b $05
  LDA.w SprY,Y : STA.b $06
  LDA.w SprYH,Y : STA.b $07
  REP #$20
  LDA.w SprCachedX : SEC : SBC.b $04 : CLC : ADC.w #$000C
  CMP.w #$0018 : BCS .skip
  LDA.w SprCachedY : SEC : SBC.b $06 : CLC : ADC.w #$000C
  CMP.w #$0024 : BCS .skip
  SEP #$20
  LDA.b #$04 : STA.w $0EA0,Y
  PHY
  LDA.b #$20 : JSL Sprite_ProjectSpeedTowardsEntityLong
  PLY
  LDA.b $00 : STA.w SprYRecoil,Y
  LDA.b $01 : STA.w SprXRecoil,Y
.skip
  SEP #$20
  DEY : BPL .next
  RTS
}

; Held-door tags read the echo after ALL sprite AI. An ordinary statue or ice
; block may clear $0642 later in the frame, so publishing that byte from the
; echo's own update would be order-dependent. No sticky shared flag is written.
; Replays native LDA $0642 / AND #00FF, M/X=16; preserves X/Y and scratch0..7.
Stone_ReadHoldSwitch:
{
  PHB : PHK : PLB
  PHX : PHY
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  LDA.b $06 : PHA
  SEP #$30
  JSR Stone_FindPressedSwitch
  BCC .not_pressed
  REP #$30
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  PLY : PLX : PLB
  LDA.w #$0001
  RTL
.not_pressed
  REP #$30
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  PLY : PLX : PLB
  LDA.w $0642 : AND.w #$00FF
  RTL
}

Stone_FindPressedSwitch:
{
  LDX.b #$0F
.find
  LDA.w SprState,X : CMP.b #$09 : BNE .next
  LDA.w SprType,X : CMP.b #$1C : BNE .next
  LDA.w SprFrame,X : CMP.b #!Stone_Marker : BNE .next
  LDA.b $A0 : CMP.w SprMiscA,X : BNE .next
  LDA.b $A1 : CMP.w SprMiscB,X : BNE .next
  LDY.b #$03
.corner
  PHY : PHX
  REP #$20
  TYA : AND.w #$00FF : ASL : TAY
  LDA.w SprX,X : AND.w #$00FF : STA.b $02
  LDA.w SprXH,X : XBA : AND.w #$FF00 : ORA.b $02
  CLC : ADC.w Stone_SwitchX,Y : STA.b $02
  LDA.w SprY,X : AND.w #$00FF : STA.b $00
  LDA.w SprYH,X : XBA : AND.w #$FF00 : ORA.b $00
  CLC : ADC.w Stone_SwitchY,Y : STA.b $00
  SEP #$20
  LDA.w SprFloor,X : JSL Sprite_GetTileAttr
  PLX : PLY
  LDA.w $0FA5
  CMP.b #$23 : BEQ .yes_corner
  CMP.b #$24 : BEQ .yes_corner
  CMP.b #$25 : BEQ .yes_corner
  CMP.b #$3B : BNE .next
.yes_corner
  DEY : BPL .corner
  SEC : RTS
.next
  DEX : BMI .none
  JMP .find
.none
  CLC : RTS
}

pushpc
; The $35 hole handler had no users in all 296 headers of base aea93a28.
; Its four-byte body is replaced; all other hole handlers remain untouched.
assert read4($01CC0C) == $0E8008A9, "Secrets tag35 original hole handler changed"
org $01CC0C ; @hook module=Items name=RoomTag_SongOfSecrets kind=jml target=RoomTag_SongOfSecrets
  JML RoomTag_SongOfSecrets

; All six original sites load a tag as a 16-bit word and mask to one byte.
assert read2($019905) == $AEA5 && read3($019907) == $00FF29
assert read2($019923) == $AFA5 && read3($019925) == $00FF29
assert read2($01996D) == $AEA5 && read3($01996F) == $00FF29
assert read2($01998B) == $AFA5 && read3($01998D) == $00FF29
assert read2($01BCC2) == $AEA5 && read3($01BCC4) == $00FF29
assert read2($01BCE0) == $AFA5 && read3($01BCE2) == $00FF29
org $019905 : JSL Secrets_ChestTagA : NOP
org $019923 : JSL Secrets_ChestTagB : NOP
org $01996D : JSL Secrets_ChestTagA : NOP
org $01998B : JSL Secrets_ChestTagB : NOP
org $01BCC2 : JSL Secrets_ChestTagA : NOP
org $01BCE0 : JSL Secrets_ChestTagB : NOP

assert read3($06C0E8) == $0DE0BD && read2($06C0EB) == $07F0
org $06C0E8 ; @hook module=Items name=Stone_StatueDispatch kind=jml target=Stone_StatueDispatch
  JML Stone_StatueDispatch : NOP
assert read3($01C568) == $0642AD && read3($01C56B) == $00FF29
org $01C568 ; @hook module=Items name=Stone_ReadHoldSwitch kind=jsl target=Stone_ReadHoldSwitch
  JSL Stone_ReadHoldSwitch : NOP #2
pullpc
