; Apart of Bank 0x0C
; Module14_Attract


; Attract_LoadNewScene
;   #_0CEEEC: dw AttractScene_PolkaDots    ; 0x00
;   #_0CEEEE: dw AttractScene_WorldMap     ; 0x01
;   #_0CEEF0: dw AttractScene_ThroneRoom   ; 0x02
;   #_0CEEF2: dw AttractScene_Prison       ; 0x03
;   #_0CEEF4: dw AttractScene_AgahnimAltar ; 0x04
;   #_0CEEF6: dw AttractScene_EndOfStory   ; 0x05

; ==========================================================

LoadCommonSprites_long = $00E384
Underworld_LoadAndDrawEntranceRoom = $02C533
Underworld_SaveAndLoadLoadAllPalettes = $02C546
AttractScene_AdvanceFromDungeon = $0CEFC0
Underworld_LoadAllPalettes = $02C55E
PuppetSoldier = $1DEB84
Attract_DrawPreloadedSprite = $0CF9B5
Attract_SetUpConclusionHDMA = $0ABC33
Attract_DoTextInDungeonScene = $0CF766
Attract_FadeInStep = $0CEEA6
Attract_DrawZelda = $0CF9E8
Attract_DrawKidnappedMaiden = $0CFA30
HandleScreenFlash = $1DE9B6
FadeMusicAndResetSRAMMirror = $0CC2F0

org $0CF9E6
  db $3D
  db $3D

org $0CFA27
.head_char
#_0CFA27: db $06

.body_char
#_0CFA28: db $08, $0C

.offset_y
#_0CFA2A: db   0,   1

.body_offset_y
#_0CFA2C: db  10,   9

.head_prop
#_0CFA2E: db $39

.body_prop
#_0CFA2F: db $39


org $0CEF4E
AttractScene_ThroneRoom:
{
  #_0CEF4E: STZ.w $420C
  #_0CEF51: STZ.b $9B

  #_0CEF53: LDA.b #$02
  #_0CEF55: STA.b $99

  #_0CEF57: LDA.b #$20
  #_0CEF59: STA.b $9A

  #_0CEF5B: LDA.b #$0A
  #_0CEF5D: STA.w $0AA4

  #_0CEF60: JSL LoadCommonSprites_long

  #_0CEF64: REP #$20

  #_0CEF66: LDA.b $20
  #_0CEF68: PHA

  #_0CEF69: LDA.b $22
  #_0CEF6B: PHA

  #_0CEF6C: SEP #$20

  #_0CEF6E: LDA.b #$74
  #_0CEF70: JSL Underworld_LoadAndDrawEntranceRoom

  ; -------------------------------------------------------

  #_0CEF74: REP #$20

  #_0CEF76: PLA
  #_0CEF77: STA.b $22

  #_0CEF79: PLA
  #_0CEF7A: STA.b $20

  #_0CEF7C: SEP #$20

  #_0CEF7E: STZ.w $0AB6
  #_0CEF81: STZ.w $0AAC

  #_0CEF84: LDA.b #$0E
  #_0CEF86: STA.w $0AAD

  #_0CEF89: LDA.b #$03
  #_0CEF8B: STA.w $0AAE

  #_0CEF8E: LDX.b #$7E
  #_0CEF90: LDA.b #$00
  #_0CEF92: JSL Underworld_SaveAndLoadLoadAllPalettes

  #_0CEF96: LDA.b #$00 ; RGB: #0008C0
  #_0CEF98: STA.l $7EC53A

  #_0CEF9C: LDA.b #$38
  #_0CEF9E: STA.l $7EC53B

  ; -------------------------------------------------------

  #_0CEFA2: STZ.w $1CD8

  #_0CEFA5: LDA.b #$13 ; MESSAGE 0113
  #_0CEFA7: STA.w $1CF0

  #_0CEFAA: LDA.b #$01
  #_0CEFAC: STA.w $1CF1

  #_0CEFAF: LDA.b #$02
  #_0CEFB1: STA.b $25

  #_0CEFB3: LDA.b #$E0
  #_0CEFB5: STA.b $2C

  #_0CEFB7: REP #$20

  #_0CEFB9: LDA.w #$0210
  #_0CEFBC: STA.b $64

  #_0CEFBE: SEP #$20
}
warnpc $0CEFC0

; ==========================================================

org $0CEFE3
AttractScene_Prison:
{
  #_0CEFE3: STZ.b $99
  #_0CEFE5: STZ.b $9A

  #_0CEFE7: REP #$20

  #_0CEFE9: LDA.b $20
  #_0CEFEB: PHA

  #_0CEFEC: LDA.b $22
  #_0CEFEE: PHA

  #_0CEFEF: SEP #$20

  #_0CEFF1: LDA.b #$73
  #_0CEFF3: JSL Underworld_LoadAndDrawEntranceRoom

  #_0CEFF7: REP #$20

  #_0CEFF9: PLA
  #_0CEFFA: STA.b $22

  #_0CEFFC: PLA
  #_0CEFFD: STA.b $20

  #_0CEFFF: SEP #$20

  #_0CF001: LDA.b #$02
  #_0CF003: STA.w $0AB6
  #_0CF006: STZ.w $0AAC

  #_0CF009: LDA.b #$0E
  #_0CF00B: STA.w $0AAD

  #_0CF00E: LDA.b #$03
  #_0CF010: STA.w $0AAE

  #_0CF013: LDX.b #$7F
  #_0CF015: LDA.b #$01

  #_0CF017: JSL Underworld_SaveAndLoadLoadAllPalettes

  #_0CF01B: LDA.b #$00 ; RGB: #000070
  #_0CF01D: STA.l $7EC53A

  #_0CF021: LDA.b #$38
  #_0CF023: STA.l $7EC53B

  ; -------------------------------------------------------

  #_0CF027: STZ.w $1CD8

  #_0CF02A: LDA.b #$14 ; MESSAGE 0114
  #_0CF02C: STA.w $1CF0

  #_0CF02F: LDA.b #$01
  #_0CF031: STA.w $1CF1

  #_0CF034: LDA.b #$94
  #_0CF036: STA.b $2B

  #_0CF038: LDA.b #$68
  #_0CF03A: STA.b $30

  #_0CF03C: STZ.b $31
  #_0CF03E: STZ.b $32
  #_0CF040: STZ.b $33

  #_0CF042: STZ.b $40
  #_0CF044: STZ.b $50
  #_0CF046: STZ.b $5F

  #_0CF048: LDA.b #$FF
  #_0CF04A: STA.b $25

  #_0CF04C: REP #$20

  #_0CF04E: LDA.w #$0240
  #_0CF051: STA.b $64

  #_0CF053: SEP #$20

  #_0CF055: JMP AttractScene_AdvanceFromDungeon
}

