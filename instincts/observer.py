"""Observer module for Instinct-Based Learning.

Handles PreToolUse and PostToolUse hooks from Claude Code,
writing observations to a JSONL file.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from instincts.config import (
    ANALYSIS_MIN_COUNT,
    ANALYSIS_PENDING_FILE,
    ANALYSIS_TRIGGER_COUNT,
    ANALYSIS_TRIGGER_HOURS,
    ARCHIVE_DIR,
    INSTINCTS_DIR,
    OBSERVATIONS_FILE,
)

# Maximum file size before archiving (in MB)
MAX_FILE_SIZE_MB: int = 10

# Maximum length for input/output strings
MAX_CONTENT_LENGTH: int = 5000

# Check analysis trigger every N observations (performance optimization)
ANALYSIS_TRIGGER_CHECK_INTERVAL: int = 10

# Counter for observations to reduce file reads
_observation_counter: int = 0


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
        archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive_path = archive_dir / f"observations-{timestamp}.jsonl"
        try:
            observations_file.rename(archive_path)
        except FileNotFoundError:
            # Another process already archived the file - this is fine
            pass


def _write_observation(observation: dict[str, Any]) -> None:
    """Write an observation to the observations file."""
    # Ensure directory exists with restrictive permissions
    INSTINCTS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

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

    # Check if analysis should be triggered (only every N observations for performance)
    global _observation_counter
    _observation_counter += 1
    if _observation_counter >= ANALYSIS_TRIGGER_CHECK_INTERVAL:
        _observation_counter = 0
        _check_analysis_trigger()


def count_observations(file_path: Path) -> int:
    """Count the number of observations in a file.

    Args:
        file_path: Path to the observations file.

    Returns:
        Number of lines in the file, or 0 if file doesn't exist.
    """
    if not file_path.exists():
        return 0

    try:
        with file_path.open() as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def get_oldest_observation_timestamp(file_path: Path) -> datetime | None:
    """Get the timestamp of the oldest observation in the file.

    Args:
        file_path: Path to the observations file.

    Returns:
        Datetime of the oldest observation, or None if file doesn't exist or is empty.
    """
    if not file_path.exists():
        return None

    try:
        with file_path.open() as f:
            first_line = f.readline().strip()
            if not first_line:
                return None

            data = json.loads(first_line)
            timestamp_str = data.get("timestamp")
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    return None


def _should_trigger_analysis() -> bool:
    """Check if analysis should be triggered.

    Returns:
        True if analysis should be triggered based on count or time.
    """
    # Don't trigger if marker already exists
    if ANALYSIS_PENDING_FILE.exists():
        return False

    obs_count = count_observations(OBSERVATIONS_FILE)

    # Trigger if count reached threshold
    if obs_count >= ANALYSIS_TRIGGER_COUNT:
        return True

    # Not enough observations for time-based trigger
    if obs_count < ANALYSIS_MIN_COUNT:
        return False

    # Check if enough time has elapsed
    oldest_ts = get_oldest_observation_timestamp(OBSERVATIONS_FILE)
    if not oldest_ts:
        return False

    elapsed = datetime.now(timezone.utc) - oldest_ts
    return elapsed >= timedelta(hours=ANALYSIS_TRIGGER_HOURS)


def _create_analysis_marker() -> None:
    """Create the analysis pending marker file atomically.

    Uses exclusive file creation to avoid race conditions when multiple
    processes try to create the marker simultaneously.
    """
    # Ensure parent directory exists
    ANALYSIS_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Check for symlink attack
    if ANALYSIS_PENDING_FILE.is_symlink():
        return

    # Write marker with timestamp using exclusive create (atomic)
    marker_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": count_observations(OBSERVATIONS_FILE),
    }
    try:
        # Use 'x' mode for exclusive creation - fails if file already exists
        with ANALYSIS_PENDING_FILE.open("x") as f:
            f.write(json.dumps(marker_data))
    except FileExistsError:
        # Another process already created the marker - this is fine
        pass


def _check_analysis_trigger() -> None:
    """Check and create analysis trigger marker if needed."""
    if _should_trigger_analysis():
        _create_analysis_marker()
