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

    for pre in test.get('preconditions', []):
        addr = pre['address']
        expected = pre['equals']
        desc = pre.get('description', addr)

        success, output = mesen_cmd('read', addr)
        if not success:
            errors.append(f"Failed to read {addr}: {output}")
            continue

        actual = parse_mesen_value(output)
        if actual is None:
            errors.append(f"Could not parse value for {addr}: {output}")
            continue

        if actual != expected:
            errors.append(f"Precondition failed: {desc} (expected {expected}, got {actual})")
        elif verbose:
            log(f"  ✓ {desc}: {actual}", Colors.GREEN)

    return len(errors) == 0, errors

def execute_step(step: dict, verbose: bool = False) -> tuple[bool, str]:
    """Execute a single test step. Returns (passed, message)."""
    step_type = step['type']

    if step_type == 'press':
        button = step['button']
        frames = step.get('frames', 5)
        success, output = mesen_cmd('press', button, frames)
        if verbose:
            log(f"  → Press {button} ({frames} frames)", Colors.BLUE)
        return success, output

    elif step_type == 'wait':
        ms = step.get('ms', 100)
        if verbose:
            log(f"  → Wait {ms}ms", Colors.BLUE)
        time.sleep(ms / 1000.0)
        return True, f"Waited {ms}ms"

    elif step_type == 'assert':
        addr = step['address']
        desc = step.get('description', f"Check {addr}")

        success, output = mesen_cmd('read', addr)
        if not success:
            return False, f"Failed to read {addr}: {output}"

        actual = parse_mesen_value(output)
        if actual is None:
            return False, f"Could not parse value for {addr}: {output}"

        # Check condition
        if 'equals' in step:
            expected = step['equals']
            if actual == expected:
                if verbose:
                    log(f"  ✓ {desc}: {actual} == {expected}", Colors.GREEN)
                return True, f"{desc}: PASS"
            else:
                return False, f"{desc}: expected {expected}, got {actual}"

        elif 'in' in step:
            valid_values = step['in']
            if actual in valid_values:
                if verbose:
                    log(f"  ✓ {desc}: {actual} in {valid_values}", Colors.GREEN)
                return True, f"{desc}: PASS"
            else:
                return False, f"{desc}: {actual} not in {valid_values}"

        elif 'not_equals' in step:
            invalid = step['not_equals']
            if actual != invalid:
                if verbose:
                    log(f"  ✓ {desc}: {actual} != {invalid}", Colors.GREEN)
                return True, f"{desc}: PASS"
            else:
                return False, f"{desc}: got {actual} (should not equal)"

    elif step_type == 'screenshot':
        path = step.get('path', '')
        success, output = mesen_cmd('screenshot', path)
        if verbose:
            log(f"  → Screenshot: {output}", Colors.BLUE)
        return success, output

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
             skip_preconditions: bool = False) -> bool:
    """Run a single test file. Returns True if passed."""

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
        return True

    # Check bridge connection
    log("\nChecking bridge connection...")
    success, output = mesen_cmd('ping')
    if not success:
        log(f"{Colors.RED}Bridge not connected: {output}{Colors.RESET}")
        log("Start Mesen2 with bridge script loaded first.")
        return False
    log(f"{Colors.GREEN}Bridge connected{Colors.RESET}")

    # Check preconditions
    if not skip_preconditions:
        log("\nChecking preconditions...")
        passed, errors = check_preconditions(test, verbose)
        if not passed:
            log(f"\n{Colors.RED}Preconditions not met:{Colors.RESET}")
            for err in errors:
                log(f"  • {err}", Colors.RED)
            log(f"\nLoad save state: {test['saveState']['category']}/{test['saveState']['file']}")
            return False
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

            return False

    log(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
    log(f"{Colors.GREEN}TEST PASSED: {test['name']}{Colors.RESET}")
    log(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Oracle of Secrets Test Runner')
    parser.add_argument('tests', nargs='+', help='Test JSON files to run')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show steps without executing')
    parser.add_argument('--skip-preconditions', action='store_true',
                        help='Skip precondition checks')
    args = parser.parse_args()

    passed = 0
    failed = 0

    for test_pattern in args.tests:
        test_path = Path(test_pattern)
        if test_path.is_file():
            if run_test(test_path, args.verbose, args.dry_run, args.skip_preconditions):
                passed += 1
            else:
                failed += 1
        else:
            # Glob pattern
            for p in Path('.').glob(test_pattern):
                if p.suffix == '.json':
                    if run_test(p, args.verbose, args.dry_run, args.skip_preconditions):
                        passed += 1
                    else:
                        failed += 1

    # Summary
    log(f"\n{'='*60}")
    log(f"Results: {passed} passed, {failed} failed")
    log(f"{'='*60}")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
