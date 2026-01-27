#!/usr/bin/env python3
import sys
import re
from pathlib import Path

def parse_zs_map(map_path):
    ranges = []
    if not map_path.exists():
        return ranges
    
    # Example format from Core/ZS ROM MAP.txt:
    # 0x128000 - 0x12FFFF: 1 Bank
    #     Custom collision data
    
    content = map_path.read_text()
    pattern = r'(0x[0-9A-Fa-f]+)\s*-\s*(0x[0-9A-Fa-f]+):\s*\d+\s*Bank\n\s+(.+)'
    for match in re.finditer(pattern, content):
        start = int(match.group(1), 16)
        end = int(match.group(2), 16)
        name = match.group(3).strip()
        ranges.append({'start': start, 'end': end, 'name': name})
    
    return ranges

def check_overlaps(symbols_path, zs_ranges):
    overlaps = []
    if not symbols_path.exists():
        return overlaps
    
    # WLA symbols format: [labels] \n 28:8000 LabelName
    # We need PC addresses. In OoS, bank $28 is at $288000.
    # Logic: PC = (Bank << 16) | Offset
    
    content = symbols_path.read_text()
    in_labels = False
    for line in content.splitlines():
        if line.strip() == "[labels]":
            in_labels = True
            continue
        if not in_labels or not line.strip() or line.startswith('['):
            in_labels = False if line.startswith('[') else in_labels
            continue
            
        match = re.match(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
        if match:
            bank = int(match.group(1), 16)
            offset = int(match.group(2), 16)
            pc = (bank << 16) | offset
            label = match.group(3)
            
            for r in zs_ranges:
                if r['start'] <= pc <= r['end']:
                    overlaps.append({
                        'label': label,
                        'pc': hex(pc),
                        'range': f"{hex(r['start'])}-{hex(r['end'])}",
                        'system': r['name']
                    })
    
    return overlaps

def main():
    root = Path(__file__).resolve().parents[1]
    map_file = root / "Core" / "ZS ROM MAP.txt"
    # Assuming the current active ROM symbols
    sym_file = root / "Roms" / "oos168x.symbols"
    
    print(f"[*] Checking for ZScream overlaps using {map_file.name}...")
    zs_ranges = parse_zs_map(map_file)
    if not zs_ranges:
        print("[-] Error: Could not parse ZS ROM map or file missing.")
        sys.exit(1)
        
    overlaps = check_overlaps(sym_file, zs_ranges)
    
    if overlaps:
        print("\n[!] CRITICAL: Found labels overlapping ZScream reserved regions!")
        print("-" * 60)
        for o in overlaps:
            print(f"Label: {o['label']:30} PC: {o['pc']:10} System: {o['system']}")
        print("-" * 60)
        print("[!] Risk: These addresses might be overwritten by ZScream edits.")
        sys.exit(1)
    else:
        print("[+] Success: No ZScream overlaps detected.")

if __name__ == "__main__":
    main()
