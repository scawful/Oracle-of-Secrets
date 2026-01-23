#!/usr/bin/env python3
"""
Test runner for Oracle of Secrets with MoE orchestrator integration.

Executes test definitions and routes failures to specialized Triforce models.

Usage:
    ./scripts/test_runner.py tests/lr_swap_test.json
    ./scripts/test_runner.py tests/*.json --verbose
    ./scripts/test_runner.py tests/lr_swap_test.json --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(msg: str, color: str = ''):
    """Print colored log message."""
    print(f"{color}{msg}{Colors.RESET}")

def mesen_cmd(cmd: str, *args, timeout: float = 2.0) -> tuple[bool, str]:
    """Execute mesen_cli.sh command and return (success, output)."""
    script_dir = Path(__file__).parent
    cli_path = script_dir / "mesen_cli.sh"

    try:
        result = subprocess.run(
            [str(cli_path), cmd, *[str(a) for a in args]],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=script_dir.parent
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def run_yabai(action: str, *args: str) -> None:
    script_path = Path(__file__).parent / "yabai_mesen_window.sh"
    if not script_path.exists():
        return
    cmd = [str(script_path), action, *[str(a) for a in args if a]]
    try:
        subprocess.run(cmd, timeout=2, check=False)
    except Exception:
        pass


def normalize_addr(addr: Any) -> str:
    if isinstance(addr, str):
        addr = addr.strip()
        if addr.startswith("$"):
            addr = "0x" + addr[1:]
        return addr
    return str(addr)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("$"):
            s = "0x" + s[1:]
        base = 16 if s.lower().startswith("0x") else 10
        try:
            return int(s, base)
        except ValueError:
            return None
    return None


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def resolve_save_state(save_state: Any, repo_root: Path, manifest_path: Path) -> dict | None:
    if not save_state:
        return None

    if isinstance(save_state, str):
        save_state = {"path": save_state}
    elif not isinstance(save_state, dict):
        raise ValueError("saveState must be a string or object")

    manifest = load_manifest(manifest_path)
    library_root = save_state.get("libraryRoot") or manifest.get("library_root") or "Roms/SaveStates/library"

    wait_seconds = save_state.get("waitSeconds")
    if wait_seconds is None:
        wait_seconds = save_state.get("wait_seconds")
    if wait_seconds is None:
        wait_seconds = save_state.get("wait")
    wait_seconds = float(wait_seconds) if wait_seconds is not None else 10.0

    reload_caches = bool(save_state.get("reloadCaches") or save_state.get("reload_caches"))
    allow_missing = bool(save_state.get("allowMissing") or save_state.get("skipMissing"))

    state_path = None
    warning = None
    if "id" in save_state:
        state_id = save_state.get("id")
        entries = manifest.get("entries", []) if manifest else []
        found = False
        for entry in entries:
            if entry.get("id") == state_id:
                state_path = entry.get("state_path")
                found = True
                break
        if not found:
            warning = f"saveState id not found in manifest: {state_id}"
    elif "path" in save_state:
        state_path = save_state.get("path")
    elif "category" in save_state and "file" in save_state:
        state_path = str(Path(save_state["category"]) / save_state["file"])

    if state_path:
        path_obj = Path(str(state_path)).expanduser()
        if not path_obj.is_absolute():
            candidate = repo_root / path_obj
            if candidate.exists():
                path_obj = candidate
            else:
                path_obj = (repo_root / library_root / path_obj)
        return {
            "kind": "path",
            "path": path_obj,
            "wait_seconds": wait_seconds,
            "reload_caches": reload_caches,
            "allow_missing": allow_missing,
            "warning": warning,
        }

    slot = save_state.get("slot")
    if slot is not None:
        return {
            "kind": "slot",
            "slot": parse_int(slot),
            "wait_seconds": wait_seconds,
            "reload_caches": reload_caches,
            "allow_missing": allow_missing,
            "warning": warning,
        }

    if warning:
        return {
            "kind": "missing",
            "reason": warning,
            "allow_missing": allow_missing,
        }

    return None


def normalize_preconditions(test: dict) -> list[dict]:
    pre = test.get("preconditions", [])
    if isinstance(pre, dict):
        normalized = []
        for addr, cond in pre.items():
            entry = {"address": addr}
            if isinstance(cond, dict):
                entry.update(cond)
            else:
                entry["equals"] = cond
            if "desc" in entry and "description" not in entry:
                entry["description"] = entry["desc"]
            normalized.append(entry)
        return normalized
    if isinstance(pre, list):
        for entry in pre:
            if "desc" in entry and "description" not in entry:
                entry["description"] = entry["desc"]
        return pre
    return []


def parse_condition(step: dict) -> tuple[str | None, Any, list[Any] | None]:
    condition = step.get("condition")
    expected = None
    values = None

    if condition:
        condition = str(condition).lower()
        if condition == "in":
            values = step.get("values", step.get("in"))
        else:
            expected = step.get("value", step.get("equals", step.get("expected")))
    else:
        if "equals" in step:
            condition = "equals"
            expected = step.get("equals")
        elif "in" in step:
            condition = "in"
            values = step.get("in")
        elif "not_equals" in step:
            condition = "not_equals"
            expected = step.get("not_equals")

    return condition, expected, values


def evaluate_condition(actual: int, condition: str, expected: Any, values: list[Any] | None) -> tuple[bool, str]:
    if condition == "equals":
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual == exp, f"{actual} == {exp}"
    if condition == "not_equals":
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual != exp, f"{actual} != {exp}"
    if condition == "in":
        vals = values or []
        parsed = [parse_int(v) for v in vals]
        parsed = [v for v in parsed if v is not None]
        if not parsed:
            return False, "Invalid expected list"
        return actual in parsed, f"{actual} in {parsed}"
    return False, f"Unknown condition: {condition}"


def normalize_state_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return "bool", value
    if isinstance(value, (int, float)):
        return "int", int(value)
    if value is None:
        return "none", ""
    return "str", str(value)

def parse_mesen_value(output: str) -> int | None:
    """Parse value from mesen_cli.sh read output."""
    # Format: "READ:0x7E0739=0x02 (2)"
    try:
        if '=' in output and '0x' in output:
            hex_part = output.split('=')[1].split()[0]
            return int(hex_part, 16)
    except (IndexError, ValueError):
        pass
    return None

def check_preconditions(test: dict, verbose: bool = False) -> tuple[bool, list[str]]:
    """Check all preconditions are met. Returns (passed, errors)."""
    errors = []

    for pre in normalize_preconditions(test):
        addr = normalize_addr(pre.get("address"))
        desc = pre.get('description', addr)

        condition, expected, values = parse_condition(pre)
        if not condition:
            errors.append(f"Missing condition for {addr}")
            continue

        success, output = mesen_cmd('read', addr)
        if not success:
            errors.append(f"Failed to read {addr}: {output}")
            continue

        actual = parse_mesen_value(output)
        if actual is None:
            errors.append(f"Could not parse value for {addr}: {output}")
            continue

        ok, detail = evaluate_condition(actual, condition, expected, values)
        if not ok:
            errors.append(f"Precondition failed: {desc} ({detail})")
        elif verbose:
            log(f"  ✓ {desc}: {detail}", Colors.GREEN)

    return len(errors) == 0, errors

def execute_step(step: dict, verbose: bool = False) -> tuple[bool, str]:
    """Execute a single test step. Returns (passed, message)."""
    step_type = step['type']

    if step_type == 'press':
        button = step['button']
        frames = step.get('frames', 5)
        success, output = mesen_cmd('press', button, frames, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Press {button} ({frames} frames)", Colors.BLUE)
        return success, output

    elif step_type == 'wait':
        seconds = step.get('seconds')
        if seconds is None:
            ms = step.get('ms', 100)
            seconds = ms / 1000.0
        if verbose:
            log(f"  → Wait {seconds:.3f}s", Colors.BLUE)
        time.sleep(float(seconds))
        return True, f"Waited {seconds:.3f}s"

    elif step_type == 'assert':
        addr = normalize_addr(step['address'])
        desc = step.get('description', step.get('desc', f"Check {addr}"))

        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for {addr}"

        success, output = mesen_cmd('read', addr, timeout=step.get("timeout", 2.0))
        if not success:
            return False, f"Failed to read {addr}: {output}"

        actual = parse_mesen_value(output)
        if actual is None:
            return False, f"Could not parse value for {addr}: {output}"

        ok, detail = evaluate_condition(actual, condition, expected, values)
        if ok:
            if verbose:
                log(f"  ✓ {desc}: {detail}", Colors.GREEN)
            return True, f"{desc}: PASS"
        return False, f"{desc}: {detail}"

    elif step_type == 'screenshot':
        path = step.get('path', '')
        success, output = mesen_cmd('screenshot', path, timeout=step.get("timeout", 4.0))
        if verbose:
            log(f"  → Screenshot: {output}", Colors.BLUE)
        return success, output
    elif step_type == "write":
        addr = normalize_addr(step["address"])
        value = step.get("value", step.get("equals"))
        if value is None:
            return False, f"Missing value for write to {addr}"
        success, output = mesen_cmd('write', addr, value, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Write {addr} = {value}", Colors.BLUE)
        return success, output
    elif step_type == "write16":
        addr = normalize_addr(step["address"])
        value = step.get("value", step.get("equals"))
        if value is None:
            return False, f"Missing value for write16 to {addr}"
        success, output = mesen_cmd('write16', addr, value, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Write16 {addr} = {value}", Colors.BLUE)
        return success, output
    elif step_type == "command":
        cmd = step.get("command")
        args = step.get("args", [])
        if not cmd:
            return False, "Missing command in command step"
        success, output = mesen_cmd(cmd, *args, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Command {cmd} {args}", Colors.BLUE)
        return success, output
    elif step_type in ("wait_addr", "wait-address"):
        addr = normalize_addr(step.get("address"))
        desc = step.get('description', step.get('desc', f"Wait for {addr}"))
        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for {addr}"
        timeout = float(step.get("timeout", 5.0))
        interval = float(step.get("interval", 0.1))
        start = time.time()
        while True:
            success, output = mesen_cmd('read', addr, timeout=step.get("readTimeout", 2.0))
            if success:
                actual = parse_mesen_value(output)
                if actual is not None:
                    ok, detail = evaluate_condition(actual, condition, expected, values)
                    if ok:
                        if verbose:
                            log(f"  ✓ {desc}: {detail}", Colors.GREEN)
                        return True, f"{desc}: PASS"
            if time.time() - start >= timeout:
                return False, f"{desc}: timeout after {timeout}s"
            time.sleep(interval)
    elif step_type in ("wait_state", "wait-state"):
        key = step.get("key") or step.get("field")
        if not key:
            return False, "Missing key for wait_state"
        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for state.{key}"
        timeout = float(step.get("timeout", 5.0))
        interval = float(step.get("interval", 0.2))
        start = time.time()
        while True:
            success, output = mesen_cmd('state', timeout=step.get("readTimeout", 2.0))
            if success and output:
                try:
                    state = json.loads(output)
                except json.JSONDecodeError:
                    state = None
                if state is not None:
                    value = state.get(key)
                    kind, actual = normalize_state_value(value)
                    if kind in ("int", "bool"):
                        actual_int = int(actual)
                        ok, detail = evaluate_condition(actual_int, condition, expected, values)
                    else:
                        if condition == "equals":
                            ok = str(actual) == str(expected)
                            detail = f"{actual} == {expected}"
                        elif condition == "not_equals":
                            ok = str(actual) != str(expected)
                            detail = f"{actual} != {expected}"
                        elif condition == "in":
                            vals = [str(v) for v in (values or [])]
                            ok = str(actual) in vals
                            detail = f"{actual} in {vals}"
                        else:
                            ok = False
                            detail = "Unknown condition"
                    if ok:
                        if verbose:
                            log(f"  ✓ state.{key}: {detail}", Colors.GREEN)
                        return True, f"state.{key}: PASS"
            if time.time() - start >= timeout:
                return False, f"state.{key}: timeout after {timeout}s"
            time.sleep(interval)

    else:
        return False, f"Unknown step type: {step_type}"

    return True, "OK"

def route_to_expert(failure_info: dict, test: dict, verbose: bool = False) -> str:
    """Route failure to MoE orchestrator for analysis."""
    on_failure = test.get('onFailure', {})
    expert = on_failure.get('expert', 'farore')
    context = on_failure.get('context', 'Test failed')

    # Build prompt for orchestrator
    prompt = f"""Test Failure Analysis Request

