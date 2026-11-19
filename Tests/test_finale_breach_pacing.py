"""Compiled 65816 & live-ROM tests for Wave 2B Lane B:
  1. DW $4D Sanctum Pit Gate (LoadOverworldPitAreas + Overworld_ResolvePitDestination)
  2. LW $0B <-> DW $4B World-Split Breach Portal (LupoPadGate_Check, FinaleBreach_IsUnlocked,
     FinaleBreach_TrySpotWarp, A4 AbyssVortex_CaptureOrigin, and read-only live-ROM safe
     walkability verification of ($07C0, $0400))
  3. Post-Kydreeok Song of Healing Rest Beat & Volatile Finale Continue Point
     (Kydreeok_PostHealRestBeat, FinaleContinue_LoadCheckpointOrWorld, Beast_Dead clear)
  4. Farore's Safe-Center Glow Ring during Ganon Beast Phase 2/3 malice phases
     (Beast_DrawSafeRing OAM bounds, Phase 1/Enter/Dead off, Phase 2/3 corners & pulse)
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

from test_finale_ganon_credits import (  # noqa: E402
    Compiled65816Harness,
    ROM_PATH,
    SYM_PATH,
    load_symbols,
)

LIVE_PROJ_ROM = Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom")
SPARKLE_CHRS = {0x83, 0xC7, 0x80, 0xB7}


class FinaleBreachHarness(Compiled65816Harness):
    """Extends Compiled65816Harness with Region B OAM, Overworld/Load stubs, and stop PCs."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int], default_db: int = 0x34):
        super().__init__(lib, rom, labels, default_db=default_db)
        self.region_b_cursor = 0x0900
        self.region_b_hi_cursor = 0x0A40
        self.region_b_allocs: list[int] = []
        self.pit_dest_stub_ent = 0x7B

        for name in (
            "OAM_AllocateFromRegionB",
            "Overworld_GetPitDestination",
            "Boat_ResetSession",
            "ItemBindings_AdapterReset",
            "ItemBindings_RestoreY",
            "Lyra_TailEvent_MigrateSave",
        ):
            addr = self.addr(name)
            if addr is not None:
                self.stubs[addr] = name

    def handle_stub(self, name: str) -> None:
        a_lo = self.cpu.a & 0xFF
        if name == "OAM_AllocateFromRegionB":
            self.calls.append((name, a_lo))
            self.region_b_allocs.append(a_lo)
            self.put16(0x90, self.region_b_cursor)
            self.put16(0x92, self.region_b_hi_cursor)
            return
        if name == "Overworld_GetPitDestination":
            self.calls.append((name, a_lo))
            self.put(0x010E, self.pit_dest_stub_ent)
            self.put(0x7EF3CA, 0x00 if self.pit_dest_stub_ent == 0x82 else 0x40)
            return
        if name in (
            "Boat_ResetSession",
            "ItemBindings_AdapterReset",
            "ItemBindings_RestoreY",
            "Lyra_TailEvent_MigrateSave",
        ):
            self.calls.append((name, a_lo))
            return
        super().handle_stub(name)

    def call_until(
        self,
        name: str,
        stop_addrs: set[int],
        *,
        x: int = 0,
        y: int = 0,
        a: int = 0,
        long_return: bool = True,
        db: int | None = None,
        limit: int = 50000,
    ) -> int:
        """Run routine until it returns normally (returns sentinel) or reaches a stop PC."""
        addr = self.addr(name)
        assert addr is not None, f"Missing symbol {name}"
        cpu = self.cpu
        cpu.x = x & 0xFF
        cpu.y = y & 0xFF
        cpu.a = (cpu.a & 0xFF00) | (a & 0xFF)
        cpu.mf = True
        cpu.xf = True
        cpu.k = addr >> 16
        cpu.pc = addr & 0xFFFF
        if db is not None:
            cpu.db = db
        sp0 = cpu.sp
        sentinel = (addr & 0xFF0000) | 0x7000
        if long_return:
            self.put(sp0, addr >> 16)
            self.put(sp0 - 1, 0x6F)
            self.put(sp0 - 2, 0xFF)
            cpu.sp -= 3
        else:
            self.put(sp0, 0x6F)
            self.put(sp0 - 1, 0xFF)
            cpu.sp -= 2

        for _ in range(limit):
            cur = (cpu.k << 16) | cpu.pc
            if cur == sentinel:
                assert not self.bad_writes, f"{name} unexpected non-WRAM writes: {self.bad_writes}"
                assert cpu.sp == sp0, f"{name} stack imbalance: {cpu.sp:#x} != {sp0:#x}"
                return cur
            if cur in stop_addrs:
                assert not self.bad_writes, f"{name} unexpected non-WRAM writes: {self.bad_writes}"
                return cur
            if cur in self.stubs:
                self.handle_stub(self.stubs[cur])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} exceeded instruction limit at {cpu.k:02X}:{cpu.pc:04X}")


