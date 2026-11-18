"""Compiled saved-selector routing, with declared loader/HUD service probes.

Uses the existing Asar/65816 runner; no game ROM, native capture, or room-art
qualification. Source flag off preserves the old selector policy.
"""
import unittest
import test_special_overworld_semantic_kernel as T


@unittest.skipUnless(T.R.ASSEMBLER and T.RUNNER, 'Asar and existing OOS_65816_RUNNER required')
class PrisonRespawnMigrationTest(unittest.TestCase):
    def build(self, enabled, checkpoint_source=None):
        checkpoint_source = checkpoint_source or T.R.ROOT / "Overworld/goron_checkpoint.asm"
        extra = f'''
!ENABLE_KALYXO_BOAT = 0
!ENABLE_DUAL_ITEM_BINDING_PROTOTYPE = 0
!ENABLE_ABYSS_SPAWN_MENU = 0
!ENABLE_D3_PRISON_SEQUENCE = {enabled}
!SPECIAL_OVERWORLD_NATIVE = 0
!Spawn_Prison = 2
!Spawn_Sanctuary = 1
!Spawn_LinksHouse = 0
!Spawn_GoronCheckpoint = 7
!CastleAmbush_HasBeenCaptured = 1
!CastleAmbush_HasEscaped = 2
namespace Oracle
SpawnPoint = $7EF3C8
CastleAmbushFlags = $7EF306
GameState = $7EF3C5
SavedWorld = $7EF3CA
FollowerId = $7EF3CC
GanondorfFight = $0F20
BossReinject = $0F21
FinaleBeat = $0F22
org $348000
incsrc "{checkpoint_source}"
CheckpointEnd:
LoadDarkWorldIntro:
  LDA.l SavedWorld : RTL
namespace off
org $028196
LegacyContinuation:
  PHP : STA.w $0F02 : PLA : STA.w $0F03
  INC.w $0F00 : RTL
org $028208
PrisonEntranceContinuation:
  INC.w $0F01 : RTL
org $0DE395
  RTL
org $0DFA6C
  RTL
org $0DDD32
  RTL
'''
        a = T.Artifact([], overrides={"SPECIAL_OVERWORLD_SEMANTIC_ENABLED": 0}, extra_source=extra)
        self.addCleanup(a.close)
        self.assertEqual(a.proc.returncode, 0, a.proc.stdout + a.proc.stderr)
        return a

    def run_case(self, art, selector, flags, world=0, state=3, follower=0):
        ram = bytearray(65536)
        for address, value in ((0xF3C8, selector), (0xF306, flags),
                               (0xF3C5, state), (0xF3CA, world),
                               (0xF3CC, follower)):
            ram[address] = value
        T.word(ram, 0x10E, 0xCAFE); T.word(ram, 0x4AA, 0xBEEF)
        result, out, before = art.call('Oracle_LoadCheckpointOrWorld',
            a=0xAB5A, x=5, y=0x42, p=0x75, db=2, d=0, ram=ram)
        for key in ('x', 'y', 'db', 'd', 'sp'):
            self.assertEqual(result['registers'][key], before[key], key)
        self.assertEqual(result['registers']['p'] & 0x30, 0x30)
        self.assertEqual(out[0xF306], flags, 'capture flags unchanged')
        self.assertEqual(out[0xF3CA], world, 'saved world unchanged')
        self.assertEqual(out[0xF3CC], follower, 'follower unchanged')
        self.assertEqual(out[0xF3C5], state, 'progression unchanged')
        return result, out

    def test_enabled_migrates_only_stale_prison_selector(self):
        art = self.build(1)
        for flags in (0, 2, 3, 0xA4, 0xA6, 0xA7):
            for world in (0, 0x40):
                with self.subTest(flags=flags, world=world):
                    result, out = self.run_case(art, 2, flags, world)
                    self.assertEqual(out[0xF3C8], 1)
                    self.assertEqual(out[0xF00:0xF02], b'\x01\x00')
                    self.assertEqual(out[0x10E:0x110], bytes.fromhex('feca'))
                    self.assertEqual(out[0x4AA:0x4AC], bytes.fromhex('efbe'))
                    # Module05 consumes the legacy service's A/N/Z.
                    self.assertEqual(out[0xF02], world)
                    self.assertEqual(out[0xF03] & 0x82, 2 if world == 0 else 0)

    def test_active_capture_keeps_complete_entrance_selection(self):
        art = self.build(1)
        for flags in (1, 0xA5):
            _, out = self.run_case(art, 2, flags)
            self.assertEqual(out[0xF3C8], 2)
            self.assertEqual(out[0xF00:0xF02], b'\x00\x01')
            self.assertEqual(out[0x10E:0x110], b'\x32\x00')
            self.assertEqual(out[0x10A], 1)
            self.assertEqual(out[0x4AA:0x4AC], b'\x00\x00')

    def test_feature_off_and_other_selectors_keep_legacy_policy(self):
        for enabled in (0, 1):
            art = self.build(enabled)
            selectors = range(7) if not enabled else (0, 1, 3, 4, 5, 6)
            for selector in selectors:
                for flags in (0, 1, 2, 3):
                    _, out = self.run_case(art, selector, flags)
                    self.assertEqual(out[0xF3C8], selector)
                    self.assertEqual(out[0xF00:0xF02], b'\x01\x00')

    def test_goron_selector_consumption_and_valid_checkpoint_unchanged(self):
        art = self.build(1)
        for state, world, follower, valid in ((2, 0, 0, True), (1, 0, 0, False),
                                            (2, 0x40, 0, False), (2, 0, 1, False)):
            # The native checkpoint uses X while copying; only this preexisting
            # branch has a distinct register contract.
            ram = bytearray(65536)
            for at, value in ((0xF3C8, 7), (0xF3C5, state),
                              (0xF3CA, world), (0xF3CC, follower)):
                ram[at] = value
            r, out, before = art.call('Oracle_LoadCheckpointOrWorld', p=0x30, db=2, d=0, ram=ram)
            self.assertEqual(out[0xF3C8], 0)
            self.assertEqual(out[0x10] == 8, valid)
            self.assertEqual(r['registers']['sp'], before['sp'])
