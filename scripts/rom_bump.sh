#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <current_version> [next_version]" >&2
  exit 1
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
fi

current_version="$1"
if ! [[ "$current_version" =~ ^[0-9]+$ ]]; then
  echo "ERROR: current_version must be numeric" >&2
  exit 1
fi

if [[ $# -eq 2 ]]; then
  next_version="$2"
  if ! [[ "$next_version" =~ ^[0-9]+$ ]]; then
    echo "ERROR: next_version must be numeric" >&2
    exit 1
  fi
else
  next_version=$((current_version + 1))
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
rom_dir="$repo_root/Roms"

clean_rom="$rom_dir/oos${current_version}.sfc"
next_clean_rom="$rom_dir/oos${next_version}.sfc"

if [[ ! -f "$clean_rom" ]]; then
  echo "ERROR: clean ROM not found: $clean_rom" >&2
  exit 1
fi

if [[ -f "$next_clean_rom" ]]; then
  echo "ERROR: target clean ROM already exists: $next_clean_rom" >&2
  exit 1
fi

mkdir -p "$rom_dir"
cp -p "$clean_rom" "$next_clean_rom"
chmod 444 "$next_clean_rom" || true

echo "Created clean ROM: $next_clean_rom (read-only)"

# Copy save states and SRAM from current patched ROM to next version.
shopt -s nullglob
for src in "$rom_dir"/oos"${current_version}"x.*; do
  if [[ "$src" == *.sfc ]]; then
    continue
  fi
  base="$(basename "$src")"
  dest_base="${base/oos${current_version}x/oos${next_version}x}"
  dest="$rom_dir/$dest_base"
  cp -p "$src" "$dest"
  echo "Copied state: $dest_base"
done
shopt -u nullglob

echo "Bump complete: oos${current_version} -> oos${next_version}"
