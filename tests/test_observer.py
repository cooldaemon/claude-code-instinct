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


class TestObservePre:
    """Tests for observe_pre function."""

    def test_observe_pre_writes_tool_start_event(self, tmp_path: Path):
        """observe_pre should write a tool_start event to observations file."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "session_id": "session-123",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

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

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {},
            "session_id": "session-456",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Bash"

    def test_observe_pre_truncates_large_input(self, tmp_path: Path):
        """observe_pre should truncate tool_input larger than 5000 chars."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        large_content = "x" * 10000
        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"content": large_content},
            "session_id": "session-789",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["input"]) <= 5000


class TestObservePost:
    """Tests for observe_post function."""

    def test_observe_post_writes_tool_complete_event(self, tmp_path: Path):
        """observe_post should write a tool_complete event to observations file."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Bash",
            "tool_output": "Hello, World!",
            "session_id": "session-123",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        assert observations_file.exists()
        event = json.loads(observations_file.read_text().strip())
        assert event["event"] == "tool_complete"
        assert event["tool"] == "Bash"
        assert event["session"] == "session-123"
        assert "output" in event
        assert "timestamp" in event

    def test_observe_post_truncates_large_output(self, tmp_path: Path):
        """observe_post should truncate tool_output larger than 5000 chars."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        large_output = "y" * 10000
        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Read",
            "tool_output": large_output,
            "session_id": "session-456",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert len(event["output"]) <= 5000


