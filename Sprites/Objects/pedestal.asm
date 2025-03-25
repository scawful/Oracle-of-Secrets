; Magic Pedestal Sprite
;
; Zora Temple (Map 1E)
; Goron Desert (Map 36)
; Fortress Secrets (Map 5E)

pushpc
; Sprite_B3_PedestalPlaque
org $1EE05F
  JSL CheckForBook
pullpc

CheckForBook:
{
  LDA.b $2F : BNE .exit
    JSL Sprite_CheckDamageToPlayer : BCC .exit
      LDA.w $0202 : CMP.b #$0F : BNE .not_holding_book
        LDY.b #$01 : BIT.b $F4 : BVS .not_pressing_y
      .not_holding_book
        LDY.b #$00
        .not_pressing_y
        CPY.b #$01 : BNE .no_book_pose
          STZ.w $0300
          LDA.b #$20
          STA.w $037A
          STZ.w $012E
        .no_book_pose
      JSR PedestalPlaque
  .exit
  LDA.b AreaIndex : CMP.b #$30
  RTL
}

PedestalPlaque:
{
  LDA.b AreaIndex : CMP.b #$1E : BEQ .zora_temple
                    CMP.b #$36 : BEQ .goron_desert
                    CMP.b #$5E : BEQ .fortress_secrets
                      JMP .return
  .zora_temple

    LDA.l $7EF29E : AND.b #$20 : BNE .return
      LDA.b SongFlag : CMP.b #$03 : BNE .return
        LDA.b #$01 : STA $04C6
        STZ.b SongFlag
        JMP .return
  .goron_desert

  .fortress_secrets

  .return
  RTS
}

