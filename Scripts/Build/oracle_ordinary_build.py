"""Explicit ordinary Save -> private Build -> Run bindings.

This route never adopts an old command-line receipt. It snapshots a genuine
current Save and an explicitly pinned command profile, runs the existing Build
in a private copy, and publishes only after owned completion and revalidation.
It grants no expanded-map policy, allocation, native proof or OS confinement.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import tempfile

import build_receipt as receipts

ESSENTIAL = frozenset(('flags', 'menu', 'overlap', 'hooks', 'assembly',
    'hooks_generation', 'manifest', 'symbol_export', 'water_tables', 'water_fill',
    'version_stamp', 'message_source', 'collision_source'))
REQUIRED = frozenset(('flags', 'menu', 'overlap', 'hooks', 'sprites'))
CHECK_NAMES = REQUIRED | {'analysis', 'smoke', 'annotations', 'source_sprite_sheets',
                         'snowpeak_sheet', 'menu_icon_sheets', 'joint_palette_source'}
GENERATED = frozenset(('Config/feature_flags.asm', 'Config/module_flags.asm',
    'Dungeons/generated/water_fill_table.asm', 'Dungeons/generated/water_gate_runtime_tables.asm'))
COMMANDS = frozenset(('Scripts/Build/oracle_ordinary_build.py',
    'Scripts/Build/build_receipt.py', 'Scripts/Build/build_rom.sh', 'Scripts/Build/build_checks.sh',
    'Scripts/Build/lyra_build_selection.py', 'Scripts/Build/lyra_macos_process_group.py',
    'Scripts/Build/lyra_process_containment.py', 'Scripts/Mesen2/yaze_dedicated_session.py',
    'Scripts/Mesen2/yaze_dedicated_profile.py', 'Scripts/Mesen2/mesen2_launch_instance.sh'))
SUCCESS_KEYS = {'kind', 'project', 'project_id', 'engine', 'generation', 'operation_id',
    'build_id', 'profile', 'save_receipt', 'save_context', 'base_rom', 'source_snapshot',
    'build_root', 'build_receipt', 'candidate'}


def require(condition, message):
    if not condition:
        raise ValueError('Ordinary Build: ' + message)


def canonical(value, *, directory=False, exists=True):
    require(type(value) is str and value and '\0' not in value, 'invalid path')
    path = Path(value)
    require(path.is_absolute() and path == path.resolve(strict=exists)
            and not any(p.is_symlink() for p in (path, *path.parents)), 'path is not canonical: ' + value)
    if exists:
        require(path.is_dir() if directory else path.is_file(), 'wrong path kind: ' + value)
    return path


def read_file(path, limit=128 * 1024 * 1024):
    path = canonical(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        # Apple system executables can be hard-linked (git is one example).
        # These bindings only read; private outputs use O_EXCL and never alias
        # them. Stable inode/metadata plus exact bytes cover this read boundary.
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
                'expected a bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink,
                              s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(identity(before) == identity(os.fstat(fd)) == identity(path.lstat())
                and len(raw) == before.st_size, 'file changed during read: ' + str(path))
        return raw
    finally:
        os.close(fd)


def binding(path):
    raw = read_file(path)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def bound(row, expected=None, *, extra=False):
    keys = {'path', 'sha256', 'size'}
    require(type(row) is dict and (keys <= set(row) if extra else set(row) == keys)
            and type(row.get('size')) is int and row['size'] >= 0
            and type(row.get('sha256')) is str
            and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'invalid file binding')
    path = canonical(row['path'])
    require(expected is None or path == expected, 'bound path differs: ' + str(path))
    raw = read_file(path)
    require(len(raw) == row['size'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
            'bound file changed: ' + str(path))
    return raw


def json_bytes(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON field: ' + key)
            result[key] = value
        return result
    require(len(raw) <= 32 * 1024 * 1024, 'metadata too large')
    result = json.loads(raw, object_pairs_hook=unique,
                        parse_constant=lambda _: require(False, 'nonfinite JSON number'))
    require(type(result) is dict, 'metadata must be an object')
    return result


def project_inputs(project, engine):
    project = canonical(str(project)); engine = canonical(str(engine), directory=True)
    config = configparser.ConfigParser(interpolation=None, comment_prefixes=('#',), strict=True)
    config.read_string(read_file(project).decode('utf-8-sig'))
    require(not config.defaults(), 'project defaults are not supported')
    project_id = config.get('project', 'project_id', fallback='').strip()
    require(project_id and len(project_id) <= 256, 'saved project ID is missing')
    require(not config.get('files', 'lyra_terrain_file', fallback='').strip()
            and not config.get('files', 'lyra_build_request_file', fallback='').strip()
            and not os.path.lexists(str(project) + '.lyra-build-latest.json'),
            'expanded project cannot use the ordinary route')
    def resolve_field(name, directory=False):
        value = config.get('files', name, fallback='').strip()
        require(bool(value), 'saved project lacks ' + name)
        path = Path(value)
        if not path.is_absolute():
            path = project.parent / path
        return canonical(str(path.resolve(strict=True)), directory=directory)
    base = resolve_field('rom_filename')
    folder = resolve_field('code_folder', directory=True)
    roots = [p for p in (folder, *folder.parents) if (p / 'Oracle_main.asm').is_file()]
    require(roots and roots[0] == engine, 'saved project code folder selects another engine')
    return project_id, base, folder


def validate_save(project, engine, receipt_path, context_path):
    """Authenticate current native Save artifacts; no Lyra producer policy."""
    project, engine = Path(project), Path(engine)
    project_id, base, _ = project_inputs(project, engine)
    require(isinstance(receipt_path, (str, Path)) and bool(str(receipt_path))
            and isinstance(context_path, (str, Path)) and bool(str(context_path)),
            'current native Save receipt/context is missing; Save Project first')
    try:
        receipt_binding, context_binding = binding(Path(receipt_path)), binding(Path(context_path))
    except (FileNotFoundError, IsADirectoryError, TypeError) as error:
        raise ValueError('Ordinary Build: current native Save receipt/context is missing; Save Project first') from error
    require(Path(receipt_path) == Path(str(project) + '.native-save.json'), 'Save receipt path differs')
    saved, context = json_bytes(bound(receipt_binding)), json_bytes(bound(context_binding))
    require(set(saved) == {'kind', 'generation', 'operation_id', 'operation', 'receipt_path',
                          'bindings_complete', 'binding_errors', 'artifacts'}
            and saved.get('kind') == 'yaze.native_save.v1'
            and type(saved.get('generation')) is int and saved['generation'] > 0
            and type(saved.get('operation_id')) is str and saved['operation_id']
            and saved.get('operation') in ('save', 'save_as')
            and saved.get('receipt_path') == str(receipt_path)
            and saved.get('bindings_complete') is True and saved.get('binding_errors') == [],
            'a complete current native Save receipt is required; Save Project first')
    require(set(context) == {'kind', 'editing_source_path', 'state', 'project_path', 'rom_path',
                             'producer', 'native_commit'}
            and context['kind'] == 'yaze.native_save_context.v1' and context['state'] == 'committed'
            and context['project_path'] == str(project) and context['rom_path'] == str(base)
            and type(context['native_commit']) is dict
            and type(context['native_commit'].get('generation')) is int
            and context['native_commit'] == {'receipt_path': str(receipt_path),
                'generation': saved['generation'], 'operation_id': saved['operation_id']},
            'native Save context does not join the current project and receipt')
    # Save As can preserve a different editing origin. The editor owns context
    # path derivation; the supervisor consumes its explicit bound path, and Run
    # rechecks it against that live editor authority.
    canonical(context['editing_source_path'], exists=False)
    artifacts = saved.get('artifacts')
    require(type(artifacts) is list and 0 < len(artifacts) <= 256, 'Save artifacts missing')
    roles = {}
    for item in artifacts:
        require(type(item) is dict and set(item) == {'role', 'path', 'sha256', 'bytes'}
                and type(item['role']) is str and item['role'], 'invalid Save artifact')
        row = {'path': item['path'], 'sha256': item['sha256'], 'size': item['bytes']}
        bound(row)
        require(item['role'] not in roles, 'duplicate Save artifact role')
        roles[item['role']] = [item]
    for role, path in (('project', project), ('rom', base)):
        require(len(roles.get(role, [])) == 1 and roles[role][0]['path'] == str(path),
                'Save lacks exact ' + role + ' binding')
    require(len(roles.get('producer', [])) == 1 and context['producer'] == roles['producer'][0],
            'recorded Save producer differs')
    # The recorded producer may differ from the current editor binary. Its
    # actual bytes are rechecked above; no replacement provenance is invented.
    bound(receipt_binding); bound(context_binding)
    return {'project': binding(project), 'project_id': project_id, 'engine': str(engine),
            'generation': saved['generation'], 'operation_id': saved['operation_id'],
            'save_receipt': receipt_binding, 'save_context': context_binding,
            'base_rom': binding(base)}


def source_map(engine):
    """Receipt's conservative source scope plus root Python/shell commands."""
    engine = canonical(str(engine), directory=True)
    candidates = {p for pattern in (*receipts.ROOT_GLOBS, '*.py', '*.sh') for p in engine.glob(pattern)}
    for name in receipts.SOURCE_DIRS:
        directory = engine / name
        if directory.exists():
            canonical(str(directory), directory=True)
            candidates.update(directory.rglob('*'))
    result = {}
    for path in sorted(candidates):
        relative = path.relative_to(engine)
        if any(part in receipts.EXCLUDED_DIRS for part in relative.parts):
            continue
        if tuple(p.casefold() for p in relative.parts[:2]) == ('tests', 'screenshots'):
            continue
        require(not path.is_symlink(), 'source contains symlink: ' + str(relative))
        if path.is_dir() or path.suffix.lower() in receipts.EXCLUDED_SUFFIXES:
            continue
        row = binding(path)
        result[relative.as_posix()] = {'sha256': row['sha256'], 'size': row['size'],
                                     'mode': stat.S_IMODE(path.stat().st_mode)}
    require('Oracle_main.asm' in result, 'source snapshot lacks Oracle_main.asm')
    return result