class TestObservationFileManagement:
    """Tests for observation file management."""

    def test_creates_instincts_dir_if_not_exists(self, tmp_path: Path):
        """observe_pre should create INSTINCTS_DIR if it doesn't exist."""
        from instincts.observer import observe_pre

        instincts_dir = tmp_path / "new_dir"
        observations_file = instincts_dir / "observations.jsonl"

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Test",
            "tool_input": {},
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", instincts_dir):
                observe_pre(hook_data)

        assert instincts_dir.exists()
        assert observations_file.exists()

    def test_appends_to_existing_file(self, tmp_path: Path):
        """Multiple observations should append to the same file."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre({
                    "hook_type": "PreToolUse",
                    "tool_name": "Tool1",
                    "tool_input": {},
                    "session_id": "s1",
                })
                observe_pre({
                    "hook_type": "PreToolUse",
                    "tool_name": "Tool2",
                    "tool_input": {},
                    "session_id": "s1",
                })

        lines = observations_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestFileArchiving:
    """Tests for file archiving when size exceeds threshold."""

    def test_archives_file_when_exceeds_max_size(self, tmp_path: Path):
        """Should archive observations file when it exceeds MAX_FILE_SIZE_MB."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        archive_dir = tmp_path / "observations.archive"

        # Create a file larger than 1MB (use small threshold for testing)
        observations_file.write_text("x" * (1024 * 1024 + 1))  # 1MB + 1 byte

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Test",
            "tool_input": {},
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ARCHIVE_DIR", archive_dir):
                    with patch("instincts.observer.MAX_FILE_SIZE_MB", 1):
                        observe_pre(hook_data)

        # Archive directory should be created
        assert archive_dir.exists()
        # Old file should be moved to archive
        archived_files = list(archive_dir.glob("observations-*.jsonl"))
        assert len(archived_files) == 1
        # New observation should be in fresh file
        assert observations_file.exists()
        new_content = observations_file.read_text()
        assert "Test" in new_content

    def test_archive_dir_created_with_restrictive_permissions(self, tmp_path: Path):
        """Archive directory should be created with mode 0o700."""
        import stat

        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        archive_dir = tmp_path / "observations.archive"

        # Create a file larger than 1MB (use small threshold for testing)
        observations_file.write_text("x" * (1024 * 1024 + 1))  # 1MB + 1 byte

        hook_data = {
            "hook_type": "PreToolUse",
            "tool_name": "Test",
            "tool_input": {},
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ARCHIVE_DIR", archive_dir):
                    with patch("instincts.observer.MAX_FILE_SIZE_MB", 1):
                        observe_pre(hook_data)

        # Archive directory should have restrictive permissions
        expected_mode = stat.S_IRWXU  # 0o700
        actual_mode = archive_dir.stat().st_mode & 0o777
        assert actual_mode == expected_mode, (
            f"Archive dir has mode {oct(actual_mode)}, expected {oct(expected_mode)}"
        )


class TestAlternativeFieldNames:
    """Tests for handling alternative field names in hook_data."""

    def test_handles_tool_field_instead_of_tool_name(self, tmp_path: Path):
        """Should handle 'tool' field as alternative to 'tool_name'."""
        from instincts.observer import observe_pre

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PreToolUse",
            "tool": "Read",  # Alternative field name
            "input": {"path": "/tmp"},  # Alternative field name
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_pre(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["tool"] == "Read"

    def test_handles_output_field_instead_of_tool_output(self, tmp_path: Path):
        """Should handle 'output' field as alternative to 'tool_output'."""
        from instincts.observer import observe_post

        observations_file = tmp_path / "observations.jsonl"
        hook_data = {
            "hook_type": "PostToolUse",
            "tool": "Bash",
            "output": "result",  # Alternative field name
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                observe_post(hook_data)

        event = json.loads(observations_file.read_text().strip())
        assert event["output"] == "result"


class TestAnalysisTrigger:
    """Tests for auto-trigger pattern analysis (AC-R1.1 to AC-R1.4)."""

    def test_creates_marker_after_200_observations(self, tmp_path: Path):
        """AC-R1.1: Should create .analysis_pending marker after 200 observations."""
        import instincts.observer as observer_module
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create 199 existing observations
        with observations_file.open("w") as f:
            for i in range(199):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}"}}\n')

        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Test200",
            "tool_output": "done",
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    # Reset counter to ensure check runs on interval boundary
                    observer_module._observation_counter = ANALYSIS_TRIGGER_CHECK_INTERVAL - 1
                    observe_post(hook_data)

        # Marker should be created (199 + 1 = 200)
        assert marker_file.exists()

    def test_does_not_create_marker_before_200_observations(self, tmp_path: Path):
        """Should not create marker when observation count < 200."""
        import instincts.observer as observer_module
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create 98 existing observations
        with observations_file.open("w") as f:
            for i in range(98):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}"}}\n')

        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Test99",
            "tool_output": "done",
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    # Reset counter to ensure check runs on interval boundary
                    observer_module._observation_counter = ANALYSIS_TRIGGER_CHECK_INTERVAL - 1
                    observe_post(hook_data)

        # Marker should not be created (98 + 1 = 99)
        assert not marker_file.exists()

    def test_does_not_create_marker_if_already_exists(self, tmp_path: Path):
        """AC-R1.4: Should not create new marker if one already exists."""
        import instincts.observer as observer_module
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create marker with existing content
        marker_file.write_text('{"created_at": "2024-01-01T00:00:00Z"}')
        original_content = marker_file.read_text()

        # Create 199 existing observations
        with observations_file.open("w") as f:
            for i in range(199):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}"}}\n')

        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Test200",
            "tool_output": "done",
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    # Reset counter to ensure check runs on interval boundary
                    observer_module._observation_counter = ANALYSIS_TRIGGER_CHECK_INTERVAL - 1
                    observe_post(hook_data)

        # Marker content should not change
        assert marker_file.read_text() == original_content

    def test_creates_marker_after_24h_with_min_observations(self, tmp_path: Path):
        """AC-R1.2: Should create marker after 24h elapsed with 20+ observations."""
        from datetime import datetime, timedelta, timezone

        import instincts.observer as observer_module
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create 19 observations with timestamps > 24h ago
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with observations_file.open("w") as f:
            for i in range(19):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}", "timestamp": "{old_timestamp}"}}\n')

        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Test20",
            "tool_output": "done",
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    # Reset counter to ensure check runs on interval boundary
                    observer_module._observation_counter = ANALYSIS_TRIGGER_CHECK_INTERVAL - 1
                    observe_post(hook_data)

        # Marker should be created (19 + 1 = 20, elapsed > 24h)
        assert marker_file.exists()

    def test_does_not_create_marker_if_under_min_count_even_after_24h(self, tmp_path: Path):
        """Should not create marker after 24h if observation count < 20."""
        from datetime import datetime, timedelta, timezone

        import instincts.observer as observer_module
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create 18 observations with timestamps > 24h ago
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with observations_file.open("w") as f:
            for i in range(18):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}", "timestamp": "{old_timestamp}"}}\n')

        hook_data = {
            "hook_type": "PostToolUse",
            "tool_name": "Test19",
            "tool_output": "done",
            "session_id": "test",
        }

        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    # Reset counter to ensure check runs on interval boundary
                    observer_module._observation_counter = ANALYSIS_TRIGGER_CHECK_INTERVAL - 1
                    observe_post(hook_data)

        # Marker should not be created (18 + 1 = 19 < 20)
        assert not marker_file.exists()


