"""Resident compiled readback with private sparse code and no address grants.

The literal hook census is independent of the inspector's implementation.
These byte fixtures prove inspection, not assembled CPU or native behavior.
"""
import copy
import re
import unittest

from test_lyra_current_build import consumer_fixture
import lyra_native_loaders as L


WORD_HOOKS = (
    (0x02FE1B, 'Full0', 3), (0x02FE22, 'Full2', 3),
    (0x02FE2B, 'Full1', 3), (0x02FE32, 'Full3', 3),
    (0x02F456, 'Horizontal0', 0), (0x02F45D, 'Horizontal1', 0),
    (0x02F466, 'Horizontal2', 0), (0x02F46D, 'Horizontal3', 0),
    (0x02F51E, 'Vertical0', 0), (0x02F525, 'Vertical2', 0),
    (0x02F52E, 'Vertical1', 0), (0x02F535, 'Vertical3', 0),
    (0x1BC9B2, 'Mutable0', 0), (0x1BC9B9, 'Mutable1', 0),
    (0x1BC9C0, 'Mutable2', 0), (0x1BC9C7, 'Mutable3', 0),
    (0x1BCA3F, 'Mutable0', 0), (0x1BCA46, 'Mutable1', 0),
    (0x1BCA4D, 'Mutable2', 0), (0x1BCA54, 'Mutable3', 0))


