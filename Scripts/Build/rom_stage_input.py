"""Exact pre-assembly staging contract: preserve source, append only FF.

This module performs no file I/O. It does not authorize generated edits,
version stamping, source migration or an arbitrary changed-byte mask.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

KIND = "oracle.pre_assembly_ff_stage.v1"
OPERATION = "append-ff-to-unheadered-4mib"
TARGET_BYTES = 0x400000
RECEIPT_SUFFIX = ".stage-input.json"


class StageInputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise StageInputError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate stage JSON key")
        result[key] = value
    return result


def document(raw):
    try:
        return json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError) as error:
        raise StageInputError("Malformed stage JSON: " + str(error)) from error


def _keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected),
            "Malformed stage " + name)


def _path(value):
    require(type(value) is str and value and "\0" not in value
            and Path(value).is_absolute() and os.path.normpath(value) == value,
            "Stage path must be absolute and normalized")
    return value


def _binding(path, raw):
    return dict(path=_path(str(path)), sha256=digest(raw), bytes=len(raw))


def _prepare(source, source_path, target_path, prepare_raw):
    require(type(source) is bytes and len(source) in (0x200000, TARGET_BYTES),
            "Stage source must be an unheadered 2MiB or 4MiB ROM")
    source_path, target_path = _path(str(source_path)), _path(str(target_path))
    require(source_path != target_path, "Stage target must differ from its source")
    prepared = document(prepare_raw)
    require(type(prepared) is dict
            and prepared.get("kind") == "lyra.current_build_prepare.v1"
            and prepared.get("selected") is True,
            "Stage requires a selected current Lyra prepare")
    require(prepared.get("base_rom") == source_path
            and prepared.get("saved_rom_sha256") == digest(source),
            "Stage prepare saved-source binding differs")
    plan = prepared.get("terrain_plan")
    target = plan.get("target") if type(plan) is dict else None
    require(type(target) is dict and target.get("path") == target_path
            and type(target.get("size")) is int
            and target["size"] == TARGET_BYTES
            and target.get("role") == "compiled_candidate",
            "Stage prepare target binding differs")
    return source_path, target_path


def describe_ff_stage(source, source_path, target_path, prepare_path, prepare_raw):
    source_path, target_path = _prepare(source, source_path, target_path, prepare_raw)
    staged = source.ljust(TARGET_BYTES, b"\xff")
    return dict(
        kind=KIND, operation=OPERATION,
        source=_binding(source_path, source), target=_binding(target_path, staged),
        prepare=_binding(prepare_path, prepare_raw),
        padding=dict(start=len(source), end=TARGET_BYTES, value=0xFF))


def verify_ff_stage(source, staged, declaration, source_path, target_path,
                    prepare_path, prepare_raw):
    expected = describe_ff_stage(source, source_path, target_path, prepare_path, prepare_raw)
    _keys(declaration, expected, "declaration")
    require(declaration["kind"] == KIND and declaration["operation"] == OPERATION,
            "Unsupported stage transform")
    for key in ("source", "target", "prepare"):
        _keys(declaration[key], {"path", "sha256", "bytes"}, key + " binding")
        require(type(declaration[key]["bytes"]) is int,
                "Stage binding byte count must be an integer")
    _keys(declaration["padding"], {"start", "end", "value"}, "padding")
    require(all(type(declaration["padding"][key]) is int
                for key in ("start", "end", "value")),
            "Stage padding fields must be integers")
    require(declaration["source"] == expected["source"],
            "Stage source binding is stale or differs")
    require(declaration["prepare"] == expected["prepare"],
            "Stage prepare binding is stale or differs")
    require(declaration["padding"] == expected["padding"],
            "Undeclared stage padding range or value")
    require(type(staged) is bytes and len(staged) == TARGET_BYTES,
            "Stage target must be exactly unheadered 4MiB")
    require(staged[:len(source)] == source,
            "Staged authored source prefix differs")
    require(staged[len(source):] == b"\xff" * (TARGET_BYTES - len(source)),
            "Staged padding contains non-FF bytes")
    require(declaration["target"] == expected["target"]
            and declaration["target"]["sha256"] == digest(staged),
            "Stage target binding differs")
    return dict(kind=KIND, operation=OPERATION,
                source_sha256=digest(source), target_sha256=digest(staged),
                source_bytes=len(source), target_bytes=len(staged),
                padding=expected["padding"])
