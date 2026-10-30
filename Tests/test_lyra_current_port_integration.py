"""Current-engine source composition checks; no assembler or CPU execution."""
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

from lyra_source_snapshots import read_snapshot_text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import asm_source as S
import generate_hack_manifest as H
import lyra_project_publisher as P
import lyra_current_transfer as X
import lyra_native_loaders as L
import test_lyra_current_native_loaders as reader_fixtures


FROZEN = 'c19cf98873c0d409043b1d59016633f415b72dba'
INTEGRATED_INCLUDES = {
    'Core/Generated/menu_icons/menu_icon_overrides.asm': 'Menu/menu.asm',
    'Data/overworld/whirlpool_placements.asm': 'Overworld/overworld.asm',
    'Items/bombchu.asm': 'Items/all_items.asm',
    'Items/bombchu_pickup.asm': 'Items/all_items.asm',
    'Items/byrna.asm': 'Items/ocarina.asm',
    'Items/deku_stick.asm': 'Items/all_items.asm',
    'Items/song_secrets_stone.asm': 'Items/ocarina.asm',
    'Items/switch_hook.asm': 'Items/all_items.asm',
    'Masks/garo_mask.asm': 'Masks/all_masks.asm',
    'Sprites/Enemies/darknut_weapon_hitbox.asm': 'Sprites/all_sprites.asm',
    'Sprites/NPCs/garo.asm': 'Sprites/all_sprites.asm',
}
SHARED_PATHS = ('Overworld/ZSCustomOverworld.asm', 'Overworld/time_system.asm',
                'Overworld/lost_woods.asm', 'Overworld/custom_gfx.asm',
                'Overworld/goron_checkpoint.asm', 'Masks/mask_routines.asm')
AUTHORITY_FLAGS = ('allocation_granted', 'publication_authorized',
                   'producer_enforcement_verified', 'ordinary_build_ready', 'runtime_admission')


def disabled_defines():
    with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '0'}):
        defines = S._load_global_defines(ROOT)
    # Explicit HOST selection: the production scanner conservatively retains
    # unknown external -D branches. Do not change that production behavior.
    defines['LYRA_PRIVATE_PILOT_INGRESS_ENABLED'] = 0
    return defines


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Reviewed integration anchor changed: ' + repr(before))
    return text.replace(before, after, 1)


def integrated_expected(name, frozen):
    """Project only literal adopted item/menu changes onto the frozen c19 source.

    0906f4a193279468eeca4318d7c44a2d12e9d7a3 adopted Garo/prototype
    cleanup and clock attributes. 8d0d660d5f9ac47f1d6b5c411f1c78ab0a0fceb1
    added Deku startup, lifecycle, sword dispatch and frame ticking.
    No live-source slice or replacement hash supplies the expected instructions.
    """
    if name == 'Overworld/time_system.asm':
        for field in ('hud_hours_low', 'hud_min_low', 'hud_hours_high', 'hud_min_high'):
            frozen = replace_once(frozen, 'LDA #$30 : STA.l !' + field + '+1',
                                  'LDA #$24 : STA.l !' + field + '+1')
    elif name == 'Masks/mask_routines.asm':
        changes = (
            ('  LDA #$10 : STA $BC\n  RTL',
             '  LDA #$10 : STA $BC\n  JSL DekuStick_Drop\n'
             '  PHX\n  LDX.b #$11\n  .clear_prototypes\n'
             '  STZ.w $07EE, X\n  DEX : BPL .clear_prototypes\n  PLX\n  RTL'),
            ('ResetToLinkGraphics:\n{\n',
             'ResetToLinkGraphics:\n{\n  JSL GaroMask_Clear\n'),
            ('ForceResetMask_GameOver:\n{\n',
             'ForceResetMask_GameOver:\n{\n  JSL DekuStick_Drop\n'),
            ('ForceResetMask_SaveAndQuit:\n{\n',
             'ForceResetMask_SaveAndQuit:\n{\n  JSL DekuStick_Drop\n'),
            ('CMP.b #$07 : BEQ .moosh_form\n                        JMP   .original_sprite',
             'CMP.b #$07 : BEQ .moosh_form\n  CMP.b #$08 : BEQ .garo_form\n'
             '                        JMP   .original_sprite'),
            ('\n  .original_sprite\n',
             '\n  .garo_form\n  LDA.b #$42 : STA.b $BC\n  JSL UpdateGaroPalette\n'
             '  RTL\n\n  .original_sprite\n'),
            ('LinkItem_CheckForSwordSwing_Masks:\n{\n',
             'LinkItem_CheckForSwordSwing_Masks:\n{\n'
             '  LDA.l DekuStick_State : BEQ .check_masks\n'
             '  BIT.b $F4 : BPL .skip_sword\n  JSL DekuStick_Stow\n'
             '.skip_sword\n  LDA.b #$10\n  RTL\n.check_masks\n'
             '  LDA.w !CurrentMask : CMP.b #$08 : BNE +\n'
             '  JSL GaroMask_CounterInput\n  BRA .return\n  +\n'),
            ('  JSL MinishPortal_Maintain\n  PLB',
             '  JSL MinishPortal_Maintain\n  JSL GaroMask_FrameTick\n'
             '  JSL DekuStick_Main\n  PLB'),
        )
        for before, after in changes:
            frozen = replace_once(frozen, before, after)
    return frozen