; ==========================================================

org $0CF058
AttractScene_AgahnimAltar:
{
  #_0CF058: REP #$20

  #_0CF05A: LDA.b $20
  #_0CF05C: PHA

  #_0CF05D: LDA.b $22
  #_0CF05F: PHA

  #_0CF060: SEP #$20

  #_0CF062: LDA.b #$75
  #_0CF064: JSL Underworld_LoadAndDrawEntranceRoom

  #_0CF068: REP #$20

  #_0CF06A: PLA
  #_0CF06B: STA.b $22

  #_0CF06D: PLA
  #_0CF06E: STA.b $20

  #_0CF070: SEP #$20

  #_0CF072: STZ.w $0AB6
  #_0CF075: STZ.w $0AAC

  #_0CF078: LDA.b #$0E
  #_0CF07A: STA.w $0AAD

  #_0CF07D: LDA.b #$03
  #_0CF07F: STA.w $0AAE
  #_0CF082: STZ.w $0AA9

  #_0CF085: JSL Underworld_LoadAllPalettes

  #_0CF089: LDX.b #$7F
  #_0CF08B: LDA.b #$02
  #_0CF08D: JSL Underworld_SaveAndLoadLoadAllPalettes

  #_0CF091: LDA.b #$00 ; RGB: #0008C0
  #_0CF093: STA.l $7EC33A
  #_0CF097: STA.l $7EC53A

  #_0CF09B: LDA.b #$38
  #_0CF09D: STA.l $7EC33B
  #_0CF0A1: STA.l $7EC53B

  ; -------------------------------------------------------

  #_0CF0A5: STZ.w $1CD8

  #_0CF0A8: LDA.b #$15 ; MESSAGE 0115
  #_0CF0AA: STA.w $1CF0

  #_0CF0AD: LDA.b #$01
  #_0CF0AF: STA.w $1CF1

  #_0CF0B2: LDA.b #$FF
  #_0CF0B4: STA.b $25

  #_0CF0B6: LDA.b #$70
  #_0CF0B8: STA.b $30
  #_0CF0BA: STA.b $62

  #_0CF0BC: LDA.b #$70
  #_0CF0BE: STA.b $63

  #_0CF0C0: LDA.b #$08
  #_0CF0C2: STA.b $32

  #_0CF0C4: STZ.b $50
  #_0CF0C6: STZ.b $51
  #_0CF0C8: STZ.b $52

  #_0CF0CA: STZ.b $5F
  #_0CF0CC: STZ.b $60
  #_0CF0CE: STZ.b $61

  #_0CF0D0: REP #$20

  #_0CF0D2: LDA.w #$00C0
  #_0CF0D5: STA.b $64

  #_0CF0D7: SEP #$20

  #_0CF0D9: JMP AttractScene_AdvanceFromDungeon
}

; ==========================================================

org $0CF0DC
AttractScene_EndOfStory:
{
  #_0CF0DC: REP #$20

  #_0CF0DE: JSL Attract_SetUpConclusionHDMA
}


; ==========================================================

; Attract_EnactStory:
;   #_0CF11C: dw AttractDramatize_PolkaDots    ; 0x00
;   #_0CF11E: dw AttractDramatize_WorldMap     ; 0x01
;   #_0CF120: dw AttractDramatize_ThroneRoom   ; 0x02
;   #_0CF122: dw AttractDramatize_Prison       ; 0x03
;   #_0CF124: dw AttractDramatize_AgahnimAltar ; 0x04

; ==========================================================

org $0CF1AE
pool_AttractDramatize_ThroneRoom:
{
.pointer_size
  #_0CF1AE: dw AttractOAMData_king_size
  #_0CF1B0: dw AttractOAMData_mantle_size

.pointer_offset_x
  #_0CF1B2: dw AttractOAMData_king_offset_x
  #_0CF1B4: dw AttractOAMData_mantle_offset_x

.pointer_offset_y
  #_0CF1B6: dw AttractOAMData_king_offset_y
  #_0CF1B8: dw AttractOAMData_mantle_offset_y

.pointer_char
  #_0CF1BA: dw AttractOAMData_king_char
  #_0CF1BC: dw AttractOAMData_mantle_char

.pointer_prop
  #_0CF1BE: dw AttractOAMData_king_prop
  #_0CF1C0: dw AttractOAMData_mantle_prop

  ; -------------------------------------------------------

.offset_x
  #_0CF1C2: db $50 ; king
  #_0CF1C3: db $68 ; mantle

.offset_y
  #_0CF1C4: db $58 ; king
  #_0CF1C5: db $20 ; mantle

  ; -------------------------------------------------------

.oam_count
  #_0CF1C6: db $03 ; king
  #_0CF1C7: db $05 ; mantle
}


; ==========================================================

org $0CF1C8
AttractDramatize_ThroneRoom:
{
    #_0CF1C8: STZ.b $2A

    #_0CF1CA: LDA.b $52
    #_0CF1CC: BNE .continue

    #_0CF1CE: LDA.b $13
    #_0CF1D0: CMP.b #$0F
    #_0CF1D2: BEQ .max_brightness

    #_0CF1D4: INC.b $13

    #_0CF1D6: BRA .continue

  .max_brightness
    #_0CF1D8: INC.b $52

    ; -------------------------------------------------------

  .continue
    #_0CF1DA: REP #$20

    #_0CF1DC: LDA.w $0122
    #_0CF1DF: BNE .scroll_screen

    #_0CF1E1: SEP #$20

    #_0CF1E3: JSR Attract_DoTextInDungeonScene

    #_0CF1E6: REP #$20

    #_0CF1E8: LDA.b $64

    #_0CF1EA: SEP #$20

    #_0CF1EC: BNE .continue_dramatization

    #_0CF1EE: LDA.b $2C
    #_0CF1F0: CMP.b #$1F
    #_0CF1F2: BCS .dont_fade_out

    #_0CF1F4: AND.b #$01
    #_0CF1F6: BNE .dont_fade_out

    #_0CF1F8: DEC.b $13

  .dont_fade_out
    #_0CF1FA: DEC.b $2C
    #_0CF1FC: BNE .continue_dramatization

    #_0CF1FE: INC.b $23
    #_0CF200: INC.b $22

    #_0CF202: RTL

    ; -------------------------------------------------------

  .scroll_screen
    #_0CF203: DEC.w $0122
    #_0CF206: DEC.w $0124

    ; -------------------------------------------------------

  .continue_dramatization
    #_0CF209: SEP #$20

    #_0CF20B: LDX.b #$02

  .next_entity
    #_0CF20D: PHX

    #_0CF20E: REP #$20

    #_0CF210: LDA.l pool_AttractDramatize_ThroneRoom_pointer_size,X
    #_0CF214: STA.b $2D

    #_0CF216: LDA.l pool_AttractDramatize_ThroneRoom_pointer_offset_x,X
    #_0CF21A: STA.b $02

    #_0CF21C: LDA.l pool_AttractDramatize_ThroneRoom_pointer_offset_y,X
    #_0CF220: STA.b $04

    #_0CF222: LDA.l pool_AttractDramatize_ThroneRoom_pointer_char,X
    #_0CF226: STA.b $06

    #_0CF228: LDA.l pool_AttractDramatize_ThroneRoom_pointer_prop,X
    #_0CF22C: STA.b $08

    #_0CF22E: TXA
    #_0CF22F: AND.w #$00FF
    #_0CF232: LSR A
    #_0CF233: TAX

    #_0CF234: LDA.l pool_AttractDramatize_ThroneRoom_offset_y,X
    #_0CF238: AND.w #$00FF
    #_0CF23B: SEC
    #_0CF23C: SBC.w $0122
    #_0CF23F: STA.b $00

    #_0CF241: CMP.w #$FFE0

    #_0CF244: SEP #$20
    #_0CF246: BMI .off_screen

    #_0CF248: LDA.l pool_AttractDramatize_ThroneRoom_offset_x,X
    #_0CF24C: STA.b $28

    #_0CF24E: LDA.b $00
    #_0CF250: STA.b $29

    #_0CF252: LDA.l pool_AttractDramatize_ThroneRoom_oam_count,X
    #_0CF256: TAY

    #_0CF257: JSR Attract_DrawPreloadedSprite

  .off_screen
    #_0CF25A: PLX

    #_0CF25B: DEX
    #_0CF25C: DEX
    #_0CF25D: BPL .next_entity

    #_0CF25F: RTL
}

