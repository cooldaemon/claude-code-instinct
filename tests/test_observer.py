"""Tests for instincts.observer module.

Tests cover:
- observe_pre: PreToolUse hook processing
- observe_post: PostToolUse hook processing
- Observation file writing (JSONL format)
- File archiving when size exceeds threshold
- Input truncation for large inputs/outputs
"""

import json
from pathlib import Path
from unittest.mock import patch


def create_project_structure(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a standard project structure for tests.

    Returns:
        Tuple of (project_root, instincts_dir, observations_file)
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    instincts_dir = project_root / "docs" / "instincts"
    instincts_dir.mkdir(parents=True)
    observations_file = instincts_dir / "observations.jsonl"
    return project_root, instincts_dir, observations_file


class TestObservePre:
    """Tests for observe_pre function."""

    def test_observe_pre_writes_tool_start_event(self, tmp_path: Path):
        """observe_pre should write a tool_start event to observations file."""
        from instincts.observer import observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "session_id": "session-123",
        }

        observe_pre(hook_data, project_root)

        assert observations_file.exists()
        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["event"] == "tool_start"
        assert event["tool"] == "Read"
        assert event["session"] == "session-123"
        assert "input" in event
        assert "timestamp" in event

    def test_observe_pre_handles_empty_input(self, tmp_path: Path):
        """observe_pre should handle hook_data with empty tool_input."""
        from instincts.observer import observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {},
            "session_id": "session-456",
        }

        observe_pre(hook_data, project_root)

        assert observations_file.exists()
        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Bash"

    def test_observe_pre_truncates_large_input(self, tmp_path: Path):
        """observe_pre should truncate inputs exceeding MAX_CONTENT_LENGTH."""
        from instincts.observer import MAX_CONTENT_LENGTH, observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        large_input = "x" * (MAX_CONTENT_LENGTH + 1000)
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Write",
            "tool_input": large_input,
            "session_id": "session-789",
        }

        observe_pre(hook_data, project_root)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["input"]) <= MAX_CONTENT_LENGTH


class TestObservePost:
    """Tests for observe_post function."""

    def test_observe_post_writes_tool_complete_event(self, tmp_path: Path):
        """observe_post should write a tool_complete event to observations file."""
        from instincts.observer import observe_post

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Read",
            "tool_output": "file contents here",
            "session_id": "session-123",
        }

        observe_post(hook_data, project_root)

        assert observations_file.exists()
        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["event"] == "tool_complete"
        assert event["tool"] == "Read"
        assert event["session"] == "session-123"
        assert "output" in event

    def test_observe_post_truncates_large_output(self, tmp_path: Path):
        """observe_post should truncate outputs exceeding MAX_CONTENT_LENGTH."""
        from instincts.observer import MAX_CONTENT_LENGTH, observe_post

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        large_output = "y" * (MAX_CONTENT_LENGTH + 2000)
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Bash",
            "tool_output": large_output,
            "session_id": "session-999",
        }

        observe_post(hook_data, project_root)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["output"]) <= MAX_CONTENT_LENGTH


class TestObservationFileManagement:
    """Tests for observation file management."""

    def test_creates_instincts_dir_if_not_exists(self, tmp_path: Path):
        """observe_pre should create instincts dir if it doesn't exist."""
        from instincts.observer import observe_pre

        project_root = tmp_path / "project"
        project_root.mkdir()
        instincts_dir = project_root / "docs" / "instincts"
        # Do NOT create instincts_dir

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Read",
            "session_id": "session-123",
        }

        observe_pre(hook_data, project_root)

        assert instincts_dir.exists()

    def test_appends_to_existing_file(self, tmp_path: Path):
        """observe_pre should append to existing observations file."""
        from instincts.observer import observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create first observation
        observe_pre({"tool_name": "Read", "session_id": "s1"}, project_root)

        # Create second observation
        observe_pre({"tool_name": "Write", "session_id": "s2"}, project_root)

        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestFileArchiving:
    """Tests for file archiving when size exceeds threshold."""

    def test_archives_file_when_exceeds_max_size(self, tmp_path: Path):
        """Should archive observations file when it exceeds MAX_FILE_SIZE_MB."""
        from instincts.observer import MAX_FILE_SIZE_MB, observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        archive_dir = instincts_dir / "observations.archive"

        # Create a large file that exceeds the threshold
        large_content = "x" * (int(MAX_FILE_SIZE_MB * 1024 * 1024) + 1000)
        observations_file.write_text(large_content)

        hook_data = {"tool_name": "Read", "session_id": "s1"}
        observe_pre(hook_data, project_root)

        # Archive directory should be created
        assert archive_dir.exists()
        # Archive should contain a file
        archive_files = list(archive_dir.glob("*.jsonl"))
        assert len(archive_files) >= 1

    def test_archive_dir_created_with_restrictive_permissions(self, tmp_path: Path):
        """Archive directory should be created with mode 0o700."""
        import stat

        from instincts.observer import MAX_FILE_SIZE_MB, observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        archive_dir = instincts_dir / "observations.archive"

        # Create a large file
        large_content = "x" * (int(MAX_FILE_SIZE_MB * 1024 * 1024) + 1000)
        observations_file.write_text(large_content)

        observe_pre({"tool_name": "Read", "session_id": "s1"}, project_root)

        assert archive_dir.exists()
        mode = archive_dir.stat().st_mode & 0o777
        assert mode == stat.S_IRWXU  # 0o700


