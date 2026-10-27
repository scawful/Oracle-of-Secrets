"""Verify the explicit ordinary private-candidate native reader variant.

This never publishes a ROM, allocates a byte, or refreshes a frozen assignment.
The saved-source ownership and compiled-reader contracts are separate checks.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_tile32 as T32

KIND = 'lyra.ordinary_private_native_readers.v1'
DESCRIPTOR_PC = 0x3C5FC0
CODE_START = 0x3C4000
CODE_END = DESCRIPTOR_PC
# Independently reviewed first assembly: ROM2153ae21, symbols9b314bda.
# Fixed source data, not mutable WLA or allocation-ledger authority.
REVIEWED_COMPILED_BINDING = json.loads(r'''{
  "qualified": false,
  "kind": "lyra.ordinary_private_native_readers.v1",
  "source_sha256": {
    "Oracle_main.asm": "e6f991fde480344f45a9616edd2f26858e7074901da3a43e60512e6c03a98f00",
    "Overworld/lyra_native_loaders.asm": "d80f2195b21dc6ca2cc2e67775148a4411c53ae9de246c5d17d2e40f25138bd8",
    "Overworld/ZSCustomOverworld.asm": "f4af3051ea42436dfdd14418c2967bdd52633ad9cfd784b997730eab028ff1cc",
    "Overworld/time_system.asm": "63b086712180db88205d7b9452bde8c1c19015c119abd3c6a7f390272fac7e7f",
    "Overworld/lost_woods.asm": "3983c065b08d95199d22543cfa6c51a03a2f323aee3841ab8d1a386e8c07640d"
  },
  "source_calls": [
    {
      "label": "LyraCall_Animated_0",
      "pc": 1317201,
      "target": "Lyra_ReadAnimated"
    },
    {
      "label": "LyraCall_Overlay_0",
      "pc": 1317288,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_Overlay_1",
      "pc": 28354,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_SpritePalette_0",
      "pc": 66602,
      "target": "Lyra_ReadSpritePalette"
    },
    {
      "label": "LyraCall_PaletteSet_0",
      "pc": 66608,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_PaletteSet_1",
      "pc": 67160,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_Overlay_2",
      "pc": 1317338,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_PaletteSet_2",
      "pc": 78737,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_Overlay_3",
      "pc": 1317363,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_Overlay_4",
      "pc": 1317395,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_MainPalette_0",
      "pc": 83604,
      "target": "Lyra_ReadMainPalette"
    },
    {
      "label": "LyraCall_Gfx0_0",
      "pc": 1317586,
      "target": "Lyra_ReadGfx0"
    },
    {
      "label": "LyraCall_MainPalette_1",
      "pc": 1317797,
      "target": "Lyra_ReadMainPalette"
    },
    {
      "label": "LyraCall_MainPalette_2",
      "pc": 1317851,
      "target": "Lyra_ReadMainPalette"
    },
    {
      "label": "LyraCall_Overlay_5",
      "pc": 1317897,
      "target": "Lyra_ReadOverlay"
    },
    {
      "label": "LyraCall_Gfx0_1",
      "pc": 1318075,
      "target": "Lyra_ReadGfx0"
    },
    {
      "label": "LyraCall_Gfx1_0",
      "pc": 1318110,
      "target": "Lyra_ReadGfx1"
    },
    {
      "label": "LyraCall_Gfx2_0",
      "pc": 1318145,
      "target": "Lyra_ReadGfx2"
    },
    {
      "label": "LyraCall_Gfx7_0",
      "pc": 1318180,
      "target": "Lyra_ReadGfx7"
    },
    {
      "label": "LyraCall_Gfx3_0",
      "pc": 1318479,
      "target": "Lyra_ReadGfx3"
    },
    {
      "label": "LyraCall_Gfx4_0",
      "pc": 1318526,
      "target": "Lyra_ReadGfx4"
    },
    {
      "label": "LyraCall_Gfx5_0",
      "pc": 1318573,
      "target": "Lyra_ReadGfx5"
    },
    {
      "label": "LyraCall_Gfx6_0",
      "pc": 1318620,
      "target": "Lyra_ReadGfx6"
    },
    {
      "label": "LyraCall_Gfx0_2",
      "pc": 1318852,
      "target": "Lyra_ReadGfx0"
    },
    {
      "label": "LyraCall_Gfx1_1",
      "pc": 1318868,
      "target": "Lyra_ReadGfx1"
    },
    {
      "label": "LyraCall_Gfx2_1",
      "pc": 1318884,
      "target": "Lyra_ReadGfx2"
    },
    {
      "label": "LyraCall_Gfx3_1",
      "pc": 1318900,
      "target": "Lyra_ReadGfx3"
    },
    {
      "label": "LyraCall_Gfx4_1",
      "pc": 1318920,
      "target": "Lyra_ReadGfx4"
    },
    {
      "label": "LyraCall_Gfx5_1",
      "pc": 1318940,
      "target": "Lyra_ReadGfx5"
    },
    {
      "label": "LyraCall_Gfx6_1",
      "pc": 1318960,
      "target": "Lyra_ReadGfx6"
    },
    {
      "label": "LyraCall_Gfx7_1",
      "pc": 1318980,
      "target": "Lyra_ReadGfx7"
    },
    {
      "label": "LyraCall_Gfx3_2",
      "pc": 1319024,
      "target": "Lyra_ReadGfx3"
    },
    {
      "label": "LyraCall_Gfx4_2",
      "pc": 1319042,
      "target": "Lyra_ReadGfx4"
    },
    {
      "label": "LyraCall_Gfx5_2",
      "pc": 1319060,
      "target": "Lyra_ReadGfx5"
    },
    {
      "label": "LyraCall_Gfx6_2",
      "pc": 1319078,
      "target": "Lyra_ReadGfx6"
    },
    {
      "label": "LyraCall_Gfx1_2",
      "pc": 1319126,
      "target": "Lyra_ReadGfx1"
    },
    {
      "label": "LyraCall_Gfx0_3",
      "pc": 1319142,
      "target": "Lyra_ReadGfx0"
    },
    {
      "label": "LyraCall_Gfx3_3",
      "pc": 1319189,
      "target": "Lyra_ReadGfx3"
    },
    {
      "label": "LyraCall_Gfx2_2",
      "pc": 1319205,
      "target": "Lyra_ReadGfx2"
    },
    {
      "label": "LyraCall_Gfx7_2",
      "pc": 1319252,
      "target": "Lyra_ReadGfx7"
    },
    {
      "label": "LyraCall_Gfx6_3",
      "pc": 1319271,
      "target": "Lyra_ReadGfx6"
    },
    {
      "label": "LyraCall_SpritePalette_1",
      "pc": 76532,
      "target": "Lyra_ReadSpritePalette"
    },
    {
      "label": "LyraCall_PaletteSet_3",
      "pc": 76538,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_Size_0",
      "pc": 1319314,
      "target": "Lyra_ReadSize"
    },
    {
      "label": "LyraCall_TransitionYY_0",
      "pc": 1319329,
      "target": "Lyra_ReadTransitionYY"
    },
    {
      "label": "LyraCall_TransitionXY_0",
      "pc": 1319343,
      "target": "Lyra_ReadTransitionXY"
    },
    {
      "label": "LyraCall_ScrollNorth_0",
      "pc": 1319357,
      "target": "Lyra_ReadScrollNorth"
    },
    {
      "label": "LyraCall_ScrollWest_0",
      "pc": 1319371,
      "target": "Lyra_ReadScrollWest"
    },
    {
      "label": "LyraCall_SpriteGfxByArea_0",
      "pc": 76567,
      "target": "Lyra_ReadSpriteGfxByArea"
    },
    {
      "label": "LyraCall_AreaGfx_0",
      "pc": 76574,
      "target": "Lyra_ReadAreaGfx"
    },
    {
      "label": "LyraCall_Size_1",
      "pc": 76589,
      "target": "Lyra_ReadSize"
    },
    {
      "label": "LyraCall_TransitionYX_0",
      "pc": 1319437,
      "target": "Lyra_ReadTransitionYX"
    },
    {
      "label": "LyraCall_TransitionXX_0",
      "pc": 1319444,
      "target": "Lyra_ReadTransitionXX"
    },
    {
      "label": "LyraCall_Size_2",
      "pc": 1319456,
      "target": "Lyra_ReadSize"
    },
    {
      "label": "LyraCall_Size_3",
      "pc": 312522,
      "target": "Lyra_ReadSize"
    },
    {
      "label": "LyraCall_SpecialSpriteGfx_0",
      "pc": 92471,
      "target": "Lyra_ReadSpecialSpriteGfx"
    },
    {
      "label": "LyraCall_SpecialEntryGfx_0",
      "pc": 92478,
      "target": "Lyra_ReadSpecialEntryGfx"
    },
    {
      "label": "LyraCall_SpecialPalette_0",
      "pc": 92485,
      "target": "Lyra_ReadSpecialPalette"
    },
    {
      "label": "LyraCall_PaletteSet_4",
      "pc": 92493,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_TransitionYX_1",
      "pc": 92525,
      "target": "Lyra_ReadTransitionYX"
    },
    {
      "label": "LyraCall_TransitionXX_1",
      "pc": 92532,
      "target": "Lyra_ReadTransitionXX"
    },
    {
      "label": "LyraCall_PaletteSet_5",
      "pc": 67291,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_PaletteSet_6",
      "pc": 78075,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_PaletteSet_7",
      "pc": 79053,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_PaletteSet_8",
      "pc": 92843,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_PaletteSet_9",
      "pc": 93416,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_SpecialPalette_1",
      "pc": 1319633,
      "target": "Lyra_ReadSpecialPalette"
    },
    {
      "label": "LyraCall_BombDoor_0",
      "pc": 94052,
      "target": "Lyra_ReadBombDoor"
    },
    {
      "label": "LyraCall_Sign_0",
      "pc": 1319657,
      "target": "Lyra_ReadSign"
    },
    {
      "label": "LyraCall_SpritePointer",
      "pc": 312560,
      "target": "Lyra_SpritePointer"
    },
    {
      "label": "LyraCall_SpritePalette_2",
      "pc": 98182,
      "target": "Lyra_ReadSpritePalette"
    },
    {
      "label": "LyraCall_PaletteSet_10",
      "pc": 98188,
      "target": "Lyra_ReadPaletteSet"
    },
    {
      "label": "LyraCall_Parent_0",
      "pc": 1077254,
      "target": "Lyra_ReadParent"
    },
    {
      "label": "LyraCall_Parent_1",
      "pc": 1077262,
      "target": "Lyra_ReadParent"
    }
  ],
  "consumer_spans": [
    {
      "label": "LyraHost_ReadAnimatedTable",
      "pc": [
        1317184,
        1317223
      ],
      "sha256": "e59e3e1cb72a8db6a5e715bf1a8c85d1ff59bedd8c3c662ef71994a4996b7dc2"
    },
    {
      "label": "LyraHost_ActivateSubScreen",
      "pc": [
        1317223,
        1317312
      ],
      "sha256": "c2712e6c45d13821aff6a355cfcc30bb92415974dc35405a6dda529434f76120"
    },
    {
      "label": "LyraHost_Palette_InitWhiteFilter_Interupt",
      "pc": [
        28347,
        28378
      ],
      "sha256": "0c5115a0a93be56a412fba4f3613075341c29434b6ce07ad881d964d1bd1b84f"
    },
    {
      "label": "LyraHost_PreOverworld_LoadProperties_Interupt",
      "pc": [
        66542,
        66772
      ],
      "sha256": "845c216a1e3b1f607279b786bfd6eed6a28f96af8e9060503cf0c9dad11b6be9"
    },
    {
      "label": "LyraHost_Credits_LoadScene_Overworld_PrepGFX_Interupt",
      "pc": [
        67122,
        67213
      ],
      "sha256": "41f2538cc2c4eeb1d032c6d604b36adb25044135f9f76755bb9f238e0ba6cd54"
    },
    {
      "label": "LyraHost_EnableSubScreenCheckForPyramid",
      "pc": [
        1317332,
        1317356
      ],
      "sha256": "3c8854da8026abffeaa959b4006cfceb7577369442998a37fb0fb2786af22614"
    },
    {
      "label": "LyraHost_MirrorWarp_LoadSpritesAndColors_Interupt",
      "pc": [
        78737,
        78850
      ],
      "sha256": "c7a6261ec67776427ce5218706808f3805860dd41e20f927f98e9fbf9606838c"
    },
    {
      "label": "LyraHost_ReadOverlayArray",
      "pc": [
        1317356,
        1317369
      ],
      "sha256": "53d4fa5fe28070f7fd81a88a8c5ffe0d82a2058fd00648d7be7d077b1708207f"
    },
    {
      "label": "LyraHost_ReadOverlayArray2",
      "pc": [
        1317388,
        1317404
      ],
      "sha256": "c811e59260401394aea2f1c876513eee5ec4431978bdae580b04a255a9642e8d"
    },
    {
      "label": "LyraHost_Overworld_LoadAreaPalettes",
      "pc": [
        83602,
        83670
      ],
      "sha256": "557215638f35455a1c00f5585059f1b41afa238bdbf166029713ba11079e7d99"
    },
    {
      "label": "LyraHost_BlockGFXCheck",
      "pc": [
        1317531,
        1317752
      ],
      "sha256": "4024295aa2676fb297b9f789e9e17aec0acd09d3916c5f1db99d1d80ff6bbebd"
    },
    {
      "label": "LyraHost_CheckForChangeGraphicsTransitionLoad",
      "pc": [
        1317752,
        1317950
      ],
      "sha256": "e4fb82da196b9edbe490798f4953e76ef7f3364cf445a2e2868585ccf8887486"
    },
    {
      "label": "LyraHost_LoadTransMainGFX",
      "pc": [
        1318047,
        1318203
      ],
      "sha256": "7836eb1516f0d02a84099f0abc94e50a4791cf6038f60292ea5920afb0f5aaec"
    },
    {
      "label": "LyraHost_NewLoadTransAuxGFX",
      "pc": [
        1318426,
        1318673
      ],
      "sha256": "3b084f646d324fcd6a4236bff101514eb0f753cbffb9163065b101e58c83014d"
    },
    {
      "label": "LyraHost_InitTilesetsLongCalls",
      "pc": [
        1318793,
        1319001
      ],
      "sha256": "2b2ca06a099c860de83a4d103576600d6b8cc4909acecc58ddfb9da0b50e58af"
    },
    {
      "label": "LyraHost_AnimateMirrorWarp_DecompressNewTileSetsLongCalls",
      "pc": [
        1319001,
        1319101
      ],
      "sha256": "79c71196d748321277f240a6bebd5a324939a62a78c1031b43cc54f52daf9312"
    },
    {
      "label": "LyraHost_AnimateMirrorWarp_DecompressNewTileSetsLongCalls2",
      "pc": [
        1319101,
        1319164
      ],
      "sha256": "14cd338be04f177f5ed0ea8d6b1f9be23d0a709132d19b58a3f29510c11ed33a"
    },
    {
      "label": "LyraHost_AnimateMirrorWarp_DecompressBackgroundsALongCalls",
      "pc": [
        1319164,
        1319227
      ],
      "sha256": "f5c834a8990cab231daa45e99b6bad43674de5b40877f2b2c93b374fa63a80ed"
    },
    {
      "label": "LyraHost_AnimateMirrorWarp_DecompressBackgroundsCLongCalls",
      "pc": [
        1319227,
        1319293
      ],
      "sha256": "b6d1de7d191ab42024f22aeb96d8d3485b18242b55dd0c16b00a50b79f00060a"
    },
    {
      "label": "LyraHost_OverworldHandleTransitions",
      "pc": [
        76228,
        76550
      ],
      "sha256": "eb94ff3cd6c04e961dd86650616afe10bc75e5ba9f20afb5413c7d6311974651"
    },
    {
      "label": "LyraHost_NewOverworld_SetCameraBounds",
      "pc": [
        1319309,
        1319421
      ],
      "sha256": "b29bd6e2221edcae53f9abcf7efcb685611967d2592e720a522c22857a7e8dd5"
    },
    {
      "label": "LyraHost_Overworld_LoadMapProperties_Interupt",
      "pc": [
        76557,
        76648
      ],
      "sha256": "5b425af73b54f8e0429b0abbc1218e10cae8bbc2d14100df76ad36cb133a6a0f"
    },
    {
      "label": "LyraHost_AreaSizeCheck",
      "pc": [
        1319430,
        1319495
      ],
      "sha256": "8c0421241a21fd57794409da3142b17b2c6dee0571cfaeb87eaca9f422d39c4e"
    },
    {
      "label": "LyraHost_LoadOverworldSprites_Interupt",
      "pc": [
        312519,
        312589
      ],
      "sha256": "ecfa7ce706ee87f42820732a6510580d30d5c4238e17e6a98104509d09322ff4"
    },
    {
      "label": "LyraHost_LoadSpecialOverworld_Interupt",
      "pc": [
        92465,
        92564
      ],
      "sha256": "671c42805707ad1b318ecf30a27fe19bf12bd39140f6ba88bff1e125498d1558"
    },
    {
      "label": "LyraHost_Sprite_LoadGfxProperties_Interupt",
      "pc": [
        1319630,
        1319653
      ],
      "sha256": "ac9731b89b50083becdf2febac0c4b5c0255425a9329fe4e38b352a60ad86153"
    },
    {
      "label": "LyraHost_Link_Read_Interupt",
      "pc": [
        1319653,
        1319663
      ],
      "sha256": "024d80acc2a122ad748cc350a994cda02595d127d57d7ee03103e0ac275e5610"
    },
    {
      "label": "LyraHost_RomToPaletteBuffer",
      "pc": [
        98180,
        98203
      ],
      "sha256": "bd9935bbd3ce651eba358463390ba5a9d13dfdfade93135b6bf8689021508680"
    },
    {
      "label": "LyraHost_LostWoods",
      "pc": [
        1077248,
        1077449
      ],
      "sha256": "9278df345021aa29f763bb8458f66e0784363b3170c287fb4f6814b01b1c1888"
    },
    {
      "label": "LyraHost_Overworld_ReloadSubscreenOverlay_Interupt",
      "pc": [
        77656,
        78028
      ],
      "sha256": "afa107171c1b1223176d74fe6d00c0b62d4e2017538adb463866e82337e7a40c"
    },
    {
      "label": "Lyra_RoutingGate",
      "pc": [
        75227,
        75260
      ],
      "sha256": "8b4136de64f7a61ed8b769ac5e61256a1861f62a4de956a8009d0c1d33621b59"
    },
    {
      "label": "Lyra_RoutingPrefix",
      "pc": [
        75219,
        75227
      ],
      "sha256": "dccab61da3d598cc16d08bdf3b29bea116e3f0c6a222f17e2ca451df7404cfe4"
    },
    {
      "label": "Lyra_LegacyMusicInitializer",
      "pc": [
        83043,
        83132
      ],
      "sha256": "386a0ea6113069a552d0637e5b47b484bfe91e5d878223bdb85908d13faf5bc8"
    }
  ],
  "fixed_native_ingress": [
    {
      "snes": 55509,
      "payload_hex": "da224099283aa8fa"
    },
    {
      "snes": 55907,
      "payload_hex": "226799288b4babbf"
    },
    {
      "snes": 57889,
      "payload_hex": "5c899f28ff000a0a"
    },
    {
      "snes": 55556,
      "payload_hex": "5c59a028ff000a0a"
    },
    {
      "snes": 55677,
      "payload_hex": "5cbda0288508bfee"
    },
    {
      "snes": 55740,
      "payload_hex": "5cfca0288508bff0"
    },
    {
      "snes": 55855,
      "payload_hex": "5c3ba1288508bff2"
    },
    {
      "snes": 180419,
      "payload_hex": "228da1286006187d"
    },
    {
      "snes": 64615,
      "payload_hex": "22cea228eaeaea29"
    },
    {
      "snes": 505112,
      "payload_hex": "22e5a2288df01ce2"
    },
    {
      "snes": 703578,
      "payload_hex": "225c9d28e61564b2"
    },
    {
      "snes": 174856,
      "payload_hex": "a68a9c1204e080b0"
    },
    {
      "snes": 189845,
      "payload_hex": "2008ab22fda128ea"
    },
    {
      "snes": 192199,
      "payload_hex": "204af5a21e00a9c4"
    },
    {
      "snes": 192490,
      "payload_hex": "204af5a21e00a9c4"
    },
    {
      "snes": 195853,
      "payload_hex": "c23020cbf7a90010"
    }
  ]
}''')

# name, SPECS table, original operand, original index, mask, selected index,
# selected load retains X only for the graphics row's variable slot.
SELECTORS = (
    ('Animated', 'animated', 0x2882A0, 'X', 0xFF, 0xA1, False),
    ('MainPalette', 'main_palette', 0x288160, 'X', 0xFF, 0xA1, False),
    ('Overlay', 'overlay', 0x288340, 'X', 0x1FF, 0x142, False),
    ('Size', 'area_size', 0x02F88D, 'X', 0xFF, 0xA1, False),
    ('Parent', 'parent', 0x288998, 'X', 0xFF, 0xA1, False),
    ('TransitionYX', 'transition_y', 0x288F38, 'X', 0x1FF, 0x142, False),
    ('TransitionXX', 'transition_x', 0x289078, 'X', 0x1FF, 0x142, False),
    ('TransitionYY', 'transition_y', 0x288F38, 'Y', 0x1FF, 0x142, False),
    ('TransitionXY', 'transition_x', 0x289078, 'Y', 0x1FF, 0x142, False),
    ('ScrollNorth', 'scroll_north', 0x2891B8, 'Y', 0x1FF, 0x142, False),
    ('ScrollWest', 'scroll_west', 0x2892F8, 'Y', 0x1FF, 0x142, False),
    ('PaletteSet', 'palette_set', 0x09C635, 'X', 0xFF, 0xA1, False),
    ('SpritePalette', 'special_sprite_palettes', 0x7EFD40, 'X', 0xFF, 0xA1, False),
    ('SpecialPalette', 'special_sprite_palettes', 0x02E701, 'X', 0xFF, 0x21, False),
    ('SpecialSpriteGfx', 'special_sprite_gfx', 0x02E6E1, 'X', 0xFF, 0x21, False),
    ('SpriteGfxByArea', 'special_sprite_gfx', 0x02E661, 'X', 0xFF, 0xA1, False),
    ('SpecialEntryGfx', 'special_entry_gfx', 0x02E821, 'X', 0xFF, 0x21, False),
    ('AreaGfx', 'area_gfx', 0x00FC9C, 'X', 0xFF, 0xA1, False),
    ('BombDoor', 'bomb_doors', 0x02A644, 'X', 0x1FF, 0x142, False),
    ('HiddenItems', 'hidden_items', 0x82A784, 'X', 0x1FF, 0x142, False),
    ('Sign', 'sign_text', 0x2897F8, 'Y', 0x1FF, 0x142, False),
) + tuple((f'Gfx{i}', 'gfx', 0x288480 + i, 'X', 0x7F8, 0x508, True) for i in range(8))

POINTER_HOOKS = (
    (0x02F59D, 'Lyra_FullHigh', 0x02F94D),
    (0x02F5C8, 'Lyra_FullLow', 0x02FB2D),
    (0x02F7E3, 'Lyra_SubHigh', 0x02F94D),
    (0x02F80E, 'Lyra_SubLow', 0x02FB2D),
)
FIXED_SIZE_SITES = (0x02AC3C, 0x02AC6C, 0x02B2F3, 0x02B34F,
    0x02ED32, 0x02ED66, 0x02F035, 0x02F2E8, 0x02F31C, 0x02F35A, 0x02F394)


def table_address(name):
    return 0x28C000 + next(s[6] for s in A.SPECS if s[0] == name)


def selected_address(row):
    name, table, old, reg, mask, index, indexed = row
    spec = next(s for s in A.SPECS if s[0] == table)
    if indexed:
        return table_address(table) + int(name[-1])
    return table_address(table) + (0xA1 - spec[3]) * spec[5]


def selector_bytes(row):
    """Exact straight-line two-way helper; no opaque body hash acceptance."""
    _, _, old, reg, mask, index, indexed = row
    selected = bytes([0xBF if indexed else 0xAF]) + selected_address(row).to_bytes(3, 'little')
    legacy = (b'\xbf' + old.to_bytes(3, 'little') if reg == 'X'
              else b'\xb9' + (old & 0xFFFF).to_bytes(2, 'little'))
    return (b'\x08\xc2\x30\x48' + bytes([0x8A if reg == 'X' else 0x98])
            + b'\x29' + mask.to_bytes(2, 'little') + b'\xc9' + index.to_bytes(2, 'little')
            + b'\xd0\x07\x68\x28' + selected + b'\x6b\x68\x28' + legacy + b'\x6b')


def descriptor_fields(raw):
    R.require(type(raw) is bytes and len(raw) == 64 and raw[:4] == b'LYR1', 'Invalid native loader descriptor')
    R.require(raw[4:12] == bytes([1, 0xA1, 0, 0xA1] + [0xA1] * 4)
              and raw[23:32] == bytes([0x30, 0x30, 0, 0, 0, 0x10, 7, 0, 0])
              and raw[32:] == bytes(32), 'Unsupported native loader capability/policy')
    R.require(255 not in raw[12:20] and raw[22] not in (0, 255), 'Unsupported A1 graphics selector')
    return dict(map_id=raw[5], size=raw[6], parent=raw[7], footprint=list(raw[8:12]),
        graphics_sheets=list(raw[12:20]), main_palette=raw[20], palette_set=raw[21], animated=raw[22])


def _labels(symbols):
    text = symbols.decode() if isinstance(symbols, bytes) else symbols
    R.require(type(text) is str, 'Native loader build symbols are required')
    result, active = {}, False
    for line in text.splitlines():
        if line.startswith('['):
            active = line == '[labels]'
        m = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?(Lyra\w+)', line)
        if active and m:
            address = int(m[1] + m[2], 16)
            R.require(m[3] not in result or result[m[3]] == address,
                      'Conflicting native loader bridge symbol')
            result[m[3]] = address
    return result


def _body(compiled, labels, name, expected):
    R.require(name in labels and name + '_End' in labels, f'Missing native helper {name}')
    at, end = A.pc(labels[name]), A.pc(labels[name + '_End'])
    R.require(CODE_START <= at < end <= CODE_END and end - at == len(expected)
              and compiled[at:end] == expected, f'Native helper body differs: {name}')
    return dict(label=name, pc=[at, end], sha256=R.sha(expected))


def _pointer_body(table, original):
    # M16/X16; P restored before each original-equivalent pointer read.
    selected = table_address(table) + 0xA1 * 3
    pair = lambda op, addr: (bytes([op]) + addr.to_bytes(3, 'little') + b'\x85\xc8'
        + bytes([op]) + (addr + 1).to_bytes(3, 'little') + b'\x85\xc9\x6b')
    return (b'\x08\xa5\x8a\x29\xff\x00\xc9\xa1\x00\xd0\x0e\x28'
        + pair(0xAF, selected) + b'\x28' + pair(0xBF, original))


def _publication(ledger_path):
    claim, digest = R.reservation_claim(ledger_path)
    expected = dict(kind=KIND, enabled=True, scope='isolated_candidate_only',
        production_admission=False, selected_maps=[0x37, 0xA1], source_map_count=160,
        table_capacity=192, save_destination='unchanged', code_pc=[CODE_START, CODE_END],
        descriptor_pc=[DESCRIPTOR_PC, DESCRIPTOR_PC + 64],
        source_reader_variant='original_native160', compiled_reader_variant=KIND)
    R.require(claim.get('ordinary_build_publication') == expected,
              'No explicit ordinary private native-loader publication authority')
    return claim, digest


def _music_ownership(ledger_path):
    ledger = json.loads(Path(ledger_path or R.LEDGER).read_bytes())
    claims = list(ledger.get('claims', []))
    reservation = [c for c in claims if c.get('id') == 'music_cache_reservation']
    future = [c for c in claims if c.get('id') == 'music_cache_192']
    R.require(len(reservation) == len(future) == 1
              and reservation[0].get('space') == future[0].get('space') == 'wram'
              and reservation[0].get('base') == future[0].get('base') == 0x7EC900
              and reservation[0].get('size') == future[0].get('size') == 192
              and reservation[0].get('container') is True
              and future[0].get('contained_by') == 'music_cache_reservation',
              'Missing physical192-byte music reservation')
    claims += [dict(id=t.get('id'), space=t.get('space'), base=t.get('address'),
                    size=t.get('count', 0) * t.get('stride', 0)) for t in ledger.get('tables', [])]
    for c in claims:
        if c.get('id') in ('music_cache_reservation', 'music_cache', 'music_cache_192'):
            continue
        if c.get('space') not in ('wram', 'save_buffer', 'snes_ram'):
            continue
        at, size = c.get('base'), c.get('size')
        if at is None:
            R.require(c.get('status') == 'proposed', 'Unresolved active RAM owner')
            continue  # An unplaced proposal is not a physical byte claim.
        R.require(type(at) is int, 'Invalid physical RAM owner')
        if at < 0x10000:
            at += 0x7E0000
        if at >> 16 < 0x40 and at & 0xFFFF < 0x2000:
            at = 0x7E0000 | (at & 0xFFFF)
        if size is None:
            R.require(at > 0x7EC9A1, 'Unresolved RAM extent can overlap A1 music byte')
            continue
        R.require(type(size) is int and size > 0, 'Invalid physical RAM owner')
        R.require(not at <= 0x7EC9A1 < at + size, f"A1 music byte conflicts with {c.get('id')}")


def sprite_pointer_bytes():
    prefix = bytes.fromhex('0848ad0a0429ff00c9a100d01fc00400f00cc00600f00e')
    def load(name):
        return b'\x68\x28\xaf' + (table_address(name) + 0x142).to_bytes(3, 'little') + b'\x6b'
    return prefix + b''.join(load(name) for name in ('sprite_phase0', 'sprite_phase1', 'sprite_phase2')) + bytes.fromhex('6828bf3894286b')


def music_tail_bytes():
    return b'\xaf' + (table_address('music_dark_special') + 0x61).to_bytes(3, 'little') + bytes.fromhex('8fa1c97ee210ab6b')


def backdrop_bytes():
    return (bytes.fromhex('08a58a29ff00c9a100d00628af')
            + (table_address('bg_color') + 0x142).to_bytes(3, 'little')
            + bytes.fromhex('6b28a58a29ff005caf8334'))


FIXED_SPRITE_PALETTE_SITES = (0x02B0F5, 0x02B38B, 0x02B4C7, 0x02EAA5, 0x02ECE2)
FIXED_SOURCE_CALLS = dict(LyraCall_PaletteSet_5=0x0286DB, LyraCall_PaletteSet_6=0x02B0FB,
    LyraCall_PaletteSet_7=0x02B4CD, LyraCall_PaletteSet_8=0x02EAAB,
    LyraCall_PaletteSet_9=0x02ECE8, LyraCall_BombDoor_0=0x02EF64)
BACKDROP_CONTINUATION = bytes.fromhex('c9a000b01dc98000d011a5a0c98101d005af4981286ba58a29ff000aaabf0080286ba900006b')
OVERLAY_RESTORE = bytes.fromhex('af13c27e858aaf15c27e8584af17c27e8588af19c27e8586af1bc27e8d1804af1dc27e8d1004af1fc27e8d1604')


def _verify_dependencies(saved, compiled, labels):
    bodies = [_body(compiled, labels, 'Lyra_SpritePointer', sprite_pointer_bytes()),
              _body(compiled, labels, 'Lyra_InitMusicTail', music_tail_bytes()),
              _body(compiled, labels, 'Lyra_ReadBackdrop', backdrop_bytes())]
    def hook(site, target, *, opcode=0x22, padding=0):
        at = A.pc(site)
        expected = bytes([opcode]) + labels[target].to_bytes(3, 'little') + b'\xea' * padding
        R.require(compiled[at:at + len(expected)] == expected, f'Compiled dependency hook differs: {site:06X}')
    for site in FIXED_SIZE_SITES:
        hook(site, 'Lyra_ReadSize')
    for site in FIXED_SPRITE_PALETTE_SITES:
        hook(site, 'Lyra_ReadSpritePalette')
    hook(0x1BC8B8, 'Lyra_ReadHiddenItems')
    hook(0x02C4BC, 'Lyra_InitMusicTail', opcode=0x5C)
    hook(0x3483AA, 'Lyra_ReadBackdrop', opcode=0x5C, padding=1)
    R.require(compiled[0x1A03AF:0x1A03D5] == BACKDROP_CONTINUATION,
              'Backdrop legacy continuation differs')
    calls = []
    for label, target in SOURCE_CALLS:
        R.require(label in labels, f'Missing source selector call: {label}')
        if label in FIXED_SOURCE_CALLS:
            R.require(labels[label] == FIXED_SOURCE_CALLS[label], 'Fixed selector call label moved')
        hook(labels[label], target)
        calls.append(dict(label=label, pc=A.pc(labels[label]), target=target))
    # The declared guard must skip both legacy return-trigger and edge-routing.
    R.require('Lyra_RoutingGate' in labels and 'Lyra_RoutingReturn' in labels, 'Missing isolated A1 routing gate')
    at, destination = A.pc(labels['Lyra_RoutingGate']), A.pc(labels['Lyra_RoutingReturn'])
    delta = destination - at - 6
    R.require(0 <= delta < 128 and compiled[at:at + 6] == bytes.fromhex('a58ac9a1f0') + bytes([delta])
              and compiled[destination:destination + 3] == bytes.fromhex('e22060'),
              'A1 routing gate/legacy fallthrough differs')
    R.require(compiled[0x1658B:0x16595] == bytes.fromhex('a9f8ff85ece2308b4bab')
              and labels.get('Lyra_Fixture_PreProfile') == 0x02E58B,
              'Ordinary pre-profile ingress differs')
    at = A.pc(labels.get('Lyra_Fixture_PreOverlaySelect', 0))
    R.require(compiled[at:at + 5] == bytes.fromhex('e0ff00d003'), 'Pre-overlay FF guard differs')
    restored = A.pc(labels.get('Lyra_Fixture_OverlayRestored', 0))
    R.require(compiled[restored - len(OVERLAY_RESTORE):restored] == OVERLAY_RESTORE
              and compiled[restored:restored + 3] == bytes.fromhex('e22060'),
              'Ordinary overlay field/scroll restoration differs')
    return dict(helper_bodies=bodies, source_calls=calls, routing_gate_pc=A.pc(labels['Lyra_RoutingGate']),
                held_destination_policy=True)


FIXED_NATIVE_INGRESS = (0x00D8D5, 0x00DA63, 0x00E221, 0x00D904, 0x00D97D,
    0x00D9BC, 0x00DA2F, 0x02C0C3, 0x00FC67, 0x07B518, 0x0ABC5A,
    0x02AB08, 0x02E595, 0x02EEC7, 0x02EFEA, 0x02FD0D)


SOURCE_FAMILY = ('Oracle_main.asm', 'Overworld/lyra_native_loaders.asm',
    'Overworld/ZSCustomOverworld.asm', 'Overworld/time_system.asm', 'Overworld/lost_woods.asm')


def inspect_unverified_native_loaders(compiled, symbols):
    """Candidate locations for independent review; never a verification result."""
    labels = _labels(symbols)
    required = {label for label, _ in SOURCE_CALLS}
    required.update('LyraHost_' + host + suffix for host in SOURCE_HOSTS for suffix in ('', '_End'))
    required.update(('Lyra_RoutingGate', 'Lyra_RoutingReturn'))
    missing = sorted(required - labels.keys())
    R.require(not missing, 'Missing mandatory native loader inspection symbols: ' + ', '.join(missing))
    root = Path(__file__).resolve().parents[2]
    calls = [dict(label=label, pc=A.pc(labels[label]), target=target) for label, target in SOURCE_CALLS]
    spans = []
    for host in SOURCE_HOSTS:
        label = 'LyraHost_' + host
        at, end = A.pc(labels[label]), A.pc(labels[label + '_End'])
        R.require(0 <= at < end <= len(compiled), 'Invalid candidate consumer span')
        spans.append(dict(label=label, pc=[at, end], sha256=R.sha(compiled[at:end])))
    # Include containment and no-overlay paths, not only selector opcodes.
    gate, end = A.pc(labels['Lyra_RoutingGate']), A.pc(labels['Lyra_RoutingReturn']) + 3
    spans.append(dict(label='Lyra_RoutingGate', pc=[gate, end], sha256=R.sha(compiled[gate:end])))
    # These inputs establish the routing and music helpers' inherited ABI.
    # They sit outside the selector hosts and must have their own source pins.
    for label, at, end in (
        ('Lyra_RoutingPrefix', A.pc(0x02A5D3), gate),
        ('Lyra_LegacyMusicInitializer', A.pc(0x02C463), A.pc(0x02C4BC)),
    ):
        R.require(0 <= at < end <= len(compiled), 'Invalid native producer/ingress span')
        spans.append(dict(label=label, pc=[at, end], sha256=R.sha(compiled[at:end])))
    return dict(qualified=False, kind=KIND, source_sha256={p: R.sha((root / p).read_bytes()) for p in SOURCE_FAMILY},
                source_calls=calls, consumer_spans=spans, fixed_native_ingress=[
                    dict(snes=a, payload_hex=compiled[A.pc(a):A.pc(a) + 8].hex()) for a in FIXED_NATIVE_INGRESS])


def _verify_reviewed_binding(compiled, symbols):
    R.require(REVIEWED_COMPILED_BINDING is not None,
              'Native consumer family awaits independent first-assembly review/pins')
    actual = inspect_unverified_native_loaders(compiled, symbols)
    R.require(actual == REVIEWED_COMPILED_BINDING,
              'Reviewed active native consumer family differs; no automatic rebind')


def verify_native_loaders(saved, compiled, symbols, descriptor, *, ledger_path=None):
    """Bind saved-source readers and actual compiled readers without rebinding115."""
    R.require(type(saved) is bytes and type(compiled) is bytes
              and len(saved) == len(compiled) == 0x400000, 'Native loader variant requires4MiB ROMs')
    claim, ledger_hash = _publication(ledger_path)
    R.derive_allocation(saved, ledger_path=ledger_path)
    _music_ownership(ledger_path)
    old = T32.ownership(saved, claim)
    R.require(compiled[0x17691:0x177CB] == saved[0x17691:0x177CB], 'Native decoder changed')
    fields, labels = descriptor_fields(descriptor), _labels(symbols)
    R.require(labels.get('Lyra_A1Descriptor') == 0xF8DFC0
              and compiled[DESCRIPTOR_PC:DESCRIPTOR_PC + 64] == descriptor, 'Actual native descriptor differs')
    bodies, hooks = [], []
    for row in SELECTORS:
        bodies.append(_body(compiled, labels, 'Lyra_Read' + row[0], selector_bytes(row)))
    for site, name, original in POINTER_HOOKS:
        table = 'map32_high' if 'High' in name else 'map32_low'
        bodies.append(_body(compiled, labels, name, _pointer_body(table, original)))
        at = A.pc(site)
        expected = b'\x22' + labels[name].to_bytes(3, 'little') + b'\xea' * 8
        R.require(compiled[at:at + 12] == expected, f'Native pointer hook differs: {site:06X}')
        hooks.append(dict(snes=site, target=name, payload_hex=expected.hex()))
    # Additional compiled selector ingress/dependency checks are defined below.
    dependencies = _verify_dependencies(saved, compiled, labels)
    all_bodies = bodies + dependencies['helper_bodies']
    cursor = CODE_START
    for row in all_bodies:
        R.require(row['pc'][0] == cursor, 'Native helper code is not the reviewed contiguous layout')
        cursor = row['pc'][1]
    R.require(A.pc(labels.get('Lyra_NativeCodeStart', 0)) == CODE_START
              and A.pc(labels.get('Lyra_NativeCodeEnd', 0)) == cursor, 'Native code scope differs')
    for name, offset, raw in (
        ('gfx', 0xA1 * 8, descriptor[12:20]), ('main_palette', 0xA1, descriptor[20:21]),
        ('palette_set', 0xA1, descriptor[21:22]), ('animated', 0xA1, descriptor[22:23]),
        ('special_entry_gfx', 0x21, descriptor[23:24]), ('area_gfx', 0xA1, descriptor[24:25]),
        ('special_sprite_gfx', 0x21, descriptor[25:26]), ('special_sprite_palettes', 0x21, descriptor[26:27]),
        ('music_dark_special', 0x61, descriptor[27:28]), ('area_size', 0xA1, b'\0'),
        ('parent', 0xA1, b'\xa1')):
        at = A.pc(table_address(name)) + offset
        R.require(compiled[at:at + len(raw)] == raw, f'Actual A1 descriptor/table mismatch: {name}')
    for name in ('sprite_phase0', 'sprite_phase1', 'sprite_phase2'):
        at = A.pc(table_address(name)) + 0x142
        R.require(compiled[at:at + 2] == b'\x81\xc8', 'A1 actors are not empty')
    _verify_reviewed_binding(compiled, symbols)
    return dict(kind=KIND, source_rom_sha256=R.sha(saved), compiled_rom_sha256=R.sha(compiled),
        source_consumer_receipt=old, ledger_sha256=ledger_hash, descriptor=fields,
        helper_bodies=bodies, pointer_hooks=hooks, dependencies=dependencies,
        production_admission=False, compiled_consumers_verified=True, runtime_verified=False, save_exit_policy='held')


SOURCE_CALLS = (('LyraCall_Animated_0', 'Lyra_ReadAnimated'), ('LyraCall_Overlay_0', 'Lyra_ReadOverlay'), ('LyraCall_Overlay_1', 'Lyra_ReadOverlay'), ('LyraCall_SpritePalette_0', 'Lyra_ReadSpritePalette'), ('LyraCall_PaletteSet_0', 'Lyra_ReadPaletteSet'), ('LyraCall_PaletteSet_1', 'Lyra_ReadPaletteSet'), ('LyraCall_Overlay_2', 'Lyra_ReadOverlay'), ('LyraCall_PaletteSet_2', 'Lyra_ReadPaletteSet'), ('LyraCall_Overlay_3', 'Lyra_ReadOverlay'), ('LyraCall_Overlay_4', 'Lyra_ReadOverlay'), ('LyraCall_MainPalette_0', 'Lyra_ReadMainPalette'), ('LyraCall_Gfx0_0', 'Lyra_ReadGfx0'), ('LyraCall_MainPalette_1', 'Lyra_ReadMainPalette'), ('LyraCall_MainPalette_2', 'Lyra_ReadMainPalette'), ('LyraCall_Overlay_5', 'Lyra_ReadOverlay'), ('LyraCall_Gfx0_1', 'Lyra_ReadGfx0'), ('LyraCall_Gfx1_0', 'Lyra_ReadGfx1'), ('LyraCall_Gfx2_0', 'Lyra_ReadGfx2'), ('LyraCall_Gfx7_0', 'Lyra_ReadGfx7'), ('LyraCall_Gfx3_0', 'Lyra_ReadGfx3'), ('LyraCall_Gfx4_0', 'Lyra_ReadGfx4'), ('LyraCall_Gfx5_0', 'Lyra_ReadGfx5'), ('LyraCall_Gfx6_0', 'Lyra_ReadGfx6'), ('LyraCall_Gfx0_2', 'Lyra_ReadGfx0'), ('LyraCall_Gfx1_1', 'Lyra_ReadGfx1'), ('LyraCall_Gfx2_1', 'Lyra_ReadGfx2'), ('LyraCall_Gfx3_1', 'Lyra_ReadGfx3'), ('LyraCall_Gfx4_1', 'Lyra_ReadGfx4'), ('LyraCall_Gfx5_1', 'Lyra_ReadGfx5'), ('LyraCall_Gfx6_1', 'Lyra_ReadGfx6'), ('LyraCall_Gfx7_1', 'Lyra_ReadGfx7'), ('LyraCall_Gfx3_2', 'Lyra_ReadGfx3'), ('LyraCall_Gfx4_2', 'Lyra_ReadGfx4'), ('LyraCall_Gfx5_2', 'Lyra_ReadGfx5'), ('LyraCall_Gfx6_2', 'Lyra_ReadGfx6'), ('LyraCall_Gfx1_2', 'Lyra_ReadGfx1'), ('LyraCall_Gfx0_3', 'Lyra_ReadGfx0'), ('LyraCall_Gfx3_3', 'Lyra_ReadGfx3'), ('LyraCall_Gfx2_2', 'Lyra_ReadGfx2'), ('LyraCall_Gfx7_2', 'Lyra_ReadGfx7'), ('LyraCall_Gfx6_3', 'Lyra_ReadGfx6'), ('LyraCall_SpritePalette_1', 'Lyra_ReadSpritePalette'), ('LyraCall_PaletteSet_3', 'Lyra_ReadPaletteSet'), ('LyraCall_Size_0', 'Lyra_ReadSize'), ('LyraCall_TransitionYY_0', 'Lyra_ReadTransitionYY'), ('LyraCall_TransitionXY_0', 'Lyra_ReadTransitionXY'), ('LyraCall_ScrollNorth_0', 'Lyra_ReadScrollNorth'), ('LyraCall_ScrollWest_0', 'Lyra_ReadScrollWest'), ('LyraCall_SpriteGfxByArea_0', 'Lyra_ReadSpriteGfxByArea'), ('LyraCall_AreaGfx_0', 'Lyra_ReadAreaGfx'), ('LyraCall_Size_1', 'Lyra_ReadSize'), ('LyraCall_TransitionYX_0', 'Lyra_ReadTransitionYX'), ('LyraCall_TransitionXX_0', 'Lyra_ReadTransitionXX'), ('LyraCall_Size_2', 'Lyra_ReadSize'), ('LyraCall_Size_3', 'Lyra_ReadSize'), ('LyraCall_SpecialSpriteGfx_0', 'Lyra_ReadSpecialSpriteGfx'), ('LyraCall_SpecialEntryGfx_0', 'Lyra_ReadSpecialEntryGfx'), ('LyraCall_SpecialPalette_0', 'Lyra_ReadSpecialPalette'), ('LyraCall_PaletteSet_4', 'Lyra_ReadPaletteSet'), ('LyraCall_TransitionYX_1', 'Lyra_ReadTransitionYX'), ('LyraCall_TransitionXX_1', 'Lyra_ReadTransitionXX'), ('LyraCall_PaletteSet_5', 'Lyra_ReadPaletteSet'), ('LyraCall_PaletteSet_6', 'Lyra_ReadPaletteSet'), ('LyraCall_PaletteSet_7', 'Lyra_ReadPaletteSet'), ('LyraCall_PaletteSet_8', 'Lyra_ReadPaletteSet'), ('LyraCall_PaletteSet_9', 'Lyra_ReadPaletteSet'), ('LyraCall_SpecialPalette_1', 'Lyra_ReadSpecialPalette'), ('LyraCall_BombDoor_0', 'Lyra_ReadBombDoor'), ('LyraCall_Sign_0', 'Lyra_ReadSign'), ('LyraCall_SpritePointer', 'Lyra_SpritePointer'), ('LyraCall_SpritePalette_2', 'Lyra_ReadSpritePalette'), ('LyraCall_PaletteSet_10', 'Lyra_ReadPaletteSet'), ('LyraCall_Parent_0', 'Lyra_ReadParent'), ('LyraCall_Parent_1', 'Lyra_ReadParent'))

SOURCE_HOSTS = {'ReadAnimatedTable': ['LyraCall_Animated_0'], 'ActivateSubScreen': ['LyraCall_Overlay_0'], 'Palette_InitWhiteFilter_Interupt': ['LyraCall_Overlay_1'], 'PreOverworld_LoadProperties_Interupt': ['LyraCall_SpritePalette_0', 'LyraCall_PaletteSet_0'], 'Credits_LoadScene_Overworld_PrepGFX_Interupt': ['LyraCall_PaletteSet_1'], 'EnableSubScreenCheckForPyramid': ['LyraCall_Overlay_2'], 'MirrorWarp_LoadSpritesAndColors_Interupt': ['LyraCall_PaletteSet_2'], 'ReadOverlayArray': ['LyraCall_Overlay_3'], 'ReadOverlayArray2': ['LyraCall_Overlay_4'], 'Overworld_LoadAreaPalettes': ['LyraCall_MainPalette_0'], 'BlockGFXCheck': ['LyraCall_Gfx0_0'], 'CheckForChangeGraphicsTransitionLoad': ['LyraCall_MainPalette_1', 'LyraCall_MainPalette_2', 'LyraCall_Overlay_5'], 'LoadTransMainGFX': ['LyraCall_Gfx0_1', 'LyraCall_Gfx1_0', 'LyraCall_Gfx2_0', 'LyraCall_Gfx7_0'], 'NewLoadTransAuxGFX': ['LyraCall_Gfx3_0', 'LyraCall_Gfx4_0', 'LyraCall_Gfx5_0', 'LyraCall_Gfx6_0'], 'InitTilesetsLongCalls': ['LyraCall_Gfx0_2', 'LyraCall_Gfx1_1', 'LyraCall_Gfx2_1', 'LyraCall_Gfx3_1', 'LyraCall_Gfx4_1', 'LyraCall_Gfx5_1', 'LyraCall_Gfx6_1', 'LyraCall_Gfx7_1'], 'AnimateMirrorWarp_DecompressNewTileSetsLongCalls': ['LyraCall_Gfx3_2', 'LyraCall_Gfx4_2', 'LyraCall_Gfx5_2', 'LyraCall_Gfx6_2'], 'AnimateMirrorWarp_DecompressNewTileSetsLongCalls2': ['LyraCall_Gfx1_2', 'LyraCall_Gfx0_3'], 'AnimateMirrorWarp_DecompressBackgroundsALongCalls': ['LyraCall_Gfx3_3', 'LyraCall_Gfx2_2'], 'AnimateMirrorWarp_DecompressBackgroundsCLongCalls': ['LyraCall_Gfx7_2', 'LyraCall_Gfx6_3'], 'OverworldHandleTransitions': ['LyraCall_SpritePalette_1', 'LyraCall_PaletteSet_3'], 'NewOverworld_SetCameraBounds': ['LyraCall_Size_0', 'LyraCall_TransitionYY_0', 'LyraCall_TransitionXY_0', 'LyraCall_ScrollNorth_0', 'LyraCall_ScrollWest_0'], 'Overworld_LoadMapProperties_Interupt': ['LyraCall_SpriteGfxByArea_0', 'LyraCall_AreaGfx_0', 'LyraCall_Size_1'], 'AreaSizeCheck': ['LyraCall_TransitionYX_0', 'LyraCall_TransitionXX_0', 'LyraCall_Size_2'], 'LoadOverworldSprites_Interupt': ['LyraCall_Size_3', 'LyraCall_SpritePointer'], 'LoadSpecialOverworld_Interupt': ['LyraCall_SpecialSpriteGfx_0', 'LyraCall_SpecialEntryGfx_0', 'LyraCall_SpecialPalette_0', 'LyraCall_PaletteSet_4', 'LyraCall_TransitionYX_1', 'LyraCall_TransitionXX_1'], 'Sprite_LoadGfxProperties_Interupt': ['LyraCall_SpecialPalette_1'], 'Link_Read_Interupt': ['LyraCall_Sign_0'], 'RomToPaletteBuffer': ['LyraCall_SpritePalette_2', 'LyraCall_PaletteSet_10'], 'LostWoods': ['LyraCall_Parent_0', 'LyraCall_Parent_1']}

SOURCE_HOSTS["Overworld_ReloadSubscreenOverlay_Interupt"] = []

# Current-engine mode is a separate, ungranted source plan. None of the
# historical constructor, byte bodies, source pins or ledger paths above change.
CURRENT_FIRST, CURRENT_END, CURRENT_PARENT_COUNT = 0xA0, 0xC0, 0xC0
CURRENT_KIND = 'lyra.current_native_readers_source_plan.v1'
# name, original ROM operand, original rows, original first area, row stride.
# Special-world tables acquire structural zero prefixes, never active defaults:
# native areas always use their original readers; every tail row is explicit.
CURRENT_TABLE_SPECS = tuple((s[0], s[1], s[2], s[3], s[5]) for s in A.SPECS) + tuple(
    (f'music_phase{i}', 0x02C303 + i * 0x40, 0x40, 0, 1) for i in range(4))
CURRENT_SELECTORS = SELECTORS + (
    ('Mosaic', 'mosaic', 0x288200, 'X', 0xFF, 0xA1, False),
) + tuple((f'ByScreen{i + 1}', f'ByScreen{i + 1}', 0x288A38 + i * 0x140,
           'X', 0x1FF, 0x142, False) for i in range(4))


def current_table_layout(table_base):
    """Return complete192-row families at an explicitly supplied LoROM origin."""
    R.require(type(table_base) is int, 'Current table origin must be an integer')
    start, cursor, rows = A.pc(table_base), 0, []
    for name, old, legacy, first, stride in CURRENT_TABLE_SPECS:
        rows.append(dict(name=name, legacy_snes=old, legacy_rows=legacy,
                         legacy_first=first, stride=stride, rows=CURRENT_PARENT_COUNT,
                         offset=cursor, snes=table_base + cursor,
                         pc=[start + cursor, start + cursor + CURRENT_PARENT_COUNT * stride]))
        cursor += CURRENT_PARENT_COUNT * stride
    R.require((table_base & 0xFFFF) + cursor <= 0x10000,
              'Current tables cross a LoROM bank')
    return rows


def current_selector_location(name, index, *, table_base):
    """Host arithmetic contract for an original reader index; no CPU execution.

    The source caller owns index width/normalization. Out-of-domain indices,
    including high garbage, retain the exact original operand and index.
    """
    R.require(type(index) is int and 0 <= index <= 0xFFFF, 'Invalid current reader index')
    row = next((r for r in CURRENT_SELECTORS if r[0] == name), None)
    R.require(row is not None, 'Unknown current selector')
    _, family, old, reg, _, _, _ = row
    layout = next(r for r in current_table_layout(table_base) if r['name'] == family)
    special = name in ('SpecialPalette', 'SpecialSpriteGfx', 'SpecialEntryGfx')
    scale = 8 if family == 'gfx' else layout['stride']
    bias = 0x80 if special else 0
    first, end = (CURRENT_FIRST - bias) * scale, (CURRENT_END - bias) * scale
    selected = first <= index < end
    slot = int(name[-1]) if family == 'gfx' else 0
    target = (layout['snes'] + index + bias * scale + slot if selected else
              old + index if reg == 'X' else 0x280000 + (old & 0xFFFF) + index)
    return dict(selected=selected, address=target, family=family,
                first_index=first, end_index=end, source_register=reg)


def current_pointer_location(index, *, table_base, plane):
    """Triplet indices belong to each actual full/sub-load quadrant, not8A."""
    R.require(plane in ('high', 'low') and type(index) is int and 0 <= index <= 0xFFFF,
              'Invalid current pointer index')
    selected = CURRENT_FIRST * 3 <= index < CURRENT_END * 3
    family = 'map32_' + plane
    row = next(r for r in current_table_layout(table_base) if r['name'] == family)
    original = 0x02F94D if plane == 'high' else 0x02FB2D
    return dict(selected=selected, address=(row['snes'] if selected else original) + index)


def _current_origins(origins):
    keys = {'table_base', 'code_base', 'code_end', 'descriptor_base'}
    R.require(type(origins) is dict and set(origins) == keys
              and all(type(v) is int for v in origins.values()), 'Explicit current origins required')
    for name in ('table_base', 'code_base', 'descriptor_base'):
        at = A.pc(origins[name])
        R.require(at < 0x400000, 'Current origin exceeds4MiB LoROM')
    code, end = origins['code_base'], origins['code_end']
    R.require(code < end and code >> 16 == (end - 1) >> 16
              and (code & 0xFFFF) >= 0x8000 and A.pc(end - 1) < 0x400000,
              'Current code range must occupy one mapped LoROM bank')
    layout = current_table_layout(origins['table_base'])
    desc = A.pc(origins['descriptor_base'])
    R.require((origins['descriptor_base'] & 0xFFFF) + 64 <= 0x10000,
              'Current descriptor crosses a LoROM bank')
    spans = [(layout[0]['pc'][0], layout[-1]['pc'][1]),
             (A.pc(code), A.pc(end - 1) + 1), (desc, desc + 64)]
    R.require(all(b <= c or a >= d for i, (a, b) in enumerate(spans)
                  for c, d in spans[i + 1:]), 'Current origin ranges overlap')
    return layout


def plan_current_tables(source, tail_rows, *, origins, policy):
    """Emit source text/data plans, never a ROM or publication authority.

    The current-transfer binder owns source-profile/grant authenticity. This
    pure producer requires its exact source identity and refuses authority flags;
    it deliberately does not consult the historical reservation constructor.
    Tail rows are already-lowered values, including explicit actor and endpoint
    pointers. No metadata is translated to an empty list or invented default.
    """
    R.require(type(source) is bytes and len(source) in (0x200000, 0x400000),
              'Current tables require exact2MiB or4MiB saved bytes')
    R.require(type(policy) is dict and policy.get('source_rom_sha256') == R.sha(source)
              and type(policy.get('source_profile_sha256')) is str
              and re.fullmatch(r'[0-9a-f]{64}', policy['source_profile_sha256']) is not None,
              'Current source/profile binding differs')
    R.require(policy.get('allocation_granted') is False
              and policy.get('publication_authorized') is False,
              'Current source plan cannot accept publication authority')
    R.require(all(policy.get(flag, False) is False for flag in
                  ('producer_enforcement_verified', 'ordinary_build_ready',
                   'runtime_admission', 'activation')),
              'Current source plan cannot accept readiness or activation')
    layout = _current_origins(origins)
    names = {r['name'] for r in layout}
    R.require(type(tail_rows) is dict and all(type(k) is int for k in tail_rows)
              and set(tail_rows) == set(range(CURRENT_FIRST, CURRENT_END)),
              'Current mode requires exactly all32 explicit tail maps')
    for area, values in tail_rows.items():
        R.require(type(values) is dict and set(values) == names,
                  f'Current map{area:02X} requires every explicit table family')
    tables = []
    for row in layout:
        name, stride = row['name'], row['stride']
        payload = bytearray(CURRENT_PARENT_COUNT * stride)
        original = A.pc(row['legacy_snes'])
        native = source[original:original + row['legacy_rows'] * stride]
        R.require(len(native) == row['legacy_rows'] * stride, 'Truncated current native table')
        begin = row['legacy_first'] * stride
        payload[begin:begin + len(native)] = native
        if name.startswith('music_phase'):
            # Native DW/SW source is shared across the four LW phase families.
            other = A.pc(0x02C403)
            payload[0x40:CURRENT_FIRST] = source[other:other + 0x60]
        for area in range(CURRENT_FIRST, CURRENT_END):
            value = tail_rows[area][name]
            if stride == 8:
                R.require(type(value) in (bytes, list, tuple) and len(value) == stride
                          and all(type(v) is int and 0 <= v <= 255 for v in value),
                          f'Invalid current graphics row{area:02X}')
                raw = bytes(value)
            else:
                R.require(type(value) is int and 0 <= value < 1 << (8 * stride),
                          f'Invalid current {name} row{area:02X}')
                if name == 'parent':
                    R.require(value < CURRENT_PARENT_COUNT, 'Current parent exceeds192 rows')
                if name == 'area_size':
                    R.require(value <= 3, 'Invalid current area size')
                if name.startswith('map32_'):
                    R.require(A.pc(value) < 0x400000, 'Current terrain pointer exceeds4MiB')
                raw = value.to_bytes(stride, 'little')
            payload[area * stride:(area + 1) * stride] = raw
        R.require(payload[begin:begin + len(native)] == native, 'Current native prefix changed')
        tables.append(dict(row, payload_hex=payload.hex(), payload_sha256=R.sha(payload),
                           native_payload_sha256=R.sha(native),
                           structural_unmapped_prefix_rows=row['legacy_first']))
    lines = ['; UNGRANTED current-engine source plan. No ROM publication.',
             'assert !LYRA_CURRENT_MODE == 1',
             '!LYRA_CURRENT_FIRST = $00A0', '!LYRA_CURRENT_END = $00C0',
             '!LYRA_CURRENT_PARENT_COUNT = $00C0']
    for key, constant in (('table_base', 'TABLE_BASE'), ('code_base', 'CODE_BASE'),
                          ('code_end', 'CODE_END'), ('descriptor_base', 'DESCRIPTOR_BASE')):
        lines.append(f'!LYRA_CURRENT_{constant} = ${origins[key]:06X}')
    constant_lines = list(lines)
    lines = ['pushpc', 'org !LYRA_CURRENT_TABLE_BASE']
    for row in tables:
        constant_lines.append(f"!LYRA_CURRENT_TABLE_{row['name']} = ${row['snes']:06X}")
        lines.append(f"Lyra_CurrentTable_{row['name']}:")
        raw = bytes.fromhex(row['payload_hex'])
        lines += ['db ' + ','.join(f'${v:02X}' for v in raw[i:i + 16])
                  for i in range(0, len(raw), 16)]
    lines += ['pullpc']
    descriptor = (b'LYC1' + bytes([1, CURRENT_FIRST, CURRENT_END, CURRENT_PARENT_COUNT])
                  + bytes.fromhex(R.sha(source)) + bytes.fromhex(policy['source_profile_sha256'])[:16]
                  + bytes(8))
    descriptor_lines = ['pushpc', 'org !LYRA_CURRENT_DESCRIPTOR_BASE', 'Lyra_CurrentDescriptor:']
    descriptor_lines += ['db ' + ','.join(f'${v:02X}' for v in descriptor[i:i + 16])
                         for i in range(0, len(descriptor), 16)]
    descriptor_lines += ['pullpc']
    return dict(kind=CURRENT_KIND, source_rom_sha256=R.sha(source),
                source_profile_sha256=policy['source_profile_sha256'], origins=dict(origins),
                source_domain=dict(first_map=CURRENT_FIRST, end_map=CURRENT_END,
                                   native_parent_count=160, parent_count=CURRENT_PARENT_COUNT),
                tables=tables, tables_bytes=sum(len(bytes.fromhex(r['payload_hex'])) for r in tables),
                assembler='\n'.join(constant_lines + lines + descriptor_lines) + '\n',
                constants_assembler='\n'.join(constant_lines) + '\n',
                tables_assembler='\n'.join(lines) + '\n',
                descriptor_assembler='\n'.join(descriptor_lines) + '\n',
                tables_pc=[tables[0]['pc'][0], tables[-1]['pc'][1]],
                tables_snes=[origins['table_base'],
                             origins['table_base'] + sum(r['rows'] * r['stride'] for r in tables)],
                code_pc=[A.pc(origins['code_base']), A.pc(origins['code_end'] - 1) + 1],
                descriptor_pc=[A.pc(origins['descriptor_base']), A.pc(origins['descriptor_base']) + 64],
                descriptor_hex=descriptor.hex(),
                allocation_granted=False, producer_enforcement_verified=False,
                publication_authorized=False, ordinary_build_ready=False, runtime_admission=False,
                current_code_fit_verified=False,
                actors_compiled=False, rom_written=False,
                remaining_consumers=['current source call-site composition', 'BG128 lifecycle',
                    'actor/door/exit admission', 'entry/save/return/world-map/mirror/flight'])


def current_property_rows(document):
    """Lower saved native selectors without assigning storage or readiness.

    SW graphics/palette selectors are one byte per area in maintained ZScream;
    distinct per-phase values cannot be represented by those readers. The
    established -1 sentinel lowers to0, as in the historical empty-actor path.
    Four music phases retain all four saved values in the current cache tail.
    """
    from lyra_project_terrain import TerrainDocument
    R.require(isinstance(document, TerrainDocument)
              and type(document.maps) is tuple and type(document.properties) is tuple
              and len(document.maps) == len(document.properties) == 32,
              'CURRENT_PROPERTY_MODEL_INVALID: all32 parsed maps required')
    result = {}
    for area, prop in enumerate(document.properties, CURRENT_FIRST):
        R.require(type(prop) is dict, 'CURRENT_PROPERTY_MODEL_INVALID: properties required')
        arrays = (('graphics_sheets', 8, 0), ('sprite_graphics', 3, -1),
                  ('sprite_palettes', 3, -1), ('music', 4, 0))
        for key, count, minimum in arrays:
            values = prop.get(key)
            R.require(type(values) is list and len(values) == count
                      and all(type(value) is int and minimum <= value <= 255 for value in values),
                      'CURRENT_PROPERTY_MODEL_INVALID: ' + key)
        for key, maximum in (('main_palette', 255), ('palette_set', 255),
                             ('animated_sheet', 255), ('message_id', 65535)):
            R.require(type(prop.get(key)) is int and 0 <= prop[key] <= maximum,
                      'CURRENT_PROPERTY_MODEL_INVALID: ' + key)
        for key in ('sprite_graphics', 'sprite_palettes'):
            R.require(len(set(prop[key])) == 1,
                      'CURRENT_PROPERTY_PHASE_SELECTOR_UNSUPPORTED: special-world ' + key)
        result[area] = dict(gfx=list(prop['graphics_sheets']), main_palette=prop['main_palette'],
            palette_set=prop['palette_set'], animated=prop['animated_sheet'], sign_text=prop['message_id'],
            special_sprite_gfx=max(0, prop['sprite_graphics'][0]),
            special_sprite_palettes=max(0, prop['sprite_palettes'][0]),
            music_dark_special=prop['music'][0],
            **{f'music_phase{phase}': value for phase, value in enumerate(prop['music'])})
    return result


def plan_current_actor_streams(source, document, *, current_source_profile):
    """Lower bound authored sprites to headerless OW lists; never place them.

    Native OW records are Y, X, sprite ID followed by a single FF terminator.
    The saved Lyra model has map-local Tile16 coordinates and three explicit
    states; it represents no extra native X/Y flag bits. Placement IDs and
    original ordinals remain provenance, never native sprite bytes. Authored
    area members aggregate in row-major order with 32-tile quadrant offsets;
    every member selects the same parent list. Storage and the bank-$09 pointer
    assignments remain unbound.
    """
    import lyra_current_transfer as current
    from lyra_project_terrain import TerrainDocument

    R.require(type(source) is bytes and len(source) in (0x200000, 0x400000),
              'CURRENT_ACTOR_MODEL_INVALID: exact saved2MiB or4MiB source required')
    R.require(isinstance(document, TerrainDocument)
              and type(document.authoring) is tuple and len(document.authoring) == 32
              and len(document.maps) == len(document.properties) == 32,
              'CURRENT_ACTOR_MODEL_INVALID: all32 ordered authored maps required')
    authored, seen = [], set()
    for area, auth in enumerate(document.authoring, CURRENT_FIRST):
        R.require(type(auth) is dict and set(auth) ==
                  {'properties', 'sprites', 'doors', 'exits', 'asset_bindings'}
                  and type(auth['sprites']) is list and len(auth['sprites']) <= 128,
                  'CURRENT_ACTOR_MODEL_INVALID: ordered sprite lists require at most128 placements per map')
        phases = [[], [], []]
        for ordinal, sprite in enumerate(auth['sprites']):
            R.require(type(sprite) is dict and set(sprite) == {'id', 'x', 'y', 'sprite_id', 'state'}
                      and all(type(sprite[key]) is int for key in sprite)
                      and 1 <= sprite['id'] <= 0xFFFFFFFF and sprite['id'] not in seen
                      and 0 <= sprite['x'] <= 31 and 0 <= sprite['y'] <= 31
                      and 0 <= sprite['sprite_id'] <= 255 and 0 <= sprite['state'] <= 2,
                      'CURRENT_ACTOR_MODEL_INVALID: invalid sprite identity, coordinate, state or byte ID')
            seen.add(sprite['id'])
            phases[sprite['state']].append((ordinal, sprite['id'],
                sprite['y'], sprite['x'], sprite['sprite_id']))
        authored.append((area, phases))

    profile = current.verify_current_native_source_profile(current_source_profile, source, document)
    area_plan = A.gameplay_area_plan(document)
    parents = {row['map_id']: row['parent_map_id'] for row in area_plan['assignments']}
    groups = {row['parent_map_id']: row['maps'] for row in area_plan['areas']}
    by_map = dict(authored)
    streams = []
    for area, phases in authored:
        parent = parents.get(area, area)
        members = groups.get(parent, [area])
        # The native loader bases its actor coordinate origin on the parent.
        # Serialize each physical page once; repeated render quadrants never
        # duplicate actors in wide/tall/small areas.
        if area in parents:
            phases = [[], [], []]
            for member in members:
                dy, dx = divmod(member - parent, 8)
                for state, placements in enumerate(by_map[member]):
                    phases[state].extend((ordinal, identity, y + dy * 32, x + dx * 32, sprite_id)
                        for ordinal, identity, y, x, sprite_id in placements)
            R.require(sum(map(len, phases)) <= 128,
                      'CURRENT_ACTOR_MODEL_INVALID: gameplay area exceeds128 placements')
        for state, placements in enumerate(phases):
            payload = bytes(value for row in placements for value in row[2:]) + b'\xFF'
            row = dict(map_id=area, state=state, payload_hex=payload.hex(),
                sha256=R.sha(payload), bytes=len(payload),
                placement_ids=[row[1] for row in placements],
                placement_ordinals=[row[0] for row in placements])
            if area in parents:
                row.update(parent_map_id=parent, source_maps=list(members),
                    placement_maps=[member for member in members for _ in by_map[member][state]])
            streams.append(row)
    result = dict(kind='lyra.current_actor_streams_source_plan.v1',
        source_rom_sha256=R.sha(source), source_size=len(source),
        source_profile_sha256=current.T.digest(profile),
        source_contract_binding=dict(profile['contract']), document_sha256=profile['document_sha256'],
        generation=profile['review']['generation'], operation_id=profile['review']['operation_id'],
        reservation_review_id=profile['reservation_review_id'],
        source_domain=dict(first_map=CURRENT_FIRST, end_map=CURRENT_END,
                           native_parent_count=160, parent_count=CURRENT_PARENT_COUNT),
        streams=streams, demand=dict(maps=32, phases=3, lists=96, placements=len(seen),
            payload_bytes=sum(row['bytes'] for row in streams), pointer_rows=96, pointer_bytes=192),
        storage=None, pointers=None,
        consumer_blockers=A.consumer_blockers(document, tuple(range(CURRENT_FIRST, CURRENT_END)), ()),
        allocation_granted=False, producer_enforcement_verified=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, actors_compiled=False, rom_written=False)
    current.verify_current_native_source_profile(profile, source, document)
    return result


def plan_current_actor_storage(source, document, *, current_source_profile, data_snes, capacity, preimage):
    """Place deduplicated actor lists inside one explicit source-profile bank.

    Native pointer rows stay u16. The current long-pointer parser supplies this
    single data bank; no native bank09 bytes or WRAM staging are allocated.
    This is a source plan, with every readiness/authority flag still false.
    """
    actors = plan_current_actor_streams(source, document, current_source_profile=current_source_profile)
    profile = current_source_profile
    origin = profile['origins'].get('actors')
    R.require(type(origin) is dict, 'CURRENT_ACTOR_STORAGE_UNBOUND: explicit actors origin required')
    R.require(type(data_snes) is int and type(capacity) is int and capacity > 0
              and [A.pc(data_snes), A.pc(data_snes)+capacity] == origin['pc']
              and [data_snes, data_snes+capacity] == origin['snes']
              and data_snes & 0xFFFF >= 0x8000
              and (data_snes & 0xFFFF)+capacity <= 0x10000,
              'CURRENT_ACTOR_STORAGE_ORIGIN_MISMATCH: one complete mapped source-profile interval required')
    expanded = A.expanded_rom(source)
    R.require(type(preimage) is bytes and len(preimage) == capacity
              and preimage == expanded[slice(*origin['pc'])],
              'CURRENT_ACTOR_STORAGE_PREIMAGE_MISMATCH: exact full saved-source interval required')
    payload, offsets, pointers = bytearray(), {}, []
    phase_rows = {area: {} for area in range(CURRENT_FIRST,CURRENT_END)}
    for row in actors['streams']:
        raw = bytes.fromhex(row['payload_hex'])
        R.require(raw and raw[-1] == 255 and len(raw) % 3 == 1,
                  'CURRENT_ACTOR_STORAGE_STREAM_INVALID: headerless terminated triples required')
        if raw not in offsets:
            offsets[raw] = len(payload)
            payload.extend(raw)
        offset = offsets[raw]
        pointer = data_snes+offset
        phase_rows[row['map_id']][f"sprite_phase{row['state']}"] = pointer & 0xFFFF
        pointers.append(dict(map_id=row['map_id'], state=row['state'], offset=offset,
                             snes=pointer, pointer_word=pointer & 0xFFFF, stream_sha256=row['sha256']))
    R.require(len(payload) <= capacity, 'CURRENT_ACTOR_STORAGE_CAPACITY: deduplicated lists exceed explicit interval')
    result = dict(kind='lyra.current_actor_storage_source_plan.v1', actor_stream_plan=actors,
        source_rom_sha256=actors['source_rom_sha256'], source_profile_sha256=actors['source_profile_sha256'],
        document_sha256=actors['document_sha256'], source_contract_binding=actors['source_contract_binding'],
        generation=actors['generation'], operation_id=actors['operation_id'],
        reservation_review_id=actors['reservation_review_id'], origin=copy.deepcopy(origin),
        data_snes=data_snes, bank=data_snes >> 16, capacity=capacity,
        preimage_sha256=R.sha(preimage), payload_hex=bytes(payload).hex(), payload_bytes=len(payload),
        payload_sha256=R.sha(payload), unique_lists=len(offsets), pointers=pointers, phase_rows=phase_rows,
        allocation_granted=False, producer_enforcement_verified=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, actors_compiled=False, rom_written=False)
    import lyra_current_transfer as current
    current.verify_current_native_source_profile(profile, source, document)
    return result


def emit_current_actor_data(plan):
    """Format a previously reconstructed source plan; no selection or writes."""
    R.require(type(plan) is dict and plan.get('kind') == 'lyra.current_actor_storage_source_plan.v1'
              and all(plan.get(flag) is False for flag in ('allocation_granted','publication_authorized',
                  'producer_enforcement_verified','ordinary_build_ready','runtime_admission','rom_written')),
              'CURRENT_ACTOR_STORAGE_PLAN_REQUIRED: ungranted source plan required')
    payload = bytes.fromhex(plan['payload_hex'])
    R.require(len(payload) == plan['payload_bytes'] <= plan['capacity']
              and R.sha(payload) == plan['payload_sha256'], 'Current actor payload differs')
    lines = ['; Ungranted source-profile actor data; no activation.', 'pushpc',
             f"org ${plan['data_snes']:06X}", 'Lyra_CurrentActorData:']
    lines += ['  db '+', '.join(f'${v:02X}' for v in payload[i:i+16]) for i in range(0,len(payload),16)]
    lines += [f"assert pc() <= ${plan['data_snes']+plan['capacity']:06X}", 'pullpc']
    return '\n'.join(lines)+'\n'