; ==========================================================

org $0CF260
pool_AttractDramatize_Prison:
{
  .soldier_offset_x
    #_0CF260: dw  32, -12

  .soldier_offset_y
    #_0CF264: db  24,  24

  .soldier_direction
    #_0CF266: db $01, $01

  .soldier_palette
    #_0CF268: db $09, $07

  .maiden_jab_offset_x
    #_0CF26A: db  0,  1,  2,  3
    #_0CF26E: db  4,  5,  5,  5
    #_0CF272: db  4,  4,  3,  3
    #_0CF276: db  2,  2,  1,  1
}

org $0CF27A
AttractDramatize_Prison:
{
    #_0CF27A: STZ.b $2A

    #_0CF27C: LDA.b $5F
    #_0CF27E: BNE .skip_fade

    #_0CF280: JSR Attract_FadeInStep

  .skip_fade
    #_0CF283: LDA.b #$38
    #_0CF285: STA.b $28

    #_0CF287: JSR Attract_DrawZelda

    #_0CF28A: LDA.b $25
    #_0CF28C: CMP.b #$C0
    #_0CF28E: BCS .delay_agahnim

    #_0CF290: JMP.w AttractDramatize_Agahnim

  .delay_agahnim
    #_0CF293: LDA.b #$70
    #_0CF295: STA.b $29

    #_0CF297: DEC.b $50
    #_0CF299: BPL .dont_reset_jab

    #_0CF29B: LDA.b #$0F
    #_0CF29D: STA.b $50

  .dont_reset_jab
    #_0CF29F: LDX.b $50

    #_0CF2A1: LDA.b $31
    #_0CF2A3: STA.b $40

    #_0CF2A5: LDA.b $30
    #_0CF2A7: CLC
    #_0CF2A8: ADC.l pool_AttractDramatize_Prison_maiden_jab_offset_x,X
    #_0CF2AC: STA.b $28

    #_0CF2AE: BCC .dont_disable_maiden

    #_0CF2B0: INC.b $40

  .dont_disable_maiden
    #_0CF2B2: JSR Attract_DrawKidnappedMaiden

    ; -------------------------------------------------------

    #_0CF2B5: LDX.b #$01

  .next_soldier
    #_0CF2B7: STZ.b $03

    #_0CF2B9: LDA.b $33
    #_0CF2BB: STA.b $06

    #_0CF2BD: LDA.b $29
    #_0CF2BF: CLC
    #_0CF2C0: ADC.l pool_AttractDramatize_Prison_soldier_offset_y,X
    #_0CF2C4: STA.b $02

    #_0CF2C6: LDA.l pool_AttractDramatize_Prison_soldier_direction,X
    #_0CF2CA: STA.b $04

    #_0CF2CC: LDA.l pool_AttractDramatize_Prison_soldier_palette,X
    #_0CF2D0: STA.b $05

    #_0CF2D2: PHX

    #_0CF2D3: REP #$20

    #_0CF2D5: TXA
    #_0CF2D6: ASL A
    #_0CF2D7: TAX

    #_0CF2D8: LDA.b $30
    #_0CF2DA: CLC
    #_0CF2DB: ADC.w #$0100

    #_0CF2DE: CLC
    #_0CF2DF: ADC.l pool_AttractDramatize_Prison_soldier_offset_x,X
    #_0CF2E3: STA.b $00

    #_0CF2E5: TAY
    #_0CF2E6: STY.b $34

    #_0CF2E8: SEP #$20

    #_0CF2EA: JSL SpritePrep_ResetProperties
    #_0CF2EE: JSL PuppetSoldier

    #_0CF2F2: PLX
    #_0CF2F3: DEX
    #_0CF2F4: BPL .next_soldier

    ; -------------------------------------------------------

    #_0CF2F6: INC.b $32

    #_0CF2F8: LDA.b $32
    #_0CF2FA: AND.b #$07
    #_0CF2FC: BNE AttractDramatize_Agahnim

    #_0CF2FE: LDY.b #$FF

    #_0CF300: LDA.b $33
    #_0CF302: CMP.b #$02
    #_0CF304: BNE .delay_sfx

    #_0CF306: STY.b $33

    #_0CF308: LDA.b $31
    #_0CF30A: BNE .delay_sfx

    #_0CF30C: LDA.b $32
    #_0CF30E: AND.b #$08
    #_0CF310: BEQ .delay_sfx

    #_0CF312: LDA.b #$04 ; SFX3.04
    #_0CF314: STA.w $012F

  .delay_sfx
    #_0CF317: INC.b $33
}

; ==========================================================

