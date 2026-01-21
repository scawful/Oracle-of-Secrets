#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <version> [asar_binary]" >&2
  exit 1
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
fi

version="$1"
if ! [[ "$version" =~ ^[0-9]+$ ]]; then
  echo "ERROR: version must be numeric" >&2
  exit 1
fi

asar_bin="${ASAR_BIN:-asar}"
if [[ $# -eq 2 ]]; then
  asar_bin="$2"
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
rom_dir="$repo_root/Roms"

clean_rom="$rom_dir/oos${version}.sfc"
patched_rom="$rom_dir/oos${version}x.sfc"

if [[ ! -f "$clean_rom" ]]; then
  echo "ERROR: clean ROM not found: $clean_rom" >&2
  exit 1
fi

backup_root="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Documents/OracleOfSecrets/Roms"
mkdir -p "$backup_root"

if [[ -f "$patched_rom" ]]; then
  timestamp="$(date +"%Y%m%d-%H%M%S")"
  backup_path="$backup_root/oos${version}x_${timestamp}.sfc"
  cp -p "$patched_rom" "$backup_path"
  echo "Archived: $backup_path"
fi

cp -f "$clean_rom" "$patched_rom"

"$asar_bin" Oracle_main.asm "$patched_rom"

echo "Built patched ROM: $patched_rom"
