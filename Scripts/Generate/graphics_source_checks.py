"""Classify source-graphics validators by their ASM consumers.

Use the existing conservative source graph: an unknown conditional keeps every
feasible include required. An unresolved include is an error, not evidence that
a feature is absent. This module neither generates assets nor selects features.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from asm_source import (DEFINE_ANY_ASSIGN_RE, SourceGraphError, _load_global_defines,
                        _parse_define_assignment, collect_reachable_asm_sources)


CONSUMERS = {
    'source_sprite_sheets': Path('Core/Generated/source_sprite_sheets/sheet_overrides.asm'),
    'snowpeak_sheet': Path('Core/Generated/source_sprite_sheets/snowpeak/sheet_overrides.asm'),
    'menu_icon_sheets': Path('Core/Generated/menu_icons/menu_icon_overrides.asm'),
    'joint_palette_source': Path('Core/Generated/joint_palette/directory.asm'),
}
JOINT_PALETTE_READER = Path('Overworld/joint_palette_readers.asm')
EXPANDED_TABLE = Path('Core/gfx_sheet_table.asm')


def source_graph(root):
    root = Path(root).resolve()
    defines = _load_global_defines(root)
    flags = {'ENABLE_SOURCE_SPRITE_SHEETS', 'ENABLE_EXPANDED_GRAPHICS_TABLE',
             'JOINT_PALETTE_DIRECTORY_ENABLED'}
    canonical_joint_palette = None
    # The shared reader deliberately ignores unsupported assignments. A known
    # graphics flag must not silently retain an earlier valid value instead.
    for relative in ('Util/macros.asm', 'Config/module_flags.asm', 'Config/feature_flags.asm',
                     'Oracle_main.asm'):
        path = root / relative
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            assignment = DEFINE_ANY_ASSIGN_RE.match(line.split(';', 1)[0])
            if assignment and assignment[1] in flags:
                parsed = _parse_define_assignment(line, defines)
                if parsed is None or parsed[1] not in (0, 1):
                    raise ValueError(f'Invalid graphics feature flag !{assignment[1]}')
                if relative != 'Oracle_main.asm' and parsed[0] == 'JOINT_PALETTE_DIRECTORY_ENABLED':
                    canonical_joint_palette = parsed[1]
    # The shared loader seeds this context-owned flag to zero. Before a
    # selected context, Asar still sees an explicit canonical flag, so that
    # synthetic default cannot justify skipping its consumer validation.
    # Selected contexts retain their authenticated generated value instead.
    if defines.get('LYRA_BUILD_CONTEXT') == 0 and canonical_joint_palette is not None:
        defines['JOINT_PALETTE_DIRECTORY_ENABLED'] = canonical_joint_palette
    reachable = set(collect_reachable_asm_sources(root, defines=defines))
    return defines, reachable


def applicable(root, name):
    root = Path(root).resolve()
    _, reachable = source_graph(root)
    consumers = [CONSUMERS[name]]
    if name == 'joint_palette_source':
        # A reader-only graph is malformed, not evidence that validation is
        # unnecessary. The maintained entry includes both under the same flag.
        consumers.append(JOINT_PALETTE_READER)
    return any((root / consumer).resolve() in reachable for consumer in consumers)


def legacy_include_allowed(root, output):
    """Only the assembled native-pointer consumer can use its old exact text."""
    root = Path(root).resolve()
    defines, reachable = source_graph(root)
    include = (Path(output) / 'sheet_overrides.asm').resolve()
    return (defines.get('ENABLE_EXPANDED_GRAPHICS_TABLE', 0) == 0
            and (root / EXPANDED_TABLE).resolve() not in reachable
            and include == (root / CONSUMERS['source_sprite_sheets']).resolve()
            and include in reachable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--check', choices=tuple(CONSUMERS), required=True)
    args = parser.parse_args()
    try:
        print('applicable' if applicable(args.root, args.check) else 'not-applicable')
        return 0
    except (OSError, ValueError, SourceGraphError) as error:
        print(f'Graphics source graph: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
