OverworldLocationNames:
  dw "RANCH___________" ; 00
  dw "RANCH___________" ; 01
  dw "PYRAMID_________" ; 02
  dw "LAND_OF_TREE____" ; 03
  dw "SNOW_MOUNTAIN___" ; 04
  dw "SNOW_MOUNTAIN___" ; 05
  dw "SNOW_MOUNTAIN___" ; 06
  dw "SNOW_MOUNTAIN___" ; 07
  dw "RANCH___________" ; 08
  dw "RANCH___________" ; 09
  dw "INN_____________" ; 0A
  dw "KALYXO_CASTLE___" ; 0B
  dw "KALYXO_CASTLE___" ; 0C
  dw "POTION_SHOP_____" ; 0D
  dw "HALL_OF_SECRETS_" ; 0E
  dw "CEMETERY________" ; 0F
  dw "TOADSTOOL_WOODS_" ; 10
  dw "RANCH_PATH______" ; 11
  dw "CROSSROADS______" ; 12
  dw "KALYXO_CASTLE___" ; 13
  dw "KALYXO_CASTLE___" ; 14
  dw "MOUNTAINSIDE____" ; 15
  dw "PATH_OF_SECRETS_" ; 16
  dw "ANCIENT_SHRINE__" ; 17
  dw "TOADSTOOL_WOODS_" ; 18
  dw "TOADSTOOL_WOODS_" ; 19
  dw "CROSSROADS______" ; 1A
  dw "KALYXO_CASTLE___" ; 1B
  dw "KALYXO_ROAD_____" ; 1C
  dw "CROSSROADS______" ; 1D
  dw "SUNKEN_CITY_____" ; 1E
  dw "SUNKEN_CITY_____" ; 1F
  dw "TOADSTOOL_WOODS_" ; 20
  dw "TOADSTOOL_WOODS_" ; 21
  dw "SWORDSMITHS_____" ; 22
  dw "WAYWARD_VILLAGE_" ; 23
  dw "WAYWARD_VILLAGE_" ; 24
  dw "VILLAGE_ROAD____" ; 25
  dw "SUNKEN_CITY_____" ; 26
  dw "SUNKEN_CITY_____" ; 27
  dw "TOADSTOOL_WOODS_" ; 28
  dw "TOADSTOOL_WOODS_" ; 29
  dw "VILLAGE_ROAD____" ; 2A
  dw "WAYWARD_VILLAGE_" ; 2B
  dw "WAYWARD_VILLAGE_" ; 2C
  dw "VALLEY__________" ; 2D
  dw "CITY_ROAD_______" ; 2E
  dw "TAIL_PALACE_____" ; 2F
  dw "DRAGON_SHIP_____" ; 30
  dw "DRAGON_SHIP_____" ; 31
  dw "SECRET_BEACH____" ; 32
  dw "LOOM_BEACH______" ; 33
  dw "LOOM_BEACH______" ; 34
  dw "BEACH_PATH______" ; 35
  dw "GARO_DESERT_____" ; 36
  dw "GARO_DESERT_____" ; 37
  dw "DRAGON_SHIP_____" ; 38
  dw "DRAGON_SHIP_____" ; 39
  dw "LOST_SEA________" ; 3A
  dw "LOOM_BEACH______" ; 3B
  dw "LOOM_BEACH______" ; 3C
  dw "LOOM_WATERFALL__" ; 3D
  dw "GARO_DESERT_____" ; 3E
  dw "GARO_DESERT_____" ; 3F

; Abyss names are 15 cells wide. DrawLocationName steps 16 cells per area, so
; each entry gets a 16th blank cell.
macro AbyssName(text)
  dw "<text>"
  dw "_"
endmacro

