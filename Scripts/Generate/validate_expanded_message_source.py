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
PROGRESSION_PATH = Path("Core/progression.asm")

FIRST_MESSAGE_ID = 0x18D
LAST_MESSAGE_ID = 0x1F9
MESSAGE_COUNT = LAST_MESSAGE_ID - FIRST_MESSAGE_ID + 1
MESSAGE_DATA_START = 0x2F8026
MESSAGE_DATA_END = 0x2FFDFF
PROGRESSION_DATA_START = MESSAGE_DATA_END + 1
PROGRESSION_DATA_END_EXCLUSIVE = 0x300000

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
DICTIONARY_TOKEN_RE = re.compile(r"^D:([0-9A-F]{2})$")
ARGUMENT_TOKEN_RE = re.compile(r"^([A-Z0-9]+):([0-9A-F]{1,2})$")

CHARACTER_BYTES = {
    **{chr(ord("A") + index): index for index in range(26)},
    **{chr(ord("a") + index): 0x1A + index for index in range(26)},
    **{str(index): 0x34 + index for index in range(10)},
    "!": 0x3E,
    "?": 0x3F,
    "-": 0x40,
    ".": 0x41,
    ",": 0x42,
    ">": 0x44,
    "(": 0x45,
    ")": 0x46,
    '"': 0x4C,
    "'": 0x51,
    " ": 0x59,
    "<": 0x5A,
    "_": 0x66,
}

ARGUMENT_TOKEN_BYTES = {
    "W": 0x6B,
    "P": 0x6D,
    "SPD": 0x6E,
    "S": 0x7A,
    "C": 0x77,
    "WT": 0x78,
    "N": 0x6C,
    "SFX": 0x79,
}

