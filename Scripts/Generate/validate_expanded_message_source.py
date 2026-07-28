#!/usr/bin/env python3
"""Validate the canonical Oracle expanded-message source contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BUNDLE_PATH = Path("Data/dialogue/expanded_messages.json")
ASM_INCLUDE_PATH = Path("Core/Generated/expanded_messages.asm")
MESSAGE_WRAPPER_PATH = Path("Core/message.asm")

FIRST_MESSAGE_ID = 0x18D
LAST_MESSAGE_ID = 0x1F9
MESSAGE_COUNT = LAST_MESSAGE_ID - FIRST_MESSAGE_ID + 1
MESSAGE_DATA_START = 0x2F8026

SOURCE_HASH_RE = re.compile(
    r"^; Source bundle SHA-256: ([0-9a-f]{64})$", re.MULTILINE
)
GENERATED_BODY_HASH_RE = re.compile(
    r"^; Generated ASM body SHA-256: ([0-9a-f]{64})$", re.MULTILINE
)
MESSAGE_LABEL_RE = re.compile(r"^\s*Message_([0-9A-Fa-f]{3}):\s*$")
ORG_RE = re.compile(r"^\s*org\b", re.IGNORECASE)
DB_RE = re.compile(r"^\s*db\s+(.+?)\s*$", re.IGNORECASE)
BYTE_RE = re.compile(r"^\$([0-9A-Fa-f]{2})$")


class MessageSourceContractError(RuntimeError):
    """Raised when tracked expanded-message artifacts drift."""


@dataclass(frozen=True)
class MessageSourceContract:
    message_count: int
    data_size: int
    bundle_sha256: str


def _load_bundle(bundle_path: Path) -> tuple[dict[str, Any], bytes, str]:
    try:
        bundle_bytes = bundle_path.read_bytes()
    except OSError as exc:
        raise MessageSourceContractError(
            f"cannot read canonical bundle {bundle_path}: {exc}"
        ) from exc

    try:
        bundle = json.loads(bundle_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MessageSourceContractError(
            f"canonical bundle is not valid JSON: {exc}"
        ) from exc

    if not isinstance(bundle, dict):
        raise MessageSourceContractError("canonical bundle must be an object")
    expected_top_level = {"counts", "format", "messages", "version"}
    if set(bundle) != expected_top_level:
        raise MessageSourceContractError(
            "canonical bundle top-level keys must be exactly "
            f"{sorted(expected_top_level)}"
        )
    if bundle["format"] != "yaze-message-bundle":
        raise MessageSourceContractError(
            "canonical bundle format must be 'yaze-message-bundle'"
        )
    if not isinstance(bundle["version"], int) or isinstance(
        bundle["version"], bool
    ) or bundle["version"] != 1:
        raise MessageSourceContractError(
            "canonical bundle version must be integer 1"
        )
    counts = bundle["counts"]
    if (
        not isinstance(counts, dict)
        or counts != {"expanded": MESSAGE_COUNT, "vanilla": 0}
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in counts.values()
        )
    ):
        raise MessageSourceContractError(
            "canonical bundle counts must be "
            f"expanded={MESSAGE_COUNT}, vanilla=0"
        )

    messages = bundle["messages"]
    if not isinstance(messages, list) or len(messages) != MESSAGE_COUNT:
        raise MessageSourceContractError(
            f"canonical bundle must contain exactly {MESSAGE_COUNT} messages"
        )
    for expected_id, entry in enumerate(messages):
        if not isinstance(entry, dict):
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} must be an object"
            )
        if set(entry) != {"bank", "id", "text"}:
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} keys must be exactly "
                "['bank', 'id', 'text']"
            )
        if entry["bank"] != "expanded":
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} must use expanded bank"
            )
        if (
            not isinstance(entry["id"], int)
            or isinstance(entry["id"], bool)
            or entry["id"] != expected_id
        ):
            raise MessageSourceContractError(
                "canonical bundle messages must be ordered with contiguous "
                f"bank-local IDs 0..{MESSAGE_COUNT - 1}"
            )
        if not isinstance(entry["text"], str) or not entry["text"]:
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} text must be nonempty"
            )
        if "[D:$" in entry["text"]:
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} uses legacy "
                "[D:$XX] syntax; use [D:XX]"
            )

    canonical_bytes = (
        json.dumps(bundle, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("ascii")
    if bundle_bytes != canonical_bytes:
        raise MessageSourceContractError(
            "canonical bundle is not in deterministic "
            "yaze message-source-sync format"
        )

    return bundle, bundle_bytes, hashlib.sha256(bundle_bytes).hexdigest()


def _render_asm_body(messages: list[tuple[int, bytes]]) -> str:
    lines: list[str] = []
    for message_id, encoded in messages:
        lines.append(f"Message_{message_id:03X}:")
        for offset in range(0, len(encoded), 16):
            chunk = encoded[offset:offset + 16]
            lines.append(
                "  db " + ", ".join(f"${value:02X}" for value in chunk)
            )
        lines.append("")
    lines.append("db $FF")
    return "\n".join(lines) + "\n"


def _render_asm_include(
    messages: list[tuple[int, bytes]], bundle_hash: str
) -> str:
    body = _render_asm_body(messages)
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (
        f"; Source bundle SHA-256: {bundle_hash}\n"
        f"; Generated ASM body SHA-256: {body_hash}\n"
        "; Generated by yaze message-source-sync. Do not edit.\n"
        "\n"
        f"{body}"
    )


def _parse_asm_include(
    include_path: Path, expected_bundle_hash: str
) -> tuple[list[int], bytes]:
    try:
        text = include_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MessageSourceContractError(
            f"cannot read generated include {include_path}: {exc}"
        ) from exc

    hash_matches = SOURCE_HASH_RE.findall(text)
    if hash_matches != [expected_bundle_hash]:
        found = ", ".join(hash_matches) if hash_matches else "missing"
        raise MessageSourceContractError(
            "generated include source hash does not match canonical bundle: "
            f"expected {expected_bundle_hash}, found {found}"
        )

    body_start = text.find(f"Message_{FIRST_MESSAGE_ID:03X}:")
    if body_start < 0:
        raise MessageSourceContractError(
            f"generated include is missing Message_{FIRST_MESSAGE_ID:03X}"
        )
    body_hash = hashlib.sha256(
        text[body_start:].encode("utf-8")
    ).hexdigest()
    body_hash_matches = GENERATED_BODY_HASH_RE.findall(text)
    if body_hash_matches != [body_hash]:
        found = (
            ", ".join(body_hash_matches)
            if body_hash_matches
            else "missing"
        )
        raise MessageSourceContractError(
            "generated include body hash does not match its ASM body: "
            f"expected {body_hash}, found {found}"
        )

    labels: list[tuple[int, int]] = []
    encoded = bytearray()
    for line_number, line in enumerate(text.splitlines(), start=1):
        source = line.split(";", 1)[0]
        if not source.strip():
            continue
        if ORG_RE.match(source):
            raise MessageSourceContractError(
                f"{include_path}:{line_number}: generated include must not "
                "contain an org directive"
            )

        label_match = MESSAGE_LABEL_RE.match(source)
        if label_match:
            labels.append((int(label_match.group(1), 16), len(encoded)))
            continue

        db_match = DB_RE.match(source)
        if not db_match:
            raise MessageSourceContractError(
                f"{include_path}:{line_number}: unsupported generated source "
                f"line: {source.strip()!r}"
            )
        operands = [operand.strip() for operand in db_match.group(1).split(",")]
        if not operands or any(not operand for operand in operands):
            raise MessageSourceContractError(
                f"{include_path}:{line_number}: malformed db directive"
            )
        for operand in operands:
            byte_match = BYTE_RE.fullmatch(operand)
            if not byte_match:
                raise MessageSourceContractError(
                    f"{include_path}:{line_number}: expected byte literal, "
                    f"found {operand!r}"
                )
            encoded.append(int(byte_match.group(1), 16))

    expected_ids = list(range(FIRST_MESSAGE_ID, LAST_MESSAGE_ID + 1))
    actual_ids = [message_id for message_id, _ in labels]
    if actual_ids != expected_ids:
        raise MessageSourceContractError(
            "generated include labels must be unique and contiguous from "
            f"Message_{FIRST_MESSAGE_ID:03X} through "
            f"Message_{LAST_MESSAGE_ID:03X}"
        )
    if not labels or labels[0][1] != 0:
        raise MessageSourceContractError(
            "generated include must not emit bytes before Message_18D"
        )
    if not encoded or encoded[-1] != 0xFF or encoded.count(0xFF) != 1:
        raise MessageSourceContractError(
            "generated include must end with one bank terminator byte $FF"
        )

    messages: list[tuple[int, bytes]] = []
    for index, (message_id, start) in enumerate(labels):
        end = labels[index + 1][1] if index + 1 < len(labels) else len(encoded) - 1
        message = bytes(encoded[start:end])
        if not message or message[-1] != 0x7F:
            raise MessageSourceContractError(
                f"Message_{message_id:03X} must end with byte $7F"
            )
        if 0x7F in message[:-1] or 0xFF in message:
            raise MessageSourceContractError(
                f"Message_{message_id:03X} has an early terminator"
            )
        messages.append((message_id, message))

    expected_text = _render_asm_include(messages, expected_bundle_hash)
    if text != expected_text:
        raise MessageSourceContractError(
            "generated include is not in deterministic "
            "yaze message-source-sync format"
        )

    return actual_ids, bytes(encoded)


def _validate_wrapper(wrapper_path: Path) -> None:
    try:
        text = wrapper_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MessageSourceContractError(
            f"cannot read message wrapper {wrapper_path}: {exc}"
        ) from exc

    boundary = (
        'assert pc() <= $2F8026, '
        '"MessageExpand loader crossed fixed data start $2F8026"'
    )
    include = 'incsrc "Core/Generated/expanded_messages.asm"'
    if text.count(boundary) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must assert that the loader does not cross "
            "$2F8026"
        )
    if text.count("org $2F8026") != 1:
        raise MessageSourceContractError(
            "Core/message.asm must fix MessageExpandedData at $2F8026"
        )
    if text.count("MessageExpandedData:") != 1 or text.count(include) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must define MessageExpandedData and include "
            "Core/Generated/expanded_messages.asm exactly once"
        )
    if text.index(boundary) > text.index("org $2F8026"):
        raise MessageSourceContractError(
            "loader boundary assert must precede the fixed data org"
        )
    if not (
        text.index("org $2F8026")
        < text.index("MessageExpandedData:")
        < text.index(include)
    ):
        raise MessageSourceContractError(
            "fixed data org, MessageExpandedData, and generated include are "
            "out of order"
        )


def validate_contract(root: Path) -> MessageSourceContract:
    root = root.resolve()
    _, _, bundle_hash = _load_bundle(root / BUNDLE_PATH)
    labels, encoded = _parse_asm_include(
        root / ASM_INCLUDE_PATH, bundle_hash
    )
    _validate_wrapper(root / MESSAGE_WRAPPER_PATH)
    return MessageSourceContract(
        message_count=len(labels),
        data_size=len(encoded),
        bundle_sha256=bundle_hash,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Oracle repo root (default: repo root)",
    )
    args = parser.parse_args()

    try:
        contract = validate_contract(args.root)
    except MessageSourceContractError as exc:
        print(f"ERROR: expanded message source contract invalid: {exc}", file=sys.stderr)
        return 1

    print(
        "Expanded message source contract valid: "
        f"{contract.message_count} messages, "
        f"{contract.data_size} bytes, "
        f"bundle SHA-256 {contract.bundle_sha256}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
