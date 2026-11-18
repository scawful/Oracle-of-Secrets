#!/usr/bin/env python3
"""List or refresh stale source hashes in Config/allocation_ownership.json.

  refresh_allocation_evidence.py                 # list stale keys (rc 1 if any)
  refresh_allocation_evidence.py --write [KEY..] # refresh all stale, or only KEYs

Edit a ledger-bound source (Core/symbols.asm, Core/sram.asm, ...) and the
allocation tests fail with "Stale source evidence: <key>". This rewrites only
the sha256 strings, after the refreshed ledger passes every anchor and address
binding check for the claims the repo root can prove. A moved address still
fails: fix the ledger claim, not the hash.
"""
import argparse
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS / 'Generate')]
from allocation_contracts import AllocationError, refresh_evidence


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('keys', nargs='*', help='source keys to refresh (default: every stale shared key)')
    p.add_argument('--root', type=Path, default=SCRIPTS.parent)
    p.add_argument('--write', action='store_true')
    a = p.parse_args(argv)
    path = a.root / 'Config/allocation_ownership.json'
    text = path.read_text()
    try:
        changes = refresh_evidence(json.loads(text), {'shared': a.root.resolve()}, a.keys)
    except AllocationError as e:
        print(f'refused: {e}', file=sys.stderr)
        return 2
    for key, (old, new) in changes.items():
        print(f'{key}\t{old[:12]} -> {new[:12]}')
        if text.count(old) != 1:
            print(f'refused: {key} hash is not unique in the ledger', file=sys.stderr)
            return 2
        text = text.replace(old, new)
    if not changes:
        print('ledger evidence is current')
        return 0
    if not a.write:
        return 1
    path.write_text(text)
    print(f'wrote {len(changes)} hash(es) to {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
