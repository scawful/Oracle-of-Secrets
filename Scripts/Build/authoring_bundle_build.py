#!/usr/bin/env python3
"""Guard an authoring bundle before delegating to its native-only build."""

from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import subprocess
import sys


def build_project(project: Path) -> int:
    project = project.resolve(strict=True)
    config = configparser.ConfigParser(interpolation=None)
    with project.open(encoding="utf-8") as stream:
        config.read_file(stream)
    terrain = config.get("files", "lyra_terrain_file", fallback="").strip()
    if terrain:
        raise ValueError(
            f"Build Project stopped: this project references Lyra terrain ({terrain}). "
            "The bundled native168 build does not compile Lyra sidecar maps or "
            "project background colors. Expanded authoring build support is not "
            "available. No build was started; project and ROM files are unchanged."
        )
    root = project.parent
    script = root / "project" / "Scripts" / "Build" / "build_rom.sh"
    if not script.is_file():
        raise ValueError(f"Bundled native build script is missing: {script}")
    environment = dict(
        os.environ, OOS_BASE_ROM="rom", OOS_BACKUP_ROOT="backups", OOS_MANIFEST_ROOT="."
    )
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
