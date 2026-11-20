"""Kalyxo ferry endpoint, NPC entry, cancel recovery, and refusal checks.

Source and the existing recovery model only. No ROM write and no CPU claim
about stripe upload or native rendering.
"""
from pathlib import Path
import importlib.util
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOAT = ROOT / "Overworld/kalyxo_boat.asm"
PLACEMENTS = ROOT / "Data/overworld/kalyxo_boat_placements.asm"


def _load_recovery():
    spec = importlib.util.spec_from_file_location(
        "ferry_contract", ROOT / "Tests/test_ferry_native_cache_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _routine(source, name):
    body = source.split(name + ":\n{", 1)[1].split("\n}", 1)[0]
    return "\n".join(line.split(";", 1)[0] for line in body.splitlines())


class KalyxoBoatEndpointBounds(unittest.TestCase):
    def test_live_rev5_coordinates_and_tiles_stay_bound(self):
        source = PLACEMENTS.read_text()
        self.assertRegex(source, r"(?m)^!KALYXO_BOAT_ENDPOINTS_BOUND = 1$")
        self.assertRegex(source, r"(?m)^!Boat_StopCount = 2$")
        self.assertRegex(source, r"(?m)^!Boat_EndpointWords = !Boat_StopCount\*2$")
        calls = re.findall(r"^  %BoatNativeCache\(([^)]+)\)", source, re.M)
        self.assertEqual(len(calls), 2)
        docks, quay = ([int(v.strip()[1:], 16) for v in call.split(",")] for call in calls)
        # area, scroll Y/X, Link Y/X. Parent $30 area tile (48, 23) and $99 (23, 19).
        self.assertEqual(docks[0], 0x30)
        self.assertEqual(docks[3], 0x0D70)
        self.assertEqual(docks[4], 0x0300)
        self.assertEqual(quay[0], 0x99)
        self.assertEqual(quay[3], 0x0730)
        self.assertEqual(quay[4], 0x0370)
        self.assertEqual((0x0D70, 0x0300), (6 * 0x200 + 23 * 16, 1 * 0x200 + 16 * 16))
        self.assertEqual((0x0730, 0x0370), (115 * 16, 55 * 16))
        for name, value in {
            "DocksOpenTile": 0x0FC0,
            "IslandOpenTile": 0x085E,
            "DocksWaterTile": 0x02CD,
            "IslandWaterTile": 0x02C3,
        }.items():
            self.assertRegex(source, rf"(?m)^!Boat_{name} = \${value:04X}$")
        self.assertNotEqual(0x0FC0, 0x02CD)
        self.assertNotEqual(0x085E, 0x02C3)

    def test_a_press_packs_destination_and_recovery_keeps_low_nibble(self):
        source = BOAT.read_text()
        try_board = _routine(source, "Boat_TryBoard")
        self.assertIn("EOR.b #$02 : ASL #4 : ORA.l Boat_Endpoint", try_board)
        self.assertIn("CPY.w #!Boat_EndpointWords", try_board)
        recover = _routine(source, "Boat_CanRecoverPlank")
        self.assertIn("AND.w #$000F : CMP.w #$0004", recover)
        self.assertNotIn("AND.w #$00FF : CMP.w #$0004", recover)


class KalyxoBoatNpcEntry(unittest.TestCase):
    def test_public_entry_takes_a_stop_index_without_the_a_press_window(self):
        body = _routine(BOAT.read_text(), "Boat_StartCrossingFromNpc")
        self.assertIn("CMP.b #!Boat_StopCount", body)
        self.assertIn("JSR Boat_TravelBlocked", body)
        self.assertIn("LDA.b #$0C : STA.b $10", body)
        self.assertIn("LDA.w #!Boat_Magic : STA.l Boat_Marker", body)
        self.assertNotIn("$F6", body)
        self.assertNotIn("CMP.w #15", body)
        self.assertIn("LSR A : CMP.b $00", body)
        self.assertIn("CLC : RTL", body)
        self.assertIn("SEC : RTL", body)

    def test_arrival_returns_to_module_09(self):
        body = _routine(BOAT.read_text(), "Boat_Arrive")
        self.assertIn("LDA.b #$09 : STA.b $10 : STA.w $010C", body)
        self.assertNotIn("LDA.b #$0B", body)

    def test_travel_block_matches_the_plank_refusals(self):
        body = _routine(BOAT.read_text(), "Boat_TravelBlocked")
        for token in ("$1B", "$0112", "$02E4", "$0FFC", "$04C6",
                      "FollowerId", "SavedWorld", "$5D", "$4B", "$4D", "$0308"):
            self.assertIn(token, body)
        self.assertIn("SEC : RTS", body)
        self.assertIn("CLC : RTS", body)


class KalyxoBoatCancelRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ferry = _load_recovery()

    def test_packed_source_nibble_still_restores_closed_plank(self):
        for endpoint, packed in ((0, 0x20), (2, 0x22)):
            with self.subTest(endpoint=endpoint, packed=packed):
                machine, symbols = self.ferry.recovery_machine(
                    endpoint=endpoint, changes={"Boat_Endpoint": packed})
                self.assertEqual(machine.read(0x7E24C0, True), 0x0FC8)
                self.assertEqual(machine.read(symbols["Boat_Marker"], True), 0)

    def test_odd_low_nibble_refuses_even_when_high_nibble_is_packed(self):
        for packed in (0x21, 0x23, 0x04):
            with self.subTest(packed=packed):
                endpoint = 0 if packed < 0x22 else 2
                machine, _symbols = self.ferry.recovery_machine(
                    endpoint=endpoint, changes={"Boat_Endpoint": packed})
                self.assertFalse(any(0x7E2000 <= address < 0x7E4000
                                     for address in machine.writes))


if __name__ == "__main__":
    unittest.main()