def validate_map(rows):
    require(type(rows) is dict and rows, 'invalid source map')
    for name, row in rows.items():
        require(type(name) is str and name and not Path(name).is_absolute()
                and '..' not in Path(name).parts and Path(name).as_posix() == name
                and '\\' not in name and type(row) is dict
                and set(row) == {'sha256', 'size', 'mode'}
                and type(row['size']) is int and row['size'] >= 0
                and type(row['mode']) is int and 0 <= row['mode'] <= 0o777
                and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                'invalid source map entry')


def load_profile(profile_binding, *, project, engine, executing=False):
    raw = bound(profile_binding, Path(str(project) + '.oracle-build-profile.json'))
    profile = json_bytes(raw)
    require(set(profile) == {'kind', 'project', 'engine', 'source_inventory', 'tools', 'path',
                             'required_checks', 'timeout'}
            and profile['kind'] == 'oracle.macos_build_profile.v1'
            and profile['project'] == str(project) and profile['engine'] == str(engine), 'profile identity differs')
    require(type(profile['timeout']) in (int, float) and math.isfinite(profile['timeout'])
            and 0 < profile['timeout'] <= 3600, 'invalid Build timeout')
    current = source_map(engine)
    commands = {name: row for name, row in current.items() if Path(name).suffix in ('.py', '.sh')}
    inventory = json_bytes(bound(profile['source_inventory']))
    require(set(inventory) == {'kind', 'engine', 'files'}
            and inventory['kind'] == 'oracle.command_source_inventory.v1'
            and inventory['engine'] == str(engine), 'command inventory identity differs')
    validate_map(inventory['files'])
    require(inventory['files'] == commands and COMMANDS <= set(commands),
            'command inventory is incomplete or changed')
    tools = profile['tools']
    require(type(tools) is dict and set(tools) == {'python', 'bash', 'asar', 'z3ed', 'git', 'analyzer'},
            'tool set differs')
    for name, tool in tools.items():
        if name == 'analyzer' and tool is None:
            continue
        bound(tool)
        require(name == 'analyzer' or os.access(tool['path'], os.X_OK), 'tool is not executable: ' + name)
    require(type(profile['path']) is list and profile['path'], 'missing command search path')
    for path in profile['path']:
        canonical(path, directory=True)
    search = os.pathsep.join(profile['path'])
    for command, name in (('python3', 'python'), ('git', 'git')):
        found = shutil.which(command, path=search)
        require(found and Path(found).resolve(strict=True) == Path(tools[name]['path']),
                'PATH selects a different ' + command)
    for command in ('basename', 'dirname', 'mkdir', 'mktemp', 'cp', 'mv', 'rm', 'date', 'cat'):
        found, system = shutil.which(command, path=search), shutil.which(command, path='/usr/bin:/bin:/usr/sbin:/sbin')
        require(found and system and Path(found).resolve() == Path(system).resolve(),
                'PATH shadows system helper ' + command)
    checks = profile['required_checks']
    require(type(checks) is list and all(type(x) is str for x in checks)
            and len(checks) == len(set(checks)) and REQUIRED <= set(checks) <= CHECK_NAMES
            and 'smoke' not in checks and ('analysis' not in checks or tools['analyzer'] is not None),
            'required checks are missing, unknown or unavailable')
    if executing:
        require(Path(tools['python']['path']) == Path(sys.executable).resolve(strict=True),
                'supervisor interpreter differs from profile')
        for name in ('oracle_ordinary_build.py', 'lyra_macos_process_group.py',
                     'lyra_process_containment.py', 'build_receipt.py', 'lyra_build_selection.py'):
            require(read_file(Path(engine) / 'Scripts/Build' / name) == read_file(Path(__file__).with_name(name)),
                    'executing command source differs from selected engine: ' + name)
    bound(profile_binding)
    return profile


