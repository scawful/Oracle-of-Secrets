#!/usr/bin/env python3
"""Run a t2kit scenario on a candidate and a control ROM and print the verdict table.

  python3 Scripts/Validate/run_t2.py keyblock --candidate HEAD --out /tmp/t2-keyblock

Each git ref is built in its own detached temporary worktree: the base ROM
(default: the main checkout's Roms/oos168.sfc, read only) is copied in as-is,
then `Scripts/Build/build_rom.sh 168` runs there (under quiet-build when it is
on PATH). Builds do not take the heavy lock. Each native episode (one case on
one ROM) holds the heavy lock through Scripts/Agents/heavy_lock.py and releases
it before the next. Prebuilt ROMs skip the build: --candidate-rom / --control-rom.

Writes <out>/summary.json and one result.json per episode; exit 0 when every
candidate case passes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from t2kit import Session, load_fixture  # noqa: E402
from t2kit.fixtures import sha256  # noqa: E402
from t2kit.lock import heavy_lock  # noqa: E402
from t2kit.report import failed_checks, table  # noqa: E402

SCENARIOS = HERE / 't2kit' / 'scenarios'


def git(*args, cwd=REPO):
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def load_scenario(name: str):
    path = Path(name) if name.endswith('.py') else SCENARIOS / f'{name}.py'
    if not path.is_file():
        have = ', '.join(sorted(p.stem for p in SCENARIOS.glob('*.py') if not p.stem.startswith('_')))
        raise SystemExit(f'scenario {name!r} not found (have: {have})')
    spec = importlib.util.spec_from_file_location(f't2_scenario_{path.stem}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ('FIXTURE', 'CASES', 'run'):
        if not hasattr(mod, attr):
            raise SystemExit(f'{path}: scenario must define {attr}')
    mod.PATH = path
    return mod


def default_base_rom() -> Path:
    common = Path(git('rev-parse', '--path-format=absolute', '--git-common-dir'))
    return common.parent / 'Roms' / 'oos168.sfc'


def build(ref: str, label: str, base_rom: Path, out: Path) -> dict:
    """Build `ref` in a detached temporary worktree; copy the ROM, .sym and receipt to out/builds/<label>."""
    commit = git('rev-parse', f'{ref}^{{commit}}')
    dest = out / 'builds' / label
    dest.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f't2-build-{label}-'))
    tree = tmp / 'tree'
    base_sha = sha256(base_rom)
    git('worktree', 'add', '--detach', str(tree), commit)
    try:
        shutil.copy2(base_rom, tree / 'Roms' / 'oos168.sfc')
        cmd = ['env', 'SKIP_ANALYSIS=1', 'bash', 'Scripts/Build/build_rom.sh', '168', '--skip-tests']
        if shutil.which('quiet-build'):
            cmd = ['quiet-build', '--', *cmd]
        print(f'build {label}: {ref} = {commit[:8]}', flush=True)
        with (dest / 'build.log').open('w') as log:
            subprocess.run(cmd, cwd=tree, stdout=log, stderr=subprocess.STDOUT, check=True)
        for name in ('oos168x.sfc', 'oos168x.sym', 'oos168x.build.json'):
            if (tree / 'Roms' / name).exists():
                shutil.copy2(tree / 'Roms' / name, dest / name)
    finally:
        git('worktree', 'remove', '--force', str(tree))
        shutil.rmtree(tmp, ignore_errors=True)
    rom = dest / 'oos168x.sfc'
    return {'ref': ref, 'commit': commit, 'rom': str(rom), 'rom_sha256': sha256(rom),
            'base_rom': str(base_rom), 'base_sha256': base_sha}


def prepare(args, out: Path) -> dict:
    roms = {}
    base = Path(args.base_rom) if args.base_rom else default_base_rom()
    built = {}
    for label, ref, rom in (('candidate', args.candidate, args.candidate_rom),
                            ('control', args.control, args.control_rom)):
        if rom:
            roms[label] = {'rom': str(Path(rom).resolve()), 'rom_sha256': sha256(rom), 'prebuilt': True}
        elif ref and ref != 'none':
            commit = git('rev-parse', f'{ref}^{{commit}}')
            if commit in built:
                roms[label] = dict(built[commit], ref=ref)
            else:
                roms[label] = built[commit] = build(ref, label, base, out)
    return roms


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scenario', help='name under Scripts/Validate/t2kit/scenarios/ or a path to a .py file')
    p.add_argument('--candidate', default='HEAD', help='git ref to test (default HEAD)')
    p.add_argument('--control', default='origin/master', help="git ref for the control run, or 'none'")
    p.add_argument('--candidate-rom', help='prebuilt candidate ROM (skips the build)')
    p.add_argument('--control-rom', help='prebuilt control ROM (skips the build)')
    p.add_argument('--srm', help="SRAM path when the registry path is absent here (hash must match)")
    p.add_argument('--cases', help='comma-separated subset of the scenario CASES')
    p.add_argument('--out', required=True)
    p.add_argument('--app', help='Mesen2 OOS.app (default: OOS_T2_APP or the first known install)')
    p.add_argument('--base-rom', help="base ROM to copy into each build (default: main checkout's Roms/oos168.sfc)")
    p.add_argument('--owner', default=f't2kit-{os.environ.get("USER", "agent")}', help='heavy lock owner name')
    p.add_argument('--lock-wait', type=float, default=3600, help='seconds to wait for the heavy lock per episode')
    args = p.parse_args(argv)

    scenario = load_scenario(args.scenario)
    cases = args.cases.split(',') if args.cases else list(scenario.CASES)
    unknown = set(cases) - set(scenario.CASES)
    if unknown:
        raise SystemExit(f'unknown cases {sorted(unknown)}; scenario has {list(scenario.CASES)}')
    fixture = load_fixture(scenario.FIXTURE, args.srm)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    roms = prepare(args, out)
    if 'candidate' not in roms:
        raise SystemExit('no candidate ROM')

    summary = {'scenario': scenario.PATH.stem, 'scenario_sha256': sha256(scenario.PATH),
               'fixture': {'name': fixture.name, 'path': str(fixture.path), 'sha256': fixture.sha256,
                           'file_slot': fixture.file_slot},
               'roms': roms, 'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'rows': []}
    for case in cases:
        row = {'case': case, 'candidate': None, 'control': None}
        for variant in ('candidate', 'control'):
            if variant not in roms:
                continue
            purpose = f'{scenario.PATH.stem} {case} {variant} (headless, own instance)'
            with heavy_lock(args.owner, purpose, wait=args.lock_wait, log=print):
                t = Session(roms[variant]['rom'], fixture.path, out / variant, scenario=scenario.PATH.stem,
                            variant=variant, case=case, file_slot=fixture.file_slot, app=args.app,
                            fixture_name=fixture.name, scenario_file=scenario.PATH)
                row[variant] = t.execute(scenario.run, case)
        summary['rows'].append(row)
        (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')

    print()
    print(table(summary['rows']))
    for row in summary['rows']:
        for variant in ('candidate', 'control'):
            names = failed_checks(row[variant])
            if names:
                print(f'  {row["case"]} {variant}: ' + '; '.join(names))
    print(f'\nsummary: {out / "summary.json"}')
    ok = all(r['candidate'] and r['candidate'].get('passed') for r in summary['rows'])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
