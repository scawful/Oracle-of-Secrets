#!/usr/bin/env python3
"""
AI Patch Generator for Oracle of Secrets

Uses Triforce models via MoE orchestrator to analyze test failures
and generate ASM patch suggestions. Optionally applies via z3ed.

Workflow:
1. Test fails → test_runner.py captures context
2. ai_patch.py routes to appropriate expert (farore/din/nayru/veran)
3. Expert generates ASM code suggestion
4. User reviews and optionally applies via z3ed

Usage:
    ./scripts/ai_patch.py analyze --context "L/R swap not working"
    ./scripts/ai_patch.py suggest --file equipment.asm --issue "toggle logic"
    ./scripts/ai_patch.py apply --patch patches/lr_fix.asm
    ./scripts/ai_patch.py interactive  # Interactive mode
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ORCHESTRATOR_PATH = Path.home() / "src" / "lab" / "afs" / "tools" / "moe_orchestrator.py"
Z3ED_PATH = Path.home() / "src" / "hobby" / "yaze" / "build" / "bin" / "yaze"

# Expert routing for different failure types
EXPERT_ROUTING = {
    "crash": "farore",
    "freeze": "farore",
    "bug": "farore",
    "debug": "farore",
    "performance": "din",
    "optimize": "din",
    "slow": "din",
    "cycles": "din",
    "collision": "veran",
    "register": "veran",
    "hardware": "veran",
    "dma": "veran",
    "code": "nayru",
    "implement": "nayru",
    "sprite": "nayru",
    "routine": "nayru",
}

class PatchSuggestion(NamedTuple):
    """AI-generated patch suggestion."""
    expert: str
    analysis: str
    code: str
    confidence: float
    file_hint: str | None
    line_hint: int | None

def detect_expert(context: str) -> str:
    """Detect which expert to route to based on context."""
    context_lower = context.lower()

    for keyword, expert in EXPERT_ROUTING.items():
        if keyword in context_lower:
            return expert

    # Default to farore (debugging expert)
    return "farore"

def call_orchestrator(prompt: str, expert: str | None = None) -> str:
    """Call MoE orchestrator with prompt."""
    if not ORCHESTRATOR_PATH.exists():
        return f"[Orchestrator not found at {ORCHESTRATOR_PATH}]\n\nManual analysis needed:\n{prompt}"

    cmd = ["python3", str(ORCHESTRATOR_PATH)]

    if expert:
        cmd.extend(["--force", expert])

    cmd.extend(["--prompt", prompt])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout + result.stderr

        # Check for import/config errors
        if "ImportError" in output or "ModuleNotFoundError" in output:
            return f"[Orchestrator configuration error - check afs tools setup]\n\nExpert: {expert}\nPrompt that would be sent:\n{prompt}"

        return output
    except subprocess.TimeoutExpired:
        return "[Orchestrator timed out]"
    except Exception as e:
        return f"[Orchestrator error: {e}]"

def build_analysis_prompt(context: str, file_path: str | None = None,
                          memory_dump: dict | None = None) -> str:
    """Build a detailed prompt for analysis."""
    prompt = f"""Oracle of Secrets - Test Failure Analysis

## Context
{context}

"""
    if file_path:
        prompt += f"""## Relevant File
{file_path}

"""
        # Try to read the file
        full_path = PROJECT_DIR / file_path
        if full_path.exists():
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                    # Limit to first 200 lines
                    lines = content.split('\n')[:200]
                    prompt += f"""```asm
{chr(10).join(lines)}
```

"""
            except:
                pass

    if memory_dump:
        prompt += f"""## Memory State
```json
{json.dumps(memory_dump, indent=2)}
```

"""

    prompt += """## Request
Analyze this issue and provide:
1. Root cause analysis
2. Suggested fix (65816 ASM code if applicable)
3. Confidence level (low/medium/high)

If providing ASM code, use asar syntax compatible with Oracle of Secrets codebase.
"""

    return prompt

def build_patch_prompt(issue: str, file_path: str) -> str:
    """Build a prompt for generating a specific patch."""
    prompt = f"""Oracle of Secrets - ASM Patch Generation

## Issue
{issue}

## Target File
{file_path}

"""
    # Read the file
    full_path = PROJECT_DIR / file_path
    if full_path.exists():
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            prompt += f"""## Current Code
```asm
{content}
```

"""
        except:
            pass

    prompt += """## Request
Generate a patch to fix this issue. Provide:
1. The specific lines to modify
2. The new ASM code
3. Explanation of the fix

