"""Source-bound manifest primitives for a portable Oracle engine snapshot.

A manifest is evidence of file identity, not an allocation or runtime grant.
The caller must obtain its expected digest and engine revision from an
independently reviewed authority. This module is not wired into Build admission.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

KIND = 'lyra.portable_source_manifest.v1'
_MAX_MANIFEST = 16 * 1024 * 1024


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _paths(values):
    _require(type(values) in (list, tuple) and values, 'A nonempty source closure is required')
    result = []
    for value in values:
        _require(type(value) is str and value and '\\' not in value and '\0' not in value,
                 'Source closure contains an invalid path')
        parsed = PurePosixPath(value)
        _require(not parsed.is_absolute() and parsed.as_posix() == value
                 and all(part not in ('', '.', '..') and ':' not in part for part in parsed.parts),
                 'Source closure contains a noncanonical path')
        result.append(value)
    _require(len({value.casefold() for value in result}) == len(result),
             'Source closure contains duplicate or case-conflicting paths')
    return sorted(result)


def _read_source(root, relative, *, mode):
    path = root.joinpath(*PurePosixPath(relative).parts)
    _require(path.is_file() and path.resolve(strict=True).is_relative_to(root)
             and not any(part.is_symlink() for part in (path, *path.parents)),
             'Source file escaped the engine or uses a symlink: ' + relative)
    if os.name != 'nt':
        _require(bool(path.stat().st_mode & 0o111) == (mode == '100755'),
                 'Source executable mode differs from reviewed manifest: ' + relative)
    return path.read_bytes()


def _committed_modes(current, root, engine_head, paths):
    raw = current._git(root, 'ls-tree', '-rz', '--full-tree', engine_head, '--', *paths)
    modes = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        try:
            metadata, name = entry.split(b'\t', 1)
            mode, kind, object_id = metadata.decode('ascii').split(' ')
            name = name.decode('utf-8')
        except (ValueError, UnicodeError) as error:
            raise ValueError('Invalid selected Git tree entry') from error
        _require(mode in ('100644', '100755') and kind == 'blob'
                 and re.fullmatch('[0-9a-f]{40}', object_id) is not None
                 and name in paths and name not in modes,
                 'Selected Git source must be a unique regular file: ' + name)
        modes[name] = mode
    _require(set(modes) == set(paths), 'Selected Git source closure is incomplete')
    return modes


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def create_for_checkout(root, engine_head, source_closure):
    """Return canonical manifest bytes for committed, unchanged closure files.

    The existing Git-backed reader supplies exact committed bytes; the caller
    must discover the complete closure and independently approve the resulting
    manifest digest before accepting an exported snapshot.
    """
    import lyra_current_transfer as current

    root = Path(root).resolve(strict=True)
    paths = _paths(source_closure)
    _require(type(engine_head) is str and re.fullmatch('[0-9a-f]{40}', engine_head),
             'An exact engine commit is required')
    _require(Path(current._git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root
             and current._git(root, 'rev-parse', engine_head + '^{commit}').decode().strip() == engine_head,
             'Source engine must be the selected Git checkout')
    modes = _committed_modes(current, root, engine_head, paths)
    committed = current._git_source_blobs(root, engine_head, paths)
    rows = []
    for relative in paths:
        content = _read_source(root, relative, mode=modes[relative])
        _require(content == committed[relative], 'Source file differs from selected commit: ' + relative)
        rows.append({'path': relative, 'sha256': _sha(content), 'size': len(content),
                     'mode': modes[relative]})
    for row in rows:
        content = _read_source(root, row['path'], mode=row['mode'])
        _require(len(content) == row['size'] and _sha(content) == row['sha256'],
                 'Source file changed during manifest creation: ' + row['path'])
    return _encoded({'kind': KIND, 'engine_head': engine_head, 'files': rows})


def verify_snapshot(root, manifest_bytes, *, trusted_sha256, engine_head, source_closure):
    """Verify an exported closure against an externally pinned manifest digest."""
    _require(type(manifest_bytes) is bytes and len(manifest_bytes) <= _MAX_MANIFEST,
             'Portable source manifest is missing or too large')
    _require(type(trusted_sha256) is str and re.fullmatch('[0-9a-f]{64}', trusted_sha256)
             and _sha(manifest_bytes) == trusted_sha256,
             'Portable source manifest differs from trusted authority')
    _require(type(engine_head) is str and re.fullmatch('[0-9a-f]{40}', engine_head),
             'An exact engine commit is required')
    paths = _paths(source_closure)
    try:
        document = json.loads(manifest_bytes)
    except (ValueError, UnicodeError) as error:
        raise ValueError('Portable source manifest is invalid JSON') from error
    _require(type(document) is dict and set(document) == {'kind', 'engine_head', 'files'}
             and document['kind'] == KIND and document['engine_head'] == engine_head
             and _encoded(document) == manifest_bytes and type(document['files']) is list,
             'Portable source manifest identity or canonical encoding differs')
    rows = document['files']
    _require(all(type(row) is dict and set(row) == {'path', 'sha256', 'size', 'mode'}
                 and type(row['path']) is str and type(row['sha256']) is str
                 and re.fullmatch('[0-9a-f]{64}', row['sha256'])
                 and type(row['size']) is int and row['size'] >= 0
                 and row['mode'] in ('100644', '100755') for row in rows),
             'Portable source manifest entries are malformed')
    _require([row['path'] for row in rows] == paths,
             'Portable source manifest does not cover the complete source closure')
    root = Path(root).resolve(strict=True)
    # A second pass catches a file changed while another file was read. The
    # caller still needs a stable owned snapshot through the subsequent Build.
    for _ in range(2):
        for row in rows:
            content = _read_source(root, row['path'], mode=row['mode'])
            _require(len(content) == row['size'] and _sha(content) == row['sha256'],
                     'Portable source file differs from reviewed manifest: ' + row['path'])
    return {'engine_head': engine_head, 'manifest_sha256': trusted_sha256,
            'files_verified': len(rows)}
