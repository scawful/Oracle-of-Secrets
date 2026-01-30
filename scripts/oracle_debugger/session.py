"""
Debug session state management for Oracle Debugger.

Maintains context across tool invocations within a single debugging session.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class SessionState(Enum):
    """Current state of the debugging session."""
    IDLE = "idle"
    MONITORING = "monitoring"
    INVESTIGATING = "investigating"
    CAPTURING = "capturing"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Detection:
    """A detected anomaly or bug."""
    detection_id: str
    detection_type: str  # softlock, crash, anomaly, regression
    pattern: Optional[str] = None  # B007, B009, INIDISP, etc.
    timestamp: float = field(default_factory=time.time)
    frame_number: int = 0
    game_mode: int = 0
    submodule: int = 0
    link_position: tuple[int, int, int] = (0, 0, 0)  # x, y, z
    description: str = ""
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "detection_id": self.detection_id,
            "type": self.detection_type,
            "pattern": self.pattern,
            "timestamp": self.timestamp,
            "frame": self.frame_number,
            "game_mode": self.game_mode,
            "submodule": self.submodule,
            "link_position": self.link_position,
            "description": self.description,
            "raw_data": self.raw_data,
        }


@dataclass
class TraceCapture:
    """Captured execution trace."""
    frames: list[dict] = field(default_factory=list)
    symbols_resolved: bool = False
    capture_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "frame_count": len(self.frames),
            "symbols_resolved": self.symbols_resolved,
            "capture_time": self.capture_time,
            "frames": self.frames[:100],  # Limit for serialization
        }


@dataclass
class StateCapture:
    """Captured emulator state."""
    state_path: Optional[str] = None
    state_slot: Optional[int] = None
    cpu_state: dict = field(default_factory=dict)
    ram_snapshot: dict = field(default_factory=dict)  # Key addresses
    capture_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "state_path": self.state_path,
            "state_slot": self.state_slot,
            "cpu_state": self.cpu_state,
            "ram_snapshot": self.ram_snapshot,
            "capture_time": self.capture_time,
        }


@dataclass
class AnalysisResult:
    """Result from MoE analysis."""
    expert: str
    prompt: str
    response: str
    confidence: float = 0.0
    analysis_time: float = field(default_factory=time.time)
    suggested_fix: Optional[str] = None
    related_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expert": self.expert,
            "prompt": self.prompt,
            "response": self.response,
            "confidence": self.confidence,
            "analysis_time": self.analysis_time,
            "suggested_fix": self.suggested_fix,
            "related_files": self.related_files,
        }


class DebugSession:
    """
    Manages state for a single debugging session.

    A session tracks all detections, captures, and analyses
    from the start of debugging until report generation.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or self._generate_id()
        self.state = SessionState.IDLE
        self.start_time = time.time()
        self.end_time: Optional[float] = None

        # Collected data
        self.detections: list[Detection] = []
        self.traces: list[TraceCapture] = []
        self.states: list[StateCapture] = []
        self.analyses: list[AnalysisResult] = []

        # Session metadata
        self.rom_path: Optional[str] = None
        self.rom_crc: Optional[str] = None
        self.tags: list[str] = []
        self.notes: list[str] = []

        # Context for MoE routing
        self.context: dict[str, Any] = {}

    @staticmethod
    def _generate_id() -> str:
        """Generate unique session ID."""
        return f"debug-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def set_state(self, state: SessionState) -> None:
        """Transition to new session state."""
        self.state = state
        if state == SessionState.COMPLETED:
            self.end_time = time.time()

    def add_detection(self, detection: Detection) -> None:
        """Record a new detection."""
        self.detections.append(detection)
        self.state = SessionState.INVESTIGATING

    def add_trace(self, trace: TraceCapture) -> None:
        """Record a captured trace."""
        self.traces.append(trace)

    def add_state(self, state: StateCapture) -> None:
        """Record a captured state."""
        self.states.append(state)

    def add_analysis(self, analysis: AnalysisResult) -> None:
        """Record an analysis result."""
        self.analyses.append(analysis)

    def add_note(self, note: str) -> None:
        """Add a session note."""
        self.notes.append(f"[{time.strftime('%H:%M:%S')}] {note}")

    def get_latest_detection(self) -> Optional[Detection]:
        """Get the most recent detection."""
        return self.detections[-1] if self.detections else None

    def get_detection_summary(self) -> dict:
        """Summarize all detections by type."""
        summary: dict[str, int] = {}
        for d in self.detections:
            key = d.pattern or d.detection_type
            summary[key] = summary.get(key, 0) + 1
        return summary

    def duration(self) -> float:
        """Get session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> dict:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration(),
            "rom_path": self.rom_path,
            "rom_crc": self.rom_crc,
            "tags": self.tags,
            "notes": self.notes,
            "detections": [d.to_dict() for d in self.detections],
            "traces": [t.to_dict() for t in self.traces],
            "states": [s.to_dict() for s in self.states],
            "analyses": [a.to_dict() for a in self.analyses],
            "context": self.context,
        }

    def save(self, output_dir: Path) -> Path:
        """Save session to JSON file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.session_id}.json"
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def load(cls, path: Path) -> "DebugSession":
        """Load session from JSON file."""
        with open(path) as f:
            data = json.load(f)

        session = cls(session_id=data["session_id"])
        session.state = SessionState(data["state"])
        session.start_time = data["start_time"]
        session.end_time = data.get("end_time")
        session.rom_path = data.get("rom_path")
        session.rom_crc = data.get("rom_crc")
        session.tags = data.get("tags", [])
        session.notes = data.get("notes", [])
        session.context = data.get("context", {})

        # Reconstruct detections
        for d in data.get("detections", []):
            session.detections.append(Detection(
                detection_id=d["detection_id"],
                detection_type=d["type"],
                pattern=d.get("pattern"),
                timestamp=d["timestamp"],
                frame_number=d.get("frame", 0),
                game_mode=d.get("game_mode", 0),
                submodule=d.get("submodule", 0),
                link_position=tuple(d.get("link_position", [0, 0, 0])),
                description=d.get("description", ""),
                raw_data=d.get("raw_data", {}),
            ))

        return session
