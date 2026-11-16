"""Project-bound private output paths for selected Lyra builds.

This checks path placement only; it grants no source, allocation or runtime
authority. The caller must still hold the project/engine locks and validate
the transfer, receipt and source bindings.
"""
from pathlib import Path
import re


def private_output_root(project):
    return Path(str(Path(project)) + '.lyra-build-output')


def is_private_generation(project, engine, candidate):
    project, engine, candidate = map(Path, (project, engine, candidate))
    root = private_output_root(project)
    return (project.is_absolute() and engine.is_absolute() and candidate.is_absolute()
            and project == project.resolve(strict=True)
            and engine == engine.resolve(strict=True)
            and candidate == candidate.resolve()
            and not root.is_relative_to(engine / 'Roms')
            and candidate.parent.parent == root
            and candidate.name == 'oos168x.sfc'
            and re.fullmatch(r'lyra-[0-9a-f]{32}', candidate.parent.name) is not None
            and not any(path.is_symlink() for path in (candidate, *candidate.parents)))
