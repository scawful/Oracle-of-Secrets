"""Managed Build adapter for the pure saved special-overworld compiler.

Only build_rom.sh selects this adapter through lyra_native_loaders.py. The
source ROM is never written; the existing Build transaction owns generated
cache files and restores the previous output set if a stage fails.
"""
from __future__ import annotations

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


def _export_source(rom, command):
    resolved = shutil.which(command or 'z3ed')
    native.require(resolved is not None,
                   'Native resource compilation requires z3ed; none found on PATH, '
                   'in the Yaze Nightly bundle or ~/.local/yaze. '
                   'Set OOS_Z3ED_BIN to a z3ed binary')
    result = subprocess.run([resolved, 'overworld-export-native-source', '--rom',
                             str(rom.resolve()), '--format', 'json'],
                            capture_output=True, text=True, timeout=120)
    native.require(result.returncode == 0,
                   f'Native source export failed ({result.returncode}): '
                   + (result.stderr + result.stdout)[-4000:])
    # Native z3ed may print INFO lines before its JSON object. Preserve strict
    # JSON parsing after that prefix; never accept a partial trailing object.
    first = result.stdout.find('{')
    native.require(first >= 0, 'Native source export did not return JSON')
    return json.loads(result.stdout[first:])


def _preparation(source, exported):
    first, size = native.RESIDENT_DATA_PC, native.RESIDENT_DATA_CAPACITY
    return compiler.prepare_revision4_compilation(source, exported,
        data_pc=first, capacity=size, preimage=source[first:first + size])


def _constants(source, prepared):
    # The source descriptor selects this composition. These flags do not
    # alter defaults for a legacy ROM or grant Main/runtime publication.
    return (native.native_reader_constants(source)
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
            exported = _export_source(args.rom, args.z3ed)
            prepared = _preparation(source, exported)
            native.require(args.rom.read_bytes() == source,
                           'Saved native ROM changed during resource preparation')
            _write_generated(args.constants, _constants(source, prepared).encode(), args.rom)
            _write_generated(cache / BINARY_FILE, prepared['binary'], args.rom)
            _write_generated(data_path, prepared['data_asm'].encode(), args.rom)
            _write_generated(export_path, (json.dumps(exported) + '\n').encode(), args.rom)
            _remove_generated(cache / DIRECTORY_FILE, args.rom)
            print(f'Native resources: {len(prepared["resident_abi"]["areas"])} areas, '
                  f'{prepared["emission"]["used_extent_bytes"]} derived bytes')
            return 0

        exported = json.loads(export_path.read_text())
        symbols = _symbols(args.symbols)
        output_path = args.seal_compiled if args.seal_compiled is not None else args.compiled
        native.require(output_path.resolve() != args.rom.resolve(),
                       'Native compiled output must not alias its editable source')
        compiled = output_path.read_bytes()
        if args.seal_compiled is not None:
            result = compiler.plan_revision4_compiled_seal(
                source, exported, compiled, symbols, allow_stale_directory=True)
            prepared = _preparation(source, exported)
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
            compiler.verify_revision4_compiled_output(source, exported, compiled, symbols)
        native.require(args.rom.read_bytes() == source,
                       'Saved native ROM changed during assembly')
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Native special overworld Build: {error}', file=sys.stderr)
        return 1
