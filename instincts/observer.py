"""Observer module for Instinct-Based Learning.

Handles PreToolUse and PostToolUse hooks from Claude Code,
writing observations to a JSONL file.
"""

import fcntl
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from instincts.auto_learn import should_trigger_learning, trigger_background_analysis
from instincts.config import (
    ANALYSIS_MIN_COUNT,
    ANALYSIS_TRIGGER_CHECK_INTERVAL,
    ANALYSIS_TRIGGER_COUNT,
    ANALYSIS_TRIGGER_HOURS,
    get_analysis_pending_file,
    get_archive_dir,
    get_observations_file,
    get_project_instincts_dir,
)

# Maximum file size before archiving (in MB)
MAX_FILE_SIZE_MB: int = 10

# Maximum length for input/output strings
MAX_CONTENT_LENGTH: int = 5000

# Thread-local storage for observation counter (CR-001: thread safety)

_observation_storage = threading.local()


def get_observation_counter() -> int:
    """Get the current observation counter value (thread-safe).

    Returns:
        Current counter value for this thread.
    """
    return getattr(_observation_storage, "counter", 0)


def increment_observation_counter() -> int:
    """Increment the observation counter (thread-safe).

    Returns:
        New counter value after increment.
    """
    current = get_observation_counter()
    new_value = current + 1
    _observation_storage.counter = new_value
    return new_value


def reset_observation_counter() -> None:
    """Reset the observation counter to zero (thread-safe)."""
    _observation_storage.counter = 0


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
    """Archive observations file if it exceeds MAX_FILE_SIZE_MB.

    Uses unique timestamp + PID for archive filename to prevent race conditions
    when multiple processes attempt to archive simultaneously.
    """
    if _get_file_size_mb(observations_file) >= MAX_FILE_SIZE_MB:
        archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        # Include PID in filename to prevent race condition with concurrent archives
        archive_path = archive_dir / f"observations-{timestamp}-{os.getpid()}.jsonl"
        try:
            observations_file.rename(archive_path)
        except FileNotFoundError:
            # Another process already archived the file - this is fine
            pass


def _append_observation_with_lock(
    observation: dict[str, Any], observations_file: Path
) -> None:
    """Append an observation to a file with exclusive file locking.

    Uses fcntl.LOCK_EX to prevent race conditions when multiple Claude Code
    sessions write to the same file simultaneously.

    Args:
        observation: The observation data to write.
        observations_file: Path to the observations JSONL file.
    """
    with observations_file.open("a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(observation) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _write_observation_to_project(
    observation: dict[str, Any], project_root: Path
) -> None:
    """Write an observation to the project's observations file.

    Uses file locking to prevent race conditions when multiple Claude Code
    sessions write to the same file simultaneously.

    Args:
        observation: The observation data to write.
        project_root: Path to the project root.
    """
    instincts_dir = get_project_instincts_dir(project_root)
    instincts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    observations_file = get_observations_file(project_root)
    archive_dir = get_archive_dir(project_root)

    _archive_if_needed(observations_file, archive_dir)
    _append_observation_with_lock(observation, observations_file)


def _extract_field(data: dict[str, Any], primary: str, fallback: str) -> Any:
    """Extract a field from data, trying primary key first, then fallback."""
    return data.get(primary, data.get(fallback, ""))


def observe_pre(hook_data: dict[str, Any], project_root: Path) -> None:
    """Process PreToolUse hook.

    Extracts tool information and writes a tool_start event.

    Args:
        hook_data: Hook data from Claude Code containing:
            - hook_type: "PreToolUse"
            - tool_name or tool: Name of the tool
            - tool_input or input: Input parameters
            - session_id: Session identifier
        project_root: Project root for project-scoped storage.
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

    _write_observation_to_project(observation, project_root)


def observe_post(hook_data: dict[str, Any], project_root: Path) -> None:
    """Process PostToolUse hook.

    Extracts tool output and writes a tool_complete event.

    Args:
        hook_data: Hook data from Claude Code containing:
            - hook_type: "PostToolUse"
            - tool_name or tool: Name of the tool
            - tool_output or output: Output from the tool
            - session_id: Session identifier
        project_root: Project root for project-scoped storage.
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

    _write_observation_to_project(observation, project_root)

    # Check auto-learning trigger for project-scoped storage
    counter = increment_observation_counter()
    if counter >= ANALYSIS_TRIGGER_CHECK_INTERVAL:
        reset_observation_counter()
        if should_trigger_learning(project_root):
            trigger_background_analysis(project_root)


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


def should_trigger_analysis(project_root: Path) -> bool:
    """Check if analysis should be triggered for a project.

    Args:
        project_root: Path to the project root.

    Returns:
        True if analysis should be triggered based on count or time.
    """
    analysis_pending_file = get_analysis_pending_file(project_root)
    observations_file = get_observations_file(project_root)

    # Don't trigger if marker already exists
    if analysis_pending_file.exists():
        return False

    obs_count = count_observations(observations_file)

    # Trigger if count reached threshold
    if obs_count >= ANALYSIS_TRIGGER_COUNT:
        return True

    # Not enough observations for time-based trigger
    if obs_count < ANALYSIS_MIN_COUNT:
        return False

    # Check if enough time has elapsed
    oldest_ts = get_oldest_observation_timestamp(observations_file)
    if not oldest_ts:
        return False

    elapsed = datetime.now(timezone.utc) - oldest_ts
    return elapsed >= timedelta(hours=ANALYSIS_TRIGGER_HOURS)


def create_analysis_marker(project_root: Path) -> None:
    """Create the analysis pending marker file atomically.

    Uses exclusive file creation to avoid race conditions when multiple
    processes try to create the marker simultaneously.

    Args:
        project_root: Path to the project root.
    """
    analysis_pending_file = get_analysis_pending_file(project_root)
    observations_file = get_observations_file(project_root)

    # Ensure parent directory exists
    analysis_pending_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Check for symlink attack
    if analysis_pending_file.is_symlink():
        return

    # Write marker with timestamp using exclusive create (atomic)
    marker_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": count_observations(observations_file),
    }
    try:
        # Use 'x' mode for exclusive creation - fails if file already exists
        with analysis_pending_file.open("x") as f:
            f.write(json.dumps(marker_data))
    except FileExistsError:
        # Another process already created the marker - this is fine
        pass


def check_analysis_trigger(project_root: Path) -> None:
    """Check and create analysis trigger marker if needed.

    Args:
        project_root: Path to the project root.
    """
    if should_trigger_analysis(project_root):
        create_analysis_marker(project_root)
