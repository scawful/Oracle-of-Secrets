; Expanded Music Banks
; Adds a new song bank to the dark world

SPC_ENGINE          = $0800
SFX_DATA            = $17C0
SAMPLE_POINTERS     = $3C00
INSTRUMENT_DATA     = $3D00
INSTRUMENT_DATA_SFX = $3E00
SAMPLE_DATA         = $4000
SONG_POINTERS       = $D000
SONG_POINTERS_AUX   = $2B00
CREDITS_AUX_POINTER = $2900
LoadOverworldSongs = $008913
SongBank_Overworld_Main = $1A9EF5

pullpc
SongBank_OverworldExpanded_Main:
  #_1A9EF5: dw $2DAE, SONG_POINTERS ; Transfer size, transfer address

base SONG_POINTERS
{
  #_1A9EF9: #_D000o: dw Song01_TriforceIntro
  #_1A9EFB: #_D002o: dw Song02_LightWorldOverture
  #_1A9EFD: #_D004o: dw Song03_Rain
  #_1A9EFF: #_D006o: dw Song04_BunnyTheme
  #_1A9F01: #_D008o: dw Song05_LostWoods
  #_1A9F03: #_D00Ao: dw Song06_LegendsTheme_Attract
  #_1A9F05: #_D00Co: dw Song07_KakarikoVillage
  #_1A9F07: #_D00Eo: dw Song08_MirrorWarp
  #_1A9F09: #_D010o: dw Song09_DarkWorld
  #_1A9F0B: #_D012o: dw Song0A_PullingTheMasterSword
  #_1A9F0D: #_D014o: dw Song0B_FairyTheme
  #_1A9F0F: #_D016o: dw Song0C_Fugitive
  #_1A9F11: #_D018o: dw Song0D_SkullWoodsMarch
  #_1A9F13: #_D01Ao: dw Song0E_MinigameTheme
  #_1A9F15: #_D01Co: dw Song0F_IntroFanfare
  #_1A9F17: #_D01Eo: dw $0000
  #_1A9F19: #_D020o: dw $0000
  #_1A9F1B: #_D022o: dw $0000
  #_1A9F1D: #_D024o: dw $0000
  #_1A9F1F: #_D026o: dw $0000
  #_1A9F21: #_D028o: dw $0000
  #_1A9F23: #_D02Ao: dw $0000
  #_1A9F25: #_D02Co: dw $0000
  #_1A9F27: #_D02Eo: dw $0000
  #_1A9F29: #_D030o: dw $0000
  #_1A9F2B: #_D032o: dw $0000
  #_1A9F2D: #_D034o: dw $0000

Song01_TriforceIntro:
  incbin song01.bin

Song02_LightWorldOverture:
  incbin song02.bin

Song03_Rain:
  ; incbin song03.bin
  incsrc deku_theme.asm

Song04_BunnyTheme:
  incbin song04.bin

Song05_LostWoods:
  incbin song05.bin

Song06_LegendsTheme_Attract:
  incbin song06.bin

Song07_KakarikoVillage:
  incbin song07.bin

Song08_MirrorWarp:
  incbin song08.bin

Song09_DarkWorld:
  incbin song09.bin

Song0A_PullingTheMasterSword:
  incbin song0A.bin

Song0B_FairyTheme:
  incbin song0B.bin

Song0C_Fugitive:
  incbin song0C.bin

Song0F_IntroFanfare:
  incbin song0F.bin
}
base off 

SongBank_Overworld_Auxiliary:
#_1ACCA7: dw $0688, SONG_POINTERS_AUX ; Transfer size, transfer address

base SONG_POINTERS_AUX
{
  Song0D_SkullWoodsMarch:
    incbin song0D.bin

  Song0E_MinigameTheme:
    incbin song0E.bin
}
base off

#_1AF420: dw $0000, SPC_ENGINE ; end of transfer

print pc
LoadOverworldSongsExpanded:
{
  LDA.w $0FFF : BEQ .light_world
    LDA.b #SongBank_OverworldExpanded_Main>>0
    STA.b $00

    LDA.b #SongBank_OverworldExpanded_Main>>8
    STA.b $01

    LDA.b #SongBank_OverworldExpanded_Main>>16
    STA.b $02
    RTL
  .light_world 
  #_008913: LDA.b #SongBank_Overworld_Main>>0
  #_008915: STA.b $00

  #_008917: LDA.b #SongBank_Overworld_Main>>8
  #_008919: STA.b $01

  #_00891B: LDA.b #SongBank_Overworld_Main>>16
  #_00891D: STA.b $02

  RTL
}

pushpc

org $008919 ; LoadOverworldSongs ; @hook module=Music
  JSL LoadOverworldSongsExpanded

pullpc
