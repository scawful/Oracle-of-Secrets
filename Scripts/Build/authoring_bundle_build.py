#!/usr/bin/env python3
"""Resolve saved authoring inputs before delegating to the maintained build."""

from __future__ import annotations

import sys

# The launcher still needs a trusted interpreter startup (including -B). Keep
# local imports read-only even when this module is invoked directly or imported.
sys.dont_write_bytecode = True

import argparse
import configparser
import io
import os
from pathlib import Path
import shutil

import lyra_build_selection as selection

BUILD_TIMEOUT_SECONDS = 3600


def current_environment(project: Path, config, engine: Path, *, request: Path,
                        candidate: Path) -> dict[str, str]:
    """Read-only admission through the same backend used again by build_rom.sh.

    An exported descriptor is a new saved-project identity. Copying old producer
    metadata never supplies a new native Save, context, transfer or allocation.
    """
    try:
        import lyra_project_publisher as publisher
        target = publisher.resolve_current_target(project, request=request, candidate=candidate)
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



def prepared_environment(project: Path, config, engine: Path, *, request: Path,
                         candidate: Path) -> dict[str, str]:
    """Resolve lightweight paths; the contained preparation checked admission.

    build_rom.sh revalidates the full request and source before assembly. This
    parent-side step must not invoke Git or other uncontained subprocesses.
    """
    import lyra_project_publisher as publisher
    bound_project, rom, _, bound_request = publisher.project_context(project, request)
    if bound_project != project or bound_request != request:
        raise ValueError('Prepared Build project or request differs from this attempt')
    return dict(OOS_BASE_ROM=str(rom), OOS_LYRA_PROJECT=str(project),
                OOS_LYRA_REQUEST=str(request), OOS_LYRA_CANDIDATE=str(candidate))


def _desktop_engine(project: Path, config, engine: Path) -> Path:
    """Bind an explicit desktop engine to this script and saved code folder.

    This is path validation only; it does not admit an executable graph or
    make the desktop Build entry point safe to launch.
    """
    engine = Path(engine)
    if (not engine.is_absolute() or engine != engine.resolve(strict=True)
            or not engine.is_dir()
            or any(path.is_symlink() for path in (engine, *engine.parents))):
        raise ValueError('Desktop engine must be a canonical non-symlink directory')
    if Path(__file__).resolve(strict=True).parents[2] != engine:
        raise ValueError('Desktop engine differs from the running supervisor source')
    code = config.get('files', 'code_folder', fallback='').strip()
    if not code:
        raise ValueError('Desktop project does not bind an engine code folder')
    code_path = Path(code)
    directory = (code_path if code_path.is_absolute() else project.parent / code_path).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('Desktop project code folder is not a directory')
    for parent in (directory, *directory.parents):
        marker = parent / 'Oracle_main.asm'
        if marker.is_file() and not marker.is_symlink():
            if parent != engine:
                raise ValueError('Desktop project resolves to a different engine')
            return engine
    raise ValueError('Desktop project has no Oracle engine above its code folder')


