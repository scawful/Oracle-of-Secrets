#!/usr/bin/env python3
"""Publish or update Review Boards v2 packets for yaze.

Contract: scratchpad/handoffs/review_boards_v2_2026-11-17/SPEC.md (QUEUE238).
- Validates yaze.review_board.v2 packets (same limits as yaze).
- Copies PNG/MP4 media into <dest>/<id>/media/ with sha256 and PNG dimensions.
- Updates superseded boards' status/superseded_by links.
- Supports status-only updates via --set-status ID STATUS --reason TEXT.
- Writes rollback copies of modified board.json files under
  ~/src/hobby/oracle-of-secrets-scratch/review-boards-publish/<UTC stamp>/.
- Writes board.json atomically via temp file + os.replace.
- Never reads, writes, or touches feedback-*.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
from typing import Any

SCHEMA_V1 = "yaze.review_board.v1"
SCHEMA_V2 = "yaze.review_board.v2"

MAX_MEDIA = 8
MAX_IMAGE_SIDE = 8192
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_QUESTIONS = 12
MAX_OPTIONS = 12

BOARD_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
ITEM_ID_RE = re.compile(r"^[a-z0-9_]{1,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

VALID_PRIORITIES = ("high", "normal", "low")
VALID_STATUSES = ("current", "superseded", "stale_landed", "stale_decided")
VALID_QUESTION_KINDS = ("single", "multi", "text", "number", "yes_no")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

DEFAULT_BUNDLE_PATH = Path(
    "~/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj"
).expanduser()
DEFAULT_SCRATCH_ROOT = Path(
    "~/src/hobby/oracle-of-secrets-scratch/review-boards-publish"
).expanduser()


class BoardValidationError(ValueError):
    """Raised when a board packet fails Review Board v2 validation."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_stamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_iso_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_default_dest(bundle_path: Path = DEFAULT_BUNDLE_PATH) -> Path:
    project_file = bundle_path / "project.yaze"
    if not project_file.is_file():
        raise FileNotFoundError(
            f"Could not find project file at {project_file}; pass --dest explicitly"
        )
    app_data_folder = ".workspace/yaze"
    for raw_line in project_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            if key.strip() == "app_data_folder" and val.strip():
                app_data_folder = val.strip()
                break
    app_data_path = Path(app_data_folder)
    if not app_data_path.is_absolute():
        app_data_path = bundle_path / app_data_path
    return app_data_path / "review_boards"


def valid_board_id(board_id: str) -> bool:
    if not isinstance(board_id, str) or not BOARD_ID_RE.match(board_id):
        return False
    return board_id.strip(".") != ""


def valid_relative_media_path(rel_path: str) -> bool:
    if (
        not isinstance(rel_path, str)
        or not rel_path
        or len(rel_path) > 255
        or "\\" in rel_path
        or "\x00" in rel_path
    ):
        return False
    parsed = Path(rel_path)
    if parsed.is_absolute() or parsed.drive or parsed.root:
        return False
    for part in parsed.parts:
        if part in ("", ".", ".."):
            return False
    return True


def read_png_dimensions(data: bytes, label: str) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise BoardValidationError(f"{label} is not a valid PNG (missing IHDR)")
    width, height = struct.unpack(">II", data[16:24])
    if (
        width <= 0
        or height <= 0
        or width > MAX_IMAGE_SIDE
        or height > MAX_IMAGE_SIDE
    ):
        raise BoardValidationError(
            f"{label} dimensions {width}x{height} outside 1..{MAX_IMAGE_SIDE}"
        )
    return width, height


