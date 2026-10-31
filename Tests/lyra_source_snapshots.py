"""Exact test-only Git source snapshots for offline, shallow checkouts.

Each fixture is the unmodified output of ``git show <full commit>:<path>``,
compressed with gzip mtime zero. The manifest pins the original Git blob,
SHA-256 and byte count, plus the stored compressed bytes. Reading a snapshot
never consults Git, the network or the current production source.
"""
import gzip
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import tempfile


_FIXTURE_ROOT = Path(__file__).resolve().parent / 'fixtures/lyra_source_snapshots'
_MANIFEST_SHA256 = 'b30b8b29fe6f28e6989ef25a3f72882a4d8e76e8ab64b617691dfe79aed84c79'


def _load_pins():
    raw = (_FIXTURE_ROOT / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != _MANIFEST_SHA256:
        raise ValueError('Lyra source snapshot manifest changed')
    manifest = json.loads(raw)
    if manifest['kind'] != 'lyra.test_source_snapshots.v1':
        raise ValueError('Unknown Lyra source snapshot manifest')
    pins = {}
    for row in manifest['snapshots']:
        key = (row['commit'], row['path'])
        if key in pins:
            raise ValueError('Duplicate Lyra source snapshot: ' + repr(key))
        pins[key] = row
    return pins


_PINS = _load_pins()
SNAPSHOT_KEYS = tuple(sorted(_PINS))


def read_snapshot(commit, path):
    """Return exact bytes for one explicitly pinned full-commit/path pair."""
    key = (commit, path)
    if key not in _PINS:
        raise ValueError('Unpinned Lyra source snapshot: ' + repr(key))
    pin = _PINS[key]
    compressed = (_FIXTURE_ROOT / (pin['git_blob'] + '.gz')).read_bytes()
    if (len(compressed) != pin['gzip_byte_count'] or
            hashlib.sha256(compressed).hexdigest() != pin['gzip_sha256']):
        raise ValueError('Lyra source snapshot compressed bytes changed: ' + repr(key))
    raw = gzip.decompress(compressed)
    if (len(raw) != pin['byte_count'] or
            hashlib.sha256(raw).hexdigest() != pin['sha256']):
        raise ValueError('Lyra source snapshot bytes changed: ' + repr(key))
    git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if git_blob != pin['git_blob']:
        raise ValueError('Lyra source snapshot Git blob changed: ' + repr(key))
    return raw


def read_snapshot_text(commit, path):
    """Return the pinned source bytes as strict UTF-8, without normalization."""
    return read_snapshot(commit, path).decode('utf-8')


@contextmanager
def staged_source_set(source_root, ledger_raw, source_set, snapshot_commit):
    """Stage exact ledger-bound bytes without importing historical code.

    Explicit snapshots supply changed consumers. Unchanged files may come from
    the checkout only when their bytes still match the historical ledger hash.
    The real validator and composer run against this temporary source root.
    """
    ledger = json.loads(ledger_raw)
    records = [row for row in ledger['sources'].values()
               if row['source_set'] == source_set]
    if not records:
        raise ValueError('No fixture source-set consumers: ' + source_set)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / 'Config').mkdir()
        (root / 'Config/allocation_ownership.json').write_bytes(ledger_raw)
        for row in records:
            relative = Path(row['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Fixture consumer escaped its root')
            key = (snapshot_commit, row['path'])
            raw = (read_snapshot(*key) if key in _PINS
                   else (source_root / relative).read_bytes())
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Fixture consumer differs from ledger: ' + row['path'])
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        yield root
