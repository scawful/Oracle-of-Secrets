#!/usr/bin/env python3
"""Dungeon render-review sheet: entrance-bound graphics, before/after, contacts, planes.

Read-only. Renders through the existing z3ed `dungeon-render` (never a second
renderer) with the graphics of the entrance the player uses, or accepts
pre-rendered PNGs (for private RAM-edit previews) and binds them to a ROM by
re-rendering the base and requiring a pixel match. Writes `sheet.png`,
`manifest.json` and the raw renders into --out. See README_render_review_sheet.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

DEFAULT_Z3ED = Path(
    "/Users/scawful/src/hobby/yaze-worktrees/save-workflow-verify-20261105"
    "/build/presets/mac-ai/bin/Debug/z3ed")
ROLES = ("lower", "upper", "mouth", "arrival")
ROLE_COLORS = {"lower": (40, 120, 255), "upper": (255, 140, 0),
               "mouth": (230, 30, 200), "arrival": (0, 200, 90)}
TILE = 8
ROOM_PX = 512
CONTACT_TILES = 8          # 64 px window, drawn at 2x
LUMA_THRESHOLD = 20.0      # a-priori; not tuned on any control
NATIVE_HUD_ROWS = 48       # native frames: skip HUD rows when matching
NATIVE_SEARCH = 24         # +/- px around the camera guess
PIXEL_TOLERANCE = 24       # per-pixel luminance difference counted as a match


class ReviewError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_hex(text: str) -> int:
    return int(text, 16) if text.lower().startswith("0x") else int(text, 16)


def parse_point(spec: str) -> tuple[str, int, int, str]:
    """`name:x,y[:note]` in 8x8 tile units of the 512x512 room image."""
    parts = spec.split(":", 2)
    if len(parts) < 2:
        raise ReviewError(f"bad point {spec!r}; want name:x,y[:note]")
    x, y = (int(v) for v in parts[1].split(","))
    if not (0 <= x < 64 and 0 <= y < 64):
        raise ReviewError(f"{spec!r}: tile coordinates must be 0..63")
    return parts[0], x, y, parts[2] if len(parts) == 3 else ""


def font(size: int):
    for candidate in ("/System/Library/Fonts/Menlo.ttc",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------- z3ed --

def z3ed_json(z3ed: Path, args: list[str]) -> dict:
    proc = subprocess.run([str(z3ed), *args, "--format=json"],
                          capture_output=True, text=True)
    text = proc.stdout
    if proc.returncode != 0 or "{" not in text:
        raise ReviewError(f"z3ed {' '.join(args)} failed rc={proc.returncode}: "
                          f"{(proc.stderr or text).strip()[:300]}")
    return json.loads(text[text.index("{"):])


def entrance_info(z3ed: Path, rom: Path, entrance: int) -> dict:
    return z3ed_json(z3ed, ["dungeon-get-entrance", f"--rom={rom}",
                            f"--entrance=0x{entrance:02X}"])


def render(z3ed: Path, rom: Path, room: int, out_png: Path, *,
           entrance: int | None, entrance_room: int | None,
           project_context: Path | None) -> dict:
    """Render one room. Direct entrances use --entrance, others --graphics-entrance."""
    args = ["dungeon-render", f"--rom={rom}", f"--room=0x{room:02X}",
            f"--output={out_png}"]
    if entrance is None:
        mode = "header_default"
    elif entrance_room == room:
        mode = "direct_entrance"
        args.append(f"--entrance=0x{entrance:02X}")
    else:
        mode = "inherited_entrance"
        args.append(f"--graphics-entrance=0x{entrance:02X}")
    if project_context:
        args.append(f"--project-context={project_context}")
    data = z3ed_json(z3ed, args)
    return {"mode": mode, "png": str(out_png), "png_sha256": sha256(out_png),
            "rom": str(rom), "rom_sha256": sha256(rom),
            "main_blockset": data.get("main_blockset"),
            "entrance_id": data.get("entrance_id") or data.get("graphics_entrance_id"),
            "slots": [s.get("sheet") for s in data.get("slots", [])]}


def pixel_diff(a: Image.Image, b: Image.Image) -> int:
    if a.size != b.size:
        return a.size[0] * a.size[1]
    mask = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L")
    return mask.point(lambda v: 255 if v else 0).histogram()[255]


# ------------------------------------------------------------ analysis --

def mean_luma(img: Image.Image, tx: int, ty: int, radius: int = 1) -> float:
    box = (max(0, (tx - radius) * TILE), max(0, (ty - radius) * TILE),
           min(img.width, (tx + radius + 1) * TILE), min(img.height, (ty + radius + 1) * TILE))
    hist = img.crop(box).convert("L").histogram()
    total = sum(hist)
    return sum(i * n for i, n in enumerate(hist)) / total if total else 0.0


def tile_layers(tiles: dict | None, tx: int, ty: int) -> dict | None:
    if not tiles:
        return None
    i = ty * 64 + tx
    attrs = tiles.get("attributes", [])
    return {"bg1_object": tiles["bg1_objects"][i], "bg2_object": tiles["bg2_objects"][i],
            "bg1_collision": attrs[i] if len(attrs) > i else None,
            "bg2_collision": attrs[4096 + i] if len(attrs) > 4096 + i else None}


def height_metric(after: Image.Image, tiles: dict | None, callouts: dict) -> dict:
    """Static heuristic only: luminance step between lower and upper callouts."""
    if "lower" not in callouts or "upper" not in callouts:
        return {"status": "NOT_MEASURED", "reason": "needs lower and upper callouts"}
    lo, up = callouts["lower"], callouts["upper"]
    l1, l2 = mean_luma(after, lo[0], lo[1]), mean_luma(after, up[0], up[1])
    delta = abs(l1 - l2)
    lay_lo, lay_up = tile_layers(tiles, *lo[:2]), tile_layers(tiles, *up[:2])
    planes_differ = None
    if lay_lo and lay_up:
        planes_differ = (lay_lo["bg1_collision"], lay_lo["bg2_collision"]) != \
                        (lay_up["bg1_collision"], lay_up["bg2_collision"])
    verdict = "LUMA_STEP_PRESENT" if delta >= LUMA_THRESHOLD else "LUMA_STEP_ABSENT"
    sentence = (f"Auto metric: lower {lo[:2]} vs upper {up[:2]} mean luminance differs by "
                f"{delta:.1f} (threshold {LUMA_THRESHOLD:.0f}) -> {verdict}"
                + ("" if planes_differ is None else
                   f"; collision planes {'differ' if planes_differ else 'match'}") + ".")
    return {"status": verdict, "luma_lower": round(l1, 1), "luma_upper": round(l2, 1),
            "delta": round(delta, 1), "threshold": LUMA_THRESHOLD,
            "layers_lower": lay_lo, "layers_upper": lay_up,
            "collision_planes_differ": planes_differ, "sentence": sentence}


def align_native(native: Image.Image, render_img: Image.Image, guess: tuple[int, int],
                 search: int = NATIVE_SEARCH) -> dict:
    """Best offset of the native 256x224 frame inside the 512x512 render (HUD rows skipped)."""
    nat = native.convert("L").crop((0, NATIVE_HUD_ROWS, native.width, native.height))
    ren = render_img.convert("L")
    best = None
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            x, y = guess[0] + dx, guess[1] + dy + NATIVE_HUD_ROWS
            if x < 0 or y < 0 or x + nat.width > ren.width or y + nat.height > ren.height:
                continue
            diff = ImageChops.difference(nat, ren.crop((x, y, x + nat.width, y + nat.height)))
            bad = sum(diff.point(lambda v: 255 if v > PIXEL_TOLERANCE else 0).histogram()[255:])
            if best is None or bad < best[0]:
                best = (bad, x, y - NATIVE_HUD_ROWS)
    if best is None:
        raise ReviewError("native frame does not fit inside the render near the camera guess")
    total = nat.width * nat.height
    return {"x": best[1], "y": best[2], "match": round(1 - best[0] / total, 4)}


# -------------------------------------------------------------- drawing --

def annotate(img: Image.Image, callouts: dict, notes: dict) -> Image.Image:
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    f = font(11)
    for role, (tx, ty, _) in callouts.items():
        cx, cy = tx * TILE + 4, ty * TILE + 4
        color = ROLE_COLORS.get(role, (255, 255, 0))
        draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), outline=color, width=3)
        label = role + (f": {notes[role]}" if notes.get(role) else "")
        tw = draw.textlength(label, font=f)
        lx = min(max(2, cx + 16), out.width - tw - 4)
        draw.rectangle((lx - 2, cy - 8, lx + tw + 2, cy + 7), fill=(0, 0, 0))
        draw.text((lx, cy - 7), label, fill=color, font=f)
    return out


def contact_crop(img: Image.Image, tx: int, ty: int) -> Image.Image:
    """2x crop around a tile; a thin crosshair marks the contact tile."""
    half = CONTACT_TILES * TILE // 2
    cx, cy = tx * TILE + 4, ty * TILE + 4
    box = (max(0, cx - half), max(0, cy - half), min(img.width, cx + half), min(img.height, cy + half))
    crop = img.convert("RGB").crop(box)
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST)
    draw = ImageDraw.Draw(crop)
    mx, my = (cx - box[0]) * 2, (cy - box[1]) * 2
    draw.rectangle((mx - 9, my - 9, mx + 8, my + 8), outline=(255, 255, 0))
    return crop


def plane_view(img: Image.Image, tiles: dict, layer: int) -> Image.Image:
    """Derived view: full colour where this BG has an object tile, hatched where its collision != 0."""
    base = img.convert("RGB")
    out = Image.blend(base, Image.new("RGB", base.size, (0, 0, 0)), 0.65)
    draw = ImageDraw.Draw(out)
    objects = tiles[f"bg{layer}_objects"]
    attrs = tiles.get("attributes", [])
    offset = 0 if layer == 1 else 4096
    tint = (255, 150, 40) if layer == 1 else (60, 200, 255)
    for i in range(4096):
        x, y = (i % 64) * TILE, (i // 64) * TILE
        if objects[i]:
            out.paste(base.crop((x, y, x + TILE, y + TILE)), (x, y))
        if len(attrs) > offset + i and attrs[offset + i]:
            draw.line((x, y + TILE - 1, x + TILE - 1, y), fill=tint)
    return out


def labelled(img: Image.Image, title: str) -> Image.Image:
    f = font(13)
    out = Image.new("RGB", (img.width, img.height + 20), (24, 24, 28))
    ImageDraw.Draw(out).text((4, 3), title, fill=(235, 235, 235), font=f)
    out.paste(img.convert("RGB"), (0, 20))
    return out


def compose(rows: list[list[Image.Image]], header: list[str], footer: list[str]) -> Image.Image:
    gap = 10
    row_imgs = []
    for row in rows:
        w = sum(i.width for i in row) + gap * (len(row) - 1)
        h = max(i.height for i in row)
        canvas = Image.new("RGB", (w, h), (24, 24, 28))
        x = 0
        for i in row:
            canvas.paste(i, (x, 0))
            x += i.width + gap
        row_imgs.append(canvas)
    f = font(14)
    width = max(r.width for r in row_imgs) + 2 * gap
    text_h = 20 * (len(header) + len(footer)) + 2 * gap
    sheet = Image.new("RGB", (width, sum(r.height for r in row_imgs) + gap * (len(row_imgs) + 1) + text_h),
                      (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    y = gap
    for line in header:
        draw.text((gap, y), line, fill=(255, 255, 255), font=f)
        y += 20
    y += gap
    for r in row_imgs:
        sheet.paste(r, (gap, y))
        y += r.height + gap
    for line in footer:
        draw.text((gap, y), line, fill=(255, 230, 120), font=f)
        y += 20
    return sheet


def wrap(lines: list[str], width_px: int, char_px: int = 9) -> list[str]:
    cols = max(40, width_px // char_px)
    out = []
    for line in lines:
        while len(line) > cols:
            cut = line.rfind(" ", 0, cols)
            cut = cut if cut > 0 else cols
            out.append(line[:cut])
            line = "    " + line[cut:].lstrip()
        out.append(line)
    return out


# ---------------------------------------------------------------- main --

def build(args: argparse.Namespace) -> dict:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    room = parse_hex(args.room)
    z3ed = Path(args.z3ed)
    entrance = parse_hex(args.graphics_entrance) if args.graphics_entrance else None
    manifest: dict = {"schema_version": 1, "room": f"0x{room:03X}", "title": args.title,
                      "limits": "Static render review only; no ROM/project writes; not a gameplay proof."}
    needs_z3ed = args.rom is not None
    if needs_z3ed:
        manifest["z3ed"] = {"path": str(z3ed), "sha256": sha256(z3ed)}
    if args.project_context:
        manifest["project_context"] = {"path": args.project_context,
                                       "sha256": sha256(Path(args.project_context))}
    ent = None
    if entrance is not None:
        if not args.rom:
            raise ReviewError("--graphics-entrance needs --rom to bind the entrance")
        ent = entrance_info(z3ed, Path(args.rom), entrance)
        manifest["graphics_entrance"] = {
            "id": f"0x{entrance:02X}", "room": ent.get("room_id"),
            "blockset": ent.get("properties", {}).get("blockset"),
            "dungeon_id": ent.get("properties", {}).get("dungeon_id"),
            "camera": ent.get("camera")}
    ent_room = int(ent["room_id"], 16) if ent else None
    pc = Path(args.project_context) if args.project_context else None

    def z_render(rom: str, name: str, use_entrance: bool) -> tuple[Image.Image, dict]:
        png = out / f"{name}.png"
        info = render(z3ed, Path(rom), room, png, entrance=entrance if use_entrance else None,
                      entrance_room=ent_room, project_context=pc)
        return Image.open(png).convert("RGB"), info

    def given(png: str, tiles: str | None) -> tuple[Image.Image, dict, dict | None]:
        info = {"mode": "prerendered", "png": png, "png_sha256": sha256(Path(png))}
        t = None
        if tiles:
            info.update(tiles=tiles, tiles_sha256=sha256(Path(tiles)))
            t = json.loads(Path(tiles).read_text())
        return Image.open(png).convert("RGB"), info, t

    after_tiles = before_tiles = None
    if args.after_png:
        after, after_info, after_tiles = given(args.after_png, args.after_tiles)
    elif args.rom:
        after, after_info = z_render(args.rom, "after", True)
    else:
        raise ReviewError("need --after-png or --rom")
    if args.before_png:
        before, before_info, before_tiles = given(args.before_png, args.before_tiles)
    elif args.before_header:
        if not args.rom:
            raise ReviewError("--before-header needs --rom")
        before, before_info = z_render(args.rom, "before-header", False)
    elif args.before_rom:
        before, before_info = z_render(args.before_rom, "before", True)
    else:
        before, before_info = None, None
    manifest["after"], manifest["before"] = after_info, before_info

    # Bind a pre-rendered image to the ROM: the z3ed render with the chosen entrance must match it.
    if args.bind and args.rom:
        target = {"before": (before, before_info), "after": (after, after_info)}[args.bind]
        if target[0] is None or target[1]["mode"] != "prerendered":
            raise ReviewError(f"--bind {args.bind} needs that image supplied as a PNG")
        bound, bound_info = z_render(args.rom, f"bind-{args.bind}", entrance is not None)
        target[1]["main_blockset"] = bound_info["main_blockset"]
        diff = pixel_diff(bound, target[0])
        manifest["graphics_binding"] = {"image": args.bind, "z3ed_render": bound_info,
                                        "differing_pixels": diff, "status": "BOUND" if diff == 0 else "UNBOUND"}
    elif after_info["mode"] == "prerendered":
        manifest["graphics_binding"] = {"status": "UNBOUND",
                                        "reason": "pre-rendered images were not re-rendered against a ROM"}
    else:
        manifest["graphics_binding"] = {"status": "BOUND", "reason": "rendered directly by z3ed"}

    callouts, notes = {}, {}
    for spec in args.callout:
        role, x, y, note = parse_point(spec)
        if role not in ROLES:
            raise ReviewError(f"callout role {role!r}; use one of {ROLES}")
        callouts[role], notes[role] = (x, y, note), note
    contacts = [parse_point(s) for s in args.contact]
    manifest["callouts"] = {r: {"tile": [v[0], v[1]], "note": v[2]} for r, v in callouts.items()}
    manifest["missing_callouts"] = [r for r in ROLES if r not in callouts]
    manifest["contacts"] = [{"name": n, "tile": [x, y], "note": note} for n, x, y, note in contacts]

    rows = []
    top = []
    if before is not None:
        top.append(labelled(before, f"BEFORE 1x  [{before_info['mode']}]"))
    top.append(labelled(annotate(after, callouts, notes), f"AFTER 1x  [{after_info['mode']}]"))
    rows.append(top)
    for name, x, y, note in contacts:
        pair = []
        if before is not None:
            pair.append(labelled(contact_crop(before, x, y), f"{name} before"))
        pair.append(labelled(contact_crop(after, x, y), f"{name} after"))
        rows.append(pair)

    tiles = after_tiles
    if tiles and not args.no_planes:
        rows.append([labelled(plane_view(after, tiles, 1), "BG1 plane (derived: object tiles lit, collision hatched)"),
                     labelled(plane_view(after, tiles, 2), "BG2 plane (derived: object tiles lit, collision hatched)")])
        manifest["bg_views"] = {"available": True, "method": "derived from .tiles.json object words and "
                                "per-layer collision; not a per-layer pixel render"}
    else:
        manifest["bg_views"] = {"available": False, "reason": "no .tiles.json for the after image; "
                                "z3ed dungeon-render exposes no per-layer output"}

    if args.native:
        native = Image.open(args.native).convert("RGB")
        if args.native_origin:
            guess = tuple(int(v) for v in args.native_origin.split(","))
        elif ent and ent_room == room:
            cam = ent["camera"]
            guess = (cam["x"] - (room & 0xF) * ROOM_PX, cam["y"] - (room >> 4) * ROOM_PX)
        else:
            raise ReviewError("--native needs --native-origin when the entrance is not direct")
        result = {"png": args.native, "png_sha256": sha256(Path(args.native)), "camera_guess": list(guess)}
        native_row = [labelled(native, "NATIVE frame")]
        for name, img in (("after", after), ("before", before)):
            if img is None:
                continue
            fit = align_native(native, img, guess)
            result[name] = fit
            crop = img.crop((fit["x"], fit["y"], fit["x"] + native.width, fit["y"] + native.height))
            native_row.append(labelled(crop, f"{name} @native {fit['match']:.1%}"))
        manifest["native"] = result
        rows.append(native_row)

    metric = height_metric(after, tiles, {r: (v[0], v[1]) for r, v in callouts.items()})
    manifest["auto_check"] = metric
    manifest["self_check"] = args.self_check or "PENDING: reviewer has not looked at this sheet yet."
    g = manifest.get("graphics_entrance")
    header = [args.title or f"Room 0x{room:03X} render review",
              ("graphics: entrance " + g["id"] + f" -> room {g['room']}, blockset {g['blockset']}"
               if g else "graphics: header default (no entrance given)")
              + f"  |  rendered main {after_info.get('main_blockset') or manifest['graphics_binding'].get('z3ed_render', {}).get('main_blockset', 'n/a')}"
              + f"  |  binding {manifest['graphics_binding']['status']}"]
    footer = []
    if metric.get("sentence"):
        footer.append(metric["sentence"])
    footer.append("Self-check: " + manifest["self_check"])
    if manifest["missing_callouts"] and callouts:
        footer.append("Missing callouts: " + ", ".join(manifest["missing_callouts"]))
    width = 20 + sum(i.width for i in top) + 10 * (len(top) - 1)
    sheet = compose(rows, header, wrap(footer, width))
    sheet_path = out / "sheet.png"
    sheet.save(sheet_path)
    manifest["sheet"] = {"png": str(sheet_path), "sha256": sha256(sheet_path)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--room", required=True, help="room id, hex")
    p.add_argument("--out", required=True, help="output directory (sheet.png, manifest.json)")
    p.add_argument("--rom", help="ROM read by z3ed (never written)")
    p.add_argument("--z3ed", default=os.environ.get("YAZE_Z3ED", str(DEFAULT_Z3ED)))
    p.add_argument("--project-context", help="read-only .yaze context passed to z3ed")
    p.add_argument("--graphics-entrance", help="entrance the player uses, hex; direct -> --entrance, "
                   "other room -> --graphics-entrance")
    p.add_argument("--after-png"), p.add_argument("--after-tiles")
    p.add_argument("--before-png"), p.add_argument("--before-tiles")
    p.add_argument("--before-rom", help="render BEFORE from this ROM with the same entrance")
    p.add_argument("--before-header", action="store_true",
                   help="BEFORE = same ROM rendered with header/default graphics (wrong-graphics control)")
    p.add_argument("--bind", choices=("before", "after"),
                   help="re-render this supplied PNG's room from --rom and require a pixel match")
    p.add_argument("--callout", action="append", default=[], help="role:x,y[:note], role in " + ",".join(ROLES))
    p.add_argument("--contact", action="append", default=[], help="name:x,y[:note]; 2x crop around tile")
    p.add_argument("--native", help="native 256x224 frame to align against the renders")
    p.add_argument("--native-origin", help="room-local px x,y of the native frame's top-left (guess)")
    p.add_argument("--no-planes", action="store_true")
    p.add_argument("--title")
    p.add_argument("--self-check", help="one sentence: is the height change visible? (after looking)")
    args = p.parse_args(argv)
    try:
        manifest = build(args)
    except ReviewError as error:
        print(f"render_review_sheet: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"sheet": manifest["sheet"]["png"], "binding": manifest["graphics_binding"]["status"],
                      "auto_check": manifest["auto_check"].get("status"),
                      "native": {k: v for k, v in manifest.get("native", {}).items() if k in ("after", "before")}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