org $0CF319
AttractDramatize_Agahnim:
{
  #_0CF319: LDA.b $60
  #_0CF31B: ASL A
  #_0CF31C: TAX

  #_0CF31D: JMP.w (.vectors,X)

  .vectors
  #_0CF320: dw Dramaghanim_WaitForCue
  #_0CF322: dw Dramaghanim_MoveAndSpin

  ; ==========================================================

  Dramaghanim_AdvanceStory:
    #_0CF324: INC.b $23

    #_0CF326: DEC.b $22
    #_0CF328: DEC.b $22

    #_0CF32A: RTL

  ; ==========================================================

  Dramaghanim_WaitForCue:
    #_0CF32B: LDA.b $34
    #_0CF32D: BNE .delay

    #_0CF32F: INC.b $60

  .delay
    #_0CF331: REP #$20

    #_0CF333: LDA.b $1A
    #_0CF335: AND.w #$0001
    #_0CF338: BEQ .delay_tick

    #_0CF33A: DEC.b $30

  .delay_tick
    #_0CF33C: LDA.w #AttractAgahnimOAM_size
    #_0CF33F: STA.b $2D

    #_0CF341: LDA.w #AttractAgahnimOAM_offset_x
    #_0CF344: STA.b $02

    #_0CF346: LDA.w #AttractAgahnimOAM_offset_y
    #_0CF349: STA.b $04

    #_0CF34B: LDA.w #AttractAgahnimOAM_char_step0
    #_0CF34E: STA.b $06

    #_0CF350: LDA.w #AttractAgahnimOAM_prop_step0
    #_0CF353: STA.b $08

    #_0CF355: SEP #$20

    #_0CF357: LDA.b #$58
    #_0CF359: STA.b $28

    #_0CF35B: LDA.b $2B
    #_0CF35D: STA.b $29

    #_0CF35F: LDY.b #$05
    #_0CF361: JSR Attract_DrawPreloadedSprite

    #_0CF364: RTL
}

; ==========================================================

org $0CF365
pool_Dramaghanim_MoveAndSpin:
{
  .pointers_char
    #_0CF365: dw AttractAgahnimOAM_char_step0
    #_0CF367: dw AttractAgahnimOAM_char_step1
    #_0CF369: dw AttractAgahnimOAM_char_step2
    #_0CF36B: dw AttractAgahnimOAM_char_step3
    #_0CF36D: dw AttractAgahnimOAM_char_step4

  .pointers_prop
    #_0CF36F: dw AttractAgahnimOAM_prop_step0
    #_0CF371: dw AttractAgahnimOAM_prop_step1
    #_0CF373: dw AttractAgahnimOAM_prop_step2
    #_0CF375: dw AttractAgahnimOAM_prop_step0
    #_0CF377: dw AttractAgahnimOAM_prop_step0
}


org $0CF379
Dramaghanim_MoveAndSpin:
{
  #_0CF379: LDA.b $25
  #_0CF37B: CMP.b #$80
  #_0CF37D: BCS .continue

  #_0CF37F: JSR Attract_DoTextInDungeonScene

  #_0CF382: REP #$20

  #_0CF384: LDA.b $64

  #_0CF386: SEP #$20

  #_0CF388: BEQ .continue

  #_0CF38A: LDX.b #$08
  #_0CF38C: BRA .animate_agahnim

  .continue
  #_0CF38E: LDX.b #$00

  #_0CF390: LDA.b $2B
  #_0CF392: CMP.b #$6E
  #_0CF394: BEQ .timer_maxed

  #_0CF396: DEC.b $2B
  #_0CF398: BRA .animate_agahnim

  .timer_maxed
  #_0CF39A: LDA.b $25
  #_0CF39C: CMP.b #$1F
  #_0CF39E: BCS .delay_fade

  #_0CF3A0: AND.b #$01
  #_0CF3A2: BNE .delay_fade

  #_0CF3A4: DEC.b $13

  .delay_fade
  #_0CF3A6: DEC.b $25
  #_0CF3A8: BNE .dont_advance_story

  #_0CF3AA: JMP.w Dramaghanim_AdvanceStory

  ; -------------------------------------------------------

  .dont_advance_story
  #_0CF3AD: LDA.b $25
  #_0CF3AF: CMP.b #$C0
  #_0CF3B1: BCS .animate_agahnim

  #_0CF3B3: INX
  #_0CF3B4: INX

  #_0CF3B5: CMP.b #$B8
  #_0CF3B7: BCS .animate_agahnim

  #_0CF3B9: INX
  #_0CF3BA: INX

  #_0CF3BB: CMP.b #$B0
  #_0CF3BD: BCS .animate_agahnim

  #_0CF3BF: INX
  #_0CF3C0: INX

  #_0CF3C1: CMP.b #$A0
  #_0CF3C3: BCS .animate_agahnim

  #_0CF3C5: INX
  #_0CF3C6: INX

  ; -------------------------------------------------------

  .animate_agahnim
  #_0CF3C7: LDA.b #$A8
  #_0CF3C9: STA.b $28

  #_0CF3CB: REP #$20

  #_0CF3CD: LDA.b $1A
  #_0CF3CF: AND.w #$0001
  #_0CF3D2: BEQ .delay_tick

  #_0CF3D4: DEC.b $30

  .delay_tick
  #_0CF3D6: LDA.w #AttractAgahnimOAM_size
  #_0CF3D9: STA.b $2D

  #_0CF3DB: LDA.w #AttractAgahnimOAM_offset_x
  #_0CF3DE: STA.b $02

  #_0CF3E0: LDA.w #AttractAgahnimOAM_offset_y
  #_0CF3E3: STA.b $04

  #_0CF3E5: LDA.l pool_Dramaghanim_MoveAndSpin_pointers_char,X
  #_0CF3E9: STA.b $06

  #_0CF3EB: LDA.l pool_Dramaghanim_MoveAndSpin_pointers_prop,X
  #_0CF3EF: STA.b $08

  #_0CF3F1: SEP #$20

  #_0CF3F3: LDA.b #$58
  #_0CF3F5: STA.b $28

  #_0CF3F7: LDA.b $2B
  #_0CF3F9: STA.b $29

  #_0CF3FB: LDY.b #$05
  #_0CF3FD: JSR Attract_DrawPreloadedSprite

  #_0CF400: RTL
}

; ==========================================================

org $0CF401
pool_AttractDramatize_AgahnimAltar:
{
  .soldier_position_x
    #_0CF401: db $30, $C0, $30, $C0, $50, $A0

  .soldier_position_y
    #_0CF407: db $70, $70, $98, $98, $C0, $C0

  .soldier_direction
    #_0CF40D: db $00, $01, $00, $01, $03, $03

  .soldier_palette
    #_0CF413: db $09, $09, $09, $09, $07, $09

  ; -------------------------------------------------------

  .vectors
  #_0CF419: dw Dramagahnim_RaiseTheRoof
  #_0CF41B: dw Dramagahnim_ReadySpell
  #_0CF41D: dw Dramagahnim_CastSpell
  #_0CF41F: dw Dramagahnim_RealizeWhatJustHappened
  #_0CF421: dw Dramagahnim_IdleGuiltily
}

  ; -------------------------------------------------------

