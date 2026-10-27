"""Exact test-only Git source snapshots for offline, shallow checkouts.

Each fixture is the unmodified output of ``git show <full commit>:<path>``,
compressed with gzip mtime zero. The manifest pins the original Git blob,
SHA-256 and byte count, plus the stored compressed bytes. Reading a snapshot
never consults Git, the network or the current production source.
"""
import gzip
import hashlib
import json
from pathlib import Path


_FIXTURE_ROOT = Path(__file__).resolve().parent / 'fixtures/lyra_source_snapshots'
_MANIFEST_SHA256 = '44f90940bae6da46e1abb496a4fa13e8c985d29137aa0ec49783d34bc6677d5a'


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