class LiveRomBreachCoordsTest(unittest.TestCase):
    """Read-only ROM verification of shared unobstructed ($07C0, $0400) courtyard tile."""

    def test_shared_breach_spot_is_unobstructed_3x3_on_lw_0b_and_dw_4b(self) -> None:
        rom_file = LIVE_PROJ_ROM if LIVE_PROJ_ROM.is_file() else ROM_PATH
        if not rom_file.is_file():
            self.skipTest("Neither live project ROM nor built worktree ROM is present")
        import check_tile16_pins as ctp
        import scene_intent_common as sic

        rom = rom_file.read_bytes()
        _, native_tables = ctp._native_table_addresses(rom)
        map32 = ctp.decode_map32_table(rom)
        tile16 = sic.decode_tile16_table(rom)
        ow_tt = list(rom[sic.PC_TILETYPE:sic.PC_TILETYPE + 0x200])

        for area in (0x0B, 0x4B):
            parent = sic.area_parent_id(rom, area)
            size = rom[0x1788D + parent]
            self.assertEqual(parent, area, f"Area ${area:02X} must be its own parent")
            self.assertEqual(size, 1, f"Area ${area:02X} must be 2x2 large area")

            nw = ctp.decode_map16_grid(rom, parent, map32, native_tables)
            ne = ctp.decode_map16_grid(rom, parent + 1, map32, native_tables)
            sw = ctp.decode_map16_grid(rom, parent + 8, map32, native_tables)
            se = ctp.decode_map16_grid(rom, parent + 9, map32, native_tables)
            grid = [nw[r] + ne[r] for r in range(32)] + [sw[r] + se[r] for r in range(32)]

            # Center (r=32, c=28) = ($07C0, $0400) + entire 3x3 buffer must be pure $00 floor!
            for r in range(31, 34):
                for c in range(27, 30):
                    tid = grid[r][c]
                    tts = [ow_tt[w & 0x1FF] for w in tile16[tid]]
                    self.assertEqual(
                        tts,
                        [0, 0, 0, 0],
                        f"Area ${area:02X} tile (r={r}, c={c}) tid=${tid:03X} has non-walkable tiletypes {tts}",
                    )


class CompiledFinaleBreachAndPacingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (ROM_PATH.is_file() and SYM_PATH.is_file()):
            raise unittest.SkipTest("Compiled ROM/symbols not present in worktree Roms/")
        cls.lib = Compiled65816Harness.get_lib()
        if cls.lib is None:
            raise unittest.SkipTest("Lakesnes 65816 core not available")
        cls.rom = ROM_PATH.read_bytes()
        cls.labels = load_symbols(SYM_PATH)

    def make_harness(self, default_db: int = 0x34) -> FinaleBreachHarness:
        return FinaleBreachHarness(self.lib, self.rom, self.labels, default_db=default_db)

    # ---- 1. DW $4D Sanctum Pit Gate ----
    def test_sanctum_pit_gate_blocks_early_and_allows_after_fortress_clear(self) -> None:
        h = self.make_harness(0x07)
        try:
            # Early DW $4D (OOSPROG == 0): Carry Set (pit bounce-back) + SFX2.$3C buzz!
            h.put(0x8A, 0x4D)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7E012E, 0x00)
            h.call("LoadOverworldPitAreas", long_return=True, db=0x07)
            self.assertTrue(h.cpu.c, "DW $4D pit must bounce back (Carry Set) before Fortress is cleared")
            self.assertEqual(h.get(0x7E012E), 0x3C, "Refused DW $4D pit must play SFX2.$3C error buzz")

            # After Dark Link sets OOSPROG bit 7 (!Story_FortressComplete = $80): Carry Clear (allow!)
            h.put(0x8A, 0x4D)
            h.put(0x7EF3D6, 0x80)
            h.put(0x7E012E, 0x00)
            h.call("LoadOverworldPitAreas", long_return=True, db=0x07)
            self.assertFalse(h.cpu.c, "DW $4D pit must allow drop (Carry Clear) once Fortress is cleared")
            self.assertEqual(h.get(0x7E012E), 0x00, "Allowed DW $4D pit must not play error buzz")

            # Other valid pit areas ($0F, $11, $23) stay unconditionally open
            for area in (0x0F, 0x11, 0x23):
                h.put(0x8A, area)
                h.put(0x7EF3D6, 0x00)
                h.put(0x7E012E, 0x00)
                h.call("LoadOverworldPitAreas", long_return=True, db=0x07)
                self.assertFalse(h.cpu.c, f"Area ${area:02X} pit must remain allowed")
                self.assertEqual(h.get(0x7E012E), 0x00)

            # Ordinary non-pit area ($00) falls in pit without SFX2.$3C buzz
            h.put(0x8A, 0x00)
            h.put(0x7E012E, 0x00)
            h.call("LoadOverworldPitAreas", long_return=True, db=0x07)
            self.assertTrue(h.cpu.c)
            self.assertEqual(h.get(0x7E012E), 0x00)

            # Overworld_ResolvePitDestination still hardens $82 -> $7B on DW $4D
            h.put(0x8A, 0x4D)
            h.pit_dest_stub_ent = 0x82
            h.call("Overworld_ResolvePitDestination", long_return=True, db=0x07)
            self.assertEqual(h.get(0x010E), 0x7B, "DW $4D $82 fallback must harden to Entrance $7B")
            self.assertEqual(h.get(0x7EF3CA), 0x40, "DW $4D $82 fallback must restore Dark World $40")
        finally:
            h.close()

    # ---- 2. LW $0B <-> DW $4B Breach Portal & Lupo Pad Gate ----
    def test_lupo_pad_gate_and_breach_unlock_conditions(self) -> None:
        h = self.make_harness(0x07)
        try:
            # FinaleBreach_IsUnlocked: locked when all 3 flags clear
            h.put(0x7EF3D4, 0x00)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7EF280 + 0x4B, 0x00)
            h.call("FinaleBreach_IsUnlocked", long_return=True, db=0x07)
            self.assertFalse(h.cpu.c)

            # Each unlock path opens the breach
            for addr, bit in ((0x7EF3D4, 0x02), (0x7EF3D6, 0x80), (0x7EF280 + 0x4B, 0x20)):
                h.put(0x7EF3D4, 0x00)
                h.put(0x7EF3D6, 0x00)
                h.put(0x7EF280 + 0x4B, 0x00)
                h.put(addr, bit)
                h.call("FinaleBreach_IsUnlocked", long_return=True, db=0x07)
                self.assertTrue(h.cpu.c, f"Expected unlock when {addr:#x} |= {bit:#x}")

            # LupoPadGate_Check: LW $02 requires D5 crystal ($04)
            h.put(0x02DB, 0x00)
            h.put(0x8A, 0x02)
            h.put(0x7EF37A, 0x00)
            h.put(0x7E012E, 0x00)
            stop = h.call_until("LupoPadGate_Check", {0x07D159}, long_return=True, db=0x07)
            self.assertEqual(stop, 0x07D159, "LW $02 without D5 crystal must refuse")
            self.assertEqual(h.get(0x02DB), 0x01)
            self.assertEqual(h.get(0x7E012E), 0x3C)

            h.put(0x02DB, 0x00)
            h.put(0x7EF37A, 0x04)
            h.put(0x7E012E, 0x00)
            stop = h.call_until("LupoPadGate_Check", {0x07D159}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D159, "LW $02 with D5 crystal must allow warp")

            # LupoPadGate_Check: LW $0B physical pad locked -> buzz + latch + refuse
            h.put(0x02DB, 0x00)
            h.put(0x8A, 0x0B)
            h.put(0x7EF3D4, 0x00)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7EF280 + 0x4B, 0x00)
            h.put(0x7E012E, 0x00)
            stop = h.call_until("LupoPadGate_Check", {0x07D159}, long_return=True, db=0x07)
            self.assertEqual(stop, 0x07D159, "Locked LW $0B pad must refuse")
            self.assertEqual(h.get(0x02DB), 0x01)
            self.assertEqual(h.get(0x7E012E), 0x3C)

            # LW $0B physical pad unlocked (Maku Seed) -> allow
            h.put(0x02DB, 0x00)
            h.put(0x7EF3D4, 0x02)
            h.put(0x7E012E, 0x00)
            stop = h.call_until("LupoPadGate_Check", {0x07D159}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D159, "Unlocked LW $0B pad must allow warp")

            # DW $4B physical pad ALWAYS allowed back to LW $0B even with all flags clear
            h.put(0x02DB, 0x00)
            h.put(0x8A, 0x4B)
            h.put(0x7EF3D4, 0x00)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7EF280 + 0x4B, 0x00)
            stop = h.call_until("LupoPadGate_Check", {0x07D159}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D159, "DW $4B -> LW $0B must always be allowed")
        finally:
            h.close()

    def test_breach_spot_warp_and_a4_vortex_integration(self) -> None:
        h = self.make_harness(0x07)
        try:
            # Setup clean outdoor overworld gameplay state at ($07C0, $0400)
            def setup_spot(area: int, x: int = 0x07C0, y: int = 0x0400) -> None:
                h.put(0x1B, 0x00)      # outdoors
                h.put(0x10, 0x09)      # overworld module
                h.put(0x11, 0x00)      # normal submode
                h.put(0x4D, 0x00)      # not jumping/recoiling
                h.put(0x031F, 0x00)    # no post-warp invuln
                h.put(0x02DB, 0x00)    # NOWARP clear
                h.put(0x0357, 0x05)    # sentinel tile flags to verify A return
                h.put(0x8A, area)
                h.put16(0x22, x)
                h.put16(0x20, y)

            # 1. Locked LW $0B at ($07C0, $0400): silent normal walk (no warp, no buzz)
            h.put(0x7EF3D4, 0x00)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7EF280 + 0x4B, 0x00)
            h.put(0x7E012E, 0x00)
            setup_spot(0x0B)
            stop = h.call_until("FinaleBreach_TrySpotWarp", {0x07D156}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D156, "Locked LW $0B spot must not warp")
            self.assertEqual(h.cpu.a & 0xFF, 0x05, "Must preserve displaced LDA.w $0357 in A")
            self.assertEqual(h.get(0x7E012E), 0x00, "Unpainted locked castle road must not buzz")

            # 2. Unlocked LW $0B at ($07C0, $0400): jumps cleanly to $07D156 (JSR Mirror_TryToWarp)
            h.put(0x7EF3D4, 0x02)
            setup_spot(0x0B)
            sp_before = h.cpu.sp
            stop = h.call_until("FinaleBreach_TrySpotWarp", {0x07D156}, long_return=True, db=0x07)
            self.assertEqual(stop, 0x07D156, "Unlocked LW $0B breach spot must jump to $07D156")
            self.assertEqual(h.cpu.sp, sp_before, "JSL return must be cleanly popped before JML $07D156")

            # 3. DW $4B at ($07C0, $0400) with all flags clear: ALWAYS warps back to LW $0B
            h.put(0x7EF3D4, 0x00)
            h.put(0x7EF3D6, 0x00)
            h.put(0x7EF280 + 0x4B, 0x00)
            setup_spot(0x4B)
            stop = h.call_until("FinaleBreach_TrySpotWarp", {0x07D156}, long_return=True, db=0x07)
            self.assertEqual(stop, 0x07D156, "DW $4B breach spot must always trigger warp to LW $0B")

            # 4. Post-warp cooldown ($031F = $90 on arrival): latches NOWARP=1, prevents ping-pong
            setup_spot(0x4B)
            h.put(0x031F, 0x90)
            stop = h.call_until("FinaleBreach_TrySpotWarp", {0x07D156}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D156)
            self.assertEqual(h.get(0x02DB), 0x01, "Arrival cooldown must latch NOWARP=1 against ping-pong")
            self.assertEqual(h.cpu.a & 0xFF, 0x05)

            # 5. Stepping off the spot clears NOWARP=0
            setup_spot(0x4B, x=0x07E0, y=0x0400)
            h.put(0x02DB, 0x01)
            stop = h.call_until("FinaleBreach_TrySpotWarp", {0x07D156}, long_return=True, db=0x07)
            self.assertNotEqual(stop, 0x07D156)
            self.assertEqual(h.get(0x02DB), 0x00, "Stepping off breach spot must clear NOWARP")

            # 6. Full Mirror_TryToWarp ($07A95C) + A4 AbyssVortex_CaptureOrigin on LW $0B -> DW $4B
            setup_spot(0x0B)
            h.put(0x7EC138, 0x00)  # SpecialOverworld_VortexWorld
            h.cpu.k = 0x07
            h.cpu.pc = 0xA95C
            h.cpu.db = 0x07
            h.cpu.mf = True
            h.cpu.xf = True
            sp0 = h.cpu.sp
            h.put(sp0, 0x6F)
            h.put(sp0 - 1, 0xFF)
            h.cpu.sp -= 2
            for _ in range(5000):
                if ((h.cpu.k << 16) | h.cpu.pc) == 0x077000:
                    break
                h.lib.cpu_runOpcode(h.p)
            self.assertEqual((h.cpu.k << 16) | h.cpu.pc, 0x077000)
            self.assertEqual(h.get(0x11), 0x23, "Mirror_TryToWarp must enter Submodule $23 (MirrorWarp)")
            self.assertEqual(h.get(0x02DB), 0x01, "Mirror_TryToWarp must latch NOWARP=1")
            self.assertEqual(h.get(0x5D), 0x14, "Mirror_TryToWarp must set LINKSTATE $14")
            self.assertEqual(h.get(0x7EC138), 0x40, "LW $0B -> DW $4B must arm A4 VortexWorld=$40 for $6C return")
            self.assertEqual(h.get(0x7E1ABF) | (h.get(0x7E1ACF) << 8), 0x07C0)
            self.assertEqual(h.get(0x7E1ADF) | (h.get(0x7E1AEF) << 8), 0x0400)
        finally:
            h.close()

    # ---- 3. Post-Kydreeok Rest Beat & Finale Continue Point ----
    def test_post_kydreeok_rest_beat_refills_spawns_fairies_and_arms_checkpoint(self) -> None:
        h = self.make_harness(0x32)
        try:
            h.ram[0x0DD0:0x0DE0] = b"\x00" * 16
            h.ram[0x0DD0 + 2] = 0x09  # Kydreeok in slot 2
            h.put(0x7EF36C, 0xA0)     # MaxHealth = 20 hearts
            h.put(0x7EF36D, 0x18)     # CurrentHealth = 3 hearts (wounded!)
            h.put(0x7EF36E, 0x10)     # MagicPower low
            h.put(0x7E012E, 0x00)     # SFX2
            h.put(0x7EC139, 0x00)     # FinaleContinueCheckpoint
            h.put16(0x22, 0x0178)     # Link X in Room $0002
            h.put16(0x20, 0x0090)     # Link Y in Room $0002
            h.put(0xEE, 0x00)         # Link floor layer

            h.call("Kydreeok_PostHealRestBeat", x=2, db=0x32)

            self.assertEqual(h.get(0x7EF36D), 0xA0, "CurrentHealth must refill to MaxHealth")
            self.assertEqual(h.get(0x7EF36E), 0x80, "MagicPower must refill to full ($80)")
            self.assertEqual(h.get(0x7E012E), 0x0F, "Refill chime SFX2.$0F must be queued")
            self.assertEqual(h.get(0x7EC139), 0xA5, "FinaleContinueCheckpoint must be armed ($A5)")

            fairies = [
                s for s in range(16)
                if s != 2 and h.ram[0x0DD0 + s] == 0x09 and h.ram[0x0E20 + s] == 0xE3
            ]
            self.assertEqual(len(fairies), 2, f"Expected 2 healing fairies ($E3), got {len(fairies)}")
            xs = sorted(h.ram[0x0D10 + s] | (h.ram[0x0D30 + s] << 8) for s in fairies)
            ys = [h.ram[0x0D00 + s] | (h.ram[0x0D20 + s] << 8) for s in fairies]
            self.assertEqual(xs, [0x0178 - 0x18, 0x0178 + 0x18], "Fairies must spawn gently left/right of Link")
            self.assertEqual(ys, [0x0088, 0x0088], "Fairies must spawn 8px above Link's Y")
            for s in fairies:
                self.assertEqual(h.ram[0x0F70 + s], 0x0C, "Fairy float height should be $0C")
                self.assertEqual(h.ram[0x0F10 + s], 0x18, "Fairy grace timer should be $18")

            # Safe when all 16 sprite slots are full (no crash / stack imbalance)
            h.ram[0x0DD0:0x0DE0] = b"\x09" * 16
            h.put(0x7EF36D, 0x08)
            h.put(0x7EF36E, 0x00)
            h.put(0x7E012E, 0x00)
            h.put(0x7EC139, 0x00)
            h.call("Kydreeok_PostHealRestBeat", x=2, db=0x32)
            self.assertEqual(h.get(0x7EF36D), 0xA0)
            self.assertEqual(h.get(0x7EF36E), 0x80)
            self.assertEqual(h.get(0x7E012E), 0x0F)
            self.assertEqual(h.get(0x7EC139), 0xA5)
        finally:
            h.close()

    def test_finale_continue_checkpoint_routes_gameover_continue_to_ent_7b(self) -> None:
        h = self.make_harness(0x02)
        try:
            load_cp = h.addr("LoadCheckpointOrWorld")
            assert load_cp is not None
            stops = {0x028208, load_cp}

            # 1. Armed checkpoint + death Continue ($010A=1) + Kydreeok dead ($7EF005 bit 3) + Ganondorf/Beast live:
            for fight_state in (0x01, 0x03):
                h.put(0x7EC139, 0xA5)
                h.put(0x010A, 0x01)
                h.put(0x04AA, 0x38)
                h.put(0x04AB, 0x01)
                h.put(0x7EF005, 0x08)
                h.put(0x7E1EA6, fight_state)  # GanondorfFight
                h.put(0x7E1EA8, 0x00)         # FinaleBeat
                h.put(0x7EF3CA, 0x00)         # SavedWorld
                stop = h.call_until("FinaleContinue_LoadCheckpointOrWorld", stops, long_return=True, db=0x02)
                self.assertEqual(stop, 0x028208, f"Fight state {fight_state} Continue must jump to LoadUnderworldRoomRebuildHUD")
                self.assertEqual(h.get(0x010E), 0x7B, "Finale Continue must load Entrance $7B (Room $0002 -> Room $0000)")
                self.assertEqual(h.get(0x010F), 0x00)
                self.assertEqual(h.get(0x010A), 0x01, "Must keep $010A=1 to skip recaching OW exit")
                self.assertEqual(h.get16(0x04AA), 0x0000, "Must clear $04AA/$04AB to select EntranceData")
                self.assertEqual(h.get(0x7EF3CA), 0x40, "Must set Dark World $40")
                self.assertEqual(h.get(0x7E1EA6), 0x00, "Must reset GanondorfFight=0 for clean rematch")
                self.assertEqual(h.get(0x7E1EA8), 0x60, "Must arm FinaleBeat=$60")

            # 2. Fresh File Select load ($010A == 0): clears volatile checkpoint and delegates to LoadCheckpointOrWorld
            h.put(0x7EC139, 0xA5)
            h.put(0x010A, 0x00)
            h.put(0x7EF005, 0x08)
            h.put(0x7E1EA6, 0x01)
            stop = h.call_until("FinaleContinue_LoadCheckpointOrWorld", stops, long_return=True, db=0x02)
            self.assertEqual(stop, load_cp, "Fresh file load must pass through to LoadCheckpointOrWorld")
            self.assertEqual(h.get(0x7EC139), 0x00, "Fresh file load must clear volatile checkpoint")

            # 3. After Beast Ganon defeated (GanondorfFight == 2): clears checkpoint and delegates
            h.put(0x7EC139, 0xA5)
            h.put(0x010A, 0x01)
            h.put(0x7EF005, 0x08)
            h.put(0x7E1EA6, 0x02)
            stop = h.call_until("FinaleContinue_LoadCheckpointOrWorld", stops, long_return=True, db=0x02)
            self.assertEqual(stop, load_cp)
            self.assertEqual(h.get(0x7EC139), 0x00)

            # 4. Beast_Dead timer==0 clears FinaleContinueCheckpoint automatically
            h.put(0x7EC139, 0xA5)
            h.spr("SprAction", 0x0F, slot=2)
            h.spr("SprTimerA", 0x00, slot=2)
            h.spr("SprState", 0x09, slot=2)
            h.call("Beast_Dead", x=2, db=0x2A)
            self.assertEqual(h.get(0x7E1EA6), 0x02)
            self.assertEqual(h.get(0x7EC139), 0x00, "Beast_Dead completion must clear FinaleContinueCheckpoint")
        finally:
            h.close()

    # ---- 4. Farore's Safe-Center Glow Ring ----
    def test_farore_safe_center_glow_ring_phases_pulse_and_oam_bounds(self) -> None:
        h = self.make_harness(0x2A)
        try:
            def prep_beast(hp: int, action: int, frame_cnt: int = 0x00, oam_base: int = 0x0900) -> None:
                h.region_b_allocs.clear()
                h.region_b_cursor = oam_base
                h.region_b_hi_cursor = 0x0A00 + ((oam_base - 0x0800) >> 2)
                h.ram[0x0800:0x0A80] = b"\xF0" * 0x280
                h.spr("SprMiscF", hp, slot=2)
                h.spr("SprAction", action, slot=2)
                h.spr("SprXH", 0x01, slot=2)
                h.spr("SprYH", 0x00, slot=2)
                h.put16(0xE2, 0x0100)  # Room $0000 right-half camera scroll X
                h.put16(0xE8, 0x0010)  # Room $0000 camera scroll Y
                h.put(0x1A, frame_cnt)

            # Off in Phase 1 (hits 6 and 5), Enter ($08), and Dead ($0F)
            for hp, act in ((6, 0x09), (5, 0x0B), (4, 0x08), (1, 0x0F)):
                prep_beast(hp, act)
                h.call("Beast_DrawSafeRing", x=2, db=0x2A)
                self.assertEqual(h.region_b_allocs, [], f"Ring must stay OFF for hp={hp}, act={act:#x}")

            # Phase 2 (hits 4..3): 4 corners at ($13A,$04A), ($1BE,$04A), ($13A,$0BE), ($1BE,$0BE) - ($100,$10)
            prep_beast(hp=4, action=0x09, frame_cnt=0x00, oam_base=0x0900)
            h.call("Beast_DrawSafeRing", x=2, db=0x2A)
            self.assertEqual(h.region_b_allocs, [0x10], "Phase 2 must allocate 4 OAM entries (16B) from Region B")
            p2_expected = [(0x3A, 0x3A), (0xBE, 0x3A), (0x3A, 0xAE), (0xBE, 0xAE)]
            p2_chrs_t0 = []
            for i, (ex, ey) in enumerate(p2_expected):
                base = 0x0900 + i * 4
                self.assertEqual((h.ram[base], h.ram[base + 1]), (ex, ey), f"Phase 2 corner {i} coords mismatch")
                self.assertIn(h.ram[base + 2], SPARKLE_CHRS)
                self.assertEqual(h.ram[base + 3], 0x1A, "Must use Pal 5 ($0A), low prio ($10), Page 0 (N=0)")
                self.assertEqual(h.ram[0x0A40 + i] & 0x02, 0x00, "Must be small 8x8 OAM tile (size bit 0)")
                p2_chrs_t0.append(h.ram[base + 2])

            # Gentle pulse check: advancing $1A by 8 rotates sparkle frames across all 4 corners
            prep_beast(hp=4, action=0x09, frame_cnt=0x08, oam_base=0x0900)
            h.call("Beast_DrawSafeRing", x=2, db=0x2A)
            p2_chrs_t1 = [h.ram[0x0900 + i * 4 + 2] for i in range(4)]
            self.assertNotEqual(p2_chrs_t0, p2_chrs_t1, "Sparkle ring must pulse/cycle tiles with $1A")

            # Phase 3 (hits 2..1): tightens to ($14A,$05A), ($1AE,$05A), ($14A,$0AE), ($1AE,$0AE) - ($100,$10)
            prep_beast(hp=2, action=0x0D, frame_cnt=0x10, oam_base=0x09F0)  # exact last legal 4-entry OAM base!
            h.call("Beast_DrawSafeRing", x=2, db=0x2A)
            self.assertEqual(h.region_b_allocs, [0x10])
            p3_expected = [(0x4A, 0x4A), (0xAE, 0x4A), (0x4A, 0x9E), (0xAE, 0x9E)]
            for i, (ex, ey) in enumerate(p3_expected):
                base = 0x09F0 + i * 4
                self.assertLessEqual(base, 0x09FC)
                self.assertEqual((h.ram[base], h.ram[base + 1]), (ex, ey), f"Phase 3 corner {i} coords mismatch")
                self.assertEqual(h.ram[base + 3], 0x1A)

            # OAM bounds guard: $09F4 would overflow past $09FC into $0A00 -> must abort with zero writes!
            prep_beast(hp=2, action=0x09, frame_cnt=0x00, oam_base=0x09F4)
            sentinel = bytes(h.ram[0x09F0:0x0A10])
            h.call("Beast_DrawSafeRing", x=2, db=0x2A)
            self.assertEqual(bytes(h.ram[0x09F0:0x0A10]), sentinel, "OAM base $09F4 must abort cleanly without overrun")

            # End-to-end Beast_Draw: during Phase 2 core-hit flicker (body skipped when $1A & 2 == 0),
            # Farore's Safe-Center Glow Ring still draws cleanly via Region B without touching body OAM!
            prep_beast(hp=4, action=0x0E, frame_cnt=0x00, oam_base=0x0920)
            h.put16(0x90, 0x0800)
            h.put16(0x92, 0x0A00)
            h.call("Beast_Draw", x=2, db=0x2A)
            self.assertEqual(h.region_b_allocs, [0x10], "Beast_Draw must keep Farore ring lit on body flicker frames")
            self.assertEqual(h.ram[0x0920], 0x3A)
            self.assertEqual(h.ram[0x0923], 0x1A)
        finally:
            h.close()


if __name__ == "__main__":
    unittest.main()