DarkWorldLocationNames:
  %AbyssName("TEMPORAL_GATE__") ; 00
  %AbyssName("TEMPORAL_GATE__") ; 01
  %AbyssName("PYRAMID_OF_EONS") ; 02
  %AbyssName("LAVA_LANDS_____") ; 03
  %AbyssName("LAVA_LANDS_____") ; 04
  %AbyssName("LAVA_LANDS_____") ; 05
  %AbyssName("LAVA_LANDS_____") ; 06
  %AbyssName("LAVA_LANDS_____") ; 07
  %AbyssName("TEMPORAL_GATE__") ; 08
  %AbyssName("TEMPORAL_GATE__") ; 09
  %AbyssName("LUPO_WATERFALL_") ; 0A
  %AbyssName("THE_FORTRESS___") ; 0B
  %AbyssName("THE_FORTRESS___") ; 0C
  %AbyssName("LUPO_MOUNTAIN__") ; 0D
  %AbyssName("LAVA_LANDS_____") ; 0E
  %AbyssName("LAVA_LANDS_____") ; 0F
  %AbyssName("SHRINE_COURAGE_") ; 10
  %AbyssName("_______________") ; 11
  %AbyssName("_______________") ; 12
  %AbyssName("THE_FORTRESS___") ; 13
  %AbyssName("THE_FORTRESS___") ; 14
  %AbyssName("LUPO_MOUNTAIN__") ; 15
  %AbyssName("LAVA_LANDS_____") ; 16
  %AbyssName("LAVA_LANDS_____") ; 17
  %AbyssName("_______________") ; 18
  %AbyssName("_______________") ; 19
  %AbyssName("_______________") ; 1A
  %AbyssName("_______________") ; 1B
  %AbyssName("_______________") ; 1C
  %AbyssName("_______________") ; 1D
  %AbyssName("LUPO_MOUNTAIN__") ; 1E
  %AbyssName("LUPO_MOUNTAIN__") ; 1F
  %AbyssName("_______________") ; 20
  %AbyssName("_______________") ; 21
  %AbyssName("_______________") ; 22
  %AbyssName("WISDOM_SWAMP___") ; 23
  %AbyssName("WISDOM_SWAMP___") ; 24
  %AbyssName("_______________") ; 25
  %AbyssName("LUPO_MOUNTAIN__") ; 26
  %AbyssName("LUPO_MOUNTAIN__") ; 27
  %AbyssName("_______________") ; 28
  %AbyssName("_______________") ; 29
  %AbyssName("_______________") ; 2A
  %AbyssName("WISDOM_SWAMP___") ; 2B
  %AbyssName("WISDOM_SWAMP___") ; 2C
  %AbyssName("_______________") ; 2D
  %AbyssName("_______________") ; 2E
  %AbyssName("_______________") ; 2F
  %AbyssName("UNDERWATER_____") ; 30
  %AbyssName("UNDERWATER_____") ; 31
  %AbyssName("UNDERWATER_____") ; 32
  %AbyssName("UNDERWATER_____") ; 33
  %AbyssName("UNDERWATER_____") ; 34
  %AbyssName("UNDERWATER_____") ; 35
  %AbyssName("ABYSS_BEACH____") ; 36
  %AbyssName("ABYSS_BEACH____") ; 37
  %AbyssName("UNDERWATER_____") ; 38
  %AbyssName("UNDERWATER_____") ; 39
  %AbyssName("UNDERWATER_____") ; 3A
  %AbyssName("UNDERWATER_____") ; 3B
  %AbyssName("UNDERWATER_____") ; 3C
  %AbyssName("UNDERWATER_____") ; 3D
  %AbyssName("ABYSS_BEACH____") ; 3E
  %AbyssName("ABYSS_BEACH____") ; 3F


