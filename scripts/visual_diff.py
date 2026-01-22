#!/usr/bin/env python3
"""
Visual Diff Pipeline for Oracle of Secrets

Compares screenshots against baselines for visual regression testing.

Features:
- Pixel-by-pixel comparison with threshold tolerance
- Structural similarity (SSIM-like) scoring
- Diff image generation highlighting changes
- Perceptual hash for quick similarity checks
- Integration with test runner

Usage:
    ./scripts/visual_diff.py compare baseline.png current.png
    ./scripts/visual_diff.py capture --name "menu_open"
    ./scripts/visual_diff.py verify current.png --baseline menu_open
    ./scripts/visual_diff.py list  # List all baselines
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Try to import PIL, fall back to basic comparison if not available
try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL not installed. Install with: pip install Pillow", file=sys.stderr)

class ComparisonResult(NamedTuple):
    """Result of image comparison."""
    identical: bool
    similarity: float  # 0.0 to 1.0
    diff_pixels: int
    total_pixels: int
    diff_image_path: Path | None
    message: str

# Directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
BASELINE_DIR = PROJECT_DIR / "tests" / "baselines"
DIFF_DIR = PROJECT_DIR / "tests" / "diffs"

def ensure_dirs():
    """Create necessary directories."""
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)

def calculate_image_hash(image_path: Path) -> str:
    """Calculate perceptual hash of image (simplified version)."""
    if not HAS_PIL:
        # Fallback: use file hash
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:16]

    img = Image.open(image_path).convert('L')  # Grayscale
    img = img.resize((8, 8), Image.Resampling.LANCZOS)

    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)

    # Generate hash based on whether each pixel is above/below average
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return hex(int(bits, 2))[2:].zfill(16)

def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculate Hamming distance between two hashes."""
    if len(hash1) != len(hash2):
        return max(len(hash1), len(hash2))

    # Convert hex to binary and count differing bits
    try:
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)
        xor = int1 ^ int2
        return bin(xor).count('1')
    except ValueError:
        return len(hash1)

def compare_images(
    baseline_path: Path,
    current_path: Path,
    threshold: float = 0.95,
    pixel_tolerance: int = 5,
    generate_diff: bool = True
) -> ComparisonResult:
    """Compare two images and return detailed result."""

    if not baseline_path.exists():
        return ComparisonResult(
            identical=False,
            similarity=0.0,
            diff_pixels=0,
            total_pixels=0,
            diff_image_path=None,
            message=f"Baseline not found: {baseline_path}"
        )

    if not current_path.exists():
        return ComparisonResult(
            identical=False,
            similarity=0.0,
            diff_pixels=0,
            total_pixels=0,
            diff_image_path=None,
            message=f"Current image not found: {current_path}"
        )

    if not HAS_PIL:
        # Fallback: compare file hashes
        hash1 = calculate_image_hash(baseline_path)
        hash2 = calculate_image_hash(current_path)
        distance = hamming_distance(hash1, hash2)
        similarity = 1.0 - (distance / 64.0)  # 64 bits in hash

        return ComparisonResult(
            identical=hash1 == hash2,
            similarity=similarity,
            diff_pixels=distance,
            total_pixels=64,
            diff_image_path=None,
            message="Hash-based comparison (PIL not available)"
        )

    # Load images
    baseline = Image.open(baseline_path).convert('RGB')
    current = Image.open(current_path).convert('RGB')

    # Check dimensions
    if baseline.size != current.size:
        return ComparisonResult(
            identical=False,
            similarity=0.0,
            diff_pixels=0,
            total_pixels=0,
            diff_image_path=None,
            message=f"Size mismatch: {baseline.size} vs {current.size}"
        )

    total_pixels = baseline.size[0] * baseline.size[1]

    # Calculate difference
    diff = ImageChops.difference(baseline, current)

    # Count differing pixels (with tolerance)
    diff_pixels = 0
    diff_data = list(diff.getdata())
    baseline_data = list(baseline.getdata())
    current_data = list(current.getdata())

    significant_diffs = []
    for i, (r, g, b) in enumerate(diff_data):
        # If any channel differs more than tolerance
        if r > pixel_tolerance or g > pixel_tolerance or b > pixel_tolerance:
            diff_pixels += 1
            if len(significant_diffs) < 100:  # Limit stored diffs
                x = i % baseline.size[0]
                y = i // baseline.size[0]
                significant_diffs.append((x, y, (r, g, b)))

    similarity = 1.0 - (diff_pixels / total_pixels)
    identical = diff_pixels == 0

    # Generate diff image
    diff_image_path = None
    if generate_diff and diff_pixels > 0:
        diff_image_path = DIFF_DIR / f"diff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        # Create highlighted diff image
        diff_highlighted = current.copy()
        draw = ImageDraw.Draw(diff_highlighted)

        # Highlight differing regions
        for x, y, color in significant_diffs:
            # Draw red marker at diff location
            draw.rectangle([x-1, y-1, x+1, y+1], outline='red')

        # Create side-by-side comparison
        comparison_width = baseline.size[0] * 3
        comparison = Image.new('RGB', (comparison_width, baseline.size[1]))
        comparison.paste(baseline, (0, 0))
        comparison.paste(current, (baseline.size[0], 0))
        comparison.paste(diff_highlighted, (baseline.size[0] * 2, 0))

        # Add labels
        draw = ImageDraw.Draw(comparison)
        draw.text((5, 5), "Baseline", fill='white')
        draw.text((baseline.size[0] + 5, 5), "Current", fill='white')
        draw.text((baseline.size[0] * 2 + 5, 5), "Diff", fill='white')

        comparison.save(diff_image_path)

    passed = similarity >= threshold
    message = f"Similarity: {similarity:.2%} ({diff_pixels}/{total_pixels} pixels differ)"
    if not passed:
        message += f" - BELOW THRESHOLD {threshold:.2%}"

    return ComparisonResult(
        identical=identical,
        similarity=similarity,
        diff_pixels=diff_pixels,
        total_pixels=total_pixels,
        diff_image_path=diff_image_path,
        message=message
    )