def build_project(project: Path, *, request: Path | None = None,
                  candidate: Path | None = None, engine: Path | None = None,
                  producer_identity: Path | None = None,
                  macos_profile: Path | None = None,
                  macos_profile_sha256: str | None = None) -> int:
    requested_project = Path(os.path.abspath(project))
    project = project.resolve(strict=True)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    project_bytes = project.read_bytes()
    config.read_file(io.StringIO(project_bytes.decode('utf-8-sig')))
    config.defaults().clear()
    terrain = config.get("files", "lyra_terrain_file", fallback="").strip()
    if terrain and ((request is None) != (candidate is None)):
        raise ValueError('Build Project stopped: a fresh transfer request and candidate are required; no build was started')
    automatic = bool(terrain and request is None)
    if not terrain and (request is not None or candidate is not None):
        raise ValueError('An ordinary Build cannot select an expanded request or candidate')
    if engine is not None and not terrain:
        raise ValueError('A desktop engine override requires expanded terrain')
    if producer_identity is not None:
        producer_identity = Path(producer_identity)
        if (not automatic or not producer_identity.is_absolute()
                or producer_identity != producer_identity.resolve(strict=True)
                or not producer_identity.is_file()
                or any(path.is_symlink() for path in
                       (producer_identity, *producer_identity.parents))):
            raise ValueError('Automatic Build needs a canonical producer identity file')
    root = project.parent
    engine = _desktop_engine(project, config, engine) if engine is not None else root / 'project'
    script = engine / "Scripts" / "Build" / "build_rom.sh"
    if not script.is_file():
        raise ValueError(f"Bundled native build script is missing: {script}")
    environment = dict(
        os.environ, OOS_BASE_ROM="rom", OOS_BACKUP_ROOT="backups", OOS_MANIFEST_ROOT="."
    )
    # A profile is an explicit internal binding, never inherited admission.
    for key in list(environment):
        if key.upper().startswith('OOS_MACOS_BUILD_'):
            del environment[key]
    target = None
    if macos_profile is not None or macos_profile_sha256 is not None:
        if (sys.platform != 'darwin' or not automatic or producer_identity is not None
                or macos_profile is None or macos_profile_sha256 is None):
            raise ValueError('macOS profile requires automatic Build with its configured Save producer')
        import lyra_macos_process_group as macos
        binding = {'path': str(macos_profile), 'sha256': macos_profile_sha256}
        profile = macos.load_oracle_profile(binding)
        if profile['project'] != str(project) or profile['engine'] != str(engine.resolve(strict=True)):
            raise ValueError('macOS profile belongs to another project or engine')
        environment.update(OOS_MACOS_BUILD_PROFILE=binding['path'],
                           OOS_MACOS_BUILD_PROFILE_SHA256=binding['sha256'])
        base = config.get('files', 'rom_filename', fallback='').strip()
        if not base:
            raise ValueError('macOS profile requires the saved project ROM')
        environment['OOS_BASE_ROM'] = str((project.parent / base).resolve(strict=True))
        bash = profile['tools']['bash']['path']
    else:
        bash = shutil.which('bash')
    if not bash:
        raise ValueError('Bundled Build requires an available bash executable')
    bash = str(Path(bash).resolve(strict=True))
    session = (selection.begin_attempt(requested_project, engine) if terrain
               else selection.begin_project_build(requested_project, engine))
    try:
        if session.project != project:
            raise ValueError('Locked project differs from the project being built')
        if project.read_bytes() != project_bytes:
            raise ValueError('Saved project changed while acquiring the project lock')
        if terrain:
            python = Path(sys.executable).resolve(strict=True)
            if automatic:
                preparer = engine / 'Scripts' / 'Build' / 'lyra_project_prepare.py'
                if not preparer.is_file():
                    raise ValueError(f'Bundled transfer preparer is missing: {preparer}')
                auto_request, auto_candidate = session.generated_paths()
                first_command = [str(python), '-B', str(preparer), '--current-save-transfer',
                                 '--auto-ordinary', '--project', str(project),
                                 '--output', str(auto_request.parent),
                                 '--candidate', str(auto_candidate),
                                 '--validate-build-engine', str(engine)]
                if producer_identity is not None:
                    first_command += ['--producer-identity', str(producer_identity)]
            else:
                publisher = engine / 'Scripts' / 'Build' / 'lyra_project_publisher.py'
                if not publisher.is_file():
                    raise ValueError(f'Bundled target validator is missing: {publisher}')
                first_command = [str(python), '-B', str(publisher), 'resolve-target',
                                 '--project', str(project), '--request', str(request),
                                 '--candidate', str(candidate)]
            def validate_prepared(actual_request, actual_candidate):
                nonlocal target
                if project.read_bytes() != project_bytes:
                    raise ValueError('Saved project changed during Build preparation')
                target = prepared_environment(project, config, engine, request=actual_request,
                                              candidate=actual_candidate)
                if (target['OOS_LYRA_PROJECT'] != str(project)
                        or target['OOS_LYRA_REQUEST'] != str(actual_request)
                        or target['OOS_LYRA_CANDIDATE'] != str(actual_candidate)):
                    raise ValueError('Prepared Build inputs differ from this attempt')
                return dict(environment, **target)
            if automatic:
                result = session.run_generated_build(
                    first_command, [bash, str(script), '168'], cwd=root,
                    timeout=BUILD_TIMEOUT_SECONDS, environment=environment,
                    validate_prepared=validate_prepared)
            else:
                result = session.run_selected_build(
                    request, candidate, first_command, [bash, str(script), '168'],
                    cwd=root, timeout=BUILD_TIMEOUT_SECONDS, environment=environment,
                    validate_prepared=validate_prepared)
        else:
            result = session.run_child([bash, str(script), '168'], cwd=root,
                                       timeout=BUILD_TIMEOUT_SECONDS, environment=environment)
        if result.timed_out:
            code = 124
        else:
            code = result.exit_code
            if type(code) is not int:
                raise RuntimeError('Contained Build did not report an exit code')
        if code == 0 and target is not None:
            candidate = Path(target['OOS_LYRA_CANDIDATE'])
            session.publish(target['OOS_LYRA_REQUEST'], candidate,
                            candidate.parent / 'oos168x.build.json')
    except BaseException as original:
        try:
            session.release()
        except BaseException as cleanup:
            raise original from cleanup
        raise
    session.release()
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--engine", type=Path)
    parser.add_argument("--producer-identity", type=Path)
    parser.add_argument("--macos-profile", type=Path)
    parser.add_argument("--macos-profile-sha256")
    args = parser.parse_args(argv)
    try:
        return build_project(args.project, request=args.request, candidate=args.candidate,
                             engine=args.engine, producer_identity=args.producer_identity,
                             macos_profile=args.macos_profile,
                             macos_profile_sha256=args.macos_profile_sha256)
    except (OSError, ValueError, RuntimeError, configparser.Error) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
