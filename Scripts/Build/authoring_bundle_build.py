#!/usr/bin/env python3
"""Resolve saved authoring inputs before delegating to the maintained build."""

from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import subprocess
import sys


def current_environment(project: Path, config, engine: Path) -> dict[str, str]:
    """Read-only admission through the same backend used again by build_rom.sh.

    An exported descriptor is a new saved-project identity. Copying old producer
    metadata never supplies a new native Save, context, transfer or allocation.
    """
    try:
        import lyra_project_publisher as publisher
        target = publisher.resolve_current_target(project)
        if Path(target['engine']) != engine.resolve(strict=True):
            raise ValueError('Reviewed current source differs from this bundled build engine')
        return dict(OOS_BASE_ROM=target['base_rom'], OOS_LYRA_PROJECT=str(project),
                    OOS_LYRA_REQUEST=target['request'], OOS_LYRA_CANDIDATE=target['candidate'])
    except (ImportError, OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(
            f'Build Project stopped: {error}. Complete native Save in this opened project, '
            'then bind its current producer, live Save context, fresh transfer request and reviewed runtime inputs. '
            'No build was started; project and ROM files are unchanged.'
        ) from error


def build_project(project: Path) -> int:
    project = project.resolve(strict=True)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    with project.open(encoding="utf-8") as stream:
        config.read_file(stream)
    config.defaults().clear()
    terrain = config.get("files", "lyra_terrain_file", fallback="").strip()
    root = project.parent
    script = root / "project" / "Scripts" / "Build" / "build_rom.sh"
    if not script.is_file():
        raise ValueError(f"Bundled native build script is missing: {script}")
    environment = dict(
        os.environ, OOS_BASE_ROM="rom", OOS_BACKUP_ROOT="backups", OOS_MANIFEST_ROOT="."
    )
    # Native projects never inherit another editor/project's Lyra selection.
    for key in ('OOS_LYRA_PROJECT', 'OOS_LYRA_REQUEST', 'OOS_LYRA_BUILD_CONTEXT', 'OOS_LYRA_CANDIDATE'):
        environment.pop(key, None)
    if terrain:
        environment.update(current_environment(project, config, root / 'project'))
    return subprocess.run(
        ["bash", str(script), "168"], cwd=root, env=environment, check=False
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return build_project(args.project)
    except (OSError, ValueError, configparser.Error) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