def inspect_media_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise BoardValidationError(f"Media file is missing or symlink: {path}")
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise BoardValidationError(
            f"Media file {path} exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MiB"
        )
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    suffix = path.suffix.lower()
    if suffix == ".png":
        width, height = read_png_dimensions(data, str(path))
        return {
            "kind": "image",
            "sha256": digest,
            "width": width,
            "height": height,
        }
    if suffix == ".mp4":
        return {
            "kind": "video",
            "sha256": digest,
            "width": 0,
            "height": 0,
        }
    raise BoardValidationError(
        f"Unsupported media extension for {path.name} (expected .png or .mp4)"
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_str(obj: dict[str, Any], key: str, allow_empty: bool = True) -> str:
    if key not in obj or obj[key] is None:
        if allow_empty:
            return ""
        raise BoardValidationError(f"'{key}' is required")
    val = obj[key]
    if not isinstance(val, str):
        raise BoardValidationError(f"'{key}' must be a string")
    if not allow_empty and not val.strip():
        raise BoardValidationError(f"'{key}' must not be empty")
    return val


def _require_str_list(obj: dict[str, Any], key: str) -> list[str]:
    if key not in obj or obj[key] is None:
        return []
    val = obj[key]
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise BoardValidationError(f"'{key}' must be a list of strings")
    return list(val)


def validate_question(
    raw_q: Any, index: int, seen_qids: set[str], media_list: list[dict[str, Any]]
) -> dict[str, Any]:
    if not isinstance(raw_q, dict):
        raise BoardValidationError(f"questions[{index}] must be an object")
    qid = _require_str(raw_q, "id", allow_empty=False)
    if not ITEM_ID_RE.match(qid):
        raise BoardValidationError(
            f"questions[{index}].id '{qid}' must match [a-z0-9_]{{1,40}}"
        )
    if qid in seen_qids:
        raise BoardValidationError(f"Duplicate question id '{qid}'")
    seen_qids.add(qid)

    prompt = _require_str(raw_q, "prompt", allow_empty=False)
    kind = _require_str(raw_q, "kind", allow_empty=False)
    if kind not in VALID_QUESTION_KINDS:
        raise BoardValidationError(
            f"Question '{qid}' kind '{kind}' must be one of {VALID_QUESTION_KINDS}"
        )

    required = raw_q.get("required", False)
    if not isinstance(required, bool):
        raise BoardValidationError(f"Question '{qid}' required must be boolean")

    allow_other = raw_q.get("allow_other", False)
    if not isinstance(allow_other, bool):
        raise BoardValidationError(
            f"Question '{qid}' allow_other must be boolean"
        )
    if allow_other and kind not in ("single", "multi"):
        raise BoardValidationError(
            f"Question '{qid}' allow_other is only valid for single/multi"
        )

    placeholder = _require_str(raw_q, "placeholder", allow_empty=True)

    q_min = raw_q.get("min", None)
    q_max = raw_q.get("max", None)
    if q_min is not None and not _is_number(q_min):
        raise BoardValidationError(f"Question '{qid}' min must be a number or null")
    if q_max is not None and not _is_number(q_max):
        raise BoardValidationError(f"Question '{qid}' max must be a number or null")
    if q_min is not None and q_max is not None and q_min > q_max:
        raise BoardValidationError(f"Question '{qid}' min ({q_min}) > max ({q_max})")

    raw_options = raw_q.get("options", [])
    if raw_options is None:
        raw_options = []
    if not isinstance(raw_options, list):
        raise BoardValidationError(f"Question '{qid}' options must be a list")
    if len(raw_options) > MAX_OPTIONS:
        raise BoardValidationError(
            f"Question '{qid}' has {len(raw_options)} options (max {MAX_OPTIONS})"
        )
    if kind in ("single", "multi") and not raw_options:
        raise BoardValidationError(
            f"Question '{qid}' of kind '{kind}' requires at least one option"
        )
    if kind not in ("single", "multi") and raw_options:
        raise BoardValidationError(
            f"Question '{qid}' of kind '{kind}' must not define options"
        )

    seen_opt_ids: set[str] = set()
    options: list[dict[str, Any]] = []
    for opt_idx, raw_opt in enumerate(raw_options):
        if not isinstance(raw_opt, dict):
            raise BoardValidationError(
                f"Question '{qid}' options[{opt_idx}] must be an object"
            )
        oid = _require_str(raw_opt, "id", allow_empty=False)
        if not ITEM_ID_RE.match(oid):
            raise BoardValidationError(
                f"Question '{qid}' option id '{oid}' must match [a-z0-9_]{{1,40}}"
            )
        if oid in seen_opt_ids:
            raise BoardValidationError(
                f"Question '{qid}' has duplicate option id '{oid}'"
            )
        seen_opt_ids.add(oid)
        label = _require_str(raw_opt, "label", allow_empty=False)
        detail = _require_str(raw_opt, "detail", allow_empty=True)
        recommended = raw_opt.get("recommended", False)
        if not isinstance(recommended, bool):
            raise BoardValidationError(
                f"Question '{qid}' option '{oid}' recommended must be boolean"
            )
        opt_media = raw_opt.get("media", None)
        if opt_media is not None:
            if isinstance(opt_media, bool) or not isinstance(opt_media, int):
                raise BoardValidationError(
                    f"Question '{qid}' option '{oid}' media must be an integer index"
                )
            if opt_media < 0 or opt_media >= len(media_list):
                raise BoardValidationError(
                    f"Question '{qid}' option '{oid}' media index {opt_media} "
                    f"out of range (0..{len(media_list) - 1})"
                )
            if media_list[opt_media].get("kind") != "image":
                raise BoardValidationError(
                    f"Question '{qid}' option '{oid}' media[{opt_media}] must be an image"
                )
        opt_out: dict[str, Any] = {
            "id": oid,
            "label": label,
            "detail": detail,
            "media": opt_media,
            "recommended": recommended,
        }
        options.append(opt_out)

    default_val = raw_q.get("default", None)
    if default_val is not None:
        if kind == "single":
            if not isinstance(default_val, str) or default_val not in seen_opt_ids:
                raise BoardValidationError(
                    f"Question '{qid}' default must be a valid option id"
                )
        elif kind == "multi":
            if not isinstance(default_val, list) or not all(
                isinstance(x, str) and x in seen_opt_ids for x in default_val
            ):
                raise BoardValidationError(
                    f"Question '{qid}' default must be a list of valid option ids"
                )
        elif kind == "text":
            if not isinstance(default_val, str):
                raise BoardValidationError(
                    f"Question '{qid}' default must be a string"
                )
        elif kind == "number":
            if not _is_number(default_val):
                raise BoardValidationError(
                    f"Question '{qid}' default must be a number"
                )
            if q_min is not None and default_val < q_min:
                raise BoardValidationError(
                    f"Question '{qid}' default {default_val} < min {q_min}"
                )
            if q_max is not None and default_val > q_max:
                raise BoardValidationError(
                    f"Question '{qid}' default {default_val} > max {q_max}"
                )
        elif kind == "yes_no":
            if not isinstance(default_val, bool):
                raise BoardValidationError(
                    f"Question '{qid}' default must be a boolean"
                )

    return {
        "id": qid,
        "prompt": prompt,
        "kind": kind,
        "required": required,
        "options": options,
        "allow_other": allow_other,
        "placeholder": placeholder,
        "min": q_min,
        "max": q_max,
        "default": default_val,
    }


def scan_max_order(dest: Path) -> int:
    if not dest.is_dir():
        return 0
    max_order = 0
    for child in sorted(dest.iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        board_file = child / "board.json"
        if not board_file.is_file():
            continue
        try:
            data = json.loads(board_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("order"), int):
            if not isinstance(data.get("order"), bool):
                max_order = max(max_order, data["order"])
    return max_order


def prepare_media_plan(
    raw_board: dict[str, Any],
    board_source_dir: Path,
    cli_media: list[Path],
    existing_board_dir: Path | None,
) -> tuple[list[dict[str, Any]], list[tuple[Path, str]]]:
    """Build normalized media[] entries and (src_file, dest_rel_path) copy plan."""
    raw_media = raw_board.get("media")
    if raw_media is not None and not isinstance(raw_media, list):
        raise BoardValidationError("'media' must be a list")
    raw_entries: list[dict[str, Any]] = list(raw_media) if raw_media else []

    copy_plan: list[tuple[Path, str]] = []
    normalized: list[dict[str, Any]] = []
    used_rel_paths: set[str] = set()

    if cli_media:
        for idx, src_path in enumerate(cli_media):
            src_resolved = src_path.expanduser().resolve()
            meta = inspect_media_file(src_resolved)
            template = raw_entries[idx] if idx < len(raw_entries) else {}
            if not isinstance(template, dict):
                raise BoardValidationError(f"media[{idx}] must be an object")
            caption = _require_str(template, "caption", allow_empty=True)
            rel_path = _require_str(template, "path", allow_empty=True)
            if not rel_path:
                candidate = f"media/{src_resolved.name}"
                if candidate in used_rel_paths:
                    candidate = f"media/{idx + 1}-{src_resolved.name}"
                rel_path = candidate
            if not valid_relative_media_path(rel_path):
                raise BoardValidationError(
                    f"media[{idx}] path '{rel_path}' must stay inside board folder"
                )
            used_rel_paths.add(rel_path)
            entry: dict[str, Any] = {
                "path": rel_path,
                "sha256": meta["sha256"],
                "kind": meta["kind"],
                "caption": caption,
            }
            if meta["kind"] == "image":
                entry["width"] = meta["width"]
                entry["height"] = meta["height"]
            normalized.append(entry)
            copy_plan.append((src_resolved, rel_path))

        # Keep any extra pre-populated entries beyond len(cli_media) if present.
        extra_entries = raw_entries[len(cli_media) :]
    else:
        extra_entries = raw_entries

    for idx_offset, item in enumerate(extra_entries):
        idx = len(normalized)
        if not isinstance(item, dict):
            raise BoardValidationError(f"media[{idx}] must be an object")
        rel_path = _require_str(item, "path", allow_empty=False)
        if not valid_relative_media_path(rel_path):
            raise BoardValidationError(
                f"media[{idx}] path '{rel_path}' must stay inside board folder"
            )
        caption = _require_str(item, "caption", allow_empty=True)

        # Locate backing file if present alongside input board.json or existing board folder.
        src_candidate: Path | None = None
        if "source_path" in item and item["source_path"]:
            src_candidate = Path(_require_str(item, "source_path")).expanduser()
            if not src_candidate.is_absolute():
                src_candidate = (board_source_dir / src_candidate).resolve()
        else:
            local_candidate = board_source_dir / rel_path
            if local_candidate.is_file():
                src_candidate = local_candidate.resolve()
            elif existing_board_dir is not None and (existing_board_dir / rel_path).is_file():
                src_candidate = (existing_board_dir / rel_path).resolve()

        if src_candidate is not None:
            meta = inspect_media_file(src_candidate)
            sha256 = item.get("sha256") or meta["sha256"]
            if sha256 != meta["sha256"]:
                raise BoardValidationError(
                    f"media[{idx}] sha256 mismatch for {rel_path}"
                )
            kind = item.get("kind") or meta["kind"]
            width = meta["width"]
            height = meta["height"]
            if existing_board_dir is None or src_candidate != (existing_board_dir / rel_path).resolve():
                copy_plan.append((src_candidate, rel_path))
        else:
            sha256 = _require_str(item, "sha256", allow_empty=False)
            kind = _require_str(item, "kind", allow_empty=False)
            width = item.get("width", 0)
            height = item.get("height", 0)

        if not SHA256_RE.match(sha256):
            raise BoardValidationError(
                f"media[{idx}] needs a 64-char lowercase hex sha256"
            )
        if kind not in ("image", "video"):
            raise BoardValidationError(
                f"media[{idx}] kind must be 'image' or 'video'"
            )
        if kind == "image" and not rel_path.lower().endswith(".png"):
            raise BoardValidationError(f"image {rel_path} must end with .png")

        entry = {
            "path": rel_path,
            "sha256": sha256,
            "kind": kind,
            "caption": caption,
        }
        if isinstance(width, int) and not isinstance(width, bool) and width > 0:
            entry["width"] = width
        if isinstance(height, int) and not isinstance(height, bool) and height > 0:
            entry["height"] = height
        normalized.append(entry)

    if not normalized:
        raise BoardValidationError("media must list at least one file")
    if len(normalized) > MAX_MEDIA:
        raise BoardValidationError(
            f"media lists {len(normalized)} files (max {MAX_MEDIA})"
        )
    return normalized, copy_plan


def build_and_validate_board(
    raw_board: dict[str, Any],
    board_source_dir: Path,
    cli_media: list[Path],
    dest: Path,
    replace: bool,
) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    if not isinstance(raw_board, dict):
        raise BoardValidationError("Input board JSON must be an object")

    schema = raw_board.get("schema", SCHEMA_V2)
    if schema not in (SCHEMA_V1, SCHEMA_V2):
        raise BoardValidationError(
            f"schema must be '{SCHEMA_V2}' (or '{SCHEMA_V1}'), got '{schema}'"
        )

    board_id = _require_str(raw_board, "id", allow_empty=False)
    if not valid_board_id(board_id):
        raise BoardValidationError(
            "id must be 1-96 characters of A-Z a-z 0-9 . _ -"
        )

    target_dir = dest / board_id
    target_board_json = target_dir / "board.json"
    if target_board_json.exists() and not replace:
        raise FileExistsError(
            f"Board '{board_id}' already exists at {target_board_json}; "
            "pass --replace to overwrite board.json"
        )

    title = _require_str(raw_board, "title", allow_empty=False)
    why = _require_str(raw_board, "why", allow_empty=True)
    ask = _require_str(raw_board, "ask", allow_empty=True)
    author = _require_str(raw_board, "author", allow_empty=True)
    group = _require_str(raw_board, "group", allow_empty=True)

    priority = raw_board.get("priority", "normal")
    if priority is None or priority == "":
        priority = "normal"
    if not isinstance(priority, str) or priority not in VALID_PRIORITIES:
        raise BoardValidationError(
            f"priority must be one of {VALID_PRIORITIES}, got '{priority}'"
        )

    status = raw_board.get("status", "current")
    if status is None or status == "":
        status = "current"
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise BoardValidationError(
            f"status must be one of {VALID_STATUSES}, got '{status}'"
        )
    status_reason = _require_str(raw_board, "status_reason", allow_empty=True)

    created_at = _require_str(raw_board, "created_at", allow_empty=True)
    if not created_at:
        created_at = utc_now_iso()
    else:
        try:
            parse_iso_utc(created_at)
        except ValueError as exc:
            raise BoardValidationError(
                f"created_at '{created_at}' is not valid ISO-8601: {exc}"
            ) from exc

    raw_order = raw_board.get("order")
    if raw_order is None:
        existing_order: int | None = None
        if replace and target_board_json.is_file():
            try:
                prev = json.loads(target_board_json.read_text(encoding="utf-8"))
                if (
                    isinstance(prev, dict)
                    and isinstance(prev.get("order"), int)
                    and not isinstance(prev.get("order"), bool)
                ):
                    existing_order = prev["order"]
            except (OSError, json.JSONDecodeError):
                existing_order = None
        order = (
            existing_order
            if existing_order is not None
            else scan_max_order(dest) + 1
        )
    elif isinstance(raw_order, int) and not isinstance(raw_order, bool):
        order = raw_order
    else:
        raise BoardValidationError("order must be an integer")

    subject_out: dict[str, str] | None = None
    if "subject" in raw_board and raw_board["subject"] is not None:
        subj = raw_board["subject"]
        if not isinstance(subj, dict):
            raise BoardValidationError("subject must be an object")
        subject_out = {
            "kind": _require_str(subj, "kind", allow_empty=True),
            "id": _require_str(subj, "id", allow_empty=True),
            "label": _require_str(subj, "label", allow_empty=True),
        }

    supersedes = _require_str_list(raw_board, "supersedes")
    for sid in supersedes:
        if not valid_board_id(sid) or sid == board_id:
            raise BoardValidationError(f"Invalid supersedes board id '{sid}'")
    superseded_by = _require_str_list(raw_board, "superseded_by")
    for sid in superseded_by:
        if not valid_board_id(sid) or sid == board_id:
            raise BoardValidationError(f"Invalid superseded_by board id '{sid}'")

    details_out: list[dict[str, str]] = []
    if "details" in raw_board and raw_board["details"] is not None:
        if not isinstance(raw_board["details"], list):
            raise BoardValidationError("details must be a list")
        for idx, item in enumerate(raw_board["details"]):
            if not isinstance(item, dict):
                raise BoardValidationError(f"details[{idx}] must be an object")
            details_out.append(
                {
                    "label": _require_str(item, "label", allow_empty=True),
                    "text": _require_str(item, "text", allow_empty=True),
                }
            )

    comments_out: list[dict[str, Any]] = []
    if "comments" in raw_board and raw_board["comments"] is not None:
        if not isinstance(raw_board["comments"], list):
            raise BoardValidationError("comments must be a list")
        for idx, item in enumerate(raw_board["comments"]):
            if not isinstance(item, dict):
                raise BoardValidationError(f"comments[{idx}] must be an object")
            c_out: dict[str, Any] = {
                "id": _require_str(item, "id", allow_empty=True),
                "at": _require_str(item, "at", allow_empty=True),
                "author": _require_str(item, "author", allow_empty=True),
                "text": _require_str(item, "text", allow_empty=True),
                "source": _require_str(item, "source", allow_empty=True),
            }
            if "pin" in item and item["pin"] is not None:
                pin = item["pin"]
                if (
                    not isinstance(pin, dict)
                    or not _is_number(pin.get("x"))
                    or not _is_number(pin.get("y"))
                ):
                    raise BoardValidationError(
                        f"comments[{idx}].pin must have numeric x and y"
                    )
                c_out["pin"] = {"x": float(pin["x"]), "y": float(pin["y"])}
            comments_out.append(c_out)

    existing_dir = target_dir if (replace and target_dir.is_dir()) else None
    media_out, copy_plan = prepare_media_plan(
        raw_board, board_source_dir, cli_media, existing_dir
    )

    raw_questions = raw_board.get("questions", [])
    if raw_questions is None:
        raw_questions = []
    if not isinstance(raw_questions, list):
        raise BoardValidationError("questions must be a list")
    if len(raw_questions) > MAX_QUESTIONS:
        raise BoardValidationError(
            f"questions lists {len(raw_questions)} items (max {MAX_QUESTIONS})"
        )
    seen_qids: set[str] = set()
    questions_out = [
        validate_question(q, idx, seen_qids, media_out)
        for idx, q in enumerate(raw_questions)
    ]

    board_out: dict[str, Any] = {
        "schema": SCHEMA_V2,
        "id": board_id,
        "title": title,
    }
    if ask:
        board_out["ask"] = ask
    board_out["priority"] = priority
    if why:
        board_out["why"] = why
    if author:
        board_out["author"] = author
    if group:
        board_out["group"] = group
    board_out["created_at"] = created_at
    board_out["status"] = status
    if status_reason:
        board_out["status_reason"] = status_reason
    board_out["order"] = order
    if subject_out and any(subject_out.values()):
        board_out["subject"] = subject_out
    if supersedes:
        board_out["supersedes"] = supersedes
    if superseded_by:
        board_out["superseded_by"] = superseded_by
    if details_out:
        board_out["details"] = details_out
    if comments_out:
        board_out["comments"] = comments_out
    board_out["questions"] = questions_out
    board_out["media"] = media_out

    return board_out, copy_plan


def atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp-", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def save_rollback_copy(
    existing_board_file: Path, board_id: str, rollback_dir: Path
) -> Path:
    if not existing_board_file.is_file():
        raise FileNotFoundError(existing_board_file)
    backup_target = rollback_dir / board_id / "board.json"
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(existing_board_file, backup_target)
    return backup_target


def run_set_status(
    dest: Path,
    board_id: str,
    new_status: str,
    reason: str,
    dry_run: bool,
    scratch_root: Path,
) -> dict[str, Any]:
    if not valid_board_id(board_id):
        raise BoardValidationError(f"Invalid board id '{board_id}'")
    if new_status not in VALID_STATUSES:
        raise BoardValidationError(
            f"status must be one of {VALID_STATUSES}, got '{new_status}'"
        )
    board_file = dest / board_id / "board.json"
    if not board_file.is_file():
        raise FileNotFoundError(f"Board not found: {board_file}")
    data = json.loads(board_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BoardValidationError(f"{board_file} is not a JSON object")

    old_status = data.get("status", "")
    data["status"] = new_status
    if reason:
        data["status_reason"] = reason

    receipt: dict[str, Any] = {
        "mode": "set_status",
        "dry_run": dry_run,
        "id": board_id,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
        "board_file": str(board_file),
    }
    if dry_run:
        return receipt

    rollback_dir = scratch_root / utc_stamp_compact()
    backup = save_rollback_copy(board_file, board_id, rollback_dir)
    atomic_write_json(board_file, data)
    atomic_write_json(
        rollback_dir / "manifest.json",
        {
            "at": utc_now_iso(),
            "action": "set_status",
            "modified": [board_id],
            "created": [],
        },
    )
    receipt["rollback_copy"] = str(backup)
    return receipt


def run_publish(
    board_json_path: Path,
    cli_media: list[Path],
    dest: Path,
    dry_run: bool,
    replace: bool,
    scratch_root: Path,
) -> dict[str, Any]:
    raw_board = json.loads(board_json_path.read_text(encoding="utf-8"))
    board_out, copy_plan = build_and_validate_board(
        raw_board, board_json_path.parent.resolve(), cli_media, dest, replace
    )
    board_id = board_out["id"]
    target_dir = dest / board_id
    target_board_file = target_dir / "board.json"
    existed = target_board_file.is_file()

    superseded_updates: list[tuple[str, Path, dict[str, Any]]] = []
    missing_supersedes: list[str] = []
    for old_id in board_out.get("supersedes", []):
        old_file = dest / old_id / "board.json"
        if not old_file.is_file():
            missing_supersedes.append(old_id)
            continue
        old_data = json.loads(old_file.read_text(encoding="utf-8"))
        if not isinstance(old_data, dict):
            raise BoardValidationError(f"Superseded board {old_file} is invalid")
        old_data["status"] = "superseded"
        sup_by = list(old_data.get("superseded_by") or [])
        if board_id not in sup_by:
            sup_by.append(board_id)
        old_data["superseded_by"] = sup_by
        if not old_data.get("status_reason"):
            old_data["status_reason"] = f"Superseded by {board_id}"
        superseded_updates.append((old_id, old_file, old_data))

    receipt: dict[str, Any] = {
        "mode": "publish",
        "dry_run": dry_run,
        "id": board_id,
        "order": board_out["order"],
        "created_at": board_out["created_at"],
        "questions": len(board_out["questions"]),
        "media": len(board_out["media"]),
        "replaced": existed,
        "superseded_updated": [sid for sid, _, _ in superseded_updates],
        "superseded_missing": missing_supersedes,
        "board_file": str(target_board_file),
    }
    if dry_run:
        return receipt

    rollback_dir = scratch_root / f"{utc_stamp_compact()}-{board_id}"
    modified_ids: list[str] = []
    created_ids: list[str] = []

    if existed:
        save_rollback_copy(target_board_file, board_id, rollback_dir)
        modified_ids.append(board_id)
    else:
        created_ids.append(board_id)

    for old_id, old_file, _ in superseded_updates:
        save_rollback_copy(old_file, old_id, rollback_dir)
        modified_ids.append(old_id)

    # Copy media files into <dest>/<id>/<rel_path> without touching feedback-*.json.
    for src_file, rel_path in copy_plan:
        dst_media = target_dir / rel_path
        dst_media.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_media)

    atomic_write_json(target_board_file, board_out)

    for _, old_file, old_data in superseded_updates:
        atomic_write_json(old_file, old_data)

    rollback_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        rollback_dir / "manifest.json",
        {
            "at": utc_now_iso(),
            "action": "publish",
            "board_id": board_id,
            "created": created_ids,
            "modified": modified_ids,
        },
    )
    receipt["rollback_dir"] = str(rollback_dir)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish or update Oracle Review Boards v2 packets."
    )
    parser.add_argument(
        "--board",
        type=Path,
        help="Path to input board.json draft (publish mode).",
    )
    parser.add_argument(
        "--media",
        type=Path,
        nargs="+",
        action="extend",
        default=[],
        help="Media file(s) (.png or .mp4) to copy into <id>/media/.",
    )
    parser.add_argument(
        "--set-status",
        nargs=2,
        metavar=("ID", "STATUS"),
        help="Update only status (and --reason) on an existing board.",
    )
    parser.add_argument(
        "--reason",
        default="",
        help="Status reason text for --set-status.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination review_boards directory (default: live project.yaze app_data_folder/review_boards).",
    )
    parser.add_argument(
        "--scratch-root",
        type=Path,
        default=DEFAULT_SCRATCH_ROOT,
        help="Directory for rollback copies of modified board.json files.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Allow replacing an existing <id>/board.json (never touches feedback-*.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and compute plan without writing any files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if bool(args.board) == bool(args.set_status):
        parser.error("Pass exactly one of --board or --set-status ID STATUS")

    try:
        dest = (
            args.dest.expanduser().resolve()
            if args.dest is not None
            else resolve_default_dest()
        )
        scratch_root = args.scratch_root.expanduser().resolve()
        if args.set_status:
            board_id, new_status = args.set_status
            receipt = run_set_status(
                dest=dest,
                board_id=board_id,
                new_status=new_status,
                reason=args.reason,
                dry_run=args.dry_run,
                scratch_root=scratch_root,
            )
        else:
            receipt = run_publish(
                board_json_path=args.board.expanduser().resolve(),
                cli_media=args.media,
                dest=dest,
                dry_run=args.dry_run,
                replace=args.replace,
                scratch_root=scratch_root,
            )
    except (BoardValidationError, FileExistsError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