AttractDramatize_AgahnimAltar:
{
    #_0CF423: LDA.b $5D
    #_0CF425: BEQ .delay

    #_0CF427: JMP.w Dramaghanim_AdvanceStory

  .delay
    #_0CF42A: STZ.b $2A

    #_0CF42C: JSL HandleScreenFlash

    #_0CF430: LDA.b $5F
    #_0CF432: BNE .delay_fade

    #_0CF434: JSR Attract_FadeInStep

  .delay_fade
    #_0CF437: LDA.b $50
    #_0CF439: CMP.b #$FF
    #_0CF43B: BEQ .delay_tick

    #_0CF43D: INC.b $50

  .delay_tick
    #_0CF43F: LDA.w $0FF9
    #_0CF442: BEQ .delay_sfx

    #_0CF444: AND.b #$04
    #_0CF446: BEQ .delay_sfx

    #_0CF448: LDX.b #$2B ; SFX3.2B
    #_0CF44A: STX.w $012F

    ; -------------------------------------------------------

  .delay_sfx
    #_0CF44D: LDA.b $60
    #_0CF44F: ASL A
    #_0CF450: TAX

    #_0CF451: JSR (pool_AttractDramatize_AgahnimAltar_vectors,X)

    ; -------------------------------------------------------

    #_0CF454: LDX.b #$05

  .next_soldier
    #_0CF456: STZ.b $01
    #_0CF458: STZ.b $03
    #_0CF45A: STZ.b $06

    #_0CF45C: LDA.l pool_AttractDramatize_AgahnimAltar_soldier_position_x,X
    #_0CF460: STA.b $00

    #_0CF462: LDA.l pool_AttractDramatize_AgahnimAltar_soldier_position_y,X
    #_0CF466: STA.b $02

    #_0CF468: LDA.l pool_AttractDramatize_AgahnimAltar_soldier_direction,X
    #_0CF46C: STA.b $04

    #_0CF46E: LDA.l pool_AttractDramatize_AgahnimAltar_soldier_palette,X
    #_0CF472: STA.b $05

    #_0CF474: PHX

    #_0CF475: JSL SpritePrep_ResetProperties
    #_0CF479: JSL PuppetSoldier

    #_0CF47D: PLX
    #_0CF47E: DEX
    #_0CF47F: BPL .next_soldier

    ; -------------------------------------------------------

    #_0CF481: LDX.b $50
    #_0CF483: CPX.b #$A0
    #_0CF485: BCC .continue

    #_0CF487: LDA.b $30
    #_0CF489: CMP.b #$60
    #_0CF48B: BEQ .tick_timer

    #_0CF48D: DEC.b $32
    #_0CF48F: BNE .continue

    #_0CF491: DEC.b $30

    #_0CF493: LDA.b #$08
    #_0CF495: STA.b $32

    #_0CF497: BRA .continue

  .tick_timer
    #_0CF499: INC.b $61

    ; -------------------------------------------------------

  .continue
    #_0CF49B: LDA.b $52
    #_0CF49D: BNE .dont_draw_maiden

    #_0CF49F: REP #$20

    #_0CF4A1: LDA.w #AttractAltarMaidenOAM_size
    #_0CF4A4: STA.b $2D

    #_0CF4A6: LDA.w #AttractAltarMaidenOAM_offset_x
    #_0CF4A9: STA.b $02

    #_0CF4AB: LDA.w #AttractAltarMaidenOAM_offset_y
    #_0CF4AE: STA.b $04

    #_0CF4B0: LDX.b #$00

    #_0CF4B2: LDA.b $30
    #_0CF4B4: AND.w #$00FF
    #_0CF4B7: CMP.w #$0070
    #_0CF4BA: BEQ .not_airborne

    #_0CF4BC: INX
    #_0CF4BD: INX

  .not_airborne
    #_0CF4BE: LDA.l .maiden_char_pointer,X
    #_0CF4C2: STA.b $06

    #_0CF4C4: LDA.w #AttractAltarMaidenOAM_prop
    #_0CF4C7: STA.b $08

    #_0CF4C9: SEP #$20

    #_0CF4CB: LDA.b #$74
    #_0CF4CD: STA.b $28

    #_0CF4CF: LDA.b $30
    #_0CF4D1: STA.b $29

    #_0CF4D3: LDY.b #$01
    #_0CF4D5: JSR Attract_DrawPreloadedSprite

    ; -------------------------------------------------------

    #_0CF4D8: LDX.b #$0E

    #_0CF4DA: LDA.b $30
    #_0CF4DC: CMP.b #$68
    #_0CF4DE: BCS .adjust_shadow_index

    #_0CF4E0: SEC
    #_0CF4E1: SBC.b #$68

    #_0CF4E3: ASL A
    #_0CF4E4: AND.b #$0E
    #_0CF4E6: TAX

  .adjust_shadow_index
    #_0CF4E7: REP #$20

    #_0CF4E9: LDA.w #AttractAltarMaidenShadowOAM_size
    #_0CF4EC: STA.b $2D

    #_0CF4EE: LDA.l .shadow_offset_x_pointer,X
    #_0CF4F2: STA.b $02

    #_0CF4F4: LDA.w #AttractAltarMaidenShadowOAM_offset_y
    #_0CF4F7: STA.b $04

    #_0CF4F9: LDA.w #AttractAltarMaidenShadowOAM_char
    #_0CF4FC: STA.b $06

    #_0CF4FE: LDA.w #AttractAltarMaidenShadowOAM_prop
    #_0CF501: STA.b $08

    #_0CF503: SEP #$20

    #_0CF505: TXA
    #_0CF506: LSR A
    #_0CF507: TAX

    #_0CF508: LDA.b #$74
    #_0CF50A: CLC
    #_0CF50B: ADC.l .shadow_base_offset_x,X
    #_0CF50F: STA.b $28

    #_0CF511: LDA.b #$76
    #_0CF513: STA.b $29

    #_0CF515: LDY.b #$01
    #_0CF517: JSR Attract_DrawPreloadedSprite

    ; -------------------------------------------------------

  .dont_draw_maiden
    #_0CF51A: LDA.b $50

    #_0CF51C: LSR A
    #_0CF51D: LSR A
    #_0CF51E: LSR A
    #_0CF51F: LSR A

    #_0CF520: AND.b #$0E
    #_0CF522: TAX

    #_0CF523: REP #$20

    #_0CF525: LDA.w #AttractAgahnimOAM_size
    #_0CF528: STA.b $2D

    #_0CF52A: LDA.w #AttractAgahnimOAM_offset_x
    #_0CF52D: STA.b $02

    #_0CF52F: LDA.w #AttractAgahnimOAM_offset_y
    #_0CF532: STA.b $04

    #_0CF534: LDA.l .agahnim_char_pointer,X
    #_0CF538: STA.b $06

    #_0CF53A: LDA.w #AttractAgahnimOAM_prop_step0
    #_0CF53D: STA.b $08

    #_0CF53F: SEP #$20

    #_0CF541: LDA.b #$70
    #_0CF543: STA.b $28

    #_0CF545: LDA.b #$46
    #_0CF547: STA.b $29

    #_0CF549: LDY.b #$05
    #_0CF54B: JSR Attract_DrawPreloadedSprite

    #_0CF54E: RTL


    ; -------------------------------------------------------

  .shadow_offset_x_pointer
    #_0CF54F: dw AttractAltarMaidenShadowOAM_offset_x_step0
    #_0CF551: dw AttractAltarMaidenShadowOAM_offset_x_step0
    #_0CF553: dw AttractAltarMaidenShadowOAM_offset_x_step1
    #_0CF555: dw AttractAltarMaidenShadowOAM_offset_x_step1
    #_0CF557: dw AttractAltarMaidenShadowOAM_offset_x_step2
    #_0CF559: dw AttractAltarMaidenShadowOAM_offset_x_step2
    #_0CF55B: dw AttractAltarMaidenShadowOAM_offset_x_step3
    #_0CF55D: dw AttractAltarMaidenShadowOAM_offset_x_step4

    ; -------------------------------------------------------

  .shadow_base_offset_x
    #_0CF55F: db  4,  4,  3,  3
    #_0CF563: db  2,  2,  1,  0

    ; -------------------------------------------------------

  .maiden_char_pointer
    #_0CF567: dw AttractAltarMaidenOAM_char_step0
    #_0CF569: dw AttractAltarMaidenOAM_char_step1

    ; -------------------------------------------------------

  .agahnim_char_pointer
    #_0CF56B: dw AttractAgahnimOAM_char_step3
    #_0CF56D: dw AttractAgahnimOAM_char_step5
    #_0CF56F: dw AttractAgahnimOAM_char_step3
    #_0CF571: dw AttractAgahnimOAM_char_step6
    #_0CF573: dw AttractAgahnimOAM_char_step3
    #_0CF575: dw AttractAgahnimOAM_char_step5
    #_0CF577: dw AttractAgahnimOAM_char_step3
    #_0CF579: dw AttractAgahnimOAM_char_step4
}