TOKEN_BYTES = {
    "L": 0x6A,
    "1": 0x74,
    "2": 0x75,
    "3": 0x76,
    "K": 0x7E,
    "V": 0x73,
    "CH3": 0x71,
    "CH2": 0x72,
    "CH2L": 0x6F,
    "CH2I": 0x68,
    "CHI": 0x69,
    "IMG": 0x67,
    "NONO": 0x70,
    "...": 0x43,
    "UP": 0x4D,
    "DOWN": 0x4E,
    "LEFT": 0x4F,
    "RIGHT": 0x50,
    "A": 0x5B,
    "B": 0x5C,
    "X": 0x5D,
    "Y": 0x5E,
    "HP1L": 0x52,
    "HP1R": 0x53,
    "HP2L": 0x54,
    "HP3L": 0x55,
    "HP3R": 0x56,
    "HP4L": 0x57,
    "HP4R": 0x58,
    "HY0": 0x47,
    "HY1": 0x48,
    "HY2": 0x49,
    "LFL": 0x4A,
    "LFR": 0x4B,
}


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
        if not isinstance(entry["text"], str):
            raise MessageSourceContractError(
                f"canonical bundle message {expected_id} text must be a string"
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


def _encode_message_text(text: str, message_id: int) -> bytes:
    """Encode canonical source text with the Yaze message byte contract."""
    encoded = bytearray()
    position = 0
    while position < len(text):
        character = text[position]
        if character in "\r\n":
            raise MessageSourceContractError(
                f"canonical bundle message {message_id} contains a literal "
                "newline; use a message command token"
            )

        if character != "[":
            value = CHARACTER_BYTES.get(character)
            if value is None:
                raise MessageSourceContractError(
                    f"canonical bundle message {message_id} has unsupported "
                    f"character {character!r} at position {position}"
                )
            encoded.append(value)
            position += 1
            continue

        close = text.find("]", position)
        if close < 0:
            raise MessageSourceContractError(
                f"canonical bundle message {message_id} has an unclosed token "
                f"at position {position}"
            )
        token = text[position + 1:close]

        dictionary_match = DICTIONARY_TOKEN_RE.fullmatch(token)
        if dictionary_match:
            dictionary_index = int(dictionary_match.group(1), 16)
            if dictionary_index > 0x60:
                raise MessageSourceContractError(
                    f"canonical bundle message {message_id} dictionary index "
                    f"0x{dictionary_index:02X} is outside 0x00..0x60"
                )
            encoded.append(0x88 + dictionary_index)
            position = close + 1
            continue

        value = TOKEN_BYTES.get(token)
        if value is not None:
            encoded.append(value)
            position = close + 1
            continue

        argument_match = ARGUMENT_TOKEN_RE.fullmatch(token)
        if (
            argument_match
            and argument_match.group(1) in ARGUMENT_TOKEN_BYTES
        ):
            name = argument_match.group(1)
            argument = int(argument_match.group(2), 16)
            encoded.extend((ARGUMENT_TOKEN_BYTES[name], argument))
            position = close + 1
            continue

        raise MessageSourceContractError(
            f"canonical bundle message {message_id} has unknown token "
            f"[{token}] at position {position}"
        )

    encoded.append(0x7F)
    return bytes(encoded)


def _encode_bundle_messages(bundle: dict[str, Any]) -> list[tuple[int, bytes]]:
    return [
        (
            FIRST_MESSAGE_ID + entry["id"],
            _encode_message_text(entry["text"], entry["id"]),
        )
        for entry in bundle["messages"]
    ]


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
    include_path: Path,
    expected_bundle_hash: str,
    expected_messages: list[tuple[int, bytes]],
) -> tuple[list[int], bytes]:
    try:
        text = include_path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise MessageSourceContractError(
            f"cannot read generated include {include_path}: {exc}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise MessageSourceContractError(
            f"generated include is not valid UTF-8: {exc}"
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
    if not encoded or encoded[-1] != 0xFF:
        raise MessageSourceContractError(
            "generated include must end with bank terminator byte $FF"
        )

    messages: list[tuple[int, bytes]] = []
    for index, (message_id, start) in enumerate(labels):
        end = labels[index + 1][1] if index + 1 < len(labels) else len(encoded) - 1
        message = bytes(encoded[start:end])
        if not message or message[-1] != 0x7F:
            raise MessageSourceContractError(
                f"Message_{message_id:03X} must end with byte $7F"
            )
        messages.append((message_id, message))

    if messages != expected_messages:
        mismatch_index = next(
            (
                index
                for index, (actual, expected) in enumerate(
                    zip(messages, expected_messages)
                )
                if actual != expected
            ),
            0,
        )
        message_id = FIRST_MESSAGE_ID + mismatch_index
        raise MessageSourceContractError(
            "generated include does not encode the canonical bundle at "
            f"Message_{message_id:03X}"
        )

    capacity = MESSAGE_DATA_END - MESSAGE_DATA_START + 1
    if len(encoded) > capacity:
        raise MessageSourceContractError(
            "generated expanded-message data exceeds fixed allocation: "
            f"{len(encoded)} bytes > {capacity} bytes"
        )

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

    message_start = f"{MESSAGE_DATA_START:06X}"
    message_end = f"{MESSAGE_DATA_END:06X}"
    progression_start = f"{PROGRESSION_DATA_START:06X}"
    boundary = (
        f'assert pc() <= ${message_start}, '
        f'"MessageExpand loader crossed fixed data start ${message_start}"'
    )
    include = 'incsrc "Core/Generated/expanded_messages.asm"'
    capacity_boundary = (
        f'assert pc() <= ${progression_start}, '
        f'"Expanded messages crossed fixed allocation end ${message_end}"'
    )
    if text.count(boundary) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must assert that the loader does not cross "
            "$2F8026"
        )
    data_org = f"org ${message_start}"
    if text.count(data_org) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must fix MessageExpandedData at $2F8026"
        )
    if text.count("MessageExpandedData:") != 1 or text.count(include) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must define MessageExpandedData and include "
            "Core/Generated/expanded_messages.asm exactly once"
        )
    if text.index(boundary) > text.index(data_org):
        raise MessageSourceContractError(
            "loader boundary assert must precede the fixed data org"
        )
    if not (
        text.index(data_org)
        < text.index("MessageExpandedData:")
        < text.index(include)
    ):
        raise MessageSourceContractError(
            "fixed data org, MessageExpandedData, and generated include are "
            "out of order"
        )
    if text.count(capacity_boundary) != 1:
        raise MessageSourceContractError(
            "Core/message.asm must stop expanded messages before the fixed "
            "progression allocation at $2FFE00"
        )
    if text.index(capacity_boundary) < text.index(include):
        raise MessageSourceContractError(
            "expanded-message capacity assert must follow the generated include"
        )


def _validate_progression(progression_path: Path) -> None:
    try:
        text = progression_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MessageSourceContractError(
            f"cannot read progression source {progression_path}: {exc}"
        ) from exc

    progression_start = f"{PROGRESSION_DATA_START:06X}"
    progression_end = f"{PROGRESSION_DATA_END_EXCLUSIVE:06X}"
    start = f"org ${progression_start}"
    boundary = (
        f'assert pc() <= ${progression_end}, '
        '"Progression helpers crossed bank $2F"'
    )
    if text.count(start) != 1:
        raise MessageSourceContractError(
            "Core/progression.asm must use fixed allocation start $2FFE00"
        )
    if text.count(boundary) != 1 or text.index(boundary) < text.index(start):
        raise MessageSourceContractError(
            "Core/progression.asm must stay within the reserved bank $2F tail"
        )


def validate_contract(root: Path) -> MessageSourceContract:
    root = root.resolve()
    bundle, _, bundle_hash = _load_bundle(root / BUNDLE_PATH)
    expected_messages = _encode_bundle_messages(bundle)
    labels, encoded = _parse_asm_include(
        root / ASM_INCLUDE_PATH, bundle_hash, expected_messages
    )
    _validate_wrapper(root / MESSAGE_WRAPPER_PATH)
    _validate_progression(root / PROGRESSION_PATH)
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
