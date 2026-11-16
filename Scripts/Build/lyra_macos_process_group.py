"""macOS guardians for fixtures and explicitly pinned automatic Build commands.

Process groups do not prevent escape. A production caller must supply a reviewed
command profile whose tools and child graph remain in-group. No default profile
is supplied; existing source, resource and allocation admission still applies.
"""
from __future__ import annotations

import os
from pathlib import Path
import configparser
import hashlib
import json
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time

from lyra_process_containment import ContainedResult, ContainmentUncertain, ContainmentUnavailable


def prepare_current_save_environment(project, *, producer_identity=None):
    """Read the existing Save/producer/policy bindings without running a tool.

    This is only the Save-derived part of a future Build environment. It does
    not choose Python, bash, an assembler, required checks or source admission.
    The normal transfer planner must revalidate these inputs before use.
    """
    import lyra_current_transfer as current
    selected = current.select_ordinary_transfer_inputs(
        project, producer_identity=producer_identity)
    return {'selection': selected, 'environment': {
        'YAZE_NATIVE_SAVE_CONTEXT': selected['save_context']['path'],
        'OOS_Z3ED_BIN': selected['verifier']['path'],
    }}


def prepare_oracle_build(argv, *, cwd, timeout, environment=None, profile=None):
    """Validate an explicit profile or retain the existing missing-profile refusal."""
    if profile is not None:
        return _prepare_profile_build(argv, cwd=cwd, timeout=timeout,
                                      environment=environment, profile=profile)
    preparer = str(Path(__file__).resolve(strict=True).with_name('lyra_project_prepare.py'))
    if (isinstance(argv, (list, tuple)) and len(argv) >= 5
            and list(argv[1:5]) == ['-B', preparer, '--current-save-transfer', '--auto-ordinary']):
        def option(name, *, required=False):
            count = argv.count(name)
            if count == 0 and not required:
                return None
            if count != 1:
                raise ValueError('Automatic Build requires one ' + name)
            index = argv.index(name) + 1
            if (index >= len(argv) or not isinstance(argv[index], str)
                    or not argv[index] or argv[index].startswith('--')):
                raise ValueError('Automatic Build requires a value for ' + name)
            return Path(argv[index])
        prepare_current_save_environment(option('--project', required=True),
                                         producer_identity=option('--producer-identity'))
    # Even a bound Save and selected ordinary policy cannot admit an unaudited
    # command/environment graph. No executable or transfer is started here.
    raise ContainmentUnavailable('No audited macOS Oracle Build command graph is admitted')


PROFILE_KIND = 'lyra.macos_build_profile.v1'
_PROFILE_KEYS = {'kind', 'project', 'engine', 'source_inventory', 'tools', 'path',
                 'home', 'tmpdir', 'required_checks'}
_REQUIRED_CHECKS = {'flags', 'menu', 'overlap', 'hooks'}
_OPTIONAL_CHECKS = {'sprites', 'annotations', 'analysis'}
_COMMAND_SOURCES = {
    'Scripts/Build/authoring_bundle_build.py', 'Scripts/Build/lyra_build_selection.py',
    'Scripts/Build/lyra_macos_process_group.py', 'Scripts/Build/lyra_process_containment.py',
    'Scripts/Build/lyra_output_paths.py',
    'Scripts/Build/lyra_project_prepare.py', 'Scripts/Build/lyra_project_publisher.py',
    'Scripts/Build/build_rom.sh', 'Scripts/Build/build_checks.sh',
}


def _require_profile(condition, message):
    if not condition:
        raise ContainmentUnavailable('macOS Build profile: ' + message)


def _canonical(path, *, directory=False):
    _require_profile(type(path) is str and bool(path), 'missing canonical path')
    value = Path(path)
    _require_profile(value.is_absolute() and value == value.resolve(strict=True)
                     and not any(p.is_symlink() for p in (value, *value.parents))
                     and (value.is_dir() if directory else value.is_file()),
                     'path is not a canonical regular ' + ('directory: ' if directory else 'file: ') + path)
    return value


def _bound_bytes(binding):
    _require_profile(type(binding) is dict and set(binding) == {'path', 'sha256'}
                     and type(binding['sha256']) is str
                     and re.fullmatch('[0-9a-f]{64}', binding['sha256']), 'invalid file binding')
    path = _canonical(binding['path'])
    raw = path.read_bytes()
    _require_profile(hashlib.sha256(raw).hexdigest() == binding['sha256'],
                     'bound file changed: ' + str(path))
    return raw