; ==========================================================

org $0CF57B
Dramagahnim_RaiseTheRoof:
{
  #_0CF57B: LDA.b $61
  #_0CF57D: BEQ .exit

  #_0CF57F: INC.b $60

  .exit
  #_0CF581: RTS
}

; ==========================================================

org $0CF582
DramagahnimSpellCharPointer:
  #_0CF582: dw DramagahnimSpellOAM_char_step0
  #_0CF584: dw DramagahnimSpellOAM_char_step1

  ; -------------------------------------------------------

DramagahnimSpellPropPointer:
  #_0CF586: dw DramagahnimSpellOAM_prop_step0
  #_0CF588: dw DramagahnimSpellOAM_prop_step1

  ; -------------------------------------------------------

pool_Dramagahnim_ReadySpell:
{
.oam_count
  #_0CF58A: db  1
  #_0CF58B: db  1
  #_0CF58C: db  1
  #_0CF58D: db  5
  #_0CF58E: db  5
  #_0CF58F: db  9
  #_0CF590: db  9
  #_0CF591: db 13
}

; -------------------------------------------------------

org $0CF592
Dramagahnim_ReadySpell:
  #_0CF592: LDA.b $1A
  #_0CF594: LSR A
  #_0CF595: AND.b #$02
  #_0CF597: TAX

  #_0CF598: REP #$20

  #_0CF59A: LDA.w #DramagahnimSpellOAM_size
  #_0CF59D: STA.b $2D

  #_0CF59F: LDA.w #DramagahnimSpellOAM_offset_x
  #_0CF5A2: STA.b $02

  #_0CF5A4: LDA.w #DramagahnimSpellOAM_offset_y
  #_0CF5A7: STA.b $04

  #_0CF5A9: LDA.l DramagahnimSpellCharPointer,X
  #_0CF5AD: STA.b $06

  #_0CF5AF: LDA.l DramagahnimSpellPropPointer,X
  #_0CF5B3: STA.b $08

  ; -------------------------------------------------------

  #_0CF5B5: SEP #$20

  #_0CF5B7: LDA.b #$6E
  #_0CF5B9: STA.b $28

  #_0CF5BB: LDA.b #$48
  #_0CF5BD: STA.b $29

  #_0CF5BF: LDA.b $51
  #_0CF5C1: LSR A
  #_0CF5C2: AND.b #$07
  #_0CF5C4: TAX

  #_0CF5C5: LDA.l pool_Dramagahnim_ReadySpell_oam_count,X
  #_0CF5C9: TAY

  #_0CF5CA: JSR Attract_DrawPreloadedSprite

  ; -------------------------------------------------------

  #_0CF5CD: LDA.b $51
  #_0CF5CF: BNE .delay_sfx

  #_0CF5D1: LDY.b $63
  #_0CF5D3: CPY.b #$70
  #_0CF5D5: BNE .delay_sfx

  #_0CF5D7: LDX.b #$27 ; SFX3.27
  #_0CF5D9: STX.w $012F

  ; -------------------------------------------------------

.delay_sfx
  #_0CF5DC: CMP.b #$0F
  #_0CF5DE: BEQ .advance

  #_0CF5E0: CMP.b #$06
  #_0CF5E2: BNE .delay_other_sfx

  #_0CF5E4: LDX.b #$90
  #_0CF5E6: STX.w $0FF9

  #_0CF5E9: LDX.b #$2B ; SFX3.2B
  #_0CF5EB: STX.w $012F

  ; -------------------------------------------------------

.delay_other_sfx
  #_0CF5EE: LDA.b $63
  #_0CF5F0: BEQ .delay_tick

  #_0CF5F2: DEC.b $63

  #_0CF5F4: RTS

  ; -------------------------------------------------------

.delay_tick
  #_0CF5F5: INC.b $51

  #_0CF5F7: RTS

  ; -------------------------------------------------------

.advance
  #_0CF5F8: INC.b $60

  #_0CF5FA: RTS

; ==========================================================

