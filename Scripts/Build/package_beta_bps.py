#!/usr/bin/env python3
"""Formal Discord Feature Beta .bps Packager, Round-Trip Verifier & Bundle Generator.

Builds (in an isolated /tmp sandbox via authoring_bundle_build.py, NEVER touching
shared Roms/ or .yazeproj/rom) or accepts an already-built rev5 ROM, runs static
release gates, diffs against canonical Vanilla US ALTTP 1.0 using flips, performs
mandatory byte-exact round-trip verification (apply(vanilla, patch) == target),
and emits a complete release bundle:
  - oracle-of-secrets-<label>.bps
  - oracle-of-secrets-<label>-showcase.srm
  - oracle-of-secrets-<label>.manifest.json
  - oracle-of-secrets-<label>-discord.md

Usage:
  python3 Scripts/Build/package_beta_bps.py --label v0.9.0-beta1 --out-dir build/releases
  python3 Scripts/Build/package_beta_bps.py --rom /tmp/built.sfc --label dryrun --out-dir /tmp/out
"""
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_BUILD_DIR = str(ROOT / "Scripts" / "Build")
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

import generate_showcase_srm as showcase_srm  # noqa: E402

# Canonical Vanilla US ALTTP 1.0 (unheadered 1 MiB LoROM)
CANONICAL_VANILLA_PATH = Path.home() / "src/hobby/roms/Legend of Zelda, The - A Link to the Past (USA).sfc"
CANONICAL_VANILLA_SIZE = 1_048_576
CANONICAL_VANILLA_SHA256 = "66871d66be19ad2c34c927d6b14cd8eb6fc3181965b6e517cb361f7316009cfb"
CANONICAL_VANILLA_CRC32 = "777aac2f"

DEFAULT_YAZE_PROJECT = Path.home() / "Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/project.yaze"
DEFAULT_FLIPS_CANDIDATES = (
    Path.home() / ".local/bin/flips",
    Path("/usr/local/bin/flips"),
    Path("/opt/homebrew/bin/flips"),
)

# 11 active beta feature flags (matching live rev5 beta build receipt)
DEFAULT_BETA_ENABLE_FLAGS = (
    "d3_prison_sequence,"
    "d8_farore_graphics,"
    "glade_ambush,"
    "horse_crowd_charge,"
    "lyra_talkers,"
    "lyra_temple_zora,"
    "minecart_cart_shutters,"
    "ocarina_song_tint,"
    "ow_aux_extension,"
    "sky_overworld_graphics,"
    "sky_overworld_route"
)


def file_hashes(path: Path) -> tuple[int, str, str]:
    """Return (size_bytes, sha256_hex, crc32_hex_8char)."""
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    crc = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
    return len(data), sha, crc


def find_flips_bin(explicit: Path | None = None) -> Path:
    """Locate the flips binary (explicit > OOS_FLIPS_BIN > ~/.local/bin/flips > PATH)."""
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    if os.environ.get("OOS_FLIPS_BIN"):
        candidates.append(Path(os.environ["OOS_FLIPS_BIN"]).expanduser())
    candidates.extend(DEFAULT_FLIPS_CANDIDATES)
    on_path = shutil.which("flips")
    if on_path:
        candidates.append(Path(on_path))
    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    raise FileNotFoundError(
        "flips binary not found (checked ~/.local/bin/flips and PATH). "
        "Install flips or pass --flips <path>."
    )


def verify_vanilla_rom(vanilla_path: Path, *, allow_custom: bool = False) -> dict[str, Any]:
    """Assert canonical Vanilla US ALTTP 1.0 size, SHA-256, and CRC32."""
    if not vanilla_path.is_file():
        raise FileNotFoundError(f"Vanilla base ROM not found: {vanilla_path}")
    size, sha, crc = file_hashes(vanilla_path)
    is_canonical = (
        size == CANONICAL_VANILLA_SIZE
        and sha == CANONICAL_VANILLA_SHA256
        and crc == CANONICAL_VANILLA_CRC32
    )
    if not allow_custom and not is_canonical:
        raise ValueError(
            f"Vanilla base ROM failed canonical US ALTTP 1.0 check: {vanilla_path}\n"
            f"  Expected size={CANONICAL_VANILLA_SIZE} sha256={CANONICAL_VANILLA_SHA256} crc32={CANONICAL_VANILLA_CRC32}\n"
            f"  Actual   size={size} sha256={sha} crc32={crc}"
        )
    return {
        "path": str(vanilla_path),
        "size": size,
        "sha256": sha,
        "crc32": crc,
        "canonical_us_1_0": is_canonical,
    }


