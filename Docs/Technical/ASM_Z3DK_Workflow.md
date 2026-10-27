# Oracle ASM and z3dk workflow

Reviewed 2026-10-27 against Oracle's build scripts and the sibling z3dk
`config.cc`, `lint.cc`, `z3asm_main.cc`, `src/z3lsp/main.cc`, and VS Code extension.
This guide describes tool contracts, not gameplay qualification.

## Sources of truth

| Question | Owning source |
|---|---|
| What code is included? | `Oracle_main.asm`, then literal `incsrc` edges and their feature conditions |
| What does a macro change? | `Core/sprite_macros.asm`, `Util/macros.asm`, or the actual defining include |
| Who owns an address? | `Config/allocation_ownership.json`, `Core/ZS ROM MAP.txt`, current source and selected composition |
| What occupies a bank in this build? | Matching ROM, symbols, exact assembler write spans when available, and build receipt |
| What did the checks establish? | The receipt's individual check states and the affected native scenario |

`MemoryMap.md` and architecture diagrams are navigation aids. An old "unused"
label, an all-FF region, or a source label does not allocate space. Preserve
original upstream code and provenance when reviewing ZSCustomOverworld; keep
Oracle extensions near their domain rather than copying another upstream file.

## Build and inspect one candidate

Use an owned source checkout and a private copy of the selected base ROM.
`Roms/oos168.sfc` is editable base input; `Roms/oos168x.sfc` is generated output.

```bash
# Run inside that owned checkout, with its selected base already present.
Scripts/Build/build_rom.sh 168
python3 Scripts/Build/check_zscream_overlap.py
```

The normal entry point records base/source/tool/output identities in
`Roms/oos168x.build.json`. It emits hooks to `Roms/hooks.json`. For z3asm,
`--asar=z3asm` resolves the supported local binary when available. Shell aliases
are not executable-path evidence; use `command -v` in the actual runner shell
or an explicit executable path.

`oos-quick.sh` and `oos-verify.sh` request legacy reset/reload. That operation
requires an explicit `OOS_TEST_SOCKET` already running the exact candidate.
For a build without runtime control use `build_rom.sh`, or
`dev_loop.sh 168 --mesen-sync`. Symbol synchronization is not a gameplay test.

The standalone `z3dk_safe_smoke.sh` assembles a temporary ROM and checks assembly
only. It does not replace the normal receipt, generated-source checks or native
verification. Supply `OOS_BASE_ROM` explicitly when alternate/legacy bases exist.

For an analyzer invocation outside the normal build, bind all three artifacts:

```bash
python3 /path/to/z3dk/scripts/oracle_analyzer.py \
  /path/to/candidate/Roms/oos168x.sfc \
  --sym /path/to/candidate/Roms/oos168x.sym \
  --hooks /path/to/candidate/Roms/hooks.json \
  --check-hooks --find-mx --find-width-imbalance --check-abi \
  --check-sprite-tables --check-phb-plb --check-jsl-targets --check-rtl-rts
```

The analyzer's `--project-root` selects source for `--diff`; it does not infer
the candidate ROM, symbols or hooks. Reuse a matching receipt's analyzer result
instead of running the same analysis again.

## Configuration and editor diagnostics

`z3dk.toml` uses flat keys accepted by `z3dk_core/config.cc`. The parser does not
implement nested `[project.defines]`, `[project.include_paths]`, `[emit]`, or
`[lint.prohibited_memory_ranges]` tables. Recognized leaf keys can appear to
work beneath a header while neighboring keys are silently ignored.

- `defines = ["ORACLE=1"]` and `include_paths = [".", "Core", ...]` are arrays.
- `emit` is an array; Oracle leaves it empty so build callers own output paths.
- LSP warnings use `warn_unknown_width`, `warn_branch_outside_bank`,
  `warn_org_collision`, `warn_stack_balance`, `warn_hook_return`,
  `warn_unauthorized_hook`, and `warn_unused_symbols`.
- Analyzer flags such as `find_mx`, `check_abi`, and `check_sprite_tables` are
  command options for `oracle_analyzer.py`, not z3dk configuration keys.
- The current z3asm CLI lint path forwards only the unused-symbol setting from
  those warning keys. z3lsp forwards the listed warning keys. Do not equate them.

`prohibited_memory_ranges` checks **assembled ROM write blocks**. It does not
inspect runtime `STA`/`STZ` destinations and cannot protect SRAM flag ownership.
Use the allocation ledger and actual consumers for WRAM/SRAM review.
The reviewed parser also drops `$`-prefixed ranges silently; use `0x`-prefixed
addresses for any actual ROM-block exclusions until that parser issue is fixed.

The z3dk extension's default LSP selector includes `asar` and `65816-assembly`,
but not generic `assembly`. Associate Oracle `.asm` files with `asar`, or
explicitly add the desired language to `z3dk.languageIds`. Keep a valid local
`z3dk.serverPath` in machine settings when needed; do not copy one person's
absolute build path into shared project configuration. The extension also
supports `Z3LSP_PATH` and executable discovery.

## Review ASM by its caller contract

At non-obvious hooks/helpers, document entry M/X, DBR/D, return frame, register
and scratch ownership, and intentional result flags. Explain the displaced
instructions and verified continuation address. Do not add boilerplate that
claims preservation the code does not provide.

- `%m8()` / `%m16()` change both A and X/Y; `%a8()` / `%a16()` change A only.
- `PHP` / `PLP` preserve P. They cannot restore index high bytes lost to X=8.
- `PHB : PHK : PLB` selects the code bank for absolute data accesses; use it
  only when required and restore the caller's DBR. Long accesses may need none.
- `pushpc` / `pullpc` manage the assembler position, not the CPU stack.
- Pair the actual call frame with its return, including documented native
  trampolines. `JML` may intentionally retain an earlier JSR return frame.

Use `@hook expected_m=... expected_x=... expected_exit_m=...` only for widths
established from the caller. See the sibling `z3dk/docs/Z3DK_HOOKS.md` for the
current schema. Python source scanning is estimated metadata; exact assembled
spans establish which conditional writes actually occurred. Hook identity and
span checks do not prove an ABI or native behavior by themselves.

## Keep organization useful

1. Keep the include order and allocations stable during unrelated cleanup.
2. Put active behavior in its existing module; separate experimental modules
   with explicit disabled defaults and dependencies.
3. Preserve vendor/upstream sections. Explain Oracle differences at the seam.
4. Prefer labels and short caller contracts over repeated raw-address prose.
5. Keep generated outputs identifiable and regenerate them through their owner;
   avoid hand-editing generated tables or mechanically rewriting all comments.

Follow `AGENTS.md` for proof tiers. A disabled build with zero changed ROM bytes
proves that disabled composition only. Save/shared-hook activation still needs
the relevant independent review and native save/reopen scenario.