def inline_goron_control_cache(text, frozen):
    """Expand only the named, unchanged zero-argument cache macro, once."""
    name = 'RegionalCheckpoint_GoronControlCache'
    pattern = (r'^macro ' + name + r'\(\)\n(?P<body>.*?)^endmacro\n'
               r'GoronCheckpoint_Cache:\n  %' + name + r'\(\)\n')
    matches = list(re.finditer(pattern, text, re.M | re.S))
    old = re.search(r'^GoronCheckpoint_Cache:\n(?P<body>.*?)^assert ', frozen, re.M | re.S)
    if (len(matches) != 1 or old is None
            or text.count('macro ' + name + '()') != 1
            or text.count('%' + name + '()') != 1
            or matches[0]['body'] != old['body']):
        raise ValueError('Reviewed Goron cache macro body or invocation changed')
    match = matches[0]
    return text[:match.start()] + 'GoronCheckpoint_Cache:\n' + match['body'] + text[match.end():]


def statements(text, defines):
    result = []
    for _, line, _ in S._iter_active_lines(text.splitlines(), defines):
        line = line.split(';', 1)[0].strip()
        line = re.sub(r'^(?:[A-Za-z_][\w.]*|\.[\w]+):\s*', '', line)
        if not line or line in ('{', '}') or re.match(r'^[!\w.]+\s*(?:#=|=)', line):
            continue
        if line.startswith('assert '):
            continue
        result.extend(part.strip() for part in line.split(':') if part.strip())
    return result


