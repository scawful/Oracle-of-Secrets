"""Prepare one project-bound Mesen profile and explicit launch inputs.

An explicit receipt-bound private app can run one bounded headless diagnostic.
The guardian owns its direct child and inherited channel. This is private-profile
isolation, not an OS sandbox. A token correlates a child; it does not authenticate it.
The explicit desktop route retains a direct GUI child and a private ROM copy,
publishes verified readiness once, and supervises that child until owned exit.
No socket discovery, existing session reuse, save copying, or stale-lock recovery
is performed. Failed/uncertain preparation retains its marker for inspection.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from yaze_dedicated_profile import prepare_settings, verify_existing_settings


def _canonical(path: Path, *, exists: bool = True) -> Path:
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=exists) != path:
        raise ValueError('Dedicated session paths must be canonical and absolute')
    if 'oos-rc-play' in str(path):
        raise ValueError('The protected session cannot be selected')
    return path


def _private_directory(path: Path) -> os.stat_result:
    _canonical(path)
    value = path.lstat()
    if (not stat.S_ISDIR(value.st_mode) or value.st_uid != os.geteuid()
            or stat.S_IMODE(value.st_mode) != 0o700):
        raise ValueError('Dedicated profile directories must be owned and mode 0700')
    return value


def _require_anchored_operations() -> None:
    required = (os.open, os.mkdir, os.stat, os.unlink, os.rmdir)
    if (not all(hasattr(os, name) for name in ('O_NOFOLLOW', 'O_DIRECTORY'))
            or not all(operation in os.supports_dir_fd for operation in required)
            or os.listdir not in os.supports_fd
            or os.stat not in os.supports_follow_symlinks):
        raise ValueError('Anchored directory operations are unavailable; no profile writes allowed')


def _same_directory(left: os.stat_result, right: os.stat_result) -> bool:
    return (stat.S_ISDIR(left.st_mode) and stat.S_ISDIR(right.st_mode)
            and (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino))


def _open_directory_at(parent_fd: int, name: str, *, private=False) -> int:
    if not name or name in ('.', '..') or '/' in name:
        raise ValueError('Expected one directory entry name')
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=parent_fd)
    except OSError as error:
        raise ValueError('Cannot open canonical directory without aliases') from error
    try:
        value = os.fstat(fd)
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _same_directory(value, entry):
            raise ValueError('Directory ownership changed during open')
        if private and (value.st_uid != os.geteuid()
                        or stat.S_IMODE(value.st_mode) != 0o700):
            raise ValueError('Dedicated profile directories must be owned and mode 0700')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_private_root(path: Path) -> int:
    expected = _private_directory(path)
    # Walk from / with O_NOFOLLOW on every component, not just the leaf.
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in path.parts[1:]:
            child = _open_directory_at(fd, name)
            os.close(fd)
            fd = child
        actual = os.fstat(fd)
        if (not _same_directory(expected, actual) or actual.st_uid != os.geteuid()
                or stat.S_IMODE(actual.st_mode) != 0o700):
            raise ValueError('Profile root ownership changed during open')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_regular(path: Path, limit: int) -> bytes:
    _canonical(path)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size > limit):
            raise ValueError('Expected one bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
                                  value.st_nlink, value.st_uid, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        if (identity(before) != identity(after)
                or identity(path.lstat()) != identity(after)
                or len(data) != before.st_size):
            raise ValueError('File changed during dedicated session preparation')
        return data
    finally:
        os.close(fd)


def _read_regular_at(directory_fd: int, name: str, limit: int) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size > limit):
            raise ValueError('Expected one bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
                                  value.st_nlink, value.st_uid, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        if (identity(before) != identity(after) or identity(entry) != identity(after)
                or len(data) != before.st_size):
            raise ValueError('File changed during dedicated session preparation')
        return data
    finally:
        os.close(fd)


def _write_new_at(directory_fd: int, name: str, data: bytes) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def _verify_profile_files(profile_fd: int) -> None:
    # A symlink/hardlink inside Saves would redirect writes despite safe folder
    # settings. Refuse any such alias in the private profile before admission.
    count = 0
    def visit(directory_fd: int, depth: int) -> None:
        nonlocal count
        if depth > 100:
            raise ValueError('Dedicated profile directory nesting is excessive')
        # listdir(fd), statat and openat errors are fatal. Never silently skip an
        # unreadable subtree, and never follow a substituted directory symlink.
        names = os.listdir(directory_fd)
        for name in names:
            count += 1
            value = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (count > 10000 or stat.S_ISLNK(value.st_mode)
                    or not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode))
                    or (stat.S_ISREG(value.st_mode) and value.st_nlink != 1)):
                raise ValueError('Dedicated profile contains unsupported file aliases')
            if stat.S_ISDIR(value.st_mode):
                child = _open_directory_at(directory_fd, name)
                try:
                    if not _same_directory(value, os.fstat(child)):
                        raise ValueError('Profile directory changed during traversal')
                    visit(child, depth + 1)
                    if not _same_directory(os.fstat(child), os.stat(
                            name, dir_fd=directory_fd, follow_symlinks=False)):
                        raise ValueError('Profile directory changed during traversal')
                finally:
                    os.close(child)
        if set(os.listdir(directory_fd)) != set(names):
            raise ValueError('Profile entries changed during traversal')
    visit(profile_fd, 0)


@dataclass(frozen=True)
class DedicatedLaunchPlan:
    """Prepared inputs only; this is not evidence of a launched/owned process."""

    project_path: str
    rom_path: str
    profile_path: str
    socket_path: str
    session_token: str
    instance_guid: str
    rom_sha256: str
    rom_sha1: str
    rom_size: int

    def child_environment(self, base: dict[str, str]) -> dict[str, str]:
        if not self.socket_path:
            raise ValueError('No admitted socket/process supervisor; launch is unavailable')
        _canonical(Path(self.socket_path), exists=False)
        # Do not inherit Mesen identity, loader, .NET or plugin injection values.
        allowed = {'HOME', 'PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'USER', 'LOGNAME'}
        result = {key: value for key, value in base.items() if key in allowed}
        result.update({
            'MESEN2_HOME': self.profile_path,
            'MESEN2_SOCKET_PATH': self.socket_path,
            'MESEN2_INSTANCE_GUID': self.instance_guid,
            'MESEN2_INSTANCE': Path(self.profile_path).name,
            'MESEN2_YAZE_RUN_TOKEN': self.session_token,
            'MESEN2_AGENT_TITLE': 'Yaze Oracle',
            'MESEN2_AGENT_SOURCE': 'yaze',
            'MESEN2_AGENT_ACTIVE': '1',
        })
        return result


class PreparedDedicatedSession:
    """Durable fail-closed reservation; only pre-launch cancellation is allowed.

    The marker prevents other cooperating preparations using this helper. It
    does not prove that an arbitrary process outside this protocol is absent.
    It must not be treated as native-launch admission or an OS security boundary.
    """

    def __init__(self, plan: DedicatedLaunchPlan, owner: bytes,
                 root_fd: int, profile_fd: int, lease_fd: int):
        self.plan = plan
        self._root_fd = root_fd
        self._profile_fd = profile_fd
        self._lease_fd = lease_fd
        self._owner = owner
        self._launch_started = False
        self._released = False

    def _close_descriptors(self) -> None:
        # Closing descriptors never reclaims an uncertain reservation.
        for name in ('_lease_fd', '_profile_fd', '_root_fd'):
            fd = getattr(self, name, -1)
            if fd >= 0:
                os.close(fd)
                setattr(self, name, -1)

    def __del__(self):
        self._close_descriptors()

    def mark_launch_started(self) -> None:
        """Latch BEFORE spawning; any uncertain spawn keeps the reservation."""
        self._verify_owner()
        self._launch_started = True

    def _verify_directories(self) -> None:
        if self._released:
            raise ValueError('Dedicated session reservation already released')
        profile = Path(self.plan.profile_path)
        root = _canonical(profile.parent)
        if (not _same_directory(root.lstat(), os.fstat(self._root_fd))
                or not _same_directory(os.stat(profile.name, dir_fd=self._root_fd,
                                                follow_symlinks=False),
                                       os.fstat(self._profile_fd))
                or not _same_directory(os.stat('.yaze-session', dir_fd=self._profile_fd,
                                                follow_symlinks=False),
                                       os.fstat(self._lease_fd))):
            raise ValueError('Dedicated session reservation identity changed')

    def _verify_owner(self) -> None:
        self._verify_directories()
        if _read_regular_at(self._lease_fd, 'owner.json', 4096) != self._owner:
            raise ValueError('Dedicated session reservation identity changed')

    def cancel_before_launch(self) -> None:
        self._verify_owner()
        if self._launch_started:
            raise ValueError('Child exit is unproven; retain dedicated profile reservation')
        if set(os.listdir(self._lease_fd)) != {'owner.json'}:
            raise ValueError('Unexpected reservation files; retain for inspection')
        os.unlink('owner.json', dir_fd=self._lease_fd)
        self._verify_directories()
        # Even if an ancestor is renamed after validation, these operations
        # target the held directories. rmdir never follows a leaf symlink.
        if not _same_directory(os.stat('.yaze-session', dir_fd=self._profile_fd,
                                       follow_symlinks=False),
                               os.fstat(self._lease_fd)):
            raise ValueError('Reservation entry changed; retain directory')
        os.rmdir('.yaze-session', dir_fd=self._profile_fd)
        self._released = True
        self._close_descriptors()


_DIAGNOSTIC_PREFERENCES = {
    'GameSelectionScreenMode': 'Disabled',
    'EnableAutoSaveState': False,
}


def _verify_diagnostic_settings(raw: bytes) -> None:
    verify_existing_settings(raw)
    preferences = json.loads(raw)['Preferences']
    for name, expected in _DIAGNOSTIC_PREFERENCES.items():
        if (type(preferences.get(name)) is not type(expected)
                or preferences[name] != expected):
            raise ValueError('Headless diagnostic requires ' + name + '=' + repr(expected))


def prepare_session(*, project_path: Path, rom_path: Path,
                    verified_rom_bytes: bytes, profiles_root: Path,
                    settings_bytes: bytes | None = None,
                    diagnostic: bool = False, ordinary_selection=None) -> PreparedDedicatedSession:
    """Reserve stable save/profile identity without starting any executable.

    The caller must already hold its project/Build receipt lease and supply the
    exact receipt-verified bytes. That receipt is not validated here. A new
    profile requires explicitly selected settings bytes; existing settings and
    Saves/SaveStates are never replaced. No existing user profile is adopted.
    Only an explicitly diagnostic new profile disables state snapshots.
    """
    if os.name != 'posix':
        raise ValueError('Dedicated profile preparation is unsupported on this platform')
    _require_anchored_operations()
    project = _canonical(project_path)
    rom = _canonical(rom_path)
    root = _canonical(profiles_root)
    _read_regular(project, 16 * 1024 * 1024)
    if ordinary_selection is None:
        if type(verified_rom_bytes) is not bytes or len(verified_rom_bytes) != 0x400000:
            raise ValueError('A receipt-verified 4 MiB headerless ROM is required')
    else:
        if diagnostic:
            raise ValueError('Ordinary selection is not a diagnostic admission')
        selector, selected, _ = _ordinary_selection(ordinary_selection, project)
        if selector['candidate']['path'] != str(rom) or selected != verified_rom_bytes:
            raise ValueError('Ordinary selection does not bind the supplied ROM')
    if _read_regular(rom, 0x400000) != verified_rom_bytes:
        raise ValueError('Selected ROM does not match the receipt-verified bytes')
    name = 'yaze-' + hashlib.sha256(str(project).encode()).hexdigest()[:32]
    profile = root / name
    binding = {'version': 1, 'project_path': str(project), 'rom_filename': rom.name}
    root_fd = _open_private_root(root)
    profile_fd = lease_fd = -1
    try:
        try:
            os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            fresh = False
        except FileNotFoundError:
            fresh = True
        if fresh:
            if settings_bytes is None:
                raise ValueError('New dedicated profile requires explicit settings')
            settings = prepare_settings(settings_bytes)
            if diagnostic:
                document = json.loads(settings)
                preferences = document['Preferences']
                protected = {key.casefold() for key in _DIAGNOSTIC_PREFERENCES}
                for key in list(preferences):
                    if key.casefold() in protected:
                        del preferences[key]
                preferences.update(_DIAGNOSTIC_PREFERENCES)
                settings = _json_bytes(document)
            os.mkdir(name, mode=0o700, dir_fd=root_fd)
        profile_fd = _open_directory_at(root_fd, name, private=True)
        # mkdir fails for a live, stale, or uncertain owner. Never steal/delete it.
        os.mkdir('.yaze-session', mode=0o700, dir_fd=profile_fd)
        lease_fd = _open_directory_at(profile_fd, '.yaze-session', private=True)
        token = secrets.token_hex(16)
        owner = _json_bytes({'version': 1, 'session_token': token,
                             'project_path': str(project), 'profile_path': str(profile)})
        _write_new_at(lease_fd, 'owner.json', owner)
        if fresh:
            _write_new_at(profile_fd, 'settings.json', settings)
            _write_new_at(profile_fd, '.yaze-profile.json', _json_bytes(binding))
            _write_new_at(profile_fd, 'instance_guid.txt', str(uuid.uuid4()).encode())
            os.mkdir('Saves', mode=0o700, dir_fd=profile_fd)
            os.mkdir('SaveStates', mode=0o700, dir_fd=profile_fd)
        else:
            if settings_bytes is not None:
                raise ValueError('Existing profile settings must not be reseeded')
            if _read_regular_at(profile_fd, '.yaze-profile.json', 4096) != _json_bytes(binding):
                raise ValueError('Existing profile project/save identity differs')
            verify_existing_settings(_read_regular_at(profile_fd, 'settings.json', 16 * 1024 * 1024))
        for directory in ('Saves', 'SaveStates'):
            fd = _open_directory_at(profile_fd, directory, private=True)
            os.close(fd)
        _verify_profile_files(profile_fd)
        guid = _read_regular_at(profile_fd, 'instance_guid.txt', 64).decode('ascii')
        if str(uuid.UUID(guid)) != guid:
            raise ValueError('Invalid dedicated instance GUID')
        # Empty endpoint prevents preparation being mistaken for Run readiness.
        plan = DedicatedLaunchPlan(str(project), str(rom), str(profile), '', token, guid,
                                   hashlib.sha256(verified_rom_bytes).hexdigest(),
                                   hashlib.sha1(verified_rom_bytes).hexdigest(),
                                   len(verified_rom_bytes))
        prepared = PreparedDedicatedSession(plan, owner, root_fd, profile_fd, lease_fd)
        # Transfer descriptor ownership before the last path/owner recheck.
        root_fd = profile_fd = lease_fd = -1
        prepared._verify_owner()
        return prepared
    finally:
        for fd in (lease_fd, profile_fd, root_fd):
            if fd >= 0:
                os.close(fd)


_REVIEWED_MESEN_SOURCE = 'a23e212da434fc7ee0991eaf613cdf03ddfc432ede44ce2f9e0c8f08a89c3d0c'
_REVIEWED_DESKTOP_MESEN_SOURCE = '9be0b13efb1e65f4896a6857f9e824e6c88668e6f574039e087e5c17d89cc693'


def _read_hashed(path: Path, expected: str, limit: int) -> bytes:
    if (type(expected) is not str or len(expected) != 64
            or any(c not in '0123456789abcdef' for c in expected)):
        raise ValueError('An explicit SHA-256 is required')
    data = _read_regular(path, limit)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Private diagnostic input hash differs: ' + str(path))
    return data


def _verify_private_app(binding: dict, *, desktop=False) -> dict:
    """Recheck the caller-selected reviewed receipt and complete private bundle."""
    if type(binding) is not dict or set(binding) != {
            'app_path', 'receipt_sha256', 'bundle_manifest_path', 'bundle_manifest_sha256'}:
        raise ValueError('Explicit private app receipt and bundle manifest are required')
    app = _canonical(Path(binding['app_path']))
    _private_directory(app.parent)
    if app.suffix != '.app' or app.is_relative_to('/Applications'):
        raise ValueError('Select an owned private app, never an installed app')
    receipt = json.loads(_read_hashed(app / 'Contents/Resources/oos-build.json',
                                     binding['receipt_sha256'], 1024 * 1024))
    reviewed_source = _REVIEWED_DESKTOP_MESEN_SOURCE if desktop else _REVIEWED_MESEN_SOURCE
    if (receipt.get('schema_version') != 2
            or receipt.get('reviewed_freeze_sha256') != reviewed_source
            or receipt.get('contains_channel_greeting') is not True
            or receipt.get('contains_frame_count') is not True):
        raise ValueError('Private app lacks the reviewed restricted lifetime implementation')
    if desktop and receipt.get('contains_private_desktop_loader') is not True:
        raise ValueError('Private app lacks the reviewed private desktop loader')
    manifest = json.loads(_read_hashed(Path(binding['bundle_manifest_path']),
                                      binding['bundle_manifest_sha256'], 4 * 1024 * 1024))
    if type(manifest) is not dict or not 3 <= len(manifest) <= 1000:
        raise ValueError('Invalid private bundle manifest')
    names = {str(p.relative_to(app)) for p in app.rglob('*') if not p.is_dir()}
    if names != set(manifest):
        raise ValueError('Private bundle inventory differs')
    for name, entry in manifest.items():
        path = app / name
        if (Path(name).is_absolute() or '..' in Path(name).parts
                or type(entry) is not dict or entry.get('kind') != 'file'
                or type(entry.get('bytes')) is not int or not 0 <= entry['bytes'] <= 256 * 1024 * 1024):
            raise ValueError('Unsupported private bundle entry')
        data = _read_hashed(path, entry['sha256'], entry['bytes'])
        if len(data) != entry['bytes'] or stat.S_IMODE(path.stat().st_mode) != entry['mode']:
            raise ValueError('Private bundle size/mode differs')
    for name, field in [('MesenCore.dylib', 'core_sha256'), ('Mesen.dll', 'managed_sha256')]:
        if manifest['Contents/MacOS/' + name]['sha256'] != receipt.get(field):
            raise ValueError('Private receipt binary identity differs')
    executable = app / 'Contents/MacOS/Mesen'
    if not os.access(executable, os.X_OK):
        raise ValueError('Private apphost is not executable')
    return {'executable': str(executable), 'core_sha256': receipt['core_sha256']}


def _verify_private_launch_inputs(prepared: PreparedDedicatedSession, private_root: Path) -> None:
    _private_directory(private_root)
    plan = prepared.plan
    for value in (plan.rom_path, plan.profile_path):
        path = _canonical(Path(value))
        if path == private_root or not path.is_relative_to(private_root):
            raise ValueError('Diagnostic ROM and profile must be inside the explicit private root')
    _read_hashed(Path(plan.rom_path), plan.rom_sha256, 0x400000)
    if Path(plan.rom_path).stat().st_mode & 0o222:
        raise ValueError('Private diagnostic ROM must be read-only')
    prepared._verify_owner()
    _verify_profile_files(prepared._profile_fd)
    if _read_regular_at(prepared._profile_fd, 'instance_guid.txt', 64).decode() != plan.instance_guid:
        raise ValueError('Dedicated profile GUID changed')
    _verify_diagnostic_settings(_read_regular_at(prepared._profile_fd, 'settings.json', 16 * 1024 * 1024))


def launch_dedicated_mesen(prepared: PreparedDedicatedSession, *, app_binding=None,
                           private_root=None, timeout=10, owner='codex-yaze-diagnostic') -> dict:
    """Run the explicitly selected private diagnostic; never discover a session."""
    prepared._verify_owner()
    if app_binding is None or private_root is None:
        raise RuntimeError('No reviewed Mesen private app and input root were supplied')
    if type(owner) is not str or not owner.strip() or len(owner) > 120:
        raise ValueError('An explicit diagnostic lease owner is required')
    _verify_private_launch_inputs(prepared, Path(private_root))
    app = _verify_private_app(app_binding)
    return _run_guardian(prepared, timeout=timeout, mesen={
        **app, 'binding': app_binding, 'private_root': str(private_root),
        'instance_guid': prepared.plan.instance_guid, 'owner': owner})


def _native_lock_module():
    path = Path(__file__).resolve().parents[1] / 'Agents/heavy_lock.py'
    spec = importlib.util.spec_from_file_location('yaze_native_lock', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Fixed, reviewable fixture graph: one Python process, no subprocess/fork/exec,
# no site initialization, no game execution, no ROM/settings/save writes.
_SYNTHETIC_CHILD = r'''
import hashlib, json, os, socket
from pathlib import Path
rom = Path(os.environ['YAZE_FIXTURE_ROM']).read_bytes()
identity = {'kind': 'snes_prg_rom', 'size': len(rom),
            'sha1': hashlib.sha1(rom).hexdigest(),
            'session': os.environ['MESEN2_YAZE_RUN_TOKEN']}
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
    listener.bind(os.environ['MESEN2_SOCKET_PATH'])
    listener.listen(1)
    connection, _ = listener.accept()
    with connection, connection.makefile('rb') as stream:
        for line in stream:
            request = json.loads(line)
            if request == {'type': 'PING'}:
                data = {'pong': True}
            elif request == {'type': 'LOADED_ROM_IDENTITY'}:
                data = identity
            else:
                raise ValueError('Unexpected fixture command')
            connection.sendall((json.dumps({'success': True, 'data': data}) + '\n').encode())
'''


def _run_synthetic_lifecycle(prepared: PreparedDedicatedSession, *, timeout=5,
                             after_peer_check=None) -> dict:
    """Exercise the fixed fixture graph only; never accept an executable argument.

    Reuse the existing macOS fixture group mechanics. A leader PID stays unreaped
    until signaling is complete. Group absence proves cleanup only for this
    fixed graph, whose source has no detached writers. Any error retains the
    profile reservation even when best-effort fixture cleanup succeeds.
    """
    if (sys.platform != 'darwin' or type(timeout) not in (int, float)
            or not 0 < timeout <= 30):
        raise ValueError('macOS and a bounded synthetic timeout are required')
    import lyra_macos_process_group as group

    prepared._verify_owner()
    _verify_profile_files(prepared._profile_fd)
    socket_dir = Path(tempfile.mkdtemp(prefix='yaze-mesen-', dir='/private/tmp'))
    plan = replace(prepared.plan, socket_path=str(socket_dir / 'session.sock'))
    prepared.plan = plan
    environment = plan.child_environment({'PATH': '/usr/bin:/bin',
                                           'HOME': plan.profile_path,
                                           'TMPDIR': str(socket_dir), 'LANG': 'C'})
    environment['YAZE_FIXTURE_ROM'] = plan.rom_path
    process = None
    reaped = False
    connection = None
    socket_identity = None
    prepared.mark_launch_started()
    deadline = time.monotonic() + timeout
    try:
        process = subprocess.Popen([sys.executable, '-I', '-S', '-c', _SYNTHETIC_CHILD],
                                   cwd=plan.profile_path, env=environment,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        while not Path(plan.socket_path).exists():
            if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
                raise RuntimeError('Synthetic child exited before socket readiness')
            if time.monotonic() >= deadline:
                raise TimeoutError('Synthetic socket readiness timed out')
            time.sleep(.01)
        socket_identity = Path(plan.socket_path).lstat()
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(max(.01, deadline - time.monotonic()))
        connection.connect(plan.socket_path)
        # Darwin sys/un.h: SOL_LOCAL=0, LOCAL_PEERPID=2; Python omits these names.
        peer = struct.unpack('i', connection.getsockopt(0, 2, struct.calcsize('i')))[0]
        if peer != process.pid:
            raise RuntimeError('Synthetic peer is not the unreaped owned child')
        if after_peer_check is not None:
            after_peer_check(plan, process.pid)
        with connection.makefile('rb') as stream:
            for command in ('PING', 'LOADED_ROM_IDENTITY'):
                connection.sendall(_json_bytes({'type': command}))
                line = stream.readline(4097)
                if len(line) > 4096:
                    raise ValueError('Oversized synthetic response')
                reply = json.loads(line)
                expected = ({'pong': True} if command == 'PING' else
                            {'kind': 'snes_prg_rom', 'size': plan.rom_size,
                             'sha1': plan.rom_sha1, 'session': plan.session_token})
                if reply != {'success': True, 'data': expected}:
                    raise ValueError('Synthetic loaded identity mismatch')
        connection.close()
        connection = None
        while True:
            exited = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            members = group._live_group_members(process.pid)
            if exited is not None and not members:
                code = process.wait()
                reaped = True
                group._wait_group_gone(process.pid, deadline)
                if code != 0:
                    raise RuntimeError('Synthetic child exited unsuccessfully')
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Synthetic child completion timed out')
            time.sleep(.01)
        current = Path(plan.socket_path).lstat()
        if ((current.st_dev, current.st_ino) !=
                (socket_identity.st_dev, socket_identity.st_ino)):
            raise ValueError('Synthetic socket ownership changed')
        Path(plan.socket_path).unlink()
        socket_dir.rmdir()
        prepared._launch_started = False
        prepared.cancel_before_launch()
        return {'pid': process.pid, 'peer_pid': peer, 'exit_code': code,
                'rom_sha1': plan.rom_sha1, 'profile_path': plan.profile_path}
    except BaseException:
        if connection is not None:
            connection.close()
        if process is not None and not reaped:
            try:
                # No signal after reaping: otherwise the PID/group may be reused.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
                reaped = True
                group._wait_group_gone(process.pid, time.monotonic() + 1)
            except (OSError, subprocess.SubprocessError, group.ContainmentUncertain):
                pass
        # Keep marker and endpoint artifacts. They record an uncertain episode.
        raise


# A separate, fixed socketpair fixture. This does not launch Mesen or install a
# filesystem sandbox. In particular, the guardian itself still has host access.
_SOCKETPAIR_CHILD = r'''
import fcntl, hashlib, json, os, socket, struct, sys, time
from pathlib import Path
commands_read = 0
peer = None
try:
    owner = int(os.environ['FIXTURE_OWNER'])
    if os.getppid() != owner:
        raise ValueError('Direct parent differs from guardian')
    connection = socket.socket(fileno=3)
    if (connection.family != socket.AF_UNIX or
            connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM):
        raise ValueError('Control FD is not a Unix stream')
    peer = struct.unpack('i', connection.getsockopt(0, 2, 4))[0]
    if peer != owner:
        raise ValueError('Control peer differs from guardian')
    descriptors = []
    for fd in sorted(int(name) for name in os.listdir('/dev/fd')):
        try:
            value = os.fstat(fd)
        except OSError:
            continue
        descriptors.append({'fd': fd, 'device': value.st_dev, 'inode': value.st_ino,
                            'mode': value.st_mode,
                            'access': fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE})
    if [entry['fd'] for entry in descriptors] != [0, 1, 2, 3]:
        raise ValueError('Unexpected inherited descriptor')
    if os.getsid(0) != os.getpid() or os.getpgrp() != os.getpid():
        raise ValueError('Child is not its own session/group leader')
    metadata = {'pid': os.getpid(), 'ppid': os.getppid(), 'peer_pid': peer,
                'sid': os.getsid(0), 'pgid': os.getpgrp(), 'descriptors': descriptors}
    # Emit nothing until parent/socket/FD checks finish. This is a fixture
    # preflight observation, not authentication of an arbitrary process.
    print(json.dumps({'checked': metadata, 'commands_read': 0}), flush=True)
    scenario = os.environ['FIXTURE_SCENARIO']
    ready = {'event': 'YAZE_DIAGNOSTIC_CHANNEL_READY', 'version': 1, 'pid': os.getpid()}
    if scenario == 'ready-pid':
        ready['pid'] += 1
    elif scenario == 'ready-version':
        ready['version'] = True
    elif scenario == 'ready-extra':
        ready['fixture'] = metadata
    connection.sendall((json.dumps(ready) + '\n').encode())
    rom = Path(os.environ['FIXTURE_ROM']).read_bytes()
    identity = {'kind': 'snes_prg_rom', 'size': len(rom),
                'sha1': hashlib.sha1(rom).hexdigest(),
                'session': os.environ['FIXTURE_TOKEN'], 'frameCount': 0}
    if scenario == 'identity-mismatch':
        identity['sha1'] = 'f' * 40
    elif scenario == 'frame-count-missing':
        del identity['frameCount']
    elif scenario == 'frame-count-bool':
        identity['frameCount'] = False
    elif scenario == 'frame-count-range':
        identity['frameCount'] = 0x100000000
    elif scenario == 'frame-count-advanced':
        identity['frameCount'] = 7
    with connection, connection.makefile('rb') as stream:
        for command in ('PING', 'LOADED_ROM_IDENTITY'):
            if scenario == 'timeout':
                time.sleep(60)
            line = stream.readline(4097)
            if not line or len(line) > 4096 or json.loads(line) != {'type': command}:
                raise ValueError('Unexpected fixture command')
            commands_read += 1
            print(json.dumps({'command': command, 'commands_read': commands_read}), flush=True)
            reply = {'success': True,
                     'data': 'PONG' if command == 'PING' else identity}
            if scenario == 'legacy-ping' and command == 'PING':
                reply['data'] = {'pong': True}
            connection.sendall((json.dumps(reply) + '\n').encode())
except BaseException as error:
    print(json.dumps({'refused': str(error), 'commands_read': commands_read,
                      'peer_pid': peer}), flush=True)
    sys.exit(78)
'''


class SyntheticGuardianError(RuntimeError):
    """A fixed-fixture failure; its reservation must remain held."""

    def __init__(self, message, observation=None):
        super().__init__(message)
        self.observation = observation


def _socketpair_interpreter() -> Path:
    # Homebrew bin/python is a launcher which may posix_spawn the framework
    # executable. Use this exact interpreter implementation for PID continuity;
    # this narrow host fixture does not admit another runtime graph.
    executable = Path(sys.base_prefix) / 'Resources/Python.app/Contents/MacOS/Python'
    executable = _canonical(executable.resolve(strict=True))
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError('Exact macOS framework fixture interpreter is unavailable')
    return executable


def _fixture_peer_pid(connection: socket.socket) -> int:
    return struct.unpack('i', connection.getsockopt(0, 2, 4))[0]


def _canonical_identity_reply(reply: dict) -> dict:
    """SHA1 hex case is representational; no other identity field is relaxed."""
    data = reply.get('data')
    digest = data.get('sha1') if type(data) is dict else None
    if (type(digest) is str and len(digest) == 40
            and all(character in '0123456789abcdefABCDEF' for character in digest)):
        return {**reply, 'data': {**data, 'sha1': digest.lower()}}
    return reply


def _identity_mismatch_evidence(reply: dict, expected: dict) -> list[dict]:
    """Bounded field evidence. Never retain either expected or observed tokens."""
    data = reply.get('data')
    actual = data if type(data) is dict else {}
    tokens = [value for value in (expected.get('session'), actual.get('session'))
              if type(value) is str and value]

    def value(field, item):
        if field == 'session':
            return '<redacted>'
        if type(item) not in (str, int, bool, type(None)):
            return '<' + type(item).__name__ + '>'
        if type(item) is str:
            for token in tokens:
                item = item.replace(token, '<redacted>')
            return item[:160]
        return item

    records = []
    if set(reply) != {'success', 'data'}:
        records.append({'field': 'envelope.keys', 'expected': ['data', 'success'],
                        'observed': '<unexpected or missing keys>'})
    if reply.get('success') is not True:
        records.append({'field': 'success', 'expected': True,
                        'observed': value('success', reply.get('success'))})
    if 'error' in reply:
        records.append({'field': 'error', 'expected': None,
                        'observed': value('error', reply['error'])})
    if type(data) is not dict or set(data) != set(expected):
        records.append({'field': 'data.keys', 'expected': sorted(expected),
                        'observed': '<unexpected or missing keys>'})
    for field, wanted in expected.items():
        observed = actual.get(field)
        if type(observed) is not type(wanted) or observed != wanted:
            records.append({'field': field, 'expected': value(field, wanted),
                            'observed': value(field, observed)})
    return records


def _fixture_line(fd: int, deadline: float, control=None) -> dict:
    # Read one bounded frame without buffering away liveness/cancellation.
    data = bytearray()
    while b'\n' not in data:
        if control is not None:
            control()
        if time.monotonic() >= deadline:
            raise TimeoutError('Synthetic guardian deadline exceeded')
        if select.select([fd], [], [], .02)[0]:
            value = os.read(fd, 1)
            if not value:
                raise SyntheticGuardianError('Synthetic endpoint closed before reply')
            data.extend(value)
            if len(data) > 4096:
                raise SyntheticGuardianError('Oversized synthetic guardian frame')
    value = json.loads(data)
    if type(value) is not dict:
        raise SyntheticGuardianError('Invalid synthetic guardian frame')
    return value


def _socketpair_guardian(config: dict) -> int:
    """Direct parent of a fixed fixture or explicitly bound private Mesen app.

    The guardian creates the pair. Darwin peer PIDs in this fixture change after
    socket traffic, rather than always recording the creator. Child identity therefore
    relies on the reserved fork PID, gated exec and exclusive endpoint custody;
    LOCAL_PEERPID alone does not authenticate either endpoint.
    """
    import lyra_macos_process_group as group
    import resource

    control_fd, report_fd = config['control_fd'], config['report_fd']
    deadline = time.monotonic() + config['timeout']
    permission = False
    control_buffer = bytearray()
    pid = None
    reaped = False
    ready_read = ready_write = gate_read = gate_write = None
    parent_endpoint = child_endpoint = None
    observation = {'guardian_pid': os.getpid(), 'child_pid': None,
                   'quiescent': False, 'success': False}
    mesen = config.get('mesen')
    if mesen:
        if _verify_private_app(mesen['binding']) != {
                'executable': mesen['executable'], 'core_sha256': mesen['core_sha256']}:
            raise ValueError('Private executable binding changed')

    def report(value):
        # One bounded write by the sole report writer, also retained in an owned
        # guardian log if the supervisor died and no report reader remains.
        line = _json_bytes(value)
        if len(line) > 4096:
            raise SyntheticGuardianError('Oversized guardian report')
        print(line.decode().rstrip(), flush=True)
        try:
            if os.write(report_fd, line) != len(line):
                raise SyntheticGuardianError('Partial guardian report')
        except BrokenPipeError:
            pass

    def control():
        nonlocal permission
        if select.select([control_fd], [], [], 0)[0]:
            data = os.read(control_fd, 64)
            if not data:
                raise SyntheticGuardianError('Supervisor liveness pipe reached EOF')
            control_buffer.extend(data)
            if len(control_buffer) > 64:
                raise SyntheticGuardianError('Oversized guardian command')
            while b'\n' in control_buffer:
                command, _, rest = control_buffer.partition(b'\n')
                control_buffer[:] = rest
                if command == b'RUN' and not permission:
                    permission = True
                else:
                    raise SyntheticGuardianError('Synthetic guardian cancelled')

    def finish_child(kill=False):
        nonlocal reaped
        if pid is None or reaped:
            return
        cleanup_deadline = time.monotonic() + 5
        if mesen and not observation.get('shutdown_signal'):
            if os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                os.kill(pid, signal.SIGTERM)
                observation['shutdown_signal'] = 'SIGTERM'
            # FD3 remains connected through verified exit. EOF would make the
            # diagnostic report owner loss instead of completing normal Stop.
            if kill:
                grace = time.monotonic() + 1
                while (time.monotonic() < grace
                       and os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None):
                    time.sleep(.01)
        if kill:
            # A deliberately missing FD closes the endpoint during pre-exec.
            # Allow the fixed child to finish its bounded refusal report before
            # killing it. No wait here reaps/releases the reserved PID.
            refusal_deadline = time.monotonic() + .25
            while (os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None
                   and time.monotonic() < refusal_deadline):
                time.sleep(.01)
            # A positive waitid exit observation makes a kill unnecessary. In
            # particular Darwin may return EPERM when signaling a zombie; that
            # error is never interpreted as absence. Group inspection below and
            # ESRCH after reap remain mandatory.
            if os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.kill(pid, signal.SIGKILL)
        while True:
            exited = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if exited is not None:
                # Inspect the owned group while the leader identity is reserved;
                # never signal after waitpid makes that identity reusable. This
                # is process ownership, not an OS prohibition on detached work.
                members = group._live_group_members(pid)
                if not members:
                    reaped = True
                    _, status = os.waitpid(pid, 0)
                    observation['child_exit'] = os.waitstatus_to_exitcode(status)
                    group._wait_group_gone(pid, cleanup_deadline)
                    if config['scenario'] == 'uncertain-quiescence':
                        raise SyntheticGuardianError('Injected uncertain quiescence observation')
                    observation['quiescent'] = True
                    return
                if kill:
                    # Exit of the leader is not exit of its group. The leader
                    # still reserves this identity while live members are
                    # signaled; uncertainty leaves the reservation held.
                    os.killpg(pid, signal.SIGKILL)
                else:
                    raise SyntheticGuardianError('Unexpected live child-group members')
            if time.monotonic() >= cleanup_deadline:
                raise SyntheticGuardianError('Child quiescence is unproven')
            time.sleep(.01)

    try:
        control()
        if config['scenario'] == 'forwarded-peer':
            parent_endpoint = socket.socket(fileno=config['forwarded_fds'][0])
            child_endpoint = socket.socket(fileno=config['forwarded_fds'][1])
        else:
            parent_endpoint, child_endpoint = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        observation['guardian_peer_pid'] = _fixture_peer_pid(parent_endpoint)
        ready_read, ready_write = os.pipe()
        gate_read, gate_write = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.setsid()
                os.close(ready_read)
                os.close(gate_write)
                os.write(ready_write, b'S')
                os.close(ready_write)
                if os.read(gate_read, 1) != b'R':
                    os._exit(79)
                os.close(gate_read)
                # Child inherits guardian stdio, all owned log/null FDs. The
                # payload never receives report/control/gate/directory/sentinel
                # FDs. Socket mapping occurs before closing every FD above 3.
                os.dup2(config['child_log_fd'], 1)
                os.dup2(config['child_log_fd'], 2)
                os.dup2(child_endpoint.fileno(), 3, inheritable=True)
                os.closerange(4, resource.getrlimit(resource.RLIMIT_NOFILE)[0])
                if config['scenario'] == 'missing-fd':
                    os.close(3)
                elif config['scenario'] == 'wrong-fd':
                    os.dup2(0, 3, inheritable=True)
                environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C',
                               'HOME': config['profile'], 'TMPDIR': config['profile'],
                               'FIXTURE_OWNER': str(os.getppid()),
                               'FIXTURE_ROM': config['rom'], 'FIXTURE_TOKEN': config['token'],
                               'FIXTURE_SCENARIO': config['scenario']}
                if mesen:
                    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C',
                        'HOME': config['profile'], 'TMPDIR': config['profile'],
                        'DOTNET_EnableDiagnostics': '0', 'COMPlus_EnableDiagnostics': '0',
                        'MESEN2_HOME': config['profile'],
                        'MESEN2_INSTANCE_GUID': mesen['instance_guid'],
                        'MESEN2_YAZE_DIAGNOSTIC': '1', 'MESEN2_YAZE_CONTROL_FD': '3',
                        'MESEN2_YAZE_OWNER_PID': str(os.getppid()),
                        'MESEN2_YAZE_RUN_TOKEN': config['token'],
                        'MESEN2_YAZE_CORE_SHA256': mesen['core_sha256']}
                    os.execve(mesen['executable'], [mesen['executable'], '--yaze-diagnostic', config['rom']], environment)
                else:
                    os.execve(config['interpreter'], [config['interpreter'], '-I', '-S', '-B',
                                                    '-c', _SOCKETPAIR_CHILD], environment)
            except BaseException:
                os._exit(79)
        observation['child_pid'] = pid
        child_endpoint.close()
        child_endpoint = None
        os.close(ready_write)
        ready_write = None
        os.close(gate_read)
        gate_read = None
        while not select.select([ready_read], [], [], .02)[0]:
            control()
            if time.monotonic() >= deadline:
                raise TimeoutError('Synthetic child session setup timed out')
        if os.read(ready_read, 1) != b'S':
            raise SyntheticGuardianError('Synthetic child session setup failed')
        os.close(ready_read)
        ready_read = None
        report({'event': 'spawned', **observation})
        while not permission:
            control()
            if time.monotonic() >= deadline:
                raise TimeoutError('Synthetic child publication timed out')
            time.sleep(.01)
        if mesen:
            _verify_private_app(mesen['binding'])
            _read_hashed(Path(config['rom']), config['rom_sha256'], 0x400000)
        os.write(gate_write, b'R')
        os.close(gate_write)
        gate_write = None
        # Do not send PING before channel readiness. A guardian write can change
        # Darwin's recorded peer PID and mask a forwarded-endpoint mistake.
        ready = _fixture_line(parent_endpoint.fileno(), deadline, control)
        if (ready != {'event': 'YAZE_DIAGNOSTIC_CHANNEL_READY', 'version': 1, 'pid': pid}
                or type(ready.get('version')) is not int or type(ready.get('pid')) is not int):
            raise SyntheticGuardianError('Synthetic channel readiness mismatch')
        observation['ready'] = ready
        observation['guardian_peer_pid_after_child_reply'] = _fixture_peer_pid(parent_endpoint)
        if (observation['guardian_peer_pid_after_child_reply'] != pid
                or os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None):
            raise SyntheticGuardianError('Synthetic ready peer is not the live unreaped child')
        # Greeting/peer correlation adds no authentication beyond exclusive
        # pair custody and this fixed gated fork/exec. Diagnostics stay in logs.
        for command in ('PING', 'LOADED_ROM_IDENTITY'):
            attempts = 0
            while True:
                control()
                parent_endpoint.sendall(_json_bytes({'type': command}))
                reply = _fixture_line(parent_endpoint.fileno(), deadline, control)
                attempts += 1
                if (mesen and command == 'LOADED_ROM_IDENTITY'
                        and reply == {'success': False, 'error': 'No SNES cartridge loaded'}):
                    if time.monotonic() + .05 >= deadline:
                        raise TimeoutError('Private Mesen ROM readiness timed out')
                    time.sleep(.05)
                    continue
                break
            if command == 'PING':
                expected = 'PONG'
            else:
                reply = _canonical_identity_reply(reply)
                data = reply.get('data')
                frame_count = data.get('frameCount') if type(data) is dict else None
                expected = {**config['identity'], 'frameCount': 0 if mesen else frame_count}
                evidence = _identity_mismatch_evidence(reply, expected)
                if evidence:
                    print(json.dumps({'event': 'identity_mismatch', 'fields': evidence}), flush=True)
                if type(frame_count) is not int or not 0 <= frame_count <= 0xffffffff:
                    raise SyntheticGuardianError('Synthetic restricted frameCount is invalid')
                if mesen and frame_count != 0:
                    raise SyntheticGuardianError('Private diagnostic completed an emulated frame')
                if evidence:
                    raise SyntheticGuardianError('Synthetic loaded identity mismatch')
                expected = {**config['identity'], 'frameCount': frame_count}
            if type(reply.get('success')) is not bool or reply != {'success': True, 'data': expected}:
                raise SyntheticGuardianError('Synthetic loaded identity mismatch')
            observation['ping' if command == 'PING' else 'identity'] = reply
            if mesen and command == 'LOADED_ROM_IDENTITY':
                observation['identity_attempts'] = attempts
        if not mesen:
            parent_endpoint.close()
            parent_endpoint = None
        finish_child()
        if mesen:
            parent_endpoint.close()
            parent_endpoint = None
        if observation['child_exit'] != 0:
            raise SyntheticGuardianError('Synthetic child failed')
        control()
        if config['scenario'] == 'uncertain-report':
            return 77
        observation['success'] = True
    except BaseException as error:
        observation['error'] = str(error)
        try:
            finish_child(kill=True)
        except BaseException as cleanup_error:
            observation['cleanup_error'] = str(cleanup_error)
    finally:
        for fd in (ready_read, ready_write, gate_read, gate_write):
            if fd is not None:
                os.close(fd)
        for endpoint in (parent_endpoint, child_endpoint):
            if endpoint is not None:
                endpoint.close()
    report({'event': 'result', **observation})
    return 0 if observation['quiescent'] else 76


def _synthetic_socketpair_guardian(config: dict) -> int:
    return _socketpair_guardian(config)


def _run_synthetic_guardian(prepared: PreparedDedicatedSession, *, timeout=5,
                            scenario='normal', after_spawn=None, sentinel_fd=None) -> dict:
    """Run only the fixed diagnostic fixture, never a Mesen executable.

    This exercises descriptor custody and direct-child ownership, not filesystem
    confinement. Any failure retains the marker even after confirmed cleanup.
    A lost guardian leaves cleanup unproven; the supervisor never signals a PID
    which only the guardian can reserve. No production entry calls this helper.
    The fixed child computes identity before serving PING. Real Mesen's possible
    PING-before-ROM readiness and bounded identity retry are not modeled here.
    """
    return _run_guardian(prepared, timeout=timeout, scenario=scenario,
                         after_spawn=after_spawn, sentinel_fd=sentinel_fd)


def _run_guardian(prepared: PreparedDedicatedSession, *, timeout=5,
                  scenario='normal', after_spawn=None, sentinel_fd=None, mesen=None) -> dict:
    scenarios = {'normal', 'forwarded-peer', 'missing-fd', 'wrong-fd',
                 'identity-mismatch', 'timeout', 'uncertain-report',
                 'uncertain-quiescence', 'cancel-before-run',
                 'ready-pid', 'ready-version', 'ready-extra', 'legacy-ping',
                 'frame-count-missing', 'frame-count-bool', 'frame-count-range',
                 'frame-count-advanced'}
    if (sys.platform != 'darwin' or type(timeout) not in (int, float)
            or not 0 < timeout <= 30 or scenario not in scenarios):
        raise ValueError('macOS and a bounded fixed guardian fixture are required')
    interpreter = _socketpair_interpreter()
    prepared._verify_owner()
    _verify_profile_files(prepared._profile_fd)
    control_read, control_write = os.pipe()
    report_read, report_write = os.pipe()
    endpoints = ()
    log_fd = child_log_fd = null_fd = None
    guardian = None
    result = None
    interrupted = False
    previous_handler = None
    lease = lease_token = None
    cleanup_verified = False
    plan = prepared.plan
    prefix = 'socketpair-' + plan.session_token
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        log_fd = os.open(prefix + '-guardian.log', flags, 0o600, dir_fd=prepared._profile_fd)
        child_log_fd = os.open(prefix + '-child.log', flags, 0o600, dir_fd=prepared._profile_fd)
        null_fd = os.open('/dev/null', os.O_RDONLY | os.O_NOFOLLOW)
        inherited = [control_read, report_write, child_log_fd]
        if sentinel_fd is not None:
            value = os.fstat(sentinel_fd)
            if not stat.S_ISREG(value.st_mode) or value.st_uid != os.geteuid():
                raise ValueError('Fixture sentinel must be an owned regular file')
            inherited.append(sentinel_fd)
        if scenario == 'forwarded-peer':
            endpoints = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            inherited.extend(endpoint.fileno() for endpoint in endpoints)
        config = {'control_fd': control_read, 'report_fd': report_write,
                  'child_log_fd': child_log_fd, 'timeout': timeout, 'scenario': scenario,
                  'forwarded_fds': [endpoint.fileno() for endpoint in endpoints],
                  'profile': plan.profile_path, 'rom': plan.rom_path,
                  'token': plan.session_token, 'interpreter': str(interpreter),
                  'identity': {'kind': 'snes_prg_rom', 'size': plan.rom_size,
                               'sha1': plan.rom_sha1, 'session': plan.session_token}}
        if mesen:
            config.update(mesen=mesen, rom_sha256=plan.rom_sha256)
        module_directory = str(Path(__file__).resolve().parent)
        build_directory = str(Path(__file__).resolve().parent.parent / 'Build')
        bootstrap = ('import sys; sys.path[:0]=' + repr([module_directory, build_directory])
                     + '; import yaze_dedicated_session as s; '
                     + 'sys.exit(s._socketpair_guardian(' + repr(config) + '))')
        if threading.current_thread() is threading.main_thread():
            previous_handler = signal.getsignal(signal.SIGTERM)
            def cancel(_signum, _frame):
                nonlocal interrupted
                interrupted = True
            signal.signal(signal.SIGTERM, cancel)
        prepared.mark_launch_started()
        guardian = subprocess.Popen([str(interpreter), '-I', '-S', '-B', '-c', bootstrap],
                                    cwd=plan.profile_path,
                                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C',
                                         'HOME': plan.profile_path, 'TMPDIR': plan.profile_path},
                                    stdin=null_fd, stdout=log_fd, stderr=log_fd,
                                    close_fds=True, pass_fds=tuple(inherited), start_new_session=True)
        os.close(control_read)
        control_read = None
        os.close(report_write)
        report_write = None
        for endpoint in endpoints:
            endpoint.close()
        endpoints = ()
        deadline = time.monotonic() + timeout + 10
        spawned = _fixture_line(report_read, deadline)
        if (spawned.get('event') != 'spawned'
                or spawned.get('guardian_pid') != guardian.pid
                or type(spawned.get('child_pid')) is not int):
            raise SyntheticGuardianError('Unproven guardian spawn publication', spawned)
        if after_spawn is not None:
            after_spawn(spawned)
        if mesen:
            lease = _native_lock_module()
            start = lease.process_start(spawned['child_pid'])
            lease_token = lease.acquire(mesen['owner'], 'Private Yaze/Mesen headless diagnostic',
                                        pid=spawned['child_pid'])
            if not lease_token or start is None or lease.process_start(spawned['child_pid']) != start:
                raise RuntimeError('Native lease unavailable for the gated diagnostic worker')
            spawned['native_lease'] = {'token': lease_token, 'pid': spawned['child_pid'], 'pid_start': start}
            _write_new_at(prepared._profile_fd, prefix + '-native-lease.json', _json_bytes(spawned['native_lease']))
            _verify_private_launch_inputs(prepared, Path(mesen['private_root']))
            # Apply the existing background native policy to our gated worker.
            subprocess.run(['/usr/sbin/taskpolicy', '-b', '-p', str(spawned['child_pid'])],
                           check=True, capture_output=True, timeout=5)
        os.write(control_write, b'CANCEL\n' if interrupted or scenario == 'cancel-before-run' else b'RUN\n')
        while not select.select([report_read], [], [], .02)[0]:
            if interrupted:
                os.close(control_write)
                control_write = None
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Guardian result timed out')
        result = _fixture_line(report_read, deadline)
        code = guardian.wait(timeout=max(.01, deadline - time.monotonic()))
        cleanup_verified = (result.get('event') == 'result'
                            and result.get('guardian_pid') == guardian.pid
                            and result.get('child_pid') == spawned['child_pid']
                            and result.get('quiescent') is True)
        if mesen:
            result['native_lease'] = spawned['native_lease']
        if (code != 0 or interrupted or result.get('event') != 'result'
                or result.get('guardian_pid') != guardian.pid
                or result.get('child_pid') != spawned['child_pid']
                or result.get('success') is not True or result.get('quiescent') is not True):
            raise SyntheticGuardianError('Synthetic guardian failed: ' + str(result.get('error', code)), result)
        prepared._verify_owner()
        if lease_token:
            if not lease.release(lease_token):
                cleanup_verified = False
                raise RuntimeError('Native lease release was not confirmed')
            result['native_lease']['released'] = True
            lease_token = None
        prepared._launch_started = False
        prepared.cancel_before_launch()
        return result
    finally:
        # EOF asks a surviving guardian to clean its own child. Do not kill the
        # guardian or child here; guardian status/cleanup uncertainty keeps lease.
        if control_write is not None:
            os.close(control_write)
        if guardian is not None and guardian.returncode is None:
            try:
                guardian.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        if lease_token and cleanup_verified:
            released = lease.release(lease_token)
            if result is not None and mesen:
                result['native_lease']['released'] = released
        if previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)
        for endpoint in endpoints:
            endpoint.close()
        for fd in (control_read, report_read, report_write, log_fd, child_log_fd, null_fd):
            if fd is not None:
                os.close(fd)


def _diagnostic_request(path: Path, expected_sha256: str) -> dict:
    request = json.loads(_read_hashed(path, expected_sha256, 1024 * 1024))
    expected = {'version', 'private_root', 'project_path', 'rom_path', 'rom_sha256',
                'profiles_root', 'settings_path', 'app_binding', 'timeout', 'owner'}
    if type(request) is not dict or set(request) != expected or request['version'] != 1:
        raise ValueError('Expected an explicit version-1 private diagnostic request')
    root = _canonical(Path(request['private_root']))
    _private_directory(root)
    for name in ('project_path', 'rom_path', 'profiles_root'):
        selected = _canonical(Path(request[name]))
        if selected == root or not selected.is_relative_to(root):
            raise ValueError('Diagnostic inputs must be inside the explicit private root')
    _private_directory(Path(request['profiles_root']))
    _verify_private_app(request['app_binding'])
    rom = _read_hashed(Path(request['rom_path']), request['rom_sha256'], 0x400000)
    settings = None if request['settings_path'] is None else _read_regular(
        Path(request['settings_path']), 16 * 1024 * 1024)
    prepared = prepare_session(project_path=Path(request['project_path']),
        rom_path=Path(request['rom_path']), verified_rom_bytes=rom,
        profiles_root=Path(request['profiles_root']), settings_bytes=settings, diagnostic=True)
    return launch_dedicated_mesen(prepared, app_binding=request['app_binding'],
        private_root=root, timeout=request['timeout'], owner=request['owner'])


def _desktop_exchange(connection, command, deadline, check_child):
    check_child()
    connection.sendall(_json_bytes({'type': command}))
    return _fixture_line(connection.fileno(), deadline, check_child)


def _desktop_ready(child, endpoint: Path, plan, deadline, cancelled):
    """Connect only to this launch's endpoint; readiness never selects a peer."""
    def check_child():
        if cancelled():
            raise InterruptedError('Desktop launch cancelled')
        if child.poll() is not None:
            raise RuntimeError('Owned desktop process exited before readiness')
        if time.monotonic() >= deadline:
            raise TimeoutError('Owned desktop ROM readiness timed out')

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(.1)
    try:
        while True:
            check_child()
            try:
                connection.connect(str(endpoint))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(.02)
        if _fixture_peer_pid(connection) != child.pid:
            raise ValueError('Desktop endpoint peer is not the owned child')
        ping = _desktop_exchange(connection, 'PING', deadline, check_child)
        if (set(ping) != {'success', 'data'} or ping['success'] is not True
                or ping['data'] != 'PONG'):
            raise ValueError('Unexpected desktop PING response')
        expected = {'kind': 'snes_prg_rom', 'size': plan.rom_size,
                    'sha1': plan.rom_sha1, 'session': plan.session_token}
        while True:
            reply = _canonical_identity_reply(_desktop_exchange(
                connection, 'LOADED_ROM_IDENTITY', deadline, check_child))
            if (set(reply) == {'success', 'error'} and reply['success'] is False
                    and reply['error'] == 'No SNES cartridge loaded'):
                time.sleep(.02)
                continue
            if _identity_mismatch_evidence(reply, expected):
                raise ValueError('Owned desktop loaded ROM identity differs')
            check_child()
            return
    finally:
        connection.close()