def _profile_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require_profile(key not in result, 'duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def _snapshot_head(engine):
    """Read the selected local Git snapshot identity without starting Git."""
    git = _canonical(str(engine / '.git'), directory=True)
    head = _canonical(str(git / 'HEAD')).read_text().strip()
    if head.startswith('ref: '):
        reference = head[5:]
        _require_profile(reference.startswith('refs/') and '..' not in Path(reference).parts
                         and Path(reference).as_posix() == reference, 'invalid snapshot HEAD reference')
        path = git / reference
        if path.is_file():
            head = _canonical(str(path)).read_text().strip()
        else:
            packed = _canonical(str(git / 'packed-refs')).read_text().splitlines()
            matches = [line.split()[0] for line in packed
                       if len(line.split()) == 2 and line.split()[1] == reference]
            _require_profile(len(matches) == 1, 'snapshot HEAD reference is unavailable')
            head = matches[0]
    _require_profile(re.fullmatch('[0-9a-f]{40}', head) is not None, 'invalid snapshot HEAD')
    return head


def load_oracle_profile(binding):
    """Read an explicitly pinned command profile; never discover or create one.

    The source inventory records the chosen Git snapshot's command inputs. It
    neither replaces Git-backed source admission nor grants policy/allocation.
    The caller must select reviewed bytes, including the tools' startup behavior.
    """
    raw = _bound_bytes(binding)
    _require_profile(len(raw) <= 65536, 'profile is too large')
    profile = _profile_json(raw)
    _require_profile(type(profile) is dict and set(profile) == _PROFILE_KEYS
                     and profile['kind'] == PROFILE_KIND, 'unsupported profile shape')
    project = _canonical(profile['project'])
    engine = _canonical(profile['engine'], directory=True)
    inventory = _profile_json(_bound_bytes(profile['source_inventory']))
    _require_profile(type(inventory) is dict and set(inventory) == {'engine_head', 'files'}
                     and type(inventory['engine_head']) is str
                     and re.fullmatch('[0-9a-f]{40}', inventory['engine_head'])
                     and type(inventory['files']) is list, 'invalid Git command-source inventory')
    _require_profile(inventory['engine_head'] == _snapshot_head(engine), 'snapshot HEAD changed')
    names = []
    for row in inventory['files']:
        _require_profile(type(row) is dict and set(row) == {'path', 'sha256', 'size', 'mode'}
                         and type(row['path']) is str and row['path']
                         and not Path(row['path']).is_absolute()
                         and '..' not in Path(row['path']).parts
                         and Path(row['path']).as_posix() == row['path']
                         and type(row['size']) is int and row['size'] >= 0
                         and row['mode'] in ('100644', '100755'), 'invalid source inventory entry')
        name = row['path']; names.append(name)
        source = engine / name
        data = _bound_bytes({'path': str(source), 'sha256': row['sha256']})
        _require_profile(len(data) == row['size']
                         and bool(source.stat().st_mode & 0o111) == (row['mode'] == '100755'),
                         'source size or executable mode changed: ' + name)
    discovered = {p.relative_to(engine).as_posix()
                  for folder in ('Build', 'Generate', 'Validate')
                  for p in (engine / 'Scripts' / folder).rglob('*')
                  if p.suffix in ('.py', '.sh') and p.is_file()}
    _require_profile(names == sorted(set(names)) and _COMMAND_SOURCES <= set(names)
                     and discovered <= set(names), 'command-source inventory is incomplete')
    # The guardian and result types execute from this module's installation.
    # A copied engine may use it only when these control bytes are identical.
    for name in ('lyra_macos_process_group.py', 'lyra_process_containment.py', 'lyra_output_paths.py'):
        _require_profile((engine / 'Scripts/Build' / name).read_bytes()
                         == Path(__file__).with_name(name).read_bytes(),
                         'guardian source differs from the selected snapshot')
    tools = profile['tools']
    _require_profile(type(tools) is dict
                     and set(tools) == {'python', 'bash', 'asar', 'git', 'analyzer'}, 'tool set differs')
    for name, tool in tools.items():
        if name == 'analyzer' and tool is None:
            continue
        _bound_bytes(tool)
        _require_profile(name == 'analyzer' or os.access(tool['path'], os.X_OK),
                         'tool is not executable: ' + name)
    _require_profile(Path(tools['python']['path']) == Path(sys.executable).resolve(strict=True),
                     'supervisor Python differs from the selected interpreter')
    _require_profile(type(profile['path']) is list and profile['path'], 'missing tool search path')
    for path in profile['path']:
        _canonical(path, directory=True)
    search = os.pathsep.join(profile['path'])
    for command, name in (('python3', 'python'), ('git', 'git')):
        selected = shutil.which(command, path=search)
        _require_profile(selected is not None
                         and Path(selected).resolve(strict=True) == Path(tools[name]['path']),
                         'PATH selects a different ' + command)
    # Shell helpers must stay on the system route even when Python lives in a
    # private tool directory. A colocated cp/rm must not shadow these commands.
    system_path = '/usr/bin:/bin:/usr/sbin:/sbin'
    for command in ('basename', 'dirname', 'mkdir', 'mktemp', 'cp', 'mv', 'rm', 'date', 'cat'):
        selected, expected = shutil.which(command, path=search), shutil.which(command, path=system_path)
        _require_profile(selected is not None and expected is not None
                         and Path(selected).resolve(strict=True) == Path(expected).resolve(strict=True),
                         'PATH shadows the system helper ' + command)
    runtime = _canonical(str(project) + '.lyra-build-runtime', directory=True)
    _require_profile(runtime.stat().st_uid == os.geteuid() and not runtime.stat().st_mode & 0o077,
                     'runtime directory must be private and owned')
    for name, child in (('home', 'home'), ('tmpdir', 'tmp')):
        path = _canonical(profile[name], directory=True)
        _require_profile(path == runtime / child and path.stat().st_uid == os.geteuid()
                         and not path.stat().st_mode & 0o077
                         and not path.is_relative_to(engine),
                         'private ' + name + ' must use this project runtime directory')
    checks = profile['required_checks']
    _require_profile(type(checks) is list and all(type(value) is str for value in checks)
                     and checks == sorted(set(checks)) and _REQUIRED_CHECKS <= set(checks)
                     and set(checks) <= _REQUIRED_CHECKS | _OPTIONAL_CHECKS
                     and ('analysis' not in checks or tools['analyzer'] is not None),
                     'required checks are missing, unknown or unavailable')
    _bound_bytes(binding)
    return profile


def _profile_command(argv, profile, environment):
    """Accept only automatic ordinary preparation or its fixed selected Build."""
    import lyra_output_paths as outputs
    _require_profile(type(environment) is dict, 'missing stage environment')
    project, engine = Path(profile['project']), Path(profile['engine'])
    fields = ('OOS_LYRA_PROJECT', 'OOS_LYRA_BUILD_ID', 'OOS_LYRA_REQUEST', 'OOS_LYRA_CANDIDATE')
    _require_profile(all(type(environment.get(key)) is str for key in fields), 'missing attempt identity')
    build_id = environment['OOS_LYRA_BUILD_ID']
    request, candidate = (Path(environment[key]) for key in fields[2:])
    _require_profile(environment['OOS_LYRA_PROJECT'] == str(project)
                     and re.fullmatch('[0-9a-f]{32}', build_id)
                     and outputs.is_private_generation(project, engine, candidate)
                     and candidate.parent.name == 'lyra-' + build_id
                     and request == candidate.parent / 'transfer/request.json'
                     and not candidate.exists(), 'stage does not belong to this fresh generation')
    tools = profile['tools']
    prepare = [tools['python']['path'], '-B', str(engine / 'Scripts/Build/lyra_project_prepare.py'),
               '--current-save-transfer', '--auto-ordinary', '--project', str(project),
               '--output', str(request.parent), '--candidate', str(candidate),
               '--validate-build-engine', str(engine)]
    producer = None
    if list(argv) == prepare:
        stage = 'prepare'
    elif list(argv) in ([tools['bash']['path'], str(engine / 'Scripts/Build/build_rom.sh'), '168'],
                       [tools['bash']['path'], str(engine / 'Scripts/Build/build_rom.sh'), '168',
                        '--asar=' + tools['asar']['path']]):
        _canonical(str(request))
        stage = 'build'
    else:
        raise ContainmentUnavailable('macOS Build profile: command is outside the fixed two-stage graph')
    return stage, producer


def _profile_environment(profile, environment, save_environment):
    project = Path(profile['project'])
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(project.read_text(encoding='utf-8-sig'))
    config.defaults().clear()
    rom = config.get('files', 'rom_filename', fallback='')
    _require_profile(bool(rom), 'project has no ROM')
    base = Path(rom) if Path(rom).is_absolute() else project.parent / rom
    base = _canonical(str(base.resolve(strict=True)))
    supplied = environment.get('OOS_BASE_ROM', str(base))
    _require_profile(type(supplied) is str
                     and (project.parent / supplied).resolve(strict=True) == base, 'base ROM differs')
    values = {'PATH': os.pathsep.join(profile['path']), 'HOME': profile['home'],
              'TMPDIR': profile['tmpdir'], 'LANG': 'C', 'LC_ALL': 'C',
              'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
              'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
              'OOS_BASE_ROM': str(base), 'OOS_MANIFEST_ROOT': str(project.parent),
              'OOS_BACKUP_ROOT': str(Path(environment['OOS_LYRA_CANDIDATE']).parent / '_archives'),
              'ASAR_BIN': profile['tools']['asar']['path'],
              'OOS_REQUIRE_CHECKS': ','.join(profile['required_checks']), **save_environment}
    for key in ('OOS_LYRA_PROJECT', 'OOS_LYRA_BUILD_ID', 'OOS_LYRA_REQUEST', 'OOS_LYRA_CANDIDATE'):
        values[key] = environment[key]
    analyzer = profile['tools']['analyzer']
    if analyzer is None:
        # Explicitly record the gap; never discover a sibling analyzer.
        values['SKIP_ANALYSIS'] = '1'
    else:
        values['OOS_ANALYZER'] = analyzer['path']
    return values


def _prepare_profile_build(argv, *, cwd, timeout, environment, profile):
    document = load_oracle_profile(profile)
    _require_profile(Path(cwd) == Path(document['project']).parent, 'working directory differs')
    stage, producer = _profile_command(argv, document, environment)
    _require_profile(environment.get('YAZE_NATIVE_SAVE_CONTEXT') == os.environ.get('YAZE_NATIVE_SAVE_CONTEXT')
                     and bool(environment.get('YAZE_NATIVE_SAVE_CONTEXT')), 'Save context differs from supervisor')
    saved = prepare_current_save_environment(document['project'], producer_identity=producer)
    _require_profile(os.access(saved['selection']['verifier']['path'], os.X_OK),
                     'selected Save verifier is not executable')
    child_environment = _profile_environment(document, environment, saved['environment'])
    command = list(argv)
    if stage == 'build':
        command = [document['tools']['bash']['path'], str(Path(document['engine']) / 'Scripts/Build/build_rom.sh'),
                   '168', '--asar=' + document['tools']['asar']['path']]
    bindings = [saved['selection'][key] for key in ('producer', 'save_receipt', 'save_context', 'ledger', 'verifier')]
    for path in (document['project'], child_environment['OOS_BASE_ROM']):
        bindings.append({'path': path, 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()})
    return {'argv': command, 'cwd': str(cwd), 'timeout': timeout, 'environment': child_environment,
            'oracle': {'profile': profile, 'bindings': bindings}}


def _oracle_arguments(argv, cwd, timeout, environment, oracle):
    _require_profile(type(oracle) is dict and set(oracle) == {'profile', 'bindings'}
                     and type(oracle['bindings']) is list and len(oracle['bindings']) == 7,
                     'invalid prepared stage bindings')
    profile = load_oracle_profile(oracle['profile'])
    _profile_command(argv, profile, environment)
    _require_profile(Path(cwd) == Path(profile['project']).parent, 'working directory differs')
    for binding in oracle['bindings']:
        _bound_bytes(binding)
    _require_profile(environment.get('YAZE_NATIVE_SAVE_CONTEXT') == oracle['bindings'][2]['path']
                     and environment.get('OOS_Z3ED_BIN') == oracle['bindings'][4]['path']
                     and profile['project'] == oracle['bindings'][5]['path']
                     and environment.get('OOS_BASE_ROM') == oracle['bindings'][6]['path'],
                     'prepared Save or ROM identity changed')
    save_environment = {key: environment.get(key) for key in ('YAZE_NATIVE_SAVE_CONTEXT', 'OOS_Z3ED_BIN')}
    _require_profile(environment == _profile_environment(profile, environment, save_environment),
                     'prepared environment changed')
    # Reuse the fixture's platform/finite-time checks, never its environment filter.
    command, directory, _ = _fixture_arguments(argv, cwd, timeout, None)
    return command, directory, dict(environment)


def run_oracle_build(prepared):
    return _run_fixture_group(prepared['argv'], cwd=prepared['cwd'], timeout=prepared['timeout'],
                              environment=prepared['environment'], oracle=prepared['oracle'])


def _ordinary_arguments(argv, cwd, timeout, environment, ordinary):
    """Recheck the separately pinned ordinary private-copy graph before exec."""
    import oracle_ordinary_build as ordinary_build
    _require_profile(type(ordinary) is dict and set(ordinary) == {'profile', 'state'},
                     'invalid ordinary attempt bindings')
    prepared = ordinary_build.ordinary_command(ordinary['profile'], ordinary['state'])
    _require_profile(list(argv) == prepared['argv'] and str(cwd) == prepared['cwd']
                     and type(timeout) is type(prepared['timeout']) and timeout == prepared['timeout']
                     and environment == prepared['environment'], 'ordinary command/environment differs')
    command, directory, _ = _fixture_arguments(argv, cwd, timeout, None)
    return command, directory, dict(environment)


def run_ordinary_build(prepared):
    return _run_fixture_group(prepared['argv'], cwd=prepared['cwd'], timeout=prepared['timeout'],
                              environment=prepared['environment'], ordinary=prepared['ordinary'])


def _group_arguments(argv, cwd, timeout, environment, oracle, ordinary):
    _require_profile(oracle is None or ordinary is None, 'mixed Build route')
    if ordinary is not None:
        return _ordinary_arguments(argv, cwd, timeout, environment, ordinary)
    return (_fixture_arguments(argv, cwd, timeout, environment) if oracle is None
            else _oracle_arguments(argv, cwd, timeout, environment, oracle))


def _live_group_members(group):
    """Take one macOS process-table snapshot; refuse an incomplete snapshot."""
    try:
        result = subprocess.run(['/bin/ps', '-A', '-o', 'pid=', '-o', 'pgid=', '-o', 'stat='],
                                check=True, capture_output=True, text=True, timeout=5)
        live = []
        leader_seen = False
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 3:
                raise ValueError('unexpected process-table row')
            pid, pgid = map(int, fields[:2])
            if pid == group and pgid == group:
                leader_seen = True
            if pgid == group and not fields[2].startswith('Z'):
                live.append(pid)
        if not leader_seen:
            raise ValueError('unreaped group leader is missing from process-table snapshot')
        return live
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ContainmentUncertain('Cannot inspect the process group') from error


def _wait_group_gone(group, deadline):
    """Confirm group absence after reaping; never signal a reusable group ID."""
    while True:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return
        except OSError as error:
            raise ContainmentUncertain('Cannot establish process-group absence') from error
        if time.monotonic() >= deadline:
            raise ContainmentUncertain('Process group still exists after leader was reaped')
        time.sleep(.02)


def _fixture_environment(directory):
    """Construct a minimal fixture environment without inheriting shell hooks.

    Real Oracle Build variables are intentionally absent. An audited Build
    profile must define and bind its own complete environment before admission.
    """
    return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(directory),
            'TMPDIR': str(directory), 'LANG': 'C', 'PYTHONNOUSERSITE': '1',
            'PYTHONDONTWRITEBYTECODE': '1'}