def capture_baseline(name: str, from_mesen: bool = True) -> Path | None:
    """Capture a new baseline screenshot."""
    ensure_dirs()

    baseline_path = BASELINE_DIR / f"{name}.png"

    if from_mesen:
        # Use mesen_cli to take screenshot
        bridge_dir = Path.home() / "Documents" / "Mesen2" / "bridge"
        temp_path = bridge_dir / "screenshot_temp.png"

        result = subprocess.run(
            [str(SCRIPT_DIR / "mesen_cli.sh"), "screenshot", str(temp_path)],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"Failed to capture screenshot: {result.stderr}", file=sys.stderr)
            return None

        # Move to baseline location
        if temp_path.exists():
            import shutil
            shutil.move(str(temp_path), str(baseline_path))
            print(f"Saved baseline: {baseline_path}")
            return baseline_path
        else:
            print(f"Screenshot not created at {temp_path}", file=sys.stderr)
            return None
    else:
        print(f"Specify source image path with --source", file=sys.stderr)
        return None

def verify_screenshot(
    current_path: Path,
    baseline_name: str,
    threshold: float = 0.95
) -> ComparisonResult:
    """Verify a screenshot against a named baseline."""
    baseline_path = BASELINE_DIR / f"{baseline_name}.png"
    return compare_images(baseline_path, current_path, threshold)

def list_baselines() -> list[dict]:
    """List all baseline images with metadata."""
    ensure_dirs()
    baselines = []

    for path in BASELINE_DIR.glob("*.png"):
        stat = path.stat()
        baselines.append({
            'name': path.stem,
            'path': str(path),
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'hash': calculate_image_hash(path)
        })

    return sorted(baselines, key=lambda x: x['name'])

def main():
    parser = argparse.ArgumentParser(
        description='Visual diff pipeline for Oracle of Secrets'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two images')
    compare_parser.add_argument('baseline', help='Baseline image path')
    compare_parser.add_argument('current', help='Current image path')
    compare_parser.add_argument('--threshold', type=float, default=0.95,
                                help='Similarity threshold (default: 0.95)')
    compare_parser.add_argument('--tolerance', type=int, default=5,
                                help='Pixel tolerance (default: 5)')
    compare_parser.add_argument('--no-diff', action='store_true',
                                help='Skip diff image generation')
    compare_parser.add_argument('--json', action='store_true',
                                help='Output as JSON')

    # Capture command
    capture_parser = subparsers.add_parser('capture', help='Capture baseline')
    capture_parser.add_argument('--name', required=True, help='Baseline name')
    capture_parser.add_argument('--source', help='Source image (default: capture from Mesen2)')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify against baseline')
    verify_parser.add_argument('current', help='Current image path')
    verify_parser.add_argument('--baseline', required=True, help='Baseline name')
    verify_parser.add_argument('--threshold', type=float, default=0.95)

    # List command
    list_parser = subparsers.add_parser('list', help='List baselines')
    list_parser.add_argument('--json', action='store_true')

    args = parser.parse_args()

    if args.command == 'compare':
        result = compare_images(
            Path(args.baseline),
            Path(args.current),
            threshold=args.threshold,
            pixel_tolerance=args.tolerance,
            generate_diff=not args.no_diff
        )

        if args.json:
            print(json.dumps({
                'identical': result.identical,
                'similarity': result.similarity,
                'diff_pixels': result.diff_pixels,
                'total_pixels': result.total_pixels,
                'diff_image': str(result.diff_image_path) if result.diff_image_path else None,
                'message': result.message,
                'passed': result.similarity >= args.threshold
            }, indent=2))
        else:
            print(result.message)
            if result.diff_image_path:
                print(f"Diff image: {result.diff_image_path}")

        return 0 if result.similarity >= args.threshold else 1

    elif args.command == 'capture':
        if args.source:
            import shutil
            ensure_dirs()
            dest = BASELINE_DIR / f"{args.name}.png"
            shutil.copy2(args.source, dest)
            print(f"Saved baseline: {dest}")
        else:
            path = capture_baseline(args.name)
            if not path:
                return 1
        return 0

    elif args.command == 'verify':
        result = verify_screenshot(
            Path(args.current),
            args.baseline,
            args.threshold
        )
        print(result.message)
        if result.diff_image_path:
            print(f"Diff image: {result.diff_image_path}")
        return 0 if result.similarity >= args.threshold else 1

    elif args.command == 'list':
        baselines = list_baselines()
        if args.json:
            print(json.dumps(baselines, indent=2))
        else:
            if not baselines:
                print("No baselines found.")
            else:
                print(f"{'Name':<30} {'Modified':<20} {'Hash':<18}")
                print('-' * 70)
                for b in baselines:
                    print(f"{b['name']:<30} {b['modified'][:19]:<20} {b['hash']:<18}")
        return 0

    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