Test: {test['name']}
Description: {test.get('description', 'N/A')}

Failure: {failure_info.get('message', 'Unknown')}
Step: {failure_info.get('step', 'N/A')}

Context: {context}

Please analyze this failure and suggest potential fixes."""

    log(f"\n{Colors.YELLOW}Routing to {expert} for analysis...{Colors.RESET}")

    # Try to call MoE orchestrator
    orchestrator_path = Path.home() / "src/lab/afs/tools/moe_orchestrator.py"
    if orchestrator_path.exists():
        try:
            result = subprocess.run(
                ["python3", str(orchestrator_path), "--force", expert, "--prompt", prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Orchestrator error: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "Orchestrator timed out"
        except Exception as e:
            return f"Failed to call orchestrator: {e}"
    else:
        return f"Orchestrator not found at {orchestrator_path}. Manual analysis needed:\n{prompt}"

def run_test(test_path: Path, verbose: bool = False, dry_run: bool = False,
             skip_preconditions: bool = False, skip_load: bool = False,
             skip_missing_state: bool = False) -> str:
    """Run a single test file. Returns 'passed', 'failed', or 'skipped'."""

    with open(test_path) as f:
        test = json.load(f)

    log(f"\n{'='*60}", Colors.BOLD)
    log(f"Test: {test['name']}", Colors.BOLD)
    log(f"{'='*60}")
    log(f"Description: {test.get('description', 'N/A')}")

    if dry_run:
        log(f"\n{Colors.YELLOW}[DRY RUN] Would execute {len(test.get('steps', []))} steps{Colors.RESET}")
        for i, step in enumerate(test.get('steps', []), 1):
            log(f"  {i}. {step['type']}: {step.get('description', step)}")
        return "passed"

    # Bring Mesen to front when tests start (optional)
    if os.environ.get("MESEN_AUTO_FOCUS", "1") not in ("0", "false", "False"):
        script_path = Path(__file__).parent / "yabai_mesen_window.sh"
        if script_path.exists():
            try:
                subprocess.run([str(script_path), "show"], timeout=2, check=False)
            except Exception:
                pass

    # Check bridge connection
    log("\nChecking bridge connection...")
    success, output = mesen_cmd('ping')
    if not success:
        log(f"{Colors.RED}Bridge not connected: {output}{Colors.RESET}")
        log("Start Mesen2 with bridge script loaded first.")
        return "failed"
    log(f"{Colors.GREEN}Bridge connected{Colors.RESET}")

    # Load save state (optional)
    if not skip_load and test.get("saveState"):
        try:
            repo_root = Path(__file__).parent.parent
            manifest_path = repo_root / "Docs" / "Testing" / "save_state_library.json"
            resolved = resolve_save_state(test.get("saveState"), repo_root, manifest_path)
        except Exception as exc:
            log(f"{Colors.RED}Invalid saveState: {exc}{Colors.RESET}")
            return "failed"

        if resolved:
            if resolved.get("warning"):
                log(f"{Colors.YELLOW}{resolved['warning']} (using fallback){Colors.RESET}")
            if resolved["kind"] == "missing":
                msg = resolved.get("reason", "Save state missing")
                if skip_missing_state or resolved.get("allow_missing"):
                    log(f"{Colors.YELLOW}{msg} (skipping){Colors.RESET}")
                    return "skipped"
                log(f"{Colors.RED}{msg}{Colors.RESET}")
                return "failed"
            if resolved["kind"] == "path":
                state_path = resolved["path"]
                if not state_path.exists():
                    msg = f"Save state not found: {state_path}"
                    if skip_missing_state or resolved.get("allow_missing"):
                        log(f"{Colors.YELLOW}{msg} (skipping){Colors.RESET}")
                        return "skipped"
                    log(f"{Colors.RED}{msg}{Colors.RESET}")
                    return "failed"
                log(f"\nLoading save state: {state_path}")
                success, output = mesen_cmd("loadstate", str(state_path), timeout=4.0)
                if not success:
                    log(f"{Colors.RED}Loadstate failed: {output}{Colors.RESET}")
                    return "failed"
            elif resolved["kind"] == "slot":
                slot = resolved.get("slot")
                if not slot:
                    log(f"{Colors.RED}Invalid saveState slot{Colors.RESET}")
                    return "failed"
                log(f"\nLoading save slot: {slot}")
                success, output = mesen_cmd("loadslot", str(slot), timeout=4.0)
                if not success:
                    log(f"{Colors.RED}Loadslot failed: {output}{Colors.RESET}")
                    return "failed"

            if resolved.get("wait_seconds", 0) > 0:
                success, output = mesen_cmd("wait-load", str(int(resolved["wait_seconds"])), timeout=resolved["wait_seconds"] + 2)
                if not success:
                    log(f"{Colors.RED}Wait-load failed: {output}{Colors.RESET}")
                    return "failed"

            if resolved.get("reload_caches"):
                log("Reloading runtime caches (L+R+Select+Start)...")
                # Hotkey: L+R+Select+Start
                mesen_cmd("press", "L+R+SELECT+START", 5, timeout=2.0)
                time.sleep(0.2)

    # Check preconditions
    if not skip_preconditions:
        log("\nChecking preconditions...")
        passed, errors = check_preconditions(test, verbose)
        if not passed:
            log(f"\n{Colors.RED}Preconditions not met:{Colors.RESET}")
            for err in errors:
                log(f"  • {err}", Colors.RED)
            log(f"\nLoad save state: {test['saveState']['category']}/{test['saveState']['file']}")
            return "failed"
        log(f"{Colors.GREEN}All preconditions met{Colors.RESET}")

    # Execute steps
    log("\nExecuting test steps...")
    for i, step in enumerate(test.get('steps', []), 1):
        step_desc = step.get('description', step['type'])

        success, message = execute_step(step, verbose)

        if not success:
            log(f"\n{Colors.RED}FAILED at step {i}: {step_desc}{Colors.RESET}")
            log(f"  {message}", Colors.RED)

            # Route to expert
            failure_info = {
                'message': message,
                'step': i,
                'step_desc': step_desc,
                'step_data': step
            }
            analysis = route_to_expert(failure_info, test, verbose)
            log(f"\n{Colors.YELLOW}Expert Analysis:{Colors.RESET}")
            log(analysis)

            return "failed"

    log(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
    log(f"{Colors.GREEN}TEST PASSED: {test['name']}{Colors.RESET}")
    log(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    return "passed"

def main():
    parser = argparse.ArgumentParser(description='Oracle of Secrets Test Runner')
    parser.add_argument('tests', nargs='+', help='Test JSON files to run')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show steps without executing')
    parser.add_argument('--skip-preconditions', action='store_true',
                        help='Skip precondition checks')
    parser.add_argument('--skip-load', action='store_true',
                        help='Skip loading save states')
    parser.add_argument('--skip-missing-state', action='store_true',
                        help='Skip tests when save state files are missing')
    args = parser.parse_args()

    if os.environ.get("MESEN_AUTO_UNSTASH", "1") not in ("0", "false", "False"):
        run_yabai("unstash")

    passed = 0
    failed = 0
    skipped = 0

    for test_pattern in args.tests:
        test_path = Path(test_pattern)
        if test_path.is_file():
            result = run_test(
                test_path,
                args.verbose,
                args.dry_run,
                args.skip_preconditions,
                args.skip_load,
                args.skip_missing_state,
            )
            if result == "passed":
                passed += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1
        else:
            # Glob pattern
            for p in Path('.').glob(test_pattern):
                if p.suffix == '.json':
                    result = run_test(
                        p,
                        args.verbose,
                        args.dry_run,
                        args.skip_preconditions,
                        args.skip_load,
                        args.skip_missing_state,
                    )
                    if result == "passed":
                        passed += 1
                    elif result == "skipped":
                        skipped += 1
                    else:
                        failed += 1

    # Summary
    log(f"\n{'='*60}")
    log(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    log(f"{'='*60}")

    if os.environ.get("MESEN_STASH_ON_FAIL", "0") not in ("0", "false", "False"):
        if failed > 0:
            scratch = os.environ.get("SCRATCH_SPACE", "")
            if scratch:
                run_yabai("stash", scratch)
            else:
                run_yabai("hide")
    elif os.environ.get("MESEN_AUTO_STASH", "0") not in ("0", "false", "False"):
        scratch = os.environ.get("SCRATCH_SPACE", "")
        if scratch:
            run_yabai("stash", scratch)
        else:
            run_yabai("hide")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