def resident_fixture():
    image, symbols = consumer_fixture(bytes(0x400000), 0xE0C000, bg_code=0xE0C800)
    image = bytearray(image)
    labels = {name: int(bank+offset, 16) for bank, offset, name in re.findall(
        r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\w+)$', symbols.decode(), re.M)}

    def put(at, raw):
        image[L.A.pc(at):L.A.pc(at)+len(raw)] = raw

    labels.update(Lyra_ResidentAtlasCodeStart=0xF88000, Lyra_ResidentAtlasCodeEnd=0xF88400,
        ResidentResourceCodeStart=0xF88600, ResidentAnimationSelected=0xF88600,
        ResidentAnimationForceTransition=0xF88620, ResidentAnimationStage=0xF88640,
        ResidentAnimationDecompress=0xF886ED, ResidentAnimationDestinations=0xF886F5,
        ResidentResourceCodeEnd=0xF886FB,
        SharedGraphicsRuntimeEnd=0xE18400, ResidentGraphicsResetMainCache=0xE18020,
        ResidentGraphicsMarkMainCache=0xE18050, SharedGraphicsStageNativeMain=0xE18060,
        SharedGraphicsStageNative=0xE18080, SharedGraphicsTransitionSource=0xE18100,
        SharedGraphicsInvalidateCache=0xE18120, SharedGraphicsIncrementalSource=0xE18140,
        InvalidateCustomGraphicsCache=0xE18500, ResolveCustomGraphicsTransitionSheet=0xE18504,
        SelectCustomGraphicsTransitionSource=0xE18560, SelectShipIncrementalGraphicsSource=0xE18564,
        AnimateMirrorWarp_DecompressAnimatedTiles=0x00D8D5,
        NewOverworld_FinishTransGfx=0xE6C000, BlockGFXCheck=0xE6C080,
        CheckForChangeGraphicsNormalLoad=0xE6C100, BirdTravel_LoadTargetArea_Interupt=0x0AB8F5)
    for start, length in ((0xF88000, 0x400), (0xF88600, 251), (0xE18000, 0x400),
                          (0xE18500, 0x68), (0x00D8D5, 25), (0x0AB8F5, 83),
                          (0xE6C000, 128), (0xE6C100, 26)):
        put(start, b'\xEA'*length)
    names = [family+str(index) for family in ('Full', 'Horizontal', 'Vertical', 'Mutable')
             for index in range(4)]
    names += ['FullWord', 'HorizontalWord', 'VerticalWord', 'MutableWord',
              'BufferDelta', 'PhysicalPage', 'Lookup', 'IceRodWord']
    for index, name in enumerate(names):
        start = 0xF88000+index*0x20
        labels['Lyra_Resident'+name] = start
        labels['Lyra_Resident'+name+'_End'] = start+16
    # Independent literal Conn writer. Only its initial word load is a JSL;
    # the semantic B7, native target and unchanged two-DMA tail remain here.
    ice_prefix = bytes.fromhex(
        '9de403a8ad8c00d0016bada303c906f0016be004f0016bade803c908f008'
        'ade803c903f0016bad0303c906f0016bad0403c906f0016b8a8f04d07e'
        'ad12422980f0f9c230ad16218f05d07ea50038ed08072d0a070a0a0a8506'
        'a50238ed0c072d0e070506aaa9b7009f00207e1864028a293f00c920009005'
        'a9000485028a29ff0fc900089007a50269ff0785028a291f00650285028a29'
        '80074a65028d16218f07d07e')
    ice_suffix = bytes.fromhex(
        '8f00d07e8f02d07e2000fdc230af07d07e6920008d16212000fdaf05d07e'
        '8d1621e230af04d07eaa6b')
    labels.update(LyraHost_IceRodStart=0x0EFBA0, LyraHost_IceRodEnd=0x0EFC70,
        LyraHost_IceRodTargetStart=0x0EFBE2, LyraCall_IceRodWord=0x0EFC43,
        LyraCall_IceRodWord_End=0x0EFC47, LyraHost_IceRodDmaStart=0x0EFD00,
        LyraHost_IceRodDmaEnd=0x0EFD21)
    put(0x0EFBA0, ice_prefix+b'\x22'
        +labels['Lyra_ResidentIceRodWord'].to_bytes(3, 'little')+ice_suffix)
    put(0x0EFD00, bytes.fromhex(
        'a97e008d0443a900d08d0243e230a9188d0143a9048d0543a9018d00438d0b4260'))
    put(0x088A5D, bytes.fromhex('22a0fb0e'))
    for at, suffix, padding in WORD_HOOKS:
        put(at, b'\x22'+labels['Lyra_Resident'+suffix].to_bytes(3, 'little')+b'\xEA'*padding)
    put(labels['ResidentAnimationDecompress'], bytes.fromhex('2294d3005c')
        + labels['ResidentAnimationStage'].to_bytes(3, 'little'))
    put(labels['ResidentAnimationDestinations'], bytes.fromhex('80a680aa80ae'))
    cache = 0x7E1E20  # Literal synthetic scratch, never a repository reservation.
    put(labels['ResidentGraphicsResetMainCache'], bytes.fromhex('08c22048e220a9ff')
        + b''.join(b'\x8F'+(cache+i).to_bytes(3, 'little') for i in range(4))
        + bytes.fromhex('c22068286b'))
    put(labels['ResolveCustomGraphicsTransitionSheet'], b'\xBF'+cache.to_bytes(3, 'little')
        + b'\xAF'+(cache+3).to_bytes(3, 'little'))
    for name, target in (('InvalidateCustomGraphicsCache', 'SharedGraphicsInvalidateCache'),
                         ('SelectCustomGraphicsTransitionSource', 'SharedGraphicsTransitionSource'),
                         ('SelectShipIncrementalGraphicsSource', 'SharedGraphicsIncrementalSource')):
        put(labels[name], b'\x5C'+labels[target].to_bytes(3, 'little'))
    call_rows = (
        ('LyraHost_PreOverworld_LoadProperties_Interupt', 'ResidentAnimationDecompress', 1),
        ('LyraHost_Credits_LoadScene_Overworld_PrepGFX_Interupt', 'ResidentAnimationDecompress', 1),
        ('LyraHost_CheckForChangeGraphicsTransitionLoad', 'ResidentAnimationForceTransition', 2),
        ('LyraHost_CheckForChangeGraphicsTransitionLoad', 'ResidentAnimationDecompress', 2),
        ('LyraHost_InitTilesetsLongCalls', 'ResidentGraphicsResetMainCache', 1),
        ('LyraHost_AnimateMirrorWarp_DecompressNewTileSetsLongCalls', 'ResidentGraphicsResetMainCache', 1),
        ('LyraHost_AnimateMirrorWarp_DecompressBackgroundsCLongCalls', 'ResidentAnimationStage', 1),
        ('AnimateMirrorWarp_DecompressAnimatedTiles', 'ResidentAnimationDecompress', 1),
        ('BirdTravel_LoadTargetArea_Interupt', 'ResidentAnimationStage', 1),
        ('BirdTravel_LoadTargetArea_Interupt', 'ResidentAnimationDecompress', 1),
        ('NewOverworld_FinishTransGfx', 'SharedGraphicsStageNativeMain', 2),
        ('CheckForChangeGraphicsNormalLoad', 'ResidentAnimationStage', 1))
    next_offset = {}
    for host, target, count in call_rows:
        offset = next_offset.get(host, 0)
        for index in range(count):
            put(labels[host]+offset+index*4, b'\x22'+labels[target].to_bytes(3, 'little'))
        next_offset[host] = offset+count*4
    symbols = ('[labels]\n'+'\n'.join(f'{value>>16:02X}:{value&65535:04X} Oracle_{name}'
        for name, value in labels.items())+'\n').encode()
    return bytes(image), symbols, labels


class ResidentCompiledInspectionTest(unittest.TestCase):
    def setUp(self):
        self.image, self.symbols, self.labels = resident_fixture()

    def inspect(self, image=None, symbols=None):
        return L.inspect_current_consumers(self.image if image is None else image,
            self.symbols if symbols is None else symbols, require_resident=True)

    def mutate(self, at, raw):
        image = bytearray(self.image)
        image[L.A.pc(at):L.A.pc(at)+len(raw)] = raw
        return bytes(image)

    def test_high_bank_code_and_twenty_native_hooks_are_read_back(self):
        observed = self.inspect()
        regions = {row['label']: row for row in observed['regions']}
        self.assertEqual(regions['Lyra_ResidentAtlasCode']['snes'], [0xF88000, 0xF88400])
        self.assertEqual(regions['ResidentResourceCode']['snes'], [0xF88600, 0xF886FB])
        hooks = {row['snes']: row['payload_hex'] for row in observed['fixed_hooks']}
        self.assertEqual(len({row[0] for row in WORD_HOOKS}), 20)
        for at, suffix, padding in WORD_HOOKS:
            self.assertEqual(hooks[at], (b'\x22'+self.labels['Lyra_Resident'+suffix].to_bytes(3, 'little')
                + b'\xEA'*padding).hex())
        self.assertEqual(sum(row['label'].startswith('ResidentCall_') for row in observed['source_calls']), 15)

    def test_every_native_hook_target_and_full_padding_are_mandatory(self):
        for at, suffix, padding in WORD_HOOKS:
            with self.subTest(site=hex(at)):
                with self.assertRaisesRegex(ValueError, 'Current active hook differs'):
                    self.inspect(self.mutate(at, b'\x22'+(self.labels['Lyra_Resident'+suffix]+1).to_bytes(3, 'little')))
                if padding:
                    with self.assertRaisesRegex(ValueError, 'Current active hook differs'):
                        self.inspect(self.mutate(at+4, b'\x00'))

    def test_missing_symbols_and_partial_resident_families_refuse(self):
        for name in ('Lyra_ResidentMutable3_End', 'ResidentAnimationStage', 'ResidentResourceCodeEnd',
                     'ResidentGraphicsResetMainCache', 'SharedGraphicsStageNativeMain',
                     'Lyra_ResidentIceRodWord_End', 'LyraCall_IceRodWord',
                     'LyraHost_IceRodDmaEnd'):
            symbols = b'\n'.join(row for row in self.symbols.splitlines() if not row.endswith(('Oracle_'+name).encode()))+b'\n'
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Missing current consumer symbol'):
                self.inspect(symbols=symbols)

    def test_old_compiled_consumers_remain_accepted_only_without_resident_requirement(self):
        image, symbols = consumer_fixture(bytes(0x400000), 0xE0C000)
        self.assertEqual(L.inspect_current_consumers(image, symbols)['kind'], 'lyra.current_compiled_consumers.v1')
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_COMPILED_BINDING_REQUIRED'):
            L.inspect_current_consumers(image, symbols, require_resident=True)
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SELECTION_INVALID'):
            L.inspect_current_consumers(image, symbols, require_resident=1)

    def test_resource_call_bypass_or_duplicate_refuses(self):
        targets = ('ResidentAnimationForceTransition', 'ResidentAnimationDecompress',
                   'ResidentGraphicsResetMainCache', 'ResidentAnimationStage', 'SharedGraphicsStageNativeMain')
        observed = self.inspect()
        for target in targets:
            row = next(row for row in observed['source_calls'] if row['label'].startswith('ResidentCall_')
                       and row['target'] == target)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_RESOURCE_CALL_UNBOUND'):
                self.inspect(self.mutate(row['snes'], b'\xEA'*4))
        start = self.labels['CheckForChangeGraphicsNormalLoad']
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_RESOURCE_CALL_UNBOUND'):
            self.inspect(self.mutate(start+8, b'\x22'+self.labels['ResidentAnimationStage'].to_bytes(3, 'little')))

    def test_native_decompressor_and_animation_destinations_are_mandatory(self):
        for label, error in (('ResidentAnimationDecompress', 'NATIVE_DECOMPRESSOR_CHANGED'),
                             ('ResidentAnimationDestinations', 'ANIMATION_DESTINATIONS_CHANGED')):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, error):
                self.inspect(self.mutate(self.labels[label], b'\x00'))

    def test_cache_reset_and_recovery_must_share_all_four_bytes(self):
        start = self.labels['ResidentGraphicsResetMainCache']
        for offset in (0, 9, 13, 17, 21, 28):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'MAIN_CACHE_RESET_CHANGED'):
                self.inspect(self.mutate(start+offset, b'\x00'))
        with self.assertRaisesRegex(ValueError, 'MAIN_CACHE_RECOVERY_CHANGED'):
            self.inspect(self.mutate(self.labels['ResolveCustomGraphicsTransitionSheet']+1, b'\x21'))
        for name in ('InvalidateCustomGraphicsCache', 'SelectCustomGraphicsTransitionSource',
                     'SelectShipIncrementalGraphicsSource'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'GRAPHICS_CALLBACK_UNBOUND'):
                self.inspect(self.mutate(self.labels[name], b'\xEA'))

    def test_ice_rod_body_call_dma_and_native_entry_are_read_back(self):
        observed = self.inspect()
        regions = {row['label']: row for row in observed['regions']}
        self.assertEqual(regions['ResidentHost_IceRod']['snes'], [0x0EFBA0, 0x0EFC70])
        self.assertEqual(regions['ResidentHost_IceRodDma']['snes'], [0x0EFD00, 0x0EFD21])
        calls = [row for row in observed['source_calls'] if row['label'] == 'LyraCall_IceRodWord']
        self.assertEqual(calls, [dict(label='LyraCall_IceRodWord', snes=0x0EFC43,
            target='Lyra_ResidentIceRodWord', payload_hex=(b'\x22'
                + self.labels['Lyra_ResidentIceRodWord'].to_bytes(3, 'little')).hex())])
        hooks = {row['snes']: row['payload_hex'] for row in observed['fixed_hooks']}
        self.assertEqual(hooks[0x088A5D], '22a0fb0e')

    def test_ice_rod_old_fill_wrong_call_and_protocol_mutations_refuse(self):
        for at, replacement in (
                (0x0EFC43, bytes.fromhex('a9831dea')),  # Old raw appearance.
                (0x0EFC43, b'\xEA'*4),
                (0x0EFC44, (self.labels['Lyra_ResidentIceRodWord']+1).to_bytes(3, 'little')),
                (0x0EFC06, b'\xB8'),  # Semantic tile identity.
                (0x0EFC47, b'\xEA'),  # First payload store.
                (0x0EFC4B, b'\xEA'),  # Second payload store.
                (0x0EFC4F, b'\xEA'),  # First DMA call.
                (0x0EFC58, b'\x18'),  # Carry-sensitive ADC row step.
                (0x0EFC5E, b'\xEA')):  # Second DMA call.
            with self.subTest(site=hex(at)), self.assertRaisesRegex(
                    ValueError, 'CURRENT_RESIDENT_ICE_ROD_BODY_CHANGED'):
                self.inspect(self.mutate(at, replacement))
        for at in (0x0EFD00, 0x0EFD0E, 0x0EFD14, 0x0EFD1D):
            with self.subTest(dma=hex(at)), self.assertRaisesRegex(
                    ValueError, 'CURRENT_RESIDENT_ICE_ROD_DMA_CHANGED'):
                self.inspect(self.mutate(at, b'\x00'))
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_ICE_ROD_ENTRY_CHANGED'):
            self.inspect(self.mutate(0x088A5D, b'\xEA'))

    def test_ice_rod_call_body_dma_and_helper_extents_refuse(self):
        for name, value, error in (
                ('LyraCall_IceRodWord', 0x0EFC42, 'ICE_ROD_HOST_EXTENT'),
                ('LyraCall_IceRodWord_End', 0x0EFC46, 'ICE_ROD_HOST_EXTENT'),
                ('LyraHost_IceRodEnd', 0x0EFC81, 'ICE_ROD_HOST_EXTENT'),
                ('LyraHost_IceRodDmaEnd', 0x0EFD22, 'ICE_ROD_DMA_EXTENT'),
                ('Lyra_ResidentIceRodWord_End', 0xF88401, 'HELPER_OUTSIDE_CODE')):
            original = f'{self.labels[name]>>16:02X}:{self.labels[name]&65535:04X} Oracle_{name}'.encode()
            changed = f'{value>>16:02X}:{value&65535:04X} Oracle_{name}'.encode()
            with self.subTest(symbol=name), self.assertRaisesRegex(ValueError, error):
                self.inspect(symbols=self.symbols.replace(original, changed))

    def test_changed_code_is_preserved_in_the_reviewed_snapshot(self):
        original = self.inspect()
        for name, offset in (('Lyra_ResidentAtlasCodeStart', 0), ('ResidentResourceCodeStart', 0x10),
                             ('SharedGraphicsRuntimeStart', 0x100),
                             ('ResolveCustomGraphicsTransitionSheet', 0x20)):
            with self.subTest(name=name):
                changed = self.inspect(self.mutate(self.labels[name]+offset, b'\x00'))
                self.assertNotEqual(changed['regions'], original['regions'])


