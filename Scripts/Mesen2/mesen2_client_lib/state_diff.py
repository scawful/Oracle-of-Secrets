"""State diffing logic for comparing save states via socket API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile

from .state_symbols import SymbolTable, load_oos_symbols, MemoryRegion


@dataclass
class MemoryDiff:
    """A single memory difference."""
    address: int
    old_value: int
    new_value: int
    label: str = ""
    meaning_old: str = ""
    meaning_new: str = ""

    def to_dict(self) -> dict:
        result = {
            "addr": f"${self.address:06X}",
            "old": f"0x{self.old_value:02X}",
            "new": f"0x{self.new_value:02X}",
        }
        if self.label:
            result["label"] = self.label
        if self.meaning_old:
            result["old_meaning"] = self.meaning_old
        if self.meaning_new:
            result["new_meaning"] = self.meaning_new
        return result


@dataclass
class RegionDiff:
    """Differences for a specific memory region."""
    name: str
    changes: list[MemoryDiff] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "region": self.name,
            "change_count": len(self.changes),
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class StateDiffResult:
    """Complete result of comparing two states."""
    slot_a: int
    slot_b: int
    total_changes: int
    regions: dict[str, RegionDiff] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        if self.error:
            return {"error": self.error}

        return {
            "summary": f"{self.total_changes} bytes changed across {len(self.regions)} regions",
            "slot_a": self.slot_a,
            "slot_b": self.slot_b,
            "total_changes": self.total_changes,
            "regions": {name: diff.to_dict() for name, diff in self.regions.items()},
        }

    def to_markdown(self) -> str:
        if self.error:
            return f"**Error:** {self.error}"

        lines = [
            f"## State Diff: Slot {self.slot_a} vs Slot {self.slot_b}",
            f"**Total changes:** {self.total_changes} bytes across {len(self.regions)} regions",
            "",
        ]

        for name, region_diff in self.regions.items():
            if not region_diff.changes:
                continue
            lines.append(f"### {name} ({len(region_diff.changes)} changes)")
            lines.append("| Address | Label | Old | New | Meaning |")
            lines.append("|---------|-------|-----|-----|---------|")
            for change in region_diff.changes:
                label = change.label or "-"
                meaning = ""
                if change.meaning_old and change.meaning_new:
                    meaning = f"{change.meaning_old} -> {change.meaning_new}"
                elif change.meaning_new:
                    meaning = change.meaning_new
                lines.append(
                    f"| `${change.address:06X}` | {label} | "
                    f"`0x{change.old_value:02X}` | `0x{change.new_value:02X}` | {meaning} |"
                )
            lines.append("")

        return "\n".join(lines)


DEFAULT_REGION_PRESETS: dict[str, list[MemoryRegion]] = {
    "link": [
        MemoryRegion(start=0x0010, length=256, mem_type="wram"),
        MemoryRegion(start=0x02E0, length=64, mem_type="wram"),
    ],
    "sprites": [
        MemoryRegion(start=0x0DD0, length=16, mem_type="wram", label="SprState"),
        MemoryRegion(start=0x0E20, length=16, mem_type="wram", label="SprType"),
        MemoryRegion(start=0x0E50, length=16, mem_type="wram", label="SprHealth"),
    ],
    "oos_wram": [
        MemoryRegion(start=0x0730, length=32, mem_type="wram"),
    ],
    "sram": [
        MemoryRegion(start=0xF340, length=256, mem_type="wram"),
    ],
}


class StateDiffer:
    """Compares two save states and returns memory differences via socket API."""

    def __init__(self, client, symbols: SymbolTable | None = None):
        self.client = client
        self.symbols = symbols or load_oos_symbols()

    def _snapshot_region(self, region: MemoryRegion) -> bytes:
        return self.client.read_block(region.start, region.length, memtype=region.mem_type.upper())

    def _snapshot_regions(self, region_names: list[str]) -> dict[str, dict[MemoryRegion, bytes]]:
        snapshots: dict[str, dict[MemoryRegion, bytes]] = {}

        for name in region_names:
            preset = self.symbols.get_region(name)
            regions = preset.ranges if preset else DEFAULT_REGION_PRESETS.get(name, [])
            if not regions:
                continue

            snapshots[name] = {}
            for region in regions:
                data = self._snapshot_region(region)
                snapshots[name][region] = data

        return snapshots

    def _compare_snapshots(
        self,
        snap_a: dict[str, dict[MemoryRegion, bytes]],
        snap_b: dict[str, dict[MemoryRegion, bytes]],
    ) -> dict[str, RegionDiff]:
        result: dict[str, RegionDiff] = {}

        for name in snap_a:
            if name not in snap_b:
                continue

            region_diff = RegionDiff(name=name)

            for region, data_a in snap_a[name].items():
                data_b = snap_b[name].get(region, b"")
                if len(data_a) != len(data_b):
                    continue

                for i in range(len(data_a)):
                    if data_a[i] != data_b[i]:
                        full_addr = 0x7E0000 + region.start + i

                        symbol = self.symbols.lookup(full_addr)
                        label = ""
                        meaning_old = ""
                        meaning_new = ""

                        if symbol:
                            label = symbol.label
                            meaning_old = symbol.interpret_value(data_a[i]) or ""
                            meaning_new = symbol.interpret_value(data_b[i]) or ""

                        diff = MemoryDiff(
                            address=full_addr,
                            old_value=data_a[i],
                            new_value=data_b[i],
                            label=label,
                            meaning_old=meaning_old,
                            meaning_new=meaning_new,
                        )
                        region_diff.changes.append(diff)

            result[name] = region_diff

        return result

    def diff_states(
        self,
        slot_a: int = 1,
        slot_b: int = 2,
        regions: list[str] | None = None,
    ) -> StateDiffResult:
        if slot_a == slot_b:
            return StateDiffResult(slot_a=slot_a, slot_b=slot_b, total_changes=0, error="slot_a and slot_b must be different")

        region_names = regions or list(DEFAULT_REGION_PRESETS.keys())

        # Save current state to temp file (avoid using user slots)
        temp_path = Path(tempfile.gettempdir()) / "mesen2_state_diff_backup.mss"
        if not self.client.save_state(path=str(temp_path)):
            return StateDiffResult(slot_a=slot_a, slot_b=slot_b, total_changes=0, error="Failed to save current state")

        try:
            if not self.client.load_state(slot=slot_a):
                return StateDiffResult(slot_a=slot_a, slot_b=slot_b, total_changes=0, error=f"Failed to load slot {slot_a}")
            snap_a = self._snapshot_regions(region_names)

            if not self.client.load_state(slot=slot_b):
                return StateDiffResult(slot_a=slot_a, slot_b=slot_b, total_changes=0, error=f"Failed to load slot {slot_b}")
            snap_b = self._snapshot_regions(region_names)

        finally:
            # Restore original state
            self.client.load_state(path=str(temp_path))
            try:
                temp_path.unlink()
            except OSError:
                pass

        regions_diff = self._compare_snapshots(snap_a, snap_b)
        total_changes = sum(len(diff.changes) for diff in regions_diff.values())

        return StateDiffResult(
            slot_a=slot_a,
            slot_b=slot_b,
            total_changes=total_changes,
            regions=regions_diff,
        )