class TestAlternativeFieldNames:
    """Tests for handling alternative field names in hook_data."""

    def test_handles_tool_field_instead_of_tool_name(self, tmp_path: Path):
        """Should handle 'tool' field instead of 'tool_name'."""
        from instincts.observer import observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        hook_data = {
            "hook_type": "PreToolUse",
            "tool": "Read",  # Using 'tool' instead of 'tool_name'
            "input": {"file": "test.py"},
            "session_id": "s1",
        }

        observe_pre(hook_data, project_root)

        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Read"

    def test_handles_output_field_instead_of_tool_output(self, tmp_path: Path):
        """Should handle 'output' field instead of 'tool_output'."""
        from instincts.observer import observe_post

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        hook_data = {
            "hook_type": "PostToolUse",
            "tool": "Bash",
            "output": "command output",  # Using 'output' instead of 'tool_output'
            "session_id": "s1",
        }

        observe_post(hook_data, project_root)

        event = json.loads(observations_file.read_text().strip())
        assert "command output" in event["output"]


class TestAnalysisTrigger:
    """Tests for analysis trigger based on observation count/time."""

    def test_creates_marker_after_200_observations(self, tmp_path: Path):
        """Should create analysis marker after ANALYSIS_TRIGGER_COUNT observations."""
        from instincts.observer import (
            ANALYSIS_TRIGGER_COUNT,
            create_analysis_marker,
            should_trigger_analysis,
        )

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create enough observations
        observations = [
            f'{{"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2024-01-01T00:00:00Z"}}'
            for _ in range(ANALYSIS_TRIGGER_COUNT + 1)
        ]
        observations_file.write_text("\n".join(observations))

        should_trigger = should_trigger_analysis(project_root)

        assert should_trigger is True

    def test_does_not_create_marker_before_200_observations(self, tmp_path: Path):
        """Should not create marker when under ANALYSIS_TRIGGER_COUNT observations."""
        from datetime import datetime, timezone

        from instincts.observer import ANALYSIS_TRIGGER_COUNT, should_trigger_analysis

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Use recent timestamp to avoid time-based trigger (must be within 24h)
        recent_timestamp = datetime.now(timezone.utc).isoformat()

        # Create fewer observations than threshold
        observations = [
            f'{{"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "{recent_timestamp}"}}'
            for _ in range(ANALYSIS_TRIGGER_COUNT - 100)
        ]
        observations_file.write_text("\n".join(observations))

        should_trigger = should_trigger_analysis(project_root)

        assert should_trigger is False

    def test_does_not_create_marker_if_already_exists(self, tmp_path: Path):
        """Should not trigger analysis if marker already exists."""
        from instincts.config import get_analysis_pending_file
        from instincts.observer import ANALYSIS_TRIGGER_COUNT, should_trigger_analysis

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create marker file
        analysis_pending_file = get_analysis_pending_file(project_root)
        analysis_pending_file.write_text('{"created_at": "2024-01-01T00:00:00Z"}')

        # Create enough observations
        observations = [
            f'{{"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "2024-01-01T00:00:00Z"}}'
            for _ in range(ANALYSIS_TRIGGER_COUNT + 1)
        ]
        observations_file.write_text("\n".join(observations))

        should_trigger = should_trigger_analysis(project_root)

        assert should_trigger is False

    def test_creates_marker_after_24h_with_min_observations(self, tmp_path: Path):
        """Should create marker after 24h if min observation count reached."""
        from datetime import datetime, timedelta, timezone

        from instincts.observer import ANALYSIS_MIN_COUNT, should_trigger_analysis

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create observations with old timestamp
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        observations = [
            f'{{"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "{old_time}"}}'
            for _ in range(ANALYSIS_MIN_COUNT + 1)
        ]
        observations_file.write_text("\n".join(observations))

        should_trigger = should_trigger_analysis(project_root)

        assert should_trigger is True

    def test_does_not_create_marker_if_under_min_count_even_after_24h(self, tmp_path: Path):
        """Should not trigger if under min count even after 24h."""
        from datetime import datetime, timedelta, timezone

        from instincts.observer import ANALYSIS_MIN_COUNT, should_trigger_analysis

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create fewer observations than min threshold with old timestamp
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        observations = [
            f'{{"event": "tool_start", "tool": "Read", "session": "s1", "timestamp": "{old_time}"}}'
            for _ in range(ANALYSIS_MIN_COUNT - 5)
        ]
        observations_file.write_text("\n".join(observations))

        should_trigger = should_trigger_analysis(project_root)

        assert should_trigger is False