_FIXTURE_BUILD_KEYS = frozenset({'OOS_BASE_ROM', 'OOS_BACKUP_ROOT', 'OOS_MANIFEST_ROOT',
                                 'OOS_LYRA_PROJECT', 'OOS_LYRA_BUILD_ID',
                                 'OOS_LYRA_REQUEST', 'OOS_LYRA_CANDIDATE'})


def _fixture_arguments(argv, cwd, timeout, environment):
    if sys.platform != 'darwin' or not all(hasattr(os, name) for name in ('waitid', 'WNOWAIT', 'P_PID')):
        raise ContainmentUnavailable('macOS waitid and process-group support required')
    if (not argv or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
            or not 0 < timeout < float('inf')):
        raise ContainmentUnavailable('A command and finite positive timeout are required')
    try:
        executable, directory = Path(argv[0]), Path(cwd)
    except (TypeError, ValueError, OSError) as error:
        raise ContainmentUnavailable('Invalid fixture command or directory') from error
    if not executable.is_absolute() or not executable.is_file():
        raise ContainmentUnavailable('Executable must be an absolute regular file')
    if not directory.is_absolute() or not directory.is_dir():
        raise ContainmentUnavailable('Working directory must be an absolute directory')
    # A fixture may receive only these explicit Build inputs, never arbitrary
    # inherited shell/Python hooks. A real Build audit must independently bind
    # its complete toolchain and environment before admission.
    child_environment = _fixture_environment(directory)
    if environment is not None:
        for key in _FIXTURE_BUILD_KEYS:
            if key in environment:
                value = environment[key]
                if not isinstance(value, str) or '\0' in value:
                    raise ContainmentUnavailable('Invalid fixture Build environment')
                child_environment[key] = value
    return [str(part) for part in argv], directory, child_environment


