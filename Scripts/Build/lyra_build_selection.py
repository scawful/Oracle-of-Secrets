"""Candidate publisher for a detached, completed Lyra build selector.

Not integrated with Build or Run. A selected or project-bound ordinary lifecycle
owns project and engine sentinels; an engine-only lifecycle owns the engine
sentinel. The private Yaze candidate uses the same project sentinel for Save;
its coverage is not yet integrated or fully verified. Consumers must revalidate
the current Save.
Windows contained children can complete a lifecycle. The macOS route has no
admitted Build command graph and refuses before launch; an uncertain child retains
the sentinels. This is not integrated
with the Build entry points. Stale sentinels require verified recovery. This
module does not snapshot preparation files or grant runtime admission.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import stat
from sys import platform
import tempfile
import threading
import uuid

import lyra_current_transfer as current
import lyra_output_paths as output_paths

KIND = 'lyra.latest_success.v1'
PENDING_KIND = 'lyra.latest_pending.v1'
_FIELDS = {'kind', 'project', 'generation', 'operation_id', 'request',
           'candidate', 'build_receipt', 'build_id'}
_MAX_JSON = 16 * 1024 * 1024


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _prepare_staged_child(argv, *, cwd, timeout, environment):
    """Validate one stage before launch and return its owned runner.

    Darwin requires an explicit pinned command profile. Reusing guardian
    mechanics does not grant source, resource or allocation admission.
    """
    if platform == 'darwin':
        import lyra_macos_process_group as macos
        profile_path = environment.get('OOS_MACOS_BUILD_PROFILE')
        profile_hash = environment.get('OOS_MACOS_BUILD_PROFILE_SHA256')
        if profile_path is not None or profile_hash is not None:
            prepared = macos.prepare_oracle_build(argv, cwd=cwd, timeout=timeout,
                environment=environment, profile={'path': profile_path, 'sha256': profile_hash})
            return lambda: macos.run_oracle_build(prepared)
        prepared = macos.prepare_oracle_build(argv, cwd=cwd, timeout=timeout)
        return lambda: macos._run_fixture_group(
            prepared[0], cwd=prepared[1], timeout=prepared[2], environment=environment)
    import lyra_process_containment as containment
    prepared = containment.prepare_contained(argv, cwd=cwd, timeout=timeout,
                                             environment=environment)
    return lambda: containment._run_windows(*prepared)


def _selected_child_safety(values):
    """Keep selected helpers read-only and disconnected from ambient sessions."""
    values = dict(values)
    for key in list(values):
        if isinstance(key, str) and key.upper() in {
                'PYTHONPYCACHEPREFIX', 'PYTHONDONTWRITEBYTECODE', 'OOS_TEST_SOCKET'}:
            del values[key]
    values['PYTHONDONTWRITEBYTECODE'] = '1'
    return values


def _file(path):
    path = Path(path)
    _require(path.is_absolute() and path == path.resolve(strict=True),
             'Selection evidence path must be absolute and canonical')
    _require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
             'Selection evidence must be a regular non-symlink file')
    return path


def _json(path):
    path = _file(path)
    _require(path.stat().st_size <= _MAX_JSON, 'Selection metadata is too large')
    value = current._json(path.read_bytes())
    _require(type(value) is dict, 'Selection metadata must be an object')
    return value


def _artifact(row, expected_path=None):
    _require(type(row) is dict and type(row.get('path')) is str
             and type(row.get('sha256')) is str and type(row.get('size')) is int,
             'Build artifact identity is incomplete')
    path = _file(row['path'])
    if expected_path is not None:
        _require(path == expected_path, 'Build artifact path differs')
    binding = current.Q.bound(path)
    _require(binding['sha256'] == row['sha256'] and path.stat().st_size == row['size'],
             'Build artifact changed')
    return binding


def validate(project, request, candidate, build_receipt):
    """Validate existing evidence; return a selector and its verified bindings.

    The transfer verifier checks the actual Save/context and immutable input
    snapshots. Receipt booleans alone are never used to manufacture admission.
    """
    project, request, candidate, build_receipt = map(
        _file, (project, request, candidate, build_receipt))
    _require(build_receipt == candidate.parent / 'oos168x.build.json',
             'Build receipt must be beside the candidate')
    build_binding = current.Q.bound(build_receipt)
    build = _json(build_receipt)
    attempt = build.get('lyra_attempt')
    _require(type(attempt) is dict and set(attempt) == {'build_id'}
             and type(attempt['build_id']) is str
             and re.fullmatch('[0-9a-f]{32}', attempt['build_id']),
             'Build attempt identity is missing or malformed')
    finish = build.get('finish')
    _require(build.get('schema_version') == 1
             and build.get('state') in ('completed', 'completed_with_gaps')
             and type(finish) is dict and type(finish.get('exit_code')) is int
             and finish['exit_code'] == 0 and finish.get('required_gaps') == [],
             'Build did not complete successfully')
    checks = build.get('checks')
    _require(type(checks) is list and all(
        type(row) is dict and type(row.get('name')) is str and row['name']
        and type(row.get('required')) is bool
        and type(row.get('status')) is str
        and row['status'] in ('passed', 'failed', 'unavailable', 'skipped')
        for row in checks), 'Build checks are malformed')
    required_lyra = [row for row in checks if row['name'] == 'lyra_verify']
    _require(len(required_lyra) == 1 and required_lyra[0]['required'] is True
             and required_lyra[0]['status'] == 'passed'
             and type(required_lyra[0].get('exit_code')) is int
             and required_lyra[0]['exit_code'] == 0,
             'Required Lyra verification did not pass')
    _require(all(not (row['required'] and row['status'] != 'passed') for row in checks),
             'Build has a failed required check')
    engine = Path(build.get('root', ''))
    _require(engine.is_absolute() and engine == engine.resolve(strict=True)
             and candidate.name == 'oos168x.sfc'
             and ((candidate.parent != engine / 'Roms'
                   and candidate.is_relative_to(engine / 'Roms'))
                  or output_paths.is_private_generation(project, engine, candidate)),
             'Candidate is not in an allowed generation for this project')
    artifacts = build.get('artifacts')
    _require(type(artifacts) is dict, 'Build artifacts are missing')
    bindings = []
    for key, expected in (('output_rom', candidate),
                          ('symbols', candidate.parent / 'oos168x.sym'),
                          ('lyra_verification', candidate.parent / 'oos168x.lyra-verification.json')):
        bindings.append(_artifact(artifacts.get(key), expected))
    _require(artifacts['output_rom']['size'] == 0x400000,
             'Expanded output must be exactly 4 MiB')
    prepared_row = artifacts.get('lyra_prepare')
    prepared_binding = _artifact(prepared_row)
    _require(Path(prepared_binding['path']).parent == candidate.parent,
             'Preparation must be snapshotted in the generation directory')
    bindings.append(prepared_binding)
    base_binding = _artifact(build.get('base_rom'))
    bindings.append(base_binding)
    prepared = _json(prepared_binding['path'])
    verified = _json(artifacts['lyra_verification']['path'])
    _require(prepared.get('kind') == 'lyra.current_build_prepare.v1'
             and all(prepared.get(flag) is True for flag in (
                 'selected', 'allocation_granted', 'producer_enforcement_verified',
                 'runtime_admission', 'ordinary_build_ready'))
             and 'runtime_scope' not in prepared,
             'Prepared build is not admitted for ordinary use')
    _require(verified.get('kind') == 'lyra.current_build_verification.v1'
             and verified.get('compiled_consumers_verified') is True
             and verified.get('prepared_sha256') == prepared_binding['sha256']
             and verified.get('compiled_rom_sha256') == artifacts['output_rom']['sha256']
             and verified.get('symbols_sha256') == artifacts['symbols']['sha256']
             and verified.get('saved_rom_sha256') == base_binding['sha256']
             and prepared.get('saved_rom_sha256') == base_binding['sha256']
             and verified.get('current_ledger_sha256') == prepared.get('current_ledger_sha256')
             and isinstance(prepared.get('current_ledger_sha256'), str),
             'Compiled verification does not bind the build')
    _require(prepared.get('project') == str(project)
             and prepared.get('request') == str(request)
             and prepared.get('base_rom') == base_binding['path'],
             'Preparation belongs to another project or request')
    request_binding = current.Q.bound(request)
    inputs = prepared.get('inputs')
    _require(type(inputs) is list and len(inputs) <= 4096 and request_binding in inputs,
             'Preparation omits its immutable request binding')
    for binding in inputs:
        current.Q.read_bound(binding)
    ledger_path = prepared.get('ledger')
    _require(type(ledger_path) is str and
             {'path': ledger_path, 'sha256': prepared['current_ledger_sha256']} in inputs,
             'Preparation omits its selected ledger binding')
    profile = prepared.get('current_source_profile')
    _require(type(profile) is dict and type(profile.get('selected_source')) is dict
             and profile['selected_source'].get('root') == str(engine),
             'Preparation belongs to another build engine')
    with current.candidate_inspection(candidate):
        transfer, _, _ = current.verify_transfer(request, project, base_binding['path'])
    live = transfer['live']
    plan = prepared.get('terrain_plan')
    _require(type(plan) is dict and plan.get('target') == transfer['target']
             and transfer['target']['path'] == str(candidate)
             and plan.get('transfer_id') == transfer['transfer_id']
             and plan.get('generation') == live['generation']
             and plan.get('operation_id') == live['operation_id']
             and plan.get('save_context') == live['save_context'],
             'Preparation does not bind this transfer and Save')
    if plan.get('enforcement_owner') == 'oracle.current_builder':
        order = verified.get('compile_order')
        _require(type(order) is dict and order.get('owner') == 'oracle.current_builder'
                 and order.get('required_order') == current.COMPILE_ORDER
                 and order.get('native_verification') == transfer.get('native_verification')
                 and plan.get('enforcement_receipt') == transfer.get('native_verification')
                 and all(order.get(key) is True for key in (
                     'saved_generation_unchanged', 'immutable_snapshot_verified',
                     'derived_output_verified', 'oracle_compile_order_verified')),
                 'Compile order is not bound to the transfer')
    else:
        _require(plan.get('enforcement_owner') == 'legacy_producer',
                 'Unsupported build enforcement owner')
        _require(plan.get('enforcement_receipt', {}).get('path') == live['enforcement_receipt'],
                 'Legacy producer enforcement does not match this Save')
        current.Q.read_bound(plan['enforcement_receipt'])
    selector = dict(kind=KIND, project=str(project), generation=live['generation'],
                    operation_id=live['operation_id'], request=str(request),
                    candidate=str(candidate), build_receipt=build_binding, **attempt)
    current._recheck(live)
    for binding in [build_binding, request_binding, *bindings, *inputs]:
        current.Q.read_bound(binding)
    return selector


def _sync_dir(path):
    """Sync directory metadata when supported; propagate other failures."""
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        if os.name == 'nt' and error.errno in (errno.EACCES, errno.EPERM):
            return
        raise
    try:
        try:
            os.fsync(fd)
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
                raise
    finally:
        os.close(fd)


def _temporary(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.',
                                     delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return temporary


def _existing(path, project):
    _require(not path.is_symlink(), 'Selector must not be a symlink')
    if not path.exists():
        return None
    _require(path.is_file() and path.stat().st_nlink == 1,
             'Selector must be a single-link regular file')
    previous = _json(path)
    if previous.get('kind') == PENDING_KIND:
        _require(previous == {'kind': PENDING_KIND, 'project': str(project)},
                 'Existing pending selector is malformed or foreign')
        return previous
    old_receipt = previous.get('build_receipt')
    _require(set(previous) == _FIELDS and previous.get('kind') == KIND
             and previous.get('project') == str(project)
             and type(previous.get('generation')) is int
             and previous['generation'] > 0
             and type(previous.get('build_id')) is str
             and re.fullmatch('[0-9a-f]{32}', previous['build_id'])
             and type(previous.get('operation_id')) is str
             and previous['operation_id']
             and all(type(previous.get(key)) is str
                     and Path(previous[key]).is_absolute()
                     and str(Path(previous[key]).resolve()) == previous[key]
                     for key in ('request', 'candidate'))
             and type(old_receipt) is dict
             and set(old_receipt) == {'path', 'sha256'}
             and type(old_receipt['path']) is str
             and Path(old_receipt['path']).is_absolute()
             and str(Path(old_receipt['path']).resolve()) == old_receipt['path']
             and type(old_receipt['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}', old_receipt['sha256']),
             'Existing selector is malformed')
    return previous


def _directory(path):
    path = Path(path)
    _require(path.is_absolute() and path == path.resolve(strict=True)
             and path.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)),
             'Build engine must be an absolute canonical non-symlink directory')
    return path


class BuildSession:
    """Own the engine sentinel and, when project-bound, acquire project first.

    Never auto-reclaim on crash.

    Windows child execution is contained in a non-breakaway job. macOS admits
    no Build graph yet; an uncertain child retains both locks.
    This lifecycle is not yet integrated with the Build entry points.
    """

    def __init__(self, project, engine, *, selected=True):
        self._project = None if project is None else _file(project)
        if self._project is not None:
            _require(self._project.stat().st_nlink == 1,
                     'Project file must have exactly one hard link')
        self._selected = bool(selected and self._project is not None)
        self._engine = _directory(engine)
        self._build_id = uuid.uuid4().hex
        self._pid = os.getpid()
        self._owned = []
        self._child_started = False
        self._child_completed = False
        self._child_failed = False
        self._child_selection = None
        self._active = False
        self._state_lock = threading.RLock()

    @property
    def build_id(self):
        return self._build_id

    @property
    def project(self):
        return self._project

    @property
    def engine(self):
        return self._engine

    def _acquire(self, path):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError as error:
            raise ValueError('Build sentinel is held or stale: ' + str(path)) from error
        info = os.fstat(fd)
        token = uuid.uuid4().hex
        project = None if self.project is None else str(self.project)
        raw = (json.dumps(dict(kind='lyra.build_lock.v1', project=project,
                               engine=str(self.engine), build_id=self.build_id,
                               pid=self._pid, token=token), sort_keys=True) + '\n').encode()
        self._owned.append((path, info.st_dev, info.st_ino, raw))
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _sync_dir(path.parent)

    def _check_owned(self):
        expected_count = 1 if self.project is None else 2
        _require(os.getpid() == self._pid and len(self._owned) == expected_count,
                 'Build lifecycle belongs to another process or is incomplete')
        project = None if self.project is None else str(self.project)
        if self.project is not None:
            _require(_file(self.project).stat().st_nlink == 1,
                     'Project file must have exactly one hard link')
        for path, device, inode, raw in self._owned:
            try:
                info = path.lstat()
            except FileNotFoundError as error:
                raise RuntimeError('Build sentinel disappeared: ' + str(path)) from error
            identity = current._json(raw)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or (info.st_dev, info.st_ino) != (device, inode)
                    or path.read_bytes() != raw
                    or identity['build_id'] != self._build_id
                    or identity['project'] != project
                    or identity['engine'] != str(self.engine)
                    or identity['pid'] != self._pid):
                raise RuntimeError('Build sentinel ownership changed: ' + str(path))

    def _release_if_quiescent(self):
        _require(os.getpid() == self._pid and not self._child_started,
                 'Cannot release an uncertain child lifecycle')
        # Check every sentinel before removing any. Uncertain locks remain.
        for path, device, inode, raw in self._owned:
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or (info.st_dev, info.st_ino) != (device, inode)
                    or path.read_bytes() != raw):
                raise RuntimeError('Build sentinel ownership changed: ' + str(path))
        for path, _, _, _ in reversed(self._owned):
            path.unlink()
            _sync_dir(path.parent)
        self._owned.clear()
        self._active = False

    def begin(self):
        _require(not self._active and not self._owned, 'Build lifecycle already started')
        try:
            if self.project is not None:
                self._acquire(Path(str(self.project) + '.lyra-build-project.lock'))
            self._acquire(self.engine / '.lyra-build-engine.lock')
            self._check_owned()
            if self._selected:
                path = Path(str(self.project) + '.lyra-build-latest.json')
                if _existing(path, self.project) is None:
                    raw = (json.dumps(dict(kind=PENDING_KIND, project=str(self.project)),
                                      sort_keys=True, indent=2) + '\n').encode()
                    temporary = _temporary(path, raw)
                    try:
                        os.link(temporary, path)
                    finally:
                        temporary.unlink(missing_ok=True)
                    _sync_dir(path.parent)
                    _require(path.read_bytes() == raw, 'Pending selector readback differs')
            self._check_owned()
            self._active = True
            return self
        except BaseException as original_error:
            if self._owned:
                try:
                    self._release_if_quiescent()
                except BaseException as cleanup_error:
                    # Keep the operation error primary, while retaining the
                    # cleanup failure as its explicit cause. Uncertain markers
                    # remain for a separately verified recovery.
                    raise original_error from cleanup_error
            raise

    def mark_child_started(self):
        """Mark an uncertain child; only contained execution can clear it."""
        with self._state_lock:
            _require(self._active, 'Build lifecycle is not active')
            _require(not self._child_started and not self._child_completed,
                     'Build lifecycle already started a child')
            self._check_owned()
            self._child_started = True

    def generated_paths(self):
        """Reserve names for this Build without creating its snapshot or ROM."""
        _require(self._active and self._selected, 'Selected Build lifecycle is not active')
        self._check_owned()
        candidate = (output_paths.private_output_root(self.project)
                     / ('lyra-' + self.build_id) / 'oos168x.sfc')
        request = candidate.parent / 'transfer' / 'request.json'
        _require(output_paths.is_private_generation(self.project, self.engine, candidate),
                 'Private Build output must be outside the engine Roms directory')
        for path in (request.parent, candidate.parent):
            _require(path == path.resolve() and not path.exists() and not path.is_symlink()
                     and not any(parent.is_symlink() for parent in path.parents),
                     'Generated Build paths must be new and canonical')
        return request, candidate

    def run_generated_build(self, prepare_argv, build_argv, *, cwd, timeout,
                            environment, validate_prepared):
        """Prepare a fresh generation and build it under the same owned locks."""
        request, candidate = self.generated_paths()
        first_environment = dict(environment)
        for key in list(first_environment):
            if isinstance(key, str) and key.upper().startswith('OOS_LYRA_'):
                del first_environment[key]
        first_environment = _selected_child_safety(first_environment)
        first_environment.update(OOS_LYRA_PROJECT=str(self.project),
                                 OOS_LYRA_BUILD_ID=self.build_id,
                                 OOS_LYRA_REQUEST=str(request),
                                 OOS_LYRA_CANDIDATE=str(candidate))
        return self._run_staged_build(request, candidate, prepare_argv, build_argv,
                                      cwd=cwd, timeout=timeout, first_environment=first_environment,
                                      validate_prepared=validate_prepared)

    def run_selected_build(self, request, candidate, validate_argv, build_argv, *, cwd,
                           timeout, environment, validate_prepared):
        """Validate an existing generation and build it under the same owned locks."""
        _require(self._active and self._selected, 'Selected Build lifecycle is not active')
        self._check_owned()
        first_environment = self._child_environment(environment, request=request,
                                                    candidate=candidate)
        request = Path(first_environment['OOS_LYRA_REQUEST'])
        candidate = Path(first_environment['OOS_LYRA_CANDIDATE'])
        return self._run_staged_build(request, candidate, validate_argv, build_argv,
                                      cwd=cwd, timeout=timeout, first_environment=first_environment,
                                      validate_prepared=validate_prepared)

    def _run_staged_build(self, request, candidate, prepare_argv, build_argv, *, cwd,
                          timeout, first_environment, validate_prepared):
        import lyra_process_containment as containment
        import time
        prepared = _prepare_staged_child(prepare_argv, cwd=cwd, timeout=timeout,
                                        environment=first_environment)
        def run():
            started = time.monotonic()
            preparation = prepared()
            if preparation.timed_out or preparation.exit_code != 0:
                return preparation
            self._check_owned()
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                return containment.ContainedResult(None, True)
            # A validation error here occurs after the preparation job has
            # exited and before the Build job exists. Treat it as a failed
            # attempt; unexpected errors still retain the sentinels.
            try:
                build_environment = validate_prepared(request, candidate)
                child_environment = self._child_environment(build_environment,
                                                            request=request, candidate=candidate)
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    return containment.ContainedResult(None, True)
                build = _prepare_staged_child(build_argv, cwd=cwd, timeout=remaining,
                                              environment=child_environment)
            except (OSError, ValueError) as error:
                import sys
                print(f'Build preparation refused: {error}', file=sys.stderr)
                return containment.ContainedResult(2, False)
            return build()
        return self._run_prepared_child(run, selection=(request, candidate))

    def _child_environment(self, environment, *, request=None, candidate=None):
        """Bind this lifecycle into an isolated child environment."""
        values = dict(os.environ if environment is None else environment)
        for key in list(values):
            if isinstance(key, str) and key.upper().startswith('OOS_LYRA_'):
                del values[key]
        if self._selected:
            values = _selected_child_safety(values)
            _require(request is not None and candidate is not None,
                     'Selected Build requires explicit request and candidate')
            request = _file(request)
            candidate = Path(candidate)
            _require(candidate.is_absolute() and candidate == candidate.resolve()
                     and output_paths.is_private_generation(self.project, self.engine, candidate)
                     and candidate.name == 'oos168x.sfc'
                     and not candidate.exists() and not candidate.is_symlink(),
                     'Selected Build requires a fresh canonical generation candidate')
            values['OOS_LYRA_PROJECT'] = str(self.project)
            values['OOS_LYRA_BUILD_ID'] = self.build_id
            values['OOS_LYRA_REQUEST'] = str(request)
            values['OOS_LYRA_CANDIDATE'] = str(candidate)
        else:
            _require(request is None and candidate is None,
                     'Ordinary Build cannot select a request or candidate')
        return values

    def run_child(self, argv, *, cwd, timeout, environment=None,
                  request=None, candidate=None):
        """Run one contained child; retain locks if its lifetime is uncertain."""
        import lyra_process_containment as containment
        _require(self._active, 'Build lifecycle is not active')
        self._check_owned()
        child_environment = self._child_environment(environment, request=request,
                                                    candidate=candidate)
        prepared = containment.prepare_contained(
            argv, cwd=cwd, timeout=timeout, environment=child_environment)
        selection = ((Path(child_environment['OOS_LYRA_REQUEST']),
                      Path(child_environment['OOS_LYRA_CANDIDATE']))
                     if self._selected else None)
        return self._run_prepared_child(lambda: containment._run_windows(*prepared),
                                        selection=selection)

    def run_macos_audited_child(self, argv, *, cwd, timeout, environment=None,
                                request=None, candidate=None):
        """Run only an admitted macOS Build graph; none is currently admitted."""
        import lyra_macos_process_group as macos
        _require(self._active, 'Build lifecycle is not active')
        self._check_owned()
        prepared = macos.prepare_oracle_build(argv, cwd=cwd, timeout=timeout)
        child_environment = self._child_environment(environment, request=request,
                                                    candidate=candidate)
        selection = ((Path(child_environment['OOS_LYRA_REQUEST']),
                      Path(child_environment['OOS_LYRA_CANDIDATE']))
                     if self._selected else None)
        return self._run_prepared_child(lambda: macos._run_fixture_group(
            prepared[0], cwd=prepared[1], timeout=prepared[2],
            environment=child_environment), selection=selection)

    def _run_prepared_child(self, run, *, selection=None):
        import lyra_process_containment as containment
        with self._state_lock:
            self.mark_child_started()
            self._child_selection = selection
        try:
            result = run()
        except containment.ContainmentUnavailable:
            # This exception is reserved for failures before a child exists.
            with self._state_lock:
                self._check_owned()
                self._child_started = False
                self._child_selection = None
            raise
        with self._state_lock:
            self._check_owned()
            self._child_failed = result.timed_out or result.exit_code != 0
            self._child_completed = True
            self._child_started = False
        return result

    def publish(self, request, candidate, build_receipt):
        with self._state_lock:
            return self._publish_locked(request, candidate, build_receipt)

    def _publish_locked(self, request, candidate, build_receipt):
        _require(self._active, 'Build lifecycle is not active')
        self._check_owned()
        _require(self._selected,
                 'An ordinary or engine-only build cannot publish a project selector')
        _require(not self._child_started,
                 'Child lifetime is not verified; publication is unavailable')
        _require(self._child_completed,
                 'No contained Build child has completed')
        _require(not self._child_failed,
                 'Failed or timed-out child cannot publish a project selector')
        _require(self._child_selection == (Path(request), Path(candidate)),
                 'Publication must match the contained Build request and candidate')
        selector = validate(self.project, request, candidate, build_receipt)
        _require(selector['build_id'] == self.build_id,
                 'Build receipt belongs to another lifecycle')
        build = _json(_file(build_receipt))
        _require(build.get('root') == str(self.engine),
                 'Build receipt belongs to another engine')
        path = Path(str(self.project) + '.lyra-build-latest.json')
        previous = _existing(path, self.project)
        if previous is not None and previous['kind'] == KIND:
            _require(previous['generation'] <= selector['generation'],
                     'Out-of-order Save generation refused')
        raw = (json.dumps(selector, sort_keys=True, indent=2) + '\n').encode()
        temporary = _temporary(path, raw)
        try:
            self._check_owned()
            _require(validate(self.project, request, candidate, build_receipt) == selector,
                     'Build or Save changed before selector publication')
            self._check_owned()
            os.replace(temporary, path)
            _sync_dir(path.parent)
            _require(path.read_bytes() == raw, 'Selector readback differs')
        finally:
            temporary.unlink(missing_ok=True)
        return selector

    def release(self):
        """Release only when no child lifetime remains uncertain."""
        with self._state_lock:
            _require(self._active, 'Build lifecycle is not active')
            self._check_owned()
            self._release_if_quiescent()


def begin_attempt(project, engine):
    """Acquire both sentinels and return an owned, not-yet-started lifecycle."""
    return BuildSession(project, engine).begin()


def begin_engine_build(engine):
    """Acquire the shared engine sentinel for an ordinary, non-Lyra build."""
    return BuildSession(None, engine, selected=False).begin()


def begin_project_build(project, engine):
    """Acquire both sentinels for an ordinary build with a known project."""
    return BuildSession(project, engine, selected=False).begin()