org $0CF5FB
pool_Dramagahnim_CastSpell:
{
  .oam_count
    #_0CF5FB: db  3
    #_0CF5FC: db  3
    #_0CF5FD: db  7
    #_0CF5FE: db  7
    #_0CF5FF: db 11
    #_0CF600: db 11
    #_0CF601: db 13
    #_0CF602: db 13

    ; -------------------------------------------------------

  .index_offset
    #_0CF603: dw 10
    #_0CF605: dw 10
    #_0CF607: dw  6
    #_0CF609: dw  6
    #_0CF60B: dw  2
    #_0CF60D: dw  2
    #_0CF60F: dw  0
    #_0CF611: dw  0
}


  ; -------------------------------------------------------

Dramagahnim_CastSpell:
{
    #_0CF613: PHB
    #_0CF614: PHK
    #_0CF615: PLB

    #_0CF616: LDA.b $1A
    #_0CF618: LSR A
    #_0CF619: AND.b #$02
    #_0CF61B: TAX

    #_0CF61C: LDA.b $51
    #_0CF61E: LSR A
    #_0CF61F: AND.b #$07
    #_0CF621: STA.b $00

    #_0CF623: ASL A
    #_0CF624: TAY

    ; -------------------------------------------------------

    #_0CF625: REP #$20

    #_0CF627: LDA.w #DramagahnimSpellOAM_size
    #_0CF62A: CLC
    #_0CF62B: ADC.w pool_Dramagahnim_CastSpell_index_offset,Y
    #_0CF62E: STA.b $2D

    #_0CF630: LDA.w #DramagahnimSpellOAM_offset_x
    #_0CF633: CLC
    #_0CF634: ADC.w pool_Dramagahnim_CastSpell_index_offset,Y
    #_0CF637: STA.b $02

    #_0CF639: LDA.w #DramagahnimSpellOAM_offset_y
    #_0CF63C: CLC
    #_0CF63D: ADC.w pool_Dramagahnim_CastSpell_index_offset,Y
    #_0CF640: STA.b $04

    #_0CF642: LDA.w DramagahnimSpellCharPointer,X
    #_0CF645: CLC
    #_0CF646: ADC.w pool_Dramagahnim_CastSpell_index_offset,Y
    #_0CF649: STA.b $06

    #_0CF64B: LDA.w DramagahnimSpellPropPointer,X
    #_0CF64E: CLC
    #_0CF64F: ADC.w pool_Dramagahnim_CastSpell_index_offset,Y
    #_0CF652: STA.b $08

    ; -------------------------------------------------------

    #_0CF654: SEP #$20

    #_0CF656: LDA.b #$6E
    #_0CF658: STA.b $28

    #_0CF65A: LDA.b #$48
    #_0CF65C: STA.b $29

    #_0CF65E: LDX.b $00

    #_0CF660: LDA.w pool_Dramagahnim_CastSpell_oam_count,X
    #_0CF663: TAY

    #_0CF664: JSR Attract_DrawPreloadedSprite

    #_0CF667: PLB

    ; -------------------------------------------------------

    #_0CF668: LDA.b $51
    #_0CF66A: BNE .delay_tick

    #_0CF66C: DEC.b $62
    #_0CF66E: BEQ Dramagahnim_ReadySpell_advance

    #_0CF670: BRA .exit

  .delay_tick
    #_0CF672: DEC.b $51

  .exit
    #_0CF674: RTS
}

; ==========================================================

org $0CF675
pool_Dramagahnim_RealizeWhatJustHappened:
{
  .pointers_offset_x
    #_0CF675: dw AttractTelebubbleOAM_step0_offset_x
    #_0CF677: dw AttractTelebubbleOAM_step1_offset_x

  .pointers_offset_y
    #_0CF679: dw AttractTelebubbleOAM_step0_offset_y
    #_0CF67B: dw AttractTelebubbleOAM_step1_offset_y

  .pointers_char
    #_0CF67D: dw AttractTelebubbleOAM_step0_char
    #_0CF67F: dw AttractTelebubbleOAM_step1_char

  .pointers_prop
    #_0CF681: dw AttractTelebubbleOAM_step0_prop
    #_0CF683: dw AttractTelebubbleOAM_step1_prop

  .position_x
    #_0CF685: db $78
    #_0CF686: db $70

  .object_count
    #_0CF687: db $00
    #_0CF688: db $01
}

; -------------------------------------------------------

org $0CF689
Dramagahnim_RealizeWhatJustHappened:
{
    #_0CF689: LDA.b $51
    #_0CF68B: CMP.b #$06
    #_0CF68D: BNE .delay_sfx

    #_0CF68F: INC.b $52

    #_0CF691: LDA.b #$33 ; SFX2.33
    #_0CF693: STA.w $012E

  .delay_sfx
    #_0CF696: CMP.b #$40
    #_0CF698: BNE .delay_tick

    #_0CF69A: LDA.b #$E0
    #_0CF69C: STA.b $51

    #_0CF69E: INC.b $60

  .delay_tick
    #_0CF6A0: CMP.b #$0F
    #_0CF6A2: BCS .skip_draw

    #_0CF6A4: LSR A
    #_0CF6A5: LSR A
    #_0CF6A6: AND.b #$02
    #_0CF6A8: TAX

    #_0CF6A9: REP #$20

    #_0CF6AB: LDA.w #AttractTelebubbleOAM_size
    #_0CF6AE: STA.b $2D

    #_0CF6B0: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_pointers_offset_x,X
    #_0CF6B4: STA.b $02

    #_0CF6B6: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_pointers_offset_y,X
    #_0CF6BA: STA.b $04

    #_0CF6BC: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_pointers_char,X
    #_0CF6C0: STA.b $06

    #_0CF6C2: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_pointers_prop,X
    #_0CF6C6: STA.b $08

    ; -------------------------------------------------------

    #_0CF6C8: SEP #$20

    #_0CF6CA: TXA
    #_0CF6CB: LSR A
    #_0CF6CC: TAX

    #_0CF6CD: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_position_x,X
    #_0CF6D1: STA.b $28

    #_0CF6D3: LDA.b #$60
    #_0CF6D5: STA.b $29

    #_0CF6D7: LDA.l pool_Dramagahnim_RealizeWhatJustHappened_object_count,X
    #_0CF6DB: TAY

    #_0CF6DC: JSR Attract_DrawPreloadedSprite

  .skip_draw
    #_0CF6DF: INC.b $51

    #_0CF6E1: RTS
}
; ==========================================================