def _run_owned_group(argv, *, cwd, timeout, environment=None, control=None, oracle=None, ordinary=None):
    """Guardian-owned group mechanics; callers must keep descendants in-group.

    Keep the leader unreaped until all signals finish. A controlled launch waits
    behind an exec gate until the supervisor acknowledges the published leader.
    This is fixture machinery, not a source/toolchain admission boundary.
    """
    argv, directory, child_environment = _group_arguments(argv, cwd, timeout, environment, oracle, ordinary)
    gate_read = gate_write = None
    if control is not None:
        if control.poll() in ('cancel', 'parent_lost'):
            return ContainedResult(128 + signal.SIGTERM, False)
        gate_read, gate_write = os.pipe()
        command = _fixture_helper_command('--fixture-exec', str(gate_read), json.dumps(argv))
    else:
        command = argv
    try:
        process = subprocess.Popen(command, cwd=directory, env=child_environment,
                                   start_new_session=True, close_fds=True,
                                   pass_fds=() if gate_read is None else (gate_read,))
    except (OSError, ValueError) as error:
        if gate_write is not None:
            os.close(gate_write)
        raise ContainmentUnavailable('Could not start fixture process') from error
    finally:
        if gate_read is not None:
            os.close(gate_read)

    deadline = time.monotonic() + timeout
    terminated = False
    cancelled = False
    cleanup_deadline = None
    leader_reap_started = False
    try:
        if control is not None:
            control.spawned(process.pid)
        while True:
            action = None if control is None else control.poll()
            if not terminated and action in ('cancel', 'parent_lost'):
                os.killpg(process.pid, signal.SIGKILL)
                terminated = cancelled = True
                cleanup_deadline = time.monotonic() + 10
            if not terminated and action == 'run' and gate_write is not None:
                os.write(gate_write, b'R')
                os.close(gate_write)
                gate_write = None
            exited = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            members = _live_group_members(process.pid)
            if exited is not None and not members:
                leader_reap_started = True
                code = process.wait()
                # A process-table scan may miss a member during concurrent fork
                # and exit. Only group absence establishes that no group member
                # remains. Do not signal after wait(), because the ID can be reused.
                _wait_group_gone(process.pid, cleanup_deadline if terminated else deadline)
                if cancelled:
                    return ContainedResult(128 + signal.SIGTERM, False)
                return ContainedResult(None if terminated else code, terminated)
            now = time.monotonic()
            if not terminated and now >= deadline:
                # The leader has not been reaped, so its PID cannot be reused.
                os.killpg(process.pid, signal.SIGKILL)
                terminated = True
                cleanup_deadline = now + 10
            elif terminated and now >= cleanup_deadline:
                raise ContainmentUncertain('Terminated process group did not become empty')
            time.sleep(.02)
    except BaseException as error:
        if not leader_reap_started:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
        # Locks remain owned: signaling does not prove every descendant exited.
        if isinstance(error, ContainmentUncertain):
            raise
        raise ContainmentUncertain('Could not establish process-group completion') from error
    finally:
        if gate_write is not None:
            os.close(gate_write)


