"""Tests for Scripts/Review/{publish_board,collect_feedback}.py (QUEUE238).

Compatible with both `pytest Scripts/Review/tests` and
`python3 -m unittest discover -s Scripts/Review/tests`.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

REVIEW_DIR = Path(__file__).resolve().parents[1]
if str(REVIEW_DIR) not in sys.path:
    sys.path.insert(0, str(REVIEW_DIR))

import collect_feedback  # noqa: E402
import publish_board  # noqa: E402


def make_png_bytes(
    width: int = 4, height: int = 3, rgb: tuple[int, int, int] = (20, 80, 160)
) -> bytes:
    """Create a minimal valid RGB PNG in memory."""

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", crc)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width
    idat = zlib.compress(row * height)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def write_png(path: Path, width: int = 4, height: int = 3) -> tuple[Path, str]:
    data = make_png_bytes(width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def sample_v2_board(board_id: str = "sky-8c-style-01") -> dict:
    return {
        "schema": "yaze.review_board.v2",
        "id": board_id,
        "title": "Sky Island $8C cliff style",
        "ask": "Pick the $8C cliff style and bridge offset.",
        "priority": "high",
        "why": "Compare b58 brown rock vs vanilla mountain trim.",
        "author": "Gemini-4-Carbon",
        "group": "sky-islands",
        "subject": {"kind": "map", "id": "$8C", "label": "Sky Island SW"},
        "questions": [
            {
                "id": "cliff_style",
                "prompt": "Which cliff style for $8C?",
                "kind": "single",
                "required": True,
                "options": [
                    {
                        "id": "a",
                        "label": "Brown b58 rock",
                        "detail": "Matches Sky sheets",
                        "media": 0,
                        "recommended": True,
                    },
                    {
                        "id": "b",
                        "label": "Vanilla trim",
                        "detail": "Zero extra tile8",
                        "media": 1,
                        "recommended": False,
                    },
                ],
                "allow_other": True,
            },
            {
                "id": "keep_layers",
                "prompt": "Which detail passes should stay?",
                "kind": "multi",
                "required": False,
                "options": [
                    {"id": "a", "label": "Cloud fringe"},
                    {"id": "c", "label": "Rope posts"},
                ],
                "allow_other": True,
                "default": ["a"],
            },
            {
                "id": "notes",
                "prompt": "Bridge placement notes",
                "kind": "text",
                "required": False,
                "placeholder": "Optional tile offset note",
            },
            {
                "id": "bridge_shift",
                "prompt": "East bridge shift (tiles)",
                "kind": "number",
                "required": True,
                "min": -4,
                "max": 4,
                "default": 0,
            },
            {
                "id": "ship_now",
                "prompt": "Port onto $8C immediately?",
                "kind": "yes_no",
                "required": True,
                "default": True,
            },
        ],
    }


class ReviewBoardScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_default_dest_reads_app_data_folder(self) -> None:
        bundle = self.tmp_path / "Sample.yazeproj"
        bundle.mkdir(parents=True)
        (bundle / "project.yaze").write_text(
            "# sample project\napp_data_folder=.workspace/yaze\n",
            encoding="utf-8",
        )
        resolved = publish_board.resolve_default_dest(bundle)
        self.assertEqual(resolved, bundle / ".workspace/yaze/review_boards")

    def test_publish_v2_board_copies_media_fills_order_and_created_at(self) -> None:
        dest = self.tmp_path / "review_boards"
        scratch = self.tmp_path / "scratch"
        src_dir = self.tmp_path / "src"
        img_a, sha_a = write_png(src_dir / "opt_a.png", 16, 12)
        img_b, sha_b = write_png(src_dir / "opt_b.png", 32, 24)

        existing_dir = dest / "existing-01"
        existing_dir.mkdir(parents=True)
        (existing_dir / "board.json").write_text(
            json.dumps(
                {
                    "schema": "yaze.review_board.v1",
                    "id": "existing-01",
                    "title": "Old",
                    "order": 7,
                }
            ),
            encoding="utf-8",
        )

        draft_path = src_dir / "draft.json"
        draft_path.write_text(json.dumps(sample_v2_board()), encoding="utf-8")

        rc = publish_board.main(
            [
                "--board",
                str(draft_path),
                "--media",
                str(img_a),
                "--media",
                str(img_b),
                "--dest",
                str(dest),
                "--scratch-root",
                str(scratch),
            ]
        )
        self.assertEqual(rc, 0)

        published_file = dest / "sky-8c-style-01" / "board.json"
        self.assertTrue(published_file.is_file())
        published = json.loads(published_file.read_text(encoding="utf-8"))
        self.assertEqual(published["schema"], "yaze.review_board.v2")
        self.assertEqual(published["order"], 8)
        self.assertTrue(published["created_at"].endswith("Z"))
        self.assertEqual(published["priority"], "high")
        self.assertEqual(len(published["questions"]), 5)
        self.assertEqual(published["media"][0]["sha256"], sha_a)
        self.assertEqual(published["media"][0]["width"], 16)
        self.assertEqual(published["media"][0]["height"], 12)
        self.assertEqual(published["media"][1]["sha256"], sha_b)
        self.assertTrue(
            (dest / "sky-8c-style-01" / published["media"][0]["path"]).is_file()
        )
        self.assertTrue(
            (dest / "sky-8c-style-01" / published["media"][1]["path"]).is_file()
        )

    def test_supersedes_replace_rollback_and_feedback_preservation(self) -> None:
        dest = self.tmp_path / "review_boards"
        scratch = self.tmp_path / "scratch"
        src_dir = self.tmp_path / "src"
        img_a, _ = write_png(src_dir / "a.png")
        img_b, _ = write_png(src_dir / "b.png")

        first = sample_v2_board("sky-8c-v1")
        first_draft = src_dir / "first.json"
        first_draft.write_text(json.dumps(first), encoding="utf-8")
        self.assertEqual(
            publish_board.main(
                [
                    "--board",
                    str(first_draft),
                    "--media",
                    str(img_a),
                    str(img_b),
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                ]
            ),
            0,
        )

        fb_v1 = dest / "sky-8c-v1" / "feedback-sky-8c-v1.json"
        fb_sentinel = '{"sentinel": "untouched"}\n'
        fb_v1.write_text(fb_sentinel, encoding="utf-8")

        # Refuses overwrite without --replace.
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                publish_board.main(
                    [
                        "--board",
                        str(first_draft),
                        "--media",
                        str(img_a),
                        str(img_b),
                        "--dest",
                        str(dest),
                        "--scratch-root",
                        str(scratch),
                    ]
                ),
                1,
            )
        self.assertEqual(fb_v1.read_text(encoding="utf-8"), fb_sentinel)

        # --replace updates board.json and media, saves rollback copies for both,
        # and keeps feedback untouched.
        img_a_v1_bytes = (dest / "sky-8c-v1" / "media" / "a.png").read_bytes()
        img_a_v2, sha_a_v2 = write_png(src_dir / "a.png", width=8, height=6)
        first_replaced = sample_v2_board("sky-8c-v1")
        first_replaced["title"] = "Updated v1 title"
        first_draft.write_text(json.dumps(first_replaced), encoding="utf-8")
        self.assertEqual(
            publish_board.main(
                [
                    "--board",
                    str(first_draft),
                    "--media",
                    str(img_a_v2),
                    str(img_b),
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                    "--replace",
                ]
            ),
            0,
        )
        self.assertEqual(fb_v1.read_text(encoding="utf-8"), fb_sentinel)
        self.assertEqual(
            hashlib.sha256(
                (dest / "sky-8c-v1" / "media" / "a.png").read_bytes()
            ).hexdigest(),
            sha_a_v2,
        )
        media_backups = list(scratch.glob("*/sky-8c-v1/media/a.png"))
        self.assertEqual(len(media_backups), 1)
        self.assertEqual(media_backups[0].read_bytes(), img_a_v1_bytes)
        manifests = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in scratch.glob("*/manifest.json")
        ]
        self.assertTrue(
            any("media/a.png" in m.get("media_backed_up", []) for m in manifests)
        )

        # Superseding board updates sky-8c-v1 status + superseded_by.
        second = sample_v2_board("sky-8c-v2")
        second["supersedes"] = ["sky-8c-v1"]
        second_draft = src_dir / "second.json"
        second_draft.write_text(json.dumps(second), encoding="utf-8")
        self.assertEqual(
            publish_board.main(
                [
                    "--board",
                    str(second_draft),
                    "--media",
                    str(img_a),
                    str(img_b),
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                ]
            ),
            0,
        )

        old_after = json.loads(
            (dest / "sky-8c-v1" / "board.json").read_text(encoding="utf-8")
        )
        self.assertEqual(old_after["status"], "superseded")
        self.assertIn("sky-8c-v2", old_after["superseded_by"])
        self.assertEqual(fb_v1.read_text(encoding="utf-8"), fb_sentinel)

        backups = list(scratch.glob("*/sky-8c-v1/board.json"))
        self.assertGreaterEqual(len(backups), 2)

    def test_set_status_and_dry_run(self) -> None:
        dest = self.tmp_path / "review_boards"
        scratch = self.tmp_path / "scratch"
        src_dir = self.tmp_path / "src"
        img_a, _ = write_png(src_dir / "a.png")
        img_b, _ = write_png(src_dir / "b.png")
        draft = src_dir / "board.json"
        draft.write_text(
            json.dumps(sample_v2_board("triage-01")), encoding="utf-8"
        )

        self.assertEqual(
            publish_board.main(
                [
                    "--board",
                    str(draft),
                    "--media",
                    str(img_a),
                    str(img_b),
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                    "--dry-run",
                ]
            ),
            0,
        )
        self.assertFalse(dest.exists())
        self.assertFalse(scratch.exists())

        self.assertEqual(
            publish_board.main(
                [
                    "--board",
                    str(draft),
                    "--media",
                    str(img_a),
                    str(img_b),
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                ]
            ),
            0,
        )
        self.assertEqual(
            publish_board.main(
                [
                    "--set-status",
                    "triage-01",
                    "stale_decided",
                    "--reason",
                    "Settled in decisions.org",
                    "--dest",
                    str(dest),
                    "--scratch-root",
                    str(scratch),
                ]
            ),
            0,
        )
        updated = json.loads(
            (dest / "triage-01" / "board.json").read_text(encoding="utf-8")
        )
        self.assertEqual(updated["status"], "stale_decided")
        self.assertEqual(updated["status_reason"], "Settled in decisions.org")

    def test_publish_rejects_schema_violations(self) -> None:
        dest = self.tmp_path / "review_boards"
        scratch = self.tmp_path / "scratch"
        src_dir = self.tmp_path / "src"
        img_a, _ = write_png(src_dir / "a.png")
        img_b, _ = write_png(src_dir / "b.png")

        mutators = [
            lambda b: b.update({"priority": "urgent"}),
            lambda b: b["questions"][0].update({"id": "BadUpper"}),
            lambda b: b["questions"].append(dict(b["questions"][0])),
            lambda b: b.update(
                {
                    "questions": [
                        {"id": f"q_{i}", "prompt": f"Q{i}", "kind": "yes_no"}
                        for i in range(13)
                    ]
                }
            ),
            lambda b: b["questions"][0].update(
                {
                    "options": [
                        {"id": f"o_{i}", "label": f"O{i}"} for i in range(13)
                    ]
                }
            ),
            lambda b: b["questions"][0]["options"][0].update({"media": 9}),
            lambda b: b["questions"][3].update({"min": 5, "max": 2}),
            lambda b: b["questions"][4].update({"default": "not-bool"}),
        ]

        for idx, mutate in enumerate(mutators):
            with self.subTest(case=idx):
                bad = sample_v2_board(f"bad-{idx:02d}")
                mutate(bad)
                draft = src_dir / f"bad_{idx}.json"
                draft.write_text(json.dumps(bad), encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()):
                    rc = publish_board.main(
                        [
                            "--board",
                            str(draft),
                            "--media",
                            str(img_a),
                            str(img_b),
                            "--dest",
                            str(dest),
                            "--scratch-root",
                            str(scratch),
                        ]
                    )
                self.assertEqual(rc, 1)
                self.assertFalse((dest / f"bad-{idx:02d}").exists())

    def test_collect_feedback_reads_v1_and_v2_and_advances_state(self) -> None:
        dest = self.tmp_path / "review_boards"
        state_file = self.tmp_path / "seen.json"

        b1 = dest / "board-v1"
        b1.mkdir(parents=True)
        (b1 / "feedback-board-v1.json").write_text(
            json.dumps(
                {
                    "schema": "yaze.review_board_feedback.v1",
                    "id": "board-v1",
                    "status": "looks_good",
                    "history": [
                        {
                            "at": "2026-11-17T10:00:00.250000+00:00",
                            "board_sha256": "a" * 64,
                            "decision": "looks_good",
                            "category": "general",
                            "comment": "Ship it",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        b2 = dest / "board-v2"
        b2.mkdir(parents=True)
        (b2 / "feedback-board-v2.json").write_text(
            json.dumps(
                {
                    "schema": "yaze.review_board_feedback.v2",
                    "id": "board-v2",
                    "status": "looks_good",
                    "answers": {
                        "cliff_style": {"value": "a"},
                        "pick": {"value": ["a", "c"], "other": "mix"},
                    },
                    "history": [
                        {
                            "at": "2026-11-17T11:30:00Z",
                            "board_sha256": "b" * 64,
                            "decision": "looks_good",
                            "category": "layout",
                            "comment": "Move bridge 2 tiles",
                            "answers": {
                                "cliff_style": {"value": "a"},
                                "pick": {"value": ["a", "c"], "other": "mix"},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = collect_feedback.main(
                [
                    "--dest",
                    str(dest),
                    "--state-file",
                    str(state_file),
                    "--json",
                    "--mark-seen",
                ]
            )
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual([r["id"] for r in out], ["board-v1", "board-v2"])
        self.assertEqual(out[1]["answers"]["cliff_style"], {"value": "a"})
        self.assertEqual(
            out[1]["answers"]["pick"], {"value": ["a", "c"], "other": "mix"}
        )
        self.assertTrue(state_file.is_file())

        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = collect_feedback.main(
                ["--dest", str(dest), "--state-file", str(state_file), "--json"]
            )
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(buf2.getvalue()), [])

        buf3 = io.StringIO()
        with contextlib.redirect_stdout(buf3):
            rc3 = collect_feedback.main(
                ["--dest", str(dest), "--since", "2026-11-17T10:30:00Z"]
            )
        self.assertEqual(rc3, 0)
        lines = buf3.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("board-v2\tdecision=looks_good\tanswers="))


if __name__ == "__main__":
    unittest.main()
