#!/usr/bin/env python3
"""
Symbol Export Tool for Oracle of Secrets

Converts WLA/asar symbol files to Mesen2 .mlb format and syncs to emulator.

Formats:
  WLA Input:  "2C:86BA :label_name"  (Bank:Address :Name)
  MLB Output: "SnesPrgRom:2C86BA:label_name" or "PRG:86BA:label_name"

Usage:
    ./scripts/export_symbols.py                    # Export current build
    ./scripts/export_symbols.py --sync             # Export and sync to Mesen2
    ./scripts/export_symbols.py --filter oracle    # Only Oracle_ prefixed labels
    ./scripts/export_symbols.py --format full      # Full SnesPrgRom: format
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Iterator, NamedTuple

class Symbol(NamedTuple):
    """Parsed symbol entry."""
    bank: int
    address: int
    name: str

    @property
    def full_address(self) -> int:
        """Get 24-bit SNES address."""
        return (self.bank << 16) | self.address

    @property
    def prg_offset(self) -> int:
        """Get PRG ROM offset (for LoROM mapping)."""
        # LoROM: banks $00-$7D at $8000-$FFFF
        # Address = (bank * 0x8000) + (addr - 0x8000)
        if self.address >= 0x8000:
            return (self.bank * 0x8000) + (self.address - 0x8000)
        return self.full_address

def parse_wla_symbols(path: Path) -> Iterator[Symbol]:
    """Parse WLA/asar symbol file."""
    in_labels = False

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()

            # Look for [labels] section
            if line == '[labels]':
                in_labels = True
                continue

            if not in_labels:
                continue

            # Skip empty lines and comments
            if not line or line.startswith(';'):
                continue

            # Parse "BB:AAAA :name" format (with colon before name)
            match = re.match(r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+:(.+)$', line)
            if match:
                bank = int(match.group(1), 16)
                addr = int(match.group(2), 16)
                name = match.group(3).strip()
                yield Symbol(bank, addr, name)
                continue

            # Parse "BB:AAAA name" format (without colon before name)
            match = re.match(r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z_][A-Za-z0-9_]*)$', line)
            if match:
                bank = int(match.group(1), 16)
                addr = int(match.group(2), 16)
                name = match.group(3).strip()
                yield Symbol(bank, addr, name)

def filter_symbols(symbols: Iterator[Symbol], filter_type: str) -> Iterator[Symbol]:
    """Filter symbols based on criteria."""
    for sym in symbols:
        if filter_type == 'all':
            yield sym
        elif filter_type == 'oracle':
            # Only Oracle_ prefixed labels
            if sym.name.startswith('Oracle_'):
                yield sym
        elif filter_type == 'named':
            # Skip auto-generated labels (pos_*, neg_*, +/-)
            if not re.match(r'^(pos_|neg_|\+|\-)', sym.name):
                yield sym
        elif filter_type == 'important':
            # Important labels: Oracle_, Sprite_, Handler_, etc.
            important_prefixes = ('Oracle_', 'Sprite_', 'Handler_', 'Music_',
                                  'Item_', 'Dungeon_', 'Overworld_', 'Menu_',
                                  'Link_', 'NPC_', 'Boss_', 'Room_')
            if any(sym.name.startswith(p) for p in important_prefixes):
                yield sym

def format_mlb_line(sym: Symbol, format_type: str) -> str:
    """Format symbol as MLB line."""
    if format_type == 'full':
        # Full Mesen2 format: SnesPrgRom:BBAAAA:name
        return f"SnesPrgRom:{sym.full_address:06X}:{sym.name}"
    elif format_type == 'prg':
        # PRG offset format: PRG:offset:name
        return f"PRG:{sym.prg_offset:X}:{sym.name}"
    else:  # 'simple'
        # Simple format: PRG:AAAA:name (address only, no bank)
        return f"PRG:{sym.address:X}:{sym.name}"

def get_wram_symbols() -> list[tuple[int, str, str]]:
    """Get common WRAM symbol definitions."""
    # (address, name, comment)
    return [
        (0x7E0010, "GameMode", "Current game mode"),
        (0x7E0011, "GameSubmode", "Game submode"),
        (0x7E001B, "IndoorFlag", "0=outdoor, 1=indoor"),
        (0x7E0020, "LinkY", "Link Y position low"),
        (0x7E0021, "LinkYH", "Link Y position high"),
        (0x7E0022, "LinkX", "Link X position low"),
        (0x7E0023, "LinkXH", "Link X position high"),
        (0x7E002F, "LinkDirection", "0=up,2=down,4=left,6=right"),
        (0x7E005D, "LinkState", "Link action state"),
        (0x7E00A0, "RoomID", "Current room/area ID"),
        (0x7E00F2, "InputHeld", "Held AXLR buttons"),
        (0x7E00F4, "InputNew", "New D-pad/Select/Start"),
        (0x7E00F6, "InputNewAXLR", "New AXLR this frame"),
        (0x7E0200, "MenuState", "Menu state"),
        (0x7E0202, "EquippedSlot", "Currently equipped item slot"),
        (0x7E0730, "FreeRAMStart", "Start of free RAM region"),
        (0x7E0739, "GoldstarOrHookshot", "0/1=hookshot, 2=goldstar"),
        (0x7EF300, "SRAMStart", "Start of SRAM region"),
        (0x7EF342, "HookshotSRAM", "1=hookshot, 2=both items"),
        (0x7EF36C, "MaxHealth", "Maximum health (quarter hearts)"),
        (0x7EF36D, "CurrentHealth", "Current health"),
        (0x7EF411, "WaterGateStates", "Water gate SRAM flags"),
    ]

def export_symbols(
    input_path: Path,
    output_path: Path,
    filter_type: str = 'named',
    format_type: str = 'simple',
    include_wram: bool = True
) -> int:
    """Export symbols to MLB format. Returns count of symbols exported."""

    symbols = list(filter_symbols(parse_wla_symbols(input_path), filter_type))

    # Sort by address
    symbols.sort(key=lambda s: s.full_address)

    with open(output_path, 'w', encoding='utf-8') as f:
        # Write header comment
        f.write(f"; Oracle of Secrets symbols\n")
        f.write(f"; Generated from {input_path.name}\n")
        f.write(f"; Filter: {filter_type}, Format: {format_type}\n")
        f.write(f"; Total: {len(symbols)} ROM symbols\n")
        f.write("\n")

        # Write WRAM symbols first
        if include_wram:
            f.write("; === WRAM Symbols ===\n")
            for addr, name, comment in get_wram_symbols():
                f.write(f"SnesWorkRam:{addr:06X}:{name}:{comment}\n")
            f.write("\n")

        # Write ROM symbols
        f.write("; === ROM Symbols ===\n")
        current_bank = -1
        for sym in symbols:
            # Add bank separator comments
            if sym.bank != current_bank:
                f.write(f"\n; Bank ${sym.bank:02X}\n")
                current_bank = sym.bank

            f.write(format_mlb_line(sym, format_type) + "\n")

    return len(symbols)

def sync_to_mesen2(mlb_path: Path, rom_name: str = "oos168x") -> bool:
    """Copy MLB file to Mesen2 directory."""
    mesen2_dir = Path.home() / "Documents" / "Mesen2" / "Debug"
    mesen2_dir.mkdir(parents=True, exist_ok=True)

    # Mesen2 auto-loads .mlb files matching ROM name
    dest_path = mesen2_dir / f"{rom_name}.mlb"

    try:
        shutil.copy2(mlb_path, dest_path)
        print(f"Synced to: {dest_path}")
        return True
    except Exception as e:
        print(f"Failed to sync: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Export Oracle of Secrets symbols to Mesen2 format'
    )
    parser.add_argument(
        'input', nargs='?',
        default='Roms/oos168x.sym',
        help='Input WLA symbol file (default: Roms/oos168x.sym)'
    )
    parser.add_argument(
        '-o', '--output',
        default='Roms/oos168x.mlb',
        help='Output MLB file (default: Roms/oos168x.mlb)'
    )
    parser.add_argument(
        '--filter',
        choices=['all', 'oracle', 'named', 'important'],
        default='named',
        help='Symbol filter (default: named - skip auto-generated)'
    )
    parser.add_argument(
        '--format',
        choices=['simple', 'prg', 'full'],
        default='full',
        help='Output format (default: full - SnesPrgRom:BBAAAA:name)'
    )
    parser.add_argument(
        '--sync', action='store_true',
        help='Sync to Mesen2 directory after export'
    )
    parser.add_argument(
        '--rom-name',
        default='oos168x',
        help='ROM name for Mesen2 sync (default: oos168x)'
    )
    parser.add_argument(
        '--no-wram', action='store_true',
        help='Skip WRAM symbol definitions'
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Resolve paths relative to script directory
    script_dir = Path(__file__).parent.parent
    input_path = script_dir / args.input
    output_path = script_dir / args.output

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")
        print(f"Filter: {args.filter}")
        print(f"Format: {args.format}")

    count = export_symbols(
        input_path,
        output_path,
        filter_type=args.filter,
        format_type=args.format,
        include_wram=not args.no_wram
    )

    print(f"Exported {count} symbols to {output_path}")

    if args.sync:
        sync_to_mesen2(output_path, args.rom_name)

    return 0

if __name__ == '__main__':
    sys.exit(main())