class TestObservationCounting:
    """Tests for observation counting functions."""

    def test_count_observations_returns_line_count(self, tmp_path: Path):
        """count_observations should return number of lines in file."""
        from instincts.observer import count_observations

        observations_file = tmp_path / "observations.jsonl"
        with observations_file.open("w") as f:
            for i in range(50):
                f.write(f'{{"event": "test{i}"}}\n')

        count = count_observations(observations_file)
        assert count == 50

    def test_count_observations_returns_zero_for_missing_file(self, tmp_path: Path):
        """count_observations should return 0 if file doesn't exist."""
        from instincts.observer import count_observations

        observations_file = tmp_path / "nonexistent.jsonl"
        count = count_observations(observations_file)
        assert count == 0

    def test_get_oldest_observation_timestamp(self, tmp_path: Path):
        """get_oldest_observation_timestamp should return timestamp of first line."""
        from datetime import datetime

        from instincts.observer import get_oldest_observation_timestamp

        observations_file = tmp_path / "observations.jsonl"
        old_ts = "2024-01-01T00:00:00+00:00"
        with observations_file.open("w") as f:
            f.write(f'{{"timestamp": "{old_ts}"}}\n')
            f.write('{"timestamp": "2024-06-01T00:00:00+00:00"}\n')

        timestamp = get_oldest_observation_timestamp(observations_file)
        assert timestamp == datetime.fromisoformat(old_ts)

    def test_get_oldest_observation_timestamp_returns_none_for_missing_file(
        self, tmp_path: Path
    ):
        """get_oldest_observation_timestamp should return None if file doesn't exist."""
        from instincts.observer import get_oldest_observation_timestamp

        observations_file = tmp_path / "nonexistent.jsonl"
        timestamp = get_oldest_observation_timestamp(observations_file)
        assert timestamp is None


class TestAnalysisTriggerPerformance:
    """Tests for performance optimization in analysis trigger checking."""

    def test_analysis_trigger_uses_modulo_check(self, tmp_path: Path):
        """Analysis trigger check should only run every N observations for performance."""
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL, observe_post

        observations_file = tmp_path / "observations.jsonl"
        marker_file = tmp_path / ".analysis_pending"

        # Create some existing observations
        with observations_file.open("w") as f:
            for i in range(5):
                f.write(f'{{"event": "tool_complete", "tool": "Test{i}"}}\n')

        # Track calls to count_observations
        with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
            with patch("instincts.observer.INSTINCTS_DIR", tmp_path):
                with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
                    with patch("instincts.observer.count_observations") as mock_count:
                        mock_count.return_value = 10  # Below threshold

                        # Call observe_post multiple times
                        for i in range(ANALYSIS_TRIGGER_CHECK_INTERVAL + 1):
                            hook_data = {
                                "hook_type": "PostToolUse",
                                "tool_name": f"Test{i}",
                                "tool_output": "done",
                                "session_id": "test",
                            }
                            observe_post(hook_data)

                        # count_observations should be called only when counter hits interval
                        # First call at interval boundary
                        assert mock_count.call_count <= 2

    def test_analysis_trigger_check_interval_constant(self):
        """Should have ANALYSIS_TRIGGER_CHECK_INTERVAL constant."""
        from instincts.observer import ANALYSIS_TRIGGER_CHECK_INTERVAL

        # Should be a reasonable interval to reduce file reads
        assert ANALYSIS_TRIGGER_CHECK_INTERVAL >= 10


class TestAtomicMarkerCreation:
    """Tests for atomic marker file creation to avoid race conditions."""

    def test_create_analysis_marker_uses_atomic_create(self, tmp_path: Path):
        """Marker creation should use atomic file create (exclusive mode)."""
        from instincts.observer import _create_analysis_marker

        marker_file = tmp_path / ".analysis_pending"
        observations_file = tmp_path / "observations.jsonl"
        observations_file.write_text('{"event": "test"}\n')

        with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
            with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
                _create_analysis_marker()

        assert marker_file.exists()

    def test_create_analysis_marker_does_not_overwrite_existing(self, tmp_path: Path):
        """Marker creation should not overwrite existing marker (race condition safe)."""
        from instincts.observer import _create_analysis_marker

        marker_file = tmp_path / ".analysis_pending"
        observations_file = tmp_path / "observations.jsonl"
        observations_file.write_text('{"event": "test"}\n')

        # Pre-create marker with specific content
        original_content = '{"created_at": "original"}'
        marker_file.write_text(original_content)

        with patch("instincts.observer.ANALYSIS_PENDING_FILE", marker_file):
            with patch("instincts.observer.OBSERVATIONS_FILE", observations_file):
                _create_analysis_marker()

        # Original content should be preserved (not overwritten)
        assert marker_file.read_text() == original_content