class ResidentIceRodShapeTest(unittest.TestCase):
    def setUp(self):
        self.plan = dict(areas=[dict(maps=[0xB0, 0xB1], remaps=[
            dict(map_id=0xB1, tile16_id=0xB7, quadrant=quadrant,
                 source_word=0x1D83, target_word=0) for quadrant in range(4)])])

    def check(self, plan=None):
        return L.require_current_resident_ice_rod_rows(self.plan if plan is None else plan)

    def test_uniform_source_and_zero_packed_word_qualify_with_dry_page_absent(self):
        self.assertEqual(self.check(), [dict(map_id=0xB1, target_word=0)])
        self.plan['areas'][0]['remaps'] = []
        self.assertEqual(self.check(), [])

    def test_nonuniform_source_or_packed_row_refuses(self):
        for field, value, error in (
                ('source_word', 0x1D82, 'SOURCE_SHAPE_UNSUPPORTED'),
                ('target_word', 1, 'PACKED_SHAPE_UNSUPPORTED')):
            plan = copy.deepcopy(self.plan)
            plan['areas'][0]['remaps'][3][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                self.check(plan)

    def test_missing_and_duplicate_quadrants_refuse(self):
        plan = copy.deepcopy(self.plan)
        plan['areas'][0]['remaps'].pop()
        with self.assertRaisesRegex(ValueError, 'PACKED_SHAPE_UNSUPPORTED'):
            self.check(plan)
        self.plan['areas'][0]['remaps'].append(dict(self.plan['areas'][0]['remaps'][0]))
        with self.assertRaisesRegex(ValueError, 'ROW_DUPLICATE'):
            self.check()

    def test_invalid_types_ranges_and_page_ownership_refuse(self):
        for field, value in (('map_id', True), ('map_id', 0xB8), ('quadrant', True),
                             ('quadrant', 4), ('tile16_id', True),
                             ('source_word', True), ('target_word', True),
                             ('target_word', -1), ('target_word', 0x10000)):
            plan = copy.deepcopy(self.plan)
            plan['areas'][0]['remaps'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                    ValueError, 'ROW_INVALID'):
                self.check(plan)


if __name__ == '__main__':
    unittest.main()