org $0CF6E2
Dramagahnim_IdleGuiltily:
{
    #_0CF6E2: JSR Attract_DoTextInDungeonScene

    #_0CF6E5: REP #$20

    #_0CF6E7: LDA.b $64

    #_0CF6E9: SEP #$20

    #_0CF6EB: BNE .exit

    #_0CF6ED: LDA.b $51
    #_0CF6EF: CMP.b #$1F
    #_0CF6F1: BCS .delay_fade

    #_0CF6F3: AND.b #$01
    #_0CF6F5: BNE .delay_fade

    #_0CF6F7: DEC.b $13

  .delay_fade
    #_0CF6F9: DEC.b $51
    #_0CF6FB: BNE .exit

    #_0CF6FD: INC.b $5D

  .exit
    #_0CF6FF: RTS
}

; ==========================================================

org $0CF700
Attract_SkipToFileSelect:
{
  #_0CF700: DEC.b $13
  #_0CF702: BNE .exit

  #_0CF704: JSL EnableForceBlank

  #_0CF708: LDA.b #$13
  #_0CF70A: STA.w BG1SC

  #_0CF70D: LDA.b #$03
  #_0CF70F: STA.w BG2SC

  #_0CF712: REP #$20

  #_0CF714: JSL Attract_SetUpConclusionHDMA

  #_0CF718: REP #$20

  #_0CF71A: STZ.w $063A
  #_0CF71D: STZ.w $0638

  #_0CF720: STZ.w $0120
  #_0CF723: STZ.w $0124

  #_0CF726: STZ.b $EA

  #_0CF728: SEP #$20

  #_0CF72A: JMP.w FadeMusicAndResetSRAMMirror

.exit
  #_0CF72D: RTL
}

org $0CF8A7
AttractOAMData:
{
  .king_size
  #_0CF8A7: db $02, $02, $02, $02

  .king_offset_x
  #_0CF8AB: db  16,   0,  16,   0

  .king_offset_y
  #_0CF8AF: db  16,  16,   0,   0

  .king_char
  #_0CF8B3: db $2A, $2A, $0A, $0A

  .king_prop
  #_0CF8B7: db $79, $39, $79, $39

  ; ==========================================================

  .mantle_size
  #_0CF8BB: db $02, $02, $02, $02, $02, $02

  .mantle_offset_x
  #_0CF8C1: db   0,  16,  32,   0,  16,  32

  .mantle_offset_y
  #_0CF8C7: db   0,   0,   0,  16,  16,  16

  .mantle_char
  #_0CF8CD: db $0C, $0E, $0C, $2C, $2E, $2C

  .mantle_prop
  #_0CF8D3: db $31, $31, $71, $31, $31, $71
}

AttractAgahnimOAM:
{
  .size
  #_0CF8D9: db $02, $02, $02, $02, $02, $02

  .offset_x
  #_0CF8DF: db  0, 16, 0, 16, 0, 16

  .offset_y
  #_0CF8E5: db  12,  12, -12,  -12, -4,   -4

  ; ==========================================================

  .char_step3
  #_0CF8EB: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step5
  #_0CF8F1: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step6
  #_0CF8F7: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step4
  #_0CF8FD: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step0
  #_0CF903: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step1
  #_0CF909: db $EC, $EE, $C7, $C7, $D7, $D7

  .char_step2
  #_0CF90F: db $EC, $EE, $C7, $C7, $D7, $D7

  ; ==========================================================

  .prop_step0
  #_0CF915: db $39, $39, $39, $79, $39, $79

  .prop_step1
  #_0CF91B: db $39, $39, $39, $79, $39, $79

  .prop_step2
  #_0CF921: db $39, $39, $39, $79, $39, $79
}

; ==========================================================

AttractAltarMaidenOAM:
{
  .size
  #_0CF927: db $02, $02

  .offset_x
  #_0CF929: db $00, $08

  .offset_y
  #_0CF92B: db $00, $00

  .char_step0
  #_0CF92D: db $03, $04

  .char_step1
  #_0CF92F: db $00, $01

  .prop
  #_0CF931: db $3D, $3D
}

; ==========================================================

AttractAltarMaidenShadowOAM:
{
  .size
  #_0CF933: db $02, $02

  ; ==========================================================

  .offset_x_step4
  #_0CF935: db $00, $08

  .offset_x_step3
  #_0CF937: db $00, $06

  .offset_x_step2
  #_0CF939: db $00, $04

  .offset_x_step1
  #_0CF93B: db $00, $02

  .offset_x_step0
  #_0CF93D: db $00, $00

  ; ==========================================================

  .offset_y
  #_0CF93F: db $00, $00

  .char
  #_0CF941: db $6C, $6C

  .prop
  #_0CF943: db $38, $38
}

; ==========================================================

DramagahnimSpellOAM:
{
  .size
  #_0CF945: db $00, $00, $00, $00
  #_0CF949: db $00, $00, $00, $00
  #_0CF94D: db $00, $00, $02, $02
  #_0CF951: db $02, $02

  .offset_x
  #_0CF953: db   0,  28,  -2,  30
  #_0CF957: db  -2,  30,   0,  28
  #_0CF95B: db   0,  28,   2,  18
  #_0CF95F: db   2,  18

  .offset_y
  #_0CF961: db   0,   0,   3,   3
  #_0CF965: db  11,  11,  16,  16
  #_0CF969: db  24,  24,  16,  16
  #_0CF96D: db  32,  32

  ; ==========================================================

  .char_step0
  #_0CF96F: db $CE, $CE, $26, $26
  #_0CF973: db $36, $36, $26, $26
  #_0CF977: db $36, $36, $20, $20
  #_0CF97B: db $20, $20

  .char_step1
  #_0CF97D: db $CE, $CE, $26, $26
  #_0CF981: db $36, $36, $26, $26
  #_0CF985: db $36, $36, $22, $22
  #_0CF989: db $22, $22

  ; ==========================================================

  .prop_step0
  #_0CF98B: db $35, $35, $75, $35
  #_0CF98F: db $75, $35, $75, $35
  #_0CF993: db $75, $35, $35, $75
  #_0CF997: db $B5, $F5

  .prop_step1
  #_0CF999: db $37, $37, $77, $37
  #_0CF99D: db $77, $37, $77, $37
  #_0CF9A1: db $77, $37, $37, $77
  #_0CF9A5: db $B7, $F7
}

; ==========================================================

AttractTelebubbleOAM:
{
  .size
  #_0CF9A7: db $02, $02

  .step0_offset_x
  #_0CF9A9: db   0

  .step0_offset_y
  #_0CF9AA: db   0

  .step0_char
  #_0CF9AB: db $C6

  .step0_prop
  #_0CF9AC: db $3D

  ; ==========================================================

  .step1_offset_x
  #_0CF9AD: db   0,  16

  .step1_offset_y
  #_0CF9AF: db   0,   0

  .step1_char
  #_0CF9B1: db $24, $24

  .step1_prop
  #_0CF9B3: db $35, $75
}