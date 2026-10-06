#!/usr/bin/env python3
"""Validate ownership and current table evidence; known defects are fatal.

No source, flag, ROM or emulator writes. The only output is --output JSON.
Pending/proposed scenarios are source-ledger evaluations, not RC ROM qualification.
"""
import argparse
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS / 'Generate'), str(SCRIPTS / 'Build')]
from allocation_contracts import (AllocationError, cart_checks, digest, emission_crossings,
    ownership_conflicts, read_ledger, read_symbols, source_evidence, table_checks,
    validate_draft, verify_receipt)
from asm_source import _load_global_defines
from generate_hack_manifest import load_exact_hooks, ManifestGenerationError


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--symbols', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--source-root', action='append', default=[], metavar='SET=PATH')
    p.add_argument('--scenario', choices=('shared', 'pending', 'proposed'), default='shared')
    p.add_argument('--hooks', type=Path)
    p.add_argument('--require-exact', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    report = {'schema_version': 1, 'scenario': args.scenario, 'errors': [], 'warnings': [], 'facts': {}, 'passed': False}
    def check(name, action):
        try:
            value = action(); report['facts'][name] = value; return value
        except (OSError, ValueError, KeyError, TypeError, ManifestGenerationError) as e:
            report['errors'].append({'check': name, 'message': str(e)}); return None
    roots = {'shared': args.root.resolve()}
    for entry in args.source_root:
        key, separator, path = entry.partition('=')
        if not separator or key == 'shared' or key in roots:
            p.error('Source roots must be unique SET=PATH bindings; shared is --root')
        roots[key] = Path(path).resolve()
    # Prevent reports from overwriting supplied artifacts or project inputs.
    out = args.output.resolve()
    if any(out.is_relative_to(root) for root in roots.values()) or out in {args.rom.resolve(), args.symbols.resolve(), args.receipt.resolve()}:
        p.error('--output must be outside the source root and distinct from input artifacts')
    report['source_roots'] = {k: str(v) for k, v in roots.items()}
    profile = check('build_receipt', lambda: verify_receipt(args.receipt, args.root, args.rom, args.symbols))
    ledger = check('ledger_schema', lambda: read_ledger(args.root / 'Config/allocation_ownership.json'))
    # Avoid embedding a second full ledger in the report.
    if ledger:
        report['facts']['ledger_schema'] = {'claims': len(ledger['claims']), 'sha256': digest(args.root / 'Config/allocation_ownership.json')}
        evidence = check('source_provenance', lambda: source_evidence(ledger, roots))
        if evidence and profile is not None:
            allocation_profile = profile
            if args.scenario != 'shared':
                allocation_profile = check('pending_profile', lambda: _load_global_defines(roots['pending_rc']))
                report['allocation_profile_scope'] = 'pending_source_only; ROM table/reset evidence remains shared candidate'
            if allocation_profile is not None:
                result = check('ownership', lambda: ownership_conflicts(ledger, allocation_profile, pending=args.scenario != 'shared', proposed=args.scenario == 'proposed'))
                if result:
                    conflicts, notes = result
                    report['facts']['ownership'] = {'conflicts': conflicts, 'notes': notes}
                    for conflict in conflicts:
                        report['errors'].append({'check': 'ownership', **conflict})
                    report['warnings'].extend(notes)
        if profile is not None:
            symbols = check('symbols', lambda: read_symbols(args.symbols))
            if symbols:
                report['facts']['symbols'] = {'sha256': digest(args.symbols), 'count': len(symbols)}
                ranges = check('tables_160', lambda: table_checks(ledger['tables'], symbols, args.rom.stat().st_size))
                cart = check('cart', lambda: cart_checks(args.root, ledger['cart'], symbols, args.rom.read_bytes()))
                if cart and not cart['reset_bounds_passed']:
                    report['errors'].append({'check': 'cart_reset_bounds', 'message': f"Reset clears {cart['reset_bytes_per_array']} bytes; arrays own {cart['expected_bytes_per_array']}"})
                if args.hooks and ranges is not None:
                    spans = check('exact_hook_provenance', lambda: load_exact_hooks(args.hooks, args.rom))
                    if spans is not None:
                        exact, provenance = spans
                        report['facts']['exact_hook_provenance'] = provenance
                        if not exact:
                            report['errors'].append({'check': 'exact_emissions', 'message': 'Empty emission evidence'})
                        else:
                            check('exact_emissions', lambda: emission_crossings(exact, ranges) or {'spans_checked': len(exact)})
                else:
                    report['facts']['exact_emissions'] = {'status': 'unavailable', 'note': 'WLA labels prove table bounds, not every emitted byte.'}
                    (report['errors'] if args.require_exact else report['warnings']).append({'check': 'exact_emissions', 'message': 'No exact assembler span file supplied'})
    check('draft_192', lambda: validate_draft(json.loads((args.root / 'Config/overworld_layout_192.draft.json').read_text()), current_tables=ledger['tables'] if ledger else None))
    report['rom_sha256'] = check('rom_identity', lambda: digest(args.rom))
    report['passed'] = not report['errors']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'errors': len(report['errors']), 'output': str(out)}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
