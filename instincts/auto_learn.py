"""Auto-learning module for Instinct-Based Learning.

This module provides automatic learning trigger logic:
- Threshold checking (50 observations)
- Cooldown mechanism (5 minutes)
- Background subprocess spawn
- Lock file to prevent concurrent runs
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instincts.config import (
    AUTO_LEARN_COOLDOWN_SECONDS,
    AUTO_LEARN_LOCK_FILE,
    AUTO_LEARN_OBSERVATION_THRESHOLD,
    AUTO_LEARN_STATE_FILE,
    get_observations_file,
    get_project_instincts_dir,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoLearnState:
    """State for auto-learning trigger.

    Attributes:
        last_analysis_time: When the last analysis was run.
        observation_count_at_analysis: Observation count at last analysis.
    """

    last_analysis_time: datetime | None
    observation_count_at_analysis: int


def _get_state_file_path(project_root: Path) -> Path:
    """Get the path to the auto-learn state file."""
    return get_project_instincts_dir(project_root) / AUTO_LEARN_STATE_FILE


def _get_lock_file_path(project_root: Path) -> Path:
    """Get the path to the auto-learn lock file."""
    return get_project_instincts_dir(project_root) / AUTO_LEARN_LOCK_FILE


def load_state(project_root: Path) -> AutoLearnState:
    """Load auto-learn state from file.

    Args:
        project_root: Path to the project root.

    Returns:
        AutoLearnState with last analysis info, or default state if not found.
    """
    state_file = _get_state_file_path(project_root)

    if not state_file.exists():
        return AutoLearnState(last_analysis_time=None, observation_count_at_analysis=0)

    try:
        data = json.loads(state_file.read_text())
        last_time = data.get("last_analysis_time")
        if last_time:
            last_time = datetime.fromisoformat(last_time)
        return AutoLearnState(
            last_analysis_time=last_time,
            observation_count_at_analysis=data.get("observation_count_at_analysis", 0),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Failed to load auto-learn state: %s", e)
        return AutoLearnState(last_analysis_time=None, observation_count_at_analysis=0)


def save_state(project_root: Path, state: AutoLearnState) -> None:
    """Save auto-learn state to file.

    Args:
        project_root: Path to the project root.
        state: State to save.
    """
    instincts_dir = get_project_instincts_dir(project_root)
    instincts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    state_file = _get_state_file_path(project_root)
    data: dict[str, Any] = {
        "last_analysis_time": state.last_analysis_time.isoformat() if state.last_analysis_time else None,
        "observation_count_at_analysis": state.observation_count_at_analysis,
    }
    state_file.write_text(json.dumps(data, indent=2))


def count_observations(project_root: Path) -> int:
    """Count observations in the project's observations file.

    Args:
        project_root: Path to the project root.

    Returns:
        Number of observations, or 0 if file doesn't exist.
    """
    obs_file = get_observations_file(project_root)

    if not obs_file.exists():
        return 0

    try:
        with obs_file.open() as f:
            return sum(1 for _ in f)
    except OSError as e:
        logger.warning("Failed to count observations: %s", e)
        return 0


def should_trigger_learning(project_root: Path) -> bool:
    """Check if auto-learning should be triggered.

    Args:
        project_root: Path to the project root.

    Returns:
        True if learning should be triggered.
    """
    try:
        obs_count = count_observations(project_root)
    except OSError:
        return False

    # Check threshold
    if obs_count < AUTO_LEARN_OBSERVATION_THRESHOLD:
        return False

    # Check cooldown
    state = load_state(project_root)
    if state.last_analysis_time:
        elapsed = datetime.now(timezone.utc) - state.last_analysis_time
        if elapsed.total_seconds() < AUTO_LEARN_COOLDOWN_SECONDS:
            return False

    return True


def acquire_lock(project_root: Path) -> bool:
    """Try to acquire the auto-learn lock.

    Args:
        project_root: Path to the project root.

    Returns:
        True if lock was acquired, False if already locked.
    """
    instincts_dir = get_project_instincts_dir(project_root)
    instincts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    lock_file = _get_lock_file_path(project_root)

    # Check if lock already exists
    if lock_file.exists():
        return False

    try:
        # Try to create lock file exclusively
        lock_data = {
            "pid": os.getpid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with lock_file.open("x") as f:
            f.write(json.dumps(lock_data))
        return True
    except FileExistsError:
        return False


def release_lock(project_root: Path) -> None:
    """Release the auto-learn lock.

    Args:
        project_root: Path to the project root.
    """
    lock_file = _get_lock_file_path(project_root)
    try:
        lock_file.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Failed to release lock: %s", e)


def trigger_background_analysis(project_root: Path) -> None:
    """Trigger background pattern analysis.

    Spawns a subprocess to run analysis without blocking.

    Args:
        project_root: Path to the project root.
    """
    try:
        # Build the command to run agent analysis
        cmd = [
            sys.executable,
            "-m",
            "instincts.agent",
            "--project-root",
            str(project_root),
        ]

        # Spawn subprocess without waiting (detached)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.debug("Triggered background analysis for %s", project_root)
    except OSError as e:
        logger.warning("Failed to trigger background analysis: %s", e)
        # Non-blocking - don't propagate error