def loaded_identity(raw):
    """Pinned normal-LoROM loader's 4 KiB zero alignment, without file padding.

    Header scoring mirrors BaseCartridge::GetHeaderScore/LoadRom. Reject other
    mappers, copier-header selection and coprocessors rather than guessing their
    transformations. This is a loaded-byte identity, not a mirroring assertion.
    """
    require(type(raw) is bytes and 0x200000 <= len(raw) <= 0x400000, 'ordinary output must be 2..4 MiB')
    # BaseCartridge::Create dispatches this exact 27-byte content signature to
    # LoadSpc before header scoring; that path replaces PRG with a 32 KiB stub.
    require(not raw.startswith(b'SNES-SPC700 Sound File Data'),
            'SPC content is not an ordinary cartridge')
    def score(address):
        if len(raw) < address + 0x7fff:
            return -1
        mode = raw[address + 0x7fd5] & ~0x10
        value = int((mode in (0x20, 0x22) and address < 0x8000)
                    or (mode in (0x21, 0x25) and address >= 0x8000))
        value += int(raw[address + 0x7fd6] < 8) + int(raw[address + 0x7fd7] < 0x10) + int(raw[address + 0x7fd8] < 8)
        word = lambda off: int.from_bytes(raw[address + off:address + off + 2], 'little')
        complement, checksum, reset = word(0x7fdc), word(0x7fde), word(0x7ffc)
        if complement and checksum and complement + checksum == 0xffff:
            value += 8
        if reset < 0x8000:
            return -1
        opcode = raw[address + (reset & 0x7fff)]
        if opcode in (0x18, 0x78, 0x4c, 0x5c, 0x20, 0x22, 0x9c): value += 8
        elif opcode in (0xc2, 0xe2, 0xa9, 0xa2, 0xa0): value += 4
        elif opcode in (0, 0xff, 0xcc): value -= 8
        return max(0, value)
    scores = [score(a) for a in (0, 0x200, 0x8000, 0x8200, 0x408000, 0x408200)]
    require(scores[0] >= 0 and all(scores[0] > value for value in scores[1:])
            and raw[0x7fd5] in (0x20, 0x30) and raw[0x7fd6] in (0, 1, 2),
            'unsupported or ambiguous ordinary cartridge format')
    size = (len(raw) + 0xfff) & ~0xfff
    digest = hashlib.sha1(raw)
    digest.update(bytes(size - len(raw)))
    return {'size': size, 'sha1': digest.hexdigest()}