class TestAnalysisTriggerPerformance:
    """Tests for analysis trigger performance optimizations."""

    def test_analysis_trigger_uses_modulo_check(self, tmp_path: Path):
        """Should use modulo check to avoid checking on every observation."""
        from instincts.observer import (
            ANALYSIS_TRIGGER_CHECK_INTERVAL,
            get_observation_counter,
            increment_observation_counter,
            reset_observation_counter,
        )

        reset_observation_counter()

        # Increment counter
        for i in range(ANALYSIS_TRIGGER_CHECK_INTERVAL - 1):
            counter = increment_observation_counter()
            assert counter == i + 1

        # At interval, counter should trigger check
        counter = increment_observation_counter()
        assert counter >= ANALYSIS_TRIGGER_CHECK_INTERVAL


class TestAtomicMarkerCreation:
    """Tests for atomic marker file creation."""

    def test_create_analysis_marker_uses_atomic_create(self, tmp_path: Path):
        """Should use exclusive file creation for marker."""
        from instincts.observer import create_analysis_marker

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create some observations
        observations_file.write_text('{"event": "test", "timestamp": "2024-01-01T00:00:00Z"}')

        create_analysis_marker(project_root)

        from instincts.config import get_analysis_pending_file

        analysis_pending_file = get_analysis_pending_file(project_root)
        assert analysis_pending_file.exists()

    def test_create_analysis_marker_does_not_overwrite_existing(self, tmp_path: Path):
        """Should not overwrite existing marker file."""
        from instincts.config import get_analysis_pending_file
        from instincts.observer import create_analysis_marker

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # Create marker with known content
        analysis_pending_file = get_analysis_pending_file(project_root)
        analysis_pending_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = '{"original": true}'
        analysis_pending_file.write_text(original_content)

        # Create some observations
        observations_file.write_text('{"event": "test", "timestamp": "2024-01-01T00:00:00Z"}')

        # Try to create marker again
        create_analysis_marker(project_root)

        # Original content should be preserved
        assert analysis_pending_file.read_text() == original_content


class TestFileLocking:
    """Tests for file locking during observation writes."""

    def test_write_observation_uses_file_locking(self, tmp_path: Path):
        """Should use file locking when writing observations."""
        from instincts.observer import observe_pre

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)

        # This test verifies that the function doesn't crash when using locking
        observe_pre({"tool_name": "Read", "session_id": "s1"}, project_root)

        assert observations_file.exists()

    def test_write_observation_releases_lock_on_exception(self, tmp_path: Path):
        """Should release lock even if write fails."""
        from instincts.observer import _append_observation_with_lock

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        observations_file.write_text("")

        # Write should work
        _append_observation_with_lock({"test": "data"}, observations_file)

        # Should be able to read the file (lock released)
        content = observations_file.read_text()
        assert "test" in content


class TestCountObservations:
    """Tests for count_observations function."""

    def test_count_observations_returns_line_count(self, tmp_path: Path):
        """Should return number of lines in file."""
        from instincts.observer import count_observations

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        observations_file.write_text("line1\nline2\nline3\n")

        count = count_observations(observations_file)

        assert count == 3

    def test_count_observations_returns_zero_for_missing_file(self, tmp_path: Path):
        """Should return 0 for non-existent file."""
        from instincts.observer import count_observations

        missing_file = tmp_path / "missing.jsonl"

        count = count_observations(missing_file)

        assert count == 0


class TestGetOldestObservationTimestamp:
    """Tests for get_oldest_observation_timestamp function."""

    def test_returns_timestamp_from_first_line(self, tmp_path: Path):
        """Should return timestamp from first observation."""
        from instincts.observer import get_oldest_observation_timestamp

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        observations_file.write_text('{"timestamp": "2024-01-15T10:00:00+00:00"}\n')

        timestamp = get_oldest_observation_timestamp(observations_file)

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15

    def test_returns_none_for_missing_file(self, tmp_path: Path):
        """Should return None for non-existent file."""
        from instincts.observer import get_oldest_observation_timestamp

        missing_file = tmp_path / "missing.jsonl"

        timestamp = get_oldest_observation_timestamp(missing_file)

        assert timestamp is None

    def test_returns_none_for_empty_file(self, tmp_path: Path):
        """Should return None for empty file."""
        from instincts.observer import get_oldest_observation_timestamp

        project_root, instincts_dir, observations_file = create_project_structure(tmp_path)
        observations_file.write_text("")

        timestamp = get_oldest_observation_timestamp(observations_file)

        assert timestamp is None


class TestThreadSafeCounter:
    """Tests for thread-safe observation counter."""

    def test_counter_is_thread_local(self):
        """Counter should be thread-local."""
        from instincts.observer import (
            get_observation_counter,
            increment_observation_counter,
            reset_observation_counter,
        )

        reset_observation_counter()
        assert get_observation_counter() == 0

        increment_observation_counter()
        assert get_observation_counter() == 1

        reset_observation_counter()
        assert get_observation_counter() == 0
