incsrc "Dungeons/keyblock.asm"
print  "End of keyblock.asm               ", pc

; Pendant from chest position
org $098823
  LDY.b #$68

; Disable hardcoded sanctuary song
org $028BE7
  NOP #2

incsrc "Dungeons/enemy_damage.asm"
print  "End of enemy_damage.asm           ", pc

incsrc "Collision/CollisionTablesExpanded.asm"
incsrc "Collision/GlobalCollisionTables.asm"

pullpc ; Bank 0x33

RoomTag_MinishShutterDoor:
{
  LDA.w $02B2 : CMP.b #$05 : BNE .no_minish
    REP #$30

    LDX.w #$0000 : CPX.w $0468 : BEQ .exit
      STZ.w $0468
      STZ.w $068E : STZ.w $0690

      SEP #$30

      LDA.b #$1B : STA.w $012F
      LDA.b #$05 : STA.b $11

    .exit
    SEP #$30
  .no_minish
  JML $01CC5A ; RoomTag_TriggerHoles return
}

pushpc

org $01CC10
RoomTag_Holes5:
  JML RoomTag_MinishShutterDoor

; RoomTag_GetHeartForPrize
; Swap LW/DW check on spawn falling prize
org $01C71B
  LDA.l $7EF37A ; Crystals in LW

org $01C727
  LDA.l $7EF374 ; Pendants in DW

pullpc

incsrc "Dungeons/house_walls.asm"

; Use of Bank 0x2C begins
incsrc "Dungeons/Objects/object_handler.asm"
print  "End of object_handler.asm         ", pc

incsrc "Dungeons/together_warp_tag.asm"
incsrc "Dungeons/spike_subtype.asm"

incsrc "Dungeons/house_tag.asm"
print  "End of house_tag.asm              ", pc

incsrc "Dungeons/floor_puzzle.asm"
print  "End of floor_puzzle.asm           ", pc

incsrc "Dungeons/attract_scenes.asm"
print  "End of attract_scenes.asm         ", pc