def _receipt_map(rows):
    return {name: {k: row[k] for k in ('sha256', 'size')} for name, row in rows.items()
            if len(Path(name).parts) > 1 or any(Path(name).match(p) for p in receipts.ROOT_GLOBS)}


def validate_receipt(receipt_binding, *, profile, base, root, candidate, selected, copied, final):
    receipt = json_bytes(bound(receipt_binding, root.parent / 'oos168x.build.json'))
    finish = receipt.get('finish')
    require(type(receipt.get('schema_version')) is int and receipt['schema_version'] == 1
            and receipt.get('root') == str(root) and receipt.get('version') == '168'
            and receipt.get('state') in ('completed', 'completed_with_gaps')
            and receipt.get('source_snapshot_status') == 'captured' and type(finish) is dict
            and type(finish.get('exit_code')) is int and finish['exit_code'] == 0
            and type(finish.get('supplied_exit_code')) is int and finish['supplied_exit_code'] == 0
            and finish.get('stage') == 'complete' and finish.get('required_gaps') == [], 'Build did not complete')
    require(not any(str(key).startswith('lyra') for key in receipt), 'expanded attempt cannot be ordinary')
    checks = receipt.get('checks'); names = set()
    require(type(checks) is list, 'checks missing')
    for row in checks:
        require(type(row) is dict and type(row.get('name')) is str and row['name']
                and row['name'] not in names and not row['name'].startswith('lyra')
                and type(row.get('required')) is bool
                and row.get('status') in ('passed', 'failed', 'skipped', 'unavailable'), 'invalid or duplicate check')
        names.add(row['name'])
        if row['required'] or row['name'] in ESSENTIAL | set(profile['required_checks']):
            require(row['required'] is True and row['status'] == 'passed'
                    and type(row.get('exit_code')) is int and row['exit_code'] == 0,
                    'required check did not pass: ' + row['name'])
    require(ESSENTIAL | set(profile['required_checks']) <= names, 'required check is missing')
    saved_copy = root.parent / 'saved-input.sfc'
    bound(base)
    bound(receipt.get('base_rom'), saved_copy)
    require(all(receipt['base_rom'][key] == base[key] for key in ('sha256', 'size')), 'private base copy differs')
    artifacts = receipt.get('artifacts')
    require(type(artifacts) is dict and {'output_rom', 'symbols', 'hooks', 'manifest', 'mlb', 'water_source_rom'} <= set(artifacts),
            'Build artifacts missing')
    fixed = {'output_rom': root/'Roms/oos168x.sfc', 'symbols': root/'Roms/oos168x.sym',
             'hooks': root/'Roms/hooks.json', 'manifest': root/'Roms/hack_manifest.json',
             'mlb': root/'Roms/oos168x.mlb', 'water_source_rom': saved_copy}
    for name, row in artifacts.items():
        require(not name.startswith('lyra'), 'expanded artifact cannot be ordinary')
        bound(row, fixed.get(name), extra=True)
        require(Path(row['path']).is_relative_to(root.parent), 'artifact escapes private generation')
    require(all(artifacts['output_rom'][k] == candidate[k] for k in ('path', 'sha256', 'size')),
            'receipt output differs')
    tools = receipt.get('tools')
    require(type(tools) is dict and {'assembler', 'python', 'z3ed'} <= set(tools), 'recorded tools missing')
    for name, row in tools.items():
        bound(row, extra=True)
        expected = profile['tools'].get('asar' if name == 'assembler' else name)
        require(expected is not None and all(row[k] == expected[k] for k in ('path', 'sha256', 'size')),
                'recorded tool differs: ' + name)
    for rows in (selected, copied, final): validate_map(rows)
    require(selected == copied, 'private source copy differs')
    pre = receipt.get('snapshots', {}).get('pre_assembly')
    require(type(pre) is dict and pre.get('method') == 'conservative_source_tree_v1'
            and type(pre.get('files')) is dict, 'pre-assembly source snapshot missing')
    files = pre['files']
    require(type(pre.get('file_count')) is int and pre['file_count'] == len(files)
            and pre.get('aggregate_sha256') == hashlib.sha256(json.dumps(files, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest(), 'pre-assembly aggregate differs')
    initial = _receipt_map(copied)
    changes = {p for p in set(initial) | set(files) if initial.get(p) != files.get(p)}
    changes |= {p for p in set(copied) | set(final) if copied.get(p) != final.get(p)}
    require(changes <= GENERATED, 'unexpected source changes: ' + ', '.join(sorted(changes - GENERATED)))
    for name, row in files.items():
        require(type(row) is dict and set(row) == {'sha256', 'size'}
                and type(row['size']) is int and row['size'] >= 0
                and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'bad receipt source row')
    for name in receipts.RESTORABLE_FLAGS:
        recorded = receipt.get('initial_profile', {}).get('files', {}).get(name, {})
        expected = initial.get(name)
        require((expected is None and recorded.get('status') == 'unavailable') or
                (expected is not None and all(recorded.get(k) == v for k, v in expected.items())
                 and recorded.get('path') == str(root/name)), 'initial flags differ')
    require(receipts.verify_source_identity(receipt, Path(receipt_binding['path'])) is None,
            'source changed after assembly or flags were not restored')
    bound(receipt_binding)
    return sorted(changes)


def validate_selector(selector_binding, *, project, engine, context_path=None):
    project, engine = canonical(str(project)), canonical(str(engine), directory=True)
    selector = json_bytes(bound(selector_binding, Path(str(project) + '.oracle-build-latest.json')))
    require(set(selector) == SUCCESS_KEYS and selector['kind'] == 'oracle.latest_success.v1'
            and selector['engine'] == str(engine) and type(selector['build_id']) is str
            and re.fullmatch('[0-9a-f]{32}', selector['build_id'])
            and type(selector['generation']) is int and selector['generation'] > 0,
            'successful ordinary selector missing')
    for name in ('project', 'save_receipt', 'save_context', 'base_rom'):
        bound(selector[name])
    saved = validate_save(project, engine, selector['save_receipt']['path'], selector['save_context']['path'])
    require(all(selector[key] == value for key, value in saved.items()), 'Save or project changed since Build')
    require(context_path is None or selector['save_context']['path'] == str(context_path), 'editor Save context differs')
    generation = Path(str(project) + '.oracle-build-output') / ('oracle-' + selector['build_id'])
    root = canonical(selector['build_root'], directory=True)
    require(root == generation / 'engine', 'private generation differs')
    for directory in (generation.parent, generation):
        value = canonical(str(directory), directory=True).stat()
        require(value.st_uid == os.geteuid() and stat.S_IMODE(value.st_mode) == 0o700, 'generation is not private and owned')
    profile = load_profile(selector['profile'], project=project, engine=engine)
    snapshot = json_bytes(bound(selector['source_snapshot'], generation/'source-snapshot.json'))
    require(set(snapshot) == {'kind', 'engine', 'build_root', 'selected', 'copied', 'final', 'generated_changes'}
            and snapshot['kind'] == 'oracle.source_snapshot.v1' and snapshot['engine'] == str(engine)
            and snapshot['build_root'] == str(root), 'source snapshot identity differs')
    require(source_map(engine) == snapshot['selected'] and source_map(root) == snapshot['final'],
            'selected or copied source changed')
    raw = bound(selector['candidate'], root/'Roms/oos168x.sfc')
    loaded = loaded_identity(raw)
    changes = validate_receipt(selector['build_receipt'], profile=profile, base=selector['base_rom'],
        root=root, candidate=selector['candidate'], selected=snapshot['selected'],
        copied=snapshot['copied'], final=snapshot['final'])
    require(snapshot['generated_changes'] == changes, 'generated change inventory differs')
    bound(selector_binding)
    return selector, raw, loaded


def _write_new(path, raw, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    require(read_file(path) == raw, 'private write readback differs')


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def _replace(path, value, expected):
    require((read_file(path) if os.path.lexists(path) else None) == expected, 'selector changed before publication')
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_encoded(value)); stream.flush(); os.fsync(stream.fileno())
        require((read_file(path) if os.path.lexists(path) else None) == expected, 'selector changed during publication')
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent)
        finally: os.close(parent)
        require(read_file(path) == _encoded(value), 'selector readback differs')
    finally:
        temporary.unlink(missing_ok=True)


def ordinary_command(profile_binding, state_binding):
    """Recheck the fixed child graph in both supervisor and guardian."""
    state = json_bytes(bound(state_binding))
    require(set(state) == {'saved', 'profile', 'build_id', 'build_root', 'selected', 'copied'}
            and state['profile'] == profile_binding, 'prepared attempt shape differs')
    saved = state['saved']; project, engine = Path(saved['project']['path']), Path(saved['engine'])
    require(saved == validate_save(project, engine, saved['save_receipt']['path'], saved['save_context']['path']),
            'Save changed before child')
    profile = load_profile(profile_binding, project=project, engine=engine, executing=True)
    require(type(state['build_id']) is str and re.fullmatch('[0-9a-f]{32}', state['build_id']), 'invalid attempt ID')
    generation = Path(str(project) + '.oracle-build-output') / ('oracle-' + state['build_id'])
    root = canonical(state['build_root'], directory=True)
    require(root == generation/'engine' and Path(state_binding['path']) == generation/'attempt.json', 'attempt path differs')
    require(source_map(engine) == state['selected'] == state['copied'] == source_map(root), 'source changed before child')
    require(not (root/'Roms/oos168x.sfc').exists() and not (generation/'oos168x.build.json').exists(), 'attempt output already exists')
    require(binding(generation/'saved-input.sfc') == {**saved['base_rom'], 'path': str(generation/'saved-input.sfc')},
            'saved ROM copy differs')
    for name in ('home', 'tmp', 'backups'):
        value = canonical(str(generation/name), directory=True).stat()
        require(value.st_uid == os.geteuid() and stat.S_IMODE(value.st_mode) == 0o700, 'runtime directory not private')
    tools = profile['tools']
    env = {'PATH': os.pathsep.join(profile['path']), 'HOME': str(generation/'home'),
           'TMPDIR': str(generation/'tmp'), 'LANG': 'C', 'LC_ALL': 'C',
           'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'OOS_BASE_ROM': str(generation/'saved-input.sfc'),
           'OOS_BACKUP_ROOT': str(generation/'backups'),
           'OOS_BUILD_RECEIPT': str(generation/'oos168x.build.json'),
           'OOS_MANIFEST_ROOT': str(root), 'OOS_Z3ED_BIN': tools['z3ed']['path'],
           'ASAR_BIN': tools['asar']['path'], 'OOS_REQUIRE_CHECKS': ','.join(profile['required_checks'])}
    if tools['analyzer'] is None: env['SKIP_ANALYSIS'] = '1'
    else: env['OOS_ANALYZER'] = tools['analyzer']['path']
    return {'argv': [tools['bash']['path'], str(root/'Scripts/Build/build_rom.sh'), '168',
                     '--asar=' + tools['asar']['path'], '--skip-tests'],
            'cwd': str(root), 'timeout': profile['timeout'], 'environment': env,
            'ordinary': {'profile': profile_binding, 'state': state_binding}}


def supervise(project, engine, profile_binding, *, environment=None):
    """Run one fresh ordinary attempt; failed/uncertain attempts stay pending."""
    require(sys.platform == 'darwin', 'ordinary guardian requires macOS')
    require(all(hasattr(signal, name) for name in ('pthread_sigmask', 'sigpending')),
            'atomic completion requires POSIX signal masking')
    import lyra_build_selection as lifecycle
    import lyra_macos_process_group as guardian
    environment = dict(os.environ if environment is None else environment)
    project, engine = canonical(str(project)), canonical(str(engine), directory=True)
    profile = load_profile(profile_binding, project=project, engine=engine, executing=True)
    _, _, code_folder = project_inputs(project, engine)
    require(environment.get('YAZE_PROJECT_FILE') == str(project)
            and environment.get('YAZE_PROJECT_CODE_FOLDER') == str(code_folder),
            'editor project/engine environment differs')
    saved = validate_save(project, engine, environment.get('YAZE_NATIVE_SAVE_RECEIPT', ''),
                          environment.get('YAZE_NATIVE_SAVE_CONTEXT', ''))
    require(environment.get('YAZE_PROJECT_ROM') == saved['base_rom']['path'], 'editor ROM differs')
    session = lifecycle.BuildSession(project, engine, selected=False).begin()
    cancelled = [False]
    committed = [False]
    def cancel(*_):
        if not committed[0]:
            cancelled[0] = True
    previous = signal.signal(signal.SIGTERM, cancel)
    try:
        saved_again = validate_save(project, engine, saved['save_receipt']['path'], saved['save_context']['path'])
        require(saved_again == saved, 'Save changed while acquiring Build locks')
        parent = Path(str(project) + '.oracle-build-output')
        canonical(str(parent), directory=True, exists=False)
        require(not any(parent.is_relative_to(engine/name) for name in (*receipts.SOURCE_DIRS, 'Roms')),
                'private output cannot overlap selected source or Roms')
        if not parent.exists(): parent.mkdir(mode=0o700)
        info = parent.stat()
        require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700, 'output root not private')
        generation = parent/('oracle-' + session.build_id)
        generation.mkdir(mode=0o700)
        selector_path = Path(str(project) + '.oracle-build-latest.json')
        old = read_file(selector_path) if os.path.lexists(selector_path) else None
        if old is not None: _write_new(generation/'previous-selector.json', old)
        pending = {'kind': 'oracle.latest_pending.v1', 'project': str(project), 'build_id': session.build_id,
                   'generation': saved['generation'], 'operation_id': saved['operation_id']}
        _replace(selector_path, pending, old)
        root = generation/'engine'; root.mkdir(mode=0o700)
        selected = source_map(engine)
        for name, row in selected.items():
            destination = root/name; destination.parent.mkdir(parents=True, exist_ok=True)
            raw = read_file(engine/name)
            require(hashlib.sha256(raw).hexdigest() == row['sha256'] and len(raw) == row['size'], 'source changed during copy')
            _write_new(destination, raw, row['mode']); destination.chmod(row['mode'])
        copied = source_map(root)
        require(copied == selected == source_map(engine), 'source copy differs')
        _write_new(generation/'saved-input.sfc', bound(saved['base_rom']), 0o400)
        for name in ('home', 'tmp', 'backups'): (generation/name).mkdir(mode=0o700)
        state = {'saved': saved, 'profile': profile_binding, 'build_id': session.build_id,
                 'build_root': str(root), 'selected': selected, 'copied': copied}
        _write_new(generation/'attempt.json', _encoded(state))
        prepared = ordinary_command(profile_binding, binding(generation/'attempt.json'))
        require(not cancelled[0], 'Build cancelled before launch')
        result = session._run_prepared_child(lambda: guardian.run_ordinary_build(prepared))
        require(not result.timed_out and result.exit_code == 0, 'owned Build failed or timed out')
        require(not cancelled[0], 'Build cancelled before publication')
        final = source_map(root)
        candidate, receipt_binding = binding(root/'Roms/oos168x.sfc'), binding(generation/'oos168x.build.json')
        loaded_identity(bound(candidate))
        changes = validate_receipt(receipt_binding, profile=profile, base=saved['base_rom'], root=root,
            candidate=candidate, selected=selected, copied=copied, final=final)
        snapshot = {'kind': 'oracle.source_snapshot.v1', 'engine': str(engine), 'build_root': str(root),
                    'selected': selected, 'copied': copied, 'final': final, 'generated_changes': changes}
        _write_new(generation/'source-snapshot.json', _encoded(snapshot))
        success = {'kind': 'oracle.latest_success.v1', **saved, 'build_id': session.build_id,
                   'profile': profile_binding, 'source_snapshot': binding(generation/'source-snapshot.json'),
                   'build_root': str(root), 'build_receipt': receipt_binding, 'candidate': candidate}
        require(source_map(engine) == selected and validate_save(project, engine,
            saved['save_receipt']['path'], saved['save_context']['path']) == saved, 'original inputs changed')
        load_profile(profile_binding, project=project, engine=engine, executing=True)
        session._check_owned()
        require(not cancelled[0], 'Build cancelled during validation')
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try:
            try:
                require(not cancelled[0] and signal.SIGTERM not in signal.sigpending(),
                        'Build cancelled during publication')
                _replace(selector_path, success, _encoded(pending))
                require(not cancelled[0] and signal.SIGTERM not in signal.sigpending(),
                        'Build cancelled during publication')
            except BaseException:
                # Roll back only while both original sentinels are still ours.
                if read_file(selector_path) == _encoded(success):
                    _replace(selector_path, pending, _encoded(success))
                raise
            # The last pending-signal observation above is the completion
            # point. SIGTERM remains masked until this terminal state is set:
            # later delivery cannot turn committed success into cancellation.
            # In particular, never roll back after a new owner can acquire.
            committed[0] = True
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    finally:
        try:
            session.release()  # Uncertain child state deliberately retains both sentinels.
        finally:
            signal.signal(signal.SIGTERM, previous)
    require(committed[0], 'Build completion was not committed')
    return success


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--macos-profile', required=True, type=Path)
    parser.add_argument('--macos-profile-sha256', required=True)
    args = parser.parse_args(argv)
    profile_binding = binding(args.macos_profile)
    require(profile_binding['sha256'] == args.macos_profile_sha256, 'selected profile hash differs')
    supervise(args.project, args.engine, profile_binding)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
