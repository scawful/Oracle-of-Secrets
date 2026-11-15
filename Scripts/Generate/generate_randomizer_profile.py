#!/usr/bin/env python3
"""Generate pinned Oracle interoperability data or inspect a ROM without writing it.

This is a receipt-domain contract, not a randomizer or a logic/placement certificate.
The authoring ROM is intentionally NOT admitted as a playable randomizer input.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '2bffad6ab6118301f125e49e414a4447260ac689'
B49_SOURCE = '313d2c2fbc578bc987c47337d28001fbb9a62c51'
B49_HASH = 'ed22c3434bd745ffabe18c76c69b5c6ed9dfcae3599491d45aea0051028b8e5e'
B50_SOURCE = '0a362d43fa80973bbe1bd25f6e9097476d61e388'
B50_HASH = 'acf7f1e0f3e3c51937f3f7c6a48fec78ffadc496b0114d1fd2924ff18a9304cc'
# Delivered b50 symbols Oracle_BombchuReceipt_CodeStart/CodeEnd ($2B:B50E..B95C).
B50_RECEIPT_CODE_PC = 0x15B50E
B50_RECEIPT_CODE_BYTES = 0x44E
AUTHORING_HASH = 'c91af2ee0713eefdb2c954230433a6af5c40fb36fc30b9f5eda79da70a311d06'
DEFAULT_OUTPUT = ROOT / 'Data/randomizer/oracle_compatibility.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned_rom(path, expected):
    data = path.read_bytes()
    if len(data) != 0x400000 or digest(data) != expected:
        raise ValueError('Unrecognized ROM: exact unheadered artifact SHA256 required')
    return data


def source_file(commit, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'])


def chest_binding(data, room):
    address = int.from_bytes(data[0xEBFB:0xEBFE], 'little')
    pc = ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)
    length = int.from_bytes(data[0xEBF6:0xEBF8], 'little')
    if pc != 0xE96E or length != 504:
        raise ValueError('Chest table contract changed')
    matches = [offset for offset in range(pc, pc + length, 3)
               if int.from_bytes(data[offset:offset + 2], 'little') & 0x7FFF == room]
    if not matches:
        raise ValueError('Required room has no chest record')
    offset = matches[0]
    return {'room_id': room, 'slot': 0, 'record_index': (offset - pc) // 3,
            'record_pc': offset, 'receipt_pc': offset + 2,
            'item_receipt': data[offset + 2],
            'big_chest': bool(data[offset + 1] & 0x80)}


def generate(b49_path, authoring_path, b50_path):
    b49 = pinned_rom(b49_path, B49_HASH)
    authoring = pinned_rom(authoring_path, AUTHORING_HASH)
    b50 = pinned_rom(b50_path, B50_HASH)
    current = source_file(SOURCE, 'Items/bombchu_receipt.asm').decode()
    old = source_file(B49_SOURCE, 'Items/bombchu_receipt.asm').decode()
    for text in (old, current):
        if 'BombchuReceipt_Id = $4C' not in text:
            raise ValueError('Bombchu source contract changed')
    if 'SwitchHookReceipt_Id = $4D' not in current or 'SwitchHookReceipt_Id' in old:
        raise ValueError('Switch Hook version boundary changed')
    menu = source_file(SOURCE, 'Menu/menu_select_item.asm').decode()
    actions = []
    switch_selection = None
    for line in menu.split('Menu_ItemIndex:', 1)[1].split('Menu_ItemIndex_End:', 1)[0].splitlines():
        code = line.split(';', 1)[0].strip()
        if code.startswith('db '):
            if 'Switch Hook' in line:
                switch_selection = len(actions)
            actions.extend(int(value, 16) for value in re.findall(r'\$([0-9A-Fa-f]+)', code))
    if switch_selection is None:
        raise ValueError('Switch Hook menu selection missing')
    masks = [int.from_bytes(b49[i:i + 2], 'little') for i in range(0x1900, 0x190C, 2)]
    if any(data[0x1900:0x190C] != b49[0x1900:0x190C] for data in (authoring, b50)):
        raise ValueError('RoomFlagMask differs across pinned artifacts')
    files = ['Menu/menu_select_item.asm', 'Menu/menu_draw.asm', 'Items/bombchu_receipt.asm', 'Core/sram.asm', 'Core/patches.asm',
             'Sprites/NPCs/maku_tree.asm', 'Sprites/NPCs/farore.asm',
             'Dungeons/custom_tag.asm', 'Docs/Technical/Dungeon_Tables_Expansion.md']
    profile = {
        'schema_version': 1,
        'purpose': 'Oracle of Secrets fan-randomizer interoperability; preserve creator attribution',
        'scope': {'logic_graph': False, 'beatability_certified': False,
                  'placement_safety_certified': False, 'rom_mutation_supported': False},
        'identifier_domains': {'item_receipt': 'Chest byte / Link_ReceiveItem ID',
            'item': 'Editor item catalog; not interchangeable with item_receipt',
            'menu_selection': 'Items menu selected index ($0202); not the Equipment page',
            'engine_action': 'Menu_ItemIndex result selecting native item-use handler',
            'dungeon_id': 'Runtime $040C; treasure ownership lookup indexes this value divided by two',
            'room_id': 'Underworld room number; all numeric JSON values are decimal'},
        'source_snapshot': {'commit': SOURCE, 'files_sha256': {
            f: digest(source_file(SOURCE, f)) for f in files}},
        'artifacts': [
            {'id': 'beta-b49', 'role': 'playable', 'version': '0.9.0', 'build': 49,
             'source_commit': B49_SOURCE, 'sha256': B49_HASH, 'bytes': len(b49),
             'base_sha256': 'c816b025ed86008e56759ace0a00356a851847ee01eb545d1778efdeb85bda8b',
             'receipt_reader_supported_ids': list(range(0x4D)),
             'unsupported_or_unknown_receipt_ids': list(range(0x4D, 256)),
             'native_receipt_tables': {name: {'pc': pc, 'bytes': size,
                 'sha256': digest(b49[pc:pc + size])} for name, pc, size in [
                     ('offset_y', 0x4836C, 76), ('offset_x', 0x483B8, 76),
                     ('gfx', 0x48404, 76), ('width', 0x48450, 76),
                     ('prop', 0x4849C, 76), ('sram_pointer', 0x484E8, 152),
                     ('value', 0x48580, 76), ('overflow', 0x3B528, 76),
                     ('message', 0x442DD, 152)]},
             'first_house_chest': chest_binding(b49, 0x104),
             'room_94_first_chest': chest_binding(b49, 0x94)},
            {'id': 'authoring-c91', 'role': 'authoring_only', 'sha256': AUTHORING_HASH,
             'bytes': len(authoring), 'source_snapshot_commit': SOURCE,
             'receipt_reader_supported_ids': [],
             'unsupported_or_unknown_receipt_ids': list(range(256)),
             'requires_compiled_successor': True,
             'first_house_chest': chest_binding(authoring, 0x104),
             'room_94_first_chest': chest_binding(authoring, 0x94)}],
        'profile_B': {'enable': ['d8_boss', 'd3_prison_sequence', 'minecart_cart_shutters',
                                'ocarina_song_tint', 'ow_aux_extension'],
                      'disable': ['kalyxo_docks_profile']},
        'receipts': {
            'native_preserved_range': [0, 75],
            'native_semantics': 'Preserved table rows; not an approved shuffle pool',
            'known': [
                {'id': 0x21, 'name': "Roc's Feather", 'ownership_wram': 0x7EF34D,
                 'value': 1, 'catalog_item_id': 0x15},
                {'id': 0x4C, 'name': 'Bombchu', 'ownership_wram': 0x7EF3AD,
                 'value': 1, 'message_id': 0x1BD, 'supported_artifacts': ['beta-b49']},
                {'id': 0x4D, 'name': 'Switch Hook', 'ownership_wram': 0x7EF3AE,
                 'value': 1, 'message_id': 0x21A,
                 'menu_selection_id': switch_selection,
                 'engine_action_id': actions[switch_selection],
                 'menu_binding_source': 'Menu/menu_select_item.asm:Menu_ItemIndex',
                 'supported_artifacts': [], 'source_capability_commit': SOURCE,
                 'status': 'Requires separately hash-qualified compiled successor; absent in b49'}]},
        'chest_persistence': {
            'table_pc': 0xE96E, 'record_bytes': 3, 'table_bytes': 504,
            'room_big_chest_mask': 0x8000, 'max_chests_and_locks_per_room': 6,
            'slot_masks': masks,
            'slot_masks_rom_pc': 0x1900,
            'slot_masks_rom_hex': b49[0x1900:0x190C].hex(),
            'slot_index_provenance': 'OpenItemChest $01EB7D ASL slot, $01EB7F TAY; $01EC3E ORA RoomFlagMask,Y',
            'live_room_flags_wram': 0x0402, 'saved_room_flags_base_wram': 0x7EF000,
            'saved_room_flags_stride': 2, 'house_room_id': 0x104,
            'house_saved_word_wram': 0x7EF208, 'house_first_chest_mask': masks[0],
            'requirements': ['Preserve chest-object and room-matching record order.',
                'Preserve slot flags across exit/re-entry and actual Save/cold load.',
                'Do not clear house chest flags as part of NPC/story initialization.',
                'Do not use slot 5 in a room with two key sprites.',
                'Do not shuffle stale records without matching chest objects.']},
        'protected_invariants': [
            {'kind': 'source_owned_receipt', 'source': 'Core/patches.asm',
             'receipt_pc': 0xE9E8, 'item_receipt': 0x39, 'room_id': 0x73},
            {'kind': 'source_owned_receipt', 'source': 'Core/patches.asm',
             'receipt_pc': 0xE9F7, 'item_receipt': 0x38, 'room_id': 0x7A},
            {'kind': 'scripted_reward_and_story', 'source': 'Sprites/NPCs/maku_tree.asm',
             'item_receipt': 0x3E, 'quest_wram': 0x7EF3D4,
             'first_meeting_assignment': 1, 'seed_bit': 2,
             'essences_wram': 0x7EF37A, 'seed_requires_essences': 255,
             'rule': 'Preserve first-meeting reward and quest transitions; starting items do not run this script.'},
            {'kind': 'story_transition', 'source': 'Sprites/NPCs/farore.asm',
             'game_state_wram': 0x7EF3C5, 'assigned_value': 2,
             'rule': 'Preserve event ordering; NPC identity or chest-reset cause is not established.'}],
        'protected_invariants_complete': False,
        'default_policy': 'Reject unrecognized ROMs and receipt IDs; unlisted scripted rewards/story edits require review.'}


    # Native rows remain separate from the compiled $4C/$4D reader extension.
    # Exact whole-ROM admission binds these fingerprints to this release only.
    profile['artifacts'].append({
        'id': 'beta-b50', 'role': 'playable', 'version': '0.9.0', 'build': 50,
        'source_commit': B50_SOURCE, 'sha256': B50_HASH, 'bytes': len(b50),
        'base_sha256': AUTHORING_HASH,
        'receipt_reader_supported_ids': list(range(0x4E)),
        'unsupported_or_unknown_receipt_ids': list(range(0x4E, 256)),
        'native_receipt_tables': {name: {
            'pc': table['pc'], 'bytes': table['bytes'],
            'sha256': digest(b50[table['pc']:table['pc'] + table['bytes']])}
            for name, table in profile['artifacts'][0]['native_receipt_tables'].items()},
        'receipt_reader_extension': {
            'pc': B50_RECEIPT_CODE_PC, 'bytes': B50_RECEIPT_CODE_BYTES,
            'sha256': digest(b50[B50_RECEIPT_CODE_PC:
                                 B50_RECEIPT_CODE_PC + B50_RECEIPT_CODE_BYTES]),
            'source': 'Items/bombchu_receipt.asm',
            'source_sha256': digest(source_file(B50_SOURCE, 'Items/bombchu_receipt.asm')),
            'symbols': ['Oracle_BombchuReceipt_CodeStart', 'Oracle_BombchuReceipt_CodeEnd'],
            'supported_extension_ids': [0x4C, 0x4D]},
        'first_house_chest': chest_binding(b50, 0x104),
        'room_94_first_chest': chest_binding(b50, 0x94)})
    known = {item['id']: item for item in profile['receipts']['known']}
    known[0x4C]['supported_artifacts'].append('beta-b50')
    known[0x4D]['supported_artifacts'] = ['beta-b50']
    known[0x4D]['status'] = 'Qualified in beta-b50 only; absent in b49; authoring ROM is not playable'
    return profile


def inspect_rom(profile, path, receipt=None):
    data = path.read_bytes()
    matches = [a for a in profile['artifacts'] if a['sha256'] == digest(data)
               and a['bytes'] == len(data)]
    if len(matches) != 1:
        raise ValueError('Unrecognized ROM: no exact compatibility artifact')
    artifact = matches[0]
    if artifact['role'] != 'playable':
        raise ValueError('Authoring ROM is not an admitted playable randomizer input')
    if receipt is not None and receipt not in artifact['receipt_reader_supported_ids']:
        raise ValueError('Unsupported or unknown item_receipt for this exact ROM')
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--b49-rom', type=Path)
    parser.add_argument('--authoring-rom', type=Path)
    parser.add_argument('--b50-rom', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check-rom', type=Path)
    parser.add_argument('--receipt', type=lambda value: int(value, 0))
    args = parser.parse_args()
    try:
        if args.check_rom:
            print(json.dumps(inspect_rom(json.loads(args.output.read_text()), args.check_rom, args.receipt), indent=2))
        else:
            if not args.b49_rom or not args.authoring_rom or not args.b50_rom:
                parser.error('Generation requires --b49-rom, --authoring-rom and --b50-rom')
            args.output.write_text(json.dumps(generate(args.b49_rom, args.authoring_rom, args.b50_rom), indent=2) + '\n')
    except ValueError as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