DungeonLocationNames:
  dw "TRIFORCE_CHAMBER", "HALL_OF_SECRETS_", "________________", "DEVELOPERS_DEN__" 
  dw "________________", "________________", "ZORA_TEMPLE_____", "SHRINE_COURAGE__"
  dw "FAIRY_FOUNTAIN__", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "________________" ; 0F

  dw "________________", "________________", "HALL_OF_SECRETS_", "________________"
  dw "________________", "ZORA_TEMPLE_____", "SHRINE_COURAGE__", "ZORA_TEMPLE_____"
  dw "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_", "________________"
  dw "________________", "TAIL_PALACE_____", "________________", "________________" ; 1F

  dw "________________", "________________", "________________", "SHRINE_COURAGE__"
  dw "ZORA_TEMPLE_____", "ZORA_TEMPLE_____", "SHRINE_COURAGE__", "ZORA_TEMPLE_____"
  dw "KALYXO_CASTLE___", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_", "________________"
  dw "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____", "________________" ; 2F

  dw "________________", "________________", "________________", "SHRINE_COURAGE__"
  dw "ZORA_TEMPLE_____", "ZORA_TEMPLE_____", "ZORA_TEMPLE_____", "KALYXO_CASTLE___"
  dw "KALYXO_CASTLE___", "KALYXO_CASTLE___", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_"
  dw "________________", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 3F

  dw "HALL_OF_SECRETS_", "HALL_OF_SECRETS_", "HALL_OF_SECRETS_", "SHRINE_COURAGE__"
  dw "ZORA_TEMPLE_____", "ZORA_TEMPLE_____", "ZORA_TEMPLE_____", "KALYXO_CASTLE___"
  dw "KALYXO_CASTLE___", "KALYXO_CASTLE___", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 4F

  dw "________________", "________________", "________________", "SHRINE_COURAGE__"
  dw "CASTLE_BASEMENT_", "CASTLE_BASEMENT_", "KALYXO_CASTLE___", "KALYXO_CASTLE___"
  dw "KALYXO_CASTLE___", "KALYXO_CASTLE___", "MUSHROOM_GROTTO_", "MUSHROOM_GROTTO_"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 5F

  dw "________________", "________________", "________________", "SHRINE_COURAGE__"
  dw "________________", "________________", "KALYXO_CASTLE___", "KALYXO_CASTLE___"
  dw "KALYXO_CASTLE___", "GORON_MINES_____", "MUSHROOM_GROTTO_", "FORTRESS_SECRETS"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 6F

  dw "CASTLE_BASEMENT_", "CASTLE_BASEMENT_", "CASTLE_BASEMENT_", "SHRINE_POWER____"
  dw "SHRINE_POWER____", "SHRINE_POWER____", "SHRINE_POWER____", "GORON_MINES_____"
  dw "GORON_MINES_____", "GORON_MINES_____", "SHRINE_WISDOM___", "FORTRESS_SECRETS"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 7F

  dw "CASTLE_BASEMENT_", "CASTLE_BASEMENT_", "CASTLE_BASEMENT_", "SHRINE_POWER____"
  dw "SHRINE_POWER____", "SHRINE_POWER____", "SHRINE_POWER____", "GORON_MINES_____"
  dw "GORON_MINES_____", "GORON_MINES_____", "SHRINE_WISDOM___", "FORTRESS_SECRETS"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "TAIL_PALACE_____", "TAIL_PALACE_____" ; 8F

  dw "________________", "________________", "________________", "________________"
  dw "________________", "________________", "________________", "GORON_MINES_____"
  dw "GORON_MINES_____", "GORON_MINES_____", "SHRINE_WISDOM___", "FORTRESS_SECRETS"
  dw "FORTRESS_SECRETS", "FORTRESS_SECRETS", "GLACIA_ESTATE___", "GLACIA_ESTATE___" ; 9F

  dw "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____"
  dw "KYDROGS_DEN_____", "KYDROGS_SHIP____", "________________", "________________"
  dw "GORON_MINES_____", "GORON_MINES_____", "SHRINE_WISDOM___", "________________"
  dw "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___" ; AF

  dw "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____"
  dw "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____"
  dw "GORON_MINES_____", "GORON_MINES_____", "SHRINE_WISDOM___", "GLACIA_ESTATE___"
  dw "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___" ; BF

  dw "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____"
  dw "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "KYDROGS_SHIP____"
  dw "GORON_MINES_____", "SHRINE_WISDOM___", "SHRINE_WISDOM___", "GLACIA_ESTATE___"
  dw "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___", "GLACIA_ESTATE___" ; CF

  dw "ABYSS_LAVA_CAVE_", "ABYSS_LAVA_CAVE_", "ABYSS_LAVA_CAVE_", "FROSTPEAK_CAVE__"
  dw "FROSTPEAK_CAVE__", "KYDROGS_SHIP____", "KYDROGS_SHIP____", "GORON_MINES_____"
  dw "GORON_MINES_____", "GORON_MINES_____", "GORON_MINES_____", "GLACIA_ESTATE___"
  dw "GLACIA_ESTATE___", "GLACIA_ESTATE___", "TAIL_PALACE_____", "GLACIA_ESTATE___" ; DF

  dw "________________", "________________", "________________", "________________"
  dw "FROSTPEAK_CAVE__", "FROSTPEAK_CAVE__", "TAIL_CAVE_ROUTE_", "TAIL_CAVE_ROUTE_"
  dw "MOUNTAIN_CAVE___", "________________", "________________", "________________"
  dw "________________", "________________", "FROSTPEAK_CAVE__", "FROSTPEAK_CAVE__" ; EF

  dw "________________", "________________", "________________", "________________"
  dw "________________", "________________", "________________", "________________"
  dw "________________", "________________", "________________", "________________"
  dw "________________", "VILLAGE_CAVE____", "VILLAGE_CAVE____", "________________" ; FF

  dw "CHEST_GAME______", "RANCH_GIRL_HOUSE", "SICK_BOY_HOUSE__", "VILLAGE_BAR_____"
  dw "YOUR_HOUSE______", "ZORA_CHAMBERS___", "________________", "VILLAGE_LIBRARY_"
  dw "RANCH_HOUSE_____", "POTION_SHOP_____", "ZENIEA_CAVE_____", "ZORA_WATERFALL__"
  dw "________________", "GORON_STORAGE___", "________________", "KALY_HOTEL______" ; 10F

  dw "________________", "ARROW_MINIGAME__", "MAGIC_SCHOOL____", "BELOW_GRAVEYARD_"
  dw "FAIRY_FOUNTAIN__", "FAIRY_FOUNTAIN__", "FAIRY_FOUNTAIN__", "SPIKE_CAVE______"
  dw "________________", "TOWN_HALL_______", "________________", "________________"
  dw "BOMB_SHOP_______", "MAYORAL_BASEMENT", "________________", "HAPPY_MASK_SHOP_" ; 11F

  dw "WOLFOS_CAVE_____", "SWORDSMITHS_HUT_", "FORTUNE_TELLER__", "CAVE____________"
  dw "CAVE____________", "CAVE____________", "CAVE____________", "CAVE____________" ; 127

