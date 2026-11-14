"""Managed Build adapter for the pure saved special-overworld compiler.

Only build_rom.sh selects this adapter through lyra_native_loaders.py. The
source ROM is never written; the existing Build transaction owns generated
cache files and restores the previous output set if a stage fails.
"""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import lyra_native_loaders as native
import special_overworld_native_build as compiler


EXPORT_FILE = 'special_overworld_native_source.json'
DATA_FILE = 'special_overworld_native_data.asm'
BINARY_FILE = 'binaries/resident-atlas.bin'
DIRECTORY_FILE = 'binaries/special-overworld-directory.bin'
BUILD_ROOT = Path(__file__).resolve().parents[2]


def _write_generated(path, raw, source_path):
    native.require_generated_output(path, source_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _remove_generated(path, source_path):
    native.require_generated_output(path, source_path)
    path.unlink(missing_ok=True)


def _export_source(rom, command, project_context=None, *, experimental_page_tile16=False):
    resolved = shutil.which(command or 'z3ed')
    native.require(resolved is not None,
                   'Native resource compilation requires z3ed; none found on PATH, '
                   'in the Yaze Nightly bundle or ~/.local/yaze. '
                   'Set OOS_Z3ED_BIN to a z3ed binary')
    arguments = [resolved, 'overworld-export-native-source', '--rom',
                 str(rom.resolve()), '--format', 'json']
    if project_context is not None:
        arguments.extend(['--project-context', str(project_context.resolve())])
    if experimental_page_tile16:
        arguments.append('--experimental-page-tile16')
    result = subprocess.run(arguments,
                            capture_output=True, text=True, timeout=120)
    native.require(result.returncode == 0,
                   f'Native source export failed ({result.returncode}): '
                   + (result.stderr + result.stdout)[-4000:])
    # Native z3ed may print INFO lines before its JSON object. Preserve strict
    # JSON parsing after that prefix; never accept a partial trailing object.
    first = result.stdout.find('{')
    native.require(first >= 0, 'Native source export did not return JSON')
    return json.loads(result.stdout[first:])


def _graphics_root(project_context, exported):
    """Bind exported source provenance to the actual selected project source."""
    native.require(type(exported) is dict and type(exported.get('native_source')) is dict,
                   'Native source export did not return a source object')
    binding = exported['native_source'].get('graphics_source')
    if project_context is None:
        native.require(binding is None,
                       'Source-backed graphics require the selected project context')
        return None
    project = project_context.resolve(strict=True)
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(project.read_text())
    spec = config.get('graphics_sheets', 'source_spec', fallback='')
    spec_sha1 = config.get('graphics_sheets', 'source_spec_sha1', fallback='')
    if not spec and not spec_sha1:
        native.require(binding is None, 'Export has unselected graphics source')
        return None
    native.require(isinstance(binding, dict)
                   and spec in ('Data/graphics/source_sprite_sheets.json',
                                'Data/graphics/d4_zora_sprite_sheets.json')
                   and binding.get('spec') == spec
                   and binding.get('spec_sha1') == spec_sha1,
                   'Export graphics source does not match the selected project')
    folder = config.get('files', 'code_folder', fallback='')
    native.require(bool(folder), 'Source-backed graphics require project code_folder')
    root = (project.parent / folder).resolve(strict=True)
    native.require(root.is_dir(), 'Project graphics code_folder is not a directory')
    native.require(root == BUILD_ROOT.resolve(),
                   'Project graphics code_folder must match the source being built')
    return root


def _preparation(source, exported, graphics_root=None, *, experimental_page_tile16=False):
    first, size = native.RESIDENT_DATA_PC, native.RESIDENT_DATA_CAPACITY
    return compiler.prepare_native_compilation(source, exported,
        data_pc=first, capacity=size, preimage=source[first:first + size],
        graphics_root=graphics_root, experimental_page_tile16=experimental_page_tile16)


def _constants(source, prepared, *, experimental_page_tile16=False):
    # The source descriptor selects this composition. These flags do not
    # alter defaults for a legacy ROM or grant Main/runtime publication.
    text = (native.native_reader_constants(
        source, experimental_page_tile16=experimental_page_tile16)
        + '!SPECIAL_OVERWORLD_NATIVE_COMPILED = 1\n'
        + '!SPECIAL_OVERWORLD_RESIDENT_ENABLED = 1\n'
        + '!SPECIAL_OVERWORLD_RESOURCES_ENABLED = 1\n'
        + '!SPECIAL_OVERWORLD_PALETTE_ENABLED = 1\n'
        + f'!LYRA_CURRENT_RESIDENT_CODE_BASE = ${native.RESIDENT_WORD_CODE_BASE:06X}\n'
        + f'!LYRA_CURRENT_RESIDENT_CODE_END = ${native.RESIDENT_WORD_CODE_LIMIT:06X}\n'
        + f'!SPECIAL_OVERWORLD_RESOURCE_CODE_BASE = ${native.RESIDENT_RESOURCE_CODE_BASE:06X}\n'
        + f'!SPECIAL_OVERWORLD_RESOURCE_CODE_END = ${native.RESIDENT_RESOURCE_CODE_LIMIT:06X}\n'
        + f'!SPECIAL_OVERWORLD_PALETTE_CODE_BASE = ${native.RESIDENT_PALETTE_CODE_BASE:06X}\n'
        + f'!SPECIAL_OVERWORLD_PALETTE_CODE_END = ${native.RESIDENT_PALETTE_CODE_LIMIT:06X}\n'
        + prepared['constants_asm'])
    if experimental_page_tile16:
        first = native.pc(native.SEMANTIC_CODE_BASE)
        end = native.pc(native.SEMANTIC_CODE_LIMIT - 1) + 1
        text += native.semantic_reader_constants(source, code_preimage=source[first:end],
            experimental_page_tile16=True)
        text += '!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 1\n'
    return text


def _symbols(path):
    native.require(path is not None and path.is_file(),
                   'Native resource compilation requires fresh assembler symbols')
    # Reuse the maintained WLA parser used by the normal symbol-export stage.
    from export_symbols import parse_wla_symbols
    symbols = {}
    for symbol in parse_wla_symbols(path):
        address = symbol.full_address
        native.require(symbol.name not in symbols or symbols[symbol.name] == address,
                       f'Ambiguous native compiler symbol: {symbol.name}')
        symbols[symbol.name] = address
    return symbols


def run_native_build_stage(args, source):
    """Prepare, seal or validate within the caller's managed transaction."""
    try:
        experimental = getattr(args, 'experimental_page_tile16', False)
        native.require(type(experimental) is bool, 'Expected explicit experimental admission')
        if experimental:
            native.require(getattr(args, 'project_context', None) is not None,
                           'Experimental native Build requires the selected project context')
            installed = native.read_native_directory(source, experimental_page_tile16=True)
            native.require(installed is not None and int.from_bytes(source[
                native.DIRECTORY_PC + 8:native.DIRECTORY_PC + 10], 'little') == 5,
                'Experimental native Build requires revision5 source; no upgrade is performed')
        cache = args.build_cache
        native.require(not cache.is_symlink(), 'Native Build cache cannot be a symlink')
        binaries = cache / 'binaries'
        native.require(not binaries.is_symlink(), 'Native Build binary cache cannot be a symlink')
        for name in ('special_overworld_reader_constants.asm', EXPORT_FILE, DATA_FILE,
                     BINARY_FILE, DIRECTORY_FILE):
            native.require_generated_output(cache / name, args.rom)
        export_path, data_path = cache / EXPORT_FILE, cache / DATA_FILE
        if args.constants is not None:
            native.require(args.constants.resolve() == (
                cache / 'special_overworld_reader_constants.asm').resolve(),
                'Native reader constants must use the managed Build cache')
            context = getattr(args, 'project_context', None)
            exported = (_export_source(args.rom, args.z3ed, context,
                experimental_page_tile16=True) if experimental else
                _export_source(args.rom, args.z3ed, context))
            root = _graphics_root(context, exported)
            prepared = _preparation(source, exported, root, experimental_page_tile16=experimental)
            native.require(args.rom.read_bytes() == source,
                           'Saved native ROM changed during resource preparation')
            _write_generated(args.constants, _constants(source, prepared, experimental_page_tile16=experimental).encode(), args.rom)
            _write_generated(cache / BINARY_FILE, prepared['binary'], args.rom)
            _write_generated(data_path, prepared['data_asm'].encode(), args.rom)
            _write_generated(export_path, (json.dumps(exported) + '\n').encode(), args.rom)
            _remove_generated(cache / DIRECTORY_FILE, args.rom)
            print(f'Native resources: {len(prepared["resident_abi"]["areas"])} areas, '
                  f'{prepared["emission"]["used_extent_bytes"]} derived bytes')
            return 0

        exported = json.loads(export_path.read_text())
        root = _graphics_root(getattr(args, 'project_context', None), exported)
        symbols = _symbols(args.symbols)
        output_path = args.seal_compiled if args.seal_compiled is not None else args.compiled
        native.require(output_path.resolve() != args.rom.resolve(),
                       'Native compiled output must not alias its editable source')
        compiled = output_path.read_bytes()
        if args.seal_compiled is not None:
            result = compiler.plan_native_compiled_seal(
                source, exported, compiled, symbols, allow_stale_directory=True,
                graphics_root=root, experimental_page_tile16=experimental,
                semantic_readers=experimental)
            prepared = _preparation(source, exported, root, experimental_page_tile16=experimental)
            data = prepared['data_asm']
            if result['needed_reassembly']:
                _write_generated(cache / DIRECTORY_FILE, result['directory_bytes'], args.rom)
                data += (f'\npushpc\norg $28F000\n'
                         f'SpecialOverworldNativeDirectory:\n'
                         f'incbin "{DIRECTORY_FILE}"\n'
                         f'SpecialOverworldNativeDirectoryEnd:\n'
                         f'assert pc() == $28F400\npullpc\n')
            else:
                _remove_generated(cache / DIRECTORY_FILE, args.rom)
            _write_generated(data_path, data.encode(), args.rom)
        else:
            compiler.verify_native_compiled_output(source, exported, compiled, symbols,
                graphics_root=root, experimental_page_tile16=experimental,
                semantic_readers=experimental)
        native.require(args.rom.read_bytes() == source,
                       'Saved native ROM changed during assembly')
        return 0
    except (ValueError, OSError, configparser.Error, subprocess.SubprocessError) as error:
        print(f'Native special overworld Build: {error}', file=sys.stderr)
        return 1
