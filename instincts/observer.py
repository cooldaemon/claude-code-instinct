"""Observer module for Instinct-Based Learning.

Handles PreToolUse and PostToolUse hooks from Claude Code,
writing observations to a JSONL file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instincts.config import ARCHIVE_DIR, INSTINCTS_DIR, OBSERVATIONS_FILE

# Maximum file size before archiving (in MB)
MAX_FILE_SIZE_MB: int = 10

# Maximum length for input/output strings
MAX_CONTENT_LENGTH: int = 5000


def _truncate(value: Any, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Truncate a value to max_length characters."""
    if isinstance(value, dict):
        text = json.dumps(value)
    else:
        text = str(value)
    return text[:max_length]


def _get_file_size_mb(path: Path) -> float:
    """Get file size in megabytes."""
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024 * 1024)


def _archive_if_needed(observations_file: Path, archive_dir: Path) -> None:
    """Archive observations file if it exceeds MAX_FILE_SIZE_MB."""
    if _get_file_size_mb(observations_file) >= MAX_FILE_SIZE_MB:
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive_path = archive_dir / f"observations-{timestamp}.jsonl"
        observations_file.rename(archive_path)


def _write_observation(observation: dict[str, Any]) -> None:
    """Write an observation to the observations file."""
    # Ensure directory exists
    INSTINCTS_DIR.mkdir(parents=True, exist_ok=True)

    # Archive if needed
    _archive_if_needed(OBSERVATIONS_FILE, ARCHIVE_DIR)

    # Append observation
    with OBSERVATIONS_FILE.open("a") as f:
        f.write(json.dumps(observation) + "\n")


def _extract_field(data: dict[str, Any], primary: str, fallback: str) -> Any:
    """Extract a field from data, trying primary key first, then fallback."""
    return data.get(primary, data.get(fallback, ""))


def observe_pre(hook_data: dict[str, Any]) -> None:
    """Process PreToolUse hook.

    Extracts tool information and writes a tool_start event.

    Args:
        hook_data: Hook data from Claude Code containing:
            - hook_type: "PreToolUse"
            - tool_name or tool: Name of the tool
            - tool_input or input: Input parameters
            - session_id: Session identifier
    """
    tool_name = _extract_field(hook_data, "tool_name", "tool")
    tool_input = _extract_field(hook_data, "tool_input", "input")
    session_id = hook_data.get("session_id", "unknown")

    observation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "tool_start",
        "tool": tool_name,
        "session": session_id,
        "input": _truncate(tool_input),
    }

    _write_observation(observation)


def observe_post(hook_data: dict[str, Any]) -> None:
    """Process PostToolUse hook.

    Extracts tool output and writes a tool_complete event.

    Args:
        hook_data: Hook data from Claude Code containing:
            - hook_type: "PostToolUse"
            - tool_name or tool: Name of the tool
            - tool_output or output: Output from the tool
            - session_id: Session identifier
    """
    tool_name = _extract_field(hook_data, "tool_name", "tool")
    tool_output = _extract_field(hook_data, "tool_output", "output")
    session_id = hook_data.get("session_id", "unknown")

    observation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "tool_complete",
        "tool": tool_name,
        "session": session_id,
        "output": _truncate(tool_output),
    }

    _write_observation(observation)