def _run_desktop(prepared, *, app_binding, verified_rom_bytes, startup_timeout,
                 identity, on_ready, loaded_identity=None, revalidate=None):
    """Retain one direct GUI child; no session discovery or process detachment.

    This user-triggered desktop session is not a bounded native test episode.
    Its profile and saves persist. An uncertain exit retains the reservation;
    there is no claim about arbitrary descendants or OS filesystem confinement.
    """
    app = _verify_private_app(app_binding, desktop=True)
    prepared._verify_owner()
    _verify_profile_files(prepared._profile_fd)
    public_session = uuid.uuid4().hex
    run_name = 'desktop-' + public_session
    os.mkdir(run_name, mode=0o700, dir_fd=prepared._profile_fd)
    run_fd = _open_directory_at(prepared._profile_fd, run_name, private=True)
    socket_root = Path(tempfile.mkdtemp(prefix='yaze-mesen-', dir='/private/tmp'))
    endpoint = socket_root / 'control.sock'
    child = None
    interrupted = 0
    previous_handlers = {}
    plan = prepared.plan
    copy_path = Path(plan.profile_path) / run_name / Path(plan.rom_path).name
    try:
        _write_new_at(run_fd, copy_path.name, verified_rom_bytes)
        os.chmod(copy_path.name, 0o400, dir_fd=run_fd, follow_symlinks=False)
        if _read_regular_at(run_fd, copy_path.name, 0x400000) != verified_rom_bytes:
            raise ValueError('Private desktop ROM copy differs')
        plan = replace(plan, rom_path=str(copy_path), socket_path=str(endpoint))
        environment = plan.child_environment(os.environ)
        # A private HOME/TMPDIR also keeps incidental runtime files out of the
        # user's normal profile. This is a directory choice, not a sandbox.
        environment.update(HOME=plan.profile_path, TMPDIR=str(copy_path.parent),
                           MESEN2_YAZE_PRIVATE_DESKTOP='1')
        if threading.current_thread() is not threading.main_thread():
            raise ValueError('Desktop supervision requires the main thread')
        def cancel(signum, _frame):
            nonlocal interrupted
            interrupted = signum
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, cancel)
        if interrupted:
            raise InterruptedError('Desktop launch cancelled')
        if revalidate is not None:
            revalidate()
        prepared.mark_launch_started()
        # Keep the direct process in the caller's owned task group, so desktop
        # task cancellation also reaches it. Never use open/nohup/disown here.
        log_fd = os.open('mesen.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=run_fd)
        with os.fdopen(log_fd, 'wb') as log:
            child = subprocess.Popen([app['executable'], plan.rom_path],
                cwd=plan.profile_path, env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, close_fds=True)
        expected = plan if loaded_identity is None else replace(plan,
            rom_size=loaded_identity['size'], rom_sha1=loaded_identity['sha1'])
        _desktop_ready(child, endpoint, expected, time.monotonic() + startup_timeout,
                       lambda: interrupted)
        if revalidate is not None:
            revalidate()
        if interrupted:
            raise InterruptedError('Desktop launch cancelled before readiness publication')
        # The public session ID is correlation only. Do not publish the private
        # MESEN2_YAZE_RUN_TOKEN used in the loaded-identity exchange.
        on_ready({'version': 1, **identity, 'pid': child.pid,
                  'session': public_session, 'socket_path': str(endpoint),
                  'profile_path': plan.profile_path, 'rom_path': plan.rom_path,
                  'rom_sha1': expected.rom_sha1})
        while child.poll() is None and not interrupted:
            time.sleep(.02)
    finally:
        quiescent = child is not None and child.poll() is not None
        if child is not None and not quiescent:
            try:
                child.terminate()  # Popen checks/reaps before signaling; no raw reused PID.
                child.wait(timeout=1.5)
                quiescent = True
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            if quiescent or not prepared._launch_started:
                if endpoint.exists():
                    if not stat.S_ISSOCK(endpoint.lstat().st_mode):
                        raise ValueError('Unexpected desktop endpoint entry; retain reservation')
                    endpoint.unlink()
                socket_root.rmdir()
                prepared._launch_started = False
                prepared.cancel_before_launch()
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
            os.close(run_fd)
        if child is not None and not quiescent:
            raise RuntimeError('Desktop child exit is unproven; profile reservation retained')
    return 128 + interrupted if interrupted else child.returncode


def _ordinary_module():
    # Always load the adjacent owned source, never code named by a receipt.
    directory = str(Path(__file__).resolve(strict=True).parents[1] / 'Build')
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import oracle_ordinary_build
    if Path(oracle_ordinary_build.__file__).resolve() != Path(directory) / 'oracle_ordinary_build.py':
        raise ValueError('Ordinary validator source differs from this launcher')
    return oracle_ordinary_build


def _ordinary_selection(selection, project):
    ordinary = _ordinary_module()
    if type(selection) is not dict or set(selection) != {'selector', 'engine'}:
        raise ValueError('Explicit ordinary selector binding is required')
    result = ordinary.validate_selector(selection['selector'], project=project,
                                        engine=Path(selection['engine']))
    ordinary.load_profile(result[0]['profile'], project=project,
                          engine=Path(selection['engine']), executing=True)
    return result


def _desktop_request(argv, on_ready, *, ordinary_selection=None):
    if len(argv) != 8 or sys.platform != 'darwin':
        raise ValueError('Expected explicit macOS desktop config and selected output binding')
    config_path, config_sha, project_path, project_id, engine_path, rom_path, rom_sha, size = argv
    config = json.loads(_read_hashed(Path(config_path), config_sha, 1024 * 1024))
    if (type(config) is not dict or set(config) != {'version', 'app_binding',
            'profiles_root', 'settings_path', 'settings_sha256', 'startup_timeout'}
            or type(config['version']) is not int or config['version'] != 1):
        raise ValueError('Expected an explicit version-1 desktop configuration')
    timeout = config['startup_timeout']
    if type(timeout) not in (int, float) or not 0 < timeout <= 60:
        raise ValueError('Desktop startup_timeout must be within 0..60 seconds')
    project = _canonical(Path(project_path))
    engine = _canonical(Path(engine_path))
    if not engine.is_dir() or not project_id or len(project_id) > 256:
        raise ValueError('Explicit project and engine identity are required')
    rom = _read_hashed(Path(rom_path), rom_sha, 0x400000)
    if str(len(rom)) != size:
        raise ValueError('Selected output size differs')
    ordinary = None
    def revalidate():
        current = _ordinary_selection(ordinary_selection, project)
        if current != ordinary:
            raise ValueError('Ordinary selection changed during desktop preparation')
    if ordinary_selection is not None:
        ordinary = _ordinary_selection(ordinary_selection, project)
        selector, selected, loaded = ordinary
        if (selector['project_id'] != project_id or selector['engine'] != str(engine)
                or selector['candidate'] != {'path': rom_path, 'sha256': rom_sha, 'size': len(rom)}
                or selected != rom):
            raise ValueError('Ordinary selector differs from selected desktop output')
    _verify_private_app(config['app_binding'], desktop=True)
    profiles = _canonical(Path(config['profiles_root']))
    _private_directory(profiles)
    profile = profiles / ('yaze-' + hashlib.sha256(str(project).encode()).hexdigest()[:32])
    settings = None
    if not profile.exists():
        if config['settings_path'] is None:
            raise ValueError('New desktop profile requires an explicit settings source')
        settings = _read_hashed(Path(config['settings_path']),
                                config['settings_sha256'], 16 * 1024 * 1024)
    prepared = prepare_session(project_path=project, rom_path=Path(rom_path),
        verified_rom_bytes=rom, profiles_root=profiles, settings_bytes=settings,
        ordinary_selection=ordinary_selection)
    extra = {} if ordinary is None else {
        'route': 'ordinary', 'selector_path': ordinary_selection['selector']['path'],
        'selector_sha256': ordinary_selection['selector']['sha256'],
        'receipt_path': selector['build_receipt']['path'],
        'receipt_sha256': selector['build_receipt']['sha256'], 'loaded_rom_size': loaded['size']}
    return _run_desktop(prepared, app_binding=config['app_binding'],
        verified_rom_bytes=rom, startup_timeout=timeout, on_ready=on_ready,
        loaded_identity=None if ordinary is None else loaded,
        revalidate=None if ordinary is None else revalidate,
        identity={'project_path': str(project), 'project_id': project_id,
                  'engine_path': str(engine), 'output_path': rom_path,
                  'output_sha256': rom_sha, 'output_size': len(rom), **extra})


def _ordinary_desktop_request(argv, on_ready):
    if len(argv) != 10:
        raise ValueError('Expected desktop binding plus ordinary selector path and SHA-256')
    ordinary = _ordinary_module()
    selected = ordinary.binding(Path(argv[8]))
    if selected['sha256'] != argv[9]:
        raise ValueError('Ordinary selector hash differs')
    return _desktop_request(argv[:8], on_ready,
        ordinary_selection={'selector': selected, 'engine': argv[4]})


def _main(argv: list[str]) -> int:
    if argv and argv[0] == '--desktop-ordinary':
        try:
            return _ordinary_desktop_request(argv[1:], lambda ready: print(
                'YAZE_DESKTOP_READY ' + json.dumps(ready, sort_keys=True), flush=True))
        except Exception as error:
            print('Private ordinary desktop session refused: ' + str(error), file=sys.stderr)
            return 2
    if argv and argv[0] == '--desktop':
        try:
            return _desktop_request(argv[1:], lambda ready: print(
                'YAZE_DESKTOP_READY ' + json.dumps(ready, sort_keys=True), flush=True))
        except Exception as error:
            print('Private desktop session refused: ' + str(error), file=sys.stderr)
            return 2
    if len(argv) != 2:
        print('Expected private diagnostic request path and SHA-256', file=sys.stderr)
        return 2
    try:
        result = _diagnostic_request(Path(argv[0]), argv[1])
    except Exception as error:
        print('Private diagnostic refused: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