def git_metadata(repo_root: Path = ROOT) -> dict[str, Any]:
    """Capture current git HEAD, branch, and dirty flag for release manifest."""
    def _git(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else ""

    head = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    return {"head": head, "branch": branch, "dirty": dirty}


def run_static_gates(
    rom_path: Path,
    *,
    symbols_path: Path | None = None,
    require_symbols: bool = False,
    repo_root: Path = ROOT,
) -> tuple[bool, list[dict[str, Any]]]:
    """Run all 6 static release gates and return (all_passed, results)."""
    py = sys.executable
    gates_spec: list[tuple[str, list[str] | None, str]] = []

    if symbols_path is not None and symbols_path.is_file():
        gates_spec.append((
            "zscream_overlap",
            [py, str(repo_root / "Scripts/Build/check_zscream_overlap.py"), "--symbols", str(symbols_path)],
            "",
        ))
    elif require_symbols:
        gates_spec.append(("zscream_overlap", None, "Required .sym file missing"))
    else:
        gates_spec.append(("zscream_overlap", None, "No sibling .sym file provided; skipped"))

    gates_spec.extend([
        (
            "tile16_pins_exits",
            [py, str(repo_root / "Scripts/Build/check_tile16_pins.py"), "--rom", str(rom_path), "--check-exits"],
            "",
        ),
        (
            "overlay_tile16",
            [py, str(repo_root / "Scripts/Build/check_overlay_tile16.py"), "--rom", str(rom_path)],
            "",
        ),
        (
            "sheet_reveal_safety",
            [py, str(repo_root / "Scripts/Build/check_sheet_reveal_safety.py"), "--rom", str(rom_path)],
            "",
        ),
        (
            "sprite_sheet_compat",
            [py, str(repo_root / "Scripts/Build/check_sprite_sheet_compat.py"), "--rom", str(rom_path)],
            "",
        ),
        (
            "overworld_seams_special",
            [py, str(repo_root / "Scripts/Build/check_overworld_seams.py"), "--rom", str(rom_path), "--region", "special"],
            "",
        ),
    ])

    results: list[dict[str, Any]] = []
    all_ok = True
    for name, cmd, skip_reason in gates_spec:
        if cmd is None:
            status = "failed" if require_symbols else "skipped"
            if status == "failed":
                all_ok = False
            results.append({
                "name": name,
                "status": status,
                "exit_code": 1 if status == "failed" else 0,
                "summary": skip_reason,
                "command": [],
            })
            continue
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        combined = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
        summary = " | ".join(line.strip() for line in combined[:2] if line.strip())
        passed = proc.returncode == 0
        if not passed:
            all_ok = False
        results.append({
            "name": name,
            "status": "passed" if passed else "failed",
            "exit_code": proc.returncode,
            "summary": summary[:320],
            "command": cmd,
        })
    return all_ok, results


def create_and_verify_bps(
    flips_bin: Path,
    vanilla_path: Path,
    target_rom_path: Path,
    patch_out_path: Path,
) -> dict[str, Any]:
    """Create .bps via flips and strictly verify byte-exact round-trip SHA-256 parity."""
    patch_out_path.parent.mkdir(parents=True, exist_ok=True)
    create_cmd = [str(flips_bin), "--create", "--bps", str(vanilla_path), str(target_rom_path), str(patch_out_path)]
    proc = subprocess.run(create_cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not patch_out_path.is_file():
        raise RuntimeError(
            f"flips --create failed (rc={proc.returncode}): {(proc.stderr or proc.stdout).strip()}"
        )

    target_size, target_sha, target_crc = file_hashes(target_rom_path)
    patch_size, patch_sha, patch_crc = file_hashes(patch_out_path)

    with tempfile.TemporaryDirectory(prefix="oos_bps_rt_") as tmp:
        rt_rom = Path(tmp) / "roundtrip.sfc"
        apply_cmd = [str(flips_bin), "--apply", str(patch_out_path), str(vanilla_path), str(rt_rom)]
        ap_proc = subprocess.run(apply_cmd, capture_output=True, text=True)
        if ap_proc.returncode != 0 or not rt_rom.is_file():
            raise RuntimeError(
                f"flips --apply round-trip failed (rc={ap_proc.returncode}): "
                f"{(ap_proc.stderr or ap_proc.stdout).strip()}"
            )
        rt_size, rt_sha, rt_crc = file_hashes(rt_rom)

    if rt_size != target_size or rt_sha != target_sha:
        raise RuntimeError(
            "MANDATORY BPS ROUND-TRIP VERIFICATION FAILED!\n"
            f"  target   size={target_size} sha256={target_sha}\n"
            f"  applied  size={rt_size} sha256={rt_sha}"
        )

    return {
        "target_size": target_size,
        "target_sha256": target_sha,
        "target_crc32": target_crc,
        "patch_size": patch_size,
        "patch_sha256": patch_sha,
        "patch_crc32": patch_crc,
        "round_trip_verified": True,
        "round_trip_sha256": rt_sha,
        "round_trip_crc32": rt_crc,
    }


def _copy_working_tree_isolated(repo_root: Path, dest: Path) -> None:
    """Copy repo working tree into an isolated /tmp build root without Roms/ or .git/."""
    dest.mkdir(parents=True, exist_ok=True)
    skip_dirs = {".git", "Roms", "Backups", "build", ".cache", "__pycache__", "node_modules"}
    for item in repo_root.iterdir():
        if item.name in skip_dirs:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                symlinks=False,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        elif item.is_file():
            shutil.copy2(item, target)
    (dest / "Roms").mkdir(exist_ok=True)


def run_isolated_rev5_build(
    project_yaze: Path,
    *,
    sandbox_dir: Path,
    version: int = 168,
    enable_flags: str = DEFAULT_BETA_ENABLE_FLAGS,
    disable_flags: str = "",
    repo_root: Path = ROOT,
) -> tuple[Path, Path]:
    """Run an isolated rev5 beta build in sandbox_dir via authoring_bundle_build.py.

    NEVER modifies shared Roms/ or the live .yazeproj/rom (verifies source ROM
    SHA-256 before and after the build).
    Returns (built_rom_path, built_sym_path) inside sandbox_dir.
    """
    project_yaze = project_yaze.expanduser().resolve(strict=True)
    proj_src_dir = project_yaze.parent

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(project_yaze, encoding="utf-8")
    rom_rel = cfg.get("files", "rom_filename", fallback="rom").strip()
    orig_rom = (Path(rom_rel) if Path(rom_rel).is_absolute() else proj_src_dir / rom_rel).resolve(strict=True)
    _, before_sha, _ = file_hashes(orig_rom)

    src_dir = sandbox_dir / "source-native"
    _copy_working_tree_isolated(repo_root, src_dir)

    # Copy read-only ROM into sandbox_dir/rom (same parent as source-native so
    # authoring_bundle_build.py's manifest_owner namespace rule passes cleanly).
    sandbox_rom = sandbox_dir / "rom"
    shutil.copyfile(orig_rom, sandbox_rom)

    # Symlink read-only project support dirs/files
    for name in ("assets", "project", "transfer", "project.yaze.native-save.json"):
        s = proj_src_dir / name
        if s.exists():
            (sandbox_dir / name).symlink_to(s)
    (sandbox_dir / "backups").mkdir(exist_ok=True)

    # Rewrite copied project.yaze to bind exclusively to sandbox paths
    if not cfg.has_section("files"):
        cfg.add_section("files")
    if not cfg.has_section("build"):
        cfg.add_section("build")
    cfg.set("files", "rom_filename", "rom")
    cfg.set("files", "code_folder", "source-native")
    cfg.set("files", "output_folder", "source-native/Roms")
    cfg.set("files", "rom_backup_folder", "backups")
    cfg.set("files", "hack_manifest_file", "source-native/Roms/hack_manifest.json")
    cfg.set("build", "output_folder", "source-native/Roms")
    cfg.set("build", "build_target", f"source-native/Roms/oos{version}x.sfc")

    sandbox_project = sandbox_dir / "project.yaze"
    with sandbox_project.open("w", encoding="utf-8") as fh:
        cfg.write(fh, space_around_delimiters=False)

    # Strip any inherited YAZE_PROJECT_* / OOS_* env bindings so sandbox owns them
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith(("YAZE_PROJECT_", "OOS_BASE_ROM", "OOS_MANIFEST_", "OOS_BACKUP_ROOT"))
    }
    cmd = [
        sys.executable,
        str(src_dir / "Scripts/Build/authoring_bundle_build.py"),
        "--project",
        str(sandbox_project),
    ]
    if enable_flags:
        cmd.extend(["--enable", enable_flags])
    if disable_flags:
        cmd.extend(["--disable", disable_flags])

    proc = subprocess.run(cmd, cwd=sandbox_dir, env=env, check=False)

    _, after_sha, _ = file_hashes(orig_rom)
    if after_sha != before_sha:
        raise RuntimeError(f"Source project ROM mutated unexpectedly: {orig_rom}")

    if proc.returncode != 0:
        raise RuntimeError(f"Isolated rev5 authoring_bundle_build.py failed with rc={proc.returncode}")

    built_rom = src_dir / "Roms" / f"oos{version}x.sfc"
    built_sym = src_dir / "Roms" / f"oos{version}x.sym"
    if not built_rom.is_file():
        raise FileNotFoundError(f"Expected built ROM missing: {built_rom}")
    return built_rom, built_sym


def render_discord_draft(manifest: dict[str, Any]) -> str:
    """Generate a ready-to-review Discord Beta Announcement draft (never auto-posted)."""
    label = manifest["label"]
    patch_file = manifest["bps_patch"]["file"]
    patch_kb = manifest["bps_patch"]["size"] / 1024.0
    srm_file = manifest["showcase_srm"]["file"]
    vanilla = manifest["vanilla_base"]
    target = manifest["target_rom"]
    gates = manifest["gates"]
    passed_count = sum(1 for g in gates if g["status"] == "passed")
    skipped_count = sum(1 for g in gates if g["status"] == "skipped")

    lines = [
        f"# Oracle of Secrets — Feature Beta `{label}` (Discord Draft — Review Before Posting)",
        "",
        f"> **Patch file:** `{patch_file}` ({patch_kb:.1f} KiB, BPS format)",
        f"> **Optional Showcase Save:** `{srm_file}` (8 KiB SNES SRAM — 3 pre-built tour slots)",
        "",
        "## What's Inside This Feature Beta",
        "- **Kalyxo Overworld & Wayward Village:** Day/Night cycle (Song of Time), Village Dogs, Business Scrubs, X-button dual item bindings, Minish Cap-style Gust Jar, Masks & Magic Rings.",
        "- **Special Overworld & Lyra Sea:** Kalyxo Boat ferry (`Docks <-> Sea Zora Quay`), Zora Coast, Deku Grove, Goron Coast, Courage Island, Sky Islands, and Song of Soaring / Sky Soaring.",
        "- **Eon Abyss (Dark World):** GBC shield & room styling, Breach Portal (`DW $4B <-> LW $0B`), Twin Brothers (`$00F5`), and Endgame Finale pacing.",
        "- *Note:* This is a **Feature Beta** focused on gameplay systems, exploration, and overworld feel — story/dialogue stitching is still WIP in several later zones.",
        "",
        "## Required Base ROM (Do NOT share copyrighted ROMs)",
        "Patch **only** against an unheadered vanilla **US A Link to the Past (1.0)** ROM:",
        f"- **Expected Size:** `{vanilla['size']:,}` bytes (1 MiB, unheadered `.sfc`)",
        f"- **CRC32:** `{vanilla['crc32']}`",
        f"- **SHA-256:** `{vanilla['sha256']}`",
        "",
        "## How to Patch",
        "1. **Browser (easiest — RomPatcher.js):**",
        f"   - Open RomPatcher.js, select your clean US ALTTP 1.0 `.sfc` as **ROM file** and `{patch_file}` as **Patch file**, then click **Apply patch**.",
        "2. **Desktop (Flips):**",
        f"   - Run `flips --apply {patch_file} alttp_usa.sfc oracle-of-secrets-{label}.sfc` (or use the Flips GUI -> *Apply Patch*).",
        f"3. **Optional — Verify Patched Output SHA-256:** `{target['sha256']}` (CRC32 `{target['crc32']}`).",
        "",
        "## Optional Showcase Save (`" + srm_file + "`)",
        "Rename the `.srm` to match your patched `.sfc` filename (e.g. `oracle-of-secrets.srm`) to jump straight in, or start a fresh **New Game** on any slot:",
        "- **Slot 1 (`LINK`):** Light World Kalyxo & Full Kit — Wayward Village / Link's House spawn with Gust Jar (Y), Ocarina + all 6 songs (X), Garo Mask (R), all masks/bottles/rings, Master Sword + Red Mail + Mirror Shield, all Kalyxo soaring spots unlocked.",
        "- **Slot 2 (`LYRA`):** Special Overworld & Lyra Sea Tour — spawns outdoors in East Kalyxo with Ocarina (Y), Gust Jar (X), Zora Mask (R), Boat & Special/Sky Soaring ready immediately.",
        "- **Slot 3 (`ABYSS`):** Eon Abyss GBC Tour — Dark World spawn chooser outside Abyss Windmill (`$63`) with GBC Mirror Shield, Golden Sword, full kit, Breach Portal & Twin Brothers ready.",
        "",
        "## Release Integrity Receipt",
        f"- **BPS Round-Trip Verified:** `PASS` (`flips --apply` matches target ROM SHA-256 byte-for-byte)",
        f"- **Static Gates:** `{passed_count}` passed, `{skipped_count}` skipped, `0` failed",
        f"- **Git Commit:** `{manifest['git']['head'][:12]}` (`{manifest['git']['branch']}`)",
        "",
    ]
    return "\n".join(lines)


def package_beta_release(
    *,
    label: str,
    out_dir: Path,
    vanilla_path: Path = CANONICAL_VANILLA_PATH,
    rom_path: Path | None = None,
    symbols_path: Path | None = None,
    project_yaze: Path = DEFAULT_YAZE_PROJECT,
    version: int = 168,
    enable_flags: str = DEFAULT_BETA_ENABLE_FLAGS,
    disable_flags: str = "",
    flips_bin: Path | None = None,
    skip_gates: bool = False,
    allow_custom_vanilla: bool = False,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    """End-to-end beta BPS packaging pipeline returning the generated manifest."""
    resolved_flips = find_flips_bin(flips_bin)
    vanilla_info = verify_vanilla_rom(vanilla_path, allow_custom=allow_custom_vanilla)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"oracle-of-secrets-{label}"
    patch_out = out_dir / f"{stem}.bps"
    srm_out = out_dir / f"{stem}-showcase.srm"
    manifest_out = out_dir / f"{stem}.manifest.json"
    discord_out = out_dir / f"{stem}-discord.md"

    with tempfile.TemporaryDirectory(prefix="oos_beta_pkg_") as sandbox_tmp:
        sandbox_dir = Path(sandbox_tmp)
        built_in_sandbox = rom_path is None
        if rom_path is not None:
            target_rom = rom_path.expanduser().resolve(strict=True)
            sym_cand = symbols_path.expanduser().resolve() if symbols_path else target_rom.with_suffix(".sym")
            target_sym = sym_cand if sym_cand.is_file() else None
        else:
            target_rom, target_sym = run_isolated_rev5_build(
                project_yaze,
                sandbox_dir=sandbox_dir,
                version=version,
                enable_flags=enable_flags,
                disable_flags=disable_flags,
                repo_root=repo_root,
            )

        if skip_gates:
            gate_results: list[dict[str, Any]] = []
        else:
            gates_ok, gate_results = run_static_gates(
                target_rom,
                symbols_path=target_sym,
                require_symbols=built_in_sandbox or symbols_path is not None,
                repo_root=repo_root,
            )
            if not gates_ok:
                failed = [g["name"] for g in gate_results if g["status"] == "failed"]
                raise RuntimeError(f"Release gates failed ({', '.join(failed)}); refusing to package .bps")

        bps_info = create_and_verify_bps(resolved_flips, vanilla_path, target_rom, patch_out)

    # Generate and validate Showcase .srm
    srm_bytes = showcase_srm.build_showcase_srm()
    srm_out.write_bytes(srm_bytes)
    srm_meta = showcase_srm.validate_showcase_srm(srm_bytes)
    srm_meta["file"] = srm_out.name

    manifest: dict[str, Any] = {
        "schema_version": 2,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "label": label,
        "version": version,
        "git": git_metadata(repo_root),
        "flips_bin": str(resolved_flips),
        "build_mode": "isolated_rev5_authoring_bundle" if rom_path is None else "prebuilt_rom",
        "beta_enable_flags": enable_flags.split(",") if enable_flags else [],
        "beta_disable_flags": disable_flags.split(",") if disable_flags else [],
        "vanilla_base": vanilla_info,
        "target_rom": {
            "source_path": str(rom_path) if rom_path else f"isolated:oos{version}x.sfc",
            "size": bps_info["target_size"],
            "sha256": bps_info["target_sha256"],
            "crc32": bps_info["target_crc32"],
        },
        "bps_patch": {
            "file": patch_out.name,
            "size": bps_info["patch_size"],
            "sha256": bps_info["patch_sha256"],
            "crc32": bps_info["patch_crc32"],
        },
        "round_trip_verified": bps_info["round_trip_verified"],
        "round_trip_sha256": bps_info["round_trip_sha256"],
        "round_trip_crc32": bps_info["round_trip_crc32"],
        "showcase_srm": srm_meta,
        "gates": gate_results,
        "discord_draft_file": discord_out.name,
    }

    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    discord_out.write_text(render_discord_draft(manifest), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--label", required=True, help="Release label, e.g. v0.9.0-beta1")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "build" / "releases", help="Output release bundle dir")
    ap.add_argument(
        "--vanilla",
        type=Path,
        default=Path(os.environ.get("OOS_VANILLA_ROM", str(CANONICAL_VANILLA_PATH))),
        help="Path to canonical vanilla US ALTTP 1.0 .sfc",
    )
    ap.add_argument("--rom", type=Path, help="Optional already-built rev5 ROM (skips isolated build)")
    ap.add_argument("--symbols", type=Path, help="Optional .sym file for check_zscream_overlap.py")
    ap.add_argument("--project", type=Path, default=DEFAULT_YAZE_PROJECT, help="Path to .yazeproj/project.yaze")
    ap.add_argument("--version", type=int, default=168, help="Numeric ROM version (default: 168)")
    ap.add_argument("--enable", default=DEFAULT_BETA_ENABLE_FLAGS, help="CSV feature flags to enable")
    ap.add_argument("--disable", default="", help="CSV feature flags to disable")
    ap.add_argument("--flips", type=Path, help="Explicit path to flips binary")
    ap.add_argument("--skip-gates", action="store_true", help="Skip static release gates (testing only)")
    ap.add_argument(
        "--allow-custom-vanilla",
        action="store_true",
        help="Bypass canonical US ALTTP 1.0 hash check (synthetic tests only)",
    )
    args = ap.parse_args(argv)

    try:
        manifest = package_beta_release(
            label=args.label,
            out_dir=args.out_dir,
            vanilla_path=args.vanilla,
            rom_path=args.rom,
            symbols_path=args.symbols,
            project_yaze=args.project,
            version=args.version,
            enable_flags=args.enable,
            disable_flags=args.disable,
            flips_bin=args.flips,
            skip_gates=args.skip_gates,
            allow_custom_vanilla=args.allow_custom_vanilla,
        )
    except Exception as exc:
        print(f"[-] Beta BPS packaging failed: {exc}", file=sys.stderr)
        return 1

    stem = f"oracle-of-secrets-{args.label}"
    bps = manifest["bps_patch"]
    print(f"[+] Packaged Oracle of Secrets beta bundle in {args.out_dir}:")
    print(f"    BPS Patch    : {bps['file']} ({bps['size']:,} bytes / {bps['size'] / 1024:.1f} KiB) sha256={bps['sha256'][:16]}...")
    print(f"    Round-Trip   : VERIFIED byte-exact SHA-256={manifest['round_trip_sha256']}")
    print(f"    Showcase SRM : {manifest['showcase_srm']['file']} ({manifest['showcase_srm']['size']} bytes)")
    print(f"    Manifest     : {stem}.manifest.json")
    print(f"    Discord Draft: {manifest['discord_draft_file']}")
    for g in manifest["gates"]:
        print(f"    Gate [{g['status'].upper():<7}] {g['name']}: {g['summary'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
