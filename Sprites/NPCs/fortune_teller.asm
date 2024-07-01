
FortuneTeller_PrepareNextMessage = $0DC953
FortuneTeller_DisplayMessage = $0DC92F

org $0DC829
FortuneTellerMessage:
.low
#_0DC829: db $EA ; MESSAGE 00EA
#_0DC82A: db $EB ; MESSAGE 00EB
#_0DC82B: db $EC ; MESSAGE 00EC
#_0DC82C: db $ED ; MESSAGE 00ED
#_0DC82D: db $EE ; MESSAGE 00EE
#_0DC82E: db $EF ; MESSAGE 00EF
#_0DC82F: db $F0 ; MESSAGE 00F0
#_0DC830: db $F1 ; MESSAGE 00F1
#_0DC831: db $F6 ; MESSAGE 00F6
#_0DC832: db $F7 ; MESSAGE 00F7
#_0DC833: db $F8 ; MESSAGE 00F8
#_0DC834: db $F9 ; MESSAGE 00F9
#_0DC835: db $FA ; MESSAGE 00FA
#_0DC836: db $FB ; MESSAGE 00FB
#_0DC837: db $FC ; MESSAGE 00FC
#_0DC838: db $FD ; MESSAGE 00FD

.high
#_0DC839: db $00
#_0DC83A: db $00
#_0DC83B: db $00
#_0DC83C: db $00
#_0DC83D: db $00
#_0DC83E: db $00
#_0DC83F: db $00
#_0DC840: db $00
#_0DC841: db $00
#_0DC842: db $00
#_0DC843: db $00
#_0DC844: db $00
#_0DC845: db $00
#_0DC846: db $00
#_0DC847: db $00
#_0DC848: db $00


FortuneTeller_PerformPseudoScience:
#_0DC849: STZ.w $0DC0,X

#_0DC84C: INC.w $0D80,X

#_0DC84F: STZ.b $03

#_0DC851: LDA.l $7EF3D6
#_0DC855: CMP.b #$02
#_0DC857: BCS .map_icon_past_pendants

#_0DC859: STZ.b $00
#_0DC85B: STZ.b $01

#_0DC85D: JMP.w FortuneTeller_DisplayMessage

.map_icon_past_pendants
#_0DC860: LDA.l $7EF344
#_0DC864: BNE .have_shroom_or_powder

#_0DC866: LDA.b #$02
#_0DC868: JSR FortuneTeller_PrepareNextMessage
#_0DC86B: BCC .have_shroom_or_powder

#_0DC86D: JMP.w FortuneTeller_DisplayMessage

.have_shroom_or_powder
#_0DC870: LDA.l $7EF37A
#_0DC874: AND.b #$10
#_0DC876: BNE .beaten_tail_palace

#_0DC878: LDA.b #$01
#_0DC87A: JSR FortuneTeller_PrepareNextMessage
#_0DC87D: BCC .beaten_tail_palace

#_0DC87F: JMP.w FortuneTeller_DisplayMessage

.beaten_tail_palace
#_0DC882: LDA.l $7EF344
#_0DC886: CMP.b #$02
#_0DC888: BCS .have_powder

#_0DC88A: LDA.b #$03
#_0DC88C: JSR FortuneTeller_PrepareNextMessage
#_0DC88F: BCC .have_powder

#_0DC891: JMP.w FortuneTeller_DisplayMessage

.have_powder

LDA.l $7EF355
BNE .have_boots

LDA.b #$06
JSR FortuneTeller_PrepareNextMessage
BCC .have_boots
JMP.w FortuneTeller_DisplayMessage

.have_boots

#_0DC894: LDA.l $7EF356
#_0DC898: BNE .have_flippers

#_0DC89A: LDA.b #$04
#_0DC89C: JSR FortuneTeller_PrepareNextMessage
#_0DC89F: BCC .have_flippers

#_0DC8A1: JMP.w FortuneTeller_DisplayMessage

.have_flippers
#_0DC8A4: LDA.l $7EF345
#_0DC8A8: BNE .have_fire_rod

#_0DC8AA: LDA.b #$05
#_0DC8AC: JSR FortuneTeller_PrepareNextMessage
#_0DC8AF: BCS FortuneTeller_DisplayMessage


.have_fire_rod

#_0DC8C0: LDA.l $7EF37B
#_0DC8C4: BNE .have_magic_upgrade

#_0DC8C6: LDA.b #$07
#_0DC8C8: JSR FortuneTeller_PrepareNextMessage
#_0DC8CB: BCS FortuneTeller_DisplayMessage


.have_magic_upgrade
#_0DC8CD: LDA.l $7EF354
#_0DC8D1: BNE .have_glove

#_0DC8D3: LDA.b #$08
#_0DC8D5: JSR FortuneTeller_PrepareNextMessage
#_0DC8D8: BCS FortuneTeller_DisplayMessage

.have_glove
#_0DC8DA: LDA.l $7EF358
#_0DC8E0: BNE .have_wolf_mask

#_0DC8E2: LDA.b #$09
#_0DC8E4: JSR FortuneTeller_PrepareNextMessage
#_0DC8E7: BCS FortuneTeller_DisplayMessage

.have_wolf_mask
#_0DC8E9: LDA.l $7EF3C9
#_0DC8ED: AND.b #$20
#_0DC8EF: BNE .rescued_smithy

#_0DC8F1: LDA.b #$0A
#_0DC8F3: JSR FortuneTeller_PrepareNextMessage
#_0DC8F6: BCS FortuneTeller_DisplayMessage

.rescued_smithy
#_0DC8F8: LDA.l $7EF352
#_0DC8FC: BNE .have_cape

#_0DC8FE: LDA.b #$0B
#_0DC900: JSR FortuneTeller_PrepareNextMessage
#_0DC903: BCS FortuneTeller_DisplayMessage

.have_cape
#_0DC905: LDA.l $7EF354
#_0DC909: AND.b #$02
#_0DC90B: BNE .have_titans_mitt

#_0DC90D: LDA.b #$0C
#_0DC90F: JSR FortuneTeller_PrepareNextMessage
#_0DC912: BCS FortuneTeller_DisplayMessage

.have_titans_mitt
#_0DC914: LDA.l $7EF359
#_0DC918: CMP.b #$04
#_0DC91A: BCS .have_butter

#_0DC91C: LDA.b #$0D
#_0DC91E: JSR FortuneTeller_PrepareNextMessage
#_0DC921: BCS FortuneTeller_DisplayMessage

.have_butter
#_0DC923: LDA.b #$0E
#_0DC925: JSR FortuneTeller_PrepareNextMessage
#_0DC928: BCS FortuneTeller_DisplayMessage

#_0DC92A: LDA.b #$0F
#_0DC92C: JSR FortuneTeller_PrepareNextMessage

warnpc $0DC92F