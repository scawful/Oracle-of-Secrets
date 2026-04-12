#!/usr/bin/env python3
"""
Full Analysis - Combined static + dynamic analysis for Oracle of Secrets.

Runs static analysis (call graph, stack balance, M/X flag checking) and
optionally dynamic analysis (P register watch, memory blame) for comprehensive
ROM debugging.

Usage:
    python3 full_analysis.py Roms/oos168x.sfc --hooks hooks.json
    python3 full_analysis.py Roms/oos168x.sfc --static-only
    python3 full_analysis.py Roms/oos168x.sfc --dynamic-only --frames 600
    python3 full_analysis.py Roms/oos168x.sfc --call-graph call_graph.dot
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add paths for imports
SCRIPT_DIR = Path(__file__).resolve().parent
Z3DK_SCRIPTS = Path.home() / "src" / "hobby" / "z3dk" / "scripts"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(Z3DK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(Z3DK_SCRIPTS))


def run_static_analysis(rom_path: Path, hooks_path: Optional[Path],
                        call_graph_path: Optional[Path],
                        verbose: bool = False) -> Dict[str, Any]:
    """Run static analysis on the ROM.

    Returns:
        Dict with static analysis results
    """
    from static_analyzer import analyze_rom, AnalysisResult

    print("Running static analysis...", file=sys.stderr)

    result = analyze_rom(
        rom_path,
        hooks_path=hooks_path,
        mapper='lorom',
    )

    # Export call graph if requested
    if call_graph_path and result.call_graph:
        if str(call_graph_path).endswith('.json'):
            result.call_graph.export_json(str(call_graph_path))
        else:
            result.call_graph.export_dot(str(call_graph_path))
        print(f"Call graph exported to: {call_graph_path}", file=sys.stderr)

    # Build results dict
    static_results = {
        'success': result.success(),
        'errors': len(result.errors()),
        'warnings': len(result.warnings()),
        'diagnostics': [
            {
                'severity': d.severity,
                'message': d.message,
                'address': f"${d.address:06X}",
                'context': d.context,
            }
            for d in result.diagnostics
        ],
        'stack_issues': [
            {
                'severity': d.severity,
                'message': d.message,
                'address': f"${d.address:06X}",
                'context': d.context,
            }
            for d in result.stack_issues
        ],
        'hooks_analyzed': len(result.hooks),
        'cross_refs_found': len(result.cross_refs),
        'addresses_visited': len(result.entry_states),
    }

    # Add call graph analysis
    if result.call_graph:
        call_graph = result.call_graph
        cross_bank = call_graph.find_cross_bank_calls()
        cycles = call_graph.find_recursive_calls()

        static_results['call_graph'] = call_graph.export_dict()['stats']
        static_results['cross_bank_calls'] = [
            {'from': f"${r.from_addr:06X}", 'to': f"${r.to_addr:06X}", 'kind': r.kind}
            for r in cross_bank[:20]
        ]
        static_results['recursive_cycles'] = [
            [f"${addr:06X}" for addr in cycle]
            for cycle in cycles[:10]
        ]

    return static_results


def run_dynamic_analysis(hooks_path: Optional[Path], frames: int,
                         watch_coords: bool = True,
                         verbose: bool = False) -> Dict[str, Any]:
    """Run dynamic analysis using the emulator.

    Returns:
        Dict with dynamic analysis results
    """
    # Import dynamic analysis modules
    from p_watch import PRegisterWatch
    from mem_blame import MemoryBlame
    from mesen2_client_lib.client import OracleDebugClient

    print("Running dynamic analysis...", file=sys.stderr)

    # Connect to emulator
    client = OracleDebugClient()
    if not client.ensure_connected():
        return {
            'error': 'Could not connect to Mesen2 socket',
            'connected': False,
        }

    dynamic_results = {
        'connected': True,
        'frames_run': frames,
    }

    # P Register Watch
    print(f"  P Register Watch ({frames} frames)...", file=sys.stderr)
    p_watch = PRegisterWatch(client)
    if hooks_path and hooks_path.exists():
        p_watch.load_hooks(hooks_path)

    p_events = p_watch.run(frames // 2)  # Half frames for P watch

    dynamic_results['p_register'] = {
        'mismatches': len(p_events),
        'm_mismatches': sum(1 for e in p_events if e.flag_type == 'M'),
        'x_mismatches': sum(1 for e in p_events if e.flag_type == 'X'),
        'events': [
            {
                'pc': f"${e.pc:06X}",
                'hook': e.hook_name,
                'flag': e.flag_type,
                'expected': e.expected,
                'actual': e.actual,
                'frame': e.frame,
            }
            for e in p_events[:20]  # Limit output
        ],
    }

    # Memory Blame (coordinates)
    if watch_coords:
        print(f"  Memory Blame ({frames // 2} frames)...", file=sys.stderr)
        blame = MemoryBlame(client)
        blame.watch_preset('coords')

        blame.run(frames // 2)

        coord_results = {}
        for addr, watch in blame.watches.items():
            coord_results[f'${addr:06X}'] = {
                'name': watch.name,
                'write_count': len(watch.write_events),
                'unique_writers': [f'${pc:06X}' for pc in sorted(watch.unique_writers)],
            }

        dynamic_results['coordinate_writes'] = coord_results

    return dynamic_results


def print_summary(results: Dict[str, Any]) -> None:
    """Print a human-readable summary of results."""
    print("\n" + "=" * 60)
    print("Oracle of Secrets Full Analysis Report")
    print("=" * 60)

    # Static analysis summary
    if 'static' in results:
        static = results['static']
        print("\nStatic Analysis:")
        print("-" * 40)
        print(f"  Hooks analyzed: {static.get('hooks_analyzed', 0)}")
        print(f"  Cross-references: {static.get('cross_refs_found', 0)}")
        print(f"  Addresses visited: {static.get('addresses_visited', 0)}")

        errors = static.get('errors', 0)
        warnings = static.get('warnings', 0)
        print(f"  Errors: {errors}")
        print(f"  Warnings: {warnings}")

        # Call graph stats
        cg = static.get('call_graph', {})
        if cg:
            print(f"  Call graph: {cg.get('total_refs', 0)} refs, "
                  f"{cg.get('entry_points', 0)} entry points")

        cross_bank = static.get('cross_bank_calls', [])
        if cross_bank:
            print(f"  Cross-bank calls (bugs?): {len(cross_bank)}")

        cycles = static.get('recursive_cycles', [])
        if cycles:
            print(f"  Recursive cycles: {len(cycles)}")

        # Show diagnostics
        diagnostics = static.get('diagnostics', []) + static.get('stack_issues', [])
        if diagnostics:
            print(f"\n  Issues ({len(diagnostics)}):")
            for d in diagnostics[:10]:
                severity = d.get('severity', 'info').upper()
                addr = d.get('address', '?')
                msg = d.get('message', '')
                print(f"    [{severity}] {addr}: {msg}")
            if len(diagnostics) > 10:
                print(f"    ... and {len(diagnostics) - 10} more")

    # Dynamic analysis summary
    if 'dynamic' in results:
        dynamic = results['dynamic']
        print("\nDynamic Analysis:")
        print("-" * 40)

        if dynamic.get('error'):
            print(f"  Error: {dynamic['error']}")
        else:
            print(f"  Frames run: {dynamic.get('frames_run', 0)}")

            # P register
            p_reg = dynamic.get('p_register', {})
            if p_reg:
                print(f"  P Register mismatches: {p_reg.get('mismatches', 0)}")
                if p_reg.get('events'):
                    for e in p_reg['events'][:5]:
                        print(f"    {e['pc']} ({e['hook']}): {e['flag']} flag "
                              f"expected {e['expected']}, got {e['actual']}")

            # Coordinate writes
            coords = dynamic.get('coordinate_writes', {})
            if coords:
                print(f"  Coordinate writes:")
                for addr, info in coords.items():
                    writers = info.get('unique_writers', [])
                    print(f"    {info['name']}: {info['write_count']} writes, "
                          f"{len(writers)} unique writers")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Combined static + dynamic analysis for Oracle of Secrets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full analysis
  %(prog)s Roms/oos168x.sfc --hooks hooks.json

  # Static analysis only
  %(prog)s Roms/oos168x.sfc --static-only

  # Dynamic analysis only (requires running emulator)
  %(prog)s Roms/oos168x.sfc --dynamic-only --frames 600

  # Export call graph
  %(prog)s Roms/oos168x.sfc --call-graph call_graph.dot

  # JSON output
  %(prog)s Roms/oos168x.sfc --json > analysis.json
"""
    )

    parser.add_argument('rom', type=Path, help='ROM file to analyze')
    parser.add_argument('--hooks', type=Path, default=Path('hooks.json'),
                       help='Hooks manifest JSON (default: hooks.json)')
    parser.add_argument('--static-only', action='store_true',
                       help='Run only static analysis')
    parser.add_argument('--dynamic-only', action='store_true',
                       help='Run only dynamic analysis')
    parser.add_argument('--call-graph', type=Path, metavar='FILE',
                       help='Export call graph to DOT or JSON file')
    parser.add_argument('--frames', type=int, default=600,
                       help='Frames for dynamic analysis (default: 600)')
    parser.add_argument('--no-coords', action='store_true',
                       help='Skip coordinate memory blame in dynamic analysis')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    results = {
        'rom': str(args.rom),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # Run static analysis
    if not args.dynamic_only:
        try:
            results['static'] = run_static_analysis(
                args.rom,
                args.hooks if args.hooks.exists() else None,
                args.call_graph,
                args.verbose,
            )
        except Exception as e:
            results['static'] = {'error': str(e)}
            print(f"Static analysis error: {e}", file=sys.stderr)

    # Run dynamic analysis
    if not args.static_only:
        try:
            results['dynamic'] = run_dynamic_analysis(
                args.hooks if args.hooks.exists() else None,
                args.frames,
                watch_coords=not args.no_coords,
                verbose=args.verbose,
            )
        except Exception as e:
            results['dynamic'] = {'error': str(e)}
            print(f"Dynamic analysis error: {e}", file=sys.stderr)

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)

    # Return code based on errors
    static_success = results.get('static', {}).get('success', True)
    dynamic_ok = not results.get('dynamic', {}).get('error')

    if not static_success:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
