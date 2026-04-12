"""Symbol loading and address resolution for state diffing."""

from __future__ import annotations

import json
import re
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Symbol:
    """A symbol with address, label, and optional value meanings."""
    address: int
    label: str
    desc: str = ""
    values: dict[str, str] = field(default_factory=dict)
    size: int = 1

    def interpret_value(self, value: int) -> str | None:
        """Return human-readable interpretation of a value, if known."""
        hex_key = f"0x{value:02X}"
        return self.values.get(hex_key)


@dataclass(frozen=True)
class MemoryRegion:
    """A memory region definition for diffing."""
    start: int
    length: int
    mem_type: str
    label: str = ""


@dataclass
class RegionPreset:
    """A preset of memory regions with a description."""
    name: str
    desc: str
    ranges: list[MemoryRegion]


class SymbolTable:
    """Symbol table for address-to-label resolution."""

    def __init__(self):
        self._symbols: dict[int, Symbol] = {}
        self._regions: dict[str, RegionPreset] = {}
        self._by_label: dict[str, Symbol] = {}

    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to the table."""
        self._symbols[symbol.address] = symbol
        self._by_label[symbol.label.upper()] = symbol

    def add_symbol_if_missing(self, symbol: Symbol) -> bool:
        """Add symbol only if address is not already populated."""
        if symbol.address in self._symbols:
            return False
        self.add_symbol(symbol)
        return True

    def add_region(self, preset: RegionPreset) -> None:
        """Add a region preset to the table."""
        self._regions[preset.name] = preset

    def lookup(self, address: int) -> Symbol | None:
        """Lookup a symbol by address."""
        return self._symbols.get(address)

    def lookup_by_label(self, label: str) -> Symbol | None:
        """Lookup a symbol by label name."""
        return self._by_label.get(label.upper())

    def get_region(self, name: str) -> RegionPreset | None:
        """Get a region preset by name."""
        return self._regions.get(name)

    def get_all_regions(self) -> dict[str, RegionPreset]:
        """Get all region presets."""
        return self._regions.copy()

    def iter_symbols(self) -> list[Symbol]:
        """Return all symbols."""
        return list(self._symbols.values())

    def annotate_address(self, address: int, value: int | None = None) -> str:
        """Return annotation string for an address."""
        symbol = self.lookup(address)
        if not symbol:
            return f"${address:06X}"

        result = f"${address:06X} ({symbol.label})"
        if value is not None and symbol.values:
            meaning = symbol.interpret_value(value)
            if meaning:
                result += f" = {meaning}"
        return result

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SymbolTable":
        """Load symbols from a JSON file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r") as f:
            data = json.load(f)

        table = cls()

        symbols_data = data.get("symbols", {})
        for addr_str, sym_data in symbols_data.items():
            addr = int(addr_str, 16)
            symbol = Symbol(
                address=addr,
                label=sym_data.get("label", f"UNK_{addr:06X}"),
                desc=sym_data.get("desc", ""),
                values=sym_data.get("values", {}),
                size=int(sym_data.get("size", 1) or 1),
            )
            table.add_symbol(symbol)

        regions_data = data.get("regions", {})
        for region_name, region_data in regions_data.items():
            ranges = []
            for r in region_data.get("ranges", []):
                start = int(r["start"], 16) if isinstance(r["start"], str) else r["start"]
                ranges.append(MemoryRegion(
                    start=start,
                    length=r["length"],
                    mem_type=r.get("mem_type", "wram"),
                    label=r.get("label", ""),
                ))
            preset = RegionPreset(
                name=region_name,
                desc=region_data.get("desc", ""),
                ranges=ranges,
            )
            table.add_region(preset)

        return table

    @classmethod
    def from_asm_files(cls, *paths: str | Path) -> "SymbolTable":
        """Parse symbols from ASM files."""
        table = cls()

        direct_pattern = re.compile(
            r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$?([0-9A-Fa-f]+)",
            re.MULTILINE,
        )
        struct_start = re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)\s+(\$[0-9A-Fa-f]+)")
        struct_field = re.compile(r"^\s*\.([A-Za-z_][A-Za-z0-9_]*)\s*:\s*skip\s+([^;\s]+)")
        struct_end = re.compile(r"^\s*endstruct\b")

        for path in paths:
            path = Path(path)
            if not path.exists():
                continue

            content = path.read_text(errors="ignore")

            for match in direct_pattern.finditer(content):
                label = match.group(1)
                addr_str = match.group(2)
                try:
                    addr = int(addr_str, 16)
                    symbol = Symbol(address=addr, label=label)
                    table.add_symbol(symbol)
                except ValueError:
                    pass

            struct_name: str | None = None
            struct_base: int | None = None
            struct_offset = 0
            for raw_line in content.splitlines():
                start_match = struct_start.match(raw_line)
                if start_match:
                    struct_name = start_match.group(1)
                    try:
                        struct_base = int(start_match.group(2).lstrip("$"), 16)
                    except ValueError:
                        struct_name = None
                        struct_base = None
                    struct_offset = 0
                    continue

                if struct_end.match(raw_line):
                    struct_name = None
                    struct_base = None
                    struct_offset = 0
                    continue

                field_match = struct_field.match(raw_line)
                if not field_match or not struct_name or struct_base is None:
                    continue
                field_name = field_match.group(1)
                size_token = field_match.group(2)
                try:
                    size = int(size_token.lstrip("$"), 16 if size_token.startswith("$") else 10)
                except ValueError:
                    struct_name = None
                    struct_base = None
                    struct_offset = 0
                    continue
                addr = struct_base + struct_offset
                struct_offset += size
                label = f"{struct_name}.{field_name}"
                table.add_symbol(Symbol(address=addr, label=label, size=size))

        return table


OOS_SYMBOL_PATHS = [
    str(Path(__file__).resolve().parents[2] / "Core" / "symbols.asm"),
    str(Path(__file__).resolve().parents[2] / "Core" / "ram.asm"),
    str(Path(__file__).resolve().parents[2] / "Core" / "sram.asm"),
    str(Path(__file__).resolve().parents[2] / "Core" / "structs.asm"),
]

OOS_JSON_PATH = str(Path(__file__).resolve().parents[1] / "state_symbols.json")


def load_oos_symbols() -> SymbolTable:
    """Load Oracle of Secrets symbols with full annotations."""
    env_path = os.getenv("OOS_STATE_SYMBOLS_PATH")
    if env_path:
        return SymbolTable.from_json_file(env_path)

    json_path = Path(OOS_JSON_PATH)
    if json_path.exists():
        base = SymbolTable.from_json_file(json_path)
        asm_table = SymbolTable.from_asm_files(*OOS_SYMBOL_PATHS)
        for sym in asm_table.iter_symbols():
            base.add_symbol_if_missing(sym)
        return base

    return SymbolTable.from_asm_files(*OOS_SYMBOL_PATHS)