_MAX_MESSAGE = 65536


def _fixture_helper_command(*arguments):
    # -I/-S/-B suppress ambient startup/import hooks. Only this fixture module's
    # explicit source directory is added for its containment result types. This
    # command has not been admitted as a production Oracle startup graph.
    source = str(Path(__file__).resolve(strict=True))
    bootstrap = ('import pathlib,runpy,sys; p=sys.argv[1]; sys.argv=sys.argv[1:]; '
                 'sys.path.insert(0,str(pathlib.Path(p).parent)); '
                 'runpy.run_path(p,run_name="__main__")')
    return [str(Path(sys.executable).resolve(strict=True)), '-I', '-S', '-B',
            '-c', bootstrap, source, *arguments]


def _send_message(fd, value):
    data = (json.dumps(value, separators=(',', ':')) + '\n').encode('utf-8')
    if len(data) > _MAX_MESSAGE:
        raise ValueError('Fixture guardian message is too large')
    while data:
        written = os.write(fd, data)
        if not written:
            raise BrokenPipeError('Fixture guardian pipe made no progress')
        data = data[written:]


class _GuardianControl:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.pending = b''
        self.parent_lost = False
        self.action = None
        self.started = False
        # The sole writer of reader's pipe belongs to the supervisor. Neither
        # guardian nor exec child receives it, so parent exit reliably yields EOF.
        while b'\n' not in self.pending:
            data = os.read(reader, 4096)
            if not data:
                raise ValueError('Supervisor exited before fixture configuration')
            self.pending += data
            if len(self.pending) > _MAX_MESSAGE:
                raise ValueError('Fixture configuration is too large')
        raw, self.pending = self.pending.split(b'\n', 1)
        self.config = json.loads(raw)
        if (type(self.config) is not dict or set(self.config) not in (
                {'argv', 'cwd', 'timeout', 'environment'},
                {'argv', 'cwd', 'timeout', 'environment', 'oracle'},
                {'argv', 'cwd', 'timeout', 'environment', 'ordinary'})
                or type(self.config['argv']) is not list
                or not all(type(value) is str for value in self.config['argv'])
                or type(self.config['cwd']) is not str
                or type(self.config['environment']) is not dict):
            raise ValueError('Invalid fixture guardian configuration')
        os.set_blocking(reader, False)

    def poll(self):
        while not self.parent_lost:
            try:
                data = os.read(self.reader, 4096)
            except BlockingIOError:
                break
            if not data:
                self.parent_lost = True
                break
            self.pending += data
            if len(self.pending) > _MAX_MESSAGE:
                raise ValueError('Fixture control stream is too large')
        while b'\n' in self.pending:
            raw, self.pending = self.pending.split(b'\n', 1)
            value = json.loads(raw)
            if value not in ({'action': 'run'}, {'action': 'cancel'}):
                raise ValueError('Invalid fixture guardian action')
            if value['action'] == 'run' and not self.started:
                raise ValueError('Fixture launch was acknowledged before publication')
            if self.action != 'cancel':
                self.action = value['action']
        return 'parent_lost' if self.parent_lost else self.action

    def spawned(self, pid):
        self.started = True
        try:
            _send_message(self.writer, {'kind': 'spawned', 'pid': pid})
        except BrokenPipeError:
            self.parent_lost = True


