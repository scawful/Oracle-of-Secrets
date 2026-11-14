"""Pure input preparation/validation for the synthetic ASM syntax job.

No file/ROM writer or production fallback. The workflow owns its disposable
zero-filled input. Real builds continue through the normal saved-base producer.
"""
from pathlib import Path
import re
import sys
import tempfile

import seed_sky_award_preimages as preimages


def fixture_inputs(root):
    root = Path(root).resolve()
    source = (root/'Dungeons/d4_water_control.asm').read_text()
    guards, expected = [], set()
    for site, width in ((0x06c003, 4), (0x05d9f3, 6)):
        block = re.search(r'(?ms)^org \$' + f'{site:06X}' +
                          r'\b(.*?)(?=^org |\Z)', source)
        if not block:
            raise ValueError(f'missing synthetic D4 hook source {site:06X}')
        code = '\n'.join(preimages.strip_comment(line) for line in block.group(1).splitlines())
        terms = list(preimages._TERM.finditer(code))
        if len(terms) != len(preimages._READ.findall(code)):
            raise ValueError('unsupported D4 synthetic hook preimage guard')
        for term in terms:
            n, address, value = preimages.parse_term(term.group(), 'D4 synthetic hook')
            guards.append((0, n, address, value))
        pc = preimages.lorom_offset(site)
        expected.update(range(pc, pc + width))
    seed = preimages.guard_bytes(guards)
    if set(seed) != expected:
        raise ValueError('D4 synthetic preimages do not cover exactly the two guarded hooks')

    sys.path.insert(0, str(root/'Scripts/Rooms'))
    sys.path.insert(0, str(root/'Scripts/Generate'))
    import d4_water_rooms as producer
    import generate_water_gate_runtime_tables as runtime
    low = (root/'Data/Rooms/d4_water/25-low.bin').read_bytes()
    high = (root/'Data/Rooms/d4_water/25-high.bin').read_bytes()
    producer.validate_selected_pair(low, high)
    producer.validate_native_sources(root)
    stream = producer.parse_stream(low)
    objects = [runtime.decode_room_object(*record, layer)
               for layer, records in enumerate(stream.lists) for record in records]
    # Only the syntax fixture synthesizes these actors. Real base admission
    # requires actual saved21/04 records through read_hub_roles_strict.
    sprites = [runtime.RoomSprite(0x21, 7, 6, 0, 0),
               runtime.RoomSprite(0x04, 7, 15, 0, 0)]
    words = runtime.hub_contact_words(objects, sprites, (104, 112), (48, 104, 152, 120))
    with tempfile.TemporaryDirectory(prefix='d4-ci-include-') as temporary:
        include = Path(temporary)/'water_gate_runtime_tables.asm'
        runtime.write_asm(include, Path('test.sfc'), {}, {},
                          [0xc9, 0xd9], [0x124, 0x137, 0x135])
        runtime.write_hub_contacts(include, words)
        asm = include.read_bytes()
    files = {'Dungeons/generated/d4_water/25-low.bin': low,
             'Dungeons/generated/d4_water/25-high.bin': high,
             'Dungeons/generated/d4_water/25-low-collision.bin': b'\xff\xff',
             'Dungeons/generated/d4_water/25-high-collision.bin': b'\xff\xff',
             'Dungeons/generated/water_gate_runtime_tables.asm': asm}
    return seed, files


def validate_fixture_inputs(data, files, seed, expected):
    """Reject missing hook bytes, states or typed binding before direct Asar."""
    for offset, value in seed.items():
        if offset >= len(data) or data[offset] != value:
            raise ValueError(f'D4 synthetic hook preimage missing at PC{offset:06X}')
    for name, value in expected.items():
        if files.get(name) != value:
            raise ValueError(f'D4 synthetic state/type binding missing or changed: {name}')
