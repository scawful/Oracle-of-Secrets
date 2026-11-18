#!/usr/bin/env python3
"""Build an approval-gated X post draft from a promo-capture bundle.

Does NOT post. Writes a post JSON compatible with the existing Keychain-backed
`x_post.py` (AFS handoffs/.../promo/x_post.py). Posting still requires:
  1. scawful's exact approval text in the `approved` field
  2. running x_post.py --send yourself (or with that approved file)

Never targets oos-rc-play. Never prints credentials.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_X_POST = Path.home() / (
    ".context/projects/oracle-of-secrets/scratchpad/handoffs/"
    "yaze_release_1_0_2026-10-31/promo/x_post.py"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_manifest(bundle: Path) -> dict:
    path = bundle / "manifest.json"
    if not path.is_file():
        raise SystemExit(f"missing manifest: {path}")
    return json.loads(path.read_text())


def pick_media(bundle: Path, manifest: dict, *, max_images: int = 4) -> list[Path]:
    exports = manifest.get("exports") or {}
    media: list[Path] = []
    for key in ("avi", "clip", "gif"):
        name = exports.get(key)
        if name:
            path = bundle / name
            if path.is_file():
                media.append(path)
                break  # one video max for X
    if media and media[0].suffix.lower() in {".mp4", ".mov", ".avi", ".gif"}:
        return media[:1]

    frames = sorted((bundle / "frames").glob("*.png")) if (bundle / "frames").is_dir() else []
    sheet = bundle / "sheet.png"
    if sheet.is_file():
        media.append(sheet)
    for frame in frames:
        if len(media) >= max_images:
            break
        if frame not in media:
            media.append(frame)
    return media[:max_images]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path, help="promo-capture.v1 output directory")
    p.add_argument("--caption", required=True, help="Exact caption text for the draft")
    p.add_argument(
        "--out",
        type=Path,
        help="Output post JSON (default: bundle/social/draft_<ts>.json)",
    )
    p.add_argument(
        "--approved",
        default="",
        help="Optional scawful approval quote (leave empty until approved)",
    )
    p.add_argument(
        "--reply",
        default="",
        help="Optional reply text (posted as thread reply by x_post.py)",
    )
    p.add_argument(
        "--x-post",
        type=Path,
        default=DEFAULT_X_POST,
        help="Path to existing x_post.py for dry-run check",
    )
    p.add_argument(
        "--dry-run-x",
        action="store_true",
        help="If approved is set, run x_post.py dry-run (never --send)",
    )
    args = p.parse_args()

    bundle = args.bundle.expanduser().resolve()
    manifest = load_manifest(bundle)
    media = pick_media(bundle, manifest)
    if not media:
        raise SystemExit(f"no media found under {bundle}")

    social_dir = bundle / "social"
    social_dir.mkdir(parents=True, exist_ok=True)
    media_dir = social_dir / "media"
    media_dir.mkdir(exist_ok=True)
    copied: list[str] = []
    for src in media:
        dest = media_dir / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        copied.append(str(dest))

    out = args.out or (social_dir / f"draft_{_now()}.json")
    out = out.expanduser().resolve()
    post = {
        "text": args.caption,
        "media": copied,
        "approved": args.approved,
        "reply": args.reply,
        "source": {
            "bundle": str(bundle),
            "manifest_schema": manifest.get("schema"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "note": "Dry-run only until `approved` quotes scawful and x_post.py --send is used.",
        },
    }
    out.write_text(json.dumps(post, indent=2) + "\n", encoding="utf-8")
    caption_path = social_dir / "caption.txt"
    caption_path.write_text(args.caption + "\n", encoding="utf-8")

    result = {
        "ok": True,
        "post_json": str(out),
        "caption_file": str(caption_path),
        "media": copied,
        "approved": bool(args.approved),
        "next": [
            "Show scawful the exact caption + media",
            "Set approved to their exact words, then:",
            f"python3 {args.x_post} {out}           # dry run",
            f"python3 {args.x_post} {out} --send    # only after approval",
        ],
    }

    if args.dry_run_x:
        if not args.approved:
            result["dry_run_x"] = {"ok": False, "error": "refusing dry-run without approved"}
        elif not args.x_post.is_file():
            result["dry_run_x"] = {"ok": False, "error": f"x_post.py not found: {args.x_post}"}
        else:
            import subprocess

            proc = subprocess.run(
                [sys.executable, str(args.x_post), str(out)],
                text=True,
                capture_output=True,
            )
            result["dry_run_x"] = {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[-800:],
                "stderr": (proc.stderr or "")[-400:],
            }
            result["ok"] = result["ok"] and proc.returncode == 0

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