Use asar syntax. Mark insertions with `+` and deletions with `-`.
"""

    return prompt

def parse_code_block(response: str) -> str | None:
    """Extract code block from response."""
    import re

    # Look for ```asm or ``` code blocks
    pattern = r'```(?:asm|assembly|65816)?\s*\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

    return None

def analyze_failure(context: str, file_path: str | None = None,
                    memory_dump: dict | None = None,
                    expert: str | None = None) -> PatchSuggestion:
    """Analyze a test failure and generate patch suggestion."""

    if not expert:
        expert = detect_expert(context)

    print(f"Routing to expert: {expert}")

    prompt = build_analysis_prompt(context, file_path, memory_dump)
    response = call_orchestrator(prompt, expert)

    # Parse response
    code = parse_code_block(response) or ""

    # Detect confidence from response
    confidence = 0.5
    if "high confidence" in response.lower() or "confident" in response.lower():
        confidence = 0.8
    elif "low confidence" in response.lower() or "uncertain" in response.lower():
        confidence = 0.3

    return PatchSuggestion(
        expert=expert,
        analysis=response,
        code=code,
        confidence=confidence,
        file_hint=file_path,
        line_hint=None
    )

def apply_patch_z3ed(patch_content: str, target_file: str) -> bool:
    """Apply a patch using z3ed CLI."""
    if not Z3ED_PATH.exists():
        print(f"z3ed not found at {Z3ED_PATH}")
        print("Manual application required.")
        return False

    # Write patch to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.asm', delete=False) as f:
        f.write(patch_content)
        patch_path = f.name

    try:
        # z3ed can apply ASM patches
        result = subprocess.run(
            [str(Z3ED_PATH), "--apply-patch", patch_path, "--target", target_file],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Patch applied successfully")
            return True
        else:
            print(f"Patch failed: {result.stderr}")
            return False
    finally:
        os.unlink(patch_path)

def save_patch(suggestion: PatchSuggestion, name: str) -> Path:
    """Save patch suggestion to file."""
    patches_dir = PROJECT_DIR / "patches"
    patches_dir.mkdir(exist_ok=True)

    patch_path = patches_dir / f"{name}.asm"

    with open(patch_path, 'w') as f:
        f.write(f"; AI-Generated Patch\n")
        f.write(f"; Expert: {suggestion.expert}\n")
        f.write(f"; Confidence: {suggestion.confidence:.0%}\n")
        f.write(f"; Target: {suggestion.file_hint or 'unknown'}\n")
        f.write(f";\n")
        f.write(f"; Analysis:\n")
        for line in suggestion.analysis.split('\n')[:20]:
            f.write(f"; {line}\n")
        f.write(f";\n\n")
        f.write(suggestion.code)

    print(f"Saved patch to: {patch_path}")
    return patch_path

def interactive_mode():
    """Interactive patch generation mode."""
    print("=== AI Patch Generator - Interactive Mode ===")
    print("Type 'help' for commands, 'quit' to exit\n")

    while True:
        try:
            cmd = input("ai_patch> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if action in ('quit', 'exit', 'q'):
            break

        elif action == 'help':
            print("""
Commands:
  analyze <context>     - Analyze a failure and get suggestions
  suggest <file> <issue> - Generate patch for specific file
  expert <name>         - Force specific expert (farore/din/nayru/veran)
  save <name>           - Save last suggestion as patch file
  apply                 - Apply last suggestion via z3ed
  status                - Show connection status
  quit                  - Exit interactive mode
""")

        elif action == 'analyze':
            if not args:
                print("Usage: analyze <context description>")
                continue
            suggestion = analyze_failure(args)
            print("\n" + "="*60)
            print(suggestion.analysis)
            print("="*60)
            if suggestion.code:
                print("\nGenerated code:")
                print(suggestion.code)

        elif action == 'suggest':
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: suggest <file> <issue>")
                continue
            file_path, issue = parts
            prompt = build_patch_prompt(issue, file_path)
            response = call_orchestrator(prompt, "nayru")
            print("\n" + response)

        elif action == 'status':
            orch_status = "available" if ORCHESTRATOR_PATH.exists() else "not found"
            z3ed_status = "available" if Z3ED_PATH.exists() else "not found"
            print(f"Orchestrator: {orch_status}")
            print(f"z3ed: {z3ed_status}")

        else:
            print(f"Unknown command: {action}")
            print("Type 'help' for available commands")

def main():
    parser = argparse.ArgumentParser(
        description='AI Patch Generator for Oracle of Secrets'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze test failure')
    analyze_parser.add_argument('--context', '-c', required=True,
                                help='Failure context/description')
    analyze_parser.add_argument('--file', '-f', help='Relevant source file')
    analyze_parser.add_argument('--expert', '-e',
                                choices=['farore', 'din', 'nayru', 'veran'],
                                help='Force specific expert')
    analyze_parser.add_argument('--save', '-s', help='Save suggestion to patch file')

    # Suggest command
    suggest_parser = subparsers.add_parser('suggest', help='Generate patch suggestion')
    suggest_parser.add_argument('--file', '-f', required=True,
                                help='Target ASM file')
    suggest_parser.add_argument('--issue', '-i', required=True,
                                help='Issue description')

    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply patch via z3ed')
    apply_parser.add_argument('--patch', '-p', required=True,
                              help='Patch file to apply')
    apply_parser.add_argument('--target', '-t', help='Target file')

    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive mode')

    args = parser.parse_args()

    if args.command == 'analyze':
        suggestion = analyze_failure(
            args.context,
            file_path=args.file,
            expert=args.expert
        )
        print("\n" + "="*60)
        print(f"Expert: {suggestion.expert}")
        print(f"Confidence: {suggestion.confidence:.0%}")
        print("="*60)
        print(suggestion.analysis)

        if suggestion.code:
            print("\n--- Generated Code ---")
            print(suggestion.code)
            print("--- End Code ---")

        if args.save:
            save_patch(suggestion, args.save)

    elif args.command == 'suggest':
        prompt = build_patch_prompt(args.issue, args.file)
        response = call_orchestrator(prompt, "nayru")
        print(response)

    elif args.command == 'apply':
        with open(args.patch, 'r') as f:
            content = f.read()
        target = args.target or "unknown"
        apply_patch_z3ed(content, target)

    elif args.command == 'interactive':
        interactive_mode()

    else:
        parser.print_help()

    return 0

if __name__ == '__main__':
    sys.exit(main())