class CurrentPortIntegrationTest(unittest.TestCase):
    def test_ordinary_context_is_disabled_and_has_original_source_domain(self):
        defines = disabled_defines()
        for key in ('LYRA_BUILD_CONTEXT', 'LYRA_CURRENT_MODE', 'LYRA_PROJECT_DATA_PRESENT',
                    'LYRA_CURRENT_RESIDENT_ENABLED', 'LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED',
                    'LYRA_CURRENT_EVENTS_ENABLED', 'LYRA_CURRENT_ACTORS_ENABLED',
                    'PROJECT_BG128_ENABLED', 'PROJECT_BG128_RESTORE_BOUND',
                    'ENABLE_OW_AREA_TILESETS', 'ENABLE_KALYXO_BOAT', 'REGIONAL_CHECKPOINTS_ENABLED'):
            self.assertEqual(defines[key], 0, key)
        paths = H.collect_reachable_asm_sources(ROOT, defines=defines)
        # Frozen c19 had174 sources. These11 owned integration includes explain
        # the new domain; none enables the current/resident runtime consumers.
        self.assertEqual(len(paths), 174 + len(INTEGRATED_INCLUDES))
        self.assertEqual(len(INTEGRATED_INCLUDES), 11)
        for path, owner in INTEGRATED_INCLUDES.items():
            self.assertIn(ROOT / path, paths)
            self.assertIn(ROOT / owner, paths)
            includes = {value for _, value in S._iter_active_incsrcs(
                (ROOT / owner).read_text().splitlines(), defines)}
            self.assertIn(path, includes, owner)
        for path in ('lyra_native_loaders.asm', 'project_bg_palette.asm', 'graphics_runtime.asm',
                     'lyra_resident_atlas.asm', 'lyra_resident_resources.asm',
                     'lyra_tail_events.asm', 'lyra_actor_stream.asm', 'lyra_private_pilot.asm'):
            self.assertNotIn(ROOT / 'Overworld' / path, paths)

    def test_disabled_shared_instructions_match_exact_current_engine(self):
        defines = disabled_defines()
        for name in SHARED_PATHS:
            with self.subTest(path=name):
                original = read_snapshot_text(FROZEN, name)
                actual = (ROOT / name).read_text()
                if name == 'Overworld/goron_checkpoint.asm':
                    actual = inline_goron_control_cache(actual, original)
                self.assertEqual(statements(actual, defines),
                                 statements(integrated_expected(name, original), defines))

    def test_finite_projections_reject_changed_anchors_and_unlisted_instructions(self):
        defines = disabled_defines()
        probes = (
            ('Overworld/time_system.asm', 'LDA #$30 : STA.l !hud_hours_low+1',
             'LDA #$24 : STA.l !hud_hours_low+1', 'LDA #$25 : STA.l !hud_hours_low+1'),
            ('Masks/mask_routines.asm', 'ResetToLinkGraphics:\n{\n',
             'JSL DekuStick_Main', 'JSL DekuStick_Drop'),
        )
        for name, anchor, before, after in probes:
            with self.subTest(path=name):
                original = read_snapshot_text(FROZEN, name)
                with self.assertRaisesRegex(ValueError, 'Reviewed integration anchor changed'):
                    integrated_expected(name, original.replace(anchor, '', 1))
                expected = statements(integrated_expected(name, original), defines)
                mutated = replace_once((ROOT / name).read_text(), before, after)
                self.assertNotEqual(statements(mutated, defines), expected)
        name = 'Overworld/goron_checkpoint.asm'
        original = read_snapshot_text(FROZEN, name)
        current = (ROOT / name).read_text()
        mutated = replace_once(current, 'dw $0036, $0016', 'dw $0037, $0016')
        with self.assertRaisesRegex(ValueError, 'Reviewed Goron cache macro body or invocation changed'):
            inline_goron_control_cache(mutated, original)
        with self.assertRaisesRegex(ValueError, 'Reviewed Goron cache macro body or invocation changed'):
            inline_goron_control_cache(current + '\n%RegionalCheckpoint_GoronControlCache()\n', original)

    def test_current_callers_have_separate_direction_and_backdrop_boundaries(self):
        zs = (ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        self.assertIn('JSL Lyra_ReadByScreen : CLC : ADC.b $84 : STA.b $84', zs)
        self.assertIn('JSL Lyra_ReadMosaic', zs)
        time = (ROOT/'Overworld/time_system.asm').read_text()
        self.assertIn('LDA.b $8A : AND.w #$00FF\nLyra_CurrentBackdropLegacy:', time)
        self.assertIn('CMP.b #!LYRA_CURRENT_END : BCC .notSpecialOverworld', zs)

    def test_current_and_bg_source_pins_match_actual_composition(self):
        ledger = json.loads((ROOT/'Config/allocation_ownership.json').read_bytes())
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        source_set = contract['ledger']['source_set']
        self.assertEqual(source_set, 'lyra_current_resident_conditional_55')
        records = [r for r in ledger['sources'].values() if r['source_set']==source_set]
        self.assertTrue(records)
        self.assertEqual(contract['ledger']['sha256'], P.R.sha((ROOT/'Config/allocation_ownership.json').read_bytes()))
        bindings = P.validate_current_source_set(contract)
        self.assertEqual(len(bindings), len(records) + 1)
        self.assertEqual({row['path']: row['sha256'] for row in bindings[1:]},
                         {str(ROOT/row['path']): row['sha256'] for row in records})
        for row in records:
            self.assertEqual(P.R.sha((ROOT/row['path']).read_bytes()), row['sha256'], row['path'])
        claim, = [r for r in ledger['claims'] if r['id']=='ProjectBGPaletteNativeUnderlay']
        # Selected source binding advances independently of historical claim
        # provenance; changing the selection grants no new physical authority.
        historical = 'lyra_private_pilot_boundary_cpu_23'
        expected = {historical + ':' + path for path in (
            'Overworld/project_bg_palette.asm', 'Masks/mask_routines.asm',
            'Overworld/goron_checkpoint.asm', 'Overworld/time_system.asm', 'Oracle_main.asm',
            'Overworld/ZSCustomOverworld.asm', 'Util/macros.asm', 'Config/feature_flags.asm')}
        self.assertEqual(set(claim['provenance']), expected)
        self.assertEqual(len(claim['provenance']), len(expected))
        for key in expected:
            self.assertEqual(ledger['sources'][key]['source_set'], historical)
            self.assertEqual(key, historical + ':' + ledger['sources'][key]['path'])
        self.assertIs(claim['source_reservation']['activation'], False)
        self.assertIs(claim['source_reservation']['code_rom_grant'], False)

    def test_actual_contract_and_review_still_refuse_before_output(self):
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        # Establish valid source binding first. With a bound ledger, an empty
        # review now reaches the real review guard; it still cannot publish.
        self.assertTrue(P.validate_current_source_set(contract))
        self.assertEqual(contract['status'], 'proposed')
        self.assertEqual(contract['scope'], 'source_review_only')
        for key in AUTHORITY_FLAGS:
            self.assertIs(contract[key], False, key)
        self.assertTrue(all(v is not None for v in contract['origins'].values()))
        for key in ('resident_data', 'resident_code', 'resident_resource_code'):
            self.assertNotIn(key, contract['origins'])
        with self.assertRaisesRegex(ValueError, '^Malformed current reservation review$'):
            X.validate_current_source_contract({}, ROOT/'unused-project', ROOT/'unused-rom')

    def test_loose_component_plan_cannot_compose_without_verified_current_profile(self):
        reader_fixtures.CurrentNativeLoaderTests.setUpClass()
        table_plan = reader_fixtures.CurrentNativeLoaderTests.plan
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        contract['ledger']['sha256'] = P.R.sha((ROOT/'Config/allocation_ownership.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_PROFILE_REQUIRED'):
            P.render_current_source_outputs(table_plan, contract=contract,
                graphics_source='; loose host fixture\n', graphics_report={})


if __name__ == '__main__':
    unittest.main()
