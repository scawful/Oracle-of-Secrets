#!/usr/bin/env python3
"""Track 6 source contracts for the Minish latch and the enemy fixes.

The compiled OAM bytes for the octorok split are executed by
Tests/test_custom_sprite_death_audit.py (same draw entry). This file locks
the control-flow contracts those bytes do not show: the 16x16 portal hold,
the mixed $65 block, the volcano return-only pads, the probe chase signal,
and the thunder-bolt wall test.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class MinishAndEnemyFixContracts(unittest.TestCase):
    def test_minish_portal_holds_for_the_whole_16x16(self) -> None:
        masks = _text("Masks/mask_routines.asm")
        hold = masks.split("MinishPortal_StillOnPortal:", 1)[1].split("MinishPortal_Tick:", 1)[0]
        self.assertIn("CMP.w #$0064", hold)
        self.assertIn("MinishPortal_ReadQuadrant", hold)
        maintain = masks.split("MinishPortal_Maintain:", 1)[1].split("Minish_GetTileType", 1)[0]
        self.assertIn("JSR MinishPortal_StillOnPortal", maintain)
        self.assertLess(
            maintain.index("JSR MinishPortal_StillOnPortal"),
            maintain.index("INC.w MinishPortalTimer"),
        )

    def test_mixed_minish_tile_blocks_every_form(self) -> None:
        form = _text("Masks/minish_form.asm")
        checker = form.split("LinkState_CheckMinishTile:", 1)[1].split("CheckForMinishLift:", 1)[0]
        self.assertIn("JSL MinishTile_AllQuadrants", checker)
        self.assertLess(checker.index("BCC .blocked"), checker.index("TSB $0343"))
        masks = _text("Masks/mask_routines.asm")
        scan = masks.split("MinishTile_AllQuadrants:", 1)[1].split("MinishPortal_StillOnPortal:", 1)[0]
        self.assertIn("AND.w #$FFF0", scan)
        self.assertIn("AND.w #$FFFE", scan)
        self.assertIn("JSR MinishPortal_ReadQuadrant", scan)
        self.assertNotIn("MinishTile_ReadQuadrant:", masks)
        self.assertIn("CMP.w #$0065", scan)
        self.assertIn("JSL MinishPortal_GetTileType", masks)

    def test_volcano_pads_are_return_only(self) -> None:
        src = _text("Overworld/lupo_pad_gate.asm")
        body = src.split("LupoPadGate_Check:", 1)[1].split("  .check_lupo\n", 1)[0]
        self.assertIn("CMP.b #$03 : BEQ .refuse", body)
        self.assertIn("CMP.b #$07 : BEQ .refuse", body)
        self.assertLess(body.index("CMP.b #$07"), body.index("BRA .warp"))

    def test_pedestal_comment_matches_fortress_compare(self) -> None:
        src = _text("Sprites/Objects/pedestal.asm")
        self.assertIn("Map 4B", src.split("PedestalPlaque:", 1)[0])
        self.assertNotIn("Map 5E", src)
        self.assertIn("CMP.b #$4B", src)

    def test_octoboss_medallion_uses_the_sprite_placement(self) -> None:
        src = _text("Sprites/Bosses/octoboss.asm")
        alt = src.split("SpawnMedallionAlt:", 1)[1]
        self.assertIn("JSL $09AE64", alt)
        self.assertNotIn("LDA.b #$DC", alt)
        self.assertNotIn("LDA.b #$F7", alt)

    def test_octorok_draw_split_and_live_allocation(self) -> None:
        src = _text("Sprites/Enemies/octorok.asm")
        draw = src.split("Sprite_Octorok_Draw:", 1)[1].split("Sprite_Octorok_DrawKalyxo:", 1)[0]
        self.assertIn("JSR Sprite_Octorok_DrawKalyxo", draw)
        self.assertIn("JSR Sprite_Octorok_DrawAbyss", draw)
        self.assertIn("JSL Sprite_PrepOamCoord : BCC .on_screen", draw)
        self.assertIn("PHA", draw)
        self.assertIn("ORA.b #$02", draw)
        abyss = src.split("Sprite_Octorok_DrawAbyss:", 1)[1].split("Sprite_Octorok_DrawTiles:", 1)[0]
        self.assertIn("STA.b $0B", abyss)
        tiles = src.split("Sprite_Octorok_DrawTiles:", 1)[1]
        self.assertIn("LDA.b $0B : BEQ .keep_priority", tiles)

    def test_booki_and_darknut_keep_raycaster_probe(self) -> None:
        booki = _text("Sprites/Enemies/booki.asm")
        self.assertIn("JSL Probe_CheckTileSolidity", booki)
        self.assertNotIn("Sprite_SpawnProbeAlways_long", booki)

        dark = _text("Sprites/Enemies/darknut.asm")
        self.assertIn("JSL Probe_CheckTileSolidity", dark)
        self.assertNotIn("Sprite_SpawnProbeAlways_long", dark)

    def test_thunder_bolt_ignores_non_wall_tiles_during_grace(self) -> None:
        src = _text("Sprites/Enemies/thunder_ghost.asm")
        fly = src.split("ThunderBolt_Fly:", 1)[1].split("ThunderBolt_HitWall:", 1)[0]
        self.assertIn("LDA.w SprTimerC, X : BNE .alive", fly)
        self.assertNotIn("Sprite_CheckTileCollision", fly)
        wall = src.split("ThunderBolt_HitWall:", 1)[1].split("Sprite_ThunderGhost_Move:", 1)[0]
        self.assertIn("JSL Probe_CheckTileSolidity", wall)
        self.assertIn("CMP.b #$09", wall)
        spawn = src.split("SpawnLightningAttack:", 1)[1].split("Sprite_ThunderGhost_Draw:", 1)[0]
        self.assertIn("LDA.b #$0C : STA.w SprTimerC, Y", spawn)
        draw = src.split("Sprite_ThunderGhost_Draw:", 1)[1]
        self.assertIn("dw -12, -8, -16", draw)
        self.assertIn("dw 12, 16, 20", draw)


if __name__ == "__main__":
    unittest.main()
