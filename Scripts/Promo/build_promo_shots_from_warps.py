#!/usr/bin/env python3
"""Build promo shots.json from Data/debug/warps.json with registry-correct labels.

Uses each warpable area's official `name` + landing coords — never invents
vanilla ALTTP place names for OoS map IDs. Lyra Sea ($A0+) is out of scope
here (no exit-table warps); add those separately with extents.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WARPS = ROOT / "Data" / "debug" / "warps.json"
DEFAULT_OUT = ROOT / "Data" / "debug" / "promo_shots" / "ow_warp_shots.json"

VIEW_W, VIEW_H = 256, 224

# area -> stable slug (labels still come from warps.json `name`)
CURATED: dict[str, str] = {
    "0x05": "snow_mountain_east",
    "0x0B": "kalyxo_castle",
    "0x0E": "hall_of_secrets",
    "0x10": "mushroom_grotto_ow",
    "0x18": "toadstool_woods_log",
    "0x1E": "sunken_city_zora",
    "0x23": "wayward_village",
    "0x25": "village_road",
    "0x2E": "city_road",
    "0x2F": "tail_palace",
    "0x32": "secret_beach",
    "0x33": "loom_beach",
    "0x36": "garo_desert",
    "0x38": "dragon_ship",
    "0x40": "temporal_gate_abyss",
    # 0x4B Lupo Mountain: warps.json exit stale on current ROM ("no longer matches room $084")
    "0x50": "shrine_courage",
}

# Story gear/flags: checkpoints.json id applied (warp=False) before staging.
AREA_CHECKPOINT: dict[str, str] = {
    "0x05": "d5-entrance",
    "0x0B": "d3-entrance",
    "0x0E": "kalyxo-return",
    "0x10": "d1-entrance",
    "0x18": "d1-entrance",
    "0x1E": "d4-entrance",
    "0x23": "village-impa",
    "0x25": "village-impa",
    "0x2E": "d2-entrance",
    "0x2F": "d2-entrance",
    "0x32": "loom-beach",
    "0x33": "loom-beach",
    "0x36": "d6-entrance",
    "0x38": "d7-entrance",
    "0x40": "abyss-arrival",
    "0x50": "abyss-owl",
}


def _hx(v: object) -> int:
    if isinstance(v, str):
        return int(v, 16)
    return int(v)  # type: ignore[arg-type]


def _slug(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:48]


def build_shots(warps_path: Path) -> dict:
    data = json.loads(warps_path.read_text())
    by_area = {a["area"]: a for a in data.get("areas", [])}
    shots: list[dict] = []
    missing: list[str] = []

    for area, slug in CURATED.items():
        entry = by_area.get(area)
        if not entry:
            missing.append(area)
            continue
        lx, ly = _hx(entry["x"]), _hx(entry["y"])
        cx, cy = max(0, lx - 120), max(0, ly - 100)
        pad = 64
        ox = max(0, (min(cx, lx) - pad) // 16 * 16)
        oy = max(0, (min(cy, ly) - pad) // 16 * 16)
        ex = max(cx + VIEW_W, lx + 64) + pad
        ey = max(cy + VIEW_H + 2, ly + 64) + pad
        width = max(VIEW_W, (ex - ox + 15) // 16 * 16)
        height = max(VIEW_H + 2, (ey - oy + 15) // 16 * 16)
        landing = entry.get("landing") or ""
        label = entry.get("name") or f"Area {area}"
        checkpoint = AREA_CHECKPOINT.get(area, "")
        base = {
            "area": area,
            "label": label,
            "landing": landing,
            "checkpoint": checkpoint,
            "extent": {
                "origin_x": ox,
                "origin_y": oy,
                "width": width,
                "height": height,
            },
            "actors": [],
        }
        shots.append(
            {
                **base,
                "name": slug,
                "note": (
                    f"{label} — {landing} (warps.json {area}; "
                    f"checkpoint={checkpoint or 'none'})"
                ),
                "camera": {"x": cx, "y": cy},
                "link": {"x": lx, "y": ly, "facing": 2},
            }
        )
        # Short east pan twin for a few hero maps
        if area in ("0x23", "0x33", "0x0B"):
            shots.append(
                {
                    **base,
                    "name": f"{slug}_east_pan",
                    "note": f"{label} east pan twin (checkpoint={checkpoint or 'none'})",
                    "extent": {
                        "origin_x": ox,
                        "origin_y": oy,
                        "width": width + 128,
                        "height": height,
                    },
                    "camera": {"x": cx + 96, "y": cy},
                    "link": {"x": lx + 80, "y": ly, "facing": 3},
                }
            )

    return {
        "version": 1,
        "comment": (
            "Generated from warps.json area names/landings + checkpoints.json "
            "story gear. Do not rename areas to vanilla ALTTP places. "
            "Lyra Sea ($A0-$BF) is special-overworld — not in this exit-table set. "
            "Director StageResolver applies checkpoint (warp=False) then warp-area; "
            "live landing + walkable snap replace doorway exit pixels."
        ),
        "source": str(warps_path.relative_to(ROOT)),
        "shots": shots,
        "missing_areas": missing,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--warps", type=Path, default=DEFAULT_WARPS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    payload = build_shots(args.warps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                "ok": True,
                "out": str(args.out),
                "shot_count": len(payload["shots"]),
                "labels": [
                    {"name": s["name"], "area": s["area"], "label": s["label"]}
                    for s in payload["shots"]
                ],
                "missing_areas": payload["missing_areas"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
