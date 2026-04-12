"""
MoE Bridge - Integration with the Mixture of Experts orchestrator.

Routes debugging tasks to specialized expert models:
- Nayru: 65816 ASM analysis and code generation
- Veran: Logic/state machine analysis
- Farore: Strategic planning and debugging
- Din: Performance optimization
- Majora: Codebase knowledge
- Hylia: Narrative context (dialogue, quests)
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .session import AnalysisResult

logger = logging.getLogger(__name__)

# Path to MoE orchestrator
AFS_TOOLS_PATH = Path.home() / "src/lab/afs/tools"
MOE_ORCHESTRATOR = AFS_TOOLS_PATH / "moe_orchestrator.py"
ORCHESTRATOR = AFS_TOOLS_PATH / "orchestrator.py"


class MoEBridge:
    """
    Bridge to the MoE orchestrator for expert analysis.

    Routes debugging tasks to appropriate expert models based on task type.
    Falls back to direct subprocess calls if imports unavailable.
    """

    # Task type to expert routing
    TASK_ROUTING = {
        "asm_analysis": "nayru",      # 65816 trace analysis
        "code_generation": "nayru",   # Fix suggestions
        "logic_check": "veran",       # State machine analysis
        "pattern_match": "veran",     # Bug pattern detection
        "planning": "farore",         # Multi-step debugging
        "crash_analysis": "farore",   # Crash investigation
        "performance": "din",         # Optimization analysis
        "codebase_search": "majora",  # Finding related code
        "narrative": "hylia",         # Story/dialogue context
    }

    def __init__(self, verbose: bool = False, remote: bool = False):
        """
        Initialize MoE bridge.

        Args:
            verbose: Enable verbose logging from experts
            remote: Use remote backend (medical-mechanica)
        """
        self.verbose = verbose
        self.remote = remote
        self._moe_module = None
        self._orchestrator_module = None

        # Try to import MoE orchestrator module
        self._try_import_moe()

    def _try_import_moe(self) -> None:
        """Attempt to import MoE orchestrator module."""
        try:
            if str(AFS_TOOLS_PATH) not in sys.path:
                sys.path.insert(0, str(AFS_TOOLS_PATH))
            import moe_orchestrator
            self._moe_module = moe_orchestrator
            logger.info("MoE orchestrator module imported successfully")
        except ImportError as e:
            logger.warning(f"Could not import MoE orchestrator: {e}")
            logger.info("Will use subprocess fallback")

    def route_task(self, task_type: str) -> str:
        """
        Get the expert for a task type.

        Args:
            task_type: Type of debugging task

        Returns:
            Expert name (nayru, veran, farore, etc.)
        """
        return self.TASK_ROUTING.get(task_type, "farore")  # Default to farore

    async def analyze_trace(
        self,
        trace: list[dict],
        symbols: Optional[dict] = None,
        context: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Route ASM execution trace to Nayru for analysis.

        Args:
            trace: List of trace frames (PC, A, X, Y, etc.)
            symbols: Optional symbol table (address -> name)
            context: Additional context about the trace

        Returns:
            AnalysisResult with expert's analysis
        """
        # Format trace for analysis
        trace_text = self._format_trace(trace, symbols)

        prompt = f"""Analyze this 65816 execution trace for bugs:

{trace_text}

{f"Context: {context}" if context else ""}

Look for:
- Register corruption (unexpected values in A/X/Y)
- Stack imbalance (mismatched push/pull)
- Invalid memory access (out of bounds)
- M/X flag mismatches (8-bit vs 16-bit operations)
- Infinite loops or stuck states
- Missing RTS/RTL returns

Identify the likely cause and suggest a fix."""

        return await self._call_expert("nayru", prompt, "asm_analysis")

    async def analyze_softlock(
        self,
        detection: dict,
        trace: Optional[list[dict]] = None,
        game_state: Optional[dict] = None,
    ) -> AnalysisResult:
        """
        Analyze a detected soft lock condition.

        Args:
            detection: Detection data (type, pattern, frame, etc.)
            trace: Optional execution trace
            game_state: Optional game state snapshot

        Returns:
            AnalysisResult with analysis and suggested fix
        """
        prompt = f"""Analyze this soft lock detection:

Detection Type: {detection.get('type', 'unknown')}
Pattern: {detection.get('pattern', 'unknown')}
Frame: {detection.get('frame', 0)}
Game Mode: ${detection.get('game_mode', 0):02X}
Submodule: ${detection.get('submodule', 0):02X}
Link Position: {detection.get('link_position', (0, 0, 0))}

{f"Game State: {game_state}" if game_state else ""}

{f"Last trace frames: {self._format_trace(trace[-20:], None)}" if trace else ""}

Determine:
1. What caused the soft lock?
2. Which code path is responsible?
3. How can it be fixed?
4. How can we detect this pattern earlier?"""

        return await self._call_expert("farore", prompt, "crash_analysis")

    async def suggest_fix(
        self,
        bug_report: dict,
        similar_bugs: Optional[list[dict]] = None,
    ) -> AnalysisResult:
        """
        Get fix suggestion from Nayru.

        Args:
            bug_report: Bug report data
            similar_bugs: Optional list of similar fixed bugs

        Returns:
            AnalysisResult with suggested ASM fix
        """
        prompt = f"""Suggest a fix for this bug:

Bug ID: {bug_report.get('id', 'unknown')}
Type: {bug_report.get('type', 'unknown')}
Pattern: {bug_report.get('pattern', 'unknown')}
Description: {bug_report.get('description', '')}
Affected Address: {bug_report.get('address', 'unknown')}
Source File: {bug_report.get('source_file', 'unknown')}
Source Line: {bug_report.get('source_line', 'unknown')}

{self._format_similar_bugs(similar_bugs) if similar_bugs else ""}

Provide 65816 ASM code that would prevent this issue.
Include:
1. The fix code itself
2. Where to insert it (before/after which instruction)
3. Any register preservation needed
4. Potential side effects to test"""

        return await self._call_expert("nayru", prompt, "code_generation")

    async def analyze_state_machine(
        self,
        transitions: list[dict],
        expected_flow: Optional[list[str]] = None,
    ) -> AnalysisResult:
        """
        Analyze game state machine transitions.

        Args:
            transitions: List of mode/submodule transitions
            expected_flow: Optional expected transition sequence

        Returns:
            AnalysisResult with state machine analysis
        """
        trans_text = "\n".join([
            f"Frame {t.get('frame', 0)}: Mode ${t.get('mode', 0):02X} "
            f"-> ${t.get('submodule', 0):02X} ({t.get('duration', 0)} frames)"
            for t in transitions
        ])

        prompt = f"""Analyze these game state transitions:

{trans_text}

{f"Expected flow: {' -> '.join(expected_flow)}" if expected_flow else ""}

Identify:
1. Any unexpected transitions (wrong state reached)
2. Stuck states (same state too long)
3. Missing transitions (skipped expected states)
4. Potential infinite loops in the state machine"""

        return await self._call_expert("veran", prompt, "logic_check")

    async def plan_investigation(
        self,
        bug_description: str,
        available_tools: list[str],
    ) -> AnalysisResult:
        """
        Plan a multi-step debugging investigation.

        Args:
            bug_description: Description of the bug to investigate
            available_tools: List of available debugging tools

        Returns:
            AnalysisResult with investigation plan
        """
        tools_text = ", ".join(available_tools)

        prompt = f"""Plan an investigation for this bug:

{bug_description}

Available tools: {tools_text}

Create a step-by-step plan to:
1. Reproduce the bug reliably
2. Capture relevant diagnostic data
3. Identify the root cause
4. Verify the fix

For each step, specify which tool to use and what data to collect."""

        return await self._call_expert("farore", prompt, "planning")

    def _format_trace(
        self,
        trace: list[dict],
        symbols: Optional[dict],
    ) -> str:
        """Format trace frames as text."""
        if not trace:
            return "(no trace available)"

        lines = ["| Frame | PC | Instruction | A | X | Y | P |"]
        lines.append("|-------|------|-------------|-----|-----|-----|-----|")

        for frame in trace[-50:]:  # Limit to last 50 frames
            pc = frame.get("pc", 0)
            symbol = ""
            if symbols and pc in symbols:
                symbol = f" ({symbols[pc]})"

            lines.append(
                f"| {frame.get('frame', 0)} | "
                f"${pc:06X}{symbol} | "
                f"{frame.get('instruction', '???')} | "
                f"${frame.get('a', 0):04X} | "
                f"${frame.get('x', 0):04X} | "
                f"${frame.get('y', 0):04X} | "
                f"${frame.get('p', 0):02X} |"
            )

        return "\n".join(lines)

    def _format_similar_bugs(self, bugs: list[dict]) -> str:
        """Format similar bugs for context."""
        if not bugs:
            return ""

        lines = ["Similar bugs that were fixed:"]
        for bug in bugs[:3]:  # Limit to 3 examples
            lines.append(f"\n- {bug.get('id', 'unknown')}: {bug.get('description', '')}")
            if bug.get('fix_commit'):
                lines.append(f"  Fix: {bug.get('fix_commit')}")
            if bug.get('fix_pattern'):
                lines.append(f"  Pattern: {bug.get('fix_pattern')}")

        return "\n".join(lines)

    async def _call_expert(
        self,
        expert: str,
        prompt: str,
        task_type: str,
    ) -> AnalysisResult:
        """
        Call an expert model with a prompt.

        Uses imported module if available, falls back to subprocess.
        """
        import time
        start_time = time.time()

        try:
            if self._moe_module:
                response = await self._call_expert_module(expert, prompt)
            else:
                response = await self._call_expert_subprocess(expert, prompt)

            return AnalysisResult(
                expert=expert,
                prompt=prompt,
                response=response,
                confidence=0.8,  # Default confidence
                analysis_time=time.time() - start_time,
            )

        except Exception as e:
            logger.error(f"Expert call failed: {e}")
            return AnalysisResult(
                expert=expert,
                prompt=prompt,
                response=f"Error calling expert: {e}",
                confidence=0.0,
                analysis_time=time.time() - start_time,
            )

    async def _call_expert_module(self, expert: str, prompt: str) -> str:
        """Call expert using imported module."""
        import asyncio

        # The MoE module uses sync calls, run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._moe_module.call_expert,
            expert,
            prompt,
            self.verbose,
            self.remote,
        )

    async def _call_expert_subprocess(self, expert: str, prompt: str) -> str:
        """Call expert using subprocess."""
        import asyncio

        cmd = [
            sys.executable,
            str(MOE_ORCHESTRATOR),
            "--force", expert,
            "--prompt", prompt,
        ]

        if self.verbose:
            cmd.append("--verbose")
        if self.remote:
            cmd.append("--remote")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": str(AFS_TOOLS_PATH)},
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Expert call failed: {stderr.decode()}")

        return stdout.decode().strip()

    def is_available(self) -> bool:
        """Check if MoE system is available."""
        return MOE_ORCHESTRATOR.exists() or self._moe_module is not None