def _guardian_fixture_main(reader, writer):
    try:
        control = _GuardianControl(reader, writer)
        config = control.config
        result = _run_owned_group(config['argv'], cwd=config['cwd'], timeout=config['timeout'],
                                  environment=config['environment'], control=control,
                                  oracle=config.get('oracle'), ordinary=config.get('ordinary'))
        _send_message(writer, {'kind': 'result', 'exit_code': result.exit_code,
                               'timed_out': result.timed_out})
        return 0
    except BrokenPipeError:
        # The supervisor is gone. _run_owned_group settled the owned group before
        # attempting its result; no dead supervisor's sentinel may be removed.
        return 0
    except BaseException as error:
        try:
            _send_message(writer, {'kind': 'uncertain', 'message': str(error)})
        except (OSError, ValueError):
            pass
        return 70
    finally:
        os.close(reader)
        os.close(writer)


def _exec_fixture_main(reader, raw_command):
    command = json.loads(raw_command)
    try:
        token = os.read(reader, 2)
    finally:
        os.close(reader)
    if token != b'R':
        return 125
    os.execve(command[0], command, dict(os.environ))


def _run_fixture_group(argv, *, cwd, timeout, environment=None, cancel_event=None, oracle=None, ordinary=None):
    """Run only owned fixtures through a guardian, retaining uncertainty.

    The guardian survives supervisor exit and observes its exclusive liveness
    pipe. It cannot contain a descendant that changes process group/session.
    Guardian death itself is uncertain; this prototype never grants Build entry.
    """
    argv, directory, child_environment = _group_arguments(argv, cwd, timeout, environment, oracle, ordinary)
    requested = [False]
    previous = None
    installed = threading.current_thread() is threading.main_thread()
    if installed:
        previous = signal.signal(signal.SIGTERM, lambda *_: requested.__setitem__(0, True))
    def cancelled():
        return requested[0] or (cancel_event is not None and cancel_event.is_set())
    control_read = control_write = result_read = result_write = None
    guardian = None
    try:
        if cancelled():
            return ContainedResult(128 + signal.SIGTERM, False)
        control_read, control_write = os.pipe()
        result_read, result_write = os.pipe()
        try:
            guardian = subprocess.Popen(
                _fixture_helper_command('--fixture-guardian', str(control_read), str(result_write)),
                cwd=directory, env=_fixture_environment(directory), start_new_session=True,
                close_fds=True, pass_fds=(control_read, result_write))
        except (OSError, ValueError) as error:
            raise ContainmentUnavailable('Could not start fixture guardian') from error
        os.close(control_read)
        control_read = None
        os.close(result_write)
        result_write = None
        configuration = {'argv': argv, 'cwd': str(directory), 'timeout': timeout,
                         'environment': child_environment}
        if oracle is not None:
            configuration['oracle'] = oracle
        if ordinary is not None:
            configuration['ordinary'] = ordinary
        _send_message(control_write, configuration)
        os.set_blocking(result_read, False)
        pending = b''
        result = None
        spawned = False
        cancel_sent = False
        deadline = time.monotonic() + timeout + 15
        while True:
            if cancelled() and not cancel_sent:
                _send_message(control_write, {'action': 'cancel'})
                cancel_sent = True
            if time.monotonic() >= deadline:
                raise ContainmentUncertain('Fixture guardian did not report completion')
            if not select.select([result_read], [], [], .02)[0]:
                continue
            data = os.read(result_read, 4096)
            if not data:
                break
            pending += data
            if len(pending) > _MAX_MESSAGE:
                raise ContainmentUncertain('Fixture guardian status is too large')
            while b'\n' in pending:
                raw, pending = pending.split(b'\n', 1)
                value = json.loads(raw)
                if (type(value) is dict and set(value) == {'kind', 'pid'}
                        and value['kind'] == 'spawned' and type(value['pid']) is int
                        and value['pid'] > 0 and not spawned and result is None):
                    spawned = True
                    if not cancelled() and not cancel_sent:
                        _send_message(control_write, {'action': 'run'})
                elif (type(value) is dict and set(value) == {'kind', 'exit_code', 'timed_out'}
                      and value['kind'] == 'result' and result is None
                      and type(value['timed_out']) is bool
                      and (type(value['exit_code']) is int or value['exit_code'] is None)):
                    result = ContainedResult(value['exit_code'], value['timed_out'])
                    if ((result.timed_out and result.exit_code is not None)
                            or (not result.timed_out and result.exit_code is None)
                            or (not spawned and result != ContainedResult(128 + signal.SIGTERM, False))):
                        raise ContainmentUncertain('Inconsistent fixture guardian result')
                else:
                    raise ContainmentUncertain('Invalid or uncertain fixture guardian status')
        remaining = max(.01, deadline - time.monotonic())
        code = guardian.wait(timeout=remaining)
        if pending or result is None or code != 0:
            raise ContainmentUncertain('Fixture guardian exited without confirmed completion')
    except ContainmentUnavailable:
        raise
    except BaseException as error:
        if isinstance(error, ContainmentUncertain):
            raise
        raise ContainmentUncertain('Fixture guardian completion is uncertain') from error
    finally:
        # Closing the only liveness writer requests cleanup even on exceptions.
        for fd in (control_read, control_write, result_read, result_write):
            if fd is not None:
                os.close(fd)
        if guardian is not None:
            try:
                guardian.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Never kill the guardian and abandon a potentially live group.
                # The caller retains sentinels; cleanup is still uncertain.
                pass
        if installed:
            signal.signal(signal.SIGTERM, previous)
    # Select the result only after cleanup and handler restoration. A SIGTERM
    # handled during guardian.wait() above must not become a successful stage
    # that lets the supervisor start the next child or publish its candidate.
    return ContainedResult(128 + signal.SIGTERM, False) if cancelled() else result


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--fixture-guardian':
        raise SystemExit(_guardian_fixture_main(int(sys.argv[2]), int(sys.argv[3])))
    if len(sys.argv) == 4 and sys.argv[1] == '--fixture-exec':
        raise SystemExit(_exec_fixture_main(int(sys.argv[2]), sys.argv[3]))
    raise SystemExit('Only the private fixture guardian protocol is supported')